"""Intent classification schemas for the Quantum Pipeline.

Phase 1 of the split architecture: Classify player intent and match to cached branches.
This replaces pure fuzzy matching with LLM-powered intent understanding.

Intent types:
- ACTION: Player wants to perform an action (execute)
- QUESTION: Player asks about possibilities (answer without state change)
- HYPOTHETICAL: Player explores "what if" scenarios (describe without state change)
- OUT_OF_CHARACTER: Meta/system requests (handle specially)
"""

from dataclasses import dataclass, field
from enum import Enum

from src.world_server.quantum.schemas import ActionType


class IntentType(str, Enum):
    """Type of player intent detected from their input."""

    ACTION = "action"  # "talk to Tom" - execute the action
    QUESTION = "question"  # "Could I talk to Tom?" - provide information
    HYPOTHETICAL = "hypothetical"  # "What if I talked to Tom?" - describe possibilities
    OUT_OF_CHARACTER = "ooc"  # "ooc: what time is it?" - meta request
    AMBIGUOUS = "ambiguous"  # Cannot determine - ask for clarification


@dataclass
class IntentClassification:
    """Result of classifying player intent.

    This is the output of Phase 1 (Intent Classifier), providing:
    - What type of intent was detected
    - Extracted action details (type, target, topic)
    - Cache matching results if applicable
    """

    intent_type: IntentType
    confidence: float  # 0.0 to 1.0

    # Extracted action details (for ACTION, QUESTION, HYPOTHETICAL)
    action_type: ActionType | None = None
    target_display: str | None = None  # Display name, e.g., "Old Tom", "the sword"
    target_key: str | None = None  # Entity key if resolved, e.g., "innkeeper_tom"
    topic: str | None = None  # For NPC interactions: what to discuss

    # Cache matching (for ACTION type)
    matched_branch_key: str | None = None
    match_confidence: float = 0.0

    # Original input for reference
    raw_input: str = ""

    def __post_init__(self) -> None:
        """Validate confidence ranges."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be 0.0-1.0, got {self.confidence}")
        if not 0.0 <= self.match_confidence <= 1.0:
            raise ValueError(f"match_confidence must be 0.0-1.0, got {self.match_confidence}")

    @property
    def is_action(self) -> bool:
        """Check if this is an actionable intent."""
        return self.intent_type == IntentType.ACTION

    @property
    def is_informational(self) -> bool:
        """Check if this is an informational request (no state change)."""
        return self.intent_type in (
            IntentType.QUESTION,
            IntentType.HYPOTHETICAL,
            IntentType.OUT_OF_CHARACTER,
        )

    @property
    def is_cache_hit(self) -> bool:
        """Check if we have a valid cache match."""
        return self.matched_branch_key is not None and self.match_confidence >= 0.7

    @property
    def needs_clarification(self) -> bool:
        """Check if we should ask the user for clarification."""
        return self.intent_type == IntentType.AMBIGUOUS or self.confidence < 0.5


@dataclass
class CachedBranchSummary:
    """Summary of a cached branch for intent matching.

    Used to provide context to the intent classifier about available
    cached branches without sending the full branch data.
    """

    branch_key: str
    action_type: ActionType
    target_display: str | None
    action_summary: str  # e.g., "talk to the bartender about drinks"
    topic: str | None = None  # For NPC interactions

    # For matching
    keywords: list[str] = field(default_factory=list)


@dataclass
class IntentClassifierInput:
    """Input to the intent classifier.

    Combines player input with scene context and cached branch options.
    """

    player_input: str
    location_display: str
    location_key: str

    # Available targets in scene
    npcs_present: list[str]  # Display names
    items_available: list[str]  # Display names
    exits_available: list[str]  # Display names

    # Cached branches to consider for matching
    cached_branches: list[CachedBranchSummary] = field(default_factory=list)

    # Player context
    player_name: str = "you"
    recent_actions: list[str] = field(default_factory=list)  # Last 3 actions
