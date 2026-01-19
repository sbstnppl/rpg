# OOC Time Hallucination

**Status:** Done
**Priority:** Medium
**Detected:** 2025-12-27
**Resolved:** 2025-12-27
**Related Sessions:** Session 293, Turn 11

## Problem Statement

When the player asks an OOC (out-of-character) question about game time, the LLM fabricates a completely wrong answer instead of checking actual game state.

## Current Behavior

Player input: "[OOC] How much time has passed today?"

LLM response:
> "Time tracked as 'minutes' since your last action. Total time passed today: 1 hour and 45 minutes."

**Actual game time**: 09:00 → 09:10 = **10 minutes** (not 1 hour 45 minutes)

The LLM invented a plausible-sounding but completely wrong time.

## Expected Behavior

For OOC time queries, the LLM should:
1. Call a tool to get actual time state (or use context)
2. Calculate real elapsed time: `current_time - start_time`
3. Report accurate information

Expected response:
> "[OOC] It's currently 09:10 on Day 1. About 10 minutes have passed since you arrived at the tavern."

## Root Cause

1. **No time query tool**: No tool existed to get elapsed time
2. **Context not used**: LLM ignored time in system prompt
3. **Hallucination tendency**: qwen3 generates plausible-sounding answers

## Solution Implemented

Added a `get_time` tool that returns accurate time information.

### Files Modified

- [x] `src/managers/time_manager.py` - Added `calculate_elapsed_minutes()` method
- [x] `src/gm/tools.py` - Added `get_time` tool definition and implementation
- [x] `tests/test_gm/test_tools.py` - Added 8 tests for time tool
- [x] `tests/test_managers/test_time_manager.py` - Added 7 tests for elapsed calculation

### Tool Definition

```python
{
    "name": "get_time",
    "description": "Get current game time and elapsed time. Use for OOC time queries like 'what time is it' or 'how long have I been here'.",
    "input_schema": {"type": "object", "properties": {}}
}
```

### Tool Returns

```json
{
    "current_day": 1,
    "current_time": "09:10",
    "day_of_week": "monday",
    "period": "morning",
    "elapsed_today": "1 hour and 10 minutes",
    "elapsed_minutes": 70
}
```

### Human-Readable Elapsed Formatting

- `0 minutes` → "just started"
- `1 minute` → "1 minute" (singular)
- `15 minutes` → "15 minutes"
- `75 minutes` → "1 hour and 15 minutes"
- `120 minutes` → "2 hours"
- `135 minutes` → "2 hours and 15 minutes"

## Test Coverage

15 new tests added:

**TimeManager tests** (`test_time_manager.py`):
- Elapsed calculation with various times
- Default start time (08:00)
- Negative elapsed (before start)

**GMTools tests** (`test_tools.py`):
- Tool is in definitions
- Returns accurate time
- Elapsed formatting (hours, minutes, singular)
- Day of week included
- Period of day included
- "Just started" case

## Related Issues

- `unrealistic-time-passage` - Both relate to time handling
- Now share time calculation logic via TimeManager
