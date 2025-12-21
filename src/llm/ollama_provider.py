"""Ollama provider implementation using langchain-ollama.

Provides native Ollama integration for local LLM inference.
"""

import json
import re
from typing import Any, Sequence

from langchain_ollama import ChatOllama
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
)

from src.llm.base import LLMProvider
from src.llm.message_types import Message, MessageRole
from src.llm.response_types import LLMResponse, ToolCall, UsageStats
from src.llm.tool_types import ToolDefinition
from src.llm.exceptions import (
    ProviderError,
    StructuredOutputError,
)


class OllamaProvider:
    """Ollama LLM implementation using langchain-ollama.

    Supports:
    - Llama 3, Llama 3.1, Llama 3.2, Mistral, Qwen3, etc.
    - Tool calling (model-dependent - llama3.1+, mistral, qwen3 support it)
    - Structured output via with_structured_output()
    - Local or remote Ollama instances
    - Thinking mode control for reasoning models (Qwen3, etc.)

    Note:
    - Token counting is approximate (Ollama doesn't expose tokenizers)
    - Usage stats are not available via langchain-ollama interface
    """

    CHARS_PER_TOKEN = 4  # Rough estimate for token counting
    # Match complete thinking blocks
    THINKING_PATTERN = re.compile(r"<think>.*?</think>\s*", re.DOTALL)
    # Match incomplete thinking blocks (cut off before closing tag)
    THINKING_INCOMPLETE = re.compile(r"<think>.*$", re.DOTALL)

    @staticmethod
    def _strip_thinking(content: str) -> str:
        """Remove <think>...</think> tags from response content.

        Handles both complete and incomplete (cut-off) thinking blocks.
        """
        # First remove complete blocks
        result = OllamaProvider.THINKING_PATTERN.sub("", content)
        # Then remove any incomplete block at the end
        result = OllamaProvider.THINKING_INCOMPLETE.sub("", result)
        return result.strip()

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "llama3",
    ) -> None:
        """Initialize Ollama provider.

        Args:
            base_url: Ollama server URL (e.g., http://localhost:11434).
            default_model: Default model to use for completions.
        """
        self._base_url = base_url
        self._default_model = default_model

    @property
    def provider_name(self) -> str:
        """Return provider identifier."""
        return "ollama"

    @property
    def default_model(self) -> str:
        """Return default model for this provider."""
        return self._default_model

    def _convert_messages(
        self, messages: Sequence[Message], system_prompt: str | None = None
    ) -> list[HumanMessage | AIMessage | SystemMessage | ToolMessage]:
        """Convert our Message types to LangChain message format."""
        lc_messages: list[HumanMessage | AIMessage | SystemMessage | ToolMessage] = []

        # Add system prompt first if provided
        if system_prompt:
            lc_messages.append(SystemMessage(content=system_prompt))

        for msg in messages:
            content = msg.content if isinstance(msg.content, str) else str(msg.content)

            if msg.role == MessageRole.USER:
                lc_messages.append(HumanMessage(content=content))
            elif msg.role == MessageRole.ASSISTANT:
                lc_messages.append(AIMessage(content=content))
            elif msg.role == MessageRole.SYSTEM:
                lc_messages.append(SystemMessage(content=content))
            elif msg.role == MessageRole.TOOL:
                lc_messages.append(
                    ToolMessage(content=content, tool_call_id=msg.tool_call_id or "")
                )

        return lc_messages

    def _parse_response(self, response: AIMessage, model: str) -> LLMResponse:
        """Parse LangChain AIMessage into LLMResponse.

        Always strips <think>...</think> tags from content.
        """
        raw_content = response.content if isinstance(response.content, str) else ""
        content = self._strip_thinking(raw_content)
        tool_calls: list[ToolCall] = []

        if response.tool_calls:
            for tc in response.tool_calls:
                tool_calls.append(
                    ToolCall(
                        id=tc.get("id", ""),
                        name=tc["name"],
                        arguments=tc["args"],
                        raw_arguments=json.dumps(tc["args"]),
                    )
                )

        # Ollama doesn't provide token usage via langchain-ollama
        return LLMResponse(
            content=content,
            tool_calls=tuple(tool_calls),
            finish_reason="stop",
            model=model,
            usage=None,
            raw_response=response,
        )

    async def complete(
        self,
        messages: Sequence[Message],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        stop_sequences: Sequence[str] | None = None,
        system_prompt: str | None = None,
        think: bool = False,
    ) -> LLMResponse:
        """Generate a completion from messages.

        Args:
            messages: Conversation messages.
            model: Model to use (defaults to provider's default).
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            stop_sequences: Stop sequences to end generation.
            system_prompt: System prompt to prepend.
            think: Enable thinking mode for reasoning models (Qwen3, etc.).
                   Defaults to False for faster responses.
        """
        # Disable thinking mode if not requested (faster responses)
        effective_system = system_prompt or ""
        if not think:
            effective_system = "/nothink\n" + effective_system if effective_system else "/nothink"

        lc_messages = self._convert_messages(messages, effective_system)
        model_name = model or self._default_model

        client = ChatOllama(
            base_url=self._base_url,
            model=model_name,
            temperature=temperature,
            num_predict=max_tokens,
            stop=list(stop_sequences) if stop_sequences else None,
        )

        try:
            response = await client.ainvoke(lc_messages)
            return self._parse_response(response, model_name)
        except Exception as e:
            raise ProviderError(str(e), is_retryable=True)

    async def complete_with_tools(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolDefinition],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tool_choice: str | dict[str, Any] = "auto",
        system_prompt: str | None = None,
        think: bool = True,
    ) -> LLMResponse:
        """Generate a completion that may include tool calls.

        Args:
            messages: Conversation messages.
            tools: Available tool definitions.
            model: Model to use (defaults to provider's default).
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            tool_choice: Tool selection mode ("auto", "none", or specific tool).
            system_prompt: System prompt to prepend.
            think: Enable thinking mode for reasoning models (Qwen3, etc.).
                   Defaults to True for tool calls (reasoning helps).

        Note: Not all Ollama models support tool calling.
        Models with tool support include: llama3.1+, mistral, qwen3, etc.
        """
        # Apply thinking mode control
        effective_system = system_prompt or ""
        if not think:
            effective_system = "/nothink\n" + effective_system if effective_system else "/nothink"

        lc_messages = self._convert_messages(messages, effective_system)
        model_name = model or self._default_model

        client = ChatOllama(
            base_url=self._base_url,
            model=model_name,
            temperature=temperature,
            num_predict=max_tokens,
        )

        # Convert tools to LangChain format (OpenAI-compatible function schema)
        lc_tools = [tool.to_openai_format()["function"] for tool in tools]
        client_with_tools = client.bind_tools(lc_tools)

        try:
            response = await client_with_tools.ainvoke(lc_messages)
            return self._parse_response(response, model_name)
        except Exception as e:
            raise ProviderError(str(e), is_retryable=True)

    async def complete_structured(
        self,
        messages: Sequence[Message],
        response_schema: type,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Generate a structured response matching a schema.

        Uses ChatOllama's with_structured_output() for Pydantic models.
        """
        lc_messages = self._convert_messages(messages, system_prompt)
        model_name = model or self._default_model

        client = ChatOllama(
            base_url=self._base_url,
            model=model_name,
            temperature=temperature,
            num_predict=max_tokens,
        )

        try:
            structured_client = client.with_structured_output(response_schema)
            result = await structured_client.ainvoke(lc_messages)

            # Result is the Pydantic model instance or dict
            if hasattr(result, "model_dump"):
                parsed_content = result.model_dump()
            else:
                parsed_content = result

            return LLMResponse(
                content="",
                parsed_content=parsed_content,
                finish_reason="stop",
                model=model_name,
                usage=None,
            )
        except Exception as e:
            raise StructuredOutputError(str(e), raw_output=str(e))

    def count_tokens(
        self,
        text: str,
        model: str | None = None,
    ) -> int:
        """Count tokens in text (rough estimate).

        Ollama doesn't provide a public tokenizer, so we use a heuristic
        of approximately 4 characters per token (similar to Anthropic).
        """
        if not text:
            return 0
        return len(text) // self.CHARS_PER_TOKEN
