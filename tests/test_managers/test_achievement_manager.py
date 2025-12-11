"""Tests for AchievementManager - achievement tracking and unlocking."""

import pytest
from sqlalchemy.orm import Session

from src.database.models import Entity, EntityType, GameSession
from src.database.models.progression import Achievement, AchievementType
from src.managers.achievement_manager import (
    AchievementManager,
    AchievementUnlock,
    AchievementProgress,
)
from tests.factories import create_entity


@pytest.fixture
def achievement_manager(
    db_session: Session, game_session: GameSession
) -> AchievementManager:
    """Create an AchievementManager instance."""
    return AchievementManager(db_session, game_session)


@pytest.fixture
def player(db_session: Session, game_session: GameSession) -> Entity:
    """Create a player entity."""
    return create_entity(
        db_session,
        game_session,
        entity_key="hero",
        entity_type=EntityType.PLAYER,
    )


class TestCreateAchievement:
    """Tests for achievement definition creation."""

    def test_create_achievement(
        self,
        achievement_manager: AchievementManager,
        db_session: Session,
    ):
        """Verify achievement creation."""
        achievement = achievement_manager.create_achievement(
            achievement_key="first_blood",
            title="First Blood",
            description="Win your first combat",
            achievement_type=AchievementType.MILESTONE,
            points=10,
        )

        assert achievement.achievement_key == "first_blood"
        assert achievement.title == "First Blood"
        assert achievement.achievement_type == AchievementType.MILESTONE
        assert achievement.points == 10
        assert achievement.is_hidden is False

    def test_create_hidden_achievement(
        self,
        achievement_manager: AchievementManager,
    ):
        """Verify hidden achievement creation."""
        achievement = achievement_manager.create_achievement(
            achievement_key="secret_ending",
            title="The Secret Ending",
            description="Discover the hidden truth",
            achievement_type=AchievementType.MILESTONE,
            is_hidden=True,
        )

        assert achievement.is_hidden is True

    def test_create_achievement_with_requirements(
        self,
        achievement_manager: AchievementManager,
    ):
        """Verify achievement with requirements."""
        achievement = achievement_manager.create_achievement(
            achievement_key="master_swordsman",
            title="Master Swordsman",
            description="Reach Master tier in swordfighting",
            achievement_type=AchievementType.TITLE,
            requirements={"skill": "swordfighting", "tier": "Master"},
        )

        assert achievement.requirements["skill"] == "swordfighting"
        assert achievement.requirements["tier"] == "Master"

    def test_get_achievement(
        self,
        achievement_manager: AchievementManager,
    ):
        """Verify achievement retrieval."""
        achievement_manager.create_achievement(
            achievement_key="explorer",
            title="Explorer",
            description="Discover 10 locations",
            achievement_type=AchievementType.FIRST_DISCOVERY,
        )

        achievement = achievement_manager.get_achievement("explorer")

        assert achievement is not None
        assert achievement.title == "Explorer"

    def test_get_achievement_not_found(
        self,
        achievement_manager: AchievementManager,
    ):
        """Verify None returned for non-existent achievement."""
        achievement = achievement_manager.get_achievement("nonexistent")
        assert achievement is None


class TestUnlockAchievement:
    """Tests for achievement unlocking."""

    def test_unlock_achievement(
        self,
        achievement_manager: AchievementManager,
        player: Entity,
        db_session: Session,
    ):
        """Verify achievement unlocking."""
        achievement_manager.create_achievement(
            achievement_key="first_step",
            title="First Step",
            description="Begin your journey",
            achievement_type=AchievementType.MILESTONE,
            points=5,
        )

        unlock = achievement_manager.unlock_achievement(
            entity_key="hero",
            achievement_key="first_step",
        )

        assert unlock.unlocked is True
        assert unlock.achievement_key == "first_step"
        assert unlock.title == "First Step"
        assert unlock.points == 5
        assert unlock.already_unlocked is False

    def test_unlock_already_unlocked(
        self,
        achievement_manager: AchievementManager,
        player: Entity,
    ):
        """Verify already unlocked achievement returns already_unlocked=True."""
        achievement_manager.create_achievement(
            achievement_key="first_step",
            title="First Step",
            description="Begin your journey",
            achievement_type=AchievementType.MILESTONE,
        )
        achievement_manager.unlock_achievement("hero", "first_step")

        unlock = achievement_manager.unlock_achievement("hero", "first_step")

        assert unlock.unlocked is True
        assert unlock.already_unlocked is True

    def test_unlock_nonexistent_achievement(
        self,
        achievement_manager: AchievementManager,
        player: Entity,
    ):
        """Verify error when unlocking non-existent achievement."""
        with pytest.raises(ValueError, match="not found"):
            achievement_manager.unlock_achievement("hero", "nonexistent")

    def test_unlock_nonexistent_entity(
        self,
        achievement_manager: AchievementManager,
    ):
        """Verify error when entity not found."""
        achievement_manager.create_achievement(
            achievement_key="test",
            title="Test",
            description="Test",
            achievement_type=AchievementType.MILESTONE,
        )

        with pytest.raises(ValueError, match="Entity.*not found"):
            achievement_manager.unlock_achievement("nonexistent", "test")


