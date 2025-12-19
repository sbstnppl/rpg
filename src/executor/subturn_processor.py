"""Subturn processor for chained multi-action turns.

This module handles processing multiple actions in sequence with state
updates between them. Each action is a "subturn" that:
1. Validates against the CURRENT (potentially updated) state
2. Checks for interrupts via the complication oracle
3. Executes and updates state for the next subturn
4. Evaluates whether the chain should continue

Example:
    Player: "go to the well and use the bucket"
    -> Subturn 1: MOVE to well (state updates: player_location = "well")
    -> Subturn 2: USE bucket (validated against new location, finds bucket)
    -> Single merged narrative covers both actions
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from src.parser.action_types import Action, ActionType

if TYPE_CHECKING:
    from src.database.models.session import GameSession
    from src.database.models.entities import Entity
    from src.oracle.complication_oracle import ComplicationOracle
    from src.oracle.complication_types import Complication
    from src.validators.action_validator import ActionValidator, ValidationResult
    from src.executor.action_executor import ExecutionResult, ActionExecutor


class ContinuationStatus(str, Enum):
    """Status for whether the action chain should continue.

    CONTINUE: Auto-proceed to the next action (minor discovery, no harm)
    OFFER_CHOICE: Ask player if they want to continue (minor injury resolved)
    ABANDON: Stop chain, player cannot continue (broken leg, blocked path)
    """

    CONTINUE = "continue"
    OFFER_CHOICE = "offer_choice"
    ABANDON = "abandon"


@dataclass
class SubturnResult:
    """Result of processing a single subturn.

    Each subturn represents one action in a multi-action chain.

    Attributes:
        action: The action that was processed.
        validation: Result of validating this action.
        execution: Result of executing (None if validation failed).
        complication: Complication triggered during this subturn (if any).
        state_snapshot: State after this subturn completed.
        continuation_status: Whether chain can continue after this subturn.
    """

    action: Action
    validation: "ValidationResult"
    execution: "ExecutionResult | None"
    complication: "Complication | None"
    state_snapshot: dict[str, Any]
    continuation_status: ContinuationStatus

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "action": {
                "type": self.action.type.value,
                "target": self.action.target,
                "indirect_target": self.action.indirect_target,
                "manner": self.action.manner,
            },
            "validation": {
                "valid": self.validation.valid,
                "reason": self.validation.reason,
                "warnings": self.validation.warnings,
                "risk_tags": self.validation.risk_tags,
            },
            "execution": {
                "success": self.execution.success,
                "outcome": self.execution.outcome,
                "state_changes": self.execution.state_changes,
            }
            if self.execution
            else None,
            "complication": self.complication.to_dict() if self.complication else None,
            "state_snapshot": self.state_snapshot,
            "continuation_status": self.continuation_status.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubturnResult":
        """Create from dictionary."""
        # Lazy imports to avoid circular dependency
        from src.validators.action_validator import ValidationResult
        from src.executor.action_executor import ExecutionResult
        from src.oracle.complication_types import Complication

        action_data = data["action"]
        action = Action(
            type=ActionType(action_data["type"]),
            target=action_data.get("target"),
            indirect_target=action_data.get("indirect_target"),
            manner=action_data.get("manner"),
        )

        validation_data = data["validation"]
        validation = ValidationResult(
            action=action,
            valid=validation_data["valid"],
            reason=validation_data.get("reason"),
            warnings=validation_data.get("warnings", []),
            risk_tags=validation_data.get("risk_tags", []),
        )

        execution = None
        if data.get("execution"):
            exec_data = data["execution"]
            execution = ExecutionResult(
                action=action,
                success=exec_data["success"],
                outcome=exec_data["outcome"],
                state_changes=exec_data.get("state_changes", []),
            )

        complication = None
        if data.get("complication"):
            complication = Complication.from_dict(data["complication"])

        return cls(
            action=action,
            validation=validation,
            execution=execution,
            complication=complication,
            state_snapshot=data.get("state_snapshot", {}),
            continuation_status=ContinuationStatus(data["continuation_status"]),
        )


@dataclass
class ChainedTurnResult:
    """Combined result of all subturns in a multi-action chain.

    This is the output of the SubturnProcessor and contains everything
    needed for the narrator to generate a merged narrative.

    Attributes:
        subturns: Results of all processed subturns.
        remaining_actions: Actions not processed due to interrupt.
        final_state_snapshot: State after all subturns completed.
        interrupting_complication: Complication that caused chain to stop.
        continuation_offered: Whether player was offered choice to continue.
        continuation_prompt: Question to ask player if choice offered.
    """

    subturns: list[SubturnResult] = field(default_factory=list)
    remaining_actions: list[Action] = field(default_factory=list)
    final_state_snapshot: dict[str, Any] = field(default_factory=dict)
    interrupting_complication: "Complication | None" = None
    continuation_offered: bool = False
    continuation_prompt: str | None = None

    @property
    def all_successful(self) -> bool:
        """Whether all subturns executed successfully."""
        return all(
            st.execution and st.execution.success
            for st in self.subturns
            if st.validation.valid
        )

    @property
    def was_interrupted(self) -> bool:
        """Whether the chain was interrupted by a complication."""
        return self.interrupting_complication is not None

    @property
    def completed_count(self) -> int:
        """Number of actions that completed execution."""
        return sum(
            1 for st in self.subturns if st.execution and st.execution.success
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "subturns": [st.to_dict() for st in self.subturns],
            "remaining_actions": [
                {
                    "type": a.type.value,
                    "target": a.target,
                    "indirect_target": a.indirect_target,
                }
                for a in self.remaining_actions
            ],
            "final_state_snapshot": self.final_state_snapshot,
            "interrupting_complication": (
                self.interrupting_complication.to_dict()
                if self.interrupting_complication
                else None
            ),
            "continuation_offered": self.continuation_offered,
            "continuation_prompt": self.continuation_prompt,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChainedTurnResult":
        """Create from dictionary."""
        # Lazy import to avoid circular dependency
        from src.oracle.complication_types import Complication

        subturns = [SubturnResult.from_dict(st) for st in data.get("subturns", [])]

        remaining_actions = []
        for a in data.get("remaining_actions", []):
            remaining_actions.append(
                Action(
                    type=ActionType(a["type"]),
                    target=a.get("target"),
                    indirect_target=a.get("indirect_target"),
                )
            )

        interrupting = None
        if data.get("interrupting_complication"):
            interrupting = Complication.from_dict(data["interrupting_complication"])

        return cls(
            subturns=subturns,
            remaining_actions=remaining_actions,
            final_state_snapshot=data.get("final_state_snapshot", {}),
            interrupting_complication=interrupting,
            continuation_offered=data.get("continuation_offered", False),
            continuation_prompt=data.get("continuation_prompt"),
        )


# Status conditions that prevent action continuation
INCAPACITATING_STATUSES = frozenset([
    "unconscious",
    "paralyzed",
    "broken_leg",
    "broken_arm",
    "stunned",
    "dead",
    "dying",
    "incapacitated",
])


class SubturnProcessor:
    """Processes multi-action turns as a sequence of subturns.

    The processor iterates through parsed actions, validating and executing
    each one while updating state between them. Interrupts (complications)
    can stop or pause the chain.

    Example:
        processor = SubturnProcessor(db, game_session, oracle, validator, executor)
        result = await processor.process_chain(
            actions=[MOVE("well"), USE("bucket")],
            actor=player,
            initial_state={"player_location": "kitchen"},
        )
    """

    def __init__(
        self,
        db: Session,
        game_session: "GameSession",
        oracle: "ComplicationOracle | None" = None,
        validator: "ActionValidator | None" = None,
        executor: "ActionExecutor | None" = None,
    ):
        """Initialize the subturn processor.

        Args:
            db: SQLAlchemy database session.
            game_session: Current game session.
            oracle: Complication oracle for interrupt checks.
            validator: Action validator (created if not provided).
            executor: Action executor (created if not provided).
        """
        self.db = db
        self.game_session = game_session
        self._oracle = oracle
        self._validator = validator
        self._executor = executor

    @property
    def validator(self) -> "ActionValidator":
        """Lazy-load ActionValidator."""
        if self._validator is None:
            from src.validators.action_validator import ActionValidator

            self._validator = ActionValidator(self.db, self.game_session)
        return self._validator

    @property
    def executor(self) -> "ActionExecutor":
        """Lazy-load ActionExecutor."""
        if self._executor is None:
            from src.executor.action_executor import ActionExecutor

            self._executor = ActionExecutor(self.db, self.game_session)
        return self._executor

    @property
    def oracle(self) -> "ComplicationOracle | None":
        """Get complication oracle (may be None)."""
        return self._oracle

    async def process_chain(
        self,
        actions: list[Action],
        actor: "Entity",
        initial_state: dict[str, Any],
        dynamic_plans: dict[str, Any] | None = None,
    ) -> ChainedTurnResult:
        """Process a chain of actions as sequential subturns.

        Each action is validated against the current state (which updates
        after each execution). Complications can interrupt the chain.

        Args:
            actions: List of actions to process in order.
            actor: Entity performing the actions.
            initial_state: Initial state snapshot (player_location, etc.).
            dynamic_plans: Plans for CUSTOM actions from dynamic_planner.

        Returns:
            ChainedTurnResult with all subturn results and final state.
        """
        subturns: list[SubturnResult] = []
        current_state = dict(initial_state)
        interrupting_complication: Complication | None = None
        continuation_offered = False
        continuation_prompt: str | None = None

        for idx, action in enumerate(actions):
            # 1. Validate action against current state
            validation = await self._validate_action(action, actor, current_state)

            if not validation.valid:
                # Record failed validation and continue to next action
                subturns.append(
                    SubturnResult(
                        action=action,
                        validation=validation,
                        execution=None,
                        complication=None,
                        state_snapshot=dict(current_state),
                        continuation_status=ContinuationStatus.CONTINUE,
                    )
                )
                continue

            # 2. Check for interrupt (complication) before execution
            complication = await self._check_interrupt(
                action=action,
                validation=validation,
                actor=actor,
                state=current_state,
                subturn_index=idx,
            )

            if complication:
                # 3. Evaluate continuation based on complication severity
                continuation = self._evaluate_continuation(
                    complication=complication,
                    remaining_actions=actions[idx + 1 :],
                    actor=actor,
                )

                if continuation == ContinuationStatus.ABANDON:
                    # Don't execute, record and stop chain
                    subturns.append(
                        SubturnResult(
                            action=action,
                            validation=validation,
                            execution=None,
                            complication=complication,
                            state_snapshot=dict(current_state),
                            continuation_status=ContinuationStatus.ABANDON,
                        )
                    )
                    interrupting_complication = complication
                    break

                elif continuation == ContinuationStatus.OFFER_CHOICE:
                    # Execute this action, then stop for player choice
                    execution = await self._execute_action(
                        validation, actor, current_state, dynamic_plans
                    )
                    current_state = self._update_state_snapshot(
                        current_state, execution, action
                    )

                    subturns.append(
                        SubturnResult(
                            action=action,
                            validation=validation,
                            execution=execution,
                            complication=complication,
                            state_snapshot=dict(current_state),
                            continuation_status=ContinuationStatus.OFFER_CHOICE,
                        )
                    )
                    interrupting_complication = complication
                    continuation_offered = True
                    continuation_prompt = self._build_continuation_prompt(
                        actions[idx + 1 :], complication
                    )
                    break

                # CONTINUE: execute and continue loop (complication recorded but doesn't stop)

            # 4. Execute action
            execution = await self._execute_action(
                validation, actor, current_state, dynamic_plans
            )

            # 5. Update state snapshot
            current_state = self._update_state_snapshot(current_state, execution, action)

            # 6. Record subturn
            subturns.append(
                SubturnResult(
                    action=action,
                    validation=validation,
                    execution=execution,
                    complication=complication,
                    state_snapshot=dict(current_state),
                    continuation_status=ContinuationStatus.CONTINUE,
                )
            )

            # Flush DB to ensure subsequent validations see changes
            self.db.flush()

        # Determine remaining actions
        processed_count = len(subturns)
        remaining = actions[processed_count:] if processed_count < len(actions) else []

        return ChainedTurnResult(
            subturns=subturns,
            remaining_actions=remaining,
            final_state_snapshot=current_state,
            interrupting_complication=interrupting_complication,
            continuation_offered=continuation_offered,
            continuation_prompt=continuation_prompt,
        )

    async def _validate_action(
        self,
        action: Action,
        actor: "Entity",
        state: dict[str, Any],
    ) -> "ValidationResult":
        """Validate a single action against current state.

        Args:
            action: Action to validate.
            actor: Entity performing the action.
            state: Current state snapshot.

        Returns:
            ValidationResult with validity and metadata.
        """
        # Validate using the standard validator with current location from state
        actor_location = state.get("player_location", "")
        return self.validator.validate(action, actor, actor_location=actor_location)

    async def _execute_action(
        self,
        validation: "ValidationResult",
        actor: "Entity",
        state: dict[str, Any],
        dynamic_plans: dict[str, Any] | None,
    ) -> "ExecutionResult":
        """Execute a single validated action.

        Args:
            validation: Validation result for the action.
            actor: Entity performing the action.
            state: Current state snapshot.
            dynamic_plans: Plans for CUSTOM actions.

        Returns:
            ExecutionResult with outcome.
        """
        # Set executor location to current state
        self.executor._actor_location = state.get("player_location", "")
        self.executor._dynamic_plans = dynamic_plans or {}

        # Execute the single action
        return await self.executor._execute_action(validation, actor)

    async def _check_interrupt(
        self,
        action: Action,
        validation: "ValidationResult",
        actor: "Entity",
        state: dict[str, Any],
        subturn_index: int,
    ) -> "Complication | None":
        """Check if a complication should interrupt at this subturn.

        Uses the oracle with enhanced probability modifiers for:
        - Subturn index (later actions in chain have higher chance)
        - Location danger level
        - Risk tags from validation

        Args:
            action: Current action being processed.
            validation: Validation result with risk tags.
            actor: Entity performing the action.
            state: Current state snapshot.
            subturn_index: 0-indexed position in action chain.

        Returns:
            Complication if triggered, None otherwise.
        """
        if self.oracle is None:
            return None

        # Build action summary
        actions_summary = f"{action.type.value} {action.target or ''}"

        # Get location danger from state or default to neutral
        location_danger = self._get_location_danger(state.get("player_location", ""))

        # Get turns since last complication
        turns_since = self.oracle.get_turns_since_complication()

        # Check with enhanced parameters
        result = await self.oracle.check(
            actions_summary=actions_summary,
            scene_context=state.get("scene_context", ""),
            risk_tags=validation.risk_tags,
            turns_since_complication=turns_since,
            subturn_index=subturn_index,
            location_danger=location_danger,
        )

        if result.triggered and result.complication:
            return result.complication

        return None

    def _evaluate_continuation(
        self,
        complication: "Complication",
        remaining_actions: list[Action],
        actor: "Entity",
    ) -> ContinuationStatus:
        """Evaluate whether chain should continue after complication.

        Args:
            complication: The triggered complication.
            remaining_actions: Actions not yet processed.
            actor: Entity performing actions.

        Returns:
            ContinuationStatus indicating how to proceed.
        """
        # 1. Check for incapacitating effects
        if self._has_incapacitating_effect(complication):
            return ContinuationStatus.ABANDON

        # 2. Check if remaining actions are still plausible
        if not self._actions_still_plausible(remaining_actions, complication):
            return ContinuationStatus.ABANDON

        # 3. Check for significant injury/cost -> offer choice
        if self._has_significant_cost(complication):
            return ContinuationStatus.OFFER_CHOICE

        # 4. Minor discovery/interruption -> auto-continue
        return ContinuationStatus.CONTINUE

    def _has_incapacitating_effect(self, complication: "Complication") -> bool:
        """Check if complication has effects that prevent continuation.

        Args:
            complication: The complication to check.

        Returns:
            True if actor is incapacitated.
        """
        from src.oracle.complication_types import EffectType

        for effect in complication.mechanical_effects:
            if effect.type == EffectType.STATUS_ADD:
                if effect.value and str(effect.value).lower() in INCAPACITATING_STATUSES:
                    return True
        return False

    def _actions_still_plausible(
        self,
        actions: list[Action],
        complication: "Complication",
    ) -> bool:
        """Check if remaining actions are still reasonable after complication.

        Args:
            actions: Remaining actions in chain.
            complication: The triggered complication.

        Returns:
            True if actions could still be attempted.
        """
        if not actions:
            return True

        from src.oracle.complication_types import EffectType

        # If complication spawned a hostile entity, non-combat actions are implausible
        for effect in complication.mechanical_effects:
            if effect.type == EffectType.SPAWN_ENTITY:
                # Check if any remaining action is non-combat
                combat_types = {ActionType.ATTACK, ActionType.FLEE, ActionType.DEFEND}
                for action in actions:
                    if action.type not in combat_types:
                        return False

        return True

    def _has_significant_cost(self, complication: "Complication") -> bool:
        """Check if complication has significant cost that warrants player choice.

        Args:
            complication: The complication to check.

        Returns:
            True if complication has HP loss or status effect.
        """
        from src.oracle.complication_types import EffectType

        for effect in complication.mechanical_effects:
            if effect.type in {EffectType.HP_LOSS, EffectType.STATUS_ADD}:
                return True
        return False

    def _update_state_snapshot(
        self,
        state: dict[str, Any],
        execution: "ExecutionResult",
        action: Action,
    ) -> dict[str, Any]:
        """Update state snapshot based on execution result.

        Args:
            state: Current state snapshot.
            execution: Result of executing the action.
            action: The action that was executed.

        Returns:
            Updated state snapshot.
        """
        new_state = dict(state)
        metadata = execution.metadata

        # Movement actions update location
        if action.type in {ActionType.MOVE, ActionType.ENTER, ActionType.EXIT}:
            if metadata.get("to_location"):
                new_state["previous_location"] = state.get("player_location")
                new_state["player_location"] = metadata["to_location"]
                new_state["location_changed"] = True

        # Time-advancing actions accumulate time
        if action.type in {ActionType.REST, ActionType.WAIT, ActionType.SLEEP}:
            minutes = metadata.get("minutes", 0)
            new_state["time_advance_minutes"] = (
                state.get("time_advance_minutes", 0) + minutes
            )

        # Combat actions set combat flag
        if action.type == ActionType.ATTACK:
            new_state["combat_active"] = True

        # Inventory actions flag for re-query
        if action.type in {ActionType.TAKE, ActionType.DROP, ActionType.GIVE}:
            new_state["inventory_changed"] = True

        return new_state

    def _get_location_danger(self, location_key: str) -> str:
        """Get danger level for a location.

        Args:
            location_key: Key of the location.

        Returns:
            Danger level string: "safe", "neutral", "risky", "dangerous", "hostile"
        """
        if not location_key:
            return "neutral"

        # Try to get from location category/atmosphere
        from src.managers.location_manager import LocationManager

        loc_manager = LocationManager(self.db, self.game_session)
        location = loc_manager.get_location(location_key)

        if location:
            # Check category for danger hints
            category = getattr(location, 'category', None)
            if category:
                cat_lower = category.lower()
                if cat_lower in ('dungeon', 'wilderness', 'cave'):
                    return "dangerous"
                if cat_lower in ('forest', 'road'):
                    return "risky"
                if cat_lower in ('home', 'temple', 'church', 'shop'):
                    return "safe"

        # Default based on location type keywords
        key_lower = location_key.lower()
        if any(kw in key_lower for kw in ["home", "temple", "church", "safe"]):
            return "safe"
        if any(kw in key_lower for kw in ["dungeon", "cave", "crypt", "lair"]):
            return "dangerous"
        if any(kw in key_lower for kw in ["forest", "road", "wild"]):
            return "risky"

        return "neutral"

    def _build_continuation_prompt(
        self,
        remaining_actions: list[Action],
        complication: "Complication",
    ) -> str:
        """Build the prompt to ask player about continuing.

        Args:
            remaining_actions: Actions not yet processed.
            complication: The complication that paused the chain.

        Returns:
            Question string for the narrator to include.
        """
        if not remaining_actions:
            return ""

        # Build description of what player was trying to do
        next_action = remaining_actions[0]
        action_desc = f"{next_action.type.value.lower()}"
        if next_action.target:
            action_desc += f" {next_action.target}"

        return f"Do you want to continue with {action_desc}?"
