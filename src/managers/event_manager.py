"""EventManager for world event tracking and management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from src.database.models.session import GameSession
from src.database.models.world import WorldEvent
from src.managers.base import BaseManager

if TYPE_CHECKING:
    from src.managers.time_manager import TimeManager


class EventManager(BaseManager):
    """Manager for world event operations.

    Handles:
    - Event creation and tracking
    - Event queries by type, location, day
    - Event processing status
    - Player knowledge management
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
            time_manager: Optional TimeManager for current day lookups.
        """
        super().__init__(db, game_session)
        self.time_manager = time_manager

    def create_event(
        self,
        event_type: str,
        summary: str,
        details: dict | None = None,
        location_key: str | None = None,
        affected_entities: list[str] | None = None,
        is_known_to_player: bool = False,
    ) -> WorldEvent:
        """Create new world event.

        Args:
            event_type: Type of event (robbery, weather_change, etc.).
            summary: Brief description.
            details: Optional detailed event data as JSON.
            location_key: Optional location key.
            affected_entities: Optional list of affected entity keys.
            is_known_to_player: Whether player knows about event.

        Returns:
            Created WorldEvent.
        """
        # Get current day from TimeManager if available
        game_day = 1
        if self.time_manager is not None:
            game_day, _ = self.time_manager.get_current_time()

        event = WorldEvent(
            session_id=self.session_id,
            event_type=event_type,
            summary=summary,
            details=details,
            location_key=location_key,
            affected_entities=affected_entities,
            is_known_to_player=is_known_to_player,
            is_processed=False,
            game_day=game_day,
            turn_created=self.current_turn,
        )
        self.db.add(event)
        self.db.flush()
        return event

    def get_event(self, event_id: int) -> WorldEvent | None:
        """Get event by ID.

        Args:
            event_id: Event ID.

        Returns:
            WorldEvent if found, None otherwise.
        """
        return (
            self.db.query(WorldEvent)
            .filter(
                WorldEvent.session_id == self.session_id,
                WorldEvent.id == event_id,
            )
            .first()
        )

    def get_unprocessed_events(self) -> list[WorldEvent]:
        """Get all unprocessed events.

        Returns:
            List of unprocessed WorldEvents.
        """
        return (
            self.db.query(WorldEvent)
            .filter(
                WorldEvent.session_id == self.session_id,
                WorldEvent.is_processed == False,
            )
            .all()
        )

    def mark_processed(self, event_id: int) -> WorldEvent:
        """Mark event as processed.

        Args:
            event_id: Event ID.

        Returns:
            Updated WorldEvent.

        Raises:
            ValueError: If event not found.
        """
        event = self.get_event(event_id)
        if event is None:
            raise ValueError(f"Event not found: {event_id}")

        event.is_processed = True
        self.db.flush()
        return event

    def get_events_at_location(
        self, location_key: str, include_processed: bool = False
    ) -> list[WorldEvent]:
        """Get events at a location.

        Args:
            location_key: Location key.
            include_processed: Whether to include processed events.

        Returns:
            List of WorldEvents at the location.
        """
        query = self.db.query(WorldEvent).filter(
            WorldEvent.session_id == self.session_id,
            WorldEvent.location_key == location_key,
        )

        if not include_processed:
            query = query.filter(WorldEvent.is_processed == False)

        return query.all()

    def get_events_by_type(self, event_type: str) -> list[WorldEvent]:
        """Get events of a specific type.

        Args:
            event_type: Event type to filter by.

        Returns:
            List of WorldEvents of the type.
        """
        return (
            self.db.query(WorldEvent)
            .filter(
                WorldEvent.session_id == self.session_id,
                WorldEvent.event_type == event_type,
            )
            .all()
        )

    def get_recent_events(
        self, limit: int = 10, known_only: bool = True
    ) -> list[WorldEvent]:
        """Get recent events (for context).

        Args:
            limit: Maximum number of events to return.
            known_only: Whether to only return events known to player.

        Returns:
            List of recent WorldEvents.
        """
        query = self.db.query(WorldEvent).filter(
            WorldEvent.session_id == self.session_id,
        )

        if known_only:
            query = query.filter(WorldEvent.is_known_to_player == True)

        return query.order_by(WorldEvent.turn_created.desc()).limit(limit).all()

    def reveal_event(self, event_id: int) -> WorldEvent:
        """Make event known to player.

        Args:
            event_id: Event ID.

        Returns:
            Updated WorldEvent.

        Raises:
            ValueError: If event not found.
        """
        event = self.get_event(event_id)
        if event is None:
            raise ValueError(f"Event not found: {event_id}")

        event.is_known_to_player = True
        event.discovery_turn = self.current_turn
        self.db.flush()
        return event

    def get_events_affecting_entity(self, entity_key: str) -> list[WorldEvent]:
        """Get events that affected an entity.

        Args:
            entity_key: Entity key.

        Returns:
            List of WorldEvents affecting the entity.
        """
        # Query events where affected_entities JSON contains the key
        all_events = (
            self.db.query(WorldEvent)
            .filter(
                WorldEvent.session_id == self.session_id,
                WorldEvent.affected_entities.isnot(None),
            )
            .all()
        )

        # Filter in Python since JSON array contains is database-specific
        return [
            e for e in all_events
            if e.affected_entities and entity_key in e.affected_entities
        ]

    def get_events_on_day(self, game_day: int) -> list[WorldEvent]:
        """Get all events on a specific day.

        Args:
            game_day: Game day number.

        Returns:
            List of WorldEvents on that day.
        """
        return (
            self.db.query(WorldEvent)
            .filter(
                WorldEvent.session_id == self.session_id,
                WorldEvent.game_day == game_day,
            )
            .all()
        )
