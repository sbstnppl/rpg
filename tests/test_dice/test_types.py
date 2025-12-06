"""Tests for dice system types."""

import pytest
from dataclasses import FrozenInstanceError

from src.dice.types import (
    DiceExpression,
    RollResult,
    AdvantageType,
    SkillCheckResult,
    AttackRollResult,
    DamageRollResult,
)


class TestDiceExpression:
    """Tests for DiceExpression dataclass."""

    def test_create_basic_expression(self):
        """Test creating a basic dice expression."""
        expr = DiceExpression(num_dice=1, die_size=20)
        assert expr.num_dice == 1
        assert expr.die_size == 20
        assert expr.modifier == 0

    def test_create_expression_with_modifier(self):
        """Test creating expression with positive modifier."""
        expr = DiceExpression(num_dice=2, die_size=6, modifier=3)
        assert expr.num_dice == 2
        assert expr.die_size == 6
        assert expr.modifier == 3

    def test_create_expression_with_negative_modifier(self):
        """Test creating expression with negative modifier."""
        expr = DiceExpression(num_dice=4, die_size=6, modifier=-2)
        assert expr.modifier == -2

    def test_expression_is_immutable(self):
        """Test that DiceExpression is frozen."""
        expr = DiceExpression(num_dice=1, die_size=20)
        with pytest.raises(FrozenInstanceError):
            expr.num_dice = 2

    def test_expression_equality(self):
        """Test that equal expressions are equal."""
        expr1 = DiceExpression(num_dice=2, die_size=6, modifier=3)
        expr2 = DiceExpression(num_dice=2, die_size=6, modifier=3)
        assert expr1 == expr2

    def test_expression_str(self):
        """Test string representation of expression."""
        expr = DiceExpression(num_dice=2, die_size=6, modifier=3)
        assert str(expr.num_dice) == "2"
        assert str(expr.die_size) == "6"


class TestRollResult:
    """Tests for RollResult dataclass."""

    def test_create_roll_result(self):
        """Test creating a roll result."""
        expr = DiceExpression(num_dice=2, die_size=6, modifier=3)
        result = RollResult(
            expression=expr,
            individual_rolls=(4, 5),
            modifier=3,
            total=12,  # 4 + 5 + 3
        )
        assert result.expression == expr
        assert result.individual_rolls == (4, 5)
        assert result.modifier == 3
        assert result.total == 12

    def test_roll_result_with_discarded(self):
        """Test roll result with discarded rolls (advantage/disadvantage)."""
        expr = DiceExpression(num_dice=1, die_size=20)
        result = RollResult(
            expression=expr,
            individual_rolls=(15,),
            modifier=0,
            total=15,
            discarded_rolls=(8,),
        )
        assert result.discarded_rolls == (8,)

    def test_roll_result_is_immutable(self):
        """Test that RollResult is frozen."""
        expr = DiceExpression(num_dice=1, die_size=20)
        result = RollResult(
            expression=expr,
            individual_rolls=(15,),
            modifier=0,
            total=15,
        )
        with pytest.raises(FrozenInstanceError):
            result.total = 20

    def test_is_natural_twenty(self):
        """Test natural 20 detection on d20."""
        expr = DiceExpression(num_dice=1, die_size=20)
        result = RollResult(
            expression=expr,
            individual_rolls=(20,),
            modifier=5,
            total=25,
        )
        assert result.is_natural_twenty is True

    def test_is_not_natural_twenty(self):
        """Test non-natural 20 detection."""
        expr = DiceExpression(num_dice=1, die_size=20)
        result = RollResult(
            expression=expr,
            individual_rolls=(15,),
            modifier=5,
            total=20,  # Total is 20 but roll was 15
        )
        assert result.is_natural_twenty is False

    def test_is_natural_one(self):
        """Test natural 1 detection on d20."""
        expr = DiceExpression(num_dice=1, die_size=20)
        result = RollResult(
            expression=expr,
            individual_rolls=(1,),
            modifier=10,
            total=11,
        )
        assert result.is_natural_one is True

    def test_is_not_natural_one(self):
        """Test non-natural 1 detection."""
        expr = DiceExpression(num_dice=1, die_size=20)
        result = RollResult(
            expression=expr,
            individual_rolls=(10,),
            modifier=-9,
            total=1,  # Total is 1 but roll was 10
        )
        assert result.is_natural_one is False

    def test_natural_twenty_only_for_single_d20(self):
        """Test that natural 20 only applies to single d20 rolls."""
        expr = DiceExpression(num_dice=2, die_size=20)
        result = RollResult(
            expression=expr,
            individual_rolls=(20, 15),
            modifier=0,
            total=35,
        )
        # Multiple dice don't count as natural 20
        assert result.is_natural_twenty is False


