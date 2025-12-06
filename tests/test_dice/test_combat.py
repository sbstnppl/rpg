"""Tests for combat dice mechanics."""

import pytest
from unittest.mock import patch

from src.dice.combat import (
    make_attack_roll,
    roll_damage,
    roll_initiative,
)
from src.dice.types import (
    AdvantageType,
    AttackRollResult,
    DamageRollResult,
    RollResult,
)


class TestMakeAttackRoll:
    """Tests for attack roll function."""

    def test_returns_attack_roll_result(self):
        """Test that make_attack_roll returns AttackRollResult."""
        result = make_attack_roll(target_ac=15)
        assert isinstance(result, AttackRollResult)

    def test_target_ac_stored(self):
        """Test that target AC is stored in result."""
        result = make_attack_roll(target_ac=18)
        assert result.target_ac == 18

    @patch("src.dice.combat.roll_with_advantage")
    def test_hit_when_total_meets_ac(self, mock_roll):
        """Test hit when roll + bonus >= AC."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(1, 20),
            individual_rolls=(10,),
            modifier=5,
            total=15,
        )
        result = make_attack_roll(target_ac=15, attack_bonus=5)
        assert result.hit is True

    @patch("src.dice.combat.roll_with_advantage")
    def test_miss_when_total_below_ac(self, mock_roll):
        """Test miss when roll + bonus < AC."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(1, 20),
            individual_rolls=(8,),
            modifier=3,
            total=11,
        )
        result = make_attack_roll(target_ac=15, attack_bonus=3)
        assert result.hit is False

    @patch("src.dice.combat.roll_with_advantage")
    def test_natural_20_is_critical_hit(self, mock_roll):
        """Test that natural 20 is always a critical hit."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(1, 20),
            individual_rolls=(20,),
            modifier=0,
            total=20,
        )
        result = make_attack_roll(target_ac=30)  # Would miss normally
        assert result.is_critical_hit is True
        assert result.hit is True  # Critical always hits

    @patch("src.dice.combat.roll_with_advantage")
    def test_natural_1_is_critical_miss(self, mock_roll):
        """Test that natural 1 is always a critical miss."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(1, 20),
            individual_rolls=(1,),
            modifier=15,
            total=16,
        )
        result = make_attack_roll(target_ac=10, attack_bonus=15)  # Would hit normally
        assert result.is_critical_miss is True
        assert result.hit is False  # Critical miss always misses

    @patch("src.dice.combat.roll_with_advantage")
    def test_attack_with_advantage(self, mock_roll):
        """Test attack roll with advantage."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(1, 20),
            individual_rolls=(18,),
            modifier=5,
            total=23,
            discarded_rolls=(7,),
        )
        result = make_attack_roll(
            target_ac=15, attack_bonus=5, advantage_type=AdvantageType.ADVANTAGE
        )
        assert result.hit is True
        mock_roll.assert_called_once()
        call_args = mock_roll.call_args
        assert call_args[0][1] == AdvantageType.ADVANTAGE

    @patch("src.dice.combat.roll_with_advantage")
    def test_attack_with_disadvantage(self, mock_roll):
        """Test attack roll with disadvantage."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(1, 20),
            individual_rolls=(5,),
            modifier=3,
            total=8,
            discarded_rolls=(15,),
        )
        result = make_attack_roll(
            target_ac=15, attack_bonus=3, advantage_type=AdvantageType.DISADVANTAGE
        )
        assert result.hit is False


