"""Achievement manager for tracking and unlocking achievements.

This manager handles achievement definitions, progress tracking,
unlocking, and notification management.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.database.models import Entity, GameSession
from src.database.models.progression import (
    Achievement,
    AchievementType,
    EntityAchievement,
)


@dataclass
class AchievementUnlock:
    """Result of an achievement unlock attempt."""

    unlocked: bool
    achievement_key: str
    title: str
    points: int
    already_unlocked: bool


@dataclass
class AchievementProgress:
    """Current progress toward an achievement."""

    achievement_key: str
    title: str
    current_count: int
    target_count: int | None
    percentage: float
    unlocked: bool


class AchievementManager:
    """Manages achievement definitions and unlocks.

    Handles creating achievements, tracking progress, unlocking,
    and generating context for display.
    """

    def __init__(self, db: Session, game_session: GameSession) -> None:
        """Initialize the achievement manager.

        Args:
            db: Database session.
            game_session: Current game session.
        """
        self.db = db
        self.game_session = game_session

    def create_achievement(
        self,
        achievement_key: str,
        title: str,
        description: str,
        achievement_type: AchievementType,
        points: int = 0,
        target_count: int | None = None,
        requirements: dict | None = None,
        is_hidden: bool = False,
    ) -> Achievement:
        """Create a new achievement definition.

        Args:
            achievement_key: Unique key within session.
            title: Display title.
            description: Description of how to earn.
            achievement_type: Type of achievement.
            points: Points awarded on unlock.
            target_count: Target for progress-based achievements.
            requirements: Additional requirements (JSON).
            is_hidden: Whether achievement is hidden until unlocked.

        Returns:
            Created Achievement.
        """
        achievement = Achievement(
            session_id=self.game_session.id,
            achievement_key=achievement_key,
            title=title,
            description=description,
            achievement_type=achievement_type,
            points=points,
            target_count=target_count,
            requirements=requirements,
            is_hidden=is_hidden,
        )
        self.db.add(achievement)
        self.db.flush()
        return achievement

    def get_achievement(self, achievement_key: str) -> Achievement | None:
        """Get an achievement by key.

        Args:
            achievement_key: The achievement key.

        Returns:
            Achievement if found, None otherwise.
        """
        return self.db.execute(
            select(Achievement).where(
                Achievement.session_id == self.game_session.id,
                Achievement.achievement_key == achievement_key,
            )
        ).scalar_one_or_none()

    def get_all_achievements(self) -> list[Achievement]:
        """Get all achievements for this session.

        Returns:
            List of all achievements.
        """
        return list(
            self.db.execute(
                select(Achievement).where(
                    Achievement.session_id == self.game_session.id
                )
            ).scalars().all()
        )

    def get_achievements_by_type(
        self, achievement_type: AchievementType
    ) -> list[Achievement]:
        """Get achievements filtered by type.

        Args:
            achievement_type: Type to filter by.

        Returns:
            List of matching achievements.
        """
        return list(
            self.db.execute(
                select(Achievement).where(
                    Achievement.session_id == self.game_session.id,
                    Achievement.achievement_type == achievement_type,
                )
            ).scalars().all()
        )

    def _get_entity(self, entity_key: str) -> Entity:
        """Get entity by key or raise error.

        Args:
            entity_key: The entity key.

        Returns:
            Entity.

        Raises:
            ValueError: If entity not found.
        """
        entity = self.db.execute(
            select(Entity).where(
                Entity.session_id == self.game_session.id,
                Entity.entity_key == entity_key,
            )
        ).scalar_one_or_none()

        if not entity:
            raise ValueError(f"Entity '{entity_key}' not found")
        return entity

    def unlock_achievement(
        self,
        entity_key: str,
        achievement_key: str,
        turn_number: int | None = None,
    ) -> AchievementUnlock:
        """Unlock an achievement for an entity.

        Args:
            entity_key: The entity to unlock for.
            achievement_key: The achievement to unlock.
            turn_number: Optional turn when unlocked.

        Returns:
            AchievementUnlock result.

        Raises:
            ValueError: If achievement or entity not found.
        """
        achievement = self.get_achievement(achievement_key)
        if not achievement:
            raise ValueError(f"Achievement '{achievement_key}' not found")

        entity = self._get_entity(entity_key)

        # Check if already unlocked
        existing = self.db.execute(
            select(EntityAchievement).where(
                EntityAchievement.entity_id == entity.id,
                EntityAchievement.achievement_id == achievement.id,
            )
        ).scalar_one_or_none()

        if existing:
            return AchievementUnlock(
                unlocked=True,
                achievement_key=achievement_key,
                title=achievement.title,
                points=achievement.points,
                already_unlocked=True,
            )

        # Create unlock record
        entity_achievement = EntityAchievement(
            entity_id=entity.id,
            achievement_id=achievement.id,
            unlocked_at=datetime.utcnow(),
            unlocked_turn=turn_number,
            current_count=achievement.target_count or 0,
            notified=False,
        )
        self.db.add(entity_achievement)
        self.db.flush()

        return AchievementUnlock(
            unlocked=True,
            achievement_key=achievement_key,
            title=achievement.title,
            points=achievement.points,
            already_unlocked=False,
        )

    def is_achievement_unlocked(
        self, entity_key: str, achievement_key: str
    ) -> bool:
        """Check if an achievement is unlocked.

        Args:
            entity_key: The entity to check.
            achievement_key: The achievement to check.

        Returns:
            True if unlocked, False otherwise.
        """
        achievement = self.get_achievement(achievement_key)
        if not achievement:
            return False

        entity = self.db.execute(
            select(Entity).where(
                Entity.session_id == self.game_session.id,
                Entity.entity_key == entity_key,
            )
        ).scalar_one_or_none()

        if not entity:
            return False

        exists = self.db.execute(
            select(EntityAchievement).where(
                EntityAchievement.entity_id == entity.id,
                EntityAchievement.achievement_id == achievement.id,
            )
        ).scalar_one_or_none()

        return exists is not None

    def get_unlocked_achievements(self, entity_key: str) -> list[Achievement]:
        """Get all unlocked achievements for an entity.

        Args:
            entity_key: The entity to check.

        Returns:
            List of unlocked achievements.
        """
        entity = self.db.execute(
            select(Entity).where(
                Entity.session_id == self.game_session.id,
                Entity.entity_key == entity_key,
            )
        ).scalar_one_or_none()

        if not entity:
            return []

        return list(
            self.db.execute(
                select(Achievement)
                .join(EntityAchievement)
                .where(EntityAchievement.entity_id == entity.id)
            ).scalars().all()
        )

    def update_progress(
        self,
        entity_key: str,
        achievement_key: str,
        increment: int = 1,
    ) -> AchievementProgress:
        """Update progress toward an achievement.

        Args:
            entity_key: The entity to update.
            achievement_key: The achievement to update.
            increment: Amount to increment progress.

        Returns:
            Current progress.

        Raises:
            ValueError: If achievement or entity not found.
        """
        achievement = self.get_achievement(achievement_key)
        if not achievement:
            raise ValueError(f"Achievement '{achievement_key}' not found")

        entity = self._get_entity(entity_key)

        # Get or create progress record
        entity_achievement = self.db.execute(
            select(EntityAchievement).where(
                EntityAchievement.entity_id == entity.id,
                EntityAchievement.achievement_id == achievement.id,
            )
        ).scalar_one_or_none()

        if entity_achievement:
            # Update existing progress
            entity_achievement.current_count += increment
        else:
            # Create new progress record (not yet unlocked)
            entity_achievement = EntityAchievement(
                entity_id=entity.id,
                achievement_id=achievement.id,
                unlocked_at=datetime.utcnow(),
                current_count=increment,
                notified=False,
            )
            self.db.add(entity_achievement)

        self.db.flush()

        # Check if we should unlock
        unlocked = False
        target = achievement.target_count
        if target and entity_achievement.current_count >= target:
            unlocked = True

        # Calculate percentage
        percentage = 0.0
        if target and target > 0:
            percentage = min(100.0, (entity_achievement.current_count / target) * 100)

        return AchievementProgress(
            achievement_key=achievement_key,
            title=achievement.title,
            current_count=entity_achievement.current_count,
            target_count=target,
            percentage=percentage,
            unlocked=unlocked,
        )

    def get_progress(
        self, entity_key: str, achievement_key: str
    ) -> AchievementProgress:
        """Get current progress for an achievement.

        Args:
            entity_key: The entity to check.
            achievement_key: The achievement to check.

        Returns:
            Current progress.

        Raises:
            ValueError: If achievement or entity not found.
        """
        achievement = self.get_achievement(achievement_key)
        if not achievement:
            raise ValueError(f"Achievement '{achievement_key}' not found")

        entity = self._get_entity(entity_key)

        entity_achievement = self.db.execute(
            select(EntityAchievement).where(
                EntityAchievement.entity_id == entity.id,
                EntityAchievement.achievement_id == achievement.id,
            )
        ).scalar_one_or_none()

        current_count = entity_achievement.current_count if entity_achievement else 0
        target = achievement.target_count

        # Calculate percentage
        percentage = 0.0
        if target and target > 0:
            percentage = min(100.0, (current_count / target) * 100)

        unlocked = target is not None and current_count >= target

        return AchievementProgress(
            achievement_key=achievement_key,
            title=achievement.title,
            current_count=current_count,
            target_count=target,
            percentage=percentage,
            unlocked=unlocked,
        )

    def get_total_points(self, entity_key: str) -> int:
        """Get total achievement points for an entity.

        Args:
            entity_key: The entity to check.

        Returns:
            Total points from unlocked achievements.
        """
        entity = self.db.execute(
            select(Entity).where(
                Entity.session_id == self.game_session.id,
                Entity.entity_key == entity_key,
            )
        ).scalar_one_or_none()

        if not entity:
            return 0

        result = self.db.execute(
            select(func.sum(Achievement.points))
            .join(EntityAchievement)
            .where(EntityAchievement.entity_id == entity.id)
        ).scalar()

        return result or 0

    def get_recent_unlocks(
        self, entity_key: str, limit: int = 5
    ) -> list[Achievement]:
        """Get recently unlocked achievements.

        Args:
            entity_key: The entity to check.
            limit: Maximum number to return.

        Returns:
            List of recently unlocked achievements.
        """
        entity = self.db.execute(
            select(Entity).where(
                Entity.session_id == self.game_session.id,
                Entity.entity_key == entity_key,
            )
        ).scalar_one_or_none()

        if not entity:
            return []

        return list(
            self.db.execute(
                select(Achievement)
                .join(EntityAchievement)
                .where(EntityAchievement.entity_id == entity.id)
                .order_by(EntityAchievement.unlocked_at.desc())
                .limit(limit)
            ).scalars().all()
        )

    def get_pending_notifications(self, entity_key: str) -> list[Achievement]:
        """Get achievements that haven't been notified yet.

        Args:
            entity_key: The entity to check.

        Returns:
            List of achievements awaiting notification.
        """
        entity = self.db.execute(
            select(Entity).where(
                Entity.session_id == self.game_session.id,
                Entity.entity_key == entity_key,
            )
        ).scalar_one_or_none()

        if not entity:
            return []

        return list(
            self.db.execute(
                select(Achievement)
                .join(EntityAchievement)
                .where(
                    EntityAchievement.entity_id == entity.id,
                    EntityAchievement.notified == False,  # noqa: E712
                )
            ).scalars().all()
        )

    def mark_notified(self, entity_key: str, achievement_key: str) -> bool:
        """Mark an achievement as notified.

        Args:
            entity_key: The entity.
            achievement_key: The achievement to mark.

        Returns:
            True if marked, False if not found.
        """
        achievement = self.get_achievement(achievement_key)
        if not achievement:
            return False

        entity = self.db.execute(
            select(Entity).where(
                Entity.session_id == self.game_session.id,
                Entity.entity_key == entity_key,
            )
        ).scalar_one_or_none()

        if not entity:
            return False

        entity_achievement = self.db.execute(
            select(EntityAchievement).where(
                EntityAchievement.entity_id == entity.id,
                EntityAchievement.achievement_id == achievement.id,
            )
        ).scalar_one_or_none()

        if not entity_achievement:
            return False

        entity_achievement.notified = True
        self.db.flush()
        return True

    def get_achievement_context(self, entity_key: str) -> str:
        """Generate context string for achievements.

        Args:
            entity_key: The entity to generate context for.

        Returns:
            Formatted context string, or empty string if no achievements.
        """
        unlocked = self.get_unlocked_achievements(entity_key)
        if not unlocked:
            return ""

        total_points = self.get_total_points(entity_key)

        lines = [f"## Achievements ({total_points} points)"]
        for ach in unlocked:
            lines.append(f"- **{ach.title}** ({ach.points} pts): {ach.description}")

        return "\n".join(lines)
