"""TimeManager for game time tracking and manipulation."""

from sqlalchemy.orm import Session

from src.database.models.enums import DayOfWeek
from src.database.models.session import GameSession
from src.database.models.world import TimeState
from src.managers.base import BaseManager


# Day of week progression
DAYS_ORDER = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


class TimeManager(BaseManager):
    """Manager for game time operations.

    Handles:
    - Getting/setting current game time
    - Advancing time (with day/week rollover)
    - Weather management
    - Period of day calculations
    """

    def get_time_state(self) -> TimeState | None:
        """Get the current time state for this session.

        Returns:
            TimeState if exists, None otherwise.
        """
        return (
            self.db.query(TimeState)
            .filter(TimeState.session_id == self.session_id)
            .first()
        )

    def get_or_create_time_state(self) -> TimeState:
        """Get existing time state or create with defaults.

        Returns:
            TimeState (existing or newly created).
        """
        time_state = self.get_time_state()
        if time_state is not None:
            return time_state

        time_state = TimeState(
            session_id=self.session_id,
            current_day=1,
            current_time="08:00",
            day_of_week="monday",
        )
        self.db.add(time_state)
        self.db.flush()
        return time_state

    def get_current_time(self) -> tuple[int, str]:
        """Get current day number and time.

        Returns:
            Tuple of (day_number, "HH:MM").
        """
        time_state = self.get_or_create_time_state()
        return time_state.current_day, time_state.current_time

    def get_day_of_week(self) -> DayOfWeek:
        """Get current day of week as enum.

        Returns:
            DayOfWeek enum value.
        """
        time_state = self.get_or_create_time_state()
        return DayOfWeek(time_state.day_of_week)

    def advance_time(self, minutes: int) -> TimeState:
        """Advance game time by specified minutes.

        Handles hour and day rollovers automatically.
        Updates day_of_week when day changes.

        Args:
            minutes: Number of minutes to advance.

        Returns:
            Updated TimeState.
        """
        time_state = self.get_or_create_time_state()

        # Parse current time
        hours, mins = map(int, time_state.current_time.split(":"))

        # Add minutes
        total_minutes = hours * 60 + mins + minutes

        # Calculate days passed and new time
        days_passed = total_minutes // (24 * 60)
        remaining_minutes = total_minutes % (24 * 60)

        new_hours = remaining_minutes // 60
        new_mins = remaining_minutes % 60

        # Update time
        time_state.current_time = f"{new_hours:02d}:{new_mins:02d}"

        # Update day if needed
        if days_passed > 0:
            time_state.current_day += days_passed

            # Update day of week
            current_day_index = DAYS_ORDER.index(time_state.day_of_week)
            new_day_index = (current_day_index + days_passed) % 7
            time_state.day_of_week = DAYS_ORDER[new_day_index]

        self.db.flush()
        return time_state

    def set_time(self, time_str: str) -> TimeState:
        """Set time explicitly (does not change day).

        Args:
            time_str: Time in "HH:MM" format.

        Returns:
            Updated TimeState.
        """
        time_state = self.get_or_create_time_state()
        time_state.current_time = time_str
        self.db.flush()
        return time_state

    def advance_day(self) -> TimeState:
        """Advance to the next day.

        Updates both current_day and day_of_week.

        Returns:
            Updated TimeState.
        """
        time_state = self.get_or_create_time_state()

        time_state.current_day += 1

        current_day_index = DAYS_ORDER.index(time_state.day_of_week)
        new_day_index = (current_day_index + 1) % 7
        time_state.day_of_week = DAYS_ORDER[new_day_index]

        self.db.flush()
        return time_state

    def set_weather(
        self, weather: str, temperature: str | None = None
    ) -> TimeState:
        """Update weather and optionally temperature.

        Args:
            weather: Weather description (e.g., "rainy", "sunny").
            temperature: Optional temperature description.

        Returns:
            Updated TimeState.
        """
        time_state = self.get_or_create_time_state()
        time_state.weather = weather
        if temperature is not None:
            time_state.temperature = temperature
        self.db.flush()
        return time_state

    def get_period_of_day(self) -> str:
        """Get current period of day.

        Periods:
        - night: 21:00 - 05:59
        - dawn: 06:00 - 06:59
        - morning: 07:00 - 11:59
        - afternoon: 12:00 - 17:59
        - evening: 18:00 - 20:59

        Returns:
            Period string (night, dawn, morning, afternoon, evening).
        """
        time_state = self.get_or_create_time_state()
        hours = int(time_state.current_time.split(":")[0])

        if hours < 6:
            return "night"
        elif hours < 7:
            return "dawn"
        elif hours < 12:
            return "morning"
        elif hours < 18:
            return "afternoon"
        elif hours < 21:
            return "evening"
        else:
            return "night"

    def is_daytime(self) -> bool:
        """Check if it's currently daytime (06:00 - 19:59).

        Returns:
            True if daytime, False if nighttime.
        """
        time_state = self.get_or_create_time_state()
        hours = int(time_state.current_time.split(":")[0])
        return 6 <= hours < 20
