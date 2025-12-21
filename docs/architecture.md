# RPG Architecture

## Overview

The RPG uses a LangGraph-based multi-agent architecture where specialized agents handle different aspects of the game. The system features:

- **Structured Character Creation** with wizard-based flow and AI assistance
- **Two-Tier Attribute System** with hidden potential stats and calculated current stats
- **Interactive Skill Checks** with proficiency tiers and dice rolling animations
- **Context-Aware Initialization** for needs, vital status, and equipment
- **NPC Full Character Generation** when NPCs are first introduced
- **Companion Tracking** for NPCs traveling with the player

## Game Pipelines

The RPG supports three game pipelines, selectable via `--pipeline` flag on CLI commands.

### System-Authority Pipeline (Default, Recommended)

```
START → ContextCompiler → ParseIntent → ValidateActions → ComplicationOracle
                                                              ↓
                         END ← Persistence ← Narrator ← ExecuteActions
```

**Philosophy**: "System decides what happens, LLM describes it"

**Benefits**:
- **Guaranteed consistency**: If narrative says player has item, inventory has item
- **Testable mechanics**: 90%+ of game logic testable without LLM
- **No drift**: No state/narrative divergence over time
- **Faster iteration**: Debug mechanics without LLM calls

**Components**:
1. **ParseIntent** - Converts natural language to structured `Action` objects
2. **ValidateActions** - Checks if actions are mechanically possible (weight, slots, reach)
3. **ComplicationOracle** - Occasionally adds narrative complications (discovery, interruption, cost, twist)
4. **ExecuteActions** - Applies state changes via Managers (ItemManager, etc.)
5. **Narrator** - Generates constrained prose from mechanical facts

**CLI**: `rpg game play --pipeline system-authority` (default)

---

### Legacy Pipeline (Backward Compatibility)

```
START → ContextCompiler → GameMaster (with Tool Calling)
                              ↓
              ┌───────────────┼───────────────┐
              ↓               ↓               ↓
       EntityExtractor  CombatResolver  WorldSimulator
              ↓
       NPCGenerator (for new NPCs)
              ↓
              └───────────────┼───────────────┘
                              ↓
                        Persistence → END
```

**Philosophy**: "LLM decides what happens AND narrates it"

**Use cases**:
- Testing legacy behavior
- Comparing output quality between pipelines
- Gradual migration of existing games

**Risks**:
- GM may forget tool calls → state/narrative drift
- Post-hoc extraction can miss or hallucinate entities
- Less predictable outcomes

**CLI**: `rpg game play --pipeline legacy`

---

### Scene-First Pipeline (New Architecture)

```
START → ContextCompiler → ParseIntent
                              ↓
                [route_after_parse]
               /               \
              ↓                 ↓
       WorldMechanics     ResolveReferences
              ↓                 |
       SceneBuilder       [route_after_resolve]
              ↓             /        \
       PersistScene   SubturnProcessor  ConstrainedNarrator
              ↓              ↓              ↓
       ResolveReferences → StateValidator → ConstrainedNarrator
                                              ↓
                                       ValidateNarrator
                                           /     \
                                          ↓       ↓
                              ConstrainedNarrator  Persistence → END
                                   (retry)
```

**Philosophy**: "Build the world BEFORE narrating it"

**Key Innovation**: All entities exist in a scene manifest before the narrator runs. The narrator can only reference entities that exist, preventing orphaned entities and state/narrative drift.

**Benefits**:
- **No orphaned entities**: Everything mentioned is pre-created
- **Single source of truth**: NarratorManifest contains all valid references
- **Proper pronoun resolution**: Full context for "he", "she", "the other one"
- **Clarification flow**: Ambiguous references prompt player for clarification
- **Constrained narrator**: Validation catches invented entities

**Components**:
1. **WorldMechanics** - Determines what exists: NPCs present (schedules, events), world state
2. **SceneBuilder** - Generates scene contents: furniture, items, atmosphere
3. **PersistScene** - Saves all scene contents to DB, builds NarratorManifest
4. **ResolveReferences** - Matches player targets to manifest entities
5. **ConstrainedNarrator** - Generates prose using only manifest entities (with [key] format)
6. **ValidateNarrator** - Ensures narrator followed rules, triggers retry if not

**Reference Format**: Narrator embeds entity keys in output:
```
"You see [marcus_001] sitting on [bed_001]."
→ Display: "You see Marcus sitting on the bed."
```

**CLI**: `rpg game play --pipeline scene-first`

**Documentation**: See `docs/scene-first-architecture/` for detailed design.

