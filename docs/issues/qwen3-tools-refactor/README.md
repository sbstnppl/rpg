# Refactor GM Pipeline to Use Qwen3 Tools via Qwen-Agent

**Status:** Done
**Priority:** Medium
**Detected:** 2025-12-21
**Completed:** 2026-01-19
**Related Sessions:** GM Pipeline implementation

## Problem Statement

The new GM pipeline was designed to use Claude's native `tool_use` for skill checks, combat, and entity creation. However, when running with Qwen3 via Ollama, tool calling fails because Ollama's native tool API doesn't support Qwen3 yet (docs say "To be updated for Qwen3"). The solution is to use the **Qwen-Agent** library which handles tool calling templates internally.

## Current Behavior

When running the GM pipeline with Qwen3/Ollama:

```
ollama._types.ResponseError: registry.ollama.ai/library/qwen3-32b-q4ks:latest
does not support tools (status code: 400)
```

The pipeline falls back to simple completion without tools, losing:
- Mid-generation skill checks
- Combat roll integration
- Dynamic entity creation

## Expected Behavior

The GM should be able to call tools (skill_check, attack_roll, damage_entity, create_entity) during response generation, regardless of whether using Claude or Qwen3.

## Investigation Notes

### Qwen3 Tool Support

- Qwen3 **does** support tools via "Hermes-style tool use format"
- Ollama's native tool API doesn't support Qwen3 yet
- **Qwen-Agent** library handles tool templates internally and works with Ollama

### Qwen-Agent Configuration

```python
from qwen_agent.agents import Assistant

llm_cfg = {
    'model': 'qwen3',
    'model_server': 'http://localhost:11434/v1',  # Ollama endpoint
    'api_key': 'EMPTY',
}

bot = Assistant(llm=llm_cfg, function_list=['skill_check', 'attack_roll'])
response = bot.run(messages=messages)
```

### Key References

- [Qwen-Agent GitHub](https://github.com/QwenLM/Qwen-Agent)
- [Qwen Function Calling Docs](https://qwen.readthedocs.io/en/latest/framework/function_call.html)
- [Qwen Ollama Docs](https://qwen.readthedocs.io/en/latest/run_locally/ollama.html) - Says "To be updated for Qwen3"

## Root Cause

LangChain's `bind_tools()` method relies on Ollama's native tool API, which hasn't been updated to support Qwen3's tool format yet. Qwen-Agent solves this by implementing the Hermes tool format internally.

## Proposed Solution

Create a **Qwen-Agent provider** that integrates with our LLM abstraction layer:

1. Add `qwen-agent` as a dependency
2. Create `QwenAgentProvider` class implementing our `LLMProvider` interface
3. Register tools using Qwen-Agent's function registration
4. Use `model_server` pointing to local Ollama

### Alternative: Hermes Format in Prompt

If we want to avoid the Qwen-Agent dependency, we could:
1. Embed tool definitions in the system prompt using Hermes format
2. Parse tool calls from the response text
3. Execute tools and continue generation

## Implementation Details

### Option 1: QwenAgentProvider

```python
# src/llm/qwen_agent_provider.py
from qwen_agent.agents import Assistant
from src.llm.base import LLMProvider

class QwenAgentProvider(LLMProvider):
    def __init__(self, model: str = "qwen3"):
        self.llm_cfg = {
            'model': model,
            'model_server': 'http://localhost:11434/v1',
            'api_key': 'EMPTY',
        }

    async def complete_with_tools(self, messages, tools, ...):
        # Convert tools to Qwen-Agent format
        function_list = self._convert_tools(tools)
        bot = Assistant(llm=self.llm_cfg, function_list=function_list)
        # Run and parse response
        ...
```

### Option 2: Hermes Format Embedding

Embed tools in system prompt:
```
<|im_start|>system
You are a helpful assistant with access to the following functions...
<tools>
{"name": "skill_check", "parameters": {...}}
</tools>
```

## Files Modified

- [x] `src/llm/qwen_agent_provider.py` - New provider class (443 lines)
- [x] `src/llm/factory.py` - Register new provider
- [x] `pyproject.toml` - Add qwen-agent>=0.0.20 dependency
- [x] `tests/test_llm/test_qwen_agent_provider.py` - Unit tests (50 tests)

## Test Cases

- [x] Skill check triggers during uncertain action (unit tests with mocks)
- [x] Attack roll executes during combat (unit tests with mocks)
- [x] Entity creation works for new NPCs/items (unit tests with mocks)
- [x] Fallback still works if Qwen-Agent unavailable (error handling tests)
- [x] Works with both Ollama and direct Qwen API (init tests for both configs)

## Related Issues

- Current GM pipeline implementation in `src/gm/`
- LLM provider abstraction in `src/llm/`

## References

- [Qwen-Agent GitHub](https://github.com/QwenLM/Qwen-Agent)
- [Qwen3 Blog Post](https://qwenlm.github.io/blog/qwen3/)
- [Hermes Tool Format](https://deepwiki.com/QwenLM/Qwen3/4.3-function-calling-and-tool-use)
- [Ollama Tool Calling Docs](https://docs.ollama.com/capabilities/tool-calling)
