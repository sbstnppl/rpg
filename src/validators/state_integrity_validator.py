"""State Integrity Validator for ensuring data consistency.

This module provides validation and auto-fix capabilities for game state,
ensuring NPCs have locations, items have storage, and relationships are valid.
"""

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from src.database.models.entities import Entity, NPCExtension
from src.database.models.items import Item
from src.database.models.relationships import Relationship
from src.database.models.enums import EntityType

if TYPE_CHECKING:
    from src.database.models.session import GameSession

logger = logging.getLogger(__name__)


@dataclass
class IntegrityViolation:
    """A single integrity violation found during validation.

    Attributes:
        category: Type of violation (entity, item, relationship)
        severity: How serious (warning, error)
        message: Description of the violation
        target_type: Type of object (entity, item, etc.)
        target_id: ID of the affected object
        fixed: Whether auto-fix was applied
        fix_action: Description of fix applied (if any)
    """

    category: str
    severity: str
    message: str
    target_type: str
    target_id: int | None = None
    fixed: bool = False
    fix_action: str | None = None


@dataclass
class ValidationReport:
    """Report from running state integrity validation.

    Attributes:
        violations: List of all violations found
        fixes_applied: Count of auto-fixes applied
        errors_remaining: Count of unfixed errors
    """

    violations: list[IntegrityViolation] = field(default_factory=list)
    fixes_applied: int = 0
    errors_remaining: int = 0

    def add_violation(self, violation: IntegrityViolation) -> None:
        """Add a violation to the report."""
        self.violations.append(violation)
        if violation.fixed:
            self.fixes_applied += 1
        elif violation.severity == "error":
            self.errors_remaining += 1

    @property
    def has_violations(self) -> bool:
        """Whether any violations were found."""
        return len(self.violations) > 0

    @property
    def has_unfixed_errors(self) -> bool:
        """Whether there are unfixed errors."""
        return self.errors_remaining > 0

    def summary(self) -> str:
        """Generate a summary string."""
        if not self.violations:
            return "No integrity violations found"
        return (
            f"Found {len(self.violations)} violation(s): "
            f"{self.fixes_applied} auto-fixed, "
            f"{self.errors_remaining} errors remaining"
        )


