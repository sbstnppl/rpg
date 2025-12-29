"""Tests for ItemManager stack operations (split, merge, quantity transfer)."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.enums import ItemType
from src.database.models.items import Item
from src.database.models.session import GameSession
from src.managers.item_manager import ItemManager
from tests.factories import create_item, create_entity


class TestSplitStack:
    """Tests for split_stack method."""

    def test_split_creates_new_item_with_quantity(
        self, db_session: Session, game_session: GameSession
    ):
        """Splitting 50 gold into 10 creates new item with quantity=10."""
        gold = create_item(
            db_session, game_session,
            item_key="gold_coins",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=50,
        )
        manager = ItemManager(db_session, game_session)

        split_item = manager.split_stack("gold_coins", quantity=10)

        assert split_item is not None
        assert split_item.quantity == 10
        assert split_item.display_name == "Gold Coins"

    def test_split_reduces_original_quantity(
        self, db_session: Session, game_session: GameSession
    ):
        """Original item quantity reduced from 50 to 40 after split of 10."""
        gold = create_item(
            db_session, game_session,
            item_key="gold_coins",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=50,
        )
        manager = ItemManager(db_session, game_session)

        manager.split_stack("gold_coins", quantity=10)

        # Refresh original item
        original = manager.get_item("gold_coins")
        assert original.quantity == 40

    def test_split_preserves_item_properties(
        self, db_session: Session, game_session: GameSession
    ):
        """New split item has same display_name, item_type, weight, properties."""
        entity = create_entity(db_session, game_session)
        gold = create_item(
            db_session, game_session,
            item_key="gold_coins",
            display_name="Gold Coins",
            item_type=ItemType.CONSUMABLE,
            is_stackable=True,
            quantity=50,
            weight=0.01,
            owner_id=entity.id,
            holder_id=entity.id,
            properties={"origin": "dragon_hoard"},
        )
        manager = ItemManager(db_session, game_session)

        split_item = manager.split_stack("gold_coins", quantity=10)

        assert split_item.display_name == "Gold Coins"
        assert split_item.item_type == ItemType.CONSUMABLE
        assert split_item.weight == 0.01
        assert split_item.is_stackable is True
        assert split_item.owner_id == entity.id
        assert split_item.holder_id == entity.id
        assert split_item.properties == {"origin": "dragon_hoard"}

    def test_split_generates_unique_key(
        self, db_session: Session, game_session: GameSession
    ):
        """New item key contains original key + _split_ suffix."""
        gold = create_item(
            db_session, game_session,
            item_key="gold_coins",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=50,
        )
        manager = ItemManager(db_session, game_session)

        split_item = manager.split_stack("gold_coins", quantity=10)

        assert split_item.item_key.startswith("gold_coins_split_")
        assert split_item.item_key != "gold_coins"

    def test_split_raises_for_non_stackable(
        self, db_session: Session, game_session: GameSession
    ):
        """ValueError when splitting non-stackable item."""
        sword = create_item(
            db_session, game_session,
            item_key="sword",
            display_name="Longsword",
            is_stackable=False,
            quantity=1,
        )
        manager = ItemManager(db_session, game_session)

        with pytest.raises(ValueError, match="not stackable"):
            manager.split_stack("sword", quantity=1)

    def test_split_raises_for_zero_quantity(
        self, db_session: Session, game_session: GameSession
    ):
        """ValueError when quantity=0."""
        gold = create_item(
            db_session, game_session,
            item_key="gold_coins",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=50,
        )
        manager = ItemManager(db_session, game_session)

        with pytest.raises(ValueError, match="must be greater than 0"):
            manager.split_stack("gold_coins", quantity=0)

    def test_split_raises_for_negative_quantity(
        self, db_session: Session, game_session: GameSession
    ):
        """ValueError when quantity is negative."""
        gold = create_item(
            db_session, game_session,
            item_key="gold_coins",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=50,
        )
        manager = ItemManager(db_session, game_session)

        with pytest.raises(ValueError, match="must be greater than 0"):
            manager.split_stack("gold_coins", quantity=-5)

    def test_split_raises_for_quantity_exceeds_total(
        self, db_session: Session, game_session: GameSession
    ):
        """ValueError when quantity > item.quantity."""
        gold = create_item(
            db_session, game_session,
            item_key="gold_coins",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=50,
        )
        manager = ItemManager(db_session, game_session)

        with pytest.raises(ValueError, match="exceeds available"):
            manager.split_stack("gold_coins", quantity=100)

    def test_split_raises_for_quantity_equals_total(
        self, db_session: Session, game_session: GameSession
    ):
        """ValueError when quantity == item.quantity (use transfer instead)."""
        gold = create_item(
            db_session, game_session,
            item_key="gold_coins",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=50,
        )
        manager = ItemManager(db_session, game_session)

        with pytest.raises(ValueError, match="equals total"):
            manager.split_stack("gold_coins", quantity=50)

    def test_split_raises_for_nonexistent_item(
        self, db_session: Session, game_session: GameSession
    ):
        """ValueError for unknown item_key."""
        manager = ItemManager(db_session, game_session)

        with pytest.raises(ValueError, match="not found"):
            manager.split_stack("nonexistent", quantity=10)


class TestMergeStacks:
    """Tests for merge_stacks method."""

    def test_merge_combines_quantities(
        self, db_session: Session, game_session: GameSession
    ):
        """Merging 30 + 20 gold results in single stack of 50."""
        entity = create_entity(db_session, game_session)
        gold1 = create_item(
            db_session, game_session,
            item_key="gold_1",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=30,
            holder_id=entity.id,
        )
        gold2 = create_item(
            db_session, game_session,
            item_key="gold_2",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=20,
            holder_id=entity.id,
        )
        manager = ItemManager(db_session, game_session)

        result = manager.merge_stacks("gold_1", "gold_2")

        assert result.quantity == 50
        assert result.item_key == "gold_1"

    def test_merge_deletes_source_item(
        self, db_session: Session, game_session: GameSession
    ):
        """Source item is deleted after merge."""
        entity = create_entity(db_session, game_session)
        gold1 = create_item(
            db_session, game_session,
            item_key="gold_1",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=30,
            holder_id=entity.id,
        )
        gold2 = create_item(
            db_session, game_session,
            item_key="gold_2",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=20,
            holder_id=entity.id,
        )
        manager = ItemManager(db_session, game_session)

        manager.merge_stacks("gold_1", "gold_2")

        # Source should be deleted
        assert manager.get_item("gold_2") is None

    def test_merge_raises_for_different_types(
        self, db_session: Session, game_session: GameSession
    ):
        """ValueError when merging different display_names."""
        entity = create_entity(db_session, game_session)
        gold = create_item(
            db_session, game_session,
            item_key="gold",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=30,
            holder_id=entity.id,
        )
        silver = create_item(
            db_session, game_session,
            item_key="silver",
            display_name="Silver Coins",
            is_stackable=True,
            quantity=20,
            holder_id=entity.id,
        )
        manager = ItemManager(db_session, game_session)

        with pytest.raises(ValueError, match="same type"):
            manager.merge_stacks("gold", "silver")

    def test_merge_raises_for_non_stackable_target(
        self, db_session: Session, game_session: GameSession
    ):
        """ValueError when target item is not stackable."""
        entity = create_entity(db_session, game_session)
        sword = create_item(
            db_session, game_session,
            item_key="sword",
            display_name="Longsword",
            is_stackable=False,
            quantity=1,
            holder_id=entity.id,
        )
        sword2 = create_item(
            db_session, game_session,
            item_key="sword2",
            display_name="Longsword",
            is_stackable=True,  # Even if source is stackable
            quantity=1,
            holder_id=entity.id,
        )
        manager = ItemManager(db_session, game_session)

        with pytest.raises(ValueError, match="not stackable"):
            manager.merge_stacks("sword", "sword2")

    def test_merge_raises_for_non_stackable_source(
        self, db_session: Session, game_session: GameSession
    ):
        """ValueError when source item is not stackable."""
        entity = create_entity(db_session, game_session)
        gold = create_item(
            db_session, game_session,
            item_key="gold",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=30,
            holder_id=entity.id,
        )
        fake_gold = create_item(
            db_session, game_session,
            item_key="fake_gold",
            display_name="Gold Coins",
            is_stackable=False,  # Not stackable
            quantity=1,
            holder_id=entity.id,
        )
        manager = ItemManager(db_session, game_session)

        with pytest.raises(ValueError, match="not stackable"):
            manager.merge_stacks("gold", "fake_gold")


class TestFindMergeableStack:
    """Tests for find_mergeable_stack method."""

    def test_finds_matching_stack(
        self, db_session: Session, game_session: GameSession
    ):
        """Returns existing stack with same display_name."""
        entity = create_entity(db_session, game_session)
        gold = create_item(
            db_session, game_session,
            item_key="existing_gold",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=50,
            holder_id=entity.id,
        )
        manager = ItemManager(db_session, game_session)

        result = manager.find_mergeable_stack(entity.id, "Gold Coins")

        assert result is not None
        assert result.item_key == "existing_gold"

    def test_returns_none_when_no_match(
        self, db_session: Session, game_session: GameSession
    ):
        """Returns None when no matching stack exists."""
        entity = create_entity(db_session, game_session)
        manager = ItemManager(db_session, game_session)

        result = manager.find_mergeable_stack(entity.id, "Gold Coins")

        assert result is None

    def test_ignores_non_stackable_items(
        self, db_session: Session, game_session: GameSession
    ):
        """Returns None when only non-stackable items match name."""
        entity = create_entity(db_session, game_session)
        fake_gold = create_item(
            db_session, game_session,
            item_key="fake_gold",
            display_name="Gold Coins",
            is_stackable=False,  # Not stackable!
            quantity=1,
            holder_id=entity.id,
        )
        manager = ItemManager(db_session, game_session)

        result = manager.find_mergeable_stack(entity.id, "Gold Coins")

        assert result is None

    def test_ignores_other_holders(
        self, db_session: Session, game_session: GameSession
    ):
        """Returns None when matching stack is held by different entity."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        gold = create_item(
            db_session, game_session,
            item_key="gold",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=50,
            holder_id=entity2.id,  # Different holder!
        )
        manager = ItemManager(db_session, game_session)

        result = manager.find_mergeable_stack(entity1.id, "Gold Coins")

        assert result is None


