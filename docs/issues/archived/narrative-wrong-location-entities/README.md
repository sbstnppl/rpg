# Narrative References Entities from Wrong Location

**Status:** Done
**Priority:** High
**Detected:** 2026-01-03
**Related Sessions:** Session 335, Turn 8

## Problem Statement

The narrative generation includes entities (NPCs, environmental details) from a previous location rather than the current scene. When the player is at `village_square`, the narrative mentions "Old Tom behind the bar" and a "loose floorboard" - details that belong to the tavern location, not the outdoor market.

## Current Behavior

**Player location:** `village_square`
**Player action:** "try to pickpocket one of the market vendors"

**Narrative output:**
> You slip your hand toward a market vendor's coin purse, but your Leather Boots catch on a **loose floorboard**, clattering loudly. **Old Tom glances up from behind the bar**, frowning, and the vendor spins around...

**Issues:**
1. "Old Tom behind the bar" - Old Tom is an NPC at `village_tavern`, not `village_square`
2. "loose floorboard" - market stalls are outdoors on cobblestones, not wooden floor

## Root Cause Analysis

This issue has **multiple contributing factors**:

### 1. Turn Recording Bug (FIXED)
The turn was saved with the OLD location before deltas were committed. This has been fixed in `game.py`.

### 2. MOVE Action Manifest Issue (SEPARATE ISSUE)
For MOVE actions, the pipeline builds the manifest for the DESTINATION location, which includes the destination's NPCs in the "AVAILABLE ENTITIES" list. This confuses the LLM about which direction the player is moving.

See: `docs/issues/move-narrative-direction-reversed/`

### 3. Potential LLM Hallucination
The LLM may reference entities from conversation history despite them not being in the current manifest. The prompt says "ONLY these entities exist" but the model may still generate references to recently-seen entities.

## Resolution

**All fixes implemented:**
- `game.py`: Turn now saves with POST-action location (commit before save)
- `entity_manager.py`: Removed display_name fallback in `get_npcs_in_scene()` to prevent false matches
- `collapse.py`: Now raises exception on invalid location instead of silent failure
- `branch_generator.py`: Added movement context for MOVE actions to clarify direction
- `pipeline.py`: Passes origin location to branch context, added `new_location` to TurnResult

## Files Modified

- [x] `src/cli/commands/game.py` - Reordered commit/refresh before save
- [x] `src/managers/entity_manager.py` - Remove display_name fallback
- [x] `src/world_server/quantum/collapse.py` - Raise exception on invalid location
- [x] `src/world_server/quantum/branch_generator.py` - Added movement context to prompt
- [x] `src/world_server/quantum/pipeline.py` - Pass origin location, added new_location to TurnResult

## Follow-up Investigation

All issues have been resolved. If NPCs still appear at wrong locations after these fixes:

1. **Check manifest construction** - Verify correct location is used for non-MOVE actions
2. **Add narrative validation** - Post-generation check against manifest
3. **Stronger prompt instructions** - Emphasize "ONLY these entities"

## Related Issues

- `docs/issues/movement-location-update-failed/` - Done (turn recording)
- `docs/issues/move-narrative-direction-reversed/` - Done (manifest for MOVE actions)

## References

- `src/gm/context_builder.py` - Manifest building
- `src/world_server/quantum/branch_generator.py` - Prompt construction
