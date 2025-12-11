"""Relationship arc models.

Tracks narrative arcs between characters (e.g., enemies-to-lovers,
betrayal, redemption). Each arc has phases with milestones and
suggested dramatic beats.

Arc types can be either predefined (using WellKnownArcType) or
LLM-generated custom arcs stored in arc_template.
"""

from enum import Enum

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base


class WellKnownArcType(str, Enum):
    """Well-known relationship arc types (for reference/fallback).

    These are predefined arc types that can be used as examples or fallbacks.
    Custom LLM-generated arc types are stored as plain strings in arc_type.
    """

    ENEMIES_TO_LOVERS = "enemies_to_lovers"
    MENTORS_FALL = "mentors_fall"
    BETRAYAL = "betrayal"
    REDEMPTION = "redemption"
    RIVALRY = "rivalry"
    FOUND_FAMILY = "found_family"
    LOST_LOVE_REKINDLED = "lost_love_rekindled"
    CORRUPTION = "corruption"


# Keep old name as alias for backward compatibility
RelationshipArcType = WellKnownArcType


class RelationshipArcPhase(str, Enum):
    """Phases of a relationship arc."""

    INTRODUCTION = "introduction"
    DEVELOPMENT = "development"
    CRISIS = "crisis"
    CLIMAX = "climax"
    RESOLUTION = "resolution"


class RelationshipArc(Base):
    """A narrative arc tracking relationship development.

    Relationship arcs provide scaffolding for dramatic storytelling,
    suggesting beats and milestones while tracking progress through
    narrative phases. Arcs serve as GM GUIDANCE (inspiration, not script) -
    player actions always determine actual outcomes.

    Arc types can be predefined (WellKnownArcType) or custom LLM-generated
    types stored as strings with their full template in arc_template.

    Attributes:
        arc_key: Unique identifier for the arc within session.
        arc_type: Type of arc - either a WellKnownArcType or custom LLM-generated type.
        arc_template: LLM-generated template with phases, milestones, etc. (None for predefined).
        arc_description: Description of what this arc represents.
        entity1_key: First entity (usually the player).
        entity2_key: Second entity (usually an NPC).
        current_phase: Current phase of the arc (flexible string, not enum).
        phase_progress: Progress within current phase (0-100).
        milestones_hit: List of achieved milestone keys.
        suggested_next_beat: Hint for GM about next dramatic moment.
        arc_tension: Current dramatic tension level (0-100).
        is_active: Whether the arc is still in progress.
        started_turn: When the arc began.
        completed_turn: When the arc ended (if completed).
    """

    __tablename__ = "relationship_arcs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("game_sessions.id"), nullable=False, index=True
    )
    arc_key: Mapped[str] = mapped_column(String(100), nullable=False)
    # arc_type can be a WellKnownArcType value or a custom LLM-generated type name
    arc_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # arc_template stores the full LLM-generated template (phases, milestones, etc.)
    # If None, uses predefined templates from ARC_TEMPLATES in the manager
    arc_template: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="LLM-generated arc template with phases and milestones"
    )
    arc_description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Description of what this arc represents"
    )
    entity1_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity2_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    current_phase: Mapped[str] = mapped_column(
        String(50), nullable=False, default="introduction"
    )
    phase_progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    milestones_hit: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    suggested_next_beat: Mapped[str | None] = mapped_column(String(500), nullable=True)
    arc_tension: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    started_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("session_id", "arc_key", name="uq_relationship_arc_session_key"),
    )
