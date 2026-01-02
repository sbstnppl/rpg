"""Tests for player location handling in game commands."""

import pytest
from unittest.mock import MagicMock

from src.cli.commands.game import _get_player_current_location


class TestGetPlayerCurrentLocation:
    """Tests for _get_player_current_location helper."""

    def test_returns_npc_extension_location(self):
        """Should return current_location from npc_extension."""
        player = MagicMock()
        player.npc_extension = MagicMock()
        player.npc_extension.current_location = "village_square"

        result = _get_player_current_location(player)
        assert result == "village_square"

    def test_returns_fallback_when_no_extension(self):
        """Should return fallback when no npc_extension."""
        player = MagicMock()
        player.npc_extension = None

        result = _get_player_current_location(player, fallback="tavern_main")
        assert result == "tavern_main"

    def test_returns_fallback_when_location_is_none(self):
        """Should return fallback when current_location is None."""
        player = MagicMock()
        player.npc_extension = MagicMock()
        player.npc_extension.current_location = None

        result = _get_player_current_location(player, fallback="tavern_main")
        assert result == "tavern_main"

    def test_returns_fallback_when_location_is_empty(self):
        """Should return fallback when current_location is empty string."""
        player = MagicMock()
        player.npc_extension = MagicMock()
        player.npc_extension.current_location = ""

        result = _get_player_current_location(player, fallback="tavern_main")
        assert result == "tavern_main"

    def test_returns_default_when_no_fallback(self):
        """Should return 'starting_location' when no fallback provided."""
        player = MagicMock()
        player.npc_extension = None

        result = _get_player_current_location(player)
        assert result == "starting_location"

    def test_prefers_db_over_fallback(self):
        """Should prefer DB location over fallback even when fallback provided."""
        player = MagicMock()
        player.npc_extension = MagicMock()
        player.npc_extension.current_location = "market_square"

        result = _get_player_current_location(player, fallback="tavern_main")
        assert result == "market_square"
