"""Complication Oracle node for the System-Authority architecture.

This node checks if a complication should occur and generates it if so.
Complications add narrative interest without breaking mechanics.
"""

from typing import TYPE_CHECKING, Any, Callable, Coroutine

from sqlalchemy.orm import Session

from src.agents.state import GameState
from src.database.models.session import GameSession

if TYPE_CHECKING:
    from src.llm.base import LLMProvider
    from src.oracle.complication_oracle import ComplicationOracle
    from src.oracle.complication_types import Complication


async def complication_oracle_node(state: GameState) -> dict[str, Any]:
    """Check for and generate complications.

    This is a simplified version that uses fallback generation
    (no LLM) for testing purposes.

    Args:
        state: Current game state with validation results.

    Returns:
        Partial state update with complication if triggered.
    """
    validation_results = state.get("validation_results", [])
    if not validation_results:
        return {"complication": None}

    # Collect risk tags from all validations
    risk_tags: list[str] = []
    for result in validation_results:
        if isinstance(result, dict):
            risk_tags.extend(result.get("risk_tags", []))

    # Build actions summary
    actions_summary = []
    for result in validation_results:
        if isinstance(result, dict):
            action = result.get("action", {})
            action_type = action.get("type", "unknown")
            target = action.get("target", "something")
            actions_summary.append(f"{action_type} {target}")

    # This simplified version always returns no complication
    # (use create_complication_oracle_node for full functionality)
    return {
        "complication": None,
    }


def create_complication_oracle_node(
    db: Session,
    game_session: GameSession,
    llm_provider: "LLMProvider | None" = None,
) -> Callable[[GameState], Coroutine[Any, Any, dict[str, Any]]]:
    """Create a complication oracle node with bound dependencies.

    Args:
        db: Database session.
        game_session: Current game session.
        llm_provider: Optional LLM provider for creative generation.

    Returns:
        Async node function that checks for complications.
    """

    async def node(state: GameState) -> dict[str, Any]:
        """Check for and generate complications.

        Args:
            state: Current game state.

        Returns:
            Partial state update with complication if triggered.
        """
        # Import at runtime to avoid circular imports
        from src.oracle.complication_oracle import ComplicationOracle

        validation_results = state.get("validation_results", [])
        if not validation_results:
            return {"complication": None}

        # Collect risk tags from all validations
        risk_tags: list[str] = []
        for result in validation_results:
            if isinstance(result, dict):
                risk_tags.extend(result.get("risk_tags", []))

        # Build actions summary
        actions_parts = []
        for result in validation_results:
            if isinstance(result, dict) and result.get("valid", False):
                action = result.get("action", {})
                action_type = action.get("type", "unknown")
                target = action.get("target", "something")
                actions_parts.append(f"{action_type} {target}")

        actions_summary = ", ".join(actions_parts) if actions_parts else "no actions"

        # Get scene context
        scene_context = state.get("scene_context", "A fantasy setting.")

        # Create oracle
        oracle = ComplicationOracle(
            db=db,
            game_session=game_session,
            llm_provider=llm_provider,
        )

        # Get turns since last complication
        turns_since = oracle.get_turns_since_complication()

        # Check for complication
        result = await oracle.check(
            actions_summary=actions_summary,
            scene_context=scene_context,
            risk_tags=risk_tags,
            turns_since_complication=turns_since,
        )

        # If triggered, record it
        complication_dict = None
        if result.triggered and result.complication:
            await oracle.record_complication(
                complication=result.complication,
                turn_number=game_session.total_turns,
                probability=result.probability.final_chance,
                risk_tags=risk_tags,
            )
            complication_dict = result.complication.to_dict()

        return {
            "complication": complication_dict,
        }

    return node
