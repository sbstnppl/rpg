# Narrative Time Inconsistency

**Status:** Done
**Priority:** Medium
**Detected:** 2026-01-03
**Fixed:** 2026-01-03
**Related Sessions:** 340, 341

## Problem Statement

The narrator generates descriptions that don't match the current in-game time of day. For example, describing "morning light" when the game time is 3:05 PM (afternoon). This breaks immersion and creates logical inconsistencies in the narrative.

## Current Behavior

Game time: 15:05 (3:05 PM)

Narrator output:
> You scan the dim interior of The Rusty Tankard, where **morning light** slants through dusty windows...

The narrative says "morning light" when it should be afternoon light.

## Root Cause

The `NarrationContext` class in `src/world_server/quantum/narrator.py` didn't include time fields (`game_time`, `game_period`, `game_day`), so the narrator engine had no temporal awareness when generating prose.

While the branch generator already had time context in `BranchContext`, the split architecture's narrator phase didn't receive this information.

## Solution Implemented

1. **Added time fields to NarrationContext** (`narrator.py`):
   - `game_time: str` - e.g., "14:30"
   - `game_period: str` - e.g., "afternoon"
   - `game_day: int` - e.g., 1

2. **Updated NARRATOR_SYSTEM_PROMPT** with explicit time-of-day guidance:
   - Clear instructions for each time period (morning, afternoon, evening, night)
   - Explicit anti-patterns ("Do NOT describe morning light when it's afternoon")

3. **Updated `_build_prompt`** to include time context:
   - Added `## Time:` section showing current time and period
   - Added instruction: "Match your descriptions to this time period!"

4. **Updated pipeline** (`pipeline.py`):
   - Added `_get_time_state()` helper to fetch TimeState from DB
   - Added `_calculate_game_period()` helper to convert time to period string
   - Updated both PHASE 4 locations to pass time to NarrationContext

5. **Added tests** for all new functionality:
   - `TestNarrationContextTimeFields` - 3 tests
   - `TestNarratorEngineTimeContext` - 3 tests
   - `TestCalculateGamePeriod` - 8 tests

## Files Modified

- [x] `src/world_server/quantum/narrator.py` - Added time fields, prompt updates
- [x] `src/world_server/quantum/pipeline.py` - Added time helpers, pass time to narrator
- [x] `tests/test_world_server/test_quantum/test_narrator.py` - Added time tests
- [x] `tests/test_world_server/test_quantum/test_pipeline.py` - Added period calculation tests

## Test Results

All 14 new tests pass:
- 6 narrator time tests
- 8 pipeline period calculation tests

## Known Limitation

The local LLM (ollama:magmell) may still occasionally generate time-inconsistent narratives despite having explicit time context. This is a limitation of smaller language models - they don't always follow instructions as reliably as larger models. The implementation is correct; the LLM behavior is the limiting factor.

Potential mitigations for future:
- Post-processing validation to detect time-inconsistent phrases
- Retry with stronger prompt if time words don't match period
- Use larger/better-tuned model for narration

## Verification

Prompt now includes:
```
## Time: Day 1, 15:30 (afternoon)
Match your descriptions to this time period!
```

System prompt includes:
```
## Time of Day

CRITICAL: Match your narrative to the time period.

- **afternoon** (12pm-6pm): midday sun, warm light, lunch/afternoon activity, busy

Do NOT describe morning light or early patrons when it's afternoon/evening/night.
```
