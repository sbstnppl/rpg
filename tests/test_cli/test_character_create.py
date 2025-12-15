"""Tests for character creation CLI command."""

import pytest
from unittest.mock import patch, MagicMock

from sqlalchemy.orm import Session

from src.database.models.enums import EntityType, VitalStatus
from src.database.models.entities import Entity, EntityAttribute
from src.database.models.character_state import CharacterNeeds
from src.database.models.vital_state import EntityVitalState
from src.database.models.session import GameSession


class TestSettingsSchema:
    """Test the settings schema module."""

    def test_fantasy_attributes_defined(self):
        """Fantasy setting should have 6 core attributes."""
        from src.schemas.settings import FANTASY_ATTRIBUTES

        assert len(FANTASY_ATTRIBUTES) == 6
        keys = [a.key for a in FANTASY_ATTRIBUTES]
        assert "strength" in keys
        assert "dexterity" in keys
        assert "constitution" in keys
        assert "intelligence" in keys
        assert "wisdom" in keys
        assert "charisma" in keys

    def test_attribute_definition_defaults(self):
        """AttributeDefinition should have sensible defaults."""
        from src.schemas.settings import AttributeDefinition

        attr = AttributeDefinition(key="test", display_name="Test")
        assert attr.min_value == 3
        assert attr.max_value == 18
        assert attr.default_value == 10

    def test_get_setting_schema_fantasy(self):
        """get_setting_schema should return fantasy schema."""
        from src.schemas.settings import get_setting_schema

        schema = get_setting_schema("fantasy")
        assert schema.name == "fantasy"
        assert len(schema.attributes) == 6
        assert schema.point_buy_total == 27

    def test_get_setting_schema_unknown_defaults_to_fantasy(self):
        """Unknown settings should default to fantasy."""
        from src.schemas.settings import get_setting_schema

        schema = get_setting_schema("unknown_setting")
        assert schema.name == "fantasy"


class TestPointBuyValidation:
    """Test point-buy allocation logic."""

    def test_calculate_point_cost_at_minimum(self):
        """Value of 8 should cost 0 points."""
        from src.schemas.settings import calculate_point_cost

        assert calculate_point_cost(8) == 0

    def test_calculate_point_cost_standard_values(self):
        """Standard point costs for values 9-15."""
        from src.schemas.settings import calculate_point_cost

        assert calculate_point_cost(9) == 1
        assert calculate_point_cost(10) == 2
        assert calculate_point_cost(11) == 3
        assert calculate_point_cost(12) == 4
        assert calculate_point_cost(13) == 5
        assert calculate_point_cost(14) == 7  # 14 and 15 cost more
        assert calculate_point_cost(15) == 9

    def test_validate_point_buy_valid(self):
        """Valid point-buy allocation should pass."""
        from src.schemas.settings import validate_point_buy

        # 15, 14, 13, 12, 10, 8 = 9 + 7 + 5 + 4 + 2 + 0 = 27 points
        attributes = {
            "strength": 15,
            "dexterity": 14,
            "constitution": 13,
            "intelligence": 12,
            "wisdom": 10,
            "charisma": 8,
        }
        is_valid, error = validate_point_buy(attributes)
        assert is_valid
        assert error is None

    def test_validate_point_buy_over_budget(self):
        """Over-budget allocation should fail."""
        from src.schemas.settings import validate_point_buy

        attributes = {
            "strength": 15,
            "dexterity": 15,
            "constitution": 15,
            "intelligence": 15,
            "wisdom": 15,
            "charisma": 15,
        }
        is_valid, error = validate_point_buy(attributes)
        assert not is_valid
        assert "exceeds" in error.lower()

    def test_validate_point_buy_value_too_low(self):
        """Values below 8 should fail."""
        from src.schemas.settings import validate_point_buy

        attributes = {
            "strength": 7,  # Too low
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
        }
        is_valid, error = validate_point_buy(attributes)
        assert not is_valid
        assert "minimum" in error.lower() or "below" in error.lower()

    def test_validate_point_buy_value_too_high(self):
        """Values above 15 should fail (pre-racial)."""
        from src.schemas.settings import validate_point_buy

        attributes = {
            "strength": 16,  # Too high
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
        }
        is_valid, error = validate_point_buy(attributes)
        assert not is_valid
        assert "maximum" in error.lower() or "above" in error.lower()


