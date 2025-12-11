# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Structured GM Output System (Phase 1-2)** - Tool-based entity creation with emergent traits
  - **Goal System Infrastructure** (`src/agents/schemas/goals.py`):
    - `NPCGoal` schema with 12 goal types (acquire, romance, survive, duty, etc.)
    - `GoalUpdate` schema for tracking goal progress
    - Priority levels: background, low, medium, high, urgent
    - Strategy steps and completion conditions
  - **NPC State Schemas** (`src/agents/schemas/npc_state.py`):
    - `NPCFullState` - Complete NPC data with appearance, personality, needs
    - `NPCAppearance` - Age (precise + narrative), physical description
    - `NPCPersonality` - Traits, values, flaws, quirks, speech patterns
    - `NPCPreferencesData` - Attraction preferences (physical + personality)
    - `EnvironmentalReaction` - NPC reactions to scene elements
    - `AttractionScore` - Physical/personality/overall attraction calculation
    - `SceneContext`, `VisibleItem`, `PlayerSummary` for situational awareness
  - **GM Response Schemas** (`src/agents/schemas/gm_response.py`):
    - `GMResponse` - Structured output with narrative + manifest
    - `GMManifest` - NPCs, items, actions, relationship changes
    - `NPCAction` - Entity actions with motivation tracking
  - **Goal Manager** (`src/managers/goal_manager.py`):
    - `create_goal()` - Create goals with triggers and strategies
    - `get_goals_for_entity()` - Query active goals
    - `update_goal_progress()` - Advance goal steps
    - `complete_goal()`, `fail_goal()`, `abandon_goal()`
    - `get_urgent_goals()` - Priority-based filtering
    - `get_goals_by_type()` - Type-based filtering
    - 35 tests in `tests/test_managers/test_goal_manager.py`
  - **Emergent NPC Generator** (`src/services/emergent_npc_generator.py`):
    - Philosophy: "GM Discovers, Not Prescribes"
    - Creates NPCs with emergent personality, preferences, attractions
    - Environmental reactions (notices items, calculates attraction)
    - Immediate goal generation based on role and needs
    - Behavioral prediction for GM guidance
    - Database persistence (Entity, NPCExtension, Skills, Preferences, Needs)
    - 27 tests in `tests/test_services/test_emergent_npc_generator.py`
  - **Emergent Item Generator** (`src/services/emergent_item_generator.py`):
    - Items have emergent quality, condition, value, provenance
    - Context-based subtype inference (e.g., "sword" → sword damage)
    - 8 item types: weapon, armor, clothing, food, drink, tool, container, misc
    - Need triggers (food→hunger, drink→thirst)
    - Narrative hooks for storytelling
    - 43 tests in `tests/test_services/test_emergent_item_generator.py`
  - **NPC Tools** (`src/agents/tools/npc_tools.py`):
    - `CREATE_NPC_TOOL` - Create NPC with emergent traits, optional constraints
    - `QUERY_NPC_TOOL` - Query existing NPC's reactions to scene
    - `CREATE_ITEM_TOOL` - Create item with emergent properties
  - **Tool Executor Updates** (`src/agents/tools/executor.py`):
    - `_execute_create_npc()` - Handler for NPC creation
    - `_execute_query_npc()` - Handler for NPC queries
    - `_execute_create_item()` - Handler for item creation
    - Lazy-loaded `npc_generator` and `item_generator` properties
  - **World Simulator Goal Processing** (`src/agents/world_simulator.py`):
    - `_check_need_driven_goals()` - Auto-create goals from urgent NPC needs
    - `_process_npc_goals()` - Process active NPC goals during simulation
    - `_execute_goal_step()` - Execute single goal step with success/failure
    - `_evaluate_step_success()` - Probabilistic step success based on type/priority
    - `_check_step_for_movement()` - Detect location-changing goal steps
    - New dataclasses: `GoalStepResult`, `GoalCreatedEvent`
    - Extended `SimulationResult` with goal tracking fields
    - Fixed bug: Removed invalid `Schedule.session_id` filter
    - 9 tests in `tests/test_agents/test_nodes/test_world_simulator_goals.py`
  - **Context Compiler with NPC Motivations** (`src/managers/context_compiler.py`):
    - `_get_npc_location_reason()` - Returns "Goal pursuit" or "Scheduled" based on NPC state
    - `_get_npc_active_goals()` - Returns formatted goal list with priority and motivation
    - `_get_urgent_needs()` - Returns needs with >60% urgency (hunger, thirst, etc.)
    - `_get_entity_registry_context()` - Provides entity keys for manifest references
    - Updated `_format_npc_context()` to include goals, location reason, urgent needs
    - Added `entity_registry_context` field to `SceneContext`
    - Updated `to_prompt()` to include entity registry section
    - 14 tests in `tests/test_managers/test_context_compiler_goals.py`
  - **GM Response Schema** (`src/agents/schemas/gm_response.py`):
    - `GMResponse` - Structured output with narrative + state + manifest
    - `GMManifest` - NPCs, items, actions, relationship changes, facts, stimuli, goals
    - `GMState` - Time advancement, location changes, combat initiation
    - `NPCAction` - Entity actions with motivation tracking
    - `ItemChange` - Item ownership/state changes
    - `RelationshipChange` - Relationship dimension changes with reason
    - `FactRevealed` - Facts learned with secret flag
    - `Stimulus` - Need-affecting stimuli with intensity
    - Re-uses `GoalCreation` and `GoalUpdate` from goals.py (no duplication)
  - Updated `src/agents/schemas/__init__.py` with GM response exports
  - **Persistence Node Manifest Support** (`src/agents/nodes/persistence_node.py`):
    - `_persist_from_manifest()` - Process GMManifest data for persistence
    - `_persist_manifest_fact()` - Persist FactRevealed entries
    - `_persist_manifest_relationship()` - Persist RelationshipChange entries
    - `_persist_manifest_goal_creation()` - Create goals from GoalCreation entries
    - `_persist_manifest_goal_update()` - Process GoalUpdate entries (complete, fail, advance)
    - Dual-mode support: manifest-based (new) or extraction-based (legacy)
    - 16 tests in `tests/test_agents/test_nodes/test_persistence_manifest.py`
  - **GameState Updates** (`src/agents/state.py`):
    - Added `gm_manifest` field for structured GMResponse output
    - Added `skill_checks` field for interactive dice display
    - Updated docstrings for legacy vs manifest fields
  - **Phase 6: Polish** (Integration tests, bug fixes, documentation):
    - 9 new integration tests in `tests/test_integration/test_emergent_scenarios.py`:
      - `TestHungryNPCScenario` - Hungry NPCs react to food, satisfied NPCs don't
      - `TestGoalDrivenNPCScenario` - Goals persisted and updated via manifest
      - `TestAttractionScenario` - Attraction varies by player traits, constraints work
      - `TestFullManifestWorkflow` - Complex manifests with multiple components
  - **Phase 1-6: Future Enhancements Implementation**
    - **Missed Appointments Check** (`src/agents/world_simulator.py`):
      - Added `_check_missed_appointments()` method to detect appointments players missed
      - Added `missed_appointments` field to `SimulationResult` dataclass
    - **Player Activity Inference** (`src/agents/nodes/world_simulator_node.py`):
      - Added `_infer_player_activity()` function to detect player state from scene context
      - Detects: sleeping, combat, socializing, resting, active states
    - **Companion Detection** (`src/agents/nodes/world_simulator_node.py`):
      - Added companion query to determine if player is alone
    - **Legacy Relationship Persistence** (`src/agents/nodes/persistence_node.py`):
      - Fixed `_persist_relationship_change()` to properly update attitude dimensions
    - **NPC Location Filtering** (`src/managers/context_compiler.py`):
      - Fixed `_get_npcs_context()` to filter NPCs by current location
    - **Task Context** (`src/managers/context_compiler.py`):
      - Added `_get_tasks_context()` to include active tasks in context
    - **Map Context for Navigation** (`src/managers/context_compiler.py`):
      - Added `_get_map_inventory_context()` to show available maps during navigation
    - **View Map Tool** (`src/agents/tools/gm_tools.py`, `src/agents/tools/executor.py`):
      - Added `VIEW_MAP_TOOL` definition for examining maps
      - Added `_execute_view_map()` handler with hierarchical zone discovery
      - Enhanced `view_map()` in DiscoveryManager to handle `coverage_zone_id`
      - Added `_get_descendant_zones()` for recursive zone tree traversal
    - **NPC Location-Based Activity** (`src/schemas/settings.py`, `src/agents/world_simulator.py`):
      - Added `LOCATION_ACTIVITY_MAPPING` dict (16 location types → activities)
      - Added `get_location_activities()` function for activity lookup
      - Updated `_get_npc_activity_type()` to use location context
      - Added `_get_location_based_activity()` and `_activity_string_to_type()`
    - **Location Change Tracking** (`src/database/models/world.py`, `src/agents/world_simulator.py`):
      - New `LocationVisit` model to track player visits with snapshots
      - Migration `012_add_location_visits.py` for the new table
      - Added `_record_location_visit()`, `_check_location_changes()`
      - Added `_get_items_at_location()`, `_get_npcs_at_location()`, `_get_events_since_visit()`
      - Added `location_changes` field to `SimulationResult` dataclass
    - **YAML/JSON World Import** (`src/services/world_loader.py`, `src/schemas/world_template.py`):
      - New `WorldTemplate`, `ZoneTemplate`, `ConnectionTemplate`, `LocationTemplate` Pydantic schemas
      - New `load_world_from_file()` function for YAML/JSON import
      - Helper functions for enum parsing with aliases
      - New CLI command `world import <file>` for importing world files
      - 8 tests in `tests/test_services/test_world_loader.py`

