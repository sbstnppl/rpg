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
  - `compile_scene(player_id, location_key, turn_number)`
  - Aggregates data from all managers
  - Returns formatted context for GM
  - Includes needs/injury summaries for NPCs
  - `_get_turn_context()` - turn number and recent history for narrative continuity
  - `_get_equipment_description()` - visible equipment context
  - `_format_appearance()` - includes age support

### 2.12 Realism Managers (NEW)
- [x] Create `src/managers/needs.py` - NeedsManager
  - All needs use unified semantics: 0=bad (red), 100=good (green)
  - 9 needs: hunger, energy, hygiene, comfort, wellness, social_connection, morale, sense_of_purpose, intimacy
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
  - `sync_pain_to_needs()` - pain→wellness integration (wellness = 100 - total_pain)
- [x] Create `src/managers/death.py` - DeathManager
  - `take_damage()` - vital status + injury creation
  - `make_death_save()` - d20 mechanics
  - `attempt_revival()` - setting-specific revival
- [x] Create `src/managers/grief.py` - GriefManager
  - Kübler-Ross stages based on relationship strength
- [x] Create `src/managers/consistency.py` - ConsistencyValidator
  - Possession/spatial/temporal/behavioral checks
- [x] Create `src/managers/context_validator.py` - ContextValidator (Pre-Generation)
  - `validate_entity_reference()` - check entity exists before generation
  - `validate_location_reference()` - check location is known
  - `validate_fact_consistency()` - detect contradictions
  - `validate_time_consistency()` - catch time/weather mismatches
  - `validate_unique_role()` - prevent duplicate unique roles
  - `validate_extraction()` - batch validation for extractions
  - `get_constraint_context()` - generate GM constraint instructions
- [x] Create `src/managers/context_budget.py` - ContextBudget
  - `add_section()` - add context section with priority
  - `compile()` - compile sections within token budget
  - Priority-based inclusion (CRITICAL > HIGH > MEDIUM > LOW > OPTIONAL)
  - Automatic truncation for large sections
  - `for_model()` - model-specific budget configuration

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

### 3.4 Audit Logging
- [x] Create `src/llm/audit_logger.py`
  - `LLMAuditContext` - session/turn/call_type tracking
  - `LLMAuditEntry` - full request/response data
  - `LLMAuditLogger` - async file writing with markdown formatting
  - `set_audit_context()`, `get_audit_context()` - context variable management
  - `get_audit_logger()` - factory with configurable directory
- [x] Create `src/llm/logging_provider.py`
  - `LoggingProvider` - wrapper that delegates + logs all LLM calls
  - Captures timing, messages, tool calls, responses
- [x] Modify `src/llm/factory.py` - wrap providers when `log_llm_calls=True`
- [x] Add `llm_log_dir` setting to `src/config.py`
- [x] Set audit context in agent nodes (game_master, entity_extractor)
- [x] Set audit context in character.py CLI
- [x] Create tests for audit logging (35 tests)

### 3.5 Dice System
- [x] Create `src/dice/types.py` - Dataclasses for expressions and results
- [x] Create `src/dice/parser.py` - Parse dice notation (1d20, 2d6+3)
- [x] Create `src/dice/roller.py` - Roll with modifiers, advantage/disadvantage
- [x] Create `src/dice/checks.py` - Skill checks, saving throws, DC constants
- [x] Create `src/dice/combat.py` - Attack rolls, damage, initiative
- [x] Critical success/failure detection (natural 20/1)
- [x] Create `src/dice/skills.py` - Skill-to-attribute mappings
- [x] Add `proficiency_to_modifier()` - Convert proficiency (1-100) to modifier (+0 to +5)
- [x] Add `get_proficiency_tier_name()` - Novice/Apprentice/Competent/Expert/Master/Legendary
- [x] Add `assess_difficulty()` - Character-based difficulty perception
- [x] Add `get_difficulty_description()` - Narrative difficulty text

### 3.5.1 Realistic Skill Checks (2d10 System)
- [x] Create `docs/game-mechanics.md` - Document D&D deviations
- [x] Add `RollType` enum - Distinguish skill checks, attacks, saves
- [x] Add `OutcomeTier` enum - Degree of success/failure tiers
- [x] Add `roll_2d10()` - Bell curve roller with 3d10 advantage/disadvantage
- [x] Add `can_auto_succeed()` - Take 10 rule (DC ≤ 10 + modifier)
- [x] Add `get_outcome_tier()` - Margin to tier conversion
- [x] Update `make_skill_check()` - Use 2d10, auto-success, outcome tiers
- [x] Update `make_saving_throw()` - Use 2d10 (same as skill checks)
- [x] Add `is_double_ten` / `is_double_one` - 2d10 critical detection
- [x] Update `_execute_skill_check()` - Handle auto-success, new fields
- [x] Update `display_skill_check_result()` - Auto-success and tier display
- [x] Update GM prompt template - Skill check guidance for 2d10
- [x] Update tests for 2d10 system (183 dice tests, 1995 total)

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
  - [x] `skill_check` tool with `entity_key` for proficiency lookup
  - [x] `attribute_key` optional override for governing attribute
- [x] Create `src/agents/tools/executor.py`
  - [x] `_execute_skill_check()` queries EntitySkill and EntityAttribute
  - [x] Returns full modifier breakdown for interactive display
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
  - [x] `display_skill_check_prompt()` - Pre-roll display with modifiers
  - [x] `display_skill_check_result()` - Post-roll with DC, margin, outcome
  - [x] `wait_for_roll()` - Interactive ENTER prompt
  - [x] `display_rolling_animation()` - Dice tumbling animation

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
  - [x] `_display_skill_checks_interactive()` - Interactive dice rolling for skill checks
  - [x] Skill checks displayed before narrative with ENTER to roll

### 6.6 Character Creation Flow
- [x] Implement conversational character creation
- [x] AI-assisted attribute assignment
- [x] Starting equipment selection
- [x] **Height & Voice Support**
  - Add `height` and `voice_description` fields to `CharacterCreationState`
  - Update `get_current_state_summary()` to display height and voice
  - Update `_create_character_records()` to persist height and voice
  - Update `wizard_appearance.md` template with height and voice prompts

### 6.7 Unified Game Start Wizard
- [x] Create `rpg game start` command combining session + character + play
- [x] Interactive setting selection menu
- [x] Session name prompt with defaults
- [x] Hybrid attribute handling (AI-suggest or point-buy)
  - [x] `_parse_point_buy_switch()` function
  - [x] Mid-conversation switch to point-buy
  - [x] Updated `character_creator.md` template
- [x] Deferred DB commits (only after character confirmed)
- [x] Automatic transition to game loop
- [x] `rpg game list` - List games with player names
- [x] `rpg game delete` - Delete game with confirmation
- [x] Deprecation warnings on session commands and character create

### 6.8 Rich Formatting
- [x] Styled output for narrative (basic)
- [x] Tables for stats/inventory
- [x] Progress bars for loading

## Phase 7: Polish & Testing

### 7.1 Tests
- [x] Test database models (2306 tests total)
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

## Phase 8: World Map & Navigation System

### 8.1 Database Schema
- [x] Add navigation enums to `src/database/models/enums.py`
  - TerrainType, ConnectionType, TransportType, MapType
  - VisibilityRange, EncounterFrequency, DiscoveryMethod, PlacementType
- [x] Create `src/database/models/navigation.py`
  - TerrainZone - explorable terrain segments
  - ZoneConnection - adjacencies between zones
  - LocationZonePlacement - links locations to zones
  - TransportMode - travel methods with terrain costs
  - ZoneDiscovery - fog of war for zones (session-scoped)
  - LocationDiscovery - fog of war for locations (session-scoped)
  - MapItem - physical maps that reveal locations
  - DigitalMapAccess - digital map services (modern/sci-fi)
- [x] Create Alembic migration `005_add_navigation_system.py`

