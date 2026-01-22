# Unified Pipeline Proposal

> **Status:** MVP Implementation Ready
> **Created:** 2026-01-21
> **Authors:** Sebastian, Claude
> **Plan File:** `~/.claude/plans/toasty-herding-music.md`

This document captures findings from analyzing the current quantum pipeline's issues and proposes a unified architecture that mirrors how conversational AI (like Claude) actually works.

> **Quick Link:** For the condensed implementation checklist, see the [Plan File](#plan-file-reference) section at the end.

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Current Architecture Analysis](#current-architecture-analysis)
3. [Root Cause: Stateless LLM Calls](#root-cause-stateless-llm-calls)
4. [Proposed Unified Architecture](#proposed-unified-architecture)
5. [Token Budget Analysis](#token-budget-analysis)
6. [Tool Design](#tool-design)
7. [MVP Decisions](#mvp-decisions)
8. [Implementation Plan](#implementation-plan)
9. [System Prompt Design](#system-prompt-design)
10. [Scene Cut Logic](#scene-cut-logic)
11. [Delta Handling](#delta-handling)
12. [Test World](#test-world)
13. [Verification](#verification)
14. [Plan File Reference](#plan-file-reference)

---

## Problem Statement

The current quantum pipeline has recurring issues that all stem from the same root cause: **the LLM lacks sufficient context to make good decisions**.

### Active Issues Summary

| Issue | Category | Root Cause |
|-------|----------|------------|
| skill-checks-not-triggering | Intent Classification | No conversation history to understand player intent |
| context-aware-location-resolution | Intent Classification | No memory of which "well" was recently discussed |
| llm-hallucinates-npcs-not-in-manifest | Hallucination | Sees flavor text, doesn't know what's real |
| branch-entity-key-collision | Hallucination | No visibility into session-wide entity keys |
| branch-regen-unknown-location | Hallucination | Invents locations that don't exist |
| item-state-desync-ref-based | Missing State Updates | Can't reference items that need to be created |
| llm-skips-mandatory-tool-calls | Missing State Updates | Doesn't know player is hungry |

**Pattern:** Every issue traces back to the LLM not having enough information.

---

## Current Architecture Analysis

### Turn Processing Flow

```
┌─────────────────────────────────────────────────────────────┐
│  1. BUILD MANIFEST         (scene entities)                 │
│  2. PREDICT ACTIONS        (what player might do)           │
│  3. CLASSIFY INTENT        (LLM call #1 - thin context)     │
│  4. MATCH INTENT           (to action prediction)           │
│  5. GET GM DECISIONS       (possible twists)                │
│  6. GENERATE BRANCH        (LLM call #2 - thin context)     │
│  7. VALIDATE BRANCH        (catch hallucinations)           │
│  8. COLLAPSE BRANCH        (roll dice, apply deltas)        │
└─────────────────────────────────────────────────────────────┘
```

### What Each LLM Call Receives

**Intent Classifier (LLM Call #1):**
```
## Player Input
"sneak into the alley"

## Scene: The Village Tavern
NPCs present: Old Tom, Martha the Barmaid
Items available: Wooden Mug, Bread Loaf
Exits: Village Square, Back Alley
```

- No conversation history
- No previous turns
- No character state
- No story context

**Branch Generator (LLM Call #2):**
```
RECENT EVENTS (for context):
- You entered the tavern and ordered ale...  [truncated to 100 chars]
- Tom mentioned something about a well...    [truncated to 100 chars]
- You finished your drink...                 [truncated to 100 chars]
```

- Only last 3 turns
- Truncated to 100 characters each
- No full conversation flow
- No character needs/state

### The Comparison

| Context Element | Claude (Our Chat) | Intent Classifier | Branch Generator |
|-----------------|-------------------|-------------------|------------------|
| Full conversation | ✅ Everything | ❌ Nothing | ❌ Nothing |
| Recent exchanges | ✅ All messages | ❌ None | ⚠️ 3 turns × 100 chars |
| Current input | ✅ | ✅ | ✅ |
| Scene entities | N/A | ✅ Names only | ✅ Full manifest |
| Character state | N/A | ❌ | ❌ |
| Story context | ✅ | ❌ | ❌ |

---

## Root Cause: Stateless LLM Calls

### How Claude Works (What We Want)

In our conversation, I:
1. See your message
2. Understand intent from full context
3. Reason about what to do
4. Execute (tool calls if needed)
5. Respond coherently

All in **one pass** with **full history**.

### How the Game Works (What's Broken)

The game splits this into isolated calls:
1. Intent classifier: Guesses intent with no context
2. Branch generator: Generates outcomes with minimal context
3. Narrator: Writes prose with even less context

Each call is essentially **stateless**. The LLM has no memory of:
- What was discussed before
- What the player cares about
- What entities were mentioned
- What the character's state is

### Example Failure

```
Turn 1: Player talks to Tom about "the old well"
Turn 2: Tom mentions "the Well of Life is dangerous"
Turn 3: Player says "I want to go there"

Intent Classifier sees:
  Input: "I want to go there"
  Exits: [Square, Alley, Market]

Result: Has NO IDEA "there" = "Well of Life"
        Classifies as MOVE to... somewhere?
```

---

## Proposed Unified Architecture

### Core Principle

**One LLM call with rich context, like a conversation.**

Instead of multiple thin calls, we make one call that has:
- Full understanding of the situation
- Ability to reason through the action
- Tools to verify/execute when needed

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    UNIFIED GM CALL                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  SYSTEM PROMPT                                              │
│  ├── Game rules and response format                         │
│  ├── Valid action types and delta types                     │
│  └── Tool descriptions                                      │
│                                                             │
│  CONTEXT (in user message)                                  │
│  ├── Character State                                        │
│  │   ├── Name, location, time                               │
│  │   ├── Needs (hunger, thirst, stamina, sleep)             │
│  │   ├── Inventory summary                                  │
│  │   └── Active quests                                      │
│  │                                                          │
│  ├── Scene Manifest                                         │
│  │   ├── Location description                               │
│  │   ├── NPCs present (with keys + descriptions)            │
│  │   ├── Items available (with keys)                        │
│  │   └── Exits (with keys)                                  │
│  │                                                          │
│  ├── Story Context                                          │
│  │   ├── Story summary (start → last milestone)             │
│  │   └── Recent summary (last milestone → yesterday)        │
│  │                                                          │
│  ├── Conversation History                                   │
│  │   └── Today's turns (full player input + GM response)    │
│  │                                                          │
│  └── Current Player Input                                   │
│                                                             │
│  TOOLS (available for LLM to call)                          │
│  ├── Retrieval: lookup_entity, lookup_fact, recall_mention  │
│  ├── Dice: roll_skill_check                                 │
│  └── State: (deltas in response, not tools)                 │
│                                                             │
│  OUTPUT                                                     │
│  ├── State deltas (JSON)                                    │
│  └── Narrative (prose for player)                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### What Changes

| Aspect | Current | Unified |
|--------|---------|---------|
| LLM calls per turn | 2-3 | 1 |
| Context per call | ~500-1000 tokens | ~3500-4000 tokens |
| Conversation history | 300 chars total | Full day's turns |
| Character state | None | Full needs/inventory |
| Story context | None | Summaries included |
| Intent classification | Separate LLM call | Implicit in understanding |
| Hallucination risk | High (guessing) | Low (full context) |

---

## Token Budget Analysis

### Input Context Breakdown

| Component | Tokens (est.) | Notes |
|-----------|---------------|-------|
| System prompt | ~1,000 | Rules, format, tool definitions |
| Character state | ~200 | Needs, location, inventory summary |
| Scene manifest | ~500 | NPCs, items, exits with descriptions |
| Story summary | ~500 | Compressed backstory (regenerated at milestones) |
| Recent summary | ~400 | Last few days (regenerated daily) |
| Today's raw turns | ~1,000 | Last 5-10 full exchanges |
| Current input | ~50 | Player's message |
| **Total Input** | **~3,650** | |

### Output Breakdown

| Component | Tokens (est.) | Notes |
|-----------|---------------|-------|
| State deltas | ~200 | JSON array of changes |
| Narrative | ~300 | Prose for player |
| **Total Output** | **~500** | |

### Speed Comparison

**Hardware:** NVIDIA GB10 (128GB unified memory)
**Models:** qwen3-32b or Qwen3-Next-80B-A3B (MoE, 3B active)
**Output speed:** ~20-30 tokens/second (local)

| Approach | Output Tokens | Time @ 20 tok/s |
|----------|---------------|-----------------|
| Current (multi-call) | ~900 total | ~45s worst case |
| Unified (single call) | ~500 total | ~25s |

**Result:** Unified approach is potentially **faster** while having **better context**.

### Existing Summarization Infrastructure

The codebase already has `SummaryManager` with:
- **Story summary**: Start → last milestone (~500 words)
- **Recent summary**: Last milestone → yesterday (~400 words)
- **Raw turns**: Today's full text

This infrastructure exists but **isn't being used** by the quantum pipeline.

---

## Tool Design

### Philosophy: Context + Tools

Like Claude, the unified GM should have:
1. **Rich context** for understanding and memory
2. **Tools** for verification and action

Context alone can't verify. Tools alone can't understand. Both together work.

### Proposed Tool Categories

#### 1. Retrieval Tools (Safety Net)

For when summaries don't capture something:

| Tool | Purpose | Example |
|------|---------|---------|
| `lookup_entity(query)` | Find entity by name/description | "well of life" → `well_of_life` |
| `lookup_location(query)` | Find location by name | "the dangerous well Tom mentioned" |
| `lookup_fact(subject, predicate?)` | Search SPV facts | Facts about "well_of_life" |
| `recall_mention(topic)` | Search turn history | When was "well" discussed? |

#### 2. Verification Tools

Prevent hallucination by checking before acting:

| Tool | Purpose | Example |
|------|---------|---------|
| `get_valid_exits()` | List exits from current location | Before generating MOVE delta |
| `get_entities_here()` | List NPCs/items at location | Before referencing an NPC |
| `entity_exists(key)` | Check if entity key is valid | Before using in delta |

#### 3. Action Tools

For uncertain outcomes that need dice:

| Tool | Purpose | Example |
|------|---------|---------|
| `roll_skill_check(skill, dc, context)` | Roll dice for skill check | Stealth DC 15 to sneak past guard |
| `roll_attack(target, weapon?)` | Combat attack roll | Attack the goblin |

#### 4. State Changes

**Not tools** - expressed as deltas in the response:

```json
{
  "deltas": [
    {"type": "UPDATE_LOCATION", "target": "player", "location": "village_square"},
    {"type": "UPDATE_NEED", "target": "player", "need": "thirst", "amount": -20},
    {"type": "TRANSFER_ITEM", "item": "ale_mug", "to": "player"}
  ],
  "narrative": "You drain the last of your ale and head out to the square..."
}
```

### Tool Usage Flow

```
Player: "I want to go to that well Tom mentioned"

LLM thinks: Tom mentioned a well... let me verify which one.

Tool call: lookup_entity("well Tom mentioned")
Result: { key: "well_of_life", display: "The Well of Life",
          notes: "Tom warned it's dangerous" }

LLM thinks: Got it. It's well_of_life. Player wants to go there.
            This is a valid location, no skill check needed.

Response:
{
  "deltas": [
    {"type": "UPDATE_LOCATION", "target": "player", "location": "well_of_life"},
    {"type": "ADVANCE_TIME", "minutes": 15}
  ],
  "narrative": "You leave the tavern and follow the winding path Tom described.
                After a short walk, you arrive at the Well of Life..."
}
```

---

## MVP Decisions

These questions have been resolved for the MVP implementation:

| Question | Decision | Rationale |
|----------|----------|-----------|
| **Single or dual model?** | Single (qwen3) | Simpler, consistent voice, good enough for MVP |
| **Output format?** | JSON with narrative field | Clean parsing, qwen3 is good at JSON |
| **Skill checks?** | Auto-succeed for MVP | Defer dice complexity, prove architecture first |
| **Conversation history?** | Scene-based (since last location change) | Natural "scene cut" at location changes |
| **Migration path?** | Create `old-pipeline` branch, replace on `main` | Clean separation, easy rollback |

### MVP Scope

**Included:**

| Component | Details |
|-----------|---------|
| Single LLM call | One call to qwen3 with rich context |
| Scene manifest | Location, NPCs, items, exits with keys |
| Player state | Key, name, inventory, current time |
| Story summary | Include if exists (from SummaryManager) |
| Current scene turns | All turns since last location change |
| Deltas (MVP) | UPDATE_LOCATION, TRANSFER_ITEM, ADVANCE_TIME, CREATE_ENTITY, UPDATE_ENTITY, RECORD_FACT |
| Test world | New minimal world for testing |

**Deferred:**

| Component | Reason |
|-----------|--------|
| Skill checks / dice | Auto-succeed for MVP |
| Needs system | Not processing hunger/thirst |
| Relationships | No attitude tracking |
| Combat | Avoid combat scenarios |
| Retrieval tools | Rely on context alone first |
| Scene summarization | Just use raw turns |
| Deltas: UPDATE_NEED, UPDATE_RELATIONSHIP, DELETE_ENTITY | Deferred features |

---

## Implementation Plan

### Branch Strategy

1. Create branch `old-pipeline` from current main (preserves quantum pipeline)
2. Continue development on `main` with new unified pipeline

### Files to Create

| File | Purpose |
|------|---------|
| `src/world_server/unified/pipeline.py` | Main UnifiedPipeline class |
| `src/world_server/unified/context_builder.py` | Builds rich context for prompt |
| `src/world_server/unified/schemas.py` | Pydantic schemas for LLM response |
| `src/world_server/unified/prompts.py` | System prompt and formatting |
| `src/world_server/unified/__init__.py` | Package init |
| `data/worlds/test_minimal/` | Minimal test world |
| `tests/test_world_server/test_unified/` | Tests for unified pipeline |

### Files to Modify

| File | Change |
|------|--------|
| `src/cli/commands/game.py` | Add flag to use unified pipeline |

### Components to Reuse

| Component | From | What We Use |
|-----------|------|-------------|
| `GMContextBuilder` | `src/gm/context_builder.py` | Scene manifest building |
| `SummaryManager` | `src/managers/summary_manager.py` | Story summary |
| `GroundingManifest` | `src/gm/grounding.py` | Entity validation |
| `DeltaType` enum | `src/world_server/quantum/schemas.py:46-57` | All 9 delta types |
| `StateDelta` class | `src/world_server/quantum/schemas.py:60-84` | Delta structure |
| `_apply_single_delta()` | `src/world_server/quantum/collapse.py:486-725` | Delta application |
| `DeltaPostProcessor` | `src/world_server/quantum/delta_postprocessor.py` | Auto-repair logic |
| `Turn` model | `src/database/models/session.py:177-273` | Turn persistence |

### Implementation Phases

#### Phase 1: Setup
- [ ] Create `old-pipeline` branch from main
- [ ] Create `src/world_server/unified/` package structure
- [ ] Create minimal test world data

#### Phase 2: Core Pipeline
- [ ] Implement `UnifiedContextBuilder` (reuse GMContextBuilder + SummaryManager)
- [ ] Implement response schemas (`UnifiedResponse`, `DeltaOutput`)
- [ ] Implement system prompt with delta rules
- [ ] Implement `UnifiedPipeline.process_turn()`

#### Phase 3: Delta Handling
- [ ] Reuse delta validation from quantum pipeline
- [ ] Reuse delta application from collapse.py
- [ ] Add turn recording

#### Phase 4: CLI Integration
- [ ] Add `--unified` flag to game command
- [ ] Wire up to existing game loop

#### Phase 5: Testing
- [ ] Unit tests for context building
- [ ] Unit tests for delta parsing
- [ ] Integration test with test world
- [ ] Manual play-testing

---

## System Prompt Design

```
You are the Game Master for a fantasy RPG. Your job is to:
1. Understand what the player wants to do
2. Determine what happens in the game world
3. Generate state changes (deltas) to update the world
4. Write narrative prose describing what happens

## Available Delta Types

### UPDATE_LOCATION
Move an entity to a new location.
- target: entity key (usually "player" or player's entity key)
- location: destination location key (MUST be from Exits list)

### TRANSFER_ITEM
Move an item between holders.
- target: item key
- to: recipient entity key (or "ground" for dropping)

### ADVANCE_TIME
Move game time forward.
- target: "time"
- minutes: number of minutes to advance (1-60 typically)

### CREATE_ENTITY
Create a new NPC or item.
- target: new unique key (snake_case, descriptive)
- entity_type: "npc" or "item"
- name: display name
- description: brief description

### UPDATE_ENTITY
Update an NPC's state.
- target: entity key
- activity: what they're doing (optional)
- mood: emotional state (optional)

### RECORD_FACT
Record a world fact.
- target: subject key
- predicate: what aspect (e.g., "knows_about", "has_visited")
- value: the value

## Rules

1. ONLY reference NPCs, items, and locations that appear in the context
2. For UPDATE_LOCATION, ONLY use location keys from the Exits list
3. Generate appropriate deltas for the action - don't skip state changes
4. Write narrative in second person ("You walk to...")
5. Keep narrative concise (2-4 sentences typically)
6. If player asks a question, answer without deltas unless action is implied

## Output Format

Respond with JSON:
{
  "deltas": [
    {"type": "...", "target": "...", ...}
  ],
  "narrative": "..."
}
```

---

## Scene Cut Logic

A "scene" is a continuous sequence of turns in the same location. When the player moves, a new scene begins.

### What Triggers a Scene Cut

| Trigger | Detection | Action |
|---------|-----------|--------|
| **Location change** | `UPDATE_LOCATION` delta applied | Mark turn as scene boundary |
| **Long time skip** | `ADVANCE_TIME` with hours/days | Could trigger cut (MVP: ignore) |
| **Sleep/rest** | Explicit rest action | Could trigger cut (MVP: ignore) |

**For MVP**: Only location changes trigger scene cuts.

### Finding Scene Turns

```python
def _get_scene_turns(self, current_location_key: str) -> list[Turn]:
    """Get all turns in the current scene (since last location change)."""

    # Get all turns for this session, newest first
    all_turns = (
        self.db.query(Turn)
        .filter(Turn.session_id == self.session_id)
        .order_by(Turn.turn_number.desc())
        .all()
    )

    scene_turns = []
    for turn in all_turns:
        # If this turn was at a different location, we've found the boundary
        if turn.location_at_turn != current_location_key:
            break
        scene_turns.append(turn)

    # Return in chronological order
    return list(reversed(scene_turns))
```

### Example

```
Turn 1: (tavern) "look around"           ← in current scene
Turn 2: (tavern) "talk to Tom"           ← in current scene
Turn 3: (tavern) "go to the square"      ← SCENE CUT (location changes)
Turn 4: (square) "look around"           ← NEW SCENE starts
Turn 5: (square) "go back to the tavern" ← SCENE CUT
Turn 6: (tavern) "talk to Tom again"     ← NEW SCENE (current)

If player is at tavern on turn 6:
  Scene turns = [Turn 6]  (only turns since last entered tavern)
```

### Context Structure

```markdown
## Story So Far
{story_summary - covers everything up to last milestone}

## Current Scene: {location_display}
{location_description}

### Present
NPCs: {npc_key}: {display_name} - {short_desc}
Items: {item_key}: {display_name}
Exits: {exit_key}: {display_name}

### Your State
Character: {player_name} ({player_key})
Inventory: {item_key}: {display_name}, ...
Time: Day {day}, {time} ({period})

## This Scene
Turn 1:
Player: {input}
GM: {response}

Turn 2:
...

## Current Input
Player: {current_input}
```

---

## Delta Handling

### Response Schema

```python
class UnifiedResponse(BaseModel):
    """Structured response from unified GM call."""

    deltas: list[DeltaOutput] = Field(
        default_factory=list,
        description="State changes to apply"
    )
    narrative: str = Field(
        description="Narrative prose for the player"
    )

class DeltaOutput(BaseModel):
    """Delta as output by LLM (converted to StateDelta for application)."""

    type: str  # "update_location", "transfer_item", etc.
    target: str  # Entity key being affected

    # Type-specific fields (all optional, validated per type)
    location: str | None = None      # For UPDATE_LOCATION
    item: str | None = None          # For TRANSFER_ITEM
    to: str | None = None            # For TRANSFER_ITEM recipient
    minutes: int | None = None       # For ADVANCE_TIME
    entity_type: str | None = None   # For CREATE_ENTITY
    name: str | None = None          # For CREATE_ENTITY
    description: str | None = None   # For CREATE_ENTITY
    activity: str | None = None      # For UPDATE_ENTITY
    mood: str | None = None          # For UPDATE_ENTITY
    predicate: str | None = None     # For RECORD_FACT
    value: str | None = None         # For RECORD_FACT
```

### Application Flow

```
LLM Response
     │
     ▼
┌─────────────────┐
│ Parse Response  │  UnifiedResponse from JSON
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Convert Deltas  │  DeltaOutput → StateDelta
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Validate Deltas │  Check keys exist in manifest
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Post-Process    │  Auto-fix minor issues (reuse DeltaPostProcessor)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Apply Deltas    │  Call _apply_single_delta() for each
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Commit & Return │  Save turn, return narrative
└─────────────────┘
```

### Error Handling

| Error | Handling |
|-------|----------|
| LLM returns invalid JSON | Retry once, then return error narrative |
| Delta references unknown entity | Skip delta, log warning, continue |
| Delta references invalid location | Skip delta, log warning, continue |
| LLM times out | Return "Something went wrong..." narrative |
| Database error during apply | Rollback, return error narrative |

---

## Test World

### Structure

```
Locations:
├── test_tavern (start)
│   ├── NPCs: barkeep_tom
│   ├── Items: ale_mug, bread_loaf
│   └── Exits: → test_square, → test_alley
├── test_square
│   ├── NPCs: (none)
│   ├── Items: (none)
│   └── Exits: → test_tavern, → test_alley
└── test_alley
    ├── NPCs: (none)
    ├── Items: old_coin
    └── Exits: → test_tavern, → test_square
```

### YAML Definition

```yaml
# data/worlds/test_minimal/world.yaml

name: "Test Minimal"
description: "Minimal world for testing unified pipeline"
starting_location: "test_tavern"

locations:
  test_tavern:
    name: "The Test Tavern"
    description: "A cozy tavern with a wooden bar and a few tables."
    exits:
      test_square: "wooden door to the square"
      test_alley: "back door to the alley"

  test_square:
    name: "The Village Square"
    description: "A small square with a well in the center."
    exits:
      test_tavern: "tavern entrance"
      test_alley: "narrow alley"

  test_alley:
    name: "The Back Alley"
    description: "A dim alley behind the buildings."
    exits:
      test_tavern: "tavern back door"
      test_square: "path to square"

npcs:
  barkeep_tom:
    name: "Tom the Barkeep"
    description: "A friendly middle-aged man with a bushy mustache."
    location: test_tavern
    occupation: "barkeep"

items:
  ale_mug:
    name: "Wooden Ale Mug"
    description: "A sturdy wooden mug, half-full of ale."
    location: test_tavern

  bread_loaf:
    name: "Bread Loaf"
    description: "A fresh loaf of brown bread."
    location: test_tavern

  old_coin:
    name: "Old Silver Coin"
    description: "A tarnished silver coin with strange markings."
    location: test_alley
```

---

## Verification

### Start Test Session

```bash
python -m src.main game start --world test_minimal --unified
```

### Test Scenarios

| # | Input | Expected Deltas | Verify |
|---|-------|-----------------|--------|
| 1 | "look around" | None or ADVANCE_TIME | Describes tavern, Tom, items |
| 2 | "talk to Tom" | ADVANCE_TIME | Narrative includes Tom's dialogue |
| 3 | "pick up the mug" | TRANSFER_ITEM: ale_mug → player | Player inventory contains ale_mug |
| 4 | "go to the square" | UPDATE_LOCATION, ADVANCE_TIME | New scene, describes square |
| 5 | "go back to the tavern" | UPDATE_LOCATION, ADVANCE_TIME | Remembers previous conversation |
| 6 | "go to the castle" | None | Narrative explains can't go there |

### Conversation Continuity Test

```
Turn 1: "ask Tom about the square"
Turn 2: "what else does he know?"
Expected: Turn 2 understands "he" = Tom from context
```

### Success Criteria

| Criteria | Measurement |
|----------|-------------|
| No NPC hallucination | LLM only references NPCs in manifest |
| No location hallucination | UPDATE_LOCATION only uses valid exit keys |
| Intent understanding | "go to that place Tom mentioned" works |
| Delta correctness | All deltas apply without errors |
| Response time | < 30 seconds per turn |

---

## Plan File Reference

The detailed implementation plan with class outlines is maintained at:

```
~/.claude/plans/toasty-herding-music.md
```

This plan file contains:
- Full class outlines for `UnifiedPipeline` and `UnifiedContextBuilder`
- Detailed scene cut algorithm
- Delta application flow
- Complete test world YAML
- All test scenarios

---

## References

- Current pipeline: `src/world_server/quantum/pipeline.py`
- Summary manager: `src/managers/summary_manager.py`
- Existing tools: `src/gm/tools.py`
- LLM deployment: `docs/llm-deployment.md`
- Active issues: `docs/issues/`
- Delta types: `src/world_server/quantum/schemas.py`
- Delta application: `src/world_server/quantum/collapse.py`
- Turn model: `src/database/models/session.py`
