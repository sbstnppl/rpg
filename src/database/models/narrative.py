"""Narrative system models for story arcs, mysteries, and conflicts."""

from datetime import datetime
from enum import Enum as PyEnum
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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.database.models.entities import Entity
    from src.database.models.session import GameSession


class ArcType(str, PyEnum):
    """Types of story arcs."""

    MAIN_QUEST = "main_quest"
    SIDE_QUEST = "side_quest"
    ROMANCE = "romance"
    REVENGE = "revenge"
    REDEMPTION = "redemption"
    MYSTERY = "mystery"
    RIVALRY = "rivalry"
    MENTORSHIP = "mentorship"
    BETRAYAL = "betrayal"
    SURVIVAL = "survival"
    DISCOVERY = "discovery"
    POLITICAL = "political"


class ArcPhase(str, PyEnum):
    """Narrative phases following classic story structure."""

    SETUP = "setup"  # Introduction, establishing normal world
    RISING_ACTION = "rising_action"  # Complications, obstacles
    MIDPOINT = "midpoint"  # Major revelation or turning point
    ESCALATION = "escalation"  # Stakes increase, complications deepen
    CLIMAX = "climax"  # Final confrontation or peak moment
    FALLING_ACTION = "falling_action"  # Immediate aftermath
    RESOLUTION = "resolution"  # New normal, wrap-up
    AFTERMATH = "aftermath"  # Long-term consequences


class ArcStatus(str, PyEnum):
    """Status of a story arc."""

    DORMANT = "dormant"  # Not yet activated
    ACTIVE = "active"  # Currently unfolding
    PAUSED = "paused"  # Temporarily on hold
    COMPLETED = "completed"  # Successfully resolved
    FAILED = "failed"  # Failed or abandoned
    ABANDONED = "abandoned"  # Player chose to abandon


class StoryArc(Base, TimestampMixin):
    """A narrative arc tracking story structure and progression.

    Story arcs provide dramatic structure by tracking:
    - Current phase (setup -> climax -> resolution)
    - Tension level (0-100)
    - Planted narrative elements (Chekhov's guns)
    - Pacing hints for the GM
    """

    __tablename__ = "story_arcs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Arc identification
    arc_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Unique key (e.g., 'main_quest', 'romance_elara')",
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Human-readable title",
    )
    arc_type: Mapped[ArcType] = mapped_column(
        Enum(ArcType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Overview of the arc",
    )

    # Narrative state
    status: Mapped[ArcStatus] = mapped_column(
        Enum(ArcStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=ArcStatus.DORMANT,
        nullable=False,
    )
    current_phase: Mapped[ArcPhase] = mapped_column(
        Enum(ArcPhase, values_callable=lambda obj: [e.value for e in obj]),
        default=ArcPhase.SETUP,
        nullable=False,
    )
    tension_level: Mapped[int] = mapped_column(
        Integer,
        default=10,
        nullable=False,
        comment="Current tension 0-100",
    )

    # Phase tracking
    phase_started_turn: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Turn when current phase began",
    )
    turns_in_phase: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="Turns spent in current phase",
    )

    # Narrative elements
    planted_elements: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Chekhov's guns - elements that must pay off",
    )
    resolved_elements: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Elements that have paid off",
    )

    # GM guidance
    next_beat_hint: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Suggestion for next narrative beat",
    )
    stakes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="What's at stake in this arc",
    )

    # Related entities
    protagonist_id: Mapped[int | None] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"),
        nullable=True,
        comment="Main character driving this arc",
    )
    antagonist_id: Mapped[int | None] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"),
        nullable=True,
        comment="Opposing force in this arc",
    )

    # Completion
    started_turn: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Turn when arc became active",
    )
    completed_turn: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Turn when arc completed",
    )
    outcome: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="How the arc resolved",
    )

    # Priority for attention
    priority: Mapped[int] = mapped_column(
        default=5,
        nullable=False,
        comment="1-10, higher = more important",
    )

    # Relationships
    session: Mapped["GameSession"] = relationship(back_populates="story_arcs")
    protagonist: Mapped["Entity | None"] = relationship(
        foreign_keys=[protagonist_id],
    )
    antagonist: Mapped["Entity | None"] = relationship(
        foreign_keys=[antagonist_id],
    )

    def __repr__(self) -> str:
        return f"<StoryArc {self.arc_key} [{self.status.value}] phase={self.current_phase.value} tension={self.tension_level}>"


