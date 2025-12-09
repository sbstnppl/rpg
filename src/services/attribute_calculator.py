"""Attribute calculation service for the two-tier potential/current stat system.

This module handles:
- Rolling potential stats (4d6 drop lowest)
- Calculating current stats from potential + modifiers
- Age-based modifiers
- Occupation-based modifiers
- Lifestyle modifiers
"""

import random
from dataclasses import dataclass
from typing import Literal

# Standard D&D-style attributes
ATTRIBUTE_NAMES = [
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
]

# Age brackets and their modifiers
# Format: (min_age, max_age, {stat: modifier})
AGE_BRACKETS: list[tuple[int, int, dict[str, int]]] = [
    (0, 5, {"strength": -5, "dexterity": -3, "constitution": -4, "intelligence": -3, "wisdom": -4, "charisma": -1}),
    (6, 11, {"strength": -4, "dexterity": -2, "constitution": -3, "intelligence": -2, "wisdom": -3, "charisma": 0}),
    (12, 15, {"strength": -2, "dexterity": -1, "constitution": -1, "intelligence": -1, "wisdom": -1, "charisma": 0}),
    (16, 25, {"strength": 0, "dexterity": 0, "constitution": 0, "intelligence": 0, "wisdom": 0, "charisma": 0}),
    (26, 40, {"strength": 0, "dexterity": 0, "constitution": 0, "intelligence": 0, "wisdom": 1, "charisma": 0}),
    (41, 60, {"strength": -1, "dexterity": -1, "constitution": -1, "intelligence": 0, "wisdom": 2, "charisma": 0}),
    (61, 80, {"strength": -2, "dexterity": -2, "constitution": -2, "intelligence": 0, "wisdom": 3, "charisma": 0}),
    (81, 200, {"strength": -3, "dexterity": -3, "constitution": -3, "intelligence": -1, "wisdom": 3, "charisma": -1}),
]

