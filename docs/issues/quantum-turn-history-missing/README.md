# Quantum Pipeline Not Recording Turn History

**Status:** Done
**Priority:** High
**Detected:** 2025-12-30
**Related Sessions:** Session 309

## Problem Statement

The quantum pipeline is processing turns successfully (narrative is generated, facts are recorded, time advances) but the `turns` table is not being updated with turn history. This breaks conversation context and player input history.

## Current Behavior

After multiple turns in session 309:
- `turns` table has 0 rows for session 309
- `facts` table has 3 entries (so state changes work)
- `time_states` table is updated
- Narrative is displayed but action matching seems stuck (repeated "rooms" response)

## Expected Behavior

1. Each turn should create a new row in the `turns` table
2. `player_input` and `gm_response` should be recorded
3. Turn number should increment

## Investigation Notes

- Facts are being recorded, so some state persistence works
- The action matcher may be getting stuck due to missing turn context
- Same "rooms" response repeated regardless of input

## Root Cause

The `game turn` command in `src/cli/commands/game.py` (lines 1750-1773) calls `quantum_pipeline.process_turn()` but never saves the turn to the `turns` table. It only:
1. Increments `game_session.total_turns`
2. Calls `process_turn()`
3. Displays the result
4. Commits the transaction

The turn history is not being persisted to the database. This is missing from the CLI command.

## Proposed Solution

Add turn recording to the `game turn` command after processing:

```python
from src.managers.turn_manager import TurnManager

turn_manager = TurnManager(db, game_session)
turn_manager.create_turn(
    turn_number=game_session.total_turns,
    player_input=player_input,
    gm_response=turn_result.narrative,
    time_passed=turn_result.time_passed_minutes,
)
```

## Implementation

Added `_save_turn_immediately()` call to the `turn` command at line 1773-1783 in `src/cli/commands/game.py`. This reuses the existing helper function that `play` uses.

## Files Modified

- [x] `src/cli/commands/game.py` - Added turn recording to `turn` command (line 1773-1783)

## Verification

Tested with Session 310:
- Turn 1: "look around the tavern" → Saved to turns table ✓
- Turn 2: "talk to Old Tom" → Saved to turns table ✓

```sql
SELECT turn_number, LEFT(player_input, 30), LEFT(gm_response, 50) FROM turns WHERE session_id = 310;
 turn_number |         input          |                      response
-------------+------------------------+----------------------------------------------------
           1 | look around the tavern | You scan the dim interior of the Rusty Tankard, no
           2 | talk to Old Tom        | You approach Old Tom and ask about rooms. He sets
```
