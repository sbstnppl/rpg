"""Integration tests for inventory and storage workflows.

Tests complete scenarios involving:
- Theft lifecycle (steal, fence, return)
- Container nesting and item movement
- Temporary surfaces (tables, floors)
- Portability and movement restrictions
"""

import pytest
from sqlalchemy.orm import Session

from src.database.models.enums import ItemType, StorageLocationType
from src.database.models.items import Item, StorageLocation
from src.database.models.session import GameSession
from src.managers.item_manager import ItemManager
from src.managers.storage_manager import StorageManager
from tests.factories import create_entity, create_location, create_item


class TestTheftWorkflow:
    """Integration tests for the complete theft lifecycle."""

    def test_steal_and_fence_workflow(
        self, db_session: Session, game_session: GameSession
    ):
        """Test stealing item from NPC, selling to fence."""
        # Setup: Victim has a valuable ring
        victim = create_entity(db_session, game_session, entity_key="merchant")
        thief = create_entity(db_session, game_session, entity_key="rogue")
        fence = create_entity(db_session, game_session, entity_key="fence")

        item_mgr = ItemManager(db_session, game_session)
        ring = item_mgr.create_item(
            item_key="gold_ring",
            display_name="Gold Ring",
            owner_id=victim.id,
            holder_id=victim.id,
        )

        # Step 1: Thief steals ring from victim
        stolen_ring = item_mgr.steal_item(
            "gold_ring",
            thief_id=thief.id,
            from_entity_id=victim.id,
        )

        # Verify theft state
        assert stolen_ring.is_stolen is True
        assert stolen_ring.was_ever_stolen is True
        assert stolen_ring.holder_id == thief.id
        assert stolen_ring.owner_id == victim.id  # Legal owner unchanged
        assert stolen_ring.stolen_from_id == victim.id

        # Step 2: Thief sells to fence (legitimizes)
        legitimate_ring = item_mgr.legitimize_item(
            "gold_ring",
            new_owner_id=fence.id,
        )

        # Verify post-sale state
        assert legitimate_ring.is_stolen is False  # No longer stolen
        assert legitimate_ring.was_ever_stolen is True  # History preserved
        assert legitimate_ring.owner_id == fence.id  # New legal owner
        assert legitimate_ring.holder_id == fence.id  # New holder
        assert legitimate_ring.stolen_from_id is None  # Cleared

    def test_steal_and_return_workflow(
        self, db_session: Session, game_session: GameSession
    ):
        """Test stealing item from establishment, returning it."""
        # Setup: Inn has bowls
        inn = create_location(db_session, game_session, location_key="inn")
        innkeeper = create_entity(db_session, game_session, entity_key="innkeeper")
        thief = create_entity(db_session, game_session, entity_key="thief")

        item_mgr = ItemManager(db_session, game_session)
        bowl = item_mgr.create_item(
            item_key="inn_bowl",
            display_name="Wooden Bowl",
            owner_location_id=inn.id,
        )

        # Step 1: Thief steals bowl from inn
        stolen_bowl = item_mgr.steal_item(
            "inn_bowl",
            thief_id=thief.id,
            from_location_id=inn.id,
        )

        # Verify theft state
        assert stolen_bowl.is_stolen is True
        assert stolen_bowl.stolen_from_location_id == inn.id
        assert stolen_bowl.holder_id == thief.id

        # Step 2: Thief returns bowl to innkeeper
        returned_bowl = item_mgr.return_stolen_item(
            "inn_bowl",
            to_entity_id=innkeeper.id,
        )

        # Verify return state
        assert returned_bowl.is_stolen is False
        assert returned_bowl.was_ever_stolen is True  # History preserved
        assert returned_bowl.holder_id == innkeeper.id
        assert returned_bowl.stolen_from_location_id is None  # Cleared
        assert returned_bowl.owner_location_id == inn.id  # Still owned by inn