### Fixed
- **EmergentNPCGenerator needs inversion bug**: Fixed `query_npc_reactions()` to properly convert CharacterNeeds (high=good) to NPCNeeds schema (high=urgent) by inverting hunger and thirst values. Previously well-fed NPCs (hunger=90) would incorrectly show "overwhelming" hunger reactions.

- **Realistic Skill Check System (2d10)** - Replace d20 with 2d10 bell curve for expert reliability
  - New `docs/game-mechanics.md` - Documents all D&D deviations and reasoning
  - **2d10 Bell Curve**: Range 2-20 (same as d20), but with 4x less variance (8.25 vs 33.25)
    - Experts perform consistently; master climber (+8) vs DC 15 now succeeds 88% (was 70%)
  - **Auto-Success (Take 10 Rule)**: If DC ≤ 10 + total_modifier, auto-succeed without rolling
    - Routine tasks for skilled characters don't require dice
  - **Degree of Success**: Margin-based outcome tiers
    - Exceptional (+10), Clear Success (+5-9), Narrow Success (+1-4), Bare Success (0)
    - Partial Failure (-1 to -4), Clear Failure (-5 to -9), Catastrophic (≤-10)
  - **New Critical System**: Double-10 = critical success (1%), Double-1 = critical failure (1%)
  - **Advantage/Disadvantage**: Roll 3d10, keep best/worst 2 (preserves bell curve)
  - **Saving throws use 2d10** for consistency (combat attacks stay d20 for drama)
  - New types: `RollType` enum, `OutcomeTier` enum
  - New functions: `roll_2d10()`, `can_auto_succeed()`, `get_outcome_tier()`
  - Updated `display_skill_check_result()` for auto-success and outcome tier display
  - Updated GM prompt template with new skill check guidance

