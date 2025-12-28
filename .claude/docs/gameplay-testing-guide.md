# Gameplay Testing & Observation Guide

This document outlines how to observe, assess, and debug the RPG game during play sessions.

## System Architecture Overview

### Pipeline Selection
The game has two pipelines (use `--pipeline` flag):
- **system-authority** (default, recommended): System decides outcomes mechanically, LLM only narrates
- **legacy** (deprecated): LLM decides everything, risk of state/narrative drift

### System-Authority Pipeline Flow
```
START → ContextCompiler → ParseIntent → ValidateActions → ComplicationOracle
                                                              ↓
                         END ← Persistence ← Narrator ← ExecuteActions
```

## Player Input Processing

### Input Flow Stages
1. **CLI Pre-validation** (`src/cli/commands/game.py:88-187`)
   - Quick checks before graph execution
   - Validates: inventory space, item possession, weight limits
   - Returns enhanced input with `[VALIDATED: action 'target']` prefix

2. **Context Compiler** (`src/agents/nodes/context_compiler_node.py`)
   - Gathers scene context: player, location, NPCs, items, time

3. **Parse Intent** (`src/agents/nodes/parse_intent_node.py`)
   - Converts natural language to structured `Action` objects
   - Pattern matching first (fast), LLM fallback for complex inputs
   - 33 action types defined in `src/parser/action_types.py`

4. **Validate Actions** (`src/agents/nodes/validate_actions_node.py`)
   - Mechanical constraint checking
   - Returns validation results with risk tags

5. **Execute Actions** (`src/agents/nodes/execute_actions_node.py`)
   - Applies state changes through managers
   - Produces `TurnResult` with execution outcomes

6. **Narrator** (`src/agents/nodes/narrator_node.py`)
   - Generates prose from mechanical facts only
   - Prevents hallucination through constraint-based generation

7. **Persistence** (`src/agents/nodes/persistence_node.py`)
   - Saves Turn record and all state changes

### Action Types Recognized
- **Movement:** MOVE, ENTER, EXIT
- **Item:** TAKE, DROP, GIVE, USE, EQUIP, UNEQUIP, EXAMINE, OPEN, CLOSE
- **Combat:** ATTACK, DEFEND, FLEE
- **Social:** TALK, ASK, TELL, TRADE, PERSUADE, INTIMIDATE
- **World:** SEARCH, REST, WAIT, SLEEP
- **Consumption:** EAT, DRINK
- **Skill:** CRAFT, LOCKPICK, SNEAK, CLIMB, SWIM
- **Meta:** LOOK, INVENTORY, STATUS, CUSTOM

## Database Tables to Monitor

### Core Session Tables
| Table | What to Check |
|-------|---------------|
| `game_sessions` | Session created with correct setting, player reference |
| `turns` | Player input, GM response, turn number sequence |
| `time_states` | Day/time advancing correctly |

### Entity Tables
| Table | What to Check |
|-------|---------------|
| `entities` | Player/NPC creation, `is_alive`, `is_active` flags |
| `entity_attributes` | STR, DEX, CON, INT, WIS, CHA values |
| `npc_extensions` | NPC location, activity, mood, companion status |
| `entity_vital_states` | Health status, death tracking |

### Character State Tables
| Table | What to Check |
|-------|---------------|
| `character_needs` | All 10 needs (hunger, thirst, energy, hygiene, comfort, wellness, social_connection, morale, sense_of_purpose, intimacy) |
| `needs_communication_log` | When needs were last narrated to player |
| `body_injuries` | Injury tracking, recovery progress |
| `mental_conditions` | PTSD, anxiety, etc. |

### Item Tables
| Table | What to Check |
|-------|---------------|
| `items` | `owner_id` vs `holder_id`, `body_slot`, `body_layer` |
| `storage_locations` | ON_PERSON, CONTAINER, PLACE types |

### Relationship Tables
| Table | What to Check |
|-------|---------------|
| `relationships` | trust, liking, respect, romantic_interest (0-100) |
| `relationship_changes` | Audit trail of changes |
| `relationship_milestones` | Threshold crossings |

### World State Tables
| Table | What to Check |
|-------|---------------|
| `locations` | Hierarchy, accessibility, visit tracking |
| `facts` | SPV facts (Subject-Predicate-Value) |
| `world_events` | Dynamic events, player awareness |
| `complication_history` | Generated complications |

## Quick Database Queries

```sql
-- Get current session
SELECT id, setting, status, total_turns FROM game_sessions
WHERE status = 'active' ORDER BY id DESC LIMIT 1;

-- Check player entity
SELECT entity_key, display_name, entity_type, is_active, is_alive
FROM entities WHERE session_id = <SESSION_ID> AND entity_type = 'PLAYER';

-- Check all needs for player
SELECT n.*, e.display_name
FROM character_needs n
JOIN entities e ON n.entity_id = e.id
WHERE n.session_id = <SESSION_ID>;

-- Check inventory (items held by player)
SELECT i.item_key, i.display_name, i.holder_id, i.owner_id, i.body_slot, i.body_layer
FROM items i
JOIN entities e ON i.holder_id = e.id
WHERE i.session_id = <SESSION_ID> AND e.entity_type = 'PLAYER';

-- Check time state
SELECT current_day, current_time, day_of_week, weather
FROM time_states WHERE session_id = <SESSION_ID>;

-- Check recent turns
SELECT turn_number, player_input, LEFT(gm_response, 100) as response_preview
FROM turns WHERE session_id = <SESSION_ID>
ORDER BY turn_number DESC LIMIT 5;

-- Check relationships
SELECT e1.display_name as from_entity, e2.display_name as to_entity,
       r.trust, r.liking, r.respect, r.romantic_interest
FROM relationships r
JOIN entities e1 ON r.from_entity_id = e1.id
JOIN entities e2 ON r.to_entity_id = e2.id
WHERE r.session_id = <SESSION_ID>;

-- Check NPCs at current location
SELECT e.display_name, n.current_location, n.current_activity, n.mood
FROM entities e
JOIN npc_extensions n ON e.id = n.entity_id
WHERE e.session_id = <SESSION_ID> AND e.is_active = true;
```

