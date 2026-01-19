# TODO: MOVE Action Narrative Direction Reversed

## Investigation Phase
- [x] Reproduce the issue
- [x] Identify affected code paths (pipeline.py lines 813-820)
- [x] Document current behavior
- [x] Find root cause (destination manifest + player input = contradiction)

## Design Phase
- [x] Propose solution (add movement context to prompt)
- [x] Identify files to modify
- [x] Define test cases
- [x] Review with user (if needed)

## Implementation Phase
- [x] Add movement context to branch generator prompt
- [x] Pass origin location to branch generator
- [x] Add/update tests
- [x] Update documentation

## Verification Phase
- [x] Test manually in gameplay
- [x] Run test suite
- [x] Verify narratives describe correct direction

## Completion
- [x] Update README.md status to "Done"
- [ ] Create commit with `/commit`
