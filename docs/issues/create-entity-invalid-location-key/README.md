# CREATE_ENTITY Delta Fails with Invalid 'location_key' Argument

**Status:** Done
**Priority:** High
**Detected:** 2025-12-30
**Resolved:** 2025-12-30
**Related Sessions:** Session 311

## Problem Statement

When the quantum pipeline generates a CREATE_ENTITY delta (e.g., to create a room key item), the delta includes a `location_key` field that is not a valid keyword argument for the Entity model. This causes the delta application to fail.

## Root Cause

Two issues:

1. **System prompt** (`branch_generator.py:228`) suggested `location_key` as a valid field:
   ```
   - create_entity: {entity_key, display_name, entity_type, location_key?, description?}
   ```

2. **Collapse code** (`collapse.py:512`) passed this invalid field to `create_entity()`:
   ```python
   entity_manager.create_entity(
       ...
       location_key=changes.get("location_key"),  # NOT A VALID FIELD
       ...
   )
   ```

The Entity model doesn't have a `location_key` field - items use `holder_id`, `owner_id`, or `storage_location_id` instead.

## Solution Applied

1. **Updated system prompt** to remove `location_key` from CREATE_ENTITY:
   ```
   - create_entity: {entity_key, display_name, entity_type, description?}
   ```

2. **Removed invalid parameter** from collapse.py:
   ```python
   entity_manager.create_entity(
       entity_key=changes.get("entity_key", delta.target_key),
       display_name=changes.get("display_name", delta.target_key),
       entity_type=changes.get("entity_type"),
       # Note: location_key is not a valid Entity field - removed
       description=changes.get("description"),
   )
   ```

## Files Modified

- [x] `src/world_server/quantum/branch_generator.py` - Removed `location_key` from system prompt
- [x] `src/world_server/quantum/collapse.py` - Removed invalid `location_key` parameter

## Test Results

All quantum pipeline tests pass (275 passed, 2 pre-existing failures unrelated to this fix).

## Related Issues

- `docs/issues/delta-update-entity-player-key/` - Fixed in same commit
- `docs/issues/record-fact-invalid-category-enum/` - Fixed in same commit
