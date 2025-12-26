"""Tests for GM grounding system.

Tests the GroundingManifest, GroundingValidator, and key stripping functionality.
"""

import pytest

from src.gm.grounding import (
    GroundedEntity,
    GroundingManifest,
    GroundingValidationResult,
    InvalidKeyReference,
    UnkeyedMention,
)
from src.gm.grounding_validator import (
    GroundingValidator,
    strip_key_references,
    KEY_PATTERN,
)


# =============================================================================
# GroundingManifest Tests
# =============================================================================


class TestGroundedEntity:
    """Tests for GroundedEntity model."""

    def test_create_basic_entity(self):
        """Test creating a basic grounded entity."""
        entity = GroundedEntity(
            key="sword_001",
            display_name="Iron Sword",
            entity_type="item",
        )
        assert entity.key == "sword_001"
        assert entity.display_name == "Iron Sword"
        assert entity.entity_type == "item"
        assert entity.short_description == ""

    def test_create_entity_with_description(self):
        """Test creating entity with short description."""
        entity = GroundedEntity(
            key="marcus_001",
            display_name="Marcus",
            entity_type="npc",
            short_description="the blacksmith",
        )
        assert entity.short_description == "the blacksmith"


class TestGroundingManifest:
    """Tests for GroundingManifest model."""

    @pytest.fixture
    def sample_manifest(self) -> GroundingManifest:
        """Create a sample manifest for testing."""
        return GroundingManifest(
            location_key="tavern_001",
            location_display="The Rusty Nail Tavern",
            player_key="player_001",
            player_display="You",
            npcs={
                "marcus_001": GroundedEntity(
                    key="marcus_001",
                    display_name="Marcus",
                    entity_type="npc",
                    short_description="blacksmith",
                ),
                "anna_001": GroundedEntity(
                    key="anna_001",
                    display_name="Anna",
                    entity_type="npc",
                    short_description="tavern keeper",
                ),
            },
            items_at_location={
                "mug_001": GroundedEntity(
                    key="mug_001",
                    display_name="Wooden Mug",
                    entity_type="item",
                ),
            },
            inventory={
                "gold_001": GroundedEntity(
                    key="gold_001",
                    display_name="Gold Coin",
                    entity_type="item",
                ),
            },
            equipped={},
            storages={
                "chest_001": GroundedEntity(
                    key="chest_001",
                    display_name="Wooden Chest",
                    entity_type="storage",
                    short_description="[FIRST TIME]",
                ),
            },
            exits={
                "street_001": GroundedEntity(
                    key="street_001",
                    display_name="Main Street",
                    entity_type="location",
                ),
            },
        )

    def test_contains_key_npc(self, sample_manifest: GroundingManifest):
        """Test contains_key for NPC."""
        assert sample_manifest.contains_key("marcus_001") is True
        assert sample_manifest.contains_key("anna_001") is True

    def test_contains_key_item(self, sample_manifest: GroundingManifest):
        """Test contains_key for items."""
        assert sample_manifest.contains_key("mug_001") is True
        assert sample_manifest.contains_key("gold_001") is True

    def test_contains_key_storage(self, sample_manifest: GroundingManifest):
        """Test contains_key for storage."""
        assert sample_manifest.contains_key("chest_001") is True

    def test_contains_key_exit(self, sample_manifest: GroundingManifest):
        """Test contains_key for exits."""
        assert sample_manifest.contains_key("street_001") is True

    def test_contains_key_location(self, sample_manifest: GroundingManifest):
        """Test contains_key for current location."""
        assert sample_manifest.contains_key("tavern_001") is True

    def test_contains_key_player(self, sample_manifest: GroundingManifest):
        """Test contains_key for player."""
        assert sample_manifest.contains_key("player_001") is True

    def test_contains_key_missing(self, sample_manifest: GroundingManifest):
        """Test contains_key returns False for missing keys."""
        assert sample_manifest.contains_key("nonexistent_001") is False
        assert sample_manifest.contains_key("") is False
        assert sample_manifest.contains_key("random_key") is False

    def test_all_keys(self, sample_manifest: GroundingManifest):
        """Test all_keys returns all valid keys."""
        keys = sample_manifest.all_keys()
        assert "marcus_001" in keys
        assert "anna_001" in keys
        assert "mug_001" in keys
        assert "gold_001" in keys
        assert "chest_001" in keys
        assert "street_001" in keys
        assert "tavern_001" in keys
        assert "player_001" in keys
        assert len(keys) == 8

    def test_all_entities(self, sample_manifest: GroundingManifest):
        """Test all_entities returns flat dict."""
        entities = sample_manifest.all_entities()
        assert "marcus_001" in entities
        assert "mug_001" in entities
        assert entities["marcus_001"].display_name == "Marcus"

    def test_get_entity_exists(self, sample_manifest: GroundingManifest):
        """Test get_entity for existing entity."""
        entity = sample_manifest.get_entity("marcus_001")
        assert entity is not None
        assert entity.display_name == "Marcus"

    def test_get_entity_missing(self, sample_manifest: GroundingManifest):
        """Test get_entity returns None for missing key."""
        entity = sample_manifest.get_entity("nonexistent_001")
        assert entity is None

    def test_format_for_prompt(self, sample_manifest: GroundingManifest):
        """Test format_for_prompt generates readable output."""
        output = sample_manifest.format_for_prompt()
        assert "## ENTITY REFERENCES" in output
        assert "[key:text]" in output
        assert "marcus_001" in output
        assert "Marcus" in output
        assert "mug_001" in output
        assert "**NPCs at location:**" in output
        assert "**Items at location:**" in output


