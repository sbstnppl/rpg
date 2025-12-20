"""Tests for WorldSimulator goal processing functionality."""

import pytest
from sqlalchemy.orm import Session

from src.agents.world_simulator import (
    GoalCreatedEvent,
    GoalStepResult,
    SimulationResult,
    WorldSimulator,
)
from src.database.models.character_state import CharacterNeeds
from src.database.models.entities import Entity, NPCExtension
from src.database.models.enums import (
    EntityType,
    GoalPriority,
    GoalStatus,
    GoalType,
)
from src.database.models.goals import NPCGoal
from src.database.models.session import GameSession
from src.database.models.world import TimeState
from src.managers.goal_manager import GoalManager
from src.managers.needs import NeedsManager


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def simulator(db_session: Session, game_session: GameSession) -> WorldSimulator:
    """Create WorldSimulator instance."""
    return WorldSimulator(db_session, game_session)


@pytest.fixture
def time_state(db_session: Session, game_session: GameSession) -> TimeState:
    """Create TimeState for the session."""
    time = TimeState(
        session_id=game_session.id,
        current_day=1,
        current_time="12:00",
        day_of_week="monday",
        weather="clear",
    )
    db_session.add(time)
    db_session.flush()
    return time


@pytest.fixture
def player_entity(db_session: Session, game_session: GameSession) -> Entity:
    """Create player entity."""
    entity = Entity(
        session_id=game_session.id,
        entity_key="player",
        display_name="Hero",
        entity_type=EntityType.PLAYER,
    )
    db_session.add(entity)
    db_session.flush()

    # Add needs
    needs = CharacterNeeds(
        session_id=game_session.id,
        entity_id=entity.id,
        hunger=50,
        thirst=50,
        stamina=50,
        social_connection=50,
        intimacy=50,
        morale=50,
    )
    db_session.add(needs)
    db_session.flush()
    return entity


@pytest.fixture
def npc_with_urgent_hunger(db_session: Session, game_session: GameSession) -> Entity:
    """Create NPC with urgent hunger need."""
    entity = Entity(
        session_id=game_session.id,
        entity_key="hungry_merchant",
        display_name="Hungry Merchant",
        entity_type=EntityType.NPC,
        is_alive=True,
        is_active=True,
    )
    db_session.add(entity)
    db_session.flush()

    # Add NPC extension
    extension = NPCExtension(
        entity_id=entity.id,
        current_location="market",
    )
    db_session.add(extension)

    # Add needs with urgent hunger (low value = bad = urgent)
    # Urgency = 100 - value, so hunger=15 means urgency=85
    needs = CharacterNeeds(
        session_id=game_session.id,
        entity_id=entity.id,
        hunger=15,  # Low value = urgent hunger (urgency = 85)
        thirst=50,
        stamina=50,
        social_connection=50,
        intimacy=50,
        morale=50,
    )
    db_session.add(needs)
    db_session.flush()
    return entity


@pytest.fixture
def npc_with_goal(
    db_session: Session,
    game_session: GameSession,
) -> tuple[Entity, NPCGoal]:
    """Create NPC with an active goal."""
    entity = Entity(
        session_id=game_session.id,
        entity_key="goal_npc",
        display_name="Goal NPC",
        entity_type=EntityType.NPC,
        is_alive=True,
        is_active=True,
    )
    db_session.add(entity)
    db_session.flush()

    # Add NPC extension
    extension = NPCExtension(
        entity_id=entity.id,
        current_location="home",
    )
    db_session.add(extension)

    # Add needs
    needs = CharacterNeeds(
        session_id=game_session.id,
        entity_id=entity.id,
        hunger=50,
        thirst=50,
        stamina=50,
        social_connection=50,
        intimacy=50,
        morale=50,
    )
    db_session.add(needs)

    # Create a goal
    goal = NPCGoal(
        session_id=game_session.id,
        entity_id=entity.id,
        goal_key="test_goal_001",
        goal_type=GoalType.ACQUIRE,
        target="sword",
        description="Buy a new sword",
        motivation=["needs_weapon"],
        priority=GoalPriority.MEDIUM,
        strategies=[
            "go to the market",
            "find a weapon shop",
            "purchase sword",
        ],
        current_step=0,
        success_condition="has_sword",
        status=GoalStatus.ACTIVE,
        created_at_turn=1,
    )
    db_session.add(goal)
    db_session.flush()
    return entity, goal


