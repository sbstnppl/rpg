"""LLM-based location extraction from narrative text.

Uses a fast/cheap model (haiku) to extract locations mentioned in narrative,
enabling automatic world-building as the story unfolds.

When the narrator says "you see a butcher, a blacksmith, and the village square",
this extractor identifies those as distinct locations that should exist in the
game world.
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, Sequence

logger = logging.getLogger(__name__)


class LocationCategory(str, Enum):
    """Category of location for world organization."""

    WILDERNESS = "wilderness"  # Forests, trails, natural areas
    SETTLEMENT = "settlement"  # Towns, villages, cities
    ESTABLISHMENT = "establishment"  # Businesses, inns, shops
    INTERIOR = "interior"  # Rooms within buildings
    EXTERIOR = "exterior"  # Outdoor areas like wells, gardens, yards
    PUBLIC = "public"  # Squares, streets, markets


@dataclass
class ExtractedLocation:
    """A location extracted from narrative text.

    Attributes:
        name: The location name as mentioned in narrative (e.g., "the well").
        location_key: Suggested key in snake_case (e.g., "farmhouse_well").
        category: Type of location for organization.
        parent_hint: Inferred parent location from context (e.g., "farmhouse").
        description: Brief description from narrative context.
    """

    name: str
    location_key: str
    category: LocationCategory = LocationCategory.INTERIOR
    parent_hint: str | None = None
    description: str = ""


@dataclass
class LocationExtractionResult:
    """Result of extracting locations from narrative.

    Attributes:
        locations: List of extracted locations.
        reasoning: Brief explanation of extraction logic (for debugging).
    """

    locations: list[ExtractedLocation] = field(default_factory=list)
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


EXTRACTION_PROMPT = """You are extracting LOCATIONS from narrative text for an RPG game.

NARRATIVE:
{narrative}

KNOWN LOCATIONS (already exist, do not re-extract):
{known_locations}

EXTRACT locations that are:
- Named places the player could visit or interact with
- Newly mentioned in this text (not in known locations list)
- Specific places, not vague references

DO extract:
- Named buildings: "the butcher's shop", "the inn", "the blacksmith"
- Specific outdoor areas: "the well", "the village square", "the garden"
- Rooms or areas within buildings: "the common room", "the cellar"
- Natural landmarks: "the old oak tree", "the river crossing"

DO NOT extract:
- Vague/generic references: "a clearing", "some houses", "the road"
- Directions: "to the north", "behind you"
- Already known locations (check the list above)
- Player's current location (they're already there)
- Abstract concepts: "home", "safety"
- PHYSICAL OBJECTS or items: "bucket", "washbasin", "sword", "table"
  (these are items, not locations - only extract PLACES you can go to)

INFER parent location when context suggests it:
- "the well behind the farmhouse" → parent_hint: "farmhouse" or "family_farm"
- "the inn's common room" → parent_hint: "inn"
- "the village square" → parent_hint: "village" or settlement name

CATEGORIES:
- wilderness: forests, trails, natural areas
- settlement: towns, villages, cities as a whole
- establishment: businesses, inns, shops
- interior: rooms within buildings
- exterior: outdoor areas like wells, gardens, yards
- public: squares, streets, markets

Respond ONLY with valid JSON:
{{
  "locations": [
    {{
      "name": "the location name as mentioned",
      "location_key": "snake_case_key",
      "category": "exterior|interior|establishment|wilderness|settlement|public",
      "parent_hint": "parent location key or null",
      "description": "brief description from context"
    }}
  ],
  "reasoning": "Brief explanation"
}}

