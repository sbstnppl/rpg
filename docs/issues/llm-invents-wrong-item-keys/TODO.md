# TODO: LLM Invents Wrong Item Keys

## Investigation Phase
- [x] Reproduce the issue (Session 293, Turn 6)
- [x] Identify affected code paths (tool parameter handling)
- [x] Document current behavior
- [x] Find root cause (LLM generates keys instead of copying)

## Design Phase
- [x] Propose solution (prompt improvement + optional fuzzy matching)
- [x] Identify files to modify
- [x] Define test cases
- [x] Review with user - choose Option A, B, or C

## Implementation Phase
- [x] Add key usage instructions to system prompt
- [N/A] Update inventory display format (if chosen) - Not selected
- [N/A] Add fuzzy matching fallback (if chosen) - Not selected
- [N/A] Add tests - Prompt change only, no new code paths

## Verification Phase
- [ ] Test manually with drinking/eating scenarios
- [x] Run test suite
- [ ] Verify fix in gameplay

## Completion
- [x] Update README.md status to "Done"
- [ ] Create commit with `/commit`
