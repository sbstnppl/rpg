# Narrative Response Degraded to Meta Confirmation Format

**Status:** Done
**Priority:** High
**Detected:** 2026-01-03
**Fixed:** 2026-01-03
**Related Sessions:** 337

## Problem Statement

When asking NPCs in-world questions, the game sometimes responds with a meta-style confirmation format ("Yes, Old Tom is here. They appear to be Innkeeper.") instead of generating proper narrative prose. This breaks immersion and indicates the quantum pipeline is falling back to a debug/verification response mode.

## Current Behavior (BEFORE FIX)

Player input: `ask Old Tom if he has any work for me`

Actual output:
```
Yes, Old Tom is here. They appear to be Innkeeper.
```

This is a meta/OOC response that:
- Confirms entity existence rather than narrating interaction
- Uses third-person clinical language ("They appear to be")
- Doesn't address the player's actual question about work

## Expected Behavior

The response should be immersive narrative prose like:
```
Old Tom scratches his chin thoughtfully. 'Work, you say? Well, the cellar
could use a good clearing out. Rats have been getting bolder lately.
Five coppers if you can deal with 'em.'
```

## Root Cause

The `IntentClassifier` (Phase 1 of quantum pipeline) was misclassifying NPC dialog requests as **QUESTION** intent instead of **ACTION** intent.

**Why**: The system prompt examples didn't distinguish between:
- "Could I talk to Tom?" → genuinely asking about possibility (QUESTION)
- "ask Tom if he has work" → imperative speech act to perform (ACTION)

The word "if" in "ask X if Y" triggered QUESTION classification because the LLM saw "if" as conditional.

**Code flow**:
```
process_turn()
  → _classify_intent() → LLM returns QUESTION (incorrect!)
  → _handle_informational_intent()
  → _generate_informational_response() line 647:
    return f"Yes, {npc.display_name} is here. They appear to be {desc}."
```

## Solution

Updated `INTENT_CLASSIFIER_SYSTEM_PROMPT` in `src/world_server/quantum/intent_classifier.py` to:

1. Add explicit examples of speech acts that look like questions but are actions
2. Add a "CRITICAL: Speech Acts vs Meta Questions" section clarifying that dialog IS action
3. Add negative examples showing the distinction

### Key Prompt Changes

Added to ACTION examples:
```
- "ask Tom about the robbery" → action (SPEECH ACT - performing dialog)
- "ask Tom if he has work" → action (SPEECH ACT - asking a question IN-WORLD)
- "tell the guard my name" → action (SPEECH ACT)
- "greet the innkeeper" → action (SPEECH ACT)
```

Added new section:
```
## CRITICAL: Speech Acts vs Meta Questions

**Speech acts** (always ACTION): Player performs dialog IN the game world
- "ask X about Y" → ACTION (player speaks to X)
- "ask X if Y" → ACTION (player asks X a question in-game)

**Meta questions** (QUESTION): Player asks about game possibilities
- "Could I talk to X?" → QUESTION (asking IF they can)
- "Is X here?" → QUESTION (asking for information)

The key difference:
- Speech acts use imperative verbs directing action ("ask", "tell", "greet", "say")
- Meta questions use modal verbs asking possibility ("could", "can", "would", "should")
```

## Files Modified

- [x] `src/world_server/quantum/intent_classifier.py` - Updated system prompt
- [x] `tests/test_world_server/test_quantum/test_intent_classifier.py` - Added 10 new tests

## Test Cases

- [x] "ask NPC about X" should be classified as ACTION
- [x] "ask NPC if Y" should be classified as ACTION (not QUESTION)
- [x] "tell X that Y" should be classified as ACTION
- [x] "greet X" should be classified as ACTION
- [x] "Could I talk to X?" should still be classified as QUESTION
- [x] "Can I pick that up?" should still be classified as QUESTION

## Verification

Manual testing confirmed:

**Before fix** (session 337, turn 4):
```
> ask Old Tom if he has any work for me
Yes, Old Tom is here. They appear to be Innkeeper.
```

**After fix** (session 337, turn 5):
```
> ask Old Tom if he has any work for me
You approach Old Tom, who is wiping down the bar... 'Work? Aye, lad — the cellar's
full of kegs that need hauling to the back storage...'
```

**Meta questions still work correctly**:
```
> could I talk to Old Tom?
Yes, Old Tom is here. They appear to be Innkeeper.
```

## Related Issues

- Turn 3 showed "You don't see 'tables' here" despite narrative mentioning tables (separate grounding issue)

## References

- Session 337, turns 3-5
- `docs/quantum-branching/README.md`
- `src/world_server/quantum/intent_classifier.py:71-155`
