# World Server Implementation Plan

## Overview

This plan implements anticipatory generation to hide LLM latency. The system pre-generates likely next locations while the player reads narrative text.

**Goal**: Reduce perceived latency from 50-80 seconds to near-instant for most transitions.

---

## Phase 1: Anticipation Engine Foundation

**Objective**: Pre-generate likely next locations during player reading time.

### 1.1 Create Core Schemas

**File**: `src/world_server/schemas.py`

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

class GenerationStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"

@dataclass
class PreGeneratedScene:
    """Scene generated but not yet observed by player."""
    location_key: str
    scene_manifest: dict[str, Any]  # SceneManifest as dict
    npcs_present: list[str]         # Entity keys
    items_present: list[str]        # Item keys
    atmosphere: dict[str, Any]
    generated_at: datetime = field(default_factory=datetime.now)
    is_committed: bool = False
    expiry_seconds: int = 300       # 5 minutes default

    def is_stale(self) -> bool:
        """Check if pre-generated content has expired."""
        age = (datetime.now() - self.generated_at).total_seconds()
        return age > self.expiry_seconds

@dataclass
class LocationPrediction:
    """Predicted next location with probability."""
    location_key: str
    probability: float              # 0.0 to 1.0
    reason: str                     # "adjacent", "quest_target", "mentioned"

@dataclass
class AnticipationTask:
    """Task queued for background generation."""
    location_key: str
    priority: float                 # Higher = generate first
    status: GenerationStatus = GenerationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
```

**Tasks**:
- [ ] Create `src/world_server/__init__.py`
- [ ] Create `src/world_server/schemas.py` with above dataclasses
- [ ] Add tests in `tests/test_world_server/test_schemas.py`

---

### 1.2 Implement Pre-Generation Cache

**File**: `src/world_server/cache.py`

```python
import asyncio
from collections import OrderedDict
from datetime import datetime

class PreGenerationCache:
    """LRU cache for pre-generated scenes."""

    def __init__(self, max_size: int = 10):
        self.max_size = max_size
        self._cache: OrderedDict[str, PreGeneratedScene] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, location_key: str) -> PreGeneratedScene | None:
        """Get pre-generated scene if available and fresh."""
        async with self._lock:
            scene = self._cache.get(location_key)
            if scene is None:
                return None
            if scene.is_stale():
                del self._cache[location_key]
                return None
            # Move to end (LRU)
            self._cache.move_to_end(location_key)
            return scene

    async def put(self, scene: PreGeneratedScene) -> None:
        """Store pre-generated scene."""
        async with self._lock:
            # Evict oldest if at capacity
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
            self._cache[scene.location_key] = scene

    async def invalidate(self, location_key: str) -> None:
        """Remove a specific location from cache."""
        async with self._lock:
            self._cache.pop(location_key, None)

    async def invalidate_all_except(self, keep_key: str | None = None) -> None:
        """Invalidate all cached scenes except one."""
        async with self._lock:
            if keep_key:
                scene = self._cache.get(keep_key)
                self._cache.clear()
                if scene:
                    self._cache[keep_key] = scene
            else:
                self._cache.clear()

    async def stats(self) -> dict:
        """Return cache statistics."""
        async with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "locations": list(self._cache.keys()),
            }
```

**Tasks**:
- [ ] Create `src/world_server/cache.py`
- [ ] Add tests for LRU eviction
- [ ] Add tests for expiry handling
- [ ] Add tests for concurrent access

---

### 1.3 Implement Location Predictor

**File**: `src/world_server/predictor.py`

```python
from sqlalchemy.orm import Session

