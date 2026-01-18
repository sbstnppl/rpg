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

from src.gm.grounding import GroundedEntity, GroundingManifest
from src.gm.grounding_validator import GroundingValidator
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

## Time of Day

CRITICAL: Match your narrative to the time period. The current time will be provided in the prompt.

- **morning/dawn** (5am-12pm): sunrise, morning light, dew, breakfast smells, early risers
- **afternoon** (12pm-6pm): midday sun, warm light, lunch/afternoon activity, busy
- **evening** (6pm-9pm): sunset, lanterns lighting, dinner time, winding down
- **night** (9pm-5am): darkness, moonlight, stars, candlelight, quiet, late hours

Do NOT describe morning light or early patrons when it's afternoon/evening/night.
Do NOT describe sunset or dinner crowds when it's morning.

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

    # Time context for temporal consistency
    game_time: str = ""  # "14:30" format
    game_period: str = ""  # "morning", "afternoon", "evening", "night"
    game_day: int = 1

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

    Includes validation and retry logic to ensure [key:text] format compliance.
    """

    llm: LLMProvider | None = None
    max_retries: int = 3
    temperature: float = 0.5  # Lowered from 0.7 for better format compliance
    strict_grounding: bool = True

    def __post_init__(self) -> None:
        """Initialize with default provider if not provided."""
        if self.llm is None:
            self.llm = get_narrator_provider()

    def _build_validation_manifest(self, context: NarrationContext) -> GroundingManifest:
        """Build a GroundingManifest from NarrationContext for validation.

        Args:
            context: The narration context with key mappings.

        Returns:
            GroundingManifest suitable for GroundingValidator.
        """
        # Build NPC entities from npcs_in_scene
        npcs: dict[str, GroundedEntity] = {}
        for display_name, key in context.npcs_in_scene.items():
            npcs[key] = GroundedEntity(
                key=key,
                display_name=display_name,
                entity_type="npc",
            )

        # Build item entities from items_in_scene and key_mapping
        items_at_location: dict[str, GroundedEntity] = {}
        for display_name, key in context.items_in_scene.items():
            items_at_location[key] = GroundedEntity(
                key=key,
                display_name=display_name,
                entity_type="item",
            )

        # Add items from key_mapping that aren't NPCs or location
        for display_name, key in context.key_mapping.items():
            if key not in npcs and key != context.location_key:
                items_at_location[key] = GroundedEntity(
                    key=key,
                    display_name=display_name,
                    entity_type="item",
                )

        return GroundingManifest(
            location_key=context.location_key or "unknown_location",
            location_display=context.location_display or "Unknown Location",
            player_key=context.player_key,
            player_display="you",
            npcs=npcs,
            items_at_location=items_at_location,
        )

    def _validate_narrative(
        self,
        narrative: str,
        context: NarrationContext,
    ) -> tuple[bool, list[str]]:
        """Validate narrative output for [key:text] format compliance.

        Args:
            narrative: The generated narrative text.
            context: The narration context with valid keys.

        Returns:
            Tuple of (is_valid, error_messages).
        """
        if not self.strict_grounding:
            return True, []

        manifest = self._build_validation_manifest(context)
        validator = GroundingValidator(manifest, skip_player_items=True)
        result = validator.validate(narrative)

        if result.valid:
            return True, []

        errors: list[str] = []

        for inv_key in result.invalid_keys:
            errors.append(
                f"Invalid key [{inv_key.key}:{inv_key.text}] - "
                f"'{inv_key.key}' not in manifest"
            )

        for unkeyed in result.unkeyed_mentions:
            errors.append(
                f"Unkeyed mention: '{unkeyed.display_name}' should be "
                f"[{unkeyed.expected_key}:{unkeyed.display_name}]"
            )

        return False, errors

    async def narrate(
        self,
        context: NarrationContext,
    ) -> NarrationResponse:
        """Generate narrative prose for an outcome with validation and retry.

        Uses a retry loop to ensure [key:text] format compliance:
        1. Generate narrative
        2. Validate output using GroundingValidator
        3. On failure, retry with error feedback (max attempts)
        4. Fall back to safe narration if all retries fail

        Args:
            context: Context including what happened and key mappings.

        Returns:
            NarrationResponse with prose using [key:display] format.
        """
        errors: list[str] = []

        for attempt in range(self.max_retries):
            prompt = self._build_prompt(context, previous_errors=errors)

            try:
                response = await self.llm.complete_structured(
                    messages=[Message.user(prompt)],
                    response_schema=NarrationResponse,
                    system_prompt=NARRATOR_SYSTEM_PROMPT,
                    temperature=self.temperature,
                    max_tokens=512,
                )

                if response.parsed_content is None:
                    logger.warning("Narrator returned no parsed content")
                    errors = ["LLM returned no content"]
                    continue

                # Handle dict response (some providers return dict instead of Pydantic)
                result = response.parsed_content
                if isinstance(result, dict):
                    result = NarrationResponse(**result)

                # Validate the narrative output
                is_valid, validation_errors = self._validate_narrative(
                    result.narrative, context
                )

                if is_valid:
                    if attempt > 0:
                        logger.info(
                            f"Narration succeeded on attempt {attempt + 1} "
                            f"after fixing format issues"
                        )
                    return result

                # Validation failed, prepare for retry
                errors = validation_errors
                logger.debug(
                    f"Narration validation failed (attempt {attempt + 1}/{self.max_retries}): "
                    f"{len(errors)} errors"
                )

            except Exception as e:
                logger.error(f"Narration failed on attempt {attempt + 1}: {e}")
                errors = [f"LLM error: {e}"]

        # All retries exhausted
        logger.warning(
            f"Narration failed after {self.max_retries} attempts, using fallback"
        )
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

    def _build_prompt(
        self,
        context: NarrationContext,
        previous_errors: list[str] | None = None,
    ) -> str:
        """Build the narration prompt.

        Args:
            context: The narration context.
            previous_errors: Errors from a previous attempt (for retry).

        Returns:
            Formatted prompt string.
        """
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

        # Add time context if available
        if context.game_period:
            lines.append(f"## Time: Day {context.game_day}, {context.game_time} ({context.game_period})")
            lines.append("Match your descriptions to this time period!")
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

        # Add error feedback from previous attempt
        if previous_errors:
            lines.extend(
                [
                    "",
                    "## IMPORTANT: Previous Attempt Had Errors",
                    "Your previous response had formatting errors. Please fix them:",
                    "",
                ]
            )
            for error in previous_errors:
                lines.append(f"- {error}")
            lines.extend(
                [
                    "",
                    "Remember: ALL entity mentions MUST use [key:display] format!",
                    "Do NOT mention entity names without wrapping them in [key:name].",
                ]
            )

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
    game_time: str = "",
    game_period: str = "",
    game_day: int = 1,
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
        game_time=game_time,
        game_period=game_period,
        game_day=game_day,
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
