# LLM Leaks Meta-Commentary About Tool Calls Into Narrative

**Status:** Investigating
**Priority:** High
**Detected:** 2025-12-30
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

Possible causes:
1. Model training bias toward explaining tool usage
2. Confusion between calling a tool vs describing calling a tool
3. System prompt length causing instruction degradation
4. Model not properly distinguishing between narrative and tool calls

## Proposed Solution

Options:
1. Add post-processing filter to detect and remove/reject meta-commentary
2. Add this pattern to character break detection (`_validate_character`)
3. Use stricter prompt formatting or few-shot examples
4. Retry with correction when meta-commentary detected

## Files to Modify

- [ ] `src/gm/gm_node.py` - Add meta-commentary detection to character validation
- [ ] `src/gm/prompts.py` - Strengthen instructions against meta-commentary

## Test Cases

- [ ] "Take the sword" should not mention take_item tool in narrative
- [ ] "Check my inventory" should not mention get_player_state tool
- [ ] Any tool call should be invisible to player

## Related Issues

- `docs/issues/llm-skips-mandatory-tool-calls/` - Related tool calling issue
- `docs/issues/grounding-retry-repeats-previous-turn/` - Related retry handling

## References

- `logs/llm/session_304/` - Session logs with meta-commentary
- `src/gm/prompts.py` - System prompt with anti-meta-commentary rules
