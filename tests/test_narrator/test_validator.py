"""Tests for NarratorValidator - Scene-First Architecture Phase 5.

These tests verify:
- Extracting [key:text] references from narrator output
- Validating keys against the manifest
- Detecting unkeyed entity mentions
- Handling edge cases (nested brackets, escaped characters)
"""

import pytest

from src.world.schemas import (
    Atmosphere,
    EntityRef,
    NarratorManifest,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_atmosphere() -> Atmosphere:
    """Create a sample atmosphere for testing."""
    return Atmosphere(
        lighting="dim candlelight",
        lighting_source="candles",
        sounds=["murmured conversations"],
        smells=["wood smoke"],
        temperature="warm",
        overall_mood="cozy",
    )


@pytest.fixture
def sample_manifest(sample_atmosphere: Atmosphere) -> NarratorManifest:
    """Create a sample narrator manifest with entities."""
    return NarratorManifest(
        location_key="tavern_main",
        location_display="The Main Hall",
        entities={
            "bartender_001": EntityRef(
                key="bartender_001",
                display_name="Tom the Bartender",
                entity_type="npc",
                short_description="Tom, polishing glasses",
                pronouns="he/him",
                position="behind the bar",
            ),
            "sarah_001": EntityRef(
                key="sarah_001",
                display_name="Sarah",
                entity_type="npc",
                short_description="Sarah, sitting at a table",
                pronouns="she/her",
                position="at a corner table",
            ),
            "bar_counter": EntityRef(
                key="bar_counter",
                display_name="long oak bar",
                entity_type="furniture",
                short_description="long oak bar counter",
                position="along the back wall",
            ),
            "mug_001": EntityRef(
                key="mug_001",
                display_name="pewter mug",
                entity_type="item",
                short_description="pewter mug of ale",
                position="on the bar",
            ),
        },
        atmosphere=sample_atmosphere,
    )


# =============================================================================
# Key Extraction Tests
# =============================================================================


class TestKeyExtraction:
    """Tests for extracting [key:text] references from text."""

    def test_extract_single_key(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Extracts a single [key:text] reference."""
        from src.narrator.validator import NarratorValidator

        validator = NarratorValidator(sample_manifest)
        text = "You see [bartender_001:Tom] behind the bar."

        keys = validator._extract_key_references(text)

        assert keys == [("bartender_001", 8)]  # (key, position)

    def test_extract_multiple_keys(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Extracts multiple [key:text] references."""
        from src.narrator.validator import NarratorValidator

        validator = NarratorValidator(sample_manifest)
        text = "[bartender_001:Tom] slides a [mug_001:mug] across the [bar_counter:bar]."

        keys = validator._extract_key_references(text)

        assert len(keys) == 3
        assert keys[0][0] == "bartender_001"
        assert keys[1][0] == "mug_001"
        assert keys[2][0] == "bar_counter"

    def test_extract_keys_with_surrounding_text(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Handles keys embedded in flowing prose."""
        from src.narrator.validator import NarratorValidator

        validator = NarratorValidator(sample_manifest)
        text = (
            "Warm candlelight illuminates the [bar_counter:bar] where "
            "[bartender_001:Tom] works. [sarah_001:Sarah] waves from her corner."
        )

        keys = validator._extract_key_references(text)

        assert len(keys) == 3
        key_names = [k[0] for k in keys]
        assert "bar_counter" in key_names
        assert "bartender_001" in key_names
        assert "sarah_001" in key_names

    def test_extract_no_keys(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Returns empty list when no keys present."""
        from src.narrator.validator import NarratorValidator

        validator = NarratorValidator(sample_manifest)
        text = "The tavern is quiet tonight."

        keys = validator._extract_key_references(text)

        assert keys == []

    def test_handles_adjacent_keys(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Correctly parses keys that appear next to each other."""
        from src.narrator.validator import NarratorValidator

        validator = NarratorValidator(sample_manifest)
        text = "[bartender_001:Tom] and [sarah_001:Sarah] talk together."

        keys = validator._extract_key_references(text)

        assert len(keys) == 2


# =============================================================================
# Key Validation Tests
# =============================================================================


class TestKeyValidation:
    """Tests for validating extracted keys against manifest."""

    def test_valid_keys_pass(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Valid keys that exist in manifest pass validation."""
        from src.narrator.validator import NarratorValidator

        validator = NarratorValidator(sample_manifest)
        text = "You see [bartender_001:Tom] standing behind the [bar_counter:bar]."

        result = validator.validate(text)

        assert result.valid is True
        assert len(result.errors) == 0

    def test_invalid_key_fails(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Invalid keys not in manifest cause validation failure."""
        from src.narrator.validator import NarratorValidator

        validator = NarratorValidator(sample_manifest)
        text = "You see [unknown_npc:stranger] sitting at the bar."

        result = validator.validate(text)

        assert result.valid is False
        assert len(result.errors) == 1
        assert result.errors[0].key == "unknown_npc"

    def test_multiple_invalid_keys(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Multiple invalid keys are all reported."""
        from src.narrator.validator import NarratorValidator

        validator = NarratorValidator(sample_manifest)
        text = "[ghost_001:ghost] floats near the [magic_sword:sword]."

        result = validator.validate(text)

        assert result.valid is False
        assert len(result.errors) == 2
        invalid_keys = [e.key for e in result.errors]
        assert "ghost_001" in invalid_keys
        assert "magic_sword" in invalid_keys

    def test_mixed_valid_and_invalid_keys(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Validation catches invalid keys even when valid ones present."""
        from src.narrator.validator import NarratorValidator

        validator = NarratorValidator(sample_manifest)
        text = "[bartender_001:Tom] hands a [magic_potion:potion] to [sarah_001:Sarah]."

        result = validator.validate(text)

        assert result.valid is False
        assert len(result.errors) == 1
        assert result.errors[0].key == "magic_potion"

    def test_includes_context_in_error(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Error includes surrounding context for debugging."""
        from src.narrator.validator import NarratorValidator

        validator = NarratorValidator(sample_manifest)
        text = "A mysterious [unknown_entity:stranger] appears in the shadows."

        result = validator.validate(text)

        assert len(result.errors) == 1
        assert "unknown_entity" in result.errors[0].context


# =============================================================================
# Unkeyed Reference Detection Tests
# =============================================================================


class TestUnkeyedReferenceDetection:
    """Tests for detecting entity mentions without [key:text] format."""

    def test_detects_unkeyed_npc_mention(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Detects when an NPC is mentioned by name without [key:text]."""
        from src.narrator.validator import NarratorValidator

        validator = NarratorValidator(sample_manifest)
        # "Tom the Bartender" is the display_name, should be flagged
        text = "Tom the Bartender waves at you."

        result = validator.validate(text)

        assert result.valid is False
        # Should detect "Tom the Bartender" without key
        unkeyed = [e for e in result.errors if hasattr(e, "display_name")]
        assert len(unkeyed) >= 1

    def test_detects_partial_name_mention(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Detects partial name matches without [key:text]."""
        from src.narrator.validator import NarratorValidator

        validator = NarratorValidator(sample_manifest)
        text = "Sarah looks up from her drink."

        result = validator.validate(text)

        assert result.valid is False

    def test_ignores_correctly_keyed_mentions(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Does not flag properly keyed entity mentions."""
        from src.narrator.validator import NarratorValidator

        validator = NarratorValidator(sample_manifest)
        # With new format, text after key is what's displayed
        text = "[bartender_001:Tom], the friendly bartender, polishes a glass."

        result = validator.validate(text)

        # Should pass because key is used properly
        assert result.valid is True

    def test_ignores_atmosphere_descriptions(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Atmosphere words are not flagged as unkeyed references."""
        from src.narrator.validator import NarratorValidator

        validator = NarratorValidator(sample_manifest)
        text = "Dim candlelight flickers. Wood smoke fills the air."

        result = validator.validate(text)

        assert result.valid is True

    def test_handles_case_insensitivity(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Unkeyed detection is case-insensitive."""
        from src.narrator.validator import NarratorValidator

        validator = NarratorValidator(sample_manifest)
        text = "SARAH shouts across the room."

        result = validator.validate(text)

        assert result.valid is False


# =============================================================================
# Valid Reference Extraction Tests
# =============================================================================


class TestValidReferenceExtraction:
    """Tests for extracting valid entity refs from validated text."""

    def test_returns_valid_references(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Valid keys return their EntityRef objects."""
        from src.narrator.validator import NarratorValidator

        validator = NarratorValidator(sample_manifest)
        text = "[bartender_001:Tom] serves a [mug_001:mug] from behind the [bar_counter:bar]."

        result = validator.validate(text)

        assert result.valid is True
        assert len(result.references) == 3

        ref_keys = [r.key for r in result.references]
        assert "bartender_001" in ref_keys
        assert "mug_001" in ref_keys
        assert "bar_counter" in ref_keys


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and unusual inputs."""

    def test_handles_empty_text(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Empty text passes validation."""
        from src.narrator.validator import NarratorValidator

        validator = NarratorValidator(sample_manifest)

        result = validator.validate("")

        assert result.valid is True
        assert len(result.errors) == 0

    def test_handles_nested_brackets(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Nested brackets are handled (though unusual)."""
        from src.narrator.validator import NarratorValidator

        validator = NarratorValidator(sample_manifest)
        text = "[[bartender_001:Tom]] looks confused."

        # Should extract bartender_001 from inner brackets
        result = validator.validate(text)

        # This is malformed but should not crash
        # Implementation choice: may pass or fail gracefully

    def test_handles_unclosed_bracket(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Unclosed brackets don't cause crash."""
        from src.narrator.validator import NarratorValidator

        validator = NarratorValidator(sample_manifest)
        text = "You see [bartender_001:Tom standing there."

        # Should not crash, may or may not find the key
        result = validator.validate(text)
        # Just verify it doesn't crash

    def test_handles_special_characters_in_key(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Keys with underscores and numbers work correctly."""
        from src.narrator.validator import NarratorValidator

        validator = NarratorValidator(sample_manifest)
        text = "[bartender_001:Tom] and a [mug_001:mug] are here."

        result = validator.validate(text)

        assert result.valid is True

    def test_handles_newlines_and_whitespace(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Text with newlines and extra whitespace is handled."""
        from src.narrator.validator import NarratorValidator

        validator = NarratorValidator(sample_manifest)
        text = """
        The tavern is warm.
        [bartender_001:Tom] stands behind the [bar_counter:bar].

        [sarah_001:Sarah] waves at you.
        """

        result = validator.validate(text)

        assert result.valid is True
        assert len(result.references) == 3


# =============================================================================
# Error Message Tests
# =============================================================================


class TestErrorMessages:
    """Tests for error message formatting."""

    def test_error_messages_are_descriptive(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Error messages help identify the problem."""
        from src.narrator.validator import NarratorValidator

        validator = NarratorValidator(sample_manifest)
        text = "A [mysterious_stranger:stranger] enters."

        result = validator.validate(text)

        assert len(result.errors) == 1
        error_msg = result.error_messages[0]
        assert "mysterious_stranger" in error_msg.lower() or "invalid" in error_msg.lower()

    def test_unkeyed_error_includes_suggestion(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Unkeyed reference errors suggest the correct key."""
        from src.narrator.validator import NarratorValidator

        validator = NarratorValidator(sample_manifest)
        text = "Sarah walks over to the bar."

        result = validator.validate(text)

        assert result.valid is False
        # Should have error that mentions sarah_001
        error_messages = " ".join(result.error_messages)
        assert "sarah" in error_messages.lower()
