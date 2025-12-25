# Item Naming Technical Debt

**Status:** Done
**Priority:** Medium
**Detected:** 2025-12-25
**Completed:** 2025-12-25
**Related Sessions:** Gameplay testing session

## Problem Statement

Item keys like `clean_shirt_001` embed state ("clean") in the permanent identifier. When the item state changes (shirt gets dirty), the key becomes misleading. State should be stored in item properties, not baked into the key.

## Solution Implemented

Created `src/services/item_state_extractor.py` utility that:
1. Extracts state adjectives from display names
2. Returns clean base name for key generation and display
3. Returns extracted state for storage in `properties.state`

### Key Changes

| File | Change |
|------|--------|
| `src/services/item_state_extractor.py` | **NEW** - State extraction utility |
| `src/managers/item_manager.py` | Added `update_item_state()` method |
| `src/agents/tools/executor.py` | Updated `spawn_item` and `acquire_item` |
| `src/gm/tools.py` | Updated `create_entity` for items |
| `src/services/emergent_item_generator.py` | Updated key generation |

### State Adjectives Recognized

| Category | Adjectives |
|----------|------------|
| Cleanliness | clean, dirty, filthy, muddy, dusty, grimy |
| Condition | pristine, new, worn, weathered, damaged, rusty, tattered, broken, decrepit |
| Freshness | fresh, stale, rotten, spoiled |
| Quality | crude, rough, poor, common, good, fine, exceptional, masterwork, exquisite |
| Age | old, ancient |

### Example Transformation

Input: "Clean Linen Shirt"
- `item_key`: `linen_shirt` (not `clean_linen_shirt`)
- `display_name`: `Linen Shirt`
- `properties.state`: `{"cleanliness": "clean"}`

When state changes:
```python
item_manager.update_item_state("linen_shirt", "cleanliness", "dirty")
# properties.state: {"cleanliness": "dirty"}
# display_name remains: "Linen Shirt"
# item_key remains: "linen_shirt"
```

## Test Coverage

- 30 tests for `item_state_extractor` utility
- 5 tests for `ItemManager.update_item_state()`
- All 104 tool tests pass
- All 1873 manager/database tests pass (excluding 4 pre-existing failures)

## Migration Notes

No database migration required. `properties.state` is additive:
- Existing items work unchanged (no state = neutral state assumed)
- New items have `properties.state` populated automatically
- `update_item_state()` creates state dict if missing
