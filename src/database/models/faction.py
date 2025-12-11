"""Faction and reputation models.

These models track factions in the game world and entity
reputation with each faction.
"""

from datetime import datetime
from enum import Enum as PyEnum
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


class ReputationTier(PyEnum):
    """Reputation standing tiers."""

    HATED = "hated"  # -100 to -75
    HOSTILE = "hostile"  # -74 to -50
    UNFRIENDLY = "unfriendly"  # -49 to -25
    NEUTRAL = "neutral"  # -24 to 24
    FRIENDLY = "friendly"  # 25 to 49
    HONORED = "honored"  # 50 to 74
    REVERED = "revered"  # 75 to 89
    EXALTED = "exalted"  # 90 to 100


class Faction(Base, TimestampMixin):
    """A faction or organization in the game world.

    Factions are session-scoped and can have relationships with
    each other (allies, rivals, vassals).
    """

    __tablename__ = "factions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Faction identity
    faction_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Unique key within session",
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Display name",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Faction description and background",
    )

    # Default reputation settings
    base_reputation: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Starting reputation for new entities (-100 to 100)",
    )
    is_hostile_by_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="If true, faction starts hostile to most entities",
    )

    # Faction status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether faction is currently active in the world",
    )

    # Relationships
    session: Mapped["GameSession"] = relationship(back_populates="factions")
    reputations: Mapped[list["EntityReputation"]] = relationship(
        back_populates="faction",
        cascade="all, delete-orphan",
    )
    # Relationships where this faction is the "from" side
    outgoing_relationships: Mapped[list["FactionRelationship"]] = relationship(
        back_populates="from_faction",
        foreign_keys="FactionRelationship.from_faction_id",
        cascade="all, delete-orphan",
    )

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("session_id", "faction_key", name="uq_faction_key"),
    )

    def __repr__(self) -> str:
        return f"<Faction {self.faction_key}: {self.name}>"


class FactionRelationship(Base, TimestampMixin):
    """Relationship between two factions.

    Tracks alliances, rivalries, vassalage, and other inter-faction
    relationships. These are directional (faction A's view of B).
    """

    __tablename__ = "faction_relationships"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    from_faction_id: Mapped[int] = mapped_column(
        ForeignKey("factions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    to_faction_id: Mapped[int] = mapped_column(
        ForeignKey("factions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationship type
    relationship_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="ally, rival, vassal, overlord, neutral, enemy, etc.",
    )

    # Relationships
    from_faction: Mapped["Faction"] = relationship(
        back_populates="outgoing_relationships",
        foreign_keys=[from_faction_id],
    )
    to_faction: Mapped["Faction"] = relationship(
        foreign_keys=[to_faction_id],
    )

    # Unique constraint - one relationship per direction
    __table_args__ = (
        UniqueConstraint(
            "from_faction_id", "to_faction_id",
            name="uq_faction_relationship_direction",
        ),
    )

    def __repr__(self) -> str:
        return f"<FactionRelationship {self.from_faction_id}→{self.to_faction_id}: {self.relationship_type}>"


class EntityReputation(Base, TimestampMixin):
    """Tracks an entity's reputation with a faction.

    Reputation ranges from -100 (hated) to +100 (exalted).
    """

    __tablename__ = "entity_reputations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    faction_id: Mapped[int] = mapped_column(
        ForeignKey("factions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Reputation value
    reputation: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Current reputation (-100 to 100)",
    )

    # Relationships
    faction: Mapped["Faction"] = relationship(back_populates="reputations")

    # Unique constraint - one reputation per entity per faction
    __table_args__ = (
        UniqueConstraint("entity_id", "faction_id", name="uq_entity_faction_reputation"),
    )

    def __repr__(self) -> str:
        return f"<EntityReputation entity={self.entity_id} faction={self.faction_id} rep={self.reputation}>"


class ReputationChange(Base):
    """Audit log for reputation changes."""

    __tablename__ = "reputation_changes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    entity_reputation_id: Mapped[int] = mapped_column(
        ForeignKey("entity_reputations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Change details
    old_value: Mapped[int] = mapped_column(nullable=False)
    new_value: Mapped[int] = mapped_column(nullable=False)
    delta: Mapped[int] = mapped_column(nullable=False)
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Why this change occurred",
    )

    # When
    turn_number: Mapped[int | None] = mapped_column(
        nullable=True,
        index=True,
        comment="Turn when change occurred",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    entity_reputation: Mapped["EntityReputation"] = relationship()

    def __repr__(self) -> str:
        return f"<ReputationChange {self.old_value}→{self.new_value} ({self.delta:+d})>"
