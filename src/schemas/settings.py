"""Setting-specific attribute and character definitions.

This module provides setting-agnostic character attribute schemas
that can be customized per game setting (fantasy, sci-fi, etc.).
"""

import random
from dataclasses import dataclass, field


@dataclass
class AttributeDefinition:
    """Definition for a character attribute."""

    key: str
    display_name: str
    min_value: int = 3
    max_value: int = 18
    default_value: int = 10


@dataclass
class SettingSchema:
    """Complete schema for a game setting."""

    name: str
    attributes: list[AttributeDefinition] = field(default_factory=list)
    point_buy_total: int = 27
    point_buy_min: int = 8
    point_buy_max: int = 15


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

    Args:
        setting_name: Name of the setting.

    Returns:
        SettingSchema for the setting (defaults to fantasy if unknown).
    """
    return _SETTINGS.get(setting_name, _SETTINGS["fantasy"])


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
