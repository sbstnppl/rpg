"""Tests for QuantumBranchCache."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.world_server.schemas import PredictionReason
from src.world_server.quantum.schemas import (
    ActionPrediction,
    ActionType,
    GMDecision,
    OutcomeVariant,
    QuantumBranch,
    QuantumMetrics,
    VariantType,
)
from src.world_server.quantum.cache import (
    CacheEntry,
    QuantumBranchCache,
)


@pytest.fixture
def sample_action():
    """Create a sample action prediction."""
    return ActionPrediction(
        action_type=ActionType.INTERACT_NPC,
        target_key="guard_001",
        input_patterns=["talk.*guard"],
        probability=0.25,
        reason=PredictionReason.ADJACENT,
    )


@pytest.fixture
def sample_gm_decision():
    """Create a sample GM decision."""
    return GMDecision(
        decision_type="no_twist",
        probability=0.7,
        grounding_facts=[],
    )


@pytest.fixture
def sample_branch(sample_action, sample_gm_decision):
    """Create a sample quantum branch."""
    return QuantumBranch(
        branch_key="village_square::interact_npc::guard_001::no_twist",
        action=sample_action,
        gm_decision=sample_gm_decision,
        variants={
            "success": OutcomeVariant(
                variant_type=VariantType.SUCCESS,
                requires_dice=False,
                narrative="You approach the guard.",
            ),
        },
        generated_at=datetime.now(),
        generation_time_ms=50.0,
    )


def create_branch(
    location: str = "village_square",
    action_type: ActionType = ActionType.INTERACT_NPC,
    target_key: str = "guard_001",
    gm_decision: str = "no_twist",
    expiry_seconds: int = 180,
) -> QuantumBranch:
    """Helper to create test branches."""
    action = ActionPrediction(
        action_type=action_type,
        target_key=target_key,
        input_patterns=[f".*{target_key}.*"],
        probability=0.25,
        reason=PredictionReason.ADJACENT,
    )

    decision = GMDecision(
        decision_type=gm_decision,
        probability=0.5,
        grounding_facts=[],
    )

    branch_key = QuantumBranch.create_key(
        location_key=location,
        action_type=action_type,
        target_key=target_key,
        gm_decision_type=gm_decision,
    )

    return QuantumBranch(
        branch_key=branch_key,
        action=action,
        gm_decision=decision,
        variants={
            "success": OutcomeVariant(
                variant_type=VariantType.SUCCESS,
                requires_dice=False,
                narrative="Success!",
            ),
        },
        generated_at=datetime.now(),
        generation_time_ms=50.0,
        expiry_seconds=expiry_seconds,
    )


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_touch_updates_metadata(self, sample_branch):
        """Test that touch updates access metadata."""
        entry = CacheEntry(branch=sample_branch)
        initial_time = entry.last_accessed
        initial_count = entry.access_count

        # Small delay to ensure time difference
        entry.touch()

        assert entry.access_count == initial_count + 1
        assert entry.last_accessed >= initial_time

    def test_is_expired(self, sample_branch):
        """Test expiry detection."""
        entry = CacheEntry(branch=sample_branch)

        # Not expired immediately
        assert not entry.is_expired(ttl_seconds=60.0)

        # Expired with 0 TTL
        assert entry.is_expired(ttl_seconds=0.0)

    def test_is_expired_with_old_timestamp(self, sample_branch):
        """Test expiry with old timestamp."""
        entry = CacheEntry(branch=sample_branch)
        entry.inserted_at = datetime.now() - timedelta(seconds=120)

        assert entry.is_expired(ttl_seconds=60.0)
        assert not entry.is_expired(ttl_seconds=180.0)


class TestQuantumBranchCacheInit:
    """Tests for cache initialization."""

    def test_default_initialization(self):
        """Test default cache initialization."""
        cache = QuantumBranchCache()

        assert cache.max_branches == 50
        assert cache.ttl_seconds == 180.0
        assert cache.size == 0
        assert cache.metrics is not None

    def test_custom_initialization(self):
        """Test cache with custom settings."""
        metrics = QuantumMetrics()
        cache = QuantumBranchCache(
            max_branches=100,
            ttl_seconds=300.0,
            metrics=metrics,
        )

        assert cache.max_branches == 100
        assert cache.ttl_seconds == 300.0
        assert cache.metrics is metrics


class TestGetAndPutBranch:
    """Tests for get_branch and put_branch operations."""

    @pytest.mark.asyncio
    async def test_put_and_get_branch(self, sample_branch, sample_action):
        """Test storing and retrieving a branch."""
        cache = QuantumBranchCache()

        await cache.put_branch(sample_branch)

        result = await cache.get_branch(
            location_key="village_square",
            action=sample_action,
            gm_decision_type="no_twist",
        )

        assert result is not None
        assert result.branch_key == sample_branch.branch_key
        assert cache.metrics.cache_hits == 1
        assert cache.metrics.cache_misses == 0

    @pytest.mark.asyncio
    async def test_get_nonexistent_branch(self, sample_action):
        """Test getting a branch that doesn't exist."""
        cache = QuantumBranchCache()

        result = await cache.get_branch(
            location_key="village_square",
            action=sample_action,
            gm_decision_type="no_twist",
        )

        assert result is None
        assert cache.metrics.cache_misses == 1

    @pytest.mark.asyncio
    async def test_get_branch_by_key(self, sample_branch):
        """Test getting a branch by its exact key."""
        cache = QuantumBranchCache()

        await cache.put_branch(sample_branch)

        result = await cache.get_branch_by_key(sample_branch.branch_key)

        assert result is not None
        assert result.branch_key == sample_branch.branch_key

    @pytest.mark.asyncio
    async def test_put_multiple_branches(self):
        """Test storing multiple branches."""
        cache = QuantumBranchCache()

        branches = [
            create_branch(target_key="guard_001"),
            create_branch(target_key="merchant_001"),
            create_branch(target_key="innkeeper_001"),
        ]

        await cache.put_branches(branches)

        assert cache.size == 3

    @pytest.mark.asyncio
    async def test_put_overwrites_existing(self, sample_action):
        """Test that putting same key overwrites."""
        cache = QuantumBranchCache()

        branch1 = create_branch()
        branch2 = create_branch()
        branch2.generation_time_ms = 999.0  # Different to distinguish

        await cache.put_branch(branch1)
        await cache.put_branch(branch2)

        assert cache.size == 1

        result = await cache.get_branch(
            location_key="village_square",
            action=sample_action,
            gm_decision_type="no_twist",
        )

        assert result.generation_time_ms == 999.0


