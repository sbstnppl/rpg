# GM Structured Output Format

**Status:** Done
**Priority:** Medium
**Detected:** 2025-12-25
**Resolved:** 2025-12-25
**Related Sessions:** Gameplay testing session

## Problem Statement

The GM outputs structured markdown sections like `**Response:**`, `**Updated Inventory (Finn):**`, and `**New Storage Container:**` instead of pure prose narration. The LLM is hallucinating this format despite the prompt saying "no JSON or metadata."

## Current Behavior

GM output:
```
**Response:**
You step back into the cottage and make your way to a wooden chest...

**Updated Inventory (Finn):**
- `clean_shirt_001`: Clean Linen Shirt
- `clean_breeches_001`: Clean Breeches

**New Storage Container:**
- `clothes_chest_001`: Wooden Chest...
```

## Expected Behavior

Pure prose narration that continues the conversation naturally:
```
You step back into the cottage and make your way to a wooden chest near the foot of the bed...
```

No markdown sections, no inventory listings, no storage container announcements. Just story.

## Root Cause

1. Prompt lacks explicit format instruction (negative-only framing)
2. No conversation-continuation framing to encourage natural prose
3. No post-hoc cleanup to strip markdown if it appears

## Solution Implemented

### 1. Prompt Changes (`src/gm/prompts.py`)

Updated NARRATIVE section from negative-only framing to explicit positive + forbidden list:

```
## NARRATIVE

Continue the conversation naturally in second person ("you"):
- 2-5 sentences of pure prose
- Show, don't tell
- End with natural pause for player input

FORBIDDEN in output:
- Markdown headers (no **Section:** or ## headers)
- Bullet lists or numbered lists
- Inventory summaries
- Any structured formatting

Just write the next part of the story.
```

### 2. Post-hoc Cleanup (`src/gm/gm_node.py`)

Added `_clean_narrative_static()` method that:
- Strips markdown headers (`**Section:**`, `## Header`)
- Strips bullet lists (`- item`, `* item`)
- Strips numbered lists (`1. item`)
- Detects structured sections (inventory, storage, items) and removes them entirely
- Preserves hyphenated words in prose
- Preserves multi-paragraph prose

Cleanup is applied in `_parse_response()` after OOC detection.

### 3. Unit Tests (`tests/test_gm/test_narrative_cleanup.py`)

13 test cases covering:
- Clean narrative passthrough
- Stripping various header formats
- Stripping inventory/storage sections
- Preserving legitimate prose
- Edge cases (empty, whitespace)

## Files Modified

- [x] `src/gm/prompts.py` - Updated NARRATIVE section
- [x] `src/gm/gm_node.py` - Added `_clean_narrative_static()` and integrated into parsing
- [x] `tests/test_gm/test_narrative_cleanup.py` - New test file (13 tests)

## Test Results

All 33 GM tests pass, including 13 new narrative cleanup tests.

## Related Issues

- Item naming technical debt (clean_shirt_001 naming)
- Player agency over-interpretation
