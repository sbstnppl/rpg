"""Subturn processor node for chained multi-action turns.

This node replaces the sequential validate_actions -> dynamic_planner ->
complication_oracle -> execute_actions flow with a single node that
processes actions as sequential subturns with state updates between them.

Each action is:
1. Validated against CURRENT state (not initial state)
2. Checked for interrupts (complications)
3. Executed with state update for next subturn
4. Recorded in the chained turn result
"""

import logging
from typing import Any

from sqlalchemy.orm import Session

from src.agents.state import GameState
from src.database.models.entities import Entity
from src.database.models.session import GameSession
from src.executor.subturn_processor import (
    ChainedTurnResult,
    ContinuationStatus,
    SubturnProcessor,
)
from src.llm.factory import get_gm_provider
from src.parser.action_types import Action, ActionType
from src.validators.action_validator import ActionValidator

logger = logging.getLogger(__name__)


async def _plan_custom_actions(
    actions: list[Action],
    actor: "Entity",
    db: Session,
    game_session: "GameSession",
    scene_context: str,
    player_location: str,
) -> tuple[dict[str, Any], str, str]:
    """Plan CUSTOM actions via DynamicActionPlanner.

    This calls the LLM to determine response_mode (INFO vs NARRATE)
    and generate execution plans for freeform actions.

    Args:
        actions: List of actions to check for CUSTOM types.
        actor: Player entity performing actions.
        db: Database session.
        game_session: Current game session.
        scene_context: Current scene context string.
        player_location: Current player location key.

    Returns:
        Tuple of (dynamic_plans dict, response_mode, narrative_style).
    """
    # Find CUSTOM actions
    custom_actions = [a for a in actions if a.type == ActionType.CUSTOM]

    if not custom_actions:
        return {}, "narrate", "action"

    # Get LLM provider for structured output
    try:
        from src.llm.factory import get_extraction_provider

        llm_provider = get_extraction_provider()
    except Exception as e:
        logger.error(f"Failed to get LLM provider for planning: {e}")
        return {}, "narrate", "action"

    # Create planner
    from src.planner.dynamic_action_planner import DynamicActionPlanner

    planner = DynamicActionPlanner(db, game_session, llm_provider)

    # Plan each custom action
    plans: dict[str, Any] = {}
    response_mode = "narrate"
    narrative_style = "action"

    for action in custom_actions:
        try:
            plan = await planner.plan(
                action, actor, scene_context, actor_location=player_location
            )

            # Store plan keyed by raw_input for executor lookup
            raw_input = action.parameters.get("raw_input", str(action))
            plan_dict = plan.model_dump()
            plans[raw_input] = plan_dict

            # Store relevant state in the plan for narrator/validator context
            relevant_state = planner._gather_relevant_state(actor, player_location)
            plan_dict["_relevant_state"] = {
                "items_at_location": relevant_state.items_at_location,
                "npcs_present": relevant_state.npcs_present,
                "inventory": relevant_state.inventory,
                "equipped": relevant_state.equipped,
            }

            # Use the first plan's response_mode and narrative_style
            if response_mode == "narrate":
                response_mode = plan_dict.get("response_mode", "narrate")
                narrative_style = plan_dict.get("narrative_style", "action")

            logger.info(
                f"Generated plan for '{raw_input[:50]}...': "
                f"type={plan.action_type}, mode={plan.response_mode}, "
                f"style={plan.narrative_style}, changes={len(plan.state_changes)}"
            )
        except Exception as e:
            logger.error(f"Failed to plan action: {e}")
            # Continue with other actions

    return plans, response_mode, narrative_style


