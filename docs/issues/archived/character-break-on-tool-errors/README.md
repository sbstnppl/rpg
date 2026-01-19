# Character Break on Tool Errors

**Status:** Done
**Priority:** Medium
**Detected:** 2025-12-27
**Related Sessions:** Session 293, Turn 6

## Problem Statement

When a tool call fails (e.g., item not found), the LLM exposes technical error details in the narrative instead of handling the failure gracefully in-story.

## Current Behavior

Turn 6: Player tried to drink from ale (but LLM used wrong item key)

Tool returned: `{"error": "Item not found: mug_of_ale"}`

LLM response:
> "You raise the 'mug of ale' to your lips, taking a refreshing sip. The drink cools your throat and carries a hint of bitterness. However, **the mug itself is not recognized in your inventory, leaving its presence unaccounted for.**"

The italicized part is technical meta-commentary that breaks immersion.

Character validation caught this with pattern `\bis not recognized\b` and triggered a retry.

## Expected Behavior

When a tool fails, the LLM should:
1. Handle it gracefully IN THE STORY
2. Never mention technical terms like "not recognized", "error", "inventory"
3. Either narrate a plausible in-story reason OR ignore the error and narrate normally

Example graceful handling:
> "You reach for the mug, but your hand finds only empty air—the drink must have been moved while you weren't looking."

Or simply:
> "You raise the mug to your lips, savoring the cool ale as it eases your thirst."

## Investigation Notes

The error handling flow:
1. Tool returns error JSON
2. LLM sees error in conversation
3. LLM tries to narrate but mentions the error
4. Character validation catches it and retries
5. Retry produces clean narrative

The issue is that the error message is shown to the LLM, which then feels compelled to explain it.

## Root Cause

1. **Error exposure**: Tool errors shown directly to LLM
2. **No guidance**: No prompt instruction on handling tool failures gracefully
3. **Model behavior**: qwen3 tries to be "helpful" by explaining errors

## Proposed Solution

### Option A: Add Error Handling Instruction
Add to system prompt:
```
### HANDLING TOOL FAILURES
If a tool returns an error:
- NEVER mention the error to the player
- NEVER use words like "error", "not found", "not recognized", "unaccounted"
- Either: Narrate as if the action succeeded (for minor errors)
- Or: Narrate an in-story reason for failure (e.g., "the item slips from your grasp")
- Keep full immersion at all times
```

### Option B: Filter Error Messages
Wrap tool results before showing to LLM:
- On error: Return generic "The action couldn't be completed"
- Hide technical details from LLM

### Option C: Both
Combine prompt guidance with error filtering.

## Files to Modify

- [x] `src/gm/prompts.py` - Add error handling instructions (lines 69-78, 379-382)
- [x] `src/gm/gm_node.py` - Add detection patterns for technical terms (lines 133-138)

## Test Cases

- [ ] Test: Tool error → No technical terms in narrative
- [ ] Test: "not recognized" → Triggers character validation
- [ ] Test: After retry → Clean immersive narrative

## Related Issues

- `tool-output-leaked-to-player` - Similar LLM behavior issue
- Both need better prompt guidance for handling internal data

## References

- `logs/llm/session_293/turn_006_*.md` - Error handling failure logs
- `src/gm/gm_node.py:_CHARACTER_BREAK_PATTERNS` - Validation patterns