### 8.2 Zone Manager
- [x] Create `src/managers/zone_manager.py`
  - `get_zone(key)`, `create_zone(**data)`
  - `connect_zones(from_key, to_key, direction)`
  - `get_adjacent_zones(zone_key)` - zones connected to this one
  - `get_adjacent_zones_with_directions(zone_key)` - with direction info
  - `place_location_in_zone(location_key, zone_key)`
  - `get_zone_locations(zone_key)` - locations within a zone
  - `get_location_zone(location_key)` - zone containing a location
  - `get_terrain_cost(zone_key, transport_mode)` - movement cost
  - `check_accessibility(zone_key, character_skills)` - skill checks
  - `get_visible_from_zone(zone_key)` - visible zones
  - `get_visible_locations_from_zone(zone_key)` - visible locations
  - `get_transport_mode(mode_key)`
  - `get_available_transport_modes(zone_key)` - usable transport in zone

### 8.3 Pathfinding System
- [x] Create `src/managers/pathfinding_manager.py`
  - `find_optimal_path(from_zone, to_zone, transport_mode)` - A* algorithm
  - `find_path_via(from_zone, to_zone, waypoints, transport_mode)`
  - `calculate_travel_time(path, transport_mode, character)` - with fatigue
  - `get_route_summary(path)` - terrain types, distances, hazards
  - Support terrain costs, transport mode limitations
  - Support route preferences (avoid forests, take roads only)

### 8.4 Travel Simulation System
- [x] Create `src/managers/travel_manager.py`
  - `start_journey(from_zone, to_zone, transport_mode, route_preference)`
  - `advance_travel()` - move to next zone, roll encounters
  - `interrupt_travel(action)` - leave road, explore side area
  - `get_journey_state()` - current position, progress, fatigue
  - `resume_journey()` - continue interrupted journey
  - `detour_to_zone()` - explore adjacent zones off the path
  - Skill checks for hazardous terrain (swimming, climbing)
  - Random encounter rolls per terrain type

### 8.5 Discovery System
- [x] Create `src/managers/discovery_manager.py`
  - `discover_zone(zone_key, method, source)` - reveal terrain zone
  - `discover_location(location_key, method, source)` - reveal location
  - `view_map(map_item)` - reveal all zones/locations on a map
  - `check_digital_access()` - available digital map services
  - `get_known_zones()`, `get_known_locations()` - discovered items
  - `auto_discover_surroundings(zone_key)` - on zone entry
  - `is_zone_discovered()`, `is_location_discovered()` - check discovery status

### 8.6 Map Item Integration
- [x] MapItem integration with Item system
- [x] "View map" action reveals zones and locations
  - `VIEW_MAP_TOOL` in `src/agents/tools/gm_tools.py`
  - `_execute_view_map()` in `src/agents/tools/executor.py`
  - Enhanced `view_map()` in DiscoveryManager with coverage zone support
  - `_get_descendant_zones()` for hierarchical zone discovery
- [ ] Setting-based digital map availability
- [ ] Device/connection requirements for digital maps

### 8.7 GM Integration
- [ ] Update GM prompt with zone navigation context
- [ ] Only reference known zones/locations in responses
- [ ] Include current zone, adjacent zones, known locations in context
- [ ] Travel time estimates based on terrain + transport
- [ ] Block impossible movements (no swimming without skill)
- [ ] Trigger travel simulation for distant destinations

### 8.8 World Building CLI Tools
- [x] CLI commands: `world zones`, `world create-zone`, `world connect-zones`, `world place-location`, `world zone-info`, `world discovered`
- [x] Import from YAML/JSON templates
  - `src/schemas/world_template.py` - Pydantic schemas for world import
  - `src/services/world_loader.py` - `load_world_from_file()` function
  - CLI command: `world import <file.yaml|json>`
- [ ] Bulk zone creation for regions

## Phase 9: NPC Full Character Generation

### 9.1 NPC Generation Schema
- [x] Create `src/agents/schemas/npc_generation.py`
  - `NPCAppearance` - 12 appearance fields
  - `NPCBackground` - backstory, occupation, personality_notes
  - `NPCSkill` - skill_key, proficiency_level
  - `NPCInventoryItem` - item details
  - `NPCPreferences` - social_tendency, drive_level, food prefs
  - `NPCInitialNeeds` - need values dict
  - `NPCGenerationResult` - combines all above

### 9.2 NPC Generator Service
- [x] Create `src/services/npc_generator.py`
  - `NPCGeneratorService.generate_npc()` - Main generation method
  - `_create_entity_with_appearance()` - Entity + appearance columns
  - `_create_npc_extension()` - NPC-specific data
  - `_create_npc_skills()` - EntitySkill records
  - `_create_npc_inventory()` - Item records
  - `_create_npc_preferences()` - CharacterPreferences record
  - `_create_npc_needs()` - CharacterNeeds record
  - `infer_npc_initial_needs()` - Time/occupation-based inference
  - `OCCUPATION_SKILLS` - Skill templates for 15+ occupations
  - `OCCUPATION_INVENTORY` - Inventory templates for 15+ occupations

### 9.3 NPC Generator LangGraph Node
- [x] Create `src/agents/nodes/npc_generator_node.py`
  - `npc_generator_node()` - Process extracted entities
  - Filter for new NPCs only
  - Call LLM for each NPC
  - Graceful fallback on errors

### 9.4 Prompt Template
- [x] Create `data/templates/npc_generator.md`
  - NPC context (name, description, traits)
  - Game context (setting, time, scene)
  - Occupation templates as guidance
  - Output JSON matching schema

### 9.5 Agent Integration
- [x] Update `src/agents/state.py`
  - Add `generated_npcs` field
  - Add `npc_generator` to `AgentName`
- [x] Update `src/agents/graph.py`
  - Add npc_generator node
  - Change edge: entity_extractor → npc_generator → persistence
- [x] Update `src/agents/nodes/persistence_node.py`
  - Skip pre-generated NPCs (avoid duplicates)

### 9.6 Companion Tracking
- [x] Add to `NPCExtension` model:
  - `is_companion: bool`
  - `companion_since_turn: int`
- [x] Create migration `010_add_companion_tracking.py`
- [x] Add `EntityManager.set_companion_status()` method
- [x] Add `EntityManager.get_companions()` method
- [x] Add `NeedsManager.apply_companion_time_decay()` method

### 9.7 Tests
- [x] Create `tests/test_services/test_npc_generator.py` (18 tests)
  - Service method tests
  - Needs inference tests
  - Occupation template tests
  - Integration tests with mocked LLM

## Phase 10: Structured GM Output with Autonomous NPCs

### 10.1 Core Infrastructure (Phase 1) ✓
- [x] Create `src/agents/schemas/goals.py`
  - `NPCGoal` schema with 12 goal types
  - `GoalUpdate` schema for progress tracking
  - Priority levels and completion conditions
- [x] Create `src/agents/schemas/npc_state.py`
  - `NPCFullState` - Complete NPC data
  - `NPCAppearance` - Physical description with precise + narrative values
  - `NPCPersonality` - Traits, values, flaws, quirks
  - `NPCPreferencesData` - Attraction preferences
  - `EnvironmentalReaction` - Scene reactions
  - `AttractionScore` - Attraction calculation
  - `SceneContext`, `VisibleItem`, `PlayerSummary`
- [x] Create `src/agents/schemas/gm_response.py`
  - `GMResponse` - Narrative + manifest structure
  - `GMManifest` - NPCs, items, actions, changes
  - `NPCAction` - Actions with motivations
- [x] Create `src/managers/goal_manager.py`
  - `create_goal()`, `get_goals_for_entity()`
  - `update_goal_progress()`, `complete_goal()`
  - `fail_goal()`, `abandon_goal()`
  - `get_urgent_goals()`, `get_goals_by_type()`
- [x] Create `tests/test_managers/test_goal_manager.py` (35 tests)

### 10.2 NPC Creation Tools (Phase 2) ✓
- [x] Create `src/services/emergent_npc_generator.py`
  - `EmergentNPCGenerator.create_npc()` - Full NPC with emergent traits
  - `query_npc_reactions()` - Update reactions to scene
  - Attraction calculation (physical + personality)
  - Environmental reaction generation
  - Immediate goal generation
  - Behavioral prediction
  - Database persistence (Entity, NPCExtension, Skills, Preferences, Needs)
- [x] Create `src/services/emergent_item_generator.py`
  - `EmergentItemGenerator.create_item()` - Items with emergent properties
  - `get_item_state()` - Retrieve existing item state
  - Context-based subtype inference
  - Quality/condition value calculation
  - Provenance and narrative hooks
