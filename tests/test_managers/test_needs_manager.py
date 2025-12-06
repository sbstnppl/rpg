"""Tests for NeedsManager class."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.character_state import CharacterNeeds, IntimacyProfile
from src.database.models.enums import DriveLevel
from src.database.models.session import GameSession
from src.managers.needs import ActivityType, NeedsManager, DECAY_RATES
from tests.factories import (
    create_character_needs,
    create_entity,
    create_intimacy_profile,
)


class TestNeedsManagerBasics:
    """Tests for NeedsManager basic operations."""

    def test_get_needs_returns_none_when_not_exists(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_needs returns None when no needs exist."""
        entity = create_entity(db_session, game_session)
        manager = NeedsManager(db_session, game_session)

        result = manager.get_needs(entity.id)

        assert result is None

    def test_get_needs_returns_existing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_needs returns existing CharacterNeeds."""
        entity = create_entity(db_session, game_session)
        needs = create_character_needs(db_session, game_session, entity, hunger=30)
        manager = NeedsManager(db_session, game_session)

        result = manager.get_needs(entity.id)

        assert result is not None
        assert result.id == needs.id
        assert result.hunger == 30

    def test_get_or_create_needs_creates_when_missing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_or_create_needs creates new CharacterNeeds."""
        entity = create_entity(db_session, game_session)
        manager = NeedsManager(db_session, game_session)

        result = manager.get_or_create_needs(entity.id)

        assert result is not None
        assert result.entity_id == entity.id
        assert result.session_id == game_session.id

    def test_get_or_create_needs_returns_existing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_or_create_needs returns existing when present."""
        entity = create_entity(db_session, game_session)
        needs = create_character_needs(db_session, game_session, entity, hunger=75)
        manager = NeedsManager(db_session, game_session)

        result = manager.get_or_create_needs(entity.id)

        assert result.id == needs.id
        assert result.hunger == 75

    def test_get_intimacy_profile_returns_none_when_missing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_intimacy_profile returns None when not exists."""
        entity = create_entity(db_session, game_session)
        manager = NeedsManager(db_session, game_session)

        result = manager.get_intimacy_profile(entity.id)

        assert result is None

    def test_get_intimacy_profile_returns_existing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_intimacy_profile returns existing profile."""
        entity = create_entity(db_session, game_session)
        profile = create_intimacy_profile(
            db_session, game_session, entity, drive_level=DriveLevel.HIGH
        )
        manager = NeedsManager(db_session, game_session)

        result = manager.get_intimacy_profile(entity.id)

        assert result is not None
        assert result.drive_level == DriveLevel.HIGH


class TestNeedsDecay:
    """Tests for need decay mechanics."""

    def test_apply_time_decay_hunger_active(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify hunger decreases during active time."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, hunger=50)
        manager = NeedsManager(db_session, game_session)

        result = manager.apply_time_decay(entity.id, hours=1, activity=ActivityType.ACTIVE)

        # hunger decay rate for active is -6 per hour
        assert result.hunger == 44

    def test_apply_time_decay_fatigue_active(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify fatigue increases during active time."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, fatigue=20)
        manager = NeedsManager(db_session, game_session)

        result = manager.apply_time_decay(entity.id, hours=1, activity=ActivityType.ACTIVE)

        # fatigue decay rate for active is +12 per hour
        assert result.fatigue == 32

    def test_apply_time_decay_sleeping_recovers_fatigue(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify sleeping reduces fatigue."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, fatigue=60)
        manager = NeedsManager(db_session, game_session)

        result = manager.apply_time_decay(entity.id, hours=1, activity=ActivityType.SLEEPING)

        # fatigue decay rate for sleeping is -15 per hour
        assert result.fatigue == 45

    def test_apply_time_decay_combat_high_fatigue(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify combat causes rapid fatigue increase."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, fatigue=30)
        manager = NeedsManager(db_session, game_session)

        result = manager.apply_time_decay(entity.id, hours=1, activity=ActivityType.COMBAT)

        # fatigue decay rate for combat is +20 per hour
        assert result.fatigue == 50

    def test_apply_time_decay_social_connection_when_alone(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify social connection decreases when alone."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, social_connection=60)
        manager = NeedsManager(db_session, game_session)

        result = manager.apply_time_decay(entity.id, hours=1, is_alone=True)

        # social decay rate for active alone is -2 per hour
        assert result.social_connection == 58

    def test_apply_time_decay_social_connection_when_socializing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify social connection increases when not alone."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, social_connection=50)
        manager = NeedsManager(db_session, game_session)

        result = manager.apply_time_decay(entity.id, hours=1, is_alone=False)

        # social increases to +5 when not alone
        assert result.social_connection == 55

    def test_apply_time_decay_clamps_to_zero(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify values don't go below 0."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, hunger=5)
        manager = NeedsManager(db_session, game_session)

        result = manager.apply_time_decay(entity.id, hours=2)

        assert result.hunger == 0

    def test_apply_time_decay_clamps_to_hundred(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify values don't exceed 100."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, fatigue=95)
        manager = NeedsManager(db_session, game_session)

        result = manager.apply_time_decay(entity.id, hours=1, activity=ActivityType.COMBAT)

        assert result.fatigue == 100

    def test_apply_time_decay_intimacy_with_high_drive(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify intimacy increases based on drive level."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, intimacy=30)
        create_intimacy_profile(
            db_session, game_session, entity, drive_level=DriveLevel.HIGH
        )
        manager = NeedsManager(db_session, game_session)

        result = manager.apply_time_decay(entity.id, hours=24)  # Full day

        # HIGH drive = 7 per day
        assert result.intimacy == 37


class TestNeedsSatisfaction:
    """Tests for need satisfaction mechanics."""

    def test_satisfy_need_hunger_increases(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify satisfying hunger increases value."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, hunger=30)
        manager = NeedsManager(db_session, game_session)

        result = manager.satisfy_need(entity.id, "hunger", 40)

        assert result.hunger == 70

    def test_satisfy_need_fatigue_decreases(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify satisfying fatigue decreases value (lower is better)."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, fatigue=70)
        manager = NeedsManager(db_session, game_session)

        result = manager.satisfy_need(entity.id, "fatigue", 50)

        assert result.fatigue == 20

    def test_satisfy_need_pain_decreases(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify satisfying pain decreases value."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, pain=60)
        manager = NeedsManager(db_session, game_session)

        result = manager.satisfy_need(entity.id, "pain", 30)

        assert result.pain == 30

    def test_satisfy_need_tracks_turn(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify satisfaction tracks last_X_turn."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, hunger=30)
        manager = NeedsManager(db_session, game_session)

        result = manager.satisfy_need(entity.id, "hunger", 40, turn=15)

        assert result.last_meal_turn == 15

    def test_satisfy_need_unknown_raises(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify unknown need name raises ValueError."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity)
        manager = NeedsManager(db_session, game_session)

        with pytest.raises(ValueError, match="Unknown need"):
            manager.satisfy_need(entity.id, "unknown_need", 10)


class TestNeedsEffects:
    """Tests for need effect calculations."""

    def test_get_active_effects_returns_empty_when_no_needs(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify empty list when entity has no needs."""
        entity = create_entity(db_session, game_session)
        manager = NeedsManager(db_session, game_session)

        result = manager.get_active_effects(entity.id)

        assert result == []

    def test_get_active_effects_starving(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify starving effect when hunger < 15."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, hunger=10)
        manager = NeedsManager(db_session, game_session)

        effects = manager.get_active_effects(entity.id)

        assert len(effects) >= 1
        hunger_effect = next(e for e in effects if e.need_name == "hunger")
        assert hunger_effect.threshold_name == "starving"
        assert hunger_effect.stat_penalties["STR"] == -3

    def test_get_active_effects_exhausted(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify exhausted effect when fatigue > 80."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, fatigue=85)
        manager = NeedsManager(db_session, game_session)

        effects = manager.get_active_effects(entity.id)

        fatigue_effect = next(e for e in effects if e.need_name == "fatigue")
        assert fatigue_effect.threshold_name == "exhausted"
        assert fatigue_effect.special_effects.get("hallucination_chance") == 0.20

    def test_get_active_effects_severe_pain(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify severe pain effect when pain > 60."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, pain=70)
        manager = NeedsManager(db_session, game_session)

        effects = manager.get_active_effects(entity.id)

        pain_effect = next(e for e in effects if e.need_name == "pain")
        assert pain_effect.threshold_name == "severe"
        assert pain_effect.check_penalty == -4

    def test_get_active_effects_no_effects_when_healthy(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify no effects when all needs are satisfied."""
        entity = create_entity(db_session, game_session)
        create_character_needs(
            db_session, game_session, entity,
            hunger=50, fatigue=20, hygiene=80, comfort=70,
            pain=0, morale=70, social_connection=60, intimacy=30
        )
        manager = NeedsManager(db_session, game_session)

        effects = manager.get_active_effects(entity.id)

        assert effects == []

    def test_calculate_stat_modifiers(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify stat modifier calculation."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, hunger=10)  # starving
        manager = NeedsManager(db_session, game_session)

        modifiers = manager.calculate_stat_modifiers(entity.id)

        assert modifiers["STR"] == -3
        assert modifiers["DEX"] == -2

    def test_calculate_check_penalty(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify check penalty calculation."""
        entity = create_entity(db_session, game_session)
        create_character_needs(
            db_session, game_session, entity,
            pain=70,  # -4 check penalty
            hygiene=10  # -3 check penalty
        )
        manager = NeedsManager(db_session, game_session)

        penalty = manager.calculate_check_penalty(entity.id)

        assert penalty == -7


class TestNeedsSummary:
    """Tests for needs summary functionality."""

    def test_get_needs_summary_no_needs(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify summary when no needs exist."""
        entity = create_entity(db_session, game_session)
        manager = NeedsManager(db_session, game_session)

        summary = manager.get_needs_summary(entity.id)

        assert summary["has_needs"] is False

    def test_get_needs_summary_with_needs(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify complete summary with needs."""
        entity = create_entity(db_session, game_session)
        create_character_needs(
            db_session, game_session, entity,
            hunger=30, fatigue=60, morale=50
        )
        manager = NeedsManager(db_session, game_session)

        summary = manager.get_needs_summary(entity.id)

        assert summary["has_needs"] is True
        assert summary["hunger"] == 30
        assert summary["fatigue"] == 60
        assert summary["morale"] == 50


class TestNPCUrgency:
    """Tests for NPC urgency calculation."""

    def test_get_npc_urgency_no_needs(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify urgency when no needs exist."""
        entity = create_entity(db_session, game_session)
        manager = NeedsManager(db_session, game_session)

        need_name, urgency = manager.get_npc_urgency(entity.id)

        assert need_name is None
        assert urgency == 0

    def test_get_npc_urgency_hunger_most_urgent(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify hunger is most urgent when very low."""
        entity = create_entity(db_session, game_session)
        create_character_needs(
            db_session, game_session, entity,
            hunger=10,  # Very hungry - urgency = 90
            fatigue=30,  # Slightly tired - urgency = 30
        )
        manager = NeedsManager(db_session, game_session)

        need_name, urgency = manager.get_npc_urgency(entity.id)

        assert need_name == "hunger"
        assert urgency == 90  # 100 - 10

    def test_get_npc_urgency_fatigue_most_urgent(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify fatigue is most urgent when very high."""
        entity = create_entity(db_session, game_session)
        create_character_needs(
            db_session, game_session, entity,
            hunger=80,  # Not hungry - urgency = 20
            fatigue=95,  # Exhausted - urgency = 95
        )
        manager = NeedsManager(db_session, game_session)

        need_name, urgency = manager.get_npc_urgency(entity.id)

        assert need_name == "fatigue"
        assert urgency == 95
