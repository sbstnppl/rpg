"""Tests for starting equipment schema parsing."""

import pytest

from src.schemas.settings import (
    StartingItem,
    SettingSchema,
    get_setting_schema,
    load_setting_from_json,
)


class TestStartingItemSchema:
    """Tests for StartingItem dataclass."""

    def test_starting_item_required_fields(self):
        """Verify StartingItem has required fields."""
        item = StartingItem(
            item_key="test_item",
            display_name="Test Item",
            item_type="misc",
        )
        assert item.item_key == "test_item"
        assert item.display_name == "Test Item"
        assert item.item_type == "misc"

    def test_starting_item_optional_body_slot(self):
        """Verify body_slot defaults to None."""
        item = StartingItem(
            item_key="test",
            display_name="Test",
            item_type="misc",
        )
        assert item.body_slot is None

    def test_starting_item_optional_body_layer(self):
        """Verify body_layer defaults to 0."""
        item = StartingItem(
            item_key="test",
            display_name="Test",
            item_type="misc",
        )
        assert item.body_layer == 0

    def test_starting_item_with_body_slot(self):
        """Verify body_slot can be set."""
        item = StartingItem(
            item_key="shirt",
            display_name="Shirt",
            item_type="clothing",
            body_slot="torso",
            body_layer=0,
        )
        assert item.body_slot == "torso"
        assert item.body_layer == 0

    def test_starting_item_with_properties(self):
        """Verify properties can be set."""
        item = StartingItem(
            item_key="gold",
            display_name="Gold Coins",
            item_type="misc",
            properties={"value": 100, "currency": "gold"},
        )
        assert item.properties == {"value": 100, "currency": "gold"}


class TestSettingSchemaStartingEquipment:
    """Tests for starting_equipment in SettingSchema."""

    def test_fantasy_has_starting_equipment(self):
        """Verify fantasy setting has starting equipment."""
        schema = load_setting_from_json("fantasy")
        assert len(schema.starting_equipment) > 0

    def test_contemporary_has_starting_equipment(self):
        """Verify contemporary setting has starting equipment."""
        schema = load_setting_from_json("contemporary")
        assert len(schema.starting_equipment) > 0

    def test_scifi_has_starting_equipment(self):
        """Verify sci-fi setting has starting equipment."""
        schema = load_setting_from_json("scifi")
        assert len(schema.starting_equipment) > 0

    def test_starting_item_has_required_fields(self):
        """Verify all starting items have required fields."""
        for setting in ["fantasy", "contemporary", "scifi"]:
            schema = load_setting_from_json(setting)
            for item in schema.starting_equipment:
                assert item.item_key, f"Missing item_key in {setting}"
                assert item.display_name, f"Missing display_name in {setting}"
                assert item.item_type, f"Missing item_type in {setting}"

    def test_fantasy_has_clothing_items(self):
        """Verify fantasy has basic clothing."""
        schema = load_setting_from_json("fantasy")
        clothing_items = [
            item for item in schema.starting_equipment
            if item.item_type == "clothing"
        ]
        assert len(clothing_items) >= 2, "Should have at least 2 clothing items"

    def test_contemporary_has_smartphone(self):
        """Verify contemporary setting has a smartphone."""
        schema = load_setting_from_json("contemporary")
        item_keys = [item.item_key for item in schema.starting_equipment]
        assert "smartphone" in item_keys

    def test_scifi_has_wrist_comm(self):
        """Verify sci-fi setting has wrist communicator."""
        schema = load_setting_from_json("scifi")
        item_keys = [item.item_key for item in schema.starting_equipment]
        assert "wrist_comm" in item_keys

    def test_equipped_items_have_body_slot(self):
        """Verify items with body_slot are meant to be equipped."""
        for setting in ["fantasy", "contemporary", "scifi"]:
            schema = load_setting_from_json(setting)
            equipped_items = [
                item for item in schema.starting_equipment
                if item.body_slot is not None
            ]
            assert len(equipped_items) > 0, f"No equipped items in {setting}"


class TestSettingSchemaDefaults:
    """Tests for default values in SettingSchema."""

    def test_empty_starting_equipment_default(self):
        """Verify starting_equipment defaults to empty list."""
        schema = SettingSchema(name="test")
        assert schema.starting_equipment == []

    def test_get_setting_schema_includes_starting_equipment(self):
        """Verify get_setting_schema returns starting equipment."""
        schema = get_setting_schema("fantasy")
        assert hasattr(schema, "starting_equipment")
        assert isinstance(schema.starting_equipment, list)
