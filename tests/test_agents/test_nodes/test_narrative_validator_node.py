"""Tests for narrative_validator_node - specifically plot hook fallback behavior."""

import pytest
from unittest.mock import MagicMock

from src.agents.nodes.narrative_validator_node import (
    _handle_plot_hook_missing,
    MAX_RETRY_COUNT,
)
from src.oracle.complication_types import ItemSpawnResult, ItemSpawnDecision


class TestHandlePlotHookMissing:
    """Tests for _handle_plot_hook_missing function."""

    @pytest.mark.asyncio
    async def test_max_retries_falls_back_to_spawn(self):
        """When max retries exceeded, should signal fallback to normal spawn."""
        plot_hooks = [
            ItemSpawnResult(
                item_name="mysterious_key",
                decision=ItemSpawnDecision.PLOT_HOOK_MISSING,
                reasoning="Testing fallback",
                plot_hook_description="A key that should be mysteriously absent",
            )
        ]
        validator = MagicMock()

        result = await _handle_plot_hook_missing(
            plot_hooks=plot_hooks,
            validator=validator,
            retry_count=MAX_RETRY_COUNT,  # At max
            new_facts=[],
        )

        # Should not have errors
        assert "errors" not in result

        # Should signal fallback
        assert result["narrative_validation_result"]["is_valid"] is True
        assert result["narrative_validation_result"]["fallback_to_spawn"] is True
        assert "plot_hook_fallback_items" in result
        assert len(result["plot_hook_fallback_items"]) == 1
        assert result["plot_hook_fallback_items"][0].item_name == "mysterious_key"

    @pytest.mark.asyncio
    async def test_retries_remaining_triggers_renarration(self):
        """When retries remain, should trigger re-narration."""
        plot_hooks = [
            ItemSpawnResult(
                item_name="mysterious_key",
                decision=ItemSpawnDecision.PLOT_HOOK_MISSING,
                reasoning="Testing retry",
                plot_hook_description="A missing key creates intrigue",
            )
        ]
        validator = MagicMock()

        result = await _handle_plot_hook_missing(
            plot_hooks=plot_hooks,
            validator=validator,
            retry_count=0,  # Still have retries
            new_facts=[],
        )

        # Should signal re-narration
        assert result.get("_route_to_narrator") is True
        assert result["narrative_retry_count"] == 1
        # Should include constraints for the narrator
        assert "narrative_constraints" in result
        assert "mysterious_key" in result["narrative_constraints"]

    @pytest.mark.asyncio
    async def test_multiple_items_fallback(self):
        """Multiple plot hook items should all be included in fallback."""
        plot_hooks = [
            ItemSpawnResult(
                item_name="wooden_bucket",
                decision=ItemSpawnDecision.PLOT_HOOK_MISSING,
                reasoning="Bucket is missing",
                plot_hook_description="The well bucket is gone",
            ),
            ItemSpawnResult(
                item_name="lantern",
                decision=ItemSpawnDecision.PLOT_HOOK_MISSING,
                reasoning="Lantern mysteriously absent",
                plot_hook_description="No light source here",
            ),
        ]
        validator = MagicMock()

        result = await _handle_plot_hook_missing(
            plot_hooks=plot_hooks,
            validator=validator,
            retry_count=MAX_RETRY_COUNT,  # At max
            new_facts=[],
        )

        # All items should be in fallback
        assert len(result["plot_hook_fallback_items"]) == 2
        item_names = [h.item_name for h in result["plot_hook_fallback_items"]]
        assert "wooden_bucket" in item_names
        assert "lantern" in item_names

    @pytest.mark.asyncio
    async def test_fallback_preserves_plot_hook_description(self):
        """Fallback items should preserve their plot hook descriptions."""
        plot_hooks = [
            ItemSpawnResult(
                item_name="father_straw_hat",
                decision=ItemSpawnDecision.PLOT_HOOK_MISSING,
                reasoning="Creates mystery",
                plot_hook_description="Father's hat is nowhere to be found",
            )
        ]
        validator = MagicMock()

        result = await _handle_plot_hook_missing(
            plot_hooks=plot_hooks,
            validator=validator,
            retry_count=MAX_RETRY_COUNT,
            new_facts=[],
        )

        fallback_item = result["plot_hook_fallback_items"][0]
        assert fallback_item.plot_hook_description == "Father's hat is nowhere to be found"
