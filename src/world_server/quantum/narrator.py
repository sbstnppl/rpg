"""Narrator Engine for the Quantum Pipeline (Phase 4).

Phase 4 of the split architecture. Uses the narrator model (magmell) to:
1. Generate creative prose from semantic outcomes
2. Ground all entity references using [key:display] format
3. Create immersive narrative that matches the game's tone

The key insight is that narration is SEPARATE from reasoning:
- Reasoning (Phase 2): Determines WHAT happens (logic)
- Narration (Phase 4): Describes HOW it looks/sounds/feels (creativity)

Input: SemanticOutcome + StateDelta[] + key_mapping
Output: Prose string with [entity_key:display_text] format
"""

import logging
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from src.llm.base import LLMProvider
from src.llm.factory import get_narrator_provider
from src.llm.message_types import Message
from src.world_server.quantum.reasoning import SemanticOutcome
from src.world_server.quantum.delta_translator import TranslationResult

logger = logging.getLogger(__name__)


# =============================================================================
# LLM Response Schema
# =============================================================================


class NarrationResponse(BaseModel):
    """Structured response from the narration LLM call."""

    narrative: str = Field(
        description="The narrative prose with [key:display] format for entities. "
        "Example: '[npc_tom:Old Tom] slides [item_ale:a mug of ale] across the bar.'"
    )
    inner_thoughts: str | None = Field(
        default=None,
        description="Optional inner thoughts/feelings of the player character",
    )
    ambient_details: str | None = Field(
        default=None,
        description="Optional ambient environmental details",
    )


# =============================================================================
# System Prompt
# =============================================================================

NARRATOR_SYSTEM_PROMPT = """You are a narrative writer for a fantasy RPG. Your job is to bring scenes to life with vivid, immersive prose.

## Entity Reference Format

CRITICAL: You MUST use the [key:display] format for ALL entity references.
- Format: [entity_key:Display Text]
- Example: [npc_tom_001:Old Tom] slides [item_ale_001:a mug of honeyed ale] across the worn wooden bar.

This format is REQUIRED for:
- NPCs: [npc_key:NPC Name]
- Items: [item_key:item description]
- Locations: [loc_key:Location Name]
- The player: [player_key:you] (use "you" as the display text)

## Writing Style

1. **Second Person**: Always use "you" for the player
   - Good: "You reach for the mug"
   - Bad: "The player reaches for the mug"

2. **Present Tense**: Write in present tense for immediacy
   - Good: "The door creaks open"
   - Bad: "The door creaked open"

3. **Sensory Details**: Include sights, sounds, smells, textures
   - Good: "The sweet scent of honey mingles with the sharp bite of hops"
   - Bad: "The ale smells good"

4. **Show, Don't Tell**: Demonstrate emotions through action
   - Good: "[npc_tom:Tom]'s weathered face creases into a warm smile"
   - Bad: "Tom is happy to see you"

5. **Concise but Vivid**: Keep it tight, 2-4 sentences typically
   - Don't pad with unnecessary description
   - Every sentence should add something

6. **Avoid Repetition**: Don't repeat location or character names
   - Bad: "You enter The Rusty Tankard. The Rusty Tankard is warm."
   - Good: "You enter The Rusty Tankard. The warmth of the hearth envelops you."
   - Use pronouns or descriptors after the first mention ("it", "the tavern", "the inn")

## Grounding Rules

You MUST only reference entities that are provided in the key mapping.
- If a key is provided, use it: [provided_key:display name]
- NEVER invent new entity keys
- NEVER reference NPCs, items, or locations not in the mapping

## Examples

Input:
what_happens: "The bartender gives the player a mug of honeyed ale"
key_mapping: {"Old Tom": "npc_tom_001", "a mug of honeyed ale": "item_ale_001"}
player_key: "hero_001"

Output:
"[npc_tom_001:Old Tom] reaches beneath the bar and produces [item_ale_001:a mug of honeyed ale], the amber liquid catching the firelight as he slides it toward [hero_001:you]. 'On the house,' he says with a knowing wink."

Input:
what_happens: "The player fails to pick the lock and the lockpick breaks"
key_mapping: {"the chest": "item_chest_001"}
player_key: "hero_001"

Output:
"[hero_001:You] work the pick into [item_chest_001:the chest]'s stubborn lock, feeling for the telltale give of tumblers. A sharp *snap* makes your heart sink—the pick's tip has broken off inside the mechanism."
"""


# =============================================================================
# Narrator Engine
# =============================================================================


@dataclass
class NarrationContext:
    """Context for narrative generation."""

    # What happened (from reasoning)
    what_happens: str
    outcome_type: str  # success, failure, etc.

    # Key mapping for entity references
    key_mapping: dict[str, str]  # display_name -> entity_key
    player_key: str = "player"

    # Scene context
    location_display: str = ""
    location_key: str = ""

    # NPCs and items in scene (for reference)
    npcs_in_scene: dict[str, str] = field(default_factory=dict)  # display -> key
    items_in_scene: dict[str, str] = field(default_factory=dict)  # display -> key

    # Optional hints for tone
    tone_hints: list[str] = field(default_factory=list)

    @property
    def full_key_mapping(self) -> dict[str, str]:
        """Get complete key mapping including scene entities."""
        mapping = dict(self.key_mapping)
        mapping.update(self.npcs_in_scene)
        mapping.update(self.items_in_scene)
        if self.location_display and self.location_key:
            mapping[self.location_display] = self.location_key
        return mapping