class Mystery(Base, TimestampMixin):
    """A mystery to be discovered by the player.

    Mysteries create engagement through:
    - A hidden truth to uncover
    - Clues that can be discovered
    - Red herrings to mislead
    - Revelation conditions
    """

    __tablename__ = "mysteries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Mystery identification
    mystery_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Unique key (e.g., 'who_killed_mayor')",
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Human-readable title",
    )

    # The truth
    truth: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="What actually happened (GM only)",
    )
    truth_summary: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Short summary for context",
    )

    # Clues and misdirection
    clues: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="List of clue objects with discovery status",
    )
    red_herrings: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="False leads to consider",
    )
    clues_discovered: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="Number of clues found",
    )
    total_clues: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="Total clues available",
    )

    # Revelation
    revelation_conditions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="What must happen for truth to be revealed",
    )
    is_solved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    solved_turn: Mapped[int | None] = mapped_column(
        nullable=True,
    )
    player_theory: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="What the player currently believes",
    )

    # Related arc
    story_arc_id: Mapped[int | None] = mapped_column(
        ForeignKey("story_arcs.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Creation tracking
    created_turn: Mapped[int] = mapped_column(nullable=False, default=1)

    # Relationships
    session: Mapped["GameSession"] = relationship(back_populates="mysteries")
    story_arc: Mapped["StoryArc | None"] = relationship()

    def __repr__(self) -> str:
        status = "SOLVED" if self.is_solved else f"{self.clues_discovered}/{self.total_clues} clues"
        return f"<Mystery {self.mystery_key} [{status}]>"


class ConflictLevel(str, PyEnum):
    """Escalation levels for conflicts."""

    TENSION = "tension"  # Underlying friction
    DISPUTE = "dispute"  # Open disagreement
    CONFRONTATION = "confrontation"  # Direct opposition
    HOSTILITY = "hostility"  # Active antagonism
    CRISIS = "crisis"  # Critical breaking point
    WAR = "war"  # Full-scale conflict


class Conflict(Base, TimestampMixin):
    """A conflict that can escalate or de-escalate.

    Conflicts drive drama by:
    - Tracking escalation levels
    - Defining triggers for escalation/de-escalation
    - Suggesting interventions
    """

    __tablename__ = "conflicts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Conflict identification
    conflict_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Unique key (e.g., 'guild_war', 'family_feud')",
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Parties involved
    party_a_key: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Entity/faction key for first party",
    )
    party_b_key: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Entity/faction key for second party",
    )

    # Escalation state
    current_level: Mapped[ConflictLevel] = mapped_column(
        Enum(ConflictLevel, values_callable=lambda obj: [e.value for e in obj]),
        default=ConflictLevel.TENSION,
        nullable=False,
    )
    level_numeric: Mapped[int] = mapped_column(
        default=1,
        nullable=False,
        comment="Numeric level 1-6 for comparison",
    )

    # Triggers
    escalation_triggers: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Conditions that escalate conflict",
    )
    de_escalation_triggers: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Conditions that reduce tension",
    )

    # Level descriptions
    level_descriptions: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Description of what each level looks like",
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_resolved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    resolution: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="How conflict was resolved",
    )

    # Timing
    started_turn: Mapped[int] = mapped_column(nullable=False, default=1)
    last_escalation_turn: Mapped[int | None] = mapped_column(nullable=True)
    resolved_turn: Mapped[int | None] = mapped_column(nullable=True)

    # Related arc
    story_arc_id: Mapped[int | None] = mapped_column(
        ForeignKey("story_arcs.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    session: Mapped["GameSession"] = relationship(back_populates="conflicts")
    story_arc: Mapped["StoryArc | None"] = relationship()

    def __repr__(self) -> str:
        status = "resolved" if self.is_resolved else self.current_level.value
        return f"<Conflict {self.conflict_key} [{status}]>"
