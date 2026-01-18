# Item State Desync - Ref-Based Mode

**Status**: Awaiting Verification
**Priority**: HIGH
**Verification**: 0/3
**Last Verified**: -
**Discovered**: Session 347 Play Test (2026-01-18)

## Problem

In ref-based mode, when an NPC "gives" the player an item (e.g., Tom gives ale), the narrative describes the item but no `TRANSFER_ITEM` delta is created. The item exists only in narrative, not in game state.

### Observed Behavior

1. Player orders ale from Tom the barkeep
2. Narrative describes: "Tom slides a frothy ale across the bar"
3. No `TRANSFER_ITEM` delta is generated
4. Player inventory remains empty
5. Running `status` shows no ale in inventory

### Expected Behavior

1. Player orders ale
2. System creates the item if it doesn't exist (or uses existing one)
3. `TRANSFER_ITEM` delta transfers item to player
4. Player inventory contains the ale

## Root Cause Analysis

The issue stems from how the ref-based system handles items that don't yet exist:

### How Ref-Based Mode Works

1. **RefManifest built at turn start** (`ref_manifest.py:89-155`)
   - Only existing entities/items get refs (A, B, C, etc.)
   - Items that will be created during the turn have NO ref

2. **LLM must use refs from manifest** (`reasoning.py:642-714`)
   - System prompt requires: "Use ONLY refs from the manifest"
   - No mechanism to reference items that don't exist yet

3. **When item doesn't exist**:
   - LLM needs to reference "the ale Tom is giving"
   - LLM invents a ref like "T" (not in manifest)
   - `_resolve_ref("T")` fails silently (`delta_translator.py:650-686`)
   - Delta is skipped entirely

4. **Auto-create mechanism never triggers**:
   - DeltaPostProcessor can auto-create items
   - But it only processes deltas that reach it
   - Invalid ref = delta discarded before postprocessing

### The Core Problem

**Ref-based mode has no way to reference items that need to be created.** The system assumes all items exist before the turn starts.

## Files Involved

| File | Lines | Role |
|------|-------|------|
| `delta_translator.py` | 650-686 | `_resolve_ref()` - silent failure on invalid refs |
| `reasoning.py` | 642-714 | System prompt - ref usage rules |
| `ref_manifest.py` | 89-155 | Ref assignment - only existing entities |
| `delta_postprocessor.py` | - | Auto-create mechanism (never reached) |

## Potential Solutions

### Option 1: Placeholder Refs for New Items

Add special syntax for items that don't exist yet:
```
TRANSFER_ITEM: @NEW:ale -> [A]
```
The `@NEW:` prefix signals the item should be created first.

**Pros**: Clean syntax, explicit intent
**Cons**: Requires LLM to learn new syntax

### Option 2: Two-Phase Delta Processing

1. First pass: Process CREATE_ITEM deltas
2. Update RefManifest with new items
3. Second pass: Process TRANSFER_ITEM deltas

**Pros**: Works with existing delta types
**Cons**: Requires orchestration changes

### Option 3: Implicit Item Creation in TRANSFER_ITEM

If TRANSFER_ITEM references an unknown item, auto-create it:
```
TRANSFER_ITEM: ale -> [A]
# System sees "ale" isn't a ref, interprets as item_key to create
```

**Pros**: Simplest for LLM
**Cons**: Ambiguous syntax (is "ale" a ref or key?)

### Option 4: Hybrid CREATE+TRANSFER Delta

New delta type that combines both operations:
```
GIVE_ITEM: "ale" from [B] to [A]
# Creates item and transfers in one atomic operation
```

**Pros**: Single operation, clear intent
**Cons**: New delta type to implement

## Recommended Approach

**Option 1 (Placeholder Refs)** with fallback to **Option 3 (Implicit Creation)**.

This gives the LLM explicit syntax for clarity while handling edge cases gracefully.

## Related Issues

- `narrative-state-desync-items` - Similar symptom, different cause (entity naming)
- `llm-invents-wrong-item-keys` - LLM making up identifiers

## Reproduction Steps

1. Start a game session with ref-based quantum pipeline
2. Go to a location with an NPC who can give items (e.g., tavern with barkeep)
3. Request an item: "I'd like to order an ale"
4. Check delta log - no TRANSFER_ITEM generated
5. Check inventory - empty

## Test Coverage Needed

- [ ] Test: TRANSFER_ITEM with non-existent item ref fails gracefully
- [ ] Test: New item creation syntax (once implemented)
- [ ] Test: End-to-end "NPC gives item" scenario
