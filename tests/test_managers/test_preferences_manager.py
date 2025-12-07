"""Tests for PreferencesManager."""

import math

import pytest
from sqlalchemy.orm import Session

from src.database.models.character_preferences import (
    CharacterPreferences,
    NeedModifier,
)
from src.database.models.enums import (
    AlcoholTolerance,
    DriveLevel,
    IntimacyStyle,
    ModifierSource,
    SocialTendency,
)
from src.database.models.session import GameSession
from src.managers.preferences_manager import PreferencesManager
from src.schemas.settings import (
    AsymmetricDistribution,
    NeedAgeCurve,
    get_setting_schema,
)
from tests.factories import (
    create_character_preferences,
    create_entity,
    create_game_session,
    create_need_modifier,
)


class TestPreferencesManagerBasics:
    """Basic CRUD tests for PreferencesManager."""

    def test_get_preferences_returns_none_if_not_exists(
        self, db_session: Session, game_session: GameSession
    ):
        """get_preferences returns None for entity without preferences."""
        entity = create_entity(db_session, game_session)
        manager = PreferencesManager(db_session, game_session)

        result = manager.get_preferences(entity.id)
        assert result is None

    def test_get_preferences_returns_existing(
        self, db_session: Session, game_session: GameSession
    ):
        """get_preferences returns existing preferences."""
        entity = create_entity(db_session, game_session)
        prefs = create_character_preferences(db_session, game_session, entity)
        manager = PreferencesManager(db_session, game_session)

        result = manager.get_preferences(entity.id)
        assert result is not None
        assert result.id == prefs.id

    def test_get_or_create_creates_if_not_exists(
        self, db_session: Session, game_session: GameSession
    ):
        """get_or_create_preferences creates new preferences."""
        entity = create_entity(db_session, game_session)
        manager = PreferencesManager(db_session, game_session)

        result = manager.get_or_create_preferences(entity.id)
        assert result is not None
        assert result.entity_id == entity.id
        assert result.session_id == game_session.id

    def test_get_or_create_returns_existing(
        self, db_session: Session, game_session: GameSession
    ):
        """get_or_create_preferences returns existing preferences."""
        entity = create_entity(db_session, game_session)
        existing = create_character_preferences(db_session, game_session, entity)
        manager = PreferencesManager(db_session, game_session)

        result = manager.get_or_create_preferences(entity.id)
        assert result.id == existing.id

    def test_create_preferences_with_defaults(
        self, db_session: Session, game_session: GameSession
    ):
        """create_preferences creates with default values."""
        entity = create_entity(db_session, game_session)
        manager = PreferencesManager(db_session, game_session)

        result = manager.create_preferences(entity.id)
        assert result.drive_level == DriveLevel.MODERATE
        assert result.social_tendency == SocialTendency.AMBIVERT
        assert result.alcohol_tolerance == AlcoholTolerance.MODERATE

    def test_create_preferences_with_custom_values(
        self, db_session: Session, game_session: GameSession
    ):
        """create_preferences accepts custom values."""
        entity = create_entity(db_session, game_session)
        manager = PreferencesManager(db_session, game_session)

        result = manager.create_preferences(
            entity.id,
            is_greedy_eater=True,
            drive_level=DriveLevel.HIGH,
            social_tendency=SocialTendency.EXTROVERT,
        )
        assert result.is_greedy_eater is True
        assert result.drive_level == DriveLevel.HIGH
        assert result.social_tendency == SocialTendency.EXTROVERT

    def test_update_preferences(
        self, db_session: Session, game_session: GameSession
    ):
        """update_preferences modifies existing preferences."""
        entity = create_entity(db_session, game_session)
        create_character_preferences(db_session, game_session, entity)
        manager = PreferencesManager(db_session, game_session)

        result = manager.update_preferences(
            entity.id,
            is_vegetarian=True,
            favorite_foods=["salad", "fruit"],
        )
        assert result.is_vegetarian is True
        assert result.favorite_foods == ["salad", "fruit"]


