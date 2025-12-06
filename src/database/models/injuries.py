"""Injury and body state models."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base, TimestampMixin
from src.database.models.enums import BodyPart, InjurySeverity, InjuryType

if TYPE_CHECKING:
    from src.database.models.entities import Entity
    from src.database.models.session import GameSession


class BodyInjury(Base, TimestampMixin):
    """Tracks injuries to specific body parts."""

    __tablename__ = "body_injuries"

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

    # Injury details
    body_part: Mapped[BodyPart] = mapped_column(
        Enum(BodyPart, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        comment="Body part affected",
    )
    injury_type: Mapped[InjuryType] = mapped_column(
        Enum(InjuryType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        comment="bruise, cut, fracture, sprain, etc.",
    )
    severity: Mapped[InjurySeverity] = mapped_column(
        Enum(InjurySeverity, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        comment="minor, moderate, severe, critical",
    )

    # Cause
    caused_by: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="What caused this injury",
    )
    occurred_turn: Mapped[int] = mapped_column(nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Medical care
    received_medical_care: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    medical_care_quality: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="0-100, affects recovery time",
    )
    medical_care_turn: Mapped[int | None] = mapped_column(nullable=True)

    # Recovery
    base_recovery_days: Mapped[int] = mapped_column(
        nullable=False,
        comment="Base recovery time without modifiers",
    )
    adjusted_recovery_days: Mapped[float] = mapped_column(
        nullable=False,
        comment="Recovery time after modifiers applied",
    )
    recovery_progress_days: Mapped[float] = mapped_column(
        default=0.0,
        nullable=False,
        comment="Days of healing completed",
    )
    is_healed: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    healed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    healed_turn: Mapped[int | None] = mapped_column(nullable=True)

    # Complications
    is_infected: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    is_reinjured: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        comment="If true, recovery time increased by 50%",
    )
    has_permanent_damage: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    permanent_damage_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Chronic pain, reduced mobility, scarring, etc.",
    )

    # Pain
    current_pain_level: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="0-100, contributes to pain need",
    )

    # Activity restrictions (cached JSON for performance)
    activity_restrictions: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Cached impact matrix for this injury",
    )

    # Relationships
    entity: Mapped["Entity"] = relationship(foreign_keys=[entity_id])

    def __repr__(self) -> str:
        healed = " [HEALED]" if self.is_healed else ""
        return (
            f"<BodyInjury {self.body_part.value} "
            f"{self.injury_type.value} ({self.severity.value}){healed}>"
        )


class ActivityRestriction(Base):
    """Pre-computed activity restrictions for quick lookup."""

    __tablename__ = "activity_restrictions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Key combination
    body_part: Mapped[BodyPart] = mapped_column(
        Enum(BodyPart, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    injury_type: Mapped[InjuryType] = mapped_column(
        Enum(InjuryType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    severity: Mapped[InjurySeverity] = mapped_column(
        Enum(InjurySeverity, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    activity_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="walking, running, surfing, writing, etc.",
    )

    # Impact
    impact_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="unaffected, painful, penalty, impossible",
    )
    impact_value: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Percentage for painful/penalty types",
    )
    requirement: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="For impossible_without types (crutches, etc.)",
    )

    def __repr__(self) -> str:
        return (
            f"<ActivityRestriction {self.body_part.value}/{self.injury_type.value} "
            f"→ {self.activity_name}: {self.impact_type}>"
        )
