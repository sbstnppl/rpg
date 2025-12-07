# Implementation Plan

## Phase 1: Foundation

### 1.1 Project Setup
- [x] Create directory structure
- [x] Create `pyproject.toml` with dependencies
- [x] Set up `src/__init__.py` files
- [x] Create `config.py` with pydantic-settings
- [x] Set up `.env.example`

### 1.2 Database Models
- [x] Create `src/database/models/enums.py` - All enumerations
- [x] Create `src/database/models/base.py` - Base class, mixins
- [x] Create `src/database/models/session.py` - GameSession, Turn
- [x] Create `src/database/models/entities.py` - Entity, Attribute, Skill, NPCExtension, MonsterExtension
- [x] Create `src/database/models/items.py` - Item, StorageLocation, EquipmentSlot
- [x] Create `src/database/models/relationships.py` - Relationship, RelationshipChange
- [x] Create `src/database/models/world.py` - Location, Schedule, TimeState, Fact, WorldEvent
- [x] Create `src/database/models/tasks.py` - Task, Appointment, Quest
- [x] Create `src/database/connection.py` - Session management

### 1.2.1 Realism System Models (NEW)
- [x] Create `src/database/models/character_state.py` - CharacterNeeds, IntimacyProfile
- [x] Create `src/database/models/injuries.py` - BodyInjury, ActivityRestriction
- [x] Create `src/database/models/vital_state.py` - EntityVitalState
- [x] Create `src/database/models/mental_state.py` - MentalCondition, GriefCondition

### 1.3 Alembic Setup
- [x] Initialize Alembic
- [x] Create initial migration with all tables
- [x] Test migration up/down

## Phase 2: Core Managers

### 2.1 Base Manager
- [x] Create `src/managers/base.py` - BaseManager class

### 2.2 Entity Management
- [x] Create `src/managers/entity_manager.py`
  - `get_entity(key)`, `create_entity(**data)`
  - `update_attribute(key, attr, value)`
  - `get_entities_at_location(location)`
  - `get_player()`, `get_npcs_in_scene(location)`
  - `get_active_entities()` - alive + active entities

### 2.3 Item Management
- [x] Create `src/managers/item_manager.py`
  - `get_item(key)`, `create_item(**data)`
  - `transfer_item(item, from, to)`
  - `equip_item(entity, item, slot, layer)`
  - `get_inventory(entity)`, `get_visible_equipment(entity)`
  - `update_visibility()` - recalculate layer visibility
  - `get_items_at_location(location)` - items at world location

### 2.4 Relationship Management
- [x] Create `src/managers/relationship_manager.py`
  - `get_attitude(from, to)`
  - `update_attitude(from, to, dimension, delta, reason)`
  - `record_meeting(entity1, entity2)`
  - `get_relationship_history(from, to)`
  - `apply_personality_modifiers()` - trait-based multipliers
  - `check_familiarity_cap()` - strangers can't reach max trust
  - `expire_mood_modifiers()` - turn-based expiration

### 2.5 Location Management
- [x] Create `src/managers/location_manager.py`
  - `get_location(key)`, `create_location(**data)`
  - `get_sublocation(parent, child)`, `get_sublocations(parent)`
  - `get_items_at_location(location)`, `get_entities_at_location(location)`
  - `set_player_location(location)` - update player position

### 2.6 Schedule Management
- [x] Create `src/managers/schedule_manager.py`
  - `get_schedule(entity)`
  - `set_schedule_entry(entity, day, time, location, activity)`
  - `get_activity_at_time(entity, day, time)`
  - `get_npcs_at_location_time(location, day, time)`
  - `clear_schedule(entity)`, `copy_schedule(from, to)`

### 2.7 Fact Management
- [x] Create `src/managers/fact_manager.py`
  - `record_fact(subject_type, subject_key, predicate, value)`
  - `get_facts_about(subject_key)`
  - `get_facts_by_predicate(predicate)`, `get_facts_by_category(category)`
  - `get_secrets()` - GM-only facts
  - `get_player_known_facts()` - non-secret facts
  - `update_certainty(fact_id, certainty)`, `contradict_fact(fact_id, new_value, reason)`

