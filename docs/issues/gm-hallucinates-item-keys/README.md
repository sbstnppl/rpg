# GM Hallucinates Item Keys Instead of Using Keys from Context

**Status:** Investigating
**Priority:** High
**Detected:** 2025-12-29
**Related Sessions:** Session 302, Turn 11

## Problem Statement

When calling tools like `take_item`, the GM invents/hallucinates item keys (e.g., `gold_coin_001`) instead of using the actual keys provided in the context (e.g., `test_hero_starting_gold`). This causes tool calls to fail with "Item not found" errors, and the GM then narrates as if the action succeeded anyway, creating state/narrative mismatches.

## Current Behavior

From audit log `turn_011_20251229_161741_gm.md`:

Context provided to GM:
```
**Your inventory** (use KEY in drop_item, give_item, etc.):
- test_hero_starting_gold: Gold Coins (10)
```

GM tool call:
```python
take_item(item_key='gold_coin_001')  # WRONG - hallucinated key
```

Tool result:
```json
{"error": "Item not found: gold_coin_001"}
```

GM narrative:
```
You pick up the gold coin from Tom's bar, tucking it safely away.
```

The narrative says the gold was picked up, but it wasn't (error was ignored).

## Expected Behavior

1. GM should use EXACT keys from context: `take_item(item_key='test_hero_starting_gold')`
2. If tool returns an error, GM should NOT narrate as if action succeeded
3. Or GM should narrate an in-story reason for failure

## Investigation Notes

The system prompt in `src/gm/prompts.py` explicitly instructs:
```
### TOOL PARAMETER RULES (CRITICAL!)
When calling tools with entity keys (item_key, entity_key, npc_key, etc.):
- ALWAYS copy the EXACT key shown in context - never derive or invent keys
- Keys appear BEFORE the colon: "ale_mug_001: Mug of Ale" → item_key="ale_mug_001"
- WRONG: item_key="mug_of_ale" (invented from display name)
- RIGHT: item_key="ale_mug_001" (copied exactly from context)
```

Despite this, the LLM still invents keys like `gold_coin_001` from the display name "Gold Coins".

Additionally, the prompt says:
```
### HANDLING TOOL FAILURES (CRITICAL!)
If a tool returns an error (success=false or error message):
- NEVER mention the error to the player
- Option A: Narrate as if the action succeeded (for minor issues)
```

This instruction is problematic - it tells GM to ignore errors!

## Root Cause

Two issues:
1. **LLM key hallucination**: Despite explicit instructions, LLM derives keys from display names
2. **Error handling instruction is too permissive**: Telling GM to "narrate as if succeeded" masks real errors

## Proposed Solution

### 1. Improve key formatting in context
Make keys more visually distinct:
```
**Your inventory** (COPY the KEY before the colon):
- KEY: test_hero_starting_gold | Gold Coins (10)
```

### 2. Add key validation before tool execution
Check if provided key exists before executing tool:
```python
if tool_name == "take_item":
    if not self._validate_item_key(tool_input["item_key"]):
        return {"error": f"Invalid key. Valid keys: {self._get_valid_item_keys()}"}
```

### 3. Fix error handling instructions
Change from "narrate as if succeeded" to "narrate in-story failure or ask for clarification"

### 4. Add retry with key hints on error
When tool fails with "Item not found", include valid keys in the error message to help GM retry correctly.

## Implementation Details

1. Update context builder to use more distinct key formatting
2. Add key validation in tool execution
3. Update system prompt error handling section
4. Add valid keys to error messages

## Files to Modify

- [ ] `src/gm/context_builder.py` - Improve key formatting
- [ ] `src/gm/tools.py` - Add key validation, improve error messages
- [ ] `src/gm/prompts.py` - Fix error handling instructions

## Test Cases

- [ ] Test case 1: GM uses exact key from context
- [ ] Test case 2: Invalid key returns helpful error with valid keys
- [ ] Test case 3: Tool errors are handled properly in narrative

## Related Issues

- This causes major state/narrative mismatches
- Compounds with `move_to` not registered issue

## References

- `src/gm/prompts.py` - System prompt with key instructions
- `src/gm/tools.py` - Tool execution
- `src/gm/context_builder.py` - Context building
- `logs/llm/session_302/turn_011_20251229_161741_gm.md` - Audit log with error
