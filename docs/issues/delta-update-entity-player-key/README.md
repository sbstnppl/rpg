# Delta UPDATE_ENTITY Fails - Wrong Entity Key "player"

**Status:** Done
**Priority:** High
**Detected:** 2025-12-30
**Resolved:** 2025-12-30
**Related Sessions:** Session 311

## Problem Statement

When applying a DeltaType.UPDATE_ENTITY delta for the player character, the system fails with "Entity not found: player". The delta is using the generic key "player" instead of the actual entity key (e.g., "test_hero"). This causes the delta applier to fail to find the entity in the database.

## Root Cause

`pipeline.py:554` hardcoded `player_key="player"` in BranchContext:

```python
return BranchContext(
    ...
    player_key="player",  # HARDCODED - should be actual entity key
    ...
)
```

The LLM received "player" in the context and used it in generated deltas, but the actual entity key was "test_hero".

## Solution Applied

**File:** `src/world_server/quantum/pipeline.py`

1. Added `_get_player_entity()` helper method to fetch player entity
2. Updated `_build_branch_context()` to use actual player entity key:

```python
# Get actual player entity key (not hardcoded "player")
player = self._get_player_entity()
player_key = player.entity_key if player else "player"

return BranchContext(
    ...
    player_key=player_key,
    ...
)
```

Also updated system prompt in `branch_generator.py` to clarify:
```
IMPORTANT: Use actual entity keys from the scene manifest, NOT generic terms like "player" or "npc".
```

## Files Modified

- [x] `src/world_server/quantum/pipeline.py` - Fetch actual player entity key
- [x] `src/world_server/quantum/branch_generator.py` - Updated system prompt

## Test Results

All quantum pipeline tests pass (275 passed, 2 pre-existing failures unrelated to this fix).

## Related Issues

- `docs/issues/create-entity-invalid-location-key/` - Fixed in same commit
- `docs/issues/record-fact-invalid-category-enum/` - Fixed in same commit
