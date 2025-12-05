"""Relationship models for tracking attitudes between entities."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.database.models.entities import Entity
    from src.database.models.session import GameSession


class Relationship(Base, TimestampMixin):
    """Directional relationship between two entities."""

    __tablename__ = "relationships"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Direction: from_entity's attitude TOWARD to_entity
    from_entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    to_entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Has this entity met the other?
    knows: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Have they met?",
    )

    # Core metrics (0-100, starting at 50 = neutral)
    trust: Mapped[int] = mapped_column(
        default=50,
        nullable=False,
        comment="How much do they trust them? 0-100",
    )
    liking: Mapped[int] = mapped_column(
        default=50,
        nullable=False,
        comment="Do they like them? 0-100",
    )
    respect: Mapped[int] = mapped_column(
        default=50,
        nullable=False,
        comment="Do they respect them? 0-100",
    )
    romantic_interest: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="Romantic attraction? 0-100",
    )

    # Temporary modifiers (mood-based)
    mood_modifier: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="Temporary mood modifier -20 to +20",
    )
    mood_reason: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    mood_expires_turn: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Turn when mood modifier expires",
    )

    # Relationship metadata
    relationship_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="friend, rival, family, colleague, etc.",
    )
    relationship_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="dating, married, engaged, etc.",
    )

    # History
    first_met_turn: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Turn when they first met",
    )
    first_met_location: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    last_interaction_turn: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    # Relationships
    from_entity: Mapped["Entity"] = relationship(
        foreign_keys=[from_entity_id],
    )
    to_entity: Mapped["Entity"] = relationship(
        foreign_keys=[to_entity_id],
    )
    changes: Mapped[list["RelationshipChange"]] = relationship(
        back_populates="relationship",
        cascade="all, delete-orphan",
    )

    # Unique constraint
    __table_args__ = (
        UniqueConstraint(
            "session_id", "from_entity_id", "to_entity_id",
            name="uq_relationship_direction",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Relationship {self.from_entity_id}→{self.to_entity_id} "
            f"T:{self.trust} L:{self.liking} R:{self.respect}>"
        )


class RelationshipChange(Base):
    """Audit log for relationship changes."""

    __tablename__ = "relationship_changes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    relationship_id: Mapped[int] = mapped_column(
        ForeignKey("relationships.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # What changed
    dimension: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="trust, liking, respect, romantic_interest",
    )
    old_value: Mapped[int] = mapped_column(nullable=False)
    new_value: Mapped[int] = mapped_column(nullable=False)
    delta: Mapped[int] = mapped_column(nullable=False)

    # Why
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Why this change occurred",
    )

    # When
    turn_number: Mapped[int] = mapped_column(nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    relationship: Mapped["Relationship"] = relationship(back_populates="changes")

    def __repr__(self) -> str:
        return f"<RelationshipChange {self.dimension} {self.old_value}→{self.new_value}>"
