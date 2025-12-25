"""Tests for GM narrative cleanup functionality.

The GM LLM sometimes outputs structured markdown sections instead of pure prose.
These tests verify the cleanup logic strips that formatting while preserving
the actual narrative content.
"""

import pytest


class TestCleanNarrative:
    """Tests for the _clean_narrative method on GMNode."""

    def test_clean_narrative_passes_through_unchanged(self):
        """Pure prose narrative should pass through without modification."""
        from src.gm.gm_node import GMNode

        narrative = "You step into the cottage and find a warm fire crackling in the hearth. The smell of fresh bread fills the air."

        result = GMNode._clean_narrative_static(narrative)

        assert result == narrative

    def test_strips_response_header(self):
        """**Response:** header should be stripped."""
        from src.gm.gm_node import GMNode

        narrative = """**Response:**
You step into the cottage and find a warm fire crackling in the hearth."""

        result = GMNode._clean_narrative_static(narrative)

        assert result == "You step into the cottage and find a warm fire crackling in the hearth."
        assert "**Response:**" not in result

    def test_strips_updated_inventory_section(self):
        """**Updated Inventory:** section should be stripped entirely."""
        from src.gm.gm_node import GMNode

        narrative = """You open the chest and find some fresh clothes inside.

**Updated Inventory (Finn):**
- `clean_shirt_001`: Clean Linen Shirt
- `clean_breeches_001`: Clean Breeches"""

        result = GMNode._clean_narrative_static(narrative)

        assert result == "You open the chest and find some fresh clothes inside."
        assert "Updated Inventory" not in result
        assert "clean_shirt_001" not in result

    def test_strips_new_storage_container_section(self):
        """**New Storage Container:** section should be stripped entirely."""
        from src.gm.gm_node import GMNode

        narrative = """You notice a wooden chest near the foot of the bed.

**New Storage Container:**
- `clothes_chest_001`: Wooden Chest containing personal belongings"""

        result = GMNode._clean_narrative_static(narrative)

        assert result == "You notice a wooden chest near the foot of the bed."
        assert "Storage Container" not in result

    def test_strips_multiple_sections(self):
        """Multiple markdown sections should all be stripped."""
        from src.gm.gm_node import GMNode

        narrative = """**Response:**
You step back into the cottage and make your way to a wooden chest near the foot of the bed.

**Updated Inventory (Finn):**
- `clean_shirt_001`: Clean Linen Shirt
- `clean_breeches_001`: Clean Breeches

**New Storage Container:**
- `clothes_chest_001`: Wooden Chest"""

        result = GMNode._clean_narrative_static(narrative)

        assert result == "You step back into the cottage and make your way to a wooden chest near the foot of the bed."
        assert "**" not in result
        assert "-" not in result or result.count("-") == 0  # No bullet points

    def test_preserves_hyphen_in_prose(self):
        """Hyphens in prose (like hyphenated words) should be preserved."""
        from src.gm.gm_node import GMNode

        narrative = "The well-worn path leads to a half-hidden door."

        result = GMNode._clean_narrative_static(narrative)

        assert result == narrative
        assert "well-worn" in result
        assert "half-hidden" in result

    def test_strips_hash_headers(self):
        """Markdown ## headers should be stripped."""
        from src.gm.gm_node import GMNode

        narrative = """## Response

You find yourself in a dimly lit room."""

        result = GMNode._clean_narrative_static(narrative)

        assert result == "You find yourself in a dimly lit room."
        assert "##" not in result

    def test_strips_bullet_lists_at_line_start(self):
        """Lines starting with bullet markers should be stripped."""
        from src.gm.gm_node import GMNode

        narrative = """You search the room and find:
- A rusty key
- Some old coins
* A torn map"""

        result = GMNode._clean_narrative_static(narrative)

        # Should strip bullet list entirely, keeping only prose
        assert "A rusty key" not in result or "- A rusty key" not in result
        assert result.strip() == "You search the room and find:"

    def test_handles_empty_string(self):
        """Empty string should return empty string."""
        from src.gm.gm_node import GMNode

        result = GMNode._clean_narrative_static("")

        assert result == ""

    def test_handles_whitespace_only(self):
        """Whitespace-only string should return empty string."""
        from src.gm.gm_node import GMNode

        result = GMNode._clean_narrative_static("   \n\n   ")

        assert result == ""

    def test_strips_numbered_lists(self):
        """Numbered lists should be stripped."""
        from src.gm.gm_node import GMNode

        narrative = """You inventory your belongings:
1. A worn leather satchel
2. Three silver coins
3. A small knife"""

        result = GMNode._clean_narrative_static(narrative)

        assert "1." not in result
        assert "2." not in result
        assert result.strip() == "You inventory your belongings:"

    def test_preserves_multiline_prose(self):
        """Multiple paragraphs of prose should be preserved."""
        from src.gm.gm_node import GMNode

        narrative = """You step into the tavern. The room is filled with the sounds of laughter and clinking mugs.

A burly man at the bar looks up as you enter. He nods in greeting before returning to his drink."""

        result = GMNode._clean_narrative_static(narrative)

        assert result == narrative

    def test_strips_backtick_entity_references(self):
        """Backtick-wrapped entity keys in lists should be stripped with the list."""
        from src.gm.gm_node import GMNode

        narrative = """You pick up the items.

**Items Added:**
- `sword_001`: Iron Sword
- `shield_001`: Wooden Shield"""

        result = GMNode._clean_narrative_static(narrative)

        assert result == "You pick up the items."
        assert "`sword_001`" not in result
