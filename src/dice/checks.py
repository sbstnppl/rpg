"""Skill checks and ability modifier calculations.

Uses 2d10 bell curve system for reliable expert performance.
See docs/game-mechanics.md for full mechanics documentation.

Key features:
- 2d10 instead of d20 for skill checks (4x less variance)
- Auto-success for routine tasks (DC <= 10 + modifier)
- Degree of success based on margin
- Critical success only on double-10 (1%), critical failure on double-1 (1%)
"""

from src.dice.types import (
    DiceExpression,
    RollResult,
    AdvantageType,
    SkillCheckResult,
    OutcomeTier,
)
from src.dice.roller import roll_with_advantage, roll_2d10


# Standard Difficulty Classes (DCs)
DC_TRIVIAL = 5  # Almost always succeeds
DC_EASY = 10  # 75% chance for trained characters
DC_MODERATE = 15  # 50% chance for trained
DC_HARD = 20  # 25% chance for trained
DC_VERY_HARD = 25  # Requires expertise
DC_LEGENDARY = 30  # Nearly impossible


# Proficiency tiers (for display)
PROFICIENCY_TIERS = {
    0: "Novice",
    1: "Apprentice",
    2: "Competent",
    3: "Expert",
    4: "Master",
    5: "Legendary",
}


def proficiency_to_modifier(proficiency_level: int) -> int:
    """Convert proficiency level (1-100) to a skill modifier.

    Uses tiered conversion: every 20 points of proficiency = +1 modifier.

    Args:
        proficiency_level: The proficiency level (1-100 scale).

    Returns:
        The skill modifier (+0 to +5).

    Examples:
        >>> proficiency_to_modifier(15)
        0
        >>> proficiency_to_modifier(45)
        2
        >>> proficiency_to_modifier(100)
        5
    """
    # Clamp to valid range
    level = max(0, min(100, proficiency_level))
    return level // 20


def get_proficiency_tier_name(proficiency_level: int) -> str:
    """Get the tier name for a proficiency level.

    Args:
        proficiency_level: The proficiency level (1-100 scale).

    Returns:
        Tier name (Novice, Apprentice, Competent, Expert, Master, Legendary).

    Examples:
        >>> get_proficiency_tier_name(15)
        'Novice'
        >>> get_proficiency_tier_name(45)
        'Competent'
    """
    modifier = proficiency_to_modifier(proficiency_level)
    return PROFICIENCY_TIERS.get(modifier, "Unknown")


def can_auto_succeed(dc: int, total_modifier: int) -> bool:
    """Check if a character can auto-succeed without rolling.

    Auto-success occurs when DC <= 10 + total_modifier.
    This represents tasks that are routine for a skilled character.

    Args:
        dc: The Difficulty Class of the task.
        total_modifier: Sum of attribute and skill modifiers.

    Returns:
        True if the character auto-succeeds without rolling.

    Examples:
        >>> can_auto_succeed(dc=15, total_modifier=8)  # 15 <= 18
        True
        >>> can_auto_succeed(dc=20, total_modifier=8)  # 20 > 18
        False
    """
    return dc <= 10 + total_modifier


def get_outcome_tier(margin: int, success: bool) -> OutcomeTier:
    """Get the outcome tier based on margin.

    Degree of success system provides nuanced narrative outcomes.
    See docs/game-mechanics.md for descriptions.

    Args:
        margin: Roll total minus DC (can be negative).
        success: Whether the check succeeded overall.

    Returns:
        OutcomeTier indicating degree of success or failure.

    Examples:
        >>> get_outcome_tier(margin=12, success=True)
        <OutcomeTier.EXCEPTIONAL: 'exceptional'>
        >>> get_outcome_tier(margin=-3, success=False)
        <OutcomeTier.PARTIAL_FAILURE: 'partial_failure'>
    """
    if margin >= 10:
        return OutcomeTier.EXCEPTIONAL
    elif margin >= 5:
        return OutcomeTier.CLEAR_SUCCESS
    elif margin >= 1:
        return OutcomeTier.NARROW_SUCCESS
    elif margin == 0:
        return OutcomeTier.BARE_SUCCESS
    elif margin >= -4:
        return OutcomeTier.PARTIAL_FAILURE
    elif margin >= -9:
        return OutcomeTier.CLEAR_FAILURE
    else:
        return OutcomeTier.CATASTROPHIC


