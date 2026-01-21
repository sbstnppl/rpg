# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Millbrook World Generation for Finn's Journey** - Complete world content for medieval fantasy setting
  - New `data/worlds/millbrook.yaml` with 9 terrain zones and 18+ locations
  - New `data/worlds/millbrook_npcs.json` with 7 NPCs (Old Aldric, Sister Maren, The Hermit, Master Corin, Henrik, Widow Brennan, Tom)
  - New `data/worlds/millbrook_schedules.json` with daily schedules for all NPCs
  - New `data/worlds/millbrook_items.json` with 6 items including 4 Starbound artifacts
  - New `data/worlds/millbrook_facts.json` with 20+ world facts (public legends, secret truths, omens)
  - Extended `src/schemas/world_template.py` with NPCTemplate, ScheduleTemplate, ItemTemplate, FactTemplate
  - New `src/services/world_loader_extended.py` for loading complete worlds
  - New `rpg world load <world_name>` CLI command (`src/cli/commands/world.py`)
  - 14 unit tests (`tests/test_services/test_world_loader_extended.py`)
  - 26 integration tests (`tests/test_integration/test_millbrook_world.py`)

- **Context-Aware Location Resolution** - LLM picks destination using conversation context, then validates
  - New `candidate_locations` field in `GroundingManifest` for non-exit locations (`src/gm/grounding.py`)
  - New `_get_candidate_locations()` method finds locations matching destination text (`src/gm/context_builder.py`)
  - New `destination_hint` parameter for `build_grounding_manifest()` to populate candidates
  - Recent events now included in branch generation prompt for discourse reference (`src/world_server/quantum/branch_generator.py`)
  - Validation accepts candidate_locations as valid destinations (`src/world_server/quantum/delta_postprocessor.py`)
  - Fuzzy matching suggestions in validation error messages (`src/world_server/quantum/validation.py`)
  - 14 new tests for candidate locations functionality (`tests/test_gm/test_grounding.py`, `tests/test_gm/test_context_builder.py`)

- **OOC Handler for Out-of-Character Queries** - Routes OOC queries to game state instead of placeholder
  - New `OOCHandler` class with keyword-based query classification (`src/world_server/quantum/ooc_handler.py`)
  - Fast-path handlers for exits, time, inventory, location, NPCs, stats, and help
  - LLM fallback for unrecognized queries with GM-style answers
  - 24 unit tests (`tests/test_world_server/test_quantum/test_ooc_handler.py`)

- **QwenAgentProvider Unit Tests** - Complete test coverage for Qwen3 tool calling provider
  - 50 unit tests covering initialization, message conversion, tool parsing, and error handling (`tests/test_llm/test_qwen_agent_provider.py`)
  - Tests for thinking block stripping, JSON tool call extraction, and structured output
  - Mocked qwen-agent integration tests for skill checks, attack rolls, and entity creation

- **Issue Verification Tracking System** - Track play-test verifications before archiving issues
  - New `/tackle verify <issue-name>` subcommand for recording verification results (`.claude/commands/tackle.md`)
  - New "Awaiting Verification" and "Verified" status values for issue lifecycle
  - Configurable verification threshold (default: 3 successful play-tests)
  - Auto-archive to `docs/issues/archived/` when threshold reached
  - `/play-test` integration: scans for pending verifications at start, prompts after session (`.claude/commands/play-test.md`)
  - New `**Verification:** 0/3` and `**Last Verified:** -` fields in issue template (`.claude/commands/issue.md`)

- **Delta Post-Processor with LLM Clarification** - Repairs common LLM errors in state deltas
  - New `DeltaPostProcessor` class with 740 lines of validation and repair logic (`src/world_server/quantum/delta_postprocessor.py`)
  - Async `process_async()` for LLM clarification when entity keys are ambiguous
  - Fuzzy key matching using `difflib.SequenceMatcher` to suggest corrections
  - Auto-injects `CREATE_ENTITY` for missing item parents (e.g., items in containers)
  - Detects conflicts (CREATE+DELETE same entity, duplicate creates, negative time)
  - Clamps out-of-range values and reorders deltas for consistency
  - 76 unit tests covering all repair scenarios (`tests/test_world_server/test_quantum/test_delta_postprocessor.py`)

- **Ref-Based Quantum Pipeline Architecture** - Deterministic entity resolution using single-letter refs
  - New `RefManifest` class assigns A/B/C refs to entities, eliminates fuzzy matching (`src/world_server/quantum/ref_manifest.py`)
  - New `RefDeltaTranslator` with direct ref→key lookup, invalid refs produce errors (`src/world_server/quantum/delta_translator.py`)
  - New `RefReasoningContext` and `reason_with_refs()` for ref-based reasoning (`src/world_server/quantum/reasoning.py`)
  - New `NarratorEngine` with grounding-aware prose generation (`src/world_server/quantum/narrator.py`)
  - New `cleanup_narrative()` for post-processing narrative output (`src/world_server/quantum/cleanup.py`)
  - New `IntentClassifier` for Phase 1 action classification (`src/world_server/quantum/intent_classifier.py`)
  - CLI `--ref-based` flag for `game turn` and `play` commands (`src/cli/commands/game.py`)
  - Audit logging for ref-based pipeline path (`src/world_server/quantum/pipeline.py`)

- **Split Architecture for Quantum Pipeline** - Separates reasoning from narration
  - Phase 1: Intent classification (LLM determines action type)
  - Phase 2: Semantic reasoning (LLM outputs what happens)
  - Phase 3: Delta translation (code resolves refs to keys)
  - Phase 4: Narration (LLM generates prose)
  - Phase 5: Cleanup (code normalizes output)

### Fixed
- **Branch Entity Key Collision Prevention** - Branch generator no longer creates duplicate entity keys
  - Added `_get_all_session_keys()` method to query ALL entity/item keys from session (`src/gm/context_builder.py`)
  - Manifest's `additional_valid_keys` now populated with session-wide keys, not just mid-turn ones
  - Added entity key uniqueness guidance to branch generator system prompt (`src/world_server/quantum/branch_generator.py`)
  - Added `session_id` field to `GroundingManifest` for debugging (`src/gm/grounding.py`)
  - 6 new tests in `TestSessionEntityKeyInclusion` class (`tests/test_gm/test_context_builder.py`)

- **Branch Regeneration for Unknown Location Destinations** - Graceful handling when LLM hallucinates locations
  - Added position vs location guidance to branch generator prompt (`src/world_server/quantum/branch_generator.py`)
  - New `_remove_invalid_location_deltas()` method removes invalid `UPDATE_LOCATION` deltas gracefully instead of failing (`src/world_server/quantum/delta_postprocessor.py`)
  - Fixes "sneak behind the bar" causing `UPDATE_LOCATION` to hallucinated `tavern_cellar`
  - 9 new tests for removal behavior and prompt content (`tests/test_world_server/test_quantum/`)

- **QwenAgentProvider Structured Output** - Fixed response type handling in `complete_structured` method
  - Now properly handles dict, list, and string responses from qwen-agent (`src/llm/qwen_agent_provider.py`)
  - Matches response handling in `complete` and `complete_with_tools` methods

- **Need-Satisfying Actions Generate Deltas** - LLM now generates `update_need` deltas for activities like eating, drinking, and socializing
  - Added INVARIANT FOR NEED-SATISFYING ACTIONS to branch generator with activity-to-need mapping table (`src/world_server/quantum/branch_generator.py`)
  - Added `social_connection` to valid needs in validation and postprocessor (`src/world_server/quantum/validation.py`, `src/world_server/quantum/delta_postprocessor.py`)
  - Fixes state desync where narrative describes eating/drinking but need stats don't change

- **Narrator Key Format Compliance** - Added validation-based retry loop for [key:text] format enforcement
  - Added `_build_validation_manifest()` and `_validate_narrative()` methods (`src/world_server/quantum/narrator.py`)
  - Retry loop with error feedback (max 3 attempts) before fallback
  - Lowered temperature from 0.7 to 0.5 for better format compliance
  - 9 new tests for validation and retry behavior (`tests/test_world_server/test_quantum/test_narrator.py`)

- **Skill Checks Not Triggering** - Skill actions like sneaking and climbing now correctly trigger dice rolls
  - Expanded `skill_use` guidance in intent classifier with 15+ explicit examples (`src/world_server/quantum/intent_classifier.py`)
  - Added explicit SKILL CHECK RULES to branch generator system prompt (`src/world_server/quantum/branch_generator.py`)
  - Fixed duplicate "pick" verb mapping that caused conflicts (`src/world_server/quantum/action_matcher.py`)
  - Added 20 parametrized tests for skill action classification (`tests/test_world_server/test_quantum/test_intent_classifier.py`)
  - Deleted stale issue `grounding-retry-repeats-previous-turn` referencing non-existent `gm_node.py`

- **NPC Item Transactions** - Generate transfer_item deltas when NPCs give items to player
  - Updated system prompt to require transfer_item deltas when narrative describes receiving items (`src/world_server/quantum/branch_generator.py`)

- **Tool-Call Meta-Commentary Detection** - Validates narratives don't expose game mechanics
  - Added `TOOL_CALL_PATTERNS` and `_check_tool_commentary()` to `NarrativeConsistencyValidator` (`src/world_server/quantum/validation.py`)
  - Detects tool names (`take_item`, `transfer_item`), usage announcements ("call the X tool"), and system references
  - Returns ERROR severity to trigger narrative retry when detected
  - 8 new tests for meta-commentary detection (`tests/test_world_server/test_quantum/test_validation.py`)
  - Added 14 item type hints for NPC-given items (mug, tankard, bowl, loaf, etc.) (`src/world_server/quantum/delta_postprocessor.py`)
  - 3 new tests for NPC item giving scenarios (`tests/test_world_server/test_quantum/test_delta_postprocessor.py`)

- **UPDATE_LOCATION Destination Validation** - Reject deltas with non-existent location destinations
  - Added destination validation in `_check_unknown_keys()` against manifest exits (`src/world_server/quantum/delta_postprocessor.py`)
  - Added `_check_unknown_locations()` method for explicit location checking
  - Invalid destinations trigger regeneration (cannot be clarified via LLM like entity keys)
  - 4 new tests for destination validation (`tests/test_world_server/test_quantum/test_delta_postprocessor.py`)

- **Speech Acts with Nested Modals** - Fix "ask X if I can Y" being misclassified as QUESTION
  - Input like "ask Old Tom if I can buy bread" was returning OOC responses instead of roleplay
  - Added explicit nested modal examples to intent classifier (`src/world_server/quantum/intent_classifier.py`)
  - Clarified rule: when "ask" comes before a target NPC, it's ALWAYS a speech act
  - Added regression test `test_ask_npc_if_can_buy_is_action` (`tests/test_world_server/test_quantum/test_intent_classifier.py`)

- **OBSERVE/WAIT Intent Matching** - Fix "look around" commands causing unintended player movement
  - Added `UNTARGETED_ACTION_TYPES` set for environmental actions that don't target entities (`src/world_server/quantum/pipeline.py`)
  - Modified `_intent_to_match_result()` to skip target matching for OBSERVE and WAIT actions
  - "look around the village square" now correctly matches OBSERVE instead of falling back to fuzzy matcher

- **Ambient NPC Grounding** - Fix "Invalid entity key" errors for dynamically created NPCs
  - Added `INVARIANT FOR AMBIENT NPCs` to branch generator system prompt requiring `[key:display]` format (`src/world_server/quantum/branch_generator.py`)
  - Added `_inject_missing_npc_creates()` to auto-create NPCs from narrative patterns (`src/world_server/quantum/delta_postprocessor.py`)
  - Added `NPC_KEY_HINTS` for recognizing NPC keys (patron, traveler, guard, etc.)
  - Fixed regression: CREATE_ENTITY keys now added to `additional_valid_keys` before validation (`src/world_server/quantum/pipeline.py`)
  - Updated `give_item` translator to handle new item keys that will be auto-created (`src/world_server/quantum/delta_translator.py`)
  - 4 new tests for key injection (`tests/test_world_server/test_quantum/test_pipeline.py`)
  - 7 new tests for intent-to-match result handling (`tests/test_world_server/test_quantum/test_pipeline.py`)

- **Narrative Time Consistency** - Pass game time context to narrator engine
  - Added `game_time`, `game_period`, `game_day` fields to `NarrationContext` (`src/world_server/quantum/narrator.py`)
  - Added Time of Day section to `NARRATOR_SYSTEM_PROMPT` with period-specific guidance
  - Added `_get_time_state()` and `_calculate_game_period()` helpers to pipeline (`src/world_server/quantum/pipeline.py`)
  - Both split architecture PHASE 4 locations now pass time context to narrator
  - 14 new tests for time context handling

- **Intent Classifier Speech Acts** - Fix dialog requests misclassified as questions
  - "ask NPC if X" now correctly classified as ACTION instead of QUESTION (`src/world_server/quantum/intent_classifier.py`)
  - Added "Speech Acts vs Meta Questions" section to classifier prompt
  - Speech acts (ask, tell, greet, say) are actions; modal verbs (could, can) are questions
  - 10 new tests for speech act classification (`tests/test_world_server/test_quantum/test_intent_classifier.py`)

- **Movement Location Recording** - Fix turn saved with pre-action location instead of post-action
  - Reordered commit/refresh before save in game loop (`src/cli/commands/game.py`)
  - Turns now correctly record where player ended up, not where they started

- **MOVE Narrative Direction Reversed** - Fix LLM generating backwards travel narratives
  - Added `origin_location_key` and `origin_location_display` to BranchContext (`src/world_server/quantum/branch_generator.py`)
  - Added MOVEMENT DIRECTION section to prompt clarifying FROM→TO direction
  - Pipeline passes origin location when building context for MOVE actions (`src/world_server/quantum/pipeline.py`)
  - Added `new_location` field to TurnResult for tracking post-move location

- **NPC False Matches by Display Name** - Fix NPCs appearing at wrong locations
  - Removed `display_name` fallback in `get_npcs_in_scene()` (`src/managers/entity_manager.py`)
  - Now uses strict `location_key` matching only

- **Silent UPDATE_LOCATION Failure** - Fix invalid location keys silently skipped
  - Now raises ValueError with available location keys (`src/world_server/quantum/collapse.py`)

- **Item Location Query** - Fix items at location not appearing in manifest
  - `get_items_at_location()` now checks both `storage_location_id` and `owner_location_id` (`src/managers/item_manager.py`)

- **Exit Resolution by Display Name** - Fix movement failing when LLM outputs display name
  - `RefManifest.resolve_exit()` now supports ref, key, or display name lookup (`src/world_server/quantum/ref_manifest.py`)

- **TRANSFER_ITEM Delta Keys** - Fix item pickup not transferring to player
  - Changed `to_entity`/`from_entity` to `to_entity_key`/`from_entity_key` to match collapse manager (`src/world_server/quantum/delta_translator.py`)

- **CREATE_ENTITY Invalid EntityType** - Fix PostgreSQL error when LLM outputs `entity_type: "location"`
  - Added `VALID_ENTITY_TYPES` mapping to normalize LLM output in delta translator (`src/world_server/quantum/delta_translator.py`)
  - Added routing for "location" type to LocationManager in collapse (`src/world_server/quantum/collapse.py`)
  - Unknown types now default to misc item instead of causing database errors

### Changed
- **Narrator Prompt** - Added repetition avoidance guideline to prevent location name spam (`src/world_server/quantum/narrator.py`)

### Fixed
- **CLI Play Shortcut** - Fix `rpg play` shortcut not passing required parameters
  - Pass explicit defaults for `roll_mode` and `anticipation` (`src/cli/main.py`)

- **Action Executor Attribute Access** - Fix combat using attribute object instead of value
  - `get_attribute()` returns int value, not Attribute model (`src/executor/action_executor.py`)

- **Complication Oracle Fact Recording** - Fix `record_fact()` API mismatch
  - Updated to use `subject_type`, `subject_key`, `category=FactCategory` parameters (`src/oracle/complication_oracle.py`)

- **Action Validator Deferred Item Location** - Prevent taking items from other locations
  - Added location check for deferred items in TAKE validation (`src/validators/action_validator.py`)

- **Test Suite Updates** - Fixed tests for recent API changes
  - Sleep test: verify stamina restoration + require sleep_pressure threshold
  - Validator mocks: added `actor_location` parameter
  - Context compiler: `well-rested` comes from low `sleep_pressure`, not high stamina
  - Base manager: verify `_clamp()` uses rounding not truncation
  - LLM factory: updated to use `ProviderConfig` pattern
  - NarratorManifest: updated expected format `[key:display_name]`


- **Quantum Pipeline Delta Validation** - Fix LLM-generated deltas with invalid values
  - Fixed hardcoded `player_key="player"` → now uses actual entity key (`src/world_server/quantum/pipeline.py`)
  - Removed invalid `location_key` field from CREATE_ENTITY (not in Entity model) (`src/world_server/quantum/collapse.py`)
  - Added FactCategory validation for RECORD_FACT - invalid categories fall back to "personal" with warning
  - Updated system prompt with valid enum values and entity key guidance (`src/world_server/quantum/branch_generator.py`)
  - Documented anticipation/caching topic-awareness problem (`docs/quantum-branching/anticipation-caching-issue.md`)

- **GM Ignores Player Input Specifics** - Fix NPC conversations ignoring conversation topics
  - Added `player_input` field to `BranchContext` for topic-awareness (`src/world_server/quantum/branch_generator.py`)
  - Pass `player_input` to branch generation so LLM knows what player asked about
  - Disabled anticipation by default (pre-generation conflicts with topic-awareness)

- **Test Fixes** - Fixed 2 pre-existing quantum test failures
  - Fixed `_normalize()` trailing space from punctuation replacement (`src/world_server/quantum/action_matcher.py`)
  - Fixed `test_modifiers_passed_to_skill_check` mock to handle new optional parameters


- **RECORD_FACT Delta Validation** - Fix null predicate/value causing database constraint violations
  - Updated branch generator prompt to specify required fields with example (`src/world_server/quantum/branch_generator.py`)
  - Added defensive validation in collapse to skip invalid deltas gracefully (`src/world_server/quantum/collapse.py`)
  - Added default category "personal" when LLM omits it
  - Strengthened validation to check for None values, not just missing keys (`src/world_server/quantum/validation.py`)
  - Added 3 tests for null field handling (`tests/test_world_server/test_quantum/test_collapse.py`)

- **Turn History Persistence** - `game turn` command now saves turns to database
  - Added `_save_turn_immediately()` call to persist turn history (`src/cli/commands/game.py:1773`)
  - Fixes missing conversation context for action matching

