# Hallucinated Tool Parameters

**Status:** Won't Fix
**Priority:** Low
**Detected:** 2025-12-27
**Resolved:** 2025-12-27
**Related Sessions:** Session 293, Turn 13

## Problem Statement

The LLM sometimes includes non-existent parameters when calling tools. While the system ignores these, it indicates the LLM doesn't fully understand the tool schema.

## Current Behavior

Turn 13: Player drew sword and took defensive stance

LLM called:
```json
{
  "tool": "skill_check",
  "arguments": {
    "dc": 12,
    "skill": "perception",
    "description": "The warrior is observant of their surroundings..."  // NOT A VALID PARAM
  }
}
```

System logged: `Tool skill_check: Ignored hallucinated params: {'description'}`

The `description` parameter doesn't exist in the skill_check schema.

## Expected Behavior

LLM should only use parameters defined in the tool schema:
- `skill_check`: `skill`, `dc`, `modifier`, `context`

The `description` parameter was invented by the LLM.

## Investigation Notes

Tool schema for skill_check:
```python
{
    "name": "skill_check",
    "description": "Roll a skill check when outcome is uncertain.",
    "parameters": {
        "skill": {"type": "string", "description": "Skill to check"},
        "dc": {"type": "integer", "description": "Difficulty class"},
        "modifier": {"type": "integer", "description": "Additional modifier"},
        "context": {"type": "string", "description": "Context for the roll"}
    }
}
```

The LLM likely confused `context` with `description`, or invented a parameter that seemed useful.

## Root Cause

1. **Schema not memorized**: LLM doesn't perfectly remember tool schemas
2. **Similar names**: `context` vs `description` confusion
3. **Helpful invention**: LLM adds params that seem useful

## Proposed Solution

### Option A: Accept as Low Priority
The system already handles this gracefully by ignoring unknown params. Consider this acceptable behavior.

### Option B: Stricter Tool Definitions
Make tool descriptions more explicit about exact parameter names:
```
PARAMETERS (use EXACTLY these names):
- skill: The skill name
- dc: Difficulty class (10-25)
- context: Brief context description (NOT "description")
```

### Option C: Schema Validation Feedback
When unknown params detected, add to next prompt:
> "Note: skill_check only accepts: skill, dc, modifier, context"

## Files to Modify

- [ ] `src/gm/tools.py` - Improve tool descriptions (if Option B)
- [ ] `src/gm/gm_node.py` - Add feedback on hallucinated params (if Option C)

## Test Cases

- [ ] Test: Unknown parameter → Logged and ignored
- [ ] Test: Tool still executes correctly with valid params
- [ ] Test: (Option C) Feedback reduces future hallucinations

## Resolution

**Decision: Won't Fix**

The system already handles hallucinated parameters gracefully:

1. `_filter_tool_input()` in `src/gm/tools.py:122-149` filters out invalid params before tool execution
2. A warning is logged for debugging: `"Ignored hallucinated params: {extra_params}"`
3. Tools execute correctly with only valid parameters
4. Test coverage exists (`test_skill_check_ignores_extra_params()`, etc.)

This is acceptable behavior. LLMs occasionally invent parameters, and the robust filtering ensures no functional impact.

## Related Issues

- `llm-invents-wrong-item-keys` - Similar invention behavior
- Part of general LLM prompt-following challenges

## References

- `logs/llm/session_293/turn_013_*.md` - Hallucinated param logs
- `src/gm/tools.py` - Tool schema definitions
