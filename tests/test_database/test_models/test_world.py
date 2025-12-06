"""Tests for world models (Location, Schedule, TimeState, Fact, WorldEvent)."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.database.models.enums import DayOfWeek, FactCategory
from src.database.models.session import GameSession
from src.database.models.world import Fact, Location, Schedule, TimeState, WorldEvent
from tests.factories import (
    create_entity,
    create_fact,
    create_game_session,
    create_location,
    create_schedule,
    create_time_state,
    create_world_event,
)


class TestLocation:
    """Tests for Location model."""

    def test_create_location_required_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify Location creation with required fields."""
        loc = Location(
            session_id=game_session.id,
            location_key="tavern",
            display_name="The Rusty Anchor",
            description="A cozy tavern near the docks.",
        )
        db_session.add(loc)
        db_session.flush()

        assert loc.id is not None
        assert loc.session_id == game_session.id
        assert loc.location_key == "tavern"
        assert loc.display_name == "The Rusty Anchor"

    def test_location_unique_constraint(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify unique constraint on session_id + location_key."""
        create_location(db_session, game_session, location_key="tavern")

        with pytest.raises(IntegrityError):
            create_location(db_session, game_session, location_key="tavern")

    def test_location_same_key_different_sessions(self, db_session: Session):
        """Verify same location_key allowed in different sessions."""
        session1 = create_game_session(db_session)
        session2 = create_game_session(db_session)

        loc1 = create_location(db_session, session1, location_key="tavern")
        loc2 = create_location(db_session, session2, location_key="tavern")

        assert loc1.id != loc2.id

    def test_location_hierarchy(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify parent_location_id self-reference."""
        city = create_location(
            db_session,
            game_session,
            location_key="city",
            display_name="The City",
        )
        district = create_location(
            db_session,
            game_session,
            location_key="market_district",
            display_name="Market District",
            parent_location_id=city.id,
        )

        db_session.refresh(district)

        assert district.parent_location_id == city.id
        assert district.parent_location is not None
        assert district.parent_location.location_key == "city"

    def test_location_category(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify location category field."""
        loc = create_location(
            db_session,
            game_session,
            category="building",
        )

        db_session.refresh(loc)
        assert loc.category == "building"

    def test_location_atmosphere_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify atmosphere and typical_crowd fields."""
        loc = create_location(
            db_session,
            game_session,
            atmosphere="Dim lighting, smoky air, murmur of conversation",
            typical_crowd="Sailors, merchants, occasional adventurers",
        )

        db_session.refresh(loc)

        assert "smoky air" in loc.atmosphere
        assert "Sailors" in loc.typical_crowd

    def test_location_accessibility(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify is_accessible and access_requirements fields."""
        loc = create_location(
            db_session,
            game_session,
            is_accessible=False,
            access_requirements="Requires guild membership",
        )

        db_session.refresh(loc)

        assert loc.is_accessible is False
        assert loc.access_requirements == "Requires guild membership"

    def test_location_consistency_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify consistency tracking fields."""
        loc = create_location(
            db_session,
            game_session,
            canonical_description="The main room has a bar on the left and booths on the right.",
            first_visited_turn=5,
            spatial_layout={"exits": ["main_door", "back_door"], "bar": "left", "booths": "right"},
        )

        db_session.refresh(loc)

        assert loc.canonical_description is not None
        assert loc.first_visited_turn == 5
        assert loc.spatial_layout["bar"] == "left"

    def test_location_state_history_json(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify state_history JSON field."""
        history = [
            {"turn": 10, "change": "fire_damage", "reason": "Dragon attack"},
            {"turn": 20, "change": "repaired", "reason": "Rebuilt by townsfolk"},
        ]
        loc = create_location(db_session, game_session, state_history=history)

        db_session.refresh(loc)

        assert loc.state_history == history
        assert len(loc.state_history) == 2

    def test_location_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        loc = create_location(db_session, game_session, location_key="castle")

        repr_str = repr(loc)
        assert "Location" in repr_str
        assert "castle" in repr_str


class TestSchedule:
    """Tests for Schedule model."""

    def test_create_schedule_required_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify Schedule creation with required fields."""
        entity = create_entity(db_session, game_session)
        schedule = Schedule(
            entity_id=entity.id,
            day_pattern=DayOfWeek.MONDAY,
            start_time="09:00",
            end_time="17:00",
            activity="Working at the forge",
        )
        db_session.add(schedule)
        db_session.flush()

        assert schedule.id is not None
        assert schedule.entity_id == entity.id
        assert schedule.day_pattern == DayOfWeek.MONDAY

    def test_schedule_day_patterns(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify different day patterns."""
        entity = create_entity(db_session, game_session)

        for day_pattern in [DayOfWeek.WEEKDAY, DayOfWeek.WEEKEND, DayOfWeek.DAILY]:
            schedule = create_schedule(db_session, entity, day_pattern=day_pattern)
            db_session.refresh(schedule)
            assert schedule.day_pattern == day_pattern

    def test_schedule_time_format(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify time format HH:MM."""
        entity = create_entity(db_session, game_session)
        schedule = create_schedule(
            db_session,
            entity,
            start_time="06:30",
            end_time="22:00",
        )

        db_session.refresh(schedule)

        assert schedule.start_time == "06:30"
        assert schedule.end_time == "22:00"

    def test_schedule_priority(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify priority field for overlapping schedules."""
        entity = create_entity(db_session, game_session)

        low_priority = create_schedule(db_session, entity, priority=1, activity="Normal work")
        high_priority = create_schedule(db_session, entity, priority=10, activity="Emergency")

        assert high_priority.priority > low_priority.priority

    def test_schedule_location_key(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify location_key field."""
        entity = create_entity(db_session, game_session)
        schedule = create_schedule(
            db_session,
            entity,
            location_key="blacksmith_shop",
        )

        db_session.refresh(schedule)
        assert schedule.location_key == "blacksmith_shop"

    def test_schedule_entity_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify schedule has back reference to entity."""
        entity = create_entity(db_session, game_session)
        schedule = create_schedule(db_session, entity)

        assert schedule.entity is not None
        assert schedule.entity.id == entity.id

    def test_entity_schedules_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify entity has schedules relationship."""
        entity = create_entity(db_session, game_session)
        create_schedule(db_session, entity, activity="Morning work")
        create_schedule(db_session, entity, activity="Afternoon break")

        db_session.refresh(entity)

        assert len(entity.schedules) == 2

    def test_schedule_cascade_delete(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify schedules are deleted when entity is deleted."""
        entity = create_entity(db_session, game_session)
        schedule = create_schedule(db_session, entity)
        schedule_id = schedule.id

        db_session.delete(entity)
        db_session.flush()
        db_session.expire_all()

        result = db_session.query(Schedule).filter(Schedule.id == schedule_id).first()
        assert result is None

    def test_schedule_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        entity = create_entity(db_session, game_session)
        schedule = create_schedule(
            db_session,
            entity,
            day_pattern=DayOfWeek.WEEKDAY,
            start_time="09:00",
            end_time="17:00",
            activity="Working",
        )

        repr_str = repr(schedule)
        assert "Schedule" in repr_str
        assert "weekday" in repr_str
        assert "09:00" in repr_str
        assert "17:00" in repr_str


class TestTimeState:
    """Tests for TimeState model."""

    def test_create_time_state(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify TimeState creation."""
        state = TimeState(session_id=game_session.id)
        db_session.add(state)
        db_session.flush()

        assert state.id is not None
        assert state.session_id == game_session.id

    def test_time_state_unique_per_session(self, db_session: Session):
        """Verify only one TimeState per session."""
        session = create_game_session(db_session)
        create_time_state(db_session, session)

        with pytest.raises(IntegrityError):
            create_time_state(db_session, session)

    def test_time_state_defaults(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify TimeState default values."""
        state = TimeState(session_id=game_session.id)
        db_session.add(state)
        db_session.flush()

        assert state.current_day == 1
        assert state.current_time == "08:00"
        assert state.day_of_week == "monday"
        assert state.year == 1
        assert state.month == 1
        assert state.season == "spring"

    def test_time_state_calendar(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify calendar fields."""
        state = create_time_state(
            db_session,
            game_session,
            year=1453,
            month=6,
            season="summer",
        )

        db_session.refresh(state)

        assert state.year == 1453
        assert state.month == 6
        assert state.season == "summer"

    def test_time_state_environment(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify environment fields."""
        state = create_time_state(
            db_session,
            game_session,
            weather="rainy",
            temperature="mild",
        )

        db_session.refresh(state)

        assert state.weather == "rainy"
        assert state.temperature == "mild"

    def test_time_state_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        state = create_time_state(
            db_session,
            game_session,
            current_day=5,
            current_time="14:30",
        )

        repr_str = repr(state)
        assert "TimeState" in repr_str
        assert "5" in repr_str
        assert "14:30" in repr_str


class TestFact:
    """Tests for Fact (SPV) model."""

    def test_create_fact_required_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify Fact creation with required fields."""
        fact = Fact(
            session_id=game_session.id,
            subject_type="entity",
            subject_key="bartender_joe",
            predicate="job",
            value="bartender",
            source_turn=1,
        )
        db_session.add(fact)
        db_session.flush()

        assert fact.id is not None
        assert fact.subject_type == "entity"
        assert fact.subject_key == "bartender_joe"
        assert fact.predicate == "job"
        assert fact.value == "bartender"

    def test_fact_spv_pattern(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify Subject-Predicate-Value storage pattern."""
        # Create multiple facts about same subject
        create_fact(
            db_session,
            game_session,
            subject_type="entity",
            subject_key="hero",
            predicate="strength",
            value="18",
        )
        create_fact(
            db_session,
            game_session,
            subject_type="entity",
            subject_key="hero",
            predicate="class",
            value="warrior",
        )

        facts = (
            db_session.query(Fact)
            .filter(Fact.subject_key == "hero")
            .all()
        )

        assert len(facts) == 2
        predicates = {f.predicate for f in facts}
        assert predicates == {"strength", "class"}

    def test_fact_category_enum(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify FactCategory enum storage."""
        for category in FactCategory:
            fact = create_fact(db_session, game_session, category=category)
            db_session.refresh(fact)
            assert fact.category == category

    def test_fact_confidence(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify confidence score 0-100."""
        fact = create_fact(db_session, game_session, confidence=75)

        db_session.refresh(fact)
        assert fact.confidence == 75

    def test_fact_secret_flag(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify is_secret boolean flag."""
        secret_fact = create_fact(
            db_session,
            game_session,
            predicate="true_identity",
            value="undercover_spy",
            is_secret=True,
        )

        db_session.refresh(secret_fact)
        assert secret_fact.is_secret is True

    def test_fact_player_believes(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify player_believes field for misinformation."""
        fact = create_fact(
            db_session,
            game_session,
            subject_key="villain",
            predicate="true_identity",
            value="evil_wizard",  # The truth
            player_believes="friendly_merchant",  # What player thinks
            is_secret=True,
        )

        db_session.refresh(fact)

        assert fact.value == "evil_wizard"
        assert fact.player_believes == "friendly_merchant"

    def test_fact_foreshadowing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify foreshadowing narrative flags."""
        fact = create_fact(
            db_session,
            game_session,
            predicate="odd_behavior",
            value="never seen eating",
            is_foreshadowing=True,
            foreshadow_target="reveal_as_vampire",
            times_mentioned=2,
        )

        db_session.refresh(fact)

        assert fact.is_foreshadowing is True
        assert fact.foreshadow_target == "reveal_as_vampire"
        assert fact.times_mentioned == 2

    def test_fact_source_tracking(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify source_turn tracking."""
        fact = create_fact(db_session, game_session, source_turn=15)

        db_session.refresh(fact)
        assert fact.source_turn == 15
        assert fact.created_at is not None

    def test_fact_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        fact = create_fact(
            db_session,
            game_session,
            subject_key="npc",
            predicate="occupation",
            value="blacksmith",
        )

        repr_str = repr(fact)
        assert "Fact" in repr_str
        assert "npc" in repr_str
        assert "occupation" in repr_str

    def test_fact_repr_secret(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify repr includes SECRET marker."""
        fact = create_fact(
            db_session,
            game_session,
            is_secret=True,
        )

        repr_str = repr(fact)
        assert "SECRET" in repr_str


class TestWorldEvent:
    """Tests for WorldEvent model."""

    def test_create_world_event_required_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify WorldEvent creation with required fields."""
        event = WorldEvent(
            session_id=game_session.id,
            event_type="robbery",
            summary="A thief stole from the market.",
            game_day=3,
            turn_created=10,
        )
        db_session.add(event)
        db_session.flush()

        assert event.id is not None
        assert event.event_type == "robbery"
        assert event.summary == "A thief stole from the market."

    def test_world_event_details_json(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify details JSON field."""
        details = {
            "stolen_items": ["gold_coins", "silver_ring"],
            "witnesses": ["bartender_joe"],
            "thief_description": "hooded figure",
        }
        event = create_world_event(db_session, game_session, details=details)

        db_session.refresh(event)

        assert event.details == details
        assert event.details["thief_description"] == "hooded figure"

    def test_world_event_affected_entities_json(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify affected_entities JSON field."""
        affected = ["merchant_bob", "guard_captain"]
        event = create_world_event(db_session, game_session, affected_entities=affected)

        db_session.refresh(event)

        assert event.affected_entities == affected

    def test_world_event_player_awareness(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify is_known_to_player and discovery_turn."""
        # Hidden event
        hidden_event = create_world_event(
            db_session,
            game_session,
            is_known_to_player=False,
        )
        assert hidden_event.is_known_to_player is False
        assert hidden_event.discovery_turn is None

        # Discovered event
        known_event = create_world_event(
            db_session,
            game_session,
            is_known_to_player=True,
            discovery_turn=15,
        )
        assert known_event.is_known_to_player is True
        assert known_event.discovery_turn == 15

    def test_world_event_processing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify is_processed flag."""
        event = create_world_event(db_session, game_session, is_processed=False)
        assert event.is_processed is False

        event.is_processed = True
        db_session.flush()
        db_session.refresh(event)
        assert event.is_processed is True

    def test_world_event_location_and_time(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify location and time fields."""
        event = create_world_event(
            db_session,
            game_session,
            game_day=5,
            game_time="14:30",
            location_key="market_square",
        )

        db_session.refresh(event)

        assert event.game_day == 5
        assert event.game_time == "14:30"
        assert event.location_key == "market_square"

    def test_world_event_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        event = create_world_event(
            db_session,
            game_session,
            event_type="weather_change",
            summary="A storm is approaching from the north.",
            is_known_to_player=True,
        )

        repr_str = repr(event)
        assert "WorldEvent" in repr_str
        assert "weather_change" in repr_str

    def test_world_event_repr_hidden(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify repr includes HIDDEN marker."""
        event = create_world_event(
            db_session,
            game_session,
            is_known_to_player=False,
        )

        repr_str = repr(event)
        assert "HIDDEN" in repr_str

    def test_world_event_session_scoping(self, db_session: Session):
        """Verify events are properly scoped to sessions."""
        session1 = create_game_session(db_session)
        session2 = create_game_session(db_session)

        event1 = create_world_event(db_session, session1)
        event2 = create_world_event(db_session, session2)

        result = (
            db_session.query(WorldEvent)
            .filter(WorldEvent.session_id == session1.id)
            .all()
        )

        assert len(result) == 1
        assert result[0].id == event1.id
