"""Dice system for RPG.

Provides dice rolling, skill checks, and combat mechanics.

Usage:
    >>> from src.dice import roll, make_skill_check, make_attack_roll
    >>> result = roll("2d6+3")
    >>> check = make_skill_check(dc=15, attribute_modifier=2, skill_modifier=3)
    >>> attack = make_attack_roll(target_ac=15, attack_bonus=7)
"""

# Types
from src.dice.types import (
    DiceExpression,
    RollResult,
    AdvantageType,
    SkillCheckResult,
    AttackRollResult,
    DamageRollResult,
)

# Parser
from src.dice.parser import parse_dice, DiceParseError

# Roller
from src.dice.roller import roll_dice, roll, roll_with_advantage

# Skill Checks
from src.dice.checks import (
    calculate_ability_modifier,
    make_skill_check,
    make_saving_throw,
    proficiency_to_modifier,
    get_proficiency_tier_name,
    assess_difficulty,
    get_difficulty_description,
    PROFICIENCY_TIERS,
    DC_TRIVIAL,
    DC_EASY,
    DC_MODERATE,
    DC_HARD,
    DC_VERY_HARD,
    DC_LEGENDARY,
)

# Combat
from src.dice.combat import (
    make_attack_roll,
    roll_damage,
    roll_initiative,
)

# Contested Rolls & Action Economy
from src.dice.contested import (
    ActionBudget,
    ActionType,
    ContestResult,
    contested_roll,
    escape_grapple_contest,
    grapple_contest,
    resolve_contest,
    shove_contest,
    social_contest,
    stealth_contest,
)

__all__ = [
    # Types
    "DiceExpression",
    "RollResult",
    "AdvantageType",
    "SkillCheckResult",
    "AttackRollResult",
    "DamageRollResult",
    # Parser
    "parse_dice",
    "DiceParseError",
    # Roller
    "roll_dice",
    "roll",
    "roll_with_advantage",
    # Checks
    "calculate_ability_modifier",
    "make_skill_check",
    "make_saving_throw",
    "proficiency_to_modifier",
    "get_proficiency_tier_name",
    "assess_difficulty",
    "get_difficulty_description",
    "PROFICIENCY_TIERS",
    "DC_TRIVIAL",
    "DC_EASY",
    "DC_MODERATE",
    "DC_HARD",
    "DC_VERY_HARD",
    "DC_LEGENDARY",
    # Combat
    "make_attack_roll",
    "roll_damage",
    "roll_initiative",
    # Contested Rolls
    "ActionBudget",
    "ActionType",
    "ContestResult",
    "contested_roll",
    "resolve_contest",
    "grapple_contest",
    "escape_grapple_contest",
    "shove_contest",
    "stealth_contest",
    "social_contest",
]
