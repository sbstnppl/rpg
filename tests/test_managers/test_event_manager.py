"""Tests for EventManager class."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.session import GameSession
from src.database.models.world import WorldEvent
from src.managers.event_manager import EventManager
from src.managers.time_manager import TimeManager
from tests.factories import create_world_event, create_time_state


class TestEventManagerBasics:
    """Tests for EventManager basic operations."""

    def test_create_event_basic(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify create_event creates new event."""
        manager = EventManager(db_session, game_session)

        result = manager.create_event(
            event_type="robbery",
            summary="The jewelry store was robbed.",
        )

        assert result is not None
        assert result.event_type == "robbery"
        assert result.summary == "The jewelry store was robbed."
        assert result.session_id == game_session.id
        assert result.is_processed is False

    def test_create_event_with_details(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify create_event can include details JSON."""
        manager = EventManager(db_session, game_session)

        result = manager.create_event(
            event_type="discovery",
            summary="Ancient artifact found.",
            details={"artifact": "Golden Chalice", "value": 1000},
        )

        assert result.details == {"artifact": "Golden Chalice", "value": 1000}

    def test_create_event_uses_current_turn(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify create_event sets turn_created from game session."""
        game_session.total_turns = 5
        manager = EventManager(db_session, game_session)

        result = manager.create_event(
            event_type="weather",
            summary="A storm has arrived.",
        )

        assert result.turn_created == 5

    def test_create_event_with_location_and_entities(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify create_event can set location and affected entities."""
        manager = EventManager(db_session, game_session)

        result = manager.create_event(
            event_type="fight",
            summary="A brawl broke out in the tavern.",
            location_key="tavern",
            affected_entities=["npc_bartender", "npc_drunk"],
        )

        assert result.location_key == "tavern"
        assert result.affected_entities == ["npc_bartender", "npc_drunk"]

    def test_get_event(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_event returns event by ID."""
        event = create_world_event(db_session, game_session)
        manager = EventManager(db_session, game_session)

        result = manager.get_event(event.id)

        assert result is not None
        assert result.id == event.id


class TestEventManagerQueries:
    """Tests for event query operations."""

    def test_get_unprocessed_events(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_unprocessed_events returns only unprocessed."""
        create_world_event(
            db_session, game_session,
            event_type="event1",
            is_processed=False
        )
        create_world_event(
            db_session, game_session,
            event_type="event2",
            is_processed=False
        )
        create_world_event(
            db_session, game_session,
            event_type="event3",
            is_processed=True
        )
        manager = EventManager(db_session, game_session)

        result = manager.get_unprocessed_events()

        assert len(result) == 2
        assert all(not e.is_processed for e in result)

    def test_mark_processed(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify mark_processed sets is_processed to True."""
        event = create_world_event(
            db_session, game_session,
            is_processed=False
        )
        manager = EventManager(db_session, game_session)

        result = manager.mark_processed(event.id)

        assert result.is_processed is True

    def test_get_events_at_location(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_events_at_location returns events at location."""
        create_world_event(
            db_session, game_session,
            event_type="event1",
            location_key="tavern"
        )
        create_world_event(
            db_session, game_session,
            event_type="event2",
            location_key="tavern"
        )
        create_world_event(
            db_session, game_session,
            event_type="event3",
            location_key="market"
        )
        manager = EventManager(db_session, game_session)

        result = manager.get_events_at_location("tavern")

        assert len(result) == 2
        assert all(e.location_key == "tavern" for e in result)

    def test_get_events_by_type(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_events_by_type returns events of type."""
        create_world_event(
            db_session, game_session,
            event_type="robbery"
        )
        create_world_event(
            db_session, game_session,
            event_type="robbery"
        )
        create_world_event(
            db_session, game_session,
            event_type="weather"
        )
        manager = EventManager(db_session, game_session)

        result = manager.get_events_by_type("robbery")

        assert len(result) == 2
        assert all(e.event_type == "robbery" for e in result)

    def test_get_recent_events_known_only(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_recent_events only returns known events by default."""
        create_world_event(
            db_session, game_session,
            event_type="known",
            is_known_to_player=True,
            turn_created=1
        )
        create_world_event(
            db_session, game_session,
            event_type="hidden",
            is_known_to_player=False,
            turn_created=2
        )
        manager = EventManager(db_session, game_session)

        result = manager.get_recent_events(limit=10, known_only=True)

        assert len(result) == 1
        assert result[0].event_type == "known"

    def test_get_recent_events_includes_unknown(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_recent_events includes all when known_only=False."""
        create_world_event(
            db_session, game_session,
            is_known_to_player=True
        )
        create_world_event(
            db_session, game_session,
            is_known_to_player=False
        )
        manager = EventManager(db_session, game_session)

        result = manager.get_recent_events(limit=10, known_only=False)

        assert len(result) == 2


class TestEventManagerReveal:
    """Tests for revealing events."""

    def test_reveal_event(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify reveal_event sets is_known_to_player to True."""
        event = create_world_event(
            db_session, game_session,
            is_known_to_player=False
        )
        manager = EventManager(db_session, game_session)

        result = manager.reveal_event(event.id)

        assert result.is_known_to_player is True

    def test_reveal_event_sets_discovery_turn(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify reveal_event sets discovery_turn."""
        game_session.total_turns = 10
        event = create_world_event(
            db_session, game_session,
            is_known_to_player=False
        )
        manager = EventManager(db_session, game_session)

        result = manager.reveal_event(event.id)

        assert result.discovery_turn == 10


class TestEventManagerAffected:
    """Tests for affected entity queries."""

    def test_get_events_affecting_entity(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_events_affecting_entity returns relevant events."""
        create_world_event(
            db_session, game_session,
            event_type="event1",
            affected_entities=["hero", "villain"]
        )
        create_world_event(
            db_session, game_session,
            event_type="event2",
            affected_entities=["hero"]
        )
        create_world_event(
            db_session, game_session,
            event_type="event3",
            affected_entities=["villain"]
        )
        manager = EventManager(db_session, game_session)

        result = manager.get_events_affecting_entity("hero")

        assert len(result) == 2
        types = [e.event_type for e in result]
        assert "event1" in types
        assert "event2" in types


class TestEventManagerDay:
    """Tests for day-based queries."""

    def test_get_events_on_day(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_events_on_day returns events on specific day."""
        create_world_event(
            db_session, game_session,
            event_type="day1_event",
            game_day=1
        )
        create_world_event(
            db_session, game_session,
            event_type="day3_event1",
            game_day=3
        )
        create_world_event(
            db_session, game_session,
            event_type="day3_event2",
            game_day=3
        )
        manager = EventManager(db_session, game_session)

        result = manager.get_events_on_day(3)

        assert len(result) == 2
        assert all(e.game_day == 3 for e in result)
