# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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

### Changed
- Game loop uses `progress_spinner` instead of `console.status()`
- `display_character_status()` now uses Rich Table instead of Panel

### Fixed
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