class StateIntegrityValidator:
    """Validates and auto-fixes game state integrity.

    Checks for common integrity issues after action execution and
    attempts to auto-fix where possible.

    Example:
        validator = StateIntegrityValidator(db, game_session)
        report = validator.validate_and_fix()
        if report.has_unfixed_errors:
            logger.error(f"Integrity errors: {report.summary()}")
    """

    def __init__(
        self,
        db: Session,
        game_session: "GameSession",
        auto_fix: bool = True,
    ):
        """Initialize validator.

        Args:
            db: Database session.
            game_session: Current game session.
            auto_fix: Whether to auto-fix violations (default True).
        """
        self.db = db
        self.game_session = game_session
        self.auto_fix = auto_fix

    def validate_and_fix(self) -> ValidationReport:
        """Run all validations and optionally auto-fix issues.

        Returns:
            ValidationReport with all findings.
        """
        report = ValidationReport()

        # Entity checks
        self._check_npc_locations(report)
        self._check_entity_required_fields(report)

        # Item checks
        self._check_item_ownership(report)
        self._check_duplicate_body_slots(report)

        # Relationship checks
        self._check_relationship_integrity(report)
        self._check_self_relationships(report)

        # Commit any fixes
        if self.auto_fix and report.fixes_applied > 0:
            self.db.flush()

        return report

    # =========================================================================
    # Entity Checks
    # =========================================================================

    def _check_npc_locations(self, report: ValidationReport) -> None:
        """Check that all NPCs have a current_location set.

        Auto-fix: Set to "unknown" if missing.
        """
        from sqlalchemy.orm import joinedload

        # Get all NPC entities in this session with extensions eagerly loaded
        npcs = (
            self.db.query(Entity)
            .options(joinedload(Entity.npc_extension))
            .filter(
                Entity.session_id == self.game_session.id,
                Entity.entity_type == EntityType.NPC,
            )
            .all()
        )

        for npc in npcs:
            # Get NPC extension (already loaded via joinedload)
            extension = npc.npc_extension

            if not extension:
                violation = IntegrityViolation(
                    category="entity",
                    severity="warning",
                    message=f"NPC {npc.entity_key} has no NPCExtension",
                    target_type="entity",
                    target_id=npc.id,
                )
                report.add_violation(violation)
                continue

            if not extension.current_location:
                if self.auto_fix:
                    extension.current_location = "unknown"
                    violation = IntegrityViolation(
                        category="entity",
                        severity="warning",
                        message=f"NPC {npc.entity_key} had no location",
                        target_type="entity",
                        target_id=npc.id,
                        fixed=True,
                        fix_action="Set location to 'unknown'",
                    )
                else:
                    violation = IntegrityViolation(
                        category="entity",
                        severity="error",
                        message=f"NPC {npc.entity_key} has no location",
                        target_type="entity",
                        target_id=npc.id,
                    )
                report.add_violation(violation)
                logger.warning(f"NPC location violation: {npc.entity_key}")

    def _check_entity_required_fields(self, report: ValidationReport) -> None:
        """Check that all entities have required fields (entity_key, display_name)."""
        entities = (
            self.db.query(Entity)
            .filter(Entity.session_id == self.game_session.id)
            .all()
        )

        for entity in entities:
            if not entity.entity_key:
                violation = IntegrityViolation(
                    category="entity",
                    severity="error",
                    message=f"Entity {entity.id} has no entity_key",
                    target_type="entity",
                    target_id=entity.id,
                )
                report.add_violation(violation)
                logger.error(f"Entity missing entity_key: {entity.id}")

            if not entity.display_name:
                if self.auto_fix:
                    # Use entity_key as fallback
                    entity.display_name = entity.entity_key or f"Entity {entity.id}"
                    violation = IntegrityViolation(
                        category="entity",
                        severity="warning",
                        message=f"Entity {entity.entity_key} had no display_name",
                        target_type="entity",
                        target_id=entity.id,
                        fixed=True,
                        fix_action=f"Set display_name to '{entity.display_name}'",
                    )
                else:
                    violation = IntegrityViolation(
                        category="entity",
                        severity="error",
                        message=f"Entity {entity.entity_key} has no display_name",
                        target_type="entity",
                        target_id=entity.id,
                    )
                report.add_violation(violation)

    # =========================================================================
    # Item Checks
    # =========================================================================

    def _check_item_ownership(self, report: ValidationReport) -> None:
        """Check that all items have valid ownership/location.

        Valid states:
        - owner_id: Entity owns this item
        - holder_id: Entity currently holds this item
        - storage_location_id: Item is in storage
        - owner_location_id: Environmental item owned by a location

        Auto-fix: Assign orphaned items to player as holder.
        """
        items = (
            self.db.query(Item)
            .filter(Item.session_id == self.game_session.id)
            .all()
        )

        # Get player entity for auto-fix
        player = None
        if self.auto_fix:
            player = (
                self.db.query(Entity)
                .filter(
                    Entity.session_id == self.game_session.id,
                    Entity.entity_type == EntityType.PLAYER,
                )
                .first()
            )

        for item in items:
            has_location = (
                item.owner_id is not None
                or item.holder_id is not None
                or item.storage_location_id is not None
                or item.owner_location_id is not None  # Environmental items
            )

            if not has_location:
                if self.auto_fix and player:
                    # Assign orphaned items to player as holder
                    item.holder_id = player.id
                    if item.body_slot:
                        fix_action = f"Assigned to player as holder (was equipped in {item.body_slot})"
                    else:
                        fix_action = "Assigned to player as holder (orphaned item)"

                    violation = IntegrityViolation(
                        category="item",
                        severity="warning",
                        message=f"Item {item.item_key} had no ownership/location",
                        target_type="item",
                        target_id=item.id,
                        fixed=True,
                        fix_action=fix_action,
                    )
                else:
                    violation = IntegrityViolation(
                        category="item",
                        severity="error",
                        message=f"Item {item.item_key} has no ownership or location",
                        target_type="item",
                        target_id=item.id,
                    )
                report.add_violation(violation)
                logger.warning(f"Item ownership violation: {item.item_key}")

    def _check_duplicate_body_slots(self, report: ValidationReport) -> None:
        """Check for duplicate items in the same body slot/layer for same entity."""
        from sqlalchemy import func

        # Find entities with duplicate equipped slots
        duplicates = (
            self.db.query(
                Item.holder_id,
                Item.body_slot,
                Item.body_layer,
                func.count(Item.id).label("count"),
            )
            .filter(
                Item.session_id == self.game_session.id,
                Item.body_slot.isnot(None),
                Item.holder_id.isnot(None),
            )
            .group_by(Item.holder_id, Item.body_slot, Item.body_layer)
            .having(func.count(Item.id) > 1)
            .all()
        )

        for dup in duplicates:
            holder_id, body_slot, body_layer, count = dup

            # Get entity name for clearer error
            entity = self.db.query(Entity).filter(Entity.id == holder_id).first()
            entity_name = entity.entity_key if entity else str(holder_id)

            violation = IntegrityViolation(
                category="item",
                severity="error",
                message=(
                    f"Entity {entity_name} has {count} items in "
                    f"{body_slot}/{body_layer or 'no layer'}"
                ),
                target_type="item",
                target_id=None,
            )
            report.add_violation(violation)
            logger.error(f"Duplicate body slot: {entity_name} {body_slot}/{body_layer}")

    # =========================================================================
    # Relationship Checks
    # =========================================================================

    def _check_relationship_integrity(self, report: ValidationReport) -> None:
        """Check that both entities in a relationship exist."""
        relationships = (
            self.db.query(Relationship)
            .filter(Relationship.session_id == self.game_session.id)
            .all()
        )

        # Get all entity IDs in session for lookup
        entity_ids = set(
            r[0]
            for r in self.db.query(Entity.id)
            .filter(Entity.session_id == self.game_session.id)
            .all()
        )

        for rel in relationships:
            orphaned = []
            if rel.from_entity_id not in entity_ids:
                orphaned.append(f"from_entity_id={rel.from_entity_id}")
            if rel.to_entity_id not in entity_ids:
                orphaned.append(f"to_entity_id={rel.to_entity_id}")

            if orphaned:
                if self.auto_fix:
                    # Delete orphaned relationship
                    self.db.delete(rel)
                    violation = IntegrityViolation(
                        category="relationship",
                        severity="warning",
                        message=f"Relationship {rel.id} had orphaned refs: {', '.join(orphaned)}",
                        target_type="relationship",
                        target_id=rel.id,
                        fixed=True,
                        fix_action="Deleted orphaned relationship",
                    )
                else:
                    violation = IntegrityViolation(
                        category="relationship",
                        severity="error",
                        message=f"Relationship {rel.id} has orphaned refs: {', '.join(orphaned)}",
                        target_type="relationship",
                        target_id=rel.id,
                    )
                report.add_violation(violation)
                logger.warning(f"Orphaned relationship: {rel.id}")

    def _check_self_relationships(self, report: ValidationReport) -> None:
        """Check for self-relationships (entity relating to itself)."""
        self_rels = (
            self.db.query(Relationship)
            .filter(
                Relationship.session_id == self.game_session.id,
                Relationship.from_entity_id == Relationship.to_entity_id,
            )
            .all()
        )

        for rel in self_rels:
            if self.auto_fix:
                self.db.delete(rel)
                violation = IntegrityViolation(
                    category="relationship",
                    severity="warning",
                    message=f"Relationship {rel.id} was self-referential",
                    target_type="relationship",
                    target_id=rel.id,
                    fixed=True,
                    fix_action="Deleted self-relationship",
                )
            else:
                violation = IntegrityViolation(
                    category="relationship",
                    severity="error",
                    message=f"Relationship {rel.id} is self-referential (entity {rel.from_entity_id})",
                    target_type="relationship",
                    target_id=rel.id,
                )
            report.add_violation(violation)
            logger.warning(f"Self-relationship found: {rel.id}")
