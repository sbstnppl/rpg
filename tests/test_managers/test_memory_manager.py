"""Tests for MemoryManager."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.enums import EmotionalValence, MemoryType
from src.managers.memory_manager import MemoryManager
from tests.factories import (
    create_character_memory,
    create_entity,
    create_game_session,
)


class TestMemoryManagerCRUD:
    """Tests for MemoryManager CRUD operations."""

    def test_create_memory(self, db_session: Session, game_session) -> None:
        """Test creating a memory through the manager."""
        entity = create_entity(db_session, game_session)
        manager = MemoryManager(db_session, game_session)

        memory = manager.create_memory(
            entity_id=entity.id,
            subject="father's sword",
            subject_type=MemoryType.ITEM,
            keywords=["sword", "blade", "hilt"],
            valence=EmotionalValence.POSITIVE,
            emotion="pride",
            context="Inherited when he passed.",
            intensity=8,
        )

        assert memory.id is not None
        assert memory.entity_id == entity.id
        assert memory.subject == "father's sword"
        assert memory.intensity == 8

    def test_get_memory(self, db_session: Session, game_session) -> None:
        """Test retrieving a memory by ID."""
        entity = create_entity(db_session, game_session)
        memory = create_character_memory(db_session, game_session, entity)
        manager = MemoryManager(db_session, game_session)

        result = manager.get_memory(memory.id)
        assert result is not None
        assert result.id == memory.id

    def test_get_memory_not_found(
        self, db_session: Session, game_session
    ) -> None:
        """Test retrieving non-existent memory returns None."""
        manager = MemoryManager(db_session, game_session)
        result = manager.get_memory(99999)
        assert result is None

    def test_get_memories_for_entity(
        self, db_session: Session, game_session
    ) -> None:
        """Test getting all memories for an entity."""
        entity = create_entity(db_session, game_session)
        manager = MemoryManager(db_session, game_session)

        # Create multiple memories
        manager.create_memory(
            entity_id=entity.id,
            subject="memory 1",
            subject_type=MemoryType.ITEM,
            keywords=["one"],
            valence=EmotionalValence.POSITIVE,
            emotion="joy",
            context="test",
            intensity=5,
        )
        manager.create_memory(
            entity_id=entity.id,
            subject="memory 2",
            subject_type=MemoryType.PERSON,
            keywords=["two"],
            valence=EmotionalValence.NEGATIVE,
            emotion="grief",
            context="test",
            intensity=8,
        )

        memories = manager.get_memories_for_entity(entity.id)
        assert len(memories) == 2
        # Should be sorted by intensity (descending)
        assert memories[0].intensity >= memories[1].intensity

    def test_get_memories_with_filters(
        self, db_session: Session, game_session
    ) -> None:
        """Test getting memories with various filters."""
        entity = create_entity(db_session, game_session)
        manager = MemoryManager(db_session, game_session)

        # Create memories with different types/valences
        manager.create_memory(
            entity_id=entity.id,
            subject="positive item",
            subject_type=MemoryType.ITEM,
            keywords=["item"],
            valence=EmotionalValence.POSITIVE,
            emotion="joy",
            context="test",
            intensity=5,
        )
        manager.create_memory(
            entity_id=entity.id,
            subject="negative person",
            subject_type=MemoryType.PERSON,
            keywords=["person"],
            valence=EmotionalValence.NEGATIVE,
            emotion="grief",
            context="test",
            intensity=8,
        )

        # Filter by type
        items = manager.get_memories_for_entity(
            entity.id, subject_type=MemoryType.ITEM
        )
        assert len(items) == 1
        assert items[0].subject == "positive item"

        # Filter by valence
        negative = manager.get_memories_for_entity(
            entity.id, valence=EmotionalValence.NEGATIVE
        )
        assert len(negative) == 1
        assert negative[0].subject == "negative person"

        # Filter by minimum intensity
        intense = manager.get_memories_for_entity(entity.id, min_intensity=7)
        assert len(intense) == 1
        assert intense[0].intensity == 8

    def test_update_memory(self, db_session: Session, game_session) -> None:
        """Test updating a memory."""
        entity = create_entity(db_session, game_session)
        memory = create_character_memory(
            db_session, game_session, entity, intensity=5
        )
        manager = MemoryManager(db_session, game_session)

        updated = manager.update_memory(
            memory.id,
            emotion="nostalgia",
            intensity=8,
        )

        assert updated is not None
        assert updated.emotion == "nostalgia"
        assert updated.intensity == 8

    def test_update_memory_clamps_intensity(
        self, db_session: Session, game_session
    ) -> None:
        """Test that intensity is clamped to 1-10."""
        entity = create_entity(db_session, game_session)
        memory = create_character_memory(db_session, game_session, entity)
        manager = MemoryManager(db_session, game_session)

        # Try to set intensity too high
        updated = manager.update_memory(memory.id, intensity=100)
        assert updated.intensity == 10

        # Try to set intensity too low
        updated = manager.update_memory(memory.id, intensity=0)
        assert updated.intensity == 1

    def test_delete_memory(self, db_session: Session, game_session) -> None:
        """Test deleting a memory."""
        entity = create_entity(db_session, game_session)
        memory = create_character_memory(db_session, game_session, entity)
        memory_id = memory.id
        manager = MemoryManager(db_session, game_session)

        result = manager.delete_memory(memory_id)
        assert result is True

        # Verify deleted
        assert manager.get_memory(memory_id) is None

    def test_delete_nonexistent_memory(
        self, db_session: Session, game_session
    ) -> None:
        """Test deleting non-existent memory returns False."""
        manager = MemoryManager(db_session, game_session)
        result = manager.delete_memory(99999)
        assert result is False


class TestMemoryManagerMatching:
    """Tests for MemoryManager matching functionality."""

    def test_find_matching_memories(
        self, db_session: Session, game_session
    ) -> None:
        """Test finding memories that match text."""
        entity = create_entity(db_session, game_session)
        manager = MemoryManager(db_session, game_session)

        # Create memories with different keywords
        manager.create_memory(
            entity_id=entity.id,
            subject="mother's hat",
            subject_type=MemoryType.ITEM,
            keywords=["hat", "straw", "wide-brimmed"],
            valence=EmotionalValence.NEGATIVE,
            emotion="grief",
            context="test",
            intensity=8,
        )
        manager.create_memory(
            entity_id=entity.id,
            subject="red chicken",
            subject_type=MemoryType.CREATURE,
            keywords=["chicken", "red", "rooster"],
            valence=EmotionalValence.NEUTRAL,
            emotion="curiosity",
            context="test",
            intensity=3,
        )

        # Search for hat-related text
        matches = manager.find_matching_memories(
            entity.id, "a wide-brimmed straw hat on the hook"
        )
        assert len(matches) == 1
        assert matches[0][0].subject == "mother's hat"
        assert matches[0][1] > 0.5  # High relevance

    def test_find_matching_memories_min_relevance(
        self, db_session: Session, game_session
    ) -> None:
        """Test minimum relevance threshold filters results."""
        entity = create_entity(db_session, game_session)
        manager = MemoryManager(db_session, game_session)

        manager.create_memory(
            entity_id=entity.id,
            subject="test memory",
            subject_type=MemoryType.ITEM,
            keywords=["hat", "straw", "wide-brimmed", "summer", "garden"],
            valence=EmotionalValence.NEUTRAL,
            emotion="neutral",
            context="test",
            intensity=5,
        )

        # Low relevance match (only 1 of 5 keywords)
        matches = manager.find_matching_memories(
            entity.id, "a hat", min_relevance=0.5
        )
        assert len(matches) == 0  # Filtered out

        # Same search with lower threshold
        matches = manager.find_matching_memories(
            entity.id, "a hat", min_relevance=0.1
        )
        assert len(matches) == 1

    def test_find_memories_by_keyword(
        self, db_session: Session, game_session
    ) -> None:
        """Test finding memories by exact keyword."""
        entity = create_entity(db_session, game_session)
        manager = MemoryManager(db_session, game_session)

        manager.create_memory(
            entity_id=entity.id,
            subject="memory with hat",
            subject_type=MemoryType.ITEM,
            keywords=["hat", "straw"],
            valence=EmotionalValence.NEUTRAL,
            emotion="neutral",
            context="test",
            intensity=5,
        )
        manager.create_memory(
            entity_id=entity.id,
            subject="memory without hat",
            subject_type=MemoryType.ITEM,
            keywords=["sword", "blade"],
            valence=EmotionalValence.NEUTRAL,
            emotion="neutral",
            context="test",
            intensity=5,
        )

        matches = manager.find_memories_by_keyword(entity.id, "hat")
        assert len(matches) == 1
        assert matches[0].subject == "memory with hat"


class TestMemoryManagerTriggerTracking:
    """Tests for MemoryManager trigger tracking."""

    def test_record_trigger(self, db_session: Session, game_session) -> None:
        """Test recording a memory trigger."""
        entity = create_entity(db_session, game_session)
        memory = create_character_memory(db_session, game_session, entity)
        manager = MemoryManager(db_session, game_session)

        # Record trigger
        updated = manager.record_trigger(memory.id, turn=5)

        assert updated is not None
        assert updated.last_triggered_turn == 5
        assert updated.trigger_count == 1

        # Record another trigger
        updated = manager.record_trigger(memory.id, turn=10)
        assert updated.last_triggered_turn == 10
        assert updated.trigger_count == 2

    def test_record_trigger_uses_current_turn(
        self, db_session: Session, game_session
    ) -> None:
        """Test recording trigger uses current turn if not specified."""
        game_session.total_turns = 15
        entity = create_entity(db_session, game_session)
        memory = create_character_memory(db_session, game_session, entity)
        manager = MemoryManager(db_session, game_session)

        updated = manager.record_trigger(memory.id)
        assert updated.last_triggered_turn == 15

    def test_get_recently_triggered(
        self, db_session: Session, game_session
    ) -> None:
        """Test getting recently triggered memories."""
        game_session.total_turns = 20
        entity = create_entity(db_session, game_session)
        manager = MemoryManager(db_session, game_session)

        # Create memories with different trigger times
        mem1 = manager.create_memory(
            entity_id=entity.id,
            subject="recent trigger",
            subject_type=MemoryType.ITEM,
            keywords=["test"],
            valence=EmotionalValence.NEUTRAL,
            emotion="neutral",
            context="test",
            intensity=5,
        )
        mem1.last_triggered_turn = 18
        mem1.trigger_count = 1

        mem2 = manager.create_memory(
            entity_id=entity.id,
            subject="old trigger",
            subject_type=MemoryType.ITEM,
            keywords=["test"],
            valence=EmotionalValence.NEUTRAL,
            emotion="neutral",
            context="test",
            intensity=5,
        )
        mem2.last_triggered_turn = 5
        mem2.trigger_count = 1

        db_session.flush()

        recent = manager.get_recently_triggered(entity.id, within_turns=10)
        assert len(recent) == 1
        assert recent[0].subject == "recent trigger"

    def test_get_most_triggered(
        self, db_session: Session, game_session
    ) -> None:
        """Test getting most frequently triggered memories."""
        entity = create_entity(db_session, game_session)
        manager = MemoryManager(db_session, game_session)

        # Create memories with different trigger counts
        mem1 = manager.create_memory(
            entity_id=entity.id,
            subject="triggered 5 times",
            subject_type=MemoryType.ITEM,
            keywords=["test"],
            valence=EmotionalValence.NEUTRAL,
            emotion="neutral",
            context="test",
            intensity=5,
        )
        mem1.trigger_count = 5

        mem2 = manager.create_memory(
            entity_id=entity.id,
            subject="triggered 10 times",
            subject_type=MemoryType.ITEM,
            keywords=["test"],
            valence=EmotionalValence.NEUTRAL,
            emotion="neutral",
            context="test",
            intensity=5,
        )
        mem2.trigger_count = 10

        db_session.flush()

        most = manager.get_most_triggered(entity.id, limit=1)
        assert len(most) == 1
        assert most[0].subject == "triggered 10 times"


class TestMemoryManagerBulkOperations:
    """Tests for MemoryManager bulk operations."""

    def test_create_memories_from_extraction(
        self, db_session: Session, game_session
    ) -> None:
        """Test creating memories from extraction results."""
        entity = create_entity(db_session, game_session)
        manager = MemoryManager(db_session, game_session)

        extracted = [
            {
                "subject": "mother's hat",
                "subject_type": "item",
                "keywords": ["hat", "straw"],
                "valence": "negative",
                "emotion": "grief",
                "context": "Mother wore this before she died.",
                "intensity": 8,
            },
            {
                "subject": "childhood home",
                "subject_type": "place",
                "keywords": ["cottage", "village"],
                "valence": "positive",
                "emotion": "nostalgia",
                "context": "Where I grew up.",
                "intensity": 6,
            },
        ]

        created = manager.create_memories_from_extraction(
            entity_id=entity.id,
            extracted_memories=extracted,
            source="backstory",
        )

        assert len(created) == 2
        assert created[0].subject == "mother's hat"
        assert created[0].subject_type == MemoryType.ITEM
        assert created[1].subject == "childhood home"
        assert created[1].subject_type == MemoryType.PLACE

    def test_create_memories_from_extraction_skips_invalid(
        self, db_session: Session, game_session
    ) -> None:
        """Test that invalid entries are skipped."""
        entity = create_entity(db_session, game_session)
        manager = MemoryManager(db_session, game_session)

        extracted = [
            {
                "subject": "valid memory",
                "subject_type": "item",
                "keywords": ["test"],
                "valence": "positive",
                "emotion": "joy",
                "context": "test",
                "intensity": 5,
            },
            {
                "subject": "invalid type",
                "subject_type": "invalid_type",  # Invalid enum
                "keywords": ["test"],
                "valence": "positive",
                "emotion": "joy",
                "context": "test",
                "intensity": 5,
            },
        ]

        created = manager.create_memories_from_extraction(
            entity_id=entity.id,
            extracted_memories=extracted,
        )

        # Only the valid one should be created
        assert len(created) == 1
        assert created[0].subject == "valid memory"

    def test_get_memory_summary(
        self, db_session: Session, game_session
    ) -> None:
        """Test getting a summary of entity's memories."""
        entity = create_entity(db_session, game_session)
        manager = MemoryManager(db_session, game_session)

        # Create various memories
        manager.create_memory(
            entity_id=entity.id,
            subject="item 1",
            subject_type=MemoryType.ITEM,
            keywords=["test"],
            valence=EmotionalValence.POSITIVE,
            emotion="joy",
            context="test",
            intensity=9,
        )
        manager.create_memory(
            entity_id=entity.id,
            subject="item 2",
            subject_type=MemoryType.ITEM,
            keywords=["test"],
            valence=EmotionalValence.NEGATIVE,
            emotion="grief",
            context="test",
            intensity=7,
        )
        manager.create_memory(
            entity_id=entity.id,
            subject="person 1",
            subject_type=MemoryType.PERSON,
            keywords=["test"],
            valence=EmotionalValence.NEGATIVE,
            emotion="fear",
            context="test",
            intensity=5,
        )

        summary = manager.get_memory_summary(entity.id)

        assert summary["total_memories"] == 3
        assert summary["by_type"]["item"] == 2
        assert summary["by_type"]["person"] == 1
        assert summary["by_valence"]["positive"] == 1
        assert summary["by_valence"]["negative"] == 2
        assert len(summary["strongest_memories"]) == 3
        assert summary["strongest_memories"][0]["intensity"] == 9

    def test_get_memory_summary_empty(
        self, db_session: Session, game_session
    ) -> None:
        """Test summary for entity with no memories."""
        entity = create_entity(db_session, game_session)
        manager = MemoryManager(db_session, game_session)

        summary = manager.get_memory_summary(entity.id)

        assert summary["total_memories"] == 0
        assert summary["by_type"] == {}
        assert summary["strongest_memories"] == []
