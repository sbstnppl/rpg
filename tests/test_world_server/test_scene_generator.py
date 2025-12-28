"""Tests for SceneGenerator."""

import pytest

from src.database.models.entities import Entity
from src.database.models.enums import EntityType
from src.database.models.world import Location, TimeState
from src.world_server.scene_generator import (
    SceneGenerator,
    create_scene_generator_callback,
)
from src.world_server.schemas import PredictionReason


class TestSceneGenerator:
    """Tests for SceneGenerator class."""

    def test_initialization(self, db_session, game_session):
        """Test generator initialization."""
        generator = SceneGenerator(db_session, game_session)

        assert generator.db == db_session
        assert generator.game_session == game_session

    @pytest.mark.asyncio
    async def test_generate_scene_location_not_found(self, db_session, game_session):
        """Test generation returns None for nonexistent location."""
        generator = SceneGenerator(db_session, game_session)

        result = await generator.generate_scene("nonexistent_location")

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_scene_basic(self, db_session, game_session):
        """Test basic scene generation for a location."""
        # Create a location
        location = Location(
            session_id=game_session.id,
            location_key="tavern",
            display_name="The Rusty Tankard",
            description="A cozy tavern with a roaring fire",
            category="tavern",
            atmosphere="Warm and inviting",
        )
        db_session.add(location)
        db_session.flush()

        generator = SceneGenerator(db_session, game_session)
        result = await generator.generate_scene("tavern")

        assert result is not None
        assert result.location_key == "tavern"
        assert result.location_display_name == "The Rusty Tankard"
        assert result.scene_manifest["description"] == "A cozy tavern with a roaring fire"
        assert result.scene_manifest["category"] == "tavern"
        assert result.is_committed is False
        assert result.generation_time_ms >= 0

    @pytest.mark.asyncio
    async def test_generate_scene_with_npcs(self, db_session, game_session):
        """Test scene generation includes NPCs at location."""
        from src.database.models.entities import NPCExtension

        # Create location
        location = Location(
            session_id=game_session.id,
            location_key="market",
            display_name="Market Square",
            description="A bustling marketplace",
        )
        db_session.add(location)
        db_session.flush()

        # Create NPC at location
        npc = Entity(
            session_id=game_session.id,
            entity_key="merchant_bob",
            display_name="Bob the Merchant",
            entity_type=EntityType.NPC,
            occupation="Merchant",
        )
        db_session.add(npc)
        db_session.flush()

        # Add NPC extension with current_location
        npc_ext = NPCExtension(
            entity_id=npc.id,
            current_location="market",
        )
        db_session.add(npc_ext)
        db_session.flush()

        generator = SceneGenerator(db_session, game_session)
        result = await generator.generate_scene("market")

        assert result is not None
        assert len(result.npcs_present) == 1
        assert result.npcs_present[0]["entity_key"] == "merchant_bob"
        assert result.npcs_present[0]["display_name"] == "Bob the Merchant"
        assert result.npcs_present[0]["occupation"] == "Merchant"

    @pytest.mark.asyncio
    async def test_generate_scene_with_items(self, db_session, game_session):
        """Test scene generation includes items at location."""
        from src.database.models.items import Item, StorageLocation
        from src.database.models.enums import StorageLocationType

        # Create location
        location = Location(
            session_id=game_session.id,
            location_key="armory",
            display_name="The Armory",
            description="Weapons line the walls",
        )
        db_session.add(location)
        db_session.flush()

        # Create storage location linked to the world location
        storage = StorageLocation(
            session_id=game_session.id,
            location_key="armory_floor",
            location_type=StorageLocationType.PLACE,
            world_location_id=location.id,
        )
        db_session.add(storage)
        db_session.flush()

        # Create item in the storage location
        item = Item(
            session_id=game_session.id,
            item_key="rusty_sword",
            display_name="Rusty Sword",
            item_type="weapon",
            storage_location_id=storage.id,
        )
        db_session.add(item)
        db_session.flush()

        generator = SceneGenerator(db_session, game_session)
        result = await generator.generate_scene("armory")

        assert result is not None
        assert len(result.items_present) >= 1
        sword = next((i for i in result.items_present if i["item_key"] == "rusty_sword"), None)
        assert sword is not None
        assert sword["display_name"] == "Rusty Sword"

    @pytest.mark.asyncio
    async def test_generate_scene_with_prediction_reason(self, db_session, game_session):
        """Test scene generation includes prediction reason."""
        location = Location(
            session_id=game_session.id,
            location_key="inn",
            display_name="The Sleeping Dragon Inn",
            description="A quiet inn",
        )
        db_session.add(location)
        db_session.flush()

        generator = SceneGenerator(db_session, game_session)
        result = await generator.generate_scene(
            "inn",
            prediction_reason=PredictionReason.ADJACENT,
        )

        assert result is not None
        assert result.prediction_reason == PredictionReason.ADJACENT

    @pytest.mark.asyncio
    async def test_generate_scene_with_exits(self, db_session, game_session):
        """Test scene generation includes exits."""
        # Create locations - exits are stored in spatial_layout["exits"]
        tavern = Location(
            session_id=game_session.id,
            location_key="tavern",
            display_name="Tavern",
            description="A tavern",
            spatial_layout={"exits": ["street"]},  # Exits are stored in JSON
        )
        street = Location(
            session_id=game_session.id,
            location_key="street",
            display_name="Main Street",
            description="A street",
            is_accessible=True,
        )
        db_session.add_all([tavern, street])
        db_session.flush()

        generator = SceneGenerator(db_session, game_session)
        result = await generator.generate_scene("tavern")

        assert result is not None
        assert "exits" in result.scene_manifest
        # The exit should include the connected location
        exit_keys = [e["key"] for e in result.scene_manifest["exits"]]
        assert "street" in exit_keys

    @pytest.mark.asyncio
    async def test_time_of_day_morning(self, db_session, game_session):
        """Test time of day detection - morning."""
        location = Location(
            session_id=game_session.id,
            location_key="garden",
            display_name="Garden",
            description="A garden",
        )
        db_session.add(location)

        time_state = TimeState(
            session_id=game_session.id,
            current_time="08:30",
        )
        db_session.add(time_state)
        db_session.flush()

        generator = SceneGenerator(db_session, game_session)
        result = await generator.generate_scene("garden")

        assert result is not None
        assert result.atmosphere["time_of_day"] == "morning"

    @pytest.mark.asyncio
    async def test_time_of_day_night(self, db_session, game_session):
        """Test time of day detection - night."""
        location = Location(
            session_id=game_session.id,
            location_key="street",
            display_name="Street",
            description="A street",
        )
        db_session.add(location)

        time_state = TimeState(
            session_id=game_session.id,
            current_time="23:30",
        )
        db_session.add(time_state)
        db_session.flush()

        generator = SceneGenerator(db_session, game_session)
        result = await generator.generate_scene("street")

        assert result is not None
        assert result.atmosphere["time_of_day"] == "night"


class TestCreateSceneGeneratorCallback:
    """Tests for create_scene_generator_callback function."""

    @pytest.mark.asyncio
    async def test_callback_creation(self, db_session, game_session):
        """Test callback can be created and called."""
        location = Location(
            session_id=game_session.id,
            location_key="shop",
            display_name="General Store",
            description="A small shop",
        )
        db_session.add(location)
        db_session.flush()

        callback = create_scene_generator_callback(db_session, game_session)

        # Callback should be callable
        assert callable(callback)

        # Callback should generate scenes
        result = await callback("shop")
        assert result is not None
        assert result.location_key == "shop"

    @pytest.mark.asyncio
    async def test_callback_returns_none_for_missing(self, db_session, game_session):
        """Test callback returns None for missing location."""
        callback = create_scene_generator_callback(db_session, game_session)

        result = await callback("nonexistent")
        assert result is None
