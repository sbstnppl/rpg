"""LLM-based item extraction from narrative text.

Uses a fast/cheap model (haiku) to extract physical items mentioned
in narrative, avoiding false positives like 'bewildering' or 'offering'.

This replaces the regex-based extraction in narrative_validator.py
which was prone to false positives (words ending in item-like suffixes).
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, Sequence

logger = logging.getLogger(__name__)


class ItemImportance(str, Enum):
    """How important an item is to gameplay.

    IMPORTANT: Functional items players can interact with (bucket, rope, washbasin).
               These should be spawned immediately.
    DECORATIVE: Atmospheric details that add flavor (pebbles, dust, cobwebs).
                These are tracked but spawned on-demand when player references them.
    REFERENCE: Items being talked about but not physically present in scene.
               These should not be validated or spawned.
    """

    IMPORTANT = "important"
    DECORATIVE = "decorative"
    REFERENCE = "reference"


@dataclass
class ExtractedItem:
    """An item extracted from narrative text.

    Attributes:
        name: The item name as mentioned in the narrative.
        importance: Gameplay importance classification.
        context: How the item appears in the narrative (e.g., "on shelf", "in corner").
        location: Where the item is located - REQUIRED, always infer from context.
                  This is a place you can go to (e.g., "the well", "the library").
        location_description: Precise placement within that location
                              (e.g., "on the shelf", "hanging from a hook").
        is_new: True if narrative introduces this as newly discovered/appearing.
    """

    name: str
    importance: ItemImportance
    context: str = ""
    location: str = ""  # Required - never null, always infer from context
    location_description: str = ""  # "on the shelf", "by the well", etc.
    is_new: bool = True


@dataclass
class ItemExtractionResult:
    """Result of extracting items from narrative.

    Attributes:
        items: List of extracted items with classifications.
        reasoning: Brief explanation of extraction logic (for debugging).
    """

    items: list[ExtractedItem] = field(default_factory=list)
    reasoning: str = ""


class LLMProviderProtocol(Protocol):
    """Protocol for LLM providers."""

    async def complete(
        self,
        messages: Sequence[Any],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        stop_sequences: Sequence[str] | None = None,
        system_prompt: str | None = None,
    ) -> Any:
        """Complete a prompt."""
        ...


EXTRACTION_PROMPT = """You are extracting PHYSICAL OBJECTS from narrative text for an RPG game.

NARRATIVE:
{narrative}

CURRENT SCENE LOCATION: {current_location}

EXTRACT items that are:
- Tangible physical objects the player could theoretically interact with
- Newly introduced or described in this text (not just referenced in passing)
- Specific items, not general categories

DO NOT extract:
- Abstract concepts or states (bewildering, offering, uncomfortable)
- Words that just END in item-like suffixes but aren't items (bewildering ends in "ring", but isn't a ring)
- Body parts or generic clothing descriptions ("rumpled tunic" when describing appearance)
- Buildings, rooms, or large structures (farmhouse, kitchen, well)
- Actions or verbs (washing, searching, looking)
- Seasons, times, weather (spring, morning, sunlight)
- Items only mentioned as memories or references to other places/times

CLASSIFY each item by importance:
- IMPORTANT: Functional items with clear use (containers, tools, weapons, furniture one can interact with)
  Examples: bucket, rope, washbasin, chair, lantern, key, book, chest
- DECORATIVE: Atmospheric details, often in groups or abstract (pebbles, dust, cobwebs, stains)
  Examples: pebbles around a well, dust on shelves, cobwebs in corners
- REFERENCE: Items talked about but NOT physically present in the current scene
  Examples: "the sword your father used to own", "the bucket that was stolen"

LOCATION (REQUIRED - every item must have a location):
Items always exist somewhere. Infer the location from context:
- Explicit: "bucket at the well" → location: "the well"
- Action context: "wash at the well using a washbasin" → location: "the well" (same action context)
- Scene default: "picks up a lantern" with no location context → location: current scene location
- Inferred: If an item logically belongs where the action happens, use that location

Locations are PLACES you can go to (the well, the library, the kitchen).
NOT furniture or surfaces (the shelf, the table, the corner) - those go in location_description.

LOCATION_DESCRIPTION (precise placement within the location):
Where exactly within that location is the item?
- "book on the shelf" → location_description: "on the shelf"
- "bucket by the well" → location_description: "by the well" or "beside the well"
- "lantern hanging from a hook" → location_description: "hanging from a hook"
- "coins scattered on the floor" → location_description: "scattered on the floor"
- If not specified, leave empty ""

This ensures consistency: if we say "book on the shelf", it stays on the shelf.

