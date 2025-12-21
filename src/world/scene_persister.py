"""ScenePersister for Scene-First Architecture.

This module handles persisting scene data to the database:
- World Mechanics output (new NPCs, events, facts)
- Scene Builder output (furniture, items)
- Building narrator manifests from persisted scenes

ScenePersister operates AFTER WorldMechanics and SceneBuilder,
taking their output and ensuring it's properly stored in the database.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from src.database.models.entities import Entity, NPCExtension
from src.database.models.enums import EntityType, ItemType, StorageLocationType
from src.database.models.items import Item, StorageLocation
from src.database.models.world import Fact, Location
from src.managers.base import BaseManager
from src.world.schemas import (
    Atmosphere,
    EntityRef,
    FurnitureSpec,
    ItemSpec,
    NarratorManifest,
    NPCPlacement,
    PersistedItem,
    PersistedNPC,
    PersistedScene,
    PersistedWorldUpdate,
    SceneManifest,
    SceneNPC,
    WorldUpdate,
)

if TYPE_CHECKING:
    from src.database.models.session import GameSession

logger = logging.getLogger(__name__)


class ScenePersister(BaseManager):
    """Persists scene data to the database.

    This class handles:
    - Creating new NPCs from World Mechanics output
    - Creating furniture and items from Scene Builder output
    - Storing facts from world updates
    - Building narrator manifests for the constrained narrator

    It ensures atomic transactions where possible and handles
    duplicate detection for idempotent operations.
    """

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
    ) -> None:
        """Initialize ScenePersister.

        Args:
            db: Database session.
            game_session: Current game session.
        """
        super().__init__(db, game_session)

    # =========================================================================
    # Persist World Update
    # =========================================================================

    def persist_world_update(
        self,
        world_update: WorldUpdate,
        location_key: str,
        turn_number: int,
    ) -> PersistedWorldUpdate:
        """Persist World Mechanics output to the database.

        This creates new NPCs and stores facts from the world update.
        Existing NPCs are not recreated.

        Args:
            world_update: Output from World Mechanics.
            location_key: Current location key.
            turn_number: Current turn number.

        Returns:
            PersistedWorldUpdate with created entities.
        """
        persisted_npcs: list[PersistedNPC] = []
        facts_stored = 0

        # Process NPC placements
        for placement in world_update.npcs_at_location:
            if placement.new_npc is not None:
                # Create new NPC
                persisted = self._create_npc(
                    placement=placement,
                    location_key=location_key,
                    turn_number=turn_number,
                )
                persisted_npcs.append(persisted)
            elif placement.entity_key:
                # Existing NPC - just record reference
                entity = self._get_entity_by_key(placement.entity_key)
                if entity:
                    persisted_npcs.append(
                        PersistedNPC(
                            entity_key=placement.entity_key,
                            entity_id=entity.id,
                            was_created=False,
                        )
                    )
                    # Update NPC extension with current location
                    if entity.npc_extension:
                        entity.npc_extension.current_location = location_key
                        entity.npc_extension.current_activity = placement.activity
                        entity.npc_extension.current_mood = placement.mood

        # Store fact updates
        for fact_update in world_update.fact_updates:
            self._store_fact(fact_update, turn_number)
            facts_stored += 1

        self.db.flush()

        return PersistedWorldUpdate(
            npcs=persisted_npcs,
            events_created=[],  # Events handled separately if needed
            facts_stored=facts_stored,
        )

    def _create_npc(
        self,
        placement: NPCPlacement,
        location_key: str,
        turn_number: int,
    ) -> PersistedNPC:
        """Create a new NPC from a placement spec.

        Args:
            placement: NPC placement with new_npc spec.
            location_key: Location where NPC is.
            turn_number: Current turn.

        Returns:
            PersistedNPC with created entity info.
        """
        spec = placement.new_npc
        if spec is None:
            raise ValueError("new_npc is required for creating NPC")

        # Generate unique key
        entity_key = self._generate_entity_key(spec.display_name)

        # Create entity
        entity = Entity(
            session_id=self.session_id,
            entity_key=entity_key,
            display_name=spec.display_name,
            entity_type=EntityType.NPC,
            gender=spec.gender,
            occupation=spec.occupation,
            is_alive=True,
            is_active=True,
            first_appeared_turn=turn_number,
        )

        # Set personality notes from hints
        if spec.personality_hints:
            entity.personality_notes = ", ".join(spec.personality_hints)

        # Set backstory from hints
        if spec.backstory_hints:
            entity.background = " ".join(spec.backstory_hints)

        self.db.add(entity)
        self.db.flush()

        # Create NPC extension
        npc_ext = NPCExtension(
            entity_id=entity.id,
            job=spec.occupation,
            current_location=location_key,
            current_activity=placement.activity,
            current_mood=placement.mood,
        )
        self.db.add(npc_ext)
        self.db.flush()

        logger.info(f"Created NPC: {entity_key} ({spec.display_name})")

        return PersistedNPC(
            entity_key=entity_key,
            entity_id=entity.id,
            was_created=True,
        )

    def _generate_entity_key(self, display_name: str) -> str:
        """Generate a unique entity key from display name.

        Args:
            display_name: The NPC's display name.

        Returns:
            Unique snake_case key like 'sarah_001'.
        """
        # Convert to snake_case and remove special characters
        base_key = display_name.lower()
        base_key = re.sub(r"[^a-z0-9\s]", "", base_key)
        base_key = re.sub(r"\s+", "_", base_key.strip())

        # If empty after cleaning, use generic
        if not base_key:
            base_key = "npc"

        # Find unique suffix
        counter = 1
        candidate = f"{base_key}_{counter:03d}"

        while self._entity_key_exists(candidate):
            counter += 1
            candidate = f"{base_key}_{counter:03d}"

        return candidate

    def _entity_key_exists(self, key: str) -> bool:
        """Check if an entity key already exists.

        Args:
            key: The entity key to check.

        Returns:
            True if key exists.
        """
        return (
            self.db.query(Entity.id)
            .filter(
                Entity.session_id == self.session_id,
                Entity.entity_key == key,
            )
            .first()
            is not None
        )

    def _store_fact(self, fact_update, turn_number: int) -> None:
        """Store a fact update.

        Args:
            fact_update: The fact to store.
            turn_number: Current turn number.
        """
        # Check if fact already exists
        existing = (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.session_id,
                Fact.subject_key == fact_update.subject,
                Fact.predicate == fact_update.predicate,
            )
            .first()
        )

        if existing:
            # Update existing fact
            existing.value = fact_update.value
            existing.times_mentioned += 1
        else:
            # Create new fact
            fact = Fact(
                session_id=self.session_id,
                subject_type="location",  # Default, could be determined from subject
                subject_key=fact_update.subject,
                predicate=fact_update.predicate,
                value=fact_update.value,
                source_turn=turn_number,
            )
            self.db.add(fact)

    # =========================================================================
    # Persist Scene
    # =========================================================================

    def persist_scene(
        self,
        scene_manifest: SceneManifest,
        location: Location,
        turn_number: int,
    ) -> PersistedScene:
        """Persist Scene Builder output to the database.

        This creates furniture and items from the scene manifest.
        Existing items are not duplicated.

        Args:
            scene_manifest: Output from Scene Builder.
            location: The location entity.
            turn_number: Current turn number.

        Returns:
            PersistedScene with created items.
        """
        persisted_furniture: list[PersistedItem] = []
        persisted_items: list[PersistedItem] = []
        location_marked = False

        # Get or create storage location for this place
        storage = self._get_or_create_storage_location(location)

        # Create furniture
        for furniture_spec in scene_manifest.furniture:
            persisted = self._create_furniture(
                furniture_spec=furniture_spec,
                location=location,
                storage=storage,
                turn_number=turn_number,
            )
            persisted_furniture.append(persisted)

        # Create items
        for item_spec in scene_manifest.items:
            persisted = self._create_item(
                item_spec=item_spec,
                location=location,
                storage=storage,
                turn_number=turn_number,
            )
            persisted_items.append(persisted)

        # Mark location as visited on first visit
        if scene_manifest.is_first_visit and location.first_visited_turn is None:
            location.first_visited_turn = turn_number
            location_marked = True

        self.db.flush()

        return PersistedScene(
            furniture=persisted_furniture,
            items=persisted_items,
            location_marked_generated=location_marked,
        )

    def _get_or_create_storage_location(
        self,
        location: Location,
    ) -> StorageLocation:
        """Get or create the storage location for a place.

        Args:
            location: The world location.

        Returns:
            StorageLocation for this place.
        """
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
            storage = StorageLocation(
                session_id=self.session_id,
                location_key=f"storage_{location.location_key}",
                location_type=StorageLocationType.PLACE,
                owner_location_id=location.id,
                is_fixed=True,
            )
            self.db.add(storage)
            self.db.flush()

        return storage

    def _create_furniture(
        self,
        furniture_spec: FurnitureSpec,
        location: Location,
        storage: StorageLocation,
        turn_number: int,
    ) -> PersistedItem:
        """Create a furniture item from spec.

        Args:
            furniture_spec: Furniture specification.
            location: The location.
            storage: Storage location for items.
            turn_number: Current turn.

        Returns:
            PersistedItem with created item info.
        """
        # Check if already exists
        existing = self._get_item_by_key(furniture_spec.furniture_key)
        if existing:
            return PersistedItem(
                item_key=furniture_spec.furniture_key,
                item_id=existing.id,
                storage_location_id=existing.storage_location_id,
                was_created=False,
            )

        # Build properties
        properties = {
            "furniture_type": furniture_spec.furniture_type,
            "material": furniture_spec.material,
            "condition": furniture_spec.condition,
            "position": furniture_spec.position_in_room,
            "is_container": furniture_spec.is_container,
        }
        if furniture_spec.container_state:
            properties["container_state"] = furniture_spec.container_state
        if furniture_spec.description_hints:
            properties["description_hints"] = furniture_spec.description_hints

        # Create item
        item = Item(
            session_id=self.session_id,
            item_key=furniture_spec.furniture_key,
            display_name=furniture_spec.display_name,
            item_type=ItemType.MISC,  # Furniture uses MISC with furniture_type property
            owner_location_id=location.id,
            storage_location_id=storage.id,
            properties=properties,
            acquired_turn=turn_number,
        )
        self.db.add(item)
        self.db.flush()

        logger.debug(f"Created furniture: {furniture_spec.furniture_key}")

        return PersistedItem(
            item_key=furniture_spec.furniture_key,
            item_id=item.id,
            storage_location_id=storage.id,
            was_created=True,
        )

    def _create_item(
        self,
        item_spec: ItemSpec,
        location: Location,
        storage: StorageLocation,
        turn_number: int,
    ) -> PersistedItem:
        """Create an item from spec.

        Args:
            item_spec: Item specification.
            location: The location.
            storage: Storage location.
            turn_number: Current turn.

        Returns:
            PersistedItem with created item info.
        """
        # Check if already exists
        existing = self._get_item_by_key(item_spec.item_key)
        if existing:
            return PersistedItem(
                item_key=item_spec.item_key,
                item_id=existing.id,
                storage_location_id=existing.storage_location_id,
                was_created=False,
            )

        # Map item_type string to enum
        item_type = self._map_item_type(item_spec.item_type)

        # Build properties
        properties = {
            "position": item_spec.position,
            "visibility": item_spec.visibility.value,
        }
        if item_spec.material:
            properties["material"] = item_spec.material
        if item_spec.condition:
            properties["condition"] = item_spec.condition
        if item_spec.properties:
            properties.update(item_spec.properties)
        if item_spec.description_hints:
            properties["description_hints"] = item_spec.description_hints

        # Create item
        item = Item(
            session_id=self.session_id,
            item_key=item_spec.item_key,
            display_name=item_spec.display_name,
            item_type=item_type,
            owner_location_id=location.id,
            storage_location_id=storage.id,
            properties=properties,
            acquired_turn=turn_number,
        )
        self.db.add(item)
        self.db.flush()

        logger.debug(f"Created item: {item_spec.item_key}")

        return PersistedItem(
            item_key=item_spec.item_key,
            item_id=item.id,
            storage_location_id=storage.id,
            was_created=True,
        )

    def _map_item_type(self, type_str: str) -> ItemType:
        """Map item type string to enum.

        Args:
            type_str: Item type as string.

        Returns:
            ItemType enum value.
        """
        type_mapping = {
            "clothing": ItemType.CLOTHING,
            "equipment": ItemType.EQUIPMENT,
            "accessory": ItemType.ACCESSORY,
            "consumable": ItemType.CONSUMABLE,
            "container": ItemType.CONTAINER,
            "tool": ItemType.TOOL,
            "weapon": ItemType.WEAPON,
            "armor": ItemType.ARMOR,
        }
        return type_mapping.get(type_str.lower(), ItemType.MISC)

    def _get_item_by_key(self, item_key: str) -> Item | None:
        """Get item by key.

        Args:
            item_key: The item key.

        Returns:
            Item or None.
        """
        return (
            self.db.query(Item)
            .filter(
                Item.session_id == self.session_id,
                Item.item_key == item_key,
            )
            .first()
        )

    # =========================================================================
    # Build Narrator Manifest
    # =========================================================================

    def build_narrator_manifest(
        self,
        scene_manifest: SceneManifest,
    ) -> NarratorManifest:
        """Build a NarratorManifest from a SceneManifest.

        This creates the manifest that the constrained narrator uses
        to know what entities it can reference.

        Args:
            scene_manifest: The scene to build manifest from.

        Returns:
            NarratorManifest with all referenceable entities.
        """
        entities: dict[str, EntityRef] = {}

        # Add NPCs
        for npc in scene_manifest.npcs:
            entities[npc.entity_key] = EntityRef(
                key=npc.entity_key,
                display_name=npc.display_name,
                entity_type="npc",
                short_description=f"{npc.display_name}, {npc.activity}",
                pronouns=npc.pronouns,
                position=npc.position_in_scene,
            )

        # Add furniture
        for furniture in scene_manifest.furniture:
            entities[furniture.furniture_key] = EntityRef(
                key=furniture.furniture_key,
                display_name=furniture.display_name,
                entity_type="furniture",
                short_description=f"{furniture.display_name} ({furniture.furniture_type})",
                position=furniture.position_in_room,
            )

        # Add items (including hidden ones - narrator needs to know about all)
        for item in scene_manifest.items:
            entities[item.item_key] = EntityRef(
                key=item.item_key,
                display_name=item.display_name,
                entity_type="item",
                short_description=f"{item.display_name} ({item.item_type})",
                position=item.position,
            )

        return NarratorManifest(
            location_key=scene_manifest.location_key,
            location_display=scene_manifest.location_display,
            entities=entities,
            atmosphere=scene_manifest.atmosphere,
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _get_entity_by_key(self, entity_key: str) -> Entity | None:
        """Get entity by key.

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