- [x] Create `src/agents/tools/npc_tools.py`
  - `CREATE_NPC_TOOL` - GM tool for NPC creation
  - `QUERY_NPC_TOOL` - GM tool for NPC queries
  - `CREATE_ITEM_TOOL` - GM tool for item creation
- [x] Update `src/agents/tools/executor.py`
  - `_execute_create_npc()` handler
  - `_execute_query_npc()` handler
  - `_execute_create_item()` handler
  - Lazy-loaded generator properties
- [x] Update `src/agents/tools/__init__.py`
  - Export new tools and lists
- [x] Create `tests/test_services/test_emergent_npc_generator.py` (74 tests)
- [x] Create `tests/test_services/test_emergent_item_generator.py` (43 tests)

### 10.2.1 NPC Generation Enhancements ✓
- [x] **Birthplace System**
  - Add `birthplace` field to Entity model
  - Create migration `369661c753f3_add_birthplace_to_entities.py`
  - Create `src/schemas/regions.py` with RegionCulture dataclass
  - Define regions for Contemporary, Fantasy, and Sci-Fi settings
  - `_generate_birthplace()` - 87% local, 13% migrant
  - `_generate_skin_color_from_birthplace()` - weighted random from region demographics
- [x] **Age-Aware Height Generation**
  - `GROWTH_PERCENTAGES` constant for pediatric growth curves
  - `_calculate_height()` - age and gender-appropriate heights
- [x] **Age-Aware Voice Generation**
  - `VOICES_CHILD` and `VOICES_TEEN` constants
  - `_generate_voice()` - pre-voice-break for children/teens
- [x] **Setting-Specific Name Pools**
  - `NAMES_BY_SETTING` dictionary (fantasy, contemporary, scifi)
  - `_SETTING_NAME_ALIASES` for setting lookup
  - Updated `_generate_name()` to use setting-specific pools
- [x] **Context-Aware Apprentice Generation**
  - `LOCATION_APPRENTICE_ROLES` mapping 50+ locations to trade-specific roles
  - `_GENERIC_APPRENTICE_ROLES` and `_GENERIC_YOUNG_ROLES` fallbacks
  - `_generate_context_aware_apprentice()` method
  - Updated `_generate_occupation_fallback()` to use location context
- [x] Create `src/schemas/regions.py` (new file)
- [x] Create `tests/test_schemas/test_regions.py` (18 tests)

### 10.3 World Simulator (Phase 3) ✓
- [x] Update `src/agents/world_simulator.py`
  - `_check_need_driven_goals()` - Auto-create goals from urgent needs
  - `_process_npc_goals()` - Process active goals during simulation
  - `_execute_goal_step()` - Execute single goal step
  - `_evaluate_step_success()` - Probabilistic step success
  - `_check_step_for_movement()` - Detect location changes
- [x] Goal pursuit logic
  - NPC movement toward goals
  - Probabilistic step success based on type/priority
  - Goal completion and blocking detection
- [x] Integration with simulation loop
  - Goals processed during `simulate_time_passage()`
  - Results include goal tracking fields
- [x] Create `tests/test_agents/test_nodes/test_world_simulator_goals.py` (9 tests)

### 10.4 Context & Output (Phase 4) ✓
- [x] Update `src/managers/context_compiler.py`
  - `_get_npc_location_reason()` - Returns goal pursuit or scheduled reason
  - `_get_npc_active_goals()` - Formatted goal list with priority/motivation
  - `_get_urgent_needs()` - Needs with >60% urgency
  - `_get_entity_registry_context()` - Entity keys for manifest references
  - Updated `_format_npc_context()` with goals, location reason, urgent needs
  - Added `entity_registry_context` field to `SceneContext`
  - Updated `to_prompt()` to include entity registry section
- [x] Create `src/agents/schemas/gm_response.py`
  - `GMResponse` - Structured output (narrative + state + manifest)
  - `GMManifest` - NPCs, items, actions, relationships, facts, stimuli, goals
  - `GMState` - Time, location, combat state changes
  - `NPCAction`, `ItemChange`, `RelationshipChange`, `FactRevealed`, `Stimulus`
  - Re-uses `GoalCreation` and `GoalUpdate` from goals.py
- [x] Update `src/agents/schemas/__init__.py`
  - Export all GM response schemas
- [x] Create `tests/test_managers/test_context_compiler_goals.py` (14 tests)

### 10.5 Integration (Phase 5) ✓
- [x] Graph already includes world simulator node (`route_after_gm` supports world_simulator)
- [x] Update `src/agents/nodes/persistence_node.py`
  - `_persist_from_manifest()` - Handle manifest-based persistence
  - `_persist_manifest_fact()` - Persist FactRevealed entries
  - `_persist_manifest_relationship()` - Persist RelationshipChange entries
  - `_persist_manifest_goal_creation()` - Create goals from GoalCreation entries
  - `_persist_manifest_goal_update()` - Process goal updates (complete, fail, advance)
  - Dual-mode: uses manifest if `gm_manifest` in state, else legacy extraction
- [x] Update `src/agents/state.py`
  - Added `gm_manifest: dict[str, Any] | None` field for structured output
  - Added `skill_checks: list[dict[str, Any]] | None` for dice display
- [x] Create `tests/test_agents/test_nodes/test_persistence_manifest.py` (16 tests)
- [ ] Remove/deprecate entity extractor (deferred - keeping for backward compatibility)

### 10.6 Polish (Phase 6) ✓
- [x] Tune NPC generation prompts
  - EmergentNPCGenerator uses data pools, not LLM prompts (no tuning needed)
  - Fixed needs inversion bug in `query_npc_reactions()`
- [x] Test emergent scenarios
  - Create `tests/test_integration/test_emergent_scenarios.py` (9 tests)
  - `TestHungryNPCScenario` - Hungry NPCs react to food, satisfied NPCs don't
  - `TestGoalDrivenNPCScenario` - Goals persisted and updated via manifest
  - `TestAttractionScenario` - Attraction varies by player traits
  - `TestFullManifestWorkflow` - Complex manifests with multiple components
- [x] Performance optimization
  - Verified indexes on key columns (session_id, entity_key)
  - No N+1 query issues in ContextCompiler (15 efficient queries)
- [x] Documentation updates
  - Updated CHANGELOG.md with Phase 6 changes
  - Updated this implementation plan

## Phase 11: Narrative Systems

### 11.1 Story Arc System ✓
- [x] Create `src/database/models/narrative.py`
  - `StoryArc` model with arc_key, title, arc_type, current_phase, status
  - `ArcType` enum (main_quest, side_quest, character_arc, mystery, romance, faction, world_event)
  - `ArcPhase` enum (setup, rising_action, midpoint, escalation, climax, falling_action, resolution, aftermath)
  - `ArcStatus` enum (planned, active, paused, completed, abandoned)
  - `tension_level` (0-100), `planted_elements` (JSON), `foreshadowing` (text)
- [x] Create `src/managers/story_arc_manager.py`
  - `create_arc()`, `get_arc()`, `get_active_arcs()`, `get_arcs_by_type()`
  - `activate_arc()`, `pause_arc()`, `complete_arc()`, `abandon_arc()`
  - `set_phase()`, `set_tension()` - phase and tension management
  - `plant_element()`, `resolve_element()`, `get_unresolved_elements()` - Chekhov's gun pattern
  - `set_foreshadowing()`, `get_pacing_hint()` - narrative guidance
  - `get_arc_context()` - formatted context for GM
  - JSON mutation detection using `flag_modified`
- [x] Create Alembic migration `c570e2f1f0dd_add_narrative_models_story_arc_mystery_.py`
- [x] Add relationships to `GameSession` model
- [x] Export models in `src/database/models/__init__.py`
- [x] Create tests in `tests/test_database/test_models/test_narrative.py` (31 tests)
- [x] Create tests in `tests/test_managers/test_story_arc_manager.py` (47 tests)

### 11.2 Mystery/Revelation System ✓
- [x] Add to `src/database/models/narrative.py`
  - `Mystery` model with mystery_key, title, truth, clues (JSON), red_herrings (JSON)
  - `revelation_conditions`, `player_theories` (JSON)
  - `clues_discovered`, `total_clues` counters
  - `is_solved`, `solved_turn` tracking
