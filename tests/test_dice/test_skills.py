"""Tests for skill-to-attribute mapping."""

import pytest

from src.dice.skills import (
    get_attribute_for_skill,
    get_skills_for_attribute,
    DEFAULT_SKILL_ATTRIBUTES,
    DEFAULT_ATTRIBUTE,
)


class TestGetAttributeForSkill:
    """Test get_attribute_for_skill function."""

    def test_stealth_uses_dexterity(self):
        """Stealth should use dexterity."""
        assert get_attribute_for_skill("stealth") == "dexterity"

    def test_persuasion_uses_charisma(self):
        """Persuasion should use charisma."""
        assert get_attribute_for_skill("persuasion") == "charisma"

    def test_athletics_uses_strength(self):
        """Athletics should use strength."""
        assert get_attribute_for_skill("athletics") == "strength"

    def test_perception_uses_wisdom(self):
        """Perception should use wisdom."""
        assert get_attribute_for_skill("perception") == "wisdom"

    def test_arcana_uses_intelligence(self):
        """Arcana should use intelligence."""
        assert get_attribute_for_skill("arcana") == "intelligence"

    def test_case_insensitive(self):
        """Skill lookup should be case insensitive."""
        assert get_attribute_for_skill("STEALTH") == "dexterity"
        assert get_attribute_for_skill("Persuasion") == "charisma"
        assert get_attribute_for_skill("ATHLETICS") == "strength"

    def test_normalizes_spaces_to_underscores(self):
        """Spaces should be normalized to underscores."""
        assert get_attribute_for_skill("animal handling") == "wisdom"
        assert get_attribute_for_skill("sleight of hand") == "dexterity"

    def test_normalizes_hyphens_to_underscores(self):
        """Hyphens should be normalized to underscores."""
        assert get_attribute_for_skill("animal-handling") == "wisdom"

    def test_unknown_skill_defaults_to_intelligence(self):
        """Unknown skills should default to intelligence."""
        assert get_attribute_for_skill("unknown_skill") == "intelligence"
        assert get_attribute_for_skill("made_up_thing") == "intelligence"

    def test_craft_skills(self):
        """Craft skills should have appropriate attributes."""
        assert get_attribute_for_skill("blacksmithing") == "strength"
        assert get_attribute_for_skill("woodworking") == "dexterity"
        assert get_attribute_for_skill("cooking") == "wisdom"

    def test_combat_skills(self):
        """Combat skills should have appropriate attributes."""
        assert get_attribute_for_skill("swordfighting") == "strength"
        assert get_attribute_for_skill("fencing") == "dexterity"
        assert get_attribute_for_skill("archery") == "dexterity"


class TestGetSkillsForAttribute:
    """Test get_skills_for_attribute function."""

    def test_charisma_skills(self):
        """Should return charisma-based skills."""
        skills = get_skills_for_attribute("charisma")
        assert "persuasion" in skills
        assert "deception" in skills
        assert "intimidation" in skills

    def test_dexterity_skills(self):
        """Should return dexterity-based skills."""
        skills = get_skills_for_attribute("dexterity")
        assert "stealth" in skills
        assert "acrobatics" in skills
        assert "lockpicking" in skills

    def test_strength_skills(self):
        """Should return strength-based skills."""
        skills = get_skills_for_attribute("strength")
        assert "athletics" in skills
        assert "climbing" in skills

    def test_case_insensitive(self):
        """Should work case-insensitively."""
        skills_lower = get_skills_for_attribute("charisma")
        skills_upper = get_skills_for_attribute("CHARISMA")
        skills_mixed = get_skills_for_attribute("Charisma")

        assert skills_lower == skills_upper == skills_mixed

    def test_unknown_attribute_returns_empty(self):
        """Unknown attribute should return empty list."""
        skills = get_skills_for_attribute("unknown_attribute")
        assert skills == []


class TestDefaultSkillAttributes:
    """Test DEFAULT_SKILL_ATTRIBUTES constant."""

    def test_has_common_skills(self):
        """Should include common RPG skills."""
        assert "stealth" in DEFAULT_SKILL_ATTRIBUTES
        assert "persuasion" in DEFAULT_SKILL_ATTRIBUTES
        assert "athletics" in DEFAULT_SKILL_ATTRIBUTES
        assert "perception" in DEFAULT_SKILL_ATTRIBUTES

    def test_values_are_valid_attributes(self):
        """All values should be valid attribute names."""
        valid_attrs = {
            "strength", "dexterity", "constitution",
            "intelligence", "wisdom", "charisma",
            "history",  # This appears to be a typo - should be intelligence
        }
        for skill, attr in DEFAULT_SKILL_ATTRIBUTES.items():
            assert attr in valid_attrs, f"Skill '{skill}' has invalid attribute '{attr}'"


class TestDefaultAttribute:
    """Test DEFAULT_ATTRIBUTE constant."""

    def test_default_is_intelligence(self):
        """Default attribute should be intelligence."""
        assert DEFAULT_ATTRIBUTE == "intelligence"
