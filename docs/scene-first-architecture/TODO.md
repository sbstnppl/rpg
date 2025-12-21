# Scene-First Architecture - Implementation TODO

## Overview

This document tracks the implementation of the Scene-First Architecture. Each section represents a phase, and tasks should be completed in order within each phase. Phases can overlap where noted.

**Estimated Scope**: ~2000 lines of new code, ~500 lines of modifications

---

## Phase 1: Foundation - Schemas and Constraints

### 1.1 Create Schema Module
- [x] Create `src/world/__init__.py`
- [x] Create `src/world/schemas.py` with all Pydantic models:
  - [x] `WorldUpdate` - Output from World Mechanics
  - [x] `NPCPlacement` - NPC at a location with reason
  - [x] `PresenceReason` - Enum (SCHEDULE, EVENT, STORY, LIVES_HERE, VISITING)
  - [x] `NewElement` - New world element being introduced
  - [x] `WorldEvent` - Event occurring in world
  - [x] `SceneManifest` - Complete scene state
  - [x] `FurnitureSpec` - Furniture in scene
  - [x] `ItemSpec` - Item in scene
  - [x] `SceneNPC` - NPC in scene
  - [x] `Atmosphere` - Sensory details
  - [x] `ItemVisibility` - Enum (OBVIOUS, DISCOVERABLE, HIDDEN)
  - [x] `ObservationLevel` - Enum (NONE, ENTRY, LOOK, SEARCH, EXAMINE)
  - [x] `NarratorManifest` - What narrator is allowed to reference
  - [x] `EntityRef` - Reference info for narrator

### 1.2 Create Constraint System
- [x] Create `src/world/constraints.py`:
  - [x] `RealisticConstraintChecker` class
  - [x] `SocialLimits` dataclass with defaults
  - [x] `check_social_constraints()` - Validate NPC introductions
  - [x] `check_event_constraints()` - Validate event frequency
  - [x] `check_physical_constraints()` - Validate physical plausibility
  - [x] `ConstraintResult` schema

### 1.3 Tests for Phase 1
- [x] Create `tests/test_world/__init__.py`
- [x] Create `tests/test_world/test_schemas.py` - Schema validation tests (53 tests)
- [x] Create `tests/test_world/test_constraints.py` - Constraint logic tests (40 tests)

**Phase 1 Complete When**: All schemas defined, constraints logic working, tests pass

---

## Phase 2: World Mechanics

### 2.1 Core World Mechanics
- [x] Create `src/world/world_mechanics.py`:
  - [x] `WorldMechanics` class
  - [x] `__init__(db, game_session, llm_provider)`
  - [x] `advance_world()` - Main entry point
  - [x] `get_npcs_at_location()` - Determine NPC presence
  - [x] `get_scheduled_npcs()` - Query NPC schedules
  - [x] `get_resident_npcs()` - NPCs who live at location
  - [ ] `_get_event_driven_npcs()` - NPCs from events (deferred to Phase 7)
  - [ ] `_get_story_driven_npcs()` - NPCs from narrative needs (deferred to Phase 7)
  - [x] `maybe_introduce_element()` - Introduce new elements with constraints
  - [x] `get_relationship_counts()` - Count player relationships by category
  - [x] `check_placement_constraints()` - Validate NPC placements

### 2.2 World Mechanics LLM Integration
- [x] Create prompt template in `data/templates/world_mechanics.jinja2`
- [ ] Implement `_call_world_mechanics_llm()` method (deferred to Phase 7)
- [ ] Handle structured output parsing (deferred to Phase 7)
- [x] Add constraint checking before accepting LLM suggestions

### 2.3 Tests for Phase 2
- [x] Create `tests/test_world/test_world_mechanics.py` (25 tests):
  - [x] Test scheduled NPC presence
  - [x] Test resident NPC presence
  - [x] Test constraint enforcement (social limits)
  - [x] Test constraint enforcement (physical plausibility)
  - [x] Test new element introduction with valid constraints
  - [x] Test new element rejection when constraints violated
  - [x] Test time context handling
  - [x] Test relationship counting

**Phase 2 Complete When**: World Mechanics correctly determines NPC presence with constraints

---

## Phase 3: Scene Builder

### 3.1 Core Scene Builder
- [x] Create `src/world/scene_builder.py`:
  - [x] `SceneBuilder` class
  - [x] `__init__(db, game_session, llm_provider)`
  - [x] `build_scene()` - Main entry point
  - [x] `_build_first_visit()` - Generate scene for new location
  - [x] `_load_existing_scene()` - Load from DB for return visit
  - [x] `_filter_by_observation_level()` - Filter items based on observation level
  - [ ] `_generate_container_contents()` - Lazy-load container contents (deferred to Phase 4)

### 3.2 Scene Builder LLM Integration
- [x] Create prompt template in `data/templates/scene_builder.jinja2`
- [x] Implement `_call_scene_builder_llm()` method
- [x] Handle structured output for furniture, items, atmosphere

