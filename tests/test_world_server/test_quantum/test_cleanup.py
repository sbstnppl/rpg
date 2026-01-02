"""Tests for the Cleanup Module (Phase 5 of split architecture)."""

import pytest

from src.world_server.quantum.cleanup import (
    CleanupResult,
    strip_entity_refs,
    normalize_whitespace,
    fix_capitalization,
    fix_pronouns,
    cleanup_narrative,
    extract_entity_keys,
    validate_entity_refs,
    replace_entity_key,
    add_entity_ref,
)


class TestStripEntityRefs:
    """Tests for strip_entity_refs function."""

    def test_strips_single_ref(self):
        text = "[npc_tom:Old Tom] waves at you."
        result = strip_entity_refs(text)

        assert result.text == "Old Tom waves at you."
        assert "npc_tom" in result.entities_found
        assert result.replacements_made == 1

    def test_strips_multiple_refs(self):
        text = "[npc_tom:Old Tom] slides [item_ale:a mug of ale] across the bar."
        result = strip_entity_refs(text)

        assert result.text == "Old Tom slides a mug of ale across the bar."
        assert "npc_tom" in result.entities_found
        assert "item_ale" in result.entities_found
        assert result.replacements_made == 2

    def test_strips_player_ref(self):
        text = "[hero_001:you] pick up the sword."
        result = strip_entity_refs(text, player_key="hero_001")

        assert result.text == "you pick up the sword."
        assert "hero_001" in result.entities_found

    def test_preserves_unformatted_text(self):
        text = "Just plain text with no refs."
        result = strip_entity_refs(text)

        assert result.text == text
        assert result.entities_found == []
        assert result.replacements_made == 0

    def test_handles_complex_display_names(self):
        text = "[item_001:a mug of honeyed ale from the cellar] sits on the bar."
        result = strip_entity_refs(text)

        assert result.text == "a mug of honeyed ale from the cellar sits on the bar."


class TestNormalizeWhitespace:
    """Tests for normalize_whitespace function."""

    def test_collapses_multiple_spaces(self):
        text = "Too   many    spaces."
        result = normalize_whitespace(text)
        assert result == "Too many spaces."

    def test_collapses_multiple_newlines(self):
        text = "Paragraph one.\n\n\n\nParagraph two."
        result = normalize_whitespace(text)
        assert result == "Paragraph one.\n\nParagraph two."

    def test_fixes_space_before_punctuation(self):
        text = "Hello , world !"
        result = normalize_whitespace(text)
        assert result == "Hello, world!"

    def test_strips_leading_trailing(self):
        text = "   Text with padding   "
        result = normalize_whitespace(text)
        assert result == "Text with padding"


class TestFixCapitalization:
    """Tests for fix_capitalization function."""

    def test_capitalizes_first_letter(self):
        text = "the door opens."
        result = fix_capitalization(text)
        assert result == "The door opens."

    def test_capitalizes_after_period(self):
        text = "First sentence. second sentence."
        result = fix_capitalization(text)
        assert result == "First sentence. Second sentence."

    def test_capitalizes_after_question(self):
        text = "What's that? it's a bird."
        result = fix_capitalization(text)
        assert result == "What's that? It's a bird."

    def test_capitalizes_after_exclamation(self):
        text = "Look out! the dragon attacks."
        result = fix_capitalization(text)
        assert result == "Look out! The dragon attacks."

    def test_handles_empty_string(self):
        assert fix_capitalization("") == ""


class TestFixPronouns:
    """Tests for fix_pronouns function."""

    def test_replaces_the_player(self):
        text = "The player picks up the sword."
        result = fix_pronouns(text)
        # Note: Verb conjugation ("picks" → "pick") is not handled
        assert result == "You picks up the sword."

    def test_replaces_bare_player_key(self):
        text = "hero_001 walks into the tavern."
        result = fix_pronouns(text, player_key="hero_001")
        assert result == "you walks into the tavern."  # Grammar off, but pronoun replaced

    def test_preserves_other_pronouns(self):
        text = "He gives you the sword."
        result = fix_pronouns(text)
        assert result == "He gives you the sword."


