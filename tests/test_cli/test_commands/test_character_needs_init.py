"""Tests for context-aware need initialization in character creation."""

import pytest

from src.cli.commands.character import _infer_initial_needs


class TestInferInitialNeedsDefaults:
    """Tests for default need values."""

    def test_defaults_with_no_context(self) -> None:
        """Test default values when no context provided."""
        needs = _infer_initial_needs()

        # Check reasonable defaults
        assert needs["hunger"] == 80
        assert needs["thirst"] == 80
        assert needs["energy"] == 80
        assert needs["hygiene"] == 80
        assert needs["comfort"] == 70
        assert needs["wellness"] == 100
        assert needs["social_connection"] == 50
        assert needs["morale"] == 70
        assert needs["sense_of_purpose"] == 60
        assert needs["intimacy"] == 80

    def test_all_needs_present(self) -> None:
        """Test all required needs are returned."""
        needs = _infer_initial_needs()

        required_needs = [
            "hunger", "thirst", "energy", "hygiene", "comfort",
            "wellness", "social_connection", "morale", "sense_of_purpose",
            "intimacy",
        ]

        for need in required_needs:
            assert need in needs
            assert 0 <= needs[need] <= 100


class TestInferInitialNeedsHardship:
    """Tests for hardship-based adjustments."""

    def test_escaped_backstory_lowers_needs(self) -> None:
        """Test 'escaped' keyword lowers comfort and hunger."""
        needs = _infer_initial_needs(backstory="I escaped a burning village.")

        assert needs["comfort"] < 70
        assert needs["morale"] < 70
        assert needs["hunger"] < 80
        assert needs["thirst"] < 80
        assert needs["hygiene"] < 80

    def test_fled_backstory_lowers_needs(self) -> None:
        """Test 'fled' keyword lowers needs."""
        needs = _infer_initial_needs(backstory="I fled from my homeland.")

        assert needs["comfort"] < 70
        assert needs["morale"] < 70

    def test_homeless_backstory_lowers_needs(self) -> None:
        """Test 'homeless' keyword lowers needs."""
        needs = _infer_initial_needs(backstory="I've been homeless for years.")

        assert needs["comfort"] < 70
        assert needs["hygiene"] < 80

    def test_starving_backstory_lowers_hunger(self) -> None:
        """Test 'starving' keyword lowers hunger."""
        needs = _infer_initial_needs(backstory="I was starving on the streets.")

        assert needs["hunger"] < 80

    def test_hardship_has_minimum_values(self) -> None:
        """Test hardship adjustments don't go below minimum."""
        needs = _infer_initial_needs(
            backstory="I escaped, fled, was homeless, poor, starving disaster"
        )

        # Should hit the minimums but not go below
        assert needs["comfort"] >= 30
        assert needs["morale"] >= 40
        assert needs["hunger"] >= 40
        assert needs["thirst"] >= 50
        assert needs["hygiene"] >= 40


class TestInferInitialNeedsSocial:
    """Tests for social-based adjustments."""

    def test_isolation_lowers_social(self) -> None:
        """Test isolation keywords lower social connection."""
        backstories = [
            "I am alone in this world.",
            "I lived as a solitary hermit.",
            "I was exiled from my homeland.",
            "I am a wanderer with no ties.",
        ]

        for backstory in backstories:
            needs = _infer_initial_needs(backstory=backstory)
            assert needs["social_connection"] < 50, f"Failed for: {backstory}"

    def test_social_raises_social(self) -> None:
        """Test social keywords raise social connection."""
        backstories = [
            "I have a loving family.",
            "I'm surrounded by friends.",
            "I grew up in a tight community.",
            "I was beloved by my people.",
        ]

        for backstory in backstories:
            needs = _infer_initial_needs(backstory=backstory)
            assert needs["social_connection"] > 50, f"Failed for: {backstory}"

    def test_isolation_has_minimum(self) -> None:
        """Test isolation doesn't go below minimum."""
        needs = _infer_initial_needs(
            backstory="A solitary hermit, alone and isolated, an exile and loner."
        )

        assert needs["social_connection"] >= 20


class TestInferInitialNeedsPurpose:
    """Tests for purpose-based adjustments."""

    def test_purpose_raises_sense_of_purpose(self) -> None:
        """Test purpose keywords raise sense of purpose."""
        backstories = [
            "I am on a mission to save my village.",
            "I believe it is my destiny.",
            "I have sworn a sacred duty.",
            "I am devoted to the cause.",
        ]

        for backstory in backstories:
            needs = _infer_initial_needs(backstory=backstory)
            assert needs["sense_of_purpose"] > 60, f"Failed for: {backstory}"

    def test_quest_raises_purpose(self) -> None:
        """Test 'quest' keyword raises purpose."""
        needs = _infer_initial_needs(backstory="I am on a quest for vengeance.")

        assert needs["sense_of_purpose"] > 60


class TestInferInitialNeedsTrauma:
    """Tests for trauma-based adjustments."""

    def test_trauma_lowers_morale(self) -> None:
        """Test trauma keywords lower morale."""
        needs = _infer_initial_needs(backstory="I am haunted by traumatic memories.")

        assert needs["morale"] < 70

    def test_trauma_lowers_wellness(self) -> None:
        """Test trauma keywords lower wellness."""
        needs = _infer_initial_needs(backstory="I was wounded in battle.")

        assert needs["wellness"] < 100

    def test_scarred_backstory_affects_needs(self) -> None:
        """Test 'scarred' keyword affects needs."""
        needs = _infer_initial_needs(backstory="I am emotionally scarred.")

        assert needs["morale"] < 70


