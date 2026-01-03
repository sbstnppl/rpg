# Poor Narrative Response - OOC-Style Answer Instead of Roleplay

**Status:** Investigating
**Priority:** High
**Detected:** 2026-01-02
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

## Investigation Notes

- This occurred on Turn 3 of Session 334
- Previous turns (look around, say hello) worked correctly
- Need to check: Was this a quantum branch cache hit or miss?
- Need to check: What did the narrator/reasoning phases produce?

## Root Cause

(To be determined)

Possible causes:
1. Quantum branch matched wrong action type
2. Narrator prompt issue
3. Entity resolution/grounding problem
4. Missing context about the NPC's role/dialogue capabilities

## Proposed Solution

(After investigation)

## Implementation Details

(After root cause identified)

## Files to Modify

- [ ] `src/world_server/quantum/` - if branch matching issue
- [ ] `src/gm/prompts.py` - if narrator prompt issue
- [ ] `src/gm/context_builder.py` - if context issue

## Test Cases

- [ ] "ask [NPC] about X" should produce roleplay narrative
- [ ] "buy X from [NPC]" should produce roleplay narrative
- [ ] Short OOC-style responses should trigger retry/validation

## Related Issues

- None identified yet

## References

- Session 334, Turn 3
- docs/gm-pipeline-e2e-testing.md - expected narrative quality
