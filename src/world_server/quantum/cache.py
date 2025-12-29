"""Quantum Branch Cache for pre-generated branches.

This module provides an LRU cache for storing pre-generated quantum branches.
Key features:
- LRU eviction when max capacity is reached
- TTL-based expiry for stale branches
- Location-based invalidation when world state changes
- Thread-safe with asyncio locks
- Metrics tracking for hit/miss rates
"""

import asyncio
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterator

from src.world_server.quantum.schemas import (
    ActionPrediction,
    ActionType,
    QuantumBranch,
    QuantumMetrics,
)

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Wrapper for a cached branch with access metadata."""

    branch: QuantumBranch
    inserted_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0

    def touch(self) -> None:
        """Update access metadata."""
        self.last_accessed = datetime.now()
        self.access_count += 1

    def is_expired(self, ttl_seconds: float) -> bool:
        """Check if entry has exceeded TTL."""
        age = (datetime.now() - self.inserted_at).total_seconds()
        return age > ttl_seconds


class QuantumBranchCache:
    """LRU cache for quantum branches with TTL expiry.

    Stores pre-generated branches keyed by:
    - location_key
    - action_type
    - target_key
    - gm_decision_type

    Supports:
    - LRU eviction when max capacity reached
    - TTL-based expiry
    - Location-based invalidation
    - Action-based lookups
    """

    def __init__(
        self,
        max_branches: int = 50,
        ttl_seconds: float = 180.0,
        metrics: QuantumMetrics | None = None,
    ):
        """Initialize the cache.

        Args:
            max_branches: Maximum number of branches to store
            ttl_seconds: Time-to-live in seconds (default 3 minutes)
            metrics: Optional metrics tracker
        """
        self.max_branches = max_branches
        self.ttl_seconds = ttl_seconds
        self._entries: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        self._metrics = metrics or QuantumMetrics()

        # Index by location for fast invalidation
        self._location_index: dict[str, set[str]] = {}

        # Index by action for finding all branches for an action
        self._action_index: dict[str, set[str]] = {}

    @property
    def metrics(self) -> QuantumMetrics:
        """Get the metrics tracker."""
        return self._metrics

    @property
    def size(self) -> int:
        """Get current number of cached branches."""
        return len(self._entries)

    async def get_branch(
        self,
        location_key: str,
        action: ActionPrediction,
        gm_decision_type: str,
    ) -> QuantumBranch | None:
        """Get a cached branch if available and not expired.

        Args:
            location_key: Current location
            action: The predicted action
            gm_decision_type: The GM decision type

        Returns:
            Cached branch if found and valid, None otherwise
        """
        start_time = time.perf_counter()
        key = QuantumBranch.create_key(
            location_key=location_key,
            action_type=action.action_type,
            target_key=action.target_key,
            gm_decision_type=gm_decision_type,
        )

        async with self._lock:
            entry = self._entries.get(key)

            if entry is None:
                self._metrics.record_cache_miss()
                return None

            # Check if expired
            if entry.is_expired(self.ttl_seconds) or entry.branch.is_stale():
                # Remove expired entry
                self._remove_entry(key)
                self._metrics.record_cache_miss()
                self._metrics.record_branch_expired()
                return None

            # Update LRU order and access metadata
            self._entries.move_to_end(key)
            entry.touch()

            latency_ms = (time.perf_counter() - start_time) * 1000
            self._metrics.record_cache_hit(latency_ms)

            logger.debug(f"Cache hit for {key} (accessed {entry.access_count} times)")
            return entry.branch

    async def get_branch_by_key(self, branch_key: str) -> QuantumBranch | None:
        """Get a branch by its exact key.

        Args:
            branch_key: The full branch key

        Returns:
            Cached branch if found and valid, None otherwise
        """
        start_time = time.perf_counter()

        async with self._lock:
            entry = self._entries.get(branch_key)

            if entry is None:
                self._metrics.record_cache_miss()
                return None

            if entry.is_expired(self.ttl_seconds) or entry.branch.is_stale():
                self._remove_entry(branch_key)
                self._metrics.record_cache_miss()
                self._metrics.record_branch_expired()
                return None

            self._entries.move_to_end(branch_key)
            entry.touch()

            latency_ms = (time.perf_counter() - start_time) * 1000
            self._metrics.record_cache_hit(latency_ms)

            return entry.branch

    async def get_branches_for_action(
        self,
        location_key: str,
        action: ActionPrediction,
    ) -> list[QuantumBranch]:
        """Get all cached branches for an action (any GM decision).

        Args:
            location_key: Current location
            action: The predicted action

        Returns:
            List of all valid cached branches for this action
        """
        action_prefix = f"{location_key}::{action.action_type.value}::{action.target_key or 'none'}"

        async with self._lock:
            branch_keys = self._action_index.get(action_prefix, set())
            branches = []

            for key in list(branch_keys):
                entry = self._entries.get(key)
                if entry is None:
                    branch_keys.discard(key)
                    continue

                if entry.is_expired(self.ttl_seconds) or entry.branch.is_stale():
                    self._remove_entry(key)
                    continue

                branches.append(entry.branch)

            return branches

    async def put_branch(self, branch: QuantumBranch) -> None:
        """Store a single branch in the cache.

        Args:
            branch: The branch to cache
        """
        await self.put_branches([branch])

    async def put_branches(self, branches: list[QuantumBranch]) -> None:
        """Store multiple branches in the cache.

        Args:
            branches: List of branches to cache
        """
        async with self._lock:
            for branch in branches:
                key = branch.branch_key

                # Create entry
                entry = CacheEntry(branch=branch)
                self._entries[key] = entry

                # Update LRU order
                self._entries.move_to_end(key)

                # Update indexes
                self._add_to_indexes(key, branch)

                logger.debug(f"Cached branch: {key}")

            # Evict if over capacity
            self._evict_if_needed()

    async def invalidate_location(self, location_key: str) -> int:
        """Invalidate all branches for a location.

        Called when world state changes at a location.

        Args:
            location_key: The location to invalidate

        Returns:
            Number of branches invalidated
        """
        async with self._lock:
            keys_to_remove = self._location_index.get(location_key, set()).copy()

            for key in keys_to_remove:
                self._remove_entry(key)
                self._metrics.record_branch_invalidated()

            count = len(keys_to_remove)
            if count > 0:
                logger.info(f"Invalidated {count} branches for location: {location_key}")

            return count

    async def invalidate_branch(self, branch_key: str) -> bool:
        """Invalidate a specific branch.

        Args:
            branch_key: The branch key to invalidate

        Returns:
            True if branch was found and removed
        """
        async with self._lock:
            if branch_key in self._entries:
                self._remove_entry(branch_key)
                self._metrics.record_branch_invalidated()
                return True
            return False

    async def clear(self) -> int:
        """Clear all cached branches.

        Returns:
            Number of branches cleared
        """
        async with self._lock:
            count = len(self._entries)
            self._entries.clear()
            self._location_index.clear()
            self._action_index.clear()
            logger.info(f"Cleared {count} branches from cache")
            return count

    async def cleanup_expired(self) -> int:
        """Remove all expired branches.

        Returns:
            Number of branches removed
        """
        async with self._lock:
            expired_keys = [
                key for key, entry in self._entries.items()
                if entry.is_expired(self.ttl_seconds) or entry.branch.is_stale()
            ]

            for key in expired_keys:
                self._remove_entry(key)
                self._metrics.record_branch_expired()

            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired branches")

            return len(expired_keys)

    def get_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        return {
            "size": self.size,
            "max_branches": self.max_branches,
            "ttl_seconds": self.ttl_seconds,
            "locations_cached": len(self._location_index),
            "actions_cached": len(self._action_index),
            "hit_rate": f"{self._metrics.hit_rate:.1%}",
            "hits": self._metrics.cache_hits,
            "misses": self._metrics.cache_misses,
            "avg_hit_latency_ms": f"{self._metrics.avg_cache_hit_latency_ms:.2f}",
        }

    def iter_branches(self) -> Iterator[QuantumBranch]:
        """Iterate over all cached branches (not async-safe).

        Yields:
            All cached branches
        """
        for entry in self._entries.values():
            yield entry.branch

    def _add_to_indexes(self, key: str, branch: QuantumBranch) -> None:
        """Add branch to lookup indexes (called under lock)."""
        # Parse location from key
        parts = key.split("::")
        if len(parts) >= 1:
            location_key = parts[0]
            if location_key not in self._location_index:
                self._location_index[location_key] = set()
            self._location_index[location_key].add(key)

        # Build action prefix (location::action_type::target)
        if len(parts) >= 3:
            action_prefix = "::".join(parts[:3])
            if action_prefix not in self._action_index:
                self._action_index[action_prefix] = set()
            self._action_index[action_prefix].add(key)

    def _remove_from_indexes(self, key: str) -> None:
        """Remove branch from lookup indexes (called under lock)."""
        parts = key.split("::")
        if len(parts) >= 1:
            location_key = parts[0]
            if location_key in self._location_index:
                self._location_index[location_key].discard(key)
                if not self._location_index[location_key]:
                    del self._location_index[location_key]

        if len(parts) >= 3:
            action_prefix = "::".join(parts[:3])
            if action_prefix in self._action_index:
                self._action_index[action_prefix].discard(key)
                if not self._action_index[action_prefix]:
                    del self._action_index[action_prefix]

    def _remove_entry(self, key: str) -> None:
        """Remove an entry from cache and indexes (called under lock)."""
        if key in self._entries:
            del self._entries[key]
            self._remove_from_indexes(key)

    def _evict_if_needed(self) -> None:
        """Evict oldest entries if over capacity (called under lock)."""
        while len(self._entries) > self.max_branches:
            # Pop oldest (first) item
            oldest_key, oldest_entry = self._entries.popitem(last=False)
            self._remove_from_indexes(oldest_key)
            self._metrics.record_branch_expired()
            logger.debug(f"Evicted branch: {oldest_key}")
