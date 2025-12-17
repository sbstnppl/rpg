"""Constrained narrator module for the System-Authority architecture.

This module generates narrative prose from mechanical results,
ensuring the narrative never contradicts the mechanics.
"""

from src.narrator.narrator import ConstrainedNarrator

__all__ = ["ConstrainedNarrator"]
