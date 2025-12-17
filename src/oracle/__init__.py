"""Complication Oracle module for injecting creative complications.

The oracle adds narrative interest by occasionally introducing
complications that don't break mechanics - they only ADD events,
never prevent player actions from succeeding.
"""

from src.oracle.complication_oracle import ComplicationOracle
from src.oracle.complication_types import (
    Complication,
    ComplicationType,
    Effect,
    EffectType,
)

__all__ = [
    "ComplicationOracle",
    "Complication",
    "ComplicationType",
    "Effect",
    "EffectType",
]