### 2.8 Time Management
- [x] Create `src/managers/time_manager.py`
  - `get_current_time()`, `advance_time(minutes)`
  - `set_weather(weather)`
  - `get_day_of_week()`

### 2.9 Event Management
- [x] Create `src/managers/event_manager.py`
  - `create_event(type, summary, details)`
  - `get_unprocessed_events()`
  - `mark_processed(event_id)`
  - `get_events_at_location(location)`
  - `get_events_involving(entity_id)`, `get_recent_events(limit)`

### 2.10 Task Management
- [x] Create `src/managers/task_manager.py`
  - `create_task(description, category, **kwargs)`
  - `complete_task(task_id)`, `fail_task(task_id, reason)`
  - `get_active_tasks()`
  - `get_appointments_for_day(day)`
  - `check_missed_appointments()`
  - `mark_appointment_kept(id)`, `mark_appointment_missed(id)`

### 2.11 Context Compiler
- [x] Create `src/managers/context_compiler.py`
  - `compile_scene(npcs_present, location)`
  - Aggregates data from all managers
  - Returns formatted context for GM
  - Includes needs/injury summaries for NPCs
  - `_get_equipment_description()` - visible equipment context
  - `_format_appearance()` - includes age support

### 2.12 Realism Managers (NEW)
- [x] Create `src/managers/needs.py` - NeedsManager
  - `apply_time_decay()` - activity-based need changes with modifier support
  - `get_active_effects()` - stat penalties from unmet needs
  - `get_npc_urgency()` - for schedule overrides
  - `get_decay_multiplier()` - combined decay rate from modifiers
  - `get_satisfaction_multiplier()` - combined satisfaction rate from modifiers
  - `get_max_intensity()` - lowest intensity cap from age/trait modifiers
  - `get_total_adaptation()` - sum of adaptation deltas for a need
  - `create_adaptation()` - create adaptation record for need changes
- [x] Create `src/managers/preferences_manager.py` - PreferencesManager
  - `get_preferences()`, `get_or_create_preferences()`, `create_preferences()`
  - `get_trait_flags()`, `set_trait()` - trait flag management
  - `sync_trait_modifiers()` - sync traits to NeedModifier records
  - `calculate_age_modifier()` - asymmetric normal distribution
  - `generate_individual_variance()` - stage 2 per-character variance
  - `generate_age_modifiers()` - two-stage age-based modifier generation
- [x] Create `src/managers/injuries.py` - InjuryManager
  - `add_injury()`, `get_injuries()`
  - `get_activity_impact()` - penalties for walking/running/etc
  - `apply_healing()` - recovery progression
  - `sync_pain_to_needs()` - pain↔needs integration
- [x] Create `src/managers/death.py` - DeathManager
  - `take_damage()` - vital status + injury creation
  - `make_death_save()` - d20 mechanics
  - `attempt_revival()` - setting-specific revival
- [x] Create `src/managers/grief.py` - GriefManager
  - Kübler-Ross stages based on relationship strength
- [x] Create `src/managers/consistency.py` - ConsistencyValidator
  - Possession/spatial/temporal/behavioral checks

## Phase 3: LLM Integration

### 3.1 Provider Abstraction
- [x] Create `src/llm/base.py` - LLMProvider protocol
- [x] Create `src/llm/message_types.py` - Message, MessageContent, MessageRole
- [x] Create `src/llm/tool_types.py` - ToolDefinition, ToolParameter
- [x] Create `src/llm/response_types.py` - LLMResponse, ToolCall, UsageStats
- [x] Create `src/llm/exceptions.py` - LLMError hierarchy
- [x] Create `src/llm/factory.py` - get_provider() factory
- [x] Create `src/llm/retry.py` - Exponential backoff with jitter

### 3.2 Anthropic Provider
- [x] Create `src/llm/anthropic_provider.py`
  - `complete()`, `complete_with_tools()`, `complete_structured()`
  - Tool use / function calling support
  - Token counting (heuristic)

