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
class SpeciesDefinition:
    """Definition for a playable species with gender options.

    Different species can have different available genders. For example:
    - Humans: Male, Female
    - Androids: None, Male-presenting, Female-presenting
    - Alien species: May have 3+ genders or entirely different concepts
    """

    name: str
    genders: list[str] = field(default_factory=lambda: ["Male", "Female"])


# =============================================================================
# Need Modifier Settings (Age Curves and Trait Effects)
# =============================================================================


@dataclass
class AsymmetricDistribution:
    """Asymmetric normal distribution parameters for age-based modifiers.

    Used to model how needs change with age. For example, intimacy drive
    peaks around age 18 and gradually declines with age, but drops sharply
    for very young ages.

    The distribution uses different standard deviations for ages below
    and above the peak age, allowing for asymmetric curves.
    """

    peak_age: int  # Age where the value is highest (e.g., 18 for intimacy)
    peak_value: float  # Expected value at peak age (e.g., 90)
    std_dev_lower: float  # Standard deviation for ages below peak (sharper curve)
    std_dev_upper: float  # Standard deviation for ages above peak (gradual decline)
    min_value: float = 0.0  # Minimum possible value
    max_value: float = 100.0  # Maximum possible value


@dataclass
class NeedAgeCurve:
    """Age curve configuration for a specific need.

    Defines how a need's baseline (decay rate and max intensity) varies
    with age using a two-stage calculation:

    Stage 1: Age -> Expected value using asymmetric distribution
    Stage 2: Individual variance applied around expected value
    """

    need_name: str  # Which need this applies to (hunger, intimacy, etc.)
    distribution: AsymmetricDistribution  # Age-based distribution parameters
    individual_variance_std: float = 15.0  # Standard deviation for Stage 2
    affects_decay: bool = True  # Whether age affects decay rate
    affects_max_intensity: bool = True  # Whether age caps max intensity


@dataclass
class TraitEffect:
    """Effect of a trait on a specific need.

    Defines how a character trait (e.g., greedy_eater) modifies
    the decay rate or satisfaction for a specific need.
    """

    decay_rate_multiplier: float = 1.0  # Multiplier for decay rate
    satisfaction_multiplier: float = 1.0  # Multiplier for satisfaction
    creates_need: str | None = None  # Optional: creates a new need (e.g., alcohol_craving)


@dataclass
class NeedModifierSettings:
    """Settings for need modifiers including age curves and trait effects."""

    age_curves: list[NeedAgeCurve] = field(default_factory=list)
    trait_effects: dict[str, dict[str, TraitEffect]] = field(default_factory=dict)
    recalculate_on_aging: bool = False  # Whether to recalculate when character ages


@dataclass
class SettingSchema:
    """Complete schema for a game setting."""

    name: str
    description: str = ""
    species: list[SpeciesDefinition] = field(
        default_factory=lambda: [SpeciesDefinition("Human")]
    )
    attributes: list[AttributeDefinition] = field(default_factory=list)
    point_buy_total: int = 27
    point_buy_min: int = 8
    point_buy_max: int = 15
    equipment_slots: list[EquipmentSlot] = field(default_factory=list)
    starting_equipment: list[StartingItem] = field(default_factory=list)
    need_modifiers: NeedModifierSettings = field(default_factory=NeedModifierSettings)


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


def _parse_species(species_data: list) -> list[SpeciesDefinition]:
    """Parse species data supporting both legacy and new formats.

    Args:
        species_data: Either a list of strings (legacy) or list of dicts (new).

    Returns:
        List of SpeciesDefinition instances.
    """
    if not species_data:
        return [SpeciesDefinition("Human")]

    species_list = []
    for item in species_data:
        if isinstance(item, str):
            # Legacy format: just a species name, use default genders
            species_list.append(SpeciesDefinition(name=item))
        elif isinstance(item, dict):
            # New format: object with name and genders
            species_list.append(
                SpeciesDefinition(
                    name=item["name"],
                    genders=item.get("genders", ["Male", "Female"]),
                )
            )

    return species_list if species_list else [SpeciesDefinition("Human")]


def _parse_setting_json(data: dict[str, Any]) -> SettingSchema:
    """Parse a setting JSON structure into a SettingSchema.

    Args:
        data: Parsed JSON data.

    Returns:
        SettingSchema instance.
    """
    # Parse species (supports both legacy string format and new object format)
    species = _parse_species(data.get("species", []))

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

    # Parse need modifiers (age curves and trait effects)
    need_modifiers = _parse_need_modifiers(data.get("need_modifiers", {}))

    return SettingSchema(
        name=data["name"],
        description=data.get("description", ""),
        species=species,
        attributes=attributes,
        point_buy_total=point_buy.get("total_points", 27),
        point_buy_min=point_buy.get("min_value", 8),
        point_buy_max=point_buy.get("max_value", 15),
        equipment_slots=equipment_slots,
        starting_equipment=starting_equipment,
        need_modifiers=need_modifiers,
    )


