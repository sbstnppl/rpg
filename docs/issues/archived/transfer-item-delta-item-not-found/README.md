# TRANSFER_ITEM Delta Fails - Item Not Found

**Status:** Done
**Priority:** Medium
**Detected:** 2026-01-02
**Resolved:** 2026-01-03
**Related Sessions:** Session 334, Turn 6

## Problem Statement

When picking a lock on a box, the quantum pipeline generated a TRANSFER_ITEM delta for `innkeeper_box_key`, but this item doesn't exist in the database. The delta application failed with "item not found" error, though the skill check and narrative still succeeded.

## Current Behavior

Player input: `try to pick the lock on the small wooden box`

Error output:
```
TRANSFER_ITEM failed: item 'innkeeper_box_key' not found
Failed to apply delta DeltaType.TRANSFER_ITEM to innkeeper_box_key: Item not found: innkeeper_box_key
```

The skill check succeeded (DC 10: Auto-success) and narrative was displayed, but the item transfer delta failed.

The narrative mentions: "Inside, a small key and a folded note rest on a bed of dried herbs" - but this key was never created in the database.

## Expected Behavior

The branch generator should auto-create items before transferring them when the LLM generates TRANSFER_ITEM deltas for non-existent items.

## Root Cause

The LLM branch generator creates TRANSFER_ITEM deltas for items that don't exist in the manifest. This is a common LLM reliability issue - the model assumes items exist without creating them first.

## Solution Implemented

Created a **DeltaPostProcessor** class that repairs common LLM errors in state deltas:

### Design Principle
**"Fix what we can, regenerate what we can't."**

### Fixable Issues (Auto-Repaired)
| Issue | Fix |
|-------|-----|
| Missing CREATE_ENTITY before TRANSFER_ITEM | Inject CREATE_ENTITY with inferred entity type |
| Out-of-range need/relationship values | Clamp to 0-100 |
| Invalid entity_type in CREATE_ENTITY | Map to valid type or default "item" |
| Invalid fact category | Default to "personal" |
| Wrong delta ordering | CREATE before UPDATE/TRANSFER |

### Unfixable Issues (Trigger Regeneration)
| Issue | Why |
|-------|-----|
| CREATE + DELETE same entity | Conflicting intent |
| Duplicate CREATE_ENTITY | Conflicting intent |
| Negative time advancement | Illogical |
| Unknown entity keys for UPDATE | Can't verify LLM intent |

## Files Modified

- [x] `src/world_server/quantum/delta_postprocessor.py` - **NEW** Post-processor class
- [x] `src/world_server/quantum/branch_generator.py` - Integrated post-processor
- [x] `src/world_server/quantum/pipeline.py` - Added RegenerationNeeded handling
- [x] `src/world_server/quantum/schemas.py` - Added regenerations_triggered metric
- [x] `src/world_server/quantum/__init__.py` - Exported new classes
- [x] `tests/test_world_server/test_quantum/test_delta_postprocessor.py` - **NEW** 58 unit tests
- [x] `tests/test_world_server/test_quantum/test_branch_generator.py` - Updated for new signature

## Test Results

- 58 unit tests for DeltaPostProcessor: All passed
- 520 quantum pipeline tests: All passed

## References

- Session 334, Turn 6
- docs/quantum-branching/README.md
- Plan: `.claude/plans/zippy-sleeping-blum.md`
