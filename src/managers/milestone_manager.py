"""Milestone manager for tracking significant story events.

Milestones mark points in the narrative where summaries should be
regenerated. They provide natural chapter-like divisions.
"""

from sqlalchemy.orm import Session

from src.database.models.context_summary import Milestone, MilestoneType
from src.database.models.session import GameSession
from src.database.models.world import TimeState
from src.managers.base import BaseManager


class MilestoneManager(BaseManager):
    """Manages story milestones for context summary regeneration.

    Milestones trigger regeneration of:
    - Story summary (covers start → last milestone)
    - Recent summary (updated to cover through last night)
    """

    def record_milestone(
        self,
        milestone_type: MilestoneType,
        description: str,
        related_entity_key: str | None = None,
    ) -> Milestone:
        """Record a new milestone in the story.

        Args:
            milestone_type: Type of milestone event
            description: Brief description of what happened
            related_entity_key: Optional key of related entity (quest, arc, etc.)

        Returns:
            The created Milestone record
        """
        # Get current game time
        time_state = (
            self.db.query(TimeState)
            .filter(TimeState.session_id == self.session_id)
            .first()
        )

        game_day = time_state.current_day if time_state else 1
        game_time = time_state.current_time if time_state else "08:00"

        milestone = Milestone(
            session_id=self.session_id,
            milestone_type=milestone_type,
            description=description,
            turn_number=self.current_turn,
            game_day=game_day,
            game_time=game_time,
            related_entity_key=related_entity_key,
        )

        self.db.add(milestone)
        self.db.flush()

        return milestone

    def get_last_milestone(self) -> Milestone | None:
        """Get the most recent milestone.

        Returns:
            Most recent Milestone or None if no milestones exist
        """
        return (
            self.db.query(Milestone)
            .filter(Milestone.session_id == self.session_id)
            .order_by(Milestone.turn_number.desc())
            .first()
        )

    def get_milestones_since(self, turn_number: int) -> list[Milestone]:
        """Get all milestones since a specific turn.

        Args:
            turn_number: Turn number to search from (exclusive)

        Returns:
            List of milestones ordered by turn number
        """
        return (
            self.db.query(Milestone)
            .filter(
                Milestone.session_id == self.session_id,
                Milestone.turn_number > turn_number,
            )
            .order_by(Milestone.turn_number.asc())
            .all()
        )

    def get_all_milestones(self) -> list[Milestone]:
        """Get all milestones for the session.

        Returns:
            List of all milestones ordered by turn number
        """
        return (
            self.db.query(Milestone)
            .filter(Milestone.session_id == self.session_id)
            .order_by(Milestone.turn_number.asc())
            .all()
        )

    def get_milestone_count(self) -> int:
        """Get total number of milestones.

        Returns:
            Count of milestones in this session
        """
        return (
            self.db.query(Milestone)
            .filter(Milestone.session_id == self.session_id)
            .count()
        )

    def get_milestones_for_day(self, game_day: int) -> list[Milestone]:
        """Get all milestones that occurred on a specific day.

        Args:
            game_day: In-game day to filter by

        Returns:
            List of milestones for that day
        """
        return (
            self.db.query(Milestone)
            .filter(
                Milestone.session_id == self.session_id,
                Milestone.game_day == game_day,
            )
            .order_by(Milestone.turn_number.asc())
            .all()
        )