class TestCheckAchievement:
    """Tests for achievement checking."""

    def test_check_achievement_locked(
        self,
        achievement_manager: AchievementManager,
        player: Entity,
    ):
        """Verify checking locked achievement."""
        achievement_manager.create_achievement(
            achievement_key="locked_one",
            title="Locked",
            description="Not yet unlocked",
            achievement_type=AchievementType.MILESTONE,
        )

        is_unlocked = achievement_manager.is_achievement_unlocked(
            entity_key="hero",
            achievement_key="locked_one",
        )

        assert is_unlocked is False

    def test_check_achievement_unlocked(
        self,
        achievement_manager: AchievementManager,
        player: Entity,
    ):
        """Verify checking unlocked achievement."""
        achievement_manager.create_achievement(
            achievement_key="unlocked_one",
            title="Unlocked",
            description="Already unlocked",
            achievement_type=AchievementType.MILESTONE,
        )
        achievement_manager.unlock_achievement("hero", "unlocked_one")

        is_unlocked = achievement_manager.is_achievement_unlocked(
            entity_key="hero",
            achievement_key="unlocked_one",
        )

        assert is_unlocked is True


class TestGetAchievements:
    """Tests for achievement listing."""

    def test_get_unlocked_achievements(
        self,
        achievement_manager: AchievementManager,
        player: Entity,
    ):
        """Verify getting unlocked achievements."""
        achievement_manager.create_achievement(
            achievement_key="ach1",
            title="Achievement 1",
            description="First",
            achievement_type=AchievementType.MILESTONE,
        )
        achievement_manager.create_achievement(
            achievement_key="ach2",
            title="Achievement 2",
            description="Second",
            achievement_type=AchievementType.TITLE,
        )
        achievement_manager.create_achievement(
            achievement_key="ach3",
            title="Achievement 3",
            description="Third",
            achievement_type=AchievementType.RANK,
        )
        achievement_manager.unlock_achievement("hero", "ach1")
        achievement_manager.unlock_achievement("hero", "ach3")

        unlocked = achievement_manager.get_unlocked_achievements("hero")

        assert len(unlocked) == 2
        keys = [a.achievement_key for a in unlocked]
        assert "ach1" in keys
        assert "ach3" in keys
        assert "ach2" not in keys

    def test_get_all_achievements(
        self,
        achievement_manager: AchievementManager,
    ):
        """Verify getting all achievements."""
        achievement_manager.create_achievement(
            achievement_key="ach1",
            title="Achievement 1",
            description="First",
            achievement_type=AchievementType.MILESTONE,
        )
        achievement_manager.create_achievement(
            achievement_key="ach2",
            title="Achievement 2",
            description="Second",
            achievement_type=AchievementType.TITLE,
            is_hidden=True,
        )

        achievements = achievement_manager.get_all_achievements()

        assert len(achievements) == 2

    def test_get_achievements_by_type(
        self,
        achievement_manager: AchievementManager,
    ):
        """Verify filtering achievements by type."""
        achievement_manager.create_achievement(
            achievement_key="title1",
            title="Title 1",
            description="A title",
            achievement_type=AchievementType.TITLE,
        )
        achievement_manager.create_achievement(
            achievement_key="milestone1",
            title="Milestone 1",
            description="A milestone",
            achievement_type=AchievementType.MILESTONE,
        )
        achievement_manager.create_achievement(
            achievement_key="title2",
            title="Title 2",
            description="Another title",
            achievement_type=AchievementType.TITLE,
        )

        titles = achievement_manager.get_achievements_by_type(AchievementType.TITLE)

        assert len(titles) == 2
        assert all(a.achievement_type == AchievementType.TITLE for a in titles)


class TestAchievementPoints:
    """Tests for achievement points tracking."""

    def test_get_total_points(
        self,
        achievement_manager: AchievementManager,
        player: Entity,
    ):
        """Verify total points calculation."""
        achievement_manager.create_achievement(
            achievement_key="ach1",
            title="Achievement 1",
            description="First",
            achievement_type=AchievementType.MILESTONE,
            points=10,
        )
        achievement_manager.create_achievement(
            achievement_key="ach2",
            title="Achievement 2",
            description="Second",
            achievement_type=AchievementType.TITLE,
            points=25,
        )
        achievement_manager.create_achievement(
            achievement_key="ach3",
            title="Achievement 3",
            description="Third",
            achievement_type=AchievementType.RANK,
            points=50,
        )
        achievement_manager.unlock_achievement("hero", "ach1")
        achievement_manager.unlock_achievement("hero", "ach2")

        total = achievement_manager.get_total_points("hero")

        assert total == 35  # 10 + 25

    def test_get_total_points_empty(
        self,
        achievement_manager: AchievementManager,
        player: Entity,
    ):
        """Verify total points when no achievements unlocked."""
        total = achievement_manager.get_total_points("hero")
        assert total == 0


