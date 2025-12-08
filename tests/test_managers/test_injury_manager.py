"""Tests for InjuryManager class."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.enums import BodyPart, InjurySeverity, InjuryType
from src.database.models.injuries import BodyInjury
from src.database.models.session import GameSession
from src.managers.injuries import InjuryManager, RECOVERY_TIMES, SEVERITY_PAIN
from src.managers.needs import NeedsManager
from tests.factories import (
    create_body_injury,
    create_character_needs,
    create_entity,
)


class TestInjuryManagerBasics:
    """Tests for InjuryManager basic operations."""

    def test_get_injuries_returns_empty_when_none(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_injuries returns empty list when no injuries."""
        entity = create_entity(db_session, game_session)
        manager = InjuryManager(db_session, game_session)

        result = manager.get_injuries(entity.id)

        assert result == []

    def test_get_injuries_returns_active_only_by_default(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_injuries filters to active injuries by default."""
        entity = create_entity(db_session, game_session)
        active_injury = create_body_injury(db_session, game_session, entity)
        healed_injury = create_body_injury(
            db_session, game_session, entity, is_healed=True
        )
        manager = InjuryManager(db_session, game_session)

        result = manager.get_injuries(entity.id)

        assert len(result) == 1
        assert result[0].id == active_injury.id

    def test_get_injuries_includes_healed_when_requested(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_injuries can include healed injuries."""
        entity = create_entity(db_session, game_session)
        create_body_injury(db_session, game_session, entity)
        create_body_injury(db_session, game_session, entity, is_healed=True)
        manager = InjuryManager(db_session, game_session)

        result = manager.get_injuries(entity.id, active_only=False)

        assert len(result) == 2

    def test_get_injury_by_part(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_injury_by_part filters by body part."""
        entity = create_entity(db_session, game_session)
        arm_injury = create_body_injury(
            db_session, game_session, entity, body_part=BodyPart.LEFT_ARM
        )
        leg_injury = create_body_injury(
            db_session, game_session, entity, body_part=BodyPart.RIGHT_LEG
        )
        manager = InjuryManager(db_session, game_session)

        result = manager.get_injury_by_part(entity.id, BodyPart.LEFT_ARM)

        assert len(result) == 1
        assert result[0].id == arm_injury.id


class TestAddInjury:
    """Tests for injury creation."""

    def test_add_injury_creates_record(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify add_injury creates a new injury record."""
        entity = create_entity(db_session, game_session)
        manager = InjuryManager(db_session, game_session)

        injury = manager.add_injury(
            entity_id=entity.id,
            body_part=BodyPart.HEAD,
            injury_type=InjuryType.CONCUSSION,
            severity=InjurySeverity.MODERATE,
            caused_by="Blunt force trauma",
            turn=5,
        )

        assert injury.id is not None
        assert injury.body_part == BodyPart.HEAD
        assert injury.injury_type == InjuryType.CONCUSSION
        assert injury.severity == InjurySeverity.MODERATE
        assert injury.caused_by == "Blunt force trauma"
        assert injury.occurred_turn == 5

    def test_add_injury_calculates_recovery_time(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify add_injury calculates appropriate recovery time."""
        entity = create_entity(db_session, game_session)
        manager = InjuryManager(db_session, game_session)

        injury = manager.add_injury(
            entity_id=entity.id,
            body_part=BodyPart.LEFT_LEG,
            injury_type=InjuryType.FRACTURE,
            severity=InjurySeverity.MODERATE,
            caused_by="Fall",
            turn=1,
        )

        # Fracture base: 42-84 days, avg=63. Moderate severity = 1.0x
        assert injury.base_recovery_days == 63  # Average
        assert injury.adjusted_recovery_days == 63.0

    def test_add_injury_severity_multiplier(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify severity multiplier affects recovery time."""
        entity = create_entity(db_session, game_session)
        manager = InjuryManager(db_session, game_session)

        minor_injury = manager.add_injury(
            entity_id=entity.id,
            body_part=BodyPart.LEFT_ARM,
            injury_type=InjuryType.BRUISE,
            severity=InjurySeverity.MINOR,
            caused_by="Impact",
            turn=1,
        )

        severe_injury = manager.add_injury(
            entity_id=entity.id,
            body_part=BodyPart.RIGHT_ARM,
            injury_type=InjuryType.BRUISE,
            severity=InjurySeverity.SEVERE,
            caused_by="Impact",
            turn=1,
        )

        # Minor = 0.5x, Severe = 1.5x
        assert minor_injury.adjusted_recovery_days < severe_injury.adjusted_recovery_days

    def test_add_injury_detects_reinjury(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify reinjury detection adds recovery time."""
        entity = create_entity(db_session, game_session)
        manager = InjuryManager(db_session, game_session)

        # First injury
        first_injury = manager.add_injury(
            entity_id=entity.id,
            body_part=BodyPart.LEFT_ARM,
            injury_type=InjuryType.SPRAIN,
            severity=InjurySeverity.MODERATE,
            caused_by="Twist",
            turn=1,
        )

        # Same body part = reinjury
        second_injury = manager.add_injury(
            entity_id=entity.id,
            body_part=BodyPart.LEFT_ARM,
            injury_type=InjuryType.SPRAIN,
            severity=InjurySeverity.MODERATE,
            caused_by="Twist again",
            turn=2,
        )

        assert second_injury.is_reinjured is True
        # Reinjury adds 50%
        assert second_injury.adjusted_recovery_days > first_injury.adjusted_recovery_days

    def test_add_injury_sets_pain_level(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify add_injury sets appropriate pain level."""
        entity = create_entity(db_session, game_session)
        manager = InjuryManager(db_session, game_session)

        injury = manager.add_injury(
            entity_id=entity.id,
            body_part=BodyPart.TORSO,
            injury_type=InjuryType.CUT,
            severity=InjurySeverity.SEVERE,
            caused_by="Blade",
            turn=1,
        )

        assert injury.current_pain_level == SEVERITY_PAIN[InjurySeverity.SEVERE]

    def test_add_injury_calculates_restrictions(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify activity restrictions are calculated."""
        entity = create_entity(db_session, game_session)
        manager = InjuryManager(db_session, game_session)

        injury = manager.add_injury(
            entity_id=entity.id,
            body_part=BodyPart.LEFT_LEG,
            injury_type=InjuryType.FRACTURE,
            severity=InjurySeverity.SEVERE,
            caused_by="Fall",
            turn=1,
        )

        assert injury.activity_restrictions is not None
        assert "walking" in injury.activity_restrictions
        assert "running" in injury.activity_restrictions


class TestHealingProgress:
    """Tests for injury healing mechanics."""

    def test_apply_healing_progresses_recovery(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify apply_healing advances recovery progress."""
        entity = create_entity(db_session, game_session)
        injury = create_body_injury(
            db_session, game_session, entity,
            base_recovery_days=10,
            adjusted_recovery_days=10,
            recovery_progress_days=0,
        )
        manager = InjuryManager(db_session, game_session)

        manager.apply_healing(entity.id, days_passed=2)

        db_session.refresh(injury)
        assert injury.recovery_progress_days == 2.0

    def test_apply_healing_reduces_pain(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify healing reduces pain level."""
        entity = create_entity(db_session, game_session)
        injury = create_body_injury(
            db_session, game_session, entity,
            severity=InjurySeverity.MODERATE,
            base_recovery_days=10,
            adjusted_recovery_days=10,
            recovery_progress_days=0,
            current_pain_level=35,
        )
        manager = InjuryManager(db_session, game_session)

        manager.apply_healing(entity.id, days_passed=5)

        db_session.refresh(injury)
        # 50% progress should reduce pain by ~50%
        assert injury.current_pain_level < 35

    def test_apply_healing_marks_healed_when_complete(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify injury is marked healed when recovery completes."""
        entity = create_entity(db_session, game_session)
        injury = create_body_injury(
            db_session, game_session, entity,
            base_recovery_days=10,
            adjusted_recovery_days=10,
            recovery_progress_days=8,
        )
        manager = InjuryManager(db_session, game_session)

        healed = manager.apply_healing(entity.id, days_passed=5)

        db_session.refresh(injury)
        assert injury.is_healed is True
        assert injury.current_pain_level == 0
        assert len(healed) == 1
        assert healed[0].id == injury.id

    def test_apply_healing_medical_care_reduces_time(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify medical care reduces recovery time."""
        entity = create_entity(db_session, game_session)
        injury = create_body_injury(
            db_session, game_session, entity,
            base_recovery_days=20,
            adjusted_recovery_days=20,
            recovery_progress_days=0,
        )
        original_time = injury.adjusted_recovery_days
        manager = InjuryManager(db_session, game_session)

        manager.apply_healing(entity.id, days_passed=1, medical_care_quality=100)

        db_session.refresh(injury)
        # 100% quality = 30% reduction
        assert injury.adjusted_recovery_days < original_time
        assert injury.received_medical_care is True

    def test_apply_healing_hardy_bonus(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify hardy constitution speeds healing."""
        entity = create_entity(db_session, game_session)
        injury = create_body_injury(
            db_session, game_session, entity,
            base_recovery_days=10,
            adjusted_recovery_days=10,
            recovery_progress_days=0,
        )
        manager = InjuryManager(db_session, game_session)

        manager.apply_healing(entity.id, days_passed=5, is_hardy=True)

        db_session.refresh(injury)
        # Hardy = 20% faster, so 5 days becomes 6 effective days
        assert injury.recovery_progress_days == 6.0

    def test_apply_healing_age_penalty(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify old age slows healing."""
        entity = create_entity(db_session, game_session)
        injury = create_body_injury(
            db_session, game_session, entity,
            base_recovery_days=10,
            adjusted_recovery_days=10,
            recovery_progress_days=0,
        )
        manager = InjuryManager(db_session, game_session)

        manager.apply_healing(entity.id, days_passed=10, age=60)

        db_session.refresh(injury)
        # Age > 50 = 77% speed (30% slower)
        assert injury.recovery_progress_days < 10


class TestActivityImpact:
    """Tests for activity impact calculations."""

    def test_get_activity_impact_no_injuries(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify unaffected when no injuries."""
        entity = create_entity(db_session, game_session)
        manager = InjuryManager(db_session, game_session)

        impact = manager.get_activity_impact(entity.id, "walking")

        assert impact.impact_type == "unaffected"
        assert impact.can_perform is True
        assert impact.effectiveness == 1.0

    def test_get_activity_impact_leg_injury_walking(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify leg injury affects walking."""
        entity = create_entity(db_session, game_session)
        manager = InjuryManager(db_session, game_session)

        manager.add_injury(
            entity_id=entity.id,
            body_part=BodyPart.LEFT_LEG,
            injury_type=InjuryType.SPRAIN,
            severity=InjurySeverity.MODERATE,
            caused_by="Twist",
            turn=1,
        )

        impact = manager.get_activity_impact(entity.id, "walking")

        assert impact.impact_type in ("painful", "penalty")
        assert len(impact.injuries) == 1

    def test_get_activity_impact_critical_impossible(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify critical leg injury makes running impossible."""
        entity = create_entity(db_session, game_session)
        manager = InjuryManager(db_session, game_session)

        manager.add_injury(
            entity_id=entity.id,
            body_part=BodyPart.LEFT_LEG,
            injury_type=InjuryType.FRACTURE,
            severity=InjurySeverity.CRITICAL,
            caused_by="Crushing impact",
            turn=1,
        )

        impact = manager.get_activity_impact(entity.id, "running")

        assert impact.impact_type == "impossible"
        assert impact.can_perform is False
        assert impact.effectiveness == 0.0

    def test_get_activity_impact_combines_multiple_injuries(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify multiple injuries combine penalties."""
        entity = create_entity(db_session, game_session)
        manager = InjuryManager(db_session, game_session)

        # Two leg injuries
        manager.add_injury(
            entity_id=entity.id,
            body_part=BodyPart.LEFT_LEG,
            injury_type=InjuryType.SPRAIN,
            severity=InjurySeverity.MODERATE,
            caused_by="Twist",
            turn=1,
        )
        manager.add_injury(
            entity_id=entity.id,
            body_part=BodyPart.RIGHT_LEG,
            injury_type=InjuryType.SPRAIN,
            severity=InjurySeverity.MODERATE,
            caused_by="Twist",
            turn=1,
        )

        impact = manager.get_activity_impact(entity.id, "walking")

        # Combined penalty should be worse
        assert len(impact.injuries) == 2


class TestPainCalculation:
    """Tests for pain level calculations."""

    def test_get_total_pain_no_injuries(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify zero pain when no injuries."""
        entity = create_entity(db_session, game_session)
        manager = InjuryManager(db_session, game_session)

        pain = manager.get_total_pain(entity.id)

        assert pain == 0

    def test_get_total_pain_single_injury(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify pain from single injury."""
        entity = create_entity(db_session, game_session)
        create_body_injury(
            db_session, game_session, entity,
            current_pain_level=40,
        )
        manager = InjuryManager(db_session, game_session)

        pain = manager.get_total_pain(entity.id)

        assert pain == 40

    def test_get_total_pain_multiple_injuries(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify pain calculation with multiple injuries."""
        entity = create_entity(db_session, game_session)
        create_body_injury(
            db_session, game_session, entity,
            body_part=BodyPart.LEFT_ARM,
            current_pain_level=50,
        )
        create_body_injury(
            db_session, game_session, entity,
            body_part=BodyPart.RIGHT_LEG,
            current_pain_level=30,
        )
        manager = InjuryManager(db_session, game_session)

        pain = manager.get_total_pain(entity.id)

        # max(50, 30) + 30% of other = 50 + 9 = 59
        assert pain == 59

    def test_get_total_pain_capped_at_100(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify total pain capped at 100."""
        entity = create_entity(db_session, game_session)
        create_body_injury(
            db_session, game_session, entity,
            body_part=BodyPart.HEAD,
            current_pain_level=80,
        )
        create_body_injury(
            db_session, game_session, entity,
            body_part=BodyPart.TORSO,
            current_pain_level=70,
        )
        create_body_injury(
            db_session, game_session, entity,
            body_part=BodyPart.LEFT_LEG,
            current_pain_level=60,
        )
        manager = InjuryManager(db_session, game_session)

        pain = manager.get_total_pain(entity.id)

        assert pain <= 100

    def test_sync_pain_to_needs(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify pain syncs to character needs as wellness (inverted)."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, wellness=100)
        create_body_injury(
            db_session, game_session, entity,
            current_pain_level=50,
        )
        injury_manager = InjuryManager(db_session, game_session)
        needs_manager = NeedsManager(db_session, game_session)

        injury_manager.sync_pain_to_needs(entity.id, needs_manager)

        needs = needs_manager.get_needs(entity.id)
        # wellness = 100 - pain, so 50 pain = 50 wellness
        assert needs.wellness == 50


class TestInjurySummary:
    """Tests for injury summary functionality."""

    def test_get_injuries_summary_no_injuries(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify summary when no injuries."""
        entity = create_entity(db_session, game_session)
        manager = InjuryManager(db_session, game_session)

        summary = manager.get_injuries_summary(entity.id)

        assert summary["has_injuries"] is False
        assert summary["injuries"] == []
        assert summary["total_pain"] == 0

    def test_get_injuries_summary_with_injuries(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify complete injury summary."""
        entity = create_entity(db_session, game_session)
        create_body_injury(
            db_session, game_session, entity,
            body_part=BodyPart.LEFT_ARM,
            injury_type=InjuryType.CUT,
            severity=InjurySeverity.MODERATE,
            current_pain_level=30,
            base_recovery_days=10,
            adjusted_recovery_days=10,
            recovery_progress_days=2,
        )
        manager = InjuryManager(db_session, game_session)

        summary = manager.get_injuries_summary(entity.id)

        assert summary["has_injuries"] is True
        assert len(summary["injuries"]) == 1
        assert summary["injuries"][0]["body_part"] == "left_arm"
        assert summary["injuries"][0]["healing_progress"] == 20.0  # 2/10 = 20%
        assert summary["total_pain"] == 30
