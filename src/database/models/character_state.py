"""Character state models (needs, intimacy profile)."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base, TimestampMixin
from src.database.models.enums import DriveLevel, IntimacyStyle

if TYPE_CHECKING:
    from src.database.models.entities import Entity
    from src.database.models.session import GameSession


class CharacterNeeds(Base, TimestampMixin):
    """Tracks character physiological and psychological needs."""

    __tablename__ = "character_needs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # === TIER 1: Survival (always tracked) ===
    hunger: Mapped[int] = mapped_column(
        default=50,
        nullable=False,
        comment="0=starving, 50=satisfied, 100=stuffed. Optimal: 30-70",
    )
    fatigue: Mapped[int] = mapped_column(
        default=20,
        nullable=False,
        comment="0=fully rested, 50=tired, 100=exhausted. Optimal: 0-40",
    )

    # === TIER 2: Comfort (normal mode) ===
    hygiene: Mapped[int] = mapped_column(
        default=80,
        nullable=False,
        comment="0=filthy, 100=spotless",
    )
    comfort: Mapped[int] = mapped_column(
        default=70,
        nullable=False,
        comment="0=miserable conditions, 100=luxurious (environmental)",
    )
    pain: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="0=no pain, 100=agony (from injuries)",
    )

    # === TIER 3: Psychological (realism mode) ===
    social_connection: Mapped[int] = mapped_column(
        default=60,
        nullable=False,
        comment="0=isolated/lonely, 100=socially fulfilled",
    )
    morale: Mapped[int] = mapped_column(
        default=70,
        nullable=False,
        comment="0=depressed, 50=neutral, 100=elated",
    )
    sense_of_purpose: Mapped[int] = mapped_column(
        default=50,
        nullable=False,
        comment="0=aimless, 100=driven by clear goals",
    )
    intimacy: Mapped[int] = mapped_column(
        default=30,
        nullable=False,
        comment="0=satisfied, 100=desperate. Intimacy need level.",
    )

    # Timestamps for decay calculation
    last_updated: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=False,
    )
    last_meal_turn: Mapped[int | None] = mapped_column(nullable=True)
    last_sleep_turn: Mapped[int | None] = mapped_column(nullable=True)
    last_bath_turn: Mapped[int | None] = mapped_column(nullable=True)
    last_social_turn: Mapped[int | None] = mapped_column(nullable=True)
    last_intimate_turn: Mapped[int | None] = mapped_column(nullable=True)

    # Relationships
    entity: Mapped["Entity"] = relationship(foreign_keys=[entity_id])

    def __repr__(self) -> str:
        return (
            f"<CharacterNeeds entity={self.entity_id} "
            f"H:{self.hunger} F:{self.fatigue} M:{self.morale}>"
        )


class IntimacyProfile(Base, TimestampMixin):
    """Intimacy preferences and drive characteristics."""

    __tablename__ = "intimacy_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Drive characteristics
    drive_level: Mapped[DriveLevel] = mapped_column(
        Enum(DriveLevel, values_callable=lambda obj: [e.value for e in obj]),
        default=DriveLevel.MODERATE,
        nullable=False,
        comment="Affects intimacy need decay rate",
    )
    drive_threshold: Mapped[int] = mapped_column(
        default=50,
        nullable=False,
        comment="When need triggers behavior (0-100)",
    )

    # Preferences
    intimacy_style: Mapped[IntimacyStyle] = mapped_column(
        Enum(IntimacyStyle, values_callable=lambda obj: [e.value for e in obj]),
        default=IntimacyStyle.EMOTIONAL,
        nullable=False,
        comment="casual, emotional, monogamous, polyamorous",
    )

    # Attraction preferences (for AI to use in matchmaking)
    attraction_preferences: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Preferred traits: {gender: any, age_range: [25,40], traits: [confident, kind]}",
    )

    # Current status
    has_regular_partner: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    is_actively_seeking: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )

    # Relationships
    entity: Mapped["Entity"] = relationship(foreign_keys=[entity_id])

    def __repr__(self) -> str:
        return (
            f"<IntimacyProfile entity={self.entity_id} "
            f"drive={self.drive_level.value} style={self.intimacy_style.value}>"
        )