def _parse_need_modifiers(data: dict[str, Any]) -> NeedModifierSettings:
    """Parse need modifier settings from JSON.

    Args:
        data: The need_modifiers section of the settings JSON.

    Returns:
        NeedModifierSettings instance.
    """
    if not data:
        return NeedModifierSettings()

    # Parse age curves
    age_curves = []
    for curve_data in data.get("age_curves", []):
        dist_data = curve_data.get("distribution", {})
        distribution = AsymmetricDistribution(
            peak_age=dist_data.get("peak_age", 25),
            peak_value=dist_data.get("peak_value", 50.0),
            std_dev_lower=dist_data.get("std_dev_lower", 10.0),
            std_dev_upper=dist_data.get("std_dev_upper", 30.0),
            min_value=dist_data.get("min_value", 0.0),
            max_value=dist_data.get("max_value", 100.0),
        )
        age_curves.append(
            NeedAgeCurve(
                need_name=curve_data["need_name"],
                distribution=distribution,
                individual_variance_std=curve_data.get("individual_variance_std", 15.0),
                affects_decay=curve_data.get("affects_decay", True),
                affects_max_intensity=curve_data.get("affects_max_intensity", True),
            )
        )

    # Parse trait effects: trait_name -> {need_name -> TraitEffect}
    trait_effects: dict[str, dict[str, TraitEffect]] = {}
    for trait_name, needs in data.get("trait_effects", {}).items():
        trait_effects[trait_name] = {}
        for need_name, effect_data in needs.items():
            trait_effects[trait_name][need_name] = TraitEffect(
                decay_rate_multiplier=effect_data.get("decay_rate_multiplier", 1.0),
                satisfaction_multiplier=effect_data.get("satisfaction_multiplier", 1.0),
                creates_need=effect_data.get("creates_need"),
            )

    return NeedModifierSettings(
        age_curves=age_curves,
        trait_effects=trait_effects,
        recalculate_on_aging=data.get("recalculate_on_aging", False),
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


# =============================================================================
# Location-Based Activity Mapping
# =============================================================================

# Maps location categories (Location.category) to typical ActivityType values.
# Used by WorldSimulator to infer NPC activities based on where they are.
# The first activity in each list is the primary/default activity for that location.
LOCATION_ACTIVITY_MAPPING: dict[str, list[str]] = {
    # Social locations
    "tavern": ["socializing", "resting"],
    "inn": ["sleeping", "resting"],
    "restaurant": ["resting", "socializing"],
    "cafe": ["resting", "socializing"],
    "pub": ["socializing", "resting"],
    "club": ["socializing", "active"],
    # Commerce
    "market": ["active"],
    "shop": ["active"],
    "store": ["active"],
    "bazaar": ["active", "socializing"],
    # Religion/Contemplation
    "temple": ["resting", "socializing"],
    "church": ["resting"],
    "shrine": ["resting"],
    "monastery": ["resting", "sleeping"],
    # Military/Training
    "barracks": ["active", "combat"],
    "training_ground": ["combat", "active"],
    "arena": ["combat", "active"],
    "dojo": ["combat", "active"],
    "gym": ["active"],
    # Residence
    "home": ["sleeping", "resting"],
    "house": ["sleeping", "resting"],
    "bedroom": ["sleeping", "resting"],
    "living_room": ["resting", "socializing"],
    "kitchen": ["active"],
    # Workspace
    "workshop": ["active"],
    "forge": ["active"],
    "office": ["active"],
    "laboratory": ["active"],
    "library": ["resting", "active"],
    # Medical
    "hospital": ["resting"],
    "clinic": ["resting"],
    "infirmary": ["resting"],
    # Outdoors
    "wilderness": ["active"],
    "forest": ["active"],
    "mountain": ["active"],
    "road": ["active"],
    "path": ["active"],
    "park": ["resting", "socializing"],
    "garden": ["resting"],
    # Maritime
    "ship": ["active"],
    "dock": ["active"],
    "port": ["active", "socializing"],
    # Default categories
    "building": ["active"],
    "room": ["active"],
    "city": ["active", "socializing"],
    "town": ["active", "socializing"],
    "village": ["active", "socializing"],
}


def get_location_activities(category: str | None) -> list[str]:
    """Get typical activities for a location category.

    Args:
        category: Location category (e.g., 'tavern', 'inn', 'market').

    Returns:
        List of activity type names, with primary activity first.
        Returns ["active"] if category is unknown or None.
    """
    if not category:
        return ["active"]

    # Normalize category key (lowercase, strip whitespace)
    key = category.lower().strip()

    return LOCATION_ACTIVITY_MAPPING.get(key, ["active"])