class TestInferInitialNeedsComfort:
    """Tests for comfort-based adjustments."""

    def test_wealthy_raises_comfort(self) -> None:
        """Test 'wealthy' keyword raises comfort."""
        needs = _infer_initial_needs(backstory="I come from a wealthy merchant family.")

        assert needs["comfort"] > 70
        assert needs["hygiene"] > 80

    def test_noble_raises_comfort(self) -> None:
        """Test 'noble' keyword raises comfort."""
        needs = _infer_initial_needs(backstory="I was born into a noble house.")

        assert needs["comfort"] > 70

    def test_luxurious_raises_comfort(self) -> None:
        """Test 'luxurious' keyword raises comfort."""
        needs = _infer_initial_needs(backstory="I lived a luxurious life.")

        assert needs["comfort"] > 70


class TestInferInitialNeedsAge:
    """Tests for age-based adjustments."""

    def test_young_age_boosts_energy(self) -> None:
        """Test young age boosts energy."""
        needs = _infer_initial_needs(age=16)

        assert needs["energy"] > 80

    def test_young_age_boosts_social(self) -> None:
        """Test young age boosts social needs."""
        needs = _infer_initial_needs(age=15)

        assert needs["social_connection"] > 50

    def test_elderly_reduces_energy(self) -> None:
        """Test elderly age reduces energy."""
        needs = _infer_initial_needs(age=65)

        assert needs["energy"] < 80

    def test_elderly_adjusts_intimacy(self) -> None:
        """Test elderly age adjusts intimacy."""
        needs = _infer_initial_needs(age=70)

        # Elderly characters are often more content with intimacy
        assert needs["intimacy"] >= 80

    def test_middle_age_no_adjustment(self) -> None:
        """Test middle age has no special adjustments."""
        default_needs = _infer_initial_needs()
        middle_age_needs = _infer_initial_needs(age=35)

        assert middle_age_needs["energy"] == default_needs["energy"]


class TestInferInitialNeedsOccupation:
    """Tests for occupation-based adjustments."""

    def test_farmer_well_fed(self) -> None:
        """Test farmer occupation boosts hunger/thirst."""
        needs = _infer_initial_needs(occupation="farmer")

        assert needs["hunger"] > 80
        assert needs["thirst"] > 80

    def test_soldier_well_fed(self) -> None:
        """Test soldier occupation boosts hunger/thirst."""
        needs = _infer_initial_needs(occupation="soldier")

        assert needs["hunger"] > 80
        assert needs["thirst"] > 80

    def test_scholar_lower_energy(self) -> None:
        """Test scholar occupation reduces energy."""
        needs = _infer_initial_needs(occupation="scholar")

        assert needs["energy"] < 80

    def test_wizard_lower_energy(self) -> None:
        """Test wizard occupation reduces energy."""
        needs = _infer_initial_needs(occupation="wizard")

        assert needs["energy"] < 80

    def test_merchant_higher_social(self) -> None:
        """Test merchant occupation boosts social."""
        needs = _infer_initial_needs(occupation="merchant")

        assert needs["social_connection"] > 50

    def test_bard_higher_social(self) -> None:
        """Test bard occupation boosts social."""
        needs = _infer_initial_needs(occupation="bard")

        assert needs["social_connection"] > 50

    def test_unknown_occupation_no_change(self) -> None:
        """Test unknown occupation has no effect."""
        default_needs = _infer_initial_needs()
        custom_needs = _infer_initial_needs(occupation="dragon_tamer")

        # Should be same as defaults
        assert custom_needs == default_needs


class TestInferInitialNeedsCombined:
    """Tests for combined context effects."""

    def test_noble_hermit_mixed_effects(self) -> None:
        """Test combined wealthy but isolated backstory."""
        needs = _infer_initial_needs(
            backstory="I was once a wealthy noble, but now live alone as a hermit."
        )

        # Wealth boosts comfort
        assert needs["comfort"] > 70
        # Isolation lowers social
        assert needs["social_connection"] < 50

    def test_young_soldier_combined(self) -> None:
        """Test young age with soldier occupation."""
        needs = _infer_initial_needs(age=17, occupation="soldier")

        # Young boosts energy
        assert needs["energy"] > 80
        # Soldier boosts hunger/thirst
        assert needs["hunger"] > 80

    def test_elderly_scholar_combined(self) -> None:
        """Test elderly age with scholar occupation."""
        needs = _infer_initial_needs(age=70, occupation="scholar")

        # Both reduce energy - check it's still in valid range
        assert 0 <= needs["energy"] <= 100

    def test_traumatic_mission_combined(self) -> None:
        """Test traumatic backstory with purpose."""
        needs = _infer_initial_needs(
            backstory="I witnessed traumatic events but now have a mission for justice."
        )

        # Trauma lowers morale
        assert needs["morale"] < 70
        # Mission raises purpose
        assert needs["sense_of_purpose"] > 60

    def test_escaped_noble_combined(self) -> None:
        """Test escaped from comfortable life."""
        needs = _infer_initial_needs(
            backstory="I escaped from my noble family's estate."
        )

        # Escaped lowers comfort despite noble background
        # The hardship effect should dominate since it's recent
        assert needs["comfort"] <= 70

    def test_case_insensitive_matching(self) -> None:
        """Test keyword matching is case insensitive."""
        upper_needs = _infer_initial_needs(backstory="I ESCAPED from my HOMELAND")
        lower_needs = _infer_initial_needs(backstory="i escaped from my homeland")

        assert upper_needs == lower_needs

    def test_all_parameters_combined(self) -> None:
        """Test all parameters work together."""
        needs = _infer_initial_needs(
            backstory="I fled my family and now wander alone on a sacred quest.",
            age=25,
            occupation="merchant",
        )

        # Should be valid
        for need, value in needs.items():
            assert 0 <= value <= 100, f"Need {need} has invalid value {value}"
