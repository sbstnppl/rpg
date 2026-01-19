# Tool Output Leaked to Player

**Status:** Done
**Priority:** High
**Detected:** 2025-12-27
**Related Sessions:** Session 293, Turn 12
**Completed:** 2025-12-27

## Problem Statement

When the LLM calls internal context tools like `get_rules()`, it sometimes exposes the raw tool output directly to the player instead of using it as internal guidance. This breaks immersion completely and reveals game mechanics to the player.

## Current Behavior

Player input: "I approach the hooded traveler and try to strike up a conversation"

LLM called `get_rules(category='npc_dialogue')` and then responded:
> "The provided text outlines rules for handling NPC dialogue in a game system, emphasizing structured narration and data tracking. Since no specific question or task is attached to this instruction, I'll ask for clarification to ensure I address your intended need.
>
> What would you like me to do with these rules?"

The character validation system (which checks for AI-assistant patterns) did NOT catch this.

## Expected Behavior

The LLM should:
1. Use the `get_rules` response as internal guidance
2. Actually perform the action (approach hooded traveler, call `get_npc_attitude`, narrate conversation)
3. Never expose tool responses or ask meta-questions like "What would you like me to do?"

## Investigation Notes

From LLM log `logs/llm/session_293/turn_012_*.md`:
- LLM correctly identified it needed NPC dialogue rules
- Tool returned full rules content with examples
- Instead of using rules, LLM treated it as external documentation to explain
- Character validation patterns didn't include: "What would you like", "The provided text", "rules for handling"

## Root Cause

1. **qwen3:32b model behavior**: Doesn't fully understand that tool responses are internal context, not content to relay to users
2. **Missing validation patterns**: Character break detection lacks patterns for meta-questions and tool content exposure

## Proposed Solution

1. Add character break patterns in `src/gm/gm_node.py` and `src/gm/context_builder.py`:
   - `r"\bwhat would you like\b"`
   - `r"\bthe provided text\b"`
   - `r"\brules for handling\b"`
   - `r"\blet me know if\b"`
   - `r"\bwhat .+ do with\b"`

2. Consider if `get_rules` tool should exist at all, or if rules should be embedded in system prompt

3. Add post-processing to detect when raw tool JSON/content patterns appear in output

## Implementation Details

Character break patterns in `GMNode._CHARACTER_BREAK_PATTERNS` and `GMContextBuilder._CHARACTER_BREAK_PATTERNS`:

```python
# Meta-questions (tool response exposure)
r"\bwhat would you like\b",
r"\bthe provided text\b",
r"\brules for (?:handling|managing|processing)\b",
r"\blet me know if\b",
r"\bwhat .+ do with (?:this|these)\b",
r"\bwould you like me to\b",
r"\bfor example:\s*$",  # Ends with "For example:" offering options
```

## Files to Modify

- [x] `src/gm/gm_node.py` - Add patterns to `_CHARACTER_BREAK_PATTERNS`
- [x] `src/gm/context_builder.py` - Add patterns to `_CHARACTER_BREAK_PATTERNS`
- [x] `tests/test_gm/test_character_validation.py` - Add test for tool output leak detection

## Test Cases

- [x] Test: LLM response containing "What would you like me to do" triggers character validation retry
- [x] Test: LLM response containing "The provided text" triggers retry
- [x] Test: LLM response containing "rules for handling" triggers retry
- [x] Test: LLM response containing "let me know if" triggers retry
- [x] Test: LLM response containing "would you like me to" triggers retry

## Related Issues

- Related to grounding validation (different validation layer)
- Could also add to prompt: "NEVER expose tool responses to the player"

## References

- `src/gm/gm_node.py:52-85` - Existing character break patterns
- `src/gm/context_builder.py:39-73` - Duplicate patterns
- `logs/llm/session_293/turn_012_*.md` - Full reproduction logs
