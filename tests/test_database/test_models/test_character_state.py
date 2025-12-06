"""Tests for CharacterNeeds and IntimacyProfile models."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.database.models.character_state import CharacterNeeds, IntimacyProfile
from src.database.models.enums import DriveLevel, IntimacyStyle
from src.database.models.session import GameSession
from tests.factories import (
    create_character_needs,
    create_entity,
    create_game_session,
    create_intimacy_profile,
)


class TestCharacterNeeds:
    """Tests for CharacterNeeds model."""

    def test_create_character_needs_required_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify CharacterNeeds creation with required fields."""
        entity = create_entity(db_session, game_session)
        needs = CharacterNeeds(
            entity_id=entity.id,
            session_id=game_session.id,
        )
        db_session.add(needs)
        db_session.flush()

        assert needs.id is not None
        assert needs.entity_id == entity.id
        assert needs.session_id == game_session.id

    def test_character_needs_one_to_one(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify unique entity_id constraint."""
        entity = create_entity(db_session, game_session)
        create_character_needs(db_session, game_session, entity)

        with pytest.raises(IntegrityError):
            create_character_needs(db_session, game_session, entity)

    def test_needs_tier1_survival_defaults(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify tier 1 survival needs defaults."""
        entity = create_entity(db_session, game_session)
        needs = CharacterNeeds(
            entity_id=entity.id,
            session_id=game_session.id,
        )
        db_session.add(needs)
        db_session.flush()

        assert needs.hunger == 50  # Satisfied
        assert needs.fatigue == 20  # Rested

    def test_needs_tier2_comfort_defaults(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify tier 2 comfort needs defaults."""
        entity = create_entity(db_session, game_session)
        needs = CharacterNeeds(
            entity_id=entity.id,
            session_id=game_session.id,
        )
        db_session.add(needs)
        db_session.flush()

        assert needs.hygiene == 80  # Clean
        assert needs.comfort == 70  # Comfortable
        assert needs.pain == 0  # No pain

    def test_needs_tier3_psychological_defaults(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify tier 3 psychological needs defaults."""
        entity = create_entity(db_session, game_session)
        needs = CharacterNeeds(
            entity_id=entity.id,
            session_id=game_session.id,
        )
        db_session.add(needs)
        db_session.flush()

        assert needs.social_connection == 60
        assert needs.morale == 70
        assert needs.sense_of_purpose == 50
        assert needs.intimacy == 30

    def test_needs_custom_values(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify custom need values."""
        entity = create_entity(db_session, game_session)
        needs = create_character_needs(
            db_session,
            game_session,
            entity,
            hunger=20,  # Hungry
            fatigue=80,  # Very tired
            morale=30,  # Low morale
        )

        db_session.refresh(needs)

        assert needs.hunger == 20
        assert needs.fatigue == 80
        assert needs.morale == 30

    def test_needs_timestamps(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify last_X_turn tracking fields."""
        entity = create_entity(db_session, game_session)
        needs = create_character_needs(
            db_session,
            game_session,
            entity,
            last_meal_turn=5,
            last_sleep_turn=3,
            last_bath_turn=1,
            last_social_turn=2,
            last_intimate_turn=10,
        )

        db_session.refresh(needs)

        assert needs.last_meal_turn == 5
        assert needs.last_sleep_turn == 3
        assert needs.last_bath_turn == 1
        assert needs.last_social_turn == 2
        assert needs.last_intimate_turn == 10

    def test_needs_entity_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify needs has back reference to entity."""
        entity = create_entity(db_session, game_session)
        needs = create_character_needs(db_session, game_session, entity)

        assert needs.entity is not None
        assert needs.entity.id == entity.id

    def test_needs_cascade_delete(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify needs deleted when entity is deleted."""
        entity = create_entity(db_session, game_session)
        needs = create_character_needs(db_session, game_session, entity)
        needs_id = needs.id

        db_session.delete(entity)
        db_session.flush()
        db_session.expire_all()

        result = db_session.query(CharacterNeeds).filter(
            CharacterNeeds.id == needs_id
        ).first()
        assert result is None

    def test_needs_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        entity = create_entity(db_session, game_session)
        needs = create_character_needs(
            db_session,
            game_session,
            entity,
            hunger=40,
            fatigue=60,
            morale=75,
        )

        repr_str = repr(needs)
        assert "CharacterNeeds" in repr_str
        assert "H:40" in repr_str
        assert "F:60" in repr_str
        assert "M:75" in repr_str


class TestIntimacyProfile:
    """Tests for IntimacyProfile model."""

    def test_create_intimacy_profile_required_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify IntimacyProfile creation with required fields."""
        entity = create_entity(db_session, game_session)
        profile = IntimacyProfile(
            entity_id=entity.id,
            session_id=game_session.id,
        )
        db_session.add(profile)
        db_session.flush()

        assert profile.id is not None
        assert profile.entity_id == entity.id

    def test_intimacy_profile_one_to_one(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify unique entity_id constraint."""
        entity = create_entity(db_session, game_session)
        create_intimacy_profile(db_session, game_session, entity)

        with pytest.raises(IntegrityError):
            create_intimacy_profile(db_session, game_session, entity)

    def test_intimacy_drive_level_enum(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify DriveLevel enum storage."""
        for drive in DriveLevel:
            entity = create_entity(db_session, game_session)
            profile = create_intimacy_profile(
                db_session, game_session, entity, drive_level=drive
            )
            db_session.refresh(profile)
            assert profile.drive_level == drive

    def test_intimacy_style_enum(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify IntimacyStyle enum storage."""
        for style in IntimacyStyle:
            entity = create_entity(db_session, game_session)
            profile = create_intimacy_profile(
                db_session, game_session, entity, intimacy_style=style
            )
            db_session.refresh(profile)
            assert profile.intimacy_style == style

    def test_intimacy_preferences_json(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify attraction_preferences JSON field."""
        entity = create_entity(db_session, game_session)
        preferences = {
            "gender": "any",
            "age_range": [25, 40],
            "traits": ["confident", "kind", "intelligent"],
        }
        profile = create_intimacy_profile(
            db_session, game_session, entity, attraction_preferences=preferences
        )

        db_session.refresh(profile)

        assert profile.attraction_preferences == preferences
        assert profile.attraction_preferences["traits"] == ["confident", "kind", "intelligent"]

    def test_intimacy_status_flags(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify has_regular_partner and is_actively_seeking flags."""
        entity = create_entity(db_session, game_session)
        profile = create_intimacy_profile(
            db_session,
            game_session,
            entity,
            has_regular_partner=True,
            is_actively_seeking=False,
        )

        db_session.refresh(profile)

        assert profile.has_regular_partner is True
        assert profile.is_actively_seeking is False

    def test_intimacy_drive_threshold(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify drive_threshold field."""
        entity = create_entity(db_session, game_session)
        profile = create_intimacy_profile(
            db_session, game_session, entity, drive_threshold=70
        )

        db_session.refresh(profile)
        assert profile.drive_threshold == 70

    def test_intimacy_entity_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify profile has back reference to entity."""
        entity = create_entity(db_session, game_session)
        profile = create_intimacy_profile(db_session, game_session, entity)

        assert profile.entity is not None
        assert profile.entity.id == entity.id

    def test_intimacy_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        entity = create_entity(db_session, game_session)
        profile = create_intimacy_profile(
            db_session,
            game_session,
            entity,
            drive_level=DriveLevel.HIGH,
            intimacy_style=IntimacyStyle.CASUAL,
        )

        repr_str = repr(profile)
        assert "IntimacyProfile" in repr_str
        assert "high" in repr_str
        assert "casual" in repr_str
