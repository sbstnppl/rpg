# GM Hallucinates Entity Keys

**Status:** Done
**Priority:** High
**Detected:** 2025-12-28
**Resolved:** 2025-12-28
**Related Sessions:** 297

## Problem Statement

The GM LLM hallucinates entity keys instead of using the exact keys provided in the system prompt context. When calling tools like `get_npc_attitude`, the model invents plausible-looking keys (e.g., `farmer_001`) instead of copying the actual keys from context (e.g., `farmer_marcus`). This causes tool calls to fail with "Entity not found" errors.

## Current Behavior

### Example 1: NPC Key Hallucination

System prompt includes:
```
**NPCs at location:**
- farmer_marcus: Marcus
```

GM calls:
```python
get_npc_attitude(from_entity='farmer_001', to_entity='player')
```

Tool returns:
```json
{"error": "Entity 'farmer_001' not found"}
```

The model then loops back to call `get_scene_details` again instead of correcting the key.

### Example 2: Item Key Hallucination

System prompt includes:
```
**Items at location:**
- bread_001: Bread
```

GM calls:
```python
take_item(item_key='bread')
```

Tool returns:
```json
{"error": "Item not found: bread"}
```

Model uses the display name instead of the exact key, even though the format `key: name` is clear.

## Expected Behavior

GM should copy the exact key from context:
```python
get_npc_attitude(from_entity='farmer_marcus', to_entity='test_hero')
```

## Root Cause

Multiple factors contributed to key hallucination:

1. **Distance Problem**: Key-copy instructions appeared ~1000 tokens BEFORE the actual entity keys in the grounding manifest
2. **Inconsistent Examples**: System prompt examples used `farmer_001` in some places and `farmer_marcus` in others, confusing the model about expected format
3. **Weak Retry Feedback**: When grounding validation failed, error messages said "key doesn't exist" but didn't show which keys ARE valid
4. **Pattern Matching**: Model learned the `_001` suffix pattern and invented similar keys

## Solution Implemented

Multi-layer fix addressing prevention, recovery, and graceful degradation:

### Layer 1: Prompt Engineering (Prevention)
- Fixed inconsistent examples in `prompts.py` (changed `farmer_001` to `farmer_marcus`)
- Enhanced `format_for_prompt()` with inline key reminders in each entity section
- Added concrete examples like `→ Example: get_npc_attitude(from_entity="farmer_marcus", ...)`
- Updated tool parameter descriptions to emphasize "EXACT key from context"

### Layer 2: Enhanced Retry Feedback (Recovery)
- Added `find_similar_key()` fuzzy matching to GroundingManifest
- Enhanced `error_feedback()` to include "Did you mean: farmer_marcus (Marcus)?" suggestions
- Error feedback now shows list of valid keys when invalid key is used

### Layer 3: Fuzzy Key Matching (Graceful Degradation)
- Added `KeyResolver` class that auto-corrects close key matches
- Integrated fuzzy matching into key-sensitive tools (`take_item`, `drop_item`, `give_item`, `get_npc_attitude`)
- Logs warnings when keys are auto-corrected for debugging

## Files Modified

- [x] `src/gm/prompts.py` - Fixed inconsistent examples (lines 260-265)
- [x] `src/gm/grounding.py` - Added `find_similar_key()`, enhanced `format_for_prompt()` and `error_feedback()`
- [x] `src/gm/tools.py` - Added `KeyResolver` class, integrated fuzzy matching, updated tool descriptions
- [x] `src/gm/gm_node.py` - Pass manifest to GMTools for fuzzy matching

## Tests Added

- [x] `tests/test_gm/test_grounding.py`:
  - `TestFindSimilarKey` - Tests for fuzzy key matching
  - `TestEnhancedErrorFeedback` - Tests for suggestion feedback

- [x] `tests/test_gm/test_tools.py`:
  - `TestKeyResolver` - Tests for KeyResolver class and integration

## Verification

All 104 tests pass in `tests/test_gm/test_grounding.py` and `tests/test_gm/test_tools.py`.

## Related Issues

- Grounding validation catches unkeyed entity mentions in narrative
- This was a different issue: tool parameter key hallucination

## References

- `logs/llm/session_297/turn_002_20251228_085752_gm.md` - Example of hallucinated key
- `src/gm/tools.py` - Tool definitions with KeyResolver
- `src/gm/prompts.py` - System prompt with improved key instructions
- `src/gm/grounding.py` - Fuzzy matching and enhanced feedback
