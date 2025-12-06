"""Tests for dice roller."""

import pytest
from unittest.mock import patch

from src.dice.roller import roll_dice, roll, roll_with_advantage
from src.dice.types import DiceExpression, RollResult, AdvantageType


class TestRollDice:
    """Tests for roll_dice function."""

    def test_roll_returns_roll_result(self):
        """Test that roll_dice returns a RollResult."""
        expr = DiceExpression(num_dice=1, die_size=20)
        result = roll_dice(expr)
        assert isinstance(result, RollResult)

    def test_roll_has_correct_expression(self):
        """Test that result contains the original expression."""
        expr = DiceExpression(num_dice=2, die_size=6, modifier=3)
        result = roll_dice(expr)
        assert result.expression == expr

    def test_roll_has_correct_modifier(self):
        """Test that result contains the modifier."""
        expr = DiceExpression(num_dice=1, die_size=20, modifier=5)
        result = roll_dice(expr)
        assert result.modifier == 5

    def test_roll_individual_rolls_correct_count(self):
        """Test that we get the right number of individual rolls."""
        expr = DiceExpression(num_dice=4, die_size=6)
        result = roll_dice(expr)
        assert len(result.individual_rolls) == 4

    def test_roll_values_in_range(self):
        """Test that rolled values are within die range."""
        expr = DiceExpression(num_dice=10, die_size=6)
        result = roll_dice(expr)
        for value in result.individual_rolls:
            assert 1 <= value <= 6

    def test_roll_d20_values_in_range(self):
        """Test that d20 values are 1-20."""
        expr = DiceExpression(num_dice=1, die_size=20)
        # Roll multiple times to increase confidence
        for _ in range(20):
            result = roll_dice(expr)
            assert 1 <= result.individual_rolls[0] <= 20

    def test_roll_total_calculated_correctly(self):
        """Test that total = sum of rolls + modifier."""
        expr = DiceExpression(num_dice=2, die_size=6, modifier=3)
        result = roll_dice(expr)
        expected_total = sum(result.individual_rolls) + result.modifier
        assert result.total == expected_total

    def test_roll_negative_modifier_applied(self):
        """Test that negative modifier is applied correctly."""
        expr = DiceExpression(num_dice=2, die_size=6, modifier=-2)
        result = roll_dice(expr)
        expected_total = sum(result.individual_rolls) - 2
        assert result.total == expected_total

    @patch("src.dice.roller.random.randint")
    def test_roll_uses_random(self, mock_randint):
        """Test that roll uses random.randint."""
        mock_randint.return_value = 15
        expr = DiceExpression(num_dice=1, die_size=20)
        result = roll_dice(expr)
        mock_randint.assert_called_with(1, 20)
        assert result.individual_rolls == (15,)

    @patch("src.dice.roller.random.randint")
    def test_roll_multiple_dice_calls_random_multiple_times(self, mock_randint):
        """Test that multiple dice call random multiple times."""
        mock_randint.side_effect = [3, 4, 5, 6]
        expr = DiceExpression(num_dice=4, die_size=6)
        result = roll_dice(expr)
        assert mock_randint.call_count == 4
        assert result.individual_rolls == (3, 4, 5, 6)
        assert result.total == 18


class TestRollConvenience:
    """Tests for roll convenience function."""

    def test_roll_parses_and_rolls(self):
        """Test that roll parses notation and rolls."""
        result = roll("1d20")
        assert isinstance(result, RollResult)
        assert result.expression.num_dice == 1
        assert result.expression.die_size == 20

    def test_roll_with_modifier(self):
        """Test roll with modifier in notation."""
        result = roll("2d6+3")
        assert result.expression.modifier == 3
        assert result.modifier == 3

    @patch("src.dice.roller.random.randint")
    def test_roll_calculates_total(self, mock_randint):
        """Test that roll calculates total correctly."""
        mock_randint.side_effect = [4, 5]
        result = roll("2d6+3")
        assert result.total == 12  # 4 + 5 + 3


class TestRollWithAdvantage:
    """Tests for advantage/disadvantage rolling."""

    def test_normal_roll_single_die(self):
        """Test normal roll returns single die result."""
        expr = DiceExpression(num_dice=1, die_size=20)
        result = roll_with_advantage(expr, AdvantageType.NORMAL)
        assert len(result.individual_rolls) == 1
        assert len(result.discarded_rolls) == 0

    @patch("src.dice.roller.random.randint")
    def test_advantage_keeps_higher(self, mock_randint):
        """Test advantage keeps the higher of two rolls."""
        mock_randint.side_effect = [8, 15]
        expr = DiceExpression(num_dice=1, die_size=20)
        result = roll_with_advantage(expr, AdvantageType.ADVANTAGE)
        assert result.individual_rolls == (15,)
        assert result.discarded_rolls == (8,)
        assert result.total == 15

    @patch("src.dice.roller.random.randint")
    def test_disadvantage_keeps_lower(self, mock_randint):
        """Test disadvantage keeps the lower of two rolls."""
        mock_randint.side_effect = [18, 5]
        expr = DiceExpression(num_dice=1, die_size=20)
        result = roll_with_advantage(expr, AdvantageType.DISADVANTAGE)
        assert result.individual_rolls == (5,)
        assert result.discarded_rolls == (18,)
        assert result.total == 5

    @patch("src.dice.roller.random.randint")
    def test_advantage_with_modifier(self, mock_randint):
        """Test advantage applies modifier to kept roll."""
        mock_randint.side_effect = [10, 15]
        expr = DiceExpression(num_dice=1, die_size=20, modifier=5)
        result = roll_with_advantage(expr, AdvantageType.ADVANTAGE)
        assert result.individual_rolls == (15,)
        assert result.total == 20  # 15 + 5

    @patch("src.dice.roller.random.randint")
    def test_advantage_equal_rolls(self, mock_randint):
        """Test advantage when both rolls are equal."""
        mock_randint.side_effect = [12, 12]
        expr = DiceExpression(num_dice=1, die_size=20)
        result = roll_with_advantage(expr, AdvantageType.ADVANTAGE)
        assert result.individual_rolls == (12,)
        assert result.discarded_rolls == (12,)

    def test_advantage_only_for_single_d20(self):
        """Test that advantage only works for single die rolls."""
        expr = DiceExpression(num_dice=2, die_size=6)
        result = roll_with_advantage(expr, AdvantageType.ADVANTAGE)
        # For multiple dice, advantage is ignored
        assert len(result.individual_rolls) == 2
        assert len(result.discarded_rolls) == 0


class TestRollResultProperties:
    """Tests for roll result natural 20/1 detection."""

    @patch("src.dice.roller.random.randint")
    def test_natural_twenty_detected(self, mock_randint):
        """Test that natural 20 is detected."""
        mock_randint.return_value = 20
        result = roll("1d20")
        assert result.is_natural_twenty is True

    @patch("src.dice.roller.random.randint")
    def test_natural_one_detected(self, mock_randint):
        """Test that natural 1 is detected."""
        mock_randint.return_value = 1
        result = roll("1d20")
        assert result.is_natural_one is True

    @patch("src.dice.roller.random.randint")
    def test_non_natural_twenty(self, mock_randint):
        """Test that non-20 is not natural twenty."""
        mock_randint.return_value = 15
        result = roll("1d20+5")
        assert result.is_natural_twenty is False