class TestAchievementProgress:
    """Tests for achievement progress tracking."""

    def test_update_progress(
        self,
        achievement_manager: AchievementManager,
        player: Entity,
    ):
        """Verify progress update for tiered achievements."""
        achievement_manager.create_achievement(
            achievement_key="monster_slayer",
            title="Monster Slayer",
            description="Defeat 100 monsters",
            achievement_type=AchievementType.MILESTONE,
            target_count=100,
        )

        progress = achievement_manager.update_progress(
            entity_key="hero",
            achievement_key="monster_slayer",
            increment=5,
        )

        assert progress.current_count == 5
        assert progress.target_count == 100
        assert progress.percentage == 5.0
        assert progress.unlocked is False

    def test_progress_triggers_unlock(
        self,
        achievement_manager: AchievementManager,
        player: Entity,
    ):
        """Verify progress reaching target unlocks achievement."""
        achievement_manager.create_achievement(
            achievement_key="monster_slayer",
            title="Monster Slayer",
            description="Defeat 10 monsters",
            achievement_type=AchievementType.MILESTONE,
            target_count=10,
            points=20,
        )

        # Progress to 9
        achievement_manager.update_progress("hero", "monster_slayer", 9)
        # Progress to 10 - should unlock
        progress = achievement_manager.update_progress("hero", "monster_slayer", 1)

        assert progress.current_count == 10
        assert progress.unlocked is True
        assert achievement_manager.is_achievement_unlocked("hero", "monster_slayer")

    def test_get_progress(
        self,
        achievement_manager: AchievementManager,
        player: Entity,
    ):
        """Verify progress retrieval."""
        achievement_manager.create_achievement(
            achievement_key="explorer",
            title="Explorer",
            description="Visit 50 locations",
            achievement_type=AchievementType.FIRST_DISCOVERY,
            target_count=50,
        )
        achievement_manager.update_progress("hero", "explorer", 25)

        progress = achievement_manager.get_progress("hero", "explorer")

        assert progress.current_count == 25
        assert progress.target_count == 50
        assert progress.percentage == 50.0


class TestAchievementContext:
    """Tests for achievement context generation."""

    def test_get_achievement_context(
        self,
        achievement_manager: AchievementManager,
        player: Entity,
    ):
        """Verify achievement context generation."""
        achievement_manager.create_achievement(
            achievement_key="title1",
            title="Hero of the Realm",
            description="Save the kingdom",
            achievement_type=AchievementType.TITLE,
            points=100,
        )
        achievement_manager.unlock_achievement("hero", "title1")

        context = achievement_manager.get_achievement_context("hero")

        assert "Achievements" in context
        assert "Hero of the Realm" in context
        assert "100" in context

    def test_get_achievement_context_empty(
        self,
        achievement_manager: AchievementManager,
        player: Entity,
    ):
        """Verify empty context when no achievements."""
        context = achievement_manager.get_achievement_context("hero")
        assert context == ""


class TestRecentAchievements:
    """Tests for recent achievement notifications."""

    def test_get_recent_unlocks(
        self,
        achievement_manager: AchievementManager,
        player: Entity,
    ):
        """Verify recent unlocks retrieval."""
        for i in range(5):
            achievement_manager.create_achievement(
                achievement_key=f"ach{i}",
                title=f"Achievement {i}",
                description=f"Description {i}",
                achievement_type=AchievementType.MILESTONE,
            )
            achievement_manager.unlock_achievement("hero", f"ach{i}")

        recent = achievement_manager.get_recent_unlocks("hero", limit=3)

        assert len(recent) == 3

    def test_mark_achievement_notified(
        self,
        achievement_manager: AchievementManager,
        player: Entity,
    ):
        """Verify marking achievement as notified."""
        achievement_manager.create_achievement(
            achievement_key="notify_test",
            title="Notify Test",
            description="Test notification",
            achievement_type=AchievementType.MILESTONE,
        )
        unlock = achievement_manager.unlock_achievement("hero", "notify_test")

        # Should be in pending notifications
        pending = achievement_manager.get_pending_notifications("hero")
        assert len(pending) == 1

        # Mark as notified
        achievement_manager.mark_notified("hero", "notify_test")

        # Should no longer be pending
        pending = achievement_manager.get_pending_notifications("hero")
        assert len(pending) == 0
