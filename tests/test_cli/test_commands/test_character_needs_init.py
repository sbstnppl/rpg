"""Tests for context-aware initialization in character creation."""

import pytest

from src.cli.commands.character import (
    _infer_initial_needs,
    _infer_initial_vital_status,
    _infer_equipment_condition,
    _infer_starting_situation,
)
from src.database.models.enums import ItemCondition, VitalStatus


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


class TestInferInitialNeedsScene:
    """Tests for starting scene situational adjustments."""

    def test_swimming_scene_lowers_hygiene_comfort(self) -> None:
        """Test swimming scene lowers hygiene and comfort."""
        needs = _infer_initial_needs(starting_scene="You are swimming in a cold lake.")

        assert needs["hygiene"] < 80
        assert needs["comfort"] < 70

    def test_cold_scene_lowers_comfort_energy(self) -> None:
        """Test cold scene lowers comfort and energy."""
        needs = _infer_initial_needs(starting_scene="Snow falls around you in the frozen wasteland.")

        assert needs["comfort"] < 70
        assert needs["energy"] < 80

    def test_dirty_scene_lowers_hygiene(self) -> None:
        """Test dirty environment lowers hygiene."""
        needs = _infer_initial_needs(starting_scene="You emerge from the filthy sewer.")

        assert needs["hygiene"] < 80

    def test_prison_scene_combined_effects(self) -> None:
        """Test prison scene has multiple effects."""
        needs = _infer_initial_needs(starting_scene="You wake in a cold, dirty dungeon cell.")

        # Prison/dungeon is dirty
        assert needs["hygiene"] < 80
        # Dungeon is cold
        assert needs["comfort"] < 70

    def test_lake_backstory_affects_needs(self) -> None:
        """Test lake in backstory affects needs."""
        needs = _infer_initial_needs(backstory="I fell into the river while escaping.")

        # River = wet
        assert needs["hygiene"] < 80


class TestInferInitialVitalStatus:
    """Tests for vital status inference."""

    def test_default_is_healthy(self) -> None:
        """Test default status is HEALTHY."""
        status = _infer_initial_vital_status()
        assert status == VitalStatus.HEALTHY

    def test_wounded_backstory(self) -> None:
        """Test wounded keyword triggers WOUNDED status."""
        status = _infer_initial_vital_status(backstory="I was wounded in battle.")
        assert status == VitalStatus.WOUNDED

    def test_injured_backstory(self) -> None:
        """Test injured keyword triggers WOUNDED status."""
        status = _infer_initial_vital_status(backstory="I was injured escaping the fire.")
        assert status == VitalStatus.WOUNDED

    def test_sick_backstory(self) -> None:
        """Test sick keyword triggers WOUNDED status."""
        status = _infer_initial_vital_status(backstory="I have been sick for weeks.")
        assert status == VitalStatus.WOUNDED

    def test_poisoned_backstory(self) -> None:
        """Test poisoned keyword triggers WOUNDED status."""
        status = _infer_initial_vital_status(backstory="I was poisoned by an assassin.")
        assert status == VitalStatus.WOUNDED

    def test_critical_injury_backstory(self) -> None:
        """Test critical injury keywords trigger WOUNDED."""
        status = _infer_initial_vital_status(backstory="I nearly died from my wounds.")
        assert status == VitalStatus.WOUNDED

    def test_starving_backstory(self) -> None:
        """Test starving keyword triggers WOUNDED status."""
        status = _infer_initial_vital_status(backstory="I was starving on the streets.")
        assert status == VitalStatus.WOUNDED

    def test_starting_scene_affects_status(self) -> None:
        """Test starting scene can trigger WOUNDED status."""
        status = _infer_initial_vital_status(
            starting_scene="You collapse, bleeding from your wounds."
        )
        assert status == VitalStatus.WOUNDED

    def test_healthy_backstory_stays_healthy(self) -> None:
        """Test non-injury backstory stays HEALTHY."""
        status = _infer_initial_vital_status(
            backstory="I lived a comfortable life as a merchant."
        )
        assert status == VitalStatus.HEALTHY

    def test_old_scar_stays_healthy(self) -> None:
        """Test mention of old scar doesn't trigger wounded (scar vs scarred)."""
        # "scar" alone doesn't trigger - only "scarred" does
        # This allows backstories to mention old scars without implying current injury
        status = _infer_initial_vital_status(backstory="I bear an old scar.")
        assert status == VitalStatus.HEALTHY

    def test_scarred_triggers_wounded(self) -> None:
        """Test 'scarred' keyword triggers WOUNDED."""
        status = _infer_initial_vital_status(backstory="I am heavily scarred from battle.")
        assert status == VitalStatus.WOUNDED


