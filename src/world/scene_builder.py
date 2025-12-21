"""SceneBuilder for Scene-First Architecture.

This module handles building scene manifests for locations:
- First visit: Generates furniture, items, and atmosphere via LLM
- Return visit: Loads existing scene from database
- Merges NPCs from WorldUpdate
- Filters items based on observation level
- Lazy-loads container contents when opened

SceneBuilder operates AFTER WorldMechanics - it receives the world state
and builds a complete scene description.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from src.database.models.enums import EntityType, StorageLocationType
from src.database.models.entities import Entity
from src.database.models.items import Item, StorageLocation
from src.database.models.world import Location, TimeState
from src.managers.base import BaseManager
from src.world.schemas import (
    Atmosphere,
    FurnitureSpec,
    ItemSpec,
    ItemVisibility,
    NPCPlacement,
    ObservationLevel,
    SceneContents,
    SceneManifest,
    SceneNPC,
    WorldUpdate,
)

if TYPE_CHECKING:
    from src.database.models.session import GameSession
    from src.llm.base import LLMProvider

logger = logging.getLogger(__name__)


# Default atmosphere when LLM is not available
DEFAULT_ATMOSPHERE = Atmosphere(
    lighting="ambient light",
    lighting_source="natural",
    sounds=[],
    smells=[],
    temperature="comfortable",
    overall_mood="neutral",
)


class SceneBuilder(BaseManager):
    """Builds scene manifests for locations.

    This class determines:
    - What furniture and items are in a scene
    - The atmosphere (lighting, sounds, smells)
    - Filters items based on observation level
    - Merges NPCs from WorldUpdate

    It operates after WorldMechanics, taking the world state and building
    a complete scene for the narrator to describe.
    """

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        llm_provider: LLMProvider | None = None,
    ) -> None:
        """Initialize SceneBuilder.

        Args:
            db: Database session.
            game_session: Current game session.
            llm_provider: Optional LLM provider for scene generation.
        """
        super().__init__(db, game_session)
        self.llm_provider = llm_provider

    # =========================================================================
    # Main Entry Point
    # =========================================================================

    async def build_scene(
        self,
        location_key: str,
        world_update: WorldUpdate,
        observation_level: ObservationLevel = ObservationLevel.ENTRY,
    ) -> SceneManifest:
        """Build a scene manifest for a location.

        This is the main entry point. It determines if this is a first visit
        or return visit and builds the scene accordingly.

        Args:
            location_key: The location to build a scene for.
            world_update: The world state from WorldMechanics.
            observation_level: How closely the player is observing.

        Returns:
            SceneManifest with complete scene state.

        Raises:
            ValueError: If location not found.
        """
        # Get location from database
        location = self._get_location(location_key)
        if location is None:
            raise ValueError(f"Location not found: {location_key}")

        # Determine if this is first visit
        is_first_visit = location.first_visited_turn is None

        if is_first_visit:
            scene = await self._build_first_visit(location, world_update)
        else:
            scene = await self._load_existing_scene(location, world_update)

        # Add NPCs from world update
        scene = self._merge_npcs(scene, world_update)

        # Filter items based on observation level
        scene = self._filter_by_observation_level(scene, observation_level)

        return scene

    # =========================================================================
    # First Visit Scene Generation
    # =========================================================================

    async def _build_first_visit(
        self,
        location: Location,
        world_update: WorldUpdate,
    ) -> SceneManifest:
        """Generate scene for first visit using LLM.

        Args:
            location: The location to generate scene for.
            world_update: Current world state.

        Returns:
            SceneManifest with generated contents.
        """
        location_type = location.category or "general"

        # Get time context
        time_state = self._get_time_state()
        time_context = self._build_time_context(time_state)

        # Try LLM generation if provider available
        if self.llm_provider is not None:
            scene_contents = await self._call_scene_builder_llm(
                location=location,
                location_type=location_type,
                time_context=time_context,
            )
        else:
            # Use defaults without LLM
            scene_contents = SceneContents(
                furniture=[],
                items=[],
                atmosphere=DEFAULT_ATMOSPHERE,
                discoverable_hints=[],
            )

        # Build manifest
        return SceneManifest(
            location_key=location.location_key,
            location_display=location.display_name,
            location_type=location_type,
            furniture=scene_contents.furniture,
            items=scene_contents.items,
            npcs=[],  # NPCs added later from world_update
            atmosphere=scene_contents.atmosphere,
            observation_level=ObservationLevel.ENTRY,
            undiscovered_hints=scene_contents.discoverable_hints,
            is_first_visit=True,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    async def _call_scene_builder_llm(
        self,
        location: Location,
        location_type: str,
        time_context: dict,
    ) -> SceneContents:
        """Call LLM to generate scene contents.

        Args:
            location: The location.
            location_type: Type of location (bedroom, tavern, etc.).
            time_context: Current time/weather context.

        Returns:
            SceneContents from LLM.
        """
        from src.llm.message_types import Message

        # Build prompt
        prompt = self._build_scene_prompt(location, location_type, time_context)

        # Get system prompt
        system_prompt = self._get_scene_builder_system_prompt()

        # Call LLM with structured output
        response = await self.llm_provider.complete_structured(
            messages=[Message.user(prompt)],
            response_schema=SceneContents,
            temperature=0.3,
            system_prompt=system_prompt,
        )

        # Convert dict to Pydantic model
        if isinstance(response.parsed_content, dict):
            return SceneContents.model_validate(response.parsed_content)
        return response.parsed_content

    def _build_scene_prompt(
        self,
        location: Location,
        location_type: str,
        time_context: dict,
    ) -> str:
        """Build the prompt for scene generation.

        Args:
            location: The location.
            location_type: Type of location.
            time_context: Current time/weather context.

        Returns:
            Prompt string.
        """
        return f"""Generate the physical contents of this location.