# =============================================================================
# GroundingValidator Tests
# =============================================================================


class TestGroundingValidator:
    """Tests for GroundingValidator."""

    @pytest.fixture
    def validator(self) -> GroundingValidator:
        """Create validator with sample manifest."""
        manifest = GroundingManifest(
            location_key="tavern_001",
            location_display="Tavern",
            player_key="player_001",
            player_display="You",
            npcs={
                "marcus_001": GroundedEntity(
                    key="marcus_001",
                    display_name="Marcus",
                    entity_type="npc",
                ),
            },
            items_at_location={
                "sword_001": GroundedEntity(
                    key="sword_001",
                    display_name="Iron Sword",
                    entity_type="item",
                ),
            },
            inventory={},
            equipped={},
            storages={},
            exits={},
        )
        return GroundingValidator(manifest)

    def test_validate_valid_references(self, validator: GroundingValidator):
        """Test validation passes for valid [key:text] references."""
        text = "[marcus_001:Marcus] waves at you. You pick up [sword_001:the iron sword]."
        result = validator.validate(text)
        assert result.valid is True
        assert len(result.invalid_keys) == 0
        assert len(result.unkeyed_mentions) == 0

    def test_validate_invalid_key(self, validator: GroundingValidator):
        """Test validation catches invalid keys."""
        text = "[nonexistent_001:Someone] waves at you."
        result = validator.validate(text)
        assert result.valid is False
        assert len(result.invalid_keys) == 1
        assert result.invalid_keys[0].key == "nonexistent_001"

    def test_validate_unkeyed_mention_full_name(self, validator: GroundingValidator):
        """Test validation catches unkeyed entity mentions (full name)."""
        text = "Marcus waves at you from across the room."
        result = validator.validate(text)
        assert result.valid is False
        assert len(result.unkeyed_mentions) == 1
        assert result.unkeyed_mentions[0].expected_key == "marcus_001"
        assert result.unkeyed_mentions[0].display_name == "Marcus"

    def test_validate_unkeyed_mention_partial_name(self, validator: GroundingValidator):
        """Test validation catches partial name mentions for items."""
        text = "The iron sword gleams in the light."
        result = validator.validate(text)
        assert result.valid is False
        # Should detect "sword" as partial match for "Iron Sword"
        assert len(result.unkeyed_mentions) >= 1

    def test_validate_mixed_valid_invalid(self, validator: GroundingValidator):
        """Test validation with mix of valid and invalid references."""
        text = "[marcus_001:Marcus] hands you [fake_001:something]."
        result = validator.validate(text)
        assert result.valid is False
        assert len(result.invalid_keys) == 1
        # marcus_001 was used properly so shouldn't be in unkeyed_mentions

    def test_validate_no_entities(self, validator: GroundingValidator):
        """Test validation passes when no entities mentioned."""
        text = "The sun sets over the horizon. Birds chirp in the distance."
        result = validator.validate(text)
        assert result.valid is True

    def test_error_feedback_format(self, validator: GroundingValidator):
        """Test error_feedback produces readable output."""
        text = "[fake_001:Someone] and Marcus are talking."
        result = validator.validate(text)
        feedback = result.error_feedback()
        assert "Invalid keys" in feedback or "Unkeyed" in feedback
        assert "Please fix" in feedback


