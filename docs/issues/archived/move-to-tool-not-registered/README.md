# move_to Tool Not Registered in execute_tool

**Status:** Done
**Priority:** High
**Detected:** 2025-12-29
**Related Sessions:** Session 302, Turn 6

## Problem Statement

The `move_to` tool is defined in the tool definitions (available to the LLM) and has a method implementation, but it's NOT registered in the `execute_tool()` dispatcher. When the LLM calls `move_to`, it returns `{"error": "Unknown tool: move_to"}`, and the player's location never updates.

This is a **critical bug** that breaks all player movement/travel functionality.

## Current Behavior

From audit log `turn_006_20251229_161047_gm.md`:

1. LLM calls `move_to`:
```python
tool_name='move_to', tool_input={'destination': 'village_square', 'travel_method': 'walk'}
```

2. Tool execution returns error:
```json
{"error": "Unknown tool: move_to"}
```

3. Player location remains unchanged:
```sql
SELECT current_location FROM npc_extensions WHERE entity_id = player_id;
-- Result: 'village_tavern' (unchanged)
```

4. Narrative describes movement that never happened, creating state/narrative mismatch.

## Expected Behavior

When `move_to` is called:
1. Tool should execute successfully
2. Player's `current_location` should update
3. Time should advance based on travel duration
4. Narrative should reflect the new location

## Investigation Notes

### Tool definition exists (line 764):
```python
{
    "name": "move_to",
    "description": "Move the player to a new location...",
    ...
}
```

### Method implementation exists (line 2208):
```python
def move_to(self, destination: str, travel_method: str = "walk") -> dict[str, Any]:
    ...
```

### BUT NOT registered in execute_tool() (lines 901-1032):
The `execute_tool()` method has cases for:
- skill_check, attack_roll, damage_entity
- create_entity, record_fact
- get_npc_attitude
- assign_quest, update_quest, complete_quest
- create_task, complete_task
- create_appointment, complete_appointment
- apply_stimulus, mark_need_communicated
- take_item, drop_item, give_item
- satisfy_need
- get_rules, get_scene_details, get_player_state, get_story_context, get_time

**Missing**: `move_to` (the ONLY missing tool)

Falls through to:
```python
else:
    return {"error": f"Unknown tool: {tool_name}"}
```

## Root Cause

The `move_to` tool was added to the tool definitions and has an implementation, but the developer forgot to add the `elif tool_name == "move_to":` case in `execute_tool()`.

## Proposed Solution

Add the missing case in `execute_tool()`:

```python
elif tool_name == "move_to":
    return self.move_to(**filtered)
```

This should be added alongside the other tool cases around line 1020.

## Implementation Details

Simple one-line fix in `src/gm/tools.py`:

```python
# Around line 1020, before the else clause:
elif tool_name == "move_to":
    return self.move_to(**filtered)
```

## Files to Modify

- [ ] `src/gm/tools.py` - Add `move_to` case to `execute_tool()`
- [ ] `tests/test_gm/test_tools.py` - Add test for move_to execution

## Test Cases

- [ ] Test case 1: `move_to` tool executes successfully
- [ ] Test case 2: Player location updates after `move_to`
- [ ] Test case 3: Time advances appropriately for travel

## Related Issues

- This is a blocking issue for all player movement
- Causes narrative/state mismatch

## References

- `src/gm/tools.py:764` - Tool definition
- `src/gm/tools.py:901-1032` - execute_tool dispatcher (missing case)
- `src/gm/tools.py:2208` - move_to method implementation
- `logs/llm/session_302/turn_006_20251229_161047_gm.md` - Audit log with error
