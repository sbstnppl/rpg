# RECORD_FACT Delta Uses Invalid Category Enum Value "quest"

**Status:** Done
**Priority:** High
**Detected:** 2025-12-30
**Resolved:** 2025-12-30
**Related Sessions:** Session 311

## Problem Statement

When the quantum pipeline generates a RECORD_FACT delta, it includes a `category` field with value "quest" which is not a valid value in the `factcategory` PostgreSQL enum. This causes a database error and rolls back the entire transaction.

## Root Cause

The LLM didn't know the valid FactCategory enum values. The system prompt only mentioned `category?` as optional but didn't list valid values:

```
- record_fact: {subject_key, predicate, value, category?, is_secret?}
```

Valid values are: `personal`, `secret`, `preference`, `skill`, `history`, `relationship`, `location`, `world`

The LLM invented "quest" which doesn't exist in the enum.

## Solution Applied

### 1. Updated system prompt with valid categories

**File:** `src/world_server/quantum/branch_generator.py`

```
- record_fact: {subject_key, predicate, value, category?, is_secret?}
  Valid categories: personal, secret, preference, skill, history, relationship, location, world
```

### 2. Added validation in collapse.py

**File:** `src/world_server/quantum/collapse.py`

```python
# Validate category - LLM sometimes invents invalid values like "quest"
valid_categories = {
    "personal", "secret", "preference", "skill",
    "history", "relationship", "location", "world"
}
raw_category = changes.get("category") or "personal"
if raw_category not in valid_categories:
    logger.warning(
        f"Invalid fact category '{raw_category}' for {delta.target_key}, "
        f"using 'personal'"
    )
    raw_category = "personal"
```

Now invalid categories are caught and fall back to "personal" instead of crashing.

## Files Modified

- [x] `src/world_server/quantum/branch_generator.py` - Added valid category values to system prompt
- [x] `src/world_server/quantum/collapse.py` - Added category validation with fallback

## Test Results

All quantum pipeline tests pass (275 passed, 2 pre-existing failures unrelated to this fix).

## Related Issues

- `docs/issues/delta-update-entity-player-key/` - Fixed in same commit
- `docs/issues/create-entity-invalid-location-key/` - Fixed in same commit
