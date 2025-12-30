"""Branch Collapse Manager for Quantum Branching.

This module handles the "collapse" of quantum branches when a player
action is observed. The key insight is that dice rolls happen at
RUNTIME - we prepare all outcomes in advance, then select based on
the actual roll.

Responsibilities:
- Select appropriate variant based on dice roll
- Validate that state deltas are still applicable
- Apply state deltas atomically
- Strip [key:text] format for display
- Track collapse metrics
"""

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from src.database.models.session import GameSession
from src.dice.checks import make_skill_check
from src.dice.skills import get_attribute_for_skill
from src.managers.entity_manager import EntityManager
from src.managers.fact_manager import FactManager
from src.managers.item_manager import ItemManager
from src.managers.needs import NeedsManager
from src.managers.relationship_manager import RelationshipManager
from src.managers.time_manager import TimeManager
from src.dice.types import AdvantageType, SkillCheckResult
from src.world_server.quantum.schemas import (
    DeltaType,
    GMDecision,
    OutcomeVariant,
    QuantumBranch,
    QuantumMetrics,
    StateDelta,
    VariantType,
)

logger = logging.getLogger(__name__)


# Regex to match [entity_key:display_text] format
ENTITY_REFERENCE_PATTERN = re.compile(r"\[([a-z0-9_]+):([^\]]+)\]")


class StaleStateError(Exception):
    """Raised when branch state is stale and cannot be applied.

    This occurs when world state has changed since the branch was
    generated, making the pre-generated deltas invalid.
    """

    def __init__(
        self,
        message: str,
        stale_delta: StateDelta | None = None,
        expected: Any = None,
        actual: Any = None,
    ):
        super().__init__(message)
        self.stale_delta = stale_delta
        self.expected = expected
        self.actual = actual


@dataclass
class CollapseResult:
    """Result of collapsing a quantum branch.

    Contains the selected narrative (both raw and display versions),
    the state changes that were applied, and metadata about the collapse.
    """

    # Narrative content
    narrative: str  # Display version with [key:text] stripped
    raw_narrative: str  # Original version with [key:text] for parsing

    # State changes
    state_deltas: list[StateDelta]
    time_passed_minutes: int

    # Dice roll info
    skill_check_result: SkillCheckResult | None = None
    selected_variant: VariantType = VariantType.SUCCESS

    # Performance
    collapse_time_ms: float = 0.0
    was_cache_hit: bool = True

    # GM decision
    gm_decision: GMDecision | None = None
    had_twist: bool = False


@dataclass
class DeltaApplicationResult:
    """Result of applying state deltas."""

    success: bool
    applied_count: int
    failed_delta: StateDelta | None = None
    error_message: str | None = None


