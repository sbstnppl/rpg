"""Tests for CharacterPreferences, NeedModifier, and NeedAdaptation models."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.database.models.character_preferences import (
    CharacterPreferences,
    NeedAdaptation,
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
from tests.factories import (
    create_character_preferences,
    create_entity,
    create_game_session,
    create_need_adaptation,
    create_need_modifier,
)


class TestCharacterPreferences:
    """Tests for CharacterPreferences model."""

    def test_create_preferences_required_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify CharacterPreferences creation with required fields."""
        entity = create_entity(db_session, game_session)
        prefs = CharacterPreferences(
            entity_id=entity.id,
            session_id=game_session.id,
        )
        db_session.add(prefs)
        db_session.flush()

        assert prefs.id is not None
        assert prefs.entity_id == entity.id
        assert prefs.session_id == game_session.id

    def test_preferences_one_to_one(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify unique entity_id constraint."""
        entity = create_entity(db_session, game_session)
        create_character_preferences(db_session, game_session, entity)

        with pytest.raises(IntegrityError):
            create_character_preferences(db_session, game_session, entity)

    # === Food Preferences Tests ===

    def test_food_preferences_defaults(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify food preference defaults."""
        entity = create_entity(db_session, game_session)
        prefs = CharacterPreferences(
            entity_id=entity.id,
            session_id=game_session.id,
        )
        db_session.add(prefs)
        db_session.flush()

        assert prefs.favorite_foods is None
        assert prefs.disliked_foods is None
        assert prefs.is_vegetarian is False
        assert prefs.is_vegan is False
        assert prefs.food_allergies is None
        assert prefs.is_greedy_eater is False
        assert prefs.is_picky_eater is False

    def test_food_preferences_json_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify food preference JSON fields."""
        entity = create_entity(db_session, game_session)
        favorites = ["steak", "potatoes", "bread"]
        dislikes = ["fish", "spinach"]
        allergies = ["peanuts", "shellfish"]

        prefs = create_character_preferences(
            db_session,
            game_session,
            entity,
            favorite_foods=favorites,
            disliked_foods=dislikes,
            food_allergies=allergies,
        )
        db_session.refresh(prefs)

        assert prefs.favorite_foods == favorites
        assert prefs.disliked_foods == dislikes
        assert prefs.food_allergies == allergies

    def test_food_trait_flags(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify food-related trait flags."""
        entity = create_entity(db_session, game_session)
        prefs = create_character_preferences(
            db_session,
            game_session,
            entity,
            is_vegetarian=True,
            is_vegan=True,
            is_greedy_eater=True,
            is_picky_eater=True,
        )
        db_session.refresh(prefs)

        assert prefs.is_vegetarian is True
        assert prefs.is_vegan is True
        assert prefs.is_greedy_eater is True
        assert prefs.is_picky_eater is True

    # === Drink Preferences Tests ===

    def test_drink_preferences_defaults(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify drink preference defaults."""
        entity = create_entity(db_session, game_session)
        prefs = CharacterPreferences(
            entity_id=entity.id,
            session_id=game_session.id,
        )
        db_session.add(prefs)
        db_session.flush()

        assert prefs.favorite_drinks is None
        assert prefs.disliked_drinks is None
        assert prefs.alcohol_tolerance == AlcoholTolerance.MODERATE
        assert prefs.is_alcoholic is False
        assert prefs.is_teetotaler is False

    def test_alcohol_tolerance_enum(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify AlcoholTolerance enum storage."""
        for tolerance in AlcoholTolerance:
            entity = create_entity(db_session, game_session)
            prefs = create_character_preferences(
                db_session, game_session, entity, alcohol_tolerance=tolerance
            )
            db_session.refresh(prefs)
            assert prefs.alcohol_tolerance == tolerance

    def test_drink_preferences_json(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify drink preference JSON fields."""
        entity = create_entity(db_session, game_session)
        favorites = ["ale", "wine", "mead"]
        dislikes = ["whiskey"]

        prefs = create_character_preferences(
            db_session,
            game_session,
            entity,
            favorite_drinks=favorites,
            disliked_drinks=dislikes,
        )
        db_session.refresh(prefs)

        assert prefs.favorite_drinks == favorites
        assert prefs.disliked_drinks == dislikes

    # === Intimacy Preferences Tests (migrated from IntimacyProfile) ===

    def test_intimacy_defaults(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify intimacy preference defaults."""
        entity = create_entity(db_session, game_session)
        prefs = CharacterPreferences(
            entity_id=entity.id,
            session_id=game_session.id,
        )
        db_session.add(prefs)
        db_session.flush()

        assert prefs.drive_level == DriveLevel.MODERATE
        assert prefs.drive_threshold == 50
        assert prefs.intimacy_style == IntimacyStyle.EMOTIONAL
        assert prefs.attraction_preferences is None
        assert prefs.has_regular_partner is False
        assert prefs.is_actively_seeking is False

    def test_intimacy_drive_level_enum(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify DriveLevel enum storage."""
        for drive in DriveLevel:
            entity = create_entity(db_session, game_session)
            prefs = create_character_preferences(
                db_session, game_session, entity, drive_level=drive
            )
            db_session.refresh(prefs)
            assert prefs.drive_level == drive

    def test_intimacy_style_enum(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify IntimacyStyle enum storage."""
        for style in IntimacyStyle:
            entity = create_entity(db_session, game_session)
            prefs = create_character_preferences(
                db_session, game_session, entity, intimacy_style=style
            )
            db_session.refresh(prefs)
            assert prefs.intimacy_style == style

    def test_attraction_preferences_json(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify attraction_preferences JSON field."""
        entity = create_entity(db_session, game_session)
        preferences = {
            "gender": "any",
            "age_range": [25, 40],
            "traits": ["confident", "kind", "intelligent"],
        }
        prefs = create_character_preferences(
            db_session, game_session, entity, attraction_preferences=preferences
        )
        db_session.refresh(prefs)

        assert prefs.attraction_preferences == preferences
        assert prefs.attraction_preferences["traits"] == ["confident", "kind", "intelligent"]

    # === Social Preferences Tests ===

    def test_social_preferences_defaults(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify social preference defaults."""
        entity = create_entity(db_session, game_session)
        prefs = CharacterPreferences(
            entity_id=entity.id,
            session_id=game_session.id,
        )
        db_session.add(prefs)
        db_session.flush()

        assert prefs.social_tendency == SocialTendency.AMBIVERT
        assert prefs.preferred_group_size == 3
        assert prefs.is_social_butterfly is False
        assert prefs.is_loner is False

    def test_social_tendency_enum(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify SocialTendency enum storage."""
        for tendency in SocialTendency:
            entity = create_entity(db_session, game_session)
            prefs = create_character_preferences(
                db_session, game_session, entity, social_tendency=tendency
            )
            db_session.refresh(prefs)
            assert prefs.social_tendency == tendency

    # === Stamina Traits Tests ===

    def test_stamina_traits_defaults(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify stamina trait defaults."""
        entity = create_entity(db_session, game_session)
        prefs = CharacterPreferences(
            entity_id=entity.id,
            session_id=game_session.id,
        )
        db_session.add(prefs)
        db_session.flush()

        assert prefs.has_high_stamina is False
        assert prefs.has_low_stamina is False
        assert prefs.is_insomniac is False
        assert prefs.is_heavy_sleeper is False

    def test_stamina_traits_custom(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify stamina trait custom values."""
        entity = create_entity(db_session, game_session)
        prefs = create_character_preferences(
            db_session,
            game_session,
            entity,
            has_high_stamina=True,
            is_insomniac=True,
        )
        db_session.refresh(prefs)

        assert prefs.has_high_stamina is True
        assert prefs.is_insomniac is True

    # === Extra Preferences Tests ===

    def test_extra_preferences_json(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify extra_preferences JSON field for setting-specific data."""
        entity = create_entity(db_session, game_session)
        extras = {
            "mana_affinity": "fire",
            "tech_preference": "cybernetics",
            "custom_trait": True,
        }
        prefs = create_character_preferences(
            db_session, game_session, entity, extra_preferences=extras
        )
        db_session.refresh(prefs)

        assert prefs.extra_preferences == extras
        assert prefs.extra_preferences["mana_affinity"] == "fire"

    # === Relationship and Cascade Tests ===

    def test_preferences_entity_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify preferences has back reference to entity."""
        entity = create_entity(db_session, game_session)
        prefs = create_character_preferences(db_session, game_session, entity)

        assert prefs.entity is not None
        assert prefs.entity.id == entity.id

    def test_preferences_cascade_delete(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify preferences deleted when entity is deleted."""
        entity = create_entity(db_session, game_session)
        prefs = create_character_preferences(db_session, game_session, entity)
        prefs_id = prefs.id

        db_session.delete(entity)
        db_session.flush()
        db_session.expire_all()

        result = db_session.query(CharacterPreferences).filter(
            CharacterPreferences.id == prefs_id
        ).first()
        assert result is None

    def test_preferences_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        entity = create_entity(db_session, game_session)
        prefs = create_character_preferences(
            db_session,
            game_session,
            entity,
            social_tendency=SocialTendency.EXTROVERT,
            drive_level=DriveLevel.HIGH,
        )

        repr_str = repr(prefs)
        assert "CharacterPreferences" in repr_str
        assert "extrovert" in repr_str


class TestNeedModifier:
    """Tests for NeedModifier model."""

    def test_create_need_modifier_required_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify NeedModifier creation with required fields."""
        entity = create_entity(db_session, game_session)
        modifier = NeedModifier(
            entity_id=entity.id,
            session_id=game_session.id,
            need_name="hunger",
            modifier_source=ModifierSource.TRAIT,
        )
        db_session.add(modifier)
        db_session.flush()

        assert modifier.id is not None
        assert modifier.entity_id == entity.id
        assert modifier.need_name == "hunger"

    def test_modifier_source_enum(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify ModifierSource enum storage."""
        for source in ModifierSource:
            entity = create_entity(db_session, game_session)
            modifier = create_need_modifier(
                db_session, game_session, entity,
                need_name=f"test_{source.value}",
                modifier_source=source,
            )
            db_session.refresh(modifier)
            assert modifier.modifier_source == source

    def test_modifier_defaults(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify modifier defaults."""
        entity = create_entity(db_session, game_session)
        modifier = NeedModifier(
            entity_id=entity.id,
            session_id=game_session.id,
            need_name="fatigue",
            modifier_source=ModifierSource.AGE,
        )
        db_session.add(modifier)
        db_session.flush()

        assert modifier.decay_rate_multiplier == 1.0
        assert modifier.satisfaction_multiplier == 1.0
        assert modifier.max_intensity_cap is None
        assert modifier.threshold_adjustment == 0
        assert modifier.is_active is True
        assert modifier.expires_at_turn is None

    def test_modifier_custom_values(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify custom modifier values."""
        entity = create_entity(db_session, game_session)
        modifier = create_need_modifier(
            db_session,
            game_session,
            entity,
            need_name="hunger",
            modifier_source=ModifierSource.TRAIT,
            source_detail="greedy_eater",
            decay_rate_multiplier=1.35,
            satisfaction_multiplier=0.8,
            max_intensity_cap=80,
            threshold_adjustment=-10,
        )
        db_session.refresh(modifier)

        assert modifier.decay_rate_multiplier == 1.35
        assert modifier.satisfaction_multiplier == 0.8
        assert modifier.max_intensity_cap == 80
        assert modifier.threshold_adjustment == -10
        assert modifier.source_detail == "greedy_eater"

    def test_modifier_expiration(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify modifier expiration fields."""
        entity = create_entity(db_session, game_session)
        modifier = create_need_modifier(
            db_session,
            game_session,
            entity,
            need_name="fatigue",
            modifier_source=ModifierSource.TEMPORARY,
            expires_at_turn=100,
            is_active=True,
        )
        db_session.refresh(modifier)

        assert modifier.expires_at_turn == 100
        assert modifier.is_active is True

    def test_modifier_unique_constraint(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify unique constraint on entity_id, need_name, source, source_detail."""
        entity = create_entity(db_session, game_session)
        create_need_modifier(
            db_session,
            game_session,
            entity,
            need_name="hunger",
            modifier_source=ModifierSource.TRAIT,
            source_detail="greedy_eater",
        )

        with pytest.raises(IntegrityError):
            create_need_modifier(
                db_session,
                game_session,
                entity,
                need_name="hunger",
                modifier_source=ModifierSource.TRAIT,
                source_detail="greedy_eater",
            )

    def test_modifier_multiple_per_entity(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify multiple modifiers allowed for same entity, different needs."""
        entity = create_entity(db_session, game_session)
        mod1 = create_need_modifier(
            db_session, game_session, entity,
            need_name="hunger",
            modifier_source=ModifierSource.TRAIT,
        )
        mod2 = create_need_modifier(
            db_session, game_session, entity,
            need_name="fatigue",
            modifier_source=ModifierSource.AGE,
        )

        assert mod1.id != mod2.id
        assert mod1.entity_id == mod2.entity_id

    def test_modifier_cascade_delete(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify modifiers deleted when entity is deleted."""
        entity = create_entity(db_session, game_session)
        modifier = create_need_modifier(
            db_session, game_session, entity, need_name="hunger"
        )
        modifier_id = modifier.id

        db_session.delete(entity)
        db_session.flush()
        db_session.expire_all()

        result = db_session.query(NeedModifier).filter(
            NeedModifier.id == modifier_id
        ).first()
        assert result is None

    def test_modifier_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        entity = create_entity(db_session, game_session)
        modifier = create_need_modifier(
            db_session,
            game_session,
            entity,
            need_name="hunger",
            modifier_source=ModifierSource.TRAIT,
            decay_rate_multiplier=1.5,
        )

        repr_str = repr(modifier)
        assert "NeedModifier" in repr_str
        assert "hunger" in repr_str
        assert "1.5" in repr_str


class TestNeedAdaptation:
    """Tests for NeedAdaptation model."""

    def test_create_adaptation_required_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify NeedAdaptation creation with required fields."""
        entity = create_entity(db_session, game_session)
        adaptation = NeedAdaptation(
            entity_id=entity.id,
            session_id=game_session.id,
            need_name="social_connection",
            adaptation_delta=-20,
            reason="Spent months alone in wilderness",
            started_turn=50,
        )
        db_session.add(adaptation)
        db_session.flush()

        assert adaptation.id is not None
        assert adaptation.entity_id == entity.id
        assert adaptation.need_name == "social_connection"
        assert adaptation.adaptation_delta == -20

    def test_adaptation_defaults(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify adaptation defaults."""
        entity = create_entity(db_session, game_session)
        adaptation = NeedAdaptation(
            entity_id=entity.id,
            session_id=game_session.id,
            need_name="comfort",
            adaptation_delta=-15,
            reason="Living outdoors",
            started_turn=1,
        )
        db_session.add(adaptation)
        db_session.flush()

        assert adaptation.trigger_event is None
        assert adaptation.completed_turn is None
        assert adaptation.is_gradual is True
        assert adaptation.duration_days is None
        assert adaptation.is_reversible is True
        assert adaptation.reversal_trigger is None

    def test_adaptation_complete_record(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify complete adaptation record."""
        entity = create_entity(db_session, game_session)
        adaptation = create_need_adaptation(
            db_session,
            game_session,
            entity,
            need_name="social_connection",
            adaptation_delta=-25,
            reason="Child separated from parents for extended period",
            trigger_event="Parents killed by bandits",
            started_turn=10,
            completed_turn=100,
            is_gradual=True,
            duration_days=30,
            is_reversible=True,
            reversal_trigger="Reunited with caring adult figure",
        )
        db_session.refresh(adaptation)

        assert adaptation.adaptation_delta == -25
        assert adaptation.trigger_event == "Parents killed by bandits"
        assert adaptation.completed_turn == 100
        assert adaptation.duration_days == 30
        assert adaptation.reversal_trigger == "Reunited with caring adult figure"

    def test_adaptation_positive_delta(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify positive adaptation delta (increased need)."""
        entity = create_entity(db_session, game_session)
        adaptation = create_need_adaptation(
            db_session,
            game_session,
            entity,
            need_name="intimacy",
            adaptation_delta=15,
            reason="New romantic relationship increased expectations",
        )
        db_session.refresh(adaptation)

        assert adaptation.adaptation_delta == 15

    def test_adaptation_sudden_not_gradual(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify sudden (non-gradual) adaptation."""
        entity = create_entity(db_session, game_session)
        adaptation = create_need_adaptation(
            db_session,
            game_session,
            entity,
            need_name="comfort",
            adaptation_delta=-30,
            reason="Traumatic event hardened character",
            is_gradual=False,
        )
        db_session.refresh(adaptation)

        assert adaptation.is_gradual is False

    def test_adaptation_irreversible(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify irreversible adaptation."""
        entity = create_entity(db_session, game_session)
        adaptation = create_need_adaptation(
            db_session,
            game_session,
            entity,
            need_name="social_connection",
            adaptation_delta=-40,
            reason="Permanent psychological trauma",
            is_reversible=False,
        )
        db_session.refresh(adaptation)

        assert adaptation.is_reversible is False

    def test_adaptation_multiple_per_entity(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify multiple adaptations allowed for same entity."""
        entity = create_entity(db_session, game_session)
        adap1 = create_need_adaptation(
            db_session, game_session, entity,
            need_name="social_connection",
            adaptation_delta=-10,
            reason="First event",
        )
        adap2 = create_need_adaptation(
            db_session, game_session, entity,
            need_name="social_connection",
            adaptation_delta=-5,
            reason="Second event",
        )
        adap3 = create_need_adaptation(
            db_session, game_session, entity,
            need_name="comfort",
            adaptation_delta=-15,
            reason="Different need",
        )

        assert adap1.id != adap2.id != adap3.id
        assert adap1.entity_id == adap2.entity_id == adap3.entity_id

    def test_adaptation_cascade_delete(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify adaptations deleted when entity is deleted."""
        entity = create_entity(db_session, game_session)
        adaptation = create_need_adaptation(
            db_session, game_session, entity,
            need_name="comfort",
            adaptation_delta=-10,
            reason="Test",
        )
        adaptation_id = adaptation.id

        db_session.delete(entity)
        db_session.flush()
        db_session.expire_all()

        result = db_session.query(NeedAdaptation).filter(
            NeedAdaptation.id == adaptation_id
        ).first()
        assert result is None

    def test_adaptation_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        entity = create_entity(db_session, game_session)
        adaptation = create_need_adaptation(
            db_session,
            game_session,
            entity,
            need_name="comfort",
            adaptation_delta=-20,
            reason="Living rough",
        )

        repr_str = repr(adaptation)
        assert "NeedAdaptation" in repr_str
        assert "comfort" in repr_str
        assert "-20" in repr_str
