# TODO: GM Structured Output Format

## Investigation Phase
- [x] Reproduce the issue
- [x] Identify affected code paths
- [x] Document current behavior
- [x] Find root cause

## Design Phase
- [x] Propose solution
- [x] Identify files to modify
- [x] Define test cases
- [x] Review with user (if needed)

## Implementation Phase
- [x] Restructure prompt as conversation continuation
- [x] Add explicit prose-only instruction
- [x] Add post-hoc output cleanup
- [ ] Update context builder for turn history (not needed - cleanup handles it)

## Verification Phase
- [x] Test manually in gameplay (verified via LLM logs - prompt updated, history shows clean output)
- [x] Run test suite
- [x] Verify clean prose output (via unit tests)

## Completion
- [x] Update README.md status to "Done"
- [ ] Create commit with `/commit`
