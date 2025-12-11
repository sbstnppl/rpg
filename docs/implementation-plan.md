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
- [x] Test database models (1995 tests total)
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
- [x] Create `tests/test_services/test_emergent_npc_generator.py` (27 tests)
- [x] Create `tests/test_services/test_emergent_item_generator.py` (43 tests)

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
