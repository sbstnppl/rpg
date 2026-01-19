# LLM Invents Wrong Item Keys

**Status:** Done
**Priority:** High
**Detected:** 2025-12-27
**Related Sessions:** Session 293, Turn 6

## Problem Statement

When the LLM calls tools that require `item_key` parameters, it generates human-readable names instead of copying the actual entity keys from the context. This causes tool failures and state inconsistencies.

## Current Behavior

Player input: "I take a drink from the ale"

LLM called:
```json
{
  "tool": "satisfy_need",
  "arguments": {
    "activity": "drinking ale",
    "amount": 25,
    "item_key": "mug_of_ale",  // WRONG - invented key
    "need": "hunger"
  }
}
```

Tool returned: `{"error": "Item not found: mug_of_ale"}`

The system prompt clearly showed: `ale_mug_001: Mug of Ale` in inventory.

## Expected Behavior

LLM should use the exact key from context:
```json
{
  "item_key": "ale_mug_001"  // Correct key from prompt
}
```

## Investigation Notes

From prompt context in `logs/llm/session_293/turn_006_*.md`:
```
**Your inventory:**
- ale_mug_001: Mug of Ale
```

The LLM saw `ale_mug_001: Mug of Ale` but generated `mug_of_ale` - a human-readable snake_case version.

This suggests the LLM:
1. Understands it needs an item key
2. Derives one from the display name instead of copying the actual key
3. Possibly confused by the `key: Display Name` format

## Root Cause

1. **LLM behavior**: qwen3:32b generates plausible-looking keys instead of copying exact keys
2. **Prompt format**: `key: Display Name` format may not be clear enough
3. **No validation**: Tool accepts any string, fails at DB lookup

## Proposed Solution

### Option A: Prompt Improvement (Low effort)
Add explicit instruction in system prompt:
```
CRITICAL: When calling tools with item_key, entity_key, etc., you MUST use the EXACT key shown before the colon.
Example: If inventory shows "ale_mug_001: Mug of Ale", use item_key="ale_mug_001" NOT "mug_of_ale"
```

### Option B: Fuzzy Key Matching (Medium effort)
Add post-processing in tool execution to fuzzy-match keys:
- If `mug_of_ale` not found, search for items containing "mug" and "ale"
- If single match, use that key
- If multiple matches, return helpful error

### Option C: Key-Only Format (Medium effort)
Change prompt format to emphasize keys:
```
**Your inventory (use keys in tool calls):**
- [ale_mug_001] Mug of Ale
- [bread_001] Bread Loaf
```

## Implementation Details

For Option A (recommended first step):

Add to `src/gm/prompts.py` system prompt:
```python
### TOOL PARAMETER RULES
When calling tools with entity keys (item_key, entity_key, npc_key, etc.):
- ALWAYS copy the exact key shown in context
- Keys are the text BEFORE the colon (e.g., "ale_mug_001" from "ale_mug_001: Mug of Ale")
- NEVER generate or derive keys from display names
- WRONG: item_key="mug_of_ale" (invented)
- RIGHT: item_key="ale_mug_001" (copied from context)
```

## Files to Modify

- [ ] `src/gm/prompts.py` - Add key usage instructions
- [ ] `src/gm/context_builder.py` - Possibly change key display format
- [ ] `src/gm/tools.py` - Optionally add fuzzy matching fallback

## Test Cases

- [ ] Test: LLM uses exact item key from inventory context
- [ ] Test: Tool returns clear error when key not found
- [ ] Test: (Optional) Fuzzy matching finds correct item

## Related Issues

- Related to grounding validation (entity references in narrative)
- Could extend validation to tool call parameters

## References

- `logs/llm/session_293/turn_006_*.md` - Full reproduction logs
- `src/gm/tools.py` - Tool implementations
- `src/gm/context_builder.py` - Inventory display formatting