# =============================================================================
# Key Pattern Tests
# =============================================================================


class TestKeyPattern:
    """Tests for KEY_PATTERN regex."""

    def test_matches_simple_key(self):
        """Test pattern matches simple [key:text]."""
        text = "[marcus_001:Marcus]"
        matches = KEY_PATTERN.findall(text)
        assert len(matches) == 1
        assert matches[0] == ("marcus_001", "Marcus")

    def test_matches_key_with_longer_text(self):
        """Test pattern matches [key:longer text]."""
        text = "[sword_001:the iron sword]"
        matches = KEY_PATTERN.findall(text)
        assert len(matches) == 1
        assert matches[0] == ("sword_001", "the iron sword")

    def test_matches_multiple_keys(self):
        """Test pattern matches multiple keys in text."""
        text = "[marcus_001:Marcus] gives [sword_001:a sword] to you."
        matches = KEY_PATTERN.findall(text)
        assert len(matches) == 2
        assert ("marcus_001", "Marcus") in matches
        assert ("sword_001", "a sword") in matches

    def test_no_match_without_colon(self):
        """Test pattern doesn't match [key] without colon."""
        text = "[marcus_001]"
        matches = KEY_PATTERN.findall(text)
        assert len(matches) == 0

    def test_no_match_with_spaces_in_key(self):
        """Test pattern doesn't match keys with spaces."""
        text = "[marcus 001:Marcus]"
        matches = KEY_PATTERN.findall(text)
        assert len(matches) == 0


# =============================================================================
# strip_key_references Tests
# =============================================================================


class TestStripKeyReferences:
    """Tests for strip_key_references function."""

    def test_strip_single_reference(self):
        """Test stripping single [key:text] reference."""
        text = "[marcus_001:Marcus] waves at you."
        result = strip_key_references(text)
        assert result == "Marcus waves at you."

    def test_strip_multiple_references(self):
        """Test stripping multiple references."""
        text = "[marcus_001:Marcus] hands you [sword_001:the iron sword]."
        result = strip_key_references(text)
        assert result == "Marcus hands you the iron sword."

    def test_strip_preserves_other_brackets(self):
        """Test stripping preserves non-key brackets."""
        text = "[OOC] This is [marcus_001:Marcus]."
        result = strip_key_references(text)
        assert result == "[OOC] This is Marcus."

    def test_strip_no_references(self):
        """Test stripping text with no references."""
        text = "Just a normal sentence."
        result = strip_key_references(text)
        assert result == "Just a normal sentence."

    def test_strip_empty_string(self):
        """Test stripping empty string."""
        result = strip_key_references("")
        assert result == ""

    def test_strip_reference_at_start(self):
        """Test stripping reference at start of sentence."""
        text = "[sword_001:The gleaming sword] catches your eye."
        result = strip_key_references(text)
        assert result == "The gleaming sword catches your eye."

    def test_strip_preserves_capitalization(self):
        """Test stripping preserves text capitalization."""
        text = "[marcus_001:MARCUS] SHOUTS AT YOU."
        result = strip_key_references(text)
        assert result == "MARCUS SHOUTS AT YOU."


# =============================================================================
# GroundingValidationResult Tests
# =============================================================================


class TestGroundingValidationResult:
    """Tests for GroundingValidationResult model."""

    def test_valid_result(self):
        """Test valid result properties."""
        result = GroundingValidationResult(valid=True)
        assert result.valid is True
        assert result.error_count == 0
        assert result.error_feedback() == ""

    def test_invalid_result_with_keys(self):
        """Test invalid result with invalid keys."""
        result = GroundingValidationResult(
            valid=False,
            invalid_keys=[
                InvalidKeyReference(
                    key="fake_001",
                    text="Someone",
                    position=0,
                    context="[fake_001:Someone]...",
                )
            ],
        )
        assert result.valid is False
        assert result.error_count == 1
        feedback = result.error_feedback()
        assert "fake_001" in feedback
        assert "Invalid keys" in feedback

    def test_invalid_result_with_unkeyed(self):
        """Test invalid result with unkeyed mentions."""
        result = GroundingValidationResult(
            valid=False,
            unkeyed_mentions=[
                UnkeyedMention(
                    expected_key="marcus_001",
                    display_name="Marcus",
                    position=0,
                    context="Marcus waves...",
                )
            ],
        )
        assert result.valid is False
        assert result.error_count == 1
        feedback = result.error_feedback()
        assert "Marcus" in feedback
        assert "marcus_001" in feedback
