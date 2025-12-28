# Error Message Leaked Into Narrative

**Status:** Done
**Priority:** High
**Detected:** 2025-12-28
**Related Sessions:** 298

## Problem Statement

Internal error messages are being displayed to the player as part of the narrative output. When the GM attempts to interact with an entity that doesn't exist in the database, the error message "**FAILED talk : 'Baker' is not here.**" appears within the story text, breaking immersion.

## Current Behavior

Player input: "approach the baker and say hello"

GM Response includes:
> **FAILED talk : 'Baker' is not here.** The bakery appears empty at the moment...

The error message is embedded directly in the narrative text that the player sees.

## Expected Behavior

Error messages should be handled internally:
1. If an entity doesn't exist, the GM should either:
   - Create it using `create_entity` tool
   - Narrate that no one is there (without exposing internal error text)
2. Error messages should never appear in player-facing narrative

## Investigation Notes

- Session 298, Turn 4
- The GM described a baker in previous turns but never created the NPC entity
- When player tried to interact, grounding validation failed
- Error text leaked into the narrative display

## Root Cause

The error is **intentionally passed as a "mechanical fact"** that the narrator must include:

1. **Action Validation** (`src/validators/action_validator.py:717+`): When validating an action like `talk`, if the target entity doesn't exist, a `ValidationResult` is created with `reason=f"'{action.target}' is not here."`

2. **Subturn Processor** (`src/agents/nodes/subturn_processor_node.py:444-452`): Failed validations are collected into `failed_actions[]` with the reason.

3. **Narrator Node** (`src/agents/nodes/narrator_node.py:172-195`): The `_build_chained_turn_result()` function passes these to the narrator.

4. **ConstrainedNarrator** (`src/narrator/narrator.py:188-195`): The `_extract_facts()` method explicitly converts failed_actions to facts:
   ```python
   facts.append(f"FAILED {action_type} {target}: {reason}")
   ```

5. **Narrator Prompt** (`src/narrator/narrator.py:27-31`): The template states "you MUST include ALL of these" mechanical facts.

6. **Fallback Narration** (`src/narrator/narrator.py:229-231`): Even formats it as "However, {fact.lower()}" if no LLM is available.

**The issue is that the system was designed to include failed action messages as facts for the narrator to weave into prose, but the format "FAILED talk : 'Baker' is not here" is too technical/mechanical.**

This affects the **scene-first pipeline** (`src/agents/nodes/`), NOT the simplified GM pipeline (`src/gm/gm_node.py`).

## Proposed Solution

**Option A: Convert technical messages to narrative-friendly facts** (Recommended)
- In `_extract_facts()`, instead of `"FAILED talk Baker: 'Baker' is not here."`, generate:
  `"You look around but don't see anyone who might be a baker here."`
- Pros: Maintains constrained narration, immersive
- Cons: Requires mapping each action type to a narrative template

**Option B: Filter FAILED facts from narrator input**
- Don't pass FAILED facts to the narrator at all
- Generate a generic "couldn't do that" narrative separately
- Pros: Simple
- Cons: Loses detail, narrator can't weave it in

**Option C: Post-process narrative to strip FAILED patterns**
- Regex filter in narrator output to remove "FAILED ..." patterns
- Pros: Quick fix
- Cons: Hacky, may leave awkward narrative gaps

**Chosen approach: Option A** - Convert to narrative-friendly format in `_extract_facts()`

## Files to Modify

- [x] `src/gm/gm_node.py` - NOT involved (different pipeline)
- [x] `src/gm/applier.py` - NOT involved (different pipeline)
- [x] `src/gm/validator.py` - NOT involved (different pipeline)
- [x] `src/narrator/narrator.py:188-195` - **Primary fix location**: Transform FAILED facts to narrative-friendly format

## Test Cases

- [x] Test that FAILED messages are never in final narrative
- [x] Test that grounding errors are handled gracefully (converted to narrative)
- [ ] Test that error recovery creates missing entities (out of scope - separate issue)

## Related Issues

- Grounding validation system
- NPC creation during scene narration

## References

- `docs/gm-pipeline-e2e-testing.md` - Grounding system docs
- `src/gm/grounding_validator.py` - Grounding validation
