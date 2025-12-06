"""TaskManager for tasks, appointments, and quests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from src.database.models.enums import AppointmentStatus, QuestStatus, TaskCategory
from src.database.models.session import GameSession
from src.database.models.tasks import Appointment, Quest, QuestStage, Task
from src.managers.base import BaseManager

if TYPE_CHECKING:
    from src.managers.time_manager import TimeManager


class TaskManager(BaseManager):
    """Manager for task, appointment, and quest operations.

    Handles:
    - Task CRUD and queries
    - Appointment scheduling and tracking
    - Quest lifecycle and stage progression
    """

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        time_manager: TimeManager | None = None,
    ):
        """Initialize with optional TimeManager dependency.

        Args:
            db: Database session.
            game_session: Game session.
            time_manager: Optional TimeManager for current day lookups.
        """
        super().__init__(db, game_session)
        self.time_manager = time_manager

    # =========================================================================
    # Task Operations
    # =========================================================================

    def create_task(
        self,
        description: str,
        category: TaskCategory,
        priority: int = 2,
        in_game_day: int | None = None,
        in_game_time: str | None = None,
        location: str | None = None,
    ) -> Task:
        """Create a new task.

        Args:
            description: Task description.
            category: Task category.
            priority: Priority (1=low, 2=medium, 3=high).
            in_game_day: Optional day for task.
            in_game_time: Optional time for task.
            location: Optional location.

        Returns:
            Created Task.
        """
        task = Task(
            session_id=self.session_id,
            description=description,
            category=category,
            priority=priority,
            in_game_day=in_game_day,
            in_game_time=in_game_time,
            location=location,
            created_turn=self.current_turn,
            completed=False,
        )
        self.db.add(task)
        self.db.flush()
        return task

    def get_task(self, task_id: int) -> Task | None:
        """Get task by ID.

        Args:
            task_id: Task ID.

        Returns:
            Task if found, None otherwise.
        """
        return (
            self.db.query(Task)
            .filter(
                Task.session_id == self.session_id,
                Task.id == task_id,
            )
            .first()
        )

    def get_active_tasks(
        self, category: TaskCategory | None = None
    ) -> list[Task]:
        """Get all active (incomplete) tasks.

        Args:
            category: Optional category filter.

        Returns:
            List of active Tasks.
        """
        query = self.db.query(Task).filter(
            Task.session_id == self.session_id,
            Task.completed == False,
        )

        if category is not None:
            query = query.filter(Task.category == category)

        return query.order_by(Task.priority.desc()).all()

    def get_tasks_for_day(self, game_day: int) -> list[Task]:
        """Get tasks scheduled for a specific day.

        Args:
            game_day: Day number.

        Returns:
            List of Tasks for that day.
        """
        return (
            self.db.query(Task)
            .filter(
                Task.session_id == self.session_id,
                Task.in_game_day == game_day,
            )
            .all()
        )

    def complete_task(self, task_id: int) -> Task:
        """Mark task as completed.

        Args:
            task_id: Task ID.

        Returns:
            Updated Task.

        Raises:
            ValueError: If task not found.
        """
        task = self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        task.completed = True
        task.completed_turn = self.current_turn
        self.db.flush()
        return task

    def fail_task(self, task_id: int, reason: str | None = None) -> Task:
        """Mark task as failed.

        Args:
            task_id: Task ID.
            reason: Optional reason for failure.

        Returns:
            Updated Task.

        Raises:
            ValueError: If task not found.
        """
        task = self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        task.completed = True  # Task is done (failed)
        task.completed_turn = self.current_turn
        self.db.flush()
        return task

    # =========================================================================
    # Appointment Operations
    # =========================================================================

    def create_appointment(
        self,
        description: str,
        game_day: int,
        participants: str,
        game_time: str | None = None,
        location_name: str | None = None,
        duration_hours: float | None = None,
        initiated_by: str | None = None,
    ) -> Appointment:
        """Create a new appointment.

        Args:
            description: Appointment description.
            game_day: Day number.
            participants: Comma-separated participant names.
            game_time: Optional time (HH:MM format).
            location_name: Optional location name.
            duration_hours: Optional duration in hours.
            initiated_by: Who suggested this appointment.

        Returns:
            Created Appointment.
        """
        appointment = Appointment(
            session_id=self.session_id,
            description=description,
            game_day=game_day,
            participants=participants,
            game_time=game_time,
            location_name=location_name,
            duration_hours=duration_hours,
            initiated_by=initiated_by,
            status=AppointmentStatus.SCHEDULED,
            created_turn=self.current_turn,
        )
        self.db.add(appointment)
        self.db.flush()
        return appointment

    def get_appointment(self, appointment_id: int) -> Appointment | None:
        """Get appointment by ID.

        Args:
            appointment_id: Appointment ID.

        Returns:
            Appointment if found, None otherwise.
        """
        return (
            self.db.query(Appointment)
            .filter(
                Appointment.session_id == self.session_id,
                Appointment.id == appointment_id,
            )
            .first()
        )

    def get_appointments_for_day(self, game_day: int) -> list[Appointment]:
        """Get appointments scheduled for a day.

        Args:
            game_day: Day number.

        Returns:
            List of Appointments for that day.
        """
        return (
            self.db.query(Appointment)
            .filter(
                Appointment.session_id == self.session_id,
                Appointment.game_day == game_day,
            )
            .all()
        )

    def complete_appointment(
        self, appointment_id: int, outcome: str | None = None
    ) -> Appointment:
        """Mark appointment as completed.

        Args:
            appointment_id: Appointment ID.
            outcome: Optional outcome notes.

        Returns:
            Updated Appointment.

        Raises:
            ValueError: If appointment not found.
        """
        appointment = self.get_appointment(appointment_id)
        if appointment is None:
            raise ValueError(f"Appointment not found: {appointment_id}")

        appointment.status = AppointmentStatus.COMPLETED
        appointment.completed_turn = self.current_turn
        if outcome is not None:
            appointment.outcome_notes = outcome
        self.db.flush()
        return appointment

    def cancel_appointment(self, appointment_id: int) -> Appointment:
        """Cancel an appointment.

        Args:
            appointment_id: Appointment ID.

        Returns:
            Updated Appointment.

        Raises:
            ValueError: If appointment not found.
        """
        appointment = self.get_appointment(appointment_id)
        if appointment is None:
            raise ValueError(f"Appointment not found: {appointment_id}")

        appointment.status = AppointmentStatus.CANCELLED
        self.db.flush()
        return appointment

    def reschedule_appointment(
        self, appointment_id: int, new_day: int, new_time: str | None = None
    ) -> Appointment:
        """Reschedule an appointment.

        Args:
            appointment_id: Appointment ID.
            new_day: New day number.
            new_time: New time (optional).

        Returns:
            Updated Appointment.

        Raises:
            ValueError: If appointment not found.
        """
        appointment = self.get_appointment(appointment_id)
        if appointment is None:
            raise ValueError(f"Appointment not found: {appointment_id}")

        appointment.game_day = new_day
        if new_time is not None:
            appointment.game_time = new_time
        appointment.status = AppointmentStatus.RESCHEDULED
        self.db.flush()
        return appointment

    def check_missed_appointments(self) -> list[Appointment]:
        """Check for and mark missed appointments.

        Uses TimeManager to get current day. Appointments in the past
        that are still SCHEDULED are marked as MISSED.

        Returns:
            List of appointments that were marked as missed.

        Raises:
            ValueError: If TimeManager not provided.
        """
        if self.time_manager is None:
            raise ValueError("TimeManager required for check_missed_appointments")

        current_day, _ = self.time_manager.get_current_time()

        # Find scheduled appointments in the past
        missed = (
            self.db.query(Appointment)
            .filter(
                Appointment.session_id == self.session_id,
                Appointment.status == AppointmentStatus.SCHEDULED,
                Appointment.game_day < current_day,
            )
            .all()
        )

        # Mark them as missed
        for appointment in missed:
            appointment.status = AppointmentStatus.MISSED

        self.db.flush()
        return missed

    def mark_appointment_kept(self, appointment_id: int) -> Appointment:
        """Mark appointment as kept/completed.

        Alias for complete_appointment.

        Args:
            appointment_id: Appointment ID.

        Returns:
            Updated Appointment.
        """
        return self.complete_appointment(appointment_id)

    def mark_appointment_missed(self, appointment_id: int) -> Appointment:
        """Mark appointment as missed.

        Args:
            appointment_id: Appointment ID.

        Returns:
            Updated Appointment.

        Raises:
            ValueError: If appointment not found.
        """
        appointment = self.get_appointment(appointment_id)
        if appointment is None:
            raise ValueError(f"Appointment not found: {appointment_id}")

        appointment.status = AppointmentStatus.MISSED
        self.db.flush()
        return appointment

    # =========================================================================
    # Quest Operations
    # =========================================================================

    def create_quest(
        self,
        quest_key: str,
        name: str,
        description: str,
        giver_entity_id: int | None = None,
        rewards: dict | None = None,
    ) -> Quest:
        """Create a new quest.

        Args:
            quest_key: Unique quest identifier.
            name: Display name.
            description: Quest description.
            giver_entity_id: Optional quest giver entity ID.
            rewards: Optional rewards dict.

        Returns:
            Created Quest.
        """
        quest = Quest(
            session_id=self.session_id,
            quest_key=quest_key,
            name=name,
            description=description,
            giver_entity_id=giver_entity_id,
            rewards=rewards,
            status=QuestStatus.AVAILABLE,
            current_stage=0,
        )
        self.db.add(quest)
        self.db.flush()
        return quest

    def get_quest(self, quest_key: str) -> Quest | None:
        """Get quest by key.

        Args:
            quest_key: Quest key.

        Returns:
            Quest if found, None otherwise.
        """
        return (
            self.db.query(Quest)
            .filter(
                Quest.session_id == self.session_id,
                Quest.quest_key == quest_key,
            )
            .first()
        )

    def start_quest(self, quest_key: str) -> Quest:
        """Start a quest (change status to active).

        Args:
            quest_key: Quest key.

        Returns:
            Updated Quest.

        Raises:
            ValueError: If quest not found.
        """
        quest = self.get_quest(quest_key)
        if quest is None:
            raise ValueError(f"Quest not found: {quest_key}")

        quest.status = QuestStatus.ACTIVE
        quest.started_turn = self.current_turn
        self.db.flush()
        return quest

    def add_quest_stage(
        self,
        quest_key: str,
        name: str,
        description: str,
        objective: str,
        hints: list | None = None,
    ) -> QuestStage:
        """Add a stage to a quest.

        Args:
            quest_key: Quest key.
            name: Stage name.
            description: Stage description.
            objective: What player needs to do.
            hints: Optional list of hints.

        Returns:
            Created QuestStage.

        Raises:
            ValueError: If quest not found.
        """
        quest = self.get_quest(quest_key)
        if quest is None:
            raise ValueError(f"Quest not found: {quest_key}")

        # Get current max stage order
        max_order = (
            self.db.query(QuestStage.stage_order)
            .filter(QuestStage.quest_id == quest.id)
            .order_by(QuestStage.stage_order.desc())
            .first()
        )
        next_order = 0 if max_order is None else max_order[0] + 1

        stage = QuestStage(
            quest_id=quest.id,
            stage_order=next_order,
            name=name,
            description=description,
            objective=objective,
            hints=hints,
            is_completed=False,
        )
        self.db.add(stage)
        self.db.flush()
        return stage

    def complete_quest_stage(self, quest_key: str) -> Quest:
        """Complete current quest stage and advance to next.

        If this was the final stage, completes the quest.

        Args:
            quest_key: Quest key.

        Returns:
            Updated Quest.

        Raises:
            ValueError: If quest not found.
        """
        quest = self.get_quest(quest_key)
        if quest is None:
            raise ValueError(f"Quest not found: {quest_key}")

        # Mark current stage as completed
        current_stage = (
            self.db.query(QuestStage)
            .filter(
                QuestStage.quest_id == quest.id,
                QuestStage.stage_order == quest.current_stage,
            )
            .first()
        )

        if current_stage is not None:
            current_stage.is_completed = True
            current_stage.completed_turn = self.current_turn

        # Check if there's a next stage
        next_stage = (
            self.db.query(QuestStage)
            .filter(
                QuestStage.quest_id == quest.id,
                QuestStage.stage_order == quest.current_stage + 1,
            )
            .first()
        )

        if next_stage is not None:
            # Advance to next stage
            quest.current_stage += 1
        else:
            # No more stages - complete the quest
            quest.status = QuestStatus.COMPLETED
            quest.completed_turn = self.current_turn

        self.db.flush()
        return quest

    def fail_quest(self, quest_key: str) -> Quest:
        """Mark quest as failed.

        Args:
            quest_key: Quest key.

        Returns:
            Updated Quest.

        Raises:
            ValueError: If quest not found.
        """
        quest = self.get_quest(quest_key)
        if quest is None:
            raise ValueError(f"Quest not found: {quest_key}")

        quest.status = QuestStatus.FAILED
        self.db.flush()
        return quest

    def get_active_quests(self) -> list[Quest]:
        """Get all active quests.

        Returns:
            List of active Quests.
        """
        return (
            self.db.query(Quest)
            .filter(
                Quest.session_id == self.session_id,
                Quest.status == QuestStatus.ACTIVE,
            )
            .all()
        )

    def get_available_quests(self) -> list[Quest]:
        """Get all available (not yet started) quests.

        Returns:
            List of available Quests.
        """
        return (
            self.db.query(Quest)
            .filter(
                Quest.session_id == self.session_id,
                Quest.status == QuestStatus.AVAILABLE,
            )
            .all()
        )

    def get_quest_stages(self, quest_key: str) -> list[QuestStage]:
        """Get all stages for a quest in order.

        Args:
            quest_key: Quest key.

        Returns:
            List of QuestStages in order.

        Raises:
            ValueError: If quest not found.
        """
        quest = self.get_quest(quest_key)
        if quest is None:
            raise ValueError(f"Quest not found: {quest_key}")

        return (
            self.db.query(QuestStage)
            .filter(QuestStage.quest_id == quest.id)
            .order_by(QuestStage.stage_order)
            .all()
        )

    def get_current_quest_stage(self, quest_key: str) -> QuestStage | None:
        """Get the current stage of a quest.

        Args:
            quest_key: Quest key.

        Returns:
            Current QuestStage or None.

        Raises:
            ValueError: If quest not found.
        """
        quest = self.get_quest(quest_key)
        if quest is None:
            raise ValueError(f"Quest not found: {quest_key}")

        return (
            self.db.query(QuestStage)
            .filter(
                QuestStage.quest_id == quest.id,
                QuestStage.stage_order == quest.current_stage,
            )
            .first()
        )
