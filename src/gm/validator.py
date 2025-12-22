"""Response validator for the Simplified GM Pipeline.

Validates GM responses for grounding and consistency.
"""

import logging
from typing import Any

from sqlalchemy.orm import Session

from src.database.models.session import GameSession
from src.gm.schemas import (
    GMResponse,
    ValidationResult,
    ValidationIssue,
    StateChangeType,
)
from src.gm.context_builder import GMContextBuilder

logger = logging.getLogger(__name__)


class ResponseValidator:
    """Validates GM responses for grounding and consistency.

    Checks:
    - Referenced entities exist
    - State changes are valid
    - No logical contradictions
    """

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        player_id: int,
        location_key: str,
    ) -> None:
        """Initialize validator.

        Args:
            db: Database session.
            game_session: Current game session.
            player_id: Player entity ID.
            location_key: Current location key.
        """
        self.db = db
        self.game_session = game_session
        self.player_id = player_id
        self.location_key = location_key

        self.context_builder = GMContextBuilder(db, game_session)

    def validate(self, response: GMResponse) -> ValidationResult:
        """Validate a GM response.

        Args:
            response: The GMResponse to validate.

        Returns:
            ValidationResult with any issues found.
        """
        issues: list[ValidationIssue] = []

        # Get known entity keys
        known_keys = self.context_builder.get_all_entity_keys(
            self.player_id,
            self.location_key,
        )

        # Add keys from new entities (they're being created)
        for new_entity in response.new_entities:
            known_keys.add(new_entity.key)

        # Check referenced entities
        issues.extend(self._check_entity_references(response, known_keys))

        # Check state changes
        issues.extend(self._check_state_changes(response, known_keys))

        # Check narrative length
        issues.extend(self._check_narrative(response))

        return ValidationResult(
            valid=not any(i.severity == "error" for i in issues),
            issues=issues,
        )

    def _check_entity_references(
        self,
        response: GMResponse,
        known_keys: set[str],
    ) -> list[ValidationIssue]:
        """Check that all referenced entities exist.

        Args:
            response: The GM response.
            known_keys: Set of known entity keys.

        Returns:
            List of validation issues.
        """
        issues = []

        for ref in response.referenced_entities:
            if ref not in known_keys:
                issues.append(ValidationIssue(
                    category="grounding",
                    message=f"Unknown entity referenced: {ref}",
                    severity="error",
                ))

        return issues

    def _check_state_changes(
        self,
        response: GMResponse,
        known_keys: set[str],
    ) -> list[ValidationIssue]:
        """Check that state changes are valid.

        Args:
            response: The GM response.
            known_keys: Set of known entity keys.

        Returns:
            List of validation issues.
        """
        issues = []

        for change in response.state_changes:
            # Check target exists
            if change.target and change.target not in known_keys:
                issues.append(ValidationIssue(
                    category="state_change",
                    message=f"State change targets unknown entity: {change.target}",
                    severity="error",
                ))

            # Type-specific validation
            if change.change_type == StateChangeType.MOVE:
                # Check destination exists
                dest = change.details.get("to")
                if dest and dest not in known_keys:
                    issues.append(ValidationIssue(
                        category="state_change",
                        message=f"Move destination unknown: {dest}",
                        severity="warning",  # Might be a new location
                    ))

            elif change.change_type == StateChangeType.TAKE:
                # Item should be at location
                item_key = change.target
                if item_key not in known_keys:
                    issues.append(ValidationIssue(
                        category="state_change",
                        message=f"Cannot take unknown item: {item_key}",
                        severity="error",
                    ))

            elif change.change_type == StateChangeType.GIVE:
                # Check recipient exists
                recipient = change.details.get("to")
                if recipient and recipient not in known_keys:
                    issues.append(ValidationIssue(
                        category="state_change",
                        message=f"Cannot give to unknown entity: {recipient}",
                        severity="error",
                    ))

        return issues

    def _check_narrative(self, response: GMResponse) -> list[ValidationIssue]:
        """Check narrative quality.

        Args:
            response: The GM response.

        Returns:
            List of validation issues.
        """
        issues = []

        # Check narrative length
        if len(response.narrative) < 10:
            issues.append(ValidationIssue(
                category="narrative",
                message="Narrative too short",
                severity="warning",
            ))

        if len(response.narrative) > 2000:
            issues.append(ValidationIssue(
                category="narrative",
                message="Narrative very long - consider brevity",
                severity="warning",
            ))

        # Check for empty narrative
        if not response.narrative.strip():
            issues.append(ValidationIssue(
                category="narrative",
                message="Empty narrative",
                severity="error",
            ))

        return issues


def validate_response(
    response: GMResponse,
    db: Session,
    game_session: GameSession,
    player_id: int,
    location_key: str,
) -> ValidationResult:
    """Convenience function to validate a GM response.

    Args:
        response: The GMResponse to validate.
        db: Database session.
        game_session: Current game session.
        player_id: Player entity ID.
        location_key: Current location key.

    Returns:
        ValidationResult with any issues found.
    """
    validator = ResponseValidator(db, game_session, player_id, location_key)
    return validator.validate(response)
