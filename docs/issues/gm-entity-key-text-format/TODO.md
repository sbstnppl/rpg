# TODO: GM Entity Key-Text Format Bug

## Investigation Phase
- [x] Reproduce the issue
- [x] Identify affected code paths
- [x] Document current behavior
- [x] Find root cause

## Design Phase
- [x] Propose solution (bandaid fix in grounding validator)
- [x] Identify files to modify
- [x] Define test cases
- [ ] Review with user (if needed)

## Implementation Phase
- [x] Add `get_entity()` helper to GroundingManifest (already existed)
- [x] Add `fix_key_only_format()` to grounding_validator.py
- [x] Update `strip_key_references()` to accept optional manifest
- [x] Add/update tests (16 new tests)

## Verification Phase
- [ ] Test manually with qwen3:32b
- [x] Run test suite: `pytest tests/test_gm/test_grounding.py` (50 passed)
- [ ] Verify fix in gameplay (session 292 or new)

## Completion
- [x] Update README.md status to "Done"
- [ ] Create commit with `/commit`
