"""Tests for GMToolExecutor._execute_drop_item - ensuring items are not orphaned."""

import pytest
from sqlalchemy.orm import Session

from src.agents.tools.executor import GMToolExecutor
from src.database.models.enums import EntityType, StorageLocationType
from src.database.models.items import StorageLocation
from src.database.models.session import GameSession
from tests.factories import create_entity, create_item, create_location


class TestExecutorDropItem:
    """Tests for GMToolExecutor._execute_drop_item."""

    def test_drop_item_creates_storage_location(
        self, db_session: Session, game_session: GameSession
    ):
        """Dropping an item should create a storage location record."""
        # Setup - create location, player, and item
        location = create_location(
            db_session, game_session, location_key="tavern", display_name="The Tavern"
        )
        player = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.PLAYER,
            entity_key="player",
            display_name="Hero",
        )
        item = create_item(
            db_session,
            game_session,
            item_key="test_sword",
            display_name="Test Sword",
            holder_id=player.id,
        )
        db_session.flush()

        # Execute drop
        executor = GMToolExecutor(
            db=db_session,
            game_session=game_session,
            current_zone_key="tavern",
        )

        result = executor._execute_drop_item({
            "entity_key": "player",
            "item_key": "test_sword",
        })

        # Verify success
        assert result["success"] is True
        assert result["dropped"] is True
        assert result["location"] == "tavern"

        # Check storage location was created
        db_session.refresh(item)
        assert item.holder_id is None, "Item should no longer have a holder"
        assert item.storage_location_id is not None, "Item should have storage location"

        # Verify the storage location details via the item's relationship
        storage = (
            db_session.query(StorageLocation)
            .filter(StorageLocation.id == item.storage_location_id)
            .first()
        )
        assert storage is not None
        assert storage.location_type == StorageLocationType.PLACE
        assert storage.location_key == "tavern"

    def test_drop_item_fails_without_location(
        self, db_session: Session, game_session: GameSession
    ):
        """Dropping an item without current location should fail gracefully."""
        player = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.PLAYER,
            entity_key="player",
            display_name="Hero",
        )
        item = create_item(
            db_session,
            game_session,
            item_key="test_sword",
            display_name="Test Sword",
            holder_id=player.id,
        )
        db_session.flush()

        # Execute drop WITHOUT location
        executor = GMToolExecutor(
            db=db_session,
            game_session=game_session,
            current_zone_key=None,  # No location!
        )

        result = executor._execute_drop_item({
            "entity_key": "player",
            "item_key": "test_sword",
        })

        # Should fail gracefully
        assert result["success"] is False
        assert "location" in result["error"].lower()

        # Item should still be held
        db_session.refresh(item)
        assert item.holder_id == player.id, "Item should still be held by player"

    def test_drop_item_does_not_orphan_items(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify dropped items are never orphaned (no holder, no storage)."""
        location = create_location(
            db_session, game_session, location_key="market", display_name="Market Square"
        )
        player = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.PLAYER,
            entity_key="player",
            display_name="Hero",
        )
        item = create_item(
            db_session,
            game_session,
            item_key="gold_coin",
            display_name="Gold Coin",
            holder_id=player.id,
        )
        db_session.flush()

        executor = GMToolExecutor(
            db=db_session,
            game_session=game_session,
            current_zone_key="market",
        )

        result = executor._execute_drop_item({
            "entity_key": "player",
            "item_key": "gold_coin",
        })

        assert result["success"] is True

        # Verify item is NOT orphaned
        db_session.refresh(item)
        has_location = (
            item.owner_id is not None
            or item.holder_id is not None
            or item.storage_location_id is not None
            or item.owner_location_id is not None
        )
        assert has_location, "Item was orphaned after drop!"

    def test_drop_item_transfer_to_entity_works(
        self, db_session: Session, game_session: GameSession
    ):
        """Transferring an item to another entity should work correctly."""
        player = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.PLAYER,
            entity_key="player",
            display_name="Hero",
        )
        npc = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.NPC,
            entity_key="merchant",
            display_name="Merchant",
        )
        item = create_item(
            db_session,
            game_session,
            item_key="apple",
            display_name="Apple",
            holder_id=player.id,
        )
        db_session.flush()

        executor = GMToolExecutor(
            db=db_session,
            game_session=game_session,
            current_zone_key="market",
        )

        result = executor._execute_drop_item({
            "entity_key": "player",
            "item_key": "apple",
            "transfer_to": "merchant",
        })

        assert result["success"] is True
        assert result["to_entity"] == "merchant"

        # Item should now be held by merchant
        db_session.refresh(item)
        assert item.holder_id == npc.id
