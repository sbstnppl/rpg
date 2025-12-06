"""Tests for JSON-based setting schema loading."""

import json
from pathlib import Path

import pytest

from src.schemas.settings import (
    AttributeDefinition,
    SettingSchema,
    get_setting_schema,
    load_setting_from_json,
    get_settings_dir,
)


class TestSettingsDirectory:
    """Tests for settings directory discovery."""

    def test_get_settings_dir_returns_path(self):
        """get_settings_dir should return a Path object."""
        settings_dir = get_settings_dir()
        assert isinstance(settings_dir, Path)

    def test_get_settings_dir_exists(self):
        """Settings directory should exist."""
        settings_dir = get_settings_dir()
        assert settings_dir.exists()


class TestLoadSettingFromJson:
    """Tests for loading settings from JSON files."""

    def test_load_fantasy_setting(self):
        """Should load fantasy setting from JSON."""
        schema = load_setting_from_json("fantasy")
        assert schema.name == "fantasy"
        assert len(schema.attributes) == 6

    def test_load_contemporary_setting(self):
        """Should load contemporary setting from JSON."""
        schema = load_setting_from_json("contemporary")
        assert schema.name == "contemporary"
        assert len(schema.attributes) >= 6

    def test_load_scifi_setting(self):
        """Should load scifi setting from JSON."""
        schema = load_setting_from_json("scifi")
        assert schema.name == "scifi"
        assert len(schema.attributes) >= 6

    def test_unknown_setting_raises_error(self):
        """Should raise FileNotFoundError for unknown setting."""
        with pytest.raises(FileNotFoundError):
            load_setting_from_json("nonexistent_setting")

    def test_fantasy_has_expected_attributes(self):
        """Fantasy setting should have D&D-style attributes."""
        schema = load_setting_from_json("fantasy")
        attr_keys = {attr.key for attr in schema.attributes}
        expected = {"strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"}
        assert attr_keys == expected

    def test_fantasy_point_buy_settings(self):
        """Fantasy setting should have correct point-buy settings."""
        schema = load_setting_from_json("fantasy")
        assert schema.point_buy_total == 27
        assert schema.point_buy_min == 8
        assert schema.point_buy_max == 15

    def test_contemporary_has_modern_attributes(self):
        """Contemporary setting should have modern attributes."""
        schema = load_setting_from_json("contemporary")
        attr_keys = {attr.key for attr in schema.attributes}
        # Contemporary uses slightly different attribute names
        assert "strength" in attr_keys or "physical" in attr_keys
        assert len(attr_keys) >= 6

    def test_scifi_has_future_attributes(self):
        """Sci-fi setting should have future-appropriate attributes."""
        schema = load_setting_from_json("scifi")
        attr_keys = {attr.key for attr in schema.attributes}
        assert len(attr_keys) >= 6


class TestAttributeDefinitionFromJson:
    """Tests for AttributeDefinition parsing from JSON."""

    def test_attribute_has_required_fields(self):
        """Each attribute should have key and display_name."""
        schema = load_setting_from_json("fantasy")
        for attr in schema.attributes:
            assert hasattr(attr, "key")
            assert hasattr(attr, "display_name")
            assert isinstance(attr.key, str)
            assert isinstance(attr.display_name, str)

    def test_attribute_has_value_ranges(self):
        """Each attribute should have min/max/default values."""
        schema = load_setting_from_json("fantasy")
        for attr in schema.attributes:
            assert hasattr(attr, "min_value")
            assert hasattr(attr, "max_value")
            assert hasattr(attr, "default_value")
            assert attr.min_value <= attr.default_value <= attr.max_value


class TestSettingSchemaValidation:
    """Tests for setting schema validation."""

    def test_point_buy_range_is_valid(self):
        """Point buy min should be less than max."""
        for setting in ["fantasy", "contemporary", "scifi"]:
            schema = load_setting_from_json(setting)
            assert schema.point_buy_min < schema.point_buy_max

    def test_all_settings_have_equipment_slots(self):
        """Each setting should define equipment slots."""
        for setting in ["fantasy", "contemporary", "scifi"]:
            schema = load_setting_from_json(setting)
            assert hasattr(schema, "equipment_slots")
            assert isinstance(schema.equipment_slots, list)

    def test_all_settings_have_description(self):
        """Each setting should have a description."""
        for setting in ["fantasy", "contemporary", "scifi"]:
            schema = load_setting_from_json(setting)
            assert hasattr(schema, "description")
            assert isinstance(schema.description, str)
            assert len(schema.description) > 0


class TestGetSettingSchemaWithJson:
    """Tests for get_setting_schema with JSON loading."""

    def test_get_setting_schema_loads_from_json(self):
        """get_setting_schema should load from JSON if available."""
        schema = get_setting_schema("fantasy")
        assert schema.name == "fantasy"

    def test_get_setting_schema_fallback_for_unknown(self):
        """get_setting_schema should fallback to fantasy for unknown settings."""
        schema = get_setting_schema("unknown_setting")
        assert schema.name == "fantasy"
