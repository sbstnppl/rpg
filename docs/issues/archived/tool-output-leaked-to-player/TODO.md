# TODO: Tool Output Leaked to Player

## Investigation Phase
- [x] Reproduce the issue (Session 293, Turn 12)
- [x] Identify affected code paths (`gm_node.py:_validate_character`)
- [x] Document current behavior
- [x] Find root cause (missing validation patterns)

## Design Phase
- [x] Propose solution (add character break patterns)
- [x] Identify files to modify
- [x] Define test cases
- [ ] Review with user (if needed)

## Implementation Phase
- [x] Add new patterns to `_CHARACTER_BREAK_PATTERNS` in gm_node.py
- [x] Add same patterns to context_builder.py
- [x] Add unit tests for new patterns (tests/test_gm/test_character_validation.py)
- [x] Fixed bug in existing `r"\bnext steps?:\b"` pattern (trailing \b doesn't match)

## Verification Phase
- [x] Run test suite (145 passed, 1 skipped in tests/test_gm/)
- [ ] Verify fix in gameplay (optional)

## Completion
- [x] Update README.md status to "Done"
- [ ] Create commit with `/commit`
