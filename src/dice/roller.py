"""Core dice rolling engine.

Provides functions to roll dice expressions with support for
advantage/disadvantage mechanics.

Supports two dice systems:
- d20: For attacks and initiative (flat distribution, swingy combat)
- 2d10: For skill checks and saving throws (bell curve, expert reliability)

See docs/game-mechanics.md for full mechanics documentation.
"""

import random

from src.dice.types import DiceExpression, RollResult, AdvantageType
from src.dice.parser import parse_dice


# Standard expression for 2d10 skill checks
SKILL_CHECK_EXPRESSION = DiceExpression(num_dice=2, die_size=10, modifier=0)


def roll_dice(expression: DiceExpression) -> RollResult:
    """Roll dice according to the expression.

    Args:
        expression: The dice expression to roll.

    Returns:
        RollResult with individual rolls and total.

    Examples:
        >>> expr = DiceExpression(num_dice=2, die_size=6, modifier=3)
        >>> result = roll_dice(expr)
        >>> len(result.individual_rolls)
        2
    """
    rolls = tuple(
        random.randint(1, expression.die_size) for _ in range(expression.num_dice)
    )
    total = sum(rolls) + expression.modifier

    return RollResult(
        expression=expression,
        individual_rolls=rolls,
        modifier=expression.modifier,
        total=total,
    )


def roll(notation: str) -> RollResult:
    """Parse dice notation and roll.

    Convenience function combining parse_dice and roll_dice.

    Args:
        notation: Dice notation string (e.g., "2d6+3").

    Returns:
        RollResult with individual rolls and total.

    Raises:
        DiceParseError: If notation is invalid.

    Examples:
        >>> result = roll("1d20+5")
        >>> result.expression.die_size
        20
    """
    expression = parse_dice(notation)
    return roll_dice(expression)


def roll_with_advantage(
    expression: DiceExpression,
    advantage_type: AdvantageType,
) -> RollResult:
    """Roll with advantage or disadvantage.

    For advantage: rolls twice, keeps higher.
    For disadvantage: rolls twice, keeps lower.
    For normal: rolls once.

    Only applies to single-die rolls (e.g., 1d20). For multiple dice,
    advantage_type is ignored and a normal roll is performed.

    Args:
        expression: The dice expression to roll.
        advantage_type: Whether to use advantage, disadvantage, or normal.

    Returns:
        RollResult with kept roll and discarded roll (if applicable).

    Examples:
        >>> expr = DiceExpression(num_dice=1, die_size=20)
        >>> result = roll_with_advantage(expr, AdvantageType.ADVANTAGE)
        >>> len(result.discarded_rolls) == 1  # One roll was discarded
        True
    """
    # Advantage only applies to single-die rolls
    if expression.num_dice != 1 or advantage_type == AdvantageType.NORMAL:
        return roll_dice(expression)

    # Roll twice
    roll1 = random.randint(1, expression.die_size)
    roll2 = random.randint(1, expression.die_size)

    # Keep higher or lower based on advantage type
    if advantage_type == AdvantageType.ADVANTAGE:
        kept = max(roll1, roll2)
        discarded = min(roll1, roll2)
    else:  # DISADVANTAGE
        kept = min(roll1, roll2)
        discarded = max(roll1, roll2)

    total = kept + expression.modifier

    return RollResult(
        expression=expression,
        individual_rolls=(kept,),
        modifier=expression.modifier,
        total=total,
        discarded_rolls=(discarded,),
    )


def roll_2d10(
    modifier: int = 0,
    advantage_type: AdvantageType = AdvantageType.NORMAL,
) -> RollResult:
    """Roll 2d10 for skill checks with optional advantage/disadvantage.

    Uses bell curve system for reliable expert performance:
    - Normal: Roll 2d10, keep both
    - Advantage: Roll 3d10, keep best 2
    - Disadvantage: Roll 3d10, keep worst 2

    Args:
        modifier: Total modifier to add (attribute + proficiency).
        advantage_type: Whether to use advantage, disadvantage, or normal.

    Returns:
        RollResult with 2d10 expression and kept/discarded dice.

    Examples:
        >>> result = roll_2d10(modifier=5)  # Normal roll
        >>> len(result.individual_rolls)
        2
        >>> result = roll_2d10(modifier=5, advantage_type=AdvantageType.ADVANTAGE)
        >>> len(result.discarded_rolls)
        1  # One die was discarded
    """
    expression = DiceExpression(num_dice=2, die_size=10, modifier=modifier)

    if advantage_type == AdvantageType.NORMAL:
        # Roll 2d10
        die1 = random.randint(1, 10)
        die2 = random.randint(1, 10)
        total = die1 + die2 + modifier

        return RollResult(
            expression=expression,
            individual_rolls=(die1, die2),
            modifier=modifier,
            total=total,
        )

    # Roll 3d10 for advantage/disadvantage
    dice = [random.randint(1, 10) for _ in range(3)]
    dice.sort()  # Sort ascending

    if advantage_type == AdvantageType.ADVANTAGE:
        # Keep best 2 (highest)
        kept = (dice[1], dice[2])
        discarded = (dice[0],)
    else:  # DISADVANTAGE
        # Keep worst 2 (lowest)
        kept = (dice[0], dice[1])
        discarded = (dice[2],)

    total = sum(kept) + modifier

    return RollResult(
        expression=expression,
        individual_rolls=kept,
        modifier=modifier,
        total=total,
        discarded_rolls=discarded,
    )
