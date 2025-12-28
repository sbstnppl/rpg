# Timing Analysis

## Executive Summary

The World Server architecture leverages a critical timing insight:

| Activity | Duration |
|----------|----------|
| Player reading time | 48-120 seconds |
| LLM generation time | 50-80 seconds |
| **Overlap** | **Near-perfect** |

This means background generation during reading time can hide almost all LLM latency.

---

## Current Pipeline Timing

### GM Pipeline Breakdown

```
Player Input
    │
    ├── Intent validation ─────────────  50ms
    │
    ├── Context building ──────────────  200-500ms
    │   ├── DB queries
    │   ├── Manifest construction
    │   └── Prompt assembly
    │
    ├── LLM call (qwen3:32b) ──────────  50,000-80,000ms  ← BOTTLENECK
    │   ├── Input tokens: ~2,000
    │   ├── Output tokens: 500-800
    │   └── Speed: 10-12 tok/s
    │
    ├── Tool execution (if any) ───────  100-500ms
    │
    ├── Validation ────────────────────  100-300ms
    │
    └── Persistence ───────────────────  100-200ms
    │
    ▼
Total: 50-80 seconds (dominated by LLM)
```

### Token Analysis

| Component | Tokens | Time at 10 tok/s |
|-----------|--------|------------------|
| System prompt | ~1,700 | N/A (input) |
| User context | ~300 | N/A (input) |
| Scene description | 500-800 | 50-80s |
| Tool calls | 50-100 | 5-10s |
| **Total output** | **550-900** | **55-90s** |

---

## Player Reading Time

### Reading Speed Analysis

- Average adult reading speed: 200-250 words per minute
- Game narrative average: 200-400 words per turn

| Narrative Length | Reading Time |
|------------------|--------------|
| Short (100 words) | 24-30 seconds |
| Medium (200 words) | 48-60 seconds |
| Long (400 words) | 96-120 seconds |
| Very long (600 words) | 144-180 seconds |

### Conservative Estimate

For typical medium-length narratives:
- **Minimum reading time: 48 seconds**
- **Maximum reading time: 120 seconds**
- **Average: ~75 seconds**

This provides a **generation window of 48-120 seconds** while the player reads.

---

## Anticipation Budget

### With Single LLM (Ollama/Sequential)

```
Reading time: 75 seconds (average)
Generation time: 65 seconds (average)
─────────────────────────────────
Available: 75 seconds
Can generate: 1 scene

Adjacent locations: 3 (typical)
Coverage: 33%
```

**Problem**: Only 1 of 3 adjacent locations can be pre-generated.

### With vLLM (Parallel)

```
Reading time: 75 seconds (average)
Generation time: 65 seconds each
Parallel factor: 3 (concurrent requests)
─────────────────────────────────
Available: 75 seconds
Can generate: 3 scenes simultaneously

Adjacent locations: 3 (typical)
Coverage: 100%
```

**Benefit**: All adjacent locations can be pre-generated in parallel.

---

## Latency Comparison

### Current (No Anticipation)

```
Every transition: 50-80 seconds wait

Player experience:
[action] ──── 60 seconds waiting ──── [response]
```

### With Anticipation (Cache Hit)

```
Cache hit transition: <500ms

Player experience:
[action] ── instant ── [response]
```

### With Anticipation (Cache Miss)

```
Cache miss transition: 50-80 seconds (same as current)

Player experience:
[action] ──── 60 seconds waiting ──── [response]
```

### Expected Distribution

With 70% prediction accuracy:

| Scenario | Frequency | Latency |
|----------|-----------|---------|
| Cache hit | 70% | <500ms |
| Cache miss | 30% | 50-80s |
| **Weighted average** | | **~18 seconds** |

This is a **70-75% reduction** in average perceived latency.

---

## vLLM vs Ollama Performance

### Benchmark Data (2025)

| Metric | Ollama | vLLM | Improvement |
|--------|--------|------|-------------|
| Peak throughput | 41 TPS | 793 TPS | 19x |
| P99 latency | 673ms | 80ms | 8x |
| Concurrent requests | 1 (queue) | Many (batch) | N/A |

### For This Use Case

| Scenario | Ollama | vLLM |
|----------|--------|------|
| Generate 1 scene | 65s | 65s |
| Generate 3 scenes sequentially | 195s | N/A |
| Generate 3 scenes in parallel | 195s (queued) | ~70s (batched) |

**Key Insight**: vLLM's continuous batching means 3 parallel requests take only slightly longer than 1 request due to efficient GPU utilization.

---

## Detailed Timing Breakdown

### Cache Hit Path

```
collapse_location() called
    │
    ├── Cache lookup ─────────────────  1ms
    │
    ├── Staleness check ──────────────  1ms
    │
    ├── Entity persistence ───────────  50-100ms
    │   ├── NPCs: 10-20ms each (2-5 NPCs)
    │   └── Items: 5-10ms each (3-10 items)
    │
    ├── Build NarratorManifest ───────  10-20ms
    │
    └── Return ───────────────────────  1ms
    │
    ▼
Total: 100-200ms
```

### Cache Miss Path (Fallback)

```
collapse_location() called
    │
    ├── Cache lookup ─────────────────  1ms (MISS)
    │
    ├── Generate scene sync ──────────  50,000-80,000ms
    │   ├── WorldMechanics.get_npcs()
    │   ├── SceneBuilder.build_scene()
    │   └── LLM call for furniture/items
    │
    ├── Entity persistence ───────────  50-100ms
    │
    └── Return ───────────────────────  1ms
    │
    ▼
Total: 50-80 seconds
```

