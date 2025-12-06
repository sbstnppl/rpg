"""Tests for TimeManager class."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.enums import DayOfWeek
from src.database.models.session import GameSession
from src.database.models.world import TimeState
from src.managers.time_manager import TimeManager
from tests.factories import create_time_state


class TestTimeManagerBasics:
    """Tests for TimeManager basic operations."""

    def test_get_time_state_returns_none_when_missing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_time_state returns None when no time state exists."""
        manager = TimeManager(db_session, game_session)

        result = manager.get_time_state()

        assert result is None

    def test_get_time_state_returns_existing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_time_state returns existing TimeState."""
        time_state = create_time_state(db_session, game_session, current_day=5)
        manager = TimeManager(db_session, game_session)

        result = manager.get_time_state()

        assert result is not None
        assert result.id == time_state.id
        assert result.current_day == 5

    def test_get_or_create_time_state_creates_when_missing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_or_create_time_state creates new TimeState with defaults."""
        manager = TimeManager(db_session, game_session)

        result = manager.get_or_create_time_state()

        assert result is not None
        assert result.session_id == game_session.id
        assert result.current_day == 1
        assert result.current_time == "08:00"
        assert result.day_of_week == "monday"

    def test_get_or_create_time_state_returns_existing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_or_create_time_state returns existing when present."""
        time_state = create_time_state(
            db_session, game_session, current_day=3, current_time="14:30"
        )
        manager = TimeManager(db_session, game_session)

        result = manager.get_or_create_time_state()

        assert result.id == time_state.id
        assert result.current_day == 3
        assert result.current_time == "14:30"


class TestTimeManagerCurrentTime:
    """Tests for getting current time."""

    def test_get_current_time_returns_day_and_time(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_current_time returns tuple of (day, time)."""
        create_time_state(
            db_session, game_session, current_day=7, current_time="15:45"
        )
        manager = TimeManager(db_session, game_session)

        day, time = manager.get_current_time()

        assert day == 7
        assert time == "15:45"

    def test_get_current_time_creates_state_if_missing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_current_time creates time state with defaults if missing."""
        manager = TimeManager(db_session, game_session)

        day, time = manager.get_current_time()

        assert day == 1
        assert time == "08:00"

    def test_get_day_of_week_returns_enum(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_day_of_week returns DayOfWeek enum."""
        create_time_state(db_session, game_session, day_of_week="wednesday")
        manager = TimeManager(db_session, game_session)

        result = manager.get_day_of_week()

        assert result == DayOfWeek.WEDNESDAY


class TestTimeManagerAdvanceTime:
    """Tests for advancing time."""

    def test_advance_time_simple(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify advance_time adds minutes correctly."""
        create_time_state(db_session, game_session, current_time="10:00")
        manager = TimeManager(db_session, game_session)

        result = manager.advance_time(30)

        assert result.current_time == "10:30"

    def test_advance_time_handles_hour_rollover(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify advance_time handles hour boundary correctly."""
        create_time_state(db_session, game_session, current_time="10:45")
        manager = TimeManager(db_session, game_session)

        result = manager.advance_time(30)

        assert result.current_time == "11:15"

    def test_advance_time_handles_day_rollover(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify advance_time handles day boundary correctly."""
        create_time_state(
            db_session, game_session,
            current_day=1,
            current_time="23:30",
            day_of_week="monday"
        )
        manager = TimeManager(db_session, game_session)

        result = manager.advance_time(60)

        assert result.current_day == 2
        assert result.current_time == "00:30"
        assert result.day_of_week == "tuesday"

    def test_advance_time_handles_week_rollover(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify advance_time handles week boundary (Sunday to Monday)."""
        create_time_state(
            db_session, game_session,
            current_day=7,
            current_time="23:30",
            day_of_week="sunday"
        )
        manager = TimeManager(db_session, game_session)

        result = manager.advance_time(60)

        assert result.current_day == 8
        assert result.current_time == "00:30"
        assert result.day_of_week == "monday"

    def test_advance_time_large_increment(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify advance_time handles multi-day increments."""
        create_time_state(
            db_session, game_session,
            current_day=1,
            current_time="12:00",
            day_of_week="monday"
        )
        manager = TimeManager(db_session, game_session)

        # Advance 2 days and 6 hours (3000 minutes = 50 hours)
        result = manager.advance_time(3000)

        assert result.current_day == 3
        assert result.current_time == "14:00"
        assert result.day_of_week == "wednesday"


class TestTimeManagerSetTime:
    """Tests for setting time explicitly."""

    def test_set_time_updates_time(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify set_time updates the current time."""
        create_time_state(db_session, game_session, current_time="08:00")
        manager = TimeManager(db_session, game_session)

        result = manager.set_time("14:30")

        assert result.current_time == "14:30"

    def test_advance_day_increments_day_and_updates_weekday(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify advance_day increments day and updates day_of_week."""
        create_time_state(
            db_session, game_session,
            current_day=5,
            day_of_week="friday"
        )
        manager = TimeManager(db_session, game_session)

        result = manager.advance_day()

        assert result.current_day == 6
        assert result.day_of_week == "saturday"


class TestTimeManagerWeather:
    """Tests for weather management."""

    def test_set_weather_updates_weather(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify set_weather updates the weather field."""
        create_time_state(db_session, game_session)
        manager = TimeManager(db_session, game_session)

        result = manager.set_weather("rainy")

        assert result.weather == "rainy"

    def test_set_weather_with_temperature(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify set_weather can also set temperature."""
        create_time_state(db_session, game_session)
        manager = TimeManager(db_session, game_session)

        result = manager.set_weather("sunny", temperature="warm")

        assert result.weather == "sunny"
        assert result.temperature == "warm"


class TestTimeManagerPeriodOfDay:
    """Tests for period of day calculations."""

    @pytest.mark.parametrize(
        "time,expected",
        [
            ("05:00", "night"),
            ("06:00", "dawn"),
            ("06:59", "dawn"),
            ("07:00", "morning"),
            ("11:59", "morning"),
            ("12:00", "afternoon"),
            ("17:59", "afternoon"),
            ("18:00", "evening"),
            ("20:59", "evening"),
            ("21:00", "night"),
            ("23:59", "night"),
            ("00:00", "night"),
        ],
    )
    def test_get_period_of_day(
        self, db_session: Session, game_session: GameSession, time: str, expected: str
    ):
        """Verify get_period_of_day returns correct period for various times."""
        create_time_state(db_session, game_session, current_time=time)
        manager = TimeManager(db_session, game_session)

        result = manager.get_period_of_day()

        assert result == expected

    @pytest.mark.parametrize(
        "time,expected",
        [
            ("05:59", False),
            ("06:00", True),
            ("12:00", True),
            ("19:59", True),
            ("20:00", False),
            ("23:00", False),
        ],
    )
    def test_is_daytime(
        self, db_session: Session, game_session: GameSession, time: str, expected: bool
    ):
        """Verify is_daytime returns correct boolean for various times."""
        create_time_state(db_session, game_session, current_time=time)
        manager = TimeManager(db_session, game_session)

        result = manager.is_daytime()

        assert result is expected
