"""Rumor system models.

Tracks rumors that spread through the game world, allowing player actions
to propagate through social networks with distortion over time.
"""

from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base

if TYPE_CHECKING:
    pass


class RumorSentiment(str, Enum):
    """Sentiment/tone of a rumor."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    SCANDALOUS = "scandalous"
    HEROIC = "heroic"


class Rumor(Base):
    """A rumor circulating in the game world.

    Rumors originate from events or player actions and spread through
    social networks. They can decay over time and become distorted
    as they pass from NPC to NPC.

    Attributes:
        rumor_key: Unique identifier for the rumor within session.
        subject_entity_key: Who/what the rumor is about.
        content: The rumor text in its original form.
        truth_value: 0.0 (completely false) to 1.0 (completely true).
        original_event_id: Optional link to WorldEvent that spawned it.
        origin_location_key: Where the rumor started.
        origin_turn: When the rumor started.
        spread_rate: How fast it propagates (0.1-1.0).
        decay_rate: How fast intensity fades per day (0.01-0.1).
        intensity: Current strength of the rumor (0.0-1.0).
        sentiment: Tone of the rumor (positive, negative, etc.).
        tags: Categorization tags (violence, romance, theft, etc.).
        is_active: Whether the rumor is still spreading.
    """

    __tablename__ = "rumors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("game_sessions.id"), nullable=False, index=True
    )
    rumor_key: Mapped[str] = mapped_column(String(100), nullable=False)
    subject_entity_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    content: Mapped[str] = mapped_column(String(1000), nullable=False)
    truth_value: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    original_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    origin_location_key: Mapped[str] = mapped_column(String(100), nullable=False)
    origin_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    spread_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    decay_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.05)
    intensity: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    sentiment: Mapped[RumorSentiment] = mapped_column(
        String(20), nullable=False, default=RumorSentiment.NEUTRAL
    )
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    known_by: Mapped[list["RumorKnowledge"]] = relationship(
        "RumorKnowledge", back_populates="rumor", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("session_id", "rumor_key", name="uq_rumor_session_key"),
    )


class RumorKnowledge(Base):
    """Tracks which NPCs know which rumors.

    Each NPC can have their own version of a rumor (local_distortion)
    and may or may not believe it or spread it further.

    Attributes:
        rumor_id: The rumor this knowledge refers to.
        entity_key: The NPC who knows this rumor.
        learned_turn: When they heard it.
        believed: Whether they believe it's true.
        will_spread: Whether they'll tell others.
        local_distortion: Their personal version of the rumor (if modified).
    """

    __tablename__ = "rumor_knowledge"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("game_sessions.id"), nullable=False, index=True
    )
    rumor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("rumors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    learned_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    believed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    will_spread: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    local_distortion: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Relationships
    rumor: Mapped["Rumor"] = relationship("Rumor", back_populates="known_by")

    __table_args__ = (
        UniqueConstraint(
            "session_id", "rumor_id", "entity_key", name="uq_rumor_knowledge_entity"
        ),
    )