# Occupation modifiers (per year of experience, capped at max_years)
# Format: occupation_key -> {stat: modifier_per_year, ..., "max_years": cap}
OCCUPATION_MODIFIERS: dict[str, dict[str, int | float]] = {
    # Physical labor
    "blacksmith": {"strength": 0.6, "dexterity": 0.2, "constitution": 0.4, "max_years": 5},
    "farmer": {"strength": 0.4, "dexterity": 0.2, "constitution": 0.4, "wisdom": 0.2, "max_years": 5},
    "miner": {"strength": 0.5, "constitution": 0.5, "max_years": 5},
    "laborer": {"strength": 0.4, "constitution": 0.3, "max_years": 5},
    "carpenter": {"strength": 0.3, "dexterity": 0.3, "constitution": 0.2, "max_years": 5},
    "mason": {"strength": 0.4, "constitution": 0.3, "max_years": 5},
    "fisherman": {"strength": 0.2, "dexterity": 0.3, "constitution": 0.3, "wisdom": 0.2, "max_years": 5},

    # Combat/military
    "soldier": {"strength": 0.4, "dexterity": 0.4, "constitution": 0.4, "wisdom": 0.2, "max_years": 5},
    "guard": {"strength": 0.3, "dexterity": 0.2, "constitution": 0.3, "wisdom": 0.2, "max_years": 5},
    "mercenary": {"strength": 0.4, "dexterity": 0.4, "constitution": 0.3, "max_years": 5},
    "knight": {"strength": 0.4, "dexterity": 0.3, "constitution": 0.3, "charisma": 0.2, "max_years": 5},
    "hunter": {"dexterity": 0.4, "constitution": 0.2, "wisdom": 0.3, "max_years": 5},
    "archer": {"dexterity": 0.5, "constitution": 0.2, "wisdom": 0.2, "max_years": 5},

    # Intellectual/skilled
    "scholar": {"strength": -0.2, "intelligence": 0.6, "wisdom": 0.4, "max_years": 5},
    "scribe": {"intelligence": 0.4, "wisdom": 0.2, "max_years": 5},
    "alchemist": {"intelligence": 0.5, "wisdom": 0.3, "dexterity": 0.2, "max_years": 5},
    "healer": {"intelligence": 0.3, "wisdom": 0.5, "max_years": 5},
    "priest": {"wisdom": 0.5, "charisma": 0.3, "max_years": 5},
    "wizard": {"intelligence": 0.6, "wisdom": 0.3, "constitution": -0.2, "max_years": 5},
    "teacher": {"intelligence": 0.4, "wisdom": 0.4, "charisma": 0.2, "max_years": 5},

    # Social/trade
    "merchant": {"intelligence": 0.2, "wisdom": 0.2, "charisma": 0.4, "max_years": 5},
    "noble": {"strength": -0.2, "intelligence": 0.2, "charisma": 0.4, "max_years": 5},
    "politician": {"intelligence": 0.3, "wisdom": 0.2, "charisma": 0.5, "max_years": 5},
    "diplomat": {"intelligence": 0.2, "wisdom": 0.3, "charisma": 0.5, "max_years": 5},
    "bard": {"dexterity": 0.2, "charisma": 0.5, "intelligence": 0.2, "max_years": 5},
    "entertainer": {"dexterity": 0.3, "charisma": 0.4, "max_years": 5},
    "innkeeper": {"constitution": 0.2, "wisdom": 0.2, "charisma": 0.3, "max_years": 5},

    # Criminal/stealth
    "thief": {"dexterity": 0.6, "intelligence": 0.2, "wisdom": 0.2, "max_years": 5},
    "assassin": {"dexterity": 0.5, "intelligence": 0.2, "constitution": 0.2, "max_years": 5},
    "spy": {"dexterity": 0.3, "intelligence": 0.4, "charisma": 0.3, "max_years": 5},
    "smuggler": {"dexterity": 0.3, "intelligence": 0.2, "charisma": 0.3, "wisdom": 0.2, "max_years": 5},

    # Service/domestic
    "servant": {"dexterity": 0.2, "wisdom": 0.2, "max_years": 5},
    "cook": {"dexterity": 0.2, "constitution": 0.2, "wisdom": 0.2, "max_years": 5},
    "stablehand": {"strength": 0.2, "dexterity": 0.2, "wisdom": 0.2, "max_years": 5},

    # Crafts
    "tailor": {"dexterity": 0.4, "intelligence": 0.2, "max_years": 5},
    "jeweler": {"dexterity": 0.5, "intelligence": 0.3, "max_years": 5},
    "potter": {"dexterity": 0.3, "constitution": 0.2, "max_years": 5},
    "brewer": {"constitution": 0.3, "intelligence": 0.2, "max_years": 5},

    # Special/default
    "commoner": {"max_years": 0},  # No modifiers
    "child": {"max_years": 0},  # No occupational experience
    "student": {"intelligence": 0.3, "max_years": 3},
}

# Lifestyle modifiers (applied once, not per year)
LIFESTYLE_MODIFIERS: dict[str, dict[str, int]] = {
    "malnourished": {"strength": -1, "constitution": -2},
    "sedentary": {"strength": -1, "constitution": -1},
    "well_fed": {"constitution": 1},
    "pampered": {"strength": -1, "constitution": 0, "charisma": 1},
    "hardship": {"strength": 1, "constitution": 1, "wisdom": 1},
    "secret_training_physical": {"strength": 1, "dexterity": 1},
    "secret_training_mental": {"intelligence": 1, "wisdom": 1},
    "natural_leader": {"charisma": 2},
    "bookworm": {"intelligence": 1, "strength": -1},
    "street_smart": {"dexterity": 1, "wisdom": 1, "charisma": 1},
    "sheltered": {"wisdom": -1, "charisma": 1},
    "privileged_education": {"intelligence": 1, "charisma": 1},
}


@dataclass
class PotentialStats:
    """Container for rolled potential stats."""

    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary."""
        return {
            "strength": self.strength,
            "dexterity": self.dexterity,
            "constitution": self.constitution,
            "intelligence": self.intelligence,
            "wisdom": self.wisdom,
            "charisma": self.charisma,
        }


@dataclass
class CurrentStats:
    """Container for calculated current stats."""

    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int

    # Breakdown of how stats were calculated (for debugging/narrative)
    breakdown: dict[str, dict[str, int | float]] | None = None

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary."""
        return {
            "strength": self.strength,
            "dexterity": self.dexterity,
            "constitution": self.constitution,
            "intelligence": self.intelligence,
            "wisdom": self.wisdom,
            "charisma": self.charisma,
        }


