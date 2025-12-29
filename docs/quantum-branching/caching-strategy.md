# Caching Strategy

The `QuantumBranchCache` stores pre-generated branches for fast retrieval during gameplay.

## Overview

The cache enables the quantum pipeline's key performance benefit: instant responses for predicted actions.

```
Without Cache:
Player Input → Generate → 3-8 seconds → Display

With Cache (hit):
Player Input → Lookup → <100ms → Display
```

## Cache Architecture

### QuantumBranchCache

```python
class QuantumBranchCache:
    def __init__(
        self,
        max_size: int = 50,           # Max branches
        default_ttl: int = 180,       # 3 minutes
        cleanup_interval: int = 60,   # 1 minute
    ):
        self._branches: dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
        self._metrics = CacheMetrics()

        # Start background cleanup
        self._cleanup_task = asyncio.create_task(
            self._cleanup_loop(cleanup_interval)
        )
```

### CacheEntry

```python
@dataclass
class CacheEntry:
    branch: QuantumBranch
    created_at: datetime
    last_accessed: datetime
    access_count: int
    ttl_seconds: int

    @property
    def is_expired(self) -> bool:
        age = (datetime.now() - self.created_at).total_seconds()
        return age > self.ttl_seconds

    def touch(self) -> None:
        self.last_accessed = datetime.now()
        self.access_count += 1
```

## Branch Key Format

Keys uniquely identify branches:

```
{location_key}::{action_type}::{target_key}::{gm_decision}

Examples:
- "tavern_main::INTERACT_NPC::bartender_001::no_twist"
- "market_square::MANIPULATE_ITEM::apple_001::no_twist"
- "forest_path::MOVE::village_gate::monster_warning"
```

## Cache Operations

### Get Branch

```python
async def get_branch(
    self,
    location_key: str,
    action: ActionPrediction,
    gm_decision: str,
) -> QuantumBranch | None:
    key = self._make_key(location_key, action, gm_decision)

    async with self._lock:
        entry = self._branches.get(key)

        if entry is None:
            self._metrics.misses += 1
            return None

        if entry.is_expired:
            del self._branches[key]
            self._metrics.expirations += 1
            return None

        # Valid hit
        entry.touch()
        self._metrics.hits += 1
        return entry.branch
```

### Put Branches

```python
async def put_branches(
    self,
    branches: list[QuantumBranch],
    ttl: int | None = None,
) -> None:
    async with self._lock:
        for branch in branches:
            entry = CacheEntry(
                branch=branch,
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                access_count=0,
                ttl_seconds=ttl or self._default_ttl,
            )

            self._branches[branch.branch_key] = entry
            self._metrics.insertions += 1

        # Evict if over capacity
        self._evict_if_needed()
```

### Invalidate Location

```python
async def invalidate_location(self, location_key: str) -> int:
    """Remove all branches for a location (e.g., after world state change)."""
    async with self._lock:
        keys_to_remove = [
            key for key in self._branches
            if key.startswith(f"{location_key}::")
        ]

        for key in keys_to_remove:
            del self._branches[key]

        self._metrics.invalidations += len(keys_to_remove)
        return len(keys_to_remove)
```

## Eviction Policies

### LRU (Least Recently Used)

When cache is full, evict least recently accessed entries:

```python
def _evict_if_needed(self) -> None:
    while len(self._branches) > self._max_size:
        # Find LRU entry
        lru_key = min(
            self._branches.keys(),
            key=lambda k: self._branches[k].last_accessed
        )

        del self._branches[lru_key]
        self._metrics.evictions += 1
```

### TTL (Time To Live)

Branches expire after TTL to ensure freshness:

```python
async def _cleanup_loop(self, interval: int) -> None:
    """Background task to remove expired entries."""
    while True:
        await asyncio.sleep(interval)

        async with self._lock:
            expired_keys = [
                key for key, entry in self._branches.items()
                if entry.is_expired
            ]

            for key in expired_keys:
                del self._branches[key]
                self._metrics.expirations += 1
```

### Staleness Detection

Branches track state version for staleness:

```python
async def get_branch(self, ...) -> QuantumBranch | None:
    entry = self._branches.get(key)

    if entry and entry.branch.state_version != current_state_version:
        # Branch generated with old state
        del self._branches[key]
        self._metrics.stale_evictions += 1
        return None

    return entry.branch if entry else None
```

## Cache Warming

### Anticipation Integration

Background anticipation pre-fills the cache:

```python
class QuantumPipeline:
    async def _anticipation_loop(self) -> None:
        while self._running:
            location = self._current_location

            # Predict actions for current scene
            predictions = await self.action_predictor.predict_actions(
                location, manifest, recent_turns
            )

            # Generate branches for top predictions
            for action in predictions[:config.max_actions_per_cycle]:
                # Skip if already cached
                if await self._is_cached(location, action):
                    continue

                # Generate and cache
                branches = await self.branch_generator.generate_branches(
                    action, gm_decisions, manifest, context
                )

                await self.branch_cache.put_branches(branches)

            await asyncio.sleep(config.cycle_delay_seconds)
```

### Location Transition

