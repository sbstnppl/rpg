# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
