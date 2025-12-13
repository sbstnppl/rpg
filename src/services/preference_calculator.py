"""Preference calculation utilities for NPC generation.

This module provides probability-based preference generation functions
used by both npc_generator.py and emergent_npc_generator.py to ensure
consistent preference distributions across all NPC creation paths.

Probability Distributions:
- Sexual Orientation: ~92% hetero, ~5% homo, ~3% bi (varies by gender)
- Drive Level: 25% low, 50% moderate, 25% high (adults)
- Age Preference: Skew-normal distribution with age-dependent spread
"""

import math
import random
from dataclasses import dataclass, field


# =============================================================================
# Constants
# =============================================================================

PHYSICAL_ATTRACTION_TRAITS = [
    "lean build", "muscular build", "athletic build", "soft curves",
    "dark hair", "light hair", "red hair", "long hair", "short hair",
    "tall stature", "average height", "shorter stature",
    "sharp features", "soft features", "strong jaw", "delicate features",
    "bright eyes", "dark eyes", "expressive face", "mysterious look",
    "well-groomed", "rugged appearance", "elegant bearing", "warm smile",
]

PERSONALITY_ATTRACTION_TRAITS = [
    "confidence", "kindness", "wit", "humor", "intelligence", "strength",
    "gentleness", "passion", "ambition", "creativity", "mystery", "warmth",
    "stability", "adventurousness", "wisdom", "charm", "honesty", "loyalty",
    "protectiveness", "sensitivity", "assertiveness", "playfulness",
]

ALL_FOODS = [
    "honey cakes", "roasted chicken", "fresh bread", "apple pie",
    "stew", "grilled fish", "cheese", "berries", "meat pies",
    "porridge", "liver", "onions", "turnips", "bitter greens",
    "pickled vegetables", "boiled cabbage", "fish stew", "mutton",
]

ALL_DRINKS = [
    "ale", "wine", "mead", "cider", "water", "milk", "tea",
    "herbal tea", "fruit juice", "hot chocolate", "coffee",
]

FAVORITE_ACTIVITIES = [
    "reading", "music", "gardening", "cooking", "dancing",
    "hunting", "crafting", "storytelling", "exploring", "games",
]

DISLIKES_OPTIONS = [
    "arrogance", "cruelty", "loud crowds", "dishonesty", "rudeness",
    "laziness", "cowardice", "waste", "violence", "prejudice",
]

FEARS_OPTIONS = [
    "rejection", "being alone", "failure", "heights", "darkness",
    "crowds", "death", "poverty", "embarrassment", "losing loved ones",
]

ALLERGY_OPTIONS = ["nuts", "shellfish", "dairy", "eggs", "wheat"]


# =============================================================================
# Result Dataclass
# =============================================================================


@dataclass
class GeneratedPreferences:
    """Result of preference generation with all fields."""

    # Attraction
    attracted_to_genders: list[str] = field(default_factory=list)
    attracted_age_offset: int = 0
    attracted_to_physical: list[str] = field(default_factory=list)
    attracted_to_personality: list[str] = field(default_factory=list)

    # Social
    social_tendency: str = "ambivert"  # introvert, ambivert, extrovert
    preferred_group_size: int = 3
    is_social_butterfly: bool = False
    is_loner: bool = False

    # Food
    favorite_foods: list[str] = field(default_factory=list)
    disliked_foods: list[str] = field(default_factory=list)
    is_vegetarian: bool = False
    is_vegan: bool = False
    food_allergies: list[str] = field(default_factory=list)
    is_greedy_eater: bool = False
    is_picky_eater: bool = False

    # Drinks
    favorite_drinks: list[str] = field(default_factory=list)
    disliked_drinks: list[str] = field(default_factory=list)
    is_alcoholic: bool = False
    is_teetotaler: bool = False
    alcohol_tolerance: str = "moderate"  # none, low, moderate, high, very_high

    # Activities
    favorite_activities: list[str] = field(default_factory=list)
    dislikes: list[str] = field(default_factory=list)
    fears: list[str] = field(default_factory=list)

    # Intimacy
    drive_level: str = "moderate"
    drive_threshold: int = 50
    intimacy_style: str = "emotional"  # casual, emotional, monogamous, polyamorous
    has_regular_partner: bool = False
    is_actively_seeking: bool = False

    # Stamina/sleep
    has_high_stamina: bool = False
    has_low_stamina: bool = False
    is_insomniac: bool = False
    is_heavy_sleeper: bool = False


# =============================================================================
# Core Generation Functions
# =============================================================================


def generate_gender_attraction(npc_gender: str) -> list[str]:
    """Generate attracted-to genders with realistic probability distribution.

    Based on real-world statistics:
    - ~90-95% heterosexual
    - ~3-5% homosexual
    - ~2-4% bisexual

    Args:
        npc_gender: The NPC's gender.

    Returns:
        List of genders the NPC is attracted to.
    """
    roll = random.random()

    if npc_gender == "male":
        if roll < 0.92:
            return ["female"]           # Heterosexual (92%)
        elif roll < 0.97:
            return ["male"]             # Homosexual (5%)
        else:
            return ["male", "female"]   # Bisexual (3%)
    elif npc_gender == "female":
        if roll < 0.90:
            return ["male"]             # Heterosexual (90%)
        elif roll < 0.96:
            return ["female"]           # Homosexual (6%)
        else:
            return ["male", "female"]   # Bisexual (4%)
    else:
        # Non-binary or other: random distribution
        return random.choice([["male"], ["female"], ["male", "female"]])