def assess_difficulty(
    dc: int,
    skill_modifier: int = 0,
    attribute_modifier: int = 0,
) -> str:
    """Assess how difficult a check appears based on character's abilities.

    Calculates expected outcome and returns a qualitative assessment
    from the character's perspective. Uses 2d10 system.

    Args:
        dc: The Difficulty Class to assess against.
        skill_modifier: Modifier from skill proficiency.
        attribute_modifier: Modifier from relevant attribute.

    Returns:
        A qualitative difficulty assessment string.

    Examples:
        >>> assess_difficulty(dc=10, skill_modifier=3, attribute_modifier=2)
        'trivial'
        >>> assess_difficulty(dc=20, skill_modifier=0, attribute_modifier=0)
        'very hard'
    """
    total_modifier = skill_modifier + attribute_modifier

    # Check for auto-success first
    if can_auto_succeed(dc, total_modifier):
        return "trivial"

    # Average 2d10 roll is 11
    expected_total = 11 + total_modifier
    margin = expected_total - dc

    if margin >= 5:
        return "easy"
    elif margin >= 0:
        return "moderate"
    elif margin >= -5:
        return "challenging"
    elif margin >= -10:
        return "very hard"
    else:
        return "nearly impossible"


def get_difficulty_description(
    dc: int,
    skill_modifier: int = 0,
    attribute_modifier: int = 0,
) -> str:
    """Get a narrative description of difficulty from character's perspective.

    Args:
        dc: The Difficulty Class to assess against.
        skill_modifier: Modifier from skill proficiency.
        attribute_modifier: Modifier from relevant attribute.

    Returns:
        A narrative description suitable for player display.

    Examples:
        >>> get_difficulty_description(dc=10, skill_modifier=3, attribute_modifier=2)
        'This looks trivial for someone with your skill'
    """
    assessment = assess_difficulty(dc, skill_modifier, attribute_modifier)

    descriptions = {
        "trivial": "This looks trivial for someone with your skill",
        "easy": "You're confident this should be easy",
        "moderate": "You have a decent chance at this",
        "challenging": "This will be challenging",
        "very hard": "This looks very difficult",
        "nearly impossible": "This seems nearly impossible",
    }

    return descriptions.get(assessment, "You're uncertain about your chances")


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

    Uses 2d10 bell curve system for reliable expert performance:
    - Auto-success if DC <= 10 + total_modifier (no roll needed)
    - Roll 2d10 + modifiers (3d10 keep best/worst 2 with advantage/disadvantage)
    - Critical success on double-10 (1%), critical failure on double-1 (1%)
    - Degree of success based on margin

    See docs/game-mechanics.md for full mechanics documentation.

    Args:
        dc: Difficulty Class to beat.
        attribute_modifier: Modifier from relevant ability score.
        skill_modifier: Modifier from skill proficiency/expertise.
        advantage_type: Whether to roll with advantage/disadvantage.

    Returns:
        SkillCheckResult with roll details and success/failure.

    Examples:
        >>> result = make_skill_check(dc=15, attribute_modifier=2, skill_modifier=3)
        >>> result.success  # True if total >= 15 or auto-success
    """
    total_modifier = attribute_modifier + skill_modifier

    # Check for auto-success (routine tasks for skilled characters)
    if can_auto_succeed(dc, total_modifier):
        # Auto-success: calculate a "virtual" margin based on average roll + modifier
        # Average 2d10 is 11, so margin = 11 + modifier - dc
        virtual_total = 11 + total_modifier
        margin = virtual_total - dc

        return SkillCheckResult(
            roll_result=None,  # No roll needed
            dc=dc,
            success=True,
            margin=margin,
            is_critical_success=False,
            is_critical_failure=False,
            advantage_type=advantage_type,
            outcome_tier=get_outcome_tier(margin, success=True),
            is_auto_success=True,
        )

    # Roll 2d10 (or 3d10 keep 2 with advantage/disadvantage)
    roll_result = roll_2d10(modifier=total_modifier, advantage_type=advantage_type)

    # Check for critical success/failure (double-10 or double-1)
    is_critical_success = roll_result.is_double_ten
    is_critical_failure = roll_result.is_double_one

    # Determine success
    # Unlike d20 system, criticals don't auto-succeed/fail in 2d10
    # Double-10 still succeeds (high roll), double-1 still likely fails (low roll)
    # But the outcome depends on margin, not automatic
    success = roll_result.total >= dc

    margin = roll_result.total - dc
    outcome_tier = get_outcome_tier(margin, success)

    return SkillCheckResult(
        roll_result=roll_result,
        dc=dc,
        success=success,
        margin=margin,
        is_critical_success=is_critical_success,
        is_critical_failure=is_critical_failure,
        advantage_type=advantage_type,
        outcome_tier=outcome_tier,
        is_auto_success=False,
    )


def make_saving_throw(
    dc: int,
    save_modifier: int = 0,
    advantage_type: AdvantageType = AdvantageType.NORMAL,
) -> SkillCheckResult:
    """Make a saving throw against a DC.

    Uses 2d10 bell curve system (same as skill checks) for consistent realism.
    Saving throws typically resist spells, traps, or other effects.

    Note: Attack rolls still use d20 for combat volatility.

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
