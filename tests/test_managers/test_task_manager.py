"""Tests for TaskManager class."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.enums import (
    AppointmentStatus,
    QuestStatus,
    TaskCategory,
)
from src.database.models.session import GameSession
from src.database.models.tasks import Appointment, Quest, QuestStage, Task
from src.managers.task_manager import TaskManager
from src.managers.time_manager import TimeManager
from tests.factories import (
    create_appointment,
    create_entity,
    create_quest,
    create_quest_stage,
    create_task,
    create_time_state,
)


class TestTaskManagerTaskBasics:
    """Tests for basic task operations."""

    def test_create_task_basic(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify create_task creates new task."""
        manager = TaskManager(db_session, game_session)

        result = manager.create_task(
            description="Buy supplies from market",
            category=TaskCategory.GOAL,
        )

        assert result is not None
        assert result.description == "Buy supplies from market"
        assert result.category == TaskCategory.GOAL
        assert result.session_id == game_session.id
        assert result.completed is False

    def test_create_task_with_priority(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify create_task can set priority."""
        manager = TaskManager(db_session, game_session)

        result = manager.create_task(
            description="Urgent task",
            category=TaskCategory.GOAL,
            priority=3,
        )

        assert result.priority == 3

    def test_create_task_with_time(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify create_task can set time/day."""
        manager = TaskManager(db_session, game_session)

        result = manager.create_task(
            description="Meet at noon",
            category=TaskCategory.APPOINTMENT,
            in_game_day=5,
            in_game_time="12:00",
        )

        assert result.in_game_day == 5
        assert result.in_game_time == "12:00"

    def test_create_task_sets_created_turn(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify create_task sets created_turn from session."""
        game_session.total_turns = 10
        manager = TaskManager(db_session, game_session)

        result = manager.create_task(
            description="Test task",
            category=TaskCategory.REMINDER,
        )

        assert result.created_turn == 10

    def test_get_task(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_task returns task by ID."""
        task = create_task(db_session, game_session, description="Find the key")
        manager = TaskManager(db_session, game_session)

        result = manager.get_task(task.id)

        assert result is not None
        assert result.id == task.id
        assert result.description == "Find the key"


class TestTaskManagerTaskQueries:
    """Tests for task query operations."""

    def test_get_active_tasks_excludes_completed(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_active_tasks only returns incomplete tasks."""
        create_task(
            db_session, game_session,
            description="active1",
            completed=False
        )
        create_task(
            db_session, game_session,
            description="active2",
            completed=False
        )
        create_task(
            db_session, game_session,
            description="done",
            completed=True
        )
        manager = TaskManager(db_session, game_session)

        result = manager.get_active_tasks()

        assert len(result) == 2
        assert all(not t.completed for t in result)

    def test_get_active_tasks_by_category(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_active_tasks can filter by category."""
        create_task(
            db_session, game_session,
            description="goal1",
            category=TaskCategory.GOAL
        )
        create_task(
            db_session, game_session,
            description="reminder1",
            category=TaskCategory.REMINDER
        )
        create_task(
            db_session, game_session,
            description="goal2",
            category=TaskCategory.GOAL
        )
        manager = TaskManager(db_session, game_session)

        result = manager.get_active_tasks(category=TaskCategory.GOAL)

        assert len(result) == 2
        assert all(t.category == TaskCategory.GOAL for t in result)

    def test_complete_task(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify complete_task marks task as completed."""
        task = create_task(db_session, game_session, completed=False)
        game_session.total_turns = 15
        manager = TaskManager(db_session, game_session)

        result = manager.complete_task(task.id)

        assert result.completed is True
        assert result.completed_turn == 15

    def test_complete_task_not_found(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify complete_task raises for nonexistent task."""
        manager = TaskManager(db_session, game_session)

        with pytest.raises(ValueError, match="Task not found"):
            manager.complete_task(9999)

    def test_get_tasks_for_day(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_tasks_for_day returns tasks scheduled for day."""
        create_task(
            db_session, game_session,
            description="day3_task",
            in_game_day=3
        )
        create_task(
            db_session, game_session,
            description="day5_task1",
            in_game_day=5
        )
        create_task(
            db_session, game_session,
            description="day5_task2",
            in_game_day=5
        )
        manager = TaskManager(db_session, game_session)

        result = manager.get_tasks_for_day(5)

        assert len(result) == 2
        assert all(t.in_game_day == 5 for t in result)


class TestTaskManagerAppointments:
    """Tests for appointment operations."""

    def test_create_appointment_basic(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify create_appointment creates new appointment."""
        manager = TaskManager(db_session, game_session)

        result = manager.create_appointment(
            description="Meet with merchant",
            game_day=3,
            participants="merchant_bob, player",
        )

        assert result is not None
        assert result.description == "Meet with merchant"
        assert result.game_day == 3
        assert result.participants == "merchant_bob, player"
        assert result.status == AppointmentStatus.SCHEDULED

    def test_create_appointment_with_details(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify create_appointment can set optional details."""
        manager = TaskManager(db_session, game_session)

        result = manager.create_appointment(
            description="Dinner at tavern",
            game_day=2,
            participants="npc_friend",
            game_time="19:00",
            location_name="The Golden Dragon",
            duration_hours=2.0,
        )

        assert result.game_time == "19:00"
        assert result.location_name == "The Golden Dragon"
        assert result.duration_hours == 2.0

    def test_get_appointment(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_appointment returns appointment by ID."""
        appt = create_appointment(db_session, game_session, description="Test meeting")
        manager = TaskManager(db_session, game_session)

        result = manager.get_appointment(appt.id)

        assert result is not None
        assert result.id == appt.id

    def test_get_appointments_for_day(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_appointments_for_day returns appointments on day."""
        create_appointment(
            db_session, game_session,
            description="day1",
            game_day=1
        )
        create_appointment(
            db_session, game_session,
            description="day3_a",
            game_day=3
        )
        create_appointment(
            db_session, game_session,
            description="day3_b",
            game_day=3
        )
        manager = TaskManager(db_session, game_session)

        result = manager.get_appointments_for_day(3)

        assert len(result) == 2
        assert all(a.game_day == 3 for a in result)

    def test_complete_appointment(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify complete_appointment marks as completed."""
        appt = create_appointment(
            db_session, game_session,
            status=AppointmentStatus.SCHEDULED
        )
        game_session.total_turns = 20
        manager = TaskManager(db_session, game_session)

        result = manager.complete_appointment(appt.id)

        assert result.status == AppointmentStatus.COMPLETED
        assert result.completed_turn == 20

    def test_complete_appointment_with_outcome(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify complete_appointment can record outcome."""
        appt = create_appointment(db_session, game_session)
        manager = TaskManager(db_session, game_session)

        result = manager.complete_appointment(
            appt.id,
            outcome="Had a productive discussion about trade routes."
        )

        assert result.outcome_notes == "Had a productive discussion about trade routes."

    def test_cancel_appointment(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify cancel_appointment sets status to cancelled."""
        appt = create_appointment(
            db_session, game_session,
            status=AppointmentStatus.SCHEDULED
        )
        manager = TaskManager(db_session, game_session)

        result = manager.cancel_appointment(appt.id)

        assert result.status == AppointmentStatus.CANCELLED

    def test_check_missed_appointments(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify check_missed_appointments finds past scheduled appointments."""
        # Current day is 5
        create_time_state(db_session, game_session, current_day=5)
        time_manager = TimeManager(db_session, game_session)

        # Past appointment (day 3) - should be missed
        past_appt = create_appointment(
            db_session, game_session,
            description="past",
            game_day=3,
            status=AppointmentStatus.SCHEDULED
        )
        # Future appointment (day 7) - should not be missed
        create_appointment(
            db_session, game_session,
            description="future",
            game_day=7,
            status=AppointmentStatus.SCHEDULED
        )
        # Already completed - should not be returned
        create_appointment(
            db_session, game_session,
            description="done",
            game_day=2,
            status=AppointmentStatus.COMPLETED
        )
        manager = TaskManager(db_session, game_session, time_manager=time_manager)

        result = manager.check_missed_appointments()

        assert len(result) == 1
        assert result[0].id == past_appt.id
        # Should also mark it as missed
        assert result[0].status == AppointmentStatus.MISSED

    def test_reschedule_appointment(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify reschedule_appointment updates day/time."""
        appt = create_appointment(
            db_session, game_session,
            game_day=3,
            game_time="10:00"
        )
        manager = TaskManager(db_session, game_session)

        result = manager.reschedule_appointment(appt.id, new_day=5, new_time="14:00")

        assert result.game_day == 5
        assert result.game_time == "14:00"
        assert result.status == AppointmentStatus.RESCHEDULED


class TestTaskManagerQuests:
    """Tests for quest operations."""

    def test_create_quest_basic(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify create_quest creates new quest."""
        manager = TaskManager(db_session, game_session)

        result = manager.create_quest(
            quest_key="main_quest_1",
            name="The Lost Artifact",
            description="Find the ancient artifact hidden in the ruins.",
        )

        assert result is not None
        assert result.quest_key == "main_quest_1"
        assert result.name == "The Lost Artifact"
        assert result.status == QuestStatus.AVAILABLE
        assert result.current_stage == 0

    def test_create_quest_with_giver(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify create_quest can set quest giver."""
        npc = create_entity(db_session, game_session, entity_key="quest_giver")
        manager = TaskManager(db_session, game_session)

        result = manager.create_quest(
            quest_key="side_quest",
            name="Help the Merchant",
            description="Assist the merchant with deliveries.",
            giver_entity_id=npc.id,
        )

        assert result.giver_entity_id == npc.id

    def test_create_quest_with_rewards(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify create_quest can set rewards."""
        manager = TaskManager(db_session, game_session)

        result = manager.create_quest(
            quest_key="bounty",
            name="Defeat the Bandits",
            description="Clear out the bandit camp.",
            rewards={"gold": 100, "experience": 50},
        )

        assert result.rewards == {"gold": 100, "experience": 50}

    def test_get_quest(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_quest returns quest by key."""
        quest = create_quest(
            db_session, game_session,
            quest_key="test_quest",
            name="Test Quest"
        )
        manager = TaskManager(db_session, game_session)

        result = manager.get_quest("test_quest")

        assert result is not None
        assert result.id == quest.id

    def test_start_quest(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify start_quest changes status to active."""
        quest = create_quest(
            db_session, game_session,
            quest_key="start_me",
            status=QuestStatus.AVAILABLE
        )
        game_session.total_turns = 25
        manager = TaskManager(db_session, game_session)

        result = manager.start_quest("start_me")

        assert result.status == QuestStatus.ACTIVE
        assert result.started_turn == 25

    def test_start_quest_not_found(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify start_quest raises for nonexistent quest."""
        manager = TaskManager(db_session, game_session)

        with pytest.raises(ValueError, match="Quest not found"):
            manager.start_quest("nonexistent")

    def test_add_quest_stage(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify add_quest_stage adds stage to quest."""
        quest = create_quest(db_session, game_session, quest_key="staged_quest")
        manager = TaskManager(db_session, game_session)

        result = manager.add_quest_stage(
            quest_key="staged_quest",
            name="Find the Map",
            description="Locate the treasure map in the library.",
            objective="Search the library shelves",
        )

        assert result.quest_id == quest.id
        assert result.name == "Find the Map"
        assert result.stage_order == 0
        assert result.is_completed is False

    def test_add_quest_stage_increments_order(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify add_quest_stage sets correct stage_order."""
        quest = create_quest(db_session, game_session, quest_key="multi_stage")
        create_quest_stage(db_session, quest, stage_order=0, name="Stage 1")
        create_quest_stage(db_session, quest, stage_order=1, name="Stage 2")
        manager = TaskManager(db_session, game_session)

        result = manager.add_quest_stage(
            quest_key="multi_stage",
            name="Stage 3",
            description="Third stage",
            objective="Do third thing",
        )

        assert result.stage_order == 2

    def test_complete_quest_stage(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify complete_quest_stage advances to next stage."""
        quest = create_quest(
            db_session, game_session,
            quest_key="advancing",
            status=QuestStatus.ACTIVE,
            current_stage=0
        )
        stage0 = create_quest_stage(db_session, quest, stage_order=0, name="Stage 1")
        create_quest_stage(db_session, quest, stage_order=1, name="Stage 2")
        game_session.total_turns = 30
        manager = TaskManager(db_session, game_session)

        result = manager.complete_quest_stage("advancing")

        assert result.current_stage == 1
        # Refresh stage0 to see update
        db_session.refresh(stage0)
        assert stage0.is_completed is True
        assert stage0.completed_turn == 30

    def test_complete_quest_stage_final_stage_completes_quest(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify completing final stage completes the quest."""
        quest = create_quest(
            db_session, game_session,
            quest_key="final_stage",
            status=QuestStatus.ACTIVE,
            current_stage=1
        )
        create_quest_stage(db_session, quest, stage_order=0, name="Stage 1", is_completed=True)
        create_quest_stage(db_session, quest, stage_order=1, name="Final Stage")
        game_session.total_turns = 50
        manager = TaskManager(db_session, game_session)

        result = manager.complete_quest_stage("final_stage")

        assert result.status == QuestStatus.COMPLETED
        assert result.completed_turn == 50

    def test_fail_quest(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify fail_quest sets status to failed."""
        quest = create_quest(
            db_session, game_session,
            quest_key="fail_me",
            status=QuestStatus.ACTIVE
        )
        manager = TaskManager(db_session, game_session)

        result = manager.fail_quest("fail_me")

        assert result.status == QuestStatus.FAILED

    def test_get_active_quests(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_active_quests returns only active quests."""
        create_quest(
            db_session, game_session,
            quest_key="active1",
            status=QuestStatus.ACTIVE
        )
        create_quest(
            db_session, game_session,
            quest_key="active2",
            status=QuestStatus.ACTIVE
        )
        create_quest(
            db_session, game_session,
            quest_key="available",
            status=QuestStatus.AVAILABLE
        )
        create_quest(
            db_session, game_session,
            quest_key="completed",
            status=QuestStatus.COMPLETED
        )
        manager = TaskManager(db_session, game_session)

        result = manager.get_active_quests()

        assert len(result) == 2
        assert all(q.status == QuestStatus.ACTIVE for q in result)

    def test_get_available_quests(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_available_quests returns quests not yet started."""
        create_quest(
            db_session, game_session,
            quest_key="available1",
            status=QuestStatus.AVAILABLE
        )
        create_quest(
            db_session, game_session,
            quest_key="available2",
            status=QuestStatus.AVAILABLE
        )
        create_quest(
            db_session, game_session,
            quest_key="active",
            status=QuestStatus.ACTIVE
        )
        manager = TaskManager(db_session, game_session)

        result = manager.get_available_quests()

        assert len(result) == 2
        assert all(q.status == QuestStatus.AVAILABLE for q in result)

    def test_get_quest_stages(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_quest_stages returns stages in order."""
        quest = create_quest(db_session, game_session, quest_key="staged")
        create_quest_stage(db_session, quest, stage_order=2, name="Third")
        create_quest_stage(db_session, quest, stage_order=0, name="First")
        create_quest_stage(db_session, quest, stage_order=1, name="Second")
        manager = TaskManager(db_session, game_session)

        result = manager.get_quest_stages("staged")

        assert len(result) == 3
        assert result[0].name == "First"
        assert result[1].name == "Second"
        assert result[2].name == "Third"

    def test_get_current_quest_stage(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_current_quest_stage returns current stage."""
        quest = create_quest(
            db_session, game_session,
            quest_key="current_test",
            current_stage=1
        )
        create_quest_stage(db_session, quest, stage_order=0, name="Past Stage")
        current = create_quest_stage(db_session, quest, stage_order=1, name="Current Stage")
        create_quest_stage(db_session, quest, stage_order=2, name="Future Stage")
        manager = TaskManager(db_session, game_session)

        result = manager.get_current_quest_stage("current_test")

        assert result is not None
        assert result.id == current.id
        assert result.name == "Current Stage"
