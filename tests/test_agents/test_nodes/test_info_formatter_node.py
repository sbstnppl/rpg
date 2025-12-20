"""Tests for info_formatter_node.

Tests the _convert_to_second_person() function to ensure:
1. "Player " prefix is removed
2. Verb-leading patterns are converted
3. "their" -> "your" works
4. "his/her" referring to NPCs is NOT converted (critical fix)
5. Reflexive pronouns are converted
"""

import pytest

from src.agents.nodes.info_formatter_node import _convert_to_second_person


class TestConvertToSecondPerson:
    """Tests for the _convert_to_second_person function."""

    def test_removes_player_prefix(self):
        """Should remove 'Player ' prefix from facts."""
        result = _convert_to_second_person("Player recalls the past")
        assert result == "You recall the past."

    def test_converts_verb_leading_knows(self):
        """Should convert 'Knows' to 'You know' (stripping optional 'that')."""
        result = _convert_to_second_person("Knows that the door is locked")
        # The regex pattern r"^knows\s+(?:that\s+)?" optionally strips "that "
        assert result == "You know the door is locked."

    def test_converts_verb_leading_is(self):
        """Should convert 'Is' to 'You are'."""
        result = _convert_to_second_person("Is quite hungry")
        assert result == "You are quite hungry."

    def test_converts_verb_leading_has(self):
        """Should convert 'Has' to 'You have'."""
        result = _convert_to_second_person("Has a knife in inventory")
        assert result == "You have a knife in inventory."

    def test_converts_verb_leading_recalls(self):
        """Should convert 'Recalls' to 'You recall' (stripping optional 'that')."""
        result = _convert_to_second_person("Recalls that father is in prison")
        # The regex pattern optionally strips "that "
        assert result == "You recall father is in prison."

    def test_converts_their_to_your(self):
        """Should convert 'their' to 'your'."""
        result = _convert_to_second_person("You check their inventory")
        assert result == "You check your inventory."

    def test_converts_players_to_your(self):
        """Should convert 'Player's' to 'your'."""
        result = _convert_to_second_person("Player's sword is sharp")
        assert result == "Your sword is sharp."

    def test_preserves_her_referring_to_npc(self):
        """CRITICAL: Should NOT convert 'her' when it refers to NPCs.

        This was the bug: 'about her' (mother) was becoming 'about your'.
        """
        result = _convert_to_second_person("You haven't heard about her since leaving")
        assert result == "You haven't heard about her since leaving."
        assert "about your" not in result

    def test_preserves_his_referring_to_npc(self):
        """CRITICAL: Should NOT convert 'his' when it refers to NPCs.

        For example, 'his sword' referring to an NPC should not become 'your sword'.
        """
        result = _convert_to_second_person("The guard draws his sword")
        assert result == "The guard draws his sword."
        assert "your sword" not in result

    def test_preserves_him_referring_to_npc(self):
        """Should NOT convert 'him' when it refers to NPCs."""
        result = _convert_to_second_person("You need to find him")
        assert result == "You need to find him."

    def test_converts_themselves_to_yourself(self):
        """Should convert 'themselves' to 'yourself'.

        Note: 'They' is not converted because it could refer to NPCs.
        Only the reflexive pronoun is converted.
        """
        result = _convert_to_second_person("You hurt themselves")
        assert result == "You hurt yourself."

    def test_converts_themself_to_yourself(self):
        """Should convert 'themself' to 'yourself'.

        Note: 'They' is not converted because it could refer to NPCs.
        Only the reflexive pronoun is converted.
        """
        result = _convert_to_second_person("You hurt themself")
        assert result == "You hurt yourself."

    def test_capitalizes_first_letter(self):
        """Should capitalize the first letter of the result."""
        result = _convert_to_second_person("recalls the past")
        assert result[0].isupper()

    def test_adds_period_if_missing(self):
        """Should add period if missing punctuation."""
        result = _convert_to_second_person("You are hungry")
        assert result.endswith(".")

    def test_preserves_existing_punctuation(self):
        """Should not add period if punctuation exists."""
        result = _convert_to_second_person("You are hungry?")
        assert result == "You are hungry?"
        assert not result.endswith(".?")

    def test_combined_player_prefix_and_verb(self):
        """Should handle both Player prefix and verb conversion."""
        result = _convert_to_second_person("Player knows that the door is locked")
        # After removing "Player ", "knows that" becomes "You know "
        assert result == "You know the door is locked."

    def test_real_world_bug_case(self):
        """Test the actual bug case from gameplay.

        Original output was:
        "he left home two weeks ago after your father's imprisonment
        and hasn't heard any news about your since arriving at the farm"

        With the planner now generating second-person facts, this scenario
        should not occur. But if it does, we should at least not break
        third-party pronoun references.
        """
        # The planner should now generate this correctly:
        good_fact = "You left home two weeks ago after your father's imprisonment and haven't heard any news about your mother since arriving at the farm"
        result = _convert_to_second_person(good_fact)
        assert "about your mother" in result

        # Even if the planner generates "about her", it should be preserved:
        fact_with_her = "You haven't heard any news about her since arriving"
        result = _convert_to_second_person(fact_with_her)
        assert "about her" in result
        assert "about your" not in result

    def test_mother_reference_preserved(self):
        """Ensure references to mother using 'her' are preserved."""
        result = _convert_to_second_person("Your mother left, but you don't know where she went or how to find her")
        assert "find her" in result
        assert "find your" not in result