### Anticipation Loop Timing

```
Every 1 second:
    │
    ├── Get predictions ──────────────  10-50ms
    │   ├── Query adjacent locations
    │   ├── Query quest targets
    │   └── Extract mentioned locations
    │
    ├── Check cache for each ─────────  1-5ms
    │
    ├── Queue generation ─────────────  1ms per location
    │
    └── Background generation starts ─  async
    │
    ▼
Loop overhead: ~60ms (negligible)
```

---

## Optimization Strategies

### 1. Reduce Token Count

Current system prompt: ~1,700 tokens

| Optimization | Reduction | New Total |
|--------------|-----------|-----------|
| Minimal context mode | 70% | ~500 tokens |
| Drop grounding manifest | 10% | ~1,530 tokens |
| Compress turn history | 15% | ~1,445 tokens |

**Impact**: 40% reduction in input processing time.

### 2. Use Smaller Model for Narration

| Model | Speed | Quality |
|-------|-------|---------|
| qwen3:32b | 10-12 tok/s | High |
| qwen3:8b | 30-40 tok/s | Medium |
| magmell:7b | 40-50 tok/s | Medium |

**Strategy**: Use qwen3:32b for world logic, faster model for prose narration.

### 3. Speculative Scene Elements

Pre-generate common elements that don't depend on player:
- Furniture layouts (by location type)
- Atmospheric descriptions (by time of day)
- NPC idle activities

**Impact**: Reduce per-scene generation by 20-30%.

### 4. Progressive Disclosure

Generate only what's visible at ENTRY observation level first:
- Obvious items
- Present NPCs
- Basic atmosphere

Defer LOOK/SEARCH level details until requested.

**Impact**: 30-40% faster initial scene generation.

---

## Memory Analysis

### Cache Memory Usage

| Component | Size per Scene | With 10 Scenes |
|-----------|---------------|----------------|
| SceneManifest (JSON) | ~10-20 KB | 100-200 KB |
| NPC data | ~2-5 KB per NPC | 20-50 KB |
| Item data | ~1-2 KB per item | 10-30 KB |
| Atmosphere | ~1-2 KB | 10-20 KB |
| **Total per scene** | **~20-50 KB** | **200-500 KB** |

**Conclusion**: Cache memory usage is negligible (<1 MB for 10 scenes).

### vLLM Memory Usage

| Model | VRAM Required |
|-------|---------------|
| qwen3:32b (FP16) | ~64 GB |
| qwen3:32b (INT8) | ~32 GB |
| qwen3:32b (INT4) | ~16 GB |

**Recommendation**: Use INT4 quantization on GX10 if VRAM is limited.

---

## Timing Targets

### Minimum Viable Product

| Metric | Target |
|--------|--------|
| Anticipation hit rate | >50% |
| Cache hit latency | <500ms |
| Cache miss latency | <80s (unchanged) |
| Memory usage | <500MB |

### Optimized System

| Metric | Target |
|--------|--------|
| Anticipation hit rate | >70% |
| Cache hit latency | <200ms |
| Cache miss latency | <60s (improved) |
| Memory usage | <500MB |

### Stretch Goals

| Metric | Target |
|--------|--------|
| Anticipation hit rate | >85% |
| Cache hit latency | <100ms |
| All transitions | <5s perceived |

---

## Measurement Plan

### Instrumentation Points

```python
# Timing decorator
@measure_time("anticipation.collapse")
async def collapse_location(self, location_key: str) -> tuple:
    ...

# Event emission
self.metrics.emit("anticipation.cache_hit", {
    "location": location_key,
    "age_seconds": age,
    "latency_ms": latency,
})
```

### Metrics to Track

| Metric | Type | Aggregation |
|--------|------|-------------|
| `anticipation.predictions` | Counter | Sum |
| `anticipation.cache_hit` | Counter | Sum |
| `anticipation.cache_miss` | Counter | Sum |
| `anticipation.hit_rate` | Gauge | Average |
| `anticipation.latency_hit` | Histogram | P50, P95, P99 |
| `anticipation.latency_miss` | Histogram | P50, P95, P99 |
| `anticipation.generation_time` | Histogram | P50, P95, P99 |
| `anticipation.wasted` | Counter | Sum |

### Reporting

Weekly report:
```
Anticipation Performance Report
───────────────────────────────
Period: 2024-01-01 to 2024-01-07
Total transitions: 1,247
Cache hits: 891 (71.5%)
Cache misses: 356 (28.5%)
Average hit latency: 187ms
Average miss latency: 62,341ms
Wasted generations: 234 (18.8%)

Top predicted locations:
1. tavern_common_room: 89% hit rate
2. market_square: 76% hit rate
3. player_home: 92% hit rate

Worst predictions:
1. old_ruins: 12% hit rate (unexpected visits)
2. secret_cave: 0% hit rate (not predicted)
```

---

## Conclusion

The anticipation architecture is viable because:

1. **Timing overlap**: 48-120s reading time matches 50-80s generation time
2. **vLLM parallelism**: Can pre-generate 3 locations simultaneously
3. **High locality**: Players mostly move to adjacent locations
4. **Low memory cost**: <500MB for full cache

Expected improvement: **70-75% reduction in average perceived latency**.