class LocationPredictor:
    """Predicts likely next player destinations."""

    def __init__(self, db: Session, session_id: int):
        self.db = db
        self.session_id = session_id

    async def predict_next_locations(
        self,
        current_location: str,
        recent_actions: list[str] | None = None,
        max_predictions: int = 3,
    ) -> list[LocationPrediction]:
        """Predict most likely next locations.

        Priority order:
        1. Adjacent locations (high base probability)
        2. Quest objective locations (boosted if active)
        3. Mentioned locations in recent dialogue
        """
        predictions: list[LocationPrediction] = []

        # 1. Get adjacent locations from spatial_layout
        adjacent = await self._get_adjacent_locations(current_location)
        for loc_key in adjacent:
            predictions.append(LocationPrediction(
                location_key=loc_key,
                probability=0.7,  # High base probability
                reason="adjacent",
            ))

        # 2. Check active quest targets
        quest_targets = await self._get_quest_target_locations()
        for loc_key in quest_targets:
            existing = next((p for p in predictions if p.location_key == loc_key), None)
            if existing:
                existing.probability = min(1.0, existing.probability + 0.2)
            else:
                predictions.append(LocationPrediction(
                    location_key=loc_key,
                    probability=0.5,
                    reason="quest_target",
                ))

        # 3. Check recently mentioned locations
        if recent_actions:
            mentioned = await self._extract_mentioned_locations(recent_actions)
            for loc_key in mentioned:
                existing = next((p for p in predictions if p.location_key == loc_key), None)
                if existing:
                    existing.probability = min(1.0, existing.probability + 0.1)
                else:
                    predictions.append(LocationPrediction(
                        location_key=loc_key,
                        probability=0.3,
                        reason="mentioned",
                    ))

        # Sort by probability descending
        predictions.sort(key=lambda p: p.probability, reverse=True)
        return predictions[:max_predictions]

    async def _get_adjacent_locations(self, location_key: str) -> list[str]:
        """Get locations connected via spatial_layout exits."""
        from src.managers.location_manager import LocationManager
        location_mgr = LocationManager(self.db, None)  # TODO: proper init
        location = location_mgr.get_location_by_key(location_key)
        if not location or not location.spatial_layout:
            return []
        exits = location.spatial_layout.get("exits", {})
        return list(exits.values())

    async def _get_quest_target_locations(self) -> list[str]:
        """Get locations that are active quest objectives."""
        # TODO: Query active tasks/quests for target locations
        return []

    async def _extract_mentioned_locations(self, actions: list[str]) -> list[str]:
        """Extract location mentions from recent player actions."""
        # TODO: NLP extraction or simple keyword matching
        return []
```

**Tasks**:
- [ ] Create `src/world_server/predictor.py`
- [ ] Implement `_get_adjacent_locations()` using LocationManager
- [ ] Implement `_get_quest_target_locations()` using TaskManager
- [ ] Add simple keyword extraction for mentioned locations
- [ ] Add tests with mock locations

---

### 1.4 Implement Anticipation Engine

**File**: `src/world_server/anticipation.py`

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

class AnticipationEngine:
    """Pre-generates content for predicted destinations."""

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        cache: PreGenerationCache,
        predictor: LocationPredictor,
        max_workers: int = 2,
    ):
        self.db = db
        self.game_session = game_session
        self.cache = cache
        self.predictor = predictor
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._running = False
        self._current_location: str | None = None
        self._generation_tasks: dict[str, AnticipationTask] = {}

    async def start(self, current_location: str) -> None:
        """Start anticipation for current player location."""
        self._running = True
        self._current_location = current_location
        asyncio.create_task(self._anticipation_loop())

    async def stop(self) -> None:
        """Stop anticipation."""
        self._running = False

    async def on_location_change(self, new_location: str) -> None:
        """Called when player moves to new location."""
        old_location = self._current_location
        self._current_location = new_location

        # Invalidate predictions based on old location
        await self.cache.invalidate_all_except(keep_key=new_location)

        # Cancel in-progress tasks for wrong predictions
        for task in self._generation_tasks.values():
            if task.status == GenerationStatus.IN_PROGRESS:
                if task.location_key != new_location:
                    task.status = GenerationStatus.EXPIRED

    async def get_pre_generated(self, location_key: str) -> PreGeneratedScene | None:
        """Get pre-generated scene if available."""
        return await self.cache.get(location_key)

    async def _anticipation_loop(self) -> None:
        """Background loop that pre-generates predicted locations."""
        while self._running:
            try:
                await self._run_anticipation_cycle()
            except Exception as e:
                # Log but don't crash
                print(f"Anticipation error: {e}")
            await asyncio.sleep(1.0)  # Check every second

    async def _run_anticipation_cycle(self) -> None:
        """Single anticipation cycle."""
        if not self._current_location:
            return

        # Get predictions
        predictions = await self.predictor.predict_next_locations(
            self._current_location,
            max_predictions=3,
        )

        # Queue generation for predictions not in cache
        for pred in predictions:
            cached = await self.cache.get(pred.location_key)
            if cached is None and pred.location_key not in self._generation_tasks:
                await self._queue_generation(pred)

    async def _queue_generation(self, prediction: LocationPrediction) -> None:
        """Queue a location for background generation."""
        task = AnticipationTask(
            location_key=prediction.location_key,
            priority=prediction.probability,
        )
        self._generation_tasks[prediction.location_key] = task

        # Run generation in thread pool
        loop = asyncio.get_event_loop()
        loop.run_in_executor(
            self.executor,
            self._generate_scene_sync,
            prediction.location_key,
        )

    def _generate_scene_sync(self, location_key: str) -> None:
        """Synchronous scene generation (runs in thread)."""
        task = self._generation_tasks.get(location_key)
        if not task:
            return

        task.status = GenerationStatus.IN_PROGRESS
        task.started_at = datetime.now()

        try:
            # TODO: Call actual scene builder
            # This is where we'd invoke the LLM
            scene = self._build_scene(location_key)

            # Store in cache
            asyncio.run(self.cache.put(scene))

            task.status = GenerationStatus.COMPLETED
            task.completed_at = datetime.now()
        except Exception as e:
            task.status = GenerationStatus.FAILED
            task.error = str(e)
        finally:
            # Clean up task tracking
            self._generation_tasks.pop(location_key, None)

    def _build_scene(self, location_key: str) -> PreGeneratedScene:
        """Build scene using existing SceneBuilder."""
        # TODO: Integrate with actual SceneBuilder
        # For now, placeholder
        return PreGeneratedScene(
            location_key=location_key,
            scene_manifest={},
            npcs_present=[],
            items_present=[],
            atmosphere={},
        )
```

