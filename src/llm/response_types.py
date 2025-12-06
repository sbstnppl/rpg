"""LLM response type definitions.

Immutable dataclasses for LLM responses, tool calls, and usage statistics.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolCall:
    """A tool/function call from the LLM.

    Attributes:
        id: Unique identifier for this call (for matching response).
        name: Name of the tool/function.
        arguments: Parsed arguments as dict.
        raw_arguments: Original JSON string.
    """

    id: str
    name: str
    arguments: dict[str, Any]
    raw_arguments: str = ""

    def __hash__(self) -> int:
        """Hash based on id, name, and frozen arguments."""
        return hash((self.id, self.name, tuple(sorted(self.arguments.items()))))


@dataclass(frozen=True)
class UsageStats:
    """Token usage statistics.

    Attributes:
        prompt_tokens: Tokens in the input.
        completion_tokens: Tokens in the output.
        total_tokens: Combined total.
        cache_read_tokens: Tokens read from cache (Anthropic).
        cache_creation_tokens: Tokens used to create cache.
    """

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0


@dataclass(frozen=True)
class LLMResponse:
    """Response from an LLM completion.

    Attributes:
        content: Text content (may be empty if only tool calls).
        tool_calls: Tool/function calls to execute.
        parsed_content: Structured data if complete_structured was used.
        finish_reason: Why generation stopped.
        model: Model that generated the response.
        usage: Token usage statistics.
        raw_response: Provider's raw response (for debugging).
    """

    content: str
    tool_calls: tuple[ToolCall, ...] = field(default_factory=tuple)
    parsed_content: Any | None = None
    finish_reason: str = "stop"
    model: str = ""
    usage: UsageStats | None = None
    raw_response: Any = None

    @property
    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return len(self.tool_calls) > 0

    def __hash__(self) -> int:
        """Hash based on immutable fields."""
        return hash((
            self.content,
            self.tool_calls,
            self.finish_reason,
            self.model,
        ))
