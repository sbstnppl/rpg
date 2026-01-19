# TODO: Item State Desync - Ref-Based Mode

## Investigation ✓

- [x] Identify root cause (RefManifest lacks future items)
- [x] Trace code path (`_resolve_ref` silent failure)
- [x] Document potential solutions
- [x] Decide on solution: Implicit item creation via descriptive keys

## Implementation ✓

### Prompt Updates ✓
- [x] Update branch_generator.py prompt to instruct LLM to use descriptive item keys
- [x] Add prompt guidance: use keys like "ale_mug", "bread_loaf" for new items

### NPC Auto-Creation ✓
- [x] Add `_inject_missing_npc_creates()` in delta_postprocessor.py
- [x] Parse `[key:display]` patterns from narrative
- [x] Auto-create NPCs matching NPC_KEY_HINTS
- [x] Add tests for NPC auto-creation

### Item Auto-Creation ✓
- [x] Enhance give_item handling when item doesn't have a ref
- [x] Allow LLM to use descriptive item_key instead of ref
- [x] Auto-create item in postprocessor before TRANSFER_ITEM (via existing _inject_missing_creates)
- [x] Add tests for item creation during give_item

## Verification

- [x] Run existing tests (pytest test_delta_postprocessor.py) - 92 passed
- [x] Run all quantum tests - 588 passed
- [ ] Manual play-test: order ale from barkeep
- [ ] Verify item appears in inventory
- [ ] Verify narrative matches game state

## Notes

Priority: HIGH - This blocks core gameplay (item acquisition from NPCs)

The solution uses implicit item creation: when LLM outputs `give_item` with a descriptive
key like "ale_mug" instead of a ref, the translator accepts it (instead of erroring),
and the postprocessor auto-creates the item before the TRANSFER_ITEM delta is applied.
