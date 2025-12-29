# Context Length Exceeds qwen3:32b 8192 Token Limit on First Turn

**Status:** Done
**Priority:** High
**Detected:** 2025-12-29
**Resolved:** 2025-12-29
**Related Sessions:** Session 302

## Problem Statement

The GM pipeline fails on the very first turn with a context length error. The qwen3:32b model via Ollama has an 8192 token limit, but the initial prompt (system prompt + grounding manifest + context) already exceeds this at 8198 tokens. This makes the game completely unplayable with the current configuration.

## Current Behavior

When starting a new game session and attempting the first turn ("look around"), the game crashes with:

```
openai.BadRequestError: Error code: 400 - {'error': {'message': "This model's maximum context length is 8192 tokens. However, your request has 8198 input tokens. Please reduce the length of the input messages. None", 'type': 'BadRequestError', 'param': None, 'code': 400}}
```

The error occurs in:
- `src/llm/openai_provider.py:319` - during `complete_with_tools` call
- `src/gm/gm_node.py:617` - in the `run` method
- `src/gm/gm_node.py:914` - in `_run_tool_loop`

## Expected Behavior

The game should be playable from the first turn. Either:
1. The initial context should fit within 8192 tokens
2. The system should handle context overflow gracefully (truncation, summarization)
3. The model configuration should support larger context windows

## Investigation Notes

- Session 302 created with auto-setup
- Starting location: village_tavern
- Error occurs before any game content is generated
- 8198 tokens vs 8192 limit = only 6 tokens over
- The system prompt + grounding manifest + tool definitions are likely the bulk

### Token budget breakdown (estimated):
- System prompt (`src/gm/prompts.py`): ~2000-3000 tokens
- Tool definitions (15 tools): ~1500-2000 tokens
- Grounding manifest: ~1000-2000 tokens
- Context/history: ~1000+ tokens
- User message: ~10 tokens

## Root Cause

**CONFIRMED**: The vLLM server is configured with `max_model_len=8192`.

Query to vLLM `/v1/models` endpoint shows:
```json
{"max_model_len":8192}
```

This is a **vLLM deployment configuration issue**, NOT a code issue. The qwen3-32b model supports up to 131k context, but vLLM was started with `--max-model-len 8192` (or similar).

The combined size of:
1. GM system prompt (comprehensive instructions)
2. 15 tool definitions with schemas
3. Grounding manifest (NPCs, items, locations, exits)
4. Session context

...exceeds the artificially low 8192 token limit.

## Resolution

**Deployment fix applied**: vLLM restarted with `--max-model-len 32768` on 2025-12-29.

The qwen3-32b model supports up to 131k context, so increasing from 8192 to 32768 provides ample headroom for the GM pipeline (~8198 tokens on first turn).

## Original Proposed Solution

**Immediate fix**: Restart vLLM with larger context:
```bash
# Add to vLLM startup command:
--max-model-len 32768
# or higher, up to 131072 for qwen3-32b
```

**Future improvements** (defense in depth, low priority now):
1. **Add context budget management** - Trim context if approaching limit
2. **Reduce system prompt size** - Compress instructions, remove redundancy
3. **Dynamically adjust grounding manifest** - Include only relevant entities
4. **Handle ContextLengthError gracefully** - Retry with truncated context

## Implementation Details

### Immediate Fix: Restart vLLM
On the vLLM server (192.168.178.35:8150), restart with increased context:
```bash
python -m vllm.entrypoints.openai.api_server \
    --model /models/Qwen3-32B \
    --max-model-len 32768 \
    ...
```

### Code Defense: Context Budget
Add pre-flight check in `GMNode.run()` to estimate token count before API call.

## Files to Modify

- [ ] `src/config.py` - Add context window configuration
- [ ] `src/llm/openai_provider.py` - Pass num_ctx parameter
- [ ] `src/gm/prompts.py` - Potentially reduce prompt size
- [ ] `src/gm/context_builder.py` - Add context budget management

## Test Cases

- [ ] Test case 1: First turn succeeds with "look around"
- [ ] Test case 2: Context doesn't exceed limit after 10 turns
- [ ] Test case 3: Long conversations still work with context management

## Related Issues

- This blocks all gameplay testing with qwen3:32b

## References

- `src/llm/openai_provider.py` - API call location
- `src/gm/gm_node.py` - GM node implementation
- `src/gm/prompts.py` - System prompt definition
- `src/gm/context_builder.py` - Context construction
- Ollama documentation for `num_ctx` parameter
