"""Vital state and death tracking models."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base, TimestampMixin
from src.database.models.enums import VitalStatus

if TYPE_CHECKING:
    from src.database.models.entities import Entity
    from src.database.models.session import GameSession


class EntityVitalState(Base, TimestampMixin):
    """Tracks character vital status, death, and revival history."""

    __tablename__ = "entity_vital_states"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Current vital status
    vital_status: Mapped[VitalStatus] = mapped_column(
        Enum(VitalStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=VitalStatus.HEALTHY,
        nullable=False,
        comment="Current state: healthy, wounded, critical, dying, dead, etc.",
    )

    # Dying mechanics
    death_saves_remaining: Mapped[int] = mapped_column(
        default=3,
        nullable=False,
        comment="Turns remaining to stabilize (3 by default)",
    )
    death_saves_failed: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="Number of failed death saves",
    )
    stabilized_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    stabilized_turn: Mapped[int | None] = mapped_column(nullable=True)

    # Death record
    is_dead: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    death_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    death_turn: Mapped[int | None] = mapped_column(nullable=True)
    death_cause: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="combat, illness, accident, old_age, etc.",
    )
    death_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Narrative description of death",
    )
    death_location: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Revival record
    has_been_revived: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    revival_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )
    last_revival_turn: Mapped[int | None] = mapped_column(nullable=True)
    revival_method: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="spell_name, medical_procedure, clone_restoration, etc.",
    )
    revival_cost: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="What was lost/spent in revival (components, CON, memories)",
    )

    # Sci-fi backup (optional)
    has_consciousness_backup: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    last_backup_turn: Mapped[int | None] = mapped_column(nullable=True)
    backup_location: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Where backup is stored",
    )

    # Relationships
    entity: Mapped["Entity"] = relationship(foreign_keys=[entity_id])

    def __repr__(self) -> str:
        status = self.vital_status.value
        if self.is_dead:
            revived = f" (revived {self.revival_count}x)" if self.has_been_revived else ""
            return f"<EntityVitalState entity={self.entity_id} DEAD{revived}>"
        return f"<EntityVitalState entity={self.entity_id} {status}>"