class TestTraitFlags:
    """Tests for trait flag methods."""

    def test_get_trait_flags_returns_all_traits(
        self, db_session: Session, game_session: GameSession
    ):
        """get_trait_flags returns dict of all trait flags."""
        entity = create_entity(db_session, game_session)
        create_character_preferences(
            db_session, game_session, entity,
            is_greedy_eater=True,
            has_high_stamina=True,
        )
        manager = PreferencesManager(db_session, game_session)

        flags = manager.get_trait_flags(entity.id)
        assert isinstance(flags, dict)
        assert flags["is_greedy_eater"] is True
        assert flags["has_high_stamina"] is True
        assert flags["is_loner"] is False

    def test_set_trait_updates_flag(
        self, db_session: Session, game_session: GameSession
    ):
        """set_trait updates a specific trait flag."""
        entity = create_entity(db_session, game_session)
        create_character_preferences(db_session, game_session, entity)
        manager = PreferencesManager(db_session, game_session)

        result = manager.set_trait(entity.id, "is_greedy_eater", True)
        assert result.is_greedy_eater is True

        result = manager.set_trait(entity.id, "is_greedy_eater", False)
        assert result.is_greedy_eater is False

    def test_set_trait_syncs_modifiers(
        self, db_session: Session, game_session: GameSession
    ):
        """set_trait syncs trait to NeedModifier records."""
        entity = create_entity(db_session, game_session)
        create_character_preferences(db_session, game_session, entity)
        manager = PreferencesManager(db_session, game_session)

        # Set greedy_eater trait
        manager.set_trait(entity.id, "is_greedy_eater", True)

        # Should create a hunger modifier
        modifiers = manager.get_modifiers_for_entity(entity.id)
        hunger_mods = [m for m in modifiers if m.need_name == "hunger" and m.modifier_source == ModifierSource.TRAIT]
        assert len(hunger_mods) == 1
        assert hunger_mods[0].decay_rate_multiplier > 1.0

    def test_set_trait_removes_modifier_when_false(
        self, db_session: Session, game_session: GameSession
    ):
        """set_trait removes modifier when trait is set to False."""
        entity = create_entity(db_session, game_session)
        create_character_preferences(db_session, game_session, entity)
        manager = PreferencesManager(db_session, game_session)

        # Set then unset
        manager.set_trait(entity.id, "is_greedy_eater", True)
        manager.set_trait(entity.id, "is_greedy_eater", False)

        modifiers = manager.get_modifiers_for_entity(entity.id)
        hunger_mods = [m for m in modifiers if m.need_name == "hunger" and m.modifier_source == ModifierSource.TRAIT]
        assert len(hunger_mods) == 0


class TestModifierMethods:
    """Tests for modifier management methods."""

    def test_get_modifiers_for_entity(
        self, db_session: Session, game_session: GameSession
    ):
        """get_modifiers_for_entity returns all modifiers."""
        entity = create_entity(db_session, game_session)
        create_need_modifier(
            db_session, game_session, entity,
            need_name="hunger", modifier_source=ModifierSource.TRAIT,
        )
        create_need_modifier(
            db_session, game_session, entity,
            need_name="fatigue", modifier_source=ModifierSource.AGE,
        )
        manager = PreferencesManager(db_session, game_session)

        modifiers = manager.get_modifiers_for_entity(entity.id)
        assert len(modifiers) == 2

    def test_get_modifiers_for_entity_filters_by_need(
        self, db_session: Session, game_session: GameSession
    ):
        """get_modifiers_for_entity can filter by need_name."""
        entity = create_entity(db_session, game_session)
        create_need_modifier(
            db_session, game_session, entity,
            need_name="hunger", modifier_source=ModifierSource.TRAIT,
        )
        create_need_modifier(
            db_session, game_session, entity,
            need_name="fatigue", modifier_source=ModifierSource.AGE,
        )
        manager = PreferencesManager(db_session, game_session)

        modifiers = manager.get_modifiers_for_entity(entity.id, need_name="hunger")
        assert len(modifiers) == 1
        assert modifiers[0].need_name == "hunger"

    def test_create_modifier(
        self, db_session: Session, game_session: GameSession
    ):
        """create_modifier creates a new modifier record."""
        entity = create_entity(db_session, game_session)
        manager = PreferencesManager(db_session, game_session)

        modifier = manager.create_modifier(
            entity_id=entity.id,
            need_name="hunger",
            source=ModifierSource.CUSTOM,
            decay_rate_multiplier=1.5,
        )
        assert modifier.id is not None
        assert modifier.decay_rate_multiplier == 1.5

    def test_remove_modifier(
        self, db_session: Session, game_session: GameSession
    ):
        """remove_modifier deletes a modifier."""
        entity = create_entity(db_session, game_session)
        mod = create_need_modifier(db_session, game_session, entity)
        mod_id = mod.id
        manager = PreferencesManager(db_session, game_session)

        manager.remove_modifier(mod_id)
        db_session.flush()

        result = db_session.query(NeedModifier).filter(NeedModifier.id == mod_id).first()
        assert result is None


