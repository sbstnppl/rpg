"""Tests for StateCollapseManager."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.database.models.world import Location
from src.world_server.cache import PreGenerationCache
from src.world_server.collapse import StateCollapseManager
from src.world_server.schemas import (
    AnticipationMetrics,
    PreGeneratedScene,
    PredictionReason,
)


def create_pre_gen_scene(
    location_key: str,
    expiry_seconds: int = 300,
) -> PreGeneratedScene:
    """Helper to create test pre-generated scenes."""
    return PreGeneratedScene(
        location_key=location_key,
        location_display_name=f"Test {location_key.title()}",
        scene_manifest={"location": location_key, "test": True},
        npcs_present=[{"entity_key": "bartender", "display_name": "Bartender"}],
        items_present=[{"item_key": "mug", "display_name": "Mug"}],
        furniture=[{"type": "bar", "description": "A wooden bar"}],
        atmosphere={"lighting": "dim", "noise": "moderate"},
        prediction_reason=PredictionReason.ADJACENT,
        expiry_seconds=expiry_seconds,
    )


class TestStateCollapseManager:
    """Tests for StateCollapseManager class."""

    @pytest.mark.asyncio
    async def test_collapse_cache_hit(self, db_session, game_session):
        """Test collapsing with a cache hit."""
        # Setup cache with pre-generated scene
        metrics = AnticipationMetrics()
        cache = PreGenerationCache(max_size=5, metrics=metrics)
        scene = create_pre_gen_scene("tavern")
        await cache.put(scene)

        # Create location in DB
        location = Location(
            session_id=game_session.id,
            location_key="tavern",
            display_name="The Rusty Anchor",
            description="A cozy tavern",
        )
        db_session.add(location)
        db_session.flush()

        # Collapse
        manager = StateCollapseManager(db_session, game_session, cache, metrics)
        result = await manager.collapse_location("tavern", turn_number=1)

        assert result.was_pre_generated is True
        assert result.location_key == "tavern"
        assert result.cache_age_seconds is not None
        assert result.latency_ms < 1000  # Should be fast
        assert result.prediction_reason == PredictionReason.ADJACENT
        assert "npcs" in result.narrator_manifest

    @pytest.mark.asyncio
    async def test_collapse_cache_miss(self, db_session, game_session):
        """Test collapsing with a cache miss falls back to sync generation."""
        metrics = AnticipationMetrics()
        cache = PreGenerationCache(max_size=5, metrics=metrics)

        # Create location in DB but no cache entry
        location = Location(
            session_id=game_session.id,
            location_key="ruins",
            display_name="Ancient Ruins",
            description="Crumbling stone structures",
        )
        db_session.add(location)
        db_session.flush()

        manager = StateCollapseManager(db_session, game_session, cache, metrics)

        # Mock the synchronous generation to avoid calling actual LLM
        with patch.object(
            manager, "_generate_synchronous", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = {
                "location_key": "ruins",
                "location_display_name": "Ancient Ruins",
                "npcs": [],
                "items": [],
                "furniture": [],
                "atmosphere": {},
            }

            result = await manager.collapse_location("ruins", turn_number=1)

            assert result.was_pre_generated is False
            assert result.location_key == "ruins"
            assert result.generation_time_ms is not None
            mock_gen.assert_called_once_with("ruins", 1)

        # Check metrics recorded cache miss
        assert metrics.cache_misses == 1

    @pytest.mark.asyncio
    async def test_collapse_stale_cache_entry(self, db_session, game_session):
        """Test that stale cache entries trigger fallback."""
        metrics = AnticipationMetrics()
        cache = PreGenerationCache(max_size=5, metrics=metrics)

        # Create stale scene
        scene = create_pre_gen_scene("tavern", expiry_seconds=300)
        scene.generated_at = datetime.now() - timedelta(seconds=400)
        await cache.put(scene)

        # Create location
        location = Location(
            session_id=game_session.id,
            location_key="tavern",
            display_name="Tavern",
            description="A local tavern",
        )
        db_session.add(location)
        db_session.flush()

        manager = StateCollapseManager(db_session, game_session, cache, metrics)

        with patch.object(
            manager, "_generate_synchronous", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = {"location_key": "tavern", "npcs": []}

            result = await manager.collapse_location("tavern", turn_number=1)

            # Should have fallen back to sync generation
            assert result.was_pre_generated is False
            mock_gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_collapse_updates_location_tracking(self, db_session, game_session):
        """Test that collapse updates location visit tracking."""
        metrics = AnticipationMetrics()
        cache = PreGenerationCache(max_size=5, metrics=metrics)
        scene = create_pre_gen_scene("market")
        await cache.put(scene)

        # Create location with no visit tracking
        location = Location(
            session_id=game_session.id,
            location_key="market",
            display_name="Market Square",
            description="A busy market",
            first_visited_turn=None,
            last_visited_turn=None,
        )
        db_session.add(location)
        db_session.flush()

        manager = StateCollapseManager(db_session, game_session, cache, metrics)
        await manager.collapse_location("market", turn_number=5)

        # Refresh location from DB
        db_session.refresh(location)

        assert location.first_visited_turn == 5
        assert location.last_visited_turn == 5

    @pytest.mark.asyncio
    async def test_collapse_updates_existing_visit_tracking(
        self, db_session, game_session
    ):
        """Test that collapse preserves first visit and updates last visit."""
        metrics = AnticipationMetrics()
        cache = PreGenerationCache(max_size=5, metrics=metrics)
        scene = create_pre_gen_scene("home")
        await cache.put(scene)

        # Create location with existing visit tracking
        location = Location(
            session_id=game_session.id,
            location_key="home",
            display_name="Home",
            description="A cozy home",
            first_visited_turn=1,
            last_visited_turn=3,
        )
        db_session.add(location)
        db_session.flush()

        manager = StateCollapseManager(db_session, game_session, cache, metrics)
        await manager.collapse_location("home", turn_number=10)

        db_session.refresh(location)

        # First visit should be preserved
        assert location.first_visited_turn == 1
        # Last visit should be updated
        assert location.last_visited_turn == 10

    @pytest.mark.asyncio
    async def test_collapse_invalidates_cache_entry(self, db_session, game_session):
        """Test that collapse removes the used entry from cache."""
        metrics = AnticipationMetrics()
        cache = PreGenerationCache(max_size=5, metrics=metrics)
        scene = create_pre_gen_scene("garden")
        await cache.put(scene)

        # Create location
        location = Location(
            session_id=game_session.id,
            location_key="garden",
            display_name="Garden",
            description="A peaceful garden",
        )
        db_session.add(location)
        db_session.flush()

        assert await cache.contains("garden") is True

        manager = StateCollapseManager(db_session, game_session, cache, metrics)
        await manager.collapse_location("garden", turn_number=1)

        # Cache entry should be removed after use
        assert await cache.contains("garden") is False

    @pytest.mark.asyncio
    async def test_collapse_marks_scene_committed(self, db_session, game_session):
        """Test that collapse marks the scene as committed."""
        metrics = AnticipationMetrics()
        cache = PreGenerationCache(max_size=5, metrics=metrics)
        scene = create_pre_gen_scene("street")
        await cache.put(scene)

        location = Location(
            session_id=game_session.id,
            location_key="street",
            display_name="Street",
            description="A quiet street",
        )
        db_session.add(location)
        db_session.flush()

        assert scene.is_committed is False

        manager = StateCollapseManager(db_session, game_session, cache, metrics)
        await manager.collapse_location("street", turn_number=1)

        assert scene.is_committed is True

    @pytest.mark.asyncio
    async def test_check_and_collapse(self, db_session, game_session):
        """Test the convenience check_and_collapse method."""
        metrics = AnticipationMetrics()
        cache = PreGenerationCache(max_size=5, metrics=metrics)
        scene = create_pre_gen_scene("inn")
        await cache.put(scene)

        location = Location(
            session_id=game_session.id,
            location_key="inn",
            display_name="Inn",
            description="A roadside inn",
        )
        db_session.add(location)
        db_session.flush()

        manager = StateCollapseManager(db_session, game_session, cache, metrics)
        manifest, was_pre_gen = await manager.check_and_collapse("inn", turn_number=1)

        assert was_pre_gen is True
        assert manifest["location_key"] == "inn"

    @pytest.mark.asyncio
    async def test_get_cache_status(self, db_session, game_session):
        """Test getting cache status."""
        metrics = AnticipationMetrics()
        metrics.cache_hits = 5
        metrics.cache_misses = 2
        cache = PreGenerationCache(max_size=10, metrics=metrics)

        manager = StateCollapseManager(db_session, game_session, cache, metrics)
        status = manager.get_cache_status("tavern")

        assert status["location_key"] == "tavern"
        assert status["cache_max_size"] == 10
        assert "hit_rate" in status["metrics"]

    @pytest.mark.asyncio
    async def test_narrator_manifest_structure(self, db_session, game_session):
        """Test that narrator manifest has correct structure."""
        metrics = AnticipationMetrics()
        cache = PreGenerationCache(max_size=5, metrics=metrics)
        scene = create_pre_gen_scene("library")
        await cache.put(scene)

        location = Location(
            session_id=game_session.id,
            location_key="library",
            display_name="Library",
            description="A dusty library",
        )
        db_session.add(location)
        db_session.flush()

        manager = StateCollapseManager(db_session, game_session, cache, metrics)
        result = await manager.collapse_location("library", turn_number=1)

        manifest = result.narrator_manifest

        # Check required fields
        assert "location_key" in manifest
        assert "location_display_name" in manifest
        assert "npcs" in manifest
        assert "items" in manifest
        assert "furniture" in manifest
        assert "atmosphere" in manifest
        assert "scene_manifest" in manifest
        assert "was_pre_generated" in manifest

        # Check values from pre-generated scene
        assert manifest["location_key"] == "library"
        assert manifest["was_pre_generated"] is True
        assert len(manifest["npcs"]) == 1
        assert manifest["npcs"][0]["entity_key"] == "bartender"

    @pytest.mark.asyncio
    async def test_collapse_with_no_location_in_db(self, db_session, game_session):
        """Test collapse when location doesn't exist in DB."""
        metrics = AnticipationMetrics()
        cache = PreGenerationCache(max_size=5, metrics=metrics)
        scene = create_pre_gen_scene("unknown")
        await cache.put(scene)

        # No location in DB

        manager = StateCollapseManager(db_session, game_session, cache, metrics)
        result = await manager.collapse_location("unknown", turn_number=1)

        # Should still work, just won't update location tracking
        assert result.was_pre_generated is True
        assert result.location_key == "unknown"
