"""Tests for CharacterMemory model."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.character_memory import CharacterMemory
from src.database.models.enums import EmotionalValence, MemoryType
from tests.factories import (
    create_character_memory,
    create_entity,
    create_game_session,
)


class TestCharacterMemoryModel:
    """Tests for CharacterMemory database model."""

    def test_create_memory_with_defaults(
        self, db_session: Session, game_session
    ) -> None:
        """Test creating a memory with default values."""
        entity = create_entity(db_session, game_session)
        memory = create_character_memory(db_session, game_session, entity)

        assert memory.id is not None
        assert memory.entity_id == entity.id
        assert memory.session_id == game_session.id
        assert memory.subject == "mother's hat"
        assert memory.subject_type == MemoryType.ITEM
        assert memory.keywords == ["hat", "wide-brimmed", "straw"]
        assert memory.valence == EmotionalValence.NEGATIVE
        assert memory.emotion == "grief"
        assert memory.source == "backstory"
        assert memory.intensity == 7
        assert memory.trigger_count == 0

    def test_create_memory_with_custom_values(
        self, db_session: Session, game_session
    ) -> None:
        """Test creating a memory with custom values."""
        entity = create_entity(db_session, game_session)
        memory = create_character_memory(
            db_session,
            game_session,
            entity,
            subject="childhood home",
            subject_type=MemoryType.PLACE,
            keywords=["cottage", "garden", "village"],
            valence=EmotionalValence.POSITIVE,
            emotion="nostalgia",
            context="Where I grew up, happy memories.",
            source="gameplay",
            intensity=5,
            created_turn=10,
        )

        assert memory.subject == "childhood home"
        assert memory.subject_type == MemoryType.PLACE
        assert memory.keywords == ["cottage", "garden", "village"]
        assert memory.valence == EmotionalValence.POSITIVE
        assert memory.emotion == "nostalgia"
        assert memory.source == "gameplay"
        assert memory.intensity == 5
        assert memory.created_turn == 10

    def test_all_memory_types(self, db_session: Session, game_session) -> None:
        """Test all MemoryType enum values can be stored."""
        entity = create_entity(db_session, game_session)

        for memory_type in MemoryType:
            memory = create_character_memory(
                db_session,
                game_session,
                entity,
                subject=f"test {memory_type.value}",
                subject_type=memory_type,
            )
            assert memory.subject_type == memory_type

    def test_all_valence_types(self, db_session: Session, game_session) -> None:
        """Test all EmotionalValence enum values can be stored."""
        entity = create_entity(db_session, game_session)

        for valence in EmotionalValence:
            memory = create_character_memory(
                db_session,
                game_session,
                entity,
                subject=f"test {valence.value}",
                valence=valence,
            )
            assert memory.valence == valence

    def test_matches_keywords_basic(
        self, db_session: Session, game_session
    ) -> None:
        """Test keyword matching returns correct relevance."""
        entity = create_entity(db_session, game_session)
        memory = create_character_memory(
            db_session,
            game_session,
            entity,
            keywords=["hat", "straw", "wide-brimmed"],
        )

        # All keywords match
        assert memory.matches_keywords("a wide-brimmed straw hat") == 1.0

        # Two of three keywords match
        relevance = memory.matches_keywords("a straw hat")
        assert 0.6 <= relevance <= 0.7  # 2/3 ≈ 0.67

        # One keyword matches
        relevance = memory.matches_keywords("just a hat")
        assert 0.3 <= relevance <= 0.4  # 1/3 ≈ 0.33

        # No keywords match
        assert memory.matches_keywords("a sword and shield") == 0.0

    def test_matches_keywords_case_insensitive(
        self, db_session: Session, game_session
    ) -> None:
        """Test keyword matching is case insensitive."""
        entity = create_entity(db_session, game_session)
        memory = create_character_memory(
            db_session,
            game_session,
            entity,
            keywords=["Hat", "STRAW"],
        )

        assert memory.matches_keywords("a straw hat") > 0
        assert memory.matches_keywords("A STRAW HAT") > 0
        assert memory.matches_keywords("a Straw Hat") > 0

    def test_matches_keywords_empty(
        self, db_session: Session, game_session
    ) -> None:
        """Test keyword matching with empty keywords list."""
        entity = create_entity(db_session, game_session)
        memory = create_character_memory(
            db_session,
            game_session,
            entity,
            keywords=[],
        )

        assert memory.matches_keywords("anything") == 0.0

    def test_memory_repr(self, db_session: Session, game_session) -> None:
        """Test memory string representation."""
        entity = create_entity(db_session, game_session)
        memory = create_character_memory(
            db_session,
            game_session,
            entity,
            subject="test subject",
            emotion="joy",
            intensity=8,
        )

        repr_str = repr(memory)
        assert "CharacterMemory" in repr_str
        assert "test subject" in repr_str
        assert "joy" in repr_str
        assert "8" in repr_str

    def test_entity_cascade_delete(
        self, db_session: Session, game_session
    ) -> None:
        """Test memory is deleted when entity is deleted."""
        entity = create_entity(db_session, game_session)
        memory = create_character_memory(db_session, game_session, entity)
        memory_id = memory.id

        db_session.delete(entity)
        db_session.flush()

        # Memory should be deleted due to cascade
        result = db_session.query(CharacterMemory).filter(
            CharacterMemory.id == memory_id
        ).first()
        assert result is None

    def test_session_cascade_delete(
        self, db_session: Session
    ) -> None:
        """Test memory is deleted when session is deleted."""
        game_session = create_game_session(db_session)
        entity = create_entity(db_session, game_session)
        memory = create_character_memory(db_session, game_session, entity)
        memory_id = memory.id

        db_session.delete(game_session)
        db_session.flush()

        # Memory should be deleted due to cascade
        result = db_session.query(CharacterMemory).filter(
            CharacterMemory.id == memory_id
        ).first()
        assert result is None

    def test_trigger_tracking_fields(
        self, db_session: Session, game_session
    ) -> None:
        """Test trigger tracking fields update correctly."""
        entity = create_entity(db_session, game_session)
        memory = create_character_memory(db_session, game_session, entity)

        # Initially not triggered
        assert memory.last_triggered_turn is None
        assert memory.trigger_count == 0

        # Simulate trigger
        memory.last_triggered_turn = 5
        memory.trigger_count = 1
        db_session.flush()

        # Query back
        result = db_session.query(CharacterMemory).filter(
            CharacterMemory.id == memory.id
        ).first()
        assert result.last_triggered_turn == 5
        assert result.trigger_count == 1