**Tasks**:
- [ ] Create `src/world_server/anticipation.py`
- [ ] Integrate with actual `SceneBuilder` class
- [ ] Handle database session scoping for thread pool
- [ ] Add metrics/logging for prediction success rate
- [ ] Add tests for anticipation loop

---

### 1.5 Implement State Collapse Manager

**File**: `src/world_server/collapse.py`

```python
class StateCollapseManager:
    """Commits pre-generated state when player observes."""

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        cache: PreGenerationCache,
    ):
        self.db = db
        self.game_session = game_session
        self.cache = cache

    async def collapse_location(
        self,
        location_key: str,
        turn_number: int,
    ) -> tuple[dict, bool]:
        """Collapse state for location when player enters.

        Returns:
            (scene_manifest, was_pre_generated)
        """
        # Check cache first
        pre_gen = await self.cache.get(location_key)

        if pre_gen and not pre_gen.is_stale():
            # Use pre-generated content - instant!
            scene = await self._commit_pre_generated(pre_gen, turn_number)
            return scene, True
        else:
            # Fallback to synchronous generation
            scene = await self._generate_synchronous(location_key, turn_number)
            return scene, False

    async def _commit_pre_generated(
        self,
        pre_gen: PreGeneratedScene,
        turn_number: int,
    ) -> dict:
        """Persist pre-generated scene to database."""
        # Mark as committed
        pre_gen.is_committed = True

        # Persist entities to database
        # TODO: Use actual persistence logic from persist_scene_node

        # Build NarratorManifest
        narrator_manifest = self._build_narrator_manifest(pre_gen)

        return narrator_manifest

    async def _generate_synchronous(
        self,
        location_key: str,
        turn_number: int,
    ) -> dict:
        """Fallback: generate scene synchronously."""
        # TODO: Call SceneBuilder directly
        # This is the slow path (50-80 seconds)
        pass

    def _build_narrator_manifest(self, pre_gen: PreGeneratedScene) -> dict:
        """Build NarratorManifest from pre-generated scene."""
        return {
            "location_key": pre_gen.location_key,
            "npcs": pre_gen.npcs_present,
            "items": pre_gen.items_present,
            "atmosphere": pre_gen.atmosphere,
        }
```

