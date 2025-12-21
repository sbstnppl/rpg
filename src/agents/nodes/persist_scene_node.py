"""Persist Scene node for Scene-First Architecture.

This node persists scene data to the database:
- World Update: new NPCs, events, facts
- Scene Manifest: furniture, items
- Builds the NarratorManifest for constrained narration

This node runs AFTER scene_builder_node.
"""

from typing import Any, TYPE_CHECKING

from src.agents.state import GameState

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from src.database.models.session import GameSession


async def persist_scene_node(state: GameState) -> dict[str, Any]:
    """Persist scene data to database and build narrator manifest.

    This node:
    1. Persists WorldUpdate (new NPCs, facts)
    2. Persists SceneManifest (furniture, items)
    3. Builds NarratorManifest for constrained narration

    Args:
        state: Current game state with world_update and scene_manifest.

    Returns:
        Partial state update with narrator_manifest dict.
    """
    db: Session | None = state.get("_db")
    game_session: GameSession | None = state.get("_game_session")

    if db is None or game_session is None:
        return {
            "narrator_manifest": None,
            "errors": ["Missing database session"],
        }

    location_key = state.get("player_location", "")
    turn_number = state.get("turn_number", 1)

    # Import here to avoid circular imports
    from src.world.scene_persister import ScenePersister
    from src.world.schemas import SceneManifest, WorldUpdate

    # Get scene manifest from previous node
    scene_manifest_dict = state.get("scene_manifest")
    if scene_manifest_dict is None:
        return {
            "narrator_manifest": None,
            "errors": ["No scene manifest to persist"],
        }

    scene_manifest = SceneManifest.model_validate(scene_manifest_dict)

    # Get world update from earlier node
    world_update_dict = state.get("world_update")
    if world_update_dict:
        world_update = WorldUpdate.model_validate(world_update_dict)
    else:
        world_update = None

    # Initialize ScenePersister
    persister = ScenePersister(
        db=db,
        game_session=game_session,
    )

    try:
        # Persist world update if present
        if world_update:
            persister.persist_world_update(
                world_update=world_update,
                location_key=location_key,
                turn_number=turn_number,
            )

        # Get location from database for scene persistence
        from src.database.models.world import Location

        location = (
            db.query(Location)
            .filter(
                Location.session_id == game_session.id,
                Location.location_key == location_key,
            )
            .first()
        )

        if location is None:
            return {
                "narrator_manifest": None,
                "errors": [f"Location not found: {location_key}"],
            }

        # Persist scene contents (furniture, items)
        if scene_manifest.is_first_visit:
            persister.persist_scene(
                scene_manifest=scene_manifest,
                location=location,
                turn_number=turn_number,
            )

        # Build narrator manifest
        narrator_manifest = persister.build_narrator_manifest(scene_manifest)

        # Convert to dict for state serialization
        narrator_manifest_dict = narrator_manifest.model_dump()

        return {
            "narrator_manifest": narrator_manifest_dict,
        }

    except Exception as e:
        return {
            "narrator_manifest": None,
            "errors": [f"Scene persistence failed: {str(e)}"],
        }
