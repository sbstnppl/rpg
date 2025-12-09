"""Tests for proficiency and difficulty assessment functions."""

import pytest

from src.dice.checks import (
    proficiency_to_modifier,
    get_proficiency_tier_name,
    assess_difficulty,
    get_difficulty_description,
    PROFICIENCY_TIERS,
)


class TestProficiencyToModifier:
    """Test proficiency_to_modifier function."""

    def test_novice_range(self):
        """Proficiency 0-19 should give +0 modifier."""
        assert proficiency_to_modifier(0) == 0
        assert proficiency_to_modifier(10) == 0
        assert proficiency_to_modifier(19) == 0

    def test_apprentice_range(self):
        """Proficiency 20-39 should give +1 modifier."""
        assert proficiency_to_modifier(20) == 1
        assert proficiency_to_modifier(30) == 1
        assert proficiency_to_modifier(39) == 1

    def test_competent_range(self):
        """Proficiency 40-59 should give +2 modifier."""
        assert proficiency_to_modifier(40) == 2
        assert proficiency_to_modifier(50) == 2
        assert proficiency_to_modifier(59) == 2

    def test_expert_range(self):
        """Proficiency 60-79 should give +3 modifier."""
        assert proficiency_to_modifier(60) == 3
        assert proficiency_to_modifier(70) == 3
        assert proficiency_to_modifier(79) == 3

    def test_master_range(self):
        """Proficiency 80-99 should give +4 modifier."""
        assert proficiency_to_modifier(80) == 4
        assert proficiency_to_modifier(90) == 4
        assert proficiency_to_modifier(99) == 4

    def test_legendary(self):
        """Proficiency 100 should give +5 modifier."""
        assert proficiency_to_modifier(100) == 5

    def test_negative_clamped(self):
        """Negative proficiency should clamp to 0."""
        assert proficiency_to_modifier(-10) == 0
        assert proficiency_to_modifier(-1) == 0

    def test_over_100_clamped(self):
        """Proficiency over 100 should clamp to 100 -> +5."""
        assert proficiency_to_modifier(150) == 5
        assert proficiency_to_modifier(200) == 5


class TestGetProficiencyTierName:
    """Test get_proficiency_tier_name function."""

    def test_novice_tier(self):
        """Low proficiency should return 'Novice'."""
        assert get_proficiency_tier_name(0) == "Novice"
        assert get_proficiency_tier_name(15) == "Novice"

    def test_apprentice_tier(self):
        """Proficiency 20-39 should return 'Apprentice'."""
        assert get_proficiency_tier_name(25) == "Apprentice"
        assert get_proficiency_tier_name(35) == "Apprentice"

    def test_competent_tier(self):
        """Proficiency 40-59 should return 'Competent'."""
        assert get_proficiency_tier_name(45) == "Competent"
        assert get_proficiency_tier_name(55) == "Competent"

    def test_expert_tier(self):
        """Proficiency 60-79 should return 'Expert'."""
        assert get_proficiency_tier_name(65) == "Expert"
        assert get_proficiency_tier_name(75) == "Expert"

    def test_master_tier(self):
        """Proficiency 80-99 should return 'Master'."""
        assert get_proficiency_tier_name(85) == "Master"
        assert get_proficiency_tier_name(95) == "Master"

    def test_legendary_tier(self):
        """Proficiency 100 should return 'Legendary'."""
        assert get_proficiency_tier_name(100) == "Legendary"


class TestAssessDifficulty:
    """Test assess_difficulty function."""

    def test_trivial_for_skilled(self):
        """High skill vs low DC should be trivial."""
        # +5 skill, +3 attr = +8 total, expected ~18.5 vs DC 5 = margin +13.5
        result = assess_difficulty(dc=5, skill_modifier=5, attribute_modifier=3)
        assert result == "trivial"

    def test_easy_for_trained(self):
        """Moderate skill vs moderate DC should be easy."""
        # +3 skill, +2 attr = +5 total, expected ~15.5 vs DC 10 = margin +5.5
        result = assess_difficulty(dc=10, skill_modifier=3, attribute_modifier=2)
        assert result == "easy"

    def test_moderate_for_average(self):
        """Average character vs moderate DC should be moderate."""
        # +0 skill, +0 attr = +0 total, expected ~10.5 vs DC 10 = margin +0.5
        result = assess_difficulty(dc=10, skill_modifier=0, attribute_modifier=0)
        assert result == "moderate"

    def test_challenging_for_untrained(self):
        """Untrained vs hard DC should be challenging."""
        # +0 skill, +0 attr = +0 total, expected ~10.5 vs DC 15 = margin -4.5
        result = assess_difficulty(dc=15, skill_modifier=0, attribute_modifier=0)
        assert result == "challenging"

    def test_very_hard_for_tough_task(self):
        """Average character vs very hard DC."""
        # +0 skill, +0 attr = +0 total, expected ~10.5 vs DC 20 = margin -9.5
        result = assess_difficulty(dc=20, skill_modifier=0, attribute_modifier=0)
        assert result == "very hard"

    def test_nearly_impossible(self):
        """Very low skill vs legendary DC."""
        # +0 skill, +0 attr = +0 total, expected ~10.5 vs DC 25 = margin -14.5
        result = assess_difficulty(dc=25, skill_modifier=0, attribute_modifier=0)
        assert result == "nearly impossible"


class TestGetDifficultyDescription:
    """Test get_difficulty_description function."""

    def test_returns_string(self):
        """Should return a descriptive string."""
        result = get_difficulty_description(dc=15, skill_modifier=2, attribute_modifier=1)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_trivial_description(self):
        """Trivial tasks should mention 'trivial'."""
        result = get_difficulty_description(dc=5, skill_modifier=5, attribute_modifier=3)
        assert "trivial" in result.lower()

    def test_challenging_description(self):
        """Challenging tasks should mention 'challenging'."""
        result = get_difficulty_description(dc=15, skill_modifier=0, attribute_modifier=0)
        assert "challenging" in result.lower()


class TestProficiencyTiersConstant:
    """Test PROFICIENCY_TIERS constant."""

    def test_has_all_tiers(self):
        """Should have all tier levels."""
        assert 0 in PROFICIENCY_TIERS
        assert 1 in PROFICIENCY_TIERS
        assert 2 in PROFICIENCY_TIERS
        assert 3 in PROFICIENCY_TIERS
        assert 4 in PROFICIENCY_TIERS
        assert 5 in PROFICIENCY_TIERS

    def test_tier_names(self):
        """Should have expected tier names."""
        assert PROFICIENCY_TIERS[0] == "Novice"
        assert PROFICIENCY_TIERS[5] == "Legendary"
