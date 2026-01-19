# LLM Leaks Meta-Commentary About Tool Calls Into Narrative

**Status:** Resolved
**Priority:** High
**Detected:** 2025-12-30
**Resolved:** 2026-01-18
**Related Sessions:** Session 304

## Problem Statement

The LLM (qwen3:32b) occasionally breaks character by including meta-commentary about tool usage in the narrative output. Instead of just narrating the story, it mentions things like "You then call the take_item tool" which breaks immersion and exposes game mechanics to the player.

## Current Behavior

Player input: "I go to the basket and take a loaf of bread"

LLM output:
```
You make your way to the basket and reach in, selecting a warm, crusty loaf of bread.
As you lift it from the basket, the bread feels solid and fresh in your hand.
You then call the take_item tool to add the loaf to your inventory.
```

The phrase "You then call the take_item tool to add the loaf to your inventory" is meta-commentary that should never appear in narrative.

## Expected Behavior

The narrative should be pure prose without any mention of game mechanics:
```
You make your way to the basket and reach in, selecting a warm, crusty loaf of bread.
As you lift it from the basket, the bread feels solid and fresh in your hand.
You slip the loaf into your pack.
```

Additionally, the `take_item` tool should actually be called to update game state.

## Investigation Notes

The system prompt explicitly forbids this:
```
ABSOLUTE RULES - VIOLATIONS WILL FAIL VALIDATION:
...
8. NEVER announce tool usage - don't say "Let me check...", "I'll get...", or similar. Just call tools silently.
```

And:
```
7. No explanations, no meta-commentary, no apologies, no bullet points - JUST STORY
```

Despite these instructions, qwen3:32b still occasionally leaks meta-commentary.

## Root Cause

1. **System prompt rules are aspirational, not enforced** - Lines 21-22 of `prompts.py` forbid meta-commentary but there was no validation
2. **`NarrativeConsistencyValidator._check_quality()` didn't check for tool names** - It only checked capitalization, punctuation, and whitespace
3. **No pattern matching for tool-call leakage** - The validator had patterns for meta-questions, AI identity, third-person, but NOT tool mentions

## Solution

Added tool-call meta-commentary detection to `NarrativeConsistencyValidator` in `validation.py`.

### Implementation Details

1. **Added `TOOL_CALL_PATTERNS` and `TOOL_CALL_RE` constants** (validation.py ~line 165)
   - Direct tool name mentions: `take_item`, `drop_item`, `transfer_item`, etc.
   - Tool usage announcements: "call the X tool", "use the X tool"
   - Process announcements: "let me check", "I'll update"
   - System references: "the system updates", "inventory is now updated"

2. **Added `_check_tool_commentary()` method** (validation.py ~line 447)
   - Scans narrative for TOOL_CALL_RE patterns
   - Returns ERROR severity issue (triggers retry in pipeline)

3. **Integrated into `validate()` method** (validation.py line 248)
   - Called as step 10 after quality checks

## Files Modified

- [x] `src/world_server/quantum/validation.py` - Added patterns and detection method
- [x] `tests/test_world_server/test_quantum/test_validation.py` - Added `TestToolCommentaryDetection` class

## Test Cases

- [x] `test_detects_tool_name_mention` - Detects "take_item tool" in narrative
- [x] `test_detects_tool_usage_announcement` - Detects "Let me update your inventory"
- [x] `test_detects_you_then_call_pattern` - Detects "You then use the pickup function"
- [x] `test_detects_system_reference` - Detects "The system updates your inventory"
- [x] `test_detects_inventory_updated` - Detects "inventory is now updated"
- [x] `test_detects_transfer_item_tool` - Detects "transfer_item" tool name
- [x] `test_clean_narrative_passes` - Clean narrative without tool commentary passes
- [x] `test_natural_word_use_not_flagged` - Common words like "use" in natural context not flagged

## Related Issues

- `docs/issues/llm-skips-mandatory-tool-calls/` - Related tool calling issue
- `docs/issues/grounding-retry-repeats-previous-turn/` - Related retry handling

## References

- `logs/llm/session_304/` - Session logs with meta-commentary
- `src/gm/prompts.py` - System prompt with anti-meta-commentary rules
