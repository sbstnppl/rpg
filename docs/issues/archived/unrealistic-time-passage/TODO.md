# TODO: Unrealistic Time Passage

## Investigation Phase
- [x] Reproduce the issue (Session 293, multiple turns)
- [x] Identify affected code paths (`gm_node._estimate_time_passed`)
- [x] Document current behavior
- [x] Find root cause (tool-centric estimation, low default)

## Design Phase
- [x] Propose solution (hybrid activity + tool estimation)
- [x] Identify files to modify
- [x] Define test cases
- [x] Review with user - chose Option C (Hybrid)

## Implementation Phase
- [x] Add activity keyword patterns with time estimates (ACTIVITY_PATTERNS)
- [x] Update _estimate_time_passed to combine activity + tool times
- [x] Add modifiers for "quickly", "briefly", etc. (TIME_MODIFIERS)
- [x] Add tests (47 tests in test_time_estimation.py)
- [x] Fix bug: tool result keys were "name"/"input" but should be "tool"/"arguments"
- [x] Fix bug: modifier check was substring-based, causing "breakfast" to match "fast"

## Verification Phase
- [x] Run test suite (47 time estimation tests pass)
- [x] Run all GM tests (196 tests pass)

## Completion
- [x] Update README.md status to "Done"
- [ ] Create commit with `/commit`
