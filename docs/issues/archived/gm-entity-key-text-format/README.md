# GM Entity Key-Text Format Bug

**Status:** Done
**Priority:** Medium
**Detected:** 2025-12-27
**Related Sessions:** Session 292 (GM pipeline testing)

## Problem Statement

The GM pipeline's LLM (qwen3:32b via Ollama) sometimes uses `[key]` format instead of the required `[key:text]` format when referencing entities. After the grounding validator strips the key brackets, this results in empty display text in the narrative.

## Current Behavior

When the player eats bread, the LLM outputs:
```
You take a bite of [fresh_bread], savoring its soft texture...
```

After key stripping, the player sees:
```
You take a bite of , savoring its soft texture...
```

The entity reference is completely missing from the displayed text.

## Expected Behavior

LLM should output:
```
You take a bite of [fresh_bread:the fresh bread], savoring its soft texture...
```

After key stripping, the player sees:
```
You take a bite of the fresh bread, savoring its soft texture...
```

## Investigation Notes

- Observed during GM pipeline E2E testing (session 292, turn 6)
- The system prompt clearly instructs `[key:text]` format in multiple places
- qwen3:32b sometimes follows the format correctly (e.g., `[marcus_baker:Marcus]`)
- Failure seems more common with items than NPCs
- LLM log: `logs/llm/orphan/20251227_184122_unknown.md`

## Root Cause

Model (qwen3:32b) doesn't consistently follow the `[key:text]` format instruction. This may be:
1. Insufficient emphasis in prompt
2. Model-specific behavior (smaller models may need more explicit instructions)
3. Context length causing instruction to be "forgotten"

## Proposed Solution

**Short-term bandaid (recommended):**
Enhance grounding validator to detect `[key]` without `:text` and fill in the display name from the GroundingManifest.

**Long-term improvements:**
1. Prompt engineering: Add more examples, place format instruction closer to output
2. Add format validation in tool loop that catches `[key]` and requests correction
3. Consider model-specific prompt variants

## Implementation Details

### Bandaid Fix

In `src/gm/grounding_validator.py`, add logic to:
1. Detect pattern `\[(\w+)\]` (key without colon)
2. Look up key in manifest
3. Replace with `[key:display_name]` format before stripping

```python
import re

def _fix_key_only_format(text: str, manifest: GroundingManifest) -> str:
    """Replace [key] with [key:display_name] using manifest lookup."""
    def replace_key(match):
        key = match.group(1)
        # Look up in manifest (NPCs, items, inventory, etc.)
        entity = manifest.get_entity(key)
        if entity:
            return f"[{key}:{entity.display_name}]"
        return match.group(0)  # Keep original if not found

    return re.sub(r'\[(\w+)\](?!:)', replace_key, text)
```

## Files Modified

- [x] `src/gm/grounding_validator.py` - Added `fix_key_only_format()` and `KEY_ONLY_PATTERN`
- [x] `src/gm/grounding.py` - `get_entity()` helper already existed
- [x] `tests/test_gm/test_grounding.py` - Added 16 new test cases

## Test Cases

- [x] Test case 1: `[fresh_bread]` → `[fresh_bread:Fresh Bread]`
- [x] Test case 2: `[marcus_baker]` → `[marcus_baker:Marcus]`
- [x] Test case 3: `[unknown_key]` → `[unknown_key]` (unchanged, no match)
- [x] Test case 4: `[key:text]` → `[key:text]` (unchanged, already correct)
- [x] Test case 5: Mixed format in same sentence

## Related Issues

- None currently

## References

- `src/gm/grounding_validator.py` - Current grounding validation
- `src/gm/grounding.py` - GroundingManifest schema
- `src/gm/prompts.py` - System prompt with format instructions
- `docs/gm-pipeline-e2e-testing.md` - E2E testing guide