class TestContainerWorkflow:
    """Integration tests for container nesting and item management."""

    def test_backpack_with_nested_pouch_workflow(
        self, db_session: Session, game_session: GameSession
    ):
        """Test creating backpack, adding pouch, moving items between them."""
        player = create_entity(db_session, game_session, entity_key="player")

        item_mgr = ItemManager(db_session, game_session)
        storage_mgr = StorageManager(db_session, game_session)

        # Step 1: Create backpack (container-item)
        backpack_item, backpack_storage = item_mgr.create_container_item(
            item_key="backpack",
            display_name="Leather Backpack",
            owner_id=player.id,
            container_type="backpack",
            capacity=20,
            weight_capacity=40.0,
        )

        # Verify backpack created
        assert backpack_item.item_type == ItemType.CONTAINER
        assert backpack_storage.container_item_id == backpack_item.id

        # Step 2: Create pouch and nest inside backpack
        pouch_item, pouch_storage = item_mgr.create_container_item(
            item_key="coin_pouch",
            display_name="Coin Pouch",
            owner_id=player.id,
            container_type="pouch",
            capacity=50,  # For coins
        )

        # Nest pouch in backpack
        storage_mgr.nest_storage("coin_pouch_storage", "backpack_storage")

        # Verify nesting
        hierarchy = storage_mgr.get_storage_hierarchy("coin_pouch_storage")
        assert len(hierarchy) == 1
        assert hierarchy[0].location_key == "backpack_storage"

        # Step 3: Add items to different levels
        # Book goes in backpack
        book = item_mgr.create_item(
            item_key="spellbook",
            display_name="Spellbook",
            weight=2.0,
        )
        item_mgr.put_in_container("spellbook", "backpack_storage")

        # Coins go in pouch
        coins = item_mgr.create_item(
            item_key="gold_coins",
            display_name="Gold Coins",
            quantity=10,
            weight=0.1,
        )
        item_mgr.put_in_container("gold_coins", "coin_pouch_storage")

        # Step 4: Get nested contents from backpack
        all_contents = storage_mgr.get_nested_contents("backpack_storage")

        assert len(all_contents) == 2
        keys = [i.item_key for i in all_contents]
        assert "spellbook" in keys
        assert "gold_coins" in keys

    def test_capacity_enforcement_workflow(
        self, db_session: Session, game_session: GameSession
    ):
        """Test that container capacity limits are enforced."""
        player = create_entity(db_session, game_session, entity_key="player")

        item_mgr = ItemManager(db_session, game_session)

        # Create small pouch with limited item capacity
        _, pouch = item_mgr.create_container_item(
            item_key="tiny_pouch",
            display_name="Tiny Pouch",
            owner_id=player.id,
            container_type="pouch",
            capacity=2,
            weight_capacity=10.0,  # High weight limit
        )

        # Add two light items - should work
        item_mgr.create_item(item_key="key1", display_name="Key 1", weight=0.1)
        item_mgr.put_in_container("key1", "tiny_pouch_storage")

        item_mgr.create_item(item_key="key2", display_name="Key 2", weight=0.1)
        item_mgr.put_in_container("key2", "tiny_pouch_storage")

        # Third item should fail (item capacity)
        item_mgr.create_item(item_key="key3", display_name="Key 3", weight=0.1)
        with pytest.raises(ValueError, match="capacity"):
            item_mgr.put_in_container("key3", "tiny_pouch_storage")

        # Create separate container with low weight limit
        _, sack = item_mgr.create_container_item(
            item_key="fragile_sack",
            display_name="Fragile Sack",
            owner_id=player.id,
            container_type="sack",
            capacity=10,  # High item limit
            weight_capacity=1.0,  # Low weight limit
        )

        # Heavy item should fail (weight)
        item_mgr.create_item(item_key="rock", display_name="Heavy Rock", weight=5.0)
        with pytest.raises(ValueError, match="weight"):
            item_mgr.put_in_container("rock", "fragile_sack_storage")


