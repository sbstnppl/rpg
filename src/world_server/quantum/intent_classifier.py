"""LLM-based Intent Classifier for the Quantum Pipeline.

Phase 1 of the split architecture. Replaces pure fuzzy matching with
LLM-powered intent understanding that can:
1. Distinguish actions from questions/hypotheticals
2. Extract action type, target, and topic
3. Match against cached branches with semantic understanding

Uses the cheap/fast provider for low latency (~100-200ms).
"""

import logging
from dataclasses import dataclass

from pydantic import BaseModel, Field

from src.llm.base import LLMProvider
from src.llm.factory import get_cheap_provider
from src.llm.message_types import Message
from src.world_server.quantum.intent import (
    IntentClassification,
    IntentClassifierInput,
    IntentType,
    CachedBranchSummary,
)
from src.world_server.quantum.schemas import ActionType

logger = logging.getLogger(__name__)


# =============================================================================
# LLM Response Schema
# =============================================================================


class IntentClassificationResponse(BaseModel):
    """Structured response from the intent classification LLM call."""

    intent_type: str = Field(
        description="Type of intent: 'action', 'question', 'hypothetical', 'ooc', or 'ambiguous'"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence in the classification (0.0-1.0)"
    )
    action_type: str | None = Field(
        default=None,
        description="Type of action if applicable: 'interact_npc', 'manipulate_item', 'move', 'observe', 'skill_use', 'combat', 'wait'",
    )
    target: str | None = Field(
        default=None, description="Target of the action (display name from scene)"
    )
    topic: str | None = Field(
        default=None, description="Topic for NPC interactions (what to discuss)"
    )
    matched_option: int | None = Field(
        default=None,
        description="Index of the best matching cached option (1-based), or null if no good match",
    )
    match_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence that matched_option is correct (0.0-1.0)",
    )


# =============================================================================
# System Prompt
# =============================================================================