def roll_4d6_drop_lowest() -> int:
    """Roll 4d6 and drop the lowest die.

    Returns:
        Sum of the three highest dice (range: 3-18).
    """
    rolls = [random.randint(1, 6) for _ in range(4)]
    rolls.sort(reverse=True)
    return sum(rolls[:3])


def roll_potential_stats() -> PotentialStats:
    """Roll potential stats using 4d6 drop lowest method.

    Returns:
        PotentialStats with all six attributes rolled.
    """
    return PotentialStats(
        strength=roll_4d6_drop_lowest(),
        dexterity=roll_4d6_drop_lowest(),
        constitution=roll_4d6_drop_lowest(),
        intelligence=roll_4d6_drop_lowest(),
        wisdom=roll_4d6_drop_lowest(),
        charisma=roll_4d6_drop_lowest(),
    )


def get_age_modifiers(age: int) -> dict[str, int]:
    """Get attribute modifiers based on age.

    Args:
        age: Character's age in years.

    Returns:
        Dict of attribute modifiers.
    """
    for min_age, max_age, modifiers in AGE_BRACKETS:
        if min_age <= age <= max_age:
            return modifiers.copy()

    # Default to elderly for ages beyond the table
    return AGE_BRACKETS[-1][2].copy()


def get_occupation_modifiers(
    occupation: str,
    years: int | None = None,
) -> dict[str, int]:
    """Get attribute modifiers based on occupation and years of experience.

    Args:
        occupation: Occupation name (lowercase, underscored).
        years: Years in the occupation (defaults to max_years if None).

    Returns:
        Dict of attribute modifiers (rounded to int).
    """
    # Normalize occupation name
    occupation_key = occupation.lower().replace(" ", "_").replace("-", "_")

    # Look up occupation or default to commoner
    occ_data = OCCUPATION_MODIFIERS.get(occupation_key, OCCUPATION_MODIFIERS["commoner"])

    max_years = occ_data.get("max_years", 5)
    if years is None:
        years = max_years
    years = min(years, max_years)

    modifiers = {}
    for stat in ATTRIBUTE_NAMES:
        modifier_per_year = occ_data.get(stat, 0)
        if isinstance(modifier_per_year, (int, float)):
            modifiers[stat] = int(round(modifier_per_year * years))

    return modifiers


def get_lifestyle_modifiers(lifestyles: list[str]) -> dict[str, int]:
    """Get attribute modifiers based on lifestyle tags.

    Args:
        lifestyles: List of lifestyle tag names.

    Returns:
        Dict of combined attribute modifiers.
    """
    combined = {stat: 0 for stat in ATTRIBUTE_NAMES}

    for lifestyle in lifestyles:
        lifestyle_key = lifestyle.lower().replace(" ", "_").replace("-", "_")
        if lifestyle_key in LIFESTYLE_MODIFIERS:
            for stat, mod in LIFESTYLE_MODIFIERS[lifestyle_key].items():
                combined[stat] += mod

    return combined


def calculate_current_stats(
    potential: PotentialStats | dict[str, int],
    age: int,
    occupation: str = "commoner",
    occupation_years: int | None = None,
    lifestyles: list[str] | None = None,
    min_stat: int = 3,
    max_stat: int = 18,
) -> CurrentStats:
    """Calculate current stats from potential and modifiers.

    Formula: Current = Potential + Age Modifier + Occupation Modifier + Lifestyle Modifiers
    Result is clamped to [min_stat, max_stat] range.

    Args:
        potential: PotentialStats or dict of potential stat values.
        age: Character's age in years.
        occupation: Primary occupation name.
        occupation_years: Years spent in occupation (defaults to appropriate max).
        lifestyles: List of lifestyle modifier tags.
        min_stat: Minimum allowed stat value (default: 3).
        max_stat: Maximum allowed stat value (default: 18).

    Returns:
        CurrentStats with calculated values and breakdown.
    """
    # Convert dict to PotentialStats if needed
    if isinstance(potential, dict):
        potential = PotentialStats(**potential)

    # Get all modifiers
    age_mods = get_age_modifiers(age)
    occ_mods = get_occupation_modifiers(occupation, occupation_years)
    life_mods = get_lifestyle_modifiers(lifestyles or [])

    # Calculate each stat with breakdown
    breakdown = {}
    current_values = {}

    for stat in ATTRIBUTE_NAMES:
        base = getattr(potential, stat)
        age_mod = age_mods.get(stat, 0)
        occ_mod = occ_mods.get(stat, 0)
        life_mod = life_mods.get(stat, 0)

        raw_total = base + age_mod + occ_mod + life_mod
        clamped = max(min_stat, min(max_stat, raw_total))

        breakdown[stat] = {
            "potential": base,
            "age_modifier": age_mod,
            "occupation_modifier": occ_mod,
            "lifestyle_modifier": life_mod,
            "raw_total": raw_total,
            "final": clamped,
        }
        current_values[stat] = clamped

    return CurrentStats(
        strength=current_values["strength"],
        dexterity=current_values["dexterity"],
        constitution=current_values["constitution"],
        intelligence=current_values["intelligence"],
        wisdom=current_values["wisdom"],
        charisma=current_values["charisma"],
        breakdown=breakdown,
    )