class TestTemporarySurfaceWorkflow:
    """Integration tests for temporary surface lifecycle."""

    def test_drop_items_on_table_workflow(
        self, db_session: Session, game_session: GameSession
    ):
        """Test placing items on table, picking up, cleanup."""
        tavern = create_location(db_session, game_session, location_key="tavern")
        player = create_entity(db_session, game_session, entity_key="player")

        item_mgr = ItemManager(db_session, game_session)

        # Player has items
        mug = item_mgr.create_item(
            item_key="mug",
            display_name="Beer Mug",
            holder_id=player.id,
        )
        bowl = item_mgr.create_item(
            item_key="bowl",
            display_name="Soup Bowl",
            holder_id=player.id,
        )

        # Step 1: Create table surface and place items
        table = item_mgr.get_or_create_surface(
            surface_key="tavern_table_1",
            world_location_id=tavern.id,
            container_type="table",
        )

        # Place items on table
        item_mgr.transfer_item("mug", to_storage_key="tavern_table_1")
        item_mgr.transfer_item("bowl", to_storage_key="tavern_table_1")

        # Verify items on table
        items_on_table = item_mgr.get_items_at_storage("tavern_table_1")
        assert len(items_on_table) == 2

        # Step 2: Player picks up items
        item_mgr.transfer_item("mug", to_entity_id=player.id)
        item_mgr.transfer_item("bowl", to_entity_id=player.id)

        # Step 3: Cleanup removes empty table
        removed = item_mgr.cleanup_empty_temporary_storage()

        assert removed == 1
        # Table no longer exists
        table_check = item_mgr.get_items_at_storage("tavern_table_1")
        assert table_check == []

    def test_floor_surface_workflow(
        self, db_session: Session, game_session: GameSession
    ):
        """Test dropping items on floor, location-specific cleanup."""
        street = create_location(db_session, game_session, location_key="street")
        alley = create_location(db_session, game_session, location_key="alley")
        player = create_entity(db_session, game_session, entity_key="player")

        item_mgr = ItemManager(db_session, game_session)

        # Player drops items in both locations
        sword = item_mgr.create_item(
            item_key="sword",
            display_name="Sword",
            holder_id=player.id,
        )
        coins = item_mgr.create_item(
            item_key="coins",
            display_name="Coins",
            holder_id=player.id,
        )

        # Drop sword on street floor
        street_floor = item_mgr.get_or_create_surface(
            surface_key="street_floor",
            world_location_id=street.id,
            container_type="floor",
        )
        item_mgr.transfer_item("sword", to_storage_key="street_floor")

        # Drop coins in alley
        alley_floor = item_mgr.get_or_create_surface(
            surface_key="alley_floor",
            world_location_id=alley.id,
            container_type="floor",
        )
        item_mgr.transfer_item("coins", to_storage_key="alley_floor")

        # Pick up sword from street
        item_mgr.transfer_item("sword", to_entity_id=player.id)

        # Cleanup only street - should remove empty street floor
        removed = item_mgr.cleanup_empty_temporary_storage(location_id=street.id)

        assert removed == 1

        # Alley floor should still exist with coins
        alley_items = item_mgr.get_items_at_storage("alley_floor")
        assert len(alley_items) == 1
        assert alley_items[0].item_key == "coins"


class TestPortabilityWorkflow:
    """Integration tests for storage portability and movement."""

    def test_move_portable_container_workflow(
        self, db_session: Session, game_session: GameSession
    ):
        """Test moving portable container to different location."""
        tavern = create_location(db_session, game_session, location_key="tavern")
        market = create_location(db_session, game_session, location_key="market")
        player = create_entity(db_session, game_session, entity_key="player")

        item_mgr = ItemManager(db_session, game_session)
        storage_mgr = StorageManager(db_session, game_session)

        # Create crate at tavern
        crate_item, crate_storage = item_mgr.create_container_item(
            item_key="crate",
            display_name="Wooden Crate",
            container_type="crate",
            is_fixed=False,
            world_location_id=tavern.id,
        )

        # Add items to crate
        item_mgr.create_item(item_key="apples", display_name="Apples")
        item_mgr.put_in_container("apples", "crate_storage")

        # Verify crate is movable
        assert storage_mgr.can_move_storage("crate_storage") is True

        # Move crate to market
        storage_mgr.move_storage_to_location("crate_storage", market.id)

        # Verify movement
        db_session.refresh(crate_storage)
        assert crate_storage.world_location_id == market.id

        # Items are still in crate
        contents = item_mgr.get_items_at_storage("crate_storage")
        assert len(contents) == 1
        assert contents[0].item_key == "apples"

    def test_fixed_storage_cannot_move_workflow(
        self, db_session: Session, game_session: GameSession
    ):
        """Test that fixed storage cannot be moved."""
        bedroom = create_location(db_session, game_session, location_key="bedroom")
        attic = create_location(db_session, game_session, location_key="attic")

        item_mgr = ItemManager(db_session, game_session)
        storage_mgr = StorageManager(db_session, game_session)

        # Create built-in closet (fixed)
        closet_item, closet_storage = item_mgr.create_container_item(
            item_key="closet",
            display_name="Built-in Closet",
            container_type="closet",
            is_fixed=True,
            world_location_id=bedroom.id,
        )

        # Verify closet is not movable
        assert storage_mgr.can_move_storage("closet_storage") is False
        assert storage_mgr.get_move_difficulty("closet_storage") == float("inf")

        # Attempt to move should fail
        with pytest.raises(ValueError, match="Cannot move fixed"):
            storage_mgr.move_storage_to_location("closet_storage", attic.id)

    def test_heavy_container_strength_check_workflow(
        self, db_session: Session, game_session: GameSession
    ):
        """Test getting move difficulty for heavy containers."""
        warehouse = create_location(db_session, game_session, location_key="warehouse")

        item_mgr = ItemManager(db_session, game_session)
        storage_mgr = StorageManager(db_session, game_session)

        # Create heavy chest
        chest_item, chest_storage = item_mgr.create_container_item(
            item_key="heavy_chest",
            display_name="Iron-Bound Chest",
            container_type="chest",
            is_fixed=False,
            world_location_id=warehouse.id,
        )
        # Set weight requirement
        chest_storage.weight_to_move = 75.0
        db_session.flush()

        # Verify movable but requires strength
        assert storage_mgr.can_move_storage("heavy_chest_storage") is True
        assert storage_mgr.get_move_difficulty("heavy_chest_storage") == 75.0

        # Light pouch has no difficulty
        _, pouch_storage = item_mgr.create_container_item(
            item_key="pouch",
            display_name="Light Pouch",
            container_type="pouch",
            is_fixed=False,
        )

        assert storage_mgr.get_move_difficulty("pouch_storage") is None