class BranchCollapseManager:
    """Manages the collapse of quantum branches.

    When a player takes an action, this manager:
    1. Rolls dice (if required) to determine outcome
    2. Validates that state deltas are still applicable
    3. Applies state changes atomically
    4. Returns the narrative for display

    The key insight is that dice rolls happen HERE at runtime,
    not during branch generation. This preserves the meaningful
    moment of uncertainty for the player.
    """

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        metrics: QuantumMetrics | None = None,
    ):
        """Initialize the collapse manager.

        Args:
            db: Database session for state queries
            game_session: Current game session
            metrics: Optional metrics tracker
        """
        self.db = db
        self.game_session = game_session
        self._metrics = metrics or QuantumMetrics()

    @property
    def metrics(self) -> QuantumMetrics:
        """Get the metrics tracker."""
        return self._metrics

    async def collapse_branch(
        self,
        branch: QuantumBranch,
        player_input: str,
        turn_number: int,
        attribute_modifier: int = 0,
        skill_modifier: int = 0,
        advantage_type: AdvantageType = AdvantageType.NORMAL,
        validate_deltas: bool = True,
        apply_deltas: bool = True,
    ) -> CollapseResult:
        """Collapse a quantum branch to a single outcome.

        This is the key moment where quantum uncertainty resolves
        into a concrete narrative and state changes.

        Args:
            branch: The pre-generated branch to collapse
            player_input: The player's original input
            turn_number: Current turn number
            attribute_modifier: Player's attribute modifier for skill checks
            skill_modifier: Player's skill modifier for skill checks
            advantage_type: Whether player has advantage/disadvantage
            validate_deltas: Whether to validate deltas before applying
            apply_deltas: Whether to actually apply deltas to database

        Returns:
            CollapseResult with narrative and metadata

        Raises:
            StaleStateError: If state has changed and deltas are invalid
        """
        start_time = time.perf_counter()

        # 1. Select variant based on dice roll
        variant, skill_result = await self._select_variant(
            branch=branch,
            attribute_modifier=attribute_modifier,
            skill_modifier=skill_modifier,
            advantage_type=advantage_type,
        )

        # 2. Validate deltas if requested
        if validate_deltas and variant.state_deltas:
            validation_result = await self._validate_deltas(variant.state_deltas)
            if not validation_result.success:
                raise StaleStateError(
                    f"State delta validation failed: {validation_result.error_message}",
                    stale_delta=validation_result.failed_delta,
                )

        # 3. Apply deltas if requested
        if apply_deltas and variant.state_deltas:
            await self._apply_deltas(variant.state_deltas, turn_number)

        # 4. Strip entity references for display
        display_narrative = strip_entity_references(variant.narrative)

        # 5. Mark branch as collapsed
        branch.is_collapsed = True
        branch.collapsed_variant = variant.variant_type.value

        # Calculate timing
        collapse_time_ms = (time.perf_counter() - start_time) * 1000

        # Record metrics
        had_twist = branch.gm_decision.decision_type != "no_twist"
        self._metrics.record_branch_collapsed(
            variant_type=variant.variant_type,
            had_twist=had_twist,
            collapse_time_ms=collapse_time_ms,
        )

        logger.info(
            f"Collapsed branch {branch.branch_key} to {variant.variant_type.value} "
            f"in {collapse_time_ms:.1f}ms"
        )

        return CollapseResult(
            narrative=display_narrative,
            raw_narrative=variant.narrative,
            state_deltas=variant.state_deltas,
            time_passed_minutes=variant.time_passed_minutes,
            skill_check_result=skill_result,
            selected_variant=variant.variant_type,
            collapse_time_ms=collapse_time_ms,
            was_cache_hit=True,
            gm_decision=branch.gm_decision,
            had_twist=had_twist,
        )

    async def _select_variant(
        self,
        branch: QuantumBranch,
        attribute_modifier: int,
        skill_modifier: int,
        advantage_type: AdvantageType,
    ) -> tuple[OutcomeVariant, SkillCheckResult | None]:
        """Select which variant to use based on dice roll.

        This is where the dice roll happens - the meaningful moment
        of uncertainty resolution.

        Args:
            branch: The branch to select from
            attribute_modifier: Player's attribute modifier
            skill_modifier: Player's skill modifier
            advantage_type: Advantage/disadvantage state

        Returns:
            Tuple of (selected variant, skill check result if rolled)
        """
        variants = branch.variants

        # Check if any variant requires a dice roll
        requires_roll = any(v.requires_dice for v in variants.values())

        if not requires_roll:
            # No dice needed - return success variant
            success_variant = variants.get("success")
            if success_variant:
                return success_variant, None
            # Fallback to first available variant
            return next(iter(variants.values())), None

        # Find variant with skill check info (usually success has DC)
        check_variant = variants.get("success") or next(iter(variants.values()))

        if not check_variant.dc:
            # No DC specified - default to success
            return check_variant, None

        # ROLL DICE AT RUNTIME - this is the meaningful moment!
        skill_name = check_variant.skill or "Skill"
        attribute_key = get_attribute_for_skill(skill_name) if skill_name else ""

        skill_result = make_skill_check(
            dc=check_variant.dc,
            attribute_modifier=attribute_modifier,
            skill_modifier=skill_modifier,
            advantage_type=advantage_type,
            skill_name=skill_name,
            attribute_key=attribute_key,
        )

        # Select variant based on roll result
        selected_variant = self._variant_for_result(variants, skill_result)

        logger.debug(
            f"Skill check DC {check_variant.dc}: "
            f"rolled {skill_result.roll_result.total if skill_result.roll_result else 'auto'}, "
            f"{'success' if skill_result.success else 'failure'}, "
            f"selected {selected_variant.variant_type.value}"
        )

        return selected_variant, skill_result

    def _variant_for_result(
        self,
        variants: dict[str, OutcomeVariant],
        skill_result: SkillCheckResult,
    ) -> OutcomeVariant:
        """Select variant based on skill check result.

        Args:
            variants: Available variants
            skill_result: Result of the skill check

        Returns:
            The appropriate variant for this result
        """
        # Critical success (double-10)
        if skill_result.is_critical_success:
            if "critical_success" in variants:
                return variants["critical_success"]
            return variants.get("success", next(iter(variants.values())))

        # Regular success
        if skill_result.success:
            return variants.get("success", next(iter(variants.values())))

        # Critical failure (double-1)
        if skill_result.is_critical_failure:
            if "critical_failure" in variants:
                return variants["critical_failure"]
            return variants.get("failure", variants.get("success", next(iter(variants.values()))))

        # Regular failure
        return variants.get("failure", variants.get("success", next(iter(variants.values()))))

    async def _validate_deltas(
        self,
        deltas: list[StateDelta],
    ) -> DeltaApplicationResult:
        """Validate that state deltas are still applicable.

        Checks that the expected state (captured at generation time)
        matches current state. If not, the branch is stale.

        Args:
            deltas: List of deltas to validate

        Returns:
            DeltaApplicationResult indicating success/failure
        """
        for delta in deltas:
            # Skip deltas without expected state
            if delta.expected_state is None:
                continue

            # Get current state for this target
            current_state = await self._get_current_state(delta.target_key, delta.delta_type)

            # Validate against expected
            if not delta.validate(current_state):
                return DeltaApplicationResult(
                    success=False,
                    applied_count=0,
                    failed_delta=delta,
                    error_message=f"State mismatch for {delta.target_key}: "
                                  f"expected {delta.expected_state}, got {current_state}",
                )

        return DeltaApplicationResult(success=True, applied_count=len(deltas))

    def _get_entity_id(self, entity_key: str) -> int | None:
        """Look up entity database ID from key.

        Args:
            entity_key: The entity's unique key

        Returns:
            Entity database ID or None if not found
        """
        entity_manager = EntityManager(self.db, self.game_session)
        entity = entity_manager.get_entity(entity_key)
        return entity.id if entity else None

    async def _get_current_state(
        self,
        target_key: str,
        delta_type: DeltaType,
    ) -> dict[str, Any]:
        """Get current state for validation.

        Args:
            target_key: Entity or location key
            delta_type: Type of delta to validate

        Returns:
            Current state as a dictionary
        """
        entity_manager = EntityManager(self.db, self.game_session)

        if delta_type == DeltaType.UPDATE_ENTITY:
            entity = entity_manager.get_entity(target_key)
            if entity:
                return {
                    "location_key": entity.location_key,
                    "is_active": entity.is_active,
                    "activity": entity.activity,
                }
            return {}

        elif delta_type == DeltaType.TRANSFER_ITEM:
            item_manager = ItemManager(self.db, self.game_session)
            item = item_manager.get_item(target_key)
            if item:
                return {
                    "holder_id": item.holder_id,
                    "owner_id": item.owner_id,
                    "location_key": item.location_key if hasattr(item, "location_key") else None,
                }
            return {}

        elif delta_type == DeltaType.UPDATE_NEED:
            entity_id = self._get_entity_id(target_key)
            if entity_id:
                needs_manager = NeedsManager(self.db, self.game_session)
                needs = needs_manager.get_or_create_needs(entity_id)
                if needs:
                    return {
                        "hunger": needs.hunger,
                        "thirst": needs.thirst,
                        "stamina": needs.stamina,
                        "sleep_pressure": needs.sleep_pressure,
                    }
            return {}

        elif delta_type == DeltaType.UPDATE_RELATIONSHIP:
            # Relationship validation would need both entity keys
            # For now, return empty - relationship changes are additive
            return {}

        elif delta_type == DeltaType.RECORD_FACT:
            # Facts are generally additive/updateable without conflict
            return {}

        elif delta_type == DeltaType.UPDATE_LOCATION:
            entity = entity_manager.get_entity(target_key)
            if entity:
                return {"location_key": entity.location_key}
            return {}

        # CREATE_ENTITY, DELETE_ENTITY, ADVANCE_TIME don't need state validation
        return {}

    async def _apply_deltas(
        self,
        deltas: list[StateDelta],
        turn_number: int,
    ) -> DeltaApplicationResult:
        """Apply state deltas atomically.

        Args:
            deltas: List of deltas to apply
            turn_number: Current turn number for audit

        Returns:
            DeltaApplicationResult indicating success/failure
        """
        applied_count = 0

        for delta in deltas:
            try:
                await self._apply_single_delta(delta, turn_number)
                applied_count += 1
            except Exception as e:
                logger.error(f"Failed to apply delta {delta.delta_type} to {delta.target_key}: {e}")
                return DeltaApplicationResult(
                    success=False,
                    applied_count=applied_count,
                    failed_delta=delta,
                    error_message=str(e),
                )

        return DeltaApplicationResult(success=True, applied_count=applied_count)

    async def _apply_single_delta(
        self,
        delta: StateDelta,
        turn_number: int,
    ) -> None:
        """Apply a single state delta.

        Args:
            delta: The delta to apply
            turn_number: Current turn number

        Raises:
            ValueError: If entity/item not found or invalid changes
        """
        logger.debug(
            f"Applying delta: {delta.delta_type.value} to {delta.target_key}, "
            f"changes={delta.changes}"
        )

        changes = delta.changes

        if delta.delta_type == DeltaType.CREATE_ENTITY:
            entity_manager = EntityManager(self.db, self.game_session)
            # Note: Entity model doesn't have 'description' field directly
            # Use 'background' for NPC backstory or store in extension
            entity_manager.create_entity(
                entity_key=changes.get("entity_key", delta.target_key),
                display_name=changes.get("display_name", delta.target_key),
                entity_type=changes.get("entity_type"),
                background=changes.get("description"),  # Map description to background
            )

        elif delta.delta_type == DeltaType.DELETE_ENTITY:
            entity_manager = EntityManager(self.db, self.game_session)
            entity_manager.mark_inactive(delta.target_key)

        elif delta.delta_type == DeltaType.UPDATE_ENTITY:
            entity_manager = EntityManager(self.db, self.game_session)
            if "location_key" in changes:
                entity_manager.update_location(delta.target_key, changes["location_key"])
            if "activity" in changes or "mood" in changes:
                entity_manager.update_activity(
                    delta.target_key,
                    activity=changes.get("activity", ""),
                    mood=changes.get("mood"),
                )

        elif delta.delta_type == DeltaType.TRANSFER_ITEM:
            item_manager = ItemManager(self.db, self.game_session)
            to_entity_id = None
            if "to_entity_key" in changes:
                to_entity_id = self._get_entity_id(changes["to_entity_key"])
            item_manager.transfer_item(
                item_key=delta.target_key,
                to_entity_id=to_entity_id,
                to_storage_key=changes.get("to_storage_key"),
            )

        elif delta.delta_type == DeltaType.UPDATE_NEED:
            entity_id = self._get_entity_id(changes.get("entity_key", delta.target_key))
            if entity_id:
                needs_manager = NeedsManager(self.db, self.game_session)
                needs_manager.satisfy_need(
                    entity_id=entity_id,
                    need_name=changes.get("need_name"),
                    amount=changes.get("amount", 0),
                    turn=turn_number,
                )

        elif delta.delta_type == DeltaType.UPDATE_RELATIONSHIP:
            rel_manager = RelationshipManager(self.db, self.game_session)
            from_id = self._get_entity_id(changes.get("from_key"))
            to_id = self._get_entity_id(changes.get("to_key"))
            if from_id and to_id:
                rel_manager.update_attitude(
                    from_id=from_id,
                    to_id=to_id,
                    dimension=changes.get("dimension", "trust"),
                    delta=changes.get("delta", 0),
                    reason=changes.get("reason", "quantum branch outcome"),
                )

        elif delta.delta_type == DeltaType.RECORD_FACT:
            predicate = changes.get("predicate")
            value = changes.get("value")

            # Skip invalid facts - LLM sometimes generates incomplete deltas
            if not predicate or not value:
                logger.warning(
                    f"Skipping RECORD_FACT for {delta.target_key}: "
                    f"missing predicate={predicate!r} or value={value!r}"
                )
                return

            # Validate category - LLM sometimes invents invalid values like "quest"
            valid_categories = {
                "personal", "secret", "preference", "skill",
                "history", "relationship", "location", "world"
            }
            raw_category = changes.get("category") or "personal"
            if raw_category not in valid_categories:
                logger.warning(
                    f"Invalid fact category '{raw_category}' for {delta.target_key}, "
                    f"using 'personal'"
                )
                raw_category = "personal"

            fact_manager = FactManager(self.db, self.game_session)
            fact_manager.record_fact(
                subject_type=changes.get("subject_type", "entity"),
                subject_key=changes.get("subject_key", delta.target_key),
                predicate=predicate,
                value=value,
                category=raw_category,
                is_secret=changes.get("is_secret", False),
            )

        elif delta.delta_type == DeltaType.UPDATE_LOCATION:
            entity_manager = EntityManager(self.db, self.game_session)
            entity_manager.update_location(
                entity_key=delta.target_key,
                location_key=changes.get("location_key"),
            )

        elif delta.delta_type == DeltaType.ADVANCE_TIME:
            time_manager = TimeManager(self.db, self.game_session)
            time_manager.advance_time(minutes=changes.get("minutes", 1))

        else:
            logger.warning(f"Unknown delta type: {delta.delta_type}")


