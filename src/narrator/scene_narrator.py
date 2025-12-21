"""SceneNarrator for Scene-First Architecture.

This module generates constrained narration from a scene manifest:
- Only references entities in the manifest using [key] format
- Validates output and retries on failure
- Strips [key] markers for display
- Falls back to safe narration if validation keeps failing

The narrator operates AFTER ScenePersister, using the manifest
to ensure all entity references are valid and persist properly.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from src.narrator.validator import NarratorValidator
from src.world.schemas import (
    NarrationContext,
    NarrationResult,
    NarrationType,
    NarratorManifest,
)

if TYPE_CHECKING:
    from src.llm.base import LLMProvider

logger = logging.getLogger(__name__)

# Pattern to match [key:text] references for stripping
# Captures: group(1)=key, group(2)=display text
KEY_PATTERN = re.compile(r"\[([a-z0-9_]+):([^\]]+)\]")


class SceneNarrator:
    """Generates constrained narration from scene manifests.

    This class:
    1. Calls LLM with manifest and narration type
    2. Validates output for [key] references
    3. Retries with error feedback if validation fails
    4. Falls back to safe narration after max retries
    5. Strips [key] markers for display

    Usage:
        narrator = SceneNarrator(manifest, llm_provider)
        result = await narrator.narrate(NarrationType.SCENE_ENTRY, context)
        print(result.display_text)  # Keys stripped
    """

    def __init__(
        self,
        manifest: NarratorManifest,
        llm_provider: LLMProvider | None = None,
        max_retries: int = 3,
        temperature: float = 0.4,  # Lower temp for more consistent [key] usage
    ) -> None:
        """Initialize SceneNarrator.

        Args:
            manifest: The narrator manifest with valid entities.
            llm_provider: Optional LLM provider for generation.
            max_retries: Maximum retry attempts on validation failure.
            temperature: LLM temperature for generation.
        """
        self.manifest = manifest
        self.llm_provider = llm_provider
        self.max_retries = max_retries
        self.temperature = temperature
        self.validator = NarratorValidator(manifest)

    async def narrate(
        self,
        narration_type: NarrationType,
        context: NarrationContext,
    ) -> NarrationResult:
        """Generate narration for the scene.

        Args:
            narration_type: Type of narration to generate.
            context: Additional context for narration.

        Returns:
            NarrationResult with display text and references.
        """
        if self.llm_provider is None:
            return self._generate_fallback(narration_type)

        # Try generating with retries
        errors: list[str] = []

        for attempt in range(self.max_retries):
            # Generate narration
            raw_output = await self._generate(
                narration_type,
                context.with_errors(errors) if errors else context,
            )

            # Validate output
            validation = self.validator.validate(raw_output)

            if validation.valid:
                # Success - strip keys and return
                display_text = self._strip_keys(raw_output)
                return NarrationResult(
                    display_text=display_text,
                    raw_output=raw_output,
                    entity_references=validation.references,
                    validation_passed=True,
                )

            # Collect errors for retry (debug level since output is still usable)
            errors = validation.error_messages
            logger.debug(
                f"Narration validation retry (attempt {attempt + 1}): {errors}"
            )

        # All retries failed - use fallback (debug level since fallback is usable)
        logger.debug("Narration validation exhausted retries, using fallback")
        fallback = self._generate_fallback(narration_type)
        fallback.validation_passed = False
        return fallback

    async def _generate(
        self,
        narration_type: NarrationType,
        context: NarrationContext,
    ) -> str:
        """Call LLM to generate narration.

        Args:
            narration_type: Type of narration.
            context: Narration context with any errors.

        Returns:
            Raw LLM output with [key] references.
        """
        from src.llm.message_types import Message

        prompt = self._build_prompt(narration_type, context)
        system_prompt = self._get_system_prompt()

        response = await self.llm_provider.complete(
            messages=[Message.user(prompt)],
            temperature=self.temperature,
            system_prompt=system_prompt,
        )

        return response.content

    def _build_prompt(
        self,
        narration_type: NarrationType,
        context: NarrationContext,
    ) -> str:
        """Build the prompt for narration.

        Args:
            narration_type: Type of narration.
            context: Narration context.

        Returns:
            Prompt string.
        """
        parts = []

        # Reference guide
        parts.append(self.manifest.get_reference_guide())
        parts.append("")

        # Atmosphere
        parts.append("## Atmosphere Details (use freely, no [key:text] needed)")
        parts.append(f"- Lighting: {self.manifest.atmosphere.lighting}")
        parts.append(f"- Sounds: {', '.join(self.manifest.atmosphere.sounds)}")
        parts.append(f"- Smells: {', '.join(self.manifest.atmosphere.smells)}")
        parts.append(f"- Temperature: {self.manifest.atmosphere.temperature}")
        parts.append(f"- Overall mood: {self.manifest.atmosphere.overall_mood}")
        parts.append("")

        # Narration type instructions
        parts.append(f"## Narration Type: {narration_type.value}")
        parts.append("")

        if narration_type == NarrationType.SCENE_ENTRY:
            parts.append(
                f"The player just entered {self.manifest.location_display}. "
                "Describe what they see, focusing on the overall impression."
            )
        elif narration_type == NarrationType.ACTION_RESULT:
            if context.player_action:
                parts.append(f"The player performed: {context.player_action}")
            if context.action_result:
                parts.append(f"Result: {context.action_result}")
            parts.append("Describe the outcome of this action.")
        elif narration_type == NarrationType.CLARIFICATION:
            if context.clarification_prompt:
                parts.append(f"Ask for clarification: {context.clarification_prompt}")
        elif narration_type == NarrationType.DIALOGUE:
            parts.append("Generate dialogue for the NPCs present.")

        parts.append("")

        # Error feedback for retries
        if context.previous_errors:
            parts.append("## IMPORTANT: Previous Attempt Had Errors")
            parts.append("")
            parts.append("Your previous output was rejected because:")
            for error in context.previous_errors:
                parts.append(f"- {error}")
            parts.append("")
            parts.append("Please correct these issues:")
            parts.append("- Use [key] format for ALL entity references")
            parts.append("- Only reference entities from the manifest above")
            parts.append("")

        parts.append("---")
        parts.append("")
        parts.append("REMINDER: Only use EXACT keys from the list above. Do not invent keys!")
        parts.append("Write the narration now:")

        return "\n".join(parts)

    def _get_system_prompt(self) -> str:
        """Get the system prompt for narration."""
        return """You are a narrator. You MUST use [key:text] format for ALL physical things.

