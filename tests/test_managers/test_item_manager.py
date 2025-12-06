"""Tests for ItemManager class."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.enums import ItemType, ItemCondition, StorageLocationType
from src.database.models.session import GameSession
from src.database.models.items import Item, StorageLocation
from src.managers.item_manager import ItemManager
from tests.factories import create_item, create_entity, create_storage_location, create_location


class TestItemManagerBasics:
    """Tests for ItemManager basic operations."""

    def test_get_item_returns_none_when_missing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_item returns None when item doesn't exist."""
        manager = ItemManager(db_session, game_session)

        result = manager.get_item("nonexistent")

        assert result is None

    def test_get_item_returns_existing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_item returns existing item by key."""
        item = create_item(
            db_session, game_session,
            item_key="magic_sword",
            display_name="Excalibur"
        )
        manager = ItemManager(db_session, game_session)

        result = manager.get_item("magic_sword")

        assert result is not None
        assert result.id == item.id
        assert result.display_name == "Excalibur"

    def test_create_item_basic(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify create_item creates new item."""
        manager = ItemManager(db_session, game_session)

        result = manager.create_item(
            item_key="health_potion",
            display_name="Health Potion",
            item_type=ItemType.CONSUMABLE,
        )

        assert result is not None
        assert result.item_key == "health_potion"
        assert result.display_name == "Health Potion"
        assert result.item_type == ItemType.CONSUMABLE
        assert result.session_id == game_session.id

    def test_create_item_with_owner(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify create_item can set owner."""
        entity = create_entity(db_session, game_session)
        manager = ItemManager(db_session, game_session)

        result = manager.create_item(
            item_key="personal_ring",
            display_name="Ring of Power",
            item_type=ItemType.ACCESSORY,
            owner_id=entity.id,
        )

        assert result.owner_id == entity.id


class TestItemManagerInventory:
    """Tests for inventory operations."""

    def test_get_inventory_returns_held_items(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_inventory returns items held by entity."""
        entity = create_entity(db_session, game_session)
        item1 = create_item(
            db_session, game_session,
            item_key="sword",
            holder_id=entity.id
        )
        item2 = create_item(
            db_session, game_session,
            item_key="shield",
            holder_id=entity.id
        )
        # Item held by someone else
        other_entity = create_entity(db_session, game_session)
        create_item(
            db_session, game_session,
            item_key="other_item",
            holder_id=other_entity.id
        )
        manager = ItemManager(db_session, game_session)

        result = manager.get_inventory(entity.id)

        assert len(result) == 2
        keys = [i.item_key for i in result]
        assert "sword" in keys
        assert "shield" in keys

    def test_get_owned_items_includes_borrowed(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_owned_items returns items owned (even if held by others)."""
        owner = create_entity(db_session, game_session, entity_key="owner")
        borrower = create_entity(db_session, game_session, entity_key="borrower")

        # Owned and held by owner
        item1 = create_item(
            db_session, game_session,
            item_key="owned_held",
            owner_id=owner.id,
            holder_id=owner.id
        )
        # Owned by owner, held by borrower
        item2 = create_item(
            db_session, game_session,
            item_key="owned_borrowed",
            owner_id=owner.id,
            holder_id=borrower.id
        )
        # Owned by someone else
        create_item(
            db_session, game_session,
            item_key="other_owned",
            owner_id=borrower.id
        )
        manager = ItemManager(db_session, game_session)

        result = manager.get_owned_items(owner.id)

        assert len(result) == 2
        keys = [i.item_key for i in result]
        assert "owned_held" in keys
        assert "owned_borrowed" in keys


class TestItemManagerTransfer:
    """Tests for item transfer operations."""

    def test_transfer_item_to_entity(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify transfer_item moves item to entity."""
        giver = create_entity(db_session, game_session, entity_key="giver")
        receiver = create_entity(db_session, game_session, entity_key="receiver")
        item = create_item(
            db_session, game_session,
            item_key="gift",
            holder_id=giver.id
        )
        manager = ItemManager(db_session, game_session)

        result = manager.transfer_item("gift", to_entity_id=receiver.id)

        assert result.holder_id == receiver.id

    def test_transfer_item_to_storage(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify transfer_item moves item to storage location."""
        entity = create_entity(db_session, game_session)
        storage = create_storage_location(
            db_session, game_session,
            location_key="chest",
            location_type=StorageLocationType.CONTAINER
        )
        item = create_item(
            db_session, game_session,
            item_key="treasure",
            holder_id=entity.id
        )
        manager = ItemManager(db_session, game_session)

        result = manager.transfer_item("treasure", to_storage_key="chest")

        assert result.storage_location_id == storage.id
        assert result.holder_id is None


class TestItemManagerEquipment:
    """Tests for equipment management."""

    def test_equip_item_sets_slot_and_layer(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify equip_item sets body_slot and body_layer."""
        entity = create_entity(db_session, game_session)
        item = create_item(
            db_session, game_session,
            item_key="shirt",
            item_type=ItemType.CLOTHING,
            holder_id=entity.id
        )
        manager = ItemManager(db_session, game_session)

        result = manager.equip_item("shirt", entity.id, body_slot="upper_body", body_layer=0)

        assert result.body_slot == "upper_body"
        assert result.body_layer == 0

    def test_unequip_item_clears_slot(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify unequip_item clears body_slot."""
        entity = create_entity(db_session, game_session)
        item = create_item(
            db_session, game_session,
            item_key="jacket",
            body_slot="upper_body",
            body_layer=1,
            holder_id=entity.id
        )
        manager = ItemManager(db_session, game_session)

        result = manager.unequip_item("jacket")

        assert result.body_slot is None
        assert result.body_layer == 0

    def test_get_equipped_items(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_equipped_items returns items with body_slot set."""
        entity = create_entity(db_session, game_session)
        # Equipped
        equipped1 = create_item(
            db_session, game_session,
            item_key="hat",
            holder_id=entity.id,
            body_slot="head"
        )
        equipped2 = create_item(
            db_session, game_session,
            item_key="boots",
            holder_id=entity.id,
            body_slot="feet"
        )
        # Not equipped (in inventory)
        create_item(
            db_session, game_session,
            item_key="potion",
            holder_id=entity.id,
            body_slot=None
        )
        manager = ItemManager(db_session, game_session)

        result = manager.get_equipped_items(entity.id)

        assert len(result) == 2
        keys = [i.item_key for i in result]
        assert "hat" in keys
        assert "boots" in keys

    def test_get_visible_equipment_outermost_only(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_visible_equipment returns only visible items."""
        entity = create_entity(db_session, game_session)
        # Layer 0 (innermost) - not visible
        create_item(
            db_session, game_session,
            item_key="undershirt",
            holder_id=entity.id,
            body_slot="upper_body",
            body_layer=0,
            is_visible=False
        )
        # Layer 1 (outer) - visible
        visible = create_item(
            db_session, game_session,
            item_key="jacket",
            holder_id=entity.id,
            body_slot="upper_body",
            body_layer=1,
            is_visible=True
        )
        manager = ItemManager(db_session, game_session)

        result = manager.get_visible_equipment(entity.id)

        assert len(result) == 1
        assert result[0].item_key == "jacket"

    def test_update_visibility_calculates_layers(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify update_visibility sets is_visible based on layers."""
        entity = create_entity(db_session, game_session)
        # Layer 0 on upper_body
        inner = create_item(
            db_session, game_session,
            item_key="inner",
            holder_id=entity.id,
            body_slot="upper_body",
            body_layer=0,
            is_visible=True  # Start as visible
        )
        # Layer 1 on upper_body (covers layer 0)
        outer = create_item(
            db_session, game_session,
            item_key="outer",
            holder_id=entity.id,
            body_slot="upper_body",
            body_layer=1,
            is_visible=True
        )
        manager = ItemManager(db_session, game_session)

        manager.update_visibility(entity.id)

        # Refresh to get updated values
        db_session.refresh(inner)
        db_session.refresh(outer)

        assert inner.is_visible is False  # Covered by outer
        assert outer.is_visible is True  # Outermost


class TestItemManagerStorage:
    """Tests for storage operations."""

    def test_get_items_at_storage(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_items_at_storage returns items in storage."""
        storage = create_storage_location(
            db_session, game_session,
            location_key="treasure_chest",
            location_type=StorageLocationType.CONTAINER
        )
        item1 = create_item(
            db_session, game_session,
            item_key="gold",
            storage_location_id=storage.id
        )
        item2 = create_item(
            db_session, game_session,
            item_key="gems",
            storage_location_id=storage.id
        )
        # Item in different storage
        other_storage = create_storage_location(
            db_session, game_session,
            location_key="other_chest"
        )
        create_item(
            db_session, game_session,
            item_key="junk",
            storage_location_id=other_storage.id
        )
        manager = ItemManager(db_session, game_session)

        result = manager.get_items_at_storage("treasure_chest")

        assert len(result) == 2
        keys = [i.item_key for i in result]
        assert "gold" in keys
        assert "gems" in keys

    def test_create_storage(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify create_storage creates storage location."""
        manager = ItemManager(db_session, game_session)

        result = manager.create_storage(
            location_key="new_chest",
            location_type=StorageLocationType.CONTAINER,
        )

        assert result is not None
        assert result.location_key == "new_chest"
        assert result.location_type == StorageLocationType.CONTAINER

    def test_get_or_create_body_storage(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_or_create_body_storage creates ON_PERSON storage."""
        entity = create_entity(db_session, game_session)
        manager = ItemManager(db_session, game_session)

        result = manager.get_or_create_body_storage(entity.id)

        assert result is not None
        assert result.location_type == StorageLocationType.ON_PERSON
        assert result.owner_entity_id == entity.id


class TestItemManagerCondition:
    """Tests for item condition management."""

    def test_set_item_condition(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify set_item_condition updates condition."""
        item = create_item(
            db_session, game_session,
            item_key="sword",
            condition=ItemCondition.GOOD
        )
        manager = ItemManager(db_session, game_session)

        result = manager.set_item_condition("sword", ItemCondition.WORN)

        assert result.condition == ItemCondition.WORN

    def test_damage_item_reduces_durability(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify damage_item reduces durability."""
        item = create_item(
            db_session, game_session,
            item_key="armor",
            durability=100,
            condition=ItemCondition.PRISTINE
        )
        manager = ItemManager(db_session, game_session)

        result = manager.damage_item("armor", 30)

        assert result.durability == 70

    def test_damage_item_updates_condition_at_threshold(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify damage_item updates condition when crossing thresholds."""
        item = create_item(
            db_session, game_session,
            item_key="shield",
            durability=80,
            condition=ItemCondition.GOOD
        )
        manager = ItemManager(db_session, game_session)

        result = manager.damage_item("shield", 35)

        assert result.durability == 45
        # At durability 45, should be WORN (threshold 50 not met)
        assert result.condition == ItemCondition.DAMAGED


class TestItemManagerLocation:
    """Tests for get_items_at_location method."""

    def test_get_items_at_location_returns_empty_when_no_location(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_items_at_location returns empty list when location doesn't exist."""
        manager = ItemManager(db_session, game_session)

        result = manager.get_items_at_location("nonexistent")

        assert result == []

    def test_get_items_at_location_returns_items_in_storage(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_items_at_location returns items in storage at that location."""
        # Create world location
        location = create_location(
            db_session, game_session,
            location_key="tavern",
            display_name="The Tavern"
        )
        # Create storage at that location
        storage = create_storage_location(
            db_session, game_session,
            location_key="tavern_shelf",
            location_type=StorageLocationType.PLACE,
            world_location_id=location.id
        )
        # Create items in storage (no holder)
        item1 = create_item(
            db_session, game_session,
            item_key="mug",
            storage_location_id=storage.id,
            holder_id=None
        )
        item2 = create_item(
            db_session, game_session,
            item_key="plate",
            storage_location_id=storage.id,
            holder_id=None
        )
        # Create item being held (should not be returned)
        entity = create_entity(db_session, game_session)
        create_item(
            db_session, game_session,
            item_key="drink",
            storage_location_id=storage.id,
            holder_id=entity.id
        )
        manager = ItemManager(db_session, game_session)

        result = manager.get_items_at_location("tavern")

        assert len(result) == 2
        keys = [i.item_key for i in result]
        assert "mug" in keys
        assert "plate" in keys

    def test_get_items_at_location_excludes_other_locations(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_items_at_location excludes items at other locations."""
        # Create two locations
        tavern = create_location(
            db_session, game_session,
            location_key="tavern"
        )
        market = create_location(
            db_session, game_session,
            location_key="market"
        )
        # Storage at tavern
        tavern_storage = create_storage_location(
            db_session, game_session,
            location_key="tavern_storage",
            location_type=StorageLocationType.PLACE,
            world_location_id=tavern.id
        )
        # Storage at market
        market_storage = create_storage_location(
            db_session, game_session,
            location_key="market_storage",
            location_type=StorageLocationType.PLACE,
            world_location_id=market.id
        )
        # Items at tavern
        create_item(
            db_session, game_session,
            item_key="tavern_item",
            storage_location_id=tavern_storage.id,
            holder_id=None
        )
        # Items at market
        create_item(
            db_session, game_session,
            item_key="market_item",
            storage_location_id=market_storage.id,
            holder_id=None
        )
        manager = ItemManager(db_session, game_session)

        result = manager.get_items_at_location("tavern")

        assert len(result) == 1
        assert result[0].item_key == "tavern_item"