- **Quantum Pipeline Runtime Fixes** - Multiple bugs discovered during play-testing
  - Fixed `TimeState.day_number` → `current_day` attribute error (`src/world_server/quantum/pipeline.py:515`)
  - Fixed BranchGenerator using wrong LLM - now uses reasoning model for structured JSON, narrator only for prose (`pipeline.py:166`)
  - Fixed dict-to-Pydantic parsing for OpenAI provider responses (`src/world_server/quantum/branch_generator.py:143`)
  - Added missing `skill_check_result` and `errors` properties to `TurnResult` (`pipeline.py:89-101`)

- **Skill Check Metadata Propagation** - Skill checks now display correct info in CLI
  - Added `skill_name`, `attribute_key`, `skill_modifier`, `attribute_modifier` fields to `SkillCheckResult` (`src/dice/types.py`)
  - Updated `make_skill_check()` to accept and store skill metadata (`src/dice/checks.py`)
  - Integrated `get_attribute_for_skill()` mapping in collapse manager (`src/world_server/quantum/collapse.py`)
  - Fixed CLI to use actual SkillCheckResult fields instead of workarounds (`src/cli/commands/game.py`)

### Documentation
- **Documentation Cleanup** - Aligned docs with codebase after quantum pipeline consolidation
  - Updated `CLAUDE.md` project statistics: tests ~3,700 (was ~2,200), models 29, commands 6
  - Fixed `docs/user-guide.md` to remove deprecated `--pipeline` flag and legacy pipeline descriptions
  - Created `docs/issues/RESOLVED.md` summary index for 5 closed issues
  - Archived deprecated proposals to `docs/archive/`: scene-first, world-server, structured-gm
  - Removed 5 resolved issue directories (consolidated into RESOLVED.md)

### Changed
- **Consolidated to Quantum-Only Pipeline** - Removed all legacy pipelines, unified on quantum branching
  - **Dual-Model Separation** - qwen3 for reasoning/logic, magmell for narrative prose
  - Removed LangGraph-based pipelines (GM, Legacy, System-Authority, Scene-First)
  - Deleted `src/agents/graph.py`, `src/agents/nodes/`, `src/agents/tools/`, `src/agents/schemas/`
  - Deleted `src/gm/graph.py`, `gm_node.py`, `validator.py`, `applier.py`, `action_classifier.py`
  - Deleted `src/world_server/` top-level files (kept `quantum/` subdirectory)
  - Simplified CLI: removed `--pipeline` option from `start`, `play`, `turn` commands
  - Updated `QuantumPipeline` to use both `get_reasoning_provider()` and `get_narrator_provider()`
  - Reduced test count from ~3,372 to ~2,200 by removing obsolete pipeline tests

### Added
- **Gold Stack Splitting** - Quantity-based operations for stackable items (gold, potions, etc.)
  - `ItemManager.split_stack()` - Split quantity from stackable item (`src/managers/item_manager.py`)
  - `ItemManager.merge_stacks()` - Combine two stacks of same type
  - `ItemManager.find_mergeable_stack()` - Find existing stack to merge into
  - `ItemManager.transfer_quantity()` - Transfer with auto-split and auto-merge
  - `drop_item(quantity=N)` - Drop partial stack at current location (`src/gm/tools.py`)
  - `take_item(quantity=N)` - Take partial stack with auto-merge into inventory
  - `give_item(recipient, quantity=N)` - Give partial stack to NPC with auto-merge
  - 32 new tests covering stack operations

- **vLLM Multi-Port Support** - Task-specific base URLs for vLLM deployments with different models on different ports
  - Added `narrator_base_url`, `reasoning_base_url`, `cheap_base_url` settings (`src/config.py`)
  - Factory functions now use task-specific URLs for OpenAI-compatible providers (`src/llm/factory.py`)
  - Enables running different models (e.g., qwen3, magmell) on separate vLLM instances

- **vLLM Thinking Mode Toggle** - Enable/disable thinking for Qwen3 models via `/nothink` prefix
  - Added `think: bool` parameter to `OpenAIProvider.complete()` (default: False for speed)
  - Added `think: bool` parameter to `OpenAIProvider.complete_with_tools()` (default: True for reasoning)
  - `_strip_thinking()` method removes `<think>` tags from responses
  - Key file: `src/llm/openai_provider.py`

- **Quantum Branching Pipeline** - Unified pipeline that pre-generates action outcome branches for instant responses
  - **ActionPredictor** - Predicts likely player actions from scene context (NPCs, items, exits) (`src/world_server/quantum/action_predictor.py`)
  - **ActionMatcher** - Fuzzy matches player input to cached predictions with configurable confidence threshold (`src/world_server/quantum/action_matcher.py`)
  - **GMDecisionOracle** - Predicts GM twist decisions with grounding facts (`src/world_server/quantum/gm_oracle.py`)
  - **BranchGenerator** - Generates narrative variants (success/failure/critical) with state deltas (`src/world_server/quantum/branch_generator.py`)
  - **QuantumBranchCache** - LRU cache with TTL for pre-generated branches (`src/world_server/quantum/cache.py`)
  - **BranchCollapseManager** - Rolls dice at runtime and applies selected variant atomically (`src/world_server/quantum/collapse.py`)
  - **QuantumPipeline** - Main entry point replacing LangGraph streaming (`src/world_server/quantum/pipeline.py`)
  - **Validation Layer** - NarrativeConsistencyValidator, DeltaValidator, BranchValidator (`src/world_server/quantum/validation.py`)
  - **CLI Integration** - Quantum is now default pipeline with `--anticipation` flag for background pre-generation
  - **Configuration** - `quantum_anticipation_enabled`, `quantum_max_actions_per_cycle`, `quantum_min_match_confidence` in `src/config.py`
  - **Documentation** - Full documentation in `docs/quantum-branching/` (README, architecture, action-prediction, branch-generation, collapse-mechanism, caching-strategy, migration-guide)
  - 259 tests covering all quantum components

- **World Server Anticipation System** - Pre-generate scenes while player reads to hide LLM latency (superseded by Quantum Branching)
  - `WorldServerManager` integration layer for CLI (`src/world_server/integration.py`)
  - `LocationPredictor` predicts likely next locations (adjacent, quest targets, mentioned) (`src/world_server/predictor.py`)
  - `PreGenerationCache` async LRU cache for pre-generated scenes (`src/world_server/cache.py`)
  - `StateCollapseManager` commits pre-generated content on observation (`src/world_server/collapse.py`)
  - `SceneGenerator` creates scene data for anticipated locations (`src/world_server/scene_generator.py`)
  - `AnticipationEngine` orchestrates background generation (`src/world_server/anticipation.py`)
  - **GM Cache Integration** - GMNode checks cache before expensive LLM generation (`src/gm/gm_node.py`)
    - `_check_pre_generated_scene()` returns cached scene if available
    - `_collapse_result_to_response()` converts cache data to GMResponse
    - `_synthesize_scene_narrative()` builds narrative from manifest when needed
  - `--anticipation/--no-anticipation` CLI flag for `rpg game play`
  - Config options: `anticipation_enabled`, `anticipation_cache_size` in `src/config.py`
  - 104 tests covering world_server and GM cache integration

- **Gameplay Monitor Script** - Interactive debugging tool for GM pipeline observation
  - Real-time display of LLM calls, tool executions, and state changes
  - Automated test scenarios with milestone and issue tracking
  - Session summary with issues found and milestones achieved
  - Key file: `scripts/gameplay_monitor.py`

### Fixed
- **Character Break Detection Leaks to Console** - Validation messages now hidden from player
  - Changed `logger.warning/error/info` to `logger.debug` for character validation (`src/gm/gm_node.py:815-865`)
  - Prevents "Character break detected..." messages from appearing during gameplay
  - Issue tracking: `docs/issues/character-break-shows-partial-response/`

- **GM Chatbot Question Endings** - Detect and prevent chatbot-like questions that break immersion
  - Added patterns: "would you like to", "do you want to", "is there anything else/specific", "what do you want to" (`src/gm/gm_node.py`)
  - Updated ABSOLUTE RULES in system prompt to explicitly forbid these endings (`src/gm/prompts.py`)
  - Added 6 new test cases for chatbot question detection (`tests/test_gm/test_character_validation.py`)

- **GM Hallucinates Item Keys** - GM now uses exact keys from context instead of inventing them
  - Changed key format to `KEY=x | Name` for visual distinction (`src/gm/grounding.py`)
  - Added key validation in `execute_tool()` for take_item/drop_item/give_item (`src/gm/tools.py`)
  - Fixed error handling: removed "narrate as if succeeded" option (`src/gm/prompts.py`)
  - 4 new tests for key validation behavior (`tests/test_gm/test_tools.py`)

- **Grounding Manifest Not Updated After create_entity** - Entities created mid-turn now valid for narrative
  - Added `additional_valid_keys` field to `GroundingManifest` (`src/gm/grounding.py`)
  - Track created entity keys in `_execute_tool_call()` (`src/gm/gm_node.py:1058-1063`)
  - 5 new tests for additional_valid_keys behavior (`tests/test_gm/test_grounding.py`)

- **move_to Tool Not Registered** - Player movement now works correctly
  - Added missing `move_to` case in `execute_tool()` dispatcher (`src/gm/tools.py:1031-1032`)
  - Added `test_execute_tool_dispatches_move_to` test (`tests/test_gm/test_tools.py`)
  - Issue tracking: `docs/issues/move-to-tool-not-registered/`

- **Auto-Start Creates Blank Location** - `game start --auto` now creates proper starter world
  - Added `_create_auto_world()` function to create Village Tavern, Square, and Market
  - Creates 2 NPCs: Old Tom (innkeeper) and Anna (merchant)
  - Sets up bidirectional exits between locations
  - Player starts in The Rusty Tankard with proper scene context
  - Key file: `src/cli/commands/game.py`
  - Issue tracking: `docs/issues/session-auto-start-blank-location/`

- **Error Messages Leaked into Narrative** - Technical failure messages now converted to immersive prose
  - "FAILED talk Baker: 'Baker' is not here." → "You look around but don't see Baker here."
  - Added `FAILED_ACTION_TEMPLATES` with narrative templates for 20+ action types
  - Added `_convert_failed_action_to_narrative()` helper for template-based conversion
  - Covers social (talk, ask, give), item (take, drop, equip), combat (attack), and movement actions
  - Added 18 unit tests for narrative conversion
  - Key file: `src/narrator/narrator.py`
  - Issue tracking: `docs/issues/error-message-leaked-narrative/`

- **GM Hallucinates Entity Keys** - Multi-layer fix for LLM inventing keys like `farmer_001` instead of copying `farmer_marcus`
  - **Layer 1 (Prevention)**: Fixed inconsistent examples in prompts.py, enhanced manifest format with inline key reminders
  - **Layer 2 (Recovery)**: Added fuzzy matching suggestions to error feedback ("Did you mean: farmer_marcus?")
  - **Layer 3 (Graceful Degradation)**: Added `KeyResolver` class for auto-correcting close key matches in tool calls
  - Key files: `src/gm/grounding.py`, `src/gm/tools.py`, `src/gm/gm_node.py`
  - Issue tracking: `docs/issues/gm-hallucinates-entity-keys/`
- **GM Meta-Commentary Before Tool Calls** - GM no longer announces tool usage
  - Detected immersion-breaking text like "Let me get the scene details for you." before tool calls
  - Added 3 detection patterns to `_CHARACTER_BREAK_PATTERNS`: "let me get/check/look", "I'll get/check/look", "I need to get/check/look"
  - Added rule 8 to GM prompt: "NEVER announce tool usage"
  - Added 6 unit tests for pre-tool announcement detection
  - Key files: `src/gm/gm_node.py`, `src/gm/prompts.py`
  - Issue tracking: `docs/issues/gm-meta-commentary-tool-calls/`

- **Character Break on Tool Errors** - LLM now handles tool failures gracefully in-story
  - Added HANDLING TOOL FAILURES section to GM_SYSTEM_PROMPT and MINIMAL_GM_CORE_PROMPT
  - LLM instructed to narrate success or give in-story reason instead of exposing technical errors
  - Added 5 detection patterns for leaked technical terms: "not in inventory", "unable to find", etc.
  - Added 10 unit tests for tool error exposure patterns
  - Key files: `src/gm/prompts.py`, `src/gm/gm_node.py`
  - Issue tracking: `docs/issues/character-break-on-tool-errors/`

- **Unrealistic Time Passage** - Activities now have realistic duration estimates
  - "Eat a hearty meal" now takes 32 minutes instead of 1 minute
  - Hybrid time estimation: combines activity keywords + tool results, takes maximum
  - Added `ACTIVITY_PATTERNS` (13 categories: eating, resting, exploration, etc.)
  - Added `TIME_MODIFIERS` (quickly=0.7x, thoroughly=1.4x, etc.)
  - Fixed bug: tool result keys were "name"/"input" but should be "tool"/"arguments"
  - Added 47 tests for time estimation
  - Key files: `src/gm/gm_node.py`, `tests/test_gm/test_time_estimation.py`
  - Issue tracking: `docs/issues/unrealistic-time-passage/`

- **Wrong Need Type for Activities** - Added explicit activity-to-need mapping in satisfy_need tool
  - LLM was selecting wrong need (e.g., drinking → hunger instead of thirst)
  - Tool description now includes explicit mapping table for eating→hunger, drinking→thirst, etc.
  - Added 4 tests to verify correct need mappings
  - Key file: `src/gm/tools.py`
  - Issue tracking: `docs/issues/wrong-need-type-for-activities/`

- **GM Invents Wrong Item Keys** - Added explicit prompt instructions to copy exact entity keys
  - LLM was generating `mug_of_ale` instead of copying `ale_mug_001` from context
  - Added TOOL PARAMETER RULES section to GM_SYSTEM_PROMPT and MINIMAL_GM_CORE_PROMPT
  - Key file: `src/gm/prompts.py`
  - Issue tracking: `docs/issues/llm-invents-wrong-item-keys/`

