# CREATE_ENTITY Delta Uses Invalid EntityType "location"

**Status:** Done
**Priority:** High
**Detected:** 2026-01-02
**Fixed:** 2026-01-02
**Related Sessions:** 330

## Problem Statement

The quantum pipeline's CREATE_ENTITY delta generator is producing `entity_type: "location"` which is not a valid value in the EntityType enum. This causes a PostgreSQL error when trying to insert the entity, rolling back the entire transaction and causing the turn to fail.

## Current Behavior

```
(psycopg2.errors.InvalidTextRepresentation) invalid input value for enum entitytype: "location"
LINE 1: ...30, 'hidden_storage_room', 'Hidden Storage Room', 'location'...
```

Player action: "try to pick the lock on the back door to see what's behind it"

The skill check succeeded (DC 10: Auto-success) but the CREATE_ENTITY delta failed because:
- LLM generated `entity_type: "location"` for the hidden storage room
- The EntityType enum doesn't include "location" as a valid value

The entire transaction was rolled back, so even though the narrative was shown, no state changes were persisted.

## Expected Behavior

1. The CREATE_ENTITY delta should only use valid EntityType enum values
2. Valid types should be: npc, monster, animal (for entities), item/weapon/etc (for items), location (for locations)
3. Each type should route to the appropriate manager (EntityManager, ItemManager, LocationManager)

## Investigation Notes

- Session 330, Turn 8
- The skill check worked correctly (DC 10, auto-success)
- The narrative was generated and displayed before the delta application failed
- Transaction rollback means no skill check result was recorded either

## Root Cause

Two issues:
1. The LLM's entity_type values were not validated/normalized in the delta translator
2. The collapse.py code only had two branches: items and entities, with no handling for locations

## Solution Implemented

### 1. Delta Translator Validation (`src/world_server/quantum/delta_translator.py`)

Added `VALID_ENTITY_TYPES` mapping that normalizes LLM output to valid types:
```python
VALID_ENTITY_TYPES = {
    # Entity types (go to EntityManager)
    "npc": "npc", "monster": "monster", "animal": "animal",
    # Item types (go to ItemManager)
    "item": "item", "object": "item", "weapon": "weapon", ...
    # Location types (go to LocationManager)
    "location": "location", "room": "location", "place": "location",
}
```

- Unknown types default to "item" with a warning
- Added `generate_location_key()` for location keys (prefix: `loc_`)

### 2. Collapse Routing (`src/world_server/quantum/collapse.py`)

Updated `_apply_single_delta()` to handle four cases:
1. **Items** (item, weapon, tool, object, etc.) → `ItemManager.create_item()`
2. **Locations** (location, room, place, area) → `LocationManager.create_location()`
3. **Entities** (npc, monster, animal) → `EntityManager.create_entity()`
4. **Unknown** → Default to misc item with warning

## Files Modified

- [x] `src/world_server/quantum/delta_translator.py` - Added VALID_ENTITY_TYPES, validation, generate_location_key()
- [x] `src/world_server/quantum/collapse.py` - Added location routing, unknown type fallback

## Test Cases

- [x] CREATE_ENTITY with entity_type='location' routes to LocationManager
- [x] CREATE_ENTITY with entity_type='room' routes to LocationManager
- [x] CREATE_ENTITY with entity_type='object' routes to ItemManager as misc
- [x] CREATE_ENTITY with unknown entity_type defaults to misc item
- [x] All 462 quantum tests pass

## Related Issues

- `docs/issues/quantum-branch-hallucinated-npc/` - Similar LLM constraint issue (resolved)
- `docs/issues/transfer-item-nonexistent-item/` - Delta referencing non-existent entities (resolved)

## References

- `src/world_server/quantum/delta_translator.py` - Entity type validation
- `src/world_server/quantum/collapse.py` - Entity type routing
- `src/managers/location_manager.py` - Location creation
