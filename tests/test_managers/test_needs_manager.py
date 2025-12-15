"""Tests for NeedsManager class."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.character_state import CharacterNeeds
from src.database.models.character_preferences import CharacterPreferences
from src.database.models.enums import DriveLevel
from src.database.models.session import GameSession
from src.managers.needs import ActivityType, NeedsManager
from src.database.models.character_preferences import NeedAdaptation, NeedModifier
from src.database.models.enums import ModifierSource
from tests.factories import (
    create_character_needs,
    create_character_preferences,
    create_entity,
    create_need_modifier,
    create_need_adaptation,
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

    def test_get_preferences_returns_none_when_missing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_preferences returns None when not exists."""
        entity = create_entity(db_session, game_session)
        manager = NeedsManager(db_session, game_session)

        result = manager.get_preferences(entity.id)

        assert result is None

    def test_get_preferences_returns_existing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_preferences returns existing CharacterPreferences."""
        entity = create_entity(db_session, game_session)
        prefs = create_character_preferences(
            db_session, game_session, entity, drive_level=DriveLevel.HIGH
        )
        manager = NeedsManager(db_session, game_session)

        result = manager.get_preferences(entity.id)

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

    def test_apply_time_decay_energy_active(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify energy decreases during active time."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, energy=80)
        manager = NeedsManager(db_session, game_session)

        result = manager.apply_time_decay(entity.id, hours=1, activity=ActivityType.ACTIVE)

        # energy decay rate for active is -12 per hour
        assert result.energy == 68

    def test_apply_time_decay_sleeping_recovers_energy(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify sleeping increases energy."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, energy=40)
        manager = NeedsManager(db_session, game_session)

        result = manager.apply_time_decay(entity.id, hours=1, activity=ActivityType.SLEEPING)

        # energy recovery rate for sleeping is +15 per hour
        assert result.energy == 55

    def test_apply_time_decay_combat_drains_energy(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify combat causes rapid energy decrease."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, energy=70)
        manager = NeedsManager(db_session, game_session)

        result = manager.apply_time_decay(entity.id, hours=1, activity=ActivityType.COMBAT)

        # energy decay rate for combat is -20 per hour
        assert result.energy == 50

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

    def test_apply_time_decay_clamps_to_zero(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify energy doesn't go below 0."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, energy=5)
        manager = NeedsManager(db_session, game_session)

        result = manager.apply_time_decay(entity.id, hours=1, activity=ActivityType.COMBAT)

        assert result.energy == 0

    def test_apply_time_decay_intimacy_with_high_drive(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify intimacy decreases based on drive level (0=desperate, 100=content)."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, intimacy=80)
        create_character_preferences(
            db_session, game_session, entity, drive_level=DriveLevel.HIGH
        )
        manager = NeedsManager(db_session, game_session)

        result = manager.apply_time_decay(entity.id, hours=24)  # Full day

        # HIGH drive = 7 per day decay, so 80 - 7 = 73
        assert result.intimacy == 73


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

    def test_satisfy_need_energy_increases(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify satisfying energy increases value (higher is better)."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, energy=30)
        manager = NeedsManager(db_session, game_session)

        result = manager.satisfy_need(entity.id, "energy", 50)

        assert result.energy == 80

    def test_satisfy_need_wellness_increases(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify satisfying wellness increases value (higher is better)."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, wellness=40)
        manager = NeedsManager(db_session, game_session)

        result = manager.satisfy_need(entity.id, "wellness", 30)

        assert result.wellness == 70

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
        """Verify exhausted effect when energy < 20."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, energy=15)
        manager = NeedsManager(db_session, game_session)

        effects = manager.get_active_effects(entity.id)

        energy_effect = next(e for e in effects if e.need_name == "energy")
        assert energy_effect.threshold_name == "exhausted"
        assert energy_effect.special_effects.get("hallucination_chance") == 0.20

    def test_get_active_effects_severe_pain(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify severe pain effect when wellness < 40."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, wellness=30)
        manager = NeedsManager(db_session, game_session)

        effects = manager.get_active_effects(entity.id)

        wellness_effect = next(e for e in effects if e.need_name == "wellness")
        assert wellness_effect.threshold_name == "severe"
        assert wellness_effect.check_penalty == -4

    def test_get_active_effects_no_effects_when_healthy(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify no effects when all needs are satisfied."""
        entity = create_entity(db_session, game_session)
        create_character_needs(
            db_session, game_session, entity,
            hunger=50, energy=80, hygiene=80, comfort=70,
            wellness=100, morale=70, social_connection=60, intimacy=70
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
            wellness=30,  # severe pain, -4 check penalty
            hygiene=10  # filthy, -3 check penalty
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
            hunger=30, energy=40, morale=50
        )
        manager = NeedsManager(db_session, game_session)

        summary = manager.get_needs_summary(entity.id)

        assert summary["has_needs"] is True
        assert summary["hunger"] == 30
        assert summary["energy"] == 40
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
            energy=70,  # Good energy - urgency = 30
        )
        manager = NeedsManager(db_session, game_session)

        need_name, urgency = manager.get_npc_urgency(entity.id)

        assert need_name == "hunger"
        assert urgency == 90  # 100 - 10

    def test_get_npc_urgency_energy_most_urgent(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify energy is most urgent when very low."""
        entity = create_entity(db_session, game_session)
        create_character_needs(
            db_session, game_session, entity,
            hunger=80,  # Not hungry - urgency = 20
            energy=5,  # Exhausted - urgency = 95
        )
        manager = NeedsManager(db_session, game_session)

        need_name, urgency = manager.get_npc_urgency(entity.id)

        assert need_name == "energy"
        assert urgency == 95  # 100 - 5


class TestModifierMethods:
    """Tests for NeedModifier-aware methods."""

    def test_get_decay_multiplier_no_modifiers(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify returns 1.0 when no modifiers exist."""
        entity = create_entity(db_session, game_session)
        manager = NeedsManager(db_session, game_session)

        result = manager.get_decay_multiplier(entity.id, "hunger")

        assert result == 1.0

    def test_get_decay_multiplier_single_modifier(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify returns modifier value when one exists."""
        entity = create_entity(db_session, game_session)
        create_need_modifier(
            db_session, game_session, entity,
            need_name="hunger",
            modifier_source=ModifierSource.TRAIT,
            decay_rate_multiplier=1.35,
        )
        manager = NeedsManager(db_session, game_session)

        result = manager.get_decay_multiplier(entity.id, "hunger")

        assert result == 1.35

    def test_get_decay_multiplier_multiple_modifiers_multiply(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify multiple modifiers are multiplied together."""
        entity = create_entity(db_session, game_session)
        create_need_modifier(
            db_session, game_session, entity,
            need_name="energy",
            modifier_source=ModifierSource.TRAIT,
            decay_rate_multiplier=0.8,
        )
        create_need_modifier(
            db_session, game_session, entity,
            need_name="energy",
            modifier_source=ModifierSource.AGE,
            source_detail="age_25",
            decay_rate_multiplier=0.7,
        )
        manager = NeedsManager(db_session, game_session)

        result = manager.get_decay_multiplier(entity.id, "energy")

        # 0.8 * 0.7 = 0.56
        assert abs(result - 0.56) < 0.001

    def test_get_decay_multiplier_ignores_inactive(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify inactive modifiers are ignored."""
        entity = create_entity(db_session, game_session)
        create_need_modifier(
            db_session, game_session, entity,
            need_name="hunger",
            modifier_source=ModifierSource.TRAIT,
            decay_rate_multiplier=1.5,
            is_active=False,
        )
        manager = NeedsManager(db_session, game_session)

        result = manager.get_decay_multiplier(entity.id, "hunger")

        assert result == 1.0

    def test_get_satisfaction_multiplier_no_modifiers(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify returns 1.0 when no modifiers exist."""
        entity = create_entity(db_session, game_session)
        manager = NeedsManager(db_session, game_session)

        result = manager.get_satisfaction_multiplier(entity.id, "hunger")

        assert result == 1.0

    def test_get_satisfaction_multiplier_with_modifier(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify returns modifier value when one exists."""
        entity = create_entity(db_session, game_session)
        create_need_modifier(
            db_session, game_session, entity,
            need_name="hunger",
            modifier_source=ModifierSource.TRAIT,
            satisfaction_multiplier=0.8,  # Gets less satisfaction from food
        )
        manager = NeedsManager(db_session, game_session)

        result = manager.get_satisfaction_multiplier(entity.id, "hunger")

        assert result == 0.8

    def test_get_max_intensity_no_cap(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify returns 100 when no cap exists."""
        entity = create_entity(db_session, game_session)
        manager = NeedsManager(db_session, game_session)

        result = manager.get_max_intensity(entity.id, "intimacy")

        assert result == 100

    def test_get_max_intensity_with_age_cap(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify returns lowest cap from modifiers."""
        entity = create_entity(db_session, game_session)
        create_need_modifier(
            db_session, game_session, entity,
            need_name="intimacy",
            modifier_source=ModifierSource.AGE,
            source_detail="age_10",
            max_intensity_cap=20,
        )
        manager = NeedsManager(db_session, game_session)

        result = manager.get_max_intensity(entity.id, "intimacy")

        assert result == 20

    def test_get_max_intensity_multiple_caps_returns_lowest(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify returns the lowest cap when multiple exist."""
        entity = create_entity(db_session, game_session)
        create_need_modifier(
            db_session, game_session, entity,
            need_name="intimacy",
            modifier_source=ModifierSource.AGE,
            source_detail="age_50",
            max_intensity_cap=60,
        )
        create_need_modifier(
            db_session, game_session, entity,
            need_name="intimacy",
            modifier_source=ModifierSource.CUSTOM,
            source_detail="trauma",
            max_intensity_cap=40,
        )
        manager = NeedsManager(db_session, game_session)

        result = manager.get_max_intensity(entity.id, "intimacy")

        assert result == 40


class TestAdaptationMethods:
    """Tests for need adaptation tracking."""

    def test_get_total_adaptation_no_adaptations(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify returns 0 when no adaptations exist."""
        entity = create_entity(db_session, game_session)
        manager = NeedsManager(db_session, game_session)

        result = manager.get_total_adaptation(entity.id, "social_connection")

        assert result == 0

    def test_get_total_adaptation_single_adaptation(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify returns single adaptation delta."""
        entity = create_entity(db_session, game_session)
        create_need_adaptation(
            db_session, game_session, entity,
            need_name="social_connection",
            adaptation_delta=-15,
            reason="Months of isolation",
        )
        manager = NeedsManager(db_session, game_session)

        result = manager.get_total_adaptation(entity.id, "social_connection")

        assert result == -15

    def test_get_total_adaptation_sums_multiple(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify sums multiple adaptation deltas."""
        entity = create_entity(db_session, game_session)
        create_need_adaptation(
            db_session, game_session, entity,
            need_name="hunger",
            adaptation_delta=-10,
            reason="Fasting practice",
        )
        create_need_adaptation(
            db_session, game_session, entity,
            need_name="hunger",
            adaptation_delta=-5,
            reason="Continued discipline",
        )
        manager = NeedsManager(db_session, game_session)

        result = manager.get_total_adaptation(entity.id, "hunger")

        assert result == -15

    def test_create_adaptation_creates_record(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify create_adaptation creates an adaptation record."""
        entity = create_entity(db_session, game_session)
        manager = NeedsManager(db_session, game_session)

        result = manager.create_adaptation(
            entity_id=entity.id,
            need_name="social_connection",
            delta=-10,
            reason="Prolonged isolation",
        )

        assert result is not None
        assert result.entity_id == entity.id
        assert result.need_name == "social_connection"
        assert result.adaptation_delta == -10
        assert result.reason == "Prolonged isolation"

    def test_create_adaptation_with_optional_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify create_adaptation accepts optional fields."""
        entity = create_entity(db_session, game_session)
        manager = NeedsManager(db_session, game_session)

        result = manager.create_adaptation(
            entity_id=entity.id,
            need_name="hunger",
            delta=-20,
            reason="Strict diet training",
            trigger_event="monastery_training",
            is_gradual=True,
            duration_days=30,
            is_reversible=True,
            reversal_trigger="Return to normal eating",
        )

        assert result.trigger_event == "monastery_training"
        assert result.is_gradual is True
        assert result.duration_days == 30
        assert result.is_reversible is True
        assert result.reversal_trigger == "Return to normal eating"


class TestDecayWithModifiers:
    """Tests for decay calculation using modifiers."""

    def test_apply_time_decay_uses_decay_multiplier(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify apply_time_decay applies decay rate multiplier."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, hunger=50)
        # Greedy eater - 1.5x hunger decay
        create_need_modifier(
            db_session, game_session, entity,
            need_name="hunger",
            modifier_source=ModifierSource.TRAIT,
            source_detail="greedy_eater",
            decay_rate_multiplier=1.5,
        )
        manager = NeedsManager(db_session, game_session)

        result = manager.apply_time_decay(entity.id, hours=1, activity=ActivityType.ACTIVE)

        # Base decay is -6 per hour, with 1.5x = -9
        assert result.hunger == 41  # 50 - 9 = 41

    def test_apply_time_decay_uses_max_intensity_cap(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify apply_time_decay respects max intensity cap."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, intimacy=30)
        # Age-based cap on intimacy
        create_need_modifier(
            db_session, game_session, entity,
            need_name="intimacy",
            modifier_source=ModifierSource.AGE,
            source_detail="age_10",
            max_intensity_cap=20,
        )
        create_character_preferences(
            db_session, game_session, entity, drive_level=DriveLevel.HIGH
        )
        manager = NeedsManager(db_session, game_session)

        result = manager.apply_time_decay(entity.id, hours=24)

        # intimacy should be capped at 20, not increase beyond
        assert result.intimacy <= 20

    def test_apply_time_decay_reduces_energy_drain_with_high_stamina(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify high stamina trait reduces energy drain."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, energy=80)
        # High stamina - 0.7x energy decay
        create_need_modifier(
            db_session, game_session, entity,
            need_name="energy",
            modifier_source=ModifierSource.TRAIT,
            source_detail="high_stamina",
            decay_rate_multiplier=0.7,
        )
        manager = NeedsManager(db_session, game_session)

        result = manager.apply_time_decay(entity.id, hours=1, activity=ActivityType.ACTIVE)

        # Base decay is -12 per hour, with 0.7x = -8.4
        # 80 - 8.4 = 71.6, rounds to 71
        assert result.energy == 71  # Instead of 68 without modifier


class TestEstimateBaseSatisfaction:
    """Tests for estimate_base_satisfaction function."""

    def test_returns_catalog_value_for_known_action(self):
        """Verify known action types return catalog values."""
        from src.managers.needs import estimate_base_satisfaction

        result = estimate_base_satisfaction("hunger", "snack", "basic")
        assert result == 10

        result = estimate_base_satisfaction("hunger", "full_meal", "basic")
        assert result == 40

        result = estimate_base_satisfaction("energy", "full_sleep", "basic")
        assert result == 75

    def test_applies_quality_multiplier(self):
        """Verify quality affects satisfaction amount."""
        from src.managers.needs import estimate_base_satisfaction

        poor = estimate_base_satisfaction("hunger", "full_meal", "poor")
        basic = estimate_base_satisfaction("hunger", "full_meal", "basic")
        good = estimate_base_satisfaction("hunger", "full_meal", "good")
        excellent = estimate_base_satisfaction("hunger", "full_meal", "excellent")

        assert poor == 24  # 40 * 0.6
        assert basic == 40  # 40 * 1.0
        assert good == 52  # 40 * 1.3
        assert excellent == 64  # 40 * 1.6

    def test_returns_default_for_unknown_action(self):
        """Verify unknown actions return default value."""
        from src.managers.needs import estimate_base_satisfaction

        result = estimate_base_satisfaction("hunger", "unknown_action", "basic")
        assert result == 20  # Default

    def test_negative_hygiene_actions(self):
        """Verify negative hygiene actions return negative values."""
        from src.managers.needs import estimate_base_satisfaction

        # Test various negative hygiene actions
        result = estimate_base_satisfaction("hygiene", "get_dirty", "basic")
        assert result == -15

        result = estimate_base_satisfaction("hygiene", "mud", "basic")
        assert result == -25

        result = estimate_base_satisfaction("hygiene", "filth", "basic")
        assert result == -35

    def test_negative_comfort_actions(self):
        """Verify negative comfort actions return negative values."""
        from src.managers.needs import estimate_base_satisfaction

        result = estimate_base_satisfaction("comfort", "get_cold", "basic")
        assert result == -20

        result = estimate_base_satisfaction("comfort", "get_wet", "basic")
        assert result == -20

        result = estimate_base_satisfaction("comfort", "freezing", "basic")
        assert result == -30

    def test_negative_social_actions(self):
        """Verify negative social actions return negative values."""
        from src.managers.needs import estimate_base_satisfaction

        result = estimate_base_satisfaction("social_connection", "rejection", "basic")
        assert result == -25

        result = estimate_base_satisfaction("social_connection", "betrayal", "basic")
        assert result == -40

    def test_negative_intimacy_actions(self):
        """Verify negative intimacy actions return negative values."""
        from src.managers.needs import estimate_base_satisfaction

        result = estimate_base_satisfaction("intimacy", "romantic_rejection", "basic")
        assert result == -20

        result = estimate_base_satisfaction("intimacy", "heartbreak", "basic")
        assert result == -40

    def test_quality_affects_negative_actions(self):
        """Verify quality multiplier applies to negative actions."""
        from src.managers.needs import estimate_base_satisfaction

        # Poor quality should reduce the negative impact (0.6x)
        poor = estimate_base_satisfaction("hygiene", "mud", "poor")
        assert poor == -15  # -25 * 0.6 = -15

        # Excellent quality should increase negative impact (1.6x)
        excellent = estimate_base_satisfaction("hygiene", "mud", "excellent")
        assert excellent == -40  # -25 * 1.6 = -40


class TestGetPreferenceMultiplier:
    """Tests for get_preference_multiplier function."""

    def test_returns_one_when_no_preferences(self):
        """Verify returns 1.0 when prefs is None."""
        from src.managers.needs import get_preference_multiplier

        result = get_preference_multiplier(None, "hunger", "full_meal", "basic")
        assert result == 1.0

    def test_greedy_eater_increases_hunger_satisfaction(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify greedy eater gets +30% hunger satisfaction."""
        from src.database.models.character_preferences import CharacterPreferences
        from src.managers.needs import get_preference_multiplier

        entity = create_entity(db_session, game_session)
        prefs = CharacterPreferences(
            entity_id=entity.id,
            session_id=game_session.id,
            is_greedy_eater=True,
        )
        db_session.add(prefs)
        db_session.flush()

        result = get_preference_multiplier(prefs, "hunger", "full_meal", "basic")
        assert result == 1.3

    def test_picky_eater_with_poor_quality(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify picky eater gets reduced satisfaction for poor quality."""
        from src.database.models.character_preferences import CharacterPreferences
        from src.managers.needs import get_preference_multiplier

        entity = create_entity(db_session, game_session)
        prefs = CharacterPreferences(
            entity_id=entity.id,
            session_id=game_session.id,
            is_picky_eater=True,
        )
        db_session.add(prefs)
        db_session.flush()

        result = get_preference_multiplier(prefs, "hunger", "full_meal", "poor")
        assert result == 0.5

    def test_insomniac_reduces_sleep_satisfaction(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify insomniac gets reduced sleep satisfaction."""
        from src.database.models.character_preferences import CharacterPreferences
        from src.managers.needs import get_preference_multiplier

        entity = create_entity(db_session, game_session)
        prefs = CharacterPreferences(
            entity_id=entity.id,
            session_id=game_session.id,
            is_insomniac=True,
        )
        db_session.add(prefs)
        db_session.flush()

        result = get_preference_multiplier(prefs, "energy", "full_sleep", "basic")
        assert result == 0.6

    def test_loner_reduces_social_satisfaction(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify loner gets reduced social satisfaction."""
        from src.database.models.character_preferences import CharacterPreferences
        from src.managers.needs import get_preference_multiplier

        entity = create_entity(db_session, game_session)
        prefs = CharacterPreferences(
            entity_id=entity.id,
            session_id=game_session.id,
            is_loner=True,
        )
        db_session.add(prefs)
        db_session.flush()

        result = get_preference_multiplier(prefs, "social_connection", "conversation", "basic")
        assert result == 0.5

    def test_asexual_drive_level_zeros_intimacy(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify asexual drive level gives 0x intimacy satisfaction."""
        from src.database.models.character_preferences import CharacterPreferences
        from src.managers.needs import get_preference_multiplier

        entity = create_entity(db_session, game_session)
        prefs = CharacterPreferences(
            entity_id=entity.id,
            session_id=game_session.id,
            drive_level=DriveLevel.ASEXUAL,
        )
        db_session.add(prefs)
        db_session.flush()

        result = get_preference_multiplier(prefs, "intimacy", "affection", "basic")
        assert result == 0.0

    def test_very_high_drive_increases_intimacy(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify very high drive level gives 1.5x intimacy satisfaction."""
        from src.database.models.character_preferences import CharacterPreferences
        from src.managers.needs import get_preference_multiplier

        entity = create_entity(db_session, game_session)
        prefs = CharacterPreferences(
            entity_id=entity.id,
            session_id=game_session.id,
            drive_level=DriveLevel.VERY_HIGH,
        )
        db_session.add(prefs)
        db_session.flush()

        result = get_preference_multiplier(prefs, "intimacy", "affection", "basic")
        assert result == 1.5


class TestSatisfyNeedWithMultiplier:
    """Tests for satisfy_need applying satisfaction_multiplier."""

    def test_satisfy_need_applies_satisfaction_multiplier(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify satisfy_need applies satisfaction_multiplier from NeedModifier."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, hunger=30)
        # Create modifier with 1.5x satisfaction
        create_need_modifier(
            db_session, game_session, entity,
            need_name="hunger",
            modifier_source=ModifierSource.TRAIT,
            source_detail="greedy_eater",
            satisfaction_multiplier=1.5,
        )
        manager = NeedsManager(db_session, game_session)

        result = manager.satisfy_need(entity.id, "hunger", 20)

        # 20 * 1.5 = 30, so 30 + 30 = 60
        assert result.hunger == 60

    def test_satisfy_need_without_modifier_uses_base_amount(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify satisfy_need uses base amount when no modifier exists."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, hunger=30)
        manager = NeedsManager(db_session, game_session)

        result = manager.satisfy_need(entity.id, "hunger", 20)

        # No modifier, so 30 + 20 = 50
        assert result.hunger == 50

    def test_satisfy_need_applies_to_energy_correctly(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify satisfy_need increases energy (higher is better)."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity, energy=20)
        manager = NeedsManager(db_session, game_session)

        result = manager.satisfy_need(entity.id, "energy", 30)

        # Energy increases: 20 + 30 = 50
        assert result.energy == 50
