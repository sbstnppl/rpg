# GM Calls Non-Existent move_to Tool - Player Movement Fails

**Status:** ✅ RESOLVED
**Priority:** High
**Detected:** 2025-12-28
**Resolved:** 2025-12-29
**Related Sessions:** 301

## Resolution

The `move_to` tool has been implemented in `src/gm/tools.py` (lines 2208-2260). The tool:
- Accepts a destination (location key or display name) and travel method
- Fuzzy matches existing locations or auto-creates new ones
- Calculates realistic travel time based on distance
- Updates player location in the database
- Returns success with travel details

## Problem Statement

When the player tries to move to a different location, the GM calls a `move_to` tool that doesn't exist. The tool returns an error "Unknown tool: move_to", but the GM then narrates the movement anyway. However, since no StateChange.MOVE was applied, the player's location in the database is not updated, causing a disconnect between narrative and game state.

## Current Behavior

Turn 5 audit log shows:
```
### [USER]
I'll head outside to the village square

### [ASSISTANT]
(tool_use: move_to with destination='village_square')

### [TOOL]
{"error": "Unknown tool: move_to"}

### [USER]
CHARACTER ERROR - You broke character...
```

After the turn:
- Narrative says: "you step into the cool evening air of the village, the lantern-lit expanse of Village Square"
- Database shows: `current_location = 'village_tavern'` (unchanged)

This creates a confusing state where the story says one thing but the game state is different.

## Expected Behavior

According to `docs/gm-pipeline-e2e-testing.md`:
- Movement should use `StateChange.MOVE` (not a `move_to` tool)
- The player's location should update in `npc_extensions.current_location`
- Time should advance 1-2 minutes for local movement

The GM prompt may need to:
1. Include a `move_player` or `change_location` tool
2. OR instruct GM to return StateChange.MOVE in its response schema
3. OR have movement handled differently

## Investigation Notes

From the system prompt, the GM is told:
- "Taking items" -> take_item()
- "Dropping items" -> drop_item()

But no movement tool is documented in the system prompt. The GM is improvising a `move_to` tool that doesn't exist.

From `docs/gm-pipeline-e2e-testing.md`:
```
### Movement - Local ("go outside", "enter building")
- **Time**: 1-2 minutes
- **Tools**: None (StateChange.MOVE)
- **Check**: Player location updated in `npc_extensions.current_location`
```

This suggests movement is supposed to work via StateChange, not a tool.

## Root Cause

The GM's system prompt doesn't explain how to handle movement. The LLM (qwen3) guesses there should be a `move_to` tool and calls it, but no such tool exists.

## Proposed Solution

Options:
1. **Add move_player tool**: Create a tool that GM can call to move the player
2. **Document StateChange usage**: If GM is supposed to return StateChange.MOVE in structured output, make this clear in the prompt
3. **Add movement to TOOL WORKFLOW**: Add movement instructions like "Movement -> move_player() or return StateChange.MOVE"

## Implementation Details

<Specific code changes after investigation>

## Files to Modify

- [ ] `src/gm/prompts.py` - Add movement instructions to system prompt
- [ ] `src/gm/tools.py` - Add move_player tool if that's the approach
- [ ] `src/gm/schemas.py` - Ensure StateChange.MOVE is properly defined

## Test Cases

- [ ] Test case 1: Player says "go outside" - location updates in DB
- [ ] Test case 2: Player says "enter the building" - location updates
- [ ] Test case 3: Movement advances time appropriately (1-2 min local)

## Related Issues

- Movement may also affect anticipation/cache (if enabled)

## References

- `logs/llm/session_301/turn_005_20251228_204023_gm.md` - Audit log showing issue
- `docs/gm-pipeline-e2e-testing.md` - Documents expected movement behavior
- `src/gm/tools.py` - Current tool definitions
- `src/gm/prompts.py` - GM system prompt
