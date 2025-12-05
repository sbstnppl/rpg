"""Task, appointment, and quest models."""

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
from src.database.models.enums import AppointmentStatus, QuestStatus, TaskCategory

if TYPE_CHECKING:
    from src.database.models.entities import Entity
    from src.database.models.session import GameSession


class Task(Base):
    """Player tasks and goals."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Task details
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Task description",
    )
    location: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Location for this task",
    )
    in_game_day: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Day number (None for open-ended)",
    )
    in_game_time: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Time (e.g., '4pm', '7:30am')",
    )
    category: Mapped[TaskCategory] = mapped_column(
        Enum(TaskCategory, values_callable=lambda obj: [e.value for e in obj]),
        default=TaskCategory.GOAL,
        nullable=False,
    )
    priority: Mapped[int] = mapped_column(
        default=2,
        nullable=False,
        comment="1=low, 2=medium, 3=high",
    )

    # Completion status
    completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    completed_turn: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    # Creation tracking
    created_turn: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    session: Mapped["GameSession"] = relationship(back_populates="tasks")

    def __repr__(self) -> str:
        status = "done" if self.completed else "pending"
        time_str = f" @ {self.in_game_time}" if self.in_game_time else ""
        day_str = f" Day {self.in_game_day}" if self.in_game_day else ""
        return f"<Task [{status}]{day_str}{time_str}: {self.description[:30]}>"


class Appointment(Base, TimestampMixin):
    """Future events/plans with NPCs."""

    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Appointment details
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    game_day: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
    )
    game_time: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    duration_hours: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    location_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Participants
    participants: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Comma-separated character names",
    )
    initiated_by: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Who suggested this appointment",
    )

    # Status
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=AppointmentStatus.SCHEDULED,
        nullable=False,
    )
    outcome_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="What happened",
    )

    # Tracking
    created_turn: Mapped[int] = mapped_column(nullable=False)
    completed_turn: Mapped[int | None] = mapped_column(nullable=True)

    # Relationships
    session: Mapped["GameSession"] = relationship(back_populates="appointments")

    def __repr__(self) -> str:
        return f"<Appointment Day {self.game_day}: {self.description[:30]}... [{self.status.value}]>"


class Quest(Base, TimestampMixin):
    """Multi-stage story quests."""

    __tablename__ = "quests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Quest identity
    quest_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Status
    status: Mapped[QuestStatus] = mapped_column(
        Enum(QuestStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=QuestStatus.AVAILABLE,
        nullable=False,
    )
    current_stage: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="Current stage index",
    )

    # Quest giver
    giver_entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Rewards
    rewards: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Rewards for completion",
    )

    # Tracking
    started_turn: Mapped[int | None] = mapped_column(nullable=True)
    completed_turn: Mapped[int | None] = mapped_column(nullable=True)

    # Relationships
    session: Mapped["GameSession"] = relationship(back_populates="quests")
    giver_entity: Mapped["Entity | None"] = relationship(
        foreign_keys=[giver_entity_id],
    )
    stages: Mapped[list["QuestStage"]] = relationship(
        back_populates="quest",
        cascade="all, delete-orphan",
        order_by="QuestStage.stage_order",
    )

    def __repr__(self) -> str:
        return f"<Quest {self.name} [{self.status.value}] Stage {self.current_stage}>"


class QuestStage(Base):
    """A stage within a quest."""

    __tablename__ = "quest_stages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    quest_id: Mapped[int] = mapped_column(
        ForeignKey("quests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Stage identity
    stage_order: Mapped[int] = mapped_column(
        nullable=False,
        comment="Order in quest (0, 1, 2...)",
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    objective: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        comment="What player needs to do",
    )

    # Completion
    is_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    completed_turn: Mapped[int | None] = mapped_column(nullable=True)

    # Hints
    hints: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Progressive hints",
    )

    # Relationships
    quest: Mapped["Quest"] = relationship(back_populates="stages")

    def __repr__(self) -> str:
        status = "done" if self.is_completed else "pending"
        return f"<QuestStage {self.quest_id}:{self.stage_order} [{status}]: {self.name}>"