class TestTransferQuantity:
    """Tests for transfer_quantity method."""

    def test_none_quantity_transfers_all(
        self, db_session: Session, game_session: GameSession
    ):
        """quantity=None transfers entire item."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        gold = create_item(
            db_session, game_session,
            item_key="gold",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=50,
            holder_id=entity1.id,
        )
        manager = ItemManager(db_session, game_session)

        result = manager.transfer_quantity("gold", quantity=None, to_entity_id=entity2.id)

        assert result.holder_id == entity2.id
        assert result.quantity == 50
        assert result.item_key == "gold"  # Same item, just moved

    def test_partial_quantity_splits_and_transfers(
        self, db_session: Session, game_session: GameSession
    ):
        """quantity=10 of 50 splits and transfers only 10."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        gold = create_item(
            db_session, game_session,
            item_key="gold",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=50,
            holder_id=entity1.id,
        )
        manager = ItemManager(db_session, game_session)

        result = manager.transfer_quantity("gold", quantity=10, to_entity_id=entity2.id)

        # Transferred item should have 10
        assert result.holder_id == entity2.id
        assert result.quantity == 10

        # Original should still have 40
        original = manager.get_item("gold")
        assert original.holder_id == entity1.id
        assert original.quantity == 40

    def test_auto_merges_at_destination(
        self, db_session: Session, game_session: GameSession
    ):
        """Transferred stack merges with existing stack at destination."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)

        # Entity1 has 50 gold
        gold1 = create_item(
            db_session, game_session,
            item_key="gold_1",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=50,
            holder_id=entity1.id,
        )
        # Entity2 already has 30 gold
        gold2 = create_item(
            db_session, game_session,
            item_key="gold_2",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=30,
            holder_id=entity2.id,
        )
        manager = ItemManager(db_session, game_session)

        # Transfer 10 gold from entity1 to entity2
        result = manager.transfer_quantity("gold_1", quantity=10, to_entity_id=entity2.id)

        # Should merge into entity2's existing stack
        assert result.item_key == "gold_2"
        assert result.quantity == 40  # 30 + 10

        # Entity1's original should have 40
        original = manager.get_item("gold_1")
        assert original.quantity == 40

    def test_full_quantity_transfers_whole_item(
        self, db_session: Session, game_session: GameSession
    ):
        """When quantity equals total, transfer whole item without split."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        gold = create_item(
            db_session, game_session,
            item_key="gold",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=50,
            holder_id=entity1.id,
        )
        manager = ItemManager(db_session, game_session)

        result = manager.transfer_quantity("gold", quantity=50, to_entity_id=entity2.id)

        # Same item, just moved
        assert result.item_key == "gold"
        assert result.holder_id == entity2.id
        assert result.quantity == 50
