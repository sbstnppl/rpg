# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
