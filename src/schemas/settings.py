"""Setting-specific attribute and character definitions.

This module provides setting-agnostic character attribute schemas
that can be customized per game setting (fantasy, sci-fi, etc.).
"""

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AttributeDefinition:
    """Definition for a character attribute."""

    key: str
    display_name: str
    description: str = ""
    min_value: int = 3
    max_value: int = 18
    default_value: int = 10


@dataclass
class EquipmentSlot:
    """Definition for an equipment slot."""

    key: str
    display_name: str
    layers: int = 1


@dataclass
class StartingItem:
    """Definition for a starting equipment item."""

    item_key: str
    display_name: str
    item_type: str  # Maps to ItemType enum value
    body_slot: str | None = None
    body_layer: int = 0
    description: str = ""
    properties: dict | None = None


@dataclass
class SettingSchema:
    """Complete schema for a game setting."""

    name: str
    description: str = ""
    attributes: list[AttributeDefinition] = field(default_factory=list)
    point_buy_total: int = 27
    point_buy_min: int = 8
    point_buy_max: int = 15
    equipment_slots: list[EquipmentSlot] = field(default_factory=list)
    starting_equipment: list[StartingItem] = field(default_factory=list)


def get_settings_dir() -> Path:
    """Get the path to the settings directory.

    Returns:
        Path to data/settings directory.
    """
    return Path(__file__).parent.parent.parent / "data" / "settings"


def load_setting_from_json(setting_name: str) -> SettingSchema:
    """Load a setting schema from a JSON file.

    Args:
        setting_name: Name of the setting (fantasy, contemporary, scifi).

    Returns:
        SettingSchema populated from the JSON file.

    Raises:
        FileNotFoundError: If the setting JSON file doesn't exist.
    """
    settings_dir = get_settings_dir()
    json_path = settings_dir / f"{setting_name}.json"

    if not json_path.exists():
        raise FileNotFoundError(f"Setting file not found: {json_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return _parse_setting_json(data)


def _parse_setting_json(data: dict[str, Any]) -> SettingSchema:
    """Parse a setting JSON structure into a SettingSchema.

    Args:
        data: Parsed JSON data.

    Returns:
        SettingSchema instance.
    """
    # Parse attributes
    attributes = []
    for attr_data in data.get("attributes", []):
        attributes.append(
            AttributeDefinition(
                key=attr_data["key"],
                display_name=attr_data["display_name"],
                description=attr_data.get("description", ""),
                min_value=attr_data.get("min_value", 3),
                max_value=attr_data.get("max_value", 18),
                default_value=attr_data.get("default_value", 10),
            )
        )

    # Parse equipment slots
    equipment_slots = []
    for slot_data in data.get("equipment_slots", []):
        equipment_slots.append(
            EquipmentSlot(
                key=slot_data["key"],
                display_name=slot_data["display_name"],
                layers=slot_data.get("layers", 1),
            )
        )

    # Parse point-buy settings
    point_buy = data.get("point_buy", {})

    # Parse starting equipment
    starting_equipment = []
    for item_data in data.get("starting_equipment", []):
        starting_equipment.append(
            StartingItem(
                item_key=item_data["item_key"],
                display_name=item_data["display_name"],
                item_type=item_data.get("item_type", "misc"),
                body_slot=item_data.get("body_slot"),
                body_layer=item_data.get("body_layer", 0),
                description=item_data.get("description", ""),
                properties=item_data.get("properties"),
            )
        )

    return SettingSchema(
        name=data["name"],
        description=data.get("description", ""),
        attributes=attributes,
        point_buy_total=point_buy.get("total_points", 27),
        point_buy_min=point_buy.get("min_value", 8),
        point_buy_max=point_buy.get("max_value", 15),
        equipment_slots=equipment_slots,
        starting_equipment=starting_equipment,
    )


# Fantasy setting - D&D-style attributes
FANTASY_ATTRIBUTES = [
    AttributeDefinition("strength", "Strength"),
    AttributeDefinition("dexterity", "Dexterity"),
    AttributeDefinition("constitution", "Constitution"),
    AttributeDefinition("intelligence", "Intelligence"),
    AttributeDefinition("wisdom", "Wisdom"),
    AttributeDefinition("charisma", "Charisma"),
]

# Pre-defined settings
_SETTINGS: dict[str, SettingSchema] = {
    "fantasy": SettingSchema(
        name="fantasy",
        attributes=FANTASY_ATTRIBUTES,
        point_buy_total=27,
        point_buy_min=8,
        point_buy_max=15,
    ),
}


def get_setting_schema(setting_name: str) -> SettingSchema:
    """Get the schema for a setting.

    Tries to load from JSON first, then falls back to hardcoded settings.

    Args:
        setting_name: Name of the setting.

    Returns:
        SettingSchema for the setting (defaults to fantasy if unknown).
    """
    # Try to load from JSON first
    try:
        return load_setting_from_json(setting_name)
    except FileNotFoundError:
        pass

    # Fall back to hardcoded settings
    if setting_name in _SETTINGS:
        return _SETTINGS[setting_name]

    # Default to fantasy
    try:
        return load_setting_from_json("fantasy")
    except FileNotFoundError:
        return _SETTINGS["fantasy"]


# Point-buy cost table (D&D 5e style)
# Value 8 costs 0, each point above 8 costs more
_POINT_COSTS = {
    8: 0,
    9: 1,
    10: 2,
    11: 3,
    12: 4,
    13: 5,
    14: 7,  # 14 and 15 cost more
    15: 9,
}


def calculate_point_cost(value: int) -> int:
    """Calculate point-buy cost for an attribute value.

    Args:
        value: The attribute value (8-15 for standard point-buy).

    Returns:
        Point cost for that value.

    Raises:
        ValueError: If value is outside point-buy range.
    """
    if value < 8 or value > 15:
        raise ValueError(f"Value {value} is outside point-buy range (8-15)")
    return _POINT_COSTS[value]


def validate_point_buy(
    attributes: dict[str, int],
    total_points: int = 27,
) -> tuple[bool, str | None]:
    """Validate a point-buy attribute allocation.

    Args:
        attributes: Dict of attribute_key to value.
        total_points: Maximum points allowed (default 27).

    Returns:
        Tuple of (is_valid, error_message or None).
    """
    total_cost = 0

    for key, value in attributes.items():
        if value < 8:
            return False, f"Attribute '{key}' is below minimum (8)"
        if value > 15:
            return False, f"Attribute '{key}' is above maximum (15)"

        total_cost += _POINT_COSTS[value]

    if total_cost > total_points:
        return False, f"Total cost ({total_cost}) exceeds budget ({total_points})"

    return True, None


def roll_attribute() -> int:
    """Roll a single attribute using 4d6-drop-lowest.

    Returns:
        Attribute value (3-18).
    """
    rolls = [random.randint(1, 6) for _ in range(4)]
    # Drop lowest, sum rest
    rolls.sort()
    return sum(rolls[1:])  # Sum top 3


def roll_all_attributes() -> dict[str, int]:
    """Roll all 6 attributes using 4d6-drop-lowest.

    Returns:
        Dict of attribute_key to rolled value.
    """
    return {
        "strength": roll_attribute(),
        "dexterity": roll_attribute(),
        "constitution": roll_attribute(),
        "intelligence": roll_attribute(),
        "wisdom": roll_attribute(),
        "charisma": roll_attribute(),
    }
