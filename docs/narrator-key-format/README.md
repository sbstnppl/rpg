# Narrator Key Format Issue

**Status:** Investigating
**Priority:** High
**Detected:** 2024-12-21
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

<To be determined after investigation>

## Proposed Solution

<After investigation>

Options to consider:
1. Strengthen prompt with explicit examples
2. Add key format to system prompt
3. Provide manifest keys more prominently in context
4. Use structured output instead of free-form text
5. Post-process to convert names to keys

## Implementation Details

<Specific code changes>

## Files to Modify

- [ ] `src/narrator/scene_narrator.py` - Main narrator logic
- [ ] `src/agents/nodes/constrained_narrator_node.py` - Node wrapper
- [ ] Narrator prompt templates

## Test Cases

- [ ] Narrator uses `[key]` format for all scene entities
- [ ] Validation passes on first attempt (no retries needed)
- [ ] Display correctly strips keys to natural language
- [ ] Edge case: Entity mentioned multiple times uses same key
- [ ] Edge case: Pronouns don't need keys ("he", "she", "it")

## Related Issues

- `docs/scene-first-architecture/troubleshooting.md` - May have related notes
- Entity reference resolution in `resolve_references_node.py`

## References

- Scene-first architecture: `docs/scene-first-architecture/`
- NarratorManifest schema: `src/world/schemas.py`
- Narrator implementation: `src/narrator/scene_narrator.py`
