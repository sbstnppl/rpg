# GM Hallucinates Inconsistent Narrative Details

**Status:** ✅ RESOLVED
**Priority:** Medium
**Detected:** 2025-12-28
**Resolved:** 2025-12-29
**Related Sessions:** 301

## Resolution

Fixed in Phase 7 of the Quantum Branching implementation with the validation layer in `src/world_server/quantum/validation.py`.

The following validators were implemented:
1. **NarrativeConsistencyValidator** (`src/world_server/quantum/validation.py:98-186`)
   - Checks NPC references match manifest (key, gender, name)
   - Detects fabricated events not in turn history
   - Flags meta-questions at end of narrative
   - Validates all entity references use proper [key:text] format
   - Detects AI identity breaks and third-person narration
   - Catches placeholder text

2. **DeltaValidator** (`src/world_server/quantum/validation.py:189-258`)
   - Validates state delta consistency
   - Ensures referenced entities exist
   - Checks operation validity

3. **BranchValidator** (`src/world_server/quantum/validation.py:261-327`)
   - Validates entire branches before caching
   - Ensures required variants exist
   - Coordinates narrative and delta validation

53 unit tests cover the validation layer in `tests/test_world_server/test_quantum/test_validation.py`.

## Problem Statement

The GM generates narrative that contradicts established facts from the game state. This includes inventing NPCs with wrong characteristics (gender, appearance), referencing events that never occurred, and fabricating details not grounded in the scene context.

## Current Behavior

Turn 9 - Player input: "I sit down at a table"

GM response included:
1. **Wrong NPC**: "The innkeeper, a broad-shouldered woman with a perpetual frown"
   - Actual innkeeper is "Old Tom" (male), established in prior turns
2. **Fabricated event**: "the fullness of your recent meal still lingered"
   - Player never ate a meal in this session
3. **Meta-question**: "Would you lean into the comfort of the moment, or let the tavern's quiet hum draw you into its stories?"
   - GM shouldn't ask meta-questions; should end at natural pause for player input

## Expected Behavior

1. NPC descriptions must match the established character (Old Tom, male innkeeper)
2. Only reference events that actually occurred in the session
3. End narrative at natural pause, not with questions directing player choices
4. All entities should use `[key:text]` grounding format

## Investigation Notes

The response came after a crash (Turn 8), which may have affected context continuity.

However, the system prompt includes:
- "NPCs at location: innkeeper_tom: Old Tom (Innkeeper)"
- Prior conversation history shows "Old Tom" mentioned correctly

Possible causes:
1. Context truncation after crash lost NPC info
2. LLM (qwen3) hallucinating despite context
3. Grounding system didn't catch the inconsistency because "innkeeper" alone isn't a keyed entity

## Root Cause

<After investigation>

## Proposed Solution

1. **Stricter grounding**: Require all NPC mentions to use `[key:text]` format
2. **Context validation**: Ensure NPC descriptions match database records
3. **No fabricated events**: Add validation layer to detect references to non-existent events
4. **No meta-questions**: Add pattern detection for questions at end of GM response

## Implementation Details

<After investigation>

## Files to Modify

- [ ] `src/gm/grounding_validator.py` - Stricter NPC validation
- [ ] `src/gm/prompts.py` - Reinforce consistency rules
- [ ] `src/gm/gm_node.py` - Add meta-question detection

## Test Cases

- [ ] Test case 1: GM mentions NPC by different name - validation fails
- [ ] Test case 2: GM references event not in turn history - validation warns
- [ ] Test case 3: GM response ending in question triggers warning

## Related Issues

- Grounding validation system
- Character break detection

## References

- Turn 9 response from session 301
- `src/gm/grounding_validator.py` - Current validation
- `src/gm/context_builder.py` - How NPC context is provided