class TestLRUEviction:
    """Tests for LRU eviction behavior."""

    @pytest.mark.asyncio
    async def test_eviction_when_over_capacity(self):
        """Test that oldest entries are evicted."""
        cache = QuantumBranchCache(max_branches=3)

        # Add 5 branches
        for i in range(5):
            branch = create_branch(target_key=f"npc_{i:03d}")
            await cache.put_branch(branch)

        # Should only have 3
        assert cache.size == 3

        # Oldest (npc_000, npc_001) should be evicted
        assert cache.metrics.branches_expired >= 2

    @pytest.mark.asyncio
    async def test_lru_order_updated_on_access(self):
        """Test that accessing moves to end of LRU."""
        cache = QuantumBranchCache(max_branches=3)

        # Add 3 branches
        branch0 = create_branch(target_key="npc_000")
        branch1 = create_branch(target_key="npc_001")
        branch2 = create_branch(target_key="npc_002")

        await cache.put_branches([branch0, branch1, branch2])

        # Access the first one (moves it to end)
        action0 = ActionPrediction(
            action_type=ActionType.INTERACT_NPC,
            target_key="npc_000",
            input_patterns=[],
            probability=0.25,
            reason=PredictionReason.ADJACENT,
        )
        await cache.get_branch("village_square", action0, "no_twist")

        # Add a new branch - should evict npc_001 (now oldest)
        branch3 = create_branch(target_key="npc_003")
        await cache.put_branch(branch3)

        # npc_000 should still be there
        result = await cache.get_branch("village_square", action0, "no_twist")
        assert result is not None

        # npc_001 should be evicted
        action1 = ActionPrediction(
            action_type=ActionType.INTERACT_NPC,
            target_key="npc_001",
            input_patterns=[],
            probability=0.25,
            reason=PredictionReason.ADJACENT,
        )
        result = await cache.get_branch("village_square", action1, "no_twist")
        assert result is None