---

## Agents (Legacy Pipeline)

The following agents are used in the **Legacy Pipeline**. The System-Authority pipeline uses different nodes documented in `src/agents/nodes/`.

### ContextCompiler
**Purpose**: Assembles relevant world state for GM prompts

**Compiled Sections**:
1. **Turn Context** - Turn number, recent history (last 3 turns)
   - First turn: "FIRST TURN. Introduce the player character."
   - Later turns: "CONTINUATION. Do NOT re-introduce the character."
2. **Time Context** - Day, time (HH:MM), weather, season
3. **Location Context** - Name, description, atmosphere
4. **Player Context**:
   - Character name and appearance
   - Equipped items and condition
   - Attributes (STR 14, DEX 12, etc.)
   - Top skills with proficiency tiers (stealth Expert, lockpicking Apprentice)
5. **NPCs Context** - NPCs at location with attitudes
6. **Tasks Context** - Active quests and objectives
7. **Navigation Context** - Current zone and adjacent discovered zones
8. **Secrets** (GM-only) - Hidden facts, planned encounters

### GameMaster (Supervisor)
**Purpose**: Primary narrative agent controlling story flow

**Tool Calling**: The GM uses structured tools to request game mechanics:
- `skill_check` - Request a skill check with DC
- `satisfy_need` - Satisfy a character need
- `apply_stimulus` - Apply environmental stimulus
- Navigation tools: `check_route`, `start_travel`, `move_to_zone`

**Skill Check Tool Parameters**:
```python
{
    "entity_key": "player",  # Who is rolling
    "dc": 15,                # Difficulty Class
    "skill_name": "persuasion",
    "description": "Convince the guard to let you pass",
    "attribute_key": None,   # Optional override
    "advantage": "normal"    # normal/advantage/disadvantage
}
```

**Routes To**:
- `EntityExtractor`: After every response (default)
- `CombatResolver`: When `combat_initiated: true`
- `WorldSimulator`: When location changes or time ≥30 minutes

### EntityExtractor
**Purpose**: Parse GM responses to extract state changes

**Extracts**:
- New entities mentioned (NPCs, monsters, objects)
- Items acquired/lost
- Facts revealed
- Relationship changes
- Location changes

### NPCGenerator (NEW)
**Purpose**: Generate full character data for newly introduced NPCs

**Triggered**: After EntityExtractor identifies NEW NPCs

**Generates**:
- Appearance (12 fields: age, gender, build, hair, eyes, etc.)
- Background and personality
- Skills based on occupation
- Inventory based on occupation
- Preferences (social, food, intimacy)
- Initial needs (context-aware from time of day)

**Occupation Templates**: 15+ occupations with skill/inventory templates:
- merchant: haggling, appraisal, persuasion + coin_purse, ledger
- guard: swordfighting, intimidation, perception + sword, shield
- scholar: arcana, history, investigation + books, writing_kit

### NPC Extraction Pipeline
**Purpose**: Intelligently extract and spawn NPCs from narrative text

**Flow**:
1. `NPCExtractor` analyzes narrative for NPC mentions
2. Classifies each NPC by importance level
3. `ComplicationOracle.evaluate_npc_spawn()` decides spawn vs defer
4. Critical/supporting NPCs spawn immediately via `EmergentNPCGenerator`
5. Background NPCs stored in `Turn.mentioned_npcs` for on-demand spawning
6. Player references trigger spawn from deferred pool

**Importance Levels**:
| Level | Description | Action |
|-------|-------------|--------|
| CRITICAL | Named characters integral to story | Spawn immediately |
| SUPPORTING | Characters with speaking roles | Spawn immediately |
| BACKGROUND | Unnamed crowd members, workers | Defer to mentioned_npcs |
| REFERENCE | Historical/absent figures | Track as facts only |

**Key Classes**:
- `NPCExtractor` (`src/narrator/npc_extractor.py`) - LLM-based classification
- `ExtractedNPC` - Pydantic model with name, occupation, importance, description
- `TurnManager` - Stores/retrieves deferred NPCs

### CombatResolver
**Purpose**: Handle tactical combat

**Mechanics**:
- Initiative rolls (DEX-based)
- Attack/defense resolution
- Damage calculation
- Status effects
- Loot generation

### WorldSimulator
**Purpose**: Background world updates

**Triggers**:
- Player moves to new location
- Significant time passes (30+ min)
- Periodic random event checks

**Actions**:
- Update NPC positions from schedules
- Apply time-based need decay to companions
- Check for missed appointments
- Generate random events
- Update weather

