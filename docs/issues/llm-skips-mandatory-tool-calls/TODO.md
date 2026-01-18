# TODO: LLM Skips Mandatory Tool Calls

## Investigation Phase
- [x] Reproduce the issue (Session 304, Turn 7)
- [x] Identify affected code paths (quantum pipeline, not gm_node.py)
- [x] Document current behavior (see README.md)
- [x] Find root cause (missing INVARIANT section in branch_generator.py prompt)

## Design Phase
- [x] Propose solution (add INVARIANT FOR NEED-SATISFYING ACTIONS)
- [x] Identify files to modify (branch_generator.py, validation.py, delta_postprocessor.py)
- [x] Define test cases (existing tests cover needs functionality)
- [x] Review with user (if needed)

## Implementation Phase
- [x] Add INVARIANT section to branch_generator.py with activity-to-need mapping
- [x] Add `social_connection` to VALID_NEEDS in validation.py
- [x] Add `social_connection` to VALID_NEEDS in delta_postprocessor.py
- [x] Run test suite (all tests pass)

## Verification Phase (Pending)
- [ ] Test manually via play-testing
- [x] Run test suite - 68 validation tests + 21 branch generator tests passed
- [ ] Verify fix in gameplay (needs 3 successful play-tests)

## Completion
- [ ] Update README.md status to "Awaiting Verification" after commit
- [ ] Create commit with `/commit`
