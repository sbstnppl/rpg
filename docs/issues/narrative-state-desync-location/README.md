# Narrative State Desync - Location

**Status:** Done
**Priority:** High
**Detected:** 2026-01-03
**Completed:** 2026-01-03
**Related Sessions:** 343, 344, 345

## Problem Statement

The narrative describes the player entering a location (kitchen) that doesn't exist in the database. The system attempts to apply an UPDATE_LOCATION delta but fails because the target location isn't registered. However, the narrative still displays as if the movement succeeded, causing a desync between what the player reads and the actual game state.

## Current Behavior (FIXED)

Before fix:
```
Player input: "try to sneak behind the bar and into the kitchen"
Error: Failed to apply delta... location 'village_tavern_kitchen' not found
Narrative: "You slip into the kitchen without a sound..."  <-- DESYNC!
Player location: Still village_tavern
```

After fix:
```
Player input: "sneak into the kitchen"
Log: Regenerating branch: UPDATE_LOCATION to unknown destination 'village_tavern_kitchen'. Valid exits: ['village_square']
Narrative: "You attempt to sneak into the kitchen..."  <-- Fallback, no desync
Player location: Still village_tavern (correct)
```

## Root Cause

The `DeltaPostProcessor.process_async()` method (used by branch generator) checked for entity key validity but NOT for location destination validity. The flow was:

1. LLM generates narrative + UPDATE_LOCATION delta with invented location key
2. `process_async()` validates entity keys (could be clarified by LLM)
3. BUT skips location validation - locations cannot be clarified by LLM
4. Branch is accepted, narrative is generated
5. Collapse tries to apply delta, fails (location not found)
6. Error logged, but narrative already displayed = DESYNC

## Solution Implemented

Added `_check_unknown_locations()` method to `DeltaPostProcessor` and called it early in both `process()` (sync) and `process_async()` methods. If an UPDATE_LOCATION delta references a destination not in `manifest.exits`, the branch is rejected with `RegenerationNeeded`.

## Files Modified

- [x] `src/world_server/quantum/delta_postprocessor.py`
  - Added `_check_unknown_locations()` method (lines 328-350)
  - Added destination validation to `_check_unknown_keys()` (lines 317-324)
  - Added location check call in `process_async()` (lines 510-517)

- [x] `tests/test_world_server/test_quantum/test_delta_postprocessor.py`
  - Added `test_update_location_unknown_destination` (sync path)
  - Added `test_update_location_valid_destination` (sync path)
  - Added `test_process_async_unknown_destination_triggers_regen` (async path)
  - Added `test_process_async_valid_destination_passes` (async path)

## Test Cases

- [x] Test case 1: Movement to non-existent location triggers regeneration (no desync narrative)
- [x] Test case 2: Valid exits pass validation normally
- [x] Test case 3: Both sync and async paths validate location destinations
- [x] Test case 4: LLM is NOT called for location validation (locations can't be clarified)

## Verification

Tested in gameplay (session 345):
- Input: "sneak into the kitchen"
- Result: Regeneration triggered, fallback narrative shown
- Player location: Remained in `village_tavern` (no desync)

## Related Issues

- docs/issues/narrative-state-desync-items/ (similar desync pattern)
