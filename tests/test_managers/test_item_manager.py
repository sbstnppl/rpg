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


class TestItemManagerSlotValidation:
    """Tests for slot availability validation methods."""

    def test_check_slot_available_returns_true_when_empty(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify check_slot_available returns True when slot is empty."""
        entity = create_entity(db_session, game_session)
        manager = ItemManager(db_session, game_session)

        result = manager.check_slot_available(entity.id, "main_hand")

        assert result is True

    def test_check_slot_available_returns_false_when_occupied(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify check_slot_available returns False when slot has item."""
        entity = create_entity(db_session, game_session)
        create_item(
            db_session, game_session,
            item_key="sword",
            holder_id=entity.id,
            body_slot="main_hand"
        )
        manager = ItemManager(db_session, game_session)

        result = manager.check_slot_available(entity.id, "main_hand")

        assert result is False

    def test_check_slot_available_different_slot_unaffected(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify check_slot_available is slot-specific."""
        entity = create_entity(db_session, game_session)
        create_item(
            db_session, game_session,
            item_key="sword",
            holder_id=entity.id,
            body_slot="main_hand"
        )
        manager = ItemManager(db_session, game_session)

        result = manager.check_slot_available(entity.id, "off_hand")

        assert result is True

    def test_get_item_in_slot_returns_item(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_item_in_slot returns the item in specified slot."""
        entity = create_entity(db_session, game_session)
        item = create_item(
            db_session, game_session,
            item_key="torch",
            holder_id=entity.id,
            body_slot="off_hand"
        )
        manager = ItemManager(db_session, game_session)

        result = manager.get_item_in_slot(entity.id, "off_hand")

        assert result is not None
        assert result.item_key == "torch"

    def test_get_item_in_slot_returns_none_when_empty(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_item_in_slot returns None when slot is empty."""
        entity = create_entity(db_session, game_session)
        manager = ItemManager(db_session, game_session)

        result = manager.get_item_in_slot(entity.id, "main_hand")

        assert result is None


class TestItemManagerWeightValidation:
    """Tests for weight limit validation methods."""

    def test_get_total_carried_weight_empty_inventory(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_total_carried_weight returns 0 for empty inventory."""
        entity = create_entity(db_session, game_session)
        manager = ItemManager(db_session, game_session)

        result = manager.get_total_carried_weight(entity.id)

        assert result == 0.0

    def test_get_total_carried_weight_sums_items(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_total_carried_weight sums all item weights."""
        entity = create_entity(db_session, game_session)
        create_item(
            db_session, game_session,
            item_key="sword",
            holder_id=entity.id,
            weight=5.0
        )
        create_item(
            db_session, game_session,
            item_key="shield",
            holder_id=entity.id,
            weight=8.0
        )
        manager = ItemManager(db_session, game_session)

        result = manager.get_total_carried_weight(entity.id)

        assert result == 13.0

    def test_get_total_carried_weight_multiplies_by_quantity(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_total_carried_weight multiplies weight by quantity."""
        entity = create_entity(db_session, game_session)
        create_item(
            db_session, game_session,
            item_key="arrows",
            holder_id=entity.id,
            weight=0.1,
            quantity=20
        )
        manager = ItemManager(db_session, game_session)

        result = manager.get_total_carried_weight(entity.id)

        assert result == pytest.approx(2.0, rel=0.01)

    def test_get_total_carried_weight_ignores_none_weight(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_total_carried_weight ignores items with None weight."""
        entity = create_entity(db_session, game_session)
        create_item(
            db_session, game_session,
            item_key="sword",
            holder_id=entity.id,
            weight=5.0
        )
        create_item(
            db_session, game_session,
            item_key="ring",
            holder_id=entity.id,
            weight=None
        )
        manager = ItemManager(db_session, game_session)

        result = manager.get_total_carried_weight(entity.id)

        assert result == 5.0

    def test_can_carry_weight_allows_under_limit(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify can_carry_weight returns True when under limit."""
        entity = create_entity(db_session, game_session)
        create_item(
            db_session, game_session,
            item_key="sword",
            holder_id=entity.id,
            weight=10.0
        )
        manager = ItemManager(db_session, game_session)

        result = manager.can_carry_weight(entity.id, 5.0, max_weight=50.0)

        assert result is True

    def test_can_carry_weight_rejects_over_limit(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify can_carry_weight returns False when would exceed limit."""
        entity = create_entity(db_session, game_session)
        create_item(
            db_session, game_session,
            item_key="armor",
            holder_id=entity.id,
            weight=45.0
        )
        manager = ItemManager(db_session, game_session)

        result = manager.can_carry_weight(entity.id, 10.0, max_weight=50.0)

        assert result is False

    def test_can_carry_weight_allows_exact_limit(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify can_carry_weight allows reaching exactly the limit."""
        entity = create_entity(db_session, game_session)
        create_item(
            db_session, game_session,
            item_key="pack",
            holder_id=entity.id,
            weight=40.0
        )
        manager = ItemManager(db_session, game_session)

        result = manager.can_carry_weight(entity.id, 10.0, max_weight=50.0)

        assert result is True


class TestItemManagerFindAvailableSlot:
    """Tests for find_available_slot auto-assignment."""

    def test_find_available_slot_weapon_prefers_main_hand(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify find_available_slot assigns weapons to main_hand first."""
        entity = create_entity(db_session, game_session)
        manager = ItemManager(db_session, game_session)

        result = manager.find_available_slot(entity.id, "weapon")

        assert result == "main_hand"

    def test_find_available_slot_weapon_falls_back_to_off_hand(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify find_available_slot uses off_hand when main_hand occupied."""
        entity = create_entity(db_session, game_session)
        create_item(
            db_session, game_session,
            item_key="sword",
            holder_id=entity.id,
            body_slot="main_hand"
        )
        manager = ItemManager(db_session, game_session)

        result = manager.find_available_slot(entity.id, "weapon")

        assert result == "off_hand"

    def test_find_available_slot_small_misc_prefers_pouch_when_available(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify find_available_slot assigns small misc to belt pouch when belt provides it."""
        entity = create_entity(db_session, game_session)
        # Belt that provides pouch slots
        create_item(
            db_session, game_session,
            item_key="leather_belt",
            holder_id=entity.id,
            body_slot="waist",
            provides_slots=["belt_pouch_1", "belt_pouch_2"]
        )
        manager = ItemManager(db_session, game_session)

        result = manager.find_available_slot(entity.id, "misc", item_size="small")

        assert result == "belt_pouch_1"

    def test_find_available_slot_small_misc_uses_hands_without_pouches(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify find_available_slot falls back to hands when no storage available."""
        entity = create_entity(db_session, game_session)
        manager = ItemManager(db_session, game_session)

        # Without any equipment providing bonus slots, falls back to hands
        result = manager.find_available_slot(entity.id, "misc", item_size="small")

        assert result == "main_hand"

    def test_find_available_slot_small_misc_falls_back_to_pocket(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify find_available_slot uses pocket when pouches full."""
        entity = create_entity(db_session, game_session)
        # Pants with pockets, belt with pouches
        create_item(
            db_session, game_session,
            item_key="trousers",
            holder_id=entity.id,
            body_slot="legs",
            provides_slots=["pocket_left", "pocket_right"]
        )
        create_item(
            db_session, game_session,
            item_key="belt",
            holder_id=entity.id,
            body_slot="waist",
            provides_slots=["belt_pouch_1", "belt_pouch_2"]
        )
        # Fill pouches
        create_item(
            db_session, game_session,
            item_key="coins",
            holder_id=entity.id,
            body_slot="belt_pouch_1"
        )
        create_item(
            db_session, game_session,
            item_key="gems",
            holder_id=entity.id,
            body_slot="belt_pouch_2"
        )
        manager = ItemManager(db_session, game_session)

        result = manager.find_available_slot(entity.id, "misc", item_size="small")

        assert result == "pocket_left"

    def test_find_available_slot_large_misc_uses_hands_or_back(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify find_available_slot assigns large items to hands/back."""
        entity = create_entity(db_session, game_session)
        manager = ItemManager(db_session, game_session)

        result = manager.find_available_slot(entity.id, "misc", item_size="large")

        assert result in ["main_hand", "off_hand", "back", "backpack_main"]

    def test_find_available_slot_returns_none_when_all_full(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify find_available_slot returns None when no slots available."""
        entity = create_entity(db_session, game_session)
        # Fill all relevant slots for weapons
        create_item(
            db_session, game_session,
            item_key="sword",
            holder_id=entity.id,
            body_slot="main_hand"
        )
        create_item(
            db_session, game_session,
            item_key="shield",
            holder_id=entity.id,
            body_slot="off_hand"
        )
        create_item(
            db_session, game_session,
            item_key="bow",
            holder_id=entity.id,
            body_slot="back"
        )
        manager = ItemManager(db_session, game_session)

        result = manager.find_available_slot(entity.id, "weapon")

        assert result is None

    def test_find_available_slot_consumable_prefers_pouch_when_available(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify find_available_slot assigns consumables to belt pouch when available."""
        entity = create_entity(db_session, game_session)
        # Belt with pouch slots
        create_item(
            db_session, game_session,
            item_key="belt",
            holder_id=entity.id,
            body_slot="waist",
            provides_slots=["belt_pouch_1"]
        )
        manager = ItemManager(db_session, game_session)

        result = manager.find_available_slot(entity.id, "consumable")

        assert result == "belt_pouch_1"

    def test_find_available_slot_consumable_returns_none_without_storage(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify find_available_slot returns None for consumable without storage slots."""
        entity = create_entity(db_session, game_session)
        manager = ItemManager(db_session, game_session)

        # Without equipment providing bonus slots, consumables have no place
        result = manager.find_available_slot(entity.id, "consumable")

        assert result is None


class TestItemManagerInventorySummary:
    """Tests for get_inventory_summary method."""

    def test_get_inventory_summary_empty_inventory(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_inventory_summary returns correct structure for empty inventory."""
        entity = create_entity(db_session, game_session)
        manager = ItemManager(db_session, game_session)

        result = manager.get_inventory_summary(entity.id)

        assert "total_weight" in result
        assert "occupied_slots" in result
        assert "free_hand_slots" in result
        assert "can_hold_more" in result
        assert result["total_weight"] == 0.0
        # Includes hand_left, hand_right, main_hand, off_hand
        assert "main_hand" in result["free_hand_slots"]
        assert "off_hand" in result["free_hand_slots"]

    def test_get_inventory_summary_includes_weight(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_inventory_summary includes total weight."""
        entity = create_entity(db_session, game_session)
        create_item(
            db_session, game_session,
            item_key="sword",
            holder_id=entity.id,
            weight=5.0
        )
        manager = ItemManager(db_session, game_session)

        result = manager.get_inventory_summary(entity.id)

        assert result["total_weight"] == 5.0

    def test_get_inventory_summary_tracks_occupied_slots(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_inventory_summary lists occupied slots."""
        entity = create_entity(db_session, game_session)
        create_item(
            db_session, game_session,
            item_key="sword",
            holder_id=entity.id,
            body_slot="main_hand"
        )
        create_item(
            db_session, game_session,
            item_key="torch",
            holder_id=entity.id,
            body_slot="off_hand"
        )
        manager = ItemManager(db_session, game_session)

        result = manager.get_inventory_summary(entity.id)

        assert "main_hand" in result["occupied_slots"]
        assert "off_hand" in result["occupied_slots"]
        # main_hand and off_hand occupied, but hand_left/hand_right still free
        assert "main_hand" not in result["free_hand_slots"]
        assert "off_hand" not in result["free_hand_slots"]

    def test_get_inventory_summary_can_hold_more_true_with_free_slots(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify can_hold_more is True when slots available."""
        entity = create_entity(db_session, game_session)
        manager = ItemManager(db_session, game_session)

        result = manager.get_inventory_summary(entity.id)

        assert result["can_hold_more"] is True

    def test_get_inventory_summary_tracks_storage_slots(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_inventory_summary includes free storage slots from equipped items."""
        entity = create_entity(db_session, game_session)
        # Belt providing pouch slots
        create_item(
            db_session, game_session,
            item_key="belt",
            holder_id=entity.id,
            body_slot="waist",
            provides_slots=["belt_pouch_1", "belt_pouch_2"]
        )
        manager = ItemManager(db_session, game_session)

        result = manager.get_inventory_summary(entity.id)

        assert "free_storage_slots" in result
        assert "belt_pouch_1" in result["free_storage_slots"]
        assert "belt_pouch_2" in result["free_storage_slots"]


# =============================================================================
# Theft Operations Tests (NEW)
# =============================================================================


class TestItemManagerTheft:
    """Tests for theft-related operations."""

    def test_steal_item_sets_stolen_flags(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify steal_item sets is_stolen and was_ever_stolen."""
        victim = create_entity(db_session, game_session, entity_key="victim")
        thief = create_entity(db_session, game_session, entity_key="thief")
        item = create_item(
            db_session, game_session,
            item_key="gold_ring",
            owner_id=victim.id,
            holder_id=victim.id,
        )
        manager = ItemManager(db_session, game_session)

        result = manager.steal_item("gold_ring", thief.id, from_entity_id=victim.id)

        assert result.is_stolen is True
        assert result.was_ever_stolen is True
        assert result.stolen_from_id == victim.id
        assert result.holder_id == thief.id
        # Owner doesn't change - still legally victim's
        assert result.owner_id == victim.id

    def test_steal_item_from_location(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify steal_item can track stealing from a location/establishment."""
        inn = create_location(db_session, game_session, location_key="inn")
        thief = create_entity(db_session, game_session, entity_key="thief")
        item = create_item(
            db_session, game_session,
            item_key="inn_bowl",
            owner_location_id=inn.id,
        )
        manager = ItemManager(db_session, game_session)

        result = manager.steal_item("inn_bowl", thief.id, from_location_id=inn.id)

        assert result.is_stolen is True
        assert result.was_ever_stolen is True
        assert result.stolen_from_location_id == inn.id
        assert result.holder_id == thief.id

    def test_steal_item_raises_for_nonexistent(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify steal_item raises ValueError for nonexistent item."""
        thief = create_entity(db_session, game_session, entity_key="thief")
        manager = ItemManager(db_session, game_session)

        with pytest.raises(ValueError, match="Item not found"):
            manager.steal_item("nonexistent", thief.id)

    def test_return_stolen_item_to_entity(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify return_stolen_item clears is_stolen and returns to victim."""
        victim = create_entity(db_session, game_session, entity_key="victim")
        thief = create_entity(db_session, game_session, entity_key="thief")
        item = create_item(
            db_session, game_session,
            item_key="gold_ring",
            owner_id=victim.id,
            holder_id=thief.id,
            is_stolen=True,
            was_ever_stolen=True,
            stolen_from_id=victim.id,
        )
        manager = ItemManager(db_session, game_session)

        result = manager.return_stolen_item("gold_ring")

        assert result.is_stolen is False
        assert result.was_ever_stolen is True  # Historical flag remains
        assert result.holder_id == victim.id
        assert result.stolen_from_id is None  # Cleared after return

    def test_return_stolen_item_to_location(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify return_stolen_item can return to a location."""
        inn = create_location(db_session, game_session, location_key="inn")
        thief = create_entity(db_session, game_session, entity_key="thief")
        marta = create_entity(db_session, game_session, entity_key="marta")
        item = create_item(
            db_session, game_session,
            item_key="inn_bowl",
            owner_location_id=inn.id,
            holder_id=thief.id,
            is_stolen=True,
            was_ever_stolen=True,
            stolen_from_location_id=inn.id,
        )
        manager = ItemManager(db_session, game_session)

        # Return to a representative of the location (Marta the innkeeper)
        result = manager.return_stolen_item("inn_bowl", to_entity_id=marta.id)

        assert result.is_stolen is False
        assert result.was_ever_stolen is True
        assert result.holder_id == marta.id
        assert result.stolen_from_location_id is None

    def test_legitimize_item_clears_stolen_transfers_owner(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify legitimize_item clears is_stolen via sale/gift."""
        victim = create_entity(db_session, game_session, entity_key="victim")
        thief = create_entity(db_session, game_session, entity_key="thief")
        fence = create_entity(db_session, game_session, entity_key="fence")
        item = create_item(
            db_session, game_session,
            item_key="gold_ring",
            owner_id=victim.id,
            holder_id=thief.id,
            is_stolen=True,
            was_ever_stolen=True,
            stolen_from_id=victim.id,
        )
        manager = ItemManager(db_session, game_session)

        # Thief sells to fence - legitimate new owner
        result = manager.legitimize_item("gold_ring", new_owner_id=fence.id)

        assert result.is_stolen is False  # No longer stolen
        assert result.was_ever_stolen is True  # Historical stain remains
        assert result.owner_id == fence.id  # New legitimate owner
        assert result.holder_id == fence.id  # Transferred possession too
        assert result.stolen_from_id is None  # Cleared

    def test_legitimize_item_to_location(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify legitimize_item can transfer ownership to a location."""
        thief = create_entity(db_session, game_session, entity_key="thief")
        new_inn = create_location(db_session, game_session, location_key="new_inn")
        item = create_item(
            db_session, game_session,
            item_key="stolen_bowl",
            holder_id=thief.id,
            is_stolen=True,
            was_ever_stolen=True,
        )
        manager = ItemManager(db_session, game_session)

        # Donate to new establishment
        result = manager.legitimize_item("stolen_bowl", new_owner_location_id=new_inn.id)

        assert result.is_stolen is False
        assert result.was_ever_stolen is True
        assert result.owner_location_id == new_inn.id
        assert result.owner_id is None  # Location owns, not entity

    def test_legitimize_item_raises_for_nonexistent(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify legitimize_item raises ValueError for nonexistent item."""
        manager = ItemManager(db_session, game_session)

        with pytest.raises(ValueError, match="Item not found"):
            manager.legitimize_item("nonexistent", new_owner_id=1)


# =============================================================================
# Container Linking Tests (NEW)
# =============================================================================


class TestItemManagerContainer:
    """Tests for container-item linking operations."""

    def test_create_container_item_creates_both(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify create_container_item creates item and linked storage."""
        player = create_entity(db_session, game_session, entity_key="player")
        manager = ItemManager(db_session, game_session)

        item, storage = manager.create_container_item(
            item_key="backpack",
            display_name="Leather Backpack",
            owner_id=player.id,
            container_type="backpack",
            capacity=20,
            weight_capacity=40.0,
        )

        # Item created correctly
        assert item.item_key == "backpack"
        assert item.display_name == "Leather Backpack"
        assert item.item_type == ItemType.CONTAINER
        assert item.owner_id == player.id

        # Storage created correctly
        assert storage.location_key == "backpack_storage"
        assert storage.location_type == StorageLocationType.CONTAINER
        assert storage.container_type == "backpack"
        assert storage.capacity == 20
        assert storage.weight_capacity == 40.0

        # Linked together
        assert storage.container_item_id == item.id

    def test_create_container_item_fixed_storage(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify create_container_item can create fixed containers."""
        location = create_location(db_session, game_session, location_key="bedroom")
        manager = ItemManager(db_session, game_session)

        item, storage = manager.create_container_item(
            item_key="closet",
            display_name="Wooden Closet",
            container_type="closet",
            is_fixed=True,
            world_location_id=location.id,
        )

        assert storage.is_fixed is True
        assert storage.world_location_id == location.id

    def test_put_in_container_moves_item(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify put_in_container moves item to container storage."""
        player = create_entity(db_session, game_session, entity_key="player")
        manager = ItemManager(db_session, game_session)

        # Create backpack
        _, backpack_storage = manager.create_container_item(
            item_key="backpack",
            display_name="Backpack",
            owner_id=player.id,
            container_type="backpack",
            capacity=20,
        )

        # Create item to put in backpack
        sword = manager.create_item(
            item_key="sword",
            display_name="Sword",
            owner_id=player.id,
            holder_id=player.id,
        )

        result = manager.put_in_container("sword", "backpack_storage")

        assert result.storage_location_id == backpack_storage.id
        assert result.holder_id is None  # No longer held, in storage

    def test_put_in_container_checks_item_capacity(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify put_in_container respects item count capacity."""
        player = create_entity(db_session, game_session, entity_key="player")
        manager = ItemManager(db_session, game_session)

        # Create tiny pouch with capacity 1
        _, pouch_storage = manager.create_container_item(
            item_key="tiny_pouch",
            display_name="Tiny Pouch",
            owner_id=player.id,
            container_type="pouch",
            capacity=1,
        )

        # Put first item in
        manager.create_item(item_key="coin1", display_name="Coin 1")
        manager.put_in_container("coin1", "tiny_pouch_storage")

        # Second item should fail
        manager.create_item(item_key="coin2", display_name="Coin 2")
        with pytest.raises(ValueError, match="capacity"):
            manager.put_in_container("coin2", "tiny_pouch_storage")

    def test_put_in_container_checks_weight_capacity(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify put_in_container respects weight capacity."""
        player = create_entity(db_session, game_session, entity_key="player")
        manager = ItemManager(db_session, game_session)

        # Create pouch with limited weight capacity
        _, pouch_storage = manager.create_container_item(
            item_key="pouch",
            display_name="Small Pouch",
            owner_id=player.id,
            container_type="pouch",
            weight_capacity=1.0,  # 1 pound max
        )

        # Create heavy item
        manager.create_item(item_key="heavy_rock", display_name="Heavy Rock", weight=5.0)

        with pytest.raises(ValueError, match="weight"):
            manager.put_in_container("heavy_rock", "pouch_storage")

    def test_get_container_remaining_capacity(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_container_remaining_capacity calculates correctly."""
        player = create_entity(db_session, game_session, entity_key="player")
        manager = ItemManager(db_session, game_session)

        # Create backpack with capacity 10 items, 20 lbs
        _, backpack_storage = manager.create_container_item(
            item_key="backpack",
            display_name="Backpack",
            owner_id=player.id,
            container_type="backpack",
            capacity=10,
            weight_capacity=20.0,
        )

        # Add some items
        manager.create_item(item_key="item1", display_name="Item 1", weight=5.0)
        manager.put_in_container("item1", "backpack_storage")
        manager.create_item(item_key="item2", display_name="Item 2", weight=3.0)
        manager.put_in_container("item2", "backpack_storage")

        count_remaining, weight_remaining = manager.get_container_remaining_capacity(
            "backpack_storage"
        )

        assert count_remaining == 8  # 10 - 2 items
        assert weight_remaining == 12.0  # 20 - 8 lbs


# =============================================================================
# Temporary Storage Tests (NEW)
# =============================================================================


class TestItemManagerTemporaryStorage:
    """Tests for temporary storage operations."""

    def test_create_temporary_surface_basic(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify create_temporary_surface creates a temporary PLACE storage."""
        location = create_location(db_session, game_session, location_key="tavern")
        manager = ItemManager(db_session, game_session)

        result = manager.create_temporary_surface(
            surface_key="tavern_table_1",
            world_location_id=location.id,
            container_type="table",
        )

        assert result.location_key == "tavern_table_1"
        assert result.location_type == StorageLocationType.PLACE
        assert result.is_temporary is True
        assert result.world_location_id == location.id
        assert result.container_type == "table"

    def test_create_temporary_surface_with_capacity(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify create_temporary_surface can set capacity limits."""
        location = create_location(db_session, game_session, location_key="shop")
        manager = ItemManager(db_session, game_session)

        result = manager.create_temporary_surface(
            surface_key="shop_counter",
            world_location_id=location.id,
            container_type="counter",
            capacity=10,
            weight_capacity=50.0,
        )

        assert result.capacity == 10
        assert result.weight_capacity == 50.0

    def test_create_temporary_surface_floor(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify create_temporary_surface works for floor surfaces."""
        location = create_location(db_session, game_session, location_key="street")
        manager = ItemManager(db_session, game_session)

        result = manager.create_temporary_surface(
            surface_key="street_floor_01",
            world_location_id=location.id,
            container_type="floor",
        )

        assert result.is_temporary is True
        assert result.container_type == "floor"

    def test_cleanup_empty_temporary_storage_removes_empty(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify cleanup_empty_temporary_storage removes empty temp storage."""
        location = create_location(db_session, game_session, location_key="tavern")
        manager = ItemManager(db_session, game_session)

        # Create temporary storage
        temp_storage = manager.create_temporary_surface(
            surface_key="empty_table",
            world_location_id=location.id,
        )
        temp_id = temp_storage.id

        # Cleanup - should remove it since it's empty
        removed_count = manager.cleanup_empty_temporary_storage()

        assert removed_count == 1
        # Verify it's gone
        storage = db_session.query(StorageLocation).filter(
            StorageLocation.id == temp_id
        ).first()
        assert storage is None

    def test_cleanup_empty_temporary_storage_keeps_non_empty(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify cleanup_empty_temporary_storage keeps temp storage with items."""
        location = create_location(db_session, game_session, location_key="tavern")
        manager = ItemManager(db_session, game_session)

        # Create temporary storage with an item
        temp_storage = manager.create_temporary_surface(
            surface_key="table_with_bowl",
            world_location_id=location.id,
        )
        create_item(
            db_session, game_session,
            item_key="bowl",
            storage_location_id=temp_storage.id,
        )

        # Cleanup - should NOT remove it since it has items
        removed_count = manager.cleanup_empty_temporary_storage()

        assert removed_count == 0
        # Verify it's still there
        storage = db_session.query(StorageLocation).filter(
            StorageLocation.location_key == "table_with_bowl"
        ).first()
        assert storage is not None

    def test_cleanup_empty_temporary_storage_ignores_permanent(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify cleanup_empty_temporary_storage ignores non-temporary storage."""
        location = create_location(db_session, game_session, location_key="tavern")
        manager = ItemManager(db_session, game_session)

        # Create permanent storage (is_temporary=False)
        permanent = manager.create_storage(
            location_key="permanent_shelf",
            location_type=StorageLocationType.PLACE,
            world_location_id=location.id,
            is_temporary=False,
        )

        # Cleanup
        removed_count = manager.cleanup_empty_temporary_storage()

        assert removed_count == 0
        # Verify permanent storage remains
        storage = db_session.query(StorageLocation).filter(
            StorageLocation.location_key == "permanent_shelf"
        ).first()
        assert storage is not None

    def test_cleanup_empty_temporary_storage_at_location(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify cleanup_empty_temporary_storage can filter by location."""
        tavern = create_location(db_session, game_session, location_key="tavern")
        market = create_location(db_session, game_session, location_key="market")
        manager = ItemManager(db_session, game_session)

        # Create temp storage at both locations
        manager.create_temporary_surface(
            surface_key="tavern_table",
            world_location_id=tavern.id,
        )
        market_table = manager.create_temporary_surface(
            surface_key="market_stall",
            world_location_id=market.id,
        )

        # Cleanup only tavern location
        removed_count = manager.cleanup_empty_temporary_storage(location_id=tavern.id)

        assert removed_count == 1
        # Market stall should remain
        storage = db_session.query(StorageLocation).filter(
            StorageLocation.location_key == "market_stall"
        ).first()
        assert storage is not None

    def test_get_or_create_surface_creates_new(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_or_create_surface creates surface if not exists."""
        location = create_location(db_session, game_session, location_key="tavern")
        manager = ItemManager(db_session, game_session)

        result = manager.get_or_create_surface(
            surface_key="tavern_floor",
            world_location_id=location.id,
            container_type="floor",
        )

        assert result.location_key == "tavern_floor"
        assert result.is_temporary is True

    def test_get_or_create_surface_returns_existing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_or_create_surface returns existing surface."""
        location = create_location(db_session, game_session, location_key="tavern")
        manager = ItemManager(db_session, game_session)

        # Create first
        first = manager.get_or_create_surface(
            surface_key="tavern_floor",
            world_location_id=location.id,
        )
        first_id = first.id

        # Get again
        second = manager.get_or_create_surface(
            surface_key="tavern_floor",
            world_location_id=location.id,
        )

        assert second.id == first_id


class TestItemManagerState:
    """Tests for item state management."""

    def test_update_item_state_sets_state(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify update_item_state sets state in properties."""
        item = create_item(
            db_session, game_session,
            item_key="linen_shirt",
            display_name="Linen Shirt",
            properties={"state": {"cleanliness": "clean"}}
        )
        manager = ItemManager(db_session, game_session)

        result = manager.update_item_state("linen_shirt", "cleanliness", "dirty")

        assert result.properties["state"]["cleanliness"] == "dirty"

    def test_update_item_state_initializes_state_dict(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify update_item_state creates state dict if missing."""
        item = create_item(
            db_session, game_session,
            item_key="old_sword",
            display_name="Iron Sword",
            properties=None
        )
        manager = ItemManager(db_session, game_session)

        result = manager.update_item_state("old_sword", "condition", "rusty")

        assert result.properties is not None
        assert result.properties["state"]["condition"] == "rusty"

    def test_update_item_state_preserves_other_properties(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify update_item_state doesn't overwrite other properties."""
        item = create_item(
            db_session, game_session,
            item_key="fancy_hat",
            display_name="Top Hat",
            properties={
                "visual": {"color": "black"},
                "state": {"cleanliness": "clean"}
            }
        )
        manager = ItemManager(db_session, game_session)

        result = manager.update_item_state("fancy_hat", "cleanliness", "dusty")

        assert result.properties["visual"]["color"] == "black"
        assert result.properties["state"]["cleanliness"] == "dusty"

    def test_update_item_state_adds_new_state_key(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify update_item_state can add new state keys."""
        item = create_item(
            db_session, game_session,
            item_key="bread",
            display_name="Bread",
            properties={"state": {"freshness": "fresh"}}
        )
        manager = ItemManager(db_session, game_session)

        result = manager.update_item_state("bread", "condition", "damaged")

        assert result.properties["state"]["freshness"] == "fresh"
        assert result.properties["state"]["condition"] == "damaged"

    def test_update_item_state_raises_for_nonexistent_item(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify update_item_state raises ValueError for missing item."""
        manager = ItemManager(db_session, game_session)

        with pytest.raises(ValueError, match="Item not found"):
            manager.update_item_state("nonexistent", "cleanliness", "dirty")
