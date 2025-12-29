"""Tests for GM tools stack splitting (quantity parameter on drop/take/give)."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.entities import NPCExtension
from src.database.models.enums import EntityType
from src.database.models.session import GameSession
from src.gm.tools import GMTools
from src.managers.entity_manager import EntityManager
from src.managers.item_manager import ItemManager
from src.managers.location_manager import LocationManager
from tests.factories import create_item, create_entity, create_location


@pytest.fixture
def player(db_session: Session, game_session: GameSession):
    """Create a player entity."""
    entity_manager = EntityManager(db_session, game_session)
    player = entity_manager.create_entity(
        entity_key="player",
        display_name="Test Player",
        entity_type=EntityType.PLAYER,
    )
    ext = NPCExtension(entity_id=player.id, current_location="tavern")
    db_session.add(ext)
    db_session.flush()
    return player


@pytest.fixture
def location(db_session: Session, game_session: GameSession):
    """Create a test location."""
    return create_location(
        db_session, game_session,
        location_key="tavern",
        display_name="The Rusty Anchor Tavern",
    )


@pytest.fixture
def tools(db_session: Session, game_session: GameSession, player, location):
    """Create GMTools instance."""
    return GMTools(
        db_session, game_session, player.id,
        location_key="tavern",
    )


class TestDropItemQuantity:
    """Tests for drop_item with quantity parameter."""

    def test_drop_partial_splits_stack(
        self, db_session: Session, game_session: GameSession, player, location, tools
    ):
        """drop_item(gold, quantity=1) leaves 9 gold with player."""
        # Create stackable gold held by player
        gold = create_item(
            db_session, game_session,
            item_key="gold_coins",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=10,
            holder_id=player.id,
        )

        result = tools.drop_item("gold_coins", quantity=1)

        assert result.get("success") is True
        assert "1" in str(result.get("quantity", "")) or result.get("quantity") == 1

        # Verify original stack still with player with reduced quantity
        item_manager = ItemManager(db_session, game_session)
        original = item_manager.get_item("gold_coins")
        assert original is not None
        assert original.quantity == 9
        assert original.holder_id == player.id

    def test_drop_full_quantity_transfers_all(
        self, db_session: Session, game_session: GameSession, player, location, tools
    ):
        """drop_item(gold, quantity=10) drops entire stack."""
        gold = create_item(
            db_session, game_session,
            item_key="gold_coins",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=10,
            holder_id=player.id,
        )

        result = tools.drop_item("gold_coins", quantity=10)

        assert result.get("success") is True

        # Verify item is dropped (no holder)
        item_manager = ItemManager(db_session, game_session)
        dropped = item_manager.get_item("gold_coins")
        assert dropped is not None
        assert dropped.holder_id is None
        assert dropped.quantity == 10

    def test_drop_none_transfers_all(
        self, db_session: Session, game_session: GameSession, player, location, tools
    ):
        """drop_item(gold) without quantity drops all."""
        gold = create_item(
            db_session, game_session,
            item_key="gold_coins",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=10,
            holder_id=player.id,
        )

        result = tools.drop_item("gold_coins")  # No quantity param

        assert result.get("success") is True

        # Verify entire stack is dropped
        item_manager = ItemManager(db_session, game_session)
        dropped = item_manager.get_item("gold_coins")
        assert dropped is not None
        assert dropped.holder_id is None
        assert dropped.quantity == 10

    def test_drop_quantity_exceeds_returns_error(
        self, db_session: Session, game_session: GameSession, player, location, tools
    ):
        """drop_item(gold, quantity=100) returns error when only 10 exist."""
        gold = create_item(
            db_session, game_session,
            item_key="gold_coins",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=10,
            holder_id=player.id,
        )

        result = tools.drop_item("gold_coins", quantity=100)

        assert "error" in result
        assert "exceeds" in result["error"].lower() or "only" in result["error"].lower()

    def test_drop_non_stackable_with_quantity_returns_error(
        self, db_session: Session, game_session: GameSession, player, location, tools
    ):
        """drop_item(sword, quantity=1) returns error for non-stackable."""
        sword = create_item(
            db_session, game_session,
            item_key="sword",
            display_name="Longsword",
            is_stackable=False,
            quantity=1,
            holder_id=player.id,
        )

        result = tools.drop_item("sword", quantity=1)

        assert "error" in result
        assert "stackable" in result["error"].lower()


class TestTakeItemQuantity:
    """Tests for take_item with quantity parameter."""

    def test_take_partial_with_auto_merge(
        self, db_session: Session, game_session: GameSession, player, location, tools
    ):
        """Taking 5 gold when player already has 10 results in 15."""
        item_manager = ItemManager(db_session, game_session)

        # Player already has 10 gold
        player_gold = create_item(
            db_session, game_session,
            item_key="player_gold",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=10,
            holder_id=player.id,
        )

        # Create a storage location for the tavern
        loc_manager = LocationManager(db_session, game_session)
        storage = item_manager.create_storage(
            location_key="tavern",
            location_type=StorageLocationType.PLACE,
        )

        # Gold on the ground (20 total)
        ground_gold = create_item(
            db_session, game_session,
            item_key="ground_gold",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=20,
            storage_location_id=storage.id,
        )

        result = tools.take_item("ground_gold", quantity=5)

        assert result.get("success") is True

        # Player's existing stack should now have 15 (merged)
        player_stack = item_manager.get_item("player_gold")
        assert player_stack.quantity == 15

        # Ground stack should have 15 left
        ground_stack = item_manager.get_item("ground_gold")
        assert ground_stack.quantity == 15

    def test_take_creates_new_stack_when_no_existing(
        self, db_session: Session, game_session: GameSession, player, location, tools
    ):
        """Taking 5 gold when player has none creates new stack."""
        item_manager = ItemManager(db_session, game_session)

        # Create a storage location for the tavern
        storage = item_manager.create_storage(
            location_key="tavern",
            location_type=StorageLocationType.PLACE,
        )

        # Gold on the ground
        ground_gold = create_item(
            db_session, game_session,
            item_key="ground_gold",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=20,
            storage_location_id=storage.id,
        )

        result = tools.take_item("ground_gold", quantity=5)

        assert result.get("success") is True

        # A split item should be created and held by player
        # The ground_gold should now have 15
        ground_stack = item_manager.get_item("ground_gold")
        assert ground_stack.quantity == 15

        # Find the new stack held by player
        player_items = item_manager.get_inventory(player.id)
        gold_items = [i for i in player_items if "Gold" in i.display_name]
        assert len(gold_items) == 1
        assert gold_items[0].quantity == 5


class TestGiveItemQuantity:
    """Tests for give_item with quantity parameter."""

    def test_give_partial_to_npc(
        self, db_session: Session, game_session: GameSession, player, location, tools
    ):
        """give_item(gold, npc, quantity=10) gives only 10."""
        entity_manager = EntityManager(db_session, game_session)

        # Create NPC
        merchant = entity_manager.create_entity(
            entity_key="merchant",
            display_name="Merchant Anna",
            entity_type=EntityType.NPC,
        )
        db_session.flush()

        # Player has 50 gold
        gold = create_item(
            db_session, game_session,
            item_key="player_gold",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=50,
            holder_id=player.id,
        )

        result = tools.give_item("player_gold", "merchant", quantity=10)

        assert result.get("success") is True

        item_manager = ItemManager(db_session, game_session)

        # Player should have 40 left
        player_stack = item_manager.get_item("player_gold")
        assert player_stack.quantity == 40

        # Merchant should have 10 (as a new split item)
        merchant_items = item_manager.get_inventory(merchant.id)
        assert len(merchant_items) == 1
        assert merchant_items[0].quantity == 10

    def test_give_auto_merges_with_npc_inventory(
        self, db_session: Session, game_session: GameSession, player, location, tools
    ):
        """NPC receives gold that merges with their existing gold."""
        entity_manager = EntityManager(db_session, game_session)
        item_manager = ItemManager(db_session, game_session)

        # Create NPC
        merchant = entity_manager.create_entity(
            entity_key="merchant",
            display_name="Merchant Anna",
            entity_type=EntityType.NPC,
        )
        db_session.flush()

        # Merchant already has 30 gold
        merchant_gold = create_item(
            db_session, game_session,
            item_key="merchant_gold",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=30,
            holder_id=merchant.id,
        )

        # Player has 50 gold
        player_gold = create_item(
            db_session, game_session,
            item_key="player_gold",
            display_name="Gold Coins",
            is_stackable=True,
            quantity=50,
            holder_id=player.id,
        )

        result = tools.give_item("player_gold", "merchant", quantity=10)

        assert result.get("success") is True

        # Player should have 40 left
        player_stack = item_manager.get_item("player_gold")
        assert player_stack.quantity == 40

        # Merchant's existing stack should have merged to 40
        merchant_stack = item_manager.get_item("merchant_gold")
        assert merchant_stack.quantity == 40


# Import needed for storage location type
from src.database.models.enums import StorageLocationType