## Location
- Name: {location.display_name}
- Type: {location_type}
- Description: {location.description}
- Atmosphere notes: {location.atmosphere or 'none'}

## Current Context
- Time: {time_context.get('time', 'unknown')}
- Day: {time_context.get('day_of_week', 'unknown')}
- Weather: {time_context.get('weather', 'clear')}
- Season: {time_context.get('season', 'spring')}

## Instructions
Generate appropriate:
1. **Furniture** - 3-5 DISTINCT pieces appropriate for this location type
2. **Items** - 3-5 DISTINCT items that would naturally be here
3. **Atmosphere** - Lighting, sounds, smells based on time and location

IMPORTANT - Avoid duplicates:
- Do NOT generate similar items (e.g., don't have both "tankards" AND "mugs")
- Each item should be functionally different
- Use clear, distinct keys (e.g., 'bar_001', 'fireplace_001')

For each furniture/item:
- Use snake_case keys like 'bar_001', 'table_001' - keep them short
- Mark visibility: OBVIOUS (seen on entry), DISCOVERABLE (seen on look), HIDDEN (found on search)
- Include position in room

Keep descriptions grounded and realistic for the setting."""

    def _get_scene_builder_system_prompt(self) -> str:
        """Get the system prompt for scene building."""
        return """You are a scene designer for a realistic RPG. Generate physical details for locations.

Key principles:
- Every location has a consistent layout that never changes unexpectedly
- Furniture and items should be appropriate for the location type
- Consider the time of day for lighting descriptions
- Hidden items should be rare and logically placed
- Use unique keys for each element (format: type_001, type_002, etc.)"""

    # =========================================================================
    # Return Visit Scene Loading
    # =========================================================================

    async def _load_existing_scene(
        self,
        location: Location,
        world_update: WorldUpdate,
    ) -> SceneManifest:
        """Load scene from database for return visit.

        Args:
            location: The location.
            world_update: Current world state.

        Returns:
            SceneManifest loaded from database.
        """
        location_type = location.category or "general"

        # Load furniture from database
        furniture = self._load_furniture_from_db(location)

        # Load items from database
        items = self._load_items_from_db(location)

        # Build atmosphere from location or generate minimal
        atmosphere = self._load_or_create_atmosphere(location)

        return SceneManifest(
            location_key=location.location_key,
            location_display=location.display_name,
            location_type=location_type,
            furniture=furniture,
            items=items,
            npcs=[],  # NPCs added later from world_update
            atmosphere=atmosphere,
            observation_level=ObservationLevel.ENTRY,
            undiscovered_hints=[],
            is_first_visit=False,
            generated_at=None,
        )

    def _load_furniture_from_db(self, location: Location) -> list[FurnitureSpec]:
        """Load furniture items from database.

        Furniture is identified by having a 'furniture_type' property or
        item_type == CONTAINER with is_fixed=True.

        Args:
            location: The location.

        Returns:
            List of FurnitureSpec.
        """
        # Query items owned by this location
        all_items = (
            self.db.query(Item)
            .filter(
                Item.session_id == self.session_id,
                Item.owner_location_id == location.id,
            )
            .all()
        )

        # Filter to furniture items (those with furniture_type property)
        furniture_items = [
            item for item in all_items
            if item.properties and item.properties.get("furniture_type")
        ]

        furniture_specs = []
        for item in furniture_items:
            props = item.properties or {}
            spec = FurnitureSpec(
                furniture_key=item.item_key,
                display_name=item.display_name,
                furniture_type=props.get("furniture_type", "furniture"),
                material=props.get("material", "wood"),
                condition=props.get("condition", "good"),
                position_in_room=props.get("position", "in the room"),
                is_container=props.get("is_container", False),
                container_state=props.get("container_state"),
                description_hints=props.get("description_hints", []),
            )
            furniture_specs.append(spec)

        return furniture_specs

    def _load_items_from_db(self, location: Location) -> list[ItemSpec]:
        """Load non-furniture items from database.

        Args:
            location: The location.

        Returns:
            List of ItemSpec.
        """
        # Get storage location for this place
        storage = (
            self.db.query(StorageLocation)
            .filter(
                StorageLocation.session_id == self.session_id,
                StorageLocation.owner_location_id == location.id,
                StorageLocation.location_type == StorageLocationType.PLACE,
            )
            .first()
        )

        if storage is None:
            return []

        # Query items at this storage
        all_items = (
            self.db.query(Item)
            .filter(
                Item.session_id == self.session_id,
                Item.storage_location_id == storage.id,
            )
            .all()
        )

        # Filter out furniture items (those with furniture_type property)
        items = [
            item for item in all_items
            if not (item.properties and item.properties.get("furniture_type"))
        ]

        item_specs = []
        for item in items:
            props = item.properties or {}
            visibility_str = props.get("visibility", "obvious")
            try:
                visibility = ItemVisibility(visibility_str)
            except ValueError:
                visibility = ItemVisibility.OBVIOUS

            spec = ItemSpec(
                item_key=item.item_key,
                display_name=item.display_name,
                item_type=str(item.item_type.value),
                position=props.get("position", "here"),
                visibility=visibility,
                material=props.get("material"),
                condition=props.get("condition"),
                properties=props,
                description_hints=props.get("description_hints", []),
            )
            item_specs.append(spec)

        return item_specs

    def _load_or_create_atmosphere(self, location: Location) -> Atmosphere:
        """Load atmosphere from location or create default.

        Args:
            location: The location.

        Returns:
            Atmosphere for the scene.
        """
        time_state = self._get_time_state()
        hour = self._parse_hour(time_state.current_time)

        # Determine lighting based on time
        if 6 <= hour < 12:
            lighting = "morning light"
            lighting_source = "window"
        elif 12 <= hour < 18:
            lighting = "afternoon light"
            lighting_source = "window"
        elif 18 <= hour < 21:
            lighting = "evening light"
            lighting_source = "window and candles"
        else:
            lighting = "dim candlelight"
            lighting_source = "candles"

        return Atmosphere(
            lighting=lighting,
            lighting_source=lighting_source,
            sounds=[],
            smells=[],
            temperature="comfortable",
            weather_effects=None,
            time_of_day_notes=f"It is {time_state.current_time}",
            overall_mood="neutral",
        )

    # =========================================================================
    # NPC Merging
    # =========================================================================

    def _merge_npcs(
        self,
        scene: SceneManifest,
        world_update: WorldUpdate,
    ) -> SceneManifest:
        """Merge NPCs from WorldUpdate into scene.

        Args:
            scene: Current scene manifest.
            world_update: World state with NPC placements.

        Returns:
            SceneManifest with NPCs added.
        """
        scene_npcs = []

        for placement in world_update.npcs_at_location:
            # Get entity details from database if existing NPC
            entity = None
            if placement.entity_key:
                entity = self._get_entity_by_key(placement.entity_key)

            if entity:
                display_name = entity.display_name
                gender = entity.gender
                pronouns = self._get_pronouns(gender)
            elif placement.new_npc:
                display_name = placement.new_npc.display_name
                gender = placement.new_npc.gender
                pronouns = self._get_pronouns(gender)
            else:
                display_name = "Unknown"
                gender = None
                pronouns = None

            scene_npc = SceneNPC(
                entity_key=placement.entity_key or f"new_npc_{len(scene_npcs)}",
                display_name=display_name,
                gender=gender,
                presence_reason=placement.presence_reason,
                activity=placement.activity,
                mood=placement.mood,
                position_in_scene=placement.position_in_scene,
                appearance_notes="",
                will_initiate=placement.will_initiate_conversation,
                pronouns=pronouns,
            )
            scene_npcs.append(scene_npc)

        # Return new manifest with NPCs
        return SceneManifest(
            location_key=scene.location_key,
            location_display=scene.location_display,
            location_type=scene.location_type,
            furniture=scene.furniture,
            items=scene.items,
            npcs=scene_npcs,
            atmosphere=scene.atmosphere,
            observation_level=scene.observation_level,
            undiscovered_hints=scene.undiscovered_hints,
            is_first_visit=scene.is_first_visit,
            generated_at=scene.generated_at,
        )

    def _get_pronouns(self, gender: str | None) -> str | None:
        """Get pronouns for a gender.

        Args:
            gender: The gender string.

        Returns:
            Pronouns string or None.
        """
        if gender == "male":
            return "he/him"
        elif gender == "female":
            return "she/her"
        return None

    # =========================================================================
    # Observation Level Filtering
    # =========================================================================

    def _filter_by_observation_level(
        self,
        scene: SceneManifest,
        observation_level: ObservationLevel,
    ) -> SceneManifest:
        """Filter items based on observation level.

        Args:
            scene: Current scene manifest.
            observation_level: How closely player is observing.

        Returns:
            SceneManifest with filtered items.
        """
        visible_items = []
        undiscovered_hints = list(scene.undiscovered_hints)

        for item in scene.items:
            if self._is_item_visible(item.visibility, observation_level):
                visible_items.append(item)
            elif item.visibility == ItemVisibility.DISCOVERABLE:
                # Add hint for discoverable items not yet seen
                hint = f"There might be something {item.position}"
                if hint not in undiscovered_hints:
                    undiscovered_hints.append(hint)

        return SceneManifest(
            location_key=scene.location_key,
            location_display=scene.location_display,
            location_type=scene.location_type,
            furniture=scene.furniture,
            items=visible_items,
            npcs=scene.npcs,
            atmosphere=scene.atmosphere,
            observation_level=observation_level,
            undiscovered_hints=undiscovered_hints,
            is_first_visit=scene.is_first_visit,
            generated_at=scene.generated_at,
        )

    def _is_item_visible(
        self,
        visibility: ItemVisibility,
        observation_level: ObservationLevel,
    ) -> bool:
        """Check if item is visible at observation level.

        Args:
            visibility: The item's visibility.
            observation_level: Current observation level.

        Returns:
            True if item should be visible.
        """
        if visibility == ItemVisibility.OBVIOUS:
            return True

        if visibility == ItemVisibility.DISCOVERABLE:
            return observation_level in {
                ObservationLevel.LOOK,
                ObservationLevel.SEARCH,
                ObservationLevel.EXAMINE,
            }

        if visibility == ItemVisibility.HIDDEN:
            return observation_level in {
                ObservationLevel.SEARCH,
                ObservationLevel.EXAMINE,
            }

        return False

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _get_location(self, location_key: str) -> Location | None:
        """Get location from database.

        Args:
            location_key: The location key.

        Returns:
            Location or None.
        """
        return (
            self.db.query(Location)
            .filter(
                Location.session_id == self.session_id,
                Location.location_key == location_key,
            )
            .first()
        )

    def _get_entity_by_key(self, entity_key: str) -> Entity | None:
        """Get entity from database by key.

        Args:
            entity_key: The entity key.

        Returns:
            Entity or None.
        """
        return (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.session_id,
                Entity.entity_key == entity_key,
            )
            .first()
        )

    def _get_time_state(self) -> TimeState:
        """Get or create time state.

        Returns:
            TimeState for this session.
        """
        time_state = (
            self.db.query(TimeState)
            .filter(TimeState.session_id == self.session_id)
            .first()
        )

        if time_state is None:
            time_state = TimeState(
                session_id=self.session_id,
                current_day=1,
                current_time="12:00",
                day_of_week="monday",
            )
            self.db.add(time_state)
            self.db.flush()

        return time_state

    def _parse_hour(self, time_str: str) -> int:
        """Parse hour from time string.

        Args:
            time_str: Time in HH:MM format.

        Returns:
            Hour as integer.
        """
        try:
            return int(time_str.split(":")[0])
        except (ValueError, IndexError):
            return 12

    def _build_time_context(self, time_state: TimeState) -> dict:
        """Build time context dict for LLM.

        Args:
            time_state: Current time state.

        Returns:
            Dict with time context.
        """
        return {
            "time": time_state.current_time,
            "day_of_week": time_state.day_of_week,
            "day": time_state.current_day,
            "weather": time_state.weather or "clear",
            "season": time_state.season,
        }

    # =========================================================================
    # Container Contents Generation (Lazy Loading)
    # =========================================================================

    async def generate_container_contents(
        self,
        container: Item,
        location: Location,
    ) -> list[ItemSpec]:
        """Generate contents for a container when first opened.

        This provides lazy-loading for container contents. Instead of
        generating contents for every drawer, chest, and cabinet upfront,
        we generate them on-demand when the player opens the container.

        Args:
            container: The container item being opened.
            location: The location containing the container.

        Returns:
            List of ItemSpec for generated contents.
        """
        # Check if container already has contents
        storage = self._get_container_storage(container)
        if storage:
            existing_items = (
                self.db.query(Item)
                .filter(
                    Item.session_id == self.session_id,
                    Item.storage_location_id == storage.id,
                )
                .all()
            )
            if existing_items:
                # Already has contents, convert to specs
                return self._items_to_specs(existing_items)

        # No contents yet - generate them
        if self.llm_provider is None:
            # No LLM, return empty (container is empty)
            return []

        # Generate contents via LLM
        contents = await self._call_container_contents_llm(container, location)
        return contents

    async def _call_container_contents_llm(
        self,
        container: Item,
        location: Location,
    ) -> list[ItemSpec]:
        """Call LLM to generate container contents.

        Args:
            container: The container being opened.
            location: The location of the container.

        Returns:
            List of ItemSpec for generated contents.
        """
        from src.llm.message_types import Message
        from pydantic import BaseModel

        class ContainerContentsResponse(BaseModel):
            """Response schema for container contents generation."""
            items: list[ItemSpec]
            is_empty: bool = False
            empty_reason: str | None = None

        container_type = container.properties.get("furniture_type", "container") if container.properties else "container"
        location_type = location.category or "general"

        prompt = f"""Generate realistic contents for a {container_type} in a {location_type}.

## Container
- Type: {container.display_name}
- Location: {location.display_name}

## Instructions
Generate 0-4 items that would realistically be found in this container.

Consider:
- Container type (chest has different contents than kitchen drawer)
- Location type (bedroom has different items than shop)
- Keep items mundane and appropriate
- Sometimes containers are empty - that's fine

For each item:
- Use snake_case keys with sequence numbers (e.g., 'quill_001', 'coin_pouch_001')
- Set visibility to OBVIOUS (they're in an opened container)
- Include position as "in the {container_type}"

If the container should be empty, set is_empty=true and provide a reason."""

        try:
            response = await self.llm_provider.complete_structured(
                messages=[Message.user(prompt)],
                response_schema=ContainerContentsResponse,
                temperature=0.4,
            )

            if response.parsed_content:
                if response.parsed_content.is_empty:
                    return []
                return response.parsed_content.items

        except Exception as e:
            logger.warning(f"Container contents generation failed: {e}")

        return []

    def _get_container_storage(self, container: Item) -> StorageLocation | None:
        """Get the storage location for a container.

        Args:
            container: The container item.

        Returns:
            StorageLocation or None if not set up.
        """
        return (
            self.db.query(StorageLocation)
            .filter(
                StorageLocation.session_id == self.session_id,
                StorageLocation.owner_item_id == container.id,
                StorageLocation.location_type == StorageLocationType.CONTAINER,
            )
            .first()
        )

    def _items_to_specs(self, items: list[Item]) -> list[ItemSpec]:
        """Convert Item models to ItemSpec objects.

        Args:
            items: List of Item models.

        Returns:
            List of ItemSpec objects.
        """
        specs = []
        for item in items:
            props = item.properties or {}
            visibility_str = props.get("visibility", "obvious")
            try:
                visibility = ItemVisibility(visibility_str)
            except ValueError:
                visibility = ItemVisibility.OBVIOUS

            spec = ItemSpec(
                item_key=item.item_key,
                display_name=item.display_name,
                item_type=str(item.item_type.value),
                position=props.get("position", "here"),
                visibility=visibility,
                material=props.get("material"),
                condition=props.get("condition"),
                properties=props,
                description_hints=props.get("description_hints", []),
            )
            specs.append(spec)

        return specs
