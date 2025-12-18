"""Dynamic planner node for the System-Authority architecture.

This node intercepts CUSTOM actions and transforms them into
structured execution plans that can be executed mechanically.
"""

import logging
from typing import Any

from sqlalchemy.orm import Session

from src.agents.state import GameState
from src.database.models.entities import Entity
from src.database.models.session import GameSession
from src.parser.action_types import Action, ActionType

logger = logging.getLogger(__name__)


async def dynamic_planner_node(state: GameState) -> dict[str, Any]:
    """Plan execution of CUSTOM actions.

    This node:
    1. Finds CUSTOM actions in validation_results
    2. For each, calls DynamicActionPlanner to generate a plan
    3. Attaches plans to the state for the executor to use

    Args:
        state: Current game state with validation_results.

    Returns:
        Partial state update with dynamic_plans.
    """
    db: Session = state.get("_db")  # type: ignore
    game_session: GameSession = state.get("_game_session")  # type: ignore

    if db is None or game_session is None:
        return {
            "dynamic_plans": {},
            "errors": ["Missing database session or game session in state"],
        }

    validation_results = state.get("validation_results", [])
    if not validation_results:
        return {"dynamic_plans": {}}

    # Find CUSTOM actions
    custom_actions = []
    for result in validation_results:
        action_dict = result.get("action", {})
        action_type = action_dict.get("type")
        if action_type == "custom" or action_type == ActionType.CUSTOM.value:
            custom_actions.append(result)

    if not custom_actions:
        # No custom actions, pass through unchanged
        return {"dynamic_plans": {}}

    # Get actor
    player_id = state.get("player_id")
    if not player_id:
        return {
            "dynamic_plans": {},
            "errors": ["Missing player_id in state"],
        }

    actor = db.query(Entity).filter(Entity.id == player_id).first()
    if not actor:
        return {
            "dynamic_plans": {},
            "errors": [f"Player entity not found: {player_id}"],
        }

    # Get scene context
    scene_context = state.get("scene_context", "")

    # Get LLM provider (lazy import to avoid circular dependency)
    try:
        from src.llm.factory import get_extraction_provider

        llm_provider = get_extraction_provider()
    except Exception as e:
        logger.error(f"Failed to get LLM provider: {e}")
        return {
            "dynamic_plans": {},
            "errors": [f"LLM provider unavailable: {e}"],
        }

    # Create planner (lazy import to avoid circular dependency)
    from src.planner.dynamic_action_planner import DynamicActionPlanner

    planner = DynamicActionPlanner(db, game_session, llm_provider)

    # Plan each custom action
    plans = {}
    for result in custom_actions:
        action_dict = result.get("action", {})

        # Reconstruct Action
        action = Action(
            type=ActionType.CUSTOM,
            target=action_dict.get("target"),
            indirect_target=action_dict.get("indirect_target"),
            manner=action_dict.get("manner"),
            parameters=action_dict.get("parameters", {}),
        )

        # Generate plan
        try:
            plan = await planner.plan(action, actor, scene_context)

            # Store plan keyed by raw_input for executor lookup
            raw_input = action.parameters.get("raw_input", str(action))
            plans[raw_input] = plan.model_dump()

            logger.info(
                f"Generated plan for '{raw_input[:50]}...': "
                f"type={plan.action_type}, changes={len(plan.state_changes)}"
            )
        except Exception as e:
            logger.error(f"Failed to plan action: {e}")
            # Continue with other actions

    return {"dynamic_plans": plans}
