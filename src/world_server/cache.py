"""LRU cache for pre-generated scenes.

The cache stores pre-generated scenes until:
1. The player observes them (committed to DB)
2. They expire (default 5 minutes)
3. They are evicted due to cache size limits (LRU)
"""

import asyncio
import logging
from collections import OrderedDict
from datetime import datetime
from typing import Callable

from src.world_server.schemas import AnticipationMetrics, PreGeneratedScene

logger = logging.getLogger(__name__)


class PreGenerationCache:
    """LRU cache for pre-generated scenes with expiry support.

    Thread-safe via asyncio.Lock for concurrent access from
    the anticipation engine and game loop.
    """

    def __init__(
        self,
        max_size: int = 10,
        on_evict: Callable[[PreGeneratedScene], None] | None = None,
        metrics: AnticipationMetrics | None = None,
    ):
        """Initialize the cache.

        Args:
            max_size: Maximum number of scenes to cache
            on_evict: Callback when a scene is evicted (for metrics)
            metrics: Shared metrics object for recording stats
        """
        self.max_size = max_size
        self._cache: OrderedDict[str, PreGeneratedScene] = OrderedDict()
        self._lock = asyncio.Lock()
        self._on_evict = on_evict
        self._metrics = metrics or AnticipationMetrics()

    async def get(self, location_key: str) -> PreGeneratedScene | None:
        """Get pre-generated scene if available and fresh.

        Args:
            location_key: The location to look up

        Returns:
            PreGeneratedScene if found and not stale, None otherwise
        """
        start = datetime.now()

        async with self._lock:
            scene = self._cache.get(location_key)

            if scene is None:
                logger.debug(f"Cache miss for {location_key}")
                return None

            if scene.is_stale():
                logger.info(
                    f"Cache entry stale for {location_key}, "
                    f"age={scene.age_seconds():.1f}s, "
                    f"ttl={scene.expiry_seconds}s"
                )
                self._evict_scene(location_key, reason="stale")
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(location_key)

            latency_ms = (datetime.now() - start).total_seconds() * 1000
            self._metrics.record_cache_hit(latency_ms)

            logger.info(
                f"Cache hit for {location_key}, "
                f"age={scene.age_seconds():.1f}s, "
                f"latency={latency_ms:.1f}ms"
            )

            return scene

    async def put(self, scene: PreGeneratedScene) -> None:
        """Store a pre-generated scene.

        If cache is at capacity, evicts the least recently used entry.

        Args:
            scene: The scene to cache
        """
        async with self._lock:
            # If already exists, update and move to end
            if scene.location_key in self._cache:
                self._cache[scene.location_key] = scene
                self._cache.move_to_end(scene.location_key)
                logger.debug(f"Updated cache entry for {scene.location_key}")
                return

            # Evict oldest entries if at capacity
            while len(self._cache) >= self.max_size:
                oldest_key = next(iter(self._cache))
                self._evict_scene(oldest_key, reason="lru")

            # Add new entry
            self._cache[scene.location_key] = scene
            logger.info(
                f"Cached scene for {scene.location_key}, "
                f"cache_size={len(self._cache)}/{self.max_size}"
            )

    async def invalidate(self, location_key: str) -> bool:
        """Remove a specific location from cache.

        Args:
            location_key: The location to invalidate

        Returns:
            True if entry was found and removed, False otherwise
        """
        async with self._lock:
            if location_key in self._cache:
                self._evict_scene(location_key, reason="invalidated")
                return True
            return False

    async def invalidate_all_except(self, keep_key: str | None = None) -> int:
        """Invalidate all cached scenes except one.

        Useful when player moves to a new location - invalidate predictions
        based on the old location but keep the new location if pre-generated.

        Args:
            keep_key: Location key to keep (optional)

        Returns:
            Number of entries invalidated
        """
        async with self._lock:
            keys_to_remove = [
                key for key in self._cache.keys() if key != keep_key
            ]

            for key in keys_to_remove:
                self._evict_scene(key, reason="bulk_invalidate")

            logger.info(
                f"Bulk invalidation: removed {len(keys_to_remove)} entries, "
                f"kept={keep_key}"
            )

            return len(keys_to_remove)

    async def clear(self) -> int:
        """Clear all cached entries.

        Returns:
            Number of entries cleared
        """
        async with self._lock:
            count = len(self._cache)
            for key in list(self._cache.keys()):
                self._evict_scene(key, reason="clear")
            logger.info(f"Cache cleared, removed {count} entries")
            return count

    async def cleanup_stale(self) -> int:
        """Remove all stale entries from cache.

        Should be called periodically to prevent memory leaks from
        entries that were never used.

        Returns:
            Number of stale entries removed
        """
        async with self._lock:
            stale_keys = [
                key for key, scene in self._cache.items() if scene.is_stale()
            ]

            for key in stale_keys:
                self._evict_scene(key, reason="cleanup_stale")

            if stale_keys:
                logger.info(f"Cleaned up {len(stale_keys)} stale entries")

            return len(stale_keys)

    async def contains(self, location_key: str) -> bool:
        """Check if location is in cache (without updating LRU order).

        Args:
            location_key: The location to check

        Returns:
            True if in cache and not stale
        """
        async with self._lock:
            scene = self._cache.get(location_key)
            if scene is None:
                return False
            if scene.is_stale():
                return False
            return True

    async def keys(self) -> list[str]:
        """Get all cached location keys.

        Returns:
            List of location keys in cache (most recent last)
        """
        async with self._lock:
            return list(self._cache.keys())

    async def stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        async with self._lock:
            entries = []
            for key, scene in self._cache.items():
                entries.append({
                    "location_key": key,
                    "age_seconds": scene.age_seconds(),
                    "remaining_ttl": scene.remaining_ttl_seconds(),
                    "is_stale": scene.is_stale(),
                    "is_committed": scene.is_committed,
                    "prediction_reason": (
                        scene.prediction_reason.value
                        if scene.prediction_reason
                        else None
                    ),
                })

            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "entries": entries,
                "metrics": self._metrics.to_dict(),
            }

    def _evict_scene(self, location_key: str, reason: str) -> None:
        """Evict a scene from cache (internal, must hold lock).

        Args:
            location_key: Key to evict
            reason: Why eviction happened (for logging/metrics)
        """
        scene = self._cache.pop(location_key, None)
        if scene is None:
            return

        # Track wasted generations (completed but never used)
        if not scene.is_committed and reason in ("stale", "lru", "cleanup_stale"):
            self._metrics.record_generation_wasted()
            logger.debug(
                f"Wasted generation for {location_key}, "
                f"reason={reason}, "
                f"age={scene.age_seconds():.1f}s"
            )

        # Call eviction callback if set
        if self._on_evict:
            try:
                self._on_evict(scene)
            except Exception as e:
                logger.error(f"Error in eviction callback: {e}")

        logger.debug(f"Evicted {location_key}, reason={reason}")

    @property
    def metrics(self) -> AnticipationMetrics:
        """Get the metrics object."""
        return self._metrics
