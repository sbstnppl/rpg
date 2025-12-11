"""Tests for ProgressionManager - skill advancement through usage."""

import pytest
from sqlalchemy.orm import Session

from src.database.models import Entity, EntitySkill, EntityType, GameSession
from src.managers.progression_manager import (
    AdvancementResult,
    ProgressionManager,
    SkillProgress,
)
from tests.factories import create_entity


def create_skill(
    db_session: Session,
    entity: Entity,
    skill_key: str,
    proficiency: int = 1,
    usage_count: int = 0,
    successful_uses: int = 0,
) -> EntitySkill:
    """Create a skill for an entity."""
    skill = EntitySkill(
        entity_id=entity.id,
        skill_key=skill_key,
        proficiency_level=proficiency,
        usage_count=usage_count,
        successful_uses=successful_uses,
    )
    db_session.add(skill)
    db_session.commit()
    db_session.refresh(skill)
    return skill


@pytest.fixture
def progression_manager(
    db_session: Session, game_session: GameSession
) -> ProgressionManager:
    """Create a ProgressionManager instance."""
    return ProgressionManager(db_session, game_session)


@pytest.fixture
def player(db_session: Session, game_session: GameSession) -> Entity:
    """Create a player entity."""
    return create_entity(
        db_session,
        game_session,
        entity_key="hero",
        entity_type=EntityType.PLAYER,
    )


class TestRecordSkillUse:
    """Tests for recording skill usage."""

    def test_record_successful_use(
        self,
        progression_manager: ProgressionManager,
        player: Entity,
        db_session: Session,
    ):
        """Verify successful skill use is recorded."""
        create_skill(db_session, player, "athletics", proficiency=20)

        result = progression_manager.record_skill_use(
            entity_key="hero",
            skill_key="athletics",
            success=True,
        )

        skill = db_session.query(EntitySkill).filter_by(
            entity_id=player.id, skill_key="athletics"
        ).first()
        assert skill.usage_count == 1
        assert skill.successful_uses == 1
        assert result.usage_count == 1
        assert result.successful_uses == 1

    def test_record_failed_use(
        self,
        progression_manager: ProgressionManager,
        player: Entity,
        db_session: Session,
    ):
        """Verify failed skill use counts usage but not success."""
        create_skill(db_session, player, "stealth", proficiency=20)

        result = progression_manager.record_skill_use(
            entity_key="hero",
            skill_key="stealth",
            success=False,
        )

        skill = db_session.query(EntitySkill).filter_by(
            entity_id=player.id, skill_key="stealth"
        ).first()
        assert skill.usage_count == 1
        assert skill.successful_uses == 0
        assert result.usage_count == 1
        assert result.successful_uses == 0

    def test_record_use_creates_skill_if_missing(
        self,
        progression_manager: ProgressionManager,
        player: Entity,
        db_session: Session,
    ):
        """Verify skill is created if it doesn't exist."""
        result = progression_manager.record_skill_use(
            entity_key="hero",
            skill_key="lockpicking",
            success=True,
        )

        skill = db_session.query(EntitySkill).filter_by(
            entity_id=player.id, skill_key="lockpicking"
        ).first()
        assert skill is not None
        assert skill.proficiency_level == 1  # Starting proficiency
        assert skill.usage_count == 1
        assert skill.successful_uses == 1

    def test_record_use_entity_not_found(
        self,
        progression_manager: ProgressionManager,
    ):
        """Verify error when entity not found."""
        with pytest.raises(ValueError, match="not found"):
            progression_manager.record_skill_use(
                entity_key="nonexistent",
                skill_key="athletics",
                success=True,
            )


