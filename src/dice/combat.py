"""Combat dice mechanics.

Provides attack rolls, damage rolls, and initiative rolls for combat resolution.
"""

from src.dice.types import (
    DiceExpression,
    AdvantageType,
    AttackRollResult,
    DamageRollResult,
    RollResult,
)
from src.dice.roller import roll, roll_with_advantage
from src.dice.parser import parse_dice


def make_attack_roll(
    target_ac: int,
    attack_bonus: int = 0,
    advantage_type: AdvantageType = AdvantageType.NORMAL,
) -> AttackRollResult:
    """Make an attack roll against a target's Armor Class.

    Rolls 1d20 + attack_bonus and compares to target AC.
    Natural 20 is always a critical hit, natural 1 is always a miss.

    Args:
        target_ac: Target's Armor Class.
        attack_bonus: Total attack bonus (ability + proficiency + other).
        advantage_type: Whether to roll with advantage/disadvantage.

    Returns:
        AttackRollResult with hit/miss and critical status.

    Examples:
        >>> result = make_attack_roll(target_ac=15, attack_bonus=7)
        >>> result.hit  # True if roll + 7 >= 15
    """
    expression = DiceExpression(num_dice=1, die_size=20, modifier=attack_bonus)
    roll_result = roll_with_advantage(expression, advantage_type)

    # Check for critical hit/miss
    is_critical_hit = roll_result.is_natural_twenty
    is_critical_miss = roll_result.is_natural_one

    # Determine if attack hits
    # Critical hit always hits, critical miss always misses
    if is_critical_hit:
        hit = True
    elif is_critical_miss:
        hit = False
    else:
        hit = roll_result.total >= target_ac

    return AttackRollResult(
        roll_result=roll_result,
        target_ac=target_ac,
        hit=hit,
        is_critical_hit=is_critical_hit,
        is_critical_miss=is_critical_miss,
    )


def roll_damage(
    damage_dice: str,
    damage_type: str = "untyped",
    bonus: int = 0,
    is_critical: bool = False,
) -> DamageRollResult:
    """Roll damage for an attack.

    On critical hit, the dice are doubled (not the bonus).

    Args:
        damage_dice: Base damage dice notation (e.g., "1d8", "2d6").
        damage_type: Type of damage (slashing, fire, etc.).
        bonus: Flat damage bonus (typically ability modifier).
        is_critical: If True, doubles the dice.

    Returns:
        DamageRollResult with total damage and breakdown.

    Examples:
        >>> result = roll_damage("1d8", damage_type="slashing", bonus=3)
        >>> result.roll_result.total  # Between 4 and 11
        >>> result = roll_damage("2d6", bonus=3, is_critical=True)
        >>> # Rolls 4d6+3 (dice doubled, bonus unchanged)
    """
    # Parse the base dice expression
    base_expr = parse_dice(damage_dice)

    # Double dice on critical, but keep same modifier (don't double)
    if is_critical:
        num_dice = base_expr.num_dice * 2
    else:
        num_dice = base_expr.num_dice

    # Build the notation string with bonus
    if bonus > 0:
        notation = f"{num_dice}d{base_expr.die_size}+{bonus}"
    elif bonus < 0:
        notation = f"{num_dice}d{base_expr.die_size}{bonus}"  # bonus already negative
    else:
        notation = f"{num_dice}d{base_expr.die_size}"

    roll_result = roll(notation)

    return DamageRollResult(
        roll_result=roll_result,
        damage_type=damage_type,
        is_critical=is_critical,
    )


def roll_initiative(dexterity_modifier: int = 0) -> RollResult:
    """Roll initiative for combat order.

    Rolls 1d20 + dexterity modifier. Higher results go first.

    Args:
        dexterity_modifier: DEX modifier to add to roll.

    Returns:
        RollResult with initiative value.

    Examples:
        >>> result = roll_initiative(dexterity_modifier=3)
        >>> result.total  # Between 4 and 23
    """
    if dexterity_modifier >= 0:
        notation = f"1d20+{dexterity_modifier}"
    else:
        notation = f"1d20{dexterity_modifier}"  # Already negative

    return roll(notation)
