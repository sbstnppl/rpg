"""Tests for skill checks and ability modifiers."""

import pytest
from unittest.mock import patch

from src.dice.checks import (
    calculate_ability_modifier,
    make_skill_check,
    make_saving_throw,
    DC_TRIVIAL,
    DC_EASY,
    DC_MODERATE,
    DC_HARD,
    DC_VERY_HARD,
    DC_LEGENDARY,
)
from src.dice.types import AdvantageType, SkillCheckResult


class TestCalculateAbilityModifier:
    """Tests for ability score to modifier conversion."""

    def test_modifier_for_score_10(self):
        """Test that score 10 gives modifier 0."""
        assert calculate_ability_modifier(10) == 0

    def test_modifier_for_score_11(self):
        """Test that score 11 gives modifier 0."""
        assert calculate_ability_modifier(11) == 0

    def test_modifier_for_score_12(self):
        """Test that score 12 gives modifier +1."""
        assert calculate_ability_modifier(12) == 1

    def test_modifier_for_score_14(self):
        """Test that score 14 gives modifier +2."""
        assert calculate_ability_modifier(14) == 2

    def test_modifier_for_score_16(self):
        """Test that score 16 gives modifier +3."""
        assert calculate_ability_modifier(16) == 3

    def test_modifier_for_score_18(self):
        """Test that score 18 gives modifier +4."""
        assert calculate_ability_modifier(18) == 4

    def test_modifier_for_score_20(self):
        """Test that score 20 gives modifier +5."""
        assert calculate_ability_modifier(20) == 5

    def test_modifier_for_score_8(self):
        """Test that score 8 gives modifier -1."""
        assert calculate_ability_modifier(8) == -1

    def test_modifier_for_score_6(self):
        """Test that score 6 gives modifier -2."""
        assert calculate_ability_modifier(6) == -2

    def test_modifier_for_score_1(self):
        """Test that score 1 gives modifier -5."""
        assert calculate_ability_modifier(1) == -5

    def test_modifier_odd_scores(self):
        """Test modifiers for odd scores."""
        assert calculate_ability_modifier(9) == -1
        assert calculate_ability_modifier(13) == 1
        assert calculate_ability_modifier(15) == 2
        assert calculate_ability_modifier(17) == 3


class TestDifficultyClassConstants:
    """Tests for DC constants."""

    def test_dc_values(self):
        """Test that DC constants have expected values."""
        assert DC_TRIVIAL == 5
        assert DC_EASY == 10
        assert DC_MODERATE == 15
        assert DC_HARD == 20
        assert DC_VERY_HARD == 25
        assert DC_LEGENDARY == 30


