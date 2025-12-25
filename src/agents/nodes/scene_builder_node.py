"""Scene Builder node for Scene-First Architecture.

This node invokes SceneBuilder to generate or load scene contents:
- First visit: Generates furniture, items, atmosphere via LLM
- Return visit: Loads existing scene from database
- Merges NPCs from WorldUpdate
- Filters items based on observation level

This node runs AFTER world_mechanics_node.
"""

from typing import Any, TYPE_CHECKING

from src.agents.state import GameState

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from src.database.models.session import GameSession


async def scene_builder_node(state: GameState) -> dict[str, Any]:
    """Build scene manifest for current location.

    This node:
    1. Gets the WorldUpdate from previous node
    2. Invokes SceneBuilder to generate or load scene
    3. Returns the SceneManifest for persistence and narration

    Args:
        state: Current game state with world_update and location.

    Returns:
        Partial state update with scene_manifest dict.
    """
    db: Session | None = state.get("_db")
    game_session: GameSession | None = state.get("_game_session")

    if db is None or game_session is None:
        return {
            "scene_manifest": None,
            "errors": ["Missing database session"],
        }

    location_key = state.get("player_location", "")
    if not location_key:
        return {
            "scene_manifest": None,
            "errors": ["No player location set"],
        }

    # Import here to avoid circular imports
    from src.llm.factory import get_creative_provider
    from src.world.scene_builder import SceneBuilder
    from src.world.schemas import ObservationLevel, WorldUpdate

    # Get world update from previous node
    world_update_dict = state.get("world_update")
    if world_update_dict is None:
        # Create empty world update if not present
        world_update = WorldUpdate(
            npcs_at_location=[],
            scheduled_movements=[],
            new_elements=[],
            events=[],
            fact_updates=[],
        )
    else:
        world_update = WorldUpdate.model_validate(world_update_dict)

    # Determine observation level based on player action
    observation_level = _determine_observation_level(state)

    # Try to get LLM provider for first-visit scene generation
    try:
        llm_provider = get_creative_provider()
    except Exception:
        llm_provider = None

    # Initialize SceneBuilder
    scene_builder = SceneBuilder(
        db=db,
        game_session=game_session,
        llm_provider=llm_provider,
    )

    try:
        scene_manifest = await scene_builder.build_scene(
            location_key=location_key,
            world_update=world_update,
            observation_level=observation_level,
        )

        # Convert to dict for state serialization
        scene_manifest_dict = scene_manifest.model_dump()

        return {
            "scene_manifest": scene_manifest_dict,
        }

    except ValueError as e:
        # Location not found
        return {
            "scene_manifest": None,
            "errors": [f"Scene building failed for '{location_key}': {str(e)}"],
        }
    except Exception as e:
        import traceback
        return {
            "scene_manifest": None,
            "errors": [f"Scene building failed for '{location_key}': {str(e)} - {traceback.format_exc()[:200]}"],
        }


def _determine_observation_level(state: GameState):
    """Determine observation level from player's action.

    Args:
        state: Current game state.

    Returns:
        ObservationLevel based on player intent.
    """
    from src.world.schemas import ObservationLevel

    # Check parsed actions for observation-related actions
    parsed_actions = state.get("parsed_actions") or []

    for action in parsed_actions:
        action_type = action.get("type", "").upper()

        if action_type == "LOOK":
            return ObservationLevel.LOOK
        elif action_type == "SEARCH":
            return ObservationLevel.SEARCH
        elif action_type == "EXAMINE":
            return ObservationLevel.EXAMINE

    # Check player input for observation keywords
    player_input = state.get("player_input", "").lower()

    if any(word in player_input for word in ["search", "look for", "find"]):
        return ObservationLevel.SEARCH
    elif any(word in player_input for word in ["look", "observe", "scan"]):
        return ObservationLevel.LOOK
    elif any(word in player_input for word in ["examine", "inspect", "study"]):
        return ObservationLevel.EXAMINE

    # Just entered location - entry level
    if state.get("just_entered_location") or state.get("location_changed"):
        return ObservationLevel.ENTRY

    # Default to entry
    return ObservationLevel.ENTRY