class TestTTLExpiry:
    """Tests for TTL-based expiry."""

    @pytest.mark.asyncio
    async def test_expired_branch_not_returned(self, sample_action):
        """Test that expired branches are not returned."""
        cache = QuantumBranchCache(ttl_seconds=0.01)  # Very short TTL

        branch = create_branch()
        await cache.put_branch(branch)

        # Wait for expiry
        await asyncio.sleep(0.02)

        result = await cache.get_branch(
            location_key="village_square",
            action=sample_action,
            gm_decision_type="no_twist",
        )

        assert result is None
        assert cache.metrics.branches_expired >= 1

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, sample_action):
        """Test cleanup_expired removes stale entries."""
        cache = QuantumBranchCache(ttl_seconds=0.01)

        # Add several branches
        for i in range(5):
            branch = create_branch(target_key=f"npc_{i:03d}")
            await cache.put_branch(branch)

        assert cache.size == 5

        # Wait for expiry
        await asyncio.sleep(0.02)

        # Cleanup
        removed = await cache.cleanup_expired()

        assert removed == 5
        assert cache.size == 0

    @pytest.mark.asyncio
    async def test_branch_own_expiry_respected(self, sample_action):
        """Test that branch's own expiry_seconds is checked."""
        cache = QuantumBranchCache(ttl_seconds=180.0)  # Long cache TTL

        # Create branch with short expiry
        branch = create_branch(expiry_seconds=0)  # Immediately expired

        await cache.put_branch(branch)

        result = await cache.get_branch(
            location_key="village_square",
            action=sample_action,
            gm_decision_type="no_twist",
        )

        assert result is None


class TestLocationInvalidation:
    """Tests for location-based invalidation."""

    @pytest.mark.asyncio
    async def test_invalidate_location(self):
        """Test invalidating all branches for a location."""
        cache = QuantumBranchCache()

        # Add branches for different locations
        await cache.put_branches([
            create_branch(location="tavern", target_key="bartender"),
            create_branch(location="tavern", target_key="patron"),
            create_branch(location="market", target_key="merchant"),
        ])

        assert cache.size == 3

        # Invalidate tavern
        removed = await cache.invalidate_location("tavern")

        assert removed == 2
        assert cache.size == 1
        assert cache.metrics.branches_invalidated == 2

    @pytest.mark.asyncio
    async def test_invalidate_nonexistent_location(self):
        """Test invalidating a location with no branches."""
        cache = QuantumBranchCache()

        await cache.put_branch(create_branch(location="tavern"))

        removed = await cache.invalidate_location("castle")

        assert removed == 0
        assert cache.size == 1

    @pytest.mark.asyncio
    async def test_invalidate_branch(self):
        """Test invalidating a specific branch."""
        cache = QuantumBranchCache()

        branch = create_branch()
        await cache.put_branch(branch)

        assert cache.size == 1

        removed = await cache.invalidate_branch(branch.branch_key)

        assert removed is True
        assert cache.size == 0


