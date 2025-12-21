"""World Mechanics node for Scene-First Architecture.

This node invokes WorldMechanics to determine the world state:
- Which NPCs are present at the player's location
- World events occurring
- New elements to introduce

This node runs BEFORE scene building and narration.
"""

from typing import Any, TYPE_CHECKING

from src.agents.state import GameState

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from src.database.models.session import GameSession


async def world_mechanics_node(state: GameState) -> dict[str, Any]:
    """Determine world state at player's location.

    This node:
    1. Gets the player's current location
    2. Invokes WorldMechanics to determine NPCs and events
    3. Returns the WorldUpdate for scene building

    Args:
        state: Current game state with player location and db/session.

    Returns:
        Partial state update with world_update dict.
    """
    db: Session | None = state.get("_db")
    game_session: GameSession | None = state.get("_game_session")

    if db is None or game_session is None:
        return {
            "world_update": None,
            "errors": ["Missing database session"],
        }

    location_key = state.get("player_location", "")
    if not location_key:
        return {
            "world_update": None,
            "errors": ["No player location set"],
        }

    # Check if player just entered this location
    location_changed = state.get("location_changed", False)
    just_entered = location_changed or state.get("just_entered_location", False)

    # Import here to avoid circular imports
    from src.world.world_mechanics import WorldMechanics
    from src.database.models.world import Location
    from src.database.models.entities import Entity
    from src.database.models.enums import EntityType

    location = (
        db.query(Location)
        .filter(
            Location.session_id == game_session.id,
            Location.location_key == location_key,
        )
        .first()
    )

    location_type = location.category if location else "general"

    # Check if this is player's home
    is_player_home = False
    player = (
        db.query(Entity)
        .filter(
            Entity.session_id == game_session.id,
            Entity.entity_type == EntityType.PLAYER,
        )
        .first()
    )
    if player and player.npc_extension:
        is_player_home = player.npc_extension.home_location == location_key

    # Initialize WorldMechanics and advance world
    world_mechanics = WorldMechanics(
        db=db,
        game_session=game_session,
        llm_provider=None,  # LLM-driven elements deferred to Phase 7 enhancements
    )

    try:
        world_update = world_mechanics.advance_world(
            location_key=location_key,
            location_type=location_type,
            is_player_home=is_player_home,
        )

        # Convert to dict for state serialization
        world_update_dict = world_update.model_dump()

        return {
            "world_update": world_update_dict,
            "just_entered_location": just_entered,
        }

    except Exception as e:
        return {
            "world_update": None,
            "errors": [f"World mechanics failed: {str(e)}"],
        }
