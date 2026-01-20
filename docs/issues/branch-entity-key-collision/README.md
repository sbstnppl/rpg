# Branch Entity Key Collisions During Generation

**Status:** Investigating
**Priority:** Medium
**Verification:** 0/3
**Last Verified:** -
**Detected:** 2026-01-19
**Related Sessions:** 348

## Problem Statement

When the branch generator creates branches with `CREATE_ENTITY` deltas, it frequently generates entity keys that already exist in the world or that were already generated in previous branches/turns. This results in validation warnings like "Entity key 'porridge_bowl' already exists" for every branch.

## Current Behavior

Every turn shows multiple validation warnings:
```
Branch validation: variant:success:delta - Delta[0]: Entity key 'porridge_bowl' already exists
Branch validation: variant:failure:delta - Delta[0]: Entity key 'porridge_bowl' already exists
Branch validation: variant:critical_success:delta - Delta[0]: Entity key 'honeyed_porridge_bowl' already exists
```

Observed patterns:
- `porridge_bowl`, `porridge_bowl_2` 
- `brass_key`
- `innkeeper_tom_coin_purse`
- `parchment_scroll`
- `silver_coin_01`, `silver_coin_02`, `silver_coin_03`

These collisions occur even on turns unrelated to those items.

## Expected Behavior

1. Branch generator should check existing entities before generating CREATE_ENTITY deltas
2. If an entity already exists, it should reference it instead of creating a new one
3. Entity keys should be unique and not reused across turns

## Investigation Notes

- The branch generator appears to not have visibility into what entities were already created
- Multiple branches generate the same "reward" items regardless of context
- The system continues to work but with excessive warnings

## Root Cause

<After investigation>

## Proposed Solution

1. Pass existing entity keys to the branch generator in the context
2. Add deduplication logic in delta post-processor
3. Consider caching created entity keys per session

## Files to Modify

- [ ] `src/world_server/quantum/branch_generator.py`
- [ ] `src/world_server/quantum/delta_post_processor.py`

## Test Cases

- [ ] Test case 1: Multiple turns don't duplicate entity keys
- [ ] Test case 2: CREATE_ENTITY references existing entities when appropriate
