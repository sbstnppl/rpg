# TODO: Movement Without State Update

## Investigation Phase
- [x] Reproduce the issue (Session 293, Turn 15)
- [x] Identify affected code paths (no move tool, state changes)
- [x] Document current behavior
- [x] Find root cause (no tool, no prompt guidance)

## Design Phase
- [x] Propose solution (add tool and/or prompt guidance)
- [x] Identify files to modify
- [x] Define test cases
- [ ] Review with user - choose Option A, B, or C

## Implementation Phase
- [ ] Add move_to tool (if chosen)
- [ ] Add movement prompt instructions (if chosen)
- [ ] Ensure applier handles MOVE state changes
- [ ] Add tests

## Verification Phase
- [ ] Test manually with movement scenarios
- [ ] Run test suite
- [ ] Verify location updates in database

## Completion
- [ ] Update README.md status to "Done"
- [ ] Create commit with `/commit`