async def subturn_processor_node(state: GameState) -> dict[str, Any]:
    """Process parsed actions as sequential subturns.

    This node handles multi-action inputs by processing each action
    sequentially with state updates between them. Complications can
    interrupt the chain.

    Args:
        state: Current game state with parsed_actions.

    Returns:
        Partial state update with chained_turn_result and related fields.
    """
    db: Session = state.get("_db")  # type: ignore
    game_session: GameSession = state.get("_game_session")  # type: ignore

    if db is None or game_session is None:
        return {
            "chained_turn_result": None,
            "errors": ["Missing database session or game session in state"],
        }

    parsed_actions = state.get("parsed_actions", [])

    # Handle scene requests - skip action processing entirely
    if state.get("is_scene_request"):
        return {
            "chained_turn_result": ChainedTurnResult().to_dict(),
            "continuation_status": None,
            "queued_actions": None,
        }

    if not parsed_actions:
        return {
            "chained_turn_result": ChainedTurnResult().to_dict(),
            "continuation_status": None,
            "queued_actions": None,
        }

    # Get actor (player entity)
    player_id = state.get("player_id")
    if not player_id:
        return {
            "chained_turn_result": ChainedTurnResult().to_dict(),
            "errors": ["Missing player_id in state"],
        }

    actor = db.query(Entity).filter(Entity.id == player_id).first()
    if not actor:
        return {
            "chained_turn_result": ChainedTurnResult().to_dict(),
            "errors": [f"Player entity not found: {player_id}"],
        }

    # Convert action dicts to Action objects
    actions = []
    for action_dict in parsed_actions:
        action = Action(
            type=ActionType(action_dict["type"]),
            target=action_dict.get("target"),
            indirect_target=action_dict.get("indirect_target"),
            manner=action_dict.get("manner"),
            parameters=action_dict.get("parameters", {}),
        )
        actions.append(action)

    # Plan CUSTOM actions via DynamicActionPlanner (determines response_mode via LLM)
    dynamic_plans, response_mode, narrative_style = await _plan_custom_actions(
        actions=actions,
        actor=actor,
        db=db,
        game_session=game_session,
        scene_context=state.get("scene_context", ""),
        player_location=state.get("player_location", ""),
    )

    # Build initial state snapshot
    initial_state = {
        "player_location": state.get("player_location", ""),
        "scene_context": state.get("scene_context", ""),
        "time_advance_minutes": state.get("time_advance_minutes", 0),
        "combat_active": state.get("combat_active", False),
    }

    # Create components
    combat_active = state.get("combat_active", False)
    validator = ActionValidator(db, game_session, combat_active=combat_active)

    # Create LLM provider for oracle (optional)
    try:
        llm_provider = get_gm_provider()
    except Exception as e:
        logger.warning(f"Could not create LLM for oracle: {e}")
        llm_provider = None

    # Lazy import to avoid circular dependency
    from src.oracle.complication_oracle import ComplicationOracle

    oracle = ComplicationOracle(
        db=db,
        game_session=game_session,
        llm_provider=llm_provider,
    )

    # Create subturn processor
    processor = SubturnProcessor(
        db=db,
        game_session=game_session,
        oracle=oracle,
        validator=validator,
    )

    # Process the action chain
    result = await processor.process_chain(
        actions=actions,
        actor=actor,
        initial_state=initial_state,
        dynamic_plans=dynamic_plans,
    )

    # Build turn_result for backward compatibility with narrator
    # This aggregates all successful executions
    turn_result = _build_turn_result(result)

    # Determine continuation status for next turn
    continuation_status = None
    queued_actions = None

    if result.continuation_offered:
        continuation_status = ContinuationStatus.OFFER_CHOICE.value
        # Store remaining actions for potential continuation
        queued_actions = [
            {
                "type": a.type.value,
                "target": a.target,
                "indirect_target": a.indirect_target,
                "manner": a.manner,
                "parameters": a.parameters or {},
            }
            for a in result.remaining_actions
        ]

    # Extract location/time changes from final state
    location_changed = result.final_state_snapshot.get("location_changed", False)
    new_location = result.final_state_snapshot.get("player_location")
    previous_location = result.final_state_snapshot.get("previous_location")
    time_advance = result.final_state_snapshot.get("time_advance_minutes", 0)

    # Extract complication if any
    complication = None
    if result.interrupting_complication:
        complication = result.interrupting_complication.to_dict()

    return {
        "chained_turn_result": result.to_dict(),
        "turn_result": turn_result,
        "dynamic_plans": dynamic_plans,
        "response_mode": response_mode,
        "narrative_style": narrative_style,
        "continuation_status": continuation_status,
        "queued_actions": queued_actions,
        "continuation_prompt": result.continuation_prompt,
        "complication": complication,
        # Location updates
        "location_changed": location_changed,
        "player_location": new_location if location_changed else state.get("player_location"),
        "previous_location": previous_location,
        # Time updates
        "time_advance_minutes": time_advance,
        # Combat state
        "combat_active": result.final_state_snapshot.get("combat_active", False),
    }


def _build_turn_result(result: ChainedTurnResult) -> dict[str, Any]:
    """Build a turn_result dict from ChainedTurnResult for narrator compatibility.

    The narrator expects turn_result with executions[] and failed_actions[].
    This converts the subturn-based structure.

    Args:
        result: ChainedTurnResult from subturn processor.

    Returns:
        Dict compatible with existing narrator expectations.
    """
    executions = []
    failed_actions = []

    for subturn in result.subturns:
        if subturn.execution and subturn.execution.success:
            executions.append({
                "action": {
                    "type": subturn.action.type.value,
                    "target": subturn.action.target,
                    "indirect_target": subturn.action.indirect_target,
                },
                "success": True,
                "outcome": subturn.execution.outcome,
                "state_changes": subturn.execution.state_changes,
                "metadata": subturn.execution.metadata,
            })
        elif not subturn.validation.valid:
            failed_actions.append({
                "action": {
                    "type": subturn.action.type.value,
                    "target": subturn.action.target,
                    "indirect_target": subturn.action.indirect_target,
                },
                "reason": subturn.validation.reason,
            })

    return {
        "executions": executions,
        "failed_actions": failed_actions,
        "new_facts": [],  # Could aggregate from subturns if needed
    }
