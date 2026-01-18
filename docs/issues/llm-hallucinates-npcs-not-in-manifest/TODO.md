# TODO: LLM Hallucinates NPCs Not in Scene Manifest

## Original Fix (Completed)
- [x] Identify affected code paths
- [x] Document current behavior
- [x] Find root cause - LLM not using [key:display] format
- [x] Update system prompt with INVARIANT FOR AMBIENT NPCs
- [x] Add `_inject_missing_npc_creates()` to DeltaPostProcessor
- [x] Add tests for NPC injection

## Regression Fix (Completed)
- [x] Identify root cause - CREATE_ENTITY keys not added to manifest before validation
- [x] Add key extraction in pipeline.py (main path)
- [x] Add key extraction in pipeline.py (retry path)
- [x] Add DeltaType import
- [x] Add TestCreateEntityKeyInjection tests (4 tests)
- [x] Run quantum test suite (592 passed)

## Verification Phase (Pending)
- [ ] Test manually in game session
- [ ] Go to tavern, try "look around"
- [ ] Try "listen to the patrons"
- [ ] Verify no "Invalid entity key" errors
- [ ] Verify ambient NPCs appear in narrative

## Completion
- [ ] Update README.md status to "Done" after verification
- [ ] Create commit with `/commit`