class TestAdvantageType:
    """Tests for AdvantageType enum."""

    def test_advantage_values(self):
        """Test advantage type enum values."""
        assert AdvantageType.NORMAL.value == "normal"
        assert AdvantageType.ADVANTAGE.value == "advantage"
        assert AdvantageType.DISADVANTAGE.value == "disadvantage"


class TestSkillCheckResult:
    """Tests for SkillCheckResult dataclass."""

    def test_create_successful_check(self):
        """Test creating a successful skill check result."""
        expr = DiceExpression(num_dice=1, die_size=20)
        roll = RollResult(
            expression=expr,
            individual_rolls=(15,),
            modifier=5,
            total=20,
        )
        result = SkillCheckResult(
            roll_result=roll,
            dc=15,
            success=True,
            margin=5,
            is_critical_success=False,
            is_critical_failure=False,
            advantage_type=AdvantageType.NORMAL,
        )
        assert result.success is True
        assert result.margin == 5
        assert result.dc == 15

    def test_create_critical_success(self):
        """Test creating a critical success result."""
        expr = DiceExpression(num_dice=1, die_size=20)
        roll = RollResult(
            expression=expr,
            individual_rolls=(20,),
            modifier=0,
            total=20,
        )
        result = SkillCheckResult(
            roll_result=roll,
            dc=25,  # Would normally fail
            success=True,  # But natural 20 succeeds
            margin=-5,
            is_critical_success=True,
            is_critical_failure=False,
            advantage_type=AdvantageType.NORMAL,
        )
        assert result.is_critical_success is True
        assert result.success is True

    def test_skill_check_is_immutable(self):
        """Test that SkillCheckResult is frozen."""
        expr = DiceExpression(num_dice=1, die_size=20)
        roll = RollResult(
            expression=expr,
            individual_rolls=(15,),
            modifier=0,
            total=15,
        )
        result = SkillCheckResult(
            roll_result=roll,
            dc=10,
            success=True,
            margin=5,
            is_critical_success=False,
            is_critical_failure=False,
            advantage_type=AdvantageType.NORMAL,
        )
        with pytest.raises(FrozenInstanceError):
            result.success = False


class TestAttackRollResult:
    """Tests for AttackRollResult dataclass."""

    def test_create_hit_result(self):
        """Test creating an attack hit result."""
        expr = DiceExpression(num_dice=1, die_size=20)
        roll = RollResult(
            expression=expr,
            individual_rolls=(15,),
            modifier=5,
            total=20,
        )
        result = AttackRollResult(
            roll_result=roll,
            target_ac=15,
            hit=True,
            is_critical_hit=False,
            is_critical_miss=False,
        )
        assert result.hit is True
        assert result.target_ac == 15

    def test_create_critical_hit(self):
        """Test creating a critical hit result."""
        expr = DiceExpression(num_dice=1, die_size=20)
        roll = RollResult(
            expression=expr,
            individual_rolls=(20,),
            modifier=0,
            total=20,
        )
        result = AttackRollResult(
            roll_result=roll,
            target_ac=25,  # Would miss normally
            hit=True,  # But crit always hits
            is_critical_hit=True,
            is_critical_miss=False,
        )
        assert result.is_critical_hit is True
        assert result.hit is True

    def test_create_critical_miss(self):
        """Test creating a critical miss result."""
        expr = DiceExpression(num_dice=1, die_size=20)
        roll = RollResult(
            expression=expr,
            individual_rolls=(1,),
            modifier=20,
            total=21,
        )
        result = AttackRollResult(
            roll_result=roll,
            target_ac=10,  # Would hit normally
            hit=False,  # But natural 1 misses
            is_critical_hit=False,
            is_critical_miss=True,
        )
        assert result.is_critical_miss is True
        assert result.hit is False


class TestDamageRollResult:
    """Tests for DamageRollResult dataclass."""

    def test_create_damage_result(self):
        """Test creating a damage roll result."""
        expr = DiceExpression(num_dice=2, die_size=6, modifier=3)
        roll = RollResult(
            expression=expr,
            individual_rolls=(4, 5),
            modifier=3,
            total=12,
        )
        result = DamageRollResult(
            roll_result=roll,
            damage_type="slashing",
            is_critical=False,
        )
        assert result.damage_type == "slashing"
        assert result.is_critical is False
        assert result.roll_result.total == 12

    def test_create_critical_damage(self):
        """Test creating a critical damage result."""
        expr = DiceExpression(num_dice=4, die_size=6, modifier=3)  # Doubled dice
        roll = RollResult(
            expression=expr,
            individual_rolls=(4, 5, 3, 6),
            modifier=3,
            total=21,
        )
        result = DamageRollResult(
            roll_result=roll,
            damage_type="piercing",
            is_critical=True,
        )
        assert result.is_critical is True
