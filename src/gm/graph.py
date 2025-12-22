"""Simplified GM Graph for the new pipeline.

A single, straightforward graph that:
1. Builds context
2. Calls the GM LLM with tools
3. Validates the response
4. Applies state changes
"""

import logging
from typing import Any, TypedDict

from langgraph.graph import StateGraph, END
from sqlalchemy.orm import Session

from src.database.models.session import GameSession
from src.gm.gm_node import GMNode
from src.gm.validator import ResponseValidator
from src.gm.applier import StateApplier
from src.gm.schemas import GMResponse

logger = logging.getLogger(__name__)


class GMState(TypedDict, total=False):
    """State for the simplified GM graph."""

    # Input (from CLI)
    session_id: int
    player_id: int
    player_location: str
    player_input: str
    turn_number: int

    # Internal
    _db: Session
    _game_session: GameSession

    # Working state
    _gm_response_obj: GMResponse | None  # Internal GMResponse object

    # Output (CLI-compatible keys)
    gm_response: str  # Narrative text (CLI displays this)
    is_ooc: bool  # Whether this is an OOC response
    new_location: str | None
    location_changed: bool
    errors: list[str]
    skill_checks: list[dict]  # For interactive display

    # Config
    roll_mode: str


async def gm_node(state: GMState) -> dict[str, Any]:
    """Run the GM LLM with tools.

    Args:
        state: Current graph state.

    Returns:
        Partial state update with gm_response.
    """
    db = state.get("_db")
    game_session = state.get("_game_session")
    player_id = state.get("player_id")
    player_location = state.get("player_location")
    player_input = state.get("player_input", "")
    turn_number = state.get("turn_number", 1)
    roll_mode = state.get("roll_mode", "auto")

    if not all([db, game_session, player_id, player_location]):
        return {
            "gm_response": "",
            "errors": ["Missing required state: db, game_session, player_id, or player_location"],
        }

    try:
        node = GMNode(
            db=db,
            game_session=game_session,
            player_id=player_id,
            location_key=player_location,
            roll_mode=roll_mode,
        )
        response = await node.run(player_input, turn_number)

        # Extract skill checks for interactive display
        skill_checks = []
        for result in response.tool_results:
            if result["tool"] == "skill_check":
                skill_checks.append(result["result"])

        return {
            "_gm_response_obj": response,
            "gm_response": response.narrative,
            "is_ooc": response.is_ooc,
            "skill_checks": skill_checks,
        }

    except Exception as e:
        logger.exception("GM node error")
        return {
            "gm_response": "",
            "errors": [str(e)],
        }


async def validator_node(state: GMState) -> dict[str, Any]:
    """Validate the GM response.

    Args:
        state: Current graph state.

    Returns:
        Partial state update with validation results.
    """
    db = state.get("_db")
    game_session = state.get("_game_session")
    player_id = state.get("player_id")
    player_location = state.get("player_location")
    gm_response_obj = state.get("_gm_response_obj")

    if not gm_response_obj:
        return {"errors": ["No GM response to validate"]}

    validator = ResponseValidator(
        db=db,
        game_session=game_session,
        player_id=player_id,
        location_key=player_location,
    )

    result = validator.validate(gm_response_obj)

    if not result.valid:
        # Log validation issues but don't block
        for issue in result.issues:
            logger.warning(f"Validation issue: {issue.category} - {issue.message}")

    return {}  # Don't modify state for now, just log


async def applier_node(state: GMState) -> dict[str, Any]:
    """Apply state changes from the GM response.

    Args:
        state: Current graph state.

    Returns:
        Partial state update with new location.
    """
    db = state.get("_db")
    game_session = state.get("_game_session")
    player_id = state.get("player_id")
    player_location = state.get("player_location")
    player_input = state.get("player_input", "")
    turn_number = state.get("turn_number", 1)
    gm_response_obj = state.get("_gm_response_obj")

    if not gm_response_obj:
        return {"errors": ["No GM response to apply"]}

    applier = StateApplier(
        db=db,
        game_session=game_session,
        player_id=player_id,
        location_key=player_location,
    )

    new_location = applier.apply(gm_response_obj, player_input, turn_number)

    # Track if location changed for CLI display
    location_changed = new_location != player_location

    return {
        "new_location": new_location,
        "player_location": new_location,  # Update for next turn (CLI uses this key)
        "location_changed": location_changed,
    }


def build_gm_graph() -> StateGraph:
    """Build the simplified GM graph.

    Returns:
        Compiled StateGraph for the GM pipeline.
    """
    graph = StateGraph(GMState)

    # Add nodes
    graph.add_node("gm", gm_node)
    graph.add_node("validator", validator_node)
    graph.add_node("applier", applier_node)

    # Set entry point
    graph.set_entry_point("gm")

    # Add edges
    graph.add_edge("gm", "validator")
    graph.add_edge("validator", "applier")
    graph.add_edge("applier", END)

    return graph.compile()


# Convenience function for running the graph
async def run_gm_graph(
    db: Session,
    game_session: GameSession,
    player_id: int,
    player_location: str,
    player_input: str,
    turn_number: int = 1,
    roll_mode: str = "auto",
) -> dict[str, Any]:
    """Run the GM graph for a single turn.

    Args:
        db: Database session.
        game_session: Current game session.
        player_id: Player entity ID.
        player_location: Current location key.
        player_input: Player's input.
        turn_number: Current turn number.
        roll_mode: "auto" or "manual".

    Returns:
        Final state with gm_response (narrative) and player_location.
    """
    graph = build_gm_graph()

    initial_state: GMState = {
        "session_id": game_session.id,
        "player_id": player_id,
        "player_location": player_location,
        "player_input": player_input,
        "turn_number": turn_number,
        "_db": db,
        "_game_session": game_session,
        "roll_mode": roll_mode,
        "_gm_response_obj": None,
        "gm_response": "",
        "is_ooc": False,
        "new_location": None,
        "location_changed": False,
        "errors": [],
        "skill_checks": [],
    }

    result = await graph.ainvoke(initial_state)
    return result
