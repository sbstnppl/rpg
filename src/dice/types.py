"""Dice system type definitions.

Immutable dataclasses for dice expressions, roll results, and check outcomes.
"""

from dataclasses import dataclass, field
from enum import Enum


class AdvantageType(str, Enum):
    """Type of advantage for a roll."""

    NORMAL = "normal"
    ADVANTAGE = "advantage"
    DISADVANTAGE = "disadvantage"


@dataclass(frozen=True)
class DiceExpression:
    """A dice expression like 2d6+3.

    Attributes:
        num_dice: Number of dice to roll.
        die_size: Size of each die (e.g., 6 for d6, 20 for d20).
        modifier: Flat modifier to add to the total.
    """

    num_dice: int
    die_size: int
    modifier: int = 0


@dataclass(frozen=True)
class RollResult:
    """Result of rolling dice.

    Attributes:
        expression: The dice expression that was rolled.
        individual_rolls: Tuple of each die's result.
        modifier: The modifier applied.
        total: Sum of rolls plus modifier.
        discarded_rolls: Rolls discarded due to advantage/disadvantage.
    """

    expression: DiceExpression
    individual_rolls: tuple[int, ...]
    modifier: int
    total: int
    discarded_rolls: tuple[int, ...] = field(default_factory=tuple)

    @property
    def is_natural_twenty(self) -> bool:
        """Check if this was a natural 20 on a single d20."""
        return (
            self.expression.num_dice == 1
            and self.expression.die_size == 20
            and self.individual_rolls[0] == 20
        )

    @property
    def is_natural_one(self) -> bool:
        """Check if this was a natural 1 on a single d20."""
        return (
            self.expression.num_dice == 1
            and self.expression.die_size == 20
            and self.individual_rolls[0] == 1
        )


@dataclass(frozen=True)
class SkillCheckResult:
    """Result of a skill check or saving throw.

    Attributes:
        roll_result: The underlying dice roll.
        dc: Difficulty class that was checked against.
        success: Whether the check succeeded.
        margin: How much the roll exceeded or fell short of DC.
        is_critical_success: Natural 20 on the roll.
        is_critical_failure: Natural 1 on the roll.
        advantage_type: Whether advantage/disadvantage was used.
    """

    roll_result: RollResult
    dc: int
    success: bool
    margin: int
    is_critical_success: bool
    is_critical_failure: bool
    advantage_type: AdvantageType


@dataclass(frozen=True)
class AttackRollResult:
    """Result of an attack roll.

    Attributes:
        roll_result: The underlying dice roll.
        target_ac: Armor class that was targeted.
        hit: Whether the attack hit.
        is_critical_hit: Natural 20 (automatic hit, double damage).
        is_critical_miss: Natural 1 (automatic miss).
    """

    roll_result: RollResult
    target_ac: int
    hit: bool
    is_critical_hit: bool
    is_critical_miss: bool


@dataclass(frozen=True)
class DamageRollResult:
    """Result of a damage roll.

    Attributes:
        roll_result: The underlying dice roll.
        damage_type: Type of damage (slashing, piercing, fire, etc.).
        is_critical: Whether this was critical hit damage.
    """

    roll_result: RollResult
    damage_type: str
    is_critical: bool
