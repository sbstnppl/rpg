"""Mental health and grief condition models."""

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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base, TimestampMixin
from src.database.models.enums import GriefStage, MentalConditionType

if TYPE_CHECKING:
    from src.database.models.entities import Entity
    from src.database.models.session import GameSession


class MentalCondition(Base, TimestampMixin):
    """Long-term mental health conditions (PTSD, phobias, depression, etc.)."""

    __tablename__ = "mental_conditions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Condition details
    condition_type: Mapped[MentalConditionType] = mapped_column(
        Enum(MentalConditionType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        comment="PTSD, depression, phobia, anxiety, etc.",
    )
    severity: Mapped[int] = mapped_column(
        default=50,
        nullable=False,
        comment="0-100 severity (affects intensity of symptoms)",
    )
    is_permanent: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        comment="If true, can only be managed, not cured",
    )
    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
        comment="Currently affecting the character",
    )

    # Triggers (for PTSD, phobias)
    trigger_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="What triggers this condition (spiders, loud noises, combat, etc.)",
    )
    triggers: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Structured trigger conditions for AI to check",
    )

    # Effects when active/triggered
    stat_penalties: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Attribute penalties: {morale: -20, WIS: -2, all_checks: -3}",
    )
    behavioral_effects: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Behavior changes: {flee_impulse: 0.7, panic_chance: 0.3}",
    )

    # Lifecycle
    acquired_turn: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
    )
    acquired_reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="What caused this condition",
    )
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Treatment progress
    can_be_treated: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )
    treatment_progress: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="0-100 progress toward recovery",
    )
    treatment_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Treatment history and methods used",
    )

    # Resolution
    resolved_turn: Mapped[int | None] = mapped_column(nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    entity: Mapped["Entity"] = relationship(foreign_keys=[entity_id])

    def __repr__(self) -> str:
        perm = " [PERMANENT]" if self.is_permanent else ""
        active = "" if self.is_active else " [INACTIVE]"
        return (
            f"<MentalCondition {self.condition_type.value} "
            f"severity={self.severity}{perm}{active}>"
        )


class GriefCondition(Base, TimestampMixin):
    """Tracks grief progression when an NPC loses someone they cared about."""

    __tablename__ = "grief_conditions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    deceased_entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Current grief stage (Kübler-Ross)
    grief_stage: Mapped[GriefStage] = mapped_column(
        Enum(GriefStage, values_callable=lambda obj: [e.value for e in obj]),
        default=GriefStage.SHOCK,
        nullable=False,
        comment="shock, denial, anger, bargaining, depression, acceptance",
    )
    intensity: Mapped[int] = mapped_column(
        default=50,
        nullable=False,
        comment="0-100 intensity (based on relationship strength)",
    )

    # Timeline
    started_turn: Mapped[int] = mapped_column(nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    current_stage_started_turn: Mapped[int] = mapped_column(nullable=False)
    expected_duration_days: Mapped[int] = mapped_column(
        nullable=False,
        comment="Total expected grief duration based on intensity",
    )

    # Effects on behavior
    morale_modifier: Mapped[int] = mapped_column(
        default=-20,
        nullable=False,
        comment="Applied to morale while grieving",
    )
    behavioral_changes: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Stage-specific behavior changes",
    )

    # Additional context
    blames_someone: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    blamed_entity_key: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Who they blame for the death (if anyone)",
    )

    # Resolution
    is_resolved: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    resolved_turn: Mapped[int | None] = mapped_column(nullable=True)

    # Relationships
    entity: Mapped["Entity"] = relationship(
        foreign_keys=[entity_id],
        primaryjoin="GriefCondition.entity_id == Entity.id",
    )
    deceased_entity: Mapped["Entity"] = relationship(
        foreign_keys=[deceased_entity_id],
        primaryjoin="GriefCondition.deceased_entity_id == Entity.id",
    )

    def __repr__(self) -> str:
        resolved = " [RESOLVED]" if self.is_resolved else ""
        return (
            f"<GriefCondition entity={self.entity_id} "
            f"for={self.deceased_entity_id} stage={self.grief_stage.value}{resolved}>"
        )
