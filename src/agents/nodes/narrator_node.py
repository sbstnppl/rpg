"""Narrator node for the System-Authority architecture.

This node generates narrative prose from mechanical results.
"""

from typing import Any, Callable, Coroutine

from sqlalchemy.orm import Session

from src.agents.state import GameState
from src.database.models.session import GameSession
from src.narrator.narrator import ConstrainedNarrator


async def narrator_node(state: GameState) -> dict[str, Any]:
    """Generate narrative from turn result.

    Uses the ConstrainedNarrator to generate prose that includes
    all mechanical facts without contradicting them.

    Args:
        state: Current game state with turn_result.

    Returns:
        Partial state update with gm_response.
    """
    turn_result = state.get("turn_result")
    if not turn_result:
        return {
            "gm_response": "Nothing happens.",
        }

    # Inject complication from state if not already in turn_result
    complication = state.get("complication")
    if complication and "complication" not in turn_result:
        turn_result = dict(turn_result)  # Make a copy
        turn_result["complication"] = complication

    scene_context = state.get("scene_context", "")
    ambient_flavor = state.get("ambient_flavor")

    # Use fallback narrator (no LLM for now - can be enhanced later)
    narrator = ConstrainedNarrator()

    result = await narrator.narrate(
        turn_result=turn_result,
        scene_context=scene_context,
        ambient_flavor=ambient_flavor,
    )

    # Collect any warnings
    errors = []
    if result.warnings:
        errors.extend(result.warnings)

    return {
        "gm_response": result.narrative,
        "errors": errors if errors else [],
    }


def create_narrator_node(
    db: Session,
    game_session: GameSession,
    llm_provider: Any = None,
) -> Callable[[GameState], Coroutine[Any, Any, dict[str, Any]]]:
    """Create a narrator node with bound dependencies.

    Args:
        db: Database session.
        game_session: Current game session.
        llm_provider: Optional LLM provider for richer narration.

    Returns:
        Async node function that generates narrative.
    """

    async def node(state: GameState) -> dict[str, Any]:
        """Generate narrative from turn result.

        Args:
            state: Current game state.

        Returns:
            Partial state update with gm_response.
        """
        turn_result = state.get("turn_result")
        if not turn_result:
            return {"gm_response": "Nothing happens."}

        # Inject complication from state if not already in turn_result
        complication = state.get("complication")
        if complication and "complication" not in turn_result:
            turn_result = dict(turn_result)  # Make a copy
            turn_result["complication"] = complication

        scene_context = state.get("scene_context", "")
        ambient_flavor = state.get("ambient_flavor")

        narrator = ConstrainedNarrator(llm_provider=llm_provider)

        result = await narrator.narrate(
            turn_result=turn_result,
            scene_context=scene_context,
            ambient_flavor=ambient_flavor,
        )

        errors = []
        if result.warnings:
            errors.extend(result.warnings)

        return {
            "gm_response": result.narrative,
            "errors": errors if errors else [],
        }

    return node