class TestRandomRolling:
    """Test 4d6-drop-lowest attribute generation."""

    def test_roll_attribute_returns_valid_range(self):
        """Single attribute roll should be 3-18."""
        from src.schemas.settings import roll_attribute

        # Roll many times to check range
        for _ in range(100):
            value = roll_attribute()
            assert 3 <= value <= 18

    def test_roll_all_attributes_returns_six(self):
        """roll_all_attributes should return all 6 attributes."""
        from src.schemas.settings import roll_all_attributes

        attributes = roll_all_attributes()
        assert len(attributes) == 6
        assert "strength" in attributes
        assert "dexterity" in attributes
        assert "constitution" in attributes
        assert "intelligence" in attributes
        assert "wisdom" in attributes
        assert "charisma" in attributes

        for key, value in attributes.items():
            assert 3 <= value <= 18


class TestCharacterCreation:
    """Test actual character creation in database."""

    def test_create_player_entity(self, db_session: Session, game_session: GameSession):
        """Creating character should create Entity with PLAYER type."""
        from src.cli.commands.character import _create_character_records

        attributes = {
            "strength": 15,
            "dexterity": 14,
            "constitution": 13,
            "intelligence": 12,
            "wisdom": 10,
            "charisma": 8,
        }

        entity = _create_character_records(
            db=db_session,
            game_session=game_session,
            name="Test Hero",
            attributes=attributes,
            background="A brave adventurer",
        )

        assert entity is not None
        assert entity.display_name == "Test Hero"
        assert entity.entity_type == EntityType.PLAYER
        assert entity.is_alive is True
        assert entity.is_active is True
        assert entity.background == "A brave adventurer"

    def test_create_player_attributes(self, db_session: Session, game_session: GameSession):
        """Character creation should create all 6 attributes."""
        from src.cli.commands.character import _create_character_records

        attributes = {
            "strength": 15,
            "dexterity": 14,
            "constitution": 13,
            "intelligence": 12,
            "wisdom": 10,
            "charisma": 8,
        }

        entity = _create_character_records(
            db=db_session,
            game_session=game_session,
            name="Test Hero",
            attributes=attributes,
        )

        # Query attributes
        db_attrs = (
            db_session.query(EntityAttribute)
            .filter(EntityAttribute.entity_id == entity.id)
            .all()
        )

        assert len(db_attrs) == 6
        attr_dict = {a.attribute_key: a.value for a in db_attrs}
        assert attr_dict["strength"] == 15
        assert attr_dict["dexterity"] == 14
        assert attr_dict["constitution"] == 13
        assert attr_dict["intelligence"] == 12
        assert attr_dict["wisdom"] == 10
        assert attr_dict["charisma"] == 8

    def test_create_player_needs(self, db_session: Session, game_session: GameSession):
        """Character creation should create CharacterNeeds."""
        from src.cli.commands.character import _create_character_records

        attributes = {"strength": 10, "dexterity": 10, "constitution": 10,
                      "intelligence": 10, "wisdom": 10, "charisma": 10}

        entity = _create_character_records(
            db=db_session,
            game_session=game_session,
            name="Test Hero",
            attributes=attributes,
        )

        needs = (
            db_session.query(CharacterNeeds)
            .filter(CharacterNeeds.entity_id == entity.id)
            .first()
        )

        assert needs is not None
        assert needs.hunger > 0
        assert needs.morale > 0

    def test_create_player_vital_state(self, db_session: Session, game_session: GameSession):
        """Character creation should create EntityVitalState."""
        from src.cli.commands.character import _create_character_records

        attributes = {"strength": 10, "dexterity": 10, "constitution": 10,
                      "intelligence": 10, "wisdom": 10, "charisma": 10}

        entity = _create_character_records(
            db=db_session,
            game_session=game_session,
            name="Test Hero",
            attributes=attributes,
        )

        vital = (
            db_session.query(EntityVitalState)
            .filter(EntityVitalState.entity_id == entity.id)
            .first()
        )

        assert vital is not None
        assert vital.vital_status == VitalStatus.HEALTHY
        assert vital.is_dead is False

    def test_creates_unique_entity_key(self, db_session: Session, game_session: GameSession):
        """Entity key should be generated from name."""
        from src.cli.commands.character import _create_character_records

        attributes = {"strength": 10, "dexterity": 10, "constitution": 10,
                      "intelligence": 10, "wisdom": 10, "charisma": 10}

        entity = _create_character_records(
            db=db_session,
            game_session=game_session,
            name="Sir Galahad the Brave",
            attributes=attributes,
        )

        assert entity.entity_key == "sir_galahad_the_brave"

    def test_prevents_duplicate_player(self, db_session: Session, game_session: GameSession):
        """Should not create multiple players in same session."""
        from src.cli.commands.character import _create_character_records

        attributes = {"strength": 10, "dexterity": 10, "constitution": 10,
                      "intelligence": 10, "wisdom": 10, "charisma": 10}

        # Create first player
        _create_character_records(
            db=db_session,
            game_session=game_session,
            name="Hero One",
            attributes=attributes,
        )
        db_session.commit()

        # Try to create second player - should raise
        with pytest.raises(ValueError, match="already has a player"):
            _create_character_records(
                db=db_session,
                game_session=game_session,
                name="Hero Two",
                attributes=attributes,
            )