**Tasks**:
- [ ] Create `src/world_server/collapse.py`
- [ ] Integrate with `PersistSceneNode` for entity persistence
- [ ] Build proper NarratorManifest structure
- [ ] Add metrics for cache hit rate
- [ ] Add tests for collapse flow

---

### 1.6 Integrate with Game Loop

**File**: `src/cli/commands/game.py` (modify)

```python
# Add after narrative display, before waiting for input

async def _trigger_anticipation(
    self,
    anticipation_engine: AnticipationEngine,
    current_location: str,
) -> None:
    """Trigger background anticipation after displaying narrative."""
    await anticipation_engine.on_location_change(current_location)
    # Anticipation loop runs in background
    # Pre-generates while player reads
```

**Tasks**:
- [ ] Initialize `AnticipationEngine` in game loop
- [ ] Call `_trigger_anticipation()` after narrative display
- [ ] Check `StateCollapseManager` before scene building
- [ ] Add `--anticipation` CLI flag to enable/disable
- [ ] Add observability hooks for anticipation events

---

### 1.7 Integrate with GM Pipeline

**File**: `src/gm/graph.py` (modify)

Add a collapse check before context building:

```python
async def check_pre_generated(state: GMState) -> GMState:
    """Check for pre-generated scene before building context."""
    collapse_mgr = state.get("_collapse_manager")
    if not collapse_mgr:
        return state

    location = state["player_location"]
    scene, was_cached = await collapse_mgr.collapse_location(
        location,
        state["turn_number"],
    )

    if was_cached:
        # Use pre-generated manifest
        state["_pre_generated_manifest"] = scene
        state["_anticipation_hit"] = True

    return state
```

**Tasks**:
- [ ] Add `check_pre_generated` node to GM graph
- [ ] Modify `GMContextBuilder` to use pre-generated manifest
- [ ] Pass collapse manager through state
- [ ] Add metrics for anticipation hit rate

---

## Phase 2: vLLM Integration

**Objective**: Enable parallel LLM requests for faster anticipation.

### 2.1 Install vLLM on Server

```bash
# On GX10 server
pip install vllm

# Start vLLM server
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-32B-Instruct \
    --port 8000 \
    --gpu-memory-utilization 0.9 \
    --max-model-len 8192
```

**Tasks**:
- [ ] Verify CUDA drivers on GX10
- [ ] Install vLLM
- [ ] Test with single request
- [ ] Benchmark throughput vs Ollama
- [ ] Document startup command

---

### 2.2 Create vLLM Provider

**File**: `src/llm/vllm_provider.py`

```python
from openai import AsyncOpenAI

class VLLMProvider(LLMProvider):
    """LLM provider using vLLM's OpenAI-compatible API."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        model: str = "Qwen/Qwen2.5-32B-Instruct",
    ):
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key="dummy",  # vLLM doesn't need real key
        )
        self.model = model

    async def complete(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Complete using vLLM."""
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            **kwargs,
        )

        return LLMResponse(
            content=response.choices[0].message.content,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            },
        )
```

**Tasks**:
- [ ] Create `src/llm/vllm_provider.py`
- [ ] Implement `complete()` method
- [ ] Implement `complete_with_tools()` if needed
- [ ] Add streaming support
- [ ] Add to provider registry
- [ ] Add config option for vLLM endpoint

---

### 2.3 Enable Parallel Anticipation

**File**: `src/world_server/anticipation.py` (modify)

```python
async def _run_parallel_generation(
    self,
    predictions: list[LocationPrediction],
) -> None:
    """Generate multiple scenes in parallel using vLLM."""
    tasks = []
    for pred in predictions:
        cached = await self.cache.get(pred.location_key)
        if cached is None:
            task = asyncio.create_task(
                self._generate_scene_async(pred.location_key)
            )
            tasks.append(task)

    # Wait for all to complete (vLLM handles batching)
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
```

**Tasks**:
- [ ] Modify anticipation to use async generation
- [ ] Remove ThreadPoolExecutor (not needed with async vLLM)
- [ ] Test parallel generation of 3 locations
- [ ] Measure speedup vs sequential

---