class TestActionBasedLookups:
    """Tests for action-based branch lookups."""

    @pytest.mark.asyncio
    async def test_get_branches_for_action(self):
        """Test getting all branches for an action (any GM decision)."""
        cache = QuantumBranchCache()

        # Add branches with different GM decisions for same action
        await cache.put_branches([
            create_branch(target_key="guard", gm_decision="no_twist"),
            create_branch(target_key="guard", gm_decision="theft_accusation"),
            create_branch(target_key="guard", gm_decision="monster_warning"),
            create_branch(target_key="merchant", gm_decision="no_twist"),  # Different action
        ])

        action = ActionPrediction(
            action_type=ActionType.INTERACT_NPC,
            target_key="guard",
            input_patterns=[],
            probability=0.25,
            reason=PredictionReason.ADJACENT,
        )

        branches = await cache.get_branches_for_action("village_square", action)

        assert len(branches) == 3
        decisions = {b.gm_decision.decision_type for b in branches}
        assert decisions == {"no_twist", "theft_accusation", "monster_warning"}

    @pytest.mark.asyncio
    async def test_get_branches_for_action_empty(self):
        """Test getting branches for an action with none cached."""
        cache = QuantumBranchCache()

        action = ActionPrediction(
            action_type=ActionType.INTERACT_NPC,
            target_key="guard",
            input_patterns=[],
            probability=0.25,
            reason=PredictionReason.ADJACENT,
        )

        branches = await cache.get_branches_for_action("village_square", action)

        assert branches == []


class TestClearCache:
    """Tests for clearing the cache."""

    @pytest.mark.asyncio
    async def test_clear(self):
        """Test clearing all branches."""
        cache = QuantumBranchCache()

        await cache.put_branches([
            create_branch(target_key="npc_001"),
            create_branch(target_key="npc_002"),
            create_branch(target_key="npc_003"),
        ])

        assert cache.size == 3

        removed = await cache.clear()

        assert removed == 3
        assert cache.size == 0

    @pytest.mark.asyncio
    async def test_clear_empty_cache(self):
        """Test clearing an empty cache."""
        cache = QuantumBranchCache()

        removed = await cache.clear()

        assert removed == 0


class TestCacheStats:
    """Tests for cache statistics."""

    @pytest.mark.asyncio
    async def test_get_stats(self, sample_action):
        """Test getting cache statistics."""
        cache = QuantumBranchCache(max_branches=100, ttl_seconds=300.0)

        # Add some branches and generate some hits/misses
        await cache.put_branch(create_branch())
        await cache.get_branch("village_square", sample_action, "no_twist")  # Hit
        await cache.get_branch("village_square", sample_action, "other")  # Miss

        stats = cache.get_stats()

        assert stats["size"] == 1
        assert stats["max_branches"] == 100
        assert stats["ttl_seconds"] == 300.0
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == "50.0%"

    @pytest.mark.asyncio
    async def test_iter_branches(self):
        """Test iterating over cached branches."""
        cache = QuantumBranchCache()

        await cache.put_branches([
            create_branch(target_key="npc_001"),
            create_branch(target_key="npc_002"),
        ])

        branches = list(cache.iter_branches())

        assert len(branches) == 2


class TestMetricsIntegration:
    """Tests for metrics tracking integration."""

    @pytest.mark.asyncio
    async def test_hit_rate_calculation(self, sample_action):
        """Test hit rate is calculated correctly."""
        cache = QuantumBranchCache()

        await cache.put_branch(create_branch())

        # 3 hits
        for _ in range(3):
            await cache.get_branch("village_square", sample_action, "no_twist")

        # 2 misses
        for _ in range(2):
            await cache.get_branch("village_square", sample_action, "other")

        assert cache.metrics.cache_hits == 3
        assert cache.metrics.cache_misses == 2
        assert cache.metrics.hit_rate == pytest.approx(0.6)

    @pytest.mark.asyncio
    async def test_avg_hit_latency(self, sample_action):
        """Test average hit latency is tracked."""
        cache = QuantumBranchCache()

        await cache.put_branch(create_branch())

        # Multiple hits
        for _ in range(5):
            await cache.get_branch("village_square", sample_action, "no_twist")

        assert cache.metrics.total_cache_hit_latency_ms > 0
        assert cache.metrics.avg_cache_hit_latency_ms > 0


