"""Character memory management for emotional reactions."""

from typing import Any

from sqlalchemy.orm import Session

from src.database.models.character_memory import CharacterMemory
from src.database.models.enums import EmotionalValence, MemoryType
from src.database.models.session import GameSession
from src.managers.base import BaseManager


class MemoryManager(BaseManager):
    """Manages character memories for emotional scene reactions.

    Handles:
    - CRUD operations for CharacterMemory
    - Memory matching and retrieval
    - Trigger tracking and statistics
    """

    # =========================================================================
    # Memory CRUD
    # =========================================================================

    def get_memory(self, memory_id: int) -> CharacterMemory | None:
        """Get a specific memory by ID.

        Args:
            memory_id: The memory ID.

        Returns:
            CharacterMemory or None if not found.
        """
        return (
            self.db.query(CharacterMemory)
            .filter(
                CharacterMemory.id == memory_id,
                CharacterMemory.session_id == self.session_id,
            )
            .first()
        )

    def get_memories_for_entity(
        self,
        entity_id: int,
        subject_type: MemoryType | None = None,
        valence: EmotionalValence | None = None,
        source: str | None = None,
        min_intensity: int | None = None,
    ) -> list[CharacterMemory]:
        """Get all memories for an entity with optional filters.

        Args:
            entity_id: The entity ID.
            subject_type: Optional filter by memory type.
            valence: Optional filter by emotional valence.
            source: Optional filter by source (backstory, gameplay).
            min_intensity: Optional minimum intensity filter.

        Returns:
            List of matching CharacterMemory records.
        """
        query = self.db.query(CharacterMemory).filter(
            CharacterMemory.entity_id == entity_id,
            CharacterMemory.session_id == self.session_id,
        )

        if subject_type is not None:
            query = query.filter(CharacterMemory.subject_type == subject_type)
        if valence is not None:
            query = query.filter(CharacterMemory.valence == valence)
        if source is not None:
            query = query.filter(CharacterMemory.source == source)
        if min_intensity is not None:
            query = query.filter(CharacterMemory.intensity >= min_intensity)

        return query.order_by(CharacterMemory.intensity.desc()).all()

    def create_memory(
        self,
        entity_id: int,
        subject: str,
        subject_type: MemoryType,
        keywords: list[str],
        valence: EmotionalValence,
        emotion: str,
        context: str,
        source: str = "backstory",
        intensity: int = 5,
        created_turn: int | None = None,
    ) -> CharacterMemory:
        """Create a new character memory.

        Args:
            entity_id: The entity ID.
            subject: What is remembered (e.g., "mother's hat").
            subject_type: Type of memory (person, item, place, etc.).
            keywords: Keywords for matching.
            valence: Emotional direction (positive, negative, mixed, neutral).
            emotion: Primary emotion (grief, joy, fear, etc.).
            context: Why this is meaningful.
            source: Where memory came from (backstory, gameplay).
            intensity: How strongly this affects character (1-10).
            created_turn: Turn when created (None for backstory).

        Returns:
            Newly created CharacterMemory.
        """
        memory = CharacterMemory(
            entity_id=entity_id,
            session_id=self.session_id,
            subject=subject,
            subject_type=subject_type,
            keywords=keywords,
            valence=valence,
            emotion=emotion,
            context=context,
            source=source,
            intensity=self._clamp(intensity, 1, 10),
            created_turn=created_turn,
            trigger_count=0,
        )
        self.db.add(memory)
        self.db.flush()
        return memory

    def update_memory(
        self,
        memory_id: int,
        **updates: Any,
    ) -> CharacterMemory | None:
        """Update a memory's fields.

        Args:
            memory_id: The memory ID.
            **updates: Fields to update.

        Returns:
            Updated CharacterMemory or None if not found.
        """
        memory = self.get_memory(memory_id)
        if memory is None:
            return None

        for key, value in updates.items():
            if hasattr(memory, key):
                if key == "intensity":
                    value = self._clamp(value, 1, 10)
                setattr(memory, key, value)

        self.db.flush()
        return memory

    def delete_memory(self, memory_id: int) -> bool:
        """Delete a memory by ID.

        Args:
            memory_id: The memory ID.

        Returns:
            True if deleted, False if not found.
        """
        result = (
            self.db.query(CharacterMemory)
            .filter(
                CharacterMemory.id == memory_id,
                CharacterMemory.session_id == self.session_id,
            )
            .delete()
        )
        self.db.flush()
        return result > 0

    # =========================================================================
    # Memory Matching
    # =========================================================================

    def find_matching_memories(
        self,
        entity_id: int,
        text: str,
        min_relevance: float = 0.3,
    ) -> list[tuple[CharacterMemory, float]]:
        """Find memories that match the given text using keyword matching.

        This is a quick filter - semantic matching should use LLM.

        Args:
            entity_id: The entity ID.
            text: Text to match against (e.g., item description).
            min_relevance: Minimum relevance score to include.

        Returns:
            List of (CharacterMemory, relevance_score) tuples, sorted by score.
        """
        memories = self.get_memories_for_entity(entity_id)
        matches: list[tuple[CharacterMemory, float]] = []

        for memory in memories:
            relevance = memory.matches_keywords(text)
            if relevance >= min_relevance:
                matches.append((memory, relevance))

        # Sort by relevance (highest first)
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches

    def find_memories_by_keyword(
        self,
        entity_id: int,
        keyword: str,
    ) -> list[CharacterMemory]:
        """Find memories containing a specific keyword.

        Args:
            entity_id: The entity ID.
            keyword: Keyword to search for.

        Returns:
            List of memories containing the keyword.
        """
        keyword_lower = keyword.lower()
        memories = self.get_memories_for_entity(entity_id)
        return [
            m for m in memories
            if any(kw.lower() == keyword_lower for kw in m.keywords)
        ]

    # =========================================================================
    # Trigger Tracking
    # =========================================================================

    def record_trigger(
        self,
        memory_id: int,
        turn: int | None = None,
    ) -> CharacterMemory | None:
        """Record that a memory was triggered.

        Updates last_triggered_turn and increments trigger_count.

        Args:
            memory_id: The memory ID.
            turn: Turn number (defaults to current turn).

        Returns:
            Updated CharacterMemory or None if not found.
        """
        memory = self.get_memory(memory_id)
        if memory is None:
            return None

        memory.last_triggered_turn = turn or self.current_turn
        memory.trigger_count += 1
        self.db.flush()
        return memory

    def get_recently_triggered(
        self,
        entity_id: int,
        within_turns: int = 10,
    ) -> list[CharacterMemory]:
        """Get memories triggered within recent turns.

        Useful for avoiding repetitive reactions.

        Args:
            entity_id: The entity ID.
            within_turns: How many turns back to check.

        Returns:
            List of recently triggered memories.
        """
        cutoff_turn = self.current_turn - within_turns
        return (
            self.db.query(CharacterMemory)
            .filter(
                CharacterMemory.entity_id == entity_id,
                CharacterMemory.session_id == self.session_id,
                CharacterMemory.last_triggered_turn is not None,
                CharacterMemory.last_triggered_turn >= cutoff_turn,
            )
            .order_by(CharacterMemory.last_triggered_turn.desc())
            .all()
        )

    def get_most_triggered(
        self,
        entity_id: int,
        limit: int = 5,
    ) -> list[CharacterMemory]:
        """Get the most frequently triggered memories.

        Args:
            entity_id: The entity ID.
            limit: Maximum number to return.

        Returns:
            List of memories sorted by trigger count.
        """
        return (
            self.db.query(CharacterMemory)
            .filter(
                CharacterMemory.entity_id == entity_id,
                CharacterMemory.session_id == self.session_id,
            )
            .order_by(CharacterMemory.trigger_count.desc())
            .limit(limit)
            .all()
        )

    # =========================================================================
    # Bulk Operations
    # =========================================================================

    def create_memories_from_extraction(
        self,
        entity_id: int,
        extracted_memories: list[dict[str, Any]],
        source: str = "backstory",
        created_turn: int | None = None,
    ) -> list[CharacterMemory]:
        """Create multiple memories from LLM extraction results.

        Expected dict format:
        {
            "subject": "mother's hat",
            "subject_type": "item",
            "keywords": ["hat", "wide-brimmed", "straw"],
            "valence": "negative",
            "emotion": "grief",
            "context": "Mother wore this...",
            "intensity": 8
        }

        Args:
            entity_id: The entity ID.
            extracted_memories: List of memory dictionaries.
            source: Source for all memories.
            created_turn: Turn for all memories.

        Returns:
            List of created CharacterMemory records.
        """
        created: list[CharacterMemory] = []

        for mem_data in extracted_memories:
            try:
                # Parse enums
                subject_type = MemoryType(mem_data.get("subject_type", "item"))
                valence = EmotionalValence(mem_data.get("valence", "neutral"))

                memory = self.create_memory(
                    entity_id=entity_id,
                    subject=mem_data.get("subject", "unknown"),
                    subject_type=subject_type,
                    keywords=mem_data.get("keywords", []),
                    valence=valence,
                    emotion=mem_data.get("emotion", "curiosity"),
                    context=mem_data.get("context", ""),
                    source=source,
                    intensity=mem_data.get("intensity", 5),
                    created_turn=created_turn,
                )
                created.append(memory)
            except (ValueError, KeyError):
                # Skip invalid entries
                continue

        return created

    def get_memory_summary(self, entity_id: int) -> dict[str, Any]:
        """Get a summary of an entity's memories for context.

        Args:
            entity_id: The entity ID.

        Returns:
            Summary dictionary with counts and highlights.
        """
        memories = self.get_memories_for_entity(entity_id)

        if not memories:
            return {
                "total_memories": 0,
                "by_type": {},
                "by_valence": {},
                "strongest_memories": [],
            }

        # Count by type
        by_type: dict[str, int] = {}
        for m in memories:
            key = m.subject_type.value
            by_type[key] = by_type.get(key, 0) + 1

        # Count by valence
        by_valence: dict[str, int] = {}
        for m in memories:
            key = m.valence.value
            by_valence[key] = by_valence.get(key, 0) + 1

        # Get strongest memories
        strongest = sorted(memories, key=lambda m: m.intensity, reverse=True)[:3]

        return {
            "total_memories": len(memories),
            "by_type": by_type,
            "by_valence": by_valence,
            "strongest_memories": [
                {
                    "subject": m.subject,
                    "emotion": m.emotion,
                    "intensity": m.intensity,
                }
                for m in strongest
            ],
        }
