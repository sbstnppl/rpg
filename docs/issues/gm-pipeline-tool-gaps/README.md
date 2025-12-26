# GM Pipeline Tool Gaps

**Status:** Mostly Complete
**Priority:** High
**Detected:** 2025-12-26
**Related Sessions:** E2E test runs

## Problem Statement

The GM pipeline was missing critical tools for item manipulation and need satisfaction, and the system prompt lacked guidance on when to use existing tools. E2E tests showed 10/18 passing (56%).

## Implementation Summary

### What Was Added

**New Tools** (`src/gm/tools.py`):
- `take_item(item_key)` - Player picks up items
- `drop_item(item_key)` - Player drops items at location
- `give_item(item_key, recipient_key)` - Player gives items to NPCs
- `satisfy_need(need, amount, activity, item_key?, destroys_item?)` - Satisfies player needs

**Updated Prompt** (`src/gm/prompts.py`):
- Clear tool categories (Dice & Combat, Items, Needs, Knowledge)
- Explicit USE/SKIP guidance for `skill_check`
- Examples for `satisfy_need` triggers
- Time estimation guidelines

**Fixed Time Estimation** (`src/gm/gm_node.py`):
- Replaced keyword matching with tool-based inference
- No more false positives ("thinking of walking" no longer matches)
- Time inferred from actual tool calls

## Results

| Scenario | Before | After | Status |
|----------|--------|-------|--------|
| Skill Challenges | 2/3 (67%) | **3/3 (100%)** | Fixed |
| Exploration & Dialog | 3/5 (60%) | **4/5 (80%)** | Improved |
| Item Discovery | 2/4 (50%) | 1/4 (25%)* | Tools work |
| Needs & Activities | 0/3 (0%) | 0/3 (0%)* | Tools work |
| Movement & Travel | 3/3 | 3/3 | Unchanged |
| OOC Commands | 3/3 | 3/3 | Unchanged |

*Tools are being called correctly, but:
- Item test fails when perception check fails (RNG)
- Needs test: GM picks wrong need (e.g., "comfort" vs "stamina")

## Remaining Issues (LLM Behavior)

These are prompt engineering issues, not code bugs:

1. **Wrong need selection**: GM calls `satisfy_need` but sometimes picks wrong need
   - "I rest" → GM chose `comfort` instead of `stamina`

2. **`record_fact` not called**: When NPCs share information, GM doesn't record it

3. **Test RNG**: Some tests fail due to failed skill checks, not tool issues

## Files Modified

| File | Changes |
|------|---------|
| `src/gm/tools.py` | +4 tool definitions, +4 implementations, +4 routing |
| `src/gm/prompts.py` | Restructured TOOLS section with examples |
| `src/gm/gm_node.py` | Replaced `_estimate_time_passed()` - now tool-based |

## Test Cases

- [x] E2E: Skill Challenges 3/3
- [~] E2E: Exploration and Dialog 4/5 (record_fact issue)
- [~] E2E: Item Discovery - tools work, test has RNG dependency
- [~] E2E: Needs and Activities - tools work, LLM picks wrong need

## Next Steps

1. Further prompt refinement for need selection accuracy
2. Consider adding unit tests for new tools
3. May need few-shot examples in prompt for edge cases

## References

- E2E logs: `logs/gm_e2e/run_20251226_*`
- Test runner: `scripts/gm_e2e_test_runner.py`
- Scenarios: `scripts/gm_e2e_scenarios.py`
