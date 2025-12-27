"""Observability hook protocol and implementations.

The ObservabilityHook protocol defines the interface for receiving events
from the GM pipeline. Implementations can render to console, write to files,
or aggregate metrics.
"""

from typing import Protocol, runtime_checkable

from src.observability.events import (
    PhaseStartEvent,
    PhaseEndEvent,
    LLMCallStartEvent,
    LLMCallEndEvent,
    LLMTokenEvent,
    ToolExecutionEvent,
    ValidationEvent,
)


@runtime_checkable
class ObservabilityHook(Protocol):
    """Protocol for observability hooks.

    Implement this protocol to receive events from the GM pipeline.
    All methods are optional - implement only what you need.
    """

    def on_phase_start(self, event: PhaseStartEvent) -> None:
        """Called when a pipeline phase starts."""
        ...

    def on_phase_end(self, event: PhaseEndEvent) -> None:
        """Called when a pipeline phase completes."""
        ...

    def on_llm_call_start(self, event: LLMCallStartEvent) -> None:
        """Called when an LLM call begins."""
        ...

    def on_llm_call_end(self, event: LLMCallEndEvent) -> None:
        """Called when an LLM call completes."""
        ...

    def on_llm_token(self, event: LLMTokenEvent) -> None:
        """Called for each token during streaming."""
        ...

    def on_tool_execution(self, event: ToolExecutionEvent) -> None:
        """Called when a tool is executed."""
        ...

    def on_validation(self, event: ValidationEvent) -> None:
        """Called during validation attempts."""
        ...


class NullHook:
    """No-op hook for when observability is disabled.

    This is the default hook - it does nothing but satisfies the protocol.
    Using this avoids null checks throughout the code.
    """

    def on_phase_start(self, event: PhaseStartEvent) -> None:
        pass

    def on_phase_end(self, event: PhaseEndEvent) -> None:
        pass

    def on_llm_call_start(self, event: LLMCallStartEvent) -> None:
        pass

    def on_llm_call_end(self, event: LLMCallEndEvent) -> None:
        pass

    def on_llm_token(self, event: LLMTokenEvent) -> None:
        pass

    def on_tool_execution(self, event: ToolExecutionEvent) -> None:
        pass

    def on_validation(self, event: ValidationEvent) -> None:
        pass


class CompositeHook:
    """Combines multiple hooks into one.

    Events are dispatched to all hooks in order.
    Useful for having both console and file output.
    """

    def __init__(self, hooks: list[ObservabilityHook]) -> None:
        """Initialize with a list of hooks.

        Args:
            hooks: List of hooks to dispatch events to.
        """
        self.hooks = hooks

    def on_phase_start(self, event: PhaseStartEvent) -> None:
        for hook in self.hooks:
            hook.on_phase_start(event)

    def on_phase_end(self, event: PhaseEndEvent) -> None:
        for hook in self.hooks:
            hook.on_phase_end(event)

    def on_llm_call_start(self, event: LLMCallStartEvent) -> None:
        for hook in self.hooks:
            hook.on_llm_call_start(event)

    def on_llm_call_end(self, event: LLMCallEndEvent) -> None:
        for hook in self.hooks:
            hook.on_llm_call_end(event)

    def on_llm_token(self, event: LLMTokenEvent) -> None:
        for hook in self.hooks:
            hook.on_llm_token(event)

    def on_tool_execution(self, event: ToolExecutionEvent) -> None:
        for hook in self.hooks:
            hook.on_tool_execution(event)

    def on_validation(self, event: ValidationEvent) -> None:
        for hook in self.hooks:
            hook.on_validation(event)
