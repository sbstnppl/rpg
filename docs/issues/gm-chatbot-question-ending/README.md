# GM Response Ends with Chatbot-like Question

**Status:** Investigating
**Priority:** Medium
**Detected:** 2025-12-29
**Related Sessions:** Session 302, Turn 3

## Problem Statement

The GM narrative ends with chatbot-like phrasing such as "Would you like to do anything specific in the tavern?" This breaks immersion by making the narrator sound like an AI assistant rather than an invisible storyteller. The system prompt explicitly forbids this pattern.

## Current Behavior

GM response from Turn 3:
```
You find yourself in The Rusty Tankard, a warm and inviting tavern...
[good narrative prose]
...The only exit you can see leads back to the Village Square.

Would you like to do anything specific in the tavern?
```

The trailing question is inappropriate for an RPG narrator.

## Expected Behavior

The narrative should end with a natural pause that invites player input without explicitly asking:

```
You find yourself in The Rusty Tankard, a warm and inviting tavern...
[good narrative prose]
...The only exit you can see leads back to the Village Square.
```

Or end with something that naturally invites action:
```
...Old Tom glances your way, as if waiting to see what you'll do.
```

## Investigation Notes

From `src/gm/prompts.py` system prompt:
```
ABSOLUTE RULES - VIOLATIONS WILL FAIL VALIDATION:
...
3. NEVER use assistant phrases: "You're welcome", "Feel free to ask", "How can I help", "Happy to help"
```

However, "Would you like to..." is NOT in this explicit list.

From `src/gm/gm_node.py:_CHARACTER_BREAK_PATTERNS`:
```python
# Chatbot phrases
r"\bfeel free to (?:ask|reach out)\b",
r"\byou'?re welcome\b",
r"\bhow can i help\b",
```

Again, "Would you like to..." is not detected.

## Root Cause

The character break detection patterns in `_CHARACTER_BREAK_PATTERNS` don't include common chatbot question endings like:
- "Would you like to..."
- "What would you like to do?"
- "Is there anything else..."
- "Do you want to..."

## Proposed Solution

Add these patterns to `_CHARACTER_BREAK_PATTERNS` in `src/gm/gm_node.py`:
```python
r"\bwould you like to\b",
r"\bwhat would you like to\b",
r"\bis there anything (?:else|specific)\b",
r"\bdo you (?:want|need) to\b",
r"\bwhat do you want to\b",
```

Also update the system prompt in `src/gm/prompts.py` to explicitly forbid question endings.

## Implementation Details

1. Add patterns to `_CHARACTER_BREAK_PATTERNS`
2. Update ABSOLUTE RULES section in system prompt
3. Add test cases for these patterns

## Files to Modify

- [ ] `src/gm/gm_node.py` - Add patterns to `_CHARACTER_BREAK_PATTERNS`
- [ ] `src/gm/prompts.py` - Update ABSOLUTE RULES section
- [ ] `tests/test_gm/test_gm_node.py` - Add tests for new patterns

## Test Cases

- [ ] Test case 1: Response ending with "Would you like to..." triggers retry
- [ ] Test case 2: Response ending with "What would you like to do?" triggers retry
- [ ] Test case 3: Natural narrative endings pass validation

## Related Issues

- Character break detection is working for other patterns
- This is a gap in the pattern coverage

## References

- `src/gm/gm_node.py:_CHARACTER_BREAK_PATTERNS` - Detection patterns
- `src/gm/prompts.py` - System prompt
- `logs/llm/session_302/turn_003_20251229_160531_gm.md` - Audit log with issue