## Character Creation System

### Wizard Flow
The character creation wizard guides players through 6 sections:

```
NAME → APPEARANCE → BACKGROUND → PERSONALITY → ATTRIBUTES → REVIEW
```

Each section has:
- Dedicated AI prompt template (`data/templates/wizard/wizard_[section].md`)
- Section-scoped conversation history (prevents context bleeding)
- JSON parsing for `field_updates` and `section_complete` signals
- Max 10 conversation turns per section

### Two-Tier Attribute System

**Hidden Potential Stats** (rolled at creation, never shown to player):
```python
roll_potential_stats()  # 4d6 drop lowest for each attribute
# Range: 3-18 per attribute
# Stored in Entity.potential_strength, potential_dexterity, etc.
```

**Current Stats** (what player sees):
```python
Current = Potential + Age_Modifier + Occupation_Modifier + Lifestyle_Modifiers
```

**Age Modifiers** (by bracket):
- Child (0-5): STR -5, DEX -3, INT -2, WIS -3
- Young Adult (16-25): Peak (no modifiers)
- Elderly (81+): STR -3, DEX -2, CON -2, WIS +3

**Occupation Modifiers** (per year, capped at 5 years):
- blacksmith: STR +0.6/yr, DEX +0.2/yr, CON +0.4/yr
- scholar: STR -0.2/yr, INT +0.6/yr, WIS +0.4/yr
- soldier: STR +0.4/yr, DEX +0.4/yr, CON +0.4/yr

**Lifestyle Modifiers** (tags from backstory):
- hardship: STR +1, CON +1, WIS +1
- pampered: STR -1, CHA +1
- secret_training_physical: STR +1, DEX +1

**Twist Narratives**: When stats don't match occupation expectations, the system generates explanations:
> "Despite years of blacksmith work, strength never came naturally to him."

### Context-Aware Initialization

**Initial Needs** (based on backstory keywords):
```python
# Hardship words (escaped, fled, homeless) → lower comfort, morale, hygiene
# Isolation words (alone, hermit, exile) → lower social_connection
# Purpose words (mission, destiny, quest) → higher sense_of_purpose
# Age adjustments: young = more energy, elderly = less energy
```

**Initial Vital Status** (based on backstory):
```python
# "wounded", "injured", "bleeding" → WOUNDED
# "sick", "poisoned", "plague" → WOUNDED
# "starving", "dehydrated" → WOUNDED
# Default → HEALTHY
```

**Equipment Condition** (based on backstory):
```python
# "wealthy", "noble" → PRISTINE
# "soldier", "merchant" → GOOD
# "escaped", "refugee" → WORN
# "battle", "fire", "flood" → DAMAGED
```

**Situational Constraints** (from backstory):
```python
# "prisoner", "slave", "swimming" → minimal_equipment, no_armor
# "peaceful", "monk" → no_weapons
# "swimming", "rain", "shipwreck" → is_wet (affects comfort/hygiene)
```

### Post-Creation Processing

After character confirmation:

1. **World Extraction** (async LLM call):
   - Extracts NPCs mentioned in backstory as "shadow entities"
   - Creates bidirectional relationships with trust/liking/respect
   - Refines player appearance details

2. **Gameplay Field Inference** (async LLM call):
   - Infers skills from background (blacksmith → blacksmithing 70)
   - Infers preferences (food, social, intimacy)
   - Creates need modifiers based on traits

3. **Memory Extraction** (rule-based):
   - Death/loss mentions → grief memories
   - Trauma keywords → fear memories
   - Achievement keywords → pride memories

## Skill Check System

This game uses a **2d10 bell curve system** for skill checks instead of d20. See `docs/game-mechanics.md` for detailed mechanics and probability tables.

### Why 2d10?
- **Bell curve**: Results cluster around 11, extremes are rare
- **4x less variance**: 8.25 vs d20's 33.25
- **Expert reliability**: Master (+8) vs DC 15 succeeds 88% (was 70% with d20)

### Auto-Success (Take 10 Rule)
If `DC ≤ 10 + total_modifier`, auto-succeed without rolling:
- Master locksmith (+8) auto-succeeds DC 18 locks
- Expert climber (+5) auto-succeeds DC 15 cliffs

### Proficiency Tiers
Proficiency level (1-100) converts to modifier and tier:

| Level | Modifier | Tier |
|-------|----------|------|
| 0-19 | +0 | Novice |
| 20-39 | +1 | Apprentice |
| 40-59 | +2 | Competent |
| 60-79 | +3 | Expert |
| 80-99 | +4 | Master |
| 100 | +5 | Legendary |