- [x] Create `src/managers/mystery_manager.py`
  - `create_mystery()`, `get_mystery()`, `get_active_mysteries()`
  - `add_clue()`, `discover_clue()`, `get_discovered_clues()`, `get_undiscovered_clues()`
  - `add_red_herring()`, `mark_red_herring_discovered()`
  - `add_player_theory()`, `get_player_theories()`
  - `check_revelation_ready()` - keyword-based trigger detection
  - `solve_mystery()`, `get_solution()`
  - `get_mystery_status()` - complete status with discovery percentage
  - `get_mysteries_context()` - formatted context for GM
- [x] Create tests in `tests/test_managers/test_mystery_manager.py` (36 tests)

### 11.3 Conflict Escalation System ✓
- [x] Add to `src/database/models/narrative.py`
  - `Conflict` model with conflict_key, title, initial_level, current_level
  - `ConflictLevel` enum (tension, dispute, confrontation, hostility, crisis, war)
  - `escalation_triggers`, `de_escalation_triggers` (JSON lists)
  - `escalation_history` (JSON list with turn and reason)
  - `is_active`, `is_resolved` status flags
- [x] Create `src/managers/conflict_manager.py`
  - `create_conflict()`, `get_conflict()`, `get_active_conflicts()`
  - `escalate()`, `de_escalate()` with reason tracking
  - `resolve_conflict()`, `pause_conflict()`, `resume_conflict()`
  - `add_escalation_trigger()`, `add_de_escalation_trigger()`
  - `check_escalation_triggers()` - keyword-based detection
  - `get_conflict_status()` - complete status with history
  - `get_conflicts_context()` - formatted context for GM
- [x] Create tests in `tests/test_managers/test_conflict_manager.py` (33 tests)

### 11.4 NPC Secrets System ✓
- [x] Add secret fields to `NPCExtension` model
  - `dark_secret` - Something NPC is hiding
  - `hidden_goal` - True goal (may differ from stated)
  - `betrayal_conditions` - What would cause betrayal
  - `secret_revealed` - Whether secret has been revealed
  - `secret_revealed_turn` - When secret was revealed
- [x] Create Alembic migration `e28e2ef1e2bf_add_npc_secrets_system_fields.py`
- [x] Create `src/managers/secret_manager.py`
  - `NPCSecret`, `SecretRevealAlert`, `BetrayalRisk` dataclasses
  - `set_dark_secret()`, `set_hidden_goal()`, `set_betrayal_conditions()`
  - `reveal_secret()` with turn tracking
  - `get_npc_secret()`, `get_npcs_with_secrets()`, `get_unrevealed_secrets()`
  - `get_npcs_with_betrayal_conditions()`
  - `check_betrayal_triggers()` - keyword-based risk detection (low/medium/high/imminent)
  - `generate_secret_reveal_alerts()` - context-based alerts
  - `get_secrets_context()`, `get_betrayal_risks_context()` - formatted context for GM
  - Automatic `NPCExtension` creation when setting secrets
- [x] Export `SecretManager`, `NPCSecret`, `BetrayalRisk` in `src/managers/__init__.py`
- [x] Create tests in `tests/test_managers/test_secret_manager.py` (22 tests)

### 11.5 Cliffhanger Detection ✓
- [x] Create `src/managers/cliffhanger_manager.py`
  - `DramaticMoment` dataclass - source, tension_score, cliffhanger_potential
  - `CliffhangerSuggestion` dataclass - hook_type, description, why_effective, follow_up_hook
  - `SceneTensionAnalysis` dataclass - overall analysis with suggestions
  - Phase-based tension scores (setup: 20, climax: 95)
  - Conflict level tension scores (tension: 15, war: 100)
  - `CliffhangerManager` with:
    - `analyze_scene_tension()` - combines story arcs, conflicts, mysteries
    - `get_cliffhanger_hooks()` - sorted by effectiveness
    - `is_cliffhanger_ready()` - returns (ready, reason) tuple
    - `get_tension_context()` - formatted context for GM
  - Weighted tension calculation (top 3: 50%, 30%, 20%)
- [x] Export in `src/managers/__init__.py`
- [x] Create tests in `tests/test_managers/test_cliffhanger_manager.py` (20 tests)

### 11.6 Summary
- [x] 5 new database models (StoryArc, Mystery, Conflict + 3 enums)
- [x] 5 new fields on NPCExtension
- [x] 5 new managers (StoryArcManager, MysteryManager, ConflictManager, SecretManager, CliffhangerManager)
- [x] 2 Alembic migrations
- [x] 189 new tests total
- [x] All managers exported in `src/managers/__init__.py`

## Phase 12: Progression System

### 12.1 Skill Advancement System ✓
- [x] Add skill tracking fields to `EntitySkill` model
  - `usage_count` - Total times skill has been used
  - `successful_uses` - Times skill was used successfully
- [x] Create Alembic migration `efe625b872a5_add_skill_usage_tracking.py`
- [x] Create `src/managers/progression_manager.py`
  - `AdvancementResult` dataclass - skill, old_proficiency, new_proficiency, tier_change
  - `SkillProgress` dataclass - progress info with percentage and tier
  - `ProgressionManager` with:
    - `record_skill_use()` - track skill usage with success flag
    - `advance_skill()` - manual proficiency advancement
    - `get_skill_progress()`, `get_all_skill_progress()` - retrieve progress
    - `get_proficiency_tier()` - convert proficiency to tier name
    - `get_progression_context()` - formatted context for display
  - Advancement formula with diminishing returns:
    - Uses 1-10: No advancement
    - Uses 11-25: +3 per 5 successful uses
    - Uses 26-50: +2 per 5 successful uses
    - Uses 51-100: +1 per 5 successful uses
    - Uses 100+: +1 per 10 successful uses
  - Proficiency tiers: Novice, Apprentice, Competent, Expert, Master, Legendary
- [x] Export in `src/managers/__init__.py`
- [x] Create tests in `tests/test_managers/test_progression_manager.py` (22 tests)

### 12.2 Achievement System ✓
- [x] Create `src/database/models/progression.py`
  - `Achievement` model - session-scoped achievement definitions
  - `AchievementType` enum (first_discovery, milestone, title, rank, secret)
  - `EntityAchievement` model - tracks entity unlocks with progress and notifications
- [x] Add `achievements` relationship to `GameSession` model
- [x] Create Alembic migration `79d56dc7020f_add_achievement_system.py`
- [x] Create `src/managers/achievement_manager.py`
  - `AchievementUnlock` dataclass - unlock result with points
  - `AchievementProgress` dataclass - progress toward milestones
  - `AchievementManager` with:
    - `create_achievement()`, `get_achievement()`, `get_all_achievements()`, `get_achievements_by_type()`
    - `unlock_achievement()`, `is_achievement_unlocked()`, `get_unlocked_achievements()`
    - `update_progress()`, `get_progress()` - milestone progress tracking
    - `get_total_points()` - total points for entity
    - `get_recent_unlocks()`, `get_pending_notifications()`, `mark_notified()`
    - `get_achievement_context()` - formatted context
- [x] Export models in `src/database/models/__init__.py`
- [x] Export in `src/managers/__init__.py`
- [x] Create tests in `tests/test_managers/test_achievement_manager.py` (23 tests)

### 12.3 Relationship Milestones ✓
- [x] Add `RelationshipMilestone` model to `src/database/models/relationships.py`
  - milestone_type, dimension, threshold_value, direction
  - message (player-facing notification)
  - notified flag for tracking
- [x] Add `milestones` relationship to `Relationship` model
- [x] Create Alembic migration `2564a021f6ff_add_relationship_milestones.py`
- [x] Add milestone tracking to `RelationshipManager`
  - `_check_milestones()` - automatic detection on attitude changes
  - `_get_active_milestone()` - deduplication with reset detection
  - `get_recent_milestones()` - retrieve milestones for relationship
  - `get_pending_milestone_notifications()` - unnotified milestones
  - `mark_milestone_notified()` - mark as seen
  - `get_milestone_context()` - formatted context
  - `MilestoneInfo` dataclass with entity names
