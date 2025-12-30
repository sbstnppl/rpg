# LLM Repeats Previous Turn on Grounding Retry

**Status:** Investigating
**Priority:** High
**Detected:** 2025-12-30
**Related Sessions:** Session 304

## Problem Statement

When the GM pipeline detects a grounding error (entity mentioned without `[key:text]` format) and retries, the LLM outputs narrative from a previous turn instead of narrating the current action. This causes the player to see stale responses that don't match their input.

## Current Behavior

1. Player says: "I would like to order a drink, an ale please"
2. LLM correctly calls `satisfy_need(need="thirst", amount=25, activity="drinking ale")`
3. LLM outputs narrative with grounding error: `"Old Tom nods..."` (missing `[key:text]`)
4. Grounding validator catches the error and sends retry prompt:
   ```
   GROUNDING ERROR - Please fix your narrative and respond again.
   ...
   REMINDER: You already processed the player's action. Narrate what happened based on these tool results:
   - satisfy_need: Satisfied thirst: 80 -> 100
   Write ONLY the corrected narrative text - do NOT call any tools.
   ```
5. LLM responds with the **greeting from turn 2** instead of the ale drinking narrative:
   ```
   "[innkeeper_tom:Old Tom] nods at you from behind the bar. 'Evenin',' he says..."
   ```

## Expected Behavior

On grounding retry, the LLM should output the corrected narrative for the CURRENT action:
```
[innkeeper_tom:Old Tom] reaches under the bar and produces a frothy mug of ale. You take a long drink, the cool amber liquid quenching your thirst.
```

## Investigation Notes

From logs at `logs/llm/session_304/turn_003_20251230_064803_gm.md`:

The conversation history in the retry includes:
- Turn 1: look around
- Turn 2: say hello (greeting response)
- Turn 3: order drink (with tool call result)

The LLM appears to be confusing the retry instruction and just fixing the grounding format on the most recent NPC dialogue it sees in context, rather than generating new narrative for the current action.

## Root Cause

Likely causes:
1. The retry prompt doesn't clearly separate "fix THIS narrative" from conversation history
2. The LLM is pattern-matching on "Old Tom" in context and outputting a corrected version of what it sees
3. Context may be including previous assistant messages that confuse the retry

## Proposed Solution

Options:
1. Make the retry prompt more explicit about which text to fix
2. Include the ORIGINAL (errored) narrative in the retry prompt so LLM knows what to fix
3. Clear or truncate conversation history for retry attempts
4. Use a separate prompt for narrative-only regeneration

## Files to Modify

- [ ] `src/gm/gm_node.py` - Grounding retry logic
- [ ] `src/gm/grounding_validator.py` - Error message formatting
- [ ] `src/gm/prompts.py` - Retry prompt template

## Test Cases

- [ ] Order drink with NPC interaction - should get drinking narrative, not greeting
- [ ] Multiple grounding retries in sequence should maintain correct turn context
- [ ] Tool results should be referenced in retry narrative

## Related Issues

- Grounding validation system in general

## References

- `logs/llm/session_304/turn_003_20251230_064803_gm.md` - Failed turn log
- `src/gm/gm_node.py` - Retry logic implementation
