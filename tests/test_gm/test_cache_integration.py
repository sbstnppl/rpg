"""Tests for GM cache integration with World Server.

Tests verify that:
- Cache check happens before expensive LLM generation
- Pre-generated scenes are used when available
- Cache misses fall through to normal generation
- Disabled anticipation skips the cache check
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.database.models.enums import EntityType
from src.gm.gm_node import GMNode
from src.gm.schemas import GMResponse
from src.world_server.schemas import CollapseResult, PredictionReason
from tests.factories import create_entity, create_location


class TestGMCacheCheck:
    """Tests for _check_pre_generated_scene method."""

    @pytest.mark.asyncio
    async def test_returns_none_when_anticipation_disabled(
        self, db_session, game_session
    ):
        """When anticipation is disabled, cache check should return None."""
        player = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.PLAYER,
            entity_key="player_001",
            display_name="Finn",
        )
        location = create_location(
            db_session,
            game_session,
            location_key="tavern",
            display_name="The Rusty Tankard",
        )

        gm_node = GMNode(
            db=db_session,
            game_session=game_session,
            player_id=player.id,
            location_key=location.location_key,
        )

        with patch("src.config.settings") as mock_settings:
            mock_settings.anticipation_enabled = False

            result = await gm_node._check_pre_generated_scene(turn_number=1)

            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_cache_miss(self, db_session, game_session):
        """When cache misses, should return None to fall through to LLM."""
        player = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.PLAYER,
            entity_key="player_001",
            display_name="Finn",
        )
        location = create_location(
            db_session,
            game_session,
            location_key="tavern",
            display_name="The Rusty Tankard",
        )

        gm_node = GMNode(
            db=db_session,
            game_session=game_session,
            player_id=player.id,
            location_key=location.location_key,
        )

        with patch("src.config.settings") as mock_settings:
            mock_settings.anticipation_enabled = True

            with patch(
                "src.world_server.integration.get_world_server_manager"
            ) as mock_get_manager:
                mock_manager = MagicMock()
                mock_manager.check_pre_generated = AsyncMock(return_value=None)
                mock_get_manager.return_value = mock_manager

                result = await gm_node._check_pre_generated_scene(turn_number=1)

                assert result is None
                mock_manager.check_pre_generated.assert_called_once_with(
                    location.location_key, 1
                )

    @pytest.mark.asyncio
    async def test_returns_gm_response_on_cache_hit(self, db_session, game_session):
        """When cache hits, should return GMResponse from cached data."""
        player = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.PLAYER,
            entity_key="player_001",
            display_name="Finn",
        )
        location = create_location(
            db_session,
            game_session,
            location_key="tavern",
            display_name="The Rusty Tankard",
        )

        gm_node = GMNode(
            db=db_session,
            game_session=game_session,
            player_id=player.id,
            location_key=location.location_key,
        )

        # Create a mock CollapseResult
        mock_collapse = CollapseResult(
            location_key="tavern",
            narrator_manifest={
                "location_key": "tavern",
                "location_display_name": "The Rusty Tankard",
                "npcs": [
                    {"entity_key": "barkeep_001", "display_name": "Old Tom"},
                ],
                "items": [],
                "furniture": [],
                "atmosphere": {"description": "Warm and smoky."},
                "scene_manifest": {"description": "A cozy tavern."},
            },
            was_pre_generated=True,
            latency_ms=5.0,
            cache_age_seconds=10.0,
            prediction_reason=PredictionReason.ADJACENT,
        )

        with patch("src.config.settings") as mock_settings:
            mock_settings.anticipation_enabled = True

            with patch(
                "src.world_server.integration.get_world_server_manager"
            ) as mock_get_manager:
                mock_manager = MagicMock()
                mock_manager.check_pre_generated = AsyncMock(return_value=mock_collapse)
                mock_get_manager.return_value = mock_manager

                result = await gm_node._check_pre_generated_scene(turn_number=1)

                assert result is not None
                assert isinstance(result, GMResponse)
                assert result.narrative == "A cozy tavern."
                assert "barkeep_001" in result.referenced_entities
                assert result.is_ooc is False


class TestCollapseResultToResponse:
    """Tests for _collapse_result_to_response method."""

    def test_uses_scene_description_when_available(self, db_session, game_session):
        """Should use scene description from manifest."""
        player = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.PLAYER,
        )
        location = create_location(db_session, game_session)

        gm_node = GMNode(
            db=db_session,
            game_session=game_session,
            player_id=player.id,
            location_key=location.location_key,
        )

        mock_collapse = CollapseResult(
            location_key="tavern",
            narrator_manifest={
                "location_display_name": "Tavern",
                "npcs": [],
                "items": [],
                "atmosphere": {},
                "scene_manifest": {"description": "The tavern is lively tonight."},
            },
            was_pre_generated=True,
            latency_ms=1.0,
        )

        result = gm_node._collapse_result_to_response(mock_collapse)

        assert result.narrative == "The tavern is lively tonight."

    def test_synthesizes_narrative_when_description_missing(
        self, db_session, game_session
    ):
        """Should synthesize narrative when scene description is empty."""
        player = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.PLAYER,
        )
        location = create_location(db_session, game_session)

        gm_node = GMNode(
            db=db_session,
            game_session=game_session,
            player_id=player.id,
            location_key=location.location_key,
        )

        mock_collapse = CollapseResult(
            location_key="market",
            narrator_manifest={
                "location_display_name": "Market Square",
                "npcs": [{"display_name": "Merchant Bob", "entity_key": "bob_001"}],
                "items": [],
                "atmosphere": {"description": "Busy and noisy."},
                "scene_manifest": {},  # No description
            },
            was_pre_generated=True,
            latency_ms=1.0,
        )

        result = gm_node._collapse_result_to_response(mock_collapse)

        assert "Market Square" in result.narrative
        assert "Merchant Bob" in result.narrative
        assert "Busy and noisy" in result.narrative

    def test_extracts_npc_keys_for_referenced_entities(
        self, db_session, game_session
    ):
        """Should extract NPC entity keys for referenced_entities."""
        player = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.PLAYER,
        )
        location = create_location(db_session, game_session)

        gm_node = GMNode(
            db=db_session,
            game_session=game_session,
            player_id=player.id,
            location_key=location.location_key,
        )

        mock_collapse = CollapseResult(
            location_key="guild",
            narrator_manifest={
                "location_display_name": "Adventurer's Guild",
                "npcs": [
                    {"display_name": "Guildmaster", "entity_key": "guildmaster_001"},
                    {"display_name": "Receptionist", "entity_key": "receptionist_001"},
                ],
                "items": [],
                "atmosphere": {},
                "scene_manifest": {"description": "The guild hall."},
            },
            was_pre_generated=True,
            latency_ms=1.0,
        )

        result = gm_node._collapse_result_to_response(mock_collapse)

        assert "guildmaster_001" in result.referenced_entities
        assert "receptionist_001" in result.referenced_entities


class TestSynthesizeSceneNarrative:
    """Tests for _synthesize_scene_narrative method."""

    def test_basic_location_only(self, db_session, game_session):
        """Should create narrative with just location name."""
        player = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.PLAYER,
        )
        location = create_location(db_session, game_session)

        gm_node = GMNode(
            db=db_session,
            game_session=game_session,
            player_id=player.id,
            location_key=location.location_key,
        )

        manifest = {
            "location_display_name": "The Library",
            "npcs": [],
            "items": [],
            "atmosphere": {},
        }

        result = gm_node._synthesize_scene_narrative(manifest)

        assert result == "You are at The Library."

    def test_includes_atmosphere(self, db_session, game_session):
        """Should include atmosphere description."""
        player = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.PLAYER,
        )
        location = create_location(db_session, game_session)

        gm_node = GMNode(
            db=db_session,
            game_session=game_session,
            player_id=player.id,
            location_key=location.location_key,
        )

        manifest = {
            "location_display_name": "The Library",
            "npcs": [],
            "items": [],
            "atmosphere": {"description": "Dusty tomes line the walls."},
        }

        result = gm_node._synthesize_scene_narrative(manifest)

        assert "The Library" in result
        assert "Dusty tomes line the walls." in result

    def test_single_npc(self, db_session, game_session):
        """Should format single NPC correctly."""
        player = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.PLAYER,
        )
        location = create_location(db_session, game_session)

        gm_node = GMNode(
            db=db_session,
            game_session=game_session,
            player_id=player.id,
            location_key=location.location_key,
        )

        manifest = {
            "location_display_name": "The Inn",
            "npcs": [{"display_name": "Innkeeper"}],
            "items": [],
            "atmosphere": {},
        }

        result = gm_node._synthesize_scene_narrative(manifest)

        assert "Innkeeper is here." in result

    def test_two_npcs(self, db_session, game_session):
        """Should format two NPCs with 'and'."""
        player = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.PLAYER,
        )
        location = create_location(db_session, game_session)

        gm_node = GMNode(
            db=db_session,
            game_session=game_session,
            player_id=player.id,
            location_key=location.location_key,
        )

        manifest = {
            "location_display_name": "The Inn",
            "npcs": [
                {"display_name": "Innkeeper"},
                {"display_name": "Bard"},
            ],
            "items": [],
            "atmosphere": {},
        }

        result = gm_node._synthesize_scene_narrative(manifest)

        assert "Innkeeper and Bard are here." in result

    def test_three_npcs(self, db_session, game_session):
        """Should format three NPCs with Oxford comma."""
        player = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.PLAYER,
        )
        location = create_location(db_session, game_session)

        gm_node = GMNode(
            db=db_session,
            game_session=game_session,
            player_id=player.id,
            location_key=location.location_key,
        )

        manifest = {
            "location_display_name": "The Inn",
            "npcs": [
                {"display_name": "Innkeeper"},
                {"display_name": "Bard"},
                {"display_name": "Traveler"},
            ],
            "items": [],
            "atmosphere": {},
        }

        result = gm_node._synthesize_scene_narrative(manifest)

        assert "Innkeeper, Bard, and Traveler are here." in result

    def test_visible_items(self, db_session, game_session):
        """Should include visible items."""
        player = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.PLAYER,
        )
        location = create_location(db_session, game_session)

        gm_node = GMNode(
            db=db_session,
            game_session=game_session,
            player_id=player.id,
            location_key=location.location_key,
        )

        manifest = {
            "location_display_name": "The Armory",
            "npcs": [],
            "items": [
                {"display_name": "Rusty Sword", "is_visible": True},
                {"display_name": "Hidden Dagger", "is_visible": False},
            ],
            "atmosphere": {},
        }

        result = gm_node._synthesize_scene_narrative(manifest)

        assert "Rusty Sword" in result
        assert "Hidden Dagger" not in result
