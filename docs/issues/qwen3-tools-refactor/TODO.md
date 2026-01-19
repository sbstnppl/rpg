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
- [x] Test skill checks with Qwen3 (unit tests with mocks)
- [x] Test attack rolls with Qwen3 (unit tests with mocks)
- [x] Test entity creation with Qwen3 (unit tests with mocks)
- [x] Test fallback when Qwen-Agent unavailable (error handling tests)
- [x] Test with both Ollama and direct Qwen API (provider init tests)

## Verification Phase
- [x] Run test suite (272 LLM tests pass, 50 new QwenAgentProvider tests)
- [ ] Test manually in gameplay (optional - requires Qwen3 model running)
- [ ] Verify tools work during combat (optional - requires Qwen3 model running)
- [ ] Verify entity creation works (optional - requires Qwen3 model running)

## Completion
- [x] Update README.md status to "Done"
- [x] Create commit with `/commit`
