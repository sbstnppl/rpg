# TODO: GM Prompt Architecture Optimization

## Investigation Phase
- [ ] Map complete prompt assembly flow (where does context come from?)
- [ ] Document all context layers and their sources
- [ ] Analyze token usage across different scenarios
- [ ] Review LLM logs for patterns of failure
- [ ] Compare current approach to best practices
- [ ] Find root cause of question vs action confusion

## Design Phase
- [ ] Decide: Single-pass enhanced vs Two-phase pipeline
- [ ] Design context layering strategy
- [ ] Define model routing (which model for which task)
- [ ] Create new prompt templates/structure
- [ ] Define interface between reasoning and narration (if two-phase)
- [ ] Review with user

## Implementation Phase
- [ ] Implement prompt changes
- [ ] Add multi-model routing if needed
- [ ] Update context assembly logic
- [ ] Add question detection patterns
- [ ] Add "never auto-acquire" rule

## Verification Phase
- [ ] Test question handling ("Are there...?", "What about...?")
- [ ] Test action handling ("I take...", "I search...")
- [ ] Test context continuity across turns
- [ ] Test NPC consistency
- [ ] Run gameplay session to verify improvements

## Completion
- [ ] Update README.md status to "Done"
- [ ] Update docs/architecture.md if pipeline changed
- [ ] Create commit with `/commit`