## Phase 3: Enhanced Prediction

**Objective**: Improve prediction accuracy to reduce wasted generation.

### 3.1 Track Prediction Success Rate

**File**: `src/world_server/metrics.py`

```python
@dataclass
class AnticipationMetrics:
    """Track anticipation performance."""
    predictions_made: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    wasted_generations: int = 0  # Generated but never used

    @property
    def hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0

    @property
    def waste_rate(self) -> float:
        if self.predictions_made == 0:
            return 0.0
        return self.wasted_generations / self.predictions_made
```

**Tasks**:
- [ ] Create `src/world_server/metrics.py`
- [ ] Instrument cache hits/misses
- [ ] Track wasted generations (expired without use)
- [ ] Add CLI command to view metrics
- [ ] Log metrics to file for analysis

---

### 3.2 Quest-Aware Prediction

**File**: `src/world_server/predictor.py` (modify)

```python
async def _get_quest_target_locations(self) -> list[str]:
    """Get locations from active quest objectives."""
    from src.managers.task_manager import TaskManager

    task_mgr = TaskManager(self.db, self.game_session)
    active_tasks = task_mgr.get_active_tasks()

    locations = []
    for task in active_tasks:
        if task.target_location_key:
            locations.append(task.target_location_key)
        # Also check task steps for location hints
        for step in task.steps:
            if step.location_key and step.status == "pending":
                locations.append(step.location_key)

    return list(set(locations))
```

**Tasks**:
- [ ] Implement `_get_quest_target_locations()`
- [ ] Add location fields to Task/TaskStep if missing
- [ ] Test with active quests
- [ ] Measure prediction improvement

---

### 3.3 Conversation-Based Hints

**File**: `src/world_server/predictor.py` (modify)

```python
async def _extract_mentioned_locations(
    self,
    recent_actions: list[str],
) -> list[str]:
    """Extract location mentions from recent dialogue."""
    # Get all known location names
    from src.managers.location_manager import LocationManager
    loc_mgr = LocationManager(self.db, None)
    all_locations = loc_mgr.get_all_locations()
    location_names = {
        loc.display_name.lower(): loc.location_key
        for loc in all_locations
    }

    # Simple keyword matching
    mentioned = []
    text = " ".join(recent_actions).lower()
    for name, key in location_names.items():
        if name in text:
            mentioned.append(key)

    return mentioned
```

**Tasks**:
- [ ] Implement location name extraction
- [ ] Consider fuzzy matching for typos
- [ ] Test with real dialogue
- [ ] Measure prediction improvement

---

## Phase 4: Lazy NPC Evaluation

**Objective**: Calculate NPC state on observation instead of continuous simulation.

### 4.1 Add Last Observed Tracking

**File**: `src/database/models/entities.py` (modify)

```python
# Add to NPCExtension
last_observed_turn: Mapped[int | None] = mapped_column(default=None)
last_observed_game_time: Mapped[str | None] = mapped_column(default=None)
```

**Tasks**:
- [ ] Add migration for new columns
- [ ] Update on player observation
- [ ] Add index for query performance

---

### 4.2 Implement Lazy NPC State Resolution

**File**: `src/world_server/npc_resolver.py`

```python
class LazyNPCResolver:
    """Resolves NPC state when player observes location."""

    async def resolve_npcs_at_location(
        self,
        location_key: str,
        current_game_time: str,
        current_game_day: int,
    ) -> list[NPCState]:
        """Calculate current NPC state at location.

        For each NPC:
        1. Check schedule for current time
        2. Calculate need decay since last observed
        3. Resolve any pending goal completions
        4. Return current state
        """
        # Get scheduled NPCs
        scheduled = await self._get_scheduled_npcs(location_key, current_game_time)

        results = []
        for npc in scheduled:
            # Calculate time since last observation
            time_delta = self._calculate_time_delta(
                npc.last_observed_game_time,
                npc.last_observed_turn,
                current_game_time,
            )

            # Apply accumulated need decay
            updated_needs = await self._apply_need_decay(npc, time_delta)

            # Resolve any goal completions
            goal_updates = await self._resolve_goals(npc, time_delta)

            # Build current state
            results.append(NPCState(
                entity_key=npc.entity_key,
                display_name=npc.display_name,
                current_activity=self._get_current_activity(npc, current_game_time),
                current_mood=self._calculate_mood(npc, updated_needs),
                needs=updated_needs,
                goal_updates=goal_updates,
            ))

        return results
```