- **NPC Full Character Generation** - NPCs now receive comprehensive data on first introduction
  - New `src/agents/schemas/npc_generation.py` - Pydantic schemas for structured NPC output:
    - `NPCAppearance`, `NPCBackground`, `NPCSkill`, `NPCInventoryItem`
    - `NPCPreferences`, `NPCInitialNeeds`, `NPCGenerationResult`
  - New `src/services/npc_generator.py` - NPC generation service:
    - `NPCGeneratorService.generate_npc()` - Creates complete NPC from extraction data
    - `_create_entity_with_appearance()`, `_create_npc_extension()`
    - `_create_npc_skills()`, `_create_npc_inventory()`
    - `_create_npc_preferences()`, `_create_npc_needs()`
    - `infer_npc_initial_needs()` - Time/occupation-based need inference
    - `OCCUPATION_SKILLS` and `OCCUPATION_INVENTORY` templates for 15+ occupations
  - New `src/agents/nodes/npc_generator_node.py` - LangGraph node for NPC generation:
    - Runs after entity extractor, before persistence
    - Generates full data for NEW NPCs only (existing entities skipped)
    - Graceful fallback on LLM errors
  - New `data/templates/npc_generator.md` - LLM prompt for NPC data generation
  - Updated `src/agents/state.py`:
    - Added `generated_npcs` field for NPC generation pipeline
    - Added `npc_generator` to `AgentName` type
  - Updated `src/agents/graph.py`:
    - New graph flow: entity_extractor → npc_generator → persistence
  - Updated `src/agents/nodes/persistence_node.py`:
    - Skips entities already generated by npc_generator (no duplicates)

- **Companion NPC Tracking** - Track NPCs traveling with the player
  - New columns in `NPCExtension`:
    - `is_companion: bool` - Whether NPC is traveling with player
    - `companion_since_turn: int` - Turn when NPC joined as companion
  - `EntityManager.set_companion_status()` - Toggle companion status
  - `EntityManager.get_companions()` - List all current companions
  - `NeedsManager.apply_companion_time_decay()` - Apply time-based need decay to all companions
  - Alembic migration `010_add_companion_tracking.py`
  - 18 new tests for NPC generation

### Changed
- **Documentation Overhaul** - Comprehensive update to reflect actual implementation
  - `docs/architecture.md` - Complete rewrite with:
    - Character creation wizard flow (6 sections)
    - Two-tier attribute system (potential vs current stats)
    - Context-aware initialization (needs, vital status, equipment)
    - Skill check system with proficiency tiers
    - Interactive dice rolling mechanics
    - Turn procedure and game loop
    - NPC generator and companion tracking
    - Updated agent architecture diagram
  - `docs/user-guide.md` - Complete rewrite with:
    - Character creation wizard walkthrough
    - Skill check interactive rolling explanation
    - Proficiency tier table
    - Character needs system
    - NPC relationships (7 dimensions)
    - Companion system
    - Navigation and travel
    - Updated commands and troubleshooting

### Added
- **Skill Check System Overhaul** - Proficiency levels now affect skill checks
  - `proficiency_to_modifier()` converts proficiency (1-100) to modifier (+0 to +5)
  - Tier system: Novice → Apprentice → Competent → Expert → Master → Legendary
  - `assess_difficulty()` calculates perceived difficulty from character's perspective
  - `get_difficulty_description()` returns narrative text for player display
  - New `src/dice/skills.py` module with skill-to-attribute mappings
  - Default mappings for 70+ skills (stealth→DEX, persuasion→CHA, etc.)
  - Unknown skills default to Intelligence

- **Interactive Dice Rolling** - Player presses ENTER to roll for skill checks
  - Pre-roll display shows skill name, modifiers, and difficulty assessment
  - Rolling animation with dice faces
  - Post-roll display shows natural roll, total, DC, margin, and outcome
  - Critical success/failure highlighted
  - DC hidden until after roll (revealed in result)

- **GM Skill Check Integration** - GM now uses character proficiency
  - `skill_check` tool requires `entity_key` parameter
  - Executor queries `EntitySkill` for proficiency level
  - Executor queries `EntityAttribute` for governing attribute
  - Optional `attribute_key` parameter for override
  - GM template updated with skill check guidance

- **Character Skills in Context** - GM sees player's skills and attributes
  - `_get_player_attributes()` shows attribute scores (STR 14, DEX 12, etc.)
  - `_get_player_skills()` shows top skills above Novice (swimming (Expert), etc.)
  - Player entity_key included in context

- **Character Memory System** - Track significant memories for emotional scene reactions
  - New `CharacterMemory` model with subject, keywords, valence, emotion, context, intensity
  - `MemoryType` enum: person, item, place, event, creature, concept
  - `EmotionalValence` enum: positive, negative, mixed, neutral
  - Alembic migration `009_add_character_memory.py`
  - `MemoryManager` for CRUD operations, trigger tracking, keyword matching
  - Memory extraction from backstory during character creation (rule-based)
  - `create_character_memory()` factory function for tests

- **Thirst need** - New vital need separate from hunger
  - Added `thirst` column to `CharacterNeeds` (default 80)
  - Added `last_drink_turn` tracking column
  - Decay rates: active=-10, resting=-5, sleeping=-2, combat=-15 (faster than hunger)
  - Satisfaction catalog: sip/drink/large_drink/drink_deeply actions
  - Effects at 20/10/5 thresholds (speed, CON/WIS penalties, death saves)

- **Craving system** - Stimulus-based psychological urgency for needs
  - 5 craving columns: hunger_craving, thirst_craving, energy_craving, social_craving, intimacy_craving
  - Formula: `effective_need = max(0, need_value - craving_value)`
  - Cravings boost when seeing relevant stimuli (capped at 50)
  - Cravings decay -20 per 30 minutes when stimulus removed
  - Cravings reset on need satisfaction

- **SceneInterpreter service** - Analyze scenes for character-relevant reactions
  - Detects need stimuli (food → hunger craving, water → thirst craving)
  - Detects memory triggers with emotional effects (grief, nostalgia, fear)
  - Detects professional interests (fisherman notices quality rod)
  - Returns `SceneReaction` objects with narrative hints for GM

- **MemoryExtractor service** - Create memories from backstory and gameplay
  - Async LLM-based extraction with structured prompts
  - Sync rule-based fallback for offline/testing
  - Backstory extraction during character creation
  - Gameplay extraction after significant events

