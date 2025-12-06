"""Tests for Task, Appointment, Quest, and QuestStage models."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.database.models.enums import AppointmentStatus, QuestStatus, TaskCategory
from src.database.models.session import GameSession
from src.database.models.tasks import Appointment, Quest, QuestStage, Task
from tests.factories import (
    create_appointment,
    create_entity,
    create_game_session,
    create_quest,
    create_quest_stage,
    create_task,
)


class TestTask:
    """Tests for Task model."""

    def test_create_task_required_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify Task creation with required fields."""
        task = Task(
            session_id=game_session.id,
            description="Find the missing key",
            created_turn=1,
        )
        db_session.add(task)
        db_session.flush()

        assert task.id is not None
        assert task.session_id == game_session.id
        assert task.description == "Find the missing key"
        assert task.created_turn == 1

    def test_task_category_enum(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify TaskCategory enum values."""
        for category in TaskCategory:
            task = create_task(db_session, game_session, category=category)
            db_session.refresh(task)
            assert task.category == category

    def test_task_priority_levels(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify priority levels 1=low, 2=medium, 3=high."""
        low = create_task(db_session, game_session, priority=1)
        medium = create_task(db_session, game_session, priority=2)
        high = create_task(db_session, game_session, priority=3)

        assert low.priority < medium.priority < high.priority

    def test_task_completion(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify completed and completed_turn fields."""
        task = create_task(db_session, game_session, completed=False)
        assert task.completed is False
        assert task.completed_turn is None

        task.completed = True
        task.completed_turn = 15
        db_session.flush()
        db_session.refresh(task)

        assert task.completed is True
        assert task.completed_turn == 15

    def test_task_timing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify in_game_day and in_game_time optional fields."""
        task = create_task(
            db_session,
            game_session,
            in_game_day=3,
            in_game_time="4pm",
            location="Market Square",
        )

        db_session.refresh(task)

        assert task.in_game_day == 3
        assert task.in_game_time == "4pm"
        assert task.location == "Market Square"

    def test_task_session_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify task has back reference to session."""
        task = create_task(db_session, game_session)

        assert task.session is not None
        assert task.session.id == game_session.id

    def test_task_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        task = create_task(
            db_session,
            game_session,
            description="Buy supplies from the merchant",
            in_game_day=2,
            in_game_time="10am",
        )

        repr_str = repr(task)
        assert "Task" in repr_str
        assert "pending" in repr_str
        assert "Day 2" in repr_str
        assert "10am" in repr_str

    def test_task_repr_completed(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify repr for completed task."""
        task = create_task(
            db_session,
            game_session,
            description="Done task",
            completed=True,
        )

        repr_str = repr(task)
        assert "done" in repr_str


class TestAppointment:
    """Tests for Appointment model."""

    def test_create_appointment_required_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify Appointment creation with required fields."""
        appt = Appointment(
            session_id=game_session.id,
            description="Meet with the merchant",
            game_day=3,
            participants="merchant_bob, player",
            created_turn=5,
        )
        db_session.add(appt)
        db_session.flush()

        assert appt.id is not None
        assert appt.game_day == 3
        assert "merchant_bob" in appt.participants

    def test_appointment_status_enum(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify AppointmentStatus enum values."""
        for status in AppointmentStatus:
            appt = create_appointment(db_session, game_session, status=status)
            db_session.refresh(appt)
            assert appt.status == status

    def test_appointment_timing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify game_time and duration_hours fields."""
        appt = create_appointment(
            db_session,
            game_session,
            game_time="14:30",
            duration_hours=2.5,
            location_name="The Rusty Anchor Tavern",
        )

        db_session.refresh(appt)

        assert appt.game_time == "14:30"
        assert appt.duration_hours == 2.5
        assert appt.location_name == "The Rusty Anchor Tavern"

    def test_appointment_outcome(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify outcome_notes field."""
        appt = create_appointment(
            db_session,
            game_session,
            status=AppointmentStatus.COMPLETED,
            outcome_notes="Successfully negotiated a trade deal.",
        )

        db_session.refresh(appt)
        assert "trade deal" in appt.outcome_notes

    def test_appointment_initiated_by(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify initiated_by field."""
        appt = create_appointment(
            db_session,
            game_session,
            initiated_by="merchant_bob",
        )

        db_session.refresh(appt)
        assert appt.initiated_by == "merchant_bob"

    def test_appointment_session_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify appointment has back reference to session."""
        appt = create_appointment(db_session, game_session)

        assert appt.session is not None
        assert appt.session.id == game_session.id

    def test_appointment_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        appt = create_appointment(
            db_session,
            game_session,
            description="Dinner at the castle",
            game_day=5,
            status=AppointmentStatus.SCHEDULED,
        )

        repr_str = repr(appt)
        assert "Appointment" in repr_str
        assert "Day 5" in repr_str
        assert "scheduled" in repr_str


class TestQuest:
    """Tests for Quest model."""

    def test_create_quest_required_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify Quest creation with required fields."""
        quest = Quest(
            session_id=game_session.id,
            quest_key="main_quest_01",
            name="The Dragon's Hoard",
            description="Recover the stolen treasure from the dragon's lair.",
        )
        db_session.add(quest)
        db_session.flush()

        assert quest.id is not None
        assert quest.quest_key == "main_quest_01"
        assert quest.name == "The Dragon's Hoard"

    def test_quest_status_enum(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify QuestStatus enum values."""
        for status in QuestStatus:
            quest = create_quest(db_session, game_session, status=status)
            db_session.refresh(quest)
            assert quest.status == status

    def test_quest_current_stage(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify current_stage tracking."""
        quest = create_quest(db_session, game_session, current_stage=2)

        db_session.refresh(quest)
        assert quest.current_stage == 2

    def test_quest_giver_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify giver_entity_id FK."""
        giver = create_entity(db_session, game_session, display_name="Old Wizard")
        quest = create_quest(db_session, game_session, giver_entity_id=giver.id)

        db_session.refresh(quest)

        assert quest.giver_entity_id == giver.id
        assert quest.giver_entity.display_name == "Old Wizard"

    def test_quest_rewards_json(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify rewards JSON field."""
        rewards = {
            "gold": 500,
            "items": ["magic_sword"],
            "reputation": {"kingdom": +10},
        }
        quest = create_quest(db_session, game_session, rewards=rewards)

        db_session.refresh(quest)

        assert quest.rewards == rewards
        assert quest.rewards["gold"] == 500

    def test_quest_stages_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify one-to-many QuestStage relationship."""
        quest = create_quest(db_session, game_session)
        stage1 = create_quest_stage(db_session, quest, stage_order=0, name="Find the map")
        stage2 = create_quest_stage(db_session, quest, stage_order=1, name="Travel to the cave")

        db_session.refresh(quest)

        assert len(quest.stages) == 2
        # Verify ordering
        assert quest.stages[0].stage_order == 0
        assert quest.stages[1].stage_order == 1

    def test_quest_tracking(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify started_turn and completed_turn tracking."""
        quest = create_quest(
            db_session,
            game_session,
            status=QuestStatus.COMPLETED,
            started_turn=5,
            completed_turn=25,
        )

        db_session.refresh(quest)

        assert quest.started_turn == 5
        assert quest.completed_turn == 25

    def test_quest_session_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify quest has back reference to session."""
        quest = create_quest(db_session, game_session)

        assert quest.session is not None
        assert quest.session.id == game_session.id

    def test_quest_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        quest = create_quest(
            db_session,
            game_session,
            name="The Lost Artifact",
            status=QuestStatus.ACTIVE,
            current_stage=1,
        )

        repr_str = repr(quest)
        assert "Quest" in repr_str
        assert "The Lost Artifact" in repr_str
        assert "active" in repr_str
        assert "Stage 1" in repr_str


class TestQuestStage:
    """Tests for QuestStage model."""

    def test_create_quest_stage_required_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify QuestStage creation with required fields."""
        quest = create_quest(db_session, game_session)
        stage = QuestStage(
            quest_id=quest.id,
            stage_order=0,
            name="Investigate the ruins",
            description="Search the ancient ruins for clues.",
            objective="Find the hidden passage.",
        )
        db_session.add(stage)
        db_session.flush()

        assert stage.id is not None
        assert stage.quest_id == quest.id
        assert stage.stage_order == 0
        assert stage.name == "Investigate the ruins"

    def test_quest_stage_ordering(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify stage_order field."""
        quest = create_quest(db_session, game_session)
        stage0 = create_quest_stage(db_session, quest, stage_order=0)
        stage1 = create_quest_stage(db_session, quest, stage_order=1)
        stage2 = create_quest_stage(db_session, quest, stage_order=2)

        assert stage0.stage_order < stage1.stage_order < stage2.stage_order

    def test_quest_stage_completion(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify is_completed and completed_turn fields."""
        quest = create_quest(db_session, game_session)
        stage = create_quest_stage(db_session, quest)

        assert stage.is_completed is False
        assert stage.completed_turn is None

        stage.is_completed = True
        stage.completed_turn = 10
        db_session.flush()
        db_session.refresh(stage)

        assert stage.is_completed is True
        assert stage.completed_turn == 10

    def test_quest_stage_hints_json(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify hints JSON array."""
        quest = create_quest(db_session, game_session)
        hints = [
            "Look for a lever behind the statue.",
            "The passage opens at midnight.",
            "Bring a light source.",
        ]
        stage = create_quest_stage(db_session, quest, hints=hints)

        db_session.refresh(stage)

        assert stage.hints == hints
        assert len(stage.hints) == 3

    def test_quest_stage_quest_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify stage has back reference to quest."""
        quest = create_quest(db_session, game_session, name="Test Quest")
        stage = create_quest_stage(db_session, quest)

        assert stage.quest is not None
        assert stage.quest.name == "Test Quest"

    def test_quest_stage_cascade_delete(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify stages are deleted when quest is deleted."""
        quest = create_quest(db_session, game_session)
        stage = create_quest_stage(db_session, quest)
        stage_id = stage.id

        db_session.delete(quest)
        db_session.flush()
        db_session.expire_all()

        result = db_session.query(QuestStage).filter(QuestStage.id == stage_id).first()
        assert result is None

    def test_quest_stage_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        quest = create_quest(db_session, game_session)
        stage = create_quest_stage(
            db_session,
            quest,
            stage_order=1,
            name="Defeat the Guardian",
            is_completed=False,
        )

        repr_str = repr(stage)
        assert "QuestStage" in repr_str
        assert "1" in repr_str  # stage_order
        assert "pending" in repr_str
        assert "Defeat the Guardian" in repr_str

    def test_quest_stage_repr_completed(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify repr for completed stage."""
        quest = create_quest(db_session, game_session)
        stage = create_quest_stage(db_session, quest, is_completed=True)

        repr_str = repr(stage)
        assert "done" in repr_str
