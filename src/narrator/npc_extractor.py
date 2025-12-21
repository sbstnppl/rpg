"""LLM-based NPC extraction from narrative text.

Uses a fast/cheap model (haiku) to extract NPCs mentioned in narrative,
classifying them by importance level for spawn decisions.

Mirrors the item_extractor.py pattern for consistency.
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, Sequence

logger = logging.getLogger(__name__)


class NPCImportance(str, Enum):
    """How important an NPC is to gameplay.

    CRITICAL: NPCs the player must interact with (quest givers, blocking NPCs).
              These should be spawned immediately with full generation.
    SUPPORTING: Named NPCs adding scene depth (shopkeepers, guards, workers).
                These should be spawned immediately with full generation.
    BACKGROUND: Crowd/atmosphere NPCs ("some farmers", "a group of children").
                These are tracked but never spawned individually.
    REFERENCE: NPCs talked about but not physically present in scene.
               These should not be validated or spawned.
    """

    CRITICAL = "critical"
    SUPPORTING = "supporting"
    BACKGROUND = "background"
    REFERENCE = "reference"


@dataclass
class ExtractedNPC:
    """An NPC extracted from narrative text.

    Attributes:
        name: The NPC name/description as mentioned in narrative.
        importance: Gameplay importance classification.
        description: Brief physical/behavioral description from narrative.
        context: What the NPC is doing in the scene.
        location: Where the NPC is located.
        is_named: True if NPC has a proper name (not "a guard", "the merchant").
        gender_hint: Gender if discernible from narrative.
        occupation_hint: Occupation if mentioned.
        role_hint: Relationship to player (employer, guard, innkeeper, etc.).
        is_new: True if narrative introduces this NPC for the first time.
    """

    name: str
    importance: NPCImportance
    description: str = ""
    context: str = ""
    location: str = ""
    is_named: bool = False
    gender_hint: str | None = None
    occupation_hint: str | None = None
    role_hint: str | None = None
    is_new: bool = True


@dataclass
class NPCExtractionResult:
    """Result of extracting NPCs from narrative.

    Attributes:
        npcs: List of extracted NPCs with classifications.
        reasoning: Brief explanation of extraction logic (for debugging).
    """

    npcs: list[ExtractedNPC] = field(default_factory=list)
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


EXTRACTION_PROMPT = """You are extracting NPCs (non-player characters) from narrative text for an RPG game.

NARRATIVE:
{narrative}

CURRENT SCENE LOCATION: {current_location}
PLAYER CHARACTER NAME: {player_name}
KNOWN NPCS ALREADY IN SCENE: {known_npcs}

EXTRACT NPCs that are:
- Individual characters (not groups like "the crowd" or "some farmers")
- Present in the current scene (not just mentioned in memories)
- New to this scene (not already in KNOWN NPCS list)

DO NOT extract:
- The player character ({player_name})
- NPCs already listed in KNOWN NPCS
- Groups of unnamed people ("the villagers", "some guards", "a crowd")
- NPCs only mentioned as memories, rumors, or references to elsewhere
- Animals (those are handled separately)

CLASSIFY each NPC by importance:
- CRITICAL: NPCs that block story progress or initiate direct interaction with player
  Examples: A guard stopping you, a merchant offering a quest, someone speaking to you
- SUPPORTING: Named NPCs present in scene but not initiating interaction
  Examples: Master Aldric working in his field, a named shopkeeper behind the counter
- BACKGROUND: Unnamed, atmospheric NPCs that add scene depth
  Examples: "an old woman sweeping", "a drunk at the bar"
- REFERENCE: NPCs talked about but NOT physically present
  Examples: "your father who was imprisoned", "the king everyone fears"

NAME DETECTION:
- is_named=true: Has a proper name (Aldric, Marta, Lord Blackwood)
- is_named=false: Generic description ("the merchant", "a guard", "an old woman")

GENDER/OCCUPATION/ROLE hints:
- Infer from narrative context (wife, daughter, merchant, guard)
- role_hint is relationship TO PLAYER (employer, guard, innkeeper, stranger)

Respond ONLY with valid JSON:
{{
  "npcs": [
    {{
      "name": "how NPC is referred to",
      "importance": "critical|supporting|background|reference",
      "description": "brief physical/behavioral description",
      "context": "what they are doing",
      "location": "where they are",
      "is_named": true,
      "gender_hint": "male|female|unknown",
      "occupation_hint": "occupation if mentioned",
      "role_hint": "relationship to player",
      "is_new": true
    }}
  ],
  "reasoning": "Brief explanation"
}}

