"""Pre-generation context validation for GM responses.

Validates entity references, location references, fact consistency,
and temporal consistency BEFORE persisting to prevent hallucinations
and contradictions.
"""

import re
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy.orm import Session

from src.database.models.entities import Entity
from src.database.models.enums import EntityType
from src.database.models.session import GameSession
from src.database.models.world import Fact, Location, TimeState
from src.managers.base import BaseManager


@dataclass
class ValidationIssue:
    """A detected validation problem."""

    category: Literal["entity", "location", "fact", "time", "role"]
    severity: Literal["warning", "error"]
    description: str
    entity_key: str | None = None
    location_key: str | None = None
    suggested_fix: str | None = None


@dataclass
class ValidationResult:
    """Result of validation check(s)."""

    is_valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_issue(self, issue: ValidationIssue) -> None:
        """Add an issue and mark invalid if error severity."""
        self.issues.append(issue)
        if issue.severity == "error":
            self.is_valid = False

    def add_warning(self, warning: str) -> None:
        """Add a warning (does not invalidate)."""
        self.warnings.append(warning)

    def merge(self, other: "ValidationResult") -> None:
        """Merge another result into this one."""
        if not other.is_valid:
            self.is_valid = False
        self.issues.extend(other.issues)
        self.warnings.extend(other.warnings)


# Unique roles that should only have one occupant per location
UNIQUE_ROLES = {
    "mayor", "king", "queen", "captain_of_guard", "high_priest",
    "guild_master", "chief", "headmaster", "sheriff",
}

# Time of day indicators in text
DAYLIGHT_INDICATORS = [
    r"\bsun\b", r"\bsunny\b", r"\bsunlight\b", r"\bsunshine\b",
    r"\bafternoon\b", r"\bnoon\b", r"\bmidday\b", r"\bdaylight\b",
    r"\bmorning sun\b", r"\bbright day\b",
]
NIGHTTIME_INDICATORS = [
    r"\bmoon\b", r"\bmoonlight\b", r"\bstars\b", r"\bstarlight\b",
    r"\bmidnight\b", r"\bnight sky\b", r"\bdark night\b",
]

# Weather indicators
CLEAR_SKY_INDICATORS = [
    r"\bclear sky\b", r"\bblue sky\b", r"\bcloudless\b",
    r"\bbright sun\b", r"\bsunshine\b",
]
RAIN_INDICATORS = [
    r"\brain\b", r"\braining\b", r"\bdownpour\b", r"\bstorm\b",
    r"\bthunder\b", r"\blightning\b", r"\bpour\b",
]