- **Context-aware need initialization** - Starting values based on backstory
  - `_infer_initial_needs()` analyzes backstory for context clues
  - Hardship words → lower comfort/morale/hunger/hygiene
  - Isolation words → lower social connection
  - Purpose words → higher sense of purpose
  - Age and occupation adjustments
  - Starting scene affects needs (wet→hygiene, cold→comfort, dirty→hygiene)

- **Context-aware vital status** - Health based on backstory
  - `_infer_initial_vital_status()` detects injury/illness keywords
  - Wounded/injured/sick/poisoned backstories start as WOUNDED
  - Healthy backstories remain HEALTHY

- **Context-aware equipment** - Condition and selection based on context
  - `_infer_equipment_condition()` sets item condition from backstory
  - Wealthy/noble → PRISTINE, escaped/refugee → WORN, disaster/battle → DAMAGED
  - `_infer_starting_situation()` filters equipment by situation
  - Swimming/prisoner/captive → minimal equipment, no armor
  - Prisoner/monk/pacifist → no weapons

- **Vital need death checks** - Scaling death save frequency
  - `check_vital_needs()` method with priority: thirst → hunger → energy
  - Need < 5: hourly checks, < 3: every 30min, = 0: every turn
  - Returns death save requirements for world simulator

- **Probability-based accumulation** - Non-vital need effects
  - `check_accumulation_effects()` for daily probability rolls
  - Formula: `daily_chance = (100 - need_value) / 4`
  - Effects: illness (hygiene), depression (social), etc.

- **GM Tools** - New and updated tools for the Game Master LLM
  - Added `thirst` to `satisfy_need` tool enum
  - New `apply_stimulus` tool for scene-triggered cravings
    - Stimulus types: food_sight, drink_sight, rest_opportunity, social_atmosphere, intimacy_trigger, memory_trigger
    - Intensity levels: mild, moderate, strong
    - Memory emotion parameter for morale effects

- **Comprehensive test coverage** - Tests for Character Needs System Enhancement (97 new tests)
  - `test_character_memory.py` - CharacterMemory model tests (11 tests)
  - `test_memory_manager.py` - MemoryManager CRUD, matching, trigger tracking tests (20 tests)
  - `test_scene_interpreter.py` - SceneInterpreter need stimuli, memory triggers, professional interest tests (29 tests)
  - `test_character_needs_init.py` - Context-aware initialization tests (37 tests)

- **Character creation wizard** - Structured wizard replacing free-form conversational creation
  - Menu-based navigation with 6 sections: Name & Species, Appearance, Background, Personality, Attributes, Review
  - Section-scoped conversation history prevents AI forgetting facts between sections
  - Explicit `section_complete` JSON signals eliminate endless loops
  - `--wizard/--conversational` flag on `rpg game start` (wizard is default)
  - Two-tier attribute system:
    - Hidden potential stats (rolled 4d6-drop-lowest, stored but never shown to player)
    - Visible current stats calculated from: `Potential + Age Modifier + Occupation Modifier + Lifestyle`
    - Natural "twist" narratives when dice rolls conflict with occupation expectations
  - `src/services/attribute_calculator.py` - Attribute calculation service:
    - `roll_potential_stats()` - Roll hidden potential with 4d6-drop-lowest
    - `calculate_current_stats()` - Apply age/occupation/lifestyle modifiers
    - `get_twist_narrative()` - Generate narrative explanations for stat anomalies
    - Age brackets: Child, Adolescent, Young Adult, Experienced, Middle Age, Elderly
    - Occupation modifiers for 13 professions (farmer, blacksmith, scholar, soldier, etc.)
    - Lifestyle modifiers (malnourished, sedentary, hardship, privileged_education, etc.)
  - New Entity model columns: `potential_strength`, `potential_dexterity`, `potential_constitution`,
    `potential_intelligence`, `potential_wisdom`, `potential_charisma`, `occupation`, `occupation_years`
  - Alembic migration `006_add_potential_stats.py` for new columns
  - `WizardSectionName` enum, `WizardSection` and `CharacterWizardState` dataclasses
  - Wizard prompt templates in `data/templates/wizard/`:
    - `wizard_name.md`, `wizard_appearance.md`, `wizard_background.md`,
      `wizard_personality.md`, `wizard_attributes.md`
  - New display functions: `display_character_wizard_menu()`, `prompt_wizard_section_choice()`,
    `display_section_header()`, `display_section_complete()`, `display_character_review()`,
    `prompt_review_confirmation()`
  - `_wizard_character_creation_async()` main wizard loop
  - `_run_section_conversation()` section handler with max turn limits
  - `_create_character_records()` updated to persist potential stats and occupation

- **Game management commands** - Complete game lifecycle from `rpg game`
  - `rpg game list` - List all games with player character names
  - `rpg game delete` - Delete a game with confirmation
  - `rpg game start` - Unified wizard (already added)
  - `rpg game play` - Continue/start game loop (already existed)

- **Unified game start wizard** (`rpg game start`) - One-command setup for new games
  - Combines session creation, character creation, and game start into seamless wizard
  - Interactive setting selection menu (fantasy, contemporary, scifi)
  - Session name prompt with sensible defaults
  - AI-guided character creation with hybrid attribute handling:
    - Player can choose AI-suggested attributes based on character concept
    - Or switch to manual point-buy mid-conversation
  - Automatic world extraction and skill inference after character creation
  - Graceful cancellation (no DB changes until character confirmed)
  - Deprecation hints on `rpg session start` and `rpg character create`
  - New display helpers: `display_game_wizard_welcome()`, `prompt_setting_choice()`, `prompt_session_name()`
  - New parsing function: `_parse_point_buy_switch()` for attribute choice handling
  - Updated `character_creator.md` template with attribute choice instructions

### Removed
- **IntimacyProfile table** - Removed duplicate table superseded by `CharacterPreferences`
  - `IntimacyProfile` model removed from `src/database/models/character_state.py`
  - `_create_intimacy_profile()` replaced with `_create_character_preferences()`
  - `NeedsManager.get_intimacy_profile()` replaced with `get_preferences()`
  - Alembic migration `007_remove_intimacy_profiles.py` drops the `intimacy_profiles` table
  - All intimacy settings now consolidated in `CharacterPreferences` table

