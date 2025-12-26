# GM Pipeline E2E Testing Guide

This document provides instructions and findings for end-to-end testing of the new GM pipeline (`src/gm/`).

## Quick Start

```bash
# Start a fresh session with the GM pipeline
python -m src.main start --pipeline=gm

# Resume existing session
python -m src.main play --session=<ID> --pipeline=gm
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
| `src/gm/tools.py` | Tool definitions (5 tools) |
| `src/gm/context_builder.py` | Builds context for GM prompt |
| `src/gm/prompts.py` | GM system prompt |
| `src/gm/schemas.py` | GMResponse and StateChange schemas |

---

## Tool Comparison: New vs Legacy

### New GM Pipeline Tools (5)

| Tool | Purpose |
|------|---------|
| `skill_check` | 2d10 dice rolls |
| `attack_roll` | Combat attack rolls |
| `damage_entity` | Apply damage to entity |
| `create_entity` | Create NPC/item/location |
| `record_fact` | SPV pattern facts |

### Legacy Pipeline Tools (27)

| Category | Tools | Status in New Pipeline |
|----------|-------|------------------------|
| **Dice** | skill_check, attack_roll, roll_damage | `skill_check`, `attack_roll` present; `roll_damage` → integrated into `attack_roll` |
| **Relationships** | get_npc_attitude, update_npc_attitude | **MISSING** |
| **Needs** | satisfy_need, apply_stimulus, mark_need_communicated | **MISSING** |
| **Navigation** | check_route, start_travel, move_to_zone, check_terrain, discover_zone, discover_location, view_map | **MISSING** (StateChange.MOVE partial replacement) |
| **Items** | acquire_item, drop_item | **MISSING** (StateChange.TAKE/DROP partial replacement) |
| **World Spawning** | spawn_storage, spawn_item | **MISSING** (`create_entity` can create items, not storages) |
| **State** | advance_time, entity_move, start_combat, end_combat | Handled via `time_passed_minutes` and StateChange |
| **Quests** | assign_quest, update_quest, complete_quest | **MISSING** |
| **Facts** | record_fact | Present |
| **NPC Scene** | introduce_npc, npc_leaves | `create_entity` partial replacement |

### Critical Missing Tools

1. **satisfy_need** - No way to satisfy hunger/thirst/stamina/etc.
2. **update_npc_attitude** - No relationship tracking
3. **Quest tools** - No quest assignment/completion
4. **spawn_storage** - Can't create furniture/containers

---

## Testing Procedure

### Test Scenarios

| Category | Actions to Test |
|----------|-----------------|
| **Observation** | "look around", "examine [X]", "search the room" |
| **Movement** | "go outside", "walk to [location]", "enter the building" |
| **Social** | "talk to [NPC]", "ask about [topic]", "greet [NPC]" |
| **Items** | "take [item]", "drop [item]", "pick up [item]" |
| **Needs** | "eat some food", "drink water", "rest" |
| **Skills** | "try to pick the lock", "sneak past", "persuade" |
| **Combat** | "attack [target]", "defend", "flee" |
| **OOC** | "ooc: what time is it?", "ooc: what skills do I have?" |

### After Each Turn, Check:

#### A. Narrative Quality
- [ ] Response makes sense given input
- [ ] No fabricated player actions (didn't say "I attack", GM shouldn't narrate attack)
- [ ] Second-person narration ("you" not "the player")
- [ ] No raw data structures in output
- [ ] No hallucinated items/NPCs not in DB

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

-- Recent turns
SELECT turn_number, LEFT(player_input, 50) as input, LEFT(gm_response, 100) as response
FROM turns WHERE session_id = ? ORDER BY turn_number DESC LIMIT 5;
```

#### C. Tool Calls
- [ ] Skill checks called when outcome is uncertain
- [ ] create_entity used for new NPCs/items (not hallucinated)
- [ ] record_fact used for world lore

#### D. Time Advancement
- Expected: ~1-5 min per action
- Combat: 1 min, Talk: 2 min, Search: 2 min, Move: 5 min
- Check `time_manager.advance_time()` via applier.py

#### E. Needs Decay
- `needs_manager.apply_time_decay()` should be called
- Decay rate depends on activity type

---

## Known Issues from Sessions 79 & 80

These issues were found in previous testing (may be legacy pipeline):

| Issue | Description | Severity |
|-------|-------------|----------|
| Time not advancing | 21 turns, only 12 min passed | Critical |
| Raw GMResponse output | Turn 13 showed "GMResponse:\n- narrative:..." | High |
| Third-person narration | "The player performed..." | Medium |
| "Nothing happens" response | Generic unhelpful response | Medium |
| NPCs ignore player | "talk to him" → NPCs talk to each other | High |
| Ambiguous ref loop | "Which him?" → "Joe" → "Which him?" | Medium |
| No relationships tracked | Empty relationships table | High |
| No NPC needs | NPCs have no character_needs | Medium |
| No NPC schedules | Empty schedules table | Low |
| No NPC goals | Empty npc_goals table | Low |

---

## Expected Behavior by Action Type

### Observation ("look", "examine", "search")
- **Time**: 1-2 minutes
- **Tools**: None required (or create_entity if discovering something)
- **Check**: Scene description matches DB location

### Movement ("go", "walk", "enter")
- **Time**: 2-5 minutes
- **Tools**: None (StateChange.MOVE)
- **Check**: Player location updated in `npc_extensions.current_location`

### Social ("talk", "ask", "greet")
- **Time**: 2-5 minutes
- **Tools**: update_npc_attitude **MISSING**
- **Check**: Relationships should update (won't without tool)

### Items ("take", "drop", "pick up")
- **Time**: 1 minute
- **Tools**: None (StateChange.TAKE/DROP)
- **Check**: `items.holder_id` updated

### Needs ("eat", "drink", "rest", "sleep")
- **Time**: Varies (rest: 30 min, sleep: 8 hours)
- **Tools**: satisfy_need **MISSING**
- **Check**: `character_needs` should update (won't without tool)

### Skills ("pick lock", "sneak", "persuade")
- **Time**: 1-5 minutes
- **Tools**: skill_check
- **Check**: Roll result affects narrative

### Combat ("attack", "fight")
- **Time**: 1 minute per round
- **Tools**: attack_roll, damage_entity
- **Check**: HP updated in entity attributes

### OOC ("ooc: ...")
- **Time**: 0 minutes
- **Tools**: record_fact (for invented lore)
- **Check**: is_ooc flag set on turn

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

---

## Quick DB Connection

```bash
PGPASSWORD=bRXAKO0T8t23Wz3l9tyB psql -h 138.199.236.25 -U langgraphrpg -d langgraphrpg
```

---

## References

- **New GM Pipeline**: `src/gm/`
- **Legacy Pipeline**: `src/agents/nodes/game_master_node.py`
- **Legacy Tools**: `src/agents/tools/gm_tools.py`
- **Gameplay Testing Guide**: `.claude/docs/gameplay-testing-guide.md`