class ContextValidator(BaseManager):
    """Validates context before GM content generation.

    Provides pre-generation validation to catch:
    - References to non-existent entities
    - References to unknown locations
    - Contradictions with existing facts
    - Time/weather inconsistencies
    - Duplicate unique roles (e.g., two mayors)
    """

    def validate_entity_reference(self, entity_key: str) -> ValidationResult:
        """Validate that an entity reference exists.

        Args:
            entity_key: Entity key to validate.

        Returns:
            ValidationResult indicating if entity exists.
        """
        result = ValidationResult(is_valid=True)

        # Special case: "player" always refers to player entity
        if entity_key == "player":
            player = (
                self.db.query(Entity)
                .filter(
                    Entity.session_id == self.session_id,
                    Entity.entity_type == EntityType.PLAYER,
                )
                .first()
            )
            if player is None:
                result.add_issue(
                    ValidationIssue(
                        category="entity",
                        severity="error",
                        description="No player entity exists in this session",
                        entity_key=entity_key,
                    )
                )
            return result

        # Check if entity exists
        entity = (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.session_id,
                Entity.entity_key == entity_key,
            )
            .first()
        )

        if entity is None:
            result.add_issue(
                ValidationIssue(
                    category="entity",
                    severity="error",
                    description=f"Entity '{entity_key}' does not exist",
                    entity_key=entity_key,
                    suggested_fix="Create the entity first or use an existing entity key",
                )
            )

        return result

    def validate_entity_references(self, entity_keys: list[str]) -> ValidationResult:
        """Validate multiple entity references.

        Args:
            entity_keys: List of entity keys to validate.

        Returns:
            ValidationResult with all issues found.
        """
        result = ValidationResult(is_valid=True)

        for key in entity_keys:
            single_result = self.validate_entity_reference(key)
            result.merge(single_result)

        return result

    def validate_location_reference(
        self,
        location_key: str,
        allow_new: bool = False,
    ) -> ValidationResult:
        """Validate that a location reference exists or is allowed.

        Args:
            location_key: Location key to validate.
            allow_new: If True, allow new locations with a warning.

        Returns:
            ValidationResult indicating if location is valid.
        """
        result = ValidationResult(is_valid=True)

        location = (
            self.db.query(Location)
            .filter(
                Location.session_id == self.session_id,
                Location.location_key == location_key,
            )
            .first()
        )

        if location is None:
            if allow_new:
                result.add_warning(
                    f"Location '{location_key}' is new and will be created"
                )
            else:
                result.add_issue(
                    ValidationIssue(
                        category="location",
                        severity="error",
                        description=f"Location '{location_key}' does not exist",
                        location_key=location_key,
                        suggested_fix="Create the location first or use an existing location key",
                    )
                )

        return result

    def validate_fact_consistency(
        self,
        subject_key: str,
        predicate: str,
        value: str,
        allow_update: bool = False,
    ) -> ValidationResult:
        """Validate that a new fact doesn't contradict existing facts.

        Args:
            subject_key: Subject of the fact.
            predicate: Predicate (aspect being described).
            value: New value.
            allow_update: If True, allow updates to mutable facts.

        Returns:
            ValidationResult indicating if fact is consistent.
        """
        result = ValidationResult(is_valid=True)

        existing = (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.session_id,
                Fact.subject_key == subject_key,
                Fact.predicate == predicate,
            )
            .first()
        )

        if existing is not None and existing.value != value:
            if allow_update:
                result.add_warning(
                    f"Fact '{subject_key}.{predicate}' will be updated "
                    f"from '{existing.value}' to '{value}'"
                )
            else:
                result.add_issue(
                    ValidationIssue(
                        category="fact",
                        severity="error",
                        description=(
                            f"Contradiction: '{subject_key}.{predicate}' is already "
                            f"'{existing.value}', cannot set to '{value}'"
                        ),
                        entity_key=subject_key,
                        suggested_fix=f"Use existing value '{existing.value}' or explicitly update the fact",
                    )
                )

        return result

    def validate_time_consistency(self, description: str) -> ValidationResult:
        """Validate that a description is consistent with current time/weather.

        Args:
            description: Narrative description to check.

        Returns:
            ValidationResult indicating if description is time-consistent.
        """
        result = ValidationResult(is_valid=True)

        # Get current time state
        time_state = (
            self.db.query(TimeState)
            .filter(TimeState.session_id == self.session_id)
            .first()
        )

        if time_state is None:
            # No time state, can't validate
            return result

        # Parse hour from current_time
        try:
            hour = int(time_state.current_time.split(":")[0])
        except (ValueError, IndexError, AttributeError):
            return result

        description_lower = description.lower()

        # Check daylight indicators at night (night = 21:00 - 05:00)
        is_night = hour >= 21 or hour < 5

        if is_night:
            for pattern in DAYLIGHT_INDICATORS:
                if re.search(pattern, description_lower):
                    result.add_issue(
                        ValidationIssue(
                            category="time",
                            severity="error",
                            description=(
                                f"Time inconsistency: Current time is {time_state.current_time} (night) "
                                f"but description mentions daylight/sun"
                            ),
                            suggested_fix=f"Remove daylight references or advance time to daytime",
                        )
                    )
                    break
        else:
            # Check nighttime indicators during day
            for pattern in NIGHTTIME_INDICATORS:
                if re.search(pattern, description_lower):
                    result.add_issue(
                        ValidationIssue(
                            category="time",
                            severity="error",
                            description=(
                                f"Time inconsistency: Current time is {time_state.current_time} (day) "
                                f"but description mentions nighttime elements"
                            ),
                            suggested_fix=f"Remove nighttime references or advance time to night",
                        )
                    )
                    break

        # Check weather consistency
        weather = time_state.weather
        if weather:
            weather_lower = weather.lower()

            # Check for clear sky mentioned during rain
            if "rain" in weather_lower or "storm" in weather_lower:
                for pattern in CLEAR_SKY_INDICATORS:
                    if re.search(pattern, description_lower):
                        result.add_issue(
                            ValidationIssue(
                                category="time",
                                severity="error",
                                description=(
                                    f"Weather inconsistency: Current weather is '{weather}' "
                                    f"but description mentions clear sky"
                                ),
                                suggested_fix=f"Update description to match weather or change weather state",
                            )
                        )
                        break

            # Check for rain mentioned during clear weather
            if "clear" in weather_lower or "sunny" in weather_lower:
                for pattern in RAIN_INDICATORS:
                    if re.search(pattern, description_lower):
                        result.add_issue(
                            ValidationIssue(
                                category="time",
                                severity="error",
                                description=(
                                    f"Weather inconsistency: Current weather is '{weather}' "
                                    f"but description mentions rain/storm"
                                ),
                                suggested_fix=f"Update description to match weather or change weather state",
                            )
                        )
                        break

        return result

    def validate_unique_role(
        self,
        entity_key: str,
        role: str,
        location_key: str | None = None,
    ) -> ValidationResult:
        """Validate that a unique role isn't already taken.

        Args:
            entity_key: Entity key being assigned the role.
            role: Role being assigned (e.g., 'mayor').
            location_key: Location scope for the role.

        Returns:
            ValidationResult indicating if role assignment is valid.
        """
        result = ValidationResult(is_valid=True)

        role_lower = role.lower()
        if role_lower not in UNIQUE_ROLES:
            # Not a unique role, no validation needed
            return result

        # Find existing holder of this role
        existing_role_facts = (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.session_id,
                Fact.predicate == "occupation",
                Fact.value.ilike(f"%{role_lower}%"),
            )
            .all()
        )

        for fact in existing_role_facts:
            if fact.subject_key == entity_key:
                # Same entity already has the role
                continue

            # Check if same location scope
            if location_key:
                workplace_fact = (
                    self.db.query(Fact)
                    .filter(
                        Fact.session_id == self.session_id,
                        Fact.subject_key == fact.subject_key,
                        Fact.predicate.in_(["workplace", "governs", "rules"]),
                    )
                    .first()
                )
                if workplace_fact and location_key not in workplace_fact.value.lower():
                    # Different location, not a conflict
                    continue

            result.add_issue(
                ValidationIssue(
                    category="role",
                    severity="error",
                    description=(
                        f"Unique role conflict: '{fact.subject_key}' is already the {role} "
                        f"in this location"
                    ),
                    entity_key=entity_key,
                    suggested_fix=f"Use a different role or remove the existing {role}",
                )
            )
            break

        return result

    def validate_extraction(
        self,
        entity_keys: list[str],
        location_key: str | None = None,
        facts: list[dict] | None = None,
        description: str | None = None,
    ) -> ValidationResult:
        """Validate a full extraction result.

        Args:
            entity_keys: List of entity keys referenced.
            location_key: Location key if location changed.
            facts: List of fact dicts with subject_key, predicate, value.
            description: Narrative description to check for time consistency.

        Returns:
            ValidationResult with all validation issues.
        """
        result = ValidationResult(is_valid=True)

        # Validate entity references
        entity_result = self.validate_entity_references(entity_keys)
        result.merge(entity_result)

        # Validate location reference
        if location_key:
            loc_result = self.validate_location_reference(location_key)
            result.merge(loc_result)

        # Validate fact consistency
        if facts:
            for fact in facts:
                fact_result = self.validate_fact_consistency(
                    subject_key=fact.get("subject_key", ""),
                    predicate=fact.get("predicate", ""),
                    value=fact.get("value", ""),
                )
                result.merge(fact_result)

        # Validate time consistency
        if description:
            time_result = self.validate_time_consistency(description)
            result.merge(time_result)

        return result

    def get_constraint_context(self, entity_keys: list[str] | None = None) -> str:
        """Get key facts that should not be contradicted.

        Useful for adding to GM prompts as constraints.

        Args:
            entity_keys: Optional list of entity keys to get facts for.

        Returns:
            Formatted string of key facts as constraints.
        """
        lines = ["## Current Facts (DO NOT CONTRADICT)"]

        # Get time state
        time_state = (
            self.db.query(TimeState)
            .filter(TimeState.session_id == self.session_id)
            .first()
        )
        if time_state:
            lines.append(f"- Current time: {time_state.current_time}")
            if time_state.weather:
                lines.append(f"- Weather: {time_state.weather}")

        # Get key facts for entities
        if entity_keys:
            for key in entity_keys:
                facts = (
                    self.db.query(Fact)
                    .filter(
                        Fact.session_id == self.session_id,
                        Fact.subject_key == key,
                        Fact.predicate.in_([
                            "occupation", "age", "gender", "hometown",
                            "relationship_status", "is_alive",
                        ]),
                    )
                    .all()
                )
                for fact in facts:
                    lines.append(f"- {key}: {fact.predicate} = \"{fact.value}\"")

        return "\n".join(lines) if len(lines) > 1 else ""