def generate_age_offset(npc_age: int) -> int:
    """Generate fixed age preference offset at character creation.

    Uses a truncated skew-normal distribution where:
    - Most NPCs prefer similar ages (offset ~0)
    - Spread scales with age (older NPCs have wider preference spread)
    - Young adults slightly prefer older, older adults prefer younger
    - Bounds ensure adults prefer 16+, minors can prefer minors

    Args:
        npc_age: The NPC's age.

    Returns:
        Integer offset from NPC's age to their preferred partner age.
        Example: offset=5 means NPC prefers partners 5 years older.
    """
    # Spread scales with age: older NPCs have wider preference spread
    sigma = 5.0 * math.sqrt(npc_age / 40)

    # Age-dependent skew (young prefer older, old prefer younger)
    if npc_age < 25:
        skew = 0.5  # Slight preference for older
    elif npc_age < 40:
        skew = 0.0  # Symmetric
    elif npc_age < 55:
        skew = -0.3  # Slight preference for younger
    else:
        skew = -0.8  # Stronger preference for younger

    # Asymmetric bounds - minors can prefer minors, adults must prefer 16+
    max_partner_age = 85
    if npc_age < 18:
        # Minors: can prefer down to ~2 years younger, but not below 10
        min_offset = max(10 - npc_age, -2)
        max_offset = min(max_partner_age - npc_age, max(30, npc_age - 10))
    else:
        # Adults: must prefer 16+
        min_offset = 16 - npc_age  # 18yo: -2, 40yo: -24, 70yo: -54
        max_offset = min(max_partner_age - npc_age, max(30, npc_age - 10))

    # Sample from skew-normal with rejection sampling
    max_iterations = 1000
    for _ in range(max_iterations):
        u = random.gauss(0, 1)
        v = random.gauss(0, 1)
        delta = skew / math.sqrt(1 + skew**2)
        x = delta * abs(u) + math.sqrt(1 - delta**2) * v
        offset = x * sigma
        if min_offset <= offset <= max_offset:
            return int(round(offset))

    # Fallback: clamp to bounds (should rarely happen)
    return int(round(max(min_offset, min(max_offset, 0))))