- **GM Tool Output Exposure** - Character validation now detects when LLM leaks tool responses to player
  - Added 9 patterns for meta-questions: "what would you like", "the provided text", "let me know if", etc.
  - Fixed bug in `next steps?:` pattern (trailing `\b` didn't match after colon)
  - Added 28 unit tests for character break detection
  - Key files: `src/gm/gm_node.py`, `src/gm/context_builder.py`
  - Issue tracking: `docs/issues/tool-output-leaked-to-player/`

- **GM Audit Context** - LLM call logs now organized by session instead of orphan folder
  - Added `set_audit_context()` call in `GMNode.run()` before LLM calls
  - Logs now saved to `logs/llm/session_<id>/turn_<n>_*.md` instead of `logs/llm/orphan/`
  - Key file: `src/gm/gm_node.py`
  - Issue tracking: `docs/issues/gm-audit-context-session-id/`

- **GM Entity Key-Text Format** - Fixed LLM outputting `[key]` instead of `[key:text]` format
  - Added `fix_key_only_format()` to convert `[key]` → `[key:display_name]` using manifest lookup
  - Updated `strip_key_references()` to accept optional manifest for auto-fix before stripping
  - Prevents empty display text like "You take a bite of , savoring..."
  - Key file: `src/gm/grounding_validator.py`
  - Issue tracking: `docs/issues/gm-entity-key-text-format/`

- **GM Grounding Retry Duplicate Responses** - Fixed narrative duplication after grounding validation retry
  - Grounding retry now includes tool result context in feedback message
  - Prevents LLM from re-describing scene instead of narrating action results
  - E2E turn pass rate improved: 61.5% → 100%
  - Key file: `src/gm/gm_node.py`

- **Grounding Validator False Positives** - Player equipment no longer triggers unkeyed mention errors
  - Added `skip_player_items=True` parameter to `GroundingValidator`
  - Player inventory and equipped items exempt from unkeyed mention checks
  - Narrative like "You're wearing a simple tunic" no longer fails validation
  - Key file: `src/gm/grounding_validator.py`
  - Issue tracking: `docs/issues/gm-unkeyed-entities/`

- **E2E Player Agent Action Loops** - Improved goal-awareness and repetition detection
  - Semantic verb matching: "look around" and "examine surroundings" now detected as repetitive
  - Goal-aware fallback variations: dialog goals → greeting actions, item goals → search actions
  - Checks last 3 actions instead of just last 1 for repetition
  - Enhanced system prompt with NPC engagement rules (rules 9-10)
  - Key file: `scripts/gm_e2e_player_agent.py`

- **GM Character Consistency** - Multi-layer defense against AI-like responses
  - Layer 1: Strengthened GM persona in system prompt with explicit character rules
  - Layer 2: `_validate_character()` detects character breaks with regex patterns and retries
  - Layer 3: `_is_valid_turn()` filters bad turns from conversation history
  - Patterns detect: AI self-identification, chatbot phrases, third-person narration, technical meta-commentary
  - E2E test pass rate: 40% → 100%
  - Key files: `src/gm/gm_node.py`, `src/gm/context_builder.py`, `src/gm/prompts.py`

- **GM Grounding Retry Loop** - Fixed retry to use text-only completion
  - Changed from `complete_with_tools()` to `complete()` for grounding retries
  - Prevents model from calling more tools instead of fixing narrative
  - Key file: `src/gm/gm_node.py`

- **GM Tool Calling Consistency** - Improved prompt structure for reliable tool execution
  - Restructured GM system prompt with "MANDATORY TOOL CALLS" section at top
  - Added all 10 needs with trigger words in table format
  - Added few-shot examples showing correct tool→narrative flow
  - Fixed `_clamp` truncation bug: `int()` → `round()` (99.9 → 100 instead of 99)
  - Added `think` parameter to `AnthropicProvider.complete_with_tools()` for compatibility
  - Key files: `src/gm/prompts.py`, `src/managers/base.py`, `src/llm/anthropic_provider.py`
  - Issue tracking: `docs/issues/gm-prompt-tool-calling/`

- **Tool Loop Message Handling** - Fixed Anthropic API message format for tool results
  - Proper tool_use content blocks in assistant messages
  - Combined multiple tool_result blocks into single user message
  - Turn number tracking for fact recording
  - Key files: `src/gm/gm_node.py`, `src/gm/tools.py`, `src/llm/anthropic_provider.py`

### Added
- **Player Movement Tool** - `move_to` tool for updating player location when traveling
  - Added `move_to(destination, travel_method)` tool with trigger words: go, walk, leave, travel, enter, exit
  - Fuzzy-matches destination names or auto-creates new locations
  - Calculates realistic travel time based on location hierarchy (2-10 min base, modifiers: run=0.5x, sneak=2x)
  - Added prompt instructions in MANDATORY TOOL CALLS section
  - Added 8 unit tests for movement scenarios
  - Key files: `src/gm/tools.py`, `src/gm/prompts.py`
  - Issue tracking: `docs/issues/movement-without-state-update/`

- **Minimal Context Mode for Local LLMs** - 70-80% token reduction for Ollama/vLLM
  - Action classifier detects action type from keywords (look, eat, attack, etc.)
  - Pre-fetches only relevant context based on action category
  - 4 new context tools: `get_rules()`, `get_scene_details()`, `get_player_state()`, `get_story_context()`
  - Auto-enabled for `ollama` and `qwen-agent` providers
  - New config: `use_minimal_context` (None=auto-detect, True/False=override)
  - Key files: `src/gm/action_classifier.py`, `src/gm/rule_content.py`, `src/gm/context_builder.py`

- **Anthropic Prompt Caching** - Faster subsequent LLM calls via cached system prompts
  - Added `cache_control: {"type": "ephemeral"}` to system prompts
  - First call caches (~40s), subsequent calls read from cache (10x cheaper)
  - Cache stats displayed in verbose mode: `⚡cached:3344` or `📦caching:3344`
  - Token streaming via `complete_with_tools_streaming()` with `on_token` callback
  - Key files: `src/llm/anthropic_provider.py`, `src/observability/console_observer.py`

- **E2E Test Grounding Validation** - Detect GM hallucinations in test assessment
  - `GME2EAssessor` class with entity grounding checks
  - Fails tests when GM response doesn't mention expected scene entities
  - Proper `Location` record creation in test setup (fixes context building)
  - Key files: `src/gm/e2e_assessor.py`, `scripts/gm_e2e_immersive_runner.py`

- **GM Pipeline Observability** - Real-time visibility into long-running E2E tests
  - New `src/observability/` module with observer pattern architecture
  - `RichConsoleObserver` renders colored console output with phase timings
  - Events: PhaseStart/End, LLMCallStart/End, ToolExecution, Validation
  - `--verbose` flag shows pipeline phases, LLM calls, tool executions
  - Single `live.log` file for `tail -f` monitoring (replaces per-scenario logs)
  - Key files: `src/observability/`, `src/gm/gm_node.py`, `scripts/gm_e2e_immersive_runner.py`

- **Immersive E2E Test Runner** - LLM-driven gameplay testing with natural player behavior
  - `TestPlayerAgent` uses Ollama qwen3:32b to decide contextually appropriate actions
  - 100 goal-based scenarios across 20 categories (5+ tests per need type)
  - Hybrid error handling: stops on 3 consecutive fundamental errors, generates diagnostic dump
  - Dump at `logs/gm_e2e/gm_e2e_error.md` for `/tackle` in Claude Code
  - Key files: `scripts/gm_e2e_immersive_runner.py`, `scripts/gm_e2e_player_agent.py`, `scripts/gm_e2e_scenarios.py`

- **Grounded Narration System** - Prevent GM from hallucinating entities with validation
  - `GroundingManifest` schema tracks all valid entity keys (NPCs, items, storages, exits)
  - `GroundingValidator` checks `[key:text]` refs exist in manifest, detects unkeyed mentions
  - Validation loop with retry (max 2x) and error feedback to LLM on grounding failures
  - Key stripping: `[marcus_001:Marcus]` → `Marcus` for natural display output
  - Updated GM prompt with `[key:text]` format rules and examples
  - 36 unit tests for grounding system
  - Key files: `src/gm/grounding.py`, `src/gm/grounding_validator.py`, `src/gm/gm_node.py`

- **Conversational GM Context Architecture** - Natural conversation flow for GM LLM calls
  - World state now in dynamic system prompt (refreshes each turn)
  - Turn history as USER/ASSISTANT message pairs (not embedded text)
  - Day-aware turn selection: 10 back + extend to day start for full-day context
  - No truncation of turn content (previously 200/500 char limits)
  - Key files: `src/gm/context_builder.py`, `src/gm/gm_node.py`

- **GM Pipeline E2E Test Framework** - Automated end-to-end testing for GM pipeline
  - `GME2ETestRunner` runs flowing gameplay scenarios with comprehensive logging
  - `GME2EAssessor` evaluates narrative quality, tool usage, DB changes, time tracking
  - `GME2ELogger` creates detailed markdown logs per test run in `logs/gm_e2e/`
  - 6 test scenarios: exploration/dialog, item interaction, skill challenges, needs, movement, OOC
  - Duplicate response detection, forbidden pattern checks, time bound validation
  - Key files: `scripts/gm_e2e_test_runner.py`, `scripts/gm_e2e_scenarios.py`, `src/gm/e2e_assessor.py`, `src/gm/e2e_logger.py`

- **Auto Mode for Game Start** - `--auto` flag for automated test session creation
  - Creates pre-populated test character without prompts
  - Enables headless session creation for E2E testing
  - Key file: `src/cli/commands/game.py`

- **Expanded E2E Testing Documentation** - Comprehensive testing guide updates
  - Test action categories with expected durations
  - Tool reliability testing procedures
  - Craving/stimulus testing scenarios
  - StateChange type reference table
  - Key file: `docs/gm-pipeline-e2e-testing.md`

- **Item Manipulation & Need Satisfaction Tools** - New GM tools for direct game state changes
  - `take_item(item_key)` - Player picks up items from scene/storage
  - `drop_item(item_key)` - Player drops items at current location
  - `give_item(item_key, recipient_key)` - Player gives items to NPCs
  - `satisfy_need(need, amount, activity)` - Satisfy player needs (hunger, thirst, stamina, etc.)
  - Tool-based time estimation (replaces fragile keyword matching)
  - Enhanced GM prompt with explicit tool usage examples
  - Key files: `src/gm/tools.py`, `src/gm/prompts.py`, `src/gm/gm_node.py`
  - Issue tracking: `docs/issues/gm-pipeline-tool-gaps/`

- **GM Pipeline Tools Expansion** - Extended GM tools from 5 to 15 with consistent architecture
  - StateChanges for mutations, Tools for queries/feedback
  - Renamed `CONSUME` to `SATISFY_NEED` - clearer for activities (sleeping, bathing)
  - Extended `SATISFY_NEED` for activity-based needs (not just item consumption)
  - Extended `MOVE` StateChange for NPC movement (not just player)
  - New `get_npc_attitude` tool - query NPC relationship before dialogue
  - New quest tools: `assign_quest`, `update_quest`, `complete_quest`
  - New task tools: `create_task`, `complete_task`
  - New appointment tools: `create_appointment`, `complete_appointment`
  - New `apply_stimulus` tool - create cravings when describing tempting scenes
  - Extended `create_entity` for `storage` type (containers/furniture)
  - Key files: `src/gm/tools.py`, `src/gm/applier.py`, `src/gm/schemas.py`

- **Item State Extraction** - Separate item identity from state in keys and properties
  - New `ItemStateExtractor` utility extracts state adjectives from display names
  - Keys now based on base name only (e.g., `linen_shirt` not `clean_linen_shirt`)
  - State stored in `properties.state` dict (cleanliness, condition, freshness, quality, age)
  - New `ItemManager.update_item_state()` method for state changes
  - Updated `spawn_item`, `acquire_item`, `create_entity`, and emergent item generation
  - Key files: `src/services/item_state_extractor.py`, `src/managers/item_manager.py`

- **Needs Validator Node** - Fallback mechanism for missed needs updates
  - Scans GM response for keywords (wash, eat, drink, rest, talk)
  - Auto-applies reasonable defaults when GM forgets to call `satisfy_need`
  - Tracks `last_*_turn` fields to avoid duplicate updates
  - Key file: `src/agents/nodes/needs_validator_node.py`

- **Storage Observation Tracking** - First-time vs revisit detection for containers
  - New `StorageObservation` model tracks when player first observes storage contents
  - `StorageObservationManager` for observation CRUD operations
  - GM context shows `[FIRST TIME]` or `[REVISIT]` tags for storage containers
  - Items created in storage via `storage_location` parameter on `create_entity`
  - Key files: `src/database/models/world.py`, `src/managers/storage_observation_manager.py`

- **Conversation-First GM Context** - Restructured prompt for better comprehension
  - Recent turns now PRIMARY context (before scene/database info)
  - Reduced system prompt from ~150 to ~75 lines
  - Added INTENT ANALYSIS section (question/action/dialogue classification)
  - Added FIRST-TIME vs REVISIT rules for storage containers
  - Key files: `src/gm/prompts.py`, `src/gm/context_builder.py`

- **Update Docs Command** - New `/update-docs` slash command for documentation maintenance
  - Audits and updates project docs to match current codebase state
  - Checks for clean working tree, runs `/commit` first if dirty
  - Compares CLAUDE.md stats, architecture.md, implementation-plan.md against actual code
  - Reports changes made and flags items needing manual attention
  - Key file: `.claude/commands/update-docs.md`

- **Multi-Model LLM Configuration** - Task-specific provider:model routing
  - New `provider:model` format in `.env` (e.g., `NARRATOR=ollama:magmell:32b`)
  - Three task-specific settings: `NARRATOR`, `REASONING`, `CHEAP`
  - Supports mixing providers (ollama, qwen-agent, anthropic, openai per task)
  - `ProviderConfig` dataclass and `parse_provider_config()` parser
  - Task-specific factory functions: `get_narrator_provider()`, `get_reasoning_provider()`, `get_cheap_provider()`
  - Key files: `src/config.py`, `src/llm/factory.py`

- **GM Spawn Tools** - New tools for creating world objects during narration
  - `spawn_storage` - Create furniture, containers, surfaces (table, chest, shelf, etc.)
  - `spawn_item` - Create discoverable items on surfaces
  - `introduce_npc` - Introduce new NPCs with initial attitude
  - Replaces verbose `create_entity` workflow with purpose-specific tools
  - Key file: `data/templates/game_master.md`

- **GM Text Accumulation** - Narrative text preserved across tool call iterations
  - LLM can now narrate before making tool calls without losing that text
  - All text from intermediate responses combined in final output
  - Key file: `src/gm/gm_node.py`

### Fixed
- **GM Player Agency Over-Interpretation** - GM no longer infers acquisition from observation verbs
  - Added PLAYER AGENCY section to GM prompts distinguishing observation vs acquisition intent
  - "find clothes" now describes items without adding to inventory
  - "take the shirt" correctly triggers acquisition
  - Trust LLM to understand natural language instead of word lists
  - Key files: `src/gm/prompts.py`, `data/templates/game_master.md`

- **GM Structured Output Cleanup** - Strip hallucinated markdown formatting from GM responses
  - Added `_clean_narrative_static()` to remove `**Section:**` headers, bullet lists, inventory summaries
  - Updated NARRATIVE prompt section with explicit FORBIDDEN list
  - 13 unit tests for cleanup edge cases
  - Key files: `src/gm/gm_node.py`, `src/gm/prompts.py`

- **Skill Check Display Compatibility** - CLI now handles both legacy and new GM pipeline formats
  - Maps field names between legacy executor and new GM pipeline
  - Calculates outcome_tier from margin when not provided
  - Key file: `src/cli/commands/game.py`

- **GM create_entity NPC bug** - Fixed broken `create_npc()` call in tools
  - Changed to use `create_entity()` with proper `EntityType.NPC`
  - Creates `NPCExtension` for location and activity tracking
  - Key file: `src/gm/tools.py`
- **GM create_entity items lack location** - Items now placed at current location
  - Items created via `create_entity` get `owner_location_id` set automatically
  - Key file: `src/gm/tools.py`
- **QwenAgentProvider model selection** - Provider now correctly uses `ollama_model` setting
  - `_get_model_for_provider()` now includes `qwen-agent` in Ollama-based providers check
  - Prevents qwen-agent from trying to use Claude/OpenAI model names
  - Key file: `src/llm/factory.py`
- **QwenAgentProvider response parsing** - Handles varied response formats from qwen-agent
  - Response iterator now handles strings, dicts, lists, and Message objects
  - Wraps raw string responses in proper assistant message format
  - Key file: `src/llm/qwen_agent_provider.py`

### Added
- **Character Familiarity Context** - GM now understands what the character is familiar with
  - New `_get_familiarity_context()` method detects home location via `lives_at` fact
  - Expanded implicit OOC signals for routine/habit questions ("where do I usually", "how do I normally")
  - Familiarity section in prompt helps LLM correctly classify OOC vs IC questions
  - Key files: `src/gm/context_builder.py`, `src/gm/prompts.py`

- **OOC (Out-of-Character) Handling** - GM now correctly handles meta and lore questions
  - Explicit OOC prefix detection (`ooc:`, `[ooc]`, etc.) with automatic stripping
  - Context-aware routing: character knowledge vs active conversation with NPCs
  - New `is_ooc` field on Turn model for OOC response metadata
  - New `record_fact` tool for persisting lore during OOC responses
  - OOC responses skip time advancement and state changes
  - Yellow-styled display panel for OOC responses in CLI
  - Key files: `src/gm/gm_node.py`, `src/gm/prompts.py`, `src/gm/tools.py`

- **Simplified GM Pipeline** - New single-LLM pipeline with native tool calling
  - New `src/gm/` module with streamlined Game Master architecture
  - `GMNode` with tool execution loop for skill checks, attacks, entity creation
  - `GMContextBuilder` for rich context with player state, location, NPCs, items
  - `GMTools` with `skill_check`, `attack_roll`, `damage_entity`, `create_entity`
  - `ResponseValidator` and `StateApplier` for grounding and persistence
  - `--pipeline gm` is now the default (replaces system-authority)
  - `--roll-mode auto|manual` for background or interactive dice rolls
  - Non-interactive skill check display in `game turn` command
  - Key files: `src/gm/gm_node.py`, `src/gm/tools.py`, `src/gm/graph.py`

- **Qwen-Agent LLM Provider** - Tool calling support for Qwen3 via Ollama
  - New `QwenAgentProvider` class using qwen-agent library (`src/llm/qwen_agent_provider.py`)
  - Bypasses Ollama's native tool API limitation (which doesn't support Qwen3 tools yet)
  - Uses Hermes-style tool format templates internally
  - Environment config: `LLM_PROVIDER=qwen-agent` with existing `OLLAMA_MODEL` setting
  - Implements full `LLMProvider` protocol: `complete`, `complete_with_tools`, `complete_structured`
  - Key files: `src/llm/qwen_agent_provider.py`, `src/llm/factory.py`

- **CLI Progress Streaming** - Real-time node-by-node progress during graph execution
  - New `_run_graph_with_progress()` uses LangGraph's `astream(stream_mode="updates")`
  - Progress spinner shows which node is running: "Building scene...", "Executing actions...", etc.
  - `NODE_PROGRESS_MESSAGES` dict maps node names to user-friendly descriptions
  - Key file: `src/cli/commands/game.py`

- **Ollama LLM Provider** - Native Ollama integration for local LLM inference
  - New `OllamaProvider` class using `langchain-ollama` (`src/llm/ollama_provider.py`)
  - Supports Llama 3, Qwen3, Mistral and other Ollama models
  - Thinking mode control: `think=False` (default) for fast responses, `think=True` for reasoning
  - Automatic `<think>` tag stripping from Qwen3 and other reasoning models
  - Environment config: `LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`
  - Tool calling and structured output support
  - 19 tests for OllamaProvider (`tests/test_llm/test_ollama_provider.py`)

- **Scene-First Architecture Phase 7-8: Graph Integration & Testing** - Complete scene-first pipeline
  - New `build_scene_first_graph()` in `src/agents/graph.py` with full node wiring
  - New graph nodes: `world_mechanics_node`, `scene_builder_node`, `persist_scene_node`, `resolve_references_node`, `constrained_narrator_node`, `validate_narrator_node`
  - Routing functions: `route_after_parse_scene_first()`, `route_after_resolve()`, `route_after_validate_narrator()`
  - Feature flag `--pipeline scene-first` in CLI to switch between pipelines
  - New `docs/IDEAS.md` for tracking deferred feature ideas
  - New `docs/scene-first-architecture/troubleshooting.md`
  - Integration test: `tests/test_integration/test_scene_first_flow.py` (14 tests)
  - Key files: `src/agents/graph.py`, `src/agents/nodes/world_mechanics_node.py`, `src/agents/nodes/scene_builder_node.py`

### Fixed
- **Narrator [key:text] format** - Changed narrator output from `[key]` to `[key:text]` format for better control
  - Narrator now writes `[cottage_001:cottage]` instead of just `[cottage_001]`
  - Display text after `:` is what readers see after stripping
  - Updated `SceneNarrator`, `NarratorValidator`, and all validation nodes
  - Key files: `src/narrator/scene_narrator.py`, `src/narrator/validator.py`

- **INFO mode bypass for factual queries** - Presence and state queries skip full narration pipeline
  - New `response_mode: "info"` bypasses SceneNarrator for direct answers
  - Supports "Am I alone?", "Who's here?", "What time is it?" type queries
  - Validation nodes skip validation for INFO mode responses
  - Key files: `src/agents/nodes/constrained_narrator_node.py`, `src/planner/prompts.py`

- **Entity location matching** - NPCs now found by display_name fallback
  - Handles data inconsistencies where NPC location was set to display name instead of key
  - Uses `OR` filter to match by either `location_key` or `display_name`
  - Key file: `src/managers/entity_manager.py`

- **Personality traits list format** - ContextCompiler now handles both list and dict formats
  - Supports `["hardworking", "practical"]` (list) and `{"shy": True}` (dict)
  - Added more observable trait mappings
  - Key file: `src/managers/context_compiler.py`

- **Game loop starting location** - Improved fallback chain for finding player start
  - First checks `npc_extension.home_location`, then category, then first location
  - Exits gracefully if no locations exist
  - Key file: `src/cli/commands/game.py`

- **Extractor default models** - ItemExtractor, NPCExtractor, LocationExtractor now use provider's default
  - Pass `model=None` to let provider choose appropriate model
  - Key files: `src/narrator/item_extractor.py`, `src/narrator/npc_extractor.py`, `src/narrator/location_extractor.py`

- **Character wizard empty responses** - LLM returning only JSON without narrative text now shows debug output
  - Added "CRITICAL: Response Format" section to all 5 wizard templates requiring both narrative + JSON
  - Debug output shows raw response when display content is empty
  - Key files: `data/templates/wizard/*.md`, `src/cli/commands/character.py`

- **Character wizard ignoring revision requests** - LLM now properly revises content when player asks for changes
  - Added "CRITICAL: Handling Player Feedback" section to background and personality templates
  - Clear saved background/personality when player rejects, forcing fresh generation
  - Key files: `data/templates/wizard/wizard_background.md`, `wizard_personality.md`, `src/cli/commands/character.py`