class TestMakeSkillCheck:
    """Tests for skill check function."""

    def test_returns_skill_check_result(self):
        """Test that make_skill_check returns SkillCheckResult."""
        result = make_skill_check(dc=10)
        assert isinstance(result, SkillCheckResult)

    def test_dc_stored_in_result(self):
        """Test that DC is stored in result."""
        result = make_skill_check(dc=15)
        assert result.dc == 15

    @patch("src.dice.checks.roll_with_advantage")
    def test_success_when_total_meets_dc(self, mock_roll):
        """Test success when roll + modifiers >= DC."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(1, 20),
            individual_rolls=(10,),
            modifier=5,
            total=15,
        )
        result = make_skill_check(dc=15, attribute_modifier=3, skill_modifier=2)
        assert result.success is True

    @patch("src.dice.checks.roll_with_advantage")
    def test_failure_when_total_below_dc(self, mock_roll):
        """Test failure when roll + modifiers < DC."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(1, 20),
            individual_rolls=(5,),
            modifier=3,
            total=8,
        )
        result = make_skill_check(dc=15, attribute_modifier=2, skill_modifier=1)
        assert result.success is False

    @patch("src.dice.checks.roll_with_advantage")
    def test_margin_calculated_correctly(self, mock_roll):
        """Test that margin is total - DC."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(1, 20),
            individual_rolls=(15,),
            modifier=5,
            total=20,
        )
        result = make_skill_check(dc=15, attribute_modifier=3, skill_modifier=2)
        assert result.margin == 5  # 20 - 15

    @patch("src.dice.checks.roll_with_advantage")
    def test_negative_margin_on_failure(self, mock_roll):
        """Test that margin is negative on failure."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(1, 20),
            individual_rolls=(5,),
            modifier=2,
            total=7,
        )
        result = make_skill_check(dc=15, attribute_modifier=1, skill_modifier=1)
        assert result.margin == -8  # 7 - 15

    @patch("src.dice.checks.roll_with_advantage")
    def test_natural_20_is_critical_success(self, mock_roll):
        """Test that natural 20 is critical success."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(1, 20),
            individual_rolls=(20,),
            modifier=0,
            total=20,
        )
        result = make_skill_check(dc=25)  # Would fail normally
        assert result.is_critical_success is True
        assert result.success is True  # Critical always succeeds

    @patch("src.dice.checks.roll_with_advantage")
    def test_natural_1_is_critical_failure(self, mock_roll):
        """Test that natural 1 is critical failure."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(1, 20),
            individual_rolls=(1,),
            modifier=15,
            total=16,
        )
        result = make_skill_check(dc=10, attribute_modifier=10, skill_modifier=5)
        assert result.is_critical_failure is True
        assert result.success is False  # Critical fail always fails

    @patch("src.dice.checks.roll_with_advantage")
    def test_advantage_type_passed_through(self, mock_roll):
        """Test that advantage type is passed to roller."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(1, 20),
            individual_rolls=(15,),
            modifier=0,
            total=15,
            discarded_rolls=(8,),
        )
        result = make_skill_check(dc=10, advantage_type=AdvantageType.ADVANTAGE)
        assert result.advantage_type == AdvantageType.ADVANTAGE
        mock_roll.assert_called_once()
        call_args = mock_roll.call_args
        assert call_args[0][1] == AdvantageType.ADVANTAGE

    @patch("src.dice.checks.roll_with_advantage")
    def test_modifiers_applied_to_total(self, mock_roll):
        """Test that modifiers are applied correctly."""
        from src.dice.types import DiceExpression, RollResult

        # Roll of 10, modifiers add 7, total should be 17
        mock_roll.return_value = RollResult(
            expression=DiceExpression(1, 20, 7),
            individual_rolls=(10,),
            modifier=7,
            total=17,
        )
        result = make_skill_check(dc=15, attribute_modifier=4, skill_modifier=3)
        assert result.roll_result.total == 17


class TestMakeSavingThrow:
    """Tests for saving throw function."""

    def test_returns_skill_check_result(self):
        """Test that make_saving_throw returns SkillCheckResult."""
        result = make_saving_throw(dc=15)
        assert isinstance(result, SkillCheckResult)

    @patch("src.dice.checks.roll_with_advantage")
    def test_saving_throw_success(self, mock_roll):
        """Test successful saving throw."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(1, 20),
            individual_rolls=(15,),
            modifier=3,
            total=18,
        )
        result = make_saving_throw(dc=15, save_modifier=3)
        assert result.success is True

    @patch("src.dice.checks.roll_with_advantage")
    def test_saving_throw_failure(self, mock_roll):
        """Test failed saving throw."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(1, 20),
            individual_rolls=(5,),
            modifier=2,
            total=7,
        )
        result = make_saving_throw(dc=15, save_modifier=2)
        assert result.success is False

    @patch("src.dice.checks.roll_with_advantage")
    def test_saving_throw_with_advantage(self, mock_roll):
        """Test saving throw with advantage."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(1, 20),
            individual_rolls=(18,),
            modifier=0,
            total=18,
            discarded_rolls=(5,),
        )
        result = make_saving_throw(
            dc=15, save_modifier=0, advantage_type=AdvantageType.ADVANTAGE
        )
        assert result.advantage_type == AdvantageType.ADVANTAGE
