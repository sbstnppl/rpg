# GM Prompt Architecture Optimization

**Status:** Done
**Priority:** High
**Detected:** 2025-12-25
**Completed:** 2025-12-25
**Related Sessions:** GM misinterpreting questions as actions (logs/llm/orphan/20251225_083641)

## Problem Statement

The GM prompt architecture needs comprehensive review and potential restructuring. Currently, the GM prompt combines multiple context layers (summaries, database info, turn history) in a way that may not be optimal for consistent, high-quality narration. Additionally, the system needs a clear strategy for using different LLMs for different tasks (reasoning vs narration).

## Current Behavior

From investigation of `src/gm/prompts.py` and LLM logs:

1. **Prompt Structure** (`GM_SYSTEM_PROMPT` + `GM_USER_TEMPLATE`):
   - System prompt: ~150 lines of instructions covering responsibilities, tools, grounding rules, OOC handling
   - User template: Player state, location, entities, knowledge, story context, recent turns

2. **Context Layers** (as understood):
   - a) Background story of the player
   - b) Turn summary until the most recent milestone
   - c) Summary since last milestone (updated daily)
   - d) Entire turns of today OR at least 10 recent turns

3. **Database Information Injected**:
   - Present NPCs with relationships
   - Present items
   - Known facts
   - Character familiarity
   - Exits and constraints
   - System hints

4. **Known Issues**:
   - GM misinterprets questions as actions (e.g., "What about other clothes?" → creates and takes coat)
   - No clear separation between reasoning (what should happen) and narration (how to describe it)
   - Single LLM handles everything despite config supporting multiple models

## Expected Behavior

1. **Optimal Context Assembly**: Information presented in a way that maximizes LLM understanding while minimizing token usage
2. **Clear Action vs Question Handling**: GM correctly distinguishes between player actions and player questions
3. **Multi-Model Pipeline**:
   - Reasoning model (qwen) for: world state decisions, tool calls, action resolution
   - Narration model (magmell) for: prose generation, dialogue, descriptions
4. **Consistent Responses**: No hallucinated items, no auto-taking actions, grounded in scene

## Investigation Notes

### Current File Locations
- `src/gm/prompts.py` - Main GM system prompt and user template
- `src/config.py` - Model configuration (narrator, reasoning, cheap models)
- `logs/llm/orphan/` - LLM call logs with full prompts

### Model Configuration (from config.py)
```python
narrator: str = "ollama:magmell:32b"  # Prose narration, scene descriptions
reasoning: str = "ollama:qwen3:32b"   # Combat, tools, extraction, intent parsing
cheap: str = "ollama:qwen3:32b"       # Summaries, quick decisions
```

### Prompt Size Analysis
- System prompt: ~3500 tokens estimated
- User template with full context: Variable, can be 2000-5000+ tokens
- Total per request: 5000-8000+ tokens

### Key Observations from Logs
1. The GM prompt includes "GROUNDING RULES" that emphasize creating items, which may cause over-eagerness
2. OOC handling section exists but doesn't cover availability questions ("Are there...?")
3. Turn history is truncated mid-sentence in some cases
4. No separation between "what to do" and "how to say it"

## Root Cause

The investigation revealed three core issues:

1. **No tracking of first-time vs revisit** - The GM couldn't distinguish between discovering storage contents for the first time (where inventing contents is appropriate) vs re-examining the same container (where referencing established contents is required).

2. **Context ordering was wrong** - Instructions dominated the prompt (6:1 ratio vs conversation), with recent conversation buried at the bottom. This caused the LLM to prioritize rule-following over natural conversational flow.

3. **No explicit intent classification** - The GM prompt lacked guidance on distinguishing questions from actions, leading to over-eager item creation.

## Implemented Solution

Used **Option C: Conversation-First Context** combined with **Storage Observation Tracking**:

### 1. Storage Observation Tracking (Database Layer)
- Added `StorageObservation` model to track when player first observed a container
- Records observer_id, storage_location_id, contents_snapshot at observation time
- Enables [FIRST TIME] vs [REVISIT] tags in GM prompts

### 2. Prompt Restructuring (Conversation-First)
New context ordering:
1. **RECENT CONVERSATION** - Last 10 turns (PRIMARY)
2. **CURRENT SCENE** - Location, NPCs, items, storage containers (SECONDARY)
3. **CONTEXT SUMMARIES** - Background story, recent events (TERTIARY)
4. **PLAYER STATE** - Needs, inventory, relationships
5. **SYSTEM NOTES** - Hints, constraints, OOC, familiarity

### 3. Simplified System Prompt
Reduced from ~150 lines to ~75 lines with clear sections:
- **INTENT ANALYSIS** - Question vs Action vs Dialogue classification
- **FIRST-TIME vs REVISIT** - Rules for storage container handling
- **TOOLS** - When and how to use each tool
- **GROUNDING** - Entity reference rules
- **OOC HANDLING** - Meta-question detection

### 4. Tool Integration
- Added `storage_location` parameter to `create_entity` tool for items
- Observations are recorded when items are created in storage
- `_record_storage_observations()` in gm_node.py handles the recording

## Files Modified

- [x] `src/database/models/world.py` - Added StorageObservation model
- [x] `src/managers/storage_observation_manager.py` - NEW: Observation CRUD
- [x] `src/gm/prompts.py` - Restructured templates, reduced instruction bloat
- [x] `src/gm/context_builder.py` - Added _get_storage_context(), reordered build()
- [x] `src/gm/tools.py` - Added storage_location param to create_entity
- [x] `src/gm/gm_node.py` - Added observation recording after item creation
- [x] `src/gm/schemas.py` - Added storage_location_key to result schemas
- [x] `alembic/versions/1d4fed343685_add_storage_observations_table.py` - Migration
- [x] `tests/test_managers/test_storage_observation_manager.py` - 11 unit tests
- [x] `tests/test_gm/test_gm_integration.py` - 10 integration tests

## Test Results

- [x] Storage observation tracking: 11 tests passing
- [x] Context ordering: Verified RECENT CONVERSATION before CURRENT SCENE
- [x] [FIRST TIME]/[REVISIT] tags: Correctly generated based on observation state
- [x] System prompt structure: INTENT ANALYSIS and FIRST-TIME vs REVISIT sections present
- [x] Integration tests: 10 tests passing

Total: **32 new tests added and passing**

## Related Issues

- Question misinterpretation bug (discussed in current session)
- See plan file: `~/.claude/plans/shimmying-sniffing-zebra.md`

## References

- `src/gm/prompts.py` - Optimized GM prompt implementation
- `src/gm/context_builder.py` - Conversation-first context builder
- `src/managers/storage_observation_manager.py` - Observation tracking
- `docs/architecture.md` - System architecture overview

## Future Work (Backlog)

- **Two-model pipeline**: Use magmell for narration after qwen reasoning
- **Enhanced OOC detection**: More patterns for implicit OOC questions
- **Storage content change events**: Track world events that modify storage contents
