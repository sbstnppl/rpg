"""Progression models for achievements, titles, and ranks.

These models track player accomplishments and progression milestones
that provide visible growth and recognition.
"""

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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.database.models.session import GameSession


class AchievementType(PyEnum):
    """Types of achievements."""

    FIRST_DISCOVERY = "first_discovery"  # First to find/do something
    MILESTONE = "milestone"  # Progress-based (kill 100 monsters)
    TITLE = "title"  # Earned title (Hero of the Realm)
    RANK = "rank"  # Faction/guild rank
    SECRET = "secret"  # Hidden achievement


class Achievement(Base, TimestampMixin):
    """Achievement definition (what can be unlocked).

    Achievements are defined per session to allow custom achievements
    for different campaigns.
    """

    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Achievement identity
    achievement_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Unique key within session (e.g., 'first_blood')",
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Display title (e.g., 'First Blood')",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Description of how to earn this achievement",
    )

    # Achievement type and value
    achievement_type: Mapped[AchievementType] = mapped_column(
        Enum(AchievementType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    points: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Achievement points awarded",
    )

    # Progress tracking (for milestone achievements)
    target_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Target count for progress-based achievements",
    )

    # Requirements and conditions
    requirements: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Requirements to unlock (skill levels, items, etc.)",
    )

    # Visibility
    is_hidden: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="If true, achievement is hidden until unlocked",
    )

    # Relationships
    session: Mapped["GameSession"] = relationship(back_populates="achievements")
    unlocks: Mapped[list["EntityAchievement"]] = relationship(
        back_populates="achievement",
        cascade="all, delete-orphan",
    )

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("session_id", "achievement_key", name="uq_achievement_key"),
    )

    def __repr__(self) -> str:
        return f"<Achievement {self.achievement_key}: {self.title}>"


class EntityAchievement(Base, TimestampMixin):
    """Tracks which achievements an entity has unlocked."""

    __tablename__ = "entity_achievements"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    achievement_id: Mapped[int] = mapped_column(
        ForeignKey("achievements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Unlock tracking
    unlocked_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    unlocked_turn: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Turn when achievement was unlocked",
    )

    # Progress tracking (for milestone achievements)
    current_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Current progress toward target",
    )

    # Notification tracking
    notified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether player has been notified of this unlock",
    )

    # Relationships
    achievement: Mapped["Achievement"] = relationship(back_populates="unlocks")

    # Unique constraint - one unlock per entity per achievement
    __table_args__ = (
        UniqueConstraint("entity_id", "achievement_id", name="uq_entity_achievement"),
    )

    def __repr__(self) -> str:
        return f"<EntityAchievement entity={self.entity_id} achievement={self.achievement_id}>"
