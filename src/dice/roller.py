"""Core dice rolling engine.

Provides functions to roll dice expressions with support for
advantage/disadvantage mechanics.
"""

import random

from src.dice.types import DiceExpression, RollResult, AdvantageType
from src.dice.parser import parse_dice


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