If no new locations found, return: {{"locations": [], "reasoning": "No new locations mentioned"}}
"""


class LocationExtractor:
    """Extracts locations from narrative text using LLM.

    Uses a fast/cheap model for speed and cost efficiency.
    Falls back to empty result if LLM is unavailable or parsing fails.

    Example:
        extractor = LocationExtractor(llm_provider)
        result = await extractor.extract(
            "You wash at the well behind the farmhouse.",
            known_locations=["farmhouse_kitchen", "family_farm"]
        )
        # result.locations = [ExtractedLocation(name="the well", ...)]
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
            model: Model to use (None = use provider's default).
            temperature: Low temperature for consistent extraction.
            max_tokens: Maximum tokens in response.
        """
        self.llm_provider = llm_provider
        self.model = model  # None = use provider's default model
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def extract(
        self,
        narrative: str,
        known_locations: list[str] | None = None,
    ) -> LocationExtractionResult:
        """Extract locations from narrative text.

        Args:
            narrative: The narrative text to analyze.
            known_locations: List of already-known location keys to avoid duplicates.

        Returns:
            LocationExtractionResult with extracted locations and reasoning.
        """
        # Skip very short narratives
        if len(narrative) < 20:
            return LocationExtractionResult(
                locations=[],
                reasoning="Narrative too short for location extraction",
            )

        # If no LLM provider, return empty result
        if self.llm_provider is None:
            logger.warning("No LLM provider for location extraction, returning empty")
            return LocationExtractionResult(
                locations=[],
                reasoning="No LLM provider available",
            )

        try:
            return await self._extract_with_llm(narrative, known_locations or [])
        except Exception as e:
            logger.warning(f"Location extraction failed: {e}")
            return LocationExtractionResult(
                locations=[],
                reasoning=f"Extraction failed: {e}",
            )

    async def _extract_with_llm(
        self,
        narrative: str,
        known_locations: list[str],
    ) -> LocationExtractionResult:
        """Extract locations using LLM.

        Args:
            narrative: The narrative text.
            known_locations: Already-known location keys.

        Returns:
            LocationExtractionResult with extracted locations.
        """
        from src.llm.message_types import Message

        # Format known locations for prompt
        known_str = ", ".join(known_locations) if known_locations else "(none)"

        prompt = EXTRACTION_PROMPT.format(
            narrative=narrative,
            known_locations=known_str,
        )

        response = await self.llm_provider.complete(
            messages=[Message.user(prompt)],
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        # Extract text from response
        content = response.content if hasattr(response, "content") else str(response)

        # Parse JSON from response
        return self._parse_response(content)

    def _parse_response(self, content: str) -> LocationExtractionResult:
        """Parse LLM response into LocationExtractionResult.

        Args:
            content: Raw LLM response text.

        Returns:
            Parsed LocationExtractionResult.
        """
        try:
            # Find JSON in response
            json_start = content.find("{")
            json_end = content.rfind("}") + 1

            if json_start < 0 or json_end <= json_start:
                logger.warning("No JSON found in location extraction response")
                return LocationExtractionResult(
                    locations=[],
                    reasoning="Failed to parse LLM response - no JSON found",
                )

            json_str = content[json_start:json_end]
            data = json.loads(json_str)

            locations = []
            for loc_data in data.get("locations", []):
                if not isinstance(loc_data, dict):
                    continue

                name = loc_data.get("name", "").strip()
                location_key = loc_data.get("location_key", "").strip()

                if not name or not location_key:
                    continue

                # Parse category
                category_str = loc_data.get("category", "interior").lower()
                try:
                    category = LocationCategory(category_str)
                except ValueError:
                    category = LocationCategory.INTERIOR

                locations.append(
                    ExtractedLocation(
                        name=name,
                        location_key=location_key,
                        category=category,
                        parent_hint=loc_data.get("parent_hint"),
                        description=loc_data.get("description", ""),
                    )
                )

            return LocationExtractionResult(
                locations=locations,
                reasoning=data.get("reasoning", ""),
            )

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error in location extraction: {e}")
            return LocationExtractionResult(
                locations=[],
                reasoning=f"JSON parse error: {e}",
            )
        except (KeyError, TypeError) as e:
            logger.warning(f"Data structure error in location extraction: {e}")
            return LocationExtractionResult(
                locations=[],
                reasoning=f"Data structure error: {e}",
            )
