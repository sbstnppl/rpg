"""Constrained narrator module for the System-Authority architecture.

This module generates narrative prose from mechanical results,
ensuring the narrative never contradicts the mechanics.

For Scene-First Architecture:
- validator: Validates narrator output against manifest
- scene_narrator: Generates narration with [key] format and validation
"""

from src.narrator.narrator import ConstrainedNarrator
from src.narrator.validator import NarratorValidator
from src.narrator.scene_narrator import SceneNarrator

__all__ = ["ConstrainedNarrator", "NarratorValidator", "SceneNarrator"]