INTENT_CLASSIFIER_SYSTEM_PROMPT = """You are an intent classifier for a fantasy RPG game. Your job is to understand what the player wants to do based on their input.

## Intent Types

1. **action** - Player wants to perform an action NOW
   - "talk to Tom" → action
   - "pick up the sword" → action
   - "go to the market" → action
   - "ask Tom about the robbery" → action (SPEECH ACT - performing dialog)
   - "ask Tom if he has work" → action (SPEECH ACT - asking a question IN-WORLD)
   - "tell the guard my name" → action (SPEECH ACT)
   - "greet the innkeeper" → action (SPEECH ACT)

2. **question** - Player is asking about possibilities (informational)
   - "Could I talk to Tom?" → question
   - "Can I pick up the sword?" → question
   - "What's available here?" → question
   - "Is Tom here?" → question

3. **hypothetical** - Player is exploring "what if" scenarios
   - "What if I talked to Tom?" → hypothetical
   - "What would happen if I attacked the guard?" → hypothetical

4. **ooc** - Out-of-character / meta requests (starts with "ooc:" or similar)
   - "ooc: what time is it?" → ooc
   - "ooc: what are my stats?" → ooc

5. **ambiguous** - Cannot determine intent, need clarification
   - Very short or unclear input
   - Multiple possible interpretations

## CRITICAL: Speech Acts vs Meta Questions

Distinguish between speech acts (ACTION) and meta questions (QUESTION):

**Speech acts** (always ACTION): Player performs dialog IN the game world
- "ask X about Y" → ACTION (player speaks to X)
- "ask X if Y" → ACTION (player asks X a question in-game)
- "tell X that Y" → ACTION (player tells X something)
- "say hello to X" → ACTION (player greets X)
- "greet X" → ACTION (player greets X)

**Meta questions** (QUESTION): Player asks about game possibilities
- "Could I talk to X?" → QUESTION (asking IF they can)
- "Can I pick that up?" → QUESTION (asking about possibility)
- "Is X here?" → QUESTION (asking for information)
- "What items are available?" → QUESTION (asking for information)

The key difference:
- Speech acts use imperative verbs directing action ("ask", "tell", "greet", "say")
- Meta questions use modal verbs asking possibility ("could", "can", "would", "should")

## Action Types

When intent is action/question/hypothetical, classify the action type:
- **interact_npc**: Talk to, trade with, attack NPC
- **manipulate_item**: Take, drop, use, examine item
- **move**: Go somewhere, travel, enter/exit
- **observe**: Look around, examine environment
- **skill_use**: Actions with uncertain outcomes requiring dice rolls

  SKILL_USE examples (classify these as skill_use, NOT move):
  - "sneak past the guard" → skill_use (stealth)
  - "try to sneak into the alley" → skill_use (stealth)
  - "hide in the shadows" → skill_use (stealth)
  - "creep quietly behind them" → skill_use (stealth)
  - "climb the wall" → skill_use (athletics)
  - "scale the cliff" → skill_use (athletics)
  - "jump across the gap" → skill_use (athletics)
  - "pick the lock" → skill_use (sleight of hand)
  - "lockpick the door" → skill_use (sleight of hand)
  - "steal the purse" → skill_use (sleight of hand)
  - "persuade the merchant" → skill_use (persuasion)
  - "convince them to help" → skill_use (persuasion)
  - "intimidate the guard" → skill_use (intimidation)
  - "deceive the shopkeeper" → skill_use (deception)
  - "bluff your way past" → skill_use (deception)

  NOT skill_use (these are move):
  - "go to the alley" → move (no skill verb)
  - "walk into the market" → move (simple travel)
  - "enter the tavern" → move (no uncertainty)

  KEY: Look for skill verbs (sneak, hide, climb, pick, steal, persuade, etc.).
  If present, it's skill_use even if movement is involved.
- **combat**: Attack, defend, flee
- **wait**: Wait, rest, sleep

## Target Extraction

Extract the target from the player's input using the available targets in the scene.
Match to the closest available target (NPC name, item name, or exit).

## Topic Extraction

For NPC interactions, extract what the player wants to discuss:
- "ask Tom about the robbery" → topic: "the robbery"
- "talk to the guard about entering" → topic: "entering"
- "greet the innkeeper" → topic: null (just a greeting)

## Cache Matching

If cached options are provided, determine if the player's input matches any of them.
Only match if the semantic meaning is very similar (same action type, same target).

Be strict about matching:
- "talk to Tom about ale" should NOT match "talk to Tom about the weather"
- "pick up sword" SHOULD match "take the sword"
- "go north" SHOULD match "head to the northern exit"

Return match_confidence >= 0.8 only if you're confident it's the same intended action.
"""


# =============================================================================
# Intent Classifier
# =============================================================================