## CRITICAL FORMAT REQUIREMENT

Every physical thing (furniture, item, person, building) MUST be written as:
[exact_key_from_manifest:display_text]

The key before : must EXACTLY match an entity key from the manifest.
The text after : is what readers will see.

## EXAMPLE

Given manifest entities: [cottage_001:cottage], [barn_001:barn], [chicken_001:chicken]

CORRECT OUTPUT:
"A weathered stone [cottage_001:cottage] stands at the center. Behind it, a wooden [barn_001:barn] houses the animals. A [chicken_001:chicken] pecks at the ground."

WRONG OUTPUT (will be rejected):
"A weathered stone cottage stands at the center. Behind it, a barn houses the animals. A chicken pecks at the ground."
↑ Missing [key:text] format! This WILL fail validation!

## RULES

1. EVERY physical object mentioned MUST use [key:text] format
2. The key MUST exactly match an entity from the manifest
3. Put adjectives BEFORE the bracket: "old wooden [barn_001:barn]" NOT "[barn_001:old wooden barn]"
4. Only atmosphere words (lighting, sounds, smells) skip [key:text]

## YOUR OUTPUT WILL BE VALIDATED

If you write "the cottage" without [cottage_001:cottage], your output will be REJECTED.
If you write "the barn" without [barn_001:barn], your output will be REJECTED.
EVERY physical thing needs [key:text]. No exceptions."""

    def _strip_keys(self, text: str) -> str:
        """Strip [key:text] markers, replacing with just the text.

        The narrator writes: "a weathered stone [cottage_001:cottage]"
        This becomes: "a weathered stone cottage"

        Args:
            text: Text with [key:text] markers.

        Returns:
            Text with [key:text] replaced by just the text portion.
        """
        def replace_key(match: re.Match) -> str:
            key = match.group(1)       # e.g., "cottage_001"
            display = match.group(2)   # e.g., "cottage"

            # Log warning if key doesn't exist (validator should catch this)
            if key not in self.manifest.entities:
                logger.warning(f"Unknown key in narration: {key}")

            # Return the display text as-is (narrator controls formatting)
            return display

        return KEY_PATTERN.sub(replace_key, text)

    def _generate_fallback(self, narration_type: NarrationType) -> NarrationResult:
        """Generate safe fallback narration without LLM.

        Args:
            narration_type: Type of narration.

        Returns:
            Simple, safe NarrationResult.
        """
        location = self.manifest.location_display
        mood = self.manifest.atmosphere.overall_mood
        lighting = self.manifest.atmosphere.lighting

        if narration_type == NarrationType.SCENE_ENTRY:
            display_text = f"You stand in {location}. {lighting.capitalize()} illuminates the {mood} space."
        elif narration_type == NarrationType.ACTION_RESULT:
            display_text = "You complete the action."
        elif narration_type == NarrationType.CLARIFICATION:
            display_text = "Could you clarify what you meant?"
        else:
            display_text = f"You are in {location}."

        return NarrationResult(
            display_text=display_text,
            raw_output=display_text,
            entity_references=[],
            validation_passed=True,
        )
