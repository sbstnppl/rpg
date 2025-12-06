"""ScheduleManager for NPC scheduling and activity lookup."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from src.database.models.enums import DayOfWeek
from src.database.models.session import GameSession
from src.database.models.world import Schedule
from src.managers.base import BaseManager

if TYPE_CHECKING:
    from src.managers.time_manager import TimeManager


# Days that count as weekdays
WEEKDAYS = {
    DayOfWeek.MONDAY,
    DayOfWeek.TUESDAY,
    DayOfWeek.WEDNESDAY,
    DayOfWeek.THURSDAY,
    DayOfWeek.FRIDAY,
}

# Days that count as weekend
WEEKEND = {
    DayOfWeek.SATURDAY,
    DayOfWeek.SUNDAY,
}


class ScheduleManager(BaseManager):
    """Manager for NPC schedule operations.

    Handles:
    - Schedule CRUD
    - Activity lookup by time
    - Location-based NPC queries
    - Time range and day pattern matching
    """

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        time_manager: TimeManager | None = None,
    ):
        """Initialize with optional TimeManager dependency.

        Args:
            db: Database session.
            game_session: Game session.
            time_manager: Optional TimeManager for current time lookups.
        """
        super().__init__(db, game_session)
        self.time_manager = time_manager

    def get_schedule(self, entity_id: int) -> list[Schedule]:
        """Get all schedule entries for entity.

        Args:
            entity_id: Entity ID.

        Returns:
            List of Schedule entries.
        """
        return (
            self.db.query(Schedule)
            .filter(Schedule.entity_id == entity_id)
            .all()
        )

    def get_schedule_entry(
        self, entity_id: int, day: DayOfWeek, time: str
    ) -> Schedule | None:
        """Get specific schedule entry matching day/time.

        Args:
            entity_id: Entity ID.
            day: Day of week.
            time: Time in HH:MM format.

        Returns:
            Matching Schedule or None.
        """
        schedules = self.get_schedule(entity_id)
        matching = [
            s for s in schedules
            if self.day_matches(day, s.day_pattern)
            and self.is_time_in_range(time, s.start_time, s.end_time)
        ]
        if not matching:
            return None
        # Return highest priority
        return max(matching, key=lambda s: s.priority)

    def set_schedule_entry(
        self,
        entity_id: int,
        day_pattern: DayOfWeek,
        start_time: str,
        end_time: str,
        activity: str,
        location_key: str | None = None,
        priority: int = 0,
    ) -> Schedule:
        """Create or update schedule entry.

        Args:
            entity_id: Entity ID.
            day_pattern: Day pattern (specific day, WEEKDAY, WEEKEND, DAILY).
            start_time: Start time in HH:MM format.
            end_time: End time in HH:MM format.
            activity: Activity description.
            location_key: Optional location key.
            priority: Priority (higher wins on overlap).

        Returns:
            Created Schedule.
        """
        schedule = Schedule(
            entity_id=entity_id,
            day_pattern=day_pattern,
            start_time=start_time,
            end_time=end_time,
            activity=activity,
            location_key=location_key,
            priority=priority,
        )
        self.db.add(schedule)
        self.db.flush()
        return schedule

    def delete_schedule_entry(self, schedule_id: int) -> bool:
        """Delete schedule entry.

        Args:
            schedule_id: Schedule ID.

        Returns:
            True if deleted, False if not found.
        """
        schedule = (
            self.db.query(Schedule)
            .filter(Schedule.id == schedule_id)
            .first()
        )
        if schedule is None:
            return False

        self.db.delete(schedule)
        self.db.flush()
        return True

    def get_activity_at_time(
        self, entity_id: int, day: DayOfWeek, time: str
    ) -> tuple[str, str | None] | None:
        """Get (activity, location_key) for entity at specified time.

        Args:
            entity_id: Entity ID.
            day: Day of week.
            time: Time in HH:MM format.

        Returns:
            Tuple of (activity, location_key) or None if no schedule.
        """
        entry = self.get_schedule_entry(entity_id, day, time)
        if entry is None:
            return None
        return (entry.activity, entry.location_key)

    def get_current_activity(
        self, entity_id: int
    ) -> tuple[str, str | None] | None:
        """Get current activity using TimeManager.

        Args:
            entity_id: Entity ID.

        Returns:
            Tuple of (activity, location_key) or None.

        Raises:
            ValueError: If TimeManager not provided.
        """
        if self.time_manager is None:
            raise ValueError("TimeManager required for get_current_activity")

        day = self.time_manager.get_day_of_week()
        _, time = self.time_manager.get_current_time()
        return self.get_activity_at_time(entity_id, day, time)

    def get_npcs_at_location_time(
        self, location_key: str, day: DayOfWeek, time: str
    ) -> list[int]:
        """Get entity IDs of NPCs scheduled at location/time.

        Args:
            location_key: Location key.
            day: Day of week.
            time: Time in HH:MM format.

        Returns:
            List of entity IDs.
        """
        # Get all schedules at this location
        schedules = (
            self.db.query(Schedule)
            .filter(Schedule.location_key == location_key)
            .all()
        )

        entity_ids = []
        for schedule in schedules:
            if (
                self.day_matches(day, schedule.day_pattern)
                and self.is_time_in_range(time, schedule.start_time, schedule.end_time)
            ):
                if schedule.entity_id not in entity_ids:
                    entity_ids.append(schedule.entity_id)

        return entity_ids

    def get_npcs_at_location_now(self, location_key: str) -> list[int]:
        """Get NPCs at location using current time.

        Args:
            location_key: Location key.

        Returns:
            List of entity IDs.

        Raises:
            ValueError: If TimeManager not provided.
        """
        if self.time_manager is None:
            raise ValueError("TimeManager required for get_npcs_at_location_now")

        day = self.time_manager.get_day_of_week()
        _, time = self.time_manager.get_current_time()
        return self.get_npcs_at_location_time(location_key, day, time)

    def is_time_in_range(self, time: str, start: str, end: str) -> bool:
        """Check if time falls within range (handles midnight crossing).

        Args:
            time: Time to check in HH:MM format.
            start: Range start in HH:MM format.
            end: Range end in HH:MM format (exclusive).

        Returns:
            True if time is in range.
        """
        def to_minutes(t: str) -> int:
            h, m = map(int, t.split(":"))
            return h * 60 + m

        time_mins = to_minutes(time)
        start_mins = to_minutes(start)
        end_mins = to_minutes(end)

        if start_mins <= end_mins:
            # Same day range
            return start_mins <= time_mins < end_mins
        else:
            # Crosses midnight
            return time_mins >= start_mins or time_mins < end_mins

    def day_matches(self, day: DayOfWeek, pattern: DayOfWeek) -> bool:
        """Check if day matches pattern.

        Args:
            day: Actual day.
            pattern: Day pattern to match.

        Returns:
            True if day matches pattern.
        """
        if pattern == DayOfWeek.DAILY:
            return True
        if pattern == DayOfWeek.WEEKDAY:
            return day in WEEKDAYS
        if pattern == DayOfWeek.WEEKEND:
            return day in WEEKEND
        return day == pattern
