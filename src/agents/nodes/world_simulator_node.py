"""World simulator node for time passage and background world updates.

This node wraps the WorldSimulator manager to handle time passage,
NPC movements, need decay, and other background world changes.
"""

from dataclasses import asdict
from typing import Any, Callable, Coroutine

from sqlalchemy.orm import Session

from src.agents.state import GameState
from src.agents.world_simulator import WorldSimulator, SimulationResult
from src.database.models.session import GameSession
from src.managers.needs import ActivityType


async def world_simulator_node(state: GameState) -> dict[str, Any]:
    """Simulate world state changes for time passage.

    This is the default node function that expects _db and _game_session
    to be present in state.

    Args:
        state: Current game state with _db and _game_session.

    Returns:
        Partial state update with simulation_result.
    """
    db: Session = state.get("_db")  # type: ignore
    game_session: GameSession = state.get("_game_session")  # type: ignore

    if db is None or game_session is None:
        return {
            "errors": ["Missing database session or game session in state"],
        }

    return await _simulate_world(db, game_session, state)


def create_world_simulator_node(
    db: Session,
    game_session: GameSession,
) -> Callable[[GameState], Coroutine[Any, Any, dict[str, Any]]]:
    """Create a world simulator node with bound dependencies.

    Args:
        db: Database session.
        game_session: Current game session.

    Returns:
        Async node function that simulates world state.
    """

    async def node(state: GameState) -> dict[str, Any]:
        """Simulate world state changes.

        Args:
            state: Current game state.

        Returns:
            Partial state update with simulation_result.
        """
        return await _simulate_world(db, game_session, state)

    return node


async def _simulate_world(
    db: Session,
    game_session: GameSession,
    state: GameState,
) -> dict[str, Any]:
    """Internal helper to simulate world state.

    Args:
        db: Database session.
        game_session: Current game session.
        state: Current game state.

    Returns:
        Partial state update.
    """
    time_advance_minutes = state.get("time_advance_minutes", 0)
    location_changed = state.get("location_changed", False)

    # Skip simulation if no time has passed and no location change
    if time_advance_minutes <= 0 and not location_changed:
        return {}

    # Ensure at least some time passes on location change (travel time)
    if location_changed and time_advance_minutes <= 0:
        time_advance_minutes = 5  # Default travel time

    hours = time_advance_minutes / 60.0

    simulator = WorldSimulator(db, game_session)

    result = simulator.simulate_time_passage(
        hours=hours,
        player_id=state["player_id"],
        player_activity=ActivityType.ACTIVE,  # TODO: Infer from context
        player_location=state.get("player_location"),
        is_player_alone=False,  # TODO: Infer from scene
    )

    return {
        "simulation_result": _simulation_result_to_dict(result),
    }


def _simulation_result_to_dict(result: SimulationResult) -> dict[str, Any]:
    """Convert SimulationResult dataclass to dict for state.

    Args:
        result: SimulationResult dataclass.

    Returns:
        Dictionary representation.
    """
    return {
        "hours_simulated": result.hours_simulated,
        "npc_movements": [
            {
                "npc_id": m.npc_id,
                "npc_name": m.npc_name,
                "from_location": m.from_location,
                "to_location": m.to_location,
                "reason": m.reason,
            }
            for m in result.npc_movements
        ],
        "needs_updated": result.needs_updated,
        "mood_modifiers_expired": result.mood_modifiers_expired,
        "missed_appointments": result.missed_appointments,
        "lighting_change": result.lighting_change,
        "crowd_change": result.crowd_change,
        "items_spoiled": result.items_spoiled,
        "items_cleaned": result.items_cleaned,
        "random_events": result.random_events,
    }