class TestConcurrency:
    """Tests for thread safety and concurrent access."""

    @pytest.mark.asyncio
    async def test_concurrent_puts(self):
        """Test concurrent put operations."""
        cache = QuantumBranchCache(max_branches=100)

        async def put_branch(i: int):
            branch = create_branch(target_key=f"npc_{i:03d}")
            await cache.put_branch(branch)

        # Put 50 branches concurrently
        tasks = [put_branch(i) for i in range(50)]
        await asyncio.gather(*tasks)

        assert cache.size == 50

    @pytest.mark.asyncio
    async def test_concurrent_gets(self, sample_action):
        """Test concurrent get operations."""
        cache = QuantumBranchCache()
        await cache.put_branch(create_branch())

        results = []

        async def get_branch():
            result = await cache.get_branch(
                "village_square", sample_action, "no_twist"
            )
            results.append(result is not None)

        # Get same branch concurrently
        tasks = [get_branch() for _ in range(20)]
        await asyncio.gather(*tasks)

        assert all(results)
        assert cache.metrics.cache_hits == 20

    @pytest.mark.asyncio
    async def test_concurrent_put_and_get(self, sample_action):
        """Test concurrent put and get operations."""
        cache = QuantumBranchCache(max_branches=100)

        async def put_branches():
            for i in range(20):
                branch = create_branch(target_key=f"npc_{i:03d}")
                await cache.put_branch(branch)
                await asyncio.sleep(0.001)

        async def get_branches():
            for _ in range(20):
                await cache.get_branch(
                    "village_square", sample_action, "no_twist"
                )
                await asyncio.sleep(0.001)

        await asyncio.gather(put_branches(), get_branches())

        # Should complete without deadlock or errors
        assert cache.size <= 100


class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.asyncio
    async def test_branch_with_none_target(self):
        """Test caching branch with None target_key."""
        cache = QuantumBranchCache()

        branch = create_branch(
            action_type=ActionType.OBSERVE,
            target_key=None,  # type: ignore (force None for test)
        )
        # Fix the branch key for None target
        branch.branch_key = "village_square::observe::none::no_twist"
        branch.action.target_key = None

        await cache.put_branch(branch)

        action = ActionPrediction(
            action_type=ActionType.OBSERVE,
            target_key=None,
            input_patterns=["look"],
            probability=0.2,
            reason=PredictionReason.ADJACENT,
        )

        result = await cache.get_branch("village_square", action, "no_twist")

        assert result is not None

    @pytest.mark.asyncio
    async def test_empty_variants(self):
        """Test caching branch with empty variants."""
        cache = QuantumBranchCache()

        action = ActionPrediction(
            action_type=ActionType.WAIT,
            target_key=None,
            input_patterns=["wait"],
            probability=0.1,
            reason=PredictionReason.ADJACENT,
        )

        branch = QuantumBranch(
            branch_key="tavern::wait::none::no_twist",
            action=action,
            gm_decision=GMDecision("no_twist", 1.0, []),
            variants={},  # Empty
            generated_at=datetime.now(),
        )

        await cache.put_branch(branch)

        result = await cache.get_branch_by_key(branch.branch_key)
        assert result is not None
        assert result.variants == {}

    @pytest.mark.asyncio
    async def test_very_long_branch_key(self):
        """Test handling of very long branch keys."""
        cache = QuantumBranchCache()

        long_target = "a" * 1000
        branch = create_branch(target_key=long_target)

        await cache.put_branch(branch)

        action = ActionPrediction(
            action_type=ActionType.INTERACT_NPC,
            target_key=long_target,
            input_patterns=[],
            probability=0.25,
            reason=PredictionReason.ADJACENT,
        )

        result = await cache.get_branch("village_square", action, "no_twist")
        assert result is not None