- [x] Milestone types: earned_trust, lost_trust, became_friends, made_enemy, earned_respect, lost_respect, romantic_spark, romantic_interest, close_bond, terrified
- [x] Export `MilestoneInfo` in `src/managers/__init__.py`
- [x] Export `RelationshipMilestone` in `src/database/models/__init__.py`
- [x] Create tests in `tests/test_managers/test_relationship_milestones.py` (20 tests)

### 12.4 Reputation/Faction System (Complete)
- [x] Create `src/database/models/faction.py`
  - `ReputationTier` enum - hated, hostile, unfriendly, neutral, friendly, honored, revered, exalted
  - `Faction` model - faction_key, name, description, base_reputation, is_hostile_by_default
  - `FactionRelationship` model - directional relationships between factions (ally, rival, vassal, enemy)
  - `EntityReputation` model - entity's reputation with factions (-100 to +100)
  - `ReputationChange` model - audit log for reputation changes
- [x] Create `src/managers/reputation_manager.py`
  - `ReputationChange` dataclass - result of reputation adjustment
  - `FactionStanding` dataclass - standing with ally/enemy/neutral status
  - `create_faction()`, `get_faction()`, `get_all_factions()`
  - `get_reputation()`, `adjust_reputation()`, `get_reputation_tier()`
  - `get_faction_standing()` - ally/neutral/enemy status based on thresholds
  - `set_faction_relationship()`, `get_faction_relationship()`
  - `get_allied_factions()`, `get_rival_factions()`
  - `get_reputation_context()` - formatted context for display
  - `get_reputation_history()` - audit trail of changes
- [x] Export `ReputationManager`, `ReputationChange`, `FactionStanding` in `src/managers/__init__.py`
- [x] Export faction models and `ReputationTier` in `src/database/models/__init__.py`
- [x] Add `factions` relationship to `GameSession` in session.py
- [x] Create Alembic migration `76cc10d0166a_add_faction_and_reputation_tables.py`
- [x] Create tests in `tests/test_managers/test_reputation_manager.py` (36 tests)

### 12.5 Summary
- [x] 7 new database models (Achievement, EntityAchievement, RelationshipMilestone, Faction, FactionRelationship, EntityReputation, ReputationChange)
- [x] 2 new fields on EntitySkill
- [x] 3 new managers (ProgressionManager, AchievementManager, ReputationManager)
- [x] 1 enhanced manager (RelationshipManager with milestones)
- [x] 4 Alembic migrations
- [x] 101 new tests total

---

## Phase 13: Combat Depth (Complete)

### 13.1 Weapon & Armor Equipment System (Complete)
- [x] Create `src/database/models/equipment.py`
  - `DamageType` enum - 13 damage types (physical and elemental)
  - `WeaponProperty` enum - 12 weapon properties (finesse, heavy, versatile, etc.)
  - `WeaponCategory` enum - simple_melee, simple_ranged, martial_melee, martial_ranged, exotic, improvised, natural
  - `WeaponRange` enum - melee, reach, ranged, thrown
  - `ArmorCategory` enum - light, medium, heavy, shield
  - `WeaponDefinition` model - weapon_key, damage_dice, damage_type, properties, range, versatile_dice
  - `ArmorDefinition` model - armor_key, base_ac, max_dex_bonus, strength_required, stealth_disadvantage
- [x] Create `src/managers/equipment_manager.py`
  - `WeaponStats` dataclass - attack_bonus, damage_dice, damage_bonus, damage_type
  - `ArmorStats` dataclass - total_ac, base_ac, dex_bonus_applied, stealth_disadvantage
  - `create_weapon()`, `get_weapon()`, `get_all_weapons()`, `get_weapons_by_category()`
  - `get_weapon_stats()` - calculates bonuses with finesse/ranged logic
  - `create_armor()`, `get_armor()`, `get_all_armors()`, `get_armors_by_category()`
  - `get_armor_stats()` - calculates AC with DEX cap
  - `calculate_total_ac()` - combines armor + shield + DEX
- [x] Export equipment models and enums in `src/database/models/__init__.py`
- [x] Export `EquipmentManager`, `WeaponStats`, `ArmorStats` in `src/managers/__init__.py`
- [x] Create migration `ec5a9e5f55d4_add_weapon_and_armor_definition_tables.py`
- [x] Create tests in `tests/test_database/test_models/test_equipment.py` (19 tests)
- [x] Create tests in `tests/test_managers/test_equipment_manager.py` (32 tests)

### 13.2 Combat Conditions System (Complete)
- [x] Create `src/database/models/combat_conditions.py`
  - `CombatCondition` enum - 16 conditions (prone, stunned, grappled, etc.)
  - `EntityCondition` model - entity_id, condition, duration_rounds, rounds_remaining, source_entity_id, exhaustion_level
- [x] Create `src/managers/combat_condition_manager.py`
  - `ConditionInfo` dataclass - condition info with source and duration
  - `ConditionEffect` dataclass - combined effects on attacks, defense, saves, movement
  - `apply_condition()` - apply/extend conditions, exhaustion stacks
  - `remove_condition()`, `remove_all_conditions()`
  - `tick_conditions()` - advance time, expire timed conditions
  - `has_condition()`, `get_active_conditions()`, `get_condition_info()`
  - `get_condition_effects()` - calculate combined effects
  - `get_condition_context()` - formatted string for display
- [x] Export combat condition models in `src/database/models/__init__.py`
- [x] Export `CombatConditionManager`, `ConditionInfo`, `ConditionEffect` in `src/managers/__init__.py`
- [x] Create migration `a3c9cc28fc46_add_entity_conditions_table.py`
- [x] Create tests in `tests/test_managers/test_combat_conditions.py` (27 tests)

### 13.3 Action Economy & Contested Rolls (Complete)
- [x] Create `src/dice/contested.py`
  - `ActionType` enum - standard, move, bonus, reaction, free
  - `ActionBudget` class - action tracking per turn
    - `can_use()`, `use()`, `reset()`
    - `convert_standard_to_move()`
    - `get_remaining_string()`
  - `ContestResult` dataclass - rolls, totals, winner, margin
  - `contested_roll()` - generic opposed check with advantage support
  - `resolve_contest()` - determine winner (ties to defender)
  - `grapple_contest()` - Athletics vs Athletics/Acrobatics
  - `escape_grapple_contest()` - Athletics/Acrobatics vs Athletics
  - `shove_contest()` - Athletics vs Athletics/Acrobatics
  - `stealth_contest()` - Stealth vs Perception
  - `social_contest()` - Social skill vs Insight
- [x] Export contested roll functions and classes in `src/dice/__init__.py`
- [x] Create tests in `tests/test_dice/test_contested_rolls.py` (23 tests)

### 13.4 Summary
- [x] 5 new database models (WeaponDefinition, ArmorDefinition, EntityCondition + 2 enums as models)
- [x] 8 new enums (DamageType, WeaponProperty, WeaponCategory, WeaponRange, ArmorCategory, CombatCondition, ActionType)
- [x] 2 new managers (EquipmentManager, CombatConditionManager)
- [x] 1 new dice module (contested.py)
- [x] 3 Alembic migrations
- [x] 101 new tests total

---

## Phase 14: Social Systems (Tier 3 - Medium Priority)

### 14.1 Rumor System (Complete)

**Purpose:** Player actions propagate through social networks. NPCs gossip about player deeds, and reputation precedes the player to new locations.

**Design:**
- Rumors have origin (who witnessed), spread rate, decay over time
- Social connections determine propagation paths
- Distortion: rumors mutate as they spread (exaggeration, minimization, inversion)
- Location-based: rumors spread faster in taverns, markets, social hubs

**Database Models:**
- [x] Create `src/database/models/rumors.py`
  - `Rumor` model:
    - `rumor_key: str` - unique identifier
    - `subject_entity_key: str` - who the rumor is about
    - `content: str` - the rumor text
    - `truth_value: float` - 0.0 (false) to 1.0 (true), tracks distortion
    - `original_event_id: int | None` - link to WorldEvent that spawned it
    - `origin_location_key: str` - where rumor started
    - `origin_turn: int` - when rumor started
    - `spread_rate: float` - how fast it propagates (0.1-1.0)
    - `decay_rate: float` - how fast it fades (0.01-0.1 per day)
    - `intensity: float` - current strength (0.0-1.0)
    - `sentiment: str` - positive, negative, neutral
    - `tags: list[str]` - categorization (violence, romance, theft, heroism, etc.)
  - `RumorKnowledge` model:
    - `entity_id: int` - NPC who knows the rumor
    - `rumor_id: int` - the rumor
    - `learned_turn: int` - when they heard it
    - `believed: bool` - do they believe it
    - `will_spread: bool` - will they tell others
    - `local_distortion: str | None` - how they've modified it

