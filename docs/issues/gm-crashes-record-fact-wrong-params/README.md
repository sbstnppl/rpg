# GM Crashes When Calling record_fact with Wrong Parameters

**Status:** ✅ RESOLVED
**Priority:** High
**Detected:** 2025-12-28
**Resolved:** 2025-12-29
**Related Sessions:** 301

## Resolution

Fixed in `src/gm/tools.py` (lines 946-963). The fix:
1. Added validation for required parameters (subject_type, subject_key, predicate, value) before calling record_fact
2. Returns helpful error with missing params list and hint
3. Wrapped call in try/catch to handle any unexpected errors gracefully
4. Also added similar protection to create_entity tool

## Problem Statement

The GM pipeline crashes when the LLM calls the `record_fact` tool with hallucinated or incorrect parameter names. Instead of gracefully handling the error, the entire turn fails with a TypeError, leaving the game in an error state.

## Current Behavior

Turn 8 attempted a persuasion action. The GM:
1. First ignored some hallucinated params: `{'category', 'key'}`
2. Then crashed when calling `record_fact` with missing required arguments

```
Tool record_fact: Ignored hallucinated params: {'category', 'key'}
GM node error
Traceback (most recent call last):
  File "/Volumes/nfs/procyon-projects/rpg/src/gm/graph.py", line 90, in gm_node
    response = await node.run(player_input, turn_number)
  ...
  File "/Volumes/nfs/procyon-projects/rpg/src/gm/tools.py", line 945, in execute_tool
    return self.record_fact(**tool_input)
TypeError: GMTools.record_fact() missing 3 required positional arguments:
'subject_type', 'subject_key', and 'predicate'

Error: GMTools.record_fact() missing 3 required positional arguments:
'subject_type', 'subject_key', and 'predicate'
Error: No GM response to validate
Error: No GM response to apply
```

The game then shows:
- "Error: No GM response to validate"
- "Error: No GM response to apply"

## Expected Behavior

When the LLM provides invalid tool parameters:
1. The system should catch the TypeError
2. Return an error result to the LLM: `{"error": "Missing required params: subject_type, subject_key, predicate"}`
3. Allow the LLM to retry or narrate gracefully
4. NOT crash the entire turn

## Investigation Notes

The code already handles some hallucinated params (ignoring `category` and `key`), but then fails when required params are still missing after filtering.

From the stack trace:
- `src/gm/tools.py:945` - `execute_tool` unpacks `**tool_input` directly
- No try/catch around the actual function call
- Missing params cause TypeError

## Root Cause

The `execute_tool` method doesn't validate that all required parameters are present before calling the tool function. It directly unpacks `**tool_input` which causes TypeError when required args are missing.

## Proposed Solution

Add parameter validation before calling tools:
1. Check required params are present
2. Return error dict instead of crashing
3. Let tool loop retry with error feedback

```python
def execute_tool(self, name: str, tool_input: dict) -> dict:
    try:
        # existing logic
        return self.record_fact(**tool_input)
    except TypeError as e:
        return {"error": f"Invalid tool parameters: {e}"}
```

## Implementation Details

<After investigation>

## Files to Modify

- [ ] `src/gm/tools.py` - Add try/catch in execute_tool
- [ ] `src/gm/gm_node.py` - Ensure tool errors are handled gracefully

## Test Cases

- [ ] Test case 1: record_fact with missing subject_type returns error dict
- [ ] Test case 2: record_fact with missing all params returns error dict
- [ ] Test case 3: Tool error allows GM to retry/recover

## Related Issues

- Issue #1: GM repeats response after tool error
- Grounding retry system

## References

- `src/gm/tools.py:945` - execute_tool method
- `logs/llm/session_301/turn_008_*.md` - Audit logs showing crash