### Skill-to-Attribute Mapping
80+ skills mapped to governing attributes:
- **Strength**: athletics, climbing, swimming, grappling, swordfighting
- **Dexterity**: acrobatics, stealth, lockpicking, archery, sleight_of_hand
- **Constitution**: endurance, concentration, holding_breath
- **Intelligence**: arcana, history, investigation, alchemy, medicine
- **Wisdom**: perception, insight, survival, tracking, animal_handling
- **Charisma**: persuasion, deception, intimidation, performance, seduction

Unknown skills default to Intelligence.

### Difficulty Classes (with 2d10)

| DC | Difficulty | Master (+8) | Expert (+5) | Untrained |
|----|------------|-------------|-------------|-----------|
| 5 | Trivial | Auto | Auto | 97% |
| 10 | Easy | Auto | Auto | 64% |
| 15 | Moderate | Auto | 72% | 21% |
| 20 | Hard | 64% | 45% | 6% |
| 25 | Very Hard | 36% | 21% | 1% |
| 30 | Legendary | 15% | 6% | <1% |

### Advantage & Disadvantage
- **Normal**: Roll 2d10, keep both
- **Advantage**: Roll 3d10, keep best 2 (~+2.2 mean shift)
- **Disadvantage**: Roll 3d10, keep worst 2 (~-2.2 mean shift)

### Interactive Dice Rolling

**Phase 1: Pre-Roll Prompt** (if not auto-success)
```
┌─ Skill Check ─────────────────────────────────┐
│ Attempting to pick the merchant's lock        │
│                                               │
│ Your modifiers (2d10 + modifier):             │
│   Lockpicking: +3 (Expert)                   │
│   Dexterity: +2                              │
│   Total: +5                                  │
│                                               │
│ This looks challenging                        │
│ Press ENTER to roll...                        │
└───────────────────────────────────────────────┘
```

**Phase 2: Rolling Animation**
```
Rolling... ⚄  (cycles through dice faces)
```

**Phase 3: Result Display**
```
┌─ Result ──────────────────────────────────────┐
│ Roll: (8+7) +5 = 20                           │
│ vs DC 15                                      │
│                                               │
│ CLEAR SUCCESS                                 │
│ (margin: +5)                                  │
└───────────────────────────────────────────────┘
```

### Outcome Tiers (Degree of Success)
| Margin | Outcome | Description |
|--------|---------|-------------|
| ≥10 | Exceptional | Beyond expectations, bonus effect |
| 5-9 | Clear Success | Clean execution |
| 1-4 | Narrow Success | Succeed with minor cost |
| 0 | Bare Success | Just barely |
| -1 to -4 | Partial Failure | Fail forward, reduced effect |
| -5 to -9 | Clear Failure | Fail with consequence |
| ≤-10 | Catastrophic | Serious setback |

### Critical Results
- **Critical Success**: Both dice = 10 (1% chance)
- **Critical Failure**: Both dice = 1 (1% chance)

Note: Combat attacks still use d20 for dramatic volatility.

## Turn Procedure

### Game Loop

```python
while True:
    player_input = prompt_input("> ")

    # Handle commands (/quit, /status, /inventory, etc.)
    if is_command(player_input):
        handle_command(player_input)
        continue

    game_session.total_turns += 1

    # Create state and invoke LangGraph
    state = create_initial_state(session_id, player_id, location,
                                 player_input, turn_number)
    result = await graph.ainvoke(state)

    # Display skill checks interactively (if any)
    for check in result.get("skill_checks", []):
        display_skill_check_prompt(check)
        wait_for_roll()  # Player presses ENTER
        display_rolling_animation()
        display_skill_check_result(check)

    # Display GM narrative
    display_narrative(result["gm_response"])

    # Handle location changes
    if result.get("location_changed"):
        display_info(f"[You are now at: {result['player_location']}]")

    db.commit()
```

### Graph State Flow

```
context_compiler
      ↓
game_master (with tool calling, up to 5 rounds)
      ↓
[Conditional Routing]
  ├→ combat_resolver (if combat_active)
  ├→ world_simulator (if location_changed OR time ≥ 30min)
  └→ entity_extractor (default)
         ↓
     npc_generator (for NEW NPCs only)
         ↓
     persistence (save to DB)
```

## Database Architecture

### Session Layer
- `game_sessions`: Session metadata, settings, total_turns
- `turns`: Immutable turn history (player_input, gm_response)
- `time_states`: Game clock (day, time, weather, season)

