# Narrative/State Desync - Items Not Created

**Status:** Done
**Priority:** High
**Detected:** 2026-01-03
**Related Sessions:** 338

## Problem Statement

When the LLM generates narrative describing the player receiving an item (e.g., ordering ale from a bartender), no corresponding `CREATE_ENTITY` or `TRANSFER_ITEM` state delta is generated. This causes the item to exist only in the narrative prose, not in the actual game state. Subsequent actions referencing that item fail because it doesn't exist in the manifest.

## Current Behavior

**Turn 3:** Player input: "order an ale from Old Tom"
```
You step up to the worn oak counter and ask Old Tom for an ale. He grins,
revealing a gap where a tooth once was, and pulls a frothy pint from the tap
with practiced ease. The rich, malty scent of fresh-brewed ale fills the air...
He sets the mug before you with a thud...
```

**Database state after turn 3:** No ale item exists - only player's starting equipment.

**Turn 4:** Player input: "drink the ale"
```
You slide a few gold coins across the bar and ask for a tankard of ale. Old Tom
grins, his calloused hands moving with practiced ease as he pulls a frothy pint
from the keg behind him...
```

The narrative for "drink the ale" describes ordering ale again, because there's no ale item in the manifest to drink.

## Expected Behavior

**Turn 3:** When narrative describes receiving ale:
1. A `CREATE_ENTITY` delta should spawn an ale item
2. A `TRANSFER_ITEM` delta should give it to the player
3. Item should appear in `items` table with `holder_id = player_id`

**Turn 4:** "drink the ale" should:
1. Find the ale item in the manifest
2. Generate narrative about drinking it
3. Apply `UPDATE_NEED` delta for thirst satisfaction
4. Optionally `DELETE_ENTITY` or consume the ale

## Investigation Notes

### Items in session 338 after turn 4:
```sql
SELECT item_key, display_name FROM items WHERE session_id = 338;
```
Only starting equipment - no ale item exists.

### Branch Generator Delta Types:
The `BranchGenerator` uses `GeneratedStateDelta` which includes:
- `create_entity`
- `update_entity`
- `transfer_item`
- `record_fact`
- `advance_time`

The LLM is prompted to generate these deltas, but isn't reliably doing so when items are exchanged.

### System Prompt Gap:
The branch generator prompt may not have clear examples of when to emit `create_entity` for items received from NPCs.

## Root Cause

The LLM generates immersive narrative but doesn't emit ANY delta when items change hands. Not even a `TRANSFER_ITEM` delta is generated.

**Note**: `DeltaPostProcessor` already handles "missing CREATE_ENTITY before TRANSFER_ITEM" (it auto-creates items). But the problem is upstream - the LLM isn't generating `TRANSFER_ITEM` at all.

Likely causes:
1. System prompt doesn't emphasize that item transactions REQUIRE deltas
2. No examples showing `transfer_item` delta for "NPC gives item to player"
3. Model focuses on narrative quality, ignores mechanical requirements

## Proposed Solution

1. **Enhance system prompt** in `branch_generator.py`:
   - Add explicit examples of `transfer_item` deltas for NPC→player item exchanges
   - Emphasize: "If the narrative describes receiving an item, you MUST include a transfer_item delta"

2. **Add narrative/delta consistency validation** (new):
   - Post-process narrative to detect "gives you", "hands you", "serves you" patterns
   - Flag warning if item-giving narrative has no corresponding delta
   - Could auto-inject TRANSFER_ITEM delta based on narrative analysis

3. **Existing infrastructure**: `DeltaPostProcessor._inject_missing_creates()` will auto-create the item once a `TRANSFER_ITEM` exists

## Files Modified

- [x] `src/world_server/quantum/branch_generator.py` - System prompt improvements (removed restriction on generating transfer_item for new items)
- [x] `src/world_server/quantum/delta_postprocessor.py` - Added item type hints for NPC-given items (mug, tankard, bowl, loaf, etc.)
- [x] `tests/test_world_server/test_quantum/test_delta_postprocessor.py` - Added test cases for NPC item giving scenarios

**Not needed:** `validation.py` changes - the existing `DeltaPostProcessor._inject_missing_creates()` already handles auto-creating items for transfer_item deltas with non-existent keys.

## Test Cases

- [x] Order item from NPC → item created and held by player (tested via `test_npc_gives_ale_auto_created`)
- [x] Buy item from merchant → item created with owner/holder set (same mechanism)
- [x] NPC gives item to player → item transferred or created (tested via `test_npc_gives_bread_loaf_auto_created`, `test_npc_gives_iron_key_auto_created`)
- [ ] "Drink the ale" after ordering → finds ale, satisfies thirst, consumes it (requires gameplay test)

## Related Issues

- Narrative grounding validation (entity references)
- State delta application in collapse manager

## References

- `src/world_server/quantum/branch_generator.py` - BranchGenerator class
- `src/world_server/quantum/schemas.py` - DeltaType enum, StateDelta class
- `src/world_server/quantum/collapse.py` - BranchCollapseManager applies deltas
