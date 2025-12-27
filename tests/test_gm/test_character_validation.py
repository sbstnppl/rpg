"""Unit tests for character break detection.

These tests verify that the _detect_character_break method catches
patterns that indicate the LLM is responding as an AI assistant
rather than staying in character as the Game Master.
"""
import pytest
from src.gm.gm_node import GMNode


class TestCharacterBreakDetection:
    """Tests for _detect_character_break static method."""

    # ===========================================================================
    # Tool Output Exposure Tests
    # ===========================================================================

    def test_detects_tool_output_leak_what_would_you_like(self):
        """Detect 'What would you like me to do' pattern."""
        text = "What would you like me to do with these rules?"
        is_broken, pattern = GMNode._detect_character_break(text)
        assert is_broken
        assert "what would you like" in pattern

    def test_detects_tool_output_leak_provided_text(self):
        """Detect 'The provided text' pattern."""
        text = "The provided text outlines rules for handling NPC dialogue."
        is_broken, pattern = GMNode._detect_character_break(text)
        assert is_broken
        assert "the provided text" in pattern

    def test_detects_rules_for_handling(self):
        """Detect 'rules for handling' pattern."""
        text = "These are the rules for handling combat in the game."
        is_broken, pattern = GMNode._detect_character_break(text)
        assert is_broken

    def test_detects_rules_for_managing(self):
        """Detect 'rules for managing' pattern."""
        text = "I'll follow the rules for managing NPC attitudes."
        is_broken, pattern = GMNode._detect_character_break(text)
        assert is_broken

    def test_detects_let_me_know_if(self):
        """Detect 'let me know if' pattern."""
        text = "Let me know if you need more information."
        is_broken, pattern = GMNode._detect_character_break(text)
        assert is_broken

    def test_detects_would_you_like_me_to(self):
        """Detect 'would you like me to' pattern."""
        text = "Would you like me to explain this further?"
        is_broken, pattern = GMNode._detect_character_break(text)
        assert is_broken

    def test_detects_for_clarification(self):
        """Detect 'for clarification' pattern."""
        text = "I'll ask for clarification on that point."
        is_broken, pattern = GMNode._detect_character_break(text)
        assert is_broken

    def test_detects_to_ensure_i_address(self):
        """Detect 'to ensure I address' pattern."""
        text = "To ensure I address your intended need, let me ask..."
        is_broken, pattern = GMNode._detect_character_break(text)
        assert is_broken

    def test_detects_no_specific_question(self):
        """Detect 'no specific question' pattern."""
        text = "Since no specific question is attached, I'll ask..."
        is_broken, pattern = GMNode._detect_character_break(text)
        assert is_broken

    def test_detects_what_do_with_this(self):
        """Detect 'what ... do with this' pattern."""
        text = "What should I do with this information?"
        is_broken, pattern = GMNode._detect_character_break(text)
        assert is_broken

    def test_detects_what_do_with_these(self):
        """Detect 'what ... do with these' pattern."""
        text = "What am I supposed to do with these rules?"
        is_broken, pattern = GMNode._detect_character_break(text)
        assert is_broken

    # ===========================================================================
    # Existing Pattern Tests (AI Self-Identification)
    # ===========================================================================

    def test_detects_im_an_ai(self):
        """Detect 'I'm an AI' pattern."""
        text = "I'm an AI, so I don't have personal experiences."
        is_broken, pattern = GMNode._detect_character_break(text)
        assert is_broken

    def test_detects_as_an_assistant(self):
        """Detect 'as an assistant' pattern."""
        text = "As an assistant, I'm here to help you."
        is_broken, pattern = GMNode._detect_character_break(text)
        assert is_broken

    def test_detects_youre_welcome(self):
        """Detect 'you're welcome' pattern."""
        text = "You're welcome! Is there anything else?"
        is_broken, pattern = GMNode._detect_character_break(text)
        assert is_broken

    def test_detects_happy_to_help(self):
        """Detect 'happy to help' pattern."""
        text = "I'm happy to help you with that!"
        is_broken, pattern = GMNode._detect_character_break(text)
        assert is_broken

    def test_detects_the_player(self):
        """Detect 'the player' pattern (should be 'you')."""
        text = "The player moves north into the forest."
        is_broken, pattern = GMNode._detect_character_break(text)
        assert is_broken

    def test_detects_function_call(self):
        """Detect 'function call' pattern."""
        text = "I need to make a function call to get that information."
        is_broken, pattern = GMNode._detect_character_break(text)
        assert is_broken

    def test_detects_json_block(self):
        """Detect JSON code block pattern."""
        text = 'Here is the result: json{ "key": "value" }'
        is_broken, pattern = GMNode._detect_character_break(text)
        assert is_broken

    def test_detects_next_steps(self):
        """Detect 'next steps' pattern."""
        text = "Next steps: move to the tavern and talk to the barkeep."
        is_broken, pattern = GMNode._detect_character_break(text)
        assert is_broken

    # ===========================================================================
    # Valid Narrative Tests (Should Pass)
    # ===========================================================================

    def test_valid_narrative_passes(self):
        """Normal narrative should pass validation."""
        text = "You approach the hooded traveler. He looks up and nods."
        is_broken, pattern = GMNode._detect_character_break(text)
        assert not is_broken
        assert pattern is None

    def test_valid_combat_narrative_passes(self):
        """Combat narrative should pass validation."""
        text = "The goblin swings its crude club. You dodge just in time."
        is_broken, pattern = GMNode._detect_character_break(text)
        assert not is_broken

    def test_valid_npc_dialogue_passes(self):
        """NPC dialogue should pass validation."""
        text = '"Welcome to the Rusty Tankard," the innkeeper says with a grin.'
        is_broken, pattern = GMNode._detect_character_break(text)
        assert not is_broken

    def test_valid_scene_description_passes(self):
        """Scene description should pass validation."""
        text = (
            "The morning sun filters through dusty windows. "
            "You smell fresh bread from the nearby bakery."
        )
        is_broken, pattern = GMNode._detect_character_break(text)
        assert not is_broken

    def test_valid_skill_check_result_passes(self):
        """Skill check result narrative should pass validation."""
        text = (
            "You focus your concentration and attempt to pick the lock. "
            "With a satisfying click, the mechanism gives way."
        )
        is_broken, pattern = GMNode._detect_character_break(text)
        assert not is_broken

    def test_valid_item_interaction_passes(self):
        """Item interaction narrative should pass validation."""
        text = "You pick up the dusty tome. Its leather binding is cracked with age."
        is_broken, pattern = GMNode._detect_character_break(text)
        assert not is_broken

    # ===========================================================================
    # Edge Cases and False Positive Awareness
    # ===========================================================================

    def test_npc_asking_what_would_you_like_is_caught(self):
        """NPC dialogue with 'what would you like' is caught.

        This is a known false positive we accept for safety.
        The retry mechanism will rephrase it appropriately.
        """
        text = "The innkeeper asks, 'What would you like to drink?'"
        is_broken, pattern = GMNode._detect_character_break(text)
        # We accept this false positive - better safe than leaking tool output
        assert is_broken

    def test_empty_string_passes(self):
        """Empty string should pass (no content to break character)."""
        is_broken, pattern = GMNode._detect_character_break("")
        assert not is_broken
        assert pattern is None

    def test_none_passes(self):
        """None should pass without error."""
        is_broken, pattern = GMNode._detect_character_break(None)
        assert not is_broken
        assert pattern is None

    # ===========================================================================
    # Tool Error Exposure Tests
    # ===========================================================================

    def test_detects_not_in_inventory(self):
        """Detect 'not in inventory' pattern."""
        text = "The item is not in your inventory."
        is_broken, pattern = GMNode._detect_character_break(text)
        assert is_broken
        assert "not in" in pattern

    def test_detects_not_in_your_inventory(self):
        """Detect 'not in your inventory' pattern."""
        text = "The mug is not in your inventory, leaving its presence unaccounted for."
        is_broken, pattern = GMNode._detect_character_break(text)
        assert is_broken

    def test_detects_unable_to_find(self):
        """Detect 'unable to find' pattern."""
        text = "The system was unable to find the specified item."
        is_broken, pattern = GMNode._detect_character_break(text)
        assert is_broken
        assert "unable to" in pattern

    def test_detects_unable_to_locate(self):
        """Detect 'unable to locate' pattern."""
        text = "I was unable to locate the mug in the scene."
        is_broken, pattern = GMNode._detect_character_break(text)
        assert is_broken

    def test_detects_presence_unaccounted(self):
        """Detect 'presence unaccounted' pattern from actual bug."""
        text = "The mug itself is not recognized, leaving its presence unaccounted for."
        is_broken, pattern = GMNode._detect_character_break(text)
        assert is_broken

    def test_detects_left_unaccounted(self):
        """Detect 'left ... unaccounted' pattern."""
        text = "The item was left in an unaccounted state."
        is_broken, pattern = GMNode._detect_character_break(text)
        assert is_broken

    def test_detects_couldnt_find_item(self):
        """Detect 'couldn't find the item' pattern."""
        text = "The tool couldn't find the item in the database."
        is_broken, pattern = GMNode._detect_character_break(text)
        assert is_broken

    def test_detects_is_not_recognized(self):
        """Detect 'is not recognized' pattern from actual bug."""
        text = "The mug itself is not recognized in your inventory."
        is_broken, pattern = GMNode._detect_character_break(text)
        assert is_broken
        assert "is not recognized" in pattern

    def test_valid_narrative_with_find_passes(self):
        """Narrative using 'find' naturally should pass."""
        text = "You search the room but find nothing of interest."
        is_broken, pattern = GMNode._detect_character_break(text)
        assert not is_broken

    def test_valid_narrative_drinking_passes(self):
        """Normal drinking narrative should pass."""
        text = "You raise the mug to your lips, savoring the cool ale."
        is_broken, pattern = GMNode._detect_character_break(text)
        assert not is_broken
