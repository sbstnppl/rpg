"""GoalManager for NPC autonomous goal management.

This manager handles CRUD operations for NPC goals, which drive autonomous
NPC behavior in the world simulation system.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from src.database.models.enums import GoalPriority, GoalStatus, GoalType
from src.database.models.goals import NPCGoal
from src.database.models.session import GameSession
from src.managers.base import BaseManager

if TYPE_CHECKING:
    from src.database.models.entities import Entity


class GoalManager(BaseManager):
    """Manager for NPC goal operations.

    Handles:
    - Goal CRUD operations
    - Goal status transitions (active, blocked, completed, failed, abandoned)
    - Goal queries by entity, type, priority, status
    - Goal progress advancement
    """

    # =========================================================================
    # Goal Creation
    # =========================================================================

    def create_goal(
        self,
        entity_id: int,
        goal_type: GoalType,
        target: str,
        description: str,
        success_condition: str,
        motivation: list[str] | None = None,
        triggered_by: str | None = None,
        priority: GoalPriority = GoalPriority.MEDIUM,
        strategies: list[str] | None = None,
        failure_condition: str | None = None,
        deadline_description: str | None = None,
        goal_key: str | None = None,
    ) -> NPCGoal:
        """Create a new goal for an NPC.

        Args:
            entity_id: ID of the entity who has this goal.
            goal_type: Category of goal (acquire, romance, etc.).
            target: Target of the goal (entity_key, location_key, item_key, or description).
            description: Human-readable description.
            success_condition: What must happen for goal completion.
            motivation: List of reasons driving this goal.
            triggered_by: Event or turn that created this goal.
            priority: Goal priority level.
            strategies: Ordered steps to achieve the goal.
            failure_condition: What would cause goal failure.
            deadline_description: Human-readable deadline.
            goal_key: Optional custom goal key (auto-generated if not provided).

        Returns:
            Created NPCGoal.
        """
        # Generate goal key if not provided
        if goal_key is None:
            goal_key = f"goal_{uuid.uuid4().hex[:8]}"

        goal = NPCGoal(
            session_id=self.session_id,
            entity_id=entity_id,
            goal_key=goal_key,
            goal_type=goal_type,
            target=target,
            description=description,
            motivation=motivation or [],
            triggered_by=triggered_by,
            priority=priority,
            strategies=strategies or [],
            current_step=0,
            success_condition=success_condition,
            failure_condition=failure_condition,
            deadline_description=deadline_description,
            status=GoalStatus.ACTIVE,
            created_at_turn=self.current_turn,
        )
        self.db.add(goal)
        self.db.flush()
        return goal

    def create_goal_from_schema(
        self,
        entity_id: int,
        goal_creation: "GoalCreation",
    ) -> NPCGoal:
        """Create a goal from a GoalCreation Pydantic schema.

        Args:
            entity_id: ID of the entity who has this goal.
            goal_creation: GoalCreation schema from GM output.

        Returns:
            Created NPCGoal.
        """
        from src.agents.schemas.goals import GoalCreation

        return self.create_goal(
            entity_id=entity_id,
            goal_type=GoalType(goal_creation.goal_type),
            target=goal_creation.target,
            description=goal_creation.description,
            success_condition=goal_creation.success_condition or f"Achieve: {goal_creation.description}",
            motivation=goal_creation.motivation,
            triggered_by=goal_creation.triggered_by,
            priority=GoalPriority(goal_creation.priority),
            strategies=goal_creation.strategies,
            failure_condition=goal_creation.failure_condition,
            deadline_description=goal_creation.deadline_description,
        )

    # =========================================================================
    # Goal Retrieval
    # =========================================================================

    def get_goal(self, goal_id: int) -> NPCGoal | None:
        """Get goal by ID.

        Args:
            goal_id: Goal ID.

        Returns:
            NPCGoal if found, None otherwise.
        """
        return (
            self.db.query(NPCGoal)
            .filter(
                NPCGoal.session_id == self.session_id,
                NPCGoal.id == goal_id,
            )
            .first()
        )

    def get_goal_by_key(self, goal_key: str) -> NPCGoal | None:
        """Get goal by goal_key.

        Args:
            goal_key: Unique goal identifier.

        Returns:
            NPCGoal if found, None otherwise.
        """
        return (
            self.db.query(NPCGoal)
            .filter(
                NPCGoal.session_id == self.session_id,
                NPCGoal.goal_key == goal_key,
            )
            .first()
        )

    def get_entity_goals(
        self,
        entity_id: int,
        status: GoalStatus | None = None,
        include_terminal: bool = False,
    ) -> list[NPCGoal]:
        """Get all goals for an entity.

        Args:
            entity_id: Entity ID.
            status: Optional status filter.
            include_terminal: If False, excludes completed/failed/abandoned goals.

        Returns:
            List of NPCGoals.
        """
        query = self.db.query(NPCGoal).filter(
            NPCGoal.session_id == self.session_id,
            NPCGoal.entity_id == entity_id,
        )

        if status is not None:
            query = query.filter(NPCGoal.status == status)
        elif not include_terminal:
            query = query.filter(
                NPCGoal.status.in_([GoalStatus.ACTIVE, GoalStatus.BLOCKED])
            )

        return query.order_by(NPCGoal.priority.desc()).all()

    def get_active_goals(
        self,
        entity_id: int | None = None,
        goal_type: GoalType | None = None,
        priority: GoalPriority | None = None,
    ) -> list[NPCGoal]:
        """Get active goals with optional filters.

        Args:
            entity_id: Optional entity filter.
            goal_type: Optional goal type filter.
            priority: Optional priority filter.

        Returns:
            List of active NPCGoals.
        """
        query = self.db.query(NPCGoal).filter(
            NPCGoal.session_id == self.session_id,
            NPCGoal.status == GoalStatus.ACTIVE,
        )

        if entity_id is not None:
            query = query.filter(NPCGoal.entity_id == entity_id)
        if goal_type is not None:
            query = query.filter(NPCGoal.goal_type == goal_type)
        if priority is not None:
            query = query.filter(NPCGoal.priority == priority)

        return query.order_by(NPCGoal.priority.desc()).all()

    def get_blocked_goals(self, entity_id: int | None = None) -> list[NPCGoal]:
        """Get blocked goals.

        Args:
            entity_id: Optional entity filter.

        Returns:
            List of blocked NPCGoals.
        """
        query = self.db.query(NPCGoal).filter(
            NPCGoal.session_id == self.session_id,
            NPCGoal.status == GoalStatus.BLOCKED,
        )

        if entity_id is not None:
            query = query.filter(NPCGoal.entity_id == entity_id)

        return query.all()

    def get_goals_by_target(
        self,
        target: str,
        goal_type: GoalType | None = None,
        active_only: bool = True,
    ) -> list[NPCGoal]:
        """Get goals targeting a specific entity/location/item.

        Args:
            target: Target key (entity_key, location_key, etc.).
            goal_type: Optional goal type filter.
            active_only: If True, only return active goals.

        Returns:
            List of NPCGoals targeting this target.
        """
        query = self.db.query(NPCGoal).filter(
            NPCGoal.session_id == self.session_id,
            NPCGoal.target == target,
        )

        if goal_type is not None:
            query = query.filter(NPCGoal.goal_type == goal_type)
        if active_only:
            query = query.filter(NPCGoal.status == GoalStatus.ACTIVE)

        return query.all()

    def get_urgent_goals(self) -> list[NPCGoal]:
        """Get all urgent priority goals that need immediate attention.

        Returns:
            List of urgent NPCGoals.
        """
        return (
            self.db.query(NPCGoal)
            .filter(
                NPCGoal.session_id == self.session_id,
                NPCGoal.status == GoalStatus.ACTIVE,
                NPCGoal.priority == GoalPriority.URGENT,
            )
            .all()
        )

    # =========================================================================
    # Goal Status Transitions
    # =========================================================================

    def complete_goal(self, goal_id: int, outcome: str) -> NPCGoal:
        """Mark a goal as completed.

        Args:
            goal_id: Goal ID.
            outcome: Description of how the goal was achieved.

        Returns:
            Updated NPCGoal.

        Raises:
            ValueError: If goal not found.
        """
        goal = self.get_goal(goal_id)
        if goal is None:
            raise ValueError(f"Goal not found: {goal_id}")

        goal.complete(outcome, self.current_turn)
        self.db.flush()
        return goal

    def fail_goal(self, goal_id: int, outcome: str) -> NPCGoal:
        """Mark a goal as failed.

        Args:
            goal_id: Goal ID.
            outcome: Description of why the goal failed.

        Returns:
            Updated NPCGoal.

        Raises:
            ValueError: If goal not found.
        """
        goal = self.get_goal(goal_id)
        if goal is None:
            raise ValueError(f"Goal not found: {goal_id}")

        goal.fail(outcome, self.current_turn)
        self.db.flush()
        return goal

    def abandon_goal(self, goal_id: int, reason: str) -> NPCGoal:
        """Mark a goal as abandoned.

        Args:
            goal_id: Goal ID.
            reason: Why the NPC gave up on this goal.

        Returns:
            Updated NPCGoal.

        Raises:
            ValueError: If goal not found.
        """
        goal = self.get_goal(goal_id)
        if goal is None:
            raise ValueError(f"Goal not found: {goal_id}")

        goal.abandon(reason, self.current_turn)
        self.db.flush()
        return goal

    def block_goal(self, goal_id: int, reason: str) -> NPCGoal:
        """Mark a goal as temporarily blocked.

        Args:
            goal_id: Goal ID.
            reason: What is preventing progress.

        Returns:
            Updated NPCGoal.

        Raises:
            ValueError: If goal not found.
        """
        goal = self.get_goal(goal_id)
        if goal is None:
            raise ValueError(f"Goal not found: {goal_id}")

        goal.block(reason)
        self.db.flush()
        return goal

    def unblock_goal(self, goal_id: int) -> NPCGoal:
        """Unblock a goal and resume pursuit.

        Args:
            goal_id: Goal ID.

        Returns:
            Updated NPCGoal.

        Raises:
            ValueError: If goal not found.
        """
        goal = self.get_goal(goal_id)
        if goal is None:
            raise ValueError(f"Goal not found: {goal_id}")

        goal.unblock()
        self.db.flush()
        return goal

    # =========================================================================
    # Goal Progress
    # =========================================================================

    def advance_goal_step(self, goal_id: int) -> tuple[NPCGoal, bool]:
        """Advance a goal to its next strategy step.

        Args:
            goal_id: Goal ID.

        Returns:
            Tuple of (updated NPCGoal, whether there was a next step).

        Raises:
            ValueError: If goal not found.
        """
        goal = self.get_goal(goal_id)
        if goal is None:
            raise ValueError(f"Goal not found: {goal_id}")

        advanced = goal.advance_step()
        self.db.flush()
        return goal, advanced

    def update_goal_last_processed(self, goal_id: int) -> NPCGoal:
        """Update the last_processed_turn for a goal.

        Called by World Simulator after processing a goal.

        Args:
            goal_id: Goal ID.

        Returns:
            Updated NPCGoal.

        Raises:
            ValueError: If goal not found.
        """
        goal = self.get_goal(goal_id)
        if goal is None:
            raise ValueError(f"Goal not found: {goal_id}")

        goal.last_processed_turn = self.current_turn
        self.db.flush()
        return goal

    def set_goal_strategies(self, goal_id: int, strategies: list[str]) -> NPCGoal:
        """Set or update the strategies for a goal.

        Args:
            goal_id: Goal ID.
            strategies: New list of strategy steps.

        Returns:
            Updated NPCGoal.

        Raises:
            ValueError: If goal not found.
        """
        goal = self.get_goal(goal_id)
        if goal is None:
            raise ValueError(f"Goal not found: {goal_id}")

        goal.strategies = strategies
        goal.current_step = 0  # Reset to beginning
        self.db.flush()
        return goal

    def update_goal_priority(self, goal_id: int, priority: GoalPriority) -> NPCGoal:
        """Update the priority of a goal.

        Args:
            goal_id: Goal ID.
            priority: New priority level.

        Returns:
            Updated NPCGoal.

        Raises:
            ValueError: If goal not found.
        """
        goal = self.get_goal(goal_id)
        if goal is None:
            raise ValueError(f"Goal not found: {goal_id}")

        goal.priority = priority
        self.db.flush()
        return goal

    # =========================================================================
    # Goal Utilities
    # =========================================================================

    def has_goal_type(
        self,
        entity_id: int,
        goal_type: GoalType,
        target: str | None = None,
    ) -> bool:
        """Check if an entity has an active goal of a specific type.

        Args:
            entity_id: Entity ID.
            goal_type: Goal type to check for.
            target: Optional target to match.

        Returns:
            True if entity has matching active goal.
        """
        query = self.db.query(NPCGoal).filter(
            NPCGoal.session_id == self.session_id,
            NPCGoal.entity_id == entity_id,
            NPCGoal.goal_type == goal_type,
            NPCGoal.status == GoalStatus.ACTIVE,
        )

        if target is not None:
            query = query.filter(NPCGoal.target == target)

        return query.first() is not None

    def get_goals_needing_processing(
        self,
        turns_since_processed: int = 1,
    ) -> list[NPCGoal]:
        """Get active goals that haven't been processed recently.

        Used by World Simulator to find goals to advance.

        Args:
            turns_since_processed: Minimum turns since last processing.

        Returns:
            List of goals needing processing.
        """
        threshold_turn = self.current_turn - turns_since_processed

        return (
            self.db.query(NPCGoal)
            .filter(
                NPCGoal.session_id == self.session_id,
                NPCGoal.status == GoalStatus.ACTIVE,
                (NPCGoal.last_processed_turn == None) | (NPCGoal.last_processed_turn <= threshold_turn),
            )
            .order_by(NPCGoal.priority.desc())
            .all()
        )

    def delete_goal(self, goal_id: int) -> bool:
        """Delete a goal entirely.

        Use sparingly - typically goals should be completed/failed/abandoned.

        Args:
            goal_id: Goal ID.

        Returns:
            True if deleted, False if not found.
        """
        goal = self.get_goal(goal_id)
        if goal is None:
            return False

        self.db.delete(goal)
        self.db.flush()
        return True

    def count_active_goals(self, entity_id: int | None = None) -> int:
        """Count active goals.

        Args:
            entity_id: Optional entity filter.

        Returns:
            Number of active goals.
        """
        query = self.db.query(NPCGoal).filter(
            NPCGoal.session_id == self.session_id,
            NPCGoal.status == GoalStatus.ACTIVE,
        )

        if entity_id is not None:
            query = query.filter(NPCGoal.entity_id == entity_id)

        return query.count()