### Entity Layer
- `entities`: Characters with appearance columns and hidden potential stats
- `entity_attributes`: Current attribute values (calculated)
- `entity_skills`: Skills with proficiency (1-100)
- `npc_extensions`: NPC-specific data (job, schedule, companion status)
- `monster_extensions`: Combat stats (HP, AC, loot tables)

### Character State Layer
- `character_needs`: 10 needs (hunger, thirst, energy, hygiene, etc.)
- `character_preferences`: Food, social, intimacy preferences
- `need_modifiers`: Trait/age-based decay/satisfaction multipliers
- `character_memories`: Significant memories for emotional reactions
- `entity_vital_states`: Health status (HEALTHY, WOUNDED, CRITICAL, DYING, DEAD)

### World Layer
- `locations`: Places with hierarchy
- `terrain_zones`: Explorable terrain segments
- `zone_connections`: Adjacencies with direction and travel time
- `schedules`: NPC routines
- `facts`: SPV (Subject-Predicate-Value) fact store
- `world_events`: Background events

### Relationship Layer
- `relationships`: 7 dimensions (trust, liking, respect, fear, familiarity, romantic_interest, sexual_tension)
- `relationship_changes`: Audit log with reasons

### Item Layer
- `items`: All objects with owner_id and holder_id (owner vs holder pattern)
- Body slot + layer system for clothing visibility

### Task Layer
- `tasks`: Player objectives
- `appointments`: Scheduled events
- `quests`: Multi-stage stories

## Manager Pattern

Each domain has a dedicated manager class:

```python
class EntityManager:
    def get_entity(key: str) -> Entity
    def create_entity(**data) -> Entity
    def create_shadow_entity(**data) -> Entity  # Backstory NPCs
    def set_companion_status(key: str, is_companion: bool, turn: int)
    def get_companions() -> list[Entity]

class NeedsManager:
    def apply_time_decay(entity_id: int, hours: float, activity: str)
    def get_active_effects(entity_id: int) -> list[str]  # Stat penalties
    def apply_companion_time_decay(hours: float, activity: str)

class RelationshipManager:
    def get_attitude(from: Entity, to: Entity) -> Relationship
    def update_attitude(from: Entity, to: Entity, dimension: str, delta: int)
    def apply_personality_modifiers()  # Trait-based multipliers

class ContextCompiler:
    def compile_scene(player_id: int, location: str, turn: int) -> SceneContext

class SnapshotManager:
    def create_snapshot(turn_number: int) -> SessionSnapshot  # Capture all tables
    def restore_snapshot(turn_number: int) -> bool  # Restore session state
    def list_snapshots() -> list[SessionSnapshot]  # Available restore points
    def delete_snapshots_after(turn_number: int)  # Clean up after reset
```

### SnapshotManager
**Purpose**: Capture and restore complete session state for game save/reset functionality

**Captured Tables**:
- entities, entity_attributes, entity_skills, npc_extensions
- items, storage_locations
- locations, terrain_zones, zone_connections
- relationships, relationship_changes
- character_needs, vital_states, memories, preferences
- facts, tasks, time_states
- All session-scoped data

**Use Cases**:
- `game history` - View turn history with player inputs and GM responses
- `game reset` - Restore session to any previous turn state
- Debug/testing - Replay specific game states

## LLM Provider Abstraction

### Providers
- **AnthropicProvider**: Claude models (default)
- **OpenAIProvider**: GPT models + OpenAI-compatible APIs (DeepSeek, vLLM)
- **OllamaProvider**: Native Ollama integration for local LLMs (Llama 3, Qwen3, Mistral)
  - Thinking mode control: `think=False` for fast narration, `think=True` for reasoning
  - Automatic `<think>` tag stripping for Qwen3 and other reasoning models
  - Configure via: `LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`

### Audit Logging
Enable with `LOG_LLM_CALLS=true`:
- Logs all prompts and responses to markdown files
- Structure: `logs/llm/session_{id}/turn_XXX_timestamp_calltype.md`

## State Persistence

### Immutable Turn History
Every turn is recorded and never modified:
```python
class Turn:
    player_input: str
    gm_response: str
    created_at: datetime
```

### Mutable Session Context
Updated after each turn:
- NPC locations and activities
- Item positions
- Relationship values
- Need levels
- Time progression

### Companion Need Tracking
NPCs marked as companions have needs tracked:
```python
entity_manager.set_companion_status("guard_thorne", True, turn_number)
needs_manager.apply_companion_time_decay(hours=2.0, activity="active")
```