- **GO action loops back for scene building** - After player moves to new location, graph routes back to `world_mechanics` to build scene
  - New `route_after_state_validator()` checks `location_changed` flag (`src/agents/graph.py`)
  - World mechanics node clears `parsed_actions` on loop-back to prevent re-execution
  - Key file: `src/agents/graph.py`, `src/agents/nodes/world_mechanics_node.py`

- **GO action fuzzy location matching** - Location targets now use fuzzy matching instead of exact keys
  - `GMToolExecutor.execute_go()` uses `fuzzy_match_location()` (`src/agents/tools/executor.py`)
  - `ActionValidator` uses fuzzy matching for GO action targets (`src/validators/action_validator.py`)
  - Allows "go to well" to resolve to "family_farm_well"

- **Improved error messages in scene-first nodes** - Include location key for easier debugging
  - SceneBuilderNode, WorldMechanicsNode, PersistSceneNode now show location in errors

- **Scene-first routing skips world_mechanics** - Added check for missing `narrator_manifest` and LOOK actions (`src/agents/graph.py:route_after_parse_scene_first`)
- **CLI hardcoded starting_location** - `_single_turn()` now finds actual location from DB (`src/cli/commands/game.py`)
- **complete_structured returns dict not model** - Added `model_validate()` conversion in SceneBuilder and WorldMechanics
- **Missing FactManager.list_facts()** - Added method for complication oracle (`src/managers/fact_manager.py`)

- **Scene-First Architecture Phase 6: Reference Resolution** - Resolves player references to scene entities
  - New `ReferenceResolver` class resolves player text to entity keys (`src/resolver/reference_resolver.py`)
  - Cascade resolution: exact key → display name → pronoun → descriptor matching
  - Pronoun resolution with gender indexing (he/him → male NPCs, she/her → female NPCs)
  - `last_mentioned` context for disambiguating pronouns in conversation
  - Descriptor matching with scoring for partial matches ("the bartender" → bartender_001)
  - Ambiguity detection returns candidate list for clarification prompts
  - 26 tests covering all resolution strategies and edge cases
  - Key files: `src/resolver/reference_resolver.py`, `tests/test_resolver/test_reference_resolver.py`

- **Scene-First Architecture Phase 5: Constrained Narrator** - Validates and generates narration
  - New `NarratorValidator` class validates [key] references in narrator output (`src/narrator/validator.py`)
  - Extracts all [key] patterns and validates against manifest entities
  - Detects unkeyed entity mentions (display names without [key] format)
  - New `SceneNarrator` class generates constrained narration (`src/narrator/scene_narrator.py`)
  - Retry loop with error feedback for validation failures (max 3 attempts)
  - `_strip_keys()` removes [key] markers for player-facing display text
  - Fallback generation when validation keeps failing
  - 41 tests covering validation, narration generation, and key stripping
  - Key files: `src/narrator/validator.py`, `src/narrator/scene_narrator.py`

- **Scene-First Architecture Phase 4: Persistence Layer** - Persists scene contents to database
  - New `ScenePersister` class saves World Mechanics and Scene Builder output (`src/world/scene_persister.py`)
  - `persist_world_update()` creates NPCs from placements with full entity linkage
  - `persist_scene()` creates furniture and items with StorageLocation records
  - `build_narrator_manifest()` converts SceneManifest to NarratorManifest with EntityRefs
  - Furniture stored as Items with `furniture_type` property in PLACE-type StorageLocation
  - Items linked to location via `owner_location_id` for scene tracking
  - Atomic transactions - all or nothing persistence
  - 23 tests covering NPC/item/furniture creation and manifest building
  - Key files: `src/world/scene_persister.py`, `tests/test_world/test_scene_persister.py`

- **Scene-First Architecture Phase 3: Scene Builder** - Generates physical scene contents for locations
  - New `SceneBuilder` class for first-visit generation and return-visit loading (`src/world/scene_builder.py`)
  - `build_scene()` main entry point returns `SceneManifest` with furniture, items, NPCs, atmosphere
  - `_build_first_visit()` calls LLM to generate furniture, items, and atmosphere for new locations
  - `_load_existing_scene()` loads previously persisted scene from database (no LLM call needed)
  - `_merge_npcs()` combines NPCs from WorldUpdate with entity details from database
  - `_filter_by_observation_level()` filters items based on ENTRY/LOOK/SEARCH/EXAMINE levels
  - Fallback mode works without LLM provider using sensible defaults
  - Time-aware atmosphere generation based on current hour
  - Furniture stored as Items with `furniture_type` property (no separate enum needed)
  - Jinja2 prompt template for LLM scene generation (`data/templates/scene_builder.jinja2`)
  - 21 new tests covering first-visit, return-visit, NPC merging, observation levels
  - Key files: `src/world/scene_builder.py`, `tests/test_world/test_scene_builder.py`

- **Scene-First Architecture Phase 2: World Mechanics** - Core world simulation engine
  - New `WorldMechanics` class determines NPC presence at locations (`src/world/world_mechanics.py`)
  - `get_scheduled_npcs()` queries NPC schedules for time/day matching
  - `get_resident_npcs()` finds NPCs who live at a location
  - `get_npcs_at_location()` combines scheduled and resident NPCs
  - `check_placement_constraints()` validates physical and social constraints
  - `advance_world()` main entry point returns `WorldUpdate` with valid placements
  - `maybe_introduce_element()` validates new elements against constraints
  - `get_relationship_counts()` categorizes player relationships (close/casual/acquaintances)
  - Jinja2 prompt template for LLM integration (`data/templates/world_mechanics.jinja2`)
  - 25 new tests covering scheduled NPCs, residents, constraints, and time context
  - Key files: `src/world/world_mechanics.py`, `tests/test_world/test_world_mechanics.py`

- **Scene-First Architecture Phase 1: Schemas & Constraints** - Foundation for new world-first architecture
  - New `src/world/` module with Pydantic schemas for World Mechanics, Scene Builder, Narrator, and Resolution
  - 25 Pydantic models: `WorldUpdate`, `NPCPlacement`, `SceneManifest`, `NarratorManifest`, `EntityRef`, etc.
  - `RealisticConstraintChecker` class enforces social, physical, and event constraints
  - `SocialLimits` with personality-adjusted relationship caps (5 close friends, 15 casual, 50 acquaintances)
  - Physical constraints: visiting hours (7am-10pm), private location access, sleep hours
  - Event constraints: max 3/day, 2 intrusions/week, 2hr minimum between events
  - 93 tests in `tests/test_world/` covering all schemas and constraint logic
  - Key files: `src/world/schemas.py`, `src/world/constraints.py`

- **Discourse-Aware Reference Resolution** - Comprehensive system for pronoun and anaphoric reference resolution
  - New `DiscourseManager` class extracts entity mentions from GM responses using LLM (`src/managers/discourse_manager.py`)
  - Tracks mentions with descriptors, gender, groups, and contrast relationships
  - Resolves pronouns ("she" → Ursula), anaphoric references ("the other one" → guitar player)
  - Pre-computes pronoun candidates by gender for classifier context
  - Just-in-time entity spawning when player references unspawned mentions
  - New `mentioned_entities` JSON column on Turn model for structured tracking
  - Enhanced classifier context: 10 turns × 1000 chars (was 2 × 300)
  - Key files: `src/managers/discourse_manager.py`, `src/agents/nodes/subturn_processor_node.py`

### Fixed
- **Pronoun Conversion Breaking NPC References** - Fix "about her" (mother) becoming "about your"
  - Removed aggressive `his/her` → `your` replacement in `_convert_to_second_person()`
  - These pronouns often refer to third parties (NPCs, family) and converting breaks grammar
  - Added NARRATOR FACT VOICE instructions to planner: generate second-person directly
  - Updated 10+ planner examples to use "You recall..." instead of "Player recalls..."
  - Key files: `src/agents/nodes/info_formatter_node.py`, `src/planner/prompts.py`

- **Pronoun Resolution Lost Before Planner** - Pass resolved target from classifier to planner
  - Classifier now includes `resolved_target` in CUSTOM action parameters
  - Planner appends `[Note: pronoun refers to ursula]` when resolved_target exists
  - Fixes "where is she?" incorrectly resolving to backstory "mother" instead of recent "Ursula"
  - Key files: `src/parser/llm_classifier.py`, `src/planner/dynamic_action_planner.py`

- **Pronoun Resolution in Player Input** - Resolve "she/he/it/they" from conversation context
  - Added `recent_mentions` field to SceneContext for conversation history
  - Intent classifier now receives entities, items, and recent GM responses
  - Added `_build_scene_context()` helper to populate context from database
  - Planner prompt now includes explicit pronoun resolution guidance
  - Key files: `src/agents/nodes/parse_intent_node.py`, `src/planner/prompts.py`

- **Turn Counter Sync on Resume** - Sync `total_turns` with actual turn count when resuming
  - Guards against crashes or inconsistencies leaving turn counter out of sync
  - Key file: `src/cli/commands/game.py`

- **Snapshot Duplicate Key Error** - Prevent UniqueViolation when resuming game sessions
  - `capture_snapshot()` now checks for existing snapshot before insertion
  - Returns `None` if snapshot already exists for turn, avoiding duplicate key error
  - Key file: `src/managers/snapshot_manager.py`

- **Item Orphaning on Drop** - Items dropped by entities are now properly stored
  - Executor now uses `ItemManager.drop_item()` instead of manual DB updates
  - Fixed pre-existing bug: `ItemManager.drop_item()` referenced non-existent column
  - Items now get a proper `storage_location_id` pointing to a PLACE StorageLocation
  - Key files: `src/agents/tools/executor.py`, `src/managers/item_manager.py`

- **Plot Hook Crash on Max Retries** - Graceful fallback instead of game crash
  - When narrator can't incorporate plot hooks after 2 retries, items now spawn normally
  - Changed from error return to warning + fallback signal
  - Key file: `src/agents/nodes/narrative_validator_node.py`

- **Sleepiness Display Confusion** - Renamed to "Restfulness" with intuitive semantics
  - Display now shows "Restfulness" (high=good) instead of "Sleepiness" (inverted)
  - Thresholds: delirious < exhausted < tired < alert < well-rested
  - Key files: `src/cli/commands/character.py`, `src/cli/display.py`

- **Movement Pattern Not Matching "head out to"** - Extended regex pattern
  - Added optional "out" and "over" to movement pattern
  - Now matches "head out to the farm", "go over to the well", etc.
  - Key file: `src/parser/patterns.py`

- **"Moved to None" Errors** - Defensive handling for null destination
  - Action executor now handles null destination gracefully
  - Returns "Left the area" instead of crashing
  - Key file: `src/executor/action_executor.py`

### Added
- **Location Inhabitants Query** - Answer "Who works/lives here?" with habitual residents
  - New `get_location_inhabitants()` method in EntityManager queries NPCs by workplace/home_location
  - Walks location hierarchy (farmhouse_kitchen → family_farm) to find relevant NPCs
  - New query type 8 in planner prompts for inhabitant queries
  - `location_inhabitants` field added to RelevantState schema
  - NPCExtension now auto-populates `workplace` and `home_location` on generation
  - Residential occupations (farmer, innkeeper, etc.) get `home_location` set automatically
  - Key files: `src/managers/entity_manager.py`, `src/planner/prompts.py`

- **Realism Validation System** - Ensures game mechanics match real-world behavior
  - New `realism-principles.md` with conceptual principles across 4 domains
  - Domain-specific validators: physiology, temporal, social, physics
  - Unified `realism-validator` orchestrator for cross-domain checks
  - Mandatory validation during planning mode for game mechanics
  - Common realism pitfalls documented (merged needs, fixed durations, etc.)
  - Key files: `.claude/agents/*-validator.md`, `.claude/docs/realism-principles.md`

- **Dynamic Fatigue System** - Replaces single `energy` field with two-resource system
  - **Stamina** (0-100): Physical capacity, recovered by rest
    - Depleted by activity (combat -25/hr, running -40/hr, walking -8/hr)
    - Recovered by rest (+15/hr sitting, +25/hr lying, +50/hr sleeping)
    - Thresholds: Fresh (70+), Fatigued (50-69), Winded (30-49), Exhausted (10-29), Collapsed (0-9)
  - **Sleep Pressure** (0-100): Sleepiness, only cleared by sleep
    - Builds at +4.5/hr while awake (even during rest!)
    - Combat/stress increases to +6/hr
    - Only sleeping clears it (-12/hr)
    - Thresholds: Well-Rested (0-20), Alert (21-40), Tired (41-60), Exhausted (61-80), Delirious (81-95), Collapse (96+)
  - **Sleep Gating**: Can't sleep if pressure < 30 ("You're not tired enough to sleep")
  - **Dynamic Sleep Duration**: Hours = clamp((pressure - 30) / 10 + 1, 1, 10)
  - New `NeedsManager` methods: `can_sleep()`, `get_sleep_duration()`, `reduce_sleep_pressure()`, `check_forced_sleep()`
  - Updated REST action: Recovers stamina but sleep pressure still builds
  - Updated SLEEP action: Checks sleep gating, calculates duration, clears pressure
  - Database migration: `alembic/versions/40abf4bc66f1_replace_energy_with_stamina_sleep_.py`
  - Removes `energy` and `energy_craving` fields entirely

- **Response Mode Routing** - Two output pipelines for different player intents
  - **INFO mode** for factual queries (bypasses narrator, 5-20 words)
    - "What color is my shirt?" → "Light purple with brown stitching."
    - "Am I hungry?" → "You are quite hungry."
    - "Where am I?" → "The farmhouse kitchen."
  - **NARRATE mode** with style hints (full narrator, controlled verbosity)
    - OBSERVE: 2-4 sentences, sensory details
    - ACTION: 1-3 sentences, outcome focused
    - DIALOGUE: NPC speech with direct quotes
    - COMBAT: mechanical result + brief flavor
    - EMOTE: 1 sentence acknowledgment
  - New `ResponseMode` and `NarrativeStyle` enums in `src/planner/schemas.py`
  - New `info_formatter_node.py` for concise INFO responses
  - Graph routing based on `response_mode` after state validation
  - `ConstrainedNarrator` now accepts `style_instruction` parameter
  - Reduces verbose output for simple queries (100+ words → 5-20 words)

- **LLM-Based Item Extraction** - Replaces regex-based hallucination detection with LLM
  - New `ItemExtractor` class (`src/narrator/item_extractor.py`) using Claude Haiku
  - Classifies items by importance: IMPORTANT (bucket, washbasin), DECORATIVE (pebbles, dust), REFERENCE (talked about)
  - Eliminates false positives like "bewildering" being flagged as "ring"
  - Uses Pydantic models for structured LLM output

- **Story-Aware Spawn Decisions** - Complication Oracle now evaluates item spawning
  - New `ItemSpawnDecision` enum: SPAWN, DEFER, PLOT_HOOK_MISSING, PLOT_HOOK_RELOCATED
  - New `ItemSpawnResult` dataclass with reasoning, spawn_location, plot hooks
  - `ComplicationOracle.evaluate_item_spawn()` for intelligent spawn decisions
  - Creates narrative opportunities: missing items become mysteries, relocated items become quests

- **Deferred Item Spawning** - Decorative items tracked for on-demand spawning
  - New `Turn.mentioned_items` field stores deferred items per turn
  - New `TurnManager` class with `get_mentioned_items_at_location()` method
  - `ActionValidator` checks deferred items when real item not found
  - Player can reference decorative items mentioned in narrative → spawned on demand
  - `DynamicActionPlanner._get_visible_location_items()` now includes deferred items
  - `ActionExecutor._spawn_deferred_item()` spawns items before action execution
  - Fixes issue where narrator didn't know about deferred items at location

- **LLM-Based Location Extraction** - Automatic world-building from narrative
  - New `LocationExtractor` class (`src/narrator/location_extractor.py`) using Claude Haiku
  - Extracts named places from narrative: "the well behind the farmhouse" → location with parent
  - Categories: wilderness, settlement, establishment, interior, exterior, public
  - Infers parent-child hierarchy from context
  - Locations created immediately when narrative mentions them

