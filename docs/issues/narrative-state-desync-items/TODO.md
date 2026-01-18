# TODO: Narrative/State Desync - Items Not Created

## Investigation Phase
- [x] Reproduce the issue (session 338, turns 3-4)
- [x] Identify affected code paths (branch_generator.py → collapse.py)
- [x] Document current behavior (narrative describes item, no delta)
- [x] Find root cause (LLM not generating CREATE_ENTITY deltas)

## Design Phase
- [x] Review branch generator system prompt
- [x] Propose solution (prompt enhancement + validation)
- [x] Identify files to modify
- [x] Define test cases
- [x] Review with user (if needed)

## Implementation Phase
- [x] Add item transaction examples to branch generator prompt
- [x] Add INVARIANT rule for item transfers
- [x] Replace restrictive block with semantic guidance
- [ ] Add/update tests (optional - manual verification first)

## Verification Phase
- [x] Test order→drink flow manually (session 339)
- [ ] Run test suite
- [x] Verify fix in gameplay

## Completion
- [x] Update README.md status to "Done"
- [ ] Create commit with `/commit`
