# Narrator Key Format Issue

**Status:** Resolved
**Priority:** High
**Detected:** 2024-12-21
**Resolved:** 2026-01-18
**Related Sessions:** Session 77 gameplay testing

## Problem Statement

The constrained narrator is not using the required `[entity_key]` format when referencing entities in the scene. Instead of outputting `[wooden_bucket_001]`, it outputs "Wooden Bucket", which breaks entity tracking and the key-stripping display pipeline.

## Current Behavior

Narrator output:
```
The morning sun casts a golden light over the area, illuminating the
Wooden Bucket washing area and the farmhouse in a warm glow. The Well
is at the center of the scene, with a Rope attached to it.
```

Validation errors (repeated 3 times before fallback):
```
Narration validation failed (attempt 1): [
  "'Wooden Bucket' mentioned without [key] format. Use [wooden_bucket_001].",
  "'Well' mentioned without [key] format. Use [well_001].",
  "'Stone' mentioned without [key] format. Use [stone_001].",
  "'Rope' mentioned without [key] format. Use [rope_001].",
  "'Bucket' mentioned without [key] format. Use [bucket_001].",
  "'Water' mentioned without [key] format. Use [water_001]."
]
```

The narrator retries 3 times, fails validation each time, then shows the non-compliant output as a fallback.

## Expected Behavior

Narrator output should use `[key]` format:
```
The morning sun casts a golden light over the area, illuminating
[wooden_bucket_001] and the farmhouse in a warm glow. [well_001]
is at the center of the scene, with [rope_001] attached to it.
```

The display layer then strips keys for the player:
```
The morning sun casts a golden light over the area, illuminating
the wooden bucket and the farmhouse in a warm glow. The well
is at the center of the scene, with a rope attached to it.
```

## Investigation Notes

### Scene-First Architecture Flow

1. `scene_builder` generates scene manifest with entity keys
2. `persist_scene` builds `NarratorManifest` with available entities
3. `constrained_narrator` receives manifest and should ONLY use those keys
4. `validate_narrator` checks all entity mentions use `[key]` format
5. Display layer strips keys: `[well_001]` → "the well"

### Potential Causes

1. **Prompt issue** - The narrator prompt may not strongly enforce key format
2. **Manifest not passed correctly** - Narrator may not see available keys
3. **LLM ignoring instructions** - Model prefers natural language over keys
4. **Retry not working** - Validation feedback not reaching retry attempts

### Key Files

- `src/agents/nodes/constrained_narrator_node.py` - Narrator node
- `src/narrator/scene_narrator.py` - SceneNarrator class
- `src/world/schemas.py` - NarratorManifest schema
- `data/templates/` - Narrator prompts (if any)

## Root Cause

1. **Temperature too high**: `NarratorEngine` used 0.7, while working `SceneNarrator` uses 0.4
2. **No retry loop**: Single LLM call with no validation or retry mechanism
3. **Warnings not errors**: Unkeyed mentions detected but not enforced
4. **No enforcement**: Validation detected issues but didn't block invalid output

## Solution Implemented

Added validation-based retry loop to `NarratorEngine` (mirroring the working `SceneNarrator` pattern):

1. **Generate narrative** via LLM
2. **Validate output** using `GroundingValidator`
3. **On failure, retry** with error feedback (max 3 attempts)
4. **Fall back** to safe narration if all retries fail

### Key Changes

1. **Lowered temperature** from 0.7 to 0.5 for better format compliance
2. **Added `_build_validation_manifest()`** to create manifest from `NarrationContext`
3. **Added `_validate_narrative()`** to check for invalid keys and unkeyed mentions
4. **Rewrote `narrate()`** with retry loop and validation
5. **Updated `_build_prompt()`** to include error feedback on retry

## Files Modified

- [x] `src/world_server/quantum/narrator.py` - Added retry loop, validation, lower temperature
- [x] `tests/test_world_server/test_quantum/test_narrator.py` - Added 9 new tests

## Test Cases

- [x] `test_retry_on_unkeyed_mention` - Verify retry triggered on format violation
- [x] `test_fallback_after_max_retries` - Verify fallback after 3 failures
- [x] `test_error_feedback_in_retry_prompt` - Verify errors included in retry
- [x] `test_valid_narrative_returns_without_retry` - No retry for valid output
- [x] `test_strict_grounding_disabled_skips_validation` - Skip when disabled
- [x] `test_build_prompt_includes_previous_errors` - Errors in prompt
- [x] `test_build_validation_manifest` - Correct manifest creation
- [x] `test_validate_narrative_valid` - Properly formatted text passes
- [x] `test_validate_narrative_unkeyed_mention` - Unkeyed mentions detected

## Related Issues

- `docs/scene-first-architecture/troubleshooting.md` - May have related notes
- Entity reference resolution in `resolve_references_node.py`

## References

- Scene-first architecture: `docs/scene-first-architecture/`
- NarratorManifest schema: `src/world/schemas.py`
- Narrator implementation: `src/narrator/scene_narrator.py`
