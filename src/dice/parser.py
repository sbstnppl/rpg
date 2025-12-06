"""Dice notation parser.

Parses standard dice notation like 1d20, 2d6+3, d100, 4d6-2.
"""

import re

from src.dice.types import DiceExpression


class DiceParseError(ValueError):
    """Error parsing dice notation."""

    pass


# Pattern: optional count, 'd', die size, optional modifier
# Examples: 1d20, 2d6+3, d100, 4d6-2, 1d20 + 5
DICE_PATTERN = re.compile(
    r"^\s*(\d*)d(\d+)\s*([+-]\s*\d+)?\s*$",
    re.IGNORECASE,
)


def parse_dice(notation: str) -> DiceExpression:
    """Parse dice notation into a DiceExpression.

    Args:
        notation: Dice notation string (e.g., "2d6+3", "1d20", "d100").

    Returns:
        DiceExpression with parsed values.

    Raises:
        DiceParseError: If notation is invalid.

    Examples:
        >>> parse_dice("1d20")
        DiceExpression(num_dice=1, die_size=20, modifier=0)
        >>> parse_dice("2d6+3")
        DiceExpression(num_dice=2, die_size=6, modifier=3)
        >>> parse_dice("d100")
        DiceExpression(num_dice=1, die_size=100, modifier=0)
    """
    if not notation or not notation.strip():
        raise DiceParseError("Dice notation cannot be empty")

    match = DICE_PATTERN.match(notation)
    if not match:
        raise DiceParseError(f"Invalid dice notation: '{notation}'")

    num_dice_str, die_size_str, modifier_str = match.groups()

    # Default to 1 die if not specified (e.g., "d20" means "1d20")
    num_dice = int(num_dice_str) if num_dice_str else 1

    # Parse die size
    die_size = int(die_size_str)

    # Parse modifier (remove spaces)
    modifier = 0
    if modifier_str:
        modifier = int(modifier_str.replace(" ", ""))

    # Validate
    if num_dice < 1:
        raise DiceParseError(f"Number of dice must be at least 1, got {num_dice}")
    if die_size < 1:
        raise DiceParseError(f"Die size must be at least 1, got {die_size}")

    return DiceExpression(num_dice=num_dice, die_size=die_size, modifier=modifier)
