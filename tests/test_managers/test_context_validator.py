"""Tests for ContextValidator class - pre-generation validation."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.enums import EntityType
from src.database.models.session import GameSession
from src.managers.context_validator import (
    ContextValidator,
    ValidationIssue,
    ValidationResult,
)
from tests.factories import (
    create_entity,
    create_fact,
    create_location,
    create_time_state,
)


class TestEntityValidation:
    """Tests for entity reference validation."""

    def test_validate_entity_exists(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify validation passes for existing entity."""
        create_entity(
            db_session, game_session,
            entity_key="bartender_bob",
            display_name="Bob",
            entity_type=EntityType.NPC,
        )
        validator = ContextValidator(db_session, game_session)

        result = validator.validate_entity_reference("bartender_bob")

        assert result.is_valid is True
        assert len(result.issues) == 0

    def test_validate_entity_not_found(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify validation fails for non-existent entity."""
        validator = ContextValidator(db_session, game_session)

        result = validator.validate_entity_reference("unknown_npc")

        assert result.is_valid is False
        assert len(result.issues) == 1
        assert result.issues[0].category == "entity"
        assert "unknown_npc" in result.issues[0].description

    def test_validate_entity_player_keyword(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify 'player' keyword is always valid."""
        create_entity(
            db_session, game_session,
            entity_key="hero",
            display_name="Hero",
            entity_type=EntityType.PLAYER,
        )
        validator = ContextValidator(db_session, game_session)

        result = validator.validate_entity_reference("player")

        assert result.is_valid is True

    def test_validate_multiple_entities(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify batch validation of multiple entity references."""
        create_entity(
            db_session, game_session,
            entity_key="npc_a",
            display_name="A",
            entity_type=EntityType.NPC,
        )
        validator = ContextValidator(db_session, game_session)

        result = validator.validate_entity_references(["npc_a", "npc_b", "npc_c"])

        assert result.is_valid is False
        assert len(result.issues) == 2  # npc_b and npc_c missing


class TestLocationValidation:
    """Tests for location reference validation."""

    def test_validate_location_exists(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify validation passes for existing location."""
        create_location(
            db_session, game_session,
            location_key="tavern",
            display_name="The Rusty Mug",
        )
        validator = ContextValidator(db_session, game_session)

        result = validator.validate_location_reference("tavern")

        assert result.is_valid is True

    def test_validate_location_not_found(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify validation fails for unknown location."""
        validator = ContextValidator(db_session, game_session)

        result = validator.validate_location_reference("unknown_place")

        assert result.is_valid is False
        assert result.issues[0].category == "location"

    def test_validate_location_allows_new_discovery(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify new location discovery is allowed with warning."""
        validator = ContextValidator(db_session, game_session)

        result = validator.validate_location_reference(
            "new_area",
            allow_new=True,
        )

        # Should be valid but with a warning
        assert result.is_valid is True
        assert len(result.warnings) == 1
        assert "new" in result.warnings[0].lower()


class TestFactConsistency:
    """Tests for fact consistency validation."""

    def test_fact_consistency_no_conflict(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify no conflict when facts are consistent."""
        create_fact(
            db_session, game_session,
            subject_key="bob",
            predicate="occupation",
            value="blacksmith",
        )
        validator = ContextValidator(db_session, game_session)

        result = validator.validate_fact_consistency(
            subject_key="bob",
            predicate="hometown",
            value="Riverdale",
        )

        assert result.is_valid is True

    def test_fact_consistency_detects_contradiction(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify contradiction detected when fact conflicts."""
        create_fact(
            db_session, game_session,
            subject_key="bob",
            predicate="occupation",
            value="blacksmith",
        )
        validator = ContextValidator(db_session, game_session)

        result = validator.validate_fact_consistency(
            subject_key="bob",
            predicate="occupation",
            value="baker",  # Contradicts existing
        )

        assert result.is_valid is False
        assert "contradiction" in result.issues[0].description.lower()
        assert "blacksmith" in result.issues[0].description

    def test_fact_consistency_allows_update_flag(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify fact update is allowed when explicitly requested."""
        create_fact(
            db_session, game_session,
            subject_key="bob",
            predicate="mood",
            value="happy",
        )
        validator = ContextValidator(db_session, game_session)

        result = validator.validate_fact_consistency(
            subject_key="bob",
            predicate="mood",
            value="angry",
            allow_update=True,  # Mood can change
        )

        assert result.is_valid is True


class TestTimeConsistency:
    """Tests for temporal consistency validation."""

    def test_time_consistency_valid(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify no issue when description matches time."""
        create_time_state(
            db_session, game_session,
            current_time="14:00",  # 2 PM
            weather="sunny",
        )
        validator = ContextValidator(db_session, game_session)

        result = validator.validate_time_consistency(
            description="The sun shines brightly through the window",
        )

        assert result.is_valid is True

    def test_time_consistency_detects_night_sun(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify contradiction when sun is mentioned at night."""
        create_time_state(
            db_session, game_session,
            current_time="02:00",  # 2 AM
            weather="clear",
        )
        validator = ContextValidator(db_session, game_session)

        result = validator.validate_time_consistency(
            description="The afternoon sun beats down on the marketplace",
        )

        assert result.is_valid is False
        assert "time" in result.issues[0].category

    def test_time_consistency_detects_weather_mismatch(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify contradiction when weather doesn't match."""
        create_time_state(
            db_session, game_session,
            current_time="12:00",
            weather="heavy_rain",
        )
        validator = ContextValidator(db_session, game_session)

        result = validator.validate_time_consistency(
            description="You walk under the clear blue sky",
        )

        assert result.is_valid is False
        assert "weather" in result.issues[0].description.lower()


class TestUniqueRoleValidation:
    """Tests for unique role validation (e.g., only one mayor)."""

    def test_unique_role_no_conflict(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify no conflict when role is not yet taken."""
        validator = ContextValidator(db_session, game_session)

        result = validator.validate_unique_role(
            entity_key="new_npc",
            role="mayor",
            location_key="village",
        )

        assert result.is_valid is True

    def test_unique_role_detects_duplicate(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify conflict when unique role already exists."""
        # Create existing mayor
        create_entity(
            db_session, game_session,
            entity_key="mayor_james",
            display_name="Mayor James",
            entity_type=EntityType.NPC,
        )
        create_fact(
            db_session, game_session,
            subject_key="mayor_james",
            predicate="occupation",
            value="mayor",
        )
        create_fact(
            db_session, game_session,
            subject_key="mayor_james",
            predicate="workplace",
            value="village",
        )
        validator = ContextValidator(db_session, game_session)

        result = validator.validate_unique_role(
            entity_key="new_mayor",
            role="mayor",
            location_key="village",
        )

        assert result.is_valid is False
        assert "mayor_james" in result.issues[0].description


class TestBatchValidation:
    """Tests for validating extraction results."""

    def test_validate_extraction_result_all_valid(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify batch validation passes for valid extraction."""
        create_entity(
            db_session, game_session,
            entity_key="player",
            display_name="Hero",
            entity_type=EntityType.PLAYER,
        )
        create_entity(
            db_session, game_session,
            entity_key="bob",
            display_name="Bob",
            entity_type=EntityType.NPC,
        )
        create_location(
            db_session, game_session,
            location_key="tavern",
            display_name="Tavern",
        )
        create_time_state(db_session, game_session, current_time="14:00", weather="sunny")
        validator = ContextValidator(db_session, game_session)

        result = validator.validate_extraction(
            entity_keys=["player", "bob"],
            location_key="tavern",
            facts=[
                {"subject_key": "bob", "predicate": "mood", "value": "happy"}
            ],
        )

        assert result.is_valid is True

    def test_validate_extraction_result_collects_all_issues(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify batch validation collects all issues."""
        validator = ContextValidator(db_session, game_session)

        result = validator.validate_extraction(
            entity_keys=["unknown_a", "unknown_b"],
            location_key="unknown_loc",
            facts=[],
        )

        assert result.is_valid is False
        # Should have issues for 2 entities + 1 location
        assert len(result.issues) >= 3