class TestSkillAdvancement:
    """Tests for skill advancement mechanics."""

    def test_no_advancement_first_10_uses(
        self,
        progression_manager: ProgressionManager,
        player: Entity,
        db_session: Session,
    ):
        """Verify no advancement in first 10 uses (learning basics)."""
        create_skill(db_session, player, "athletics", proficiency=20, successful_uses=9)

        result = progression_manager.record_skill_use(
            entity_key="hero",
            skill_key="athletics",
            success=True,
        )

        assert result.advanced is False
        skill = db_session.query(EntitySkill).filter_by(
            entity_id=player.id, skill_key="athletics"
        ).first()
        assert skill.proficiency_level == 20  # Unchanged

    def test_advancement_after_10_uses(
        self,
        progression_manager: ProgressionManager,
        player: Entity,
        db_session: Session,
    ):
        """Verify advancement starts after 10 successful uses (first milestone at 15)."""
        # First milestone in early tier (11-25) is at 15 successful uses
        # Uses 11-15 = 5 uses in tier = first milestone
        create_skill(db_session, player, "athletics", proficiency=20, successful_uses=14, usage_count=14)

        result = progression_manager.record_skill_use(
            entity_key="hero",
            skill_key="athletics",
            success=True,
        )

        # 15 uses should trigger first advancement in early tier
        assert result.advanced is True
        assert result.proficiency_gained == 3  # Early tier gives +3
        skill = db_session.query(EntitySkill).filter_by(
            entity_id=player.id, skill_key="athletics"
        ).first()
        assert skill.proficiency_level == 23

    def test_fast_advancement_early_stage(
        self,
        progression_manager: ProgressionManager,
        player: Entity,
        db_session: Session,
    ):
        """Verify fast advancement in early stage (11-25 uses)."""
        # At 14 successful uses, advancement gives +3 per 5 uses
        create_skill(db_session, player, "athletics", proficiency=20, successful_uses=14, usage_count=14)

        result = progression_manager.record_skill_use(
            entity_key="hero",
            skill_key="athletics",
            success=True,
        )

        # 15 uses = 1 milestone in early stage = +3 proficiency
        assert result.advanced is True
        assert result.proficiency_gained == 3
        skill = db_session.query(EntitySkill).filter_by(
            entity_id=player.id, skill_key="athletics"
        ).first()
        assert skill.proficiency_level == 23

    def test_steady_advancement_mid_stage(
        self,
        progression_manager: ProgressionManager,
        player: Entity,
        db_session: Session,
    ):
        """Verify steady advancement in mid stage (26-50 uses)."""
        # At 29 successful uses, advancement gives +2 per 5 uses
        create_skill(db_session, player, "athletics", proficiency=30, successful_uses=29, usage_count=30)

        result = progression_manager.record_skill_use(
            entity_key="hero",
            skill_key="athletics",
            success=True,
        )

        # 30 uses = milestone in mid stage = +2 proficiency
        assert result.advanced is True
        assert result.proficiency_gained == 2
        skill = db_session.query(EntitySkill).filter_by(
            entity_id=player.id, skill_key="athletics"
        ).first()
        assert skill.proficiency_level == 32

    def test_slow_advancement_late_stage(
        self,
        progression_manager: ProgressionManager,
        player: Entity,
        db_session: Session,
    ):
        """Verify slow advancement in late stage (51-100 uses)."""
        # At 54 successful uses, advancement gives +1 per 5 uses
        create_skill(db_session, player, "athletics", proficiency=50, successful_uses=54, usage_count=60)

        result = progression_manager.record_skill_use(
            entity_key="hero",
            skill_key="athletics",
            success=True,
        )

        # 55 uses = milestone in late stage = +1 proficiency
        assert result.advanced is True
        assert result.proficiency_gained == 1
        skill = db_session.query(EntitySkill).filter_by(
            entity_id=player.id, skill_key="athletics"
        ).first()
        assert skill.proficiency_level == 51

    def test_very_slow_advancement_mastery_stage(
        self,
        progression_manager: ProgressionManager,
        player: Entity,
        db_session: Session,
    ):
        """Verify very slow advancement in mastery stage (100+ uses)."""
        # At 109 successful uses, advancement gives +1 per 10 uses
        create_skill(db_session, player, "athletics", proficiency=70, successful_uses=109, usage_count=120)

        result = progression_manager.record_skill_use(
            entity_key="hero",
            skill_key="athletics",
            success=True,
        )

        # 110 uses = milestone in mastery stage = +1 proficiency
        assert result.advanced is True
        assert result.proficiency_gained == 1
        skill = db_session.query(EntitySkill).filter_by(
            entity_id=player.id, skill_key="athletics"
        ).first()
        assert skill.proficiency_level == 71

    def test_proficiency_capped_at_100(
        self,
        progression_manager: ProgressionManager,
        player: Entity,
        db_session: Session,
    ):
        """Verify proficiency is capped at 100."""
        create_skill(db_session, player, "athletics", proficiency=99, successful_uses=14, usage_count=14)

        result = progression_manager.record_skill_use(
            entity_key="hero",
            skill_key="athletics",
            success=True,
        )

        skill = db_session.query(EntitySkill).filter_by(
            entity_id=player.id, skill_key="athletics"
        ).first()
        assert skill.proficiency_level == 100  # Capped

    def test_no_advancement_on_failed_use(
        self,
        progression_manager: ProgressionManager,
        player: Entity,
        db_session: Session,
    ):
        """Verify no advancement on failed skill use."""
        # At 14 successful uses, would advance on success
        create_skill(db_session, player, "athletics", proficiency=20, successful_uses=14, usage_count=14)

        result = progression_manager.record_skill_use(
            entity_key="hero",
            skill_key="athletics",
            success=False,
        )

        assert result.advanced is False
        skill = db_session.query(EntitySkill).filter_by(
            entity_id=player.id, skill_key="athletics"
        ).first()
        assert skill.proficiency_level == 20  # Unchanged


