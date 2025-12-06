"""Tests for ScheduleManager class."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.enums import DayOfWeek
from src.database.models.session import GameSession
from src.database.models.world import Schedule
from src.managers.schedule_manager import ScheduleManager
from src.managers.time_manager import TimeManager
from tests.factories import create_entity, create_schedule, create_time_state


class TestScheduleManagerBasics:
    """Tests for ScheduleManager basic operations."""

    def test_get_schedule_returns_all_entries(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_schedule returns all schedule entries for entity."""
        entity = create_entity(db_session, game_session)
        create_schedule(db_session, entity, day_pattern=DayOfWeek.MONDAY, activity="Work")
        create_schedule(db_session, entity, day_pattern=DayOfWeek.TUESDAY, activity="Rest")
        manager = ScheduleManager(db_session, game_session)

        result = manager.get_schedule(entity.id)

        assert len(result) == 2
        activities = [s.activity for s in result]
        assert "Work" in activities
        assert "Rest" in activities

    def test_set_schedule_entry_creates_new(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify set_schedule_entry creates new schedule entry."""
        entity = create_entity(db_session, game_session)
        manager = ScheduleManager(db_session, game_session)

        result = manager.set_schedule_entry(
            entity_id=entity.id,
            day_pattern=DayOfWeek.DAILY,
            start_time="08:00",
            end_time="17:00",
            activity="Working at shop",
            location_key="shop",
        )

        assert result is not None
        assert result.entity_id == entity.id
        assert result.day_pattern == DayOfWeek.DAILY
        assert result.start_time == "08:00"
        assert result.end_time == "17:00"
        assert result.activity == "Working at shop"
        assert result.location_key == "shop"

    def test_delete_schedule_entry(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify delete_schedule_entry removes entry."""
        entity = create_entity(db_session, game_session)
        schedule = create_schedule(db_session, entity)
        manager = ScheduleManager(db_session, game_session)

        result = manager.delete_schedule_entry(schedule.id)

        assert result is True
        remaining = db_session.query(Schedule).filter(Schedule.id == schedule.id).first()
        assert remaining is None


class TestScheduleManagerActivityLookup:
    """Tests for activity lookup operations."""

    def test_get_activity_at_time_matches_day_and_time(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_activity_at_time returns activity for matching time."""
        entity = create_entity(db_session, game_session)
        create_schedule(
            db_session, entity,
            day_pattern=DayOfWeek.MONDAY,
            start_time="09:00",
            end_time="17:00",
            activity="Working",
            location_key="office"
        )
        manager = ScheduleManager(db_session, game_session)

        result = manager.get_activity_at_time(entity.id, DayOfWeek.MONDAY, "12:00")

        assert result is not None
        activity, location = result
        assert activity == "Working"
        assert location == "office"

    def test_get_activity_at_time_returns_none_outside_hours(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_activity_at_time returns None outside schedule hours."""
        entity = create_entity(db_session, game_session)
        create_schedule(
            db_session, entity,
            day_pattern=DayOfWeek.MONDAY,
            start_time="09:00",
            end_time="17:00",
            activity="Working"
        )
        manager = ScheduleManager(db_session, game_session)

        result = manager.get_activity_at_time(entity.id, DayOfWeek.MONDAY, "20:00")

        assert result is None

    def test_get_activity_at_time_priority_wins(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify higher priority schedule wins when overlapping."""
        entity = create_entity(db_session, game_session)
        create_schedule(
            db_session, entity,
            day_pattern=DayOfWeek.MONDAY,
            start_time="08:00",
            end_time="18:00",
            activity="Regular work",
            priority=1
        )
        create_schedule(
            db_session, entity,
            day_pattern=DayOfWeek.MONDAY,
            start_time="12:00",
            end_time="13:00",
            activity="Lunch break",
            priority=5
        )
        manager = ScheduleManager(db_session, game_session)

        result = manager.get_activity_at_time(entity.id, DayOfWeek.MONDAY, "12:30")

        assert result is not None
        activity, _ = result
        assert activity == "Lunch break"

    def test_get_activity_at_time_weekday_pattern(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify WEEKDAY pattern matches Mon-Fri."""
        entity = create_entity(db_session, game_session)
        create_schedule(
            db_session, entity,
            day_pattern=DayOfWeek.WEEKDAY,
            start_time="09:00",
            end_time="17:00",
            activity="Weekday work"
        )
        manager = ScheduleManager(db_session, game_session)

        # Monday (weekday) should match
        result_mon = manager.get_activity_at_time(entity.id, DayOfWeek.MONDAY, "12:00")
        assert result_mon is not None

        # Friday (weekday) should match
        result_fri = manager.get_activity_at_time(entity.id, DayOfWeek.FRIDAY, "12:00")
        assert result_fri is not None

        # Saturday (weekend) should not match
        result_sat = manager.get_activity_at_time(entity.id, DayOfWeek.SATURDAY, "12:00")
        assert result_sat is None

    def test_get_activity_at_time_weekend_pattern(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify WEEKEND pattern matches Sat-Sun."""
        entity = create_entity(db_session, game_session)
        create_schedule(
            db_session, entity,
            day_pattern=DayOfWeek.WEEKEND,
            start_time="10:00",
            end_time="14:00",
            activity="Weekend relaxation"
        )
        manager = ScheduleManager(db_session, game_session)

        # Saturday (weekend) should match
        result_sat = manager.get_activity_at_time(entity.id, DayOfWeek.SATURDAY, "12:00")
        assert result_sat is not None

        # Monday (weekday) should not match
        result_mon = manager.get_activity_at_time(entity.id, DayOfWeek.MONDAY, "12:00")
        assert result_mon is None

    def test_get_activity_at_time_daily_pattern(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify DAILY pattern matches all days."""
        entity = create_entity(db_session, game_session)
        create_schedule(
            db_session, entity,
            day_pattern=DayOfWeek.DAILY,
            start_time="06:00",
            end_time="07:00",
            activity="Morning routine"
        )
        manager = ScheduleManager(db_session, game_session)

        # Should match any day
        for day in [DayOfWeek.MONDAY, DayOfWeek.SATURDAY, DayOfWeek.SUNDAY]:
            result = manager.get_activity_at_time(entity.id, day, "06:30")
            assert result is not None


class TestScheduleManagerCurrentActivity:
    """Tests for current activity with TimeManager integration."""

    def test_get_current_activity_uses_time_manager(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_current_activity uses TimeManager for current time."""
        entity = create_entity(db_session, game_session)
        create_schedule(
            db_session, entity,
            day_pattern=DayOfWeek.MONDAY,
            start_time="09:00",
            end_time="17:00",
            activity="Working"
        )
        create_time_state(
            db_session, game_session,
            current_time="12:00",
            day_of_week="monday"
        )
        time_manager = TimeManager(db_session, game_session)
        manager = ScheduleManager(db_session, game_session, time_manager=time_manager)

        result = manager.get_current_activity(entity.id)

        assert result is not None
        activity, _ = result
        assert activity == "Working"


class TestScheduleManagerLocationQueries:
    """Tests for location-based queries."""

    def test_get_npcs_at_location_time(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_npcs_at_location_time returns scheduled NPCs."""
        npc1 = create_entity(db_session, game_session, entity_key="npc1")
        npc2 = create_entity(db_session, game_session, entity_key="npc2")
        npc3 = create_entity(db_session, game_session, entity_key="npc3")

        # NPC1 at tavern Mon 10-14
        create_schedule(
            db_session, npc1,
            day_pattern=DayOfWeek.MONDAY,
            start_time="10:00",
            end_time="14:00",
            location_key="tavern"
        )
        # NPC2 at tavern Mon 12-18
        create_schedule(
            db_session, npc2,
            day_pattern=DayOfWeek.MONDAY,
            start_time="12:00",
            end_time="18:00",
            location_key="tavern"
        )
        # NPC3 at market Mon 10-14
        create_schedule(
            db_session, npc3,
            day_pattern=DayOfWeek.MONDAY,
            start_time="10:00",
            end_time="14:00",
            location_key="market"
        )
        manager = ScheduleManager(db_session, game_session)

        result = manager.get_npcs_at_location_time("tavern", DayOfWeek.MONDAY, "13:00")

        assert len(result) == 2
        assert npc1.id in result
        assert npc2.id in result
        assert npc3.id not in result


class TestScheduleManagerTimeHelpers:
    """Tests for time helper methods."""

    def test_is_time_in_range_same_day(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify is_time_in_range works for same-day ranges."""
        manager = ScheduleManager(db_session, game_session)

        assert manager.is_time_in_range("12:00", "09:00", "17:00") is True
        assert manager.is_time_in_range("08:00", "09:00", "17:00") is False
        assert manager.is_time_in_range("18:00", "09:00", "17:00") is False
        assert manager.is_time_in_range("09:00", "09:00", "17:00") is True
        assert manager.is_time_in_range("17:00", "09:00", "17:00") is False

    def test_is_time_in_range_crosses_midnight(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify is_time_in_range works for ranges crossing midnight."""
        manager = ScheduleManager(db_session, game_session)

        # Night shift: 22:00 - 06:00
        assert manager.is_time_in_range("23:00", "22:00", "06:00") is True
        assert manager.is_time_in_range("02:00", "22:00", "06:00") is True
        assert manager.is_time_in_range("21:00", "22:00", "06:00") is False
        assert manager.is_time_in_range("07:00", "22:00", "06:00") is False

    def test_day_matches_specific_day(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify day_matches works for specific days."""
        manager = ScheduleManager(db_session, game_session)

        assert manager.day_matches(DayOfWeek.MONDAY, DayOfWeek.MONDAY) is True
        assert manager.day_matches(DayOfWeek.MONDAY, DayOfWeek.TUESDAY) is False

    def test_day_matches_weekday(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify day_matches works for WEEKDAY pattern."""
        manager = ScheduleManager(db_session, game_session)

        assert manager.day_matches(DayOfWeek.MONDAY, DayOfWeek.WEEKDAY) is True
        assert manager.day_matches(DayOfWeek.FRIDAY, DayOfWeek.WEEKDAY) is True
        assert manager.day_matches(DayOfWeek.SATURDAY, DayOfWeek.WEEKDAY) is False
        assert manager.day_matches(DayOfWeek.SUNDAY, DayOfWeek.WEEKDAY) is False

    def test_day_matches_weekend(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify day_matches works for WEEKEND pattern."""
        manager = ScheduleManager(db_session, game_session)

        assert manager.day_matches(DayOfWeek.SATURDAY, DayOfWeek.WEEKEND) is True
        assert manager.day_matches(DayOfWeek.SUNDAY, DayOfWeek.WEEKEND) is True
        assert manager.day_matches(DayOfWeek.MONDAY, DayOfWeek.WEEKEND) is False

    def test_day_matches_daily(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify day_matches works for DAILY pattern."""
        manager = ScheduleManager(db_session, game_session)

        for day in [DayOfWeek.MONDAY, DayOfWeek.WEDNESDAY, DayOfWeek.SATURDAY]:
            assert manager.day_matches(day, DayOfWeek.DAILY) is True
