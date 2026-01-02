"""Validation Layer for Quantum Branching.

This module provides validation for pre-generated narratives and state
deltas. Unlike runtime validation, quantum validation happens during
branch generation to catch issues before caching.

Key validators:
- NarrativeConsistencyValidator: Validates narrative quality and grounding
- DeltaValidator: Validates state deltas are applicable
- BranchValidator: Combines both for full branch validation
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from src.database.models.session import GameSession
from src.gm.grounding import GroundingManifest
from src.gm.grounding_validator import GroundingValidator
from src.world_server.quantum.schemas import (
    DeltaType,
    OutcomeVariant,
    QuantumBranch,
    StateDelta,
)

logger = logging.getLogger(__name__)


class IssueSeverity(str, Enum):
    """Severity level for validation issues."""

    ERROR = "error"  # Must be fixed, blocks usage
    WARNING = "warning"  # Should be fixed, but usable
    INFO = "info"  # Minor issue, informational only


@dataclass
class ValidationIssue:
    """A single validation issue found during validation."""

    category: str  # e.g., "grounding", "meta", "consistency", "delta"
    message: str
    severity: IssueSeverity
    location: str | None = None  # Where in the text the issue occurred
    suggestion: str | None = None  # How to fix the issue


@dataclass
class ValidationResult:
    """Result of validating a narrative or branch."""

    valid: bool  # True if no errors (warnings are OK)
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        """Count of error-severity issues."""
        return sum(1 for i in self.issues if i.severity == IssueSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        """Count of warning-severity issues."""
        return sum(1 for i in self.issues if i.severity == IssueSeverity.WARNING)

    @property
    def errors(self) -> list[ValidationIssue]:
        """Get only error-severity issues."""
        return [i for i in self.issues if i.severity == IssueSeverity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        """Get only warning-severity issues."""
        return [i for i in self.issues if i.severity == IssueSeverity.WARNING]

    def format_issues(self) -> str:
        """Format issues for display or logging.

        Returns:
            Human-readable issue summary.
        """
        if not self.issues:
            return "No issues found."

        lines = []
        for issue in self.issues:
            prefix = {
                IssueSeverity.ERROR: "[ERROR]",
                IssueSeverity.WARNING: "[WARN]",
                IssueSeverity.INFO: "[INFO]",
            }[issue.severity]

            line = f"{prefix} [{issue.category}] {issue.message}"
            if issue.location:
                line += f" at: {issue.location}"
            if issue.suggestion:
                line += f"\n  → Suggestion: {issue.suggestion}"
            lines.append(line)

        return "\n".join(lines)


# =============================================================================
# Pattern Definitions
# =============================================================================

# Meta-questions that break immersion (LLM asking player what to do)
META_QUESTION_PATTERNS = [
    r"what would you like to do\??$",
    r"what do you do\??$",
    r"how do you respond\??$",
    r"how would you like to proceed\??$",
    r"what's your next move\??$",
    r"do you want to .+\?$",
    r"would you like to .+\?$",
    r"shall i .+\?$",
    r"should i .+\?$",
]

# AI/assistant self-identification patterns
AI_IDENTITY_PATTERNS = [
    r"\bi'?m an? (?:ai|assistant|language model)\b",
    r"\bas an? (?:ai|assistant)\b",
    r"\bi don'?t have (?:feelings|emotions|a body)\b",
    r"\bi was (?:designed|programmed|created) to\b",
]

# Third-person player references (should be second-person)
THIRD_PERSON_PATTERNS = [
    r"\bthe player\b",
    r"\bplayer's\b",
    r"\bthe character\b",
    r"\bthe protagonist\b",
]

# Patterns indicating unfinished/placeholder content
PLACEHOLDER_PATTERNS = [
    r"\[.*\.\.\.\]",  # [something...]
    r"\bTODO\b",
    r"\bFIXME\b",
    r"\bXXX\b",
    r"<.*>",  # <placeholder>
    r"\$\{.*\}",  # ${variable}
]

# Patterns indicating NPC dialogue (quotes with speech verbs)
NPC_DIALOGUE_PATTERNS = [
    r"'[^']{5,}'",  # Single-quoted speech (min 5 chars)
    r'"[^"]{5,}"',  # Double-quoted speech (min 5 chars)
    r"\b(?:says?|said|replies?|replied|asks?|asked|tells?|told|whispers?|shouts?|grunts?|mutters?|exclaims?)\b",
]

# Compile patterns for efficiency
META_QUESTION_RE = [re.compile(p, re.IGNORECASE) for p in META_QUESTION_PATTERNS]
AI_IDENTITY_RE = [re.compile(p, re.IGNORECASE) for p in AI_IDENTITY_PATTERNS]
THIRD_PERSON_RE = [re.compile(p, re.IGNORECASE) for p in THIRD_PERSON_PATTERNS]
PLACEHOLDER_RE = [re.compile(p, re.IGNORECASE) for p in PLACEHOLDER_PATTERNS]
NPC_DIALOGUE_RE = [re.compile(p, re.IGNORECASE) for p in NPC_DIALOGUE_PATTERNS]


class NarrativeConsistencyValidator:
    """Validates pre-generated narrative for consistency and quality.

    This validator checks for:
    1. Grounding issues (entity references)
    2. Meta-questions (breaking immersion)
    3. AI identity leakage
    4. Third-person references (should be second-person)
    5. Placeholder content
    6. Narrative length and quality

    Usage:
        validator = NarrativeConsistencyValidator(manifest)
        result = validator.validate(narrative)
        if not result.valid:
            # Handle errors
    """

    def __init__(
        self,
        manifest: GroundingManifest,
        min_length: int = 20,
        max_length: int = 2000,
    ):
        """Initialize the validator.

        Args:
            manifest: Grounding manifest for entity validation
            min_length: Minimum acceptable narrative length
            max_length: Maximum acceptable narrative length
        """
        self.manifest = manifest
        self.min_length = min_length
        self.max_length = max_length
        self._grounding_validator = GroundingValidator(manifest)

    def validate(self, narrative: str) -> ValidationResult:
        """Validate a narrative for consistency issues.

        Args:
            narrative: The narrative text to validate

        Returns:
            ValidationResult with any issues found
        """
        issues: list[ValidationIssue] = []

        # 1. Check for empty or too short
        if not narrative or not narrative.strip():
            issues.append(ValidationIssue(
                category="content",
                message="Narrative is empty",
                severity=IssueSeverity.ERROR,
            ))
            return ValidationResult(valid=False, issues=issues)

        # 2. Check length
        issues.extend(self._check_length(narrative))

        # 3. Grounding validation (entity references)
        issues.extend(self._check_grounding(narrative))

        # 4. NPC hallucination detection (dialogue when no NPCs present)
        issues.extend(self._check_npc_hallucination(narrative))

        # 5. Meta-question detection
        issues.extend(self._check_meta_questions(narrative))

        # 6. AI identity detection
        issues.extend(self._check_ai_identity(narrative))

        # 7. Third-person detection
        issues.extend(self._check_third_person(narrative))

        # 8. Placeholder detection
        issues.extend(self._check_placeholders(narrative))

        # 9. Narrative quality checks
        issues.extend(self._check_quality(narrative))

        # Valid if no errors
        valid = not any(i.severity == IssueSeverity.ERROR for i in issues)

        return ValidationResult(valid=valid, issues=issues)

    def _check_length(self, narrative: str) -> list[ValidationIssue]:
        """Check narrative length."""
        issues = []
        length = len(narrative.strip())

        if length < self.min_length:
            issues.append(ValidationIssue(
                category="length",
                message=f"Narrative too short ({length} chars, min {self.min_length})",
                severity=IssueSeverity.WARNING,
            ))

        if length > self.max_length:
            issues.append(ValidationIssue(
                category="length",
                message=f"Narrative too long ({length} chars, max {self.max_length})",
                severity=IssueSeverity.WARNING,
                suggestion="Consider breaking into multiple turns or summarizing",
            ))

        return issues

    def _check_grounding(self, narrative: str) -> list[ValidationIssue]:
        """Check entity reference grounding."""
        issues = []

        result = self._grounding_validator.validate(narrative)

        for invalid_key in result.invalid_keys:
            similar = self.manifest.find_similar_key(invalid_key.key)
            suggestion = f"Did you mean '{similar}'?" if similar else None

            issues.append(ValidationIssue(
                category="grounding",
                message=f"Invalid entity key: [{invalid_key.key}:{invalid_key.text}]",
                severity=IssueSeverity.ERROR,
                location=invalid_key.context,
                suggestion=suggestion,
            ))

        for unkeyed in result.unkeyed_mentions:
            issues.append(ValidationIssue(
                category="grounding",
                message=f"Entity mentioned without [key:text] format: '{unkeyed.display_name}'",
                severity=IssueSeverity.WARNING,
                location=unkeyed.context,
                suggestion=f"Use [{unkeyed.expected_key}:{unkeyed.display_name}]",
            ))

        return issues

    def _check_npc_hallucination(self, narrative: str) -> list[ValidationIssue]:
        """Check for NPC dialogue when no NPCs are present.

        If the manifest has no NPCs at the location, but the narrative contains
        dialogue patterns (quotes, speech verbs), this indicates the LLM hallucinated
        an NPC interaction.
        """
        issues = []

        # Only check if there are NO NPCs in the manifest
        if self.manifest.npcs:
            return issues  # NPCs present, dialogue is OK

        # Check for dialogue patterns
        for pattern in NPC_DIALOGUE_RE:
            match = pattern.search(narrative)
            if match:
                issues.append(ValidationIssue(
                    category="npc_hallucination",
                    message="NPC dialogue detected but no NPCs are at this location",
                    severity=IssueSeverity.ERROR,
                    location=match.group(0)[:50],
                    suggestion="Remove NPC dialogue or only describe the environment",
                ))
                break  # One error is enough

        return issues

    def _check_meta_questions(self, narrative: str) -> list[ValidationIssue]:
        """Check for meta-questions that break immersion."""
        issues = []

        # Get last sentence
        sentences = narrative.strip().split(".")
        last_sentence = sentences[-1].strip() if sentences else ""

        for pattern in META_QUESTION_RE:
            if pattern.search(last_sentence):
                issues.append(ValidationIssue(
                    category="meta",
                    message="Narrative ends with meta-question to player",
                    severity=IssueSeverity.WARNING,
                    location=last_sentence[-50:] if len(last_sentence) > 50 else last_sentence,
                    suggestion="End at a natural pause, not with a question to the player",
                ))
                break

        return issues

    def _check_ai_identity(self, narrative: str) -> list[ValidationIssue]:
        """Check for AI/assistant identity leakage."""
        issues = []

        for pattern in AI_IDENTITY_RE:
            match = pattern.search(narrative)
            if match:
                issues.append(ValidationIssue(
                    category="identity",
                    message="AI identity leakage detected",
                    severity=IssueSeverity.ERROR,
                    location=match.group(0),
                    suggestion="Remove references to being an AI or assistant",
                ))

        return issues

    def _check_third_person(self, narrative: str) -> list[ValidationIssue]:
        """Check for third-person player references."""
        issues = []

        for pattern in THIRD_PERSON_RE:
            match = pattern.search(narrative)
            if match:
                issues.append(ValidationIssue(
                    category="perspective",
                    message=f"Third-person player reference: '{match.group(0)}'",
                    severity=IssueSeverity.WARNING,
                    location=match.group(0),
                    suggestion="Use second-person ('you') instead",
                ))

        return issues

    def _check_placeholders(self, narrative: str) -> list[ValidationIssue]:
        """Check for placeholder content."""
        issues = []

        for pattern in PLACEHOLDER_RE:
            match = pattern.search(narrative)
            if match:
                issues.append(ValidationIssue(
                    category="placeholder",
                    message=f"Placeholder content detected: '{match.group(0)}'",
                    severity=IssueSeverity.ERROR,
                    location=match.group(0),
                    suggestion="Replace with actual narrative content",
                ))

        return issues

    def _check_quality(self, narrative: str) -> list[ValidationIssue]:
        """Check narrative quality markers."""
        issues = []

        # Check for proper sentence structure (starts with capital)
        if narrative and not narrative[0].isupper():
            issues.append(ValidationIssue(
                category="quality",
                message="Narrative doesn't start with capital letter",
                severity=IssueSeverity.INFO,
            ))

        # Check for proper ending (period, exclamation, etc.)
        stripped = narrative.strip()
        if stripped and stripped[-1] not in ".!?\"'":
            issues.append(ValidationIssue(
                category="quality",
                message="Narrative doesn't end with proper punctuation",
                severity=IssueSeverity.INFO,
            ))

        # Check for multiple consecutive spaces
        if "  " in narrative:
            issues.append(ValidationIssue(
                category="quality",
                message="Multiple consecutive spaces found",
                severity=IssueSeverity.INFO,
                suggestion="Clean up whitespace",
            ))

        return issues


class DeltaValidator:
    """Validates state deltas for applicability.

    Checks that state deltas are valid and can be applied:
    - Target entities exist
    - Required fields are present
    - Values are within acceptable ranges
    - No conflicting deltas

    Usage:
        validator = DeltaValidator(db, game_session, manifest)
        result = validator.validate(deltas)
    """

    def __init__(
        self,
        db: Session | None = None,
        game_session: GameSession | None = None,
        manifest: GroundingManifest | None = None,
    ):
        """Initialize the validator.

        Args:
            db: Database session for lookups (optional)
            game_session: Current game session (optional)
            manifest: Grounding manifest for entity validation (optional)
        """
        self.db = db
        self.game_session = game_session
        self.manifest = manifest

    def validate(self, deltas: list[StateDelta]) -> ValidationResult:
        """Validate a list of state deltas.

        Args:
            deltas: List of state deltas to validate

        Returns:
            ValidationResult with any issues found
        """
        issues: list[ValidationIssue] = []

        for i, delta in enumerate(deltas):
            prefix = f"Delta[{i}]"

            # Check target key
            if not delta.target_key:
                issues.append(ValidationIssue(
                    category="delta",
                    message=f"{prefix}: Missing target_key",
                    severity=IssueSeverity.ERROR,
                ))
                continue

            # Type-specific validation
            delta_issues = self._validate_delta(delta, prefix)
            issues.extend(delta_issues)

        # Check for conflicting deltas
        issues.extend(self._check_conflicts(deltas))

        valid = not any(i.severity == IssueSeverity.ERROR for i in issues)

        return ValidationResult(valid=valid, issues=issues)

    def _validate_delta(self, delta: StateDelta, prefix: str) -> list[ValidationIssue]:
        """Validate a single delta based on its type."""
        issues = []

        if delta.delta_type == DeltaType.CREATE_ENTITY:
            issues.extend(self._validate_create_entity(delta, prefix))
        elif delta.delta_type == DeltaType.UPDATE_ENTITY:
            issues.extend(self._validate_update_entity(delta, prefix))
        elif delta.delta_type == DeltaType.TRANSFER_ITEM:
            issues.extend(self._validate_transfer_item(delta, prefix))
        elif delta.delta_type == DeltaType.RECORD_FACT:
            issues.extend(self._validate_record_fact(delta, prefix))
        elif delta.delta_type == DeltaType.UPDATE_NEED:
            issues.extend(self._validate_update_need(delta, prefix))
        elif delta.delta_type == DeltaType.UPDATE_RELATIONSHIP:
            issues.extend(self._validate_update_relationship(delta, prefix))
        elif delta.delta_type == DeltaType.ADVANCE_TIME:
            issues.extend(self._validate_advance_time(delta, prefix))
        elif delta.delta_type == DeltaType.UPDATE_LOCATION:
            issues.extend(self._validate_update_location(delta, prefix))

        return issues

    def _validate_create_entity(
        self, delta: StateDelta, prefix: str
    ) -> list[ValidationIssue]:
        """Validate CREATE_ENTITY delta."""
        issues = []
        changes = delta.changes

        if not changes.get("entity_type"):
            issues.append(ValidationIssue(
                category="delta",
                message=f"{prefix}: CREATE_ENTITY missing entity_type",
                severity=IssueSeverity.ERROR,
            ))

        if not changes.get("display_name"):
            issues.append(ValidationIssue(
                category="delta",
                message=f"{prefix}: CREATE_ENTITY missing display_name",
                severity=IssueSeverity.WARNING,
            ))

        # Check for duplicate key if manifest available
        if self.manifest and self.manifest.contains_key(delta.target_key):
            issues.append(ValidationIssue(
                category="delta",
                message=f"{prefix}: Entity key '{delta.target_key}' already exists",
                severity=IssueSeverity.ERROR,
            ))

        return issues

    def _validate_update_entity(
        self, delta: StateDelta, prefix: str
    ) -> list[ValidationIssue]:
        """Validate UPDATE_ENTITY delta."""
        issues = []

        if not delta.changes:
            issues.append(ValidationIssue(
                category="delta",
                message=f"{prefix}: UPDATE_ENTITY has no changes",
                severity=IssueSeverity.WARNING,
            ))

        # Check entity exists if manifest available
        if self.manifest and not self.manifest.contains_key(delta.target_key):
            issues.append(ValidationIssue(
                category="delta",
                message=f"{prefix}: Entity '{delta.target_key}' not found",
                severity=IssueSeverity.ERROR,
            ))

        return issues

    def _validate_transfer_item(
        self, delta: StateDelta, prefix: str
    ) -> list[ValidationIssue]:
        """Validate TRANSFER_ITEM delta."""
        issues = []
        changes = delta.changes

        # Accept BOTH naming conventions:
        # - Legacy: "from" / "to"
        # - Current: "from_entity_key" / "to_entity_key"
        has_from = "from" in changes or "from_entity_key" in changes
        has_to = "to" in changes or "to_entity_key" in changes

        if not has_from and not has_to:
            issues.append(ValidationIssue(
                category="delta",
                message=f"{prefix}: TRANSFER_ITEM needs 'from'/'to' or 'from_entity_key'/'to_entity_key'",
                severity=IssueSeverity.ERROR,
            ))

        # Check item exists in manifest (WARNING - item may be created mid-turn)
        if self.manifest:
            item_key = delta.target_key
            # Check all possible item locations in manifest
            items_at_location = getattr(self.manifest, 'items_at_location', None) or {}
            inventory = getattr(self.manifest, 'inventory', None) or {}
            equipped = getattr(self.manifest, 'equipped', None) or {}
            additional_keys = getattr(self.manifest, 'additional_valid_keys', None) or set()

            item_in_manifest = (
                item_key in items_at_location or
                item_key in inventory or
                item_key in equipped or
                item_key in additional_keys
            )
            if not item_in_manifest:
                issues.append(ValidationIssue(
                    category="delta",
                    message=f"{prefix}: Item '{item_key}' not found in manifest",
                    severity=IssueSeverity.WARNING,
                ))

        return issues

    def _validate_record_fact(
        self, delta: StateDelta, prefix: str
    ) -> list[ValidationIssue]:
        """Validate RECORD_FACT delta."""
        issues = []
        changes = delta.changes

        predicate = changes.get("predicate")
        if not predicate:  # Catches both missing key and None/empty value
            issues.append(ValidationIssue(
                category="delta",
                message=f"{prefix}: RECORD_FACT missing or empty predicate",
                severity=IssueSeverity.ERROR,
            ))

        value = changes.get("value")
        if not value:  # Catches both missing key and None/empty value
            issues.append(ValidationIssue(
                category="delta",
                message=f"{prefix}: RECORD_FACT missing or empty value",
                severity=IssueSeverity.ERROR,
            ))

        return issues

    def _validate_update_need(
        self, delta: StateDelta, prefix: str
    ) -> list[ValidationIssue]:
        """Validate UPDATE_NEED delta."""
        issues = []
        changes = delta.changes

        valid_needs = {"hunger", "thirst", "stamina", "sleep_pressure", "wellness", "hygiene"}

        for key, value in changes.items():
            if key not in valid_needs:
                issues.append(ValidationIssue(
                    category="delta",
                    message=f"{prefix}: Unknown need '{key}'",
                    severity=IssueSeverity.WARNING,
                ))
            elif isinstance(value, (int, float)):
                if value < 0 or value > 100:
                    issues.append(ValidationIssue(
                        category="delta",
                        message=f"{prefix}: Need '{key}' value {value} out of range (0-100)",
                        severity=IssueSeverity.WARNING,
                    ))

        return issues

    def _validate_update_relationship(
        self, delta: StateDelta, prefix: str
    ) -> list[ValidationIssue]:
        """Validate UPDATE_RELATIONSHIP delta."""
        issues = []
        changes = delta.changes

        valid_attrs = {"trust", "liking", "respect", "romantic_interest", "knows"}

        for key, value in changes.items():
            if key not in valid_attrs:
                issues.append(ValidationIssue(
                    category="delta",
                    message=f"{prefix}: Unknown relationship attribute '{key}'",
                    severity=IssueSeverity.WARNING,
                ))
            elif key != "knows" and isinstance(value, (int, float)):
                if value < 0 or value > 100:
                    issues.append(ValidationIssue(
                        category="delta",
                        message=f"{prefix}: Relationship '{key}' value {value} out of range (0-100)",
                        severity=IssueSeverity.WARNING,
                    ))

        return issues

    def _validate_advance_time(
        self, delta: StateDelta, prefix: str
    ) -> list[ValidationIssue]:
        """Validate ADVANCE_TIME delta."""
        issues = []
        changes = delta.changes

        minutes = changes.get("minutes", 0)
        if not isinstance(minutes, (int, float)):
            issues.append(ValidationIssue(
                category="delta",
                message=f"{prefix}: ADVANCE_TIME 'minutes' must be a number",
                severity=IssueSeverity.ERROR,
            ))
        elif minutes < 0:
            issues.append(ValidationIssue(
                category="delta",
                message=f"{prefix}: ADVANCE_TIME cannot go backwards ({minutes} minutes)",
                severity=IssueSeverity.ERROR,
            ))
        elif minutes > 1440:  # 24 hours
            issues.append(ValidationIssue(
                category="delta",
                message=f"{prefix}: ADVANCE_TIME very large ({minutes} minutes = {minutes/60:.1f} hours)",
                severity=IssueSeverity.WARNING,
            ))

        return issues

    def _validate_update_location(
        self, delta: StateDelta, prefix: str
    ) -> list[ValidationIssue]:
        """Validate UPDATE_LOCATION delta."""
        issues = []
        changes = delta.changes

        # Must have location_key
        if not changes.get("location_key"):
            issues.append(ValidationIssue(
                category="delta",
                message=f"{prefix}: UPDATE_LOCATION missing 'location_key'",
                severity=IssueSeverity.ERROR,
            ))

        # Soft check: destination should be a known exit
        # Note: This uses the manifest passed to validator which may be the destination
        # manifest for MOVE actions. The real validation happens in collapse.py which
        # checks if the location exists in the database before applying the delta.
        destination = changes.get("location_key")
        if destination and self.manifest:
            exits = getattr(self.manifest, 'exits', None) or {}
            if exits and destination not in exits:
                issues.append(ValidationIssue(
                    category="delta",
                    message=f"{prefix}: Destination '{destination}' not in manifest exits (will validate at collapse)",
                    severity=IssueSeverity.WARNING,
                    suggestion=f"Available exits: {list(exits.keys())}",
                ))

        return issues

    def _check_conflicts(self, deltas: list[StateDelta]) -> list[ValidationIssue]:
        """Check for conflicting deltas."""
        issues = []

        # Check for multiple operations on same target
        targets_seen: dict[str, list[DeltaType]] = {}

        for delta in deltas:
            key = delta.target_key
            if key not in targets_seen:
                targets_seen[key] = []
            targets_seen[key].append(delta.delta_type)

        for key, types in targets_seen.items():
            # Check for create + delete conflict
            if DeltaType.CREATE_ENTITY in types and DeltaType.DELETE_ENTITY in types:
                issues.append(ValidationIssue(
                    category="conflict",
                    message=f"Conflicting CREATE and DELETE for '{key}'",
                    severity=IssueSeverity.ERROR,
                ))

            # Check for multiple creates
            create_count = types.count(DeltaType.CREATE_ENTITY)
            if create_count > 1:
                issues.append(ValidationIssue(
                    category="conflict",
                    message=f"Multiple CREATE_ENTITY deltas for '{key}'",
                    severity=IssueSeverity.ERROR,
                ))

        return issues


class BranchValidator:
    """Validates complete quantum branches.

    Combines narrative and delta validation for full branch validation.

    Usage:
        validator = BranchValidator(manifest)
        result = validator.validate(branch)
    """

    def __init__(
        self,
        manifest: GroundingManifest,
        db: Session | None = None,
        game_session: GameSession | None = None,
    ):
        """Initialize the validator.

        Args:
            manifest: Grounding manifest for validation
            db: Optional database session
            game_session: Optional game session
        """
        self.manifest = manifest
        self.narrative_validator = NarrativeConsistencyValidator(manifest)
        self.delta_validator = DeltaValidator(db, game_session, manifest)

    def validate(self, branch: QuantumBranch) -> ValidationResult:
        """Validate a complete branch.

        Args:
            branch: The branch to validate

        Returns:
            ValidationResult with all issues
        """
        all_issues: list[ValidationIssue] = []

        # Validate each variant
        for variant_name, variant in branch.variants.items():
            # Validate narrative
            narrative_result = self.narrative_validator.validate(variant.narrative)
            for issue in narrative_result.issues:
                issue.category = f"variant:{variant_name}:{issue.category}"
                all_issues.append(issue)

            # Validate deltas
            delta_result = self.delta_validator.validate(variant.state_deltas)
            for issue in delta_result.issues:
                issue.category = f"variant:{variant_name}:{issue.category}"
                all_issues.append(issue)

        valid = not any(i.severity == IssueSeverity.ERROR for i in all_issues)

        return ValidationResult(valid=valid, issues=all_issues)

    def validate_variant(self, variant: OutcomeVariant) -> ValidationResult:
        """Validate a single variant.

        Args:
            variant: The variant to validate

        Returns:
            ValidationResult with issues
        """
        all_issues: list[ValidationIssue] = []

        # Validate narrative
        narrative_result = self.narrative_validator.validate(variant.narrative)
        all_issues.extend(narrative_result.issues)

        # Validate deltas
        delta_result = self.delta_validator.validate(variant.state_deltas)
        all_issues.extend(delta_result.issues)

        valid = not any(i.severity == IssueSeverity.ERROR for i in all_issues)

        return ValidationResult(valid=valid, issues=all_issues)
