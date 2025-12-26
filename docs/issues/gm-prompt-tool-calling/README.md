# Strengthen GM Prompts for Tool Calling Consistency

**Status:** Partially Complete
**Priority:** Medium
**Detected:** 2025-12-26
**Updated:** 2025-12-26
**Related Sessions:** E2E test runs (sessions 108-123)

## Problem Statement

The GM pipeline LLM does not consistently call the appropriate tools when player actions require them. Specifically, the model fails to call `satisfy_need` for eating/drinking/resting, `take_item`/`drop_item` for item manipulation, and `record_fact` when NPCs share information.

## Changes Made

### 1. Fixed `_clamp` Truncation Bug
**File:** `src/managers/base.py:41-47`

Changed `int()` to `round()` to fix floating-point truncation:
```python
# BEFORE: 99.9 → 99
return int(max(min_val, min(max_val, value)))

# AFTER: 99.9 → 100
return round(max(min_val, min(max_val, value)))
```

**Root cause:** After `satisfy_need` set value to 100, `apply_time_decay` was called in the same transaction. Float arithmetic `100 + (-rate * hours)` resulted in 99.something, which `int()` truncated to 99.

### 2. Added `think` Parameter to AnthropicProvider
**File:** `src/llm/anthropic_provider.py:256-266`

Added `think: bool = False` parameter to `complete_with_tools()` for compatibility with GM node calls.

### 3. Restructured GM System Prompt
**File:** `src/gm/prompts.py`

Added **MANDATORY TOOL CALLS** section at the TOP of the prompt with:
- All 10 needs listed with trigger words
- take_item/drop_item triggers
- record_fact triggers
- get_npc_attitude requirement for NPC dialogue
- Clear "WHY" explanations for consequences

Added **EXAMPLES OF CORRECT TOOL USAGE** section at the END with:
- 4 correct examples (eating, socializing, taking item, NPC info)
- 1 negative example showing what NOT to do

## Test Results

### Before Changes (Baseline)
- Overall: 71.4% (original qwen3:32b tests)
- Claude quick test (Exploration): 20%

### After Changes
| Scenario | Claude | Notes |
|----------|--------|-------|
| Exploration and Dialog | 4/5 (80%) | `record_fact` still not called for location info |
| Item Discovery | 1/4 (25%) | Items not available in scene |
| Skill Challenges | 3/3 (100%) | ✓ Perfect |
| Needs and Activities | 0/3 (0%) | No food/water in scene - realistic RP |
| Movement and Travel | 3/3 (100%) | ✓ Perfect |
| OOC Commands | 3/3 (100%) | ✓ Perfect |
| **Overall** | **14/21 (66.7%)** | |

### Key Findings

1. **`get_npc_attitude` now reliably called** - Prompt changes working
2. **Needs scenario fails for valid reasons** - Claude role-plays realistically when no food is in scene
3. **`record_fact` inconsistent** - NPC shares info narratively but tool not called
4. **Third-person narration issues** - Separate problem (prompt says "second person" but not enforced strongly)

## Remaining Issues

### Issue 1: Needs Scenario Test Design
The test expects `satisfy_need` to be called for "I'm hungry, I eat some food", but Claude correctly determines there's no food in the scene and role-plays accordingly. This is arguably correct GM behavior.

**Options:**
- A) Update test scene to include food items
- B) Accept this as valid behavior (realistic RP)
- C) Add food items to player inventory in test setup

### Issue 2: record_fact for Location Info
When NPC describes location ("Tell me about this place"), the model shares info narratively but doesn't call `record_fact`. The prompt mentions this trigger but models don't consistently follow it.

**Options:**
- A) Make few-shot example specifically for location info
- B) Accept that location descriptions are ambient (not facts)
- C) Add post-processing to detect info-sharing and auto-record

## Files Modified

| File | Change |
|------|--------|
| `src/managers/base.py` | Fixed `_clamp` truncation (line 47) |
| `src/llm/anthropic_provider.py` | Added `think` parameter (line 265) |
| `src/gm/prompts.py` | Added mandatory section + examples (~80 lines) |

## Recommendations

1. **Mark as "Partially Complete"** - Core prompt improvements done
2. **Create separate issue** for test scenario improvements (add food to scene)
3. **Consider post-processing** for `record_fact` if models remain unreliable
4. **Third-person narration** is a separate prompt issue - not addressed here

## Related Files

- Test logs: `logs/gm_e2e/run_20251226_*.md`
- Prompts: `src/gm/prompts.py`
- E2E runner: `scripts/gm_e2e_test_runner.py`
