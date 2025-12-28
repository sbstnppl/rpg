"""Tests for WorldServerManager integration."""

import pytest
from unittest.mock import AsyncMock, patch

from src.world_server.integration import (
    WorldServerManager,
    get_world_server_manager,
    shutdown_world_server,
)
from src.world_server.schemas import PredictionReason, PreGeneratedScene


def create_test_scene(location_key: str) -> PreGeneratedScene:
    """Create a test pre-generated scene."""
    return PreGeneratedScene(
        location_key=location_key,
        location_display_name=f"Test {location_key.title()}",
        scene_manifest={"test": True},
        npcs_present=[],
        items_present=[],
        furniture=[],
        atmosphere={},
        prediction_reason=PredictionReason.ADJACENT,
    )


class TestWorldServerManager:
    """Tests for WorldServerManager class."""

    def test_initialization(self, db_session, game_session):
        """Test manager initialization."""
        manager = WorldServerManager(
            db=db_session,
            game_session=game_session,
            max_cache_size=5,
            enabled=True,
        )

        assert manager.enabled is True
        assert manager.game_session.id == game_session.id

    def test_initialization_disabled(self, db_session, game_session):
        """Test manager initialization when disabled."""
        manager = WorldServerManager(
            db=db_session,
            game_session=game_session,
            enabled=False,
        )

        assert manager.enabled is False

    @pytest.mark.asyncio
    async def test_trigger_anticipation_disabled(self, db_session, game_session):
        """Test that anticipation does nothing when disabled."""
        manager = WorldServerManager(
            db=db_session,
            game_session=game_session,
            enabled=False,
        )

        # Should return immediately without error
        await manager.trigger_anticipation("tavern")

    @pytest.mark.asyncio
    async def test_trigger_anticipation_no_predictions(
        self, db_session, game_session
    ):
        """Test anticipation with no predicted locations."""
        manager = WorldServerManager(
            db=db_session,
            game_session=game_session,
            enabled=True,
        )

        # No locations in DB, so no predictions
        await manager.trigger_anticipation("nonexistent")

    @pytest.mark.asyncio
    async def test_check_pre_generated_disabled(self, db_session, game_session):
        """Test check returns None when disabled."""
        manager = WorldServerManager(
            db=db_session,
            game_session=game_session,
            enabled=False,
        )

        result = await manager.check_pre_generated("tavern", turn_number=1)
        assert result is None

    @pytest.mark.asyncio
    async def test_check_pre_generated_cache_miss(self, db_session, game_session):
        """Test check returns None on cache miss."""
        manager = WorldServerManager(
            db=db_session,
            game_session=game_session,
            enabled=True,
        )

        # Nothing in cache
        result = await manager.check_pre_generated("tavern", turn_number=1)
        assert result is None

    @pytest.mark.asyncio
    async def test_check_pre_generated_cache_hit(self, db_session, game_session):
        """Test check returns result on cache hit."""
        from src.database.models.world import Location

        # Create location in DB
        location = Location(
            session_id=game_session.id,
            location_key="tavern",
            display_name="Tavern",
            description="A cozy tavern",
        )
        db_session.add(location)
        db_session.flush()

        manager = WorldServerManager(
            db=db_session,
            game_session=game_session,
            enabled=True,
        )

        # Add scene to cache
        scene = create_test_scene("tavern")
        await manager._cache.put(scene)

        result = await manager.check_pre_generated("tavern", turn_number=1)

        assert result is not None
        assert result.location_key == "tavern"
        assert result.was_pre_generated is True

    def test_get_stats(self, db_session, game_session):
        """Test getting statistics."""
        manager = WorldServerManager(
            db=db_session,
            game_session=game_session,
            enabled=True,
        )

        stats = manager.get_stats()

        assert "enabled" in stats
        assert "metrics" in stats
        assert "predictor_stats" in stats
        assert stats["enabled"] is True

    @pytest.mark.asyncio
    async def test_invalidate_cache_specific(self, db_session, game_session):
        """Test invalidating specific cache entry."""
        manager = WorldServerManager(
            db=db_session,
            game_session=game_session,
            enabled=True,
        )

        # Add scenes to cache
        await manager._cache.put(create_test_scene("tavern"))
        await manager._cache.put(create_test_scene("market"))

        count = await manager.invalidate_cache("tavern")

        assert count == 1
        assert await manager._cache.contains("tavern") is False
        assert await manager._cache.contains("market") is True

    @pytest.mark.asyncio
    async def test_invalidate_cache_all(self, db_session, game_session):
        """Test invalidating all cache entries."""
        manager = WorldServerManager(
            db=db_session,
            game_session=game_session,
            enabled=True,
        )

        # Add scenes to cache
        await manager._cache.put(create_test_scene("tavern"))
        await manager._cache.put(create_test_scene("market"))

        count = await manager.invalidate_cache()

        assert count == 2
        assert await manager._cache.contains("tavern") is False
        assert await manager._cache.contains("market") is False

    @pytest.mark.asyncio
    async def test_shutdown(self, db_session, game_session):
        """Test shutdown cleans up resources."""
        manager = WorldServerManager(
            db=db_session,
            game_session=game_session,
            enabled=True,
        )

        # Add scene to cache
        await manager._cache.put(create_test_scene("tavern"))

        await manager.shutdown()

        # Cache should be cleared
        keys = await manager._cache.keys()
        assert len(keys) == 0


class TestGetWorldServerManager:
    """Tests for get_world_server_manager function."""

    @pytest.mark.asyncio
    async def test_creates_new_manager(self, db_session, game_session):
        """Test that function creates a new manager."""
        # Reset singleton
        import src.world_server.integration as integration

        integration._manager = None

        manager = get_world_server_manager(db_session, game_session, enabled=True)

        assert manager is not None
        assert manager.enabled is True

        # Cleanup
        await shutdown_world_server()

    @pytest.mark.asyncio
    async def test_returns_same_manager_for_same_session(
        self, db_session, game_session
    ):
        """Test that same manager is returned for same session."""
        import src.world_server.integration as integration

        integration._manager = None

        manager1 = get_world_server_manager(db_session, game_session, enabled=True)
        manager2 = get_world_server_manager(db_session, game_session, enabled=True)

        assert manager1 is manager2

        # Cleanup
        await shutdown_world_server()