class TestRollDamage:
    """Tests for damage roll function."""

    def test_returns_damage_roll_result(self):
        """Test that roll_damage returns DamageRollResult."""
        result = roll_damage("1d8")
        assert isinstance(result, DamageRollResult)

    def test_damage_type_stored(self):
        """Test that damage type is stored."""
        result = roll_damage("1d8", damage_type="slashing")
        assert result.damage_type == "slashing"

    def test_default_damage_type(self):
        """Test default damage type is 'untyped'."""
        result = roll_damage("2d6")
        assert result.damage_type == "untyped"

    @patch("src.dice.combat.roll")
    def test_bonus_added_to_damage(self, mock_roll):
        """Test that bonus is added to damage total."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(1, 8, 3),
            individual_rolls=(5,),
            modifier=3,
            total=8,
        )
        result = roll_damage("1d8", bonus=3)
        # The bonus should be included in the roll call
        mock_roll.assert_called_with("1d8+3")

    @patch("src.dice.combat.roll")
    def test_negative_bonus(self, mock_roll):
        """Test negative damage bonus."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(2, 6, -2),
            individual_rolls=(4, 3),
            modifier=-2,
            total=5,
        )
        result = roll_damage("2d6", bonus=-2)
        mock_roll.assert_called_with("2d6-2")

    def test_is_critical_stored(self):
        """Test that is_critical flag is stored."""
        result = roll_damage("1d8", is_critical=True)
        assert result.is_critical is True

    @patch("src.dice.combat.roll")
    def test_critical_doubles_dice(self, mock_roll):
        """Test that critical hit doubles the dice."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(2, 8, 3),
            individual_rolls=(5, 6),
            modifier=3,
            total=14,
        )
        result = roll_damage("1d8", bonus=3, is_critical=True)
        # 1d8 doubled = 2d8
        mock_roll.assert_called_with("2d8+3")

    @patch("src.dice.combat.roll")
    def test_critical_doubles_multiple_dice(self, mock_roll):
        """Test that critical doubles multiple dice."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(4, 6, 5),
            individual_rolls=(3, 4, 5, 6),
            modifier=5,
            total=23,
        )
        result = roll_damage("2d6", bonus=5, is_critical=True)
        # 2d6 doubled = 4d6
        mock_roll.assert_called_with("4d6+5")

    @patch("src.dice.combat.roll")
    def test_critical_does_not_double_bonus(self, mock_roll):
        """Test that critical does not double the bonus."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(2, 6, 3),  # Bonus is still 3, not 6
            individual_rolls=(4, 5),
            modifier=3,
            total=12,
        )
        result = roll_damage("1d6", bonus=3, is_critical=True)
        # Dice doubled: 2d6, bonus unchanged: +3
        mock_roll.assert_called_with("2d6+3")


class TestRollInitiative:
    """Tests for initiative roll function."""

    def test_returns_roll_result(self):
        """Test that roll_initiative returns RollResult."""
        result = roll_initiative()
        assert isinstance(result, RollResult)

    def test_rolls_d20(self):
        """Test that initiative uses d20."""
        result = roll_initiative()
        assert result.expression.num_dice == 1
        assert result.expression.die_size == 20

    @patch("src.dice.combat.roll")
    def test_dexterity_modifier_applied(self, mock_roll):
        """Test that dexterity modifier is applied."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(1, 20, 3),
            individual_rolls=(12,),
            modifier=3,
            total=15,
        )
        result = roll_initiative(dexterity_modifier=3)
        mock_roll.assert_called_with("1d20+3")
        assert result.total == 15

    @patch("src.dice.combat.roll")
    def test_negative_dexterity_modifier(self, mock_roll):
        """Test negative dexterity modifier."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(1, 20, -2),
            individual_rolls=(10,),
            modifier=-2,
            total=8,
        )
        result = roll_initiative(dexterity_modifier=-2)
        mock_roll.assert_called_with("1d20-2")

    def test_default_no_modifier(self):
        """Test default with no modifier."""
        result = roll_initiative()
        assert result.expression.modifier == 0

    def test_initiative_in_valid_range(self):
        """Test that initiative values are reasonable."""
        for _ in range(20):
            result = roll_initiative(dexterity_modifier=5)
            # 1d20+5 should be between 6 and 25
            assert 6 <= result.total <= 25
