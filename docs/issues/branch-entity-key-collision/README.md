# Branch Entity Key Collisions During Generation

**Status:** Awaiting Verification
**Priority:** Medium
**Verification:** 0/3
**Last Verified:** -
**Detected:** 2026-01-19
**Fixed:** 2026-01-21
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

## Root Cause

The collision occurs because of a **scope mismatch**:

1. **Manifest is turn-local**: The `GroundingManifest` was built fresh each turn and only contained entities currently at the location (via DB query) + entities created within the current turn (via `additional_valid_keys`).

2. **No cross-turn tracking**: `additional_valid_keys` was meant to track entities created mid-turn during post-processing, NOT entities from previous turns. It wasn't persisted.

3. **LLM has no global visibility**: The branch generator only saw entities in the current scene manifest. It had no knowledge of keys created in previous turns.

4. **Database query gap**: Items created in turn 1 may not appear in `items_at_location` queries in turn 2 if:
   - The item's `location_id` wasn't properly set
   - The item was transferred to player inventory (no longer at location)
   - The item "exists" but isn't tied to the location

## Implemented Solution

**Two-part fix:**

### Part 1: Session-Level Entity Key Registry

Added a method `_get_all_session_keys()` in `GMContextBuilder` that queries ALL entity and item keys from the session:

```python
def _get_all_session_keys(self) -> set[str]:
    """Get all entity and item keys from the current session."""
    keys: set[str] = set()

    entity_keys = self.db.query(Entity.entity_key).filter(
        Entity.session_id == self.session_id
    ).all()
    keys.update(row[0] for row in entity_keys)

    item_keys = self.db.query(Item.item_key).filter(
        Item.session_id == self.session_id
    ).all()
    keys.update(row[0] for row in item_keys)

    return keys
```

This is now passed to the manifest via `additional_valid_keys` so the post-processor's `_item_exists()` check can find ALL session entities.

### Part 2: LLM Prompt Guidance

Added explicit guidance to the branch generator system prompt telling the LLM not to create entities that already exist:

```
IMPORTANT: Entity Key Uniqueness
- Do NOT generate CREATE_ENTITY for keys that already appear in AVAILABLE ENTITIES
- If you need to reference an existing entity, use its key directly in deltas
- Only create NEW entities with unique, descriptive keys that don't match existing ones
- When creating new items, use descriptive keys like "ale_mug_fresh" to avoid collisions
```

### Part 3: Session ID Tracking

Added `session_id` field to `GroundingManifest` for better debugging and tracking which session a manifest belongs to.

## Files Modified

- [x] `src/gm/grounding.py` - Added `session_id` field to GroundingManifest
- [x] `src/gm/context_builder.py` - Added `_get_all_session_keys()` method and populate `additional_valid_keys`
- [x] `src/world_server/quantum/branch_generator.py` - Added key uniqueness guidance to system prompt
- [x] `tests/test_gm/test_context_builder.py` - Added tests for session key inclusion

## Test Cases

- [x] Test `_get_all_session_keys()` returns entity keys
- [x] Test `_get_all_session_keys()` returns item keys
- [x] Test `_get_all_session_keys()` excludes other sessions
- [x] Test `build_grounding_manifest()` includes session keys in `additional_valid_keys`
- [x] Test `contains_key()` finds session-level entities
- [x] Test `session_id` is set on manifest

## Verification Steps

1. [ ] Play-test multiple turns without entity collision warnings
2. [ ] Verify items created in turn 1 aren't recreated in turn 2+
3. [ ] Verify new unique item creation still works normally
