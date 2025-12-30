# CREATE_ENTITY Delta Fails with 'description' Invalid Keyword Argument

**Status:** Done
**Priority:** High
**Detected:** 2025-12-30
**Resolved:** 2025-12-30
**Related Sessions:** Session 313

## Problem Statement

When the quantum pipeline generates a CREATE_ENTITY delta with a `description` field, the entity creation fails because `Entity` model doesn't accept `description` as a keyword argument. The system prompt tells the LLM to include `description?` (optional) but the collapse code passes it through to a method that doesn't support it.

## Current Behavior

Error message during turn 7 of play-test session 313:
```
Failed to apply delta DeltaType.CREATE_ENTITY to found_silver_thimble: 'description' is an invalid keyword argument for Entity
```

The narrative was good (describing a silver thimble) but the delta application failed.

## Expected Behavior

The CREATE_ENTITY delta should successfully create entities with descriptions stored appropriately.

## Root Cause

The `Entity` model does not have a `description` column. It has:
- `background` - for character backstory
- `personality_notes` - for personality traits

The collapse code was passing `description=changes.get("description")` directly to the Entity constructor, which doesn't accept it.

## Solution Applied

Map `description` to `background` field in collapse.py:

```python
entity_manager.create_entity(
    entity_key=changes.get("entity_key", delta.target_key),
    display_name=changes.get("display_name", delta.target_key),
    entity_type=changes.get("entity_type"),
    background=changes.get("description"),  # Map description to background
)
```

## Files Modified

- [x] `src/world_server/quantum/collapse.py` - Map description to background field

## Notes

In the future, we may want to add a CREATE_ITEM delta type for creating items (like the silver thimble) since items should be tracked separately from entities. Currently, discovered items are being created as entities which isn't semantically correct.

## Related Issues

- `docs/issues/create-entity-invalid-location-key/` - Fixed earlier (removed invalid location_key)
- `docs/issues/record-fact-invalid-category-enum/` - Fixed earlier (added category validation)
