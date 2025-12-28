"""Tests for ConstrainedNarrator - narrative-friendly error messages.

These tests verify that technical failure messages are converted to
narrative-friendly prose for the player.
"""

import pytest

from src.narrator.narrator import (
    ConstrainedNarrator,
    _convert_failed_action_to_narrative,
    FAILED_ACTION_TEMPLATES,
)


# =============================================================================
# Test _convert_failed_action_to_narrative
# =============================================================================


class TestConvertFailedActionToNarrative:
    """Tests for the failed action conversion helper."""

    def test_social_action_talk_proper_noun(self) -> None:
        """Talk action with proper noun target (Baker)."""
        result = _convert_failed_action_to_narrative(
            action_type="talk",
            target="Baker",
            reason="'Baker' is not here.",
        )
        assert result == "You look around but don't see Baker here."
        # Should NOT add article for proper nouns (starts with uppercase)
        assert "the Baker" not in result

    def test_social_action_talk_common_noun(self) -> None:
        """Talk action with common noun target (baker)."""
        result = _convert_failed_action_to_narrative(
            action_type="talk",
            target="baker",
            reason="'baker' is not here.",
        )
        assert result == "You look around but don't see the baker here."

    def test_item_action_take(self) -> None:
        """Take action with item target."""
        result = _convert_failed_action_to_narrative(
            action_type="take",
            target="sword",
            reason="'sword' is not here.",
        )
        assert result == "You don't see the sword here to take."

    def test_item_action_with_quoted_target(self) -> None:
        """Target with quotes should have quotes stripped."""
        result = _convert_failed_action_to_narrative(
            action_type="take",
            target="'golden key'",
            reason="'golden key' is not here.",
        )
        # Quotes should be stripped from target
        assert "'" not in result or result.count("'") == 1  # only the contraction "don't"
        assert "golden key" in result

    def test_consumption_action_eat(self) -> None:
        """Eat action with food target."""
        result = _convert_failed_action_to_narrative(
            action_type="eat",
            target="bread",
            reason="'bread' is not in inventory.",
        )
        assert result == "You don't have the bread to eat."

    def test_consumption_action_drink(self) -> None:
        """Drink action with beverage target."""
        result = _convert_failed_action_to_narrative(
            action_type="drink",
            target="ale",
            reason="'ale' is not in inventory.",
        )
        assert result == "You don't have the ale to drink."

    def test_combat_action_attack(self) -> None:
        """Attack action with NPC target."""
        result = _convert_failed_action_to_narrative(
            action_type="attack",
            target="Goblin",
            reason="'Goblin' is not here.",
        )
        assert result == "You look around but don't see Goblin to attack."

    def test_movement_action_move(self) -> None:
        """Move action with location target."""
        result = _convert_failed_action_to_narrative(
            action_type="move",
            target="forest",
            reason="Cannot reach 'forest' from here.",
        )
        assert result == "You can't go to the forest from here."

    def test_unknown_action_type_fallback(self) -> None:
        """Unknown action type uses default template."""
        result = _convert_failed_action_to_narrative(
            action_type="dance",
            target="partner",
            reason="'partner' is not here.",
        )
        assert result == "You can't do that with the partner - it's not here."

    def test_target_with_existing_article(self) -> None:
        """Target already having an article should not get another."""
        result = _convert_failed_action_to_narrative(
            action_type="take",
            target="the old sword",
            reason="'the old sword' is not here.",
        )
        # Should NOT say "the the old sword"
        assert "the the" not in result
        assert "the old sword" in result

    def test_give_action(self) -> None:
        """Give action with recipient target."""
        result = _convert_failed_action_to_narrative(
            action_type="give",
            target="merchant",
            reason="'merchant' is not here.",
        )
        assert result == "You look around but don't see the merchant to give that to."


# =============================================================================
# Test ConstrainedNarrator._extract_facts with failed actions
# =============================================================================


