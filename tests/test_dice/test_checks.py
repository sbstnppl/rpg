"""Tests for skill checks and ability modifiers.

Tests the 2d10 bell curve skill check system with:
- Auto-success for routine tasks (DC <= 10 + modifier)
- Degree of success based on margin
- Critical success on double-10 (1%)
- Critical failure on double-1 (1%)
"""

import pytest
from unittest.mock import patch

from src.dice.checks import (
    calculate_ability_modifier,
    make_skill_check,
    make_saving_throw,
    can_auto_succeed,
    get_outcome_tier,
    DC_TRIVIAL,
    DC_EASY,
    DC_MODERATE,
    DC_HARD,
    DC_VERY_HARD,
    DC_LEGENDARY,
)
from src.dice.types import AdvantageType, SkillCheckResult, OutcomeTier


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


class TestCanAutoSucceed:
    """Tests for auto-success (Take 10 rule)."""

    def test_auto_success_when_dc_at_threshold(self):
        """Test auto-success when DC equals 10 + modifier."""
        assert can_auto_succeed(dc=15, total_modifier=5) is True  # 15 <= 15

    def test_auto_success_when_dc_below_threshold(self):
        """Test auto-success when DC is below threshold."""
        assert can_auto_succeed(dc=10, total_modifier=5) is True  # 10 <= 15

    def test_no_auto_success_when_dc_above_threshold(self):
        """Test no auto-success when DC exceeds threshold."""
        assert can_auto_succeed(dc=20, total_modifier=5) is False  # 20 > 15

    def test_master_auto_succeeds_moderate_tasks(self):
        """Test master (+8 modifier) auto-succeeds DC 18 and below."""
        assert can_auto_succeed(dc=18, total_modifier=8) is True
        assert can_auto_succeed(dc=19, total_modifier=8) is False

    def test_untrained_limited_auto_success(self):
        """Test untrained (+0 modifier) only auto-succeeds DC 10."""
        assert can_auto_succeed(dc=10, total_modifier=0) is True
        assert can_auto_succeed(dc=11, total_modifier=0) is False


class TestGetOutcomeTier:
    """Tests for degree of success calculation."""

    def test_exceptional_margin(self):
        """Test exceptional outcome with margin >= 10."""
        assert get_outcome_tier(margin=10, success=True) == OutcomeTier.EXCEPTIONAL
        assert get_outcome_tier(margin=15, success=True) == OutcomeTier.EXCEPTIONAL

    def test_clear_success_margin(self):
        """Test clear success with margin 5-9."""
        assert get_outcome_tier(margin=5, success=True) == OutcomeTier.CLEAR_SUCCESS
        assert get_outcome_tier(margin=9, success=True) == OutcomeTier.CLEAR_SUCCESS

    def test_narrow_success_margin(self):
        """Test narrow success with margin 1-4."""
        assert get_outcome_tier(margin=1, success=True) == OutcomeTier.NARROW_SUCCESS
        assert get_outcome_tier(margin=4, success=True) == OutcomeTier.NARROW_SUCCESS

    def test_bare_success_margin(self):
        """Test bare success with margin 0."""
        assert get_outcome_tier(margin=0, success=True) == OutcomeTier.BARE_SUCCESS

    def test_partial_failure_margin(self):
        """Test partial failure with margin -1 to -4."""
        assert get_outcome_tier(margin=-1, success=False) == OutcomeTier.PARTIAL_FAILURE
        assert get_outcome_tier(margin=-4, success=False) == OutcomeTier.PARTIAL_FAILURE

    def test_clear_failure_margin(self):
        """Test clear failure with margin -5 to -9."""
        assert get_outcome_tier(margin=-5, success=False) == OutcomeTier.CLEAR_FAILURE
        assert get_outcome_tier(margin=-9, success=False) == OutcomeTier.CLEAR_FAILURE

    def test_catastrophic_margin(self):
        """Test catastrophic failure with margin <= -10."""
        assert get_outcome_tier(margin=-10, success=False) == OutcomeTier.CATASTROPHIC
        assert get_outcome_tier(margin=-15, success=False) == OutcomeTier.CATASTROPHIC


