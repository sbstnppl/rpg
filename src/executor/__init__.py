"""Action executor module for the System-Authority architecture.

This module executes validated actions and produces results
that can be narrated by the narrator.

Main Components:
    - ActionExecutor: Executes validated actions
    - ExecutionResult: Result of executing a single action
    - TurnResult: Combined result of all actions in a turn
"""

from src.executor.action_executor import (
    ActionExecutor,
    ExecutionResult,
    TurnResult,
)

__all__ = [
    "ActionExecutor",
    "ExecutionResult",
    "TurnResult",
]
