"""Tests for TurnManager class."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.session import GameSession
from src.managers.turn_manager import TurnManager
from tests.factories import create_turn


class TestTurnManager:
    """Tests for TurnManager class."""

    def test_init_creates_manager(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify TurnManager can be initialized."""
        manager = TurnManager(db_session, game_session)

        assert manager.db is db_session
        assert manager.game_session is game_session

    def test_get_recent_turns_empty(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_recent_turns returns empty list when no turns."""
        manager = TurnManager(db_session, game_session)

        result = manager.get_recent_turns()

        assert result == []

    def test_get_recent_turns_returns_turns(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_recent_turns returns turns in order."""
        turn1 = create_turn(
            db_session, game_session,
            turn_number=1,
            player_input="First action",
        )
        turn2 = create_turn(
            db_session, game_session,
            turn_number=2,
            player_input="Second action",
        )
        turn3 = create_turn(
            db_session, game_session,
            turn_number=3,
            player_input="Third action",
        )
        db_session.flush()

        manager = TurnManager(db_session, game_session)
        result = manager.get_recent_turns()

        # Should be newest first
        assert len(result) == 3
        assert result[0].turn_number == 3
        assert result[1].turn_number == 2
        assert result[2].turn_number == 1

    def test_get_recent_turns_respects_limit(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_recent_turns respects count limit."""
        for i in range(5):
            create_turn(db_session, game_session, turn_number=i + 1)
        db_session.flush()

        manager = TurnManager(db_session, game_session)
        result = manager.get_recent_turns(count=2)

        assert len(result) == 2
        assert result[0].turn_number == 5
        assert result[1].turn_number == 4


class TestGetMentionedItemsAtLocation:
    """Tests for get_mentioned_items_at_location method."""

    def test_returns_empty_when_no_turns(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify returns empty list when no turns exist."""
        manager = TurnManager(db_session, game_session)

        result = manager.get_mentioned_items_at_location("tavern")

        assert result == []

    def test_returns_empty_when_no_mentioned_items(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify returns empty list when turns have no mentioned_items."""
        create_turn(
            db_session, game_session,
            turn_number=1,
            location_at_turn="tavern",
            mentioned_items=None,
        )
        db_session.flush()

        manager = TurnManager(db_session, game_session)
        result = manager.get_mentioned_items_at_location("tavern")

        assert result == []

    def test_returns_items_at_matching_location(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify returns items matching the location."""
        create_turn(
            db_session, game_session,
            turn_number=1,
            location_at_turn="tavern",
            mentioned_items=[
                {"name": "dusty bottle", "context": "on shelf", "location": "tavern"},
                {"name": "cobwebs", "context": "in corner", "location": "tavern"},
            ],
        )
        db_session.flush()

        manager = TurnManager(db_session, game_session)
        result = manager.get_mentioned_items_at_location("tavern")

        assert len(result) == 2
        names = [item["name"] for item in result]
        assert "dusty bottle" in names
        assert "cobwebs" in names

    def test_filters_by_location(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify only returns items at specified location."""
        create_turn(
            db_session, game_session,
            turn_number=1,
            mentioned_items=[
                {"name": "dusty bottle", "context": "on shelf", "location": "tavern"},
                {"name": "pebbles", "context": "on path", "location": "village_road"},
                {"name": "cobwebs", "context": "in corner", "location": "tavern"},
            ],
        )
        db_session.flush()

        manager = TurnManager(db_session, game_session)
        result = manager.get_mentioned_items_at_location("tavern")

        assert len(result) == 2
        names = [item["name"] for item in result]
        assert "dusty bottle" in names
        assert "cobwebs" in names
        assert "pebbles" not in names

    def test_aggregates_from_multiple_turns(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify aggregates items from multiple recent turns."""
        create_turn(
            db_session, game_session,
            turn_number=1,
            mentioned_items=[
                {"name": "dusty bottle", "context": "on shelf", "location": "tavern"},
            ],
        )
        create_turn(
            db_session, game_session,
            turn_number=2,
            mentioned_items=[
                {"name": "cobwebs", "context": "in corner", "location": "tavern"},
            ],
        )
        db_session.flush()

        manager = TurnManager(db_session, game_session)
        result = manager.get_mentioned_items_at_location("tavern")

        assert len(result) == 2
        names = [item["name"] for item in result]
        assert "dusty bottle" in names
        assert "cobwebs" in names

    def test_includes_turn_number_in_result(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify result includes turn_number for tracking."""
        create_turn(
            db_session, game_session,
            turn_number=5,
            mentioned_items=[
                {"name": "dusty bottle", "context": "on shelf", "location": "tavern"},
            ],
        )
        db_session.flush()

        manager = TurnManager(db_session, game_session)
        result = manager.get_mentioned_items_at_location("tavern")

        assert len(result) == 1
        assert result[0]["turn_number"] == 5

    def test_respects_lookback_limit(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify only looks back specified number of turns."""
        for i in range(5):
            create_turn(
                db_session, game_session,
                turn_number=i + 1,
                mentioned_items=[
                    {"name": f"item_{i}", "context": "", "location": "tavern"},
                ],
            )
        db_session.flush()

        manager = TurnManager(db_session, game_session)
        result = manager.get_mentioned_items_at_location("tavern", lookback_turns=2)

        # Should only get items from turns 4 and 5 (most recent 2)
        assert len(result) == 2
        names = [item["name"] for item in result]
        assert "item_4" in names
        assert "item_3" in names
        assert "item_0" not in names


class TestGetTurnByNumber:
    """Tests for get_turn_by_number method."""

    def test_returns_none_when_not_found(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify returns None when turn doesn't exist."""
        manager = TurnManager(db_session, game_session)

        result = manager.get_turn_by_number(999)

        assert result is None

    def test_returns_turn_when_found(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify returns turn when it exists."""
        turn = create_turn(
            db_session, game_session,
            turn_number=5,
            player_input="Look around",
        )
        db_session.flush()

        manager = TurnManager(db_session, game_session)
        result = manager.get_turn_by_number(5)

        assert result is not None
        assert result.id == turn.id
        assert result.player_input == "Look around"


class TestGetLatestTurn:
    """Tests for get_latest_turn method."""

    def test_returns_none_when_no_turns(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify returns None when no turns exist."""
        manager = TurnManager(db_session, game_session)

        result = manager.get_latest_turn()

        assert result is None

    def test_returns_most_recent_turn(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify returns the most recent turn."""
        create_turn(db_session, game_session, turn_number=1)
        create_turn(db_session, game_session, turn_number=2)
        latest = create_turn(
            db_session, game_session,
            turn_number=3,
            player_input="Latest action",
        )
        db_session.flush()

        manager = TurnManager(db_session, game_session)
        result = manager.get_latest_turn()

        assert result is not None
        assert result.id == latest.id
        assert result.turn_number == 3


class TestSaveMentionedItems:
    """Tests for save_mentioned_items method."""

    def test_returns_false_when_turn_not_found(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify returns False when turn doesn't exist."""
        manager = TurnManager(db_session, game_session)

        result = manager.save_mentioned_items(999, [{"name": "item"}])

        assert result is False

    def test_saves_items_to_turn(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify saves items to turn."""
        turn = create_turn(
            db_session, game_session,
            turn_number=1,
            mentioned_items=None,
        )
        db_session.flush()

        items = [
            {"name": "dusty bottle", "context": "on shelf", "location": "tavern"},
        ]

        manager = TurnManager(db_session, game_session)
        result = manager.save_mentioned_items(1, items)

        assert result is True
        db_session.refresh(turn)
        assert len(turn.mentioned_items) == 1
        assert turn.mentioned_items[0]["name"] == "dusty bottle"

    def test_merges_with_existing_items(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify merges with existing mentioned_items."""
        turn = create_turn(
            db_session, game_session,
            turn_number=1,
            mentioned_items=[
                {"name": "existing", "context": "", "location": "tavern"},
            ],
        )
        db_session.flush()

        new_items = [
            {"name": "new_item", "context": "", "location": "tavern"},
        ]

        manager = TurnManager(db_session, game_session)
        result = manager.save_mentioned_items(1, new_items)

        assert result is True
        db_session.refresh(turn)
        assert len(turn.mentioned_items) == 2
        names = [item["name"] for item in turn.mentioned_items]
        assert "existing" in names
        assert "new_item" in names