class TestExtractFactsWithFailedActions:
    """Tests that _extract_facts converts failed actions correctly."""

    def test_failed_action_converted_to_narrative(self) -> None:
        """Failed actions should be converted to narrative-friendly facts."""
        narrator = ConstrainedNarrator()

        turn_result = {
            "executions": [],
            "failed_actions": [
                {
                    "action": {"type": "talk", "target": "Baker"},
                    "reason": "'Baker' is not here.",
                }
            ],
        }

        facts = narrator._extract_facts(turn_result)

        # Should NOT contain technical FAILED prefix
        assert len(facts) == 1
        assert not facts[0].startswith("FAILED")
        assert "Baker" in facts[0]
        assert "don't see" in facts[0]

    def test_multiple_failed_actions(self) -> None:
        """Multiple failed actions should all be converted."""
        narrator = ConstrainedNarrator()

        turn_result = {
            "executions": [],
            "failed_actions": [
                {
                    "action": {"type": "talk", "target": "Baker"},
                    "reason": "'Baker' is not here.",
                },
                {
                    "action": {"type": "take", "target": "bread"},
                    "reason": "'bread' is not here.",
                },
            ],
        }

        facts = narrator._extract_facts(turn_result)

        assert len(facts) == 2
        # None should contain FAILED prefix
        for fact in facts:
            assert not fact.startswith("FAILED")

    def test_mixed_success_and_failure(self) -> None:
        """Successful and failed actions should both appear."""
        narrator = ConstrainedNarrator()

        turn_result = {
            "executions": [
                {
                    "action": {"type": "look"},
                    "success": True,
                    "outcome": "You look around the tavern.",
                    "state_changes": [],
                    "metadata": {},
                }
            ],
            "failed_actions": [
                {
                    "action": {"type": "talk", "target": "Baker"},
                    "reason": "'Baker' is not here.",
                }
            ],
        }

        facts = narrator._extract_facts(turn_result)

        assert len(facts) == 2
        assert any("look around" in f for f in facts)
        assert any("don't see" in f for f in facts)


# =============================================================================
# Test fallback narration
# =============================================================================


class TestFallbackNarration:
    """Tests for _fallback_narrate with narrative-friendly facts."""

    def test_fallback_handles_narrative_friendly_facts(self) -> None:
        """Fallback narration works with new narrative-friendly format."""
        narrator = ConstrainedNarrator()

        facts = [
            "You look around but don't see Baker here."
        ]

        result = narrator._fallback_narrate(facts)

        # Should capitalize and work correctly
        assert result.startswith("You look around")
        assert "Baker" in result
        assert result.endswith(".")

    def test_fallback_joins_multiple_facts(self) -> None:
        """Multiple narrative-friendly facts are joined properly."""
        narrator = ConstrainedNarrator()

        facts = [
            "You enter the tavern.",
            "You look around but don't see the baker here.",
        ]

        result = narrator._fallback_narrate(facts)

        assert "enter the tavern" in result
        assert "don't see the baker" in result


# =============================================================================
# Regression test: ensure FAILED never appears in output
# =============================================================================


class TestNoFailedInOutput:
    """Regression tests ensuring FAILED never appears in narrative output."""

    @pytest.mark.asyncio
    async def test_narrate_without_llm_no_failed_prefix(self) -> None:
        """Narration without LLM should not expose FAILED prefix."""
        narrator = ConstrainedNarrator(llm_provider=None)

        turn_result = {
            "executions": [],
            "failed_actions": [
                {
                    "action": {"type": "talk", "target": "Baker"},
                    "reason": "'Baker' is not here.",
                }
            ],
        }

        result = await narrator.narrate(turn_result)

        # The narrative should NEVER contain "FAILED"
        assert "FAILED" not in result.narrative
        assert "failed" not in result.narrative.lower() or "failed" in result.narrative.lower().replace("you look around but don't see", "")
        # Should be narrative-friendly
        assert "Baker" in result.narrative

    @pytest.mark.asyncio
    async def test_facts_passed_to_llm_are_narrative_friendly(self) -> None:
        """Facts extracted for LLM prompt should be narrative-friendly."""
        narrator = ConstrainedNarrator(llm_provider=None)

        turn_result = {
            "executions": [],
            "failed_actions": [
                {
                    "action": {"type": "attack", "target": "Goblin"},
                    "reason": "'Goblin' is not here.",
                }
            ],
        }

        result = await narrator.narrate(turn_result)

        # Check facts_included doesn't have FAILED prefix
        for fact in result.facts_included:
            assert not fact.startswith("FAILED"), f"Fact has FAILED prefix: {fact}"
