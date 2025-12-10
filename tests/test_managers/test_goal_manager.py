"""Tests for GoalManager class."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.enums import GoalPriority, GoalStatus, GoalType
from src.database.models.entities import Entity
from src.database.models.goals import NPCGoal
from src.database.models.session import GameSession
from src.managers.goal_manager import GoalManager
from tests.factories import create_entity, create_npc_goal


class TestGoalManagerCreation:
    """Tests for goal creation operations."""

    def test_create_goal_basic(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify create_goal creates a new goal with required fields."""
        manager = GoalManager(db_session, game_session)

        result = manager.create_goal(
            entity_id=npc_entity.id,
            goal_type=GoalType.ACQUIRE,
            target="sword",
            description="Get a sword",
            success_condition="Possess a sword",
        )

        assert result is not None
        assert result.entity_id == npc_entity.id
        assert result.goal_type == GoalType.ACQUIRE
        assert result.target == "sword"
        assert result.description == "Get a sword"
        assert result.success_condition == "Possess a sword"
        assert result.session_id == game_session.id
        assert result.status == GoalStatus.ACTIVE
        assert result.current_step == 0

    def test_create_goal_with_all_fields(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify create_goal accepts all optional fields."""
        manager = GoalManager(db_session, game_session)

        result = manager.create_goal(
            entity_id=npc_entity.id,
            goal_type=GoalType.ROMANCE,
            target="player",
            description="Win the player's heart",
            success_condition="Player reciprocates feelings",
            motivation=["attraction", "loneliness"],
            triggered_by="positive_interaction_turn_5",
            priority=GoalPriority.HIGH,
            strategies=["find player", "talk to player", "give gift"],
            failure_condition="Player leaves town",
            deadline_description="before the festival",
            goal_key="romance_player_001",
        )

        assert result.motivation == ["attraction", "loneliness"]
        assert result.triggered_by == "positive_interaction_turn_5"
        assert result.priority == GoalPriority.HIGH
        assert result.strategies == ["find player", "talk to player", "give gift"]
        assert result.failure_condition == "Player leaves town"
        assert result.deadline_description == "before the festival"
        assert result.goal_key == "romance_player_001"

    def test_create_goal_auto_generates_key(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify create_goal generates unique goal_key if not provided."""
        manager = GoalManager(db_session, game_session)

        goal1 = manager.create_goal(
            entity_id=npc_entity.id,
            goal_type=GoalType.ACQUIRE,
            target="item1",
            description="Get item1",
            success_condition="Has item1",
        )
        goal2 = manager.create_goal(
            entity_id=npc_entity.id,
            goal_type=GoalType.ACQUIRE,
            target="item2",
            description="Get item2",
            success_condition="Has item2",
        )

        assert goal1.goal_key.startswith("goal_")
        assert goal2.goal_key.startswith("goal_")
        assert goal1.goal_key != goal2.goal_key

    def test_create_goal_sets_created_turn(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify create_goal sets created_at_turn from session."""
        game_session.total_turns = 15
        manager = GoalManager(db_session, game_session)

        result = manager.create_goal(
            entity_id=npc_entity.id,
            goal_type=GoalType.GO_TO,
            target="market",
            description="Go to market",
            success_condition="Arrived at market",
        )

        assert result.created_at_turn == 15


class TestGoalManagerRetrieval:
    """Tests for goal retrieval operations."""

    def test_get_goal_by_id(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify get_goal returns goal by ID."""
        goal = create_npc_goal(db_session, game_session, npc_entity)
        manager = GoalManager(db_session, game_session)

        result = manager.get_goal(goal.id)

        assert result is not None
        assert result.id == goal.id

    def test_get_goal_returns_none_for_invalid_id(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_goal returns None for non-existent ID."""
        manager = GoalManager(db_session, game_session)

        result = manager.get_goal(99999)

        assert result is None

    def test_get_goal_by_key(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify get_goal_by_key returns goal by key."""
        goal = create_npc_goal(
            db_session, game_session, npc_entity, goal_key="find_treasure_001"
        )
        manager = GoalManager(db_session, game_session)

        result = manager.get_goal_by_key("find_treasure_001")

        assert result is not None
        assert result.goal_key == "find_treasure_001"

    def test_get_entity_goals(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify get_entity_goals returns all goals for an entity."""
        create_npc_goal(db_session, game_session, npc_entity, description="Goal 1")
        create_npc_goal(db_session, game_session, npc_entity, description="Goal 2")
        # Create goal for different entity
        other_npc = create_entity(db_session, game_session, entity_key="other_npc")
        create_npc_goal(db_session, game_session, other_npc, description="Other goal")

        manager = GoalManager(db_session, game_session)
        result = manager.get_entity_goals(npc_entity.id)

        assert len(result) == 2
        assert all(g.entity_id == npc_entity.id for g in result)

    def test_get_entity_goals_filters_by_status(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify get_entity_goals can filter by status."""
        create_npc_goal(
            db_session, game_session, npc_entity,
            description="Active goal",
            status=GoalStatus.ACTIVE
        )
        create_npc_goal(
            db_session, game_session, npc_entity,
            description="Completed goal",
            status=GoalStatus.COMPLETED
        )

        manager = GoalManager(db_session, game_session)
        result = manager.get_entity_goals(npc_entity.id, status=GoalStatus.ACTIVE)

        assert len(result) == 1
        assert result[0].description == "Active goal"

    def test_get_entity_goals_excludes_terminal_by_default(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify get_entity_goals excludes completed/failed/abandoned by default."""
        create_npc_goal(
            db_session, game_session, npc_entity,
            status=GoalStatus.ACTIVE
        )
        create_npc_goal(
            db_session, game_session, npc_entity,
            status=GoalStatus.BLOCKED
        )
        create_npc_goal(
            db_session, game_session, npc_entity,
            status=GoalStatus.COMPLETED
        )
        create_npc_goal(
            db_session, game_session, npc_entity,
            status=GoalStatus.FAILED
        )
        create_npc_goal(
            db_session, game_session, npc_entity,
            status=GoalStatus.ABANDONED
        )

        manager = GoalManager(db_session, game_session)
        result = manager.get_entity_goals(npc_entity.id)

        assert len(result) == 2  # Only ACTIVE and BLOCKED

    def test_get_entity_goals_includes_terminal_when_requested(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify get_entity_goals includes terminal states when requested."""
        create_npc_goal(
            db_session, game_session, npc_entity,
            status=GoalStatus.ACTIVE
        )
        create_npc_goal(
            db_session, game_session, npc_entity,
            status=GoalStatus.COMPLETED
        )

        manager = GoalManager(db_session, game_session)
        result = manager.get_entity_goals(npc_entity.id, include_terminal=True)

        assert len(result) == 2

    def test_get_active_goals(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify get_active_goals returns only active goals."""
        create_npc_goal(
            db_session, game_session, npc_entity,
            status=GoalStatus.ACTIVE
        )
        create_npc_goal(
            db_session, game_session, npc_entity,
            status=GoalStatus.BLOCKED
        )

        manager = GoalManager(db_session, game_session)
        result = manager.get_active_goals()

        assert len(result) == 1
        assert result[0].status == GoalStatus.ACTIVE

    def test_get_active_goals_filters_by_type(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify get_active_goals can filter by goal type."""
        create_npc_goal(
            db_session, game_session, npc_entity,
            goal_type=GoalType.ACQUIRE
        )
        create_npc_goal(
            db_session, game_session, npc_entity,
            goal_type=GoalType.ROMANCE
        )

        manager = GoalManager(db_session, game_session)
        result = manager.get_active_goals(goal_type=GoalType.ROMANCE)

        assert len(result) == 1
        assert result[0].goal_type == GoalType.ROMANCE

    def test_get_goals_by_target(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify get_goals_by_target returns goals targeting specific entity."""
        create_npc_goal(
            db_session, game_session, npc_entity,
            target="player"
        )
        create_npc_goal(
            db_session, game_session, npc_entity,
            target="player"
        )
        create_npc_goal(
            db_session, game_session, npc_entity,
            target="merchant"
        )

        manager = GoalManager(db_session, game_session)
        result = manager.get_goals_by_target("player")

        assert len(result) == 2
        assert all(g.target == "player" for g in result)

    def test_get_urgent_goals(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify get_urgent_goals returns only urgent priority goals."""
        create_npc_goal(
            db_session, game_session, npc_entity,
            priority=GoalPriority.URGENT
        )
        create_npc_goal(
            db_session, game_session, npc_entity,
            priority=GoalPriority.HIGH
        )
        create_npc_goal(
            db_session, game_session, npc_entity,
            priority=GoalPriority.MEDIUM
        )

        manager = GoalManager(db_session, game_session)
        result = manager.get_urgent_goals()

        assert len(result) == 1
        assert result[0].priority == GoalPriority.URGENT


class TestGoalManagerStatusTransitions:
    """Tests for goal status transition operations."""

    def test_complete_goal(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify complete_goal marks goal as completed."""
        game_session.total_turns = 10
        goal = create_npc_goal(db_session, game_session, npc_entity)
        manager = GoalManager(db_session, game_session)

        result = manager.complete_goal(goal.id, "Found the treasure!")

        assert result.status == GoalStatus.COMPLETED
        assert result.outcome == "Found the treasure!"
        assert result.completed_at_turn == 10

    def test_fail_goal(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify fail_goal marks goal as failed."""
        game_session.total_turns = 12
        goal = create_npc_goal(db_session, game_session, npc_entity)
        manager = GoalManager(db_session, game_session)

        result = manager.fail_goal(goal.id, "Target escaped")

        assert result.status == GoalStatus.FAILED
        assert result.outcome == "Target escaped"
        assert result.completed_at_turn == 12

    def test_abandon_goal(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify abandon_goal marks goal as abandoned."""
        game_session.total_turns = 8
        goal = create_npc_goal(db_session, game_session, npc_entity)
        manager = GoalManager(db_session, game_session)

        result = manager.abandon_goal(goal.id, "Lost interest")

        assert result.status == GoalStatus.ABANDONED
        assert result.outcome == "Lost interest"
        assert result.completed_at_turn == 8

    def test_block_goal(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify block_goal marks goal as blocked."""
        goal = create_npc_goal(db_session, game_session, npc_entity)
        manager = GoalManager(db_session, game_session)

        result = manager.block_goal(goal.id, "Bridge is out")

        assert result.status == GoalStatus.BLOCKED
        assert result.blocked_reason == "Bridge is out"

    def test_unblock_goal(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify unblock_goal resumes blocked goal."""
        goal = create_npc_goal(
            db_session, game_session, npc_entity,
            status=GoalStatus.BLOCKED,
            blocked_reason="Bridge is out"
        )
        manager = GoalManager(db_session, game_session)

        result = manager.unblock_goal(goal.id)

        assert result.status == GoalStatus.ACTIVE
        assert result.blocked_reason is None

    def test_status_transition_raises_on_invalid_id(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify status transitions raise ValueError for invalid ID."""
        manager = GoalManager(db_session, game_session)

        with pytest.raises(ValueError, match="Goal not found"):
            manager.complete_goal(99999, "outcome")


class TestGoalManagerProgress:
    """Tests for goal progress operations."""

    def test_advance_goal_step(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify advance_goal_step increments current_step."""
        goal = create_npc_goal(
            db_session, game_session, npc_entity,
            strategies=["step1", "step2", "step3"],
            current_step=0
        )
        manager = GoalManager(db_session, game_session)

        result, advanced = manager.advance_goal_step(goal.id)

        assert advanced is True
        assert result.current_step == 1

    def test_advance_goal_step_returns_false_at_end(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify advance_goal_step returns False when at last step."""
        goal = create_npc_goal(
            db_session, game_session, npc_entity,
            strategies=["step1", "step2"],
            current_step=1  # Already at last step
        )
        manager = GoalManager(db_session, game_session)

        result, advanced = manager.advance_goal_step(goal.id)

        assert advanced is False
        assert result.current_step == 1  # Still at last step

    def test_update_goal_last_processed(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify update_goal_last_processed sets turn number."""
        game_session.total_turns = 20
        goal = create_npc_goal(db_session, game_session, npc_entity)
        manager = GoalManager(db_session, game_session)

        result = manager.update_goal_last_processed(goal.id)

        assert result.last_processed_turn == 20

    def test_set_goal_strategies(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify set_goal_strategies replaces strategies and resets step."""
        goal = create_npc_goal(
            db_session, game_session, npc_entity,
            strategies=["old_step"],
            current_step=0
        )
        manager = GoalManager(db_session, game_session)
        manager.advance_goal_step(goal.id)  # Move to step 1

        result = manager.set_goal_strategies(goal.id, ["new1", "new2", "new3"])

        assert result.strategies == ["new1", "new2", "new3"]
        assert result.current_step == 0  # Reset to beginning

    def test_update_goal_priority(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify update_goal_priority changes priority."""
        goal = create_npc_goal(
            db_session, game_session, npc_entity,
            priority=GoalPriority.LOW
        )
        manager = GoalManager(db_session, game_session)

        result = manager.update_goal_priority(goal.id, GoalPriority.URGENT)

        assert result.priority == GoalPriority.URGENT


class TestGoalManagerUtilities:
    """Tests for goal utility operations."""

    def test_has_goal_type_returns_true(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify has_goal_type returns True when matching goal exists."""
        create_npc_goal(
            db_session, game_session, npc_entity,
            goal_type=GoalType.ROMANCE,
            target="player"
        )
        manager = GoalManager(db_session, game_session)

        result = manager.has_goal_type(npc_entity.id, GoalType.ROMANCE)

        assert result is True

    def test_has_goal_type_returns_false(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify has_goal_type returns False when no matching goal."""
        create_npc_goal(
            db_session, game_session, npc_entity,
            goal_type=GoalType.ACQUIRE
        )
        manager = GoalManager(db_session, game_session)

        result = manager.has_goal_type(npc_entity.id, GoalType.ROMANCE)

        assert result is False

    def test_has_goal_type_with_target(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify has_goal_type can filter by target."""
        create_npc_goal(
            db_session, game_session, npc_entity,
            goal_type=GoalType.ROMANCE,
            target="merchant"
        )
        manager = GoalManager(db_session, game_session)

        assert manager.has_goal_type(npc_entity.id, GoalType.ROMANCE, target="player") is False
        assert manager.has_goal_type(npc_entity.id, GoalType.ROMANCE, target="merchant") is True

    def test_get_goals_needing_processing(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify get_goals_needing_processing returns unprocessed goals."""
        game_session.total_turns = 10
        # Never processed - should be included
        create_npc_goal(
            db_session, game_session, npc_entity,
            last_processed_turn=None
        )
        # Processed this turn - should NOT be included
        create_npc_goal(
            db_session, game_session, npc_entity,
            last_processed_turn=10
        )
        # Processed last turn (threshold is 1) - should be included (10 - 1 = 9, 9 <= 9)
        create_npc_goal(
            db_session, game_session, npc_entity,
            last_processed_turn=9
        )
        # Processed long ago - should be included
        create_npc_goal(
            db_session, game_session, npc_entity,
            last_processed_turn=5
        )

        manager = GoalManager(db_session, game_session)
        result = manager.get_goals_needing_processing(turns_since_processed=1)

        # Never processed, processed at turn 9, processed at turn 5 = 3 goals
        # Only "processed this turn (10)" is excluded
        assert len(result) == 3

    def test_delete_goal(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify delete_goal removes goal from database."""
        goal = create_npc_goal(db_session, game_session, npc_entity)
        goal_id = goal.id
        manager = GoalManager(db_session, game_session)

        result = manager.delete_goal(goal_id)

        assert result is True
        assert manager.get_goal(goal_id) is None

    def test_delete_goal_returns_false_for_invalid(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify delete_goal returns False for non-existent goal."""
        manager = GoalManager(db_session, game_session)

        result = manager.delete_goal(99999)

        assert result is False

    def test_count_active_goals(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify count_active_goals returns correct count."""
        create_npc_goal(
            db_session, game_session, npc_entity,
            status=GoalStatus.ACTIVE
        )
        create_npc_goal(
            db_session, game_session, npc_entity,
            status=GoalStatus.ACTIVE
        )
        create_npc_goal(
            db_session, game_session, npc_entity,
            status=GoalStatus.COMPLETED
        )

        manager = GoalManager(db_session, game_session)
        result = manager.count_active_goals()

        assert result == 2

    def test_count_active_goals_by_entity(
        self, db_session: Session, game_session: GameSession, npc_entity: Entity
    ):
        """Verify count_active_goals can filter by entity."""
        other_npc = create_entity(db_session, game_session, entity_key="other")
        create_npc_goal(db_session, game_session, npc_entity)
        create_npc_goal(db_session, game_session, npc_entity)
        create_npc_goal(db_session, game_session, other_npc)

        manager = GoalManager(db_session, game_session)
        result = manager.count_active_goals(entity_id=npc_entity.id)

        assert result == 2


class TestGoalManagerSessionIsolation:
    """Tests for session isolation of goals."""

    def test_goals_are_session_scoped(
        self,
        db_session: Session,
        game_session: GameSession,
        game_session_2: GameSession,
        npc_entity: Entity,
    ):
        """Verify goals are isolated by session."""
        # Create entity in session 2
        npc_2 = create_entity(
            db_session, game_session_2, entity_key="npc_session2"
        )

        # Create goals in both sessions
        create_npc_goal(db_session, game_session, npc_entity)
        create_npc_goal(db_session, game_session_2, npc_2)

        manager1 = GoalManager(db_session, game_session)
        manager2 = GoalManager(db_session, game_session_2)

        # Each manager should only see its session's goals
        assert len(manager1.get_active_goals()) == 1
        assert len(manager2.get_active_goals()) == 1
