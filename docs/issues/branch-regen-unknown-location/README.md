# Branch Regeneration Fails for Unknown Location Destinations

**Status:** Awaiting Verification
**Priority:** High
**Verification:** 0/3
**Last Verified:** -
**Detected:** 2026-01-19
**Related Sessions:** 348

## Problem Statement

When the branch generator creates a branch with an `UPDATE_LOCATION` delta that references a location that doesn't exist in the world (e.g., `tavern_cellar`), the delta post-processor attempts regeneration but fails. This results in a broken narrative being displayed to the player with the raw input truncated.

## Root Cause

The system had two spatial concepts that the LLM didn't properly distinguish:
1. **Locations** - Distinct rooms/areas (e.g., `village_tavern`, `village_square`)
2. **Positions** - Spots within a location (e.g., "behind the bar", "at a corner table")

When the player said "sneak behind the bar", the LLM incorrectly treated this as a MOVE action requiring `UPDATE_LOCATION` and hallucinated `tavern_cellar` as a destination. It should have been handled as a position change within the same room with a stealth skill check.

## Solution Implemented

### Part 1: Updated Branch Generator Prompt

Added explicit guidance to the branch generator system prompt about position vs location changes:

**File:** `src/world_server/quantum/branch_generator.py` (line ~285)

```
IMPORTANT: UPDATE_LOCATION vs POSITION CHANGE
- UPDATE_LOCATION: Moving to a DIFFERENT room/area (must use a key from Exits or Other known locations)
- POSITION CHANGE: Moving within the same room (behind bar, at table, near door, by fireplace)

Position changes within a room do NOT require update_location deltas.
Instead, describe the position change in the narrative only.

Examples:
- "go to the village square" → UPDATE_LOCATION to village_square (it's in Exits)
- "sneak behind the bar" → NO update_location (same room, just a position)
- "climb up to the rafters" → NO update_location (same room, elevated position)
```

### Part 2: Graceful Delta Removal

Added graceful handling for cases where the LLM still hallucinates invalid locations:

**File:** `src/world_server/quantum/delta_postprocessor.py`

Added `_remove_invalid_location_deltas()` method that:
- Filters out `UPDATE_LOCATION` deltas with invalid destinations
- Logs warnings for tracking
- Lets the branch continue with remaining deltas intact
- The player doesn't actually move, but the narrative proceeds

This replaces the previous behavior which triggered regeneration (and often failed on retry too).

## Tests Added

### New Test Class: `TestRemoveInvalidLocationDeltas`
- `test_remove_invalid_destination` - Invalid destination is removed
- `test_preserve_valid_destination` - Valid exits are preserved
- `test_preserve_candidate_location` - Non-adjacent known locations work
- `test_remove_only_invalid_keep_other_deltas` - Only bad deltas removed
- `test_position_change_scenario` - Simulates "sneak behind the bar"

### Updated Test: `TestProcessAsync`
- `test_process_async_unknown_destination_removed_gracefully` - Verifies graceful removal

### New Test Class: `TestSystemPromptContent`
- `test_system_prompt_includes_position_vs_location_guidance`
- `test_system_prompt_warns_against_hallucinating_locations`
- `test_system_prompt_includes_skill_check_rules`
- `test_system_prompt_includes_entity_grounding_rules`

## Verification Steps

1. Run quantum pipeline tests: `pytest tests/test_world_server/test_quantum/test_delta_postprocessor.py tests/test_world_server/test_quantum/test_branch_generator.py -v`
2. Play-test: "sneak behind the bar" should work without errors
3. Play-test: "go to the square" should still work (valid location move)

## Files Modified

- [x] `src/world_server/quantum/branch_generator.py` - Added position vs location guidance
- [x] `src/world_server/quantum/delta_postprocessor.py` - Added graceful removal
- [x] `tests/test_world_server/test_quantum/test_delta_postprocessor.py` - Added tests
- [x] `tests/test_world_server/test_quantum/test_branch_generator.py` - Added prompt tests

## Related Issues

- Branch validation showing entity key collisions (separate issue)
- Skill checks not triggering (separate issue - skill checks for sneaking are context-dependent)

## References

- `src/world_server/quantum/` - Quantum pipeline code
- `docs/quantum-branching/README.md` - Quantum architecture docs