class TestAgeModifierCalculation:
    """Tests for age-based modifier calculations."""

    def test_calculate_age_modifier_at_peak(
        self, db_session: Session, game_session: GameSession
    ):
        """calculate_age_modifier returns peak value at peak age."""
        manager = PreferencesManager(db_session, game_session)
        curve = NeedAgeCurve(
            need_name="intimacy",
            distribution=AsymmetricDistribution(
                peak_age=18,
                peak_value=90,
                std_dev_lower=3,
                std_dev_upper=45,
            ),
        )

        result = manager.calculate_age_modifier(age=18, curve=curve)
        assert result == 90.0

    def test_calculate_age_modifier_below_peak(
        self, db_session: Session, game_session: GameSession
    ):
        """calculate_age_modifier decreases sharply below peak."""
        manager = PreferencesManager(db_session, game_session)
        curve = NeedAgeCurve(
            need_name="intimacy",
            distribution=AsymmetricDistribution(
                peak_age=18,
                peak_value=90,
                std_dev_lower=3,
                std_dev_upper=45,
            ),
        )

        # Age 10 should be much lower (8 years below peak, std_dev=3)
        result = manager.calculate_age_modifier(age=10, curve=curve)
        assert result < 50  # Should be significantly reduced
        assert result >= 0  # But not negative

    def test_calculate_age_modifier_above_peak(
        self, db_session: Session, game_session: GameSession
    ):
        """calculate_age_modifier decreases gradually above peak."""
        manager = PreferencesManager(db_session, game_session)
        curve = NeedAgeCurve(
            need_name="intimacy",
            distribution=AsymmetricDistribution(
                peak_age=18,
                peak_value=90,
                std_dev_lower=3,
                std_dev_upper=45,
            ),
        )

        # Age 40 should be lower but not as drastically (22 years above, std_dev=45)
        result = manager.calculate_age_modifier(age=40, curve=curve)
        assert 40 < result < 90  # Gradual decline

        # Age 70 should be even lower
        result_70 = manager.calculate_age_modifier(age=70, curve=curve)
        assert result_70 < result

    def test_calculate_age_modifier_respects_min_max(
        self, db_session: Session, game_session: GameSession
    ):
        """calculate_age_modifier respects min/max bounds."""
        manager = PreferencesManager(db_session, game_session)
        curve = NeedAgeCurve(
            need_name="test",
            distribution=AsymmetricDistribution(
                peak_age=25,
                peak_value=100,
                std_dev_lower=5,
                std_dev_upper=20,
                min_value=10,
                max_value=95,
            ),
        )

        # At peak, should be capped at max
        result = manager.calculate_age_modifier(age=25, curve=curve)
        assert result <= 95

        # Very old should not go below min
        result = manager.calculate_age_modifier(age=100, curve=curve)
        assert result >= 10

    def test_generate_individual_variance(
        self, db_session: Session, game_session: GameSession
    ):
        """generate_individual_variance adds variance around expected."""
        manager = PreferencesManager(db_session, game_session)

        # Run multiple times to verify it's adding variance
        results = [
            manager.generate_individual_variance(expected=50, variance_std=15)
            for _ in range(100)
        ]

        # Should have some variance
        assert min(results) < max(results)
        # Should be centered around expected
        avg = sum(results) / len(results)
        assert 40 < avg < 60  # Roughly centered around 50

    def test_generate_age_modifiers_creates_records(
        self, db_session: Session, game_session: GameSession
    ):
        """generate_age_modifiers creates modifier records for all curves."""
        entity = create_entity(db_session, game_session, age=25)
        manager = PreferencesManager(db_session, game_session)

        modifiers = manager.generate_age_modifiers(
            entity_id=entity.id,
            age=25,
            setting_name="fantasy",
        )

        # Fantasy has 3 age curves (intimacy, fatigue, social_connection)
        assert len(modifiers) >= 1
        # All should be AGE source
        for mod in modifiers:
            assert mod.modifier_source == ModifierSource.AGE

    def test_generate_age_modifiers_for_young_character(
        self, db_session: Session, game_session: GameSession
    ):
        """generate_age_modifiers produces low values for young characters."""
        entity = create_entity(db_session, game_session, age=10)
        manager = PreferencesManager(db_session, game_session)

        modifiers = manager.generate_age_modifiers(
            entity_id=entity.id,
            age=10,
            setting_name="fantasy",
        )

        # Find intimacy modifier
        intimacy_mods = [m for m in modifiers if m.need_name == "intimacy"]
        if intimacy_mods:
            # Should have low decay rate for young character
            assert intimacy_mods[0].decay_rate_multiplier < 0.5


class TestSyncTraitModifiers:
    """Tests for syncing all traits to modifiers."""

    def test_sync_trait_modifiers_creates_for_active_traits(
        self, db_session: Session, game_session: GameSession
    ):
        """sync_trait_modifiers creates modifiers for active traits."""
        entity = create_entity(db_session, game_session)
        create_character_preferences(
            db_session, game_session, entity,
            is_greedy_eater=True,
            has_high_stamina=True,
        )
        manager = PreferencesManager(db_session, game_session)

        modifiers = manager.sync_trait_modifiers(entity.id)

        # Should have modifiers for both traits
        assert len(modifiers) >= 2
        need_names = {m.need_name for m in modifiers}
        assert "hunger" in need_names  # greedy_eater affects hunger
        assert "fatigue" in need_names  # high_stamina affects fatigue

    def test_sync_trait_modifiers_removes_for_inactive_traits(
        self, db_session: Session, game_session: GameSession
    ):
        """sync_trait_modifiers removes modifiers for inactive traits."""
        entity = create_entity(db_session, game_session)
        prefs = create_character_preferences(
            db_session, game_session, entity,
            is_greedy_eater=True,
        )
        manager = PreferencesManager(db_session, game_session)

        # Initial sync
        manager.sync_trait_modifiers(entity.id)

        # Disable trait
        prefs.is_greedy_eater = False
        db_session.flush()

        # Re-sync
        modifiers = manager.sync_trait_modifiers(entity.id)

        # Should not have greedy_eater modifier anymore
        hunger_trait_mods = [
            m for m in modifiers
            if m.need_name == "hunger" and m.source_detail == "greedy_eater"
        ]
        assert len(hunger_trait_mods) == 0
