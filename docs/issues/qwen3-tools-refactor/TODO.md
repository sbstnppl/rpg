# TODO: Qwen3 Tools Refactor

## Investigation Phase
- [x] Reproduce the issue (Ollama/Qwen3 throws "does not support tools")
- [x] Identify affected code paths (`src/gm/gm_node.py` tool loop)
- [x] Document current behavior (fallback to simple completion)
- [x] Find root cause (Ollama native API doesn't support Qwen3 tools yet)
- [x] Research solutions (Qwen-Agent library handles tool templates internally)

## Design Phase
- [x] Evaluate QwenAgentProvider approach vs Hermes format embedding
- [x] Design provider interface changes (if any needed)
- [x] Identify files to modify
- [x] Define test cases
- [x] Review with user (if needed)

## Implementation Phase
- [x] Add `qwen-agent` dependency
- [x] Create `src/llm/qwen_agent_provider.py`
- [x] Register provider in `src/llm/factory.py`
- [x] Update config to include qwen-agent provider type
- [x] ~~Update GM node to select appropriate provider~~ (Not needed - factory handles it)
- [x] ~~Add fallback if Qwen-Agent unavailable~~ (Not needed - standalone provider)

## Testing Phase
- [ ] Test skill checks with Qwen3
- [ ] Test attack rolls with Qwen3
- [ ] Test entity creation with Qwen3
- [ ] Test fallback when Qwen-Agent unavailable
- [ ] Test with both Ollama and direct Qwen API

## Verification Phase
- [ ] Test manually in gameplay
- [ ] Run test suite
- [ ] Verify tools work during combat
- [ ] Verify entity creation works

## Completion
- [ ] Update README.md status to "Done"
- [ ] Create commit with `/commit`