class TestSlugify:
    """Test name to entity_key conversion."""

    def test_slugify_simple(self):
        """Simple name should lowercase and underscore."""
        from src.cli.commands.character import slugify

        assert slugify("John Smith") == "john_smith"

    def test_slugify_special_chars(self):
        """Special characters should be removed."""
        from src.cli.commands.character import slugify

        assert slugify("Sir Galahad the Brave!") == "sir_galahad_the_brave"

    def test_slugify_multiple_spaces(self):
        """Multiple spaces should collapse."""
        from src.cli.commands.character import slugify

        assert slugify("John    Smith") == "john_smith"

    def test_slugify_unicode(self):
        """Unicode should be handled."""
        from src.cli.commands.character import slugify

        assert slugify("José García") == "jose_garcia"


class TestExtractMissingAppearanceFields:
    """Tests for the fallback appearance field extraction from narrative."""

    def test_extracts_eye_color_from_simple_pattern(self):
        """Should extract 'hazel eyes' pattern."""
        from src.cli.commands.character import _extract_missing_appearance_fields

        updates = {"hair_color": "brown"}
        result = _extract_missing_appearance_fields(
            "A slim figure with hazel eyes and a warm smile.",
            updates
        )
        assert result["eye_color"] == "hazel"
        assert result["hair_color"] == "brown"  # Preserved

    def test_extracts_eye_color_with_modifier(self):
        """Should extract 'bright green eyes' pattern."""
        from src.cli.commands.character import _extract_missing_appearance_fields

        updates = {}
        result = _extract_missing_appearance_fields(
            "She has bright green eyes that seem to notice everything.",
            updates
        )
        assert "green" in result["eye_color"].lower()

    def test_does_not_overwrite_existing_eye_color(self):
        """Should not overwrite if eye_color already in updates."""
        from src.cli.commands.character import _extract_missing_appearance_fields

        updates = {"eye_color": "blue"}
        result = _extract_missing_appearance_fields(
            "hazel eyes with green flecks",
            updates
        )
        assert result["eye_color"] == "blue"  # Not overwritten

    def test_extracts_hair_color_from_simple_pattern(self):
        """Should extract 'brown hair' pattern."""
        from src.cli.commands.character import _extract_missing_appearance_fields

        updates = {"eye_color": "green"}
        result = _extract_missing_appearance_fields(
            "A young man with brown hair and green eyes.",
            updates
        )
        assert result["hair_color"] == "brown"
        assert result["eye_color"] == "green"  # Preserved

    def test_extracts_compound_eye_color(self):
        """Should handle compound colors like 'hazel-green'."""
        from src.cli.commands.character import _extract_missing_appearance_fields

        updates = {}
        result = _extract_missing_appearance_fields(
            "warm hazel-green eyes",
            updates
        )
        assert "hazel" in result.get("eye_color", "").lower()

    def test_handles_none_updates(self):
        """Should handle None updates dict."""
        from src.cli.commands.character import _extract_missing_appearance_fields

        result = _extract_missing_appearance_fields(
            "blue eyes and black hair",
            None
        )
        assert result["eye_color"] == "blue"
        assert result["hair_color"] == "black"

    def test_no_match_returns_unchanged(self):
        """Should return unchanged if no patterns match."""
        from src.cli.commands.character import _extract_missing_appearance_fields

        updates = {"build": "slim"}
        result = _extract_missing_appearance_fields(
            "A slim figure standing in the doorway.",
            updates
        )
        assert result == {"build": "slim"}
        assert "eye_color" not in result
        assert "hair_color" not in result
