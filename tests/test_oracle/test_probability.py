"""Tests for the probability calculation module."""

import pytest

from src.oracle.probability import (
    ComplicationProbability,
    ProbabilityCalculator,
    should_trigger_complication,
)


class TestProbabilityCalculator:
    """Tests for ProbabilityCalculator."""

    def test_base_chance_with_no_modifiers(self):
        """Test that base chance is returned when no modifiers apply."""
        calc = ProbabilityCalculator(base_chance=0.05)
        result = calc.calculate(risk_tags=[])

        assert result.base_chance == 0.05
        assert result.final_chance == 0.05
        assert result.arc_modifier == 0.0
        assert result.risk_modifier == 0.0

    def test_risk_tag_increases_chance(self):
        """Test that risk tags increase probability."""
        calc = ProbabilityCalculator(base_chance=0.05)
        result = calc.calculate(risk_tags=["dangerous"])

        assert result.risk_modifier > 0
        assert result.final_chance > result.base_chance

    def test_multiple_risk_tags_stack(self):
        """Test that multiple risk tags stack additively."""
        calc = ProbabilityCalculator(base_chance=0.05)

        single_tag = calc.calculate(risk_tags=["dangerous"])
        double_tag = calc.calculate(risk_tags=["dangerous", "mysterious"])

        assert double_tag.risk_modifier > single_tag.risk_modifier
        assert double_tag.final_chance > single_tag.final_chance

    def test_arc_phase_modifier(self):
        """Test that arc phase affects probability."""
        calc = ProbabilityCalculator(base_chance=0.05)

        setup_result = calc.calculate(risk_tags=[], arc_phase="setup")
        climax_result = calc.calculate(risk_tags=[], arc_phase="climax")

        assert climax_result.arc_modifier > setup_result.arc_modifier
        assert climax_result.final_chance > setup_result.final_chance

    def test_arc_tension_modifier(self):
        """Test that arc tension affects probability above threshold."""
        calc = ProbabilityCalculator(base_chance=0.05)

        low_tension = calc.calculate(risk_tags=[], arc_tension=30)
        high_tension = calc.calculate(risk_tags=[], arc_tension=80)

        # Low tension should not add modifier
        assert "arc_tension" in low_tension.breakdown
        assert low_tension.breakdown["arc_tension"] == 0.0

        # High tension should add modifier
        assert high_tension.breakdown["arc_tension"] > 0

    def test_cooldown_reduces_chance(self):
        """Test that recent complication reduces probability."""
        calc = ProbabilityCalculator(base_chance=0.10, cooldown_turns=3)

        # Just had a complication
        recent = calc.calculate(risk_tags=[], turns_since_complication=1)

        # Long time ago
        old = calc.calculate(risk_tags=[], turns_since_complication=10)

        assert recent.cooldown_multiplier < 1.0
        assert old.cooldown_multiplier == 1.0
        assert recent.final_chance < old.final_chance

    def test_hard_cap(self):
        """Test that probability never exceeds max_chance."""
        calc = ProbabilityCalculator(base_chance=0.30, max_chance=0.35)

        # Add many risk tags to push over cap
        result = calc.calculate(
            risk_tags=["dangerous", "mysterious", "forbidden", "cursed"],
            arc_phase="climax",
            arc_tension=100,
        )

        assert result.final_chance <= calc.max_chance

    def test_unknown_risk_tag_no_effect(self):
        """Test that unknown risk tags don't affect probability."""
        calc = ProbabilityCalculator(base_chance=0.05)

        with_unknown = calc.calculate(risk_tags=["nonexistent_tag"])
        without = calc.calculate(risk_tags=[])

        assert with_unknown.final_chance == without.final_chance


class TestShouldTriggerComplication:
    """Tests for the trigger function."""

    def test_zero_chance_never_triggers(self):
        """Test that zero probability never triggers."""
        prob = ComplicationProbability(
            base_chance=0.0,
            arc_modifier=0.0,
            risk_modifier=0.0,
            cooldown_multiplier=1.0,
            final_chance=0.0,
            breakdown={},
        )

        # Run many times to verify
        results = [should_trigger_complication(prob) for _ in range(100)]
        assert not any(results)

    def test_full_chance_always_triggers(self):
        """Test that 100% probability always triggers."""
        prob = ComplicationProbability(
            base_chance=1.0,
            arc_modifier=0.0,
            risk_modifier=0.0,
            cooldown_multiplier=1.0,
            final_chance=1.0,
            breakdown={},
        )

        results = [should_trigger_complication(prob) for _ in range(100)]
        assert all(results)
