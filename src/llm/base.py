"""LLM provider protocol definition.

Defines the interface that all LLM providers must implement.
"""

from typing import Any, Protocol, Sequence, runtime_checkable

from src.llm.message_types import Message
from src.llm.response_types import LLMResponse
from src.llm.tool_types import ToolDefinition


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM providers.

    All providers must implement both sync and async versions
    to support LangGraph's async execution model while allowing
    sync usage in simpler contexts.
    """

    @property
    def provider_name(self) -> str:
        """Return provider identifier (e.g., 'anthropic', 'openai')."""
        ...

    @property
    def default_model(self) -> str:
        """Return default model for this provider."""
        ...

    async def complete(
        self,
        messages: Sequence[Message],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        stop_sequences: Sequence[str] | None = None,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Generate a completion from messages.

        Args:
            messages: Conversation history.
            model: Model to use (defaults to provider's default).
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature (0.0-1.0).
            stop_sequences: Sequences that stop generation.
            system_prompt: System-level instructions.

        Returns:
            LLMResponse with text and metadata.
        """
        ...

    async def complete_with_tools(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolDefinition],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tool_choice: str | dict[str, Any] = "auto",
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Generate a completion that may include tool calls.

        Args:
            messages: Conversation history.
            tools: Available tools/functions.
            model: Model to use.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            tool_choice: "auto", "any", "none", or specific tool.
            system_prompt: System-level instructions.

        Returns:
            LLMResponse with text and/or tool_calls.
        """
        ...

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

        Uses tool_use/function_calling under the hood to ensure
        valid JSON output matching the provided schema.

        Args:
            messages: Conversation history.
            response_schema: Pydantic model or dataclass for output.
            model: Model to use.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature (default lower for structured).
            system_prompt: System-level instructions.

        Returns:
            LLMResponse with parsed_content containing the structured data.
        """
        ...

    def count_tokens(
        self,
        text: str,
        model: str | None = None,
    ) -> int:
        """Count tokens in text for context window management.

        Args:
            text: Text to count tokens for.
            model: Model to use for tokenization.

        Returns:
            Token count.
        """
        ...