### Deprecated
- **Session commands** - All `rpg session` commands now show deprecation warnings
  - `rpg session start` → use `rpg game start`
  - `rpg session list` → use `rpg game list`
  - `rpg session load` → use `rpg game list`
  - `rpg session delete` → use `rpg game delete`
  - `rpg session continue` → use `rpg game play`
- **Character create** - `rpg character create` → use `rpg game start`

### Added (continued)
- **World map navigation system (Phases 1-7)** - Complete zone-based terrain for open world exploration
  - `src/database/models/navigation.py` - 8 new models for navigation system:
    - `TerrainZone` - explorable terrain segments (forests, roads, lakes, etc.)
    - `ZoneConnection` - adjacencies between zones with direction, passability
    - `LocationZonePlacement` - links locations to zones with visibility settings
    - `TransportMode` - travel methods with terrain cost multipliers
    - `ZoneDiscovery` / `LocationDiscovery` - fog of war (session-scoped)
    - `MapItem` - physical maps that reveal locations when viewed
    - `DigitalMapAccess` - modern/sci-fi digital map services
  - New enums: `TerrainType` (14 types), `ConnectionType` (8 types), `TransportType` (9 types), `MapType`, `VisibilityRange`, `EncounterFrequency`, `DiscoveryMethod`, `PlacementType`
  - `src/managers/zone_manager.py` - terrain zone operations:
    - Zone CRUD: `get_zone()`, `create_zone()`, `get_all_zones()`
    - Connections: `connect_zones()`, `get_adjacent_zones()`, `get_adjacent_zones_with_directions()`
    - Location placement: `place_location_in_zone()`, `get_zone_locations()`, `get_location_zone()`
    - Terrain costs: `get_terrain_cost()` with transport mode multipliers
    - Accessibility: `check_accessibility()` with skill requirements
    - Visibility: `get_visible_from_zone()`, `get_visible_locations_from_zone()`
    - Transport: `get_transport_mode()`, `get_available_transport_modes()`
  - `src/managers/pathfinding_manager.py` - A* pathfinding algorithm:
    - `find_optimal_path()` with weighted A* considering terrain costs
    - `find_path_via()` for routing through waypoints
    - `get_route_summary()` for terrain breakdown and hazard identification
    - Support for route preferences (avoid terrain types, prefer roads)
    - Transport mode cost multipliers (mounted faster on roads, impassable in forests)
    - Bidirectional and one-way connection handling
  - `src/managers/travel_manager.py` - journey simulation:
    - `start_journey()` initializes route with pathfinding
    - `advance_travel()` moves through zones with encounter rolls
    - `interrupt_travel()` / `resume_journey()` for mid-journey stops
    - `detour_to_zone()` for exploring adjacent zones off-path
    - Skill check detection for hazardous terrain
    - `JourneyState` dataclass for tracking progress
  - `src/managers/discovery_manager.py` - fog of war system:
    - `discover_zone()` / `discover_location()` with method tracking
    - `view_map()` for batch discovery from map items
    - `auto_discover_surroundings()` on zone entry
    - `check_digital_access()` for modern/sci-fi settings
    - `get_known_zones()` / `get_known_locations()` with filtering
    - Source tracking (NPC, map, visible from zone)
  - `src/managers/map_manager.py` - map item operations:
    - `create_map_item()` with zone/location reveal lists
    - `get_map_item()`, `is_map_item()`, `get_all_maps()`
    - `get_map_zones()`, `get_map_locations()` for querying contents
    - `setup_digital_access()`, `setup_digital_access_for_setting()`
    - `toggle_digital_access()` for enabling/disabling services
    - Setting-based digital map configs (contemporary, scifi, cyberpunk, fantasy)
  - `src/managers/context_compiler.py` - navigation context for GM:
    - `_get_navigation_context()` method for current zone and adjacencies
    - Filters to only show discovered zones/locations
    - Terrain hazard warnings and skill requirements
    - `SceneContext.navigation_context` field added
  - `src/agents/tools/gm_tools.py` - 6 new navigation tools:
    - `check_route` - pathfinding with travel time estimates
    - `start_travel` - begin simulated journeys
    - `move_to_zone` - immediate adjacent zone movement
    - `check_terrain` - terrain accessibility checks
    - `discover_zone` / `discover_location` - fog of war updates
  - `src/agents/tools/executor.py` - navigation tool handlers:
    - Route checking with discovery validation
    - Travel initiation with TravelManager integration
    - Zone movement with auto-discovery
    - Terrain accessibility with skill requirements
  - `data/templates/game_master.md` - navigation rules added:
    - Guidelines for known location references
    - Travel tool usage instructions
    - Time estimates for different journey lengths
  - `src/cli/commands/world.py` - new zone CLI commands:
    - `world zones` - list terrain zones (discovered or all)
    - `world create-zone` - create new terrain zone with terrain type and cost
    - `world connect-zones` - connect zones with direction and crossing time
    - `world place-location` - place location in a zone
    - `world zone-info` - show detailed zone information with adjacencies
    - `world discovered` - show all discovered zones and locations
  - Alembic migration `005_add_navigation_system.py` with seeded transport modes
  - 162 new tests (49 model, 32 zone, 20 pathfinding, 19 travel, 20 discovery, 14 map, 8 context)

- **LLM audit logging to filesystem** - Log all LLM prompts and responses for debugging
  - `src/llm/audit_logger.py` - Core logging infrastructure
    - `LLMAuditContext` dataclass: session_id, turn_number, call_type
    - `LLMAuditEntry` dataclass: full request/response data
    - `LLMAuditLogger` class: async file writing, markdown formatting
    - `set_audit_context()` / `get_audit_context()` context variable functions
    - `get_audit_logger()` factory with configurable log directory
  - `src/llm/logging_provider.py` - Wrapper provider that logs all calls
    - `LoggingProvider` wraps any `LLMProvider` and delegates + logs
    - Captures timing, all messages, tool calls, responses
    - Logs to markdown files for human readability
  - Log file structure: `logs/llm/session_{id}/turn_XXX_timestamp_calltype.md`
  - Orphan calls (no session): `logs/llm/orphan/timestamp_calltype.md`
  - Enable with `LOG_LLM_CALLS=true` in environment
  - `llm_log_dir` config setting (default: `logs/llm`)
  - 35 new tests for audit logging functionality

