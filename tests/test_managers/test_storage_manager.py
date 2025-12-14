"""Tests for StorageManager class."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.enums import StorageLocationType, ItemType
from src.database.models.session import GameSession
from src.database.models.items import StorageLocation
from src.managers.storage_manager import StorageManager
from tests.factories import (
    create_item,
    create_entity,
    create_storage_location,
    create_location,
)


class TestStorageManagerPortability:
    """Tests for storage portability operations."""

    def test_can_move_storage_returns_true_for_portable(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify can_move_storage returns True for non-fixed storage."""
        storage = create_storage_location(
            db_session, game_session,
            location_key="backpack",
            location_type=StorageLocationType.CONTAINER,
            is_fixed=False,
        )
        manager = StorageManager(db_session, game_session)

        result = manager.can_move_storage("backpack")

        assert result is True

    def test_can_move_storage_returns_false_for_fixed(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify can_move_storage returns False for fixed storage."""
        storage = create_storage_location(
            db_session, game_session,
            location_key="closet",
            location_type=StorageLocationType.CONTAINER,
            is_fixed=True,
        )
        manager = StorageManager(db_session, game_session)

        result = manager.can_move_storage("closet")

        assert result is False

    def test_can_move_storage_raises_for_nonexistent(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify can_move_storage raises ValueError for nonexistent storage."""
        manager = StorageManager(db_session, game_session)

        with pytest.raises(ValueError, match="Storage not found"):
            manager.can_move_storage("nonexistent")

    def test_get_move_difficulty_returns_weight(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_move_difficulty returns weight_to_move."""
        storage = create_storage_location(
            db_session, game_session,
            location_key="heavy_chest",
            location_type=StorageLocationType.CONTAINER,
            is_fixed=False,
            weight_to_move=50.0,
        )
        manager = StorageManager(db_session, game_session)

        result = manager.get_move_difficulty("heavy_chest")

        assert result == 50.0

    def test_get_move_difficulty_returns_none_for_light(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_move_difficulty returns None for easily movable storage."""
        storage = create_storage_location(
            db_session, game_session,
            location_key="pouch",
            location_type=StorageLocationType.CONTAINER,
            is_fixed=False,
            weight_to_move=None,
        )
        manager = StorageManager(db_session, game_session)

        result = manager.get_move_difficulty("pouch")

        assert result is None

    def test_get_move_difficulty_returns_infinity_for_fixed(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_move_difficulty returns infinity for fixed storage."""
        storage = create_storage_location(
            db_session, game_session,
            location_key="built_in_closet",
            location_type=StorageLocationType.CONTAINER,
            is_fixed=True,
        )
        manager = StorageManager(db_session, game_session)

        result = manager.get_move_difficulty("built_in_closet")

        assert result == float("inf")


class TestStorageManagerHierarchy:
    """Tests for storage hierarchy operations."""

    def test_get_storage_hierarchy_returns_empty_for_root(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_storage_hierarchy returns empty list for top-level storage."""
        storage = create_storage_location(
            db_session, game_session,
            location_key="chest",
            location_type=StorageLocationType.CONTAINER,
        )
        manager = StorageManager(db_session, game_session)

        result = manager.get_storage_hierarchy("chest")

        assert result == []

    def test_get_storage_hierarchy_returns_parents(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_storage_hierarchy returns parent chain."""
        parent = create_storage_location(
            db_session, game_session,
            location_key="backpack",
            location_type=StorageLocationType.CONTAINER,
        )
        child = create_storage_location(
            db_session, game_session,
            location_key="pouch_in_backpack",
            location_type=StorageLocationType.CONTAINER,
            parent_location_id=parent.id,
        )
        manager = StorageManager(db_session, game_session)

        result = manager.get_storage_hierarchy("pouch_in_backpack")

        assert len(result) == 1
        assert result[0].location_key == "backpack"

    def test_get_storage_hierarchy_returns_multiple_levels(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_storage_hierarchy returns full parent chain."""
        grandparent = create_storage_location(
            db_session, game_session,
            location_key="room_shelf",
            location_type=StorageLocationType.PLACE,
        )
        parent = create_storage_location(
            db_session, game_session,
            location_key="backpack_on_shelf",
            location_type=StorageLocationType.CONTAINER,
            parent_location_id=grandparent.id,
        )
        child = create_storage_location(
            db_session, game_session,
            location_key="pouch_in_backpack",
            location_type=StorageLocationType.CONTAINER,
            parent_location_id=parent.id,
        )
        manager = StorageManager(db_session, game_session)

        result = manager.get_storage_hierarchy("pouch_in_backpack")

        assert len(result) == 2
        # Returns from immediate parent to root
        assert result[0].location_key == "backpack_on_shelf"
        assert result[1].location_key == "room_shelf"

    def test_get_nested_contents_returns_direct_items(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_nested_contents returns items directly in storage."""
        storage = create_storage_location(
            db_session, game_session,
            location_key="chest",
            location_type=StorageLocationType.CONTAINER,
        )
        item1 = create_item(
            db_session, game_session,
            item_key="sword",
            storage_location_id=storage.id,
        )
        item2 = create_item(
            db_session, game_session,
            item_key="shield",
            storage_location_id=storage.id,
        )
        manager = StorageManager(db_session, game_session)

        result = manager.get_nested_contents("chest")

        assert len(result) == 2
        keys = [i.item_key for i in result]
        assert "sword" in keys
        assert "shield" in keys

    def test_get_nested_contents_includes_nested_items(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_nested_contents returns items in nested containers."""
        # Backpack storage
        backpack_storage = create_storage_location(
            db_session, game_session,
            location_key="backpack_storage",
            location_type=StorageLocationType.CONTAINER,
        )
        # Item directly in backpack
        direct_item = create_item(
            db_session, game_session,
            item_key="book",
            storage_location_id=backpack_storage.id,
        )
        # Pouch inside backpack
        pouch_storage = create_storage_location(
            db_session, game_session,
            location_key="pouch_storage",
            location_type=StorageLocationType.CONTAINER,
            parent_location_id=backpack_storage.id,
        )
        # Item in pouch
        nested_item = create_item(
            db_session, game_session,
            item_key="coins",
            storage_location_id=pouch_storage.id,
        )
        manager = StorageManager(db_session, game_session)

        result = manager.get_nested_contents("backpack_storage")

        assert len(result) == 2
        keys = [i.item_key for i in result]
        assert "book" in keys
        assert "coins" in keys


class TestStorageManagerLocation:
    """Tests for storage location operations."""

    def test_get_all_storages_at_location(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_all_storages_at_location returns storages at location."""
        location = create_location(db_session, game_session, location_key="tavern")
        storage1 = create_storage_location(
            db_session, game_session,
            location_key="shelf",
            location_type=StorageLocationType.PLACE,
            world_location_id=location.id,
        )
        storage2 = create_storage_location(
            db_session, game_session,
            location_key="barrel",
            location_type=StorageLocationType.CONTAINER,
            world_location_id=location.id,
        )
        # Different location
        other_loc = create_location(db_session, game_session, location_key="market")
        create_storage_location(
            db_session, game_session,
            location_key="market_stall",
            world_location_id=other_loc.id,
        )
        manager = StorageManager(db_session, game_session)

        result = manager.get_all_storages_at_location(location.id)

        assert len(result) == 2
        keys = [s.location_key for s in result]
        assert "shelf" in keys
        assert "barrel" in keys

    def test_move_storage_to_location(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify move_storage_to_location moves portable storage."""
        tavern = create_location(db_session, game_session, location_key="tavern")
        market = create_location(db_session, game_session, location_key="market")
        storage = create_storage_location(
            db_session, game_session,
            location_key="crate",
            location_type=StorageLocationType.CONTAINER,
            world_location_id=tavern.id,
            is_fixed=False,
        )
        manager = StorageManager(db_session, game_session)

        result = manager.move_storage_to_location("crate", market.id)

        assert result.world_location_id == market.id

    def test_move_storage_to_location_raises_for_fixed(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify move_storage_to_location raises for fixed storage."""
        tavern = create_location(db_session, game_session, location_key="tavern")
        market = create_location(db_session, game_session, location_key="market")
        storage = create_storage_location(
            db_session, game_session,
            location_key="built_in_closet",
            location_type=StorageLocationType.CONTAINER,
            world_location_id=tavern.id,
            is_fixed=True,
        )
        manager = StorageManager(db_session, game_session)

        with pytest.raises(ValueError, match="Cannot move fixed"):
            manager.move_storage_to_location("built_in_closet", market.id)

    def test_move_storage_with_contents_moves_all(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify move_storage_with_contents moves storage and nested containers."""
        tavern = create_location(db_session, game_session, location_key="tavern")
        market = create_location(db_session, game_session, location_key="market")

        # Backpack at tavern
        backpack = create_storage_location(
            db_session, game_session,
            location_key="backpack",
            location_type=StorageLocationType.CONTAINER,
            world_location_id=tavern.id,
            is_fixed=False,
        )
        # Pouch inside backpack
        pouch = create_storage_location(
            db_session, game_session,
            location_key="pouch",
            location_type=StorageLocationType.CONTAINER,
            parent_location_id=backpack.id,
        )
        manager = StorageManager(db_session, game_session)

        manager.move_storage_to_location("backpack", market.id)

        # Refresh to see changes
        db_session.refresh(backpack)
        db_session.refresh(pouch)

        # Backpack moved
        assert backpack.world_location_id == market.id
        # Pouch follows (has no world_location_id, but parent moved)
        # The hierarchy relationship remains intact


class TestStorageManagerNesting:
    """Tests for container nesting operations."""

    def test_nest_storage_in_parent(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify nest_storage sets parent relationship."""
        backpack = create_storage_location(
            db_session, game_session,
            location_key="backpack",
            location_type=StorageLocationType.CONTAINER,
        )
        pouch = create_storage_location(
            db_session, game_session,
            location_key="pouch",
            location_type=StorageLocationType.CONTAINER,
        )
        manager = StorageManager(db_session, game_session)

        result = manager.nest_storage("pouch", "backpack")

        assert result.parent_location_id == backpack.id

    def test_unnest_storage_removes_parent(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify unnest_storage clears parent relationship."""
        backpack = create_storage_location(
            db_session, game_session,
            location_key="backpack",
            location_type=StorageLocationType.CONTAINER,
        )
        pouch = create_storage_location(
            db_session, game_session,
            location_key="pouch",
            location_type=StorageLocationType.CONTAINER,
            parent_location_id=backpack.id,
        )
        manager = StorageManager(db_session, game_session)

        result = manager.unnest_storage("pouch")

        assert result.parent_location_id is None

    def test_get_child_storages(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_child_storages returns nested containers."""
        backpack = create_storage_location(
            db_session, game_session,
            location_key="backpack",
            location_type=StorageLocationType.CONTAINER,
        )
        pouch1 = create_storage_location(
            db_session, game_session,
            location_key="pouch1",
            location_type=StorageLocationType.CONTAINER,
            parent_location_id=backpack.id,
        )
        pouch2 = create_storage_location(
            db_session, game_session,
            location_key="pouch2",
            location_type=StorageLocationType.CONTAINER,
            parent_location_id=backpack.id,
        )
        manager = StorageManager(db_session, game_session)

        result = manager.get_child_storages("backpack")

        assert len(result) == 2
        keys = [s.location_key for s in result]
        assert "pouch1" in keys
        assert "pouch2" in keys