class TestSkillProgress:
    """Tests for skill progress tracking."""

    def test_get_skill_progress(
        self,
        progression_manager: ProgressionManager,
        player: Entity,
        db_session: Session,
    ):
        """Verify skill progress retrieval."""
        create_skill(db_session, player, "athletics", proficiency=45, successful_uses=22, usage_count=30)

        progress = progression_manager.get_skill_progress("hero", "athletics")

        assert progress.skill_key == "athletics"
        assert progress.proficiency_level == 45
        assert progress.tier_name == "Competent"
        assert progress.usage_count == 30
        assert progress.successful_uses == 22
        assert progress.uses_to_next_milestone > 0

    def test_get_skill_progress_not_found(
        self,
        progression_manager: ProgressionManager,
        player: Entity,
    ):
        """Verify None returned for non-existent skill."""
        progress = progression_manager.get_skill_progress("hero", "nonexistent")
        assert progress is None

    def test_get_all_skill_progress(
        self,
        progression_manager: ProgressionManager,
        player: Entity,
        db_session: Session,
    ):
        """Verify retrieval of all skills with progress."""
        create_skill(db_session, player, "athletics", proficiency=40)
        create_skill(db_session, player, "stealth", proficiency=60)
        create_skill(db_session, player, "persuasion", proficiency=25)

        all_progress = progression_manager.get_all_skill_progress("hero")

        assert len(all_progress) == 3
        keys = [p.skill_key for p in all_progress]
        assert "athletics" in keys
        assert "stealth" in keys
        assert "persuasion" in keys


class TestTierProgression:
    """Tests for tier progression tracking."""

    def test_tier_change_notification(
        self,
        progression_manager: ProgressionManager,
        player: Entity,
        db_session: Session,
    ):
        """Verify tier change is detected."""
        # Proficiency 19 -> 20 is Novice -> Apprentice
        create_skill(db_session, player, "athletics", proficiency=19, successful_uses=14, usage_count=14)

        result = progression_manager.record_skill_use(
            entity_key="hero",
            skill_key="athletics",
            success=True,
        )

        # Should advance by +3 to 22
        assert result.advanced is True
        assert result.tier_changed is True
        assert result.new_tier == "Apprentice"
        assert result.old_tier == "Novice"

    def test_no_tier_change_within_tier(
        self,
        progression_manager: ProgressionManager,
        player: Entity,
        db_session: Session,
    ):
        """Verify no tier change within same tier."""
        # Proficiency 22 -> 25 stays in Apprentice
        create_skill(db_session, player, "athletics", proficiency=22, successful_uses=14, usage_count=14)

        result = progression_manager.record_skill_use(
            entity_key="hero",
            skill_key="athletics",
            success=True,
        )

        assert result.advanced is True
        assert result.tier_changed is False


class TestManualAdvancement:
    """Tests for manual skill advancement (training, etc.)."""

    def test_advance_skill_manually(
        self,
        progression_manager: ProgressionManager,
        player: Entity,
        db_session: Session,
    ):
        """Verify manual skill advancement."""
        create_skill(db_session, player, "athletics", proficiency=20)

        result = progression_manager.advance_skill(
            entity_key="hero",
            skill_key="athletics",
            amount=10,
            reason="Training with master",
        )

        assert result.proficiency_gained == 10
        skill = db_session.query(EntitySkill).filter_by(
            entity_id=player.id, skill_key="athletics"
        ).first()
        assert skill.proficiency_level == 30

    def test_advance_skill_respects_cap(
        self,
        progression_manager: ProgressionManager,
        player: Entity,
        db_session: Session,
    ):
        """Verify manual advancement respects cap."""
        create_skill(db_session, player, "athletics", proficiency=95)

        result = progression_manager.advance_skill(
            entity_key="hero",
            skill_key="athletics",
            amount=10,
        )

        assert result.proficiency_gained == 5  # Only 5 to reach cap
        skill = db_session.query(EntitySkill).filter_by(
            entity_id=player.id, skill_key="athletics"
        ).first()
        assert skill.proficiency_level == 100

    def test_advance_skill_creates_if_missing(
        self,
        progression_manager: ProgressionManager,
        player: Entity,
        db_session: Session,
    ):
        """Verify manual advancement creates skill if missing."""
        result = progression_manager.advance_skill(
            entity_key="hero",
            skill_key="swimming",
            amount=15,
        )

        skill = db_session.query(EntitySkill).filter_by(
            entity_id=player.id, skill_key="swimming"
        ).first()
        assert skill is not None
        # Starts at 1, gains 15 = 16
        assert skill.proficiency_level == 16


class TestProgressionContext:
    """Tests for progression context string generation."""

    def test_get_progression_context(
        self,
        progression_manager: ProgressionManager,
        player: Entity,
        db_session: Session,
    ):
        """Verify progression context generation."""
        create_skill(db_session, player, "athletics", proficiency=45, successful_uses=22, usage_count=30)
        create_skill(db_session, player, "stealth", proficiency=75, successful_uses=80, usage_count=100)

        context = progression_manager.get_progression_context("hero")

        assert "Skill Progress" in context
        assert "athletics" in context.lower()
        assert "stealth" in context.lower()
        assert "Competent" in context  # athletics tier
        assert "Expert" in context  # stealth tier

    def test_get_progression_context_empty(
        self,
        progression_manager: ProgressionManager,
        player: Entity,
    ):
        """Verify empty context when no skills."""
        context = progression_manager.get_progression_context("hero")
        assert context == ""
