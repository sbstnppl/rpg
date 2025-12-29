# Migration Guide

This guide covers migrating from legacy pipelines (GM, Legacy, System-Authority, Scene-First) to the Quantum Branching architecture.

## Overview

The Quantum Branching pipeline is now the **default** pipeline. Previous pipelines remain available for comparison and debugging but are considered deprecated.

## Pipeline Comparison

| Feature | Legacy/GM | Scene-First | Quantum |
|---------|-----------|-------------|---------|
| Turn Processing | Sequential | Sequential | Cache-first |
| Latency (typical) | 50-80s | 10-30s | <100ms (hit) |
| Dice Timing | Pre-determined | Pre-determined | Runtime |
| Narration | Generated per-turn | Generated per-turn | Pre-generated |
| Entity Grounding | Implicit | Manifest-based | Manifest + keys |

## CLI Changes

### Default Pipeline

```bash
# Old: Specified pipeline explicitly
python -m src.main game play 1 --pipeline gm

# New: Quantum is default
python -m src.main game play 1
# Or explicitly:
python -m src.main game play 1 --pipeline quantum
```

### Pipeline Aliases

Available `--pipeline` values:

| Alias | Pipeline | Status |
|-------|----------|--------|
| `quantum`, `q`, `new` | Quantum | **Default** |
| `gm` | GM Pipeline | Deprecated |
| `legacy` | Legacy | Deprecated |
| `system-authority`, `sa` | System-Authority | Deprecated |
| `scene-first`, `sf` | Scene-First | Deprecated |

### Anticipation Option

```bash
# Enable background branch pre-generation
python -m src.main game play 1 --anticipation

# Disable anticipation (still uses quantum, but sync generation)
python -m src.main game play 1 --no-anticipation
```

## Configuration Changes

### New Settings

Add to `.env` or environment:

```bash
# Enable background anticipation by default
QUANTUM_ANTICIPATION_ENABLED=true

# Number of actions to pre-generate per cycle
QUANTUM_MAX_ACTIONS_PER_CYCLE=5

# Number of GM decisions per action
QUANTUM_MAX_GM_DECISIONS=2

# Delay between anticipation cycles
QUANTUM_CYCLE_DELAY=0.5

# Minimum match confidence for cache hit
QUANTUM_MIN_MATCH_CONFIDENCE=0.7
```

### Legacy Settings (Still Work)

These settings are still respected:

```bash
# LLM provider for generation
LLM_PROVIDER=anthropic
NARRATOR=anthropic:claude-sonnet-4-20250514
REASONING=anthropic:claude-sonnet-4-20250514
```

## Code Migration

### Using QuantumPipeline Directly

Old approach (LangGraph streaming):

```python
from src.agents.graph import get_gm_graph

graph = get_gm_graph(db, game_session)
async for event in graph.astream(initial_state):
    # Process streaming events
    pass
```

New approach (QuantumPipeline):

```python
from src.world_server.quantum import QuantumPipeline, AnticipationConfig

config = AnticipationConfig(
    enabled=True,
    max_actions_per_cycle=5,
)

pipeline = QuantumPipeline(
    db=db,
    game_session=game_session,
    anticipation_config=config,
)

# Process turn
result = await pipeline.process_turn(
    player_input="talk to the bartender",
    location_key="tavern_main",
    turn_number=game_session.total_turns,
)

# Access result
print(result.narrative)
print(f"Cache hit: {result.was_cache_hit}")
print(f"Latency: {result.latency_ms}ms")
```

### Handling Turn Results

Old approach (parse from GM response):

```python
gm_response = state["gm_response"]
# Parse narrative, extract state changes, etc.
```

New approach (structured result):

```python
result = await pipeline.process_turn(...)

# Narrative is ready to display
narrative = result.narrative

# Dice result if applicable
if result.skill_check_result:
    print(f"Roll: {result.skill_check_result.total} vs DC {result.skill_check_result.dc}")

# State changes already applied
# Access via result.errors if any failed
```

### Error Handling

Old approach (catch various exceptions):

```python
try:
    async for event in graph.astream(...):
        pass
except GMError as e:
    # Handle GM failure
except NarratorError as e:
    # Handle narrator failure
```

New approach (check result errors):

```python
result = await pipeline.process_turn(...)

if result.errors:
    for error in result.errors:
        logger.warning(f"Turn processing error: {error}")
    # Narrative still provided via fallback

# Pipeline handles fallback internally
```

## Test Migration

### Mocking QuantumPipeline

