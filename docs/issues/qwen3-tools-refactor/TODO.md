# TODO: Qwen3 Tools Refactor

## Investigation Phase
- [x] Reproduce the issue (Ollama/Qwen3 throws "does not support tools")
- [x] Identify affected code paths (`src/gm/gm_node.py` tool loop)
- [x] Document current behavior (fallback to simple completion)
- [x] Find root cause (Ollama native API doesn't support Qwen3 tools yet)
- [x] Research solutions (Qwen-Agent library handles tool templates internally)

## Design Phase
- [ ] Evaluate QwenAgentProvider approach vs Hermes format embedding
- [ ] Design provider interface changes (if any needed)
- [ ] Identify files to modify
- [ ] Define test cases
- [ ] Review with user (if needed)

## Implementation Phase
- [ ] Add `qwen-agent` dependency
- [ ] Create `src/llm/qwen_agent_provider.py`
- [ ] Register provider in `src/llm/factory.py`
- [ ] Update GM node to select appropriate provider
- [ ] Add fallback if Qwen-Agent unavailable

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
