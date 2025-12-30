# Scene-First Architecture - Detailed Design

## Core Principle

> "In real life, when I enter a room, things are just there."

The Scene-First Architecture inverts the current causality:

| Current System | Scene-First System |
|----------------|-------------------|
| Narrator describes → System extracts → World changes | World exists → System persists → Narrator describes |
| Narrator CAN invent, extraction may fail | Narrator CANNOT invent, validation enforced |
| Resolution happens in 5 places | Resolution happens in 1 place |
| Deferred spawning with 3 tracking systems | Immediate spawning, no tracking needed |

---

## System Components

### 1. World Mechanics (`src/world/world_mechanics.py`)

**Purpose**: Simulate the world independent of player observation.

**Responsibilities**:
- Determine NPC presence at locations (schedules, events, story)
- Introduce new world elements within constraints
- Generate world events
- Advance world state with time

**Key Design Decisions**:

1. **NPC Presence Sources** (in priority order):
   - `LIVES_HERE`: NPC's home location
   - `SCHEDULE`: NPC schedule says they're here now
   - `EVENT`: World event placed them here (thief, messenger)
   - `STORY`: Narrative logic suggests they should be here
   - `VISITING`: Came to see player or someone else

2. **Can Invent, With Constraints**:
   - May introduce new NPCs (e.g., "you have a school friend")
   - Must respect `SocialLimits` (max friends, rate limits)
   - Must respect physical plausibility (can't teleport)
   - Must have narrative purpose

3. **Constraint Examples**:
   ```python
   SocialLimits:
     MAX_CLOSE_FRIENDS = 5
     MAX_CASUAL_FRIENDS = 15
     MAX_NEW_RELATIONSHIPS_PER_WEEK = 3

   PhysicalLimits:
     # NPC must be able to reach location
     # Private spaces need reason for entry
     # Time of day matters (sleeping NPCs)
   ```

**Interface**:
```python
class WorldMechanics:
    def advance_world(
        self,
        location_key: str,
        location_type: str | None = None,
        is_player_home: bool = False,
    ) -> WorldUpdate

    def get_npcs_at_location(self, location_key: str) -> list[NPCPlacement]
    """Sync version: scheduled + resident + event-driven NPCs."""

    async def get_npcs_at_location_async(
        self,
        location_key: str,
        location_type: str = "general",
        scene_context: str = "",
    ) -> list[NPCPlacement]
    """Async version: includes story-driven NPCs via LLM."""

    def get_scheduled_npcs(self, location_key: str) -> list[NPCPlacement]
    def get_resident_npcs(self, location_key: str) -> list[NPCPlacement]
    def get_event_driven_npcs(self, location_key: str) -> list[NPCPlacement]

    async def get_story_driven_npcs(
        self,
        location_key: str,
        location_type: str,
        scene_context: str = "",
    ) -> list[NPCPlacement]
    """Uses LLM to determine if story needs an NPC appearance."""
```

---

### 2. Scene Builder (`src/world/scene_builder.py`)

**Purpose**: Populate locations with physical contents.

**Responsibilities**:
- Generate furniture appropriate to location type
- Generate items that logically belong
- Create atmospheric details
- Handle observation levels (entry → look → search)

**Key Design Decisions**:

1. **First Visit vs Return Visit**:
   - First visit: Generate full scene, persist everything
   - Return visit: Load from DB, only update dynamic elements

2. **Observation Levels**:
   ```
   ENTRY:   See obvious furniture, people, large items
   LOOK:    See additional details, items on surfaces
   SEARCH:  Find hidden items, look inside containers
   EXAMINE: Detailed inspection of specific thing
   ```

3. **Lazy Container Contents**:
   - Containers created with `contents_generated = False`
   - Contents generated when player opens/searches
   - Prevents over-generation on first visit

4. **Cannot Introduce NPCs**:
   - Scene Builder only does physical contents
   - NPCs come from World Mechanics
   - Clear separation of concerns

**Interface**:
```python
class SceneBuilder:
    async def build_scene(
        self,
        location_key: str,
        world_update: WorldUpdate,
        observation_level: ObservationLevel = ObservationLevel.ENTRY,
    ) -> SceneManifest

    async def generate_container_contents(
        self,
        container: Item,
        location: Location,
    ) -> list[ItemSpec]
    """Lazy-loads container contents when opened for first time."""
```

---

### 3. Scene Persister (`src/world/scene_persister.py`)

**Purpose**: Persist all generated content to database atomically.

**Responsibilities**:
- Create NPC entities with proper linkage
- Create items with storage locations
- Create furniture items
- Build narrator manifest from persisted data

**Key Design Decisions**:

1. **Atomic Transactions**:
   - All-or-nothing persistence
   - If any creation fails, rollback entire scene
   - No orphaned entities possible

2. **Manifest Building**:
   - After persistence, build `NarratorManifest`
   - Contains all entity keys
   - Becomes single source of truth for narrator

3. **Storage Location Handling**:
   - Items at location → Create `StorageLocation` with type `PLACE`
   - Items in container → Create `StorageLocation` with type `CONTAINER`
   - Items on person → Use entity's body storage

**Interface**:
```python
class ScenePersister:
    def persist_world_update(self, update: WorldUpdate) -> PersistedWorldUpdate
    def persist_scene(self, manifest: SceneManifest) -> PersistedScene
    def build_narrator_manifest(
        self,
        persisted_world: PersistedWorldUpdate,
        persisted_scene: PersistedScene,
    ) -> NarratorManifest
```

---

### 4. Constrained Narrator (`src/narrator/constrained_narrator.py`)

**Purpose**: Generate prose that only describes what exists.

**Responsibilities**:
- Generate engaging narrative
- Use [key] format for all entity references
- Never invent new entities
- Retry on validation failure

**Key Design Decisions**:

1. **[key] Format Requirement**:
   ```
   Narrator output:
   "You see [marcus_001] sitting on [bed_001], reading [book_001]."

   Display to player:
   "You see Marcus sitting on the bed, reading a leather-bound journal."
   ```

2. **Validation Before Display**:
   - Parse all `[key]` references
   - Verify each exists in manifest
   - Detect unkeyed mentions (heuristic)
   - Reject and retry if invalid

3. **Retry with Feedback**:
   - Up to 3 retries
   - Include validation errors in retry prompt
   - Fallback to safe generic narration if all fail

4. **Narration Types**:
   - `SCENE_ENTRY`: Describe location on arrival
   - `ACTION_RESULT`: Describe outcome of player action
   - `DIALOGUE`: NPC speech
   - `CLARIFICATION`: Ask for reference clarification
   - `AMBIENT`: General scene description

**Interface**:
```python
class ConstrainedNarrator:
    async def narrate(
        self,
        manifest: NarratorManifest,
        narration_type: NarrationType,
        context: NarrationContext,
    ) -> NarrationResult
```

---

### 5. Reference Resolver (`src/resolver/reference_resolver.py`)

**Purpose**: Resolve player references to entity keys.

**Responsibilities**:
- Match player text to manifest entities
- Handle pronouns, descriptors, partial names
- Detect and report ambiguity

**Key Design Decisions**:

1. **Resolution Priority**:
   ```
   1. Exact key match ("marcus_001")
   2. Exact display name ("Marcus")
   3. Partial display name ("the friend")
   4. Pronoun by gender ("him" → most recent male)
   5. Descriptor match ("the guy reading")
   ```

2. **Ambiguity Handling**:
   - If multiple candidates at same priority → ambiguous
   - Return `ClarificationRequired` with candidates
   - Game asks player to specify

3. **No More Deferred Spawning**:
   - Everything in manifest already exists in DB
   - Resolution is just lookup, never creation
   - Massively simplified logic

**Interface**:
```python
class ReferenceResolver:
    def __init__(self, manifest: NarratorManifest): ...

    def resolve(self, reference: str) -> ResolutionResult
```

---

## Graph Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                              TURN START                              │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │      WORLD MECHANICS          │
                    │                               │
                    │  • Query NPC schedules        │
                    │  • Check for events           │
                    │  • Maybe introduce elements   │
                    │  • Enforce constraints        │
                    │                               │
                    │  Output: WorldUpdate          │
                    └───────────────┬───────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │       SCENE BUILDER           │
                    │                               │
                    │  • First visit? Generate      │
                    │  • Return visit? Load         │
                    │  • Add observation details    │
                    │                               │
                    │  Output: SceneManifest        │
                    └───────────────┬───────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │       PERSIST SCENE           │
                    │                               │
                    │  • Create NPCs in DB          │
                    │  • Create items in DB         │
                    │  • Build NarratorManifest     │
                    │                               │
                    │  Output: NarratorManifest     │
                    └───────────────┬───────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │       PARSE INTENT            │
                    │                               │
                    │  • Pattern matching           │
                    │  • LLM classification         │
                    │                               │
                    │  Output: ParsedActions        │
                    └───────────────┬───────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                    ▼                               ▼
        ┌─────────────────┐             ┌─────────────────┐
        │   HAS ACTIONS   │             │   SCENE ONLY    │
        └────────┬────────┘             └────────┬────────┘
                 │                               │
                 ▼                               │
    ┌───────────────────────────┐               │
    │   RESOLVE REFERENCES      │               │
    │                           │               │
    │  • Match to manifest      │               │
    │  • Handle pronouns        │               │
    │  • Detect ambiguity       │               │
    └───────────┬───────────────┘               │
                │                               │
    ┌───────────┴───────────┐                   │
    │                       │                   │
    ▼                       ▼                   │
┌─────────┐         ┌─────────────┐             │
│RESOLVED │         │ AMBIGUOUS   │             │
└────┬────┘         └──────┬──────┘             │
     │                     │                    │
     ▼                     │                    │
┌───────────────────┐      │                    │
│ EXECUTE ACTIONS   │      │                    │
│                   │      │                    │
│ • Validate action │      │                    │
│ • Execute         │      │                    │
│ • Update state    │      │                    │
└─────────┬─────────┘      │                    │
          │                │                    │
          └────────────────┼────────────────────┘
                           │
                           ▼
              ┌───────────────────────────┐
              │   CONSTRAINED NARRATOR    │
              │                           │
              │  • Receive manifest       │
              │  • Generate prose         │
              │  • Use [key] format       │
              └───────────────┬───────────┘
                              │
                              ▼
              ┌───────────────────────────┐
              │   VALIDATE NARRATOR       │
              │                           │
              │  • Check all [key] refs   │
              │  • Detect unkeyed refs    │
              └───────────────┬───────────┘
                              │
              ┌───────────────┴───────────┐
              │                           │
              ▼                           ▼
        ┌──────────┐              ┌──────────┐
        │  VALID   │              │ INVALID  │
        └────┬─────┘              └────┬─────┘
             │                         │
             ▼                         │
      ┌────────────┐                   │
      │   OUTPUT   │                   │
      │            │                   │
      │ Strip keys │◄──────────────────┘
      │ Display    │      (retry with feedback)
      └────────────┘
```

---

## State Schema

```python
class GameState(TypedDict):
    # Existing fields
    session_id: int
    player_id: int
    player_location: str
    turn_number: int
    player_input: str
    game_time: dict  # GameTime as dict

    # New Scene-First fields
    world_update: dict | None          # WorldUpdate from World Mechanics
    scene_manifest: dict | None        # SceneManifest from Scene Builder
    narrator_manifest: dict | None     # NarratorManifest for narrator

    # Resolution fields
    parsed_actions: list[dict]         # From intent parser
    resolved_actions: list[dict]       # With entity_keys resolved
    needs_clarification: bool
    clarification_prompt: str | None
    clarification_candidates: list[dict]

    # Context flags
    just_entered_location: bool        # Triggers scene building
    observation_level: str             # ENTRY, LOOK, SEARCH, etc.

    # Output
    gm_response: str                   # Final display text
    narrator_raw: str                  # Raw output with [key] markers
    entity_references: list[dict]      # Parsed references from narrator
```

---

## Database Considerations

### Existing Models Used

1. **Entity** - NPCs created by World Mechanics
2. **NPCExtension** - NPC location, schedule, etc.
3. **Item** - Items created by Scene Builder
4. **StorageLocation** - Item placement
5. **Location** - Location records

### Potential New Fields

```python
# On Location model
scene_generated: bool = False  # Has scene been built?
scene_generated_at: datetime   # When was it built?

# On Item model (already exists)
owner_location_id: int  # Environmental items owned by location
visibility: str  # OBVIOUS, DISCOVERABLE, HIDDEN

# On StorageLocation (may need)
is_furniture: bool = False  # Distinguish furniture from containers
```

### No New Models Needed

The existing model structure should support Scene-First architecture. Key insight: furniture can be modeled as Items with `is_furniture=True` or a specific `ItemType`.

---

## Error Handling

### World Mechanics Failures

```python
try:
    update = await world_mechanics.advance_world(...)
except LLMError:
    # Fall back to schedule-only NPC presence
    update = world_mechanics.get_scheduled_only(...)
except ConstraintViolation as e:
    # Log constraint failure, proceed without new elements
    logger.warning(f"Constraint violation: {e}")
    update = WorldUpdate(npcs=scheduled_npcs, new_elements=[])
```

### Scene Builder Failures

```python
try:
    manifest = await scene_builder.build_scene(...)
except LLMError:
    # Fall back to minimal scene
    manifest = scene_builder.build_minimal_scene(location)
```

### Narrator Validation Failures

```python
for attempt in range(3):
    output = await narrator.generate(...)
    validation = validator.validate(output, manifest)

    if validation.valid:
        return output

    # Add error feedback for retry
    context = context.with_errors(validation.errors)

# Final fallback
return narrator.generate_safe_fallback(manifest)
```

---

## Performance Considerations

### LLM Calls Per Turn

| Scenario | World Mechanics | Scene Builder | Narrator | Total |
|----------|-----------------|---------------|----------|-------|
| New location | 1 | 1 | 1 | 3 |
| Same location, action | 0* | 0 | 1 | 1 |
| Same location, look | 0* | 1 | 1 | 2 |

*World Mechanics can be skipped if no significant time passed

### Optimizations

1. **Cache Scene Manifest**: Reuse between turns at same location
2. **Skip World Mechanics**: Only run on location change or time advance
3. **Use Haiku**: Scene Builder and World Mechanics can use faster model
4. **Batch NPC Queries**: Single query for all NPCs at location

### Caching Strategy

```python
class SceneCache:
    def __init__(self):
        self.manifests: dict[str, NarratorManifest] = {}
        self.timestamps: dict[str, datetime] = {}

    def get(self, location_key: str, max_age: timedelta) -> NarratorManifest | None:
        if location_key not in self.manifests:
            return None
        if datetime.now() - self.timestamps[location_key] > max_age:
            return None
        return self.manifests[location_key]

    def set(self, location_key: str, manifest: NarratorManifest):
        self.manifests[location_key] = manifest
        self.timestamps[location_key] = datetime.now()
```
