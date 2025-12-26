# TODO: Strengthen GM Prompts for Tool Calling

## Investigation Phase
- [x] Reproduce the issue (E2E tests: 71.4% overall)
- [x] Identify affected code paths (`src/gm/prompts.py`)
- [x] Document current behavior (see README.md)
- [x] Find root cause (prompt structure, model limitations)
- [x] Discover secondary bug: `_clamp` truncation (80→99 instead of 100)

## Design Phase
- [x] Review current prompt structure in `prompts.py`
- [x] Research prompt patterns for reliable tool calling
- [x] Decide between Approach 1 (strengthen) vs Approach 2 (few-shot) → Used both
- [x] Test prompt changes with Claude baseline

## Implementation Phase
- [x] Fix `_clamp` truncation bug (`int()` → `round()`)
- [x] Add `think` parameter to AnthropicProvider for compatibility
- [x] Restructure GM_SYSTEM_PROMPT with mandatory tool sections
- [x] Add all 10 needs with trigger words
- [x] Add explicit triggers for take_item, drop_item, record_fact, get_npc_attitude
- [x] Add few-shot examples at end of prompt

## Verification Phase
- [x] Run Claude baseline before changes: 20%
- [x] Run Claude baseline after changes: 80% (quick), 66.7% (full)
- [x] Run qwen3 after changes: 40% (quick)

## Results Summary
| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Claude quick (Exploration) | 20% | 80% | ✓ Improved |
| Claude full (6 scenarios) | N/A | 66.7% | 85% not met |
| get_npc_attitude | Not called | Reliably called | ✓ Fixed |
| satisfy_need | Not called | Still inconsistent* | Needs test fix |
| record_fact | Not called | Still inconsistent | Needs more work |

*satisfy_need fails because test scene has no food - Claude correctly role-plays this

## Follow-up Issues (Not Done)
- [ ] Update test scenarios to include food/water in scene
- [ ] Add few-shot example specifically for location info → record_fact
- [ ] Address third-person narration issue (separate problem)
- [ ] Test with qwen3 improvements to see if local model improves

## Completion
- [x] Update README.md status to "Partially Complete"
- [x] Document final findings in README
- [ ] Create commit with `/commit`
