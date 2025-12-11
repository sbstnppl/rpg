"""Tests for contested rolls and action economy."""

import pytest

from src.dice.contested import (
    ActionType,
    ContestResult,
    contested_roll,
    resolve_contest,
)


class TestContestedRoll:
    """Tests for contested roll mechanics."""

    def test_contested_roll_clear_winner(self):
        """Test when there's a clear winner."""
        # Mock a situation where attacker rolls high
        result = contested_roll(
            attacker_modifier=5,
            defender_modifier=-2,
        )
        assert result.attacker_total == result.attacker_roll + 5
        assert result.defender_total == result.defender_roll - 2
        assert result.winner in ("attacker", "defender")

    def test_contested_roll_with_advantage(self):
        """Test contested roll with advantage."""
        result = contested_roll(
            attacker_modifier=3,
            defender_modifier=3,
            attacker_advantage=True,
        )
        # Advantage means we took best of 2 rolls
        assert result.attacker_total >= result.attacker_roll + 3

    def test_contested_roll_with_disadvantage(self):
        """Test contested roll with disadvantage."""
        result = contested_roll(
            attacker_modifier=3,
            defender_modifier=3,
            defender_disadvantage=True,
        )
        assert result.defender_total <= result.defender_roll + 3

    def test_contested_roll_tie_goes_to_defender(self):
        """Test that ties favor the defender (status quo)."""
        # We can't easily force a tie, but we test the tiebreaker logic
        result = resolve_contest(
            attacker_total=15,
            defender_total=15,
        )
        assert result == "defender"  # Status quo holds

    def test_contested_roll_margin(self):
        """Test margin of success calculation."""
        result = contested_roll(
            attacker_modifier=10,
            defender_modifier=0,
        )
        expected_margin = result.attacker_total - result.defender_total
        assert result.margin == expected_margin


class TestResolveContest:
    """Tests for contest resolution."""

    def test_attacker_wins(self):
        result = resolve_contest(attacker_total=18, defender_total=12)
        assert result == "attacker"

    def test_defender_wins(self):
        result = resolve_contest(attacker_total=10, defender_total=15)
        assert result == "defender"

    def test_tie_defender_wins(self):
        result = resolve_contest(attacker_total=14, defender_total=14)
        assert result == "defender"


class TestCommonContests:
    """Tests for common contest types."""

    def test_grapple_contest(self):
        """Grapple: Athletics vs Athletics or Acrobatics."""
        from src.dice.contested import grapple_contest

        result = grapple_contest(
            grappler_athletics=5,
            target_athletics=3,
            target_acrobatics=4,  # Target picks higher
        )
        assert result.contest_type == "grapple"
        # Target should use acrobatics (4) over athletics (3)
        assert result.defender_skill == "acrobatics"

    def test_escape_grapple_contest(self):
        """Escape grapple: Athletics or Acrobatics vs Athletics."""
        from src.dice.contested import escape_grapple_contest

        result = escape_grapple_contest(
            escapee_athletics=2,
            escapee_acrobatics=5,
            grappler_athletics=4,
        )
        assert result.contest_type == "escape_grapple"
        assert result.attacker_skill == "acrobatics"

    def test_stealth_vs_perception(self):
        """Stealth vs Perception contest."""
        from src.dice.contested import stealth_contest

        result = stealth_contest(
            hider_stealth=7,
            seeker_perception=5,
        )
        assert result.contest_type == "stealth"
        assert result.winner in ("attacker", "defender")

    def test_shove_contest(self):
        """Shove: Athletics vs Athletics or Acrobatics."""
        from src.dice.contested import shove_contest

        result = shove_contest(
            shover_athletics=6,
            target_athletics=4,
            target_acrobatics=5,
        )
        assert result.contest_type == "shove"

    def test_deception_vs_insight(self):
        """Deception vs Insight contest."""
        from src.dice.contested import social_contest

        result = social_contest(
            actor_skill=8,
            actor_skill_name="deception",
            observer_insight=6,
        )
        assert result.contest_type == "social"


class TestActionType:
    """Tests for action type enum."""

    def test_action_types(self):
        assert ActionType.STANDARD.value == "standard"
        assert ActionType.MOVE.value == "move"
        assert ActionType.BONUS.value == "bonus"
        assert ActionType.REACTION.value == "reaction"
        assert ActionType.FREE.value == "free"


class TestActionEconomy:
    """Tests for action economy tracking."""

    def test_create_action_budget(self):
        from src.dice.contested import ActionBudget

        budget = ActionBudget()
        assert budget.standard_actions == 1
        assert budget.move_actions == 1
        assert budget.bonus_actions == 1
        assert budget.reaction == 1

    def test_use_standard_action(self):
        from src.dice.contested import ActionBudget

        budget = ActionBudget()
        assert budget.can_use(ActionType.STANDARD)
        budget.use(ActionType.STANDARD)
        assert not budget.can_use(ActionType.STANDARD)

    def test_use_move_action(self):
        from src.dice.contested import ActionBudget

        budget = ActionBudget()
        budget.use(ActionType.MOVE)
        assert not budget.can_use(ActionType.MOVE)

    def test_use_bonus_action(self):
        from src.dice.contested import ActionBudget

        budget = ActionBudget()
        budget.use(ActionType.BONUS)
        assert not budget.can_use(ActionType.BONUS)

    def test_use_reaction(self):
        from src.dice.contested import ActionBudget

        budget = ActionBudget()
        budget.use(ActionType.REACTION)
        assert not budget.can_use(ActionType.REACTION)

    def test_free_actions_unlimited(self):
        from src.dice.contested import ActionBudget

        budget = ActionBudget()
        # Free actions don't consume anything
        for _ in range(5):
            budget.use(ActionType.FREE)
            assert budget.can_use(ActionType.FREE)

    def test_reset_budget(self):
        from src.dice.contested import ActionBudget

        budget = ActionBudget()
        budget.use(ActionType.STANDARD)
        budget.use(ActionType.MOVE)
        budget.reset()
        assert budget.can_use(ActionType.STANDARD)
        assert budget.can_use(ActionType.MOVE)

    def test_convert_standard_to_move(self):
        from src.dice.contested import ActionBudget

        budget = ActionBudget()
        budget.use(ActionType.MOVE)  # Use normal move
        # Can convert standard action to movement
        assert budget.can_convert_standard_to_move()
        budget.convert_standard_to_move()
        assert budget.can_use(ActionType.MOVE)
        assert not budget.can_use(ActionType.STANDARD)

    def test_get_remaining_actions_string(self):
        from src.dice.contested import ActionBudget

        budget = ActionBudget()
        budget.use(ActionType.STANDARD)
        remaining = budget.get_remaining_string()
        assert "Move" in remaining
        assert "Bonus" in remaining
        assert "Standard" not in remaining or "0" in remaining
