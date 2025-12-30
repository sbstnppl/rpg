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


class RollType(str, Enum):
    """Type of roll being made.

    Determines which dice system to use:
    - SKILL_CHECK, SAVING_THROW: 2d10 (bell curve, expert reliability)
    - ATTACK, INITIATIVE: 1d20 (flat distribution, combat volatility)
    - DAMAGE: Various dice per weapon/spell
    """

    SKILL_CHECK = "skill_check"
    SAVING_THROW = "saving_throw"
    ATTACK = "attack"
    INITIATIVE = "initiative"
    DAMAGE = "damage"


class OutcomeTier(str, Enum):
    """Degree of success/failure based on margin.

    Used for skill checks to provide nuanced narrative outcomes.
    See docs/game-mechanics.md for full description.
    """

    EXCEPTIONAL = "exceptional"  # margin >= 10
    CLEAR_SUCCESS = "clear_success"  # margin 5-9
    NARROW_SUCCESS = "narrow_success"  # margin 1-4
    BARE_SUCCESS = "bare_success"  # margin 0
    PARTIAL_FAILURE = "partial_failure"  # margin -1 to -4
    CLEAR_FAILURE = "clear_failure"  # margin -5 to -9
    CATASTROPHIC = "catastrophic"  # margin <= -10


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

    @property
    def is_double_ten(self) -> bool:
        """Check if both dice show 10 on a 2d10 roll (critical success).

        For 2d10 skill checks, both dice showing 10 (1% chance) is a critical.
        """
        return (
            self.expression.num_dice == 2
            and self.expression.die_size == 10
            and len(self.individual_rolls) == 2
            and self.individual_rolls[0] == 10
            and self.individual_rolls[1] == 10
        )

    @property
    def is_double_one(self) -> bool:
        """Check if both dice show 1 on a 2d10 roll (critical failure).

        For 2d10 skill checks, both dice showing 1 (1% chance) is a critical.
        """
        return (
            self.expression.num_dice == 2
            and self.expression.die_size == 10
            and len(self.individual_rolls) == 2
            and self.individual_rolls[0] == 1
            and self.individual_rolls[1] == 1
        )


@dataclass(frozen=True)
class SkillCheckResult:
    """Result of a skill check or saving throw.

    Uses 2d10 bell curve system for reliable expert performance.
    See docs/game-mechanics.md for full mechanics description.

    Attributes:
        roll_result: The underlying dice roll (None if auto-success).
        dc: Difficulty class that was checked against.
        success: Whether the check succeeded.
        margin: How much the roll exceeded or fell short of DC.
        is_critical_success: Both dice = 10 (1% chance) OR auto-success cannot fail.
        is_critical_failure: Both dice = 1 (1% chance).
        advantage_type: Whether advantage/disadvantage was used.
        outcome_tier: Degree of success/failure based on margin.
        is_auto_success: True if DC <= 10 + modifier (no roll needed).
        skill_name: Name of the skill being checked (e.g., "Persuasion").
        skill_modifier: Player's modifier from skill proficiency.
        attribute_key: The attribute used (e.g., "charisma").
        attribute_modifier: Player's modifier from attribute.
    """

    roll_result: RollResult | None  # None if auto-success
    dc: int
    success: bool
    margin: int
    is_critical_success: bool
    is_critical_failure: bool
    advantage_type: AdvantageType
    outcome_tier: OutcomeTier = OutcomeTier.BARE_SUCCESS
    is_auto_success: bool = False
    # Skill metadata (for display)
    skill_name: str = ""
    skill_modifier: int = 0
    attribute_key: str = ""
    attribute_modifier: int = 0

    @property
    def total_modifier(self) -> int:
        """Total modifier (skill + attribute)."""
        return self.skill_modifier + self.attribute_modifier


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