class TestInferEquipmentCondition:
    """Tests for equipment condition inference."""

    def test_default_is_good(self) -> None:
        """Test default condition is GOOD."""
        condition = _infer_equipment_condition()
        assert condition == ItemCondition.GOOD

    def test_wealthy_gets_pristine(self) -> None:
        """Test wealthy backstory gets PRISTINE equipment."""
        condition = _infer_equipment_condition(backstory="I come from a wealthy family.")
        assert condition == ItemCondition.PRISTINE

    def test_noble_gets_pristine(self) -> None:
        """Test noble backstory gets PRISTINE equipment."""
        condition = _infer_equipment_condition(backstory="I am a noble from House Stark.")
        assert condition == ItemCondition.PRISTINE

    def test_escaped_gets_worn(self) -> None:
        """Test escaped backstory gets WORN equipment."""
        condition = _infer_equipment_condition(backstory="I escaped from prison.")
        assert condition == ItemCondition.WORN

    def test_refugee_gets_worn(self) -> None:
        """Test refugee backstory gets WORN equipment."""
        condition = _infer_equipment_condition(backstory="I am a refugee from the war.")
        assert condition == ItemCondition.WORN

    def test_disaster_gets_damaged(self) -> None:
        """Test disaster backstory gets DAMAGED equipment."""
        condition = _infer_equipment_condition(backstory="My village was destroyed in a fire.")
        assert condition == ItemCondition.DAMAGED

    def test_battle_gets_damaged(self) -> None:
        """Test battle backstory gets DAMAGED equipment."""
        condition = _infer_equipment_condition(backstory="I survived a terrible battle.")
        assert condition == ItemCondition.DAMAGED

    def test_peasant_gets_worn(self) -> None:
        """Test peasant backstory gets WORN equipment."""
        condition = _infer_equipment_condition(backstory="I grew up as a peasant farmer.")
        assert condition == ItemCondition.WORN

    def test_soldier_occupation_gets_good(self) -> None:
        """Test soldier occupation maintains GOOD equipment."""
        condition = _infer_equipment_condition(occupation="soldier")
        assert condition == ItemCondition.GOOD

    def test_backstory_overrides_occupation(self) -> None:
        """Test backstory takes precedence over occupation."""
        # Wealthy backstory beats soldier occupation
        condition = _infer_equipment_condition(
            backstory="I am a wealthy merchant's son.",
            occupation="soldier",
        )
        assert condition == ItemCondition.PRISTINE


class TestInferStartingSituation:
    """Tests for situational flag inference."""

    def test_default_all_false(self) -> None:
        """Test defaults are all False."""
        situation = _infer_starting_situation()

        assert situation["is_wet"] is False
        assert situation["is_cold"] is False
        assert situation["is_dirty"] is False
        assert situation["minimal_equipment"] is False
        assert situation["no_weapons"] is False
        assert situation["no_armor"] is False

    def test_swimming_is_wet(self) -> None:
        """Test swimming triggers wet flag."""
        situation = _infer_starting_situation(starting_scene="You are swimming in the lake.")

        assert situation["is_wet"] is True
        assert situation["minimal_equipment"] is True
        assert situation["no_armor"] is True

    def test_rain_is_wet(self) -> None:
        """Test rain triggers wet flag."""
        situation = _infer_starting_situation(starting_scene="Rain pours down on you.")

        assert situation["is_wet"] is True

    def test_snow_is_cold(self) -> None:
        """Test snow triggers cold flag."""
        situation = _infer_starting_situation(starting_scene="Snow falls around you.")

        assert situation["is_cold"] is True

    def test_freezing_is_cold(self) -> None:
        """Test freezing triggers cold flag."""
        situation = _infer_starting_situation(backstory="I was freezing in the mountains.")

        assert situation["is_cold"] is True

    def test_sewer_is_dirty(self) -> None:
        """Test sewer triggers dirty flag."""
        situation = _infer_starting_situation(starting_scene="You crawl through the sewer.")

        assert situation["is_dirty"] is True

    def test_prison_is_dirty(self) -> None:
        """Test prison triggers dirty flag."""
        situation = _infer_starting_situation(backstory="I was held in a filthy prison.")

        assert situation["is_dirty"] is True

    def test_prisoner_has_no_weapons(self) -> None:
        """Test prisoner has no weapons."""
        situation = _infer_starting_situation(backstory="I was a prisoner.")

        assert situation["no_weapons"] is True
        assert situation["minimal_equipment"] is True

    def test_captive_has_minimal_equipment(self) -> None:
        """Test captive has minimal equipment."""
        situation = _infer_starting_situation(starting_scene="You were held captive.")

        assert situation["minimal_equipment"] is True
        assert situation["no_armor"] is True

    def test_shipwreck_combined_effects(self) -> None:
        """Test shipwreck has multiple effects."""
        situation = _infer_starting_situation(backstory="I survived a shipwreck.")

        assert situation["is_wet"] is True
        assert situation["minimal_equipment"] is True

    def test_monk_has_no_weapons(self) -> None:
        """Test monk/pacifist has no weapons."""
        situation = _infer_starting_situation(backstory="I am a peaceful monk.")

        assert situation["no_weapons"] is True

    def test_combined_backstory_and_scene(self) -> None:
        """Test both backstory and scene affect flags."""
        situation = _infer_starting_situation(
            backstory="I was a prisoner in the dungeon.",
            starting_scene="You stand in the cold rain.",
        )

        # Prisoner = no weapons, minimal equipment
        assert situation["no_weapons"] is True
        assert situation["minimal_equipment"] is True
        # Dungeon = dirty
        assert situation["is_dirty"] is True
        # Rain = wet, cold
        assert situation["is_wet"] is True
        assert situation["is_cold"] is True