@dataclass
class NarratorEngine:
    """LLM-based narrator for generating immersive prose.

    Uses the narrator model (magmell) to transform semantic outcomes
    into vivid narrative text with proper entity grounding.
    """

    llm: LLMProvider | None = None

    def __post_init__(self) -> None:
        """Initialize with default provider if not provided."""
        if self.llm is None:
            self.llm = get_narrator_provider()

    async def narrate(
        self,
        context: NarrationContext,
    ) -> NarrationResponse:
        """Generate narrative prose for an outcome.

        Args:
            context: Context including what happened and key mappings.

        Returns:
            NarrationResponse with prose using [key:display] format.
        """
        prompt = self._build_prompt(context)

        try:
            response = await self.llm.complete_structured(
                messages=[Message.user(prompt)],
                response_schema=NarrationResponse,
                system_prompt=NARRATOR_SYSTEM_PROMPT,
                temperature=0.7,  # Higher temperature for creativity
                max_tokens=512,
            )

            if response.parsed_content is None:
                logger.warning("Narrator returned no parsed content")
                return self._fallback_narration(context)

            # Handle dict response (some providers return dict instead of Pydantic model)
            result = response.parsed_content
            if isinstance(result, dict):
                result = NarrationResponse(**result)

            return result

        except Exception as e:
            logger.error(f"Narration failed: {e}")
            return self._fallback_narration(context)

    async def narrate_from_outcome(
        self,
        outcome: SemanticOutcome,
        translation: TranslationResult,
        player_key: str,
        location_display: str = "",
        location_key: str = "",
        npcs_in_scene: dict[str, str] | None = None,
        items_in_scene: dict[str, str] | None = None,
    ) -> NarrationResponse:
        """Convenience method to narrate from outcome and translation.

        Args:
            outcome: SemanticOutcome from reasoning phase.
            translation: TranslationResult from delta translator.
            player_key: Entity key of the player.
            location_display: Display name of current location.
            location_key: Entity key of current location.
            npcs_in_scene: NPCs in scene (display -> key).
            items_in_scene: Items in scene (display -> key).

        Returns:
            NarrationResponse with grounded prose.
        """
        context = NarrationContext(
            what_happens=outcome.what_happens,
            outcome_type=outcome.outcome_type,
            key_mapping=translation.key_mapping,
            player_key=player_key,
            location_display=location_display,
            location_key=location_key,
            npcs_in_scene=npcs_in_scene or {},
            items_in_scene=items_in_scene or {},
        )
        return await self.narrate(context)

    def _build_prompt(self, context: NarrationContext) -> str:
        """Build the narration prompt."""
        lines = [
            "## What Happens",
            context.what_happens,
            "",
            f"## Outcome: {context.outcome_type}",
            "",
        ]

        if context.location_display:
            lines.append(f"## Location: {context.location_display}")
            lines.append("")

        # Build key mapping section
        lines.append("## Entity Key Mapping")
        lines.append("Use these EXACT keys in [key:display] format:")
        lines.append("")

        full_mapping = context.full_key_mapping

        # Player
        lines.append(f"- Player: [{context.player_key}:you]")

        # Location
        if context.location_key:
            lines.append(f"- Location: [{context.location_key}:{context.location_display}]")

        # Other entities
        for display, key in full_mapping.items():
            if key != context.player_key and key != context.location_key:
                lines.append(f"- [{key}:{display}]")

        lines.extend(
            [
                "",
                "## Task",
                "Write 2-4 sentences of immersive narrative prose.",
                "Use [key:display] format for ALL entity references.",
                "Write in second person (you) and present tense.",
            ]
        )

        if context.tone_hints:
            lines.append("")
            lines.append(f"Tone: {', '.join(context.tone_hints)}")

        return "\n".join(lines)

    def _fallback_narration(self, context: NarrationContext) -> NarrationResponse:
        """Create a fallback narration when LLM fails."""
        # Simple fallback that still uses key format
        narrative = context.what_happens

        # Try to add player reference
        narrative = narrative.replace(
            "the player", f"[{context.player_key}:you]"
        ).replace("The player", f"[{context.player_key}:You]")

        return NarrationResponse(narrative=narrative)


# =============================================================================
# Helper Functions
# =============================================================================


def build_narration_context(
    what_happens: str,
    outcome_type: str,
    key_mapping: dict[str, str],
    player_key: str,
    location_display: str = "",
    location_key: str = "",
    npcs_in_scene: dict[str, str] | None = None,
    items_in_scene: dict[str, str] | None = None,
    tone_hints: list[str] | None = None,
) -> NarrationContext:
    """Build NarrationContext from components.

    Convenience function for creating narration context.
    """
    return NarrationContext(
        what_happens=what_happens,
        outcome_type=outcome_type,
        key_mapping=key_mapping,
        player_key=player_key,
        location_display=location_display,
        location_key=location_key,
        npcs_in_scene=npcs_in_scene or {},
        items_in_scene=items_in_scene or {},
        tone_hints=tone_hints or [],
    )


def narrate_question_response(
    question: str,
    answer: str,
    player_key: str,
) -> str:
    """Generate a simple response for informational questions.

    For QUESTION intents that don't change state, we generate
    a simple informational response without full narration.
    """
    return f"[{player_key}:You] consider: {answer}"


def narrate_ooc_response(
    request: str,
    response: str,
) -> str:
    """Generate a response for out-of-character requests.

    OOC requests get plain text responses without entity formatting.
    """
    return f"[OOC] {response}"
