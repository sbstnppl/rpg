# TODO: Look Around Command Unexpectedly Moves Player

## Investigation Phase
- [ ] Reproduce the issue in fresh session
- [ ] Check action matcher classification for "look around"
- [ ] Review branch cache for observation vs movement branches
- [ ] Check GM decision oracle output
- [ ] Document current behavior with logs

## Design Phase
- [ ] Identify why OBSERVE action triggers MOVE
- [ ] Determine if issue is in prediction, matching, or collapse
- [ ] Define test cases for observation commands
- [ ] Review with user (if needed)

## Implementation Phase
- [ ] Fix action classification or matching logic
- [ ] Add/update tests for observation commands
- [ ] Ensure OBSERVE actions never change location

## Verification Phase
- [ ] Test "look around" manually
- [ ] Test other observation commands (examine, search, inspect)
- [ ] Run test suite
- [ ] Verify fix in gameplay

## Completion
- [ ] Update README.md status to "Done"
- [ ] Create commit with `/commit`