Respond ONLY with valid JSON:
{{
  "items": [
    {{
      "name": "item name",
      "importance": "important|decorative|reference",
      "context": "brief context from narrative",
      "location": "the location name (REQUIRED - never null)",
      "location_description": "where within the location (or empty string)",
      "is_new": true
    }}
  ],
  "reasoning": "Brief explanation"
}}

If no physical items are found, return: {{"items": [], "reasoning": "No physical items mentioned"}}
"""


class ItemExtractor:
    """Extracts physical items from narrative text using LLM.

    Uses a fast/cheap model for speed and cost efficiency.
    Falls back to empty result if LLM is unavailable or parsing fails.

    Example:
        extractor = ItemExtractor(llm_provider)
        result = await extractor.extract("You find a wooden bucket near the well.")
        # result.items = [ExtractedItem(name="bucket", importance=IMPORTANT, ...)]
    """

    def __init__(
        self,
        llm_provider: LLMProviderProtocol | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 500,
    ) -> None:
        """Initialize the extractor.

        Args:
            llm_provider: LLM provider for extraction. If None, returns empty results.
            model: Model to use (defaults to haiku for speed/cost).
            temperature: Low temperature for consistent extraction.
            max_tokens: Maximum tokens in response.
        """
        self.llm_provider = llm_provider
        self.model = model or "claude-3-5-haiku-20241022"
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def extract(
        self,
        narrative: str,
        current_location: str = "unknown",
    ) -> ItemExtractionResult:
        """Extract physical items from narrative text.

        Args:
            narrative: The narrative text to analyze.
            current_location: The current scene location for context-aware inference.
                              Items without explicit location will default to this.

        Returns:
            ItemExtractionResult with extracted items and reasoning.
        """
        # Skip very short narratives
        if len(narrative) < 20:
            return ItemExtractionResult(
                items=[],
                reasoning="Narrative too short for item extraction",
            )

        # If no LLM provider, return empty result
        if self.llm_provider is None:
            logger.warning("No LLM provider for item extraction, returning empty result")
            return ItemExtractionResult(
                items=[],
                reasoning="No LLM provider available",
            )

        try:
            return await self._extract_with_llm(narrative, current_location)
        except Exception as e:
            logger.warning(f"Item extraction failed: {e}")
            return ItemExtractionResult(
                items=[],
                reasoning=f"Extraction failed: {e}",
            )

    async def _extract_with_llm(
        self,
        narrative: str,
        current_location: str,
    ) -> ItemExtractionResult:
        """Extract items using LLM.

        Args:
            narrative: The narrative text.
            current_location: Current scene location for default item placement.

        Returns:
            ItemExtractionResult with extracted items.
        """
        from src.llm.message_types import Message

        prompt = EXTRACTION_PROMPT.format(
            narrative=narrative,
            current_location=current_location,
        )

        response = await self.llm_provider.complete(
            messages=[Message.user(prompt)],
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        # Extract text from response
        # LLMResponse uses 'content' attribute for text
        content = response.content if hasattr(response, "content") else str(response)

        # Parse JSON from response
        return self._parse_response(content)

    def _parse_response(self, content: str) -> ItemExtractionResult:
        """Parse LLM response into ItemExtractionResult.

        Args:
            content: Raw LLM response text.

        Returns:
            Parsed ItemExtractionResult.
        """
        try:
            # Find JSON in response
            json_start = content.find("{")
            json_end = content.rfind("}") + 1

            if json_start < 0 or json_end <= json_start:
                logger.warning("No JSON found in item extraction response")
                return ItemExtractionResult(
                    items=[],
                    reasoning="Failed to parse LLM response - no JSON found",
                )

            json_str = content[json_start:json_end]
            data = json.loads(json_str)

            items = []
            for item_data in data.get("items", []):
                if not isinstance(item_data, dict):
                    continue

                name = item_data.get("name", "").strip()
                if not name:
                    continue

                # Parse importance
                importance_str = item_data.get("importance", "important").lower()
                try:
                    importance = ItemImportance(importance_str)
                except ValueError:
                    importance = ItemImportance.IMPORTANT

                # Ensure location is never null - use empty string as fallback
                location = item_data.get("location") or ""
                if location == "null":
                    location = ""

                items.append(
                    ExtractedItem(
                        name=name,
                        importance=importance,
                        context=item_data.get("context", ""),
                        location=location,
                        location_description=item_data.get("location_description", ""),
                        is_new=item_data.get("is_new", True),
                    )
                )

            return ItemExtractionResult(
                items=items,
                reasoning=data.get("reasoning", ""),
            )

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error in item extraction: {e}")
            return ItemExtractionResult(
                items=[],
                reasoning=f"JSON parse error: {e}",
            )
        except (KeyError, TypeError) as e:
            logger.warning(f"Data structure error in item extraction: {e}")
            return ItemExtractionResult(
                items=[],
                reasoning=f"Data structure error: {e}",
            )
