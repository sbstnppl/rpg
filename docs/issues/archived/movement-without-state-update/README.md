# Movement Without State Update

**Status:** Done
**Priority:** Low
**Detected:** 2025-12-27
**Resolved:** 2025-12-27
**Related Sessions:** Session 293, Turn 15

## Problem Statement

When the player indicates they want to move to a new location, the LLM narrates the movement but no state update occurs. The player's location in the database remains unchanged.

## Current Behavior

Turn 15: Player said "I decide to leave the tavern and explore the village"

LLM response:
> "You turn away from the tavern's interior, stepping out into the cool evening air. The familiar creak of the door echoes behind you as you set your course toward the village beyond."

**No tool calls made.**

Database state: Player location still `village_tavern`

The narrative describes leaving, but no `move_entity` or similar tool was called.

## Expected Behavior

When player explicitly moves to a new location:
1. LLM should call a movement tool (or create the location if needed)
2. Player location should update in database
3. New location description should be provided

## Root Cause

1. **No movement tool**: No explicit tool for moving player
2. **State change not generated**: LLM didn't add MOVE to state_changes
3. **Prompt gap**: No instruction on how to handle player movement

## Solution Implemented

**Option C: Both tool AND prompt guidance** (following the `satisfy_need` pattern)

### 1. Added `move_to` Tool (`src/gm/tools.py`)

Tool definition with:
- Trigger words: go, walk, leave, travel, head, enter, exit, return, move to, explore
- Parameters: destination (required), travel_method (walk/run/sneak)
- Auto-creates locations if destination doesn't exist (uses `fuzzy_match_location` first)

Implementation:
- Uses `LocationManager.fuzzy_match_location()` to resolve informal destination names
- Uses `LocationManager.resolve_or_create_location()` for unknown destinations
- Calculates realistic travel time based on location hierarchy
- Updates player location via `LocationManager.set_player_location()`

### 2. Added Prompt Instructions (`src/gm/prompts.py`)

Added to MANDATORY TOOL CALLS section:
```
### PLAYER MOVEMENT → move_to
TRIGGER WORDS: go, walk, leave, travel, head, enter, exit, return, move to, explore
- "I leave the tavern" → move_to(destination="village_square")
- "I go to the well" → move_to(destination="the well")
- "I head home" → move_to(destination="player_home")
WHY: If you describe movement without calling move_to, the player's location won't update!
```

### 3. Travel Time Calculation

Travel time based on location relationship:
- Same location: 0 min
- Same parent (adjacent rooms): 2 min base
- Parent-child (entering/exiting): 2 min base
- Different areas: 10 min base

Modifiers:
- walk: 1.0x
- run: 0.5x
- sneak: 2.0x

## Files Modified

- [x] `src/gm/tools.py` - Added `move_to` tool definition and implementation
- [x] `src/gm/prompts.py` - Added movement instructions
- [x] `tests/test_gm/test_tools.py` - Added `TestMoveTo` class with 8 tests

## Test Cases

- [x] Test: Move to existing location → Location changes correctly
- [x] Test: Fuzzy match destination → "the well" matches "farmhouse_well"
- [x] Test: Unknown destination → Auto-creates new location
- [x] Test: Running is faster than walking
- [x] Test: Sneaking is slower than walking
- [x] Test: Same location → Zero travel time
- [x] Test: Empty destination → Error returned
- [x] Test: GMTools.location_key updated for subsequent tool calls

## Related Issues

- `unrealistic-time-passage` - Travel time now calculated realistically
- May need location discovery system (future enhancement)

## References

- `src/gm/tools.py:move_to` - Tool implementation
- `src/gm/tools.py:_calculate_travel_time` - Travel time logic
- `src/gm/prompts.py:66-72` - Prompt instructions
- `tests/test_gm/test_tools.py:TestMoveTo` - Test coverage
