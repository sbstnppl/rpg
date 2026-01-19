# RECORD_FACT Delta with Null Predicate/Value

**Status:** Done
**Priority:** High
**Detected:** 2025-12-30
**Related Sessions:** Session 307

## Problem Statement

The quantum pipeline generates a RECORD_FACT delta with null `predicate` and `value` fields, causing a `psycopg2.errors.NotNullViolation` when trying to insert into the `facts` table. This breaks the turn processing and causes a transaction rollback, even though the narrative was generated successfully.

## Current Behavior

When processing a "look around" action, the pipeline generates a delta like:

```python
DeltaType.RECORD_FACT for innkeeper_tom with:
- subject_type: 'entity'
- subject_key: 'innkeeper_tom'
- predicate: None  # PROBLEM
- value: None      # PROBLEM
- category: 'personal'
- confidence: 80
```

This causes:
```
psycopg2.errors.NotNullViolation: null value in column "predicate" of relation "facts" violates not-null constraint
DETAIL: Failing row contains (174, 307, entity, innkeeper_tom, null, null, personal, 80, f, null, f, null, 1, 1, ...)
```

The narrative was successfully generated but the state changes could not be committed.

## Expected Behavior

1. RECORD_FACT deltas should always have valid `predicate` and `value` fields
2. If the LLM fails to provide these, the delta should be:
   - Rejected during validation (before applying)
   - Or have sensible defaults applied
3. The turn should complete successfully with valid deltas applied

## Investigation Notes

- Error occurs in `src/world_server/quantum/` delta application
- The LLM (qwen3:32b) is generating incomplete fact deltas
- Narrative output was fine: "You scan the dim interior of Old Tom's tavern..."

## Root Cause

**Primary cause (prompt)**: The system prompt only said `record_fact: New information learned` without specifying the required fields (`predicate`, `value`). The LLM didn't know what structure was expected.

**Secondary cause (validation)**: Even when validation existed in `_validate_record_fact()`, it only checked key presence not None values, and wasn't called during collapse.

## Proposed Solution

1. Update prompt to specify required fields for `record_fact` with an example
2. Add defensive check before DB insert to skip invalid deltas
3. Strengthen validation to check for None values

## Implementation Details

### 1. Updated prompt in `branch_generator.py`:
```python
State deltas should capture meaningful changes. Each delta type has required fields:
- record_fact: {subject_key, predicate, value, category?, is_secret?} - predicate and value are REQUIRED

Example record_fact for learning NPC information:
{"delta_type": "record_fact", "target_key": "innkeeper_tom", "changes": {"subject_key": "innkeeper_tom", "predicate": "occupation", "value": "runs the tavern for 20 years"}}
```

### 2. Defensive validation in `collapse.py`:
```python
elif delta.delta_type == DeltaType.RECORD_FACT:
    predicate = changes.get("predicate")
    value = changes.get("value")

    # Skip invalid facts - LLM sometimes generates incomplete deltas
    if not predicate or not value:
        logger.warning(...)
        return
```

### 3. Strengthened `_validate_record_fact()` to use `if not predicate:` instead of `if "predicate" not in changes:`

## Files Modified

- [x] `src/world_server/quantum/branch_generator.py` - Updated prompt with required fields
- [x] `src/world_server/quantum/collapse.py` - Added defensive validation
- [x] `src/world_server/quantum/validation.py` - Strengthened validation for None values
- [x] `tests/test_world_server/test_quantum/test_collapse.py` - Added 3 tests for null handling

## Test Cases

- [x] Test RECORD_FACT delta with null predicate is skipped (`test_apply_record_fact_skips_null_predicate`)
- [x] Test RECORD_FACT delta with null value is skipped (`test_apply_record_fact_skips_null_value`)
- [x] Test RECORD_FACT delta with missing fields is skipped (`test_apply_record_fact_skips_missing_fields`)
- [x] Test valid RECORD_FACT delta is applied successfully (`test_apply_record_fact`)
- [x] Verified turn completes successfully in Session 308

## Related Issues

- None yet

## References

- `src/database/models/facts.py` - Facts model with NOT NULL constraints
- Session 307, Turn 1
