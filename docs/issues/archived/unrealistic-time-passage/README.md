# Unrealistic Time Passage

**Status:** Done
**Priority:** Medium
**Detected:** 2025-12-27
**Resolved:** 2025-12-27
**Related Sessions:** Session 293, Multiple Turns

## Problem Statement

The GM pipeline assigns unrealistically short time durations to activities. Actions that should take 10-30 minutes are completing in 1 minute, breaking immersion and making the game world feel rushed.

## Current Behavior

| Turn | Action | Time Passed | Expected |
|------|--------|-------------|----------|
| 8 | Eat a hearty meal | 1 min | 15-30 min |
| 10 | Rest by fire | 1 min | 10-15 min |
| 15 | Leave tavern, explore village | 1 min | 5-10 min |

All actions default to 1 minute regardless of complexity.

## Expected Behavior

Time should reflect realistic activity durations:
- Eating a full meal: 15-30 minutes
- Quick snack: 5-10 minutes
- Resting: 10-15 minutes
- Short rest: 5 minutes
- Walking within location: 1-2 minutes
- Traveling to new area: 5-15 minutes
- Conversation: 2-10 minutes

## Investigation Notes

Time estimation happens in `GMNode._estimate_time_passed()` at `src/gm/gm_node.py:1006-1074`.

Current logic:
1. Checks tool calls made during turn
2. Returns max time from tools called
3. Default: 1 minute

The issue: `satisfy_need` tool with `need="hunger"` returns 15 minutes, BUT:
- In Turn 8, hunger was already at 100, so tool likely returned "already satisfied"
- Code returns default 1 minute if tool didn't trigger actual satisfaction

Also, the LLM's `time_passed_minutes` in GMResponse is being set by `_estimate_time_passed()`, which only looks at tool results, not the narrative description.

## Root Cause

1. **Tool-centric time estimation**: Time only calculated from successful tool results
2. **No narrative-based estimation**: Doesn't consider what the narrative describes
3. **Default too low**: 1 minute default for anything without tool calls
4. **satisfy_need edge case**: When need is already full, no time credit given

## Proposed Solution

### Option A: Activity-Based Time Estimation
Add activity classification to time estimation:

```python
def _estimate_time_passed(self, player_input: str, state_changes: list) -> int:
    input_lower = player_input.lower()

    # Activity patterns with time estimates
    if any(word in input_lower for word in ['eat', 'meal', 'food', 'dine']):
        return 15 if 'quick' not in input_lower else 5
    if any(word in input_lower for word in ['rest', 'sit', 'relax']):
        return 10
    if any(word in input_lower for word in ['drink', 'sip']):
        return 3
    if any(word in input_lower for word in ['leave', 'go to', 'travel', 'explore']):
        return 5
    if any(word in input_lower for word in ['look', 'examine', 'search']):
        return 2

    # Existing tool-based logic as fallback
    return self._estimate_from_tools(state_changes)
```

### Option B: LLM Determines Time
Add `time_passed` as required output in GMResponse schema, let LLM estimate.

### Option C: Hybrid
Combine activity patterns with tool results, take maximum.

## Implementation Details

Recommend Option C (Hybrid):

1. Parse player input for activity keywords
2. Assign base time from activity type
3. Check tool results for additional time
4. Return maximum of all estimates
5. Apply multipliers for "quickly", "briefly", etc.

## Files Modified

- [x] `src/gm/gm_node.py` - Implemented hybrid time estimation with `ACTIVITY_PATTERNS`, `TIME_MODIFIERS`, `_estimate_activity_time()`, `_estimate_tool_time()`
- [x] `tests/test_gm/test_time_estimation.py` - Added 47 tests for time estimation

## Test Cases

- [x] Test: "eat a meal" → 25 minutes
- [x] Test: "eat a hearty meal" → 32 minutes (25 * 1.3)
- [x] Test: "rest by the fire" → 15 minutes
- [x] Test: "take a quick drink" → 3 minutes (5 * 0.7)
- [x] Test: "explore the village" → 10 minutes
- [x] Test: "look around" → 3 minutes

## Related Issues

- OOC time hallucination (Turn 11 claimed wrong total time)
- Could add time tracking tool for OOC queries

## References

- `src/gm/gm_node.py:1006-1074` - Current time estimation
- `.claude/docs/realism-principles.md` - Temporal realism guidelines
- `docs/issues/` - Related issues