### 3.3 Location Templates (Optional Enhancement)
- [ ] Create `src/world/location_templates.py`:
  - [ ] `LocationTemplate` dataclass
  - [ ] Default templates for common locations (bedroom, tavern, shop, etc.)
  - [ ] Template loading from `data/templates/locations/`

### 3.4 Tests for Phase 3
- [x] Create `tests/test_world/test_scene_builder.py` (21 tests):
  - [x] Test first visit scene generation
  - [x] Test return visit loading
  - [x] Test observation level progression
  - [x] Test container content hiding (contents visible only when opened)

**Phase 3 Complete When**: Scene Builder generates appropriate scene contents

---

## Phase 4: Persistence Layer

### 4.1 Scene Persister
- [ ] Create `src/world/scene_persister.py`:
  - [ ] `ScenePersister` class
  - [ ] `persist_world_update()` - Persist World Mechanics output
  - [ ] `persist_scene()` - Persist Scene Builder output
  - [ ] `build_narrator_manifest()` - Build manifest for narrator
  - [ ] `_create_npc()` - Create new NPC with full linkage
  - [ ] `_create_item()` - Create new item with location
  - [ ] `_create_furniture()` - Create furniture item

### 4.2 Database Considerations
- [ ] Review `StorageLocation` model - ensure it supports scene items
- [ ] Review `Item` model - ensure `owner_location_id` works for scene items
- [ ] Consider if new model needed for furniture vs items
- [ ] Add `scene_generated` flag to Location model (tracks if scene built)

### 4.3 Tests for Phase 4
- [ ] Create `tests/test_world/test_scene_persister.py`:
  - [ ] Test NPC creation with location
  - [ ] Test item creation with storage location
  - [ ] Test furniture creation
  - [ ] Test manifest building
  - [ ] Test atomic transaction (all or nothing)

**Phase 4 Complete When**: All scene contents persist correctly to DB

---

## Phase 5: Constrained Narrator

### 5.1 Narrator Validator
- [ ] Create `src/narrator/validator.py`:
  - [ ] `NarratorValidator` class
  - [ ] `validate()` - Check output against manifest
  - [ ] `_extract_key_references()` - Find all [key] patterns
  - [ ] `_detect_unkeyed_references()` - Catch mentions without keys
  - [ ] `ValidationResult` schema
  - [ ] `InvalidReference` error type
  - [ ] `UnkeyedReference` error type

### 5.2 Constrained Narrator
- [ ] Create `src/narrator/constrained_narrator.py`:
  - [ ] `ConstrainedNarrator` class
  - [ ] `narrate()` - Main entry with retry loop
  - [ ] `_generate()` - Call LLM with manifest
  - [ ] `_strip_keys()` - Remove [key] markers for display
  - [ ] `_generate_safe_fallback()` - Fallback if validation keeps failing
  - [ ] `NarrationType` enum (SCENE_ENTRY, ACTION_RESULT, DIALOGUE, CLARIFICATION)
  - [ ] `NarrationContext` dataclass
  - [ ] `NarrationResult` dataclass

### 5.3 Narrator Prompts
- [ ] Create `data/templates/constrained_narrator.jinja2`
- [ ] Include manifest reference guide in prompt
- [ ] Include [key] format rules
- [ ] Include retry feedback mechanism

### 5.4 Tests for Phase 5
- [ ] Create `tests/test_narrator/test_validator.py`:
  - [ ] Test valid output passes
  - [ ] Test invalid key detected
  - [ ] Test unkeyed reference detected
- [ ] Create `tests/test_narrator/test_constrained_narrator.py`:
  - [ ] Test successful narration
  - [ ] Test retry on validation failure
  - [ ] Test key stripping for display

**Phase 5 Complete When**: Narrator generates valid, constrained output

---

## Phase 6: Reference Resolution

### 6.1 Simple Reference Resolver
- [ ] Create `src/resolver/__init__.py`
- [ ] Create `src/resolver/reference_resolver.py`:
  - [ ] `ReferenceResolver` class
  - [ ] `resolve()` - Main resolution method
  - [ ] `_try_exact_key()` - Direct key match
  - [ ] `_try_display_name()` - Display name match
  - [ ] `_try_pronoun()` - Pronoun resolution
  - [ ] `_try_descriptor()` - Descriptor matching
  - [ ] `ResolutionResult` schema

### 6.2 Tests for Phase 6
- [ ] Create `tests/test_resolver/test_reference_resolver.py`:
  - [ ] Test exact key resolution
  - [ ] Test display name resolution
  - [ ] Test pronoun resolution (single candidate)
  - [ ] Test pronoun ambiguity (multiple candidates)
  - [ ] Test descriptor resolution
  - [ ] Test unknown reference

**Phase 6 Complete When**: References resolve correctly from manifest

---

## Phase 7: Graph Integration