- **Item Location Context** - Items now extracted with their mentioned location
  - `ExtractedItem.location` field now REQUIRED (never null, always inferred from context)
  - New `ExtractedItem.location_description` field for precise placement ("on the shelf", "by the well")
  - Context-aware location inference: "wash at the well using a washbasin" → washbasin at the well
  - `ItemExtractor.extract()` now accepts `current_location` for default placement
  - "bucket at the well" → item with location="the well", location_description="by the well"
  - `LocationManager.resolve_or_create_location()` matches text to existing or creates new
  - `LocationManager.fuzzy_match_location()` finds locations by partial name match
  - Deferred items now have correct location (not player's current location)
  - Ensures consistency: items don't mysteriously move between visits

- **Database Reference Documentation** - `.claude/docs/database-reference.md`
  - Connection details from .env
  - Table schemas for key tables (turns, entities, items, locations, etc.)
  - Common query examples

- **Plot Hook System** - Missing/relocated items create narrative hooks
  - PLOT_HOOK_MISSING: Item mysteriously absent → triggers re-narration with constraints
  - PLOT_HOOK_RELOCATED: Item spawned at alternate location → creates quest hook
  - New facts recorded for world state consistency

- **Intelligent Hallucination Handler** (DEPRECATED categorization) - Smart handling of narrator hallucinations
  - New `HallucinationHandler` module (`src/narrator/hallucination_handler.py`)
  - Categorizes hallucinated items: SPAWN_ALLOWED (washbasin, bucket) vs SPAWN_FORBIDDEN (dragon, gold)
  - Reasonable environmental items are spawned to make narrative valid (no re-narration needed!)
  - Dangerous items (threats, valuables, NPCs) trigger re-narration with constraints
  - Philosophy: Like a GM who says "actually yeah, there would be a washbasin there"
  - Note: `categorize_item()` and `analyze_hallucinations()` deprecated in favor of ItemExtractor

- **Unified Detail Enrichment System** - Players can ask about any missing details and get consistent answers
  - `ENRICH` pattern in planner prompts for generating + persisting missing details
  - Supports item properties (color, material, texture), location details (floor, lighting, smells),
    world facts (currency, customs, weather), NPC details (accent, scars), and personal knowledge
  - New `RelevantState` fields: `location_details`, `world_facts`, `recent_actions`
  - New gathering methods in `DynamicActionPlanner`: `_get_location_details()`, `_get_world_facts()`, `_search_recent_actions()`
  - Updated `PLANNER_USER_TEMPLATE` with "Already Established Details" section
  - Fixed executor to pass `subject_type` when recording facts
  - Covers 100% of 150 tested player questions (sensory, physical, personal, world knowledge)

- **Personal Knowledge Establishment** - Players can now ask about things their character would know
  - `ESTABLISH_KNOWLEDGE` pattern in planner prompts for personal/routine knowledge
  - Uses `StateChangeType.FACT` to create knowledge that "should exist" for the character
  - Examples: "Where do I wash?", "Where do I sleep?", "Where is the bucket kept?"
  - Similar to `SPAWN_ITEM` but for knowledge instead of items

- **Turn History Search** - Recent memory queries now search actual turn history
  - `_search_recent_actions()` method searches past 20 turns for relevant actions
  - "What did I eat for breakfast?" finds actual EAT actions from history
  - Falls back to establishing reasonable defaults if no history found

- **Game History & Reset System** - Complete session state management with snapshots
  - New `game history` command shows turn history in table/panel format
  - New `game reset` command restores session to any previous turn state
  - New `SnapshotManager` class (`src/managers/snapshot_manager.py`) for state capture
  - Session snapshots capture all tables at each turn for full restoration
  - Database migration for snapshot tables (`session_snapshots`, `snapshot_data`)

- **NPC Extraction & Deferred Spawning** - Dynamic NPC generation from narrative
  - New `NPCExtractor` class (`src/narrator/npc_extractor.py`) classifies NPCs by importance
  - Importance levels: CRITICAL, SUPPORTING, BACKGROUND, REFERENCE
  - Named/critical NPCs spawn immediately with full `EmergentNPCGenerator`
  - Background NPCs defer to `Turn.mentioned_npcs` for on-demand activation
  - `ComplicationOracle.evaluate_npc_spawn()` makes intelligent spawn/defer decisions
  - Mirrors item extraction pattern for consistent entity handling

- **Subturn Processor** - Handles chained multi-action turns with interrupt support
  - New `SubturnProcessor` class (`src/executor/subturn_processor.py`)
  - Processes action chains within single turn
  - Interrupt handling for failed actions (stops chain, reports partial completion)
  - Supports multi-step player commands like "go to X and talk to Y"

### Changed
- **Narrative Validator Redesign** - Complete rewrite using LLM-based detection
  - Replaced regex-based item detection with LLM extraction (no more false positives)
  - New async `validate_async()` method in `NarrativeValidator` class
  - `narrative_validator_node` now uses `ItemExtractor` and `ComplicationOracle`
  - Story-aware spawn decisions replace simple spawn/reject binary

- **Stricter Narrator Constraints** - Reduced hallucination in narrative output
  - Enhanced `NARRATOR_TEMPLATE` with explicit "DO NOT HALLUCINATE" rules
  - Updated `LOOK_PROMPT` and `LOOK_SYSTEM` to only reference provided context
  - Narrator now only mentions items that appear in mechanical facts

### Fixed
- **Snapshot Restore FK Ordering** - Fixed `rpg game reset` failing with foreign key violations
  - `SESSION_SCOPED_MODELS` ordering was incorrect: `Item` and `StorageLocation` were listed after `Location`
  - When reversed for insert, this caused `Item.owner_location_id` to reference non-existent `Location` rows
  - Reordered to: `Item`, `StorageLocation`, `Location`, `Entity`, `TimeState` (children before parents)
  - Added per-model-type `flush()` to enforce insertion order (SQLAlchemy was reordering inserts)
  - Key file: `src/managers/snapshot_manager.py`

- **Turn Timestamps Not Populated** - Turns now record game day and time
  - `Turn.game_day_at_turn` and `Turn.game_time_at_turn` were always NULL
  - Now populated from `TimeState` when turns are saved
  - Both `_save_turn_immediately()` and `_create_turn_record()` set these fields
  - Stores end-of-turn time (after action execution)

- **Pronoun Handling in INFO Mode** - Correct pronoun usage for character gender
  - INFO mode responses now use correct pronouns (he/she/they) based on character data
  - Fixed inconsistent pronoun usage in concise responses

- **Occupation NPC Generation** - Improved occupation-based attribute inference
  - NPC attributes now correctly reflect occupation modifiers
  - Fixed attribute calculation for occupation years and lifestyle tags

- **StateIntegrityValidator Type Error** - Fixed crash when auto-fixing orphaned items
  - `_check_item_ownership()` tried to set `storage_location_id = "unknown"` (a string)
  - But `storage_location_id` is an integer foreign key, causing `InvalidTextRepresentation` error
  - Now assigns orphaned items to player as holder instead of invalid storage location

- **Environmental Items Missing Ownership** - Items spawned from narrative had no owner
  - `EmergentItemGenerator._persist_item()` didn't set `owner_location_id` for environmental items
  - Items at locations (e.g., bucket at well) now properly owned by the Location
  - `StateIntegrityValidator` now also checks `owner_location_id` as valid ownership

- **INFO Responses Not Deferring Items** - Items mentioned in INFO responses were never spawnable
  - INFO mode bypassed `narrative_validator_node` entirely, so items weren't extracted
  - Added item extraction to `info_formatter_node` with deferred item registration
  - Items like "bucket and washbasin" mentioned in INFO responses now get deferred
  - Added `TurnManager.get_all_mentioned_items()` fallback for cross-location lookup
  - `ActionValidator._find_deferred_item()` now checks ALL deferred items as fallback

- **Items Deferred at Wrong Location** - "bucket at the well" was saved at player's location
  - Both `info_formatter_node` and `narrative_validator_node` used `player_location` for all items
  - Now extracts actual location from narrative context using `ItemExtractor.location` field
  - Creates location if it doesn't exist via `LocationManager.resolve_or_create_location()`
  - Deferred items now correctly placed at their mentioned location (e.g., bucket → farmhouse_well)

- **Deferred Items Not Persisted** - Fixed `Turn.mentioned_items` never being saved
  - `persistence_node._create_turn_record()` now persists `deferred_items` from state to `Turn.mentioned_items`
  - Decorative items marked for on-demand spawning (like "wooden bucket") are now properly stored
  - Players can now reference items mentioned in narrative that were deferred for later spawning

- **LLM-Based Item Extraction Never Used** - Fixed `narrative_validator_node` falling back to regex
  - The node expected `_llm_provider` from state but it was never set
  - Changed to use `get_extraction_provider()` directly (like other nodes)
  - LLM-based `ItemExtractor` now properly used to avoid false positives
  - Prevents regex from incorrectly flagging verbs ("mirror") and body parts ("chest") as items

- **ItemExtractor Response Parsing** - Fixed JSON parse error in item extraction
  - `ItemExtractor` used `response.text` but `LLMResponse` has `content` attribute
  - Changed to use `response.content` for correct text extraction

- **Narrator Fact Extraction for Dynamic Plans** - Fixed "Fact may be missing" errors for enrichment queries
  - `_extract_facts()` now distinguishes between dynamic plans (with narrator_facts) and regular actions
  - For dynamic plans, only `narrator_facts` from metadata are used for validation, not raw state_changes
  - Raw state_changes like `"player.routine_knowledge: None -> ..."` are internal db operations, not narration facts
  - Regular actions (without narrator_facts) continue to use outcome and state_changes as before
  - Skip "Attempted:" and "[VALIDATED:" fallback outcomes that don't need narration validation
  - This fixes false validation warnings when using the ENRICH/ESTABLISH_KNOWLEDGE patterns

- **DynamicActionPlan Parsing** - Handle LLM response with 'input' wrapper
  - Added handling for case where LLM wraps structured response in extra `{'input': {...}}` layer
  - Extracts the actual plan content from the wrapper to prevent validation errors

- **Narrative Validator False Positives** - Common words no longer flagged as hallucinations
  - Fixed regex to only match words ENDING with item suffixes (not containing them)
  - "contemplate" no longer flagged as "plate", "dragon" no longer matches "rag"
  - Added verbs ending with item suffixes: "contemplate", "bring", "think", "overlook", etc.
  - Added clothes, rooms, and adjectives to common words list
  - Added seasons/time words: "spring", "summer", "morning", "evening", etc.
  - Added action verbs: "preparing", "searching", "looking", "finding"
  - Added descriptors: "somewhat", "refreshing", "clear", "cold", "warm"

- **Autonomous World Generation & Narrative Validation** - Two-layer system for grounded narratives
  - `SPAWN_ITEM` state change type in `DynamicActionPlanner` for autonomous item creation
  - `SpawnItemSpec` schema for specifying emergent items (item_type, context, display_name, quality, condition)
  - Enhanced planner prompts with world generation rules (when to spawn contextually appropriate items)
  - Enhanced planner prompts with grounding rules (only reference items that exist or are being spawned)
  - `NarrativeValidator` class for post-narration validation against known game state
  - `narrative_validator_node` in graph pipeline with conditional re-narration routing
  - Max 2 re-narration attempts with strict constraints on retry
  - New state fields: `spawned_items`, `narrative_retry_count`, `narrative_validation_result`, `narrative_constraints`
  - Executor integration with `EmergentItemGenerator` for rich item creation

- **System-Authority Architecture (Phase 1 & 2)** - New game loop ensuring mechanical consistency
  - Refactored from "LLM decides what happens" to "System decides, LLM describes"
  - Guarantees no state/narrative drift - if narrative says player has item, inventory has item

  **Phase 1 - Foundation:**
  - `ActionValidator` with 33 action types for mechanical validation
  - `ActionExecutor` with full manager integration for state changes
  - Fixed UNEQUIP validator to use `get_equipped_items()` instead of `get_inventory()`
  - Implemented `_is_in_combat()` with `combat_active` parameter
  - Added separate ASK/TELL validators requiring `indirect_target`
  - Added `delete_item()` to ItemManager for consumables
  - Integrated `DeathManager.take_damage()` for combat damage with HP tracking
  - Connected `RelationshipManager` to PERSUADE/INTIMIDATE with skill checks
  - Connected `TimeManager` to REST/WAIT/SLEEP for time advancement
  - Connected `NeedsManager` to EAT/DRINK/SLEEP for need satisfaction
  - Added new GameState fields: `parsed_actions`, `ambient_flavor`, `validation_results`, `turn_result`

  **Phase 2 - LangGraph Integration:**
  - New `parse_intent_node` - Converts player input to structured actions
  - New `validate_actions_node` - Validates actions mechanically
  - New `execute_actions_node` - Executes valid actions, produces results
  - New `narrator_node` - Generates constrained prose from facts
  - New `ConstrainedNarrator` class in `src/narrator/` module
  - New `build_system_authority_graph()` function for the new pipeline
  - Linear flow: context_compiler → parse_intent → validate_actions → execute_actions → narrator → persistence

  **Phase 3 - Complication Oracle:**
  - New `src/oracle/` module for creative complication generation
  - `ComplicationType` enum: discovery, interruption, cost, twist
  - `EffectType` enum: hp_loss, hp_gain, resource_loss, status_add, reveal_fact, spawn_entity, etc.
  - `Effect` dataclass with serialization (to_dict/from_dict)
  - `Complication` dataclass with mechanical effects, new facts, foreshadowing
  - `ProbabilityCalculator` with configurable base chance, max chance, and cooldown
    - Risk tag modifiers (dangerous: +10%, mysterious: +8%, forbidden: +12%, etc.)
    - Arc phase modifiers (climax: +15%, escalation: +10%, setup: +2%)
    - Arc tension modifier (>50 tension adds up to +5%)
    - Cooldown system to prevent complication spam (3-turn full cooldown, 6-turn recovery)
    - Hard cap to never exceed max probability (default 35%)
  - `ComplicationOracle` class with LLM and fallback generation
    - Integrates with `StoryArcManager` for narrative context
    - Integrates with `FactManager` for world facts
    - `get_turns_since_complication()` for cooldown tracking
    - `record_complication()` persists to database and records new facts
  - New `ComplicationHistory` database model for tracking complications
  - New `complication_oracle_node` for the LangGraph pipeline
  - Updated `GameState` with `complication` field
  - Updated narrator to include complications in fact extraction
  - Pipeline flow updated: validate_actions → **complication_oracle** → execute_actions
  - New prompt template: `data/templates/complication_generator.md`
  - Unit tests: `tests/test_oracle/` with probability, types, and oracle tests

  **Phase 4 - Dynamic Action Planner:**
  - New `src/planner/` module for transforming CUSTOM actions into structured plans
  - `DynamicActionType` enum: state_change, recall, narrative_only
  - `StateChangeType` enum: item_property, entity_state, fact, knowledge_query
  - `StateChange` dataclass for atomic state modifications
  - `DynamicActionPlan` dataclass with narrator_facts, state_changes, roll requirements
  - `DynamicActionPlanner` class with LLM-powered plan generation
    - Gathers current state (inventory, equipped items, known facts, entity state)
    - Calls LLM with structured output schema
    - Returns mechanical execution plan
  - New `dynamic_planner_node` for the LangGraph pipeline
  - New `temporary_state` JSON column on Entity model for transient state
  - `ItemManager.update_item_property()` for modifying item properties
  - `ItemManager.get_item_property()` for reading item properties
  - `EntityManager.update_temporary_state()` for entity transient state
  - `EntityManager.get_temporary_state()` for reading entity state
  - `EntityManager.clear_temporary_state()` for clearing transient state
  - Updated `ActionExecutor._execute_custom()` to use dynamic plans
  - Added `_apply_state_change()` helper for applying plan changes
  - Pipeline flow: validate_actions → **dynamic_planner** → complication_oracle

  **Phase 4b - Comprehensive Player Query System:**
  - Updated `CLASSIFIER_SYSTEM_PROMPT` to route player queries (memory, inventory, state, perception, possibility, relationship, location) as CUSTOM actions
  - Expanded `RelevantState` schema with 8 new fields for comprehensive queries:
    - `character_needs`: hunger/thirst/energy/wellness (0=critical, 100=satisfied)
    - `visible_injuries`: injuries on exposed body parts only
    - `character_memories`: emotional memories (subject, emotion, context)
    - `npcs_present`: NPCs with VISIBLE info only (appearance, mood, visible equipment)
    - `items_at_location`: items on surfaces (not in closed containers)
    - `available_exits`: exits with accessibility info (blocked_reason, access_requirements)
    - `discovered_locations`: location keys player has visited
    - `relationships`: attitudes toward NPCs player has MET (knows=True only)
  - Added 10+ helper methods to `DynamicActionPlanner` for visibility-filtered data gathering:
    - `_get_character_needs()`, `_get_visible_injuries()`, `_get_character_memories()`
    - `_get_visible_npcs()`, `_get_visible_equipment()`, `_get_visible_location_items()`
    - `_get_available_exits()`, `_get_discovered_locations()`, `_get_known_relationships()`
  - Updated `PLANNER_SYSTEM_PROMPT` with detailed query handling instructions
  - Updated `PLANNER_USER_TEMPLATE` to include all new state fields
  - Updated `dynamic_planner_node` to pass `actor_location` to the planner
  - Enforces information boundaries:
    - NPC secrets (hidden_backstory, dark_secret) never revealed
    - Only visible equipment layers shown (is_visible=True)
    - Relationships only for NPCs player has met (knows=True)
    - Only discovered locations shown
    - Secret facts excluded (is_secret=True)

  **Phase 5 - State Integrity Validator:**
  - New `src/validators/state_integrity_validator.py` module
  - `StateIntegrityValidator` class with auto-fix capabilities
  - `ValidationReport` and `IntegrityViolation` dataclasses
  - Entity checks: NPC locations, required fields
  - Item checks: ownership/location, duplicate body slots
  - Relationship checks: orphaned refs, self-relationships
  - Auto-fix mode: sets NPC locations to "unknown", fixes item ownership
  - New `state_validator_node` for the LangGraph pipeline
  - Pipeline flow: execute_actions → **state_validator** → narrator

  **Phase 4 - Migration & Cleanup:**
  - Added `--pipeline` option to CLI commands: `rpg game start`, `rpg game play`, `rpg game turn`
    - `system-authority` (default): New pipeline with guaranteed mechanical consistency
    - `legacy`: Old LLM-decides-everything flow for backward compatibility
  - Added deprecation notices to legacy nodes:
    - `game_master_node.py` - Now marked as deprecated, recommends System-Authority flow
    - `entity_extractor_node.py` - No longer needed with System-Authority (executor handles state)
  - Updated `graph.py` module docstring documenting both pipeline options
  - System-Authority is now the default for all new games

- **Unit Tests for System-Authority:**
  - `tests/test_validators/test_action_validator.py` - 15+ tests for validation logic
  - `tests/test_executor/test_action_executor.py` - 15+ tests for execution logic

- **Signal-Based Needs Communication System** - Prevents repetitive need narration ("stomach growls" every turn)
  - New `NeedsCommunicationLog` database model tracks when needs were last communicated to the player
  - New `NeedsCommunicationManager` with state tracking, alert generation, and reminder logic
  - Context compiler now generates categorized needs alerts:
    - **Alerts**: State changes (e.g., hunger dropped to "hungry") - always narrate these
    - **Reminders**: Ongoing negative states not mentioned for 2+ in-game hours - consider mentioning
    - **Status**: Reference-only information for GM awareness
  - New `mark_need_communicated` GM tool to record when a need was narrated
  - GM prompt updated with "Needs Narration Guidelines" section explaining the system
  - Added 17 unit tests for the communication manager
  - Fixes repetitive need narration that annoyed players

- **GM Needs Awareness - Positive States** - GM now receives information about positive need states
  - Context compiler reports "well-fed" when hunger > 85, "well-rested" when energy > 80
  - Reports "clean" when hygiene > 80, "comfortable" when comfort > 80
  - Reports "in good spirits" when morale > 80, "socially fulfilled" when social > 80
  - Reports "healthy" when wellness > 90, "content" when intimacy > 80
  - Fixes issue where GM would assume hunger when player was full (hunger=85+)
  - Added 7 unit tests for positive/negative state descriptors

- **Negative Action Types for Needs** - GM can now decrease needs for adverse events
  - Hygiene: sweat (-10), get_dirty (-15), mud (-25), blood (-20), filth (-35), sewer (-40)
  - Comfort: cramped (-10), uncomfortable (-15), get_wet (-20), get_cold (-20), freezing (-30)
  - Social: snub (-10), argument (-15), rejection (-25), betrayal (-40), isolation (-20)
  - Intimacy: rebuff (-10), romantic_rejection (-20), heartbreak (-40), loneliness (-15)
  - Thirst: salty_food (-10), vomit (-25), heavy_exertion (-20)
  - Updated GM prompt template with negative action documentation
  - Updated satisfy_need tool description to explain negative actions
  - Added 6 unit tests for negative action types

- **GM World Spawning Tools** - GM can now create furniture and items in the world that appear in `/nearby`
  - `spawn_storage` tool: Creates storage surfaces (table, shelf, chest, counter, barrel, etc.) at current location
  - `spawn_item` tool: Places interactable items on storage surfaces (requires surface to exist first)
  - Both tools auto-generate unique keys and link to current Location via `world_location_id`
  - Items appear correctly grouped by surface in `/nearby` command output
  - Added 10 unit tests for spawn tool definitions and executors
- **Location Inventory Context for GM** - GM now sees existing storage and items when describing scenes
  - New `_get_location_inventory_context()` method in `ContextCompiler`
  - Shows storage surfaces (tables, shelves, etc.) at current location with their contents
  - Shows detailed item list with keys, descriptions, and placement
  - Prevents GM from duplicating existing items or describing "phantom" items
  - Added to `SceneContext.location_inventory_context` field
  - Added 6 unit tests for inventory context compilation
- **World Creation Rules in GM Prompt** - Clear instructions for the describe-then-spawn workflow
  - "Location Inventory Awareness" section explains checking existing items first
  - "Spawning Furniture" section with `spawn_storage` examples
  - "Spawning Items" section with clear ✅/❌ examples of what to spawn vs skip
  - "Describe-Then-Spawn Workflow" step-by-step guide
  - "Don't Duplicate" section to prevent phantom items

- **Full NPC Generation for Backstory Characters** - Family/friends from character creation now get full NPC data
  - Enhanced `world_extraction.md` template with relationship_role, relationship_context, age, gender, occupation, personality_traits, brief_appearance
  - Added `create_backstory_npc()` method in `EmergentNPCGenerator` that creates complete NPCs with:
    - Full appearance (height, build, hair, eyes, skin, clothing)
    - Background with relationship-aware summary (e.g., "Younger Brother of Kieran. Idolizes the player...")
    - Personality traits from extraction plus generated flaws/quirks
    - Starting needs (hunger, thirst, energy, social, intimacy) with age-appropriate defaults
    - Preferences (food, drink, social, physical attraction)
    - Attributes (STR, DEX, etc.) and skills
  - Updated `_create_world_from_extraction()` in character.py to use full generation instead of shadow entities
  - Added 6 unit tests for backstory NPC generation
- **Attribute Re-roll in Character Wizard** - Players can now re-roll their attributes during character creation
  - Added `reroll_attributes` JSON output support in `wizard_attributes.md` template
  - Handler in character wizard clears `potential_stats` and triggers fresh dice roll
  - Maintains age/occupation modifiers while re-rolling innate potential

- **Layered Context Summary System** - Prevents repetitive narration and improves narrative continuity
  - New database models: `Milestone`, `ContextSummary`, `NarrativeMentionLog`
  - Three-layer context architecture:
    - **Story Summary**: From start to last milestone (LLM-generated, updated at milestones only)
    - **Recent Summary**: From last milestone to last night (LLM-generated, updated once per in-game day)
    - **Today's Turns**: Full raw text since last night (no truncation, typically 5-15 turns)
  - New `MilestoneManager` for tracking story milestones (arc phase changes, quest completions, etc.)
  - New `SummaryManager` with LLM prompts for generating narrative summaries
  - New `NarrativeMentionManager` for tracking what conditions have been mentioned to prevent repetition
  - Integrated into `ContextCompiler` with new fields: `story_summary`, `recent_summary`, `turns_since_night`, `stable_conditions`
  - Updated `ConstrainedNarrator` template with repetition avoidance rules
  - Fixes issue where GM would repeatedly describe stable conditions (e.g., "disheveled appearance") every turn
  - Database migration: `929cfa212ff9_add_context_summary_models.py`

### Changed
- **Documentation Updates** - Updated README.md and user-guide.md to reflect current state
  - Fixed incorrect CLI commands in README.md Quick Start (`rpg start` → `rpg game start`)
  - Added missing commands to user-guide.md: `/location`, `/nearby`, `/portrait`, `/scene`, action commands
  - Added `--pipeline` flag documentation for System-Authority vs Legacy pipelines
  - Expanded installation instructions with prerequisites and virtual environment setup
  - Reorganized Special Commands section into logical categories
- **Stats-Derived Build** - Character physical build now auto-derived from calculated attributes
  - Added `infer_build_from_stats()` function to `attribute_calculator.py`
  - Removed `build` from required NAME section fields (now optional)
  - Build auto-set when attributes are finalized: high STR → "muscular", high DEX → "lean and agile", etc.
  - Ensures appearance consistency with actual stats (no more "lean agile" with STR 16, DEX 11)
- **Outfit Command Visual Details** - `/outfit` now shows clothing color and material inline
  - Format: `Simple Tunic (faded blue linen)` instead of just `Simple Tunic`
  - Extracts visual properties from `item.properties["visual"]` if available

### Fixed
- **Character Wizard Background Confirmation Bypass** - Fixed bug where BACKGROUND/PERSONALITY sections completed without user confirmation
  - Root cause: When background was saved via `field_updates` in a previous turn, `already_saved` check passed and `newly_added` was empty, skipping confirmation
  - Fix: Added special handling for content-heavy sections (BACKGROUND, PERSONALITY) that always requires user confirmation before completing
  - Now shows "Say 'ok' to confirm, or provide changes" even when field was previously saved
- **No Current Value When Revisiting Wizard Section** - Fixed bug where revisiting Background/Personality sections showed only the header
  - Root cause: `_run_section_conversation()` only displayed `display_section_header(title)` with no content preview
  - Fix: Added display of current saved value in a Panel when entering sections that already have content
  - Now shows "Current background:" with the full text before prompting for input
- **Character Occupation Not in Opening Scene** - Fixed bug where player occupation was ignored in game opening
  - Root cause: `ContextCompiler._get_player_context()` omitted occupation from player context passed to GM
  - Fix: Added occupation (with years if set) to player context after appearance section
  - Example: "- Occupation: farmer (3 years)"
- **Character Wizard eye_color Not Saved** - Fixed bug where eye color was displayed in narrative but not saved
  - Root cause: LLM mentions "hazel eyes" in text but omits `eye_color` from JSON `field_updates`
  - Fix: Added `_extract_missing_appearance_fields()` fallback extractor that parses eye/hair color from narrative when missing from JSON
  - Applied only to NAME section where these fields are required
  - Added 7 unit tests for the extraction logic
- **Turn Entity Extraction Not Persisted** - Fixed bug where `Turn.entities_extracted` was NULL for turns 15+
  - Root cause: `persistence_node.py:_create_turn_record()` only set `entities_extracted` when updating existing turns, not when creating new ones
  - Fix: Added `entities_extracted` and `location_at_turn` fields to Turn creation (line 481-482)
  - Also added `db.flush()` after updating existing turns to ensure visibility (line 473)
  - Added regression test `TestTurnPersistence::test_entities_extracted_persisted_on_turn_record`
- **Session 72 Data Corrections** - Manual SQL fixes for game state issues:
  - Moved `porridge_bowl` from player's hand to table (storage_location_id=19)
  - Fixed location hierarchy: `weary_traveler_inn`, `henrik_forge`, `baker_shop` now correctly parented to `village`
  - Fixed turn 21 location: `inn_common_room` → `village_square` (player had exited inn)

### Changed
- **GM Prompt Location Guidance** - Added "Location Changes" section to `data/templates/game_master.md`
  - Clear instructions for when to use `location_change` in STATE block
  - Examples: exiting buildings, entering buildings, traveling between areas
  - Emphasizes that location tracking depends on this signal

### Added
- **Phase 2 GM Tools: Quest, Fact, and NPC Management** - New tools for comprehensive game state management
  - **Quest Tools**: `assign_quest`, `update_quest`, `complete_quest` for quest lifecycle management
  - **World Fact Tool**: `record_fact` for SPV (Subject-Predicate-Value) world knowledge tracking
  - **NPC Scene Tools**: `introduce_npc` (creates/updates NPC with initial relationship), `npc_leaves` (updates NPC location)
  - All tools integrated into GMToolExecutor with proper validation
  - Added 13 new tests (3 definition + 10 executor) for Phase 2 tools
- **Player Action Commands with Pre-Validation** - New slash commands that validate before GM invocation
  - **`/go <place>`** - Movement command with validation context for GM
  - **`/take <item>`** - Pickup with weight and slot validation; rejects if inventory full
  - **`/drop <item>`** - Drop with inventory check; rejects if item not possessed
  - **`/give <item> to <npc>`** - Give with inventory validation
  - **`/attack <target>`** - Combat initiation with validation context
  - **Smart Hybrid Input**: Both slash commands AND natural language (e.g., "pick up the sword") are detected and validated
  - **Immediate Feedback**: Invalid actions return errors instantly without waiting for GM response
  - **Enhanced Input**: Valid actions pass `[VALIDATED: ...]` context to GM for reliable tool invocation
  - Added 20 new tests for action detection and validation (`TestActionCommandDetection`, `TestActionCommandValidation`)
  - Updated `/help` command to show new action commands
- **Tool-Based State Management** - New GM tools to replace fragile STATE block parsing
  - **`advance_time`** - Explicitly advance game time (1-480 minutes) with automatic TimeState update
  - **`entity_move`** - Move player or NPCs to locations; player moves update game state, NPC moves update NPCExtension
  - **`start_combat` / `end_combat`** - Combat lifecycle management with enemy validation and outcome tracking
  - **`pending_state_updates`** mechanism in GMToolExecutor for reliable state propagation
  - Tool-based updates take precedence over STATE block parsing (kept as fallback)
  - Updated `game_master.md` template with tool usage instructions
  - Comprehensive unit tests for all new tools and integration tests for state propagation
- **Enhanced Inventory & Storage System** - Comprehensive item ownership, theft tracking, and container management
  - **Theft Tracking**: Items now track `is_stolen` (active), `was_ever_stolen` (historical), `stolen_from_id`, `stolen_from_location_id`, and `original_owner_id` for provenance
  - **Location Ownership**: Items and storage can be owned by locations (e.g., inn's bowls) via `owner_location_id`
  - **Container-Item Linking**: Containers (backpacks, pouches, chests) are both Items and StorageLocations linked via `container_item_id`
  - **Portability System**: Storage has `is_fixed` (immovable) and `weight_to_move` (strength check required) for realistic movement
  - **Weight Capacity**: Containers track both item count (`capacity`) and weight limit (`weight_capacity`)
  - **Temporary Surfaces**: Tables, floors, and counters created dynamically and auto-cleaned when empty
  - **ItemManager Methods**: `steal_item()`, `return_stolen_item()`, `legitimize_item()`, `create_container_item()`, `put_in_container()`, `get_container_remaining_capacity()`, `create_temporary_surface()`, `get_or_create_surface()`, `cleanup_empty_temporary_storage()`
  - **New StorageManager**: Dedicated manager for storage hierarchy and portability
    - `can_move_storage()`, `get_move_difficulty()` - portability checking
    - `get_storage_hierarchy()`, `get_nested_contents()`, `get_child_storages()` - hierarchy navigation
    - `nest_storage()`, `unnest_storage()` - container nesting operations
    - `get_all_storages_at_location()`, `move_storage_to_location()` - location management
  - **Integration Tests**: 10 workflow tests covering theft lifecycle, container nesting, temporary surfaces, and portability
  - **Alembic Migration**: `25d0fb8756ad_add_theft_tracking_and_storage_enhancements.py`
- **Session 72 Migration Script** - Data migration script to align legacy game data with new inventory system
  - `scripts/migrate_session_72.py` - Creates Location records, StorageLocations (ON_PERSON, CONTAINER, PLACE), fixes item ownership
  - Demonstrates full inventory system capability: location hierarchies, container-item linking, location ownership
  - Idempotent script (can be re-run safely, checks for existing records)
- **Tool-Based Item Acquisition System** - GM now uses `acquire_item` and `drop_item` tools for inventory management
  - Validates slot availability before item pickup (hands full, belt full, etc.)
  - Validates weight limits before acquisition (too heavy to carry)
  - Auto-assigns items to appropriate slots based on item type and size
  - Returns immediate feedback to GM for narrative integration ("Your hands are full")
  - Added `ItemManager.check_slot_available()`, `get_item_in_slot()`, `get_total_carried_weight()`, `can_carry_weight()`, `find_available_slot()`, `get_inventory_summary()` methods
  - Added `ACQUIRE_ITEM_TOOL` and `DROP_ITEM_TOOL` definitions to `gm_tools.py`
  - Added `_execute_acquire_item()` and `_execute_drop_item()` handlers to `executor.py`
  - Updated GM prompt with item acquisition instructions
- **In-Game Image Prompt Commands** - New `/scene` and `/portrait` commands generate FLUX.1-dev image prompts during gameplay
  - `/scene [pov|third] [photo|art]` - Generate scene image prompt from current location
  - `/portrait [base|current] [photo|art]` - Generate character portrait prompt
  - Uses LLM to intelligently condense game state to ~60 tokens (CLIP limit)
  - Added `src/services/image_prompt_generator.py` - LLM-based prompt generation service
  - Added `data/templates/image_prompt.md` - System prompt for LLM
  - Added `rpg scene dump` and `rpg scene portrait` CLI commands for debugging
- **Species-Specific Gender Options** - Genders are now defined per species in setting configurations
  - Added `SpeciesDefinition` dataclass to `src/schemas/settings.py` with `name` and `genders` fields
  - Updated all setting JSON files to use the new species object format
  - Different species can have different genders (e.g., Androids have "None", "Male-presenting", "Female-presenting")
  - Backward compatible: legacy string format still supported
  - Updated wizard template to show species-specific gender options

### Fixed
- **Duplicate Entity Creation** - Fixed bug where the same NPC could be created multiple times with different `entity_key` values (e.g., "village_woman_elara" and "elara" for the same person). Added `EntityManager.get_entity_by_display_name()` method for case-insensitive lookup and added secondary check in `_persist_entity()` to prevent creating entities when one with the same display name already exists.
- **Turn entities_extracted Always Null** - Fixed bug where the `entities_extracted` JSON field on Turn records was never populated even when entity extraction succeeded. Changed condition from truthy check (`if state.get(...)`) to key presence check (`if "extracted_entities" in state`) so empty extraction results are also recorded.
- **Relationship Changes Not Persisted** - Fixed bug where NPC-player relationships were never created during gameplay. The `_persist_relationship_change()` function expected legacy schema keys (`entity_key`, `change`) but entity extractor output used new keys (`from_entity`, `to_entity`, `delta`). Now supports both formats. Also improved entity extractor prompt to explicitly instruct extraction of relationship changes (familiarity +10-20 on first meeting, liking/trust on friendly interactions).
- **Duplicate Turn Records** - Fixed bug where each turn was being saved twice to the database. Two issues: (1) `_save_turn_immediately()` created turns unconditionally even when `persistence_node` had already created one during graph execution - now checks for existing turn first; (2) off-by-one error in turn_number calculation used `total_turns + 1` after already incrementing. Added `scripts/cleanup_duplicate_turns.py` utility to clean up existing duplicates.
- **GM Re-Introducing Character Every Turn** - Fixed bug where the Game Master repeated the full character introduction ("You are Durgan Stonehammer...") on every turn instead of only the first. The issue was inconsistent `turn_number` calculation in `game.py`: initial scene used `total_turns + 1` but subsequent turns used just `total_turns` after increment, resulting in both being turn 1. Now both use `total_turns + 1` for consistent numbering.
- **Tool Calling API Error** - Fixed "unexpected tool_use_id in tool_result blocks" error when GM used tools (skill checks, etc.). The assistant message wasn't including `tool_use` content blocks alongside the text, so tool_result messages couldn't find their corresponding tool_use IDs. Now builds proper assistant messages with both text and tool_use blocks.
- **GM Response Lost on Quit** - Fixed issue where quitting (Ctrl+C or /quit) after seeing the GM's response but before full turn processing would lose the response. Now the Turn record is saved and committed immediately after displaying the narrative, ensuring the response is preserved even if subsequent processing is interrupted.
- **Wizard Personality Delegation Not Generating Content** - Fixed bug where LLM would tease generating personality ("I'll craft a nuanced personality...") then ask follow-up questions instead of actually generating it. Updated `wizard_personality.md` template with explicit CRITICAL section showing WRONG vs RIGHT examples for delegation handling. LLM must immediately generate full personality AND output JSON when user says "make it up".
- **Wizard Section Loop After Auto-Fill Confirmation** - Fixed bug where wizard got stuck in a loop after user said "ok" to accept auto-filled values. The LLM kept asking follow-up questions instead of completing the section. Added `pending_confirmation` flag to track when we're waiting for user acceptance after auto-fill, and bypass the LLM when user confirms with acceptance patterns like "ok", "yes", "accept", etc.
- **Wizard Auto-Completing Without Confirmation Prompt** - Fixed bug where personality section auto-completed without showing "Auto-filled: ... Say 'ok' to accept" prompt. The `already_saved` set was calculated AFTER applying field_updates, so new fields were already marked as saved. Moved `already_saved` capture to BEFORE applying updates. Also fixed `{}` appearing in output by removing escaped JSON examples from template.
- **Combined JSON Appearing in Wizard Output** - Fixed bug where combined JSON blocks containing both `field_updates` and `section_complete` were not being stripped from display. Replaced multiple regex patterns with a robust balanced-brace parser in `_strip_json_blocks()` that properly removes any JSON containing wizard-specific keys.
- **Wizard Attributes Section Not Completing** - Fixed bug where attributes section would not output JSON or complete when user said "great", "good", etc. Updated `wizard_attributes.md` template with explicit CRITICAL section showing WRONG vs RIGHT examples. LLM must output field_updates AND section_complete in first response, and immediately complete on acceptance phrases.
- **Wizard Name Section Not Saving Player Values** - Fixed bug where LLM said "I'll update the eye color to hazel" but didn't output JSON, so the field wasn't saved. Updated `wizard_name.md` template with explicit WRONG vs RIGHT examples for when player provides a value directly (like "hazel is cool").
- **Wizard Not Returning to Navigation After Section Completion** - Fixed bug where character creation wizard continued in conversational mode instead of returning to the navigation menu after completing a section (like Species & Gender). The `_parse_wizard_response()` function now handles JSON both with and without markdown code fences, since LLMs sometimes output raw JSON.
- **Prompt Template Leaking into Wizard Display** - Fixed bug where LLM sometimes echoed back parts of the prompt template (e.g., `## Player Input`, `Player: 25`) in its response. Enhanced `_strip_json_blocks()` to strip these template artifacts before display.
- **JSON Output in Wizard Display** - Fixed `section_complete` JSON blocks appearing in character creation wizard output. Added missing regex pattern to `_strip_json_blocks()` function in `src/cli/commands/character.py`.
- **Character Creation Wizard KeyError** - Fixed `KeyError: '"section_complete"'` that occurred when starting a new game. The bug was caused by JSON examples in wizard templates (`data/templates/wizard/*.md`) containing unescaped braces that Python's `str.format()` interpreted as format placeholders. Fixed by escaping braces in all wizard template JSON examples.
- **Background Template KeyError** - Fixed `{name}` placeholder in `wizard_background.md` that caused KeyError during Background section. Changed to `[character]` to avoid Python format string issues.
- **Attributes Template Braces** - Fixed unescaped JSON braces in `wizard_attributes.md` that caused KeyError during Attributes section.
- **Urban Fantasy Spells Showing as Setting** - Moved `urban_fantasy_spells.json` from `data/settings/` to `data/spells/` so it no longer appears as a selectable game setting.
- **Menu "or quit" Display Bug** - Fixed Rich markup in `display.py` where `[q]uit` and `[r]eview` were being interpreted as style tags, showing as "or uit" and "or eview". Escaped brackets with backslash.
- **Game Start EntityAttribute Error** - Fixed `'EntityAttribute' object has no attribute 'current_value'` error when starting game. Changed `attr.current_value` to `attr.value` in `context_compiler.py:342`.
- **LLM Simulating Player Dialogue** - Fixed bug where LLM would generate fake "Player:" dialogue inside its response (e.g., "Player: sounds good", "Player: athletic"). Added regex to `_strip_json_blocks()` to remove all simulated player/assistant dialogue turns.
- **Wizard Field Updates Not Saving** - Strengthened `wizard_name.md` template with explicit FORBIDDEN section and WRONG/RIGHT examples to ensure LLM includes all discussed fields in the JSON output, not just narrative text.
- **Wizard Auto-Completing Without Confirmation** - Fixed bug where wizard could mark sections complete while silently filling in values the user never confirmed. Added validation in `character.py` to detect when `section_data` introduces new required values, showing "Auto-filled: field=value" and requiring explicit confirmation before proceeding.
- **Hidden Backstory Leaking to Player** - CRITICAL fix for wizard revealing GM-only secrets in visible text (e.g., "Hidden Backstory Element: Unknown to Calum..."). Updated `wizard_background.md` with explicit FORBIDDEN section and added safety net regex in `_strip_json_blocks()` to strip any "Hidden Backstory:", "Secret:", "GM Note:", or "Unknown to X," patterns that leak into narrative.
- **Locations Not Created During Gameplay** - Fixed bug where LocationManager was never called during gameplay, resulting in 0 Location records despite rich narrative mentioning places. Added `LocationExtraction` schema to `extraction.py`, added location extraction section to `entity_extractor.md` prompt, added `_persist_location()` to `persistence_node.py`, and added `extracted_locations` to GameState. Now new locations mentioned in GM narrative are automatically created.
- **No Body Storage for New Entities** - Fixed bug where NPCs created during gameplay had no ON_PERSON storage, breaking inventory operations. Added auto-creation of body storage in `persistence_node._persist_entity()` by calling `ItemManager.get_or_create_body_storage()` after entity creation.
- **Container Items Missing Storage Link** - Fixed bug where container items (backpacks, pouches) were created as regular items without linked StorageLocation. Updated `persistence_node._persist_item()` to detect `item_type == "container"` and use `ItemManager.create_container_item()` instead of `create_item()` to auto-create linked storage.
- **Entity Description Causing Persistence Failure** - Fixed bug where passing `description` field to `EntityManager.create_entity()` raised an error because Entity model doesn't have that field. Now description is stored as a fact using `FactManager.record_fact()` instead.
- **LocationManager.get_location_by_display_name() Missing** - Added `get_location_by_display_name()` method to LocationManager for duplicate detection, matching EntityManager's pattern.

- **Comprehensive E2E Tests for CLI Commands** - 45 new tests covering all game commands
  - Tests for `rpg game` commands: start, list, delete, play, turn
  - Tests for `rpg world` commands: time, locations, npcs, events, zones
  - Tests for `rpg character` commands: status, inventory
  - Tests for wizard response JSON parsing with edge cases
  - Tests for character record creation
  - Tests for session isolation and cascade deletion
  - Tests for error handling and edge cases

- **Urban Fantasy Setting** - Contemporary world with secret magic societies
  - Full setting configuration (`data/settings/urban_fantasy.json`)
    - 7 attributes including Willpower for magic
    - 21 skills (15 mundane + 6 magical)
    - 6 factions (Council of the Veil, Hermetic Order, Circle of Thorns, Covenant of Shadows, Order of the Dawn, Mundanes)
    - Veil mechanics for maintaining magical secrecy
    - Supernatural creatures (vampires, werewolves, ghosts, demons, fae, constructs)
    - Modern starting equipment with magical items (focus pendant, chalk pouch, silver knife)
    - Dual currency system (dollars + Council Marks)
  - Starter spell collection (`data/spells/urban_fantasy_spells.json`)
    - 12 spells tailored for urban use with Veil safety ratings
    - Includes: Veil Sight, Minor Ward, Glamour, Forget, Tech Jinx, Sense Lies, Spirit Bolt, Shadow Step, Binding Circle, Psychic Shield, True Name Binding, Healing Touch
    - Spells designed for subtlety and modern scenarios

- **LLM-Driven Relationship Arcs & Voice Generation** - Transform static templates to dynamic LLM-generated content
  - **Arc Generation System** (`src/agents/schemas/arc_generation.py`, `data/templates/arc_generator.md`)
    - `ArcPhaseTemplate` schema - phase definition with milestones and suggested scenes
    - `GeneratedArcTemplate` schema - full arc template with phases, endings, tension triggers
    - Prompt template with relationship context, character details, and example arcs
    - Arc types changed from enum to flexible strings (any LLM-generated type allowed)
    - `arc_template` JSON column stores LLM-generated template per-arc
    - `arc_description` text column for arc summary
  - **Voice Generation System** (`src/agents/schemas/voice_generation.py`, `data/templates/voice_generator.md`)
    - `GeneratedVoiceTemplate` schema - comprehensive voice definition with 20+ fields
    - Includes vocabulary_level, verbal_tics, speech_patterns, example_dialogue
    - Setting-specific guidance (fantasy, contemporary, sci-fi)
    - `voice_template_json` JSON column added to NPCExtension for persistence
  - **RelationshipArcManager Enhancements** (`src/managers/relationship_arc_manager.py`)
    - `generate_arc_for_relationship()` async method - LLM generates custom arc based on relationship dynamics
    - `create_arc_from_generated()` - create arc from LLM template
    - Updated `get_arc_beat_suggestion()` to use stored arc_template
    - `ArcInfo` dataclass extended with `arc_description`, `is_custom` fields
    - Predefined arcs remain as examples/fallback via `WellKnownArcType` enum
  - **VoiceManager Enhancements** (`src/managers/voice_manager.py`)
    - `generate_voice_template()` async method - LLM generates voice based on NPC characteristics
    - `format_generated_voice_context()` - formats voice for GM prompt
    - `voice_template_from_dict()` - loads cached voice from database
    - YAML templates retained as few-shot examples in prompts
    - Setting-specific voice guidance (medieval, contemporary slang, sci-fi terminology)
  - **Database Migration** (`alembic/versions/4fbbe5395f6d_llm_generated_arcs_and_voices.py`)
    - `relationship_arcs.arc_type` column extended to 100 chars (was 30)
    - `relationship_arcs.current_phase` column extended to 50 chars (was 20)
    - Added `relationship_arcs.arc_template` JSON column
    - Added `relationship_arcs.arc_description` Text column
    - Added `npc_extensions.voice_template_json` JSON column
  - **Schema Exports** - Added `ArcPhaseTemplate`, `GeneratedArcTemplate`, `GeneratedVoiceTemplate` to `src/agents/schemas/__init__.py`

- **Future Phases Documentation** - Comprehensive specifications for Tier 3-4 features in `docs/implementation-plan.md`
  - **Phase 14: Social Systems** (Tier 3 - Medium Priority)
    - Rumor System - social network propagation, distortion mechanics, decay over time
    - Relationship Arc Templates - 8 arc types (enemies-to-lovers, betrayal, redemption, etc.) with milestone tracking
    - NPC Voice Templates - YAML-based speech patterns by social class, occupation, personality, region
  - **Phase 15: World Simulation** (Tier 4 - Lower Priority)
    - Economic Events System - market prices, trade routes, supply/demand, seasonal modifiers
    - Magic System - flexible mana-based casting with spell definitions and effect structures
    - Prophesy & Destiny Tracking - fulfillment conditions, multiple interpretation paths
    - Encumbrance & Weight System - Strength-based capacity, movement penalties
  - **Phase 16: Future Considerations** - crafting, weather, disease, mounts, base building

- **Phase 14: Social Systems (Implementation)** - NPC communication and social dynamics
  - **Rumor System** (`src/database/models/rumors.py`, `src/managers/rumor_manager.py`)
    - `Rumor` model with truth_value, spread_rate, decay_rate, intensity, sentiment, tags
    - `RumorKnowledge` model - tracks which NPCs know which rumors with belief and distortion
    - `RumorSentiment` enum (positive, negative, neutral, scandalous, heroic)
    - `RumorManager` with:
      - `create_rumor()`, `get_rumor()`, `get_rumors_about()`, `get_active_rumors()`
      - `add_knowledge()`, `get_rumors_known_by()`, `entity_knows_rumor()`
      - `decay_rumors()` - intensity reduction over time, deactivates weak rumors
      - `spread_rumor_to_entity()` - propagation with optional distortion
      - `get_rumor_info()`, `get_rumor_context_for_entity()`, `get_rumors_context()`
    - Migration: `232c117be2f2_add_rumor_system_tables.py`
    - 36 tests in `tests/test_managers/test_rumor_manager.py`

  - **Relationship Arc Templates** (`src/database/models/relationship_arcs.py`, `src/managers/relationship_arc_manager.py`)
    - `RelationshipArcType` enum - 8 arc types:
      - enemies_to_lovers, mentors_fall, betrayal, redemption
      - rivalry, found_family, lost_love_rekindled, corruption
    - `RelationshipArcPhase` enum (introduction, development, crisis, climax, resolution)
    - `RelationshipArc` model with phase_progress, milestones_hit, arc_tension, suggested_next_beat
    - `ARC_TEMPLATES` dictionary with suggested scenes and milestones for each arc/phase
    - `RelationshipArcManager` with:
      - `create_arc()`, `get_arc()`, `get_active_arcs()`, `get_arcs_for_entity()`
      - `advance_phase()`, `update_phase_progress()`, `update_tension()`
      - `hit_milestone()`, `has_milestone()`
      - `complete_arc()`, `abandon_arc()`
      - `get_arc_beat_suggestion()`, `set_suggested_beat()`
      - `get_arc_info()`, `get_arc_context()`, `get_arc_context_for_entity()`
    - Migration: `111af31a57d1_add_relationship_arcs_table.py`
    - 29 tests in `tests/test_managers/test_relationship_arc_manager.py`

  - **NPC Voice Templates** (`src/managers/voice_manager.py`, `data/templates/voices/`)
    - YAML-based voice template configuration:
      - `base_classes.yaml` - noble, merchant, commoner, scholar, criminal
      - `occupations.yaml` - soldier, innkeeper, blacksmith, healer, priest, guard, farmer, sailor
      - `personalities.yaml` - nervous, confident, friendly, hostile, mysterious, jovial, melancholic, arrogant, shy
      - `regions.yaml` - northern, southern, eastern, western, coastal, mountain, urban
    - `VoiceTemplate` dataclass with vocabulary_level, contractions, greetings, speech_patterns, verbal_tics
    - `VoiceManager` with:
      - `get_base_class()`, `get_occupation()`, `get_personality()`, `get_region()`
      - `build_voice_template()` - merges base class with modifiers
      - `get_example_dialogue()`, `get_occupation_phrase()`
      - `get_voice_context()` - formatted voice guidance for GM
    - 25 tests in `tests/test_managers/test_voice_manager.py`

  - **Phase 14 Summary:**
    - 2 new database models (Rumor, RumorKnowledge)
    - 1 new database model (RelationshipArc)
    - 3 new managers (RumorManager, RelationshipArcManager, VoiceManager)
    - 4 YAML voice template files
    - 2 Alembic migrations
    - 90 new tests total

- **Phase 15: World Simulation (Implementation)** - World dynamics and player capabilities
  - **Encumbrance System** (`src/managers/encumbrance_manager.py`)
    - `EncumbranceLevel` enum (light, medium, heavy, over)
    - `EncumbranceStatus` dataclass with carried_weight, capacity, level, speed_penalty, combat_penalty, percentage
    - `EncumbranceManager` with:
      - `get_carry_capacity()` - strength × 15 pounds formula
      - `get_entity_capacity()` - capacity from entity's strength attribute
      - `get_carried_weight()` - sums held item weights
      - `get_encumbrance_status()` - full encumbrance breakdown
      - `can_pick_up()` - checks if entity can carry additional item
      - `get_encumbrance_context()` - formatted encumbrance for GM prompt
    - Encumbrance levels: Light (0-33%), Medium (34-66%), Heavy (67-100%), Over (>100%)
    - Movement penalties: -10 ft (medium), -20 ft (heavy), immobile (over)
    - Combat penalties: disadvantage on physical (heavy), disadvantage on all (over)
    - Migration: `12d9e2934e02_add_item_weight_field.py`
    - 25 tests in `tests/test_managers/test_encumbrance_manager.py`

  - **Economy System** (`src/database/models/economy.py`, `src/managers/economy_manager.py`)
    - `SupplyLevel` enum (scarce, low, normal, abundant, oversupply)
    - `DemandLevel` enum (none, low, normal, high, desperate)
    - `RouteStatus` enum (active, disrupted, blocked, destroyed)
    - `MarketPrice` model - tracks item category prices at locations with supply/demand levels
    - `TradeRoute` model - connections between markets with goods_traded, travel_days, danger_level
    - `EconomicEvent` model - market-affecting events with price_modifier, affected_locations, duration
    - `PriceInfo` dataclass with base_price, current_price, supply/demand levels, modifiers breakdown
    - `MarketSummary` dataclass with categories, connected_routes, active_events
    - `EconomyManager` with:
      - `set_market_price()`, `get_market_price()`, `get_market_prices_for_location()`
      - `calculate_price()` - applies supply/demand/event modifiers
      - `create_trade_route()`, `get_trade_route()`, `get_routes_for_location()`
      - `disrupt_trade_route()`, `block_trade_route()`, `restore_trade_route()`
      - `create_economic_event()`, `get_event()`, `get_active_events()`, `end_event()`
      - `get_market_summary()`, `get_economy_context()`
    - Price formula: base × location × supply × demand × events
    - Migration: `d44072093509_add_economy_tables.py`
    - 31 tests in `tests/test_managers/test_economy_manager.py`

  - **Magic System** (`src/database/models/magic.py`, `src/managers/magic_manager.py`)
    - `MagicTradition` enum (arcane, divine, primal, psionic, occult)
    - `SpellSchool` enum (abjuration, conjuration, divination, enchantment, evocation, illusion, necromancy, transmutation)
    - `CastingTime` enum (action, bonus_action, reaction, ritual)
    - `SpellDefinition` model - spell templates with level, cost, components, effects (JSON), scaling
    - `EntityMagicProfile` model - entity mana pool, known/prepared spells, mana regen
    - `SpellCastRecord` model - cast history with targets, mana spent, success
    - `SpellInfo` dataclass with spell details and cast availability
    - `CastResult` dataclass with success, mana_spent, effect_description, targets_affected
    - `MagicManager` with:
      - `get_or_create_magic_profile()`, `get_magic_profile()`, `set_magic_profile()`
      - `create_spell()`, `get_spell()`, `get_spells_by_tradition()`, `get_spells_by_school()`, `get_spells_by_level()`
      - `learn_spell()`, `forget_spell()`, `prepare_spell()`, `unprepare_spell()`
      - `spend_mana()`, `restore_mana()`, `regenerate_mana()` (long/short rest)
      - `can_cast_spell()`, `cast_spell()` with upcast support
      - `get_known_spells()`, `get_spell_cast_history()`, `get_magic_context()`
    - Cantrips (level 0) are free to cast
    - Upcast cost: +2 mana per level above base
    - Migration: `7247cbddafd1_add_magic_system_tables.py`
    - 41 tests in `tests/test_managers/test_magic_manager.py`

  - **Destiny System** (`src/database/models/destiny.py`, `src/managers/destiny_manager.py`)
    - `ProphesyStatus` enum (active, fulfilled, subverted, abandoned)
    - `DestinyElementType` enum (omen, sign, portent, vision)
    - `Prophesy` model - prophecy tracking with player-visible text, GM-only true_meaning, fulfillment/subversion conditions, interpretation hints
    - `DestinyElement` model - omens/signs linked to prophecies, witnessed_by tracking, significance level
    - `ProphesyProgress` dataclass with conditions_met/total, elements_manifested, hints_available
    - `DestinyManager` with:
      - `create_prophesy()`, `get_prophesy()`, `get_active_prophesies()`
      - `fulfill_prophesy()`, `subvert_prophesy()`, `abandon_prophesy()`
      - `add_destiny_element()`, `get_destiny_element()`, `get_elements_for_prophesy()`
      - `mark_element_noticed()`, `get_elements_by_type()`, `get_unnoticed_elements()`
      - `check_prophesy_progress()`, `mark_condition_met()`, `add_interpretation_hint()`
      - `get_recent_elements()`, `get_destiny_context()`
    - Migration: `7deb1bdd87cc_add_destiny_tables.py`
    - 28 tests in `tests/test_managers/test_destiny_manager.py`

  - **Phase 15 Summary:**
    - 8 new database models (MarketPrice, TradeRoute, EconomicEvent, SpellDefinition, EntityMagicProfile, SpellCastRecord, Prophesy, DestinyElement)
    - 4 new managers (EncumbranceManager, EconomyManager, MagicManager, DestinyManager)
    - 4 Alembic migrations
    - 125 new tests total

- **Phase 2: Narrative Systems** - Story structure and dramatic tension management
  - **Story Arc Model & Manager** (`src/database/models/narrative.py`, `src/managers/story_arc_manager.py`)
    - `StoryArc` model with `ArcType` (main_quest, side_quest, character_arc, mystery, romance, faction, world_event)
    - `ArcPhase` enum (setup, rising_action, midpoint, escalation, climax, falling_action, resolution, aftermath)
    - `ArcStatus` enum (planned, active, paused, completed, abandoned)
    - Planted elements tracking for Chekhov's gun pattern
    - Foreshadowing hints per arc
    - `StoryArcManager` with:
      - `create_arc()`, `get_arc()`, `get_active_arcs()`
      - `activate_arc()`, `pause_arc()`, `complete_arc()`, `abandon_arc()`
      - `set_phase()`, `set_tension()` (0-100 scale)
      - `plant_element()`, `resolve_element()`, `get_unresolved_elements()` with JSON mutation detection via `flag_modified`
      - `set_foreshadowing()`, `get_pacing_hint()` - phase-aware narrative guidance
      - `get_arc_context()` - formatted string for GM prompt
    - 47 tests in `tests/test_managers/test_story_arc_manager.py`
  - **Mystery/Revelation System** (`src/database/models/narrative.py`, `src/managers/mystery_manager.py`)
    - `Mystery` model with truth, clues (JSON list), red herrings, revelation conditions
    - `clues_discovered`, `total_clues` counters for progress tracking
    - Player theories tracking (JSON field)
    - `MysteryManager` with:
      - `create_mystery()`, `get_mystery()`, `get_active_mysteries()`
      - `add_clue()`, `discover_clue()`, `get_discovered_clues()`, `get_undiscovered_clues()`
      - `add_red_herring()`, `mark_red_herring_discovered()`
      - `add_player_theory()`, `get_player_theories()`
      - `check_revelation_ready()` - keyword-based revelation checking
      - `solve_mystery()`, `get_solution()`
      - `get_mystery_status()` - complete status with discovery percentage
      - `get_mysteries_context()` - formatted string for GM prompt
    - 36 tests in `tests/test_managers/test_mystery_manager.py`
  - **Conflict Escalation System** (`src/database/models/narrative.py`, `src/managers/conflict_manager.py`)
    - `Conflict` model with `ConflictLevel` enum (tension, dispute, confrontation, hostility, crisis, war)
    - Escalation and de-escalation triggers (JSON lists)
    - Escalation history tracking (JSON list with turn and reason)
    - `ConflictManager` with:
      - `create_conflict()`, `get_conflict()`, `get_active_conflicts()`
      - `escalate()`, `de_escalate()` with reason tracking
      - `resolve_conflict()`, `pause_conflict()`, `resume_conflict()`
      - `add_escalation_trigger()`, `add_de_escalation_trigger()`
      - `check_escalation_triggers()` - keyword-based trigger detection
      - `get_conflict_status()` - complete status including escalation history
      - `get_conflicts_context()` - formatted string for GM prompt
    - 33 tests in `tests/test_managers/test_conflict_manager.py`
  - **NPC Secrets System** (`src/managers/secret_manager.py`)
    - New fields on `NPCExtension`: `dark_secret`, `hidden_goal`, `betrayal_conditions`, `secret_revealed`, `secret_revealed_turn`
    - Migration `e28e2ef1e2bf_add_npc_secrets_system_fields.py`
    - `NPCSecret`, `SecretRevealAlert`, `BetrayalRisk` dataclasses
    - `SecretManager` with:
      - `set_dark_secret()`, `set_hidden_goal()`, `set_betrayal_conditions()`
      - `reveal_secret()` - mark secret as revealed with turn tracking
      - `get_npc_secret()`, `get_npcs_with_secrets()`, `get_unrevealed_secrets()`
      - `get_npcs_with_betrayal_conditions()`
      - `check_betrayal_triggers()` - keyword-based betrayal risk detection with risk levels (low/medium/high/imminent)
      - `generate_secret_reveal_alerts()` - context-based alert generation
      - `get_secrets_context()`, `get_betrayal_risks_context()` - formatted strings for GM prompt
    - Automatic `NPCExtension` creation when setting secrets
    - 22 tests in `tests/test_managers/test_secret_manager.py`
  - **Cliffhanger Detection** (`src/managers/cliffhanger_manager.py`)
    - `DramaticMoment` dataclass - source, tension_score (0-100), cliffhanger_potential (low/medium/high/perfect)
    - `CliffhangerSuggestion` dataclass - hook_type (revelation/threat/choice/mystery/arrival), description, why_effective, follow_up_hook
    - `SceneTensionAnalysis` dataclass - overall_tension, primary_source, dramatic_moments, is_good_stopping_point, stopping_recommendation, suggested_cliffhangers
    - Phase-based tension scores (setup: 20, climax: 95)
    - Conflict level tension scores (tension: 15, war: 100)
    - `CliffhangerManager` with:
      - `analyze_scene_tension()` - combines story arcs, conflicts, mysteries
      - `get_cliffhanger_hooks()` - sorted suggestions by effectiveness
      - `is_cliffhanger_ready()` - tuple of (ready, reason)
      - `get_tension_context()` - formatted string for GM prompt
    - Weighted tension calculation (top 3 sources: 50%, 30%, 20%)
    - 20 tests in `tests/test_managers/test_cliffhanger_manager.py`
  - **Narrative Model Tests** - 31 tests in `tests/test_database/test_models/test_narrative.py`
  - **Database Migration** - `c570e2f1f0dd_add_narrative_models_story_arc_mystery_.py`
  - 189 new tests total for narrative systems

- **Phase 3: Progression System** - Player growth and achievement tracking
  - **Skill Advancement System** (`src/managers/progression_manager.py`)
    - New `usage_count` and `successful_uses` fields on `EntitySkill` model
    - `AdvancementResult` dataclass - skill, old_proficiency, new_proficiency, tier_change
    - `SkillProgress` dataclass - skill progress with percentage and tier
    - `ProgressionManager` with:
      - `record_skill_use()` - track skill usage with success flag
      - `advance_skill()` - manual proficiency advancement
      - `get_skill_progress()`, `get_all_skill_progress()` - retrieve progress info
      - `get_proficiency_tier()` - convert proficiency to tier name
      - `get_progression_context()` - formatted string for player display
    - Advancement formula with diminishing returns:
      - Uses 1-10: No advancement (learning basics)
      - Uses 11-25: +3 per 5 successful uses (fast early learning)
      - Uses 26-50: +2 per 5 successful uses (steady growth)
      - Uses 51-100: +1 per 5 successful uses (mastery)
      - Uses 100+: +1 per 10 successful uses (refinement)
    - Proficiency tiers: Novice (0-15), Apprentice (16-30), Competent (31-50), Expert (51-70), Master (71-85), Legendary (86-100)
    - Migration `efe625b872a5_add_skill_usage_tracking.py`
    - 22 tests in `tests/test_managers/test_progression_manager.py`
  - **Achievement System** (`src/database/models/progression.py`, `src/managers/achievement_manager.py`)
    - `Achievement` model with session-scoped definitions
    - `AchievementType` enum: first_discovery, milestone, title, rank, secret
    - `EntityAchievement` model for tracking unlocks with progress and notification state
    - `AchievementUnlock` dataclass - unlock result with points and already_unlocked flag
    - `AchievementProgress` dataclass - progress toward milestone achievements
    - `AchievementManager` with:
      - `create_achievement()`, `get_achievement()`, `get_all_achievements()`, `get_achievements_by_type()`
      - `unlock_achievement()`, `is_achievement_unlocked()`, `get_unlocked_achievements()`
      - `update_progress()`, `get_progress()` - progress-based milestone tracking
      - `get_total_points()` - total achievement points for an entity
      - `get_recent_unlocks()`, `get_pending_notifications()`, `mark_notified()` - notification management
      - `get_achievement_context()` - formatted string for player display
    - Migration `79d56dc7020f_add_achievement_system.py`
    - 23 tests in `tests/test_managers/test_achievement_manager.py`
  - **Relationship Milestones** (`src/database/models/relationships.py`)
    - `RelationshipMilestone` model for tracking significant relationship changes
    - Milestone types: earned_trust, lost_trust, became_friends, made_enemy, earned_respect, lost_respect, romantic_spark, romantic_interest, close_bond, terrified
    - `MilestoneInfo` dataclass with entity names and notification state
    - `RelationshipManager` enhancements:
      - `_check_milestones()` - automatic milestone detection on attitude changes
      - `get_recent_milestones()` - retrieve milestones for a relationship
      - `get_pending_milestone_notifications()` - unnotified milestones for display
      - `mark_milestone_notified()` - mark milestone as seen
      - `get_milestone_context()` - formatted string for player display
    - Smart deduplication: milestones reset when crossing back below threshold
    - Migration `2564a021f6ff_add_relationship_milestones.py`
    - 20 tests in `tests/test_managers/test_relationship_milestones.py`
  - **Reputation/Faction System** (`src/database/models/faction.py`, `src/managers/reputation_manager.py`)
    - `Faction` model with session-scoped definitions
    - `ReputationTier` enum: hated, hostile, unfriendly, neutral, friendly, honored, revered, exalted
    - `FactionRelationship` model for inter-faction relationships (ally, rival, vassal, enemy)
    - `EntityReputation` model for tracking entity-faction reputation (-100 to +100)
    - `ReputationChange` model for audit log
    - `FactionStanding` dataclass - standing with ally/enemy/neutral status
    - `ReputationManager` with:
      - `create_faction()`, `get_faction()`, `get_all_factions()` - faction management
      - `get_reputation()`, `adjust_reputation()`, `get_reputation_tier()` - reputation tracking
      - `get_faction_standing()` - ally/enemy/neutral status calculation
      - `set_faction_relationship()`, `get_faction_relationship()` - inter-faction relationships
      - `get_allied_factions()`, `get_rival_factions()` - query factions by relationship
      - `get_reputation_context()` - formatted string for player display
      - `get_reputation_history()` - audit trail of reputation changes
    - Tier thresholds: Hated (-100 to -75), Hostile (-74 to -50), Unfriendly (-49 to -25), Neutral (-24 to 24), Friendly (25 to 49), Honored (50 to 74), Revered (75 to 89), Exalted (90 to 100)
    - Ally threshold: 50+, Enemy threshold: -50 or below
    - Migration `76cc10d0166a_add_faction_and_reputation_tables.py`
    - 36 tests in `tests/test_managers/test_reputation_manager.py`
  - 101 new tests total for progression systems

- **Phase 4: Combat Depth** - Enhanced combat mechanics with tactical options
  - **Weapon & Armor Equipment System** (`src/database/models/equipment.py`, `src/managers/equipment_manager.py`)
    - `DamageType` enum - slashing, piercing, bludgeoning, fire, cold, lightning, acid, poison, psychic, radiant, necrotic, force, thunder
    - `WeaponProperty` enum - finesse, heavy, light, reach, two_handed, versatile, ammunition, loading, thrown, special, silvered, magical
    - `WeaponCategory` enum - simple_melee, simple_ranged, martial_melee, martial_ranged, exotic, improvised, natural
    - `WeaponRange` enum - melee, reach, ranged, thrown
    - `ArmorCategory` enum - light, medium, heavy, shield
    - `WeaponDefinition` model - damage dice, damage type, properties, range, versatile dice
    - `ArmorDefinition` model - base AC, max DEX bonus, strength required, stealth disadvantage
    - `EquipmentManager` with:
      - `create_weapon()`, `get_weapon()`, `get_all_weapons()`, `get_weapons_by_category()`
      - `get_weapon_stats()` - calculates attack/damage bonuses based on finesse, ranged, etc.
      - `create_armor()`, `get_armor()`, `get_all_armors()`, `get_armors_by_category()`
      - `get_armor_stats()` - calculates total AC with DEX cap
      - `calculate_total_ac()` - combines armor + shield + DEX
    - `WeaponStats` and `ArmorStats` dataclasses for calculated values
    - Migration `ec5a9e5f55d4_add_weapon_and_armor_definition_tables.py`
    - 19 model tests + 32 manager tests = 51 tests
  - **Combat Conditions System** (`src/database/models/combat_conditions.py`, `src/managers/combat_condition_manager.py`)
    - `CombatCondition` enum - 16 conditions: prone, grappled, restrained, paralyzed, blinded, deafened, invisible, stunned, incapacitated, unconscious, poisoned, frightened, charmed, exhausted, concentrating, petrified, hidden
    - `EntityCondition` model - tracks active conditions with duration, source, exhaustion level
    - `CombatConditionManager` with:
      - `apply_condition()` - apply/extend conditions, exhaustion stacks
      - `remove_condition()`, `remove_all_conditions()`
      - `tick_conditions()` - advance time, expire timed conditions
      - `has_condition()`, `get_active_conditions()`, `get_condition_info()`
      - `get_condition_effects()` - combined effects on attacks, saves, movement
      - `get_condition_context()` - formatted string for GM display
    - Condition effects: attack/defense modifiers, save auto-fails, speed penalties
    - Exhaustion levels 1-6 with cumulative penalties
    - Migration `a3c9cc28fc46_add_entity_conditions_table.py`
    - 27 tests in `tests/test_managers/test_combat_conditions.py`
  - **Action Economy & Contested Rolls** (`src/dice/contested.py`)
    - `ActionType` enum - standard, move, bonus, reaction, free
    - `ActionBudget` class - tracks available actions per turn
      - `can_use()`, `use()`, `reset()` - manage action budget
      - `convert_standard_to_move()` - trade action for extra movement
      - `get_remaining_string()` - formatted display
    - `ContestResult` dataclass - rolls, totals, winner, margin
    - `contested_roll()` - generic opposed check (d20 + mod vs d20 + mod)
    - `resolve_contest()` - determine winner (ties go to defender)
    - Common contests: `grapple_contest()`, `escape_grapple_contest()`, `shove_contest()`, `stealth_contest()`, `social_contest()`
    - Support for advantage/disadvantage on either side
    - 23 tests in `tests/test_dice/test_contested_rolls.py`
  - 101 new tests total for combat depth

- **Pre-Generation Context Validator** - Prevents hallucinations before they happen
  - New `src/managers/context_validator.py` with:
    - `validate_entity_reference()` - checks if entity exists
    - `validate_location_reference()` - checks if location is known
    - `validate_fact_consistency()` - detects contradictions with existing facts
    - `validate_time_consistency()` - catches time/weather inconsistencies in descriptions
    - `validate_unique_role()` - prevents duplicate unique roles (e.g., two mayors)
    - `validate_extraction()` - batch validation for extraction results
    - `get_constraint_context()` - generates constraint instructions for GM prompt
  - 17 new tests in `tests/test_managers/test_context_validator.py`
- **Constraint Instructions in GM Prompt** - GM now receives key facts to avoid contradictions
  - Added `{constraint_context}` placeholder to `data/templates/game_master.md`
  - Context includes current time, weather, and key entity facts
  - Updated game_master_node.py to generate and include constraint context
- **Token Budget Management** - Smart context prioritization within token limits
  - New `src/managers/context_budget.py` with:
    - `ContextBudget` class for managing token limits
    - Priority-based section inclusion (CRITICAL, HIGH, MEDIUM, LOW, OPTIONAL)
    - Automatic truncation for large sections
    - Model-specific budget configuration
    - Token estimation (~4 chars/token heuristic)
  - 23 new tests in `tests/test_managers/test_context_budget.py`
- **Entity Existence Validation in Extraction** - Validates extracted references
  - Entity extractor now validates entity keys in relationship changes, item owners, and appointment participants
  - Location references validated with allow_new flag for discoveries
  - Validation warnings logged and returned in state
- **Birthplace System** - NPCs now have birthplace and derive traits from it
  - New `birthplace` field on Entity model with database migration
  - New `src/schemas/regions.py` with region definitions by setting:
    - **Contemporary**: Northern Europe, Mediterranean, Sub-Saharan Africa, East Asia, South Asia, North America, Latin America, Middle East, Southeast Asia
    - **Fantasy**: Northern Kingdoms, Elven Lands, Dwarven Mountains, Southern Deserts, Eastern Empire, Jungle Tribes, Central Plains
    - **Sci-Fi**: Earth Standard, Martian Colonies, Outer Rim, Cyborg Enclaves, Alien Homeworlds
  - `RegionCulture` dataclass with skin color weights, accent style, common foods/drinks, naming style, height modifier
  - Birthplace generation: 87% local, 13% migrant from other regions
  - Skin color now derived from birthplace demographics using weighted random selection
- **Age-Aware Height Generation** - Children and teens now get realistic heights
  - Growth curve percentages: age 5 = 55% adult height, age 10 = 70%, age 15 = 93%, age 18+ = 100%
  - Gender-appropriate adult base heights (female: 170cm, male: 180cm)
- **Age-Aware Voice Generation** - Pre-voice-break voices for children and teens
  - Child voices (<10): "high and clear", "piping", "soft", "childlike", "bright"
  - Teen voices (pre-voice-break): "youthful", "clear", "light", "bright", "unbroken"
  - Voice break ages: males ~15, females ~13
- **Setting-Specific Name Pools** - Names now match the game setting
  - `NAMES_BY_SETTING` dictionary with fantasy, contemporary, and sci-fi name pools
  - Contemporary names include diverse cultural backgrounds (James, Carlos, Wei, Priya, etc.)
  - Sci-fi names include futuristic options (Zex, Nova, Axiom, Vortex, etc.)
  - Automatic setting detection from game session
- **Context-Aware Apprentice Generation** - Youth occupations now match their location
  - `LOCATION_APPRENTICE_ROLES` mapping 50+ location types to trade-specific youth roles
  - Examples: bakery → "baker's apprentice", blacksmith → "forge helper", tavern → "pot boy"
  - Age-aware: under 14 gets helper roles, 14-17 gets apprentice roles
- **Player Character Height & Voice** - Character creation now supports height and voice
  - Added `height` and `voice_description` fields to `CharacterCreationState`
  - Updated wizard_appearance.md template to prompt for these fields
  - Fields are now saved to Entity when character is created

### Changed
- **Age-Relative Attraction System** - Improved realism in NPC age preferences
  - **Age-Relative Decay Rate**: Younger NPCs are now pickier about age gaps
    - 18yo: 5-year gap = 33% attraction (high decay)
    - 60yo: 5-year gap = 72% attraction (low decay)
    - Formula: `decay_rate = 0.1 * (40 / npc_age)`, clamped to [0.03, 0.30]
  - **Fixed Offset Distribution**: Each NPC gets a single fixed age preference offset using skew-normal distribution
    - Most NPCs prefer similar ages (offset ~0)
    - Spread scales with age (older NPCs have wider preference range)
    - Age-bounded: Adults prefer 16+, minors can prefer 10+
    - Skew varies by age: young adults slightly prefer older, older adults prefer younger
  - **Refined Age Brackets**: children (6-9), teens (10-17), young adults (18-30), etc.
  - **Intimacy System by Age**: children (<10) have no drive, teens (10-16) have developing drive
  - **Family Situation**: new dedicated bracket for ages 18-25
  - **Alcohol Preferences**: now start at age 16
  - **Perfect Match Range**: +/-2 years around preferred age gives 100% attraction before decay starts
  - Removed `attracted_age_range` field from `NPCPreferences` schema (replaced by fixed PERFECT_MATCH_RANGE constant)
  - 12 new tests for age attraction system in `tests/test_services/test_emergent_npc_generator.py`

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
