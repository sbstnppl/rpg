# World Server Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              WORLD SERVER                                   │
│                                                                             │
│  ┌────────────────────┐         ┌────────────────────────────────────────┐ │
│  │  LocationPredictor │         │        AnticipationEngine              │ │
│  │                    │         │                                        │ │
│  │  • Adjacent locs   │────────▶│  • Background generation loop         │ │
│  │  • Quest targets   │         │  • Thread pool for LLM calls          │ │
│  │  • Mentioned locs  │         │  • Task queue management              │ │
│  └────────────────────┘         └──────────────┬─────────────────────────┘ │
│                                                │                           │
│                                                ▼                           │
│                                 ┌────────────────────────────────────────┐ │
│                                 │       PreGenerationCache               │ │
│                                 │                                        │ │
│                                 │  • LRU eviction (max 10 scenes)       │ │
│                                 │  • Expiry (5 min default)             │ │
│                                 │  • Thread-safe access                 │ │
│                                 └──────────────┬─────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
                                                 │
                                                 │ Pre-generated scenes
                                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              GAME SESSION                                   │
│                                                                             │
│  Player Input                                                               │
│       │                                                                     │
│       ▼                                                                     │
│  ┌──────────────┐    ┌─────────────────────────────────────────────────┐   │
│  │ Intent Parse │───▶│           StateCollapseManager                  │   │
│  └──────────────┘    │                                                 │   │
│                      │  1. Check cache for pre-generated scene         │   │
│                      │  2. If hit: commit to DB (instant)              │   │
│                      │  3. If miss: generate synchronously (slow)      │   │
│                      └───────────────────┬─────────────────────────────┘   │
│                                          │                                  │
│              ┌───────────────────────────┼───────────────────────────┐     │
│              │                           │                           │     │
│              ▼                           ▼                           ▼     │
│       [Cache Hit]                  [Cache Miss]               [Mechanics]  │
│           │                             │                           │     │
│           │ ~100ms                      │ 50-80s                    │     │
│           │                             │                           │     │
│           └──────────────┬──────────────┘                           │     │
│                          ▼                                          │     │
│                    ┌───────────┐                                    │     │
│                    │ Narrator  │◀───────────────────────────────────┘     │
│                    └─────┬─────┘                                          │
│                          │                                                 │
│                          ▼                                                 │
│                  Display to Player                                         │
│                          │                                                 │
│              ┌───────────▼───────────┐                                    │
│              │    READING TIME       │                                    │
│              │    (48-120 seconds)   │ ◀──── Anticipation pre-generates  │
│              └───────────────────────┘       next locations here          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. LocationPredictor

**Purpose**: Predict most likely next player destinations.

**Inputs**:
- Current player location
- Recent player actions/dialogue
- Active quests/tasks

**Outputs**:
- Ranked list of `LocationPrediction` with probabilities

**Algorithm**:
```
1. Get adjacent locations (base probability: 0.7)
2. Check quest target locations (boost: +0.2)
3. Extract mentioned locations from dialogue (boost: +0.1)
4. Sort by probability descending
5. Return top 3
```

**File**: `src/world_server/predictor.py`

---

### 2. AnticipationEngine

**Purpose**: Pre-generate scenes for predicted locations in background.

**Lifecycle**:
```
start() ──▶ anticipation_loop() ──▶ stop()
                   │
                   ├── predict locations
                   ├── check cache
                   ├── queue generation
                   └── store in cache
```

**Thread Model**:
- Main thread: Game loop, user interaction
- Background thread(s): LLM generation via ThreadPoolExecutor

**With vLLM**:
- All async (no thread pool needed)
- Parallel requests handled by vLLM's continuous batching

**File**: `src/world_server/anticipation.py`

---

### 3. PreGenerationCache

**Purpose**: Store pre-generated scenes until player observes them.

**Eviction Policy**: LRU (Least Recently Used)

**Expiry**: Scenes older than 5 minutes are considered stale.

**Thread Safety**: Uses `asyncio.Lock` for concurrent access.

**Data Structure**:
```python
OrderedDict[location_key, PreGeneratedScene]
```

**File**: `src/world_server/cache.py`

---

### 4. StateCollapseManager

**Purpose**: Handle "wave function collapse" when player observes a location.

**Flow**:
```
collapse_location(location_key)
         │
         ▼
   ┌─────────────┐
   │ Check Cache │
   └──────┬──────┘
          │
    ┌─────┴─────┐
    │           │
    ▼           ▼
[Cache Hit] [Cache Miss]
    │           │
    ▼           ▼
 Commit     Generate
 to DB      Sync
    │           │
    └─────┬─────┘
          ▼
  Return NarratorManifest
```

**Commit Process**:
1. Persist entities (NPCs, items) to database
2. Update location visit tracking
3. Build NarratorManifest for narrator node
4. Mark pre-generated scene as committed

**File**: `src/world_server/collapse.py`

---

### 5. LazyNPCResolver

**Purpose**: Calculate NPC state at observation time instead of continuous simulation.

**Philosophy**: NPCs don't "exist" when not observed. Their state is calculated when the player arrives based on:
- Elapsed time since last observation
- Schedule for current time
- Need decay rates
- Goal completion checks

**Benefits**:
- No background simulation needed
- Deterministic (same inputs = same outputs)
- Memory efficient (no cached NPC state)

**File**: `src/world_server/npc_resolver.py`

---

## Data Flow

### Normal Turn (Cache Hit)

