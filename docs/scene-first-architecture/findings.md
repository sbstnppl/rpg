# Scene-First Architecture - Findings and Analysis

This document captures the analysis that led to the Scene-First Architecture design. Read this to understand WHY we're making these changes.

---

## Current System Problems

### Problem 1: Narrator Invents Entities That May Not Get Persisted

**Symptom**: Narrator mentions "a merchant approaches" but no merchant entity exists in DB.

**Root Cause**: Original design had Narrator = GM + Tools. Narrator could call tools to spawn entities, but tool usage wasn't guaranteed.

**Attempted Fix**: Moved to "system authority" where narrator only narrates. But then the system struggled to know WHAT to persist from narrative.

**Commits Showing This**:
- Multiple commits trying to extract entities from narrative
- `ItemExtractor`, `NPCExtractor`, `LocationExtractor` classes
- Still fragile because extraction is lossy

### Problem 2: Fragmented Reference Resolution

**Symptom**: "Talk to her" fails or resolves to wrong entity.

**Root Cause**: Resolution logic spread across 5 places, each with partial context:

| Location | What It Knows | Gap |
|----------|--------------|-----|
| `IntentParser._resolve_targets()` | Entity names at location | No pronouns, no recency |
| `LLMClassifier` | Recent text | Not what actually exists |
| `DiscourseManager` | Structured mentions | May not be spawned |
| `_resolve_and_spawn_target()` | Can query DB | Different rules than others |
| `ActionValidator` | DB ground truth | Too late in pipeline |

**Commits Showing This**:
- `4853c3b` - Add recent_mentions for pronoun resolution
- `6f4172f` - Fix pronoun handling breaking NPC references
- `b23f658` - Full discourse-aware system (still partial fix)

### Problem 3: Deferred Spawning Complexity

**Symptom**: Items and NPCs mentioned in narrative get "lost" or cause orphaning.

**Root Cause**: Three parallel tracking systems evolved independently:

1. `Turn.mentioned_items` - For decorative items
2. `Turn.mentioned_npcs` - For background NPCs
3. `Turn.mentioned_entities` - For discourse tracking

These don't talk to each other. Race conditions occur when player references something between mention and spawn.

**Commits Showing This**:
- `e958034` - Fix item orphaning when dropping
- `3bfed5d` - Items not persisted in INFO mode
- `e338827` - Regex-based item detection causing false positives

### Problem 4: No Clarification Path for Ambiguous References

**Symptom**: System guesses at ambiguous references instead of asking.

**Example**: "Talk to her" when 3 women present → system picks one (often wrong)

**Root Cause**: No architectural support for clarification. Resolution either succeeds or fails silently.

### Problem 5: Orphaned Entities

**Symptom**: Items created without location, NPCs created without proper linkage.

**Root Cause**: Just-in-time spawning happens mid-execution with partial context. The spawn might succeed but linkage (location, owner) might fail.

**Commits Showing This**:
- `e958034` - Fix drop_item not creating storage location
- State integrity validator added to catch and fix orphans after the fact

---

## Key Insights

### Insight 1: Causality Is Backwards

**Current**: Narrator describes → System extracts → World changes

**Reality**: World exists → Player observes → Description follows

The system should match reality. Build the world, THEN describe it.

### Insight 2: Separation of Concerns

Three distinct responsibilities are currently conflated:

1. **World Simulation**: What exists, where, why
2. **Physical Description**: What things look like
3. **Narrative Prose**: How to describe it engagingly

These should be separate components with clear interfaces.

### Insight 3: Structured Output Eliminates Extraction

If LLMs output structured data when creating things, we don't need to extract from prose. Extraction is inherently lossy.

### Insight 4: Validation Is Easier Than Extraction

It's easier to check "did narrator only reference things from this list?" than "what new things did narrator introduce?"

Validation is deterministic. Extraction requires another LLM call or error-prone regex.

### Insight 5: World Mechanics Can Invent, Narrator Cannot

The creative freedom should be in WORLD BUILDING, not NARRATION.

- World Mechanics: "There should be a school friend here" → Creates with constraints
- Narrator: "Marcus sits on the bed" → Only describes what exists

---

## Design Decisions and Rationale

### Decision 1: Two-Phase World Building

**Choice**: Separate World Mechanics (NPCs, events) from Scene Builder (physical contents)

**Rationale**:
- NPCs require different constraints than furniture
- NPC placement has social/schedule logic
- Physical contents have location-type logic
- Easier to test and reason about separately

**Alternative Considered**: Single "Scene Generator" for everything
**Why Rejected**: Mixed concerns, harder to apply appropriate constraints

### Decision 2: Narrator Uses [key] Format

**Choice**: Require narrator to use `[entity_key]` markers in output

**Rationale**:
- Makes validation deterministic (regex, not LLM)
- Creates explicit link between prose and entities
- Easy to strip for display
- Catches both invalid references AND unkeyed mentions

**Alternative Considered**: Post-hoc entity extraction from prose
**Why Rejected**: Already tried, too lossy

### Decision 3: Immediate Persistence, No Deferred Spawning

**Choice**: Persist all entities before narrator runs

**Rationale**:
- No tracking systems needed
- No race conditions
- Resolution is just DB lookup
- No orphaning possible

**Alternative Considered**: Keep deferred spawning but improve tracking
**Why Rejected**: Fundamental complexity remains