### Fixed
- **GM no longer re-introduces character every turn** - Added turn context to scene context
  - `ContextCompiler._get_turn_context()` provides turn number and recent history
  - First turn explicitly marked as "FIRST TURN. Introduce the player character."
  - Continuation turns marked as "CONTINUATION. Do NOT re-introduce the character."
  - Recent 3 turns of history included with smart truncation:
    - Most recent turn: up to 1000 chars (captures full dialogue/NPC names)
    - Older turns: up to 400 chars (for context efficiency)
  - Updated GM template with clear Turn Handling section
  - Context compiler node now passes `turn_number` from state
- **Character name extraction from conversation history** - Dead code now used
  - `_extract_name_from_history()` was defined but never called
  - Now used as fallback when AI mentions a name (e.g., "Finn is a...") but forgets to output JSON
  - Fixes issue where AI would ask for character name even though it had been discussed

### Changed
- **Normalized need semantics** - All needs now follow consistent 0=bad, 100=good pattern
  - Renamed `fatigue` → `energy` (0=exhausted, 100=energized)
  - Renamed `pain` → `wellness` (0=agony, 100=pain-free)
  - Inverted `intimacy` meaning (0=desperate, 100=content)
  - Updated NeedsManager decay rates, satisfaction logic, and effect thresholds
  - Updated display.py with consistent color coding (low=red, high=green)
  - Updated InjuryManager to sync pain→wellness (wellness = 100 - total_pain)
  - Alembic migration `004_normalize_need_semantics.py` for column renames and value inversion

### Added
- **Structured AI character creation with field tracking** - Complete redesign of character creation
  - `CharacterCreationState` dataclass tracks all required fields across 5 groups:
    - Name, Attributes, Appearance, Background, Personality
  - `hidden_backstory` field on Entity for secret GM content
  - AI parses `field_updates` JSON to populate state incrementally
  - AI parses `hidden_content` JSON for secret backstory elements
  - Delegation support ("make this up", "you decide") for AI-generated values
  - Character summary display before confirmation
  - AI inference system for gameplay-relevant fields:
    - `_infer_gameplay_fields()` analyzes background/personality
    - Creates `EntitySkill` records from inferred skills
    - Creates `CharacterPreferences` record with inferred traits
    - Creates `NeedModifier` records for trait-based modifiers
  - New prompt templates:
    - `data/templates/character_creator.md` - Field-based character creation
    - `data/templates/character_inference.md` - Gameplay field inference
  - Alembic migration `543ae419033d_add_hidden_backstory_to_entities.py`
  - 18 new tests for CharacterCreationState, field parsing, and application

- **Character preferences and need modifiers system** - Comprehensive preference tracking
  - `CharacterPreferences` model replacing narrow `IntimacyProfile`
    - Food preferences: favorite_foods, disliked_foods, is_vegetarian, is_vegan, food_allergies
    - Food traits: is_greedy_eater, is_picky_eater
    - Drink preferences: favorite_drinks, alcohol_tolerance, is_alcoholic, is_teetotaler
    - Intimacy preferences: migrated from IntimacyProfile (drive_level, intimacy_style, etc.)
    - Social preferences: social_tendency, preferred_group_size, is_social_butterfly, is_loner
    - Stamina traits: has_high_stamina, has_low_stamina, is_insomniac, is_heavy_sleeper
    - Flexible JSON extra_preferences for setting-specific data
  - `NeedModifier` model for per-entity need decay/satisfaction modifiers
    - Supports trait-based, age-based, adaptation, and custom modifiers
    - decay_rate_multiplier, satisfaction_multiplier, max_intensity_cap
    - Unique constraint on (entity_id, need_name, modifier_source, source_detail)
  - `NeedAdaptation` model for tracking need baseline changes over time
    - adaptation_delta, reason, trigger_event
    - is_gradual, duration_days, is_reversible, reversal_trigger
  - New enums: AlcoholTolerance, SocialTendency, ModifierSource
  - Age curve settings in fantasy.json for age-based modifiers
    - AsymmetricDistribution dataclass for two-stage normal distribution
    - NeedAgeCurve for per-need age curves (intimacy peaks at 18, etc.)
    - TraitEffect for trait-based modifier mappings
  - Alembic migration `003_add_character_preferences.py`
  - `PreferencesManager` for managing character preferences
    - CRUD operations for `CharacterPreferences`
    - Trait flag management with automatic modifier syncing
    - Age-based modifier generation using two-stage normal distribution
    - `calculate_age_modifier()` for asymmetric distribution calculation
    - `generate_individual_variance()` for per-character variance
    - `sync_trait_modifiers()` to sync trait flags to NeedModifier records
  - `NeedsManager` modifier-aware methods
    - `get_decay_multiplier()` - combined decay rate from all active modifiers
    - `get_satisfaction_multiplier()` - combined satisfaction rate from modifiers
    - `get_max_intensity()` - lowest intensity cap from age/trait modifiers
    - `get_total_adaptation()` - sum of adaptation deltas for a need
    - `create_adaptation()` - create adaptation record for need baseline changes
    - `apply_time_decay()` now uses decay multipliers and max intensity caps
  - 71 new tests for preferences manager and needs manager modifiers
- **Rich character appearance system** - Dedicated columns for media generation
  - 12 new appearance columns: age, age_apparent, gender, height, build, hair_color, hair_style, eye_color, skin_tone, species, distinguishing_features, voice_description
  - `Entity.APPEARANCE_FIELDS` constant for iteration
  - `Entity.set_appearance_field()` method with JSON sync
  - `Entity.sync_appearance_to_json()` for bulk updates
  - `Entity.get_appearance_summary()` for readable descriptions
  - Alembic migration `002_add_appearance_columns.py`
