# GM Pipeline E2E Testing Guide

This document provides a **reusable reference** for end-to-end testing of the GM pipeline (`src/gm/`). Test results are logged to `logs/gm_e2e/` - do not add session-specific results to this document.

## Quick Start

```bash
# Run all E2E test scenarios (creates fresh sessions automatically)
python scripts/gm_e2e_test_runner.py

# Run a specific scenario
python scripts/gm_e2e_test_runner.py --scenario dialog

# Run quick test subset
python scripts/gm_e2e_test_runner.py --quick

# View test logs
ls logs/gm_e2e/
```

### Manual Testing

```bash
# Start a fresh session with the GM pipeline
python -m src.main start --pipeline=gm

# Or create a test session without entering game loop
python -m src.main start --pipeline=gm --auto
```

---

## Pipeline Architecture

### New GM Pipeline (`--pipeline=gm`)

```
gm_node → validator_node → applier_node → END
```

| Component | File | Purpose |
|-----------|------|---------|
| `gm_node` | `src/gm/gm_node.py` | LLM call with tool loop (max 10 iterations) |
| `validator_node` | `src/gm/validator.py` | Validates response (logs warnings, doesn't block) |
| `applier_node` | `src/gm/applier.py` | Applies state changes, advances time, decays needs |

### Key Files

| File | Purpose |
|------|---------|
| `src/gm/graph.py` | Pipeline graph definition |
| `src/gm/tools.py` | Tool definitions (15 tools) |
| `src/gm/context_builder.py` | Builds context for GM prompt |
| `src/gm/prompts.py` | GM system prompt |
| `src/gm/schemas.py` | GMResponse and StateChange schemas |
| `src/gm/grounding.py` | GroundingManifest schema for entity validation |
| `src/gm/grounding_validator.py` | Validates `[key:text]` references in GM output |

### Grounding System

The GM uses a grounding system to prevent entity hallucination:

1. **`[key:text]` Format**: GM must reference entities as `[marcus_001:Marcus]` or `[sword_001:the iron sword]`
2. **GroundingManifest**: Contains all valid entity keys (NPCs, items, storages, exits, inventory)
3. **Validation**: After GM response, `GroundingValidator` checks:
   - All `[key:text]` references exist in manifest
   - Entity names aren't mentioned without `[key:text]` format
4. **Retry Loop**: On validation failure, GM retries with error feedback (max 2 retries)
5. **Key Stripping**: Before display, `[key:text]` is stripped to just `text`

**Example Flow**:
```
GM Output: "[marcus_001:Marcus] waves at you from behind [counter_001:the counter]."
Validation: ✓ marcus_001 in manifest, ✓ counter_001 in manifest
Display: "Marcus waves at you from behind the counter."
```

---

## Tool Comparison: New vs Legacy

### New GM Pipeline Tools (15)

| Tool | Purpose |
|------|---------|
| `skill_check` | 2d10 dice rolls |
| `attack_roll` | Combat attack rolls |
| `damage_entity` | Apply damage to entity |
| `create_entity` | Create NPC/item/location/storage |
| `record_fact` | SPV pattern facts |
| `get_npc_attitude` | Query NPC attitude toward entity |
| `assign_quest` | Create and assign a new quest |
| `update_quest` | Advance quest to next stage |
| `complete_quest` | Mark quest completed/failed |
| `create_task` | Add task/goal for player |
| `complete_task` | Mark task as completed |
| `create_appointment` | Schedule future meeting/event |
| `complete_appointment` | Mark appointment kept/missed/cancelled |
| `apply_stimulus` | Create craving from stimuli |
| `mark_need_communicated` | Mark need mentioned (prevents repetition) |

### Legacy Pipeline Tools (27)

| Category | Tools | Status in New Pipeline |
|----------|-------|------------------------|
| **Dice** | skill_check, attack_roll, roll_damage | ✓ `skill_check`, `attack_roll` present; `roll_damage` integrated into `attack_roll` |
| **Relationships** | get_npc_attitude, update_npc_attitude | ✓ `get_npc_attitude` present; updates via StateChange.RELATIONSHIP |
| **Needs** | satisfy_need, apply_stimulus, mark_need_communicated | ✓ `apply_stimulus`, `mark_need_communicated` present; satisfy via StateChange.SATISFY_NEED |
| **Navigation** | check_route, start_travel, move_to_zone, check_terrain, discover_zone, discover_location, view_map | StateChange.MOVE (player + NPC) |
| **Items** | acquire_item, drop_item | StateChange.TAKE/DROP/GIVE |
| **World Spawning** | spawn_storage, spawn_item | ✓ `create_entity` supports storage type |
| **State** | advance_time, entity_move, start_combat, end_combat | Handled via `time_passed_minutes` and StateChange |
| **Quests** | assign_quest, update_quest, complete_quest | ✓ All 3 quest tools present |
| **Tasks** | N/A (new) | ✓ `create_task`, `complete_task`, `create_appointment`, `complete_appointment` |
| **Facts** | record_fact | ✓ Present |
| **NPC Scene** | introduce_npc, npc_leaves | ✓ `create_entity` for NPCs, StateChange.MOVE for leaving |

### StateChange Types

The GM pipeline uses StateChange for mechanical effects instead of dedicated tools:

| StateChangeType | Purpose |
|-----------------|---------|
| `MOVE` | Entity moves to location (player or NPC) |
| `TAKE` | Player takes item |
| `DROP` | Player drops item |
| `GIVE` | Player gives item to NPC |
| `EQUIP` / `UNEQUIP` | Equipment changes |
| `SATISFY_NEED` | Satisfy hunger/thirst/sleep/etc. (activities) |
| `DAMAGE` / `HEAL` | Health changes |
| `RELATIONSHIP` | Relationship dimension update |
| `FACT` | Establish new fact |
| `TIME_SKIP` | Significant time passage |
| `ITEM_PROPERTY` | Modify item property |

---

## Testing Procedure

### Test Scenarios

> **Note**: Combat testing deferred - requires separate testing process.

#### Observation (5 actions)
- "look around"
- "examine the chest"
- "search the room"
- "inspect the door"
- "check under the bed"

#### Dialog/Conversation (5 actions)
- "How are you?"
- "What's your name?"
- "Tell me about yourself"
- "Good morning!"
- "Thanks for your help"

#### Movement - Local (5 actions)
- "go outside"
- "enter the building"
- "walk to the table"
- "move to the corner"
- "step back"

#### Movement - Travel (5 actions)
- "walk to the village"
- "travel to the castle"
- "head to the market"
- "journey to the forest"
- "return to town"

#### Items - Take (5 actions)
- "take the key"
- "pick up the book"
- "grab the sword"
- "collect the coins"
- "get the rope"

#### Items - Drop (5 actions)
- "drop the key"
- "put down the book"
- "leave the sword here"
- "discard the coins"
- "set down the rope"

#### Items - Give (5 actions)
- "give the key to Marcus"
- "hand the book to her"
- "offer the coins"
- "pass him the rope"
- "present the gift"

#### Items - Use/Interact (5 actions)
- "open the chest"
- "read the book"
- "unlock the door"
- "light the torch"
- "ring the bell"

#### Needs - Hunger (8 actions)
- "eat the bread"
- "have some food"
- "grab a bite"
- "feast on the meal"
- "nibble the cheese"
- "finish my meal"
- "eat breakfast"
- "accept the offered food"

#### Needs - Thirst (7 actions)
- "drink water"
- "take a sip"
- "gulp some ale"
- "have a drink"
- "quench my thirst"
- "drink from the stream"
- "finish my drink"

#### Needs - Sleep (8 actions)
- "go to sleep"
- "take a nap"
- "rest in the bed"
- "lie down"
- "close my eyes and sleep"
- "sleep until morning"
- "doze off"
- "get some shut-eye"

#### Needs - Hygiene (8 actions)
- "wash my hands"
- "take a bath"
- "clean myself"
- "bathe in the river"
- "freshen up"
- "wash my face"
- "scrub off the dirt"
- "change into clean clothes"

#### Needs - Comfort (8 actions)
- "sit by the fire"
- "find a warm spot"
- "get comfortable"
- "stretch out"
- "relax in the chair"
- "warm myself by the fire"
- "find shelter from the rain"
- "cool off in the shade"

#### Needs - Stamina (7 actions)
- "rest for a bit"
- "catch my breath"
- "take a break"
- "sit down to rest"
- "recover my strength"
- "lean against the wall"
- "stop to rest"

#### Needs - Social (8 actions)
- "chat with Marcus"
- "spend time with friends"
- "join the conversation"
- "socialize at the tavern"
- "have a heart-to-heart"
- "catch up with an old friend"
- "share stories"
- "hang out with the group"

#### Needs - Wellness (8 actions)
- "tend to my wounds"
- "apply the bandage"
- "take the medicine"
- "rest to recover"
- "see the healer"
- "drink the healing potion"
- "let the wound heal"
- "recover from the illness"

#### Needs - Morale (8 actions)
- "celebrate the victory"
- "enjoy the music"
- "laugh with friends"
- "savor the moment"
- "treat myself"
- "appreciate the view"
- "reflect on good memories"
- "feel proud of my accomplishment"

#### Needs - Sense of Purpose (8 actions)
- "focus on my mission"
- "remind myself why I'm here"
- "set a new goal"
- "commit to the cause"
- "find meaning in this"
- "dedicate myself to this task"
- "remember my promise"
- "renew my vows"

#### Needs - Intimacy (8 actions)
- "hold her hand"
- "embrace him"
- "cuddle by the fire"
- "share a tender moment"
- "lean against her shoulder"
- "give him a hug"
- "hold each other close"
- "rest my head on her lap"

#### Multi-Need Actions (satisfy multiple needs at once)
- "enjoy a meal together" → hunger + social + morale
- "take a relaxing bath" → hygiene + comfort
- "rest by the fire with friends" → stamina + comfort + social
- "share a drink at the tavern" → thirst + social
- "cook a meal for everyone" → hunger + social + purpose
- "sleep in a warm bed" → sleep + comfort
- "celebrate with a feast" → hunger + social + morale
- "tend to each other's wounds" → wellness + social + intimacy

#### Skills - Perception (5 actions)
- "listen carefully"
- "search for traps"
- "spot any danger"
- "notice anything unusual"
- "keep watch"

#### Skills - Stealth (5 actions)
- "sneak past"
- "hide in the shadows"
- "move quietly"
- "stay out of sight"
- "creep along"

#### Skills - Social (5 actions)
- "persuade him"
- "convince her"
- "negotiate a deal"
- "charm the guard"
- "intimidate the thug"

#### Skills - Physical (5 actions)
- "climb the wall"
- "force the door"
- "jump across"
- "swim to shore"
- "lift the boulder"

#### Quests (0 time - technical)
- "accept the quest"
- "what are my active quests?"
- "I finished the task"

#### Tasks/Appointments (0 time - technical)
- "remind me to meet Marcus tomorrow"
- "schedule a meeting"
- "what's on my agenda?"

#### OOC (0 time)
- "ooc: what time is it?"
- "ooc: what skills do I have?"
- "ooc: how hungry am I?"

### After Each Turn, Check:

#### A. Narrative Quality
- [ ] Response makes sense given input
- [ ] No fabricated player actions (didn't say "I attack", GM shouldn't narrate attack)
- [ ] Second-person narration ("you" not "the player")
- [ ] No raw data structures in output
- [ ] No hallucinated items/NPCs not in DB
- [ ] Entity references use `[key:text]` format (stripped for display)

#### B. Database Queries

```sql
-- Replace ? with your session_id and player entity_id

-- Time advancement
SELECT current_day, current_time FROM time_states WHERE session_id = ?;

-- Player needs
SELECT hunger, thirst, stamina, sleep_pressure, hygiene, comfort
FROM character_needs WHERE entity_id = ?;

-- Items held
SELECT item_key, display_name, holder_id, owner_id
FROM items WHERE session_id = ? AND holder_id = ?;

-- NPCs at current location
SELECT e.display_name, n.current_location, n.current_activity
FROM npc_extensions n
JOIN entities e ON n.entity_id = e.id
WHERE e.session_id = ?;

-- Relationships (should track after social interactions)
SELECT e1.display_name as from_npc, e2.display_name as to_entity, r.trust, r.liking
FROM relationships r
JOIN entities e1 ON r.from_entity_id = e1.id
JOIN entities e2 ON r.to_entity_id = e2.id
WHERE r.session_id = ?;

-- Facts recorded
SELECT subject_key, predicate, value FROM facts
WHERE session_id = ? ORDER BY id DESC LIMIT 10;

-- Quests (should update after quest interactions)
SELECT quest_key, name, status, current_stage
FROM quests WHERE session_id = ?;

-- Tasks and appointments
SELECT description, category, status FROM tasks WHERE session_id = ?;
SELECT description, game_day, game_time, status FROM appointments WHERE session_id = ?;

-- Recent turns
SELECT turn_number, LEFT(player_input, 50) as input, LEFT(gm_response, 100) as response
FROM turns WHERE session_id = ? ORDER BY turn_number DESC LIMIT 5;
```

#### C. Tool Calls
- [ ] Skill checks called when outcome is uncertain
- [ ] create_entity used for new NPCs/items/storage (not hallucinated)
- [ ] record_fact used for world lore
- [ ] get_npc_attitude queried before dialogue with existing NPCs
- [ ] assign_quest/update_quest/complete_quest used for quest progression
- [ ] apply_stimulus used when describing tempting stimuli

#### D. Time Advancement
- See Time Expectations Reference table in Expected Behavior section
- Greetings: < 1 min, Full conversation: 2-10 min
- Take/drop items: < 1 min
- Local movement: 1-2 min, Travel: 10 min to 4 hours
- Quest/task actions: 0 min (technical)
- Check `time_manager.advance_time()` via applier.py

#### E. Needs Decay
- `needs_manager.apply_time_decay()` should be called
- Decay rate depends on activity type

---

## Tool Reliability Testing

For each tool, verify:
1. Tool is called when expected
2. Parameters are correct
3. Result is applied to DB
4. Response references tool result

### Tools to Test

| Tool | When to Trigger | What to Verify |
|------|-----------------|----------------|
| `skill_check` | Uncertain outcomes (sneak, persuade, climb) | Roll logged with appropriate DC |
| `create_entity` | New NPC/item/storage discovered | Entity in DB with correct type |
| `record_fact` | World lore revealed or invented | Fact in `facts` table |
| `get_npc_attitude` | Before NPC dialog | Attitude retrieved, affects response |
| `assign_quest` | NPC gives player a mission | Quest in `quests` table, status=active |
| `update_quest` | Player makes progress | Stage incremented |
| `complete_quest` | Quest finished | Status = completed or failed |
| `create_task` | Player sets a goal | Task in `tasks` table |
| `complete_task` | Player finishes goal | Task status = completed |
| `create_appointment` | Meeting scheduled with NPC | Appointment in table with day/time |
| `complete_appointment` | Meeting occurs | Appointment status updated |
| `apply_stimulus` | Tempting scene (food, drinks) | Craving value boosted |
| `mark_need_communicated` | Need mentioned in narrative | (stub - no DB change yet) |

### Tool Call Verification Queries

```sql
-- Check tool calls from recent turns (if logged)
-- Verify skill_check results
-- Look for create_entity calls in narrative patterns

-- After "I try to sneak past":
-- Should see skill_check with skill=stealth, DC appropriate

-- After "look at the mysterious traveler":
-- Should see get_npc_attitude call before dialog
```

---

## Craving Testing

Cravings are temporary urgency boosts triggered by stimuli. Test that `apply_stimulus` is called appropriately.

### Craving Triggers

| Stimulus Type | Triggers When | Need Affected | Test Scenario |
|---------------|---------------|---------------|---------------|
| `food_sight` | Player sees/smells food | `hunger_craving` | Enter tavern with food on tables |
| `drink_sight` | Player sees drinks/water | `thirst_craving` | Approach well or fountain |
| `social_atmosphere` | Lively social setting | `social_craving` | Enter busy tavern with conversations |
| `intimacy_trigger` | Romantic/intimate setting | `intimacy_craving` | Cozy firelight scene with partner |

### Craving Test Verification

```sql
-- Check craving values after stimulus
SELECT hunger_craving, thirst_craving, social_craving, intimacy_craving
FROM character_needs WHERE entity_id = ?;

-- Cravings should be > 0 after appropriate stimuli
-- Cravings decay over time if not satisfied
```

### Test Actions for Cravings

1. **Hunger craving**: Walk into kitchen with fresh bread baking
2. **Thirst craving**: Pass by cool stream on hot day
3. **Social craving**: Hear laughter from nearby gathering
4. **Intimacy craving**: Partner gives meaningful look by firelight

---

## Expected Behavior by Action Type

> **Note**: Combat testing deferred - requires separate testing process.

### Time Expectations Reference

| Action Type | Expected Duration |
|-------------|-------------------|
| Greeting/brief dialog | < 1 minute |
| Full conversation | 2-10 minutes |
| Drop/take item | < 1 minute |
| Use item | 1-5 minutes |
| Local movement | 1-2 minutes |
| Travel (nearby) | 10-30 minutes |
| Travel (distant) | 1-4 hours |
| Eating | 5-30 minutes |
| Drinking | 1-5 minutes |
| Nap | 20-60 minutes |
| Full sleep | Varies (sleep logic) |
| Bathing | 15-45 minutes |
| Skill check action | 1-10 minutes |
| Quest/task actions | 0 minutes (technical) |
| OOC | 0 minutes |

### Observation ("look", "examine", "search")
- **Time**: 1-2 minutes
- **Tools**: None required (or `create_entity` if discovering something)
- **Check**: Scene description matches DB location

### Dialog/Conversation ("how are you", "good morning")
- **Time**: < 1 minute (greeting) to 2-10 minutes (full conversation)
- **Tools**: `get_npc_attitude` (query before dialog)
- **Check**: NPC response reflects their attitude

### Movement - Local ("go outside", "enter building")
- **Time**: 1-2 minutes
- **Tools**: None (StateChange.MOVE)
- **Check**: Player location updated in `npc_extensions.current_location`

### Movement - Travel ("walk to village", "journey to forest")
- **Time**: 10 minutes to 4 hours (based on distance)
- **Tools**: None (StateChange.MOVE)
- **Check**: Player location updated, time advanced appropriately

### Social ("chat", "spend time", "heart-to-heart")
- **Time**: 2-10 minutes
- **Tools**: `get_npc_attitude` (query), StateChange.RELATIONSHIP (update)
- **Check**: Relationships table should update with trust/liking/respect changes

### Items - Take/Drop ("take key", "drop sword")
- **Time**: < 1 minute
- **Tools**: None (StateChange.TAKE/DROP)
- **Check**: `items.holder_id` updated

### Items - Give ("give key to Marcus")
- **Time**: < 1 minute
- **Tools**: None (StateChange.GIVE)
- **Check**: `items.holder_id` updated to recipient

### Items - Use ("open chest", "read book", "light torch")
- **Time**: 1-5 minutes
- **Tools**: May trigger `skill_check` for locked items
- **Check**: Item state/properties may update

### Needs - Physical (hunger, thirst, stamina, sleep, hygiene, comfort, wellness)
- **Time**: Varies (see Time Expectations table)
- **Tools**: StateChange.SATISFY_NEED (with activity type)
- **Check**: `character_needs` values should update after activity

### Needs - Psychological (social, morale, sense_of_purpose, intimacy)
- **Time**: Varies by activity
- **Tools**: StateChange.SATISFY_NEED (with activity type)
- **Check**: `character_needs` values should update after activity

### Skills ("sneak past", "persuade", "climb wall")
- **Time**: 1-10 minutes
- **Tools**: `skill_check`
- **Check**: Roll result affects narrative, appropriate DC used

### OOC ("ooc: ...")
- **Time**: 0 minutes
- **Tools**: `record_fact` (for invented lore)
- **Check**: `is_ooc` flag set on turn

### Quests ("accept quest", "complete mission")
- **Time**: 0 minutes (technical/meta action)
- **Tools**: `assign_quest`, `update_quest`, `complete_quest`
- **Check**: `quests` table updated with status changes

### Tasks & Appointments ("remind me", "schedule meeting")
- **Time**: 0 minutes (technical/meta action)
- **Tools**: `create_task`, `create_appointment`, `complete_task`, `complete_appointment`
- **Check**: `tasks` or `appointments` table updated

---

## Troubleshooting

### No time passing
- Check `applier.py:_advance_time()` is being called
- Check `gm_node.py:_estimate_time_passed()` returns > 0
- Verify `response.time_passed_minutes` is set

### Needs not decaying
- Check `applier.py:_advance_time()` calls `needs_manager.apply_time_decay()`
- Verify player has `character_needs` record

### Items not moving
- Check `applier.py:_apply_take()` and `_apply_drop()`
- Verify StateChange.TAKE/DROP in response

### NPCs not responding
- Check `context_builder.py` includes NPCs at location
- Verify NPC has `npc_extensions` record with `current_location`

### Relationships not updating
- Check for StateChange.RELATIONSHIP in GM response
- Verify `applier.py:_apply_relationship()` is called
- Check `relationship_manager.update_attitude()` receives correct dimensions

### Needs not satisfying
- Check for StateChange.SATISFY_NEED in GM response
- Verify `activity_type` is set correctly (eating, drinking, sleeping, bathing, etc.)
- Check `applier.py:_apply_satisfy_need()` is called

### Grounding validation failing
- Check `gm_node.py:_validate_grounding()` logs for invalid keys or unkeyed mentions
- Verify entity exists in `GroundingManifest` (check `context_builder.build_grounding_manifest()`)
- If GM mentions entity without `[key:text]` format, grounding will retry with feedback
- Max 2 retries before invalid refs are stripped
- Enable `grounding_log_only=True` to log issues without blocking

---

## Quick DB Connection

```bash
PGPASSWORD=bRXAKO0T8t23Wz3l9tyB psql -h 138.199.236.25 -U langgraphrpg -d langgraphrpg
```

---

## References

- **New GM Pipeline**: `src/gm/`
- **Grounding Tests**: `tests/test_gm/test_grounding.py` (36 unit tests)
- **Legacy Pipeline**: `src/agents/nodes/game_master_node.py`
- **Legacy Tools**: `src/agents/tools/gm_tools.py`
- **Gameplay Testing Guide**: `.claude/docs/gameplay-testing-guide.md`