**Manager:**
- [x] Create `src/managers/rumor_manager.py`
  - `create_rumor()` - create from player action or event
  - `spread_rumors()` - called on time advance, propagate through social network
  - `get_rumors_known_by()` - what an NPC knows
  - `get_rumors_about()` - all rumors about an entity
  - `get_rumors_at_location()` - rumors circulating in a place
  - `decay_rumors()` - reduce intensity over time
  - `distort_rumor()` - mutate content based on NPC personality
  - `check_rumor_reaction()` - how NPC reacts to hearing about player
  - `get_rumor_context()` - formatted for GM prompt

**Integration Points:**
- `WorldEvent` creation triggers rumor generation for significant events
- `RelationshipManager` - rumors affect initial attitudes with strangers
- `ContextCompiler` - include relevant rumors in scene context
- NPCs may reference rumors in dialogue

**Example Flow:**
1. Player kills bandit leader in village square (witnesses present)
2. Rumor created: "A stranger slew the bandit chief with a single blow"
3. Witnesses spread to friends/family (social connections)
4. Rumor reaches tavern → rapid spread to travelers
5. Player arrives in next town → NPCs already heard "a mighty warrior" is coming
6. Some distortion: "single blow" becomes "bare hands" after 3 hops

---

### 14.2 Relationship Arc Templates (Complete + LLM Enhancement)

**Purpose:** Provide narrative scaffolding for relationship development. Templates suggest dramatic beats for common relationship patterns.

**Design:**
- Predefined arc types with milestone progression
- Each arc has trigger conditions, suggested scenes, climax moment
- GM receives hints when arc conditions are met
- Player unaware of arc mechanics (emergent storytelling)

**Arc Types:**
1. **Enemies to Lovers** - initial hostility → grudging respect → attraction → confession
2. **Mentor's Fall** - admiration → learning → mentor's flaw revealed → disillusionment or forgiveness
3. **Betrayal** - trust building → secret agenda hints → betrayal → confrontation
4. **Redemption** - villain/morally gray → player influence → crisis point → redemption or rejection
5. **Rivalry** - competition → escalation → mutual respect or enmity
6. **Found Family** - strangers → shared hardship → loyalty → family bond
7. **Lost Love Rekindled** - past connection → reunion → obstacles → resolution
8. **Corruption** - innocent ally → temptation → moral decay → player choice to save or condemn

**Database Models:**
- [x] Create `src/database/models/relationship_arcs.py`
  - `RelationshipArcType` enum - arc type names
  - `RelationshipArcPhase` enum - introduction, development, crisis, climax, resolution
  - `RelationshipArc` model:
    - `arc_key: str` - unique identifier
    - `arc_type: RelationshipArcType`
    - `entity1_key: str` - usually player
    - `entity2_key: str` - the NPC
    - `current_phase: RelationshipArcPhase`
    - `phase_progress: int` - 0-100 progress in current phase
    - `milestones_hit: list[str]` - JSON list of achieved milestones
    - `suggested_next_beat: str | None` - hint for GM
    - `arc_tension: int` - 0-100 dramatic tension
    - `is_active: bool`
    - `started_turn: int`
    - `completed_turn: int | None`
  - `ArcTemplate` - static definitions (could be JSON config instead)
    - `arc_type: RelationshipArcType`
    - `phases: dict` - phase definitions with milestones
    - `trigger_conditions: list[str]` - when to suggest this arc
    - `climax_options: list[str]` - possible climax scenarios

**Manager:**
- [x] Create `src/managers/relationship_arc_manager.py`
  - `suggest_arc()` - analyze relationship, suggest fitting arc
  - `start_arc()` - begin tracking an arc
  - `check_milestone()` - evaluate if milestone conditions met
  - `advance_phase()` - move to next arc phase
  - `get_arc_hint()` - GM guidance for current phase
  - `get_active_arcs()` - all in-progress relationship arcs
  - `complete_arc()` - mark arc as resolved
  - `get_arc_context()` - formatted for GM prompt

**Template Example - Enemies to Lovers:**
```python
{
    "arc_type": "enemies_to_lovers",
    "phases": {
        "introduction": {
            "description": "Initial antagonism established",
            "milestones": ["first_conflict", "verbal_sparring", "physical_confrontation"],
            "attitude_range": {"liking": (-100, -30)},
            "suggested_scenes": ["Forced to work together", "Rescue despite hatred"]
        },
        "development": {
            "description": "Grudging respect develops",
            "milestones": ["acknowledge_skill", "share_vulnerability", "defend_reputation"],
            "attitude_range": {"liking": (-30, 20), "respect": (30, 100)},
            "suggested_scenes": ["See them in new light", "Learn their backstory"]
        },
        "crisis": {
            "description": "Feelings surface, must be addressed",
            "milestones": ["jealousy_moment", "almost_kiss", "confession_interrupted"],
            "suggested_scenes": ["Third party romantic interest", "Separation threat"]
        },
        "climax": {
            "description": "Declaration or rejection",
            "milestones": ["love_confession", "grand_gesture"],
            "suggested_scenes": ["Life-threatening situation", "Choice between duty and love"]
        },
        "resolution": {
            "description": "New relationship status established",
            "milestones": ["relationship_defined", "future_discussed"],
            "suggested_scenes": ["Quiet moment together", "Public acknowledgment"]
        }
    },
    "trigger_conditions": [
        "liking < -50 AND respect > 30",
        "has_tag('romantic_potential') AND has_tag('initial_enemy')"
    ]
}
```

**LLM Enhancement (Complete):**

Arcs can now be fully generated by LLM based on relationship dynamics, not limited to predefined types.

- [x] Create `src/agents/schemas/arc_generation.py`
  - `ArcPhaseTemplate` schema - phase with milestones and suggested scenes
  - `GeneratedArcTemplate` schema - full arc with phases, endings, tension triggers
- [x] Create `data/templates/arc_generator.md` - prompt template for arc generation
- [x] Database changes:
  - `arc_type` changed from `String(30)` to `String(100)` (allows any LLM-generated type)
  - `current_phase` changed from `String(20)` to `String(50)` (custom phase names)
  - Added `arc_template: JSON` - stores LLM-generated template
  - Added `arc_description: Text` - arc summary
  - Migration: `4fbbe5395f6d_llm_generated_arcs_and_voices.py`
- [x] Manager enhancements:
  - `generate_arc_for_relationship()` - async method generates custom arc via LLM
  - `create_arc_from_generated()` - create arc from LLM template
  - `get_arc_beat_suggestion()` - uses stored arc_template when available
  - `ArcInfo` extended with `arc_description`, `is_custom` fields
  - Predefined arcs retained as `WellKnownArcType` enum (examples/fallback)

**Critical Design: Arcs as Guidance, Not Scripts**

| Aspect | Arc System Does | Arc System Does NOT |
|--------|-----------------|---------------------|
| Suggestions | "This trajectory could lead to betrayal" | "At turn 50, NPC betrays player" |
| Milestones | "Watch for moments of vulnerability" | Force scenes to happen |
| Endings | "Possible: reconciliation OR enmity" | Lock in a predetermined ending |
| Relationships | Leave values unchanged | Override or script relationship changes |

Player agency preserved - arcs inspire GM, actual outcomes depend on player actions.

---

### 14.3 NPC Voice Templates (Complete + LLM Enhancement)

**Purpose:** Provide consistent speech patterns for NPCs based on social class, occupation, region, and personality. GM uses these to maintain voice consistency.

**Design:**
- Voice templates define vocabulary, sentence structure, verbal tics
- Templates combined: base (class) + occupation modifier + personality modifier + regional dialect
- Include example phrases for common situations
- Stored as configuration (not database) for easy editing

