"""Game session and turn models."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.database.models.destiny import DestinyElement, Prophesy
    from src.database.models.entities import Entity
    from src.database.models.faction import Faction
    from src.database.models.goals import NPCGoal
    from src.database.models.magic import EntityMagicProfile, SpellCastRecord, SpellDefinition
    from src.database.models.narrative import Conflict, Mystery, StoryArc
    from src.database.models.progression import Achievement
    from src.database.models.snapshots import SessionSnapshot
    from src.database.models.tasks import Appointment, Quest, Task


class SessionStatus(str):
    """Session status values."""

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class GameSession(Base, TimestampMixin):
    """An RPG game session."""

    __tablename__ = "game_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Identity
    session_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    setting: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="fantasy",
        comment="Setting type: fantasy, contemporary, scifi, custom",
    )

    # Player character reference
    player_entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )

    # State
    status: Mapped[str] = mapped_column(
        String(20),
        default=SessionStatus.ACTIVE,
        nullable=False,
    )
    total_turns: Mapped[int] = mapped_column(default=0, nullable=False)

    # LLM configuration
    llm_provider: Mapped[str] = mapped_column(
        String(20),
        default="anthropic",
        nullable=False,
        comment="LLM provider: anthropic, openai",
    )
    gm_model: Mapped[str] = mapped_column(
        String(100),
        default="claude-sonnet-4-20250514",
        nullable=False,
    )

    # Attribute schema (setting-dependent)
    attribute_schema: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Attribute definitions for this session's setting",
    )

    # Equipment slot schema
    equipment_slots: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Available equipment slots for this setting",
    )

    # Session context (mutable state snapshot)
    session_context: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Current session state summary",
    )

    # Timestamps
    last_activity: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    turns: Mapped[list["Turn"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    entities: Mapped[list["Entity"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        foreign_keys="Entity.session_id",
    )
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    quests: Mapped[list["Quest"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    npc_goals: Mapped[list["NPCGoal"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    story_arcs: Mapped[list["StoryArc"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    mysteries: Mapped[list["Mystery"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    conflicts: Mapped[list["Conflict"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    achievements: Mapped[list["Achievement"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    factions: Mapped[list["Faction"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    spell_definitions: Mapped[list["SpellDefinition"]] = relationship(
        back_populates="game_session",
        cascade="all, delete-orphan",
    )
    entity_magic_profiles: Mapped[list["EntityMagicProfile"]] = relationship(
        back_populates="game_session",
        cascade="all, delete-orphan",
    )
    spell_cast_records: Mapped[list["SpellCastRecord"]] = relationship(
        back_populates="game_session",
        cascade="all, delete-orphan",
    )
    prophesies: Mapped[list["Prophesy"]] = relationship(
        back_populates="game_session",
        cascade="all, delete-orphan",
    )
    destiny_elements: Mapped[list["DestinyElement"]] = relationship(
        back_populates="game_session",
        cascade="all, delete-orphan",
    )
    snapshots: Mapped[list["SessionSnapshot"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<GameSession {self.id}: {self.session_name or 'Unnamed'} ({self.setting})>"


class Turn(Base):
    """A single conversation turn (immutable)."""

    __tablename__ = "turns"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    turn_number: Mapped[int] = mapped_column(nullable=False, index=True)

    # Input/Output
    player_input: Mapped[str] = mapped_column(Text, nullable=False)
    gm_response: Mapped[str] = mapped_column(Text, nullable=False)

    # NPC dialogues extracted
    npc_dialogues: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="[{npc: name, dialogue: text, emotion: mood}]",
    )

    # Context snapshot at this turn
    location_at_turn: Mapped[str | None] = mapped_column(String(100), nullable=True)
    npcs_present_at_turn: Mapped[list | None] = mapped_column(JSON, nullable=True)
    game_day_at_turn: Mapped[int | None] = mapped_column(nullable=True)
    game_time_at_turn: Mapped[str | None] = mapped_column(String(5), nullable=True)

    # Extraction results
    entities_extracted: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Entities extracted by EntityExtractor agent",
    )
    world_events_generated: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="World events generated this turn",
    )

    # Deferred items (mentioned in narrative but not spawned yet)
    # For on-demand spawning when player references them later
    mentioned_items: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="[{name, context, location}] - decorative items for deferred spawn",
    )

    # Deferred NPCs (mentioned in narrative but not spawned yet)
    # For on-demand spawning when player interacts with them later
    mentioned_npcs: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="[{name, description, context, location}] - background NPCs for deferred spawn",
    )

    # Chained subturn metadata (hidden from player, for debugging/analytics)
    subturn_metadata: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="[{index, action, execution, complication, state_after}] - subturn details",
    )

    # Queued actions from OFFER_CHOICE continuation (for next turn)
    queued_actions: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Remaining actions for player choice continuation",
    )

    # Timestamp (immutable)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    session: Mapped["GameSession"] = relationship(back_populates="turns")

    def __repr__(self) -> str:
        return f"<Turn {self.session_id}:{self.turn_number}>"