If no NPCs are found, return: {{"npcs": [], "reasoning": "No NPCs mentioned"}}
"""


class NPCExtractor:
    """Extracts NPCs from narrative text using LLM.

    Uses a fast/cheap model for speed and cost efficiency.
    Falls back to empty result if LLM is unavailable or parsing fails.

    Example:
        extractor = NPCExtractor(llm_provider)
        result = await extractor.extract(
            "Master Aldric greets you at the door.",
            current_location="farmhouse",
            player_name="Finn",
        )
        # result.npcs = [ExtractedNPC(name="Master Aldric", importance=CRITICAL, ...)]
    """

    def __init__(
        self,
        llm_provider: LLMProviderProtocol | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 800,
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
        current_location: str = "unknown",
        player_name: str = "the player",
        known_npcs: list[str] | None = None,
    ) -> NPCExtractionResult:
        """Extract NPCs from narrative text.

        Args:
            narrative: The narrative text to analyze.
            current_location: The current scene location for context.
            player_name: The player character's name to exclude.
            known_npcs: List of NPC names already present in scene.

        Returns:
            NPCExtractionResult with extracted NPCs and reasoning.
        """
        # Skip very short narratives
        if len(narrative) < 20:
            return NPCExtractionResult(
                npcs=[],
                reasoning="Narrative too short for NPC extraction",
            )

        # If no LLM provider, return empty result
        if self.llm_provider is None:
            logger.warning("No LLM provider for NPC extraction, returning empty result")
            return NPCExtractionResult(
                npcs=[],
                reasoning="No LLM provider available",
            )

        try:
            return await self._extract_with_llm(
                narrative, current_location, player_name, known_npcs or []
            )
        except Exception as e:
            logger.warning(f"NPC extraction failed: {e}")
            return NPCExtractionResult(
                npcs=[],
                reasoning=f"Extraction failed: {e}",
            )

    async def _extract_with_llm(
        self,
        narrative: str,
        current_location: str,
        player_name: str,
        known_npcs: list[str],
    ) -> NPCExtractionResult:
        """Extract NPCs using LLM.

        Args:
            narrative: The narrative text.
            current_location: Current scene location.
            player_name: Player character name to exclude.
            known_npcs: NPCs already in scene.

        Returns:
            NPCExtractionResult with extracted NPCs.
        """
        from src.llm.message_types import Message

        known_npcs_str = ", ".join(known_npcs) if known_npcs else "None"

        prompt = EXTRACTION_PROMPT.format(
            narrative=narrative,
            current_location=current_location,
            player_name=player_name,
            known_npcs=known_npcs_str,
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

    def _parse_response(self, content: str) -> NPCExtractionResult:
        """Parse LLM response into NPCExtractionResult.

        Args:
            content: Raw LLM response text.

        Returns:
            Parsed NPCExtractionResult.
        """
        try:
            # Find JSON in response
            json_start = content.find("{")
            json_end = content.rfind("}") + 1

            if json_start < 0 or json_end <= json_start:
                logger.warning("No JSON found in NPC extraction response")
                return NPCExtractionResult(
                    npcs=[],
                    reasoning="Failed to parse LLM response - no JSON found",
                )

            json_str = content[json_start:json_end]
            data = json.loads(json_str)

            npcs = []
            for npc_data in data.get("npcs", []):
                if not isinstance(npc_data, dict):
                    continue

                name = npc_data.get("name", "").strip()
                if not name:
                    continue

                # Parse importance
                importance_str = npc_data.get("importance", "supporting").lower()
                try:
                    importance = NPCImportance(importance_str)
                except ValueError:
                    importance = NPCImportance.SUPPORTING

                # Handle null values
                location = npc_data.get("location") or ""
                if location == "null":
                    location = ""

                gender_hint = npc_data.get("gender_hint")
                if gender_hint in ("null", "unknown", ""):
                    gender_hint = None

                occupation_hint = npc_data.get("occupation_hint")
                if occupation_hint in ("null", "", None):
                    occupation_hint = None

                role_hint = npc_data.get("role_hint")
                if role_hint in ("null", "", None):
                    role_hint = None

                npcs.append(
                    ExtractedNPC(
                        name=name,
                        importance=importance,
                        description=npc_data.get("description", ""),
                        context=npc_data.get("context", ""),
                        location=location,
                        is_named=npc_data.get("is_named", False),
                        gender_hint=gender_hint,
                        occupation_hint=occupation_hint,
                        role_hint=role_hint,
                        is_new=npc_data.get("is_new", True),
                    )
                )

            return NPCExtractionResult(
                npcs=npcs,
                reasoning=data.get("reasoning", ""),
            )

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error in NPC extraction: {e}")
            return NPCExtractionResult(
                npcs=[],
                reasoning=f"JSON parse error: {e}",
            )
        except (KeyError, TypeError) as e:
            logger.warning(f"Data structure error in NPC extraction: {e}")
            return NPCExtractionResult(
                npcs=[],
                reasoning=f"Data structure error: {e}",
            )