### 3.3 OpenAI Provider
- [x] Create `src/llm/openai_provider.py`
  - `complete()`, `complete_with_tools()`, `complete_structured()`
  - Configurable `base_url` for OpenAI-compatible APIs (DeepSeek, Ollama, vLLM)
  - Token counting via tiktoken

### 3.4 Dice System
- [x] Create `src/dice/types.py` - Dataclasses for expressions and results
- [x] Create `src/dice/parser.py` - Parse dice notation (1d20, 2d6+3)
- [x] Create `src/dice/roller.py` - Roll with modifiers, advantage/disadvantage
- [x] Create `src/dice/checks.py` - Skill checks, saving throws, DC constants
- [x] Create `src/dice/combat.py` - Attack rolls, damage, initiative
- [x] Critical success/failure detection (natural 20/1)

## Phase 4: LangGraph Agents

### 4.1 State Schema
- [x] Create `src/agents/state.py` - GameState TypedDict

### 4.2 Graph Builder
- [x] Create `src/agents/graph.py` - Build LangGraph graph

### 4.3 Context Compiler Agent
- [x] Create `src/agents/nodes/context_compiler_node.py`
  - Node that calls ContextCompiler manager

### 4.4 Game Master Agent
- [x] Create `src/agents/nodes/game_master_node.py`
  - System prompt template
  - Narrative generation
  - Routing logic

### 4.5 Entity Extractor Agent
- [x] Create `src/agents/nodes/entity_extractor_node.py`
  - Parse GM responses
  - Extract entities, facts, changes
  - Call managers to persist

### 4.6 Agent Tools
- [x] Create `src/agents/tools/gm_tools.py`
- [x] Create `src/agents/tools/extraction_tools.py`

## Phase 5: Advanced Features

### 5.1 Combat Resolver
- [x] Create `src/agents/nodes/combat_resolver_node.py`
  - Initiative system
  - Attack resolution
  - Damage calculation
  - Loot generation
- [x] Create `src/managers/combat_manager.py` - Combat state management

### 5.2 World Simulator
- [x] Create `src/agents/world_simulator.py`
  - NPC schedule execution
  - Need decay integration (calls NeedsManager)
  - Mood modifier expiration
  - Time advancement
  - LangGraph node wrapper

### 5.3 Combat Tools
- [x] Create `src/agents/tools/combat_tools.py`

### 5.4 World Tools
- [x] Create `src/agents/tools/world_tools.py`

## Phase 6: CLI & UX

### 6.1 CLI Setup
- [x] Create `src/main.py` - Entry point
- [x] Create `src/cli/main.py` - Typer app
- [x] Create `src/cli/display.py` - Display utilities

### 6.2 Session Commands
- [x] Create `src/cli/commands/session.py`
  - `start`, `continue`, `list`, `load`, `save`

### 6.3 Character Commands
- [x] Create `src/cli/commands/character.py`
  - `status`, `inventory`, `equipment`

### 6.4 World Commands
- [x] Create `src/cli/commands/world.py`
  - `locations`, `npcs`, `time`

### 6.5 Game Command
- [x] Create `src/cli/commands/game.py` - Main game loop

### 6.6 Character Creation Flow
- [x] Implement conversational character creation
- [x] AI-assisted attribute assignment
- [x] Starting equipment selection

### 6.7 Rich Formatting
- [x] Styled output for narrative (basic)
- [x] Tables for stats/inventory
- [x] Progress bars for loading

## Phase 7: Polish & Testing

### 7.1 Tests
- [x] Test database models (1226 tests total)
- [x] Test managers
- [x] Test agent tools
- [x] Integration tests

### 7.2 Documentation
- [x] Project outline
- [x] Architecture doc
- [x] User guide
- [x] Implementation plan
- [x] API documentation

### 7.3 Setting Templates
- [x] Create `data/settings/fantasy.json`
- [x] Create `data/settings/contemporary.json`
- [x] Create `data/settings/scifi.json`

### 7.4 Prompt Templates
- [x] Create `data/templates/game_master.md`
- [x] Create `data/templates/entity_extractor.md`
- [x] Create `data/templates/world_simulator.md`
- [x] Create `data/templates/combat_resolver.md`
- [x] Create `data/templates/character_creator.md`