def strip_entity_references(text: str) -> str:
    """Strip [entity_key:display_text] format, keeping only display text.

    Args:
        text: Text containing entity references

    Returns:
        Text with entity references replaced by display text

    Examples:
        >>> strip_entity_references("You talk to [guard_001:the guard].")
        'You talk to the guard.'
        >>> strip_entity_references("[innkeeper:Tom] smiles.")
        'Tom smiles.'
    """
    return ENTITY_REFERENCE_PATTERN.sub(r"\2", text)


def extract_entity_references(text: str) -> list[tuple[str, str]]:
    """Extract all entity references from text.

    Args:
        text: Text containing entity references

    Returns:
        List of (entity_key, display_text) tuples

    Examples:
        >>> extract_entity_references("You talk to [guard_001:the guard].")
        [('guard_001', 'the guard')]
    """
    return ENTITY_REFERENCE_PATTERN.findall(text)


def format_skill_check_result(result: SkillCheckResult) -> str:
    """Format a skill check result for display.

    Args:
        result: The skill check result

    Returns:
        Formatted string for display

    Examples:
        >>> result = make_skill_check(dc=15, attribute_modifier=2, skill_modifier=3)
        >>> format_skill_check_result(result)
        '2d10+5 vs DC 15: 18 (Success!)'
    """
    if result.is_auto_success:
        return f"DC {result.dc}: Auto-success (trivial for your skill level)"

    roll = result.roll_result
    if not roll:
        return f"DC {result.dc}: Success"

    dice_str = f"{roll.expression.num_dice}d{roll.expression.die_size}"
    if roll.modifier != 0:
        dice_str += f"{'+' if roll.modifier > 0 else ''}{roll.modifier}"

    outcome = "Success!" if result.success else "Failed"
    if result.is_critical_success:
        outcome = "Critical Success!"
    elif result.is_critical_failure:
        outcome = "Critical Failure!"

    return f"{dice_str} vs DC {result.dc}: {roll.total} ({outcome})"