class TestComplexNestedScenario:
    """Integration test for complex nested container scenarios."""

    def test_backpack_in_chest_with_items(
        self, db_session: Session, game_session: GameSession
    ):
        """Test items nested multiple levels deep."""
        bedroom = create_location(db_session, game_session, location_key="bedroom")
        player = create_entity(db_session, game_session, entity_key="player")

        item_mgr = ItemManager(db_session, game_session)
        storage_mgr = StorageManager(db_session, game_session)

        # Create chest in bedroom
        chest_item, chest_storage = item_mgr.create_container_item(
            item_key="chest",
            display_name="Storage Chest",
            container_type="chest",
            world_location_id=bedroom.id,
        )

        # Create backpack and put in chest
        backpack_item, backpack_storage = item_mgr.create_container_item(
            item_key="backpack",
            display_name="Backpack",
            container_type="backpack",
            owner_id=player.id,
        )
        item_mgr.put_in_container("backpack", "chest_storage")
        storage_mgr.nest_storage("backpack_storage", "chest_storage")

        # Create pouch in backpack
        pouch_item, pouch_storage = item_mgr.create_container_item(
            item_key="pouch",
            display_name="Coin Pouch",
            container_type="pouch",
            owner_id=player.id,
        )
        item_mgr.put_in_container("pouch", "backpack_storage")
        storage_mgr.nest_storage("pouch_storage", "backpack_storage")

        # Add items at each level
        # Clothes in chest
        item_mgr.create_item(item_key="clothes", display_name="Spare Clothes")
        item_mgr.put_in_container("clothes", "chest_storage")

        # Book in backpack
        item_mgr.create_item(item_key="book", display_name="Spell Book")
        item_mgr.put_in_container("book", "backpack_storage")

        # Coins in pouch
        item_mgr.create_item(item_key="coins", display_name="Gold Coins", quantity=50)
        item_mgr.put_in_container("coins", "pouch_storage")

        # Verify full hierarchy from pouch
        hierarchy = storage_mgr.get_storage_hierarchy("pouch_storage")
        assert len(hierarchy) == 2
        assert hierarchy[0].location_key == "backpack_storage"
        assert hierarchy[1].location_key == "chest_storage"

        # Get all nested contents from chest
        all_items = storage_mgr.get_nested_contents("chest_storage")

        # Should find: clothes, backpack, book, pouch, coins = 5 items
        assert len(all_items) == 5
        keys = [i.item_key for i in all_items]
        assert "clothes" in keys
        assert "backpack" in keys  # Container items count too
        assert "book" in keys
        assert "pouch" in keys
        assert "coins" in keys