Pre-warm cache when player moves:

```python
async def _on_location_change(
    self,
    old_location: str,
    new_location: str,
) -> None:
    # Invalidate old location (may be stale when player returns)
    await self.branch_cache.invalidate_location(old_location)

    # Start generating for new location
    await self._trigger_anticipation(new_location)
```

## Cache Metrics

```python
@dataclass
class CacheMetrics:
    hits: int = 0
    misses: int = 0
    insertions: int = 0
    evictions: int = 0
    expirations: int = 0
    invalidations: int = 0
    stale_evictions: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    @property
    def size(self) -> int:
        return self.insertions - self.evictions - self.expirations

    def reset(self) -> None:
        self.hits = 0
        self.misses = 0
        # ... reset all
```

### Metrics Display

```python
def get_cache_stats(cache: QuantumBranchCache) -> dict:
    return {
        "size": len(cache._branches),
        "max_size": cache._max_size,
        "hit_rate": f"{cache._metrics.hit_rate:.1%}",
        "hits": cache._metrics.hits,
        "misses": cache._metrics.misses,
        "evictions": cache._metrics.evictions,
        "expirations": cache._metrics.expirations,
    }
```

## Configuration

### Environment Variables

```bash
# Maximum branches in cache
QUANTUM_CACHE_SIZE=50

# Default TTL in seconds
QUANTUM_CACHE_TTL=180

# Cleanup interval in seconds
QUANTUM_CACHE_CLEANUP_INTERVAL=60
```

### AnticipationConfig

```python
@dataclass
class AnticipationConfig:
    enabled: bool = False
    max_actions_per_cycle: int = 5
    max_gm_decisions_per_action: int = 2
    cycle_delay_seconds: float = 0.5
```

## Memory Management

### Branch Size Estimation

```python
def estimate_branch_size(branch: QuantumBranch) -> int:
    """Estimate memory usage in bytes."""
    size = 0

    # Base object overhead
    size += 200

    # Key
    size += len(branch.branch_key) * 2

    # Variants
    for variant in branch.variants.values():
        size += len(variant.narrative) * 2
        size += len(variant.state_deltas) * 100

    return size


def estimate_cache_memory(cache: QuantumBranchCache) -> int:
    """Estimate total cache memory usage."""
    return sum(
        estimate_branch_size(entry.branch)
        for entry in cache._branches.values()
    )
```

### Memory Limits

```python
class QuantumBranchCache:
    def __init__(
        self,
        max_size: int = 50,
        max_memory_mb: int = 100,
    ):
        self._max_memory = max_memory_mb * 1024 * 1024

    def _evict_if_needed(self) -> None:
        # Evict by count
        while len(self._branches) > self._max_size:
            self._evict_lru()

        # Evict by memory
        while self._estimate_memory() > self._max_memory:
            self._evict_lru()
```

## Testing Cache Behavior

```python
@pytest.mark.asyncio
async def test_cache_hit(quantum_cache):
    """Test cache returns stored branch."""
    branch = create_test_branch("tavern::INTERACT_NPC::npc_001::no_twist")
    await quantum_cache.put_branches([branch])

    result = await quantum_cache.get_branch(
        "tavern",
        ActionPrediction(ActionType.INTERACT_NPC, "npc_001", ...),
        "no_twist",
    )

    assert result is not None
    assert result.branch_key == branch.branch_key
    assert quantum_cache._metrics.hits == 1


@pytest.mark.asyncio
async def test_cache_ttl_expiration(quantum_cache):
    """Test branches expire after TTL."""
    branch = create_test_branch("tavern::OBSERVE::None::no_twist")
    await quantum_cache.put_branches([branch], ttl=1)  # 1 second TTL

    # Immediately available
    result = await quantum_cache.get_branch(...)
    assert result is not None

    # Wait for expiration
    await asyncio.sleep(1.5)

    # Now expired
    result = await quantum_cache.get_branch(...)
    assert result is None


@pytest.mark.asyncio
async def test_cache_lru_eviction(quantum_cache):
    """Test LRU eviction when at capacity."""
    quantum_cache._max_size = 2

    # Add 3 branches
    branch1 = create_test_branch("loc1::...")
    branch2 = create_test_branch("loc2::...")
    branch3 = create_test_branch("loc3::...")

    await quantum_cache.put_branches([branch1])
    await quantum_cache.put_branches([branch2])

    # Access branch1 to make it recently used
    await quantum_cache.get_branch("loc1", ...)

    # Add branch3, should evict branch2 (LRU)
    await quantum_cache.put_branches([branch3])

    assert await quantum_cache.get_branch("loc1", ...) is not None
    assert await quantum_cache.get_branch("loc2", ...) is None  # Evicted
    assert await quantum_cache.get_branch("loc3", ...) is not None
```

## Best Practices

1. **Tune TTL for game pace**: Longer sessions may need shorter TTL
2. **Monitor hit rate**: Target >60% for good performance
3. **Invalidate on state changes**: Don't serve stale branches
4. **Size cache for expected actions**: More NPCs = larger cache
5. **Use metrics for tuning**: Adjust based on actual usage
