"""Scene generator for anticipatory pre-generation.

This module provides lightweight scene generation that can run in the
background while the player reads. It generates scene descriptions and
NPC/item data for predicted locations.
"""

import logging
import time
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from src.database.models.entities import Entity
from src.database.models.enums import EntityType
from src.database.models.session import GameSession
from src.database.models.world import Location
from src.managers.entity_manager import EntityManager
from src.managers.item_manager import ItemManager
from src.managers.location_manager import LocationManager
from src.world_server.schemas import PreGeneratedScene, PredictionReason

logger = logging.getLogger(__name__)


class SceneGenerator:
    """Generates scene data for anticipated locations.

    This is a lightweight generator that prepares scene data (NPCs, items,
    atmosphere) without running the full GM LLM. The generated data can be
    cached and used to speed up scene transitions.
    """

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
    ) -> None:
        """Initialize scene generator.

        Args:
            db: Database session.
            game_session: Current game session.
        """
        self.db = db
        self.game_session = game_session
        self._entity_manager = EntityManager(db, game_session)
        self._item_manager = ItemManager(db, game_session)
        self._location_manager = LocationManager(db, game_session)

    async def generate_scene(
        self,
        location_key: str,
        prediction_reason: PredictionReason | None = None,
    ) -> PreGeneratedScene | None:
        """Generate scene data for a location.

        Gathers all relevant data for the location from the database,
        preparing it for use when the player arrives.

        Args:
            location_key: The location to generate a scene for.
            prediction_reason: Why this location was predicted.

        Returns:
            PreGeneratedScene with all location data, or None if location not found.
        """
        start_time = time.time()

        # Get location
        location = (
            self.db.query(Location)
            .filter(
                Location.session_id == self.game_session.id,
                Location.location_key == location_key,
            )
            .first()
        )

        if not location:
            logger.debug(f"Location not found: {location_key}")
            return None

        # Gather NPCs at location
        npcs = self._entity_manager.get_npcs_in_scene(location_key)
        npcs_data = [self._serialize_npc(npc) for npc in npcs]

        # Gather items at location
        items = self._item_manager.get_items_at_location(location_key)
        items_data = [self._serialize_item(item) for item in items]

        # Build scene manifest
        scene_manifest = {
            "location_key": location_key,
            "display_name": location.display_name,
            "description": location.description or "",
            "category": location.category,
            "atmosphere": location.atmosphere or "",
            "parent_location": location.parent_location,
        }

        # Get exits
        try:
            exits = self._location_manager.get_accessible_locations(location_key)
            scene_manifest["exits"] = [
                {"key": e.location_key, "name": e.display_name}
                for e in exits
            ]
        except Exception:
            scene_manifest["exits"] = []

        # Build atmosphere dict
        atmosphere = {
            "description": location.atmosphere or "",
            "time_of_day": self._get_time_of_day(),
        }

        generation_time = (time.time() - start_time) * 1000  # Convert to ms

        return PreGeneratedScene(
            location_key=location_key,
            location_display_name=location.display_name,
            scene_manifest=scene_manifest,
            npcs_present=npcs_data,
            items_present=items_data,
            furniture=[],  # Could be expanded to include furniture entities
            atmosphere=atmosphere,
            generated_at=datetime.now(),
            generation_time_ms=generation_time,
            prediction_reason=prediction_reason,
        )

    def _serialize_npc(self, npc: Entity) -> dict[str, Any]:
        """Serialize NPC entity for caching.

        Args:
            npc: NPC entity to serialize.

        Returns:
            Dict with NPC data.
        """
        data = {
            "id": npc.id,
            "entity_key": npc.entity_key,
            "display_name": npc.display_name,
            "occupation": npc.occupation,
        }

        # Add NPC extension data if available
        if npc.npc_extension:
            data["current_location"] = npc.npc_extension.current_location
            data["mood"] = npc.npc_extension.current_mood
            data["activity"] = npc.npc_extension.current_activity
            data["home_location"] = npc.npc_extension.home_location

        return data

    def _serialize_item(self, item) -> dict[str, Any]:
        """Serialize item for caching.

        Args:
            item: Item to serialize.

        Returns:
            Dict with item data.
        """
        item_type = item.item_type.value if hasattr(item.item_type, 'value') else str(item.item_type)
        return {
            "id": item.id,
            "item_key": item.item_key,
            "display_name": item.display_name,
            "item_type": item_type,
            "is_visible": item.is_visible,
        }

    def _get_time_of_day(self) -> str:
        """Get current time of day for atmosphere.

        Returns:
            Time period string (morning, afternoon, evening, night).
        """
        from src.database.models.world import TimeState

        time_state = (
            self.db.query(TimeState)
            .filter(TimeState.session_id == self.game_session.id)
            .first()
        )

        if not time_state or not time_state.current_time:
            return "day"

        try:
            hour = int(time_state.current_time.split(":")[0])
            if hour < 6:
                return "night"
            elif hour < 12:
                return "morning"
            elif hour < 18:
                return "afternoon"
            elif hour < 22:
                return "evening"
            else:
                return "night"
        except (ValueError, IndexError):
            return "day"


def create_scene_generator_callback(
    db: Session,
    game_session: GameSession,
):
    """Create a scene generator callback for the anticipation engine.

    This returns an async function that can be passed to
    WorldServerManager.trigger_anticipation().

    Args:
        db: Database session.
        game_session: Current game session.

    Returns:
        Async function that generates scenes.
    """
    generator = SceneGenerator(db, game_session)

    async def generate(location_key: str) -> PreGeneratedScene | None:
        return await generator.generate_scene(location_key)

    return generate