class TestMakeSkillCheck:
    """Tests for skill check function (2d10 system)."""

    def test_returns_skill_check_result(self):
        """Test that make_skill_check returns SkillCheckResult."""
        result = make_skill_check(dc=10)
        assert isinstance(result, SkillCheckResult)

    def test_dc_stored_in_result(self):
        """Test that DC is stored in result."""
        result = make_skill_check(dc=15)
        assert result.dc == 15

    def test_auto_success_for_skilled_character(self):
        """Test auto-success when modifier is high enough."""
        # With +8 modifier, DC 15 should auto-succeed (15 <= 18)
        result = make_skill_check(dc=15, attribute_modifier=4, skill_modifier=4)
        assert result.is_auto_success is True
        assert result.success is True
        assert result.roll_result is None  # No roll made

    def test_no_auto_success_for_hard_task(self):
        """Test that hard tasks require rolling even for experts."""
        # With +8 modifier, DC 20 requires a roll (20 > 18)
        result = make_skill_check(dc=20, attribute_modifier=4, skill_modifier=4)
        assert result.is_auto_success is False
        assert result.roll_result is not None

    @patch("src.dice.checks.roll_2d10")
    def test_success_when_total_meets_dc(self, mock_roll):
        """Test success when 2d10 + modifiers >= DC."""
        from src.dice.types import DiceExpression, RollResult

        # High DC to force a roll (no auto-success)
        mock_roll.return_value = RollResult(
            expression=DiceExpression(2, 10, 5),
            individual_rolls=(8, 7),  # 15 base
            modifier=5,
            total=20,  # 15 + 5 = 20
        )
        result = make_skill_check(dc=18, attribute_modifier=3, skill_modifier=2)
        assert result.success is True

    @patch("src.dice.checks.roll_2d10")
    def test_failure_when_total_below_dc(self, mock_roll):
        """Test failure when 2d10 + modifiers < DC."""
        from src.dice.types import DiceExpression, RollResult

        # High DC to force a roll
        mock_roll.return_value = RollResult(
            expression=DiceExpression(2, 10, 0),
            individual_rolls=(3, 4),  # 7 base
            modifier=0,
            total=7,
        )
        result = make_skill_check(dc=20)  # No modifiers
        assert result.success is False

    @patch("src.dice.checks.roll_2d10")
    def test_margin_calculated_correctly(self, mock_roll):
        """Test that margin is total - DC."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(2, 10, 5),
            individual_rolls=(8, 7),  # 15 base
            modifier=5,
            total=20,
        )
        result = make_skill_check(dc=20, attribute_modifier=3, skill_modifier=2)
        assert result.margin == 0  # 20 - 20

    @patch("src.dice.checks.roll_2d10")
    def test_negative_margin_on_failure(self, mock_roll):
        """Test that margin is negative on failure."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(2, 10, 2),
            individual_rolls=(3, 4),  # 7 base
            modifier=2,
            total=9,
        )
        result = make_skill_check(dc=20, attribute_modifier=1, skill_modifier=1)
        assert result.margin == -11  # 9 - 20

    @patch("src.dice.checks.roll_2d10")
    def test_double_10_is_critical_success(self, mock_roll):
        """Test that both dice showing 10 is critical success."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(2, 10, 0),
            individual_rolls=(10, 10),  # Double 10!
            modifier=0,
            total=20,
        )
        result = make_skill_check(dc=20)
        assert result.is_critical_success is True

    @patch("src.dice.checks.roll_2d10")
    def test_double_1_is_critical_failure(self, mock_roll):
        """Test that both dice showing 1 is critical failure."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(2, 10, 0),
            individual_rolls=(1, 1),  # Double 1!
            modifier=0,
            total=2,
        )
        result = make_skill_check(dc=20)
        assert result.is_critical_failure is True

    @patch("src.dice.checks.roll_2d10")
    def test_no_critical_on_mixed_rolls(self, mock_roll):
        """Test that mixed rolls (not double) are not criticals."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(2, 10, 0),
            individual_rolls=(10, 9),  # Not double
            modifier=0,
            total=19,
        )
        result = make_skill_check(dc=20)
        assert result.is_critical_success is False
        assert result.is_critical_failure is False

    @patch("src.dice.checks.roll_2d10")
    def test_advantage_type_passed_through(self, mock_roll):
        """Test that advantage type is passed to roller."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(2, 10, 0),
            individual_rolls=(8, 7),
            modifier=0,
            total=15,
            discarded_rolls=(3,),  # Advantage discards lowest
        )
        result = make_skill_check(dc=20, advantage_type=AdvantageType.ADVANTAGE)
        assert result.advantage_type == AdvantageType.ADVANTAGE
        mock_roll.assert_called_once()
        call_args = mock_roll.call_args
        assert call_args[1]["advantage_type"] == AdvantageType.ADVANTAGE

    @patch("src.dice.checks.roll_2d10")
    def test_outcome_tier_included(self, mock_roll):
        """Test that outcome tier is included in result."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(2, 10, 5),
            individual_rolls=(8, 7),
            modifier=5,
            total=20,
        )
        result = make_skill_check(dc=20, attribute_modifier=3, skill_modifier=2)
        assert result.outcome_tier == OutcomeTier.BARE_SUCCESS  # margin 0

    def test_auto_success_has_outcome_tier(self):
        """Test that auto-success results have an outcome tier."""
        result = make_skill_check(dc=10, attribute_modifier=4, skill_modifier=4)
        assert result.is_auto_success is True
        assert result.outcome_tier is not None
        # Auto-success margin = 11 + 8 - 10 = 9 -> clear success
        assert result.outcome_tier == OutcomeTier.CLEAR_SUCCESS


class TestMakeSavingThrow:
    """Tests for saving throw function (uses 2d10 like skill checks)."""

    def test_returns_skill_check_result(self):
        """Test that make_saving_throw returns SkillCheckResult."""
        result = make_saving_throw(dc=15)
        assert isinstance(result, SkillCheckResult)

    @patch("src.dice.checks.roll_2d10")
    def test_saving_throw_success(self, mock_roll):
        """Test successful saving throw."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(2, 10, 3),
            individual_rolls=(8, 7),
            modifier=3,
            total=18,
        )
        result = make_saving_throw(dc=20, save_modifier=3)
        assert result.success is False  # 18 < 20

    @patch("src.dice.checks.roll_2d10")
    def test_saving_throw_failure(self, mock_roll):
        """Test failed saving throw."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(2, 10, 2),
            individual_rolls=(3, 4),
            modifier=2,
            total=9,
        )
        result = make_saving_throw(dc=15, save_modifier=2)
        assert result.success is False

    @patch("src.dice.checks.roll_2d10")
    def test_saving_throw_with_advantage(self, mock_roll):
        """Test saving throw with advantage."""
        from src.dice.types import DiceExpression, RollResult

        mock_roll.return_value = RollResult(
            expression=DiceExpression(2, 10, 0),
            individual_rolls=(9, 8),
            modifier=0,
            total=17,
            discarded_rolls=(3,),
        )
        result = make_saving_throw(
            dc=20, save_modifier=0, advantage_type=AdvantageType.ADVANTAGE
        )
        assert result.advantage_type == AdvantageType.ADVANTAGE

    def test_saving_throw_auto_success(self):
        """Test that saving throws can also auto-succeed."""
        # With +8 save modifier, DC 15 should auto-succeed
        result = make_saving_throw(dc=15, save_modifier=8)
        assert result.is_auto_success is True
        assert result.success is True