### Decision 4: Realistic Constraints for World Mechanics

**Choice**: Hard limits on social/physical plausibility

**Rationale**:
- Prevents absurd situations (265 school friends)
- Makes world feel coherent
- Constraints can be setting-specific
- Easy to test and verify

**Examples**:
```python
MAX_CLOSE_FRIENDS = 5
MAX_NEW_RELATIONSHIPS_PER_WEEK = 3
# Can't place NPC in locked room without key
# Can't place NPC across the world instantly
```

### Decision 5: Observation Levels for Progressive Detail

**Choice**: Generate scene contents based on observation level (ENTRY → LOOK → SEARCH)

**Rationale**:
- Don't over-generate on first visit
- Creates exploration gameplay
- Hidden items remain hidden until searched
- More realistic perception model

### Decision 6: Clarification Flow for Ambiguity

**Choice**: When resolution is ambiguous, ask player instead of guessing

**Rationale**:
- Better player experience than wrong guess
- Prevents frustration from "wrong target" actions
- Natural conversational flow
- Simple to implement with new architecture

---

## What We're Keeping

### Keep: DiscourseManager Concept

The idea of tracking entity mentions with gender, descriptors, relationships is good. We're keeping this as part of the `NarratorManifest` structure.

### Keep: SceneContext Pattern

The `SceneContext` dataclass that holds entities, items, locations is useful. We're expanding it to `NarratorManifest`.

### Keep: ActionType and Action

The parsing layer's action types and structures are fine. Resolution changes, but parsing doesn't.

### Keep: Validation → Execution Flow

The subturn processor's pattern of validate-then-execute is correct. We're just ensuring resolution happens before validation.

---

## What We're Removing/Replacing

### Remove: _resolve_and_spawn_target()

**Location**: `src/agents/nodes/subturn_processor_node.py:36-107`

**Reason**: JIT spawning with partial context causes orphaning. Replaced by upfront persistence.

### Remove: IntentParser._resolve_targets()

**Location**: `src/parser/intent_parser.py:148-228`

**Reason**: Partial resolution with incomplete context. Replaced by ReferenceResolver with full manifest.

### Simplify: DiscourseManager

**Keep**: Entity extraction structure
**Remove**: Spawning responsibility, resolve_reference complexity

The new `ReferenceResolver` handles resolution. `DiscourseManager` extraction might feed into World Mechanics for story-driven NPC placement.

### Remove: Turn.mentioned_items, Turn.mentioned_npcs

**Not immediately** - keep columns but stop using them. New system doesn't need deferred tracking.

---

## Risk Assessment

### Risk 1: Performance (Two LLM Calls Before Narrator)

**Mitigation**:
- Cache scene manifests between turns at same location
- Skip World Mechanics when no time passed
- Use Haiku for World Mechanics and Scene Builder

### Risk 2: World Mechanics Creates Too Much

**Mitigation**:
- Strong constraints on new element introduction
- Rate limiting on new relationships
- Log all introductions for debugging

### Risk 3: Narrator Validation False Positives

**Mitigation**:
- Allow synonyms in [key] format: `[bed_001:the wooden bed]`
- Tune unkeyed reference detection carefully
- Safe fallback if validation keeps failing

### Risk 4: Complexity of New System

**Mitigation**:
- Implement incrementally with feature flag
- Comprehensive tests at each phase
- Can run old and new graphs in parallel during transition

---

## Testing Strategy

### Unit Tests Per Component

Each component has isolated tests:
- World Mechanics: Constraint enforcement, NPC placement logic
- Scene Builder: Scene generation, observation levels
- Persister: DB operations, manifest building
- Narrator: [key] format usage, validation
- Resolver: Resolution priority, ambiguity detection

### Integration Tests

Full flow tests:
- Enter new location → World Mechanics → Scene Builder → Persist → Narrator
- Action with resolved reference → Execute → Narrator
- Ambiguous reference → Clarification prompt

### Manual Testing Scenarios

1. Enter bedroom, verify appropriate contents
2. Talk to NPC using pronoun, verify correct resolution
3. Multiple same-gender NPCs, verify clarification asked
4. Search room, verify hidden items revealed
5. Return to location, verify same contents

---

## Migration Path

### Phase 1: Build New Components (Non-Breaking)

Create all new components without touching existing code. Test in isolation.

### Phase 2: Feature Flag Integration

Add feature flag to switch between old graph and new graph. Both work.

### Phase 3: Parallel Running

Run both graphs, compare results. Catch discrepancies.

### Phase 4: Gradual Rollout

Switch to new graph as default. Keep old graph available for fallback.

### Phase 5: Cleanup

Remove old code paths once new system is stable.

---

## Open Questions

### Question 1: Furniture vs Items

Should furniture be separate model or just Item with `is_furniture=True`?

**Current Thinking**: Use Item with flag. Simpler, leverages existing code.

### Question 2: Container Contents Generation

When should container contents be generated?

**Current Thinking**: Lazy-load on open/search. Prevents over-generation.

### Question 3: Setting-Specific Constraints

How do constraints vary by setting (medieval, modern, sci-fi)?

**Current Thinking**: `SocialLimits.for_setting(setting_key)` factory method.

### Question 4: NPC Schedule Integration

How does World Mechanics interact with existing NPC schedules?

**Current Thinking**: Query schedules first, then overlay event/story placement.