- **Shadow Entity pattern** - Backstory NPCs tracked before first appearance
  - `EntityManager.create_shadow_entity()` - Creates inactive entity from backstory
  - `EntityManager.activate_shadow_entity()` - Activates on first appearance with locked appearance
  - `EntityManager.get_shadow_entities()` - List all shadow entities
  - `EntityManager.get_or_create_entity()` - Idempotent entity creation
- **World extraction from character creation** - Automatic backstory persistence
  - `data/templates/world_extraction.md` - LLM prompt for extracting entities, locations, relationships
  - `_extract_world_data()` async function in character.py
  - `_create_world_from_extraction()` creates shadow entities and relationships
  - Bidirectional relationships between player and backstory NPCs
- **Appearance query methods** in EntityManager
  - `update_appearance()` - Update multiple appearance fields with sync
  - `get_entities_by_appearance()` - Query entities by appearance criteria
  - `get_appearance_summary()` - Get readable appearance for entity
- **Intimacy profile defaults** - Silent creation during character creation
  - `_create_intimacy_profile()` function with MODERATE drive, EMOTIONAL style defaults
  - Created automatically on character creation
- **Comprehensive CLI test coverage** - 64 new tests for previously untested areas
  - `tests/test_config.py` - Config validation tests (15 tests)
  - `tests/test_cli/test_session_commands.py` - Session CLI tests (12 tests)
  - `tests/test_cli/test_character_commands.py` - Character CLI tests (11 tests)
  - `tests/test_cli/test_ai_character_creation.py` - AI creation tests (19 tests)
  - `tests/test_e2e/test_game_flow.py` - End-to-end smoke tests (7 tests)
- **First-turn character introduction** - Game now introduces the player character at start
  - ContextCompiler includes player equipment in scene context
  - `_get_equipment_description()` method in ContextCompiler
  - `_format_appearance()` now includes age if set
  - GM template includes first-turn instructions for character introduction
  - Initial scene prompt requests character introduction with appearance, clothing, and feelings
- **Starting equipment** - Characters now receive starting equipment on creation
  - `StartingItem` dataclass in `src/schemas/settings.py`
  - Starting equipment definitions in all setting JSON files
  - `_create_starting_equipment()` function in character.py
  - Equipment displayed after character creation
- **Enhanced Rich tables** - Improved display formatting
  - Enhanced `display_character_status()` with proper Rich tables
  - Enhanced `display_inventory()` with slot, condition columns
  - New `display_equipment()` function with layer visualization
  - Color-coded condition display (pristine/good/worn/damaged/broken)
- **Progress indicators** - Rich progress spinners for loading
  - `progress_spinner()` context manager for async operations
  - `progress_bar()` context manager for multi-step operations
  - `_create_progress_bar()` returns styled Rich Text objects
  - Game loop now uses progress spinners instead of status
- **API reference documentation** - `docs/api-reference.md`
  - Complete manager API documentation
  - LLM module reference
  - Dice system reference
  - Agent nodes reference
- **Setting templates** - JSON configuration files for game settings
  - `data/settings/fantasy.json` - D&D-style fantasy with 6 attributes
  - `data/settings/contemporary.json` - Modern setting with 6 attributes
  - `data/settings/scifi.json` - Sci-fi setting with 6 attributes
  - JSON loader in `src/schemas/settings.py` - `load_setting_from_json()`
  - `EquipmentSlot` dataclass for per-setting equipment definitions
- **Prompt templates** - LLM prompt templates for agents
  - `data/templates/world_simulator.md` - World simulation narration
  - `data/templates/combat_resolver.md` - Combat narration
  - `data/templates/character_creator.md` - AI character creation assistant
- **Agent tools** - Tool definitions for LLM function calling
  - `src/agents/tools/extraction_tools.py` - Entity/fact/item extraction tools
  - `src/agents/tools/combat_tools.py` - Combat resolution tools
  - `src/agents/tools/world_tools.py` - World simulation tools
- **AI character creation** - Conversational character creation with LLM
  - `--ai` flag for `rpg character create` command
  - AI suggests attributes based on character concept
  - Validates suggestions against point-buy rules
  - Display helpers in `src/cli/display.py`
- Mandatory documentation requirements in CLAUDE.md
- 32 new tests for starting equipment and display functions (1226 total)
- **Enhanced body slot system** - Granular equipment slots matching story-learning
  - 26 base body slots including individual finger slots (10), ear slots, feet_socks/feet_shoes
  - `BODY_SLOTS` constant with max_layers and descriptions
  - `BONUS_SLOTS` for dynamic slots (pockets, belt pouches, backpack compartments)
  - `SLOT_COVERS` system - full_body covers torso and legs
  - `ItemManager.get_available_slots()` - Returns base + bonus slots for entity
  - `ItemManager.get_outfit_by_slot()` - Groups equipped items by slot
  - `ItemManager.get_visible_by_slot()` - Gets only visible items per slot
  - `ItemManager.format_outfit_description()` - Human-readable outfit for GM context
  - Updated `ItemManager.update_visibility()` with covering system
- **Outfit CLI command** - `rpg character outfit` shows layered clothing
  - Groups items by body slot with layer display
  - Shows hidden items (dimmed) vs visible items
  - Displays bonus slots provided by items
  - Visible items summary at bottom
- **Updated setting JSON files** with new equipment slots
  - All settings now have 26+ base slots
  - Added `bonus_slots` section for dynamic slots
  - Starting equipment uses new slots (feet_shoes, belt pouches, etc.)
  - Items can now have `provides_slots` array

### Changed
- Game loop uses `progress_spinner` instead of `console.status()`
- `display_character_status()` now uses Rich Table instead of Panel

### Fixed
- **AI character creation JSON hidden from users** - JSON blocks no longer shown in dialogue
  - Added `_strip_json_blocks()` function to remove `suggested_attributes` and `character_complete` JSON
  - Users now see clean conversational text without machine-readable markup
