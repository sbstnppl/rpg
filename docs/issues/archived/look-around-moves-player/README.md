# Look Around Command Unexpectedly Moves Player

**Status:** Done
**Priority:** High
**Detected:** 2026-01-03
**Resolved:** 2026-01-03
**Related Sessions:** 342

## Problem Statement

When the player enters a "look around" observation command while in a location, the quantum pipeline unexpectedly moves the player to a different location instead of describing the current scene. The narrative describes leaving the current location rather than observing it.

## Current Behavior

**Player Input:** "look around the village square"
**Player Location:** `village_square`

**Narrative Output:**
> You step away from the bustling Village Square, where the morning sun glints off dew-kissed cobblestones... The The Rusty Tankard looms ahead...

**Result:** Player was moved from `village_square` back to `village_tavern`

## Expected Behavior

A "look around" command should:
1. Keep the player in their current location
2. Describe the scene at that location
3. NOT generate any movement or location change

## Root Cause

In `_intent_to_match_result()` (pipeline.py:727-770), when the intent classifier correctly returns `action_type=OBSERVE` with `target_display="village square"`, the function skips the OBSERVE prediction because its `display_name="Look around"` doesn't contain "village square".

The flow:
1. Intent classifier correctly identifies: `action_type=OBSERVE`, `target_display="village square"`
2. Function iterates predictions looking for OBSERVE match
3. OBSERVE prediction has `target_key=None` and `display_name="Look around"`
4. Target matching logic at lines 751-761 checks: `"village square" in "look around"` → **False**
5. OBSERVE prediction is skipped, function returns `None`
6. Falls back to fuzzy matcher which may incorrectly match MOVE

## Solution

Added `UNTARGETED_ACTION_TYPES` set containing `{ActionType.OBSERVE, ActionType.WAIT}`. These are "environmental" actions that don't target specific entities. When an intent matches one of these action types, the function now returns immediately without requiring target matching.

## Implementation Details

**File:** `src/world_server/quantum/pipeline.py`

1. Added `UNTARGETED_ACTION_TYPES` constant (line 93):
```python
UNTARGETED_ACTION_TYPES = {ActionType.OBSERVE, ActionType.WAIT}
```

2. Modified `_intent_to_match_result()` to skip target matching for environmental actions:
```python
# Skip target matching for environmental actions (OBSERVE, WAIT).
if prediction.action_type in UNTARGETED_ACTION_TYPES:
    return MatchResult(
        prediction=prediction,
        confidence=intent_result.confidence,
        match_reason="intent_classifier",
    )
```

## Files Modified

- [x] `src/world_server/quantum/pipeline.py` - Added UNTARGETED_ACTION_TYPES, modified _intent_to_match_result()
- [x] `tests/test_world_server/test_quantum/test_pipeline.py` - Added TestIntentToMatchResult class with 7 test cases

## Test Cases

- [x] `test_observe_with_location_target_matches` - "look around the village square" matches OBSERVE
- [x] `test_observe_without_target_matches` - "look around" matches OBSERVE
- [x] `test_wait_with_duration_target_matches` - "wait for a few hours" matches WAIT
- [x] `test_interact_npc_requires_target_match` - "talk to the guard" still requires NPC matching
- [x] `test_interact_npc_no_match_wrong_target` - "talk to blacksmith" returns None if not in predictions
- [x] `test_move_requires_target_match` - "go to the tavern" still requires target matching
- [x] `test_no_action_type_returns_none` - No action_type returns None

## References

- Turn data in `turns` table for session 342
- Quantum pipeline docs: `docs/quantum-branching/README.md`
