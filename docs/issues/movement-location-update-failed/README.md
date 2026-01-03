# Movement Location Update Failed

**Status:** Done
**Priority:** High
**Detected:** 2026-01-03
**Resolved:** 2026-01-03
**Related Sessions:** Session 335, Turn 5

## Problem Statement

When the player requested to "go to the village square" from village_tavern, the movement failed in two ways:
1. The player's `current_location` was not updated in the database (stayed at `village_tavern`)
2. The narrative incorrectly described moving TO the tavern instead of FROM it

## Current Behavior (BEFORE FIX)

**Player input:** "go to the village square"
**Player location before:** `village_tavern`
**Player location after:** `village_tavern` (unchanged - BUG)

**Narrative output:**
> You step confidently from the center of the village square toward the The Rusty Tankard...

The narrative describes movement in the WRONG direction.

## Root Cause

**Issue 1 (Location not recorded):** Turn was saved with OLD location before delta changes were committed.

In `game.py`:
```python
# OLD (buggy) order:
_save_turn_immediately(..., player_location=player_location)  # Old location!
db.commit()
db.refresh(player)  # Too late - turn already saved
player_location = _get_player_current_location(...)
```

**Issue 2 (Narrative direction):** This is a SEPARATE issue - the manifest is built for the destination location, confusing the LLM. See `docs/issues/move-narrative-direction-reversed/`.

## Resolution

**Fixed in `game.py`:** Reordered to commit and refresh BEFORE saving turn:
```python
# NEW (fixed) order:
db.commit()  # Commit delta changes first
db.refresh(player)
player_location = _get_player_current_location(...)  # Get updated location
_save_turn_immediately(..., player_location=player_location)  # Now correct!
```

**Additional fixes:**
- `collapse.py`: Now raises ValueError instead of silently skipping invalid location keys
- `entity_manager.py`: Removed display_name fallback in `get_npcs_in_scene()` to prevent false matches

## Files Modified

- [x] `src/cli/commands/game.py` - Reordered commit/refresh before save
- [x] `src/world_server/quantum/collapse.py` - Raise exception on invalid location
- [x] `src/managers/entity_manager.py` - Remove display_name fallback

## Test Results

- All entity_manager tests pass (36 tests)
- All collapse tests pass (58 tests)

## Related Issues

- `docs/issues/move-narrative-direction-reversed/` - Separate issue for narrative direction
- `docs/issues/narrative-wrong-location-entities/` - May be related to manifest building

## References

- Plan file: `/Users/sebastian/.claude/plans/indexed-petting-hickey.md`