```
1. Player: "go north"
   │
2. Intent Parse: Action(MOVE, direction="north")
   │
3. Resolve target: location_key = "tavern_common_room"
   │
4. StateCollapseManager.collapse_location("tavern_common_room")
   │
   ├── Cache lookup: HIT (pre-generated 30 seconds ago)
   │
   ├── Commit to DB: persist NPCs, items
   │
   └── Return: NarratorManifest
   │
5. Narrator generates prose using manifest
   │
6. Display to player (total time: ~500ms)
   │
7. WHILE PLAYER READS:
   │
   └── AnticipationEngine pre-generates:
       - "tavern_kitchen" (adjacent)
       - "tavern_upstairs" (adjacent)
       - "market_square" (quest target)
```

### Cache Miss (Fallback)

```
1. Player: "go to the old ruins"
   │
2. Intent Parse: Action(MOVE, target="old_ruins")
   │
3. StateCollapseManager.collapse_location("old_ruins")
   │
   ├── Cache lookup: MISS (unexpected destination)
   │
   ├── Generate synchronously: 50-80 seconds
   │   └── SceneBuilder.build_scene()
   │
   └── Return: NarratorManifest
   │
4. Narrator generates prose
   │
5. Display to player (total time: 50-80 seconds)
```

---

## State Transitions

### PreGeneratedScene Lifecycle

```
                    ┌─────────┐
                    │ Created │
                    └────┬────┘
                         │
                         ▼
                  ┌────────────┐
         ┌───────│ In Cache   │───────┐
         │       └──────┬─────┘       │
         │              │             │
    [Expired]     [Observed]    [Evicted]
         │              │             │
         ▼              ▼             ▼
    ┌─────────┐   ┌──────────┐   ┌─────────┐
    │ Stale   │   │ Committed│   │ Wasted  │
    │ (discard)│   │ (in DB)  │   │ (discard)│
    └─────────┘   └──────────┘   └─────────┘
```

### AnticipationTask States

```
PENDING ──▶ IN_PROGRESS ──▶ COMPLETED
                │
                ├──▶ FAILED (error)
                │
                └──▶ EXPIRED (location changed)
```

---

## Integration Points

### With GM Pipeline

**File**: `src/gm/graph.py`

```
START
  │
  ▼
┌─────────────────────┐
│ check_pre_generated │ ◀── NEW NODE
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  GMContextBuilder   │ (uses pre-generated if available)
└──────────┬──────────┘
           │
           ▼
       ... rest of GM pipeline ...
```

### With Game Loop

**File**: `src/cli/commands/game.py`

```python
# Initialize once per session
anticipation = AnticipationEngine(db, game_session, cache, predictor)
collapse_mgr = StateCollapseManager(db, game_session, cache)

# Per-turn flow
while True:
    # 1. Get player input
    player_input = await get_input()

    # 2. Run GM pipeline (collapse happens inside)
    result = await run_gm_pipeline(player_input, collapse_mgr)

    # 3. Display narrative
    display(result.narrative)

    # 4. Trigger anticipation (runs in background)
    await anticipation.on_location_change(result.new_location)

    # 5. Player reads while anticipation runs...
```

---

## Configuration

```python
@dataclass
class WorldServerConfig:
    # Anticipation settings
    anticipation_enabled: bool = True
    max_predictions: int = 3
    prediction_lookahead: int = 1  # Depth of location graph to consider

    # Cache settings
    cache_max_size: int = 10
    cache_expiry_seconds: int = 300

    # LLM backend
    use_vllm: bool = False
    vllm_endpoint: str = "http://localhost:8000/v1"
    vllm_model: str = "Qwen/Qwen2.5-32B-Instruct"

    # NPC resolution
    use_lazy_npcs: bool = True

    # Performance
    generation_thread_pool_size: int = 2  # Only used without vLLM
```

---

## Error Handling

### Generation Failure

```python
try:
    scene = await generate_scene(location_key)
    await cache.put(scene)
except Exception as e:
    log.error(f"Anticipation failed for {location_key}: {e}")
    # Don't crash - fallback to sync generation later
```

### Cache Corruption

```python
async def get(self, location_key: str) -> PreGeneratedScene | None:
    try:
        scene = self._cache.get(location_key)
        if scene and scene.is_stale():
            del self._cache[location_key]
            return None
        return scene
    except Exception as e:
        log.error(f"Cache error: {e}")
        self._cache.clear()  # Nuclear option
        return None
```

### vLLM Unavailable

```python
async def generate_scene_async(self, location_key: str) -> PreGeneratedScene:
    try:
        if self.config.use_vllm:
            return await self._generate_with_vllm(location_key)
        else:
            return await self._generate_with_ollama(location_key)
    except ConnectionError:
        log.warning("vLLM unavailable, falling back to Ollama")
        self.config.use_vllm = False
        return await self._generate_with_ollama(location_key)
```

---

## Observability

### Metrics to Track

| Metric | Type | Purpose |
|--------|------|---------|
| `anticipation_predictions` | Counter | Total predictions made |
| `anticipation_cache_hits` | Counter | Pre-generated scenes used |
| `anticipation_cache_misses` | Counter | Fallback to sync |
| `anticipation_wasted` | Counter | Generated but never used |
| `anticipation_generation_time` | Histogram | LLM call duration |
| `anticipation_cache_size` | Gauge | Current cache occupancy |

### Logging

```python
# Debug level - prediction details
log.debug(f"Predicted: {[p.location_key for p in predictions]}")

# Info level - cache events
log.info(f"Cache hit for {location_key}, age={age_seconds}s")
log.info(f"Cache miss for {location_key}, generating sync")

# Warning level - performance issues
log.warning(f"Prediction wrong: expected {predicted}, got {actual}")

# Error level - failures
log.error(f"Generation failed for {location_key}: {error}")
```

### CLI Commands

```bash
# View anticipation stats
rpg debug anticipation-stats

# Clear cache
rpg debug anticipation-clear

# Force pre-generate a location
rpg debug anticipation-generate <location_key>
```
