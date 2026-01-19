# TimeState Attribute Error: day_number vs current_day

**Status:** Done
**Priority:** High
**Detected:** 2025-12-30
**Related Sessions:** Play-test session 305

## Problem Statement

The quantum pipeline code in `src/world_server/quantum/pipeline.py` references `time_state.day_number`, but the `TimeState` model in `src/database/models/world.py` uses `current_day` as the column name. This mismatch causes an `AttributeError` when processing turns.

## Current Behavior

When executing a turn with the quantum pipeline:

```
Turn processing failed: 'TimeState' object has no attribute 'day_number'
Error: Error: 'TurnResult' object has no attribute 'skill_check_result'
```

The error occurs at line 503 in pipeline.py:
```python
game_day = time_state.day_number if time_state else 1
```

## Expected Behavior

The pipeline should correctly reference `time_state.current_day` to get the in-game day number.

## Investigation Notes

**TimeState model definition** (`src/database/models/world.py:209`):
```python
current_day: Mapped[int] = mapped_column(
    default=1,
    nullable=False,
    comment="In-game day number",
)
```

**Pipeline code** (`src/world_server/quantum/pipeline.py:503`):
```python
game_day = time_state.day_number if time_state else 1  # WRONG
```

## Root Cause

Simple attribute name mismatch. The `TimeState` model uses `current_day` but the pipeline code uses `day_number`.

## Proposed Solution

Change line 503 in `pipeline.py` from:
```python
game_day = time_state.day_number if time_state else 1
```
to:
```python
game_day = time_state.current_day if time_state else 1
```

## Files to Modify

- [x] `src/world_server/quantum/pipeline.py` - Line 503 (`day_number` -> `current_day`)
- [x] `src/world_server/quantum/pipeline.py` - Added `skill_check_result` property to `TurnResult`
- [x] `src/world_server/quantum/pipeline.py` - Added `errors` property to `TurnResult` (CLI compatibility)

## Test Cases

- [x] Test case 1: Execute a turn with quantum pipeline - should not error on TimeState attribute (verified: got past attribute error)
- [x] Test case 2: Verify game_day is correctly extracted from TimeState (code review confirms fix)

**Note:** Full gameplay testing requires Ollama to be running. The code fixes were verified via test suite and partial execution (error passed first issue and hit LLM timeout).

## Related Issues

- ~~Secondary error about `TurnResult.skill_check_result` may be a separate issue~~ - FIXED: Added `skill_check_result` property to TurnResult dataclass

## References

- `src/database/models/world.py:195-224` - TimeState model definition
- `src/world_server/quantum/pipeline.py:495-516` - Time state usage in pipeline