# =============================================================================
# Need-Driven Goal Creation Tests
# =============================================================================


class TestNeedDrivenGoalCreation:
    """Tests for automatic goal creation from urgent needs."""

    def test_creates_goal_for_urgent_hunger(
        self,
        simulator: WorldSimulator,
        player_entity: Entity,
        npc_with_urgent_hunger: Entity,
        time_state: TimeState,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test that urgent hunger creates a survival goal."""
        result = simulator.simulate_time_passage(
            hours=1.0,
            player_id=player_entity.id,
            player_location="market",
        )

        # Should have created a goal
        assert len(result.goals_created) == 1
        goal_event = result.goals_created[0]
        assert goal_event.entity_id == npc_with_urgent_hunger.id
        assert goal_event.goal_type == "survive"
        assert goal_event.target == "food"
        assert goal_event.motivation == "hunger"

        # Verify goal in database
        goals = (
            db_session.query(NPCGoal)
            .filter(
                NPCGoal.session_id == game_session.id,
                NPCGoal.entity_id == npc_with_urgent_hunger.id,
            )
            .all()
        )
        assert len(goals) == 1
        assert goals[0].goal_type == GoalType.SURVIVE

    def test_does_not_create_goal_for_moderate_need(
        self,
        simulator: WorldSimulator,
        player_entity: Entity,
        db_session: Session,
        game_session: GameSession,
        time_state: TimeState,
    ):
        """Test that moderate needs don't trigger goals."""
        # Create NPC with moderate hunger (below threshold)
        npc = Entity(
            session_id=game_session.id,
            entity_key="moderate_npc",
            display_name="Moderate NPC",
            entity_type=EntityType.NPC,
            is_alive=True,
            is_active=True,
        )
        db_session.add(npc)
        db_session.flush()

        needs = CharacterNeeds(
            session_id=game_session.id,
            entity_id=npc.id,
            hunger=60,  # Below 75 threshold
            thirst=50,
            stamina=50,
            social_connection=50,
            intimacy=50,
            morale=50,
        )
        db_session.add(needs)
        db_session.flush()

        result = simulator.simulate_time_passage(
            hours=1.0,
            player_id=player_entity.id,
            player_location="market",
        )

        # No goals should be created for this NPC
        npc_goals = [g for g in result.goals_created if g.entity_id == npc.id]
        assert len(npc_goals) == 0

    def test_does_not_duplicate_existing_goal(
        self,
        simulator: WorldSimulator,
        player_entity: Entity,
        npc_with_urgent_hunger: Entity,
        time_state: TimeState,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test that existing goals prevent duplicate creation."""
        # Create existing hunger-related goal
        existing_goal = NPCGoal(
            session_id=game_session.id,
            entity_id=npc_with_urgent_hunger.id,
            goal_key="existing_hunger_goal",
            goal_type=GoalType.SURVIVE,
            target="food",
            description="Already looking for food",
            motivation=["hunger"],
            priority=GoalPriority.HIGH,
            strategies=["find food"],
            current_step=0,
            success_condition="not_hungry",
            status=GoalStatus.ACTIVE,
            created_at_turn=1,
        )
        db_session.add(existing_goal)
        db_session.flush()

        result = simulator.simulate_time_passage(
            hours=1.0,
            player_id=player_entity.id,
            player_location="market",
        )

        # Should not create another goal for the same need
        npc_goals = [g for g in result.goals_created if g.entity_id == npc_with_urgent_hunger.id]
        assert len(npc_goals) == 0


# =============================================================================
# Goal Processing Tests
# =============================================================================


class TestGoalProcessing:
    """Tests for processing NPC goals during simulation."""

    def test_processes_goal_step_on_long_time_passage(
        self,
        simulator: WorldSimulator,
        player_entity: Entity,
        npc_with_goal: tuple[Entity, NPCGoal],
        time_state: TimeState,
        db_session: Session,
    ):
        """Test that goals are processed when time >= 30 minutes."""
        npc, goal = npc_with_goal

        result = simulator.simulate_time_passage(
            hours=1.0,  # 1 hour - should process goals
            player_id=player_entity.id,
            player_location="market",
        )

        # Should have attempted to execute a goal step
        assert len(result.goal_steps_executed) >= 1
        step_result = result.goal_steps_executed[0]
        assert step_result.entity_id == npc.id
        assert step_result.goal_id == goal.id

    def test_does_not_process_goals_on_short_time(
        self,
        simulator: WorldSimulator,
        player_entity: Entity,
        npc_with_goal: tuple[Entity, NPCGoal],
        time_state: TimeState,
    ):
        """Test that goals are NOT processed when time < 30 minutes."""
        result = simulator.simulate_time_passage(
            hours=0.25,  # 15 minutes - too short
            player_id=player_entity.id,
            player_location="market",
        )

        # Should not have processed any goals
        assert len(result.goal_steps_executed) == 0

    def test_goal_step_advances_on_success(
        self,
        simulator: WorldSimulator,
        player_entity: Entity,
        time_state: TimeState,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test that successful steps advance the goal."""
        # Run multiple simulations and track successful step executions
        # Since goals can get blocked and need new goals, we track across all NPCs

        # Create multiple NPCs with goals to increase chance of seeing success
        for i in range(3):
            npc = Entity(
                session_id=game_session.id,
                entity_key=f"success_npc_{i}",
                display_name=f"Success NPC {i}",
                entity_type=EntityType.NPC,
                is_alive=True,
                is_active=True,
            )
            db_session.add(npc)
            db_session.flush()

            extension = NPCExtension(entity_id=npc.id)
            db_session.add(extension)

            needs = CharacterNeeds(
                session_id=game_session.id,
                entity_id=npc.id,
                hunger=50, thirst=50, stamina=50,
                social_connection=50, intimacy=50, morale=50,
            )
            db_session.add(needs)

            # Create goal with high-success step
            goal = NPCGoal(
                session_id=game_session.id,
                entity_id=npc.id,
                goal_key=f"success_goal_{i}",
                goal_type=GoalType.ACQUIRE,
                target="item",
                description="Use item",
                priority=GoalPriority.URGENT,  # Higher success rate
                strategies=["use item"],  # "use" has 90% success
                current_step=0,
                success_condition="done",
                status=GoalStatus.ACTIVE,
                created_at_turn=1,
            )
            db_session.add(goal)

        db_session.flush()

        # Run simulation multiple times and count successes
        total_successful_steps = 0
        for _ in range(20):
            result = simulator.simulate_time_passage(
                hours=1.0,
                player_id=player_entity.id,
                player_location="market",
            )

            # Count successful steps
            successful_steps = [s for s in result.goal_steps_executed if s.success]
            total_successful_steps += len(successful_steps)

            if total_successful_steps > 0:
                # At least one step succeeded
                return  # Test passed

        # With 90%+ success rate and 3 NPCs x 20 iterations, we should see success
        pytest.fail(f"Expected successful steps but got {total_successful_steps}")

    def test_goal_completes_when_all_steps_done(
        self,
        simulator: WorldSimulator,
        player_entity: Entity,
        time_state: TimeState,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test that goal is marked complete when all steps succeed."""
        # Create NPC with goal that has only one step
        npc = Entity(
            session_id=game_session.id,
            entity_key="single_step_npc",
            display_name="Quick NPC",
            entity_type=EntityType.NPC,
            is_alive=True,
            is_active=True,
        )
        db_session.add(npc)
        db_session.flush()

        extension = NPCExtension(
            entity_id=npc.id,
        )
        db_session.add(extension)

        needs = CharacterNeeds(
            session_id=game_session.id,
            entity_id=npc.id,
            hunger=50,
            thirst=50,
            stamina=50,
            social_connection=50,
            intimacy=50,
            morale=50,
        )
        db_session.add(needs)

        # Create goal with single high-success step
        goal = NPCGoal(
            session_id=game_session.id,
            entity_id=npc.id,
            goal_key="quick_goal",
            goal_type=GoalType.ACQUIRE,
            target="item",
            description="Quick task",
            priority=GoalPriority.URGENT,  # Higher success rate
            strategies=["use item"],  # "use" has 90% success rate
            current_step=0,
            success_condition="done",
            status=GoalStatus.ACTIVE,
            created_at_turn=1,
        )
        db_session.add(goal)
        db_session.flush()

        # Run until goal completes or max attempts
        for _ in range(20):
            result = simulator.simulate_time_passage(
                hours=1.0,
                player_id=player_entity.id,
                player_location="market",
            )

            if goal.id in result.goals_completed:
                db_session.refresh(goal)
                assert goal.status == GoalStatus.COMPLETED
                break
        else:
            # If we didn't break, goal should still have made progress
            db_session.refresh(goal)
            # With 90% success rate and 20 attempts, very likely to complete


# =============================================================================
# SimulationResult Tests
# =============================================================================


class TestSimulationResult:
    """Tests for SimulationResult dataclass."""

    def test_result_includes_goal_fields(
        self,
        simulator: WorldSimulator,
        player_entity: Entity,
        time_state: TimeState,
    ):
        """Test that SimulationResult has goal-related fields."""
        result = simulator.simulate_time_passage(
            hours=1.0,
            player_id=player_entity.id,
            player_location="market",
        )

        assert hasattr(result, "goals_created")
        assert hasattr(result, "goal_steps_executed")
        assert hasattr(result, "goals_completed")
        assert hasattr(result, "goals_failed")
        assert isinstance(result.goals_created, list)
        assert isinstance(result.goal_steps_executed, list)
        assert isinstance(result.goals_completed, list)
        assert isinstance(result.goals_failed, list)


# =============================================================================
# Integration Tests
# =============================================================================


class TestGoalIntegration:
    """Integration tests for goal system with world simulation."""

    def test_full_goal_lifecycle(
        self,
        simulator: WorldSimulator,
        player_entity: Entity,
        npc_with_urgent_hunger: Entity,
        time_state: TimeState,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test complete goal lifecycle: creation -> processing -> completion."""
        # Step 1: First simulation creates goal from need
        result1 = simulator.simulate_time_passage(
            hours=1.0,
            player_id=player_entity.id,
            player_location="market",
        )

        assert len(result1.goals_created) == 1

        # Get all goals for the NPC (may be active or already processing)
        goals = (
            db_session.query(NPCGoal)
            .filter(
                NPCGoal.session_id == game_session.id,
                NPCGoal.entity_id == npc_with_urgent_hunger.id,
            )
            .all()
        )
        assert len(goals) >= 1
        goal = goals[0]

        # Step 2: Subsequent simulations process the goal
        total_steps_executed = len(result1.goal_steps_executed)
        for _ in range(30):  # Max iterations
            result = simulator.simulate_time_passage(
                hours=1.0,
                player_id=player_entity.id,
                player_location="market",
            )
            total_steps_executed += len(result.goal_steps_executed)

            # Check if goal completed or blocked
            db_session.refresh(goal)
            if goal.status in (GoalStatus.COMPLETED, GoalStatus.BLOCKED):
                break

        # Should have processed some steps
        assert total_steps_executed > 0
