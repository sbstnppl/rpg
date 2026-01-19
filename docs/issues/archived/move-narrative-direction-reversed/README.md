# MOVE Action Narrative Direction Reversed

**Status:** Done
**Priority:** High
**Detected:** 2026-01-03
**Resolved:** 2026-01-03
**Related Sessions:** Session 335 (Turn 5), Session 336 (Turn 1)

## Problem Statement

When a player executes a MOVE action (e.g., "go to the village square"), the generated narrative describes movement in the WRONG direction. The LLM describes going TO the tavern when the player asked to go to the village square. This is caused by the manifest being built for the destination location, which creates a contradiction with the player's input.

## Current Behavior

**Player input:** "go to the village square"
**Player location:** `village_tavern`

**Prompt sent to LLM:**
```
SCENE: Village Square  <-- Destination manifest!
...
PLAYER INPUT: "go to the village square"
```

**LLM sees contradiction:** Player says "go to village_square" but the SCENE says they're already at Village Square. LLM generates narrative about going to one of the exits (the tavern).

**Resulting narrative:**
> You step confidently from the center of the village square toward the The Rusty Tankard...

This is BACKWARDS - the narrative describes going TO the tavern instead of FROM it.

## Expected Behavior

1. Narrative should describe leaving the origin location
2. Narrative should describe arriving at the destination
3. Prompt should not create contradictions between SCENE and player input

## Investigation Notes

From `pipeline.py` lines 813-820:
```python
if action.action_type == ActionType.MOVE and action.target_key:
    # Build manifest for destination so narrative describes where player arrives
    try:
        generation_manifest = await self._build_manifest(
            self._get_player_id(), action.target_key
        )
        generation_location = action.target_key
```

The code intentionally builds the destination manifest so the LLM can describe the arrival scene. But this creates a contradiction when combined with "PLAYER INPUT: go to X" since the SCENE shows X.

## Root Cause

The pipeline builds the destination manifest for MOVE actions (lines 813-820), but:
1. The SCENE header shows the destination location
2. The PLAYER INPUT says "go to [destination]"
3. The LLM interprets this as: "Player is at destination but wants to go to destination" = contradiction
4. LLM "resolves" the contradiction by having the player go to an exit instead

## Proposed Solution

Options:
1. **Add movement context to prompt**: "Player is MOVING FROM {origin} TO {destination}. Describe their arrival at {destination}."
2. **Use origin manifest but add destination info**: Keep origin SCENE, add separate DESTINATION section
3. **Two-phase narrative**: Generate departure from origin, then arrival at destination

Recommended: Option 1 - Add clear movement context to the prompt

## Implementation Details

Modify `branch_generator.py` to add movement context when generating MOVE branches:
```python
if action.action_type == ActionType.MOVE:
    context_lines.append(f"MOVEMENT: Player is traveling FROM {origin_location} TO {destination_location}")
    context_lines.append("Describe their journey and arrival at the destination.")
```

## Resolution

Implemented Option 1 - Added movement context to the prompt:

1. **BranchContext extended** (`branch_generator.py`):
   - Added `origin_location_key` and `origin_location_display` fields
   - These track where the player is coming FROM during MOVE actions

2. **Prompt updated** (`branch_generator.py` `_build_generation_prompt()`):
   - Added MOVEMENT DIRECTION section when action is MOVE and origin is known
   - Explicitly tells LLM: "Player is traveling FROM {origin} TO {destination}"
   - Clarifies that SCENE shows destination, narrative should describe arrival

3. **Pipeline updated** (`pipeline.py`):
   - `_build_branch_context()` now accepts `origin_location_key` parameter
   - MOVE action handling passes origin location to context builder
   - Added `new_location` field to TurnResult for location tracking

## Files Modified

- [x] `src/world_server/quantum/branch_generator.py` - Added movement context to prompt
- [x] `src/world_server/quantum/pipeline.py` - Pass origin location to branch generator

## Test Results

All tests pass:
- `test_branch_generator.py` - 21 passed
- `test_pipeline.py` - 22 passed
- `test_collapse.py` - 58 passed

## Related Issues

- `docs/issues/movement-location-update-failed/` - Related but different (that was about turn recording)
- `docs/issues/narrative-wrong-location-entities/` - May be partially explained by this issue

## References

- `src/world_server/quantum/pipeline.py` lines 813-820
- `src/world_server/quantum/branch_generator.py`
- Log file: `logs/llm/orphan/20260103_113923_unknown.md`
