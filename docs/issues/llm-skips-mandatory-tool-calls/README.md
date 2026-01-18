# LLM Skips Mandatory Tool Calls for Need-Satisfying Actions

**Status:** Awaiting Verification
**Priority:** High
**Detected:** 2025-12-30
**Fixed:** 2026-01-18
**Verification:** 0/3
**Last Verified:** -
**Related Sessions:** Session 304

## Problem Statement

When a player performs an action that should satisfy a character need (like having a conversation for social_connection), the LLM skips generating the required `update_need` delta. This causes the game state to become inconsistent - the narrative describes the action happening, but the need stat doesn't change.

## Root Cause

The issue was in the quantum pipeline's branch generator prompt (`src/world_server/quantum/branch_generator.py`):

1. **Minimal `update_need` guidance**: Only said `update_need: {entity_key, need_name, amount} - for hunger, thirst, stamina changes`
2. **No trigger criteria**: Unlike item transfers (which have an INVARIANT section), there was no guidance on WHEN to generate `update_need` deltas
3. **No activity-to-need mapping**: The old GM tools had explicit mappings like "Eating/food/meal/bread → need='hunger'" but the quantum pipeline lacked this
4. **Missing social_connection**: The valid needs list didn't include `social_connection`

**Note**: The issue was originally filed against the old GM tools system (`satisfy_need` function calls) but the game now uses the quantum pipeline which uses semantic `update_need` deltas instead.

## Solution

Added an **INVARIANT FOR NEED-SATISFYING ACTIONS** section to `branch_generator.py` (lines 312-332) with:

1. **Activity-to-need mapping table** with example amounts
2. **Explicit examples** for drinking ale and having conversations
3. **Warning about state desync** similar to the item transfer invariant

Also added `social_connection` to valid needs in:
- `validation.py:694`
- `delta_postprocessor.py:164`

### Files Modified

| File | Change |
|------|--------|
| `src/world_server/quantum/branch_generator.py` | Added INVARIANT section with activity-to-need mapping |
| `src/world_server/quantum/validation.py` | Added `social_connection` to VALID_NEEDS |
| `src/world_server/quantum/delta_postprocessor.py` | Added `social_connection` to VALID_NEEDS |

## Test Results

- 68 validation tests passed
- 21 branch generator tests passed
- All existing needs functionality tests pass

## Verification Checklist

After play-testing, verify:
- [ ] Eating/drinking generates `update_need` delta for hunger/thirst
- [ ] Conversation with NPC generates `update_need` delta for social_connection
- [ ] Need stats change correctly in player status
- [ ] No regressions in other narrative quality

## Related Issues

- `docs/issues/grounding-retry-repeats-previous-turn/` - Related retry handling issue

## References

- `logs/llm/session_304/turn_007_20251230_065443_gm.md` - Original failed turn log
- `src/gm/tools.py:792-801` - Old satisfy_need tool with activity mappings (reference)
