"""Context compiler node for gathering scene context.

This node wraps the ContextCompiler manager to build scene context
for the GameMaster's prompt.
"""

from typing import Any, Callable, Coroutine

from sqlalchemy.orm import Session

from src.agents.state import GameState
from src.database.models.session import GameSession
from src.managers.context_compiler import ContextCompiler


async def context_compiler_node(state: GameState) -> dict[str, Any]:
    """Compile scene context from game state.

    This is the default node function that expects _db and _game_session
    to be present in state. For cleaner dependency injection, use
    create_context_compiler_node() factory.

    Args:
        state: Current game state with _db and _game_session.

    Returns:
        Partial state update with scene_context and next_agent.
    """
    db: Session = state.get("_db")  # type: ignore
    game_session: GameSession = state.get("_game_session")  # type: ignore

    if db is None or game_session is None:
        return {
            "scene_context": "",
            "next_agent": "game_master",
            "errors": ["Missing database session or game session in state"],
        }

    return await _compile_context(
        db=db,
        game_session=game_session,
        player_id=state["player_id"],
        player_location=state["player_location"],
    )


def create_context_compiler_node(
    db: Session,
    game_session: GameSession,
) -> Callable[[GameState], Coroutine[Any, Any, dict[str, Any]]]:
    """Create a context compiler node with bound dependencies.

    This factory pattern allows clean dependency injection without
    putting database sessions into the state dictionary.

    Args:
        db: Database session.
        game_session: Current game session.

    Returns:
        Async node function that compiles context.
    """

    async def node(state: GameState) -> dict[str, Any]:
        """Compile scene context for GM prompt.

        Args:
            state: Current game state.

        Returns:
            Partial state update with scene_context and next_agent.
        """
        return await _compile_context(
            db=db,
            game_session=game_session,
            player_id=state["player_id"],
            player_location=state["player_location"],
        )

    return node


async def _compile_context(
    db: Session,
    game_session: GameSession,
    player_id: int,
    player_location: str,
) -> dict[str, Any]:
    """Internal helper to compile context.

    Args:
        db: Database session.
        game_session: Current game session.
        player_id: Player entity ID.
        player_location: Current location key.

    Returns:
        Partial state update.
    """
    compiler = ContextCompiler(db, game_session)

    scene_context = compiler.compile_scene(
        player_id=player_id,
        location_key=player_location,
        include_secrets=True,
    )

    return {
        "scene_context": scene_context.to_prompt(include_secrets=True),
        "next_agent": "game_master",
    }
