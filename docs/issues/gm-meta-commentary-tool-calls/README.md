# GM Shows Meta-Commentary Before Tool Calls

**Status:** Done
**Priority:** Medium
**Detected:** 2025-12-29
**Related Sessions:** Session 302, Turn 3

## Problem Statement

When the GM needs to call a tool (like `get_scene_details`), it outputs meta-commentary like "Let me get the scene details for you." before the tool call. This breaks immersion by exposing the internal workings of the system to the player. The GM should either call tools silently or integrate them naturally into the narrative.

## Current Behavior

From audit log `turn_003_20251229_160531_gm.md`:

```
### [ASSISTANT]
(MessageContent(type='text', text='Let me get the scene details for you.', ...),
 MessageContent(type='tool_use', tool_name='get_scene_details', ...))
```

The player sees:
```
Let me get the scene details for you.

You find yourself in The Rusty Tankard...
```

## Expected Behavior

The GM should NOT output any text before tool calls that explains what it's doing. Either:

1. **Silent tool calls**: Call tools without announcing them
2. **Narrative integration**: "You take a moment to survey your surroundings..." (if any preamble is needed)

The player should just see:
```
You find yourself in The Rusty Tankard...
```

## Investigation Notes

The issue appears to be model-specific behavior (Claude tends to "think out loud" before tool calls). The current character break validation doesn't catch this pattern.

Patterns that should be filtered:
- "Let me [verb]..."
- "I'll [verb]..."
- "I need to [verb]..."
- "I should [verb]..."

## Root Cause

The `_CHARACTER_BREAK_PATTERNS` in `src/gm/gm_node.py` doesn't include patterns for meta-commentary about tool usage. The model outputs "helpful" explanations before tool calls, which is appropriate for an assistant but not for a game narrator.

## Proposed Solution

Two approaches (can use both):

### 1. Add detection patterns
Add to `_CHARACTER_BREAK_PATTERNS`:
```python
r"^let me (?:get|check|look|see|find)\b",
r"^i'?ll (?:get|check|look|see|find)\b",
r"^i (?:need|should|will) (?:to )?\w+\b",
```

### 2. Strip pre-tool text
In the response processing, strip any text that appears before the first tool call if it matches assistant-like patterns.

### 3. Update system prompt
Add explicit instruction:
```
NEVER announce what you're about to do. Don't say "Let me check..." or "I'll look...".
Just call the tool and use the result in your narrative.
```

## Implementation Details

Option 2 is probably most robust - strip text before tool calls during output processing.

## Files to Modify

- [ ] `src/gm/gm_node.py` - Add patterns or strip pre-tool text
- [ ] `src/gm/prompts.py` - Add explicit instruction
- [ ] `tests/test_gm/test_gm_node.py` - Add test cases

## Test Cases

- [ ] Test case 1: "Let me get the scene details" before tool call is stripped/rejected
- [ ] Test case 2: "I'll check your inventory" before tool call is stripped/rejected
- [ ] Test case 3: Normal narrative without meta-commentary passes

## Related Issues

- `docs/issues/gm-chatbot-question-ending/` - Related character break issue

## References

- `src/gm/gm_node.py:_CHARACTER_BREAK_PATTERNS` - Detection patterns
- `logs/llm/session_302/turn_003_20251229_160531_gm.md` - Audit log with issue
