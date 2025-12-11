"""World state models (locations, schedules, facts, events)."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base, TimestampMixin
from src.database.models.enums import DayOfWeek, FactCategory

if TYPE_CHECKING:
    from src.database.models.entities import Entity
    from src.database.models.session import GameSession


class Location(Base, TimestampMixin):
    """A location in the game world."""

    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Identity
    location_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Unique key (e.g., 'tavern_main_room')",
    )
    display_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full description of the location",
    )

    # Hierarchy
    parent_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
    )
    category: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="city, building, room, wilderness, etc.",
    )

    # Atmosphere
    atmosphere: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Mood, lighting, sounds, smells",
    )
    typical_crowd: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Who's usually here",
    )

    # State
    is_accessible: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    access_requirements: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Key needed, permission required, etc.",
    )

    # Dynamic state (what's changed since last visit)
    current_state_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Current state changes",
    )
    last_visited_turn: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    # Consistency tracking (new)
    canonical_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Saved on first visit. Layout never changes unless event explains it.",
    )
    first_visited_turn: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Turn when player first visited (locks canonical description)",
    )
    state_history: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="History of changes: [{turn: X, change: 'description', reason: 'why'}]",
    )
    spatial_layout: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Room connections, passages, exits - never changes unless event explains",
    )

    # Relationships
    parent_location: Mapped["Location | None"] = relationship(
        remote_side="Location.id",
        foreign_keys=[parent_location_id],
    )

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("session_id", "location_key", name="uq_location_session_key"),
    )

    def __repr__(self) -> str:
        return f"<Location {self.location_key}>"


class Schedule(Base):
    """NPC schedule entry (rule-based positioning)."""

    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # When
    day_pattern: Mapped[DayOfWeek] = mapped_column(
        Enum(DayOfWeek, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        comment="monday, weekday, weekend, daily, etc.",
    )
    start_time: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        comment="HH:MM",
    )
    end_time: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        comment="HH:MM",
    )

    # What and where
    activity: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="What they're doing",
    )
    location_key: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Where they are (location key)",
    )

    # Priority for overlaps
    priority: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="Higher priority wins when schedules overlap",
    )

    # Relationships
    entity: Mapped["Entity"] = relationship(
        back_populates="schedules",
        foreign_keys=[entity_id],
    )

    def __repr__(self) -> str:
        return f"<Schedule {self.day_pattern.value} {self.start_time}-{self.end_time}: {self.activity}>"


class TimeState(Base, TimestampMixin):
    """Tracks in-game time for a session."""

    __tablename__ = "time_states"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Time
    current_day: Mapped[int] = mapped_column(
        default=1,
        nullable=False,
        comment="In-game day number",
    )
    current_time: Mapped[str] = mapped_column(
        String(5),
        default="08:00",
        nullable=False,
        comment="HH:MM",
    )
    day_of_week: Mapped[str] = mapped_column(
        String(10),
        default="monday",
        nullable=False,
    )

    # Calendar (optional)
    year: Mapped[int] = mapped_column(default=1, nullable=False)
    month: Mapped[int] = mapped_column(default=1, nullable=False)
    season: Mapped[str] = mapped_column(
        String(20),
        default="spring",
        nullable=False,
    )

    # Environment
    weather: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Current weather",
    )
    temperature: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Temperature description",
    )

    def __repr__(self) -> str:
        return f"<TimeState Day {self.current_day} {self.current_time}>"


class Fact(Base):
    """SPV (Subject-Predicate-Value) fact store."""

    __tablename__ = "facts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Subject-Predicate-Value
    subject_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="entity, location, world, item, group",
    )
    subject_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Key of the subject",
    )
    predicate: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="What aspect (job, allergic_to, likes, etc.)",
    )
    value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="The value",
    )

    # Metadata
    category: Mapped[FactCategory] = mapped_column(
        Enum(FactCategory, values_callable=lambda obj: [e.value for e in obj]),
        default=FactCategory.PERSONAL,
        nullable=False,
    )
    confidence: Mapped[int] = mapped_column(
        default=80,
        nullable=False,
        comment="0-100 confidence in this fact",
    )
    is_secret: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="GM knows, player doesn't",
    )

    # What player believes (if different from actual value)
    player_believes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="What player thinks is true (if different)",
    )

    # Story/narrative flags
    is_foreshadowing: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Hint planted for future payoff (AI tracks these)",
    )
    foreshadow_target: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="What this foreshadows (for AI reference)",
    )
    times_mentioned: Mapped[int] = mapped_column(
        default=1,
        nullable=False,
        comment="Rule of three: mention hints in 3 contexts before payoff",
    )

    # Tracking
    source_turn: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
        comment="Turn when fact was recorded",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        secret = " [SECRET]" if self.is_secret else ""
        return f"<Fact {self.subject_key}.{self.predicate}={self.value[:20]}{secret}>"


class WorldEvent(Base):
    """AI-driven dynamic world events."""

    __tablename__ = "world_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Event details
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="robbery, weather_change, npc_mood, discovery, etc.",
    )
    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Brief description",
    )
    details: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Detailed event data",
    )

    # When and where
    game_day: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
    )
    game_time: Mapped[str | None] = mapped_column(
        String(5),
        nullable=True,
    )
    location_key: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    # Affected entities
    affected_entities: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="List of affected entity keys",
    )

    # Player awareness
    is_known_to_player: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    discovery_turn: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Turn when player discovered this",
    )

    # Processing
    is_processed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Has this event been processed?",
    )
    turn_created: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        known = "" if self.is_known_to_player else " [HIDDEN]"
        return f"<WorldEvent {self.event_type}: {self.summary[:30]}{known}>"


class LocationVisit(Base, TimestampMixin):
    """Track player visits to locations for change detection.

    Stores a snapshot of who/what was at a location when the player last visited,
    allowing the game to describe what changed since then.
    """

    __tablename__ = "location_visits"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Which location
    location_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Key of the visited location",
    )

    # When the player was last there
    last_visit_turn: Mapped[int] = mapped_column(
        nullable=False,
        comment="Turn number of the last visit",
    )
    last_visit_time: Mapped[str | None] = mapped_column(
        String(5),
        nullable=True,
        comment="In-game time of the last visit (HH:MM)",
    )
    last_visit_day: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="In-game day of the last visit",
    )

    # Snapshot of who/what was there
    items_snapshot: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="List of item keys present at last visit",
    )
    npcs_snapshot: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="List of NPC entity keys present at last visit",
    )

    # Constraint: one record per location per session
    __table_args__ = (
        UniqueConstraint(
            "session_id", "location_key", name="uq_location_visit_session_location"
        ),
    )

    def __repr__(self) -> str:
        return f"<LocationVisit {self.location_key} turn={self.last_visit_turn}>"