def generate_preferences(gender: str, age: int) -> GeneratedPreferences:
    """Generate all NPC preferences using probability distributions.

    This is the main function that generates a complete set of preferences
    for an NPC using formulas and probability distributions rather than LLM.

    Args:
        gender: NPC's gender for attraction generation.
        age: NPC's age for age-based preferences.

    Returns:
        GeneratedPreferences with all fields populated.
    """
    # Gender and age attraction
    attracted_to_genders = generate_gender_attraction(gender)
    offset = generate_age_offset(age)

    # Physical attraction (2-4 traits)
    attracted_physical = random.sample(PHYSICAL_ATTRACTION_TRAITS, random.randint(2, 4))

    # Personality attraction (2-4 traits)
    attracted_personality = random.sample(PERSONALITY_ATTRACTION_TRAITS, random.randint(2, 4))

    # Favorites
    favorite_foods = random.sample(ALL_FOODS[:9], random.randint(1, 3))
    favorite_drinks = random.sample(ALL_DRINKS, random.randint(1, 2))

    # Disliked (exclude favorites)
    available_for_dislike = [f for f in ALL_FOODS if f not in favorite_foods]
    disliked_foods = random.sample(available_for_dislike, random.randint(1, 3))
    available_drinks_dislike = [d for d in ALL_DRINKS if d not in favorite_drinks]
    disliked_drinks = random.sample(available_drinks_dislike, random.randint(0, 2))

    favorite_activities = random.sample(FAVORITE_ACTIVITIES, random.randint(1, 3))

    # Dislikes (personality/behavior dislikes)
    dislikes = random.sample(DISLIKES_OPTIONS, random.randint(2, 4))

    # Fears (1-2)
    fears = random.sample(FEARS_OPTIONS, random.randint(1, 2))

    # Food preferences (booleans) - low probability for special diets
    is_vegetarian = random.random() < 0.08  # 8%
    is_vegan = random.random() < 0.02 if not is_vegetarian else False  # 2%
    is_greedy_eater = random.random() < 0.15  # 15%
    is_picky_eater = random.random() < 0.20 if not is_greedy_eater else False  # 20%

    # Food allergies (5% chance)
    food_allergies: list[str] = []
    if random.random() < 0.05:
        food_allergies = random.sample(ALLERGY_OPTIONS, random.randint(1, 2))

    # Alcohol preferences - correlated with age
    if age < 16:
        is_alcoholic = False
        is_teetotaler = random.random() < 0.80  # Most minors don't drink
    else:
        is_alcoholic = random.random() < 0.05  # 5%
        is_teetotaler = random.random() < 0.15 if not is_alcoholic else False  # 15%

    # Intimacy preferences
    drive_roll = random.random()
    if age < 10:
        # Children have no drive
        drive_level = "low"
        drive_threshold = 0
        is_actively_seeking = False
    elif age < 16:
        # Minors have lower/developing drive
        if drive_roll < 0.3 + 0.1 * (16 - age):
            drive_level = "low"
            drive_threshold = 60 + random.randint(0, 30)
        elif drive_roll < 0.77 + 0.03 * (16 - age):
            drive_level = "moderate"
            drive_threshold = 40 + random.randint(0, 30)
        else:
            drive_level = "high"
            drive_threshold = 20 + random.randint(0, 30)
        is_actively_seeking = random.random() < 0.30
    else:
        # Adults
        if drive_roll < 0.25:
            drive_level = "low"  # 25%
            drive_threshold = 60 + random.randint(0, 30)
        elif drive_roll < 0.75:
            drive_level = "moderate"  # 50%
            drive_threshold = 40 + random.randint(0, 30)
        else:
            drive_level = "high"  # 25%
            drive_threshold = 20 + random.randint(0, 30)
        is_actively_seeking = random.random() < 0.30

    # Partnership status (correlates with age)
    if age < 16:
        has_regular_partner = random.random() < 0.25 - 0.025 * (16 - age)  # Young crushes
    elif age < 30:
        has_regular_partner = random.random() < 0.35  # 35%
    elif age < 50:
        has_regular_partner = random.random() < 0.65  # 65%
    else:
        has_regular_partner = random.random() < 0.55  # 55%

    # Stamina/sleep preferences
    has_high_stamina = random.random() < 0.20  # 20%
    has_low_stamina = random.random() < 0.20 if not has_high_stamina else False  # 20%
    is_insomniac = random.random() < 0.10  # 10%
    is_heavy_sleeper = random.random() < 0.15 if not is_insomniac else False  # 15%

    # Social preferences
    social_roll = random.random()
    if social_roll < 0.25:
        social_tendency = "introvert"  # 25%
        preferred_group_size = random.randint(1, 3)
        is_loner = random.random() < 0.30  # 30% of introverts are loners
        is_social_butterfly = False
    elif social_roll < 0.75:
        social_tendency = "ambivert"  # 50%
        preferred_group_size = random.randint(2, 6)
        is_loner = False
        is_social_butterfly = False
    else:
        social_tendency = "extrovert"  # 25%
        preferred_group_size = random.randint(4, 12)
        is_loner = False
        is_social_butterfly = random.random() < 0.30  # 30% of extroverts are butterflies

    # Alcohol tolerance - correlates with age and whether they drink
    if is_teetotaler:
        alcohol_tolerance = "none"
    elif age < 18:
        alcohol_tolerance = random.choice(["none", "low"])
    elif is_alcoholic:
        alcohol_tolerance = random.choice(["high", "very_high"])
    else:
        tolerance_roll = random.random()
        if tolerance_roll < 0.20:
            alcohol_tolerance = "low"  # 20%
        elif tolerance_roll < 0.70:
            alcohol_tolerance = "moderate"  # 50%
        elif tolerance_roll < 0.90:
            alcohol_tolerance = "high"  # 20%
        else:
            alcohol_tolerance = "very_high"  # 10%

    # Intimacy style
    style_roll = random.random()
    if style_roll < 0.10:
        intimacy_style = "casual"  # 10%
    elif style_roll < 0.50:
        intimacy_style = "emotional"  # 40%
    elif style_roll < 0.90:
        intimacy_style = "monogamous"  # 40%
    else:
        intimacy_style = "polyamorous"  # 10%

    return GeneratedPreferences(
        attracted_to_genders=attracted_to_genders,
        attracted_age_offset=offset,
        attracted_to_physical=attracted_physical,
        attracted_to_personality=attracted_personality,
        social_tendency=social_tendency,
        preferred_group_size=preferred_group_size,
        is_social_butterfly=is_social_butterfly,
        is_loner=is_loner,
        favorite_foods=favorite_foods,
        disliked_foods=disliked_foods,
        is_vegetarian=is_vegetarian,
        is_vegan=is_vegan,
        food_allergies=food_allergies,
        is_greedy_eater=is_greedy_eater,
        is_picky_eater=is_picky_eater,
        favorite_drinks=favorite_drinks,
        disliked_drinks=disliked_drinks,
        is_alcoholic=is_alcoholic,
        is_teetotaler=is_teetotaler,
        alcohol_tolerance=alcohol_tolerance,
        favorite_activities=favorite_activities,
        dislikes=dislikes,
        fears=fears,
        drive_level=drive_level,
        drive_threshold=drive_threshold,
        intimacy_style=intimacy_style,
        has_regular_partner=has_regular_partner,
        is_actively_seeking=is_actively_seeking,
        has_high_stamina=has_high_stamina,
        has_low_stamina=has_low_stamina,
        is_insomniac=is_insomniac,
        is_heavy_sleeper=is_heavy_sleeper,
    )