### 7.1 New Graph Nodes
- [ ] Create `src/agents/nodes/world_mechanics_node.py`
- [ ] Create `src/agents/nodes/scene_builder_node.py`
- [ ] Create `src/agents/nodes/persist_scene_node.py`
- [ ] Create `src/agents/nodes/resolve_references_node.py`
- [ ] Create `src/agents/nodes/constrained_narrator_node.py`
- [ ] Create `src/agents/nodes/validate_narrator_node.py`

### 7.2 State Updates
- [ ] Update `src/agents/state.py`:
  - [ ] Add `world_update: dict | None`
  - [ ] Add `scene_manifest: dict | None`
  - [ ] Add `narrator_manifest: dict | None`
  - [ ] Add `resolved_actions: list[dict]`
  - [ ] Add `needs_clarification: bool`
  - [ ] Add `clarification_prompt: str | None`
  - [ ] Add `clarification_candidates: list[dict]`
  - [ ] Add `just_entered_location: bool`

### 7.3 New Graph Builder
- [ ] Create `build_scene_first_graph()` in `src/agents/graph.py`
- [ ] Add routing functions:
  - [ ] `route_after_parse()` - has_actions vs scene_only
  - [ ] `route_after_resolve()` - resolved vs needs_clarification
  - [ ] `route_after_validation()` - valid vs retry
- [ ] Wire all nodes together

### 7.4 Integration Tests
- [ ] Create `tests/test_integration/test_scene_first_flow.py`:
  - [ ] Test complete flow: enter location → see scene
  - [ ] Test complete flow: enter → action → narrate
  - [ ] Test clarification flow: ambiguous reference → ask → resolve
  - [ ] Test constraint enforcement end-to-end

**Phase 7 Complete When**: New graph processes turns correctly

---

## Phase 8: Migration and Cleanup

### 8.1 Parallel Running
- [ ] Add feature flag to switch between old and new graph
- [ ] Test both graphs in parallel
- [ ] Monitor for issues

### 8.2 Remove Legacy Code
- [ ] Remove `_resolve_and_spawn_target()` from `subturn_processor_node.py`
- [ ] Remove `_resolve_targets()` from `intent_parser.py`
- [ ] Deprecate or simplify `DiscourseManager`
- [ ] Remove `Turn.mentioned_items` usage (keep column for now)
- [ ] Remove `Turn.mentioned_npcs` usage (keep column for now)

### 8.3 Documentation
- [ ] Update `docs/architecture.md` with new flow
- [ ] Update `CLAUDE.md` with new patterns
- [ ] Add troubleshooting guide

**Phase 8 Complete When**: Old code removed, new system is default

---

## Nice-to-Have Enhancements (Post-MVP)

### Location Templates
- [ ] Create template system for common location types
- [ ] Define templates for: bedroom, tavern, shop, smithy, forest, road
- [ ] Allow setting-specific template overrides

### Container Content Generation
- [ ] Implement lazy generation when containers opened
- [ ] Track `contents_generated` flag on containers
- [ ] Generate contextually appropriate contents

### Event System Integration
- [ ] Connect World Mechanics to event system
- [ ] Allow events to trigger NPC placement
- [ ] Allow events to modify scene contents

### Performance Optimization
- [ ] Cache scene manifests between turns at same location
- [ ] Use Haiku for Scene Builder (structured output is simpler)
- [ ] Batch NPC schedule queries

---

## Testing Checklist

### Unit Tests (per phase above)
- [ ] All Phase 1-6 tests pass

### Integration Tests
- [ ] Full turn flow works
- [ ] Reference resolution works
- [ ] Clarification flow works
- [ ] Constraints are enforced

### Manual Testing
- [ ] Play through game entering various locations
- [ ] Test all action types work with new resolution
- [ ] Test edge cases:
  - [ ] Multiple same-gender NPCs (pronouns)
  - [ ] "The other one" references
  - [ ] Looking in containers
  - [ ] Searching for hidden items

---

## Progress Tracking

| Phase | Status | Started | Completed |
|-------|--------|---------|-----------|
| 1. Schemas & Constraints | Complete | 2025-12-21 | 2025-12-21 |
| 2. World Mechanics | Complete | 2025-12-21 | 2025-12-21 |
| 3. Scene Builder | Complete | 2025-12-21 | 2025-12-21 |
| 4. Persistence | Not Started | | |
| 5. Constrained Narrator | Not Started | | |
| 6. Reference Resolution | Not Started | | |
| 7. Graph Integration | Not Started | | |
| 8. Migration & Cleanup | Not Started | | |

---

## Notes for Implementation

1. **TDD Required**: Write tests first for each component
2. **Use Existing Patterns**: Follow manager pattern from existing codebase
3. **Structured Output**: Use Pydantic models with `complete_structured()`
4. **Error Handling**: Always handle LLM failures gracefully
5. **Logging**: Add debug logging for troubleshooting