**Configuration Structure:**
- [x] Create `data/templates/voices/` directory
- [x] Create voice template files:

**Base Templates (Social Class):**
```yaml
# data/templates/voices/base_noble.yaml
noble:
  vocabulary_level: sophisticated
  sentence_structure: complex, complete
  contractions: never
  swearing: euphemisms only ("By the stars", "Confound it")
  greetings: ["Good morrow", "Well met", "I bid you welcome"]
  farewells: ["Fare thee well", "Until we meet again", "I take my leave"]
  affirmatives: ["Indeed", "Quite so", "As you say"]
  negatives: ["I think not", "That would be... inadvisable", "Regrettably, no"]
  filler_words: ["Perhaps", "One might consider", "It would seem"]
  speech_patterns:
    - Uses third person ("One does not simply...")
    - Indirect requests ("It would please me if...")
    - Formal titles always
  example_dialogue:
    greeting_stranger: "Ah, a visitor. State your business, if you would be so kind."
    refusing_request: "While I appreciate your... enthusiasm, I fear I must decline."
    expressing_anger: "This is most vexing. You try my patience, truly."
```

```yaml
# data/templates/voices/base_commoner.yaml
commoner:
  vocabulary_level: simple
  sentence_structure: short, direct
  contractions: frequent
  swearing: common, work-related ("Bloody hell", "Damn the rot")
  greetings: ["Hey there", "Oi", "What d'ya want"]
  farewells: ["See ya", "Take care now", "Off with ya"]
  affirmatives: ["Aye", "Right", "Sure thing"]
  negatives: ["Nah", "No way", "Can't do it"]
  filler_words: ["Well", "Y'know", "Thing is"]
  speech_patterns:
    - Dropped letters ("goin'", "'bout", "nothin'")
    - Double negatives acceptable
    - First names or nicknames
  example_dialogue:
    greeting_stranger: "Oi, you new 'round here? What're ya after?"
    refusing_request: "Sorry mate, can't help ya there."
    expressing_anger: "What in the bloody hell d'ya think you're doin'?!"
```

**Occupation Modifiers:**
```yaml
# data/templates/voices/occupation_merchant.yaml
merchant:
  additional_vocabulary: ["deal", "bargain", "value", "worth", "coin", "trade"]
  verbal_tics: ["speaking of value", "between you and me", "I'll tell you what"]
  speech_patterns:
    - Relates things to money/trade
    - Tries to find common ground
    - Uses flattery strategically
  occupation_phrases:
    haggling: "Now now, surely we can come to an arrangement..."
    greeting: "Welcome, welcome! You look like someone with discerning taste."
    farewell: "May your purse stay heavy and your roads stay safe!"
```

```yaml
# data/templates/voices/occupation_soldier.yaml
soldier:
  additional_vocabulary: ["orders", "duty", "formation", "watch", "enemy", "blade"]
  verbal_tics: ["on my honor", "by the code", "soldier to soldier"]
  speech_patterns:
    - Brief, efficient communication
    - Military metaphors
    - Ranks and chain of command references
  occupation_phrases:
    greeting: "State your name and business."
    warning: "That's your first warning. Won't be a second."
    respect: "You handle yourself well. Soldier?"
```

**Personality Modifiers:**
```yaml
# data/templates/voices/personality_nervous.yaml
nervous:
  speech_patterns:
    - Incomplete sentences
    - Self-interruption
    - Excessive apologies
  verbal_tics: ["um", "er", "sorry", "I didn't mean", "that is to say"]
  modifications:
    sentence_length: shorter
    pause_frequency: high
  example_dialogue:
    any: "I... well, that is... sorry, what I meant was... never mind, it's nothing."
```

**Regional Dialects:**
```yaml
# data/templates/voices/region_northern.yaml
northern:
  accent_notes: "Hard consonants, rolling Rs"
  vocabulary_replacements:
    hello: "well met"
    friend: "kinsman"
    stranger: "outlander"
    cold: "bitter"
  regional_expressions: ["By the frost", "Cold as a witch's heart", "Sturdy as mountain stone"]
```

**Manager:**
- [x] Create `src/managers/voice_manager.py`
  - `build_voice_template()` - combine templates for an NPC
  - `get_example_dialogue()` - get example for situation type
  - `get_base_class()`, `get_occupation()`, `get_personality()`, `get_region()` - individual template access
  - `get_voice_context()` - formatted for GM prompt
  - `get_available_base_classes()`, `get_available_occupations()`, etc. - list available templates

**Integration:**
- `ContextCompiler` includes voice guidance for NPCs in scene
- `NPCExtension` stores voice template keys (class, occupation, personality, region)
- GM prompt section: "NPC Voice Guidelines" with merged template info

**LLM Enhancement (Complete):**

Voices can now be fully generated by LLM based on NPC characteristics and setting.

- [x] Create `src/agents/schemas/voice_generation.py`
  - `GeneratedVoiceTemplate` schema with 20+ fields:
    - Core: vocabulary_level, sentence_structure, formality, speaking_pace
    - Patterns: verbal_tics, speech_patterns, filler_words
    - Vocabulary: favorite_expressions, greetings, farewells, affirmatives, negatives
    - Swearing: swearing_style, swear_examples
    - Dialogue: example_dialogue (dict of situation → example line)
    - Regional: accent_notes, dialect_features, vocabulary_notes
    - Context changes: formal_context_changes, stress_context_changes
    - Summary: voice_summary (one-sentence voice description)
- [x] Create `data/templates/voice_generator.md` - prompt template with setting-specific guidance:
  - Fantasy: Medieval speech, class distinctions, regional dialects
  - Contemporary: Modern slang, professional jargon, regional accents
  - Sci-fi: Technical terminology, alien speech patterns, futuristic expressions
- [x] Database changes:
  - Added `voice_template_json: JSON` to NPCExtension for persistence
  - Migration: `4fbbe5395f6d_llm_generated_arcs_and_voices.py`
- [x] Manager enhancements:
  - `generate_voice_template()` - async method generates custom voice via LLM
  - `format_generated_voice_context()` - formats voice for GM prompt
  - `voice_template_from_dict()` - loads cached voice from database
  - YAML templates retained as few-shot examples in LLM prompts

---

## Phase 15: World Simulation (Tier 4 - Lower Priority) [COMPLETE]

### 15.1 Economic Events System [COMPLETE]

**Purpose:** Dynamic economy with market fluctuations, trade routes, supply/demand. Creates living world where prices change based on events.

**Design:**
- Base prices per item per region
- Modifiers: scarcity, demand, events, season, trade route status
- Events trigger price changes (war → weapons expensive, famine → food expensive)
- Trade routes connect regions; disruption affects availability

**Database Models:**
- [x] Create `src/database/models/economy.py`
  - `MarketPrice` model:
    - `location_key: str` - market location
    - `item_key: str` - item being priced
    - `base_price: int` - standard price in copper
    - `current_price: int` - actual current price
    - `supply_level: str` - scarce, low, normal, abundant, oversupply
    - `demand_level: str` - none, low, normal, high, desperate
    - `price_trend: str` - rising, stable, falling
    - `last_updated_turn: int`
  - `TradeRoute` model:
    - `route_key: str`
    - `origin_location_key: str`
    - `destination_location_key: str`
    - `goods_traded: list[str]` - item categories
    - `route_status: str` - active, disrupted, blocked, destroyed
    - `disruption_reason: str | None`
    - `travel_time_days: int`
    - `danger_level: int` - 0-100
  - `EconomicEvent` model:
    - `event_key: str`
    - `event_type: str` - famine, war, festival, discovery, plague, etc.
    - `affected_locations: list[str]`
    - `affected_items: list[str]`
    - `price_modifier: float` - multiplier (0.5 = half price, 2.0 = double)
    - `supply_effect: str` - decrease, increase, none
    - `start_turn: int`
    - `duration_turns: int | None` - None = permanent until resolved
    - `is_active: bool`

**Manager:**
- [x] Create `src/managers/economy_manager.py`
  - `get_price()` - current price for item at location
  - `update_prices()` - recalculate based on events/supply/demand
  - `create_economic_event()` - trigger economic change
  - `resolve_economic_event()` - end an event
  - `get_trade_routes()` - routes to/from location
  - `disrupt_trade_route()` - block a route
  - `restore_trade_route()` - reopen a route
  - `get_market_summary()` - overview for location
  - `get_economy_context()` - formatted for GM prompt