class AttributeCalculator:
    """High-level interface for attribute calculations.

    Provides methods for character creation workflow.
    """

    @staticmethod
    def roll_new_potential() -> PotentialStats:
        """Roll new potential stats for a character.

        Returns:
            PotentialStats with all six attributes.
        """
        return roll_potential_stats()

    @staticmethod
    def calculate_from_background(
        potential: PotentialStats | dict[str, int],
        age: int,
        occupation: str,
        occupation_years: int | None = None,
        lifestyles: list[str] | None = None,
    ) -> CurrentStats:
        """Calculate current stats based on character background.

        Args:
            potential: Rolled potential stats.
            age: Character's age.
            occupation: Primary occupation.
            occupation_years: Years in occupation.
            lifestyles: Lifestyle modifier tags.

        Returns:
            CurrentStats with full breakdown.
        """
        return calculate_current_stats(
            potential=potential,
            age=age,
            occupation=occupation,
            occupation_years=occupation_years,
            lifestyles=lifestyles,
        )

    @staticmethod
    def get_twist_narrative(
        current: CurrentStats,
        occupation: str,
    ) -> dict[str, str]:
        """Generate narrative explanations for any 'twist' stats.

        A twist occurs when the current stat differs significantly from
        what the occupation would suggest (e.g., weak blacksmith).

        Args:
            current: Calculated current stats.
            occupation: Character's occupation.

        Returns:
            Dict of stat_name -> narrative explanation for twists.
        """
        if current.breakdown is None:
            return {}

        twists = {}
        occ_mods = get_occupation_modifiers(occupation, years=5)  # Max years for comparison

        for stat in ATTRIBUTE_NAMES:
            expected_bonus = occ_mods.get(stat, 0)
            actual_final = current.breakdown[stat]["final"]
            potential = current.breakdown[stat]["potential"]

            # Check for significant twists
            if expected_bonus >= 2 and potential <= 8:
                # Expected to be good at this, but low potential
                twists[stat] = f"Despite the demands of {occupation} work, {stat} never came naturally."
            elif expected_bonus <= -1 and potential >= 14:
                # Expected to be weak here, but high potential
                twists[stat] = f"Surprisingly capable in {stat}, despite the {occupation} lifestyle."
            elif potential >= 16:
                # Exceptional natural talent
                twists[stat] = f"A natural gift for {stat} that stands out."
            elif potential <= 6:
                # Notable weakness
                twists[stat] = f"A noticeable weakness in {stat}."

        return twists

    @staticmethod
    def get_available_occupations() -> list[str]:
        """Get list of all available occupation types.

        Returns:
            List of occupation names (properly formatted).
        """
        return [
            occ.replace("_", " ").title()
            for occ in OCCUPATION_MODIFIERS.keys()
            if occ not in ("commoner", "child")
        ]

    @staticmethod
    def get_available_lifestyles() -> list[str]:
        """Get list of all available lifestyle modifiers.

        Returns:
            List of lifestyle names (properly formatted).
        """
        return [
            life.replace("_", " ").title()
            for life in LIFESTYLE_MODIFIERS.keys()
        ]
