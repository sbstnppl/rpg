"""Event dataclasses for observability hooks.

These events are emitted by the GM pipeline at key points to provide
visibility into what's happening during execution.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class PhaseStartEvent:
    """Emitted when a pipeline phase starts."""

    phase: str
    timestamp: datetime = field(default_factory=datetime.now)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class PhaseEndEvent:
    """Emitted when a pipeline phase completes."""

    phase: str
    duration_ms: float
    success: bool = True
    timestamp: datetime = field(default_factory=datetime.now)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMCallStartEvent:
    """Emitted when an LLM call begins."""

    iteration: int
    model: str
    has_tools: bool
    system_prompt_tokens: int
    message_count: int
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class LLMCallEndEvent:
    """Emitted when an LLM call completes."""

    iteration: int
    duration_ms: float
    response_tokens: int
    has_tool_calls: bool
    tool_count: int = 0
    text_preview: str = ""
    cache_read_tokens: int = 0  # Tokens read from cache (fast)
    cache_creation_tokens: int = 0  # Tokens cached for next call
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class LLMTokenEvent:
    """Emitted for each token during streaming."""

    token: str
    is_tool_use: bool = False
    tool_name: str | None = None


@dataclass
class ToolExecutionEvent:
    """Emitted when a tool is executed."""

    tool_name: str
    arguments: dict[str, Any]
    result: dict[str, Any]
    duration_ms: float
    success: bool = True
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ValidationEvent:
    """Emitted during grounding or character validation."""

    validator_type: str  # "grounding" or "character"
    attempt: int
    max_attempts: int
    passed: bool
    error_count: int = 0
    errors: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
