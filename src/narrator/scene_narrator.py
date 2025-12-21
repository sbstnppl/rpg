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

# Pattern to match [key] references for stripping
KEY_PATTERN = re.compile(r"\[([a-z0-9_]+)\]")


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
        temperature: float = 0.7,
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

            # Collect errors for retry
            errors = validation.error_messages
            logger.warning(
                f"Narration validation failed (attempt {attempt + 1}): {errors}"
            )

        # All retries failed - use fallback
        logger.error("All narration attempts failed, using fallback")
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
        parts.append("## Atmosphere Details (use freely, no [key] needed)")
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
        parts.append("Write the narration now. Use [key] format for all entity references!")

        return "\n".join(parts)

    def _get_system_prompt(self) -> str:
        """Get the system prompt for narration."""
        return """You are the Narrator for a fantasy RPG.

Your ONLY job is to describe what exists. You CANNOT invent new things.

## Critical Rules

### Rule 1: Use [key] Format for ALL Entity References

When mentioning ANY entity (NPC, item, furniture), you MUST use the [key] format:

CORRECT:
"You see [marcus_001] sitting on [bed_001], reading [book_001]."

WRONG:
"You see Marcus sitting on the bed."
"You see your friend sitting on a wooden bed."

### Rule 2: ONLY Reference Entities from the Manifest

If it's not in the entity list provided, it DOES NOT EXIST.
Do not mention items, people, or objects not listed.

### Rule 3: You May Describe Entities Creatively

[marcus_001] can be described as:
- "your old friend [marcus_001]"
- "[marcus_001], looking tired but pleased"

But you MUST include the [key].

### Rule 4: Atmosphere Is Free

You may use atmosphere details (lighting, sounds, smells) without [key] format.

## Output Format

Write engaging, immersive prose with [key] markers embedded.
The [key] markers will be stripped before showing to the player."""

    def _strip_keys(self, text: str) -> str:
        """Strip [key] markers and replace with display names.

        Args:
            text: Text with [key] markers.

        Returns:
            Text with keys replaced by display names.
        """
        def replace_key(match: re.Match) -> str:
            key = match.group(1)
            if key in self.manifest.entities:
                return self.manifest.entities[key].display_name
            # Unknown key - just remove the brackets
            return key

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
