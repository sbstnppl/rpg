# TODO: Character Break on Tool Errors

## Investigation Phase
- [x] Reproduce the issue (Session 293, Turn 6)
- [x] Identify affected code paths (tool error handling)
- [x] Document current behavior
- [x] Find root cause (error exposure, no guidance)

## Design Phase
- [x] Propose solution (prompt guidance + detection patterns)
- [x] Identify files to modify
- [x] Define test cases

## Implementation Phase
- [x] Add error handling instructions to GM_SYSTEM_PROMPT (src/gm/prompts.py:69-78)
- [x] Add error handling instructions to MINIMAL_GM_CORE_PROMPT (src/gm/prompts.py:379-382)
- [x] Add detection patterns for technical terms (src/gm/gm_node.py:133-138)

## Verification Phase
- [x] Run test suite (38 tests pass)
- [x] Added 10 new test cases for tool error patterns
- [ ] Manual test with failing tool scenarios (optional - needs live game)

## Completion
- [x] Update README.md status to "Done"
- [ ] Create commit with `/commit`
