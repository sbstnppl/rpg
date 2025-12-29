# Gold Stack Splitting - Dropping "One Coin" Drops Entire Stack

**Status:** Done
**Priority:** Medium
**Detected:** 2025-12-29
**Completed:** 2025-12-29
**Related Sessions:** Session 302, Turn 10

## Problem Statement

When the player asks to drop "one gold coin" as a tip, the GM drops the entire stack of 10 gold coins instead of splitting the stack. The game doesn't support stackable/splittable items, so operations on partial quantities fail silently by affecting the whole stack.

## Current Behavior

Player action:
```
"I drop one of my gold coins on the bar as a tip"
```

GM tool call:
```python
drop_item(item_key='test_hero_starting_gold')
```

Result in database:
```sql
SELECT item_key, display_name, holder_id FROM items WHERE item_key LIKE '%gold%';
-- test_hero_starting_gold | Gold Coins (10) | NULL (dropped)
```

The entire "Gold Coins (10)" item was dropped, not split into 9+1.

## Solution Implemented

Added quantity-based operations for stackable items. The Item model already had `quantity` and `is_stackable` fields - we only needed to add business logic.

### Design Decisions
- `quantity` parameter: Optional on give_item/drop_item/take_item, defaults to "all" (entire stack)
- Auto-merge: When taking/receiving stackable items, merge with existing stacks of same type

### New ItemManager Methods

1. **`split_stack(item_key, quantity)`** - Split quantity from stackable item, creating new item
2. **`merge_stacks(target_key, source_key)`** - Combine two stacks of same type
3. **`find_mergeable_stack(holder_id, display_name)`** - Find existing stack to merge into
4. **`transfer_quantity(item_key, quantity, to_entity_id, to_storage_key)`** - Transfer with auto-split and auto-merge

### GM Tool Updates

All three tools now accept an optional `quantity` parameter:

```python
drop_item(item_key: str, quantity: int | None = None) -> dict[str, Any]
take_item(item_key: str, quantity: int | None = None) -> dict[str, Any]
give_item(item_key: str, recipient_key: str, quantity: int | None = None) -> dict[str, Any]
```

## Files Modified

- [x] `src/managers/item_manager.py` - Added 4 new methods for stack operations
- [x] `src/gm/tools.py` - Updated drop_item/take_item/give_item with quantity parameter
- [x] `tests/test_managers/test_item_manager_stacking.py` - New test file (23 tests)
- [x] `tests/test_gm/test_tools_stacking.py` - New test file (9 tests)

## Test Cases

- [x] Test case 1: Drop partial stack creates two items (split + remaining)
- [x] Test case 2: Taking partial stack from ground works with auto-merge
- [x] Test case 3: Giving partial stack to NPC auto-merges with their existing stack
- [x] Test case 4: Non-stackable items with quantity specified return error

## Example Usage

```python
# Player has 50 gold, wants to give 10 to merchant
result = tools.give_item("player_gold", "merchant", quantity=10)
# Player now has 40 gold, merchant receives 10 (auto-merged if they had gold)

# Player wants to drop 1 coin as tip
result = tools.drop_item("player_gold", quantity=1)
# Player now has 49 gold, 1 coin is on the ground
```

## References

- `src/managers/item_manager.py:1548-1765` - Stack operation methods
- `src/gm/tools.py:2066-2234` - Updated GM tools
- `tests/test_managers/test_item_manager_stacking.py` - ItemManager stacking tests
- `tests/test_gm/test_tools_stacking.py` - GM tools stacking tests
