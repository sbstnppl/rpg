"""Tests for PreGenerationCache."""

import asyncio
import pytest
from datetime import datetime, timedelta

from src.world_server.cache import PreGenerationCache
from src.world_server.schemas import AnticipationMetrics, PreGeneratedScene


def create_scene(location_key: str, expiry_seconds: int = 300) -> PreGeneratedScene:
    """Helper to create test scenes."""
    return PreGeneratedScene(
        location_key=location_key,
        location_display_name=f"Test {location_key}",
        scene_manifest={"location": location_key},
        npcs_present=[],
        items_present=[],
        furniture=[],
        atmosphere={},
        expiry_seconds=expiry_seconds,
    )


def create_stale_scene(location_key: str) -> PreGeneratedScene:
    """Helper to create a stale scene."""
    scene = create_scene(location_key, expiry_seconds=300)
    scene.generated_at = datetime.now() - timedelta(seconds=400)
    return scene


class TestPreGenerationCache:
    """Tests for PreGenerationCache class."""

    @pytest.mark.asyncio
    async def test_put_and_get(self):
        """Test basic put and get operations."""
        cache = PreGenerationCache(max_size=5)
        scene = create_scene("tavern")

        await cache.put(scene)
        result = await cache.get("tavern")

        assert result is not None
        assert result.location_key == "tavern"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self):
        """Test getting a nonexistent key returns None."""
        cache = PreGenerationCache(max_size=5)
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_stale_returns_none(self):
        """Test getting a stale entry returns None and evicts it."""
        cache = PreGenerationCache(max_size=5)
        scene = create_stale_scene("tavern")

        await cache.put(scene)
        result = await cache.get("tavern")

        assert result is None
        # Should be evicted
        assert await cache.contains("tavern") is False

    @pytest.mark.asyncio
    async def test_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = PreGenerationCache(max_size=3)

        await cache.put(create_scene("loc1"))
        await cache.put(create_scene("loc2"))
        await cache.put(create_scene("loc3"))

        # Cache is now full, adding loc4 should evict loc1 (oldest)
        await cache.put(create_scene("loc4"))

        assert await cache.contains("loc1") is False
        assert await cache.contains("loc2") is True
        assert await cache.contains("loc3") is True
        assert await cache.contains("loc4") is True

    @pytest.mark.asyncio
    async def test_lru_order_updated_on_get(self):
        """Test that get updates LRU order."""
        cache = PreGenerationCache(max_size=3)

        await cache.put(create_scene("loc1"))
        await cache.put(create_scene("loc2"))
        await cache.put(create_scene("loc3"))

        # Access loc1, making it most recently used
        await cache.get("loc1")

        # Adding loc4 should now evict loc2 (oldest after loc1 was accessed)
        await cache.put(create_scene("loc4"))

        assert await cache.contains("loc1") is True
        assert await cache.contains("loc2") is False
        assert await cache.contains("loc3") is True
        assert await cache.contains("loc4") is True

    @pytest.mark.asyncio
    async def test_invalidate(self):
        """Test invalidating a specific entry."""
        cache = PreGenerationCache(max_size=5)
        await cache.put(create_scene("tavern"))
        await cache.put(create_scene("market"))

        result = await cache.invalidate("tavern")

        assert result is True
        assert await cache.contains("tavern") is False
        assert await cache.contains("market") is True

    @pytest.mark.asyncio
    async def test_invalidate_nonexistent(self):
        """Test invalidating a nonexistent entry returns False."""
        cache = PreGenerationCache(max_size=5)
        result = await cache.invalidate("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_invalidate_all_except(self):
        """Test invalidating all entries except one."""
        cache = PreGenerationCache(max_size=5)
        await cache.put(create_scene("loc1"))
        await cache.put(create_scene("loc2"))
        await cache.put(create_scene("loc3"))

        count = await cache.invalidate_all_except("loc2")

        assert count == 2
        assert await cache.contains("loc1") is False
        assert await cache.contains("loc2") is True
        assert await cache.contains("loc3") is False

    @pytest.mark.asyncio
    async def test_invalidate_all(self):
        """Test invalidating all entries."""
        cache = PreGenerationCache(max_size=5)
        await cache.put(create_scene("loc1"))
        await cache.put(create_scene("loc2"))

        count = await cache.invalidate_all_except(None)

        assert count == 2
        keys = await cache.keys()
        assert len(keys) == 0

    @pytest.mark.asyncio
    async def test_clear(self):
        """Test clearing the entire cache."""
        cache = PreGenerationCache(max_size=5)
        await cache.put(create_scene("loc1"))
        await cache.put(create_scene("loc2"))

        count = await cache.clear()

        assert count == 2
        keys = await cache.keys()
        assert len(keys) == 0

    @pytest.mark.asyncio
    async def test_cleanup_stale(self):
        """Test cleaning up stale entries."""
        cache = PreGenerationCache(max_size=5)
        await cache.put(create_scene("fresh"))
        await cache.put(create_stale_scene("stale1"))
        await cache.put(create_stale_scene("stale2"))

        count = await cache.cleanup_stale()

        assert count == 2
        assert await cache.contains("fresh") is True
        assert await cache.contains("stale1") is False
        assert await cache.contains("stale2") is False

    @pytest.mark.asyncio
    async def test_contains(self):
        """Test contains check."""
        cache = PreGenerationCache(max_size=5)
        await cache.put(create_scene("tavern"))

        assert await cache.contains("tavern") is True
        assert await cache.contains("nonexistent") is False

    @pytest.mark.asyncio
    async def test_contains_stale_returns_false(self):
        """Test contains returns False for stale entries."""
        cache = PreGenerationCache(max_size=5)
        await cache.put(create_stale_scene("stale"))

        assert await cache.contains("stale") is False

    @pytest.mark.asyncio
    async def test_keys(self):
        """Test getting all cache keys."""
        cache = PreGenerationCache(max_size=5)
        await cache.put(create_scene("loc1"))
        await cache.put(create_scene("loc2"))
        await cache.put(create_scene("loc3"))

        keys = await cache.keys()

        assert len(keys) == 3
        assert "loc1" in keys
        assert "loc2" in keys
        assert "loc3" in keys

    @pytest.mark.asyncio
    async def test_stats(self):
        """Test getting cache statistics."""
        cache = PreGenerationCache(max_size=5)
        await cache.put(create_scene("loc1"))
        await cache.put(create_scene("loc2"))

        stats = await cache.stats()

        assert stats["size"] == 2
        assert stats["max_size"] == 5
        assert len(stats["entries"]) == 2

    @pytest.mark.asyncio
    async def test_update_existing_entry(self):
        """Test updating an existing entry."""
        cache = PreGenerationCache(max_size=5)

        scene1 = create_scene("tavern")
        scene1.scene_manifest = {"version": 1}
        await cache.put(scene1)

        scene2 = create_scene("tavern")
        scene2.scene_manifest = {"version": 2}
        await cache.put(scene2)

        result = await cache.get("tavern")
        assert result.scene_manifest["version"] == 2

    @pytest.mark.asyncio
    async def test_metrics_cache_hit(self):
        """Test metrics are updated on cache hit."""
        metrics = AnticipationMetrics()
        cache = PreGenerationCache(max_size=5, metrics=metrics)

        await cache.put(create_scene("tavern"))
        await cache.get("tavern")

        assert metrics.cache_hits == 1

    @pytest.mark.asyncio
    async def test_metrics_wasted_generation(self):
        """Test wasted generation is tracked."""
        metrics = AnticipationMetrics()
        cache = PreGenerationCache(max_size=2, metrics=metrics)

        # Fill cache
        await cache.put(create_scene("loc1"))
        await cache.put(create_scene("loc2"))

        # Force eviction of loc1 (never used)
        await cache.put(create_scene("loc3"))

        assert metrics.generations_wasted == 1

    @pytest.mark.asyncio
    async def test_on_evict_callback(self):
        """Test eviction callback is called."""
        evicted = []

        def on_evict(scene: PreGeneratedScene):
            evicted.append(scene.location_key)

        cache = PreGenerationCache(max_size=2, on_evict=on_evict)

        await cache.put(create_scene("loc1"))
        await cache.put(create_scene("loc2"))
        await cache.put(create_scene("loc3"))  # Evicts loc1

        assert "loc1" in evicted

    @pytest.mark.asyncio
    async def test_concurrent_access(self):
        """Test cache handles concurrent access correctly."""
        cache = PreGenerationCache(max_size=10)

        async def put_and_get(key: str):
            await cache.put(create_scene(key))
            await asyncio.sleep(0.01)
            return await cache.get(key)

        # Run multiple concurrent operations
        tasks = [put_and_get(f"loc{i}") for i in range(5)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(r is not None for r in results)
        assert len(await cache.keys()) == 5
