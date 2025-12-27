"""Observability module for GM pipeline monitoring.

Provides hooks and observers for real-time visibility into pipeline phases,
LLM calls, tool executions, and validation steps.
"""

from src.observability.events import (
    PhaseStartEvent,
    PhaseEndEvent,
    LLMCallStartEvent,
    LLMCallEndEvent,
    LLMTokenEvent,
    ToolExecutionEvent,
    ValidationEvent,
)
from src.observability.hooks import (
    ObservabilityHook,
    NullHook,
    CompositeHook,
)
from src.observability.console_observer import RichConsoleObserver

__all__ = [
    # Events
    "PhaseStartEvent",
    "PhaseEndEvent",
    "LLMCallStartEvent",
    "LLMCallEndEvent",
    "LLMTokenEvent",
    "ToolExecutionEvent",
    "ValidationEvent",
    # Hooks
    "ObservabilityHook",
    "NullHook",
    "CompositeHook",
    # Observers
    "RichConsoleObserver",
]