**Tasks**:
- [ ] Create `src/world_server/npc_resolver.py`
- [ ] Implement `_apply_need_decay()` for time-based decay
- [ ] Implement `_resolve_goals()` for goal completion
- [ ] Integrate with scene building
- [ ] Add tests for lazy resolution

---

### 4.3 Integrate with Scene Building

**File**: `src/world/scene_builder.py` (modify)

```python
async def build_scene(
    self,
    location: Location,
    observation_level: ObservationLevel,
    use_lazy_npcs: bool = True,
) -> SceneManifest:
    """Build scene with optional lazy NPC resolution."""
    if use_lazy_npcs:
        npcs = await self.npc_resolver.resolve_npcs_at_location(
            location.location_key,
            self.time_state.current_time,
            self.time_state.current_day,
        )
    else:
        # Original eager loading
        npcs = await self._get_npcs_at_location(location)

    # ... rest of scene building
```

**Tasks**:
- [ ] Add `npc_resolver` to SceneBuilder
- [ ] Add `use_lazy_npcs` parameter
- [ ] Update tests for lazy resolution
- [ ] Benchmark lazy vs eager loading

---

## Testing Strategy

### Unit Tests

| Component | Test File | Coverage |
|-----------|-----------|----------|
| PreGenerationCache | `test_cache.py` | LRU, expiry, concurrency |
| LocationPredictor | `test_predictor.py` | Adjacent, quest, mentioned |
| AnticipationEngine | `test_anticipation.py` | Loop, queue, cancellation |
| StateCollapseManager | `test_collapse.py` | Hit, miss, commit |
| LazyNPCResolver | `test_npc_resolver.py` | Decay, goals, schedules |

### Integration Tests

| Scenario | Test | Expected |
|----------|------|----------|
| Player enters adjacent room | `test_anticipation_hit` | Cache hit, instant |
| Player enters unexpected room | `test_anticipation_miss` | Fallback, 50-80s |
| NPC state after 1 hour | `test_lazy_npc_decay` | Needs decayed correctly |
| Quest location prediction | `test_quest_prediction` | Quest target in predictions |

### Performance Tests

| Metric | Target | Measurement |
|--------|--------|-------------|
| Anticipation hit rate | >70% | Track over 100 transitions |
| Time to first byte (hit) | <100ms | Measure cache retrieval |
| Time to first byte (miss) | <2s | Measure fallback path |
| vLLM parallel speedup | >2x | Compare 3 sequential vs parallel |

---

## Configuration

**File**: `src/config.py` (add)

```python
@dataclass
class AnticipationConfig:
    enabled: bool = True
    max_predictions: int = 3
    cache_size: int = 10
    cache_expiry_seconds: int = 300
    use_vllm: bool = False
    vllm_endpoint: str = "http://localhost:8000/v1"
    use_lazy_npcs: bool = True
```

---

## Rollout Plan

### Stage 1: Internal Testing
- [ ] Implement Phase 1 with ThreadPoolExecutor
- [ ] Test with single location predictions
- [ ] Measure baseline hit rate

### Stage 2: vLLM Integration
- [ ] Install vLLM on GX10
- [ ] Switch to parallel generation
- [ ] Measure throughput improvement

### Stage 3: Enhanced Prediction
- [ ] Add quest awareness
- [ ] Add conversation hints
- [ ] Target 70%+ hit rate

### Stage 4: Production
- [ ] Add monitoring/alerting
- [ ] Document operation
- [ ] Enable by default

---

## Success Metrics

| Metric | Target | Why |
|--------|--------|-----|
| **Anticipation Hit Rate** | >70% | Most transitions should be instant |
| **Time to Response (hit)** | <500ms | Feels immediate |
| **Time to Response (miss)** | <80s | Same as current |
| **Wasted Generation Rate** | <30% | Minimize LLM waste |
| **Memory Usage** | <500MB | Reasonable cache size |
