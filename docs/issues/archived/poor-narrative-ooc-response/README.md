# Poor Narrative Response - OOC-Style Answer Instead of Roleplay

**Status:** Resolved
**Priority:** High
**Detected:** 2026-01-02
**Resolved:** 2026-01-18
**Related Sessions:** Session 334, Turn 3

## Problem Statement

When asked "ask Old Tom if I can buy some bread", the quantum pipeline returned a meta/OOC-style response: "Yes, Old Tom is here. They appear to be Innkeeper." instead of narrating the actual roleplay interaction. This breaks immersion and is not proper second-person narrative.

## Current Behavior

Player input: `ask Old Tom if I can buy some bread`

Response:
```
Yes, Old Tom is here. They appear to be Innkeeper.
```

This is an out-of-character, meta response that:
- Doesn't narrate the player approaching and speaking
- Doesn't have Old Tom respond in character
- Uses "they appear to be" which is system/inspection language
- Is far too short for an NPC interaction (~50 chars when it should be 100+)

## Expected Behavior

A proper second-person narrative like:
```
You approach Old Tom at the bar and ask about buying some bread. The
weathered innkeeper pauses his polishing and nods. "Aye, fresh loaves
from this morning. Two coppers for a small loaf, five for a large one."
He gestures toward a basket near the kitchen doorway where several
crusty loaves are wrapped in cloth.
```

## Root Cause

**Intent Classifier Confusion with Nested Modals**

The failing input `"ask Old Tom if I can buy some bread"` contains:
1. `"ask X if Y"` pattern (should be ACTION per classifier rules)
2. Nested `"can I buy"` which matches the QUESTION pattern

The LLM saw both patterns and got confused because:
- Prompt rule: `"ask X if Y"` → ACTION
- Prompt rule: `"Can I pick that up?"` → QUESTION

The **nested "can I" inside the speech act** caused misclassification as QUESTION, which triggered `_generate_informational_response()` in `pipeline.py:690` and produced the OOC response.

## Solution

Strengthened the intent classifier prompt with explicit edge case examples:

1. Added examples showing nested modals are still speech acts:
   - `"ask X if I can Y"` → ACTION
   - `"ask X if I could Y"` → ACTION

2. Added clarifying rule: "When 'ask' comes BEFORE a target name (NPC), it's ALWAYS a speech act. The words inside the question don't matter."

3. Emphasized the key distinction:
   - Speech acts have a TARGET NPC after the verb
   - Meta questions have NO target - player asks the game itself

## Files Modified

- [x] `src/world_server/quantum/intent_classifier.py` - Enhanced CRITICAL section with nested modal examples
- [x] `tests/test_world_server/test_quantum/test_intent_classifier.py` - Added regression test

## Test Cases

- [x] `test_ask_npc_if_can_buy_is_action` - "ask Old Tom if I can buy some bread" → ACTION
- [x] `test_ask_guard_if_can_enter_is_action` - "ask the guard if I can enter" → ACTION (existing)

## Verification

All 53 intent classifier tests pass.

## Related Issues

- None
