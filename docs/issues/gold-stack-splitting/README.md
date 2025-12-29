# Gold Stack Splitting - Dropping "One Coin" Drops Entire Stack

**Status:** Investigating
**Priority:** Medium
**Detected:** 2025-12-29
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

## Expected Behavior

When player specifies a partial quantity:
1. Stack should split: "Gold Coins (10)" → "Gold Coins (9)" (kept) + "Gold Coin" (dropped)
2. Or: GM should recognize this and create a new single coin entity
3. Or: System should prevent dropping currency entirely and use a "pay" mechanism

## Investigation Notes

The item system treats items as indivisible units. There's no concept of:
- Stack quantity as a property
- Stack splitting
- Partial operations

Items like "Gold Coins (10)" have the quantity baked into the display_name, not as a separate field.

## Root Cause

The item model doesn't support stackable items with quantities. Each item is a unique entity. The "(10)" in "Gold Coins (10)" is just part of the display name, not a quantity field.

The GM correctly called `drop_item` for the gold, but the system has no way to split stacks.

## Proposed Solution

### Option 1: Add quantity field to items (recommended)
```python
class Item:
    ...
    quantity: int = 1
    is_stackable: bool = False
```

When dropping partial amounts:
1. Reduce quantity on original
2. Create new item with dropped quantity

### Option 2: LLM-side workaround
Instruct GM to create a new "single gold coin" entity when player wants to give partial stack, and leave the original reduced in name.

### Option 3: Currency as special case
Treat gold/coins differently - as a numeric value on player rather than an item.

## Implementation Details

Option 1 requires:
1. Add `quantity` and `is_stackable` fields to Item model
2. Add migration
3. Update `drop_item` tool to accept optional `quantity` parameter
4. Implement stack splitting logic
5. Update `take_item` and `give_item` similarly

## Files to Modify

- [ ] `src/database/models/item.py` - Add quantity field
- [ ] `src/gm/tools.py` - Update drop_item/take_item/give_item
- [ ] `alembic/versions/` - Migration for quantity field
- [ ] Tests for stack operations

## Test Cases

- [ ] Test case 1: Drop partial stack creates two items
- [ ] Test case 2: Taking partial stack from ground works
- [ ] Test case 3: Stacking same items combines quantities
- [ ] Test case 4: Non-stackable items remain singular

## Related Issues

- This is a feature gap, not a bug per se
- Related to item system design

## References

- `src/database/models/item.py` - Item model
- `src/gm/tools.py:drop_item` - Drop tool implementation
- `logs/llm/session_302/turn_010_20251229_161555_gm.md` - Audit log
