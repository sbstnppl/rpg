"""Skill checks and ability modifier calculations.

Provides D&D-style skill checks with critical success/failure handling.
"""

from src.dice.types import (
    DiceExpression,
    RollResult,
    AdvantageType,
    SkillCheckResult,
)
from src.dice.roller import roll_with_advantage


# Standard Difficulty Classes (DCs)
DC_TRIVIAL = 5  # Almost always succeeds
DC_EASY = 10  # 75% chance for trained characters
DC_MODERATE = 15  # 50% chance for trained
DC_HARD = 20  # 25% chance for trained
DC_VERY_HARD = 25  # Requires expertise
DC_LEGENDARY = 30  # Nearly impossible


def calculate_ability_modifier(ability_score: int) -> int:
    """Convert D&D ability score to modifier.

    Uses standard D&D formula: (score - 10) // 2

    Args:
        ability_score: The ability score (typically 1-20).

    Returns:
        The modifier (e.g., 10 -> 0, 14 -> +2, 8 -> -1).

    Examples:
        >>> calculate_ability_modifier(10)
        0
        >>> calculate_ability_modifier(14)
        2
        >>> calculate_ability_modifier(8)
        -1
    """
    return (ability_score - 10) // 2


def make_skill_check(
    dc: int,
    attribute_modifier: int = 0,
    skill_modifier: int = 0,
    advantage_type: AdvantageType = AdvantageType.NORMAL,
) -> SkillCheckResult:
    """Make a skill check against a Difficulty Class.

    Rolls 1d20 + attribute_modifier + skill_modifier and compares to DC.
    Natural 20 is always a critical success, natural 1 is always critical failure.

    Args:
        dc: Difficulty Class to beat.
        attribute_modifier: Modifier from relevant ability score.
        skill_modifier: Modifier from skill proficiency/expertise.
        advantage_type: Whether to roll with advantage/disadvantage.

    Returns:
        SkillCheckResult with roll details and success/failure.

    Examples:
        >>> result = make_skill_check(dc=15, attribute_modifier=2, skill_modifier=3)
        >>> result.success  # True if total >= 15
    """
    total_modifier = attribute_modifier + skill_modifier
    expression = DiceExpression(num_dice=1, die_size=20, modifier=total_modifier)

    roll_result = roll_with_advantage(expression, advantage_type)

    # Check for critical success/failure
    is_critical_success = roll_result.is_natural_twenty
    is_critical_failure = roll_result.is_natural_one

    # Determine success
    # Critical success always succeeds, critical failure always fails
    if is_critical_success:
        success = True
    elif is_critical_failure:
        success = False
    else:
        success = roll_result.total >= dc

    margin = roll_result.total - dc

    return SkillCheckResult(
        roll_result=roll_result,
        dc=dc,
        success=success,
        margin=margin,
        is_critical_success=is_critical_success,
        is_critical_failure=is_critical_failure,
        advantage_type=advantage_type,
    )


def make_saving_throw(
    dc: int,
    save_modifier: int = 0,
    advantage_type: AdvantageType = AdvantageType.NORMAL,
) -> SkillCheckResult:
    """Make a saving throw against a DC.

    Mechanically identical to a skill check but with different semantics.
    Saving throws typically resist spells, traps, or other effects.

    Args:
        dc: Difficulty Class to beat (typically spell DC or trap DC).
        save_modifier: Modifier from ability score and proficiency.
        advantage_type: Whether to roll with advantage/disadvantage.

    Returns:
        SkillCheckResult with roll details and success/failure.

    Examples:
        >>> result = make_saving_throw(dc=15, save_modifier=5)
        >>> result.success  # True if total >= 15
    """
    return make_skill_check(
        dc=dc,
        attribute_modifier=save_modifier,
        skill_modifier=0,
        advantage_type=advantage_type,
    )