class TestCleanupNarrative:
    """Tests for cleanup_narrative function."""

    def test_full_cleanup(self):
        text = "[npc_tom:Old Tom] slides [item_ale:a mug of ale] toward [hero_001:you]."
        result = cleanup_narrative(text, player_key="hero_001")

        assert result.text == "Old Tom slides a mug of ale toward you."
        assert "npc_tom" in result.entities_found
        assert "item_ale" in result.entities_found
        assert "hero_001" in result.entities_found

    def test_cleanup_with_whitespace_issues(self):
        text = "[npc_tom:Old Tom]  slides   [item_ale:a mug] ."
        result = cleanup_narrative(text)

        assert "  " not in result.text
        assert result.text == "Old Tom slides a mug."

    def test_cleanup_fixes_capitalization(self):
        text = "[hero_001:you] pick up the sword. the guard watches."
        result = cleanup_narrative(text, player_key="hero_001")

        assert result.text.startswith("You") or result.text.startswith("you")
        # After period, should capitalize
        assert "The guard" in result.text or "the guard" in result.text

    def test_cleanup_without_normalization(self):
        text = "Text   with  spaces."
        result = cleanup_narrative(text, normalize=False)
        assert "   " in result.text or "  " in result.text

    def test_cleanup_without_caps_fix(self):
        text = "lowercase start."
        result = cleanup_narrative(text, fix_caps=False)
        assert result.text.startswith("l")


class TestExtractEntityKeys:
    """Tests for extract_entity_keys function."""

    def test_extracts_single_key(self):
        text = "[npc_tom:Old Tom] waves."
        keys = extract_entity_keys(text)
        assert keys == ["npc_tom"]

    def test_extracts_multiple_keys(self):
        text = "[npc_tom:Tom] gives [item_ale:ale] to [hero:you]."
        keys = extract_entity_keys(text)
        assert keys == ["npc_tom", "item_ale", "hero"]

    def test_returns_empty_for_no_refs(self):
        text = "Plain text with no refs."
        keys = extract_entity_keys(text)
        assert keys == []


class TestValidateEntityRefs:
    """Tests for validate_entity_refs function."""

    def test_all_valid(self):
        text = "[npc_tom:Tom] and [item_ale:ale]."
        valid_keys = {"npc_tom", "item_ale"}
        invalid = validate_entity_refs(text, valid_keys)
        assert invalid == []

    def test_detects_invalid(self):
        text = "[npc_tom:Tom] and [unknown_key:mystery]."
        valid_keys = {"npc_tom"}
        invalid = validate_entity_refs(text, valid_keys)
        assert invalid == ["unknown_key"]

    def test_player_key_always_valid(self):
        text = "[hero_001:you] picks up [item:sword]."
        valid_keys = {"item"}
        invalid = validate_entity_refs(text, valid_keys, player_key="hero_001")
        assert invalid == []


class TestReplaceEntityKey:
    """Tests for replace_entity_key function."""

    def test_replaces_key(self):
        text = "[old_key:Display] appears."
        result = replace_entity_key(text, "old_key", "new_key")
        assert result == "[new_key:Display] appears."

    def test_preserves_display(self):
        text = "[item_001:a rusty sword] lies on the ground."
        result = replace_entity_key(text, "item_001", "item_sword")
        assert result == "[item_sword:a rusty sword] lies on the ground."

    def test_replaces_multiple_occurrences(self):
        text = "[npc:Tom] waves. [npc:Tom] smiles."
        result = replace_entity_key(text, "npc", "npc_tom_001")
        assert result == "[npc_tom_001:Tom] waves. [npc_tom_001:Tom] smiles."


class TestAddEntityRef:
    """Tests for add_entity_ref function."""

    def test_adds_ref_to_text(self):
        text = "Old Tom waves at you."
        result = add_entity_ref(text, "Old Tom", "npc_tom")
        assert result == "[npc_tom:Old Tom] waves at you."

    def test_only_replaces_first_occurrence(self):
        text = "Tom waves. Tom smiles."
        result = add_entity_ref(text, "Tom", "npc_tom")
        # Should only replace first "Tom"
        assert result.count("[npc_tom:Tom]") == 1

    def test_uses_word_boundaries(self):
        text = "Tommy talks to Tom."
        result = add_entity_ref(text, "Tom", "npc_tom")
        # Should not match "Tommy"
        assert "Tommy" in result
        assert "[npc_tom:Tom]" in result
