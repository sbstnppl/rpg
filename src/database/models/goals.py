"""NPC Goal models for autonomous behavior.

Goals drive NPC behavior even when the player isn't watching. The World
Simulator processes goals between turns, advancing NPCs through their
strategies and creating a living world.
"""

from datetime import datetime
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
from src.database.models.enums import GoalPriority, GoalStatus, GoalType

if TYPE_CHECKING:
    from src.database.models.entities import Entity
    from src.database.models.session import GameSession


class NPCGoal(Base, TimestampMixin):
    """A goal that an NPC is actively pursuing.

    Goals are created from:
    - Interactions with the player (positive interaction → romance goal)
    - Critical needs (hunger > 80 → survive goal to find food)
    - Events in the world (theft detected → revenge goal)
    - NPC personality and values (ambitious NPC → earn_money goals)

    The World Simulator processes goals between turns, advancing NPCs
    through their strategies even when the player isn't watching.
    """

    __tablename__ = "npc_goals"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Session scoping - all goals belong to a game session
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The NPC who has this goal
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Unique goal identifier within session (e.g., "goal_elara_001")
    goal_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Unique goal identifier within session",
    )

    # What they want
    goal_type: Mapped[GoalType] = mapped_column(
        Enum(GoalType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True,
        comment="Category of goal",
    )

    # Target of the goal (entity_key, location_key, item_key, or description)
    target: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Target: entity_key, location_key, item_key, or description",
    )

    # Human-readable description
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Human-readable goal description",
    )

    # Why they want it (JSON array of motivation strings)
    motivation: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="Reasons driving this goal",
    )

    # What triggered the goal
    triggered_by: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Event or turn that created this goal",
    )

    # Priority
    priority: Mapped[GoalPriority] = mapped_column(
        Enum(GoalPriority, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=GoalPriority.MEDIUM,
        index=True,
        comment="Goal priority level",
    )

    # Deadline (game time)
    deadline: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="Game time deadline for this goal",
    )

    deadline_description: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Human-readable deadline description",
    )

    # Strategies - ordered steps to achieve goal (JSON array)
    strategies: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="Ordered steps to achieve the goal",
    )

    # Current progress
    current_step: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Index of current strategy step",
    )

    blocked_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Why the NPC cannot proceed (if blocked)",
    )

    # Completion conditions
    success_condition: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="What must happen for goal completion",
    )

    failure_condition: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="What would cause goal failure",
    )

    # Status
    status: Mapped[GoalStatus] = mapped_column(
        Enum(GoalStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=GoalStatus.ACTIVE,
        index=True,
        comment="Current goal status",
    )

    # Outcome (filled when completed or failed)
    outcome: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Description of outcome when completed/failed",
    )

    # Turn tracking
    created_at_turn: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Turn number when goal was created",
    )

    completed_at_turn: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Turn number when goal was completed",
    )

    # Last processed turn (for World Simulator)
    last_processed_turn: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Last turn this goal was processed by World Simulator",
    )

    # Relationships
    session: Mapped["GameSession"] = relationship(
        "GameSession",
        back_populates="npc_goals",
    )

    entity: Mapped["Entity"] = relationship(
        "Entity",
        back_populates="goals",
    )

    # Constraints
    __table_args__ = (
        # Goal key must be unique within a session
        UniqueConstraint("session_id", "goal_key", name="uq_goal_session_key"),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<NPCGoal(goal_key='{self.goal_key}', type={self.goal_type.value}, "
            f"status={self.status.value}, priority={self.priority.value})>"
        )

    @property
    def is_active(self) -> bool:
        """Check if goal is still being pursued."""
        return self.status == GoalStatus.ACTIVE

    @property
    def is_complete(self) -> bool:
        """Check if goal has been completed."""
        return self.status == GoalStatus.COMPLETED

    @property
    def is_terminal(self) -> bool:
        """Check if goal is in a terminal state (completed, failed, abandoned)."""
        return self.status in (
            GoalStatus.COMPLETED,
            GoalStatus.FAILED,
            GoalStatus.ABANDONED,
        )

    @property
    def current_strategy_step(self) -> str | None:
        """Get the current strategy step being pursued."""
        if self.strategies and 0 <= self.current_step < len(self.strategies):
            return self.strategies[self.current_step]
        return None

    @property
    def progress_percentage(self) -> float:
        """Get progress as percentage (0-100)."""
        if not self.strategies:
            return 0.0
        return (self.current_step / len(self.strategies)) * 100

    def advance_step(self) -> bool:
        """Advance to the next strategy step.

        Returns:
            True if advanced, False if already at end.
        """
        if self.current_step < len(self.strategies) - 1:
            self.current_step += 1
            return True
        return False

    def complete(self, outcome: str, turn: int) -> None:
        """Mark goal as completed.

        Args:
            outcome: Description of how goal was achieved.
            turn: Turn number when completed.
        """
        self.status = GoalStatus.COMPLETED
        self.outcome = outcome
        self.completed_at_turn = turn

    def fail(self, outcome: str, turn: int) -> None:
        """Mark goal as failed.

        Args:
            outcome: Description of why goal failed.
            turn: Turn number when failed.
        """
        self.status = GoalStatus.FAILED
        self.outcome = outcome
        self.completed_at_turn = turn

    def abandon(self, reason: str, turn: int) -> None:
        """Mark goal as abandoned.

        Args:
            reason: Why NPC gave up on this goal.
            turn: Turn number when abandoned.
        """
        self.status = GoalStatus.ABANDONED
        self.outcome = reason
        self.completed_at_turn = turn

    def block(self, reason: str) -> None:
        """Mark goal as temporarily blocked.

        Args:
            reason: What is preventing progress.
        """
        self.status = GoalStatus.BLOCKED
        self.blocked_reason = reason

    def unblock(self) -> None:
        """Remove blocked status and resume pursuit."""
        self.status = GoalStatus.ACTIVE
        self.blocked_reason = None