@dataclass
class IntentClassifier:
    """LLM-based intent classifier for player input.

    Uses a fast/cheap LLM to classify player intent and optionally
    match against cached branches.
    """

    llm: LLMProvider | None = None
    min_confidence: float = 0.5  # Minimum confidence to trust classification

    def __post_init__(self) -> None:
        """Initialize with default provider if not provided."""
        if self.llm is None:
            self.llm = get_cheap_provider()

    async def classify(
        self,
        input_data: IntentClassifierInput,
    ) -> IntentClassification:
        """Classify player intent using LLM.

        Args:
            input_data: Player input with scene context and cached branches.

        Returns:
            IntentClassification with extracted intent details.
        """
        prompt = self._build_prompt(input_data)

        try:
            response = await self.llm.complete_structured(
                messages=[Message.user(prompt)],
                response_schema=IntentClassificationResponse,
                system_prompt=INTENT_CLASSIFIER_SYSTEM_PROMPT,
                temperature=0.1,  # Low temperature for consistent classification
                max_tokens=256,
            )

            if response.parsed_content is None:
                logger.warning("Intent classifier returned no parsed content")
                return self._fallback_classification(input_data.player_input)

            return self._convert_response(
                response.parsed_content,
                input_data,
            )

        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            return self._fallback_classification(input_data.player_input)

    def _build_prompt(self, input_data: IntentClassifierInput) -> str:
        """Build the classification prompt."""
        lines = [
            f"## Player Input",
            f'"{input_data.player_input}"',
            "",
            f"## Scene: {input_data.location_display}",
            "",
        ]

        # Add available targets
        if input_data.npcs_present:
            lines.append(f"NPCs present: {', '.join(input_data.npcs_present)}")
        if input_data.items_available:
            lines.append(f"Items available: {', '.join(input_data.items_available)}")
        if input_data.exits_available:
            lines.append(f"Exits: {', '.join(input_data.exits_available)}")

        # Add cached options if any
        if input_data.cached_branches:
            lines.extend(["", "## Cached Actions (match if semantically equivalent)"])
            for i, branch in enumerate(input_data.cached_branches, 1):
                lines.append(f"{i}. {branch.action_summary}")

        lines.extend(
            [
                "",
                "## Task",
                "Classify the player's intent and extract action details.",
                "If a cached action matches, provide the option number.",
            ]
        )

        return "\n".join(lines)

    def _convert_response(
        self,
        response: IntentClassificationResponse | dict,
        input_data: IntentClassifierInput,
    ) -> IntentClassification:
        """Convert LLM response to IntentClassification."""
        # Handle dict response (some providers return dict instead of Pydantic model)
        if isinstance(response, dict):
            response = IntentClassificationResponse(**response)

        # Parse intent type
        try:
            intent_type = IntentType(response.intent_type.lower())
        except ValueError:
            intent_type = IntentType.AMBIGUOUS

        # Parse action type
        action_type = None
        if response.action_type:
            try:
                action_type = ActionType(response.action_type.lower())
            except ValueError:
                pass

        # Resolve target to entity key if possible
        target_key = None
        if response.target:
            target_key = self._resolve_target_key(response.target, input_data)

        # Get matched branch key
        matched_branch_key = None
        if response.matched_option and response.match_confidence >= 0.7:
            idx = response.matched_option - 1  # Convert to 0-based
            if 0 <= idx < len(input_data.cached_branches):
                matched_branch_key = input_data.cached_branches[idx].branch_key

        return IntentClassification(
            intent_type=intent_type,
            confidence=response.confidence,
            action_type=action_type,
            target_display=response.target,
            target_key=target_key,
            topic=response.topic,
            matched_branch_key=matched_branch_key,
            match_confidence=response.match_confidence if matched_branch_key else 0.0,
            raw_input=input_data.player_input,
        )

    def _resolve_target_key(
        self,
        target_display: str,
        input_data: IntentClassifierInput,
    ) -> str | None:
        """Try to resolve target display name to entity key.

        This is a simple fuzzy match - the actual key resolution
        happens later when we have access to the full manifest.
        """
        # For now, just return None - key resolution happens in pipeline
        # with access to GroundingManifest
        return None

    def _fallback_classification(self, player_input: str) -> IntentClassification:
        """Create a fallback classification when LLM fails.

        Uses simple heuristics to provide a basic classification.
        """
        lower_input = player_input.lower().strip()

        # Check for OOC
        if lower_input.startswith("ooc:") or lower_input.startswith("ooc "):
            return IntentClassification(
                intent_type=IntentType.OUT_OF_CHARACTER,
                confidence=0.9,
                raw_input=player_input,
            )

        # Check for question patterns
        question_starters = ("could i", "can i", "should i", "what if", "would it")
        if any(lower_input.startswith(q) for q in question_starters) or lower_input.endswith("?"):
            return IntentClassification(
                intent_type=IntentType.QUESTION,
                confidence=0.6,
                raw_input=player_input,
            )

        # Default to action with low confidence (let old matcher handle it)
        return IntentClassification(
            intent_type=IntentType.ACTION,
            confidence=0.4,  # Low confidence triggers fallback to old matcher
            raw_input=player_input,
        )


# =============================================================================
# Helper Functions
# =============================================================================


def build_classifier_input(
    player_input: str,
    location_display: str,
    location_key: str,
    npcs: list[str],
    items: list[str],
    exits: list[str],
    cached_summaries: list[CachedBranchSummary] | None = None,
) -> IntentClassifierInput:
    """Build IntentClassifierInput from components.

    Convenience function for creating classifier input from
    individual components rather than constructing the dataclass directly.
    """
    return IntentClassifierInput(
        player_input=player_input,
        location_display=location_display,
        location_key=location_key,
        npcs_present=npcs,
        items_available=items,
        exits_available=exits,
        cached_branches=cached_summaries or [],
    )
