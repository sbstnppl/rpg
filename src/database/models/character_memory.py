"""Character memory model for emotional reactions to scene elements."""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base, TimestampMixin
from src.database.models.enums import EmotionalValence, MemoryType

if TYPE_CHECKING:
    from src.database.models.entities import Entity
    from src.database.models.session import GameSession


class CharacterMemory(Base, TimestampMixin):
    """Significant memories that can trigger emotional reactions.

    Memories are extracted from:
    - Character backstory during creation
    - Gameplay events (first encounters, emotional moments)

    They enable context-aware reactions when encountering related elements.
    """

    __tablename__ = "character_memories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # What is remembered
    subject: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="What is remembered: 'mother's hat', 'red chicken', 'house fire'",
    )
    subject_type: Mapped[MemoryType] = mapped_column(
        nullable=False,
        comment="Type of memory subject (person, item, place, event, creature, concept)",
    )
    keywords: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="Keywords for matching: ['hat', 'wide-brimmed', 'straw']",
    )

    # Emotional context
    valence: Mapped[EmotionalValence] = mapped_column(
        nullable=False,
        comment="Emotional direction: positive, negative, mixed, neutral",
    )
    emotion: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Primary emotion: 'grief', 'joy', 'fear', 'curiosity', 'nostalgia'",
    )
    context: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Why this is meaningful: 'Mother wore this hat every summer before she died'",
    )

    # Source and strength
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="backstory",
        comment="Where memory came from: 'backstory', 'gameplay', 'relationship'",
    )
    intensity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
        comment="How strongly this affects character (1-10)",
    )

    # Tracking
    created_turn: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Turn number when memory was created (null for backstory)",
    )
    last_triggered_turn: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Turn number when memory was last activated",
    )
    trigger_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="How many times this memory has been triggered",
    )

    # Relationships
    entity: Mapped["Entity"] = relationship(foreign_keys=[entity_id])
    session: Mapped["GameSession"] = relationship(foreign_keys=[session_id])

    def __repr__(self) -> str:
        return (
            f"<CharacterMemory entity={self.entity_id} "
            f"subject='{self.subject}' emotion='{self.emotion}' "
            f"intensity={self.intensity}>"
        )

    def matches_keywords(self, text: str) -> float:
        """Check if text matches any keywords, return relevance score.

        This is a simple keyword matching for quick filtering.
        Semantic matching should use LLM for better accuracy.

        Args:
            text: Text to check against keywords

        Returns:
            Relevance score 0.0-1.0 based on keyword matches
        """
        if not self.keywords:
            return 0.0

        text_lower = text.lower()
        matches = sum(1 for kw in self.keywords if kw.lower() in text_lower)

        if matches == 0:
            return 0.0

        # Score based on percentage of keywords matched
        return min(1.0, matches / len(self.keywords))
