"""Action validators for the System-Authority architecture.

This module provides validation logic for all action types.
Validators check if actions are mechanically possible before execution.

Main Components:
    - ValidationResult: Result of validating a single action
    - ActionValidator: Main validator that dispatches to type-specific validators
"""

from src.validators.action_validator import (
    ActionValidator,
    ValidationResult,
    RiskTag,
)

__all__ = [
    "ActionValidator",
    "ValidationResult",
    "RiskTag",
]