**Price Calculation:**
```python
def calculate_price(base_price, supply, demand, events, season):
    modifier = 1.0

    # Supply modifier
    supply_mods = {"scarce": 2.0, "low": 1.3, "normal": 1.0, "abundant": 0.8, "oversupply": 0.5}
    modifier *= supply_mods[supply]

    # Demand modifier
    demand_mods = {"none": 0.5, "low": 0.8, "normal": 1.0, "high": 1.3, "desperate": 2.0}
    modifier *= demand_mods[demand]

    # Event modifiers (multiplicative)
    for event in events:
        modifier *= event.price_modifier

    # Season modifier (food more expensive in winter, etc.)
    modifier *= get_seasonal_modifier(item_category, season)

    return int(base_price * modifier)
```

---

### 15.2 Magic System [COMPLETE]

**Purpose:** Flexible magic system adaptable to different settings. Core mechanics that can be flavored for fantasy, sci-fi (psionics), or supernatural horror.

**Design Principles:**
- Resource-based casting (mana, spell slots, fatigue)
- Schools/traditions for categorization
- Scaling effects based on power invested
- Consequences for overuse or failure

**Core Mechanics:**
- [x] Create `src/database/models/magic.py`
  - `MagicTradition` enum - arcane, divine, primal, psionic, occult (setting-configurable)
  - `SpellSchool` enum - evocation, illusion, necromancy, etc.
  - `SpellDefinition` model:
    - `spell_key: str`
    - `name: str`
    - `tradition: MagicTradition`
    - `school: SpellSchool`
    - `base_cost: int` - mana/power points
    - `casting_time: str` - action, bonus, ritual (minutes)
    - `range: str` - self, touch, 30ft, sight, unlimited
    - `duration: str` - instant, concentration, 1 hour, permanent
    - `description: str`
    - `effects: dict` - structured effect data
    - `scaling: dict | None` - how spell improves with more power
    - `components: list[str]` - verbal, somatic, material
    - `material_cost: str | None` - consumed materials
  - `EntityMagic` model (extension to Entity):
    - `entity_id: int`
    - `tradition: MagicTradition`
    - `max_mana: int`
    - `current_mana: int`
    - `mana_regen_rate: int` - per rest
    - `known_spells: list[str]` - spell_keys
    - `prepared_spells: list[str]` - if preparation system used
    - `spell_slots: dict | None` - if slot-based system
  - `SpellCast` model (history):
    - `caster_entity_id: int`
    - `spell_key: str`
    - `turn_cast: int`
    - `target_entity_keys: list[str]`
    - `power_used: int`
    - `success: bool`
    - `outcome: str`

**Manager:**
- [x] Create `src/managers/magic_manager.py`
  - `learn_spell()` - add spell to known list
  - `prepare_spell()` - ready spell for casting
  - `can_cast()` - check resources and conditions
  - `cast_spell()` - execute spell, consume resources
  - `get_spell_effect()` - calculate effect based on caster stats
  - `apply_spell_effect()` - modify target state
  - `regenerate_mana()` - restore on rest
  - `get_known_spells()` - list caster's spells
  - `get_magic_context()` - formatted for GM prompt

**Spell Effect Structure:**
```python
{
    "damage": {"dice": "3d6", "type": "fire", "save": "dexterity", "half_on_save": True},
    "healing": {"dice": "2d8+4"},
    "condition": {"apply": "frightened", "duration": 3, "save": "wisdom"},
    "buff": {"attribute": "strength", "bonus": 4, "duration": 10},
    "summon": {"entity_template": "fire_elemental", "duration": 60},
    "utility": {"effect": "light", "radius": 20, "duration": 60}
}
```

---

### 15.3 Prophesy & Destiny Tracking [COMPLETE]

**Purpose:** Track foreshadowing, prophesies, and destiny elements. Ensure planted narrative seeds are harvested.

**Design:**
- Prophesies have conditions for fulfillment
- Multiple interpretation paths (subverted, fulfilled literally, fulfilled metaphorically)
- GM receives reminders when prophesy elements appear
- Player choices can alter destiny (or seal it)

**Database Models:**
- [x] Create `src/database/models/destiny.py`
  - `Prophesy` model:
    - `prophesy_key: str`
    - `prophesy_text: str` - the actual prophesy wording
    - `true_meaning: str` - GM-only actual meaning
    - `source: str` - who/what delivered it
    - `delivered_turn: int`
    - `status: str` - active, fulfilled, subverted, abandoned
    - `fulfillment_conditions: list[str]` - what must happen
    - `subversion_conditions: list[str]` - how it could be avoided
    - `interpretation_hints: list[str]` - clues for player
    - `fulfilled_turn: int | None`
    - `fulfillment_description: str | None`
  - `DestinyElement` model:
    - `element_key: str`
    - `element_type: str` - omen, sign, portent, vision
    - `description: str`
    - `linked_prophesy_key: str | None`
    - `witnessed_by: list[str]` - entity_keys
    - `turn_occurred: int`
    - `significance_level: int` - 1-5
    - `player_noticed: bool`

**Manager:**
- [x] Create `src/managers/destiny_manager.py`
  - `create_prophesy()` - establish a prophesy
  - `add_destiny_element()` - plant foreshadowing
  - `check_prophesy_status()` - evaluate fulfillment conditions
  - `fulfill_prophesy()` - mark as fulfilled
  - `subvert_prophesy()` - mark as subverted
  - `get_active_prophesies()` - all in-progress prophesies
  - `get_relevant_elements()` - destiny elements for current scene
  - `get_prophesy_hints()` - GM reminders for prophesy progression
  - `get_destiny_context()` - formatted for GM prompt

---

### 15.4 Encumbrance & Weight System [COMPLETE]

**Purpose:** Track carrying capacity and movement penalties. Creates meaningful inventory decisions.

**Design:**
- Strength-based carrying capacity
- Weight categories: light, medium, heavy, over-encumbered
- Movement and combat penalties when over-burdened
- Container capacity (bags, backpacks)

**Implementation:**
- [x] Add to `src/database/models/items.py`:
  - `weight: float` field on Item model (in pounds/kg)
  - `capacity: float | None` field for containers

- [x] Create `src/managers/encumbrance_manager.py`
  - `get_carried_weight()` - total weight carried by entity
  - `get_carry_capacity()` - max weight based on Strength
  - `get_encumbrance_level()` - light/medium/heavy/over
  - `get_movement_penalty()` - speed reduction
  - `get_combat_penalty()` - disadvantage on checks
  - `can_pick_up()` - check if item fits in capacity
  - `get_encumbrance_context()` - formatted for display

**Capacity Calculation:**
```python
def get_carry_capacity(strength: int) -> dict:
    base = strength * 15  # pounds
    return {
        "light": base * 0.33,      # No penalty
        "medium": base * 0.66,     # -10 speed
        "heavy": base,             # -20 speed, disadvantage on physical checks
        "max_lift": base * 2       # Can lift but not move
    }
```

**Movement Penalties:**
```python
ENCUMBRANCE_EFFECTS = {
    "light": {"speed_penalty": 0, "check_penalty": None},
    "medium": {"speed_penalty": 10, "check_penalty": None},
    "heavy": {"speed_penalty": 20, "check_penalty": "disadvantage_physical"},
    "over": {"speed_penalty": "immobile", "check_penalty": "disadvantage_all"}
}
```

---

## Phase 16: Future Considerations

### 16.1 Potential Additions (Not Planned)
- **Crafting System** - create items from materials
- **Weather Impact** - weather affects travel, combat, NPC behavior
- **Disease & Plague** - illness mechanics beyond injury
- **Mount & Vehicle System** - travel speeds, mounted combat
- **Base Building** - player-owned structures
- **Time Skip Mechanics** - fast-forward through downtime
- **Multiplayer Support** - multiple player characters

### 16.2 Setting-Specific Modules
- **Fantasy Module** - full magic, divine intervention, mythical creatures
- **Sci-Fi Module** - technology, hacking, space travel
- **Horror Module** - sanity system, supernatural dread
- **Historical Module** - realistic constraints, period accuracy
