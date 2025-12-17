"""Intent parser module for converting player input to structured actions.

This module provides the core parsing infrastructure for the System-Authority
architecture. It converts natural language player input into structured
Action objects that can be validated and executed by the game system.

Main Components:
    - ActionType: Enum of all mechanical action types
    - Action: Dataclass representing a single parsed action
    - ParsedIntent: Container for all actions from one player input
    - IntentParser: Main parser class with pattern matching and LLM fallback
    - SceneContext: Context information for parsing
"""

from src.parser.action_types import (
    Action,
    ActionCategory,
    ActionType,
    ParsedIntent,
    ACTION_CATEGORIES,
)
from src.parser.intent_parser import IntentParser, SceneContext
from src.parser.patterns import parse_input, parse_command, parse_natural_language
from src.parser.llm_classifier import classify_intent

__all__ = [
    # Core types
    "Action",
    "ActionCategory",
    "ActionType",
    "ParsedIntent",
    "ACTION_CATEGORIES",
    # Parser classes
    "IntentParser",
    "SceneContext",
    # Direct parsing functions
    "parse_input",
    "parse_command",
    "parse_natural_language",
    # LLM classification
    "classify_intent",
]