- **AI character creation preserves mystery** - No more spoilers about hidden character aspects
  - Added "Character Creation Philosophy" section to template
  - AI only reveals what the character knows about themselves
  - Secret backstory elements (hidden powers, mysterious origins) are created but never mentioned
- **AI character creation asks for confirmation** - Final check before completing
  - Added "Before Completing Character" section to template
  - AI now asks "Is there anything else you'd like to add or change?" before finishing
  - Gives players a chance to tweak details before committing
- **AI character creation "surprise me" behavior** - AI now respects user delegation phrases
  - Added "Detecting User Delegation" section to `character_creator.md` template
  - Handles full delegation ("surprise me", "it's up to you", "dealer's choice")
  - Handles partial delegation ("I like Eldrin, you decide the rest")
  - AI now generates complete character immediately instead of asking more questions
- **Play without character prompts for creation** - `rpg play` no longer silently creates empty character
  - Now prompts "Create a character now? (y/n)" when no character exists
  - If yes, launches AI-assisted character creation
  - If no, exits with helpful message to use `rpg character create`
  - Removed `_get_or_create_player` in favor of `_get_player` (no silent creation)
- **Async AI character creation** - `_ai_character_creation()` now properly awaits async LLM calls
  - Added wrapper function with `asyncio.run()` to call async `_ai_character_creation_async()`
- **Invalid model name** - Fixed `cheap_model` from `claude-haiku-3` to `claude-3-5-haiku-20241022`
- **SQLite foreign key enforcement** - `get_db_session()` now enables `PRAGMA foreign_keys=ON`
- **Character status command** - Fixed iteration over `player.attributes` relationship
  - Was calling `.items()` on SQLAlchemy relationship list, now iterates properly
- **NeedsManager method name** - Fixed `get_needs_state()` to `get_needs()` in status command
- `is_equipped` bug in character.py - was referencing non-existent field
  - Now correctly uses `body_slot is not None` to check equipped status
  - Fixed both inventory and equipment commands

### Also Changed
- Updated `docs/implementation-plan.md` to reflect actual implementation status
- Updated test count in CLAUDE.md (1121 tests, not 500)
- Extended `SettingSchema` with `description`, `equipment_slots`, and `starting_equipment` fields
- Extended `AttributeDefinition` with `description` field

## [0.1.0] - 2025-12-06

### Added

#### Core Managers (15 total)
- **EntityManager** - Entity CRUD, attributes, skills, location queries, `get_active_entities()`
- **ItemManager** - Items, inventory, equipment (body slots/layers), visibility, `get_items_at_location()`
- **LocationManager** - Location hierarchy, visits, state, accessibility, `set_player_location()`
- **RelationshipManager** - Attitudes (trust, liking, respect), personality modifiers, mood
- **FactManager** - SPV fact store, secrets, foreshadowing, `contradict_fact()`
- **ScheduleManager** - NPC schedules, time-based activities, `copy_schedule()`
- **EventManager** - World events, processing status, `get_events_involving()`
- **TaskManager** - Tasks, appointments, quests, `fail_task()`, `mark_appointment_kept/missed()`
- **TimeManager** - In-game time, day/night, weather
- **NeedsManager** - Hunger, fatigue, hygiene, pain, morale, intimacy decay
- **InjuryManager** - Body injuries, recovery, activity restrictions
- **DeathManager** - Vital status, death saves, revival mechanics
- **GriefManager** - Kübler-Ross grief stages
- **ConsistencyValidator** - Temporal/spatial/possession consistency checks
- **ContextCompiler** - Scene context aggregation for LLM

#### Database Models
- **Session models** - GameSession, Turn (immutable history)
- **Entity models** - Entity, EntityAttribute, EntitySkill, NPCExtension, MonsterExtension
- **Item models** - Item, StorageLocation (owner vs holder pattern)
- **Relationship models** - Relationship (7 dimensions), RelationshipChange (audit log)
- **World models** - Location, Schedule, TimeState, Fact (SPV), WorldEvent
- **Task models** - Task, Appointment, Quest, QuestStage
- **Character state** - CharacterNeeds, IntimacyProfile
- **Vital state** - EntityVitalState (death saves, revival tracking)
- **Injury models** - BodyInjury, ActivityRestriction
- **Mental state** - MentalCondition, GriefCondition

#### LLM Integration
- **AnthropicProvider** - Claude API integration with tool use
- **OpenAIProvider** - OpenAI API with configurable base_url (DeepSeek, Ollama compatible)
- **LLM abstraction** - Provider protocol, message types, retry logic

#### LangGraph Agents
- **Agent graph** - 6-node LangGraph workflow
- **GameMaster node** - Narrative generation with GM tools
- **EntityExtractor node** - Parse responses, extract entities/facts
- **WorldSimulator node** - NPC schedules, need decay, time advancement
- **ContextCompiler node** - Scene context for LLM
- **CombatResolver node** - Initiative, attacks, damage
- **Persistence node** - State persistence

#### Dice System
- **Parser** - Dice notation parsing (1d20, 2d6+3, etc.)
- **Roller** - Roll with modifiers, advantage/disadvantage
- **Checks** - Skill checks, saving throws, DC system
- **Combat** - Attack rolls, damage calculation, initiative

#### CLI
- **game** command - Main game loop
- **session** commands - start, continue, list, load
- **character** commands - status, inventory, equipment
- **world** commands - locations, npcs, time

#### Testing
- 1121 tests total (~3 seconds runtime)
- Test factories for all models
- TDD approach enforced

#### Documentation
- Project architecture (`docs/architecture.md`)
- Implementation plan (`docs/implementation-plan.md`)
- User guide (`docs/user-guide.md`)
- Coding standards (`.claude/docs/coding-standards.md`)
- Database conventions (`.claude/docs/database-conventions.md`)

### Technical Details
- Python 3.11+
- SQLAlchemy 2.0+ with async support
- PostgreSQL database
- Alembic migrations
- Typer + Rich CLI
- Session-scoped queries (multi-session isolation)
- Body slot + layer system for clothing
- Owner vs holder pattern for items