## Key Design Patterns to Verify

### Owner vs Holder Pattern
Items have two ownership fields:
- `owner_id`: Permanent owner (who the item belongs to)
- `holder_id`: Current holder (who has it now)

When verifying:
- After TAKE: both should be player's entity_id
- After DROP: holder_id should be NULL, owner_id unchanged
- After GIVE: holder_id = recipient, owner_id unchanged (unless gift)
- Theft: `is_stolen`, `was_ever_stolen`, `stolen_from_id` flags

### Body Slots + Layers Pattern
Clothing uses realistic outfit tracking:
- `body_slot`: Where item is worn (upper_body, lower_body, feet, etc.)
- `body_layer`: Layer number (0=innermost, higher=outer)

Visibility rules:
- Items at max layer in slot are visible
- Unless covered by another slot (full_body covers torso/legs)

### Session Scoping
ALL queries must filter by `session_id` to prevent cross-session data leakage:
```python
# Correct
db.query(Entity).filter(Entity.session_id == game_session.id)

# WRONG - could get data from other sessions
db.query(Entity).all()
```

### Needs Communication System
Prevents repetitive narration ("your stomach growls" every turn):
- **Alerts**: State changes (hunger dropped to "hungry") - narrate immediately
- **Reminders**: Ongoing negative states not mentioned for 2+ in-game hours
- **Status**: Reference-only for GM awareness

Check `needs_communication_log` table for when needs were last narrated.

## Common Issues to Watch For

### Character Creation
1. **Confirmation bypass**: BACKGROUND/PERSONALITY sections should always ask for confirmation
2. **Missing display**: Revisiting sections should show current saved value
3. **Field extraction**: Check if AI extracts all required fields

### Gameplay
1. **State/narrative drift**: GM describing things that didn't mechanically happen
2. **Phantom items**: GM mentioning items that don't exist in database
3. **Location mismatch**: Player location in state vs database
4. **Need decay**: Needs should decay based on activity type and time elapsed

### Inventory
1. **Weight limits**: Check `weight` against carrying capacity
2. **Slot limits**: Check `provides_slots` and current inventory count
3. **Equipment visibility**: Check `is_visible` flag after equip/unequip

## Managers Reference

| Manager | Responsibility | Key Methods |
|---------|---------------|-------------|
| `NeedsManager` | Character needs tracking | `satisfy_need()`, `apply_time_decay()`, `get_active_effects()` |
| `ItemManager` | Inventory & equipment | `transfer_item()`, `equip_item()`, `get_inventory()` |
| `EntityManager` | Entity CRUD | `get_player()`, `get_entities_at_location()` |
| `LocationManager` | World hierarchy | `get_location()`, `record_visit()`, `get_accessible_locations()` |
| `RelationshipManager` | Social bonds | `modify_relationship()`, `get_relationship()` |
| `TimeManager` | Game time | `advance_time()`, `get_period_of_day()` |
| `CombatManager` | Combat resolution | `resolve_attack()`, `apply_damage()` |
| `FactManager` | SPV fact store | `add_fact()`, `get_facts()` |

## Testing Commands

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_managers/test_needs_manager.py

# Run with verbose output
pytest -v

# Run tests matching pattern
pytest -k "character"

# Run with coverage
pytest --cov=src
```

## Interactive Gameplay Monitor

For hands-on debugging, use the gameplay monitor script:

```bash
python scripts/gameplay_monitor.py
```

This creates a test session and runs predefined actions while displaying:
- All LLM calls with tokens
- Tool calls and results
- State changes (needs, time, location)
- Automatic issue and milestone tracking

The script includes 15 predefined actions covering scene intro, dialog, item interaction, skill checks, and time passage. It stops after 5 milestones or 5 issues.

## Debugging Tips

1. **Enable debug logging**: Check `src/llm/` for provider logging
2. **Inspect GameState**: Add breakpoints in node functions to see state flow
3. **Check validation results**: `state["validation_results"]` shows why actions failed
4. **Review turn history**: `state["scene_context"]` includes recent turns
5. **Trace manager calls**: Managers log operations to understand state changes

## Files to Reference

- `src/agents/graph.py` - Pipeline definitions
- `src/agents/state.py` - GameState schema
- `src/parser/patterns.py` - Action pattern matching
- `src/validators/action_validator.py` - Validation logic
- `src/executor/action_executor.py` - Execution logic
- `src/managers/` - All business logic
- `src/database/models/` - Database schema
