# Grounding Manifest Not Updated After create_entity Tool Call

**Status:** Investigating
**Priority:** High
**Detected:** 2025-12-29
**Related Sessions:** Session 302, Turn 5

## Problem Statement

When the GM creates a new entity using `create_entity` tool during a turn, the grounding manifest is not updated to include the new entity. This causes the grounding validator to reject valid references to the newly created entity, triggering unnecessary retries and eventually forcing the GM to strip the entity reference from the narrative.

## Current Behavior

From audit log `turn_005_20251229_160851_gm.md`:

1. GM calls `create_entity` for ale:
```json
{"entity_key": "tankard_ale_794", "entity_type": "item", "display_name": "Tankard Ale", "success": true}
```

2. GM calls `satisfy_need` with the new key (works fine):
```json
{"success": true, "need": "thirst", "item_consumed": "tankard_ale_794", "message": "Satisfied thirst: 80 -> 100"}
```

3. GM writes narrative using the key:
```
[tankard_ale_794:The ale] was placed before you...
```

4. **Grounding validator rejects it**:
```
**Invalid keys (not in manifest):**
- [tankard_ale_794:The ale] - key 'tankard_ale_794' does not exist
```

5. GM retries, invents a different key `ale_001`, still rejected

6. Eventually GM gives up and writes narrative without key references

## Expected Behavior

After `create_entity` returns a new entity key, that key should be immediately valid for use in the narrative. The grounding manifest should either:
1. Be updated dynamically during the tool loop
2. Include keys returned by `create_entity` as valid

## Investigation Notes

The grounding manifest is built in `src/gm/context_builder.py:build_grounding_manifest()` BEFORE the tool loop runs. When `create_entity` creates a new entity, it's committed to the database but the manifest is stale.

The validator in `src/gm/grounding_validator.py` checks keys against the pre-built manifest and doesn't know about mid-turn entity creation.

## Root Cause

**Stale manifest**: The grounding manifest is built once at the start of the turn and never updated. The tool execution loop creates entities that aren't reflected in the manifest used for validation.

## Proposed Solution

### Option 1: Track created entities during tool loop
Maintain a set of entity keys created during the tool loop. Add these to the valid keys list before grounding validation.

```python
# In GMNode
self._created_entity_keys: set[str] = set()

# When processing create_entity tool result
if tool_name == "create_entity" and result.get("success"):
    self._created_entity_keys.add(result["entity_key"])

# When validating grounding
valid_keys = manifest.all_keys() | self._created_entity_keys
```

### Option 2: Rebuild manifest before validation
After all tools complete, rebuild the grounding manifest to include new entities. This is more expensive but simpler.

### Option 3: Whitelist create_entity return keys
The grounding validator could receive the list of keys returned by `create_entity` and automatically whitelist them.

## Implementation Details

Option 1 is recommended:
1. Add `_created_entity_keys: set[str]` to `GMNode`
2. In `_execute_tool_call()`, capture `create_entity` success keys
3. In `_validate_grounding()`, pass created keys to validator
4. Modify `GroundingValidator.validate()` to accept additional valid keys

## Files to Modify

- [ ] `src/gm/gm_node.py` - Track created entities, pass to validator
- [ ] `src/gm/grounding_validator.py` - Accept additional valid keys parameter
- [ ] `tests/test_gm/test_grounding.py` - Add test for mid-turn entity creation

## Test Cases

- [ ] Test case 1: create_entity key is valid for immediate use in narrative
- [ ] Test case 2: Multiple create_entity calls all register valid keys
- [ ] Test case 3: Invalid keys still rejected (not in manifest or created)

## Related Issues

- Grounding validation is otherwise working correctly
- This affects any scenario where GM creates entities (items, NPCs) dynamically

## References

- `src/gm/gm_node.py` - Tool loop and grounding validation
- `src/gm/grounding_validator.py` - Validation logic
- `src/gm/context_builder.py` - Manifest building
- `logs/llm/session_302/turn_005_20251229_160851_gm.md` - Audit log with issue
