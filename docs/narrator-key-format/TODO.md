# TODO: Narrator Key Format Issue

## Investigation Phase
- [ ] Read `src/narrator/scene_narrator.py` to understand current implementation
- [ ] Check what prompt is being sent to the LLM
- [ ] Verify NarratorManifest is correctly passed to narrator
- [ ] Check if validation feedback reaches retry attempts
- [ ] Look at successful examples (if any) vs failures

## Design Phase
- [ ] Identify root cause
- [ ] Propose solution (prompt changes, structured output, post-processing)
- [ ] Review approach with user
- [ ] Define success criteria

## Implementation Phase
- [ ] Implement fix
- [ ] Add/update tests for key format compliance
- [ ] Update narrator prompt if needed

## Verification Phase
- [ ] Test manually with GO action to new location
- [ ] Verify validation passes on first attempt
- [ ] Verify display shows natural language (keys stripped)
- [ ] Test with multiple entity types (NPCs, items, furniture)

## Completion
- [ ] Update README.md status to "Done"
- [ ] Create commit with `/commit`
