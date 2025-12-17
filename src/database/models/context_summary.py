"""Context summary models for layered narrative context.

This module provides models for:
- Milestone: Significant story events that trigger summary regeneration
- ContextSummary: LLM-generated summaries at different time scales
- NarrativeMentionLog: Tracks what was mentioned to prevent repetition
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
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

if TYPE_CHECKING:
    from src.database.models.session import GameSession


class MilestoneType(str, PyEnum):
    """Types of story milestones that trigger summary regeneration."""

    ARC_PHASE_CHANGE = "arc_phase_change"  # Story arc moved to new phase
    QUEST_COMPLETE = "quest_complete"  # Quest finished
    MYSTERY_SOLVED = "mystery_solved"  # Mystery revealed
    MAJOR_RELATIONSHIP = "major_relationship"  # Significant relationship change
    REGION_TRANSITION = "region_transition"  # Major location change
    CONFLICT_RESOLUTION = "conflict_resolution"  # Conflict resolved/escalated
    MAJOR_DISCOVERY = "major_discovery"  # Significant item/info found
    CHARACTER_DEVELOPMENT = "character_development"  # Player leveled up, gained skill


class Milestone(Base, TimestampMixin):
    """A significant story event that triggers summary regeneration.

    Milestones mark points in the narrative where the story summary
    should be updated. They provide natural chapter-like divisions
    in the ongoing narrative.
    """

    __tablename__ = "milestones"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Milestone identification
    milestone_type: Mapped[MilestoneType] = mapped_column(
        Enum(MilestoneType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Brief description of what happened at this milestone",
    )

    # Timing
    turn_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="Turn number when milestone occurred",
    )
    game_day: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="In-game day when milestone occurred",
    )
    game_time: Mapped[str | None] = mapped_column(
        String(5),
        nullable=True,
        comment="In-game time (HH:MM) when milestone occurred",
    )

    # Related entity for context
    related_entity_key: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Key of related entity (quest_key, arc_key, etc.)",
    )

    # Relationships
    session: Mapped["GameSession"] = relationship()

    def __repr__(self) -> str:
        return (
            f"<Milestone {self.milestone_type.value} "
            f"turn={self.turn_number} day={self.game_day}>"
        )


class SummaryType(str, PyEnum):
    """Types of context summaries."""

    STORY = "story"  # From start to last milestone
    RECENT = "recent"  # From last milestone to last night


class ContextSummary(Base, TimestampMixin):
    """LLM-generated summary of story events at different time scales.

    Summaries are cached in the database to avoid regenerating them
    every turn. They are regenerated when:
    - Story summary: At each milestone
    - Recent summary: At the start of each in-game day
    """

    __tablename__ = "context_summaries"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "summary_type",
            name="uq_context_summary_session_type"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Summary identification
    summary_type: Mapped[SummaryType] = mapped_column(
        Enum(SummaryType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )

    # Content
    summary_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="The generated summary text",
    )

    # Generation metadata
    generated_at_turn: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Turn when this summary was generated",
    )
    generated_at_day: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="In-game day when this summary was generated",
    )

    # Coverage
    covers_through_turn: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Last turn number included in this summary",
    )
    covers_through_day: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Last in-game day included in this summary",
    )

    # Milestone reference (for story summary)
    milestone_id: Mapped[int | None] = mapped_column(
        ForeignKey("milestones.id", ondelete="SET NULL"),
        nullable=True,
        comment="Last milestone covered by this summary",
    )

    # Extracted key elements (for context/reference)
    key_characters: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Key characters mentioned in summary",
    )
    key_decisions: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Key player decisions captured",
    )
    current_objectives: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Current active objectives/quests",
    )

    # Token tracking for budget management
    token_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Approximate token count of summary",
    )

    # Relationships
    session: Mapped["GameSession"] = relationship()
    milestone: Mapped["Milestone | None"] = relationship()

    def __repr__(self) -> str:
        return (
            f"<ContextSummary {self.summary_type.value} "
            f"through_turn={self.covers_through_turn} "
            f"through_day={self.covers_through_day}>"
        )


class NarrativeMentionLog(Base, TimestampMixin):
    """Tracks when stable conditions were last mentioned in narrative.

    This enables signal-based narration for stable conditions:
    - Track when player's appearance/condition was described
    - Prevent repetitive descriptions every turn
    - Allow periodic reminders for ongoing states

    Similar pattern to NeedsCommunicationLog but for narrative elements.
    """

    __tablename__ = "narrative_mention_log"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "mention_type", "subject_key",
            name="uq_narrative_mention_session_type_subject"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # What was mentioned
    mention_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type of mention: need_state, injury, equipment, relationship, etc.",
    )
    subject_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Subject of mention: entity_key, need_name, item_key, etc.",
    )
    mention_value: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="The specific value/state mentioned: 'disheveled', 'tired', etc.",
    )

    # When was it mentioned
    mentioned_turn: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="Turn number when this was mentioned",
    )
    mentioned_game_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        comment="In-game datetime when this was mentioned",
    )

    # Relationships
    session: Mapped["GameSession"] = relationship()

    def __repr__(self) -> str:
        return (
            f"<NarrativeMentionLog {self.mention_type}:{self.subject_key}="
            f"'{self.mention_value}' turn={self.mentioned_turn}>"
        )
