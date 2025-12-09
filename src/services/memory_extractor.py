"""Memory extraction service for creating memories from gameplay and backstory.

This service uses LLM to analyze:
- Character backstory for significant memories
- Gameplay turns for memorable events
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from src.database.models.character_memory import CharacterMemory
from src.database.models.enums import EmotionalValence, MemoryType
from src.database.models.session import GameSession
from src.managers.memory_manager import MemoryManager


@dataclass
class ExtractedMemory:
    """Memory extracted from text before database insertion."""

    subject: str
    subject_type: str  # Will be converted to MemoryType
    keywords: list[str]
    valence: str  # Will be converted to EmotionalValence
    emotion: str
    context: str
    intensity: int  # 1-10


# Prompt templates for LLM extraction
BACKSTORY_EXTRACTION_PROMPT = """Analyze this character's backstory and extract significant memories that could trigger emotional reactions during gameplay.

CHARACTER BACKSTORY:
{backstory}

HIDDEN BACKSTORY (secrets the player doesn't know):
{hidden_backstory}

Extract memories that are:
1. Emotionally significant (people, places, events that shaped the character)
2. Visually/sensually memorable (specific objects, sounds, smells)
3. Traumatic or joyful experiences
4. Important relationships (living or dead)

For each memory, provide:
- subject: What is remembered (e.g., "mother's wide-brimmed straw hat")
- subject_type: One of [person, item, place, event, creature, concept]
- keywords: 3-5 words that would trigger this memory (e.g., ["hat", "straw", "wide-brimmed"])
- valence: One of [positive, negative, mixed, neutral]
- emotion: Primary emotion (grief, joy, fear, pride, nostalgia, guilt, love, anger, etc.)
- context: Brief explanation of why this is meaningful (1-2 sentences)
- intensity: 1-10 how strongly this affects the character

Return as JSON array. Focus on quality over quantity - extract 3-8 significant memories.

Example output:
[
  {{
    "subject": "mother's wide-brimmed straw hat",
    "subject_type": "item",
    "keywords": ["hat", "straw", "wide-brimmed", "summer"],
    "valence": "negative",
    "emotion": "grief",
    "context": "Mother wore this hat every summer before she died of fever when the character was 10.",
    "intensity": 8
  }},
  {{
    "subject": "the blacksmith forge",
    "subject_type": "place",
    "keywords": ["forge", "anvil", "hammer", "fire", "smith"],
    "valence": "positive",
    "emotion": "pride",
    "context": "Father's forge where the character learned their craft and received praise.",
    "intensity": 6
  }}
]

Now extract memories from the provided backstory:"""


GAMEPLAY_EXTRACTION_PROMPT = """Analyze this gameplay turn and determine if anything significant happened that should become a lasting memory for the character.

GM'S NARRATION:
{gm_response}

PLAYER'S ACTION:
{player_input}

Consider if any of these occurred:
1. First encounter with something unusual/remarkable
2. Major emotional event (betrayal, gift, loss, achievement)
3. Discovery of something beautiful/terrible/significant
4. Meeting someone who made a strong impression
5. Near-death experience or survival moment
6. Significant success or failure
7. Witnessing something extraordinary

If something memorable occurred, extract it. If this was routine, return empty array.

For memorable events, provide:
- subject: What should be remembered
- subject_type: One of [person, item, place, event, creature, concept]
- keywords: 3-5 matching keywords
- valence: One of [positive, negative, mixed, neutral]
- emotion: Primary emotion felt
- context: What happened and why it matters
- intensity: 1-10 significance

Return as JSON array (empty [] if nothing memorable):"""


class MemoryExtractor:
    """Extracts significant moments to create character memories.

    Uses LLM to analyze backstory and gameplay for memorable elements.
    """

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        llm_client: Any = None,
    ) -> None:
        """Initialize the MemoryExtractor.

        Args:
            db: Database session
            game_session: Current game session
            llm_client: LLM client for extraction (optional, for testing)
        """
        self.db = db
        self.game_session = game_session
        self.memory_manager = MemoryManager(db, game_session)
        self._llm_client = llm_client

    async def extract_from_backstory(
        self,
        entity_id: int,
        backstory: str,
        hidden_backstory: str = "",
    ) -> list[CharacterMemory]:
        """Extract memories from character backstory.

        Args:
            entity_id: The character entity ID
            backstory: Visible backstory text
            hidden_backstory: Hidden backstory (GM secrets)

        Returns:
            List of created CharacterMemory objects
        """
        # Build prompt
        prompt = BACKSTORY_EXTRACTION_PROMPT.format(
            backstory=backstory,
            hidden_backstory=hidden_backstory or "None provided.",
        )

        # Get LLM response
        extracted = await self._call_llm(prompt)

        # Convert to memories
        memories = self.memory_manager.create_memories_from_extraction(
            entity_id=entity_id,
            extracted_memories=extracted,
            source="backstory",
            created_turn=None,  # Backstory memories have no turn
        )

        return memories

    async def analyze_turn_for_memories(
        self,
        entity_id: int,
        gm_response: str,
        player_input: str,
        current_turn: int,
    ) -> list[CharacterMemory]:
        """Analyze a gameplay turn for memorable events.

        Called after each turn to detect significant moments worth remembering.

        Args:
            entity_id: The character entity ID
            gm_response: GM's narration for the turn
            player_input: Player's action/input
            current_turn: Current turn number

        Returns:
            List of created CharacterMemory objects (usually 0-1)
        """
        # Build prompt
        prompt = GAMEPLAY_EXTRACTION_PROMPT.format(
            gm_response=gm_response,
            player_input=player_input,
        )

        # Get LLM response
        extracted = await self._call_llm(prompt)

        if not extracted:
            return []

        # Convert to memories
        memories = self.memory_manager.create_memories_from_extraction(
            entity_id=entity_id,
            extracted_memories=extracted,
            source="gameplay",
            created_turn=current_turn,
        )

        return memories

    async def _call_llm(self, prompt: str) -> list[dict[str, Any]]:
        """Call LLM and parse response as JSON array.

        Args:
            prompt: The prompt to send

        Returns:
            Parsed list of memory dictionaries
        """
        if self._llm_client is None:
            # Without LLM client, return empty (for testing/offline)
            return []

        try:
            # Call LLM (implementation depends on provider)
            response = await self._llm_client.generate(
                prompt=prompt,
                system="You are a memory extraction assistant. Respond only with valid JSON arrays.",
                max_tokens=2000,
            )

            # Parse JSON from response
            import json

            # Try to extract JSON array from response
            text = response.strip()

            # Handle responses that might have extra text
            start_idx = text.find("[")
            end_idx = text.rfind("]") + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_str = text[start_idx:end_idx]
                return json.loads(json_str)

            return []

        except Exception:
            # Log error but don't crash - memories are optional enhancement
            return []

    def extract_from_backstory_sync(
        self,
        entity_id: int,
        backstory: str,
        hidden_backstory: str = "",
    ) -> list[ExtractedMemory]:
        """Synchronous backstory extraction using rule-based approach.

        This is a fallback when LLM is not available. Uses keyword patterns
        to identify potential memories.

        Args:
            entity_id: The character entity ID
            backstory: Combined backstory text
            hidden_backstory: Hidden backstory

        Returns:
            List of ExtractedMemory objects (not yet saved to DB)
        """
        memories: list[ExtractedMemory] = []
        text = f"{backstory} {hidden_backstory}".lower()

        # Pattern: Death/loss mentions
        death_keywords = ["died", "death", "killed", "lost", "passed away", "funeral"]
        for kw in death_keywords:
            if kw in text:
                memories.append(ExtractedMemory(
                    subject="deceased loved one",
                    subject_type="person",
                    keywords=["death", "grave", "memorial", "loss"],
                    valence="negative",
                    emotion="grief",
                    context="Memory of someone who passed away.",
                    intensity=7,
                ))
                break

        # Pattern: Trauma mentions
        trauma_keywords = ["fire", "burned", "attacked", "betrayed", "abandoned"]
        for kw in trauma_keywords:
            if kw in text:
                memories.append(ExtractedMemory(
                    subject=f"traumatic {kw} event",
                    subject_type="event",
                    keywords=[kw, "trauma", "fear", "nightmare"],
                    valence="negative",
                    emotion="fear",
                    context=f"Traumatic memory involving {kw}.",
                    intensity=8,
                ))
                break

        # Pattern: Positive family mentions
        family_keywords = ["mother", "father", "parent", "family", "sibling"]
        positive_indicators = ["loved", "taught", "happy", "fond", "remember"]
        for fam in family_keywords:
            if fam in text:
                is_positive = any(pos in text for pos in positive_indicators)
                if is_positive:
                    memories.append(ExtractedMemory(
                        subject=f"{fam}'s presence",
                        subject_type="person",
                        keywords=[fam, "family", "home", "childhood"],
                        valence="positive",
                        emotion="nostalgia",
                        context=f"Fond memories of {fam}.",
                        intensity=6,
                    ))
                    break

        # Pattern: Home/origin place
        place_keywords = ["village", "town", "city", "home", "homeland", "born"]
        for place in place_keywords:
            if place in text:
                memories.append(ExtractedMemory(
                    subject=f"childhood {place}",
                    subject_type="place",
                    keywords=[place, "home", "origin", "childhood"],
                    valence="mixed",
                    emotion="nostalgia",
                    context=f"Memory of {place} from childhood.",
                    intensity=5,
                ))
                break

        return memories

    def create_memories_from_extracted(
        self,
        entity_id: int,
        extracted: list[ExtractedMemory],
        source: str = "backstory",
        created_turn: int | None = None,
    ) -> list[CharacterMemory]:
        """Convert ExtractedMemory objects to database records.

        Args:
            entity_id: The character entity ID
            extracted: List of extracted memories
            source: Memory source
            created_turn: Turn number if from gameplay

        Returns:
            List of created CharacterMemory objects
        """
        created: list[CharacterMemory] = []

        for mem in extracted:
            try:
                subject_type = MemoryType(mem.subject_type)
                valence = EmotionalValence(mem.valence)

                memory = self.memory_manager.create_memory(
                    entity_id=entity_id,
                    subject=mem.subject,
                    subject_type=subject_type,
                    keywords=mem.keywords,
                    valence=valence,
                    emotion=mem.emotion,
                    context=mem.context,
                    source=source,
                    intensity=mem.intensity,
                    created_turn=created_turn,
                )
                created.append(memory)
            except (ValueError, KeyError):
                continue

        return created
