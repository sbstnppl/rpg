"""Destiny and prophecy system database models."""

from enum import Enum

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base, TimestampMixin


class ProphesyStatus(str, Enum):
    """Status of a prophecy."""

    ACTIVE = "active"  # Still in play
    FULFILLED = "fulfilled"  # Came true
    SUBVERTED = "subverted"  # Player avoided fate
    ABANDONED = "abandoned"  # No longer relevant


class DestinyElementType(str, Enum):
    """Types of destiny elements."""

    OMEN = "omen"  # Warning sign of things to come
    SIGN = "sign"  # Indicator of progress toward prophecy
    PORTENT = "portent"  # Major event indicator
    VISION = "vision"  # Direct revelation


class Prophesy(Base, TimestampMixin):
    """A prophecy or destiny to track.

    Prophecies have a player-visible text (what they hear) and
    a GM-only true meaning (actual interpretation). This allows
    for dramatic irony and unexpected fulfillments.
    """

    __tablename__ = "prophesies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Identity
    prophesy_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Unique prophecy identifier",
    )
    prophesy_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Prophecy text as the player hears it",
    )
    true_meaning: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="GM-only: actual interpretation of the prophecy",
    )

    # Source
    source: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Source of prophecy: oracle, ancient_tome, dying_seer, etc.",
    )
    delivered_turn: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Turn when prophecy was delivered to player",
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default=ProphesyStatus.ACTIVE.value,
        nullable=False,
        index=True,
        comment="Prophecy status: active, fulfilled, subverted, abandoned",
    )

    # Conditions (JSON lists)
    fulfillment_conditions: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        comment="Conditions that would fulfill this prophecy",
    )
    subversion_conditions: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        comment="Conditions that would allow avoiding this prophecy",
    )
    interpretation_hints: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        comment="Clues/hints for player interpretation",
    )

    # Resolution
    fulfilled_turn: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Turn when prophecy was resolved (fulfilled/subverted)",
    )
    resolution_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Description of how prophecy was resolved",
    )

    # Relationships
    game_session = relationship("GameSession", back_populates="prophesies")
    destiny_elements = relationship(
        "DestinyElement",
        back_populates="prophesy",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Prophesy {self.prophesy_key} ({self.status})>"


class DestinyElement(Base, TimestampMixin):
    """An omen, sign, or portent linked to a prophecy.

    Destiny elements are narrative beats that foreshadow or
    track progress toward prophecy fulfillment.
    """

    __tablename__ = "destiny_elements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Identity
    element_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Unique element identifier",
    )
    element_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Element type: omen, sign, portent, vision",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Description of the destiny element",
    )

    # Link to prophecy (optional)
    prophesy_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("prophesies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Linked prophecy (if any)",
    )

    # Witnesses
    witnessed_by: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        comment="Entity keys of those who witnessed this element",
    )

    # Timing and importance
    turn_occurred: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Turn when element occurred",
    )
    significance: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
        comment="Significance level 1-5 (5 = most significant)",
    )
    player_noticed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether player explicitly noticed this element",
    )

    # Relationships
    game_session = relationship("GameSession", back_populates="destiny_elements")
    prophesy = relationship("Prophesy", back_populates="destiny_elements")

    def __repr__(self) -> str:
        return f"<DestinyElement {self.element_key} ({self.element_type})>"