```python
from unittest.mock import AsyncMock, MagicMock
from src.world_server.quantum import TurnResult

@pytest.fixture
def mock_quantum_pipeline():
    pipeline = MagicMock()
    pipeline.process_turn = AsyncMock(return_value=TurnResult(
        narrative="The bartender nods at you.",
        was_cache_hit=True,
        latency_ms=45.0,
    ))
    return pipeline


async def test_game_turn(mock_quantum_pipeline):
    result = await mock_quantum_pipeline.process_turn(
        player_input="greet bartender",
        location_key="tavern",
        turn_number=1,
    )

    assert result.was_cache_hit
    assert "bartender" in result.narrative
```

### Testing Cache Behavior

```python
from src.world_server.quantum import QuantumBranchCache

@pytest.fixture
def quantum_cache():
    return QuantumBranchCache(max_size=10, default_ttl=60)


async def test_cache_hit_path(quantum_cache, sample_branch):
    # Pre-populate cache
    await quantum_cache.put_branches([sample_branch])

    # Verify hit
    result = await quantum_cache.get_branch(
        "tavern",
        sample_action,
        "no_twist",
    )

    assert result is not None
    assert quantum_cache._metrics.hits == 1
```

## Behavioral Differences

### Dice Rolling

**Old**: Dice rolled during GM reasoning, result baked into narrative.

**New**: Dice rolled at collapse time. Same branch can yield different outcomes.

```python
# Branch has variants for success/failure
# Dice roll at runtime determines which variant is used

# Roll 1: 2d10 = 15 vs DC 12 → SUCCESS variant
# Roll 2: 2d10 = 8 vs DC 12 → FAILURE variant
```

### Narrative Generation

**Old**: Fresh narrative for every turn.

**New**: Pre-generated narratives selected from cache.

This means:
- Faster responses (cache hit)
- More consistent quality (validated before caching)
- Less variety (same actions may get similar narratives)

### State Changes

**Old**: GM response parsed for state changes.

**New**: Explicit `StateDelta` objects applied atomically.

```python
# Old: "The merchant gives you a health potion"
# Parser extracts: item transfer to player

# New: StateDelta applied directly
StateDelta(
    delta_type=DeltaType.ITEM,
    entity_key="health_potion_001",
    operation="update",
    value={"holder_id": "player"},
)
```

## Fallback Behavior

The quantum pipeline gracefully degrades:

1. **Cache hit** → Instant response (<100ms)
2. **Cache miss** → Sync generation (3-8s)
3. **Generation failure** → Constrained narrator fallback
4. **Total failure** → Error message with retry option

```python
async def process_turn(self, ...) -> TurnResult:
    # Try cache
    if branch := await self._try_cache_hit(...):
        return await self._collapse_branch(branch, ...)

    # Sync generation
    try:
        return await self._generate_sync(...)
    except BranchGenerationError:
        pass

    # Narrator fallback
    try:
        return await self._narrator_fallback(...)
    except:
        return TurnResult(
            narrative="An error occurred. Please try again.",
            errors=["Failed to process turn"],
        )
```

## Monitoring

### Cache Statistics

```python
stats = pipeline.get_cache_stats()
print(f"Hit rate: {stats['hit_rate']}")
print(f"Cache size: {stats['size']}/{stats['max_size']}")
```

### Latency Tracking

```python
result = await pipeline.process_turn(...)
print(f"Turn latency: {result.latency_ms}ms")
print(f"Cache hit: {result.was_cache_hit}")
```

### Anticipation Status

```python
status = pipeline.get_anticipation_status()
print(f"Running: {status['running']}")
print(f"Branches generated: {status['branches_generated']}")
print(f"Current location: {status['current_location']}")
```

## Troubleshooting

### Low Cache Hit Rate

**Symptoms**: Most turns show "cache miss", high latency.

**Causes**:
- Anticipation disabled
- Player actions unpredictable
- TTL too short
- Match confidence too high

**Solutions**:
```bash
# Enable anticipation
QUANTUM_ANTICIPATION_ENABLED=true

# Lower match threshold
QUANTUM_MIN_MATCH_CONFIDENCE=0.6

# Increase cache TTL
QUANTUM_CACHE_TTL=300
```

### Stale Branch Errors

**Symptoms**: `StaleStateError` in logs, regeneration on most turns.

**Causes**:
- World state changing frequently
- Branches generated with old state version

**Solutions**:
- Reduce anticipation cycle time
- Increase state version checking granularity
- Invalidate cache on significant events

### Memory Usage

**Symptoms**: High memory consumption.

**Causes**:
- Cache too large
- Long narratives in branches

**Solutions**:
```bash
# Reduce cache size
QUANTUM_CACHE_SIZE=30

# Shorter TTL for faster eviction
QUANTUM_CACHE_TTL=120
```

## Reverting to Legacy

If issues arise, temporarily revert to legacy pipeline:

```bash
# Use GM pipeline
python -m src.main game play 1 --pipeline gm

# Or scene-first
python -m src.main game play 1 --pipeline scene-first
```

Report issues to help improve the quantum pipeline.
