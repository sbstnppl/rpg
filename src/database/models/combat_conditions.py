"""Combat conditions model.

Tracks active combat conditions on entities like prone, stunned,
grappled, etc.
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.database.models.entities import Entity
    from src.database.models.session import GameSession


class CombatCondition(PyEnum):
    """Combat conditions that affect entities."""

    # Movement conditions
    PRONE = "prone"  # Knocked down, disadvantage on attacks, melee advantage against
    GRAPPLED = "grappled"  # Speed becomes 0, can't move
    RESTRAINED = "restrained"  # Speed 0, attack disadvantage, advantage against
    PARALYZED = "paralyzed"  # Incapacitated, can't move or speak, auto-fail STR/DEX saves

    # Sensory conditions
    BLINDED = "blinded"  # Can't see, auto-fail sight checks, attack disadvantage
    DEAFENED = "deafened"  # Can't hear, auto-fail hearing checks
    INVISIBLE = "invisible"  # Can't be seen, attack advantage, attacks against disadvantage

    # Impairment conditions
    STUNNED = "stunned"  # Incapacitated, can't move, speak falteringly, auto-fail STR/DEX
    INCAPACITATED = "incapacitated"  # Can't take actions or reactions
    UNCONSCIOUS = "unconscious"  # Incapacitated, can't move, unaware, drop held items

    # Debuff conditions
    POISONED = "poisoned"  # Disadvantage on attacks and ability checks
    FRIGHTENED = "frightened"  # Disadvantage on checks/attacks while source visible
    CHARMED = "charmed"  # Can't attack charmer, charmer has advantage on social
    EXHAUSTED = "exhausted"  # Cumulative penalties (levels 1-6)

    # Special conditions
    CONCENTRATING = "concentrating"  # Maintaining a spell/ability
    PETRIFIED = "petrified"  # Turned to stone, incapacitated, resistance to all damage
    HIDDEN = "hidden"  # Unseen and unheard


class EntityCondition(Base, TimestampMixin):
    """An active condition on an entity.

    Tracks the condition, its duration, and source.
    """

    __tablename__ = "entity_conditions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Condition
    condition: Mapped[CombatCondition] = mapped_column(
        Enum(CombatCondition, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )

    # Duration (null = permanent until removed)
    duration_rounds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Total duration in rounds (null = permanent)",
    )
    rounds_remaining: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Rounds left (decremented each turn)",
    )

    # Source (who/what caused this condition)
    source_entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"),
        nullable=True,
        comment="Entity that caused this condition",
    )
    source_description: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Description of source (e.g., 'Ghoul's Paralysis')",
    )

    # Special: Exhaustion level (1-6)
    exhaustion_level: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="For exhaustion: level 1-6",
    )

    # Tracking
    applied_turn: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Turn number when applied",
    )

    # Relationships
    entity: Mapped["Entity"] = relationship(
        foreign_keys=[entity_id],
    )
    source_entity: Mapped["Entity | None"] = relationship(
        foreign_keys=[source_entity_id],
    )

    # Unique constraint - one instance of each condition per entity
    # (except exhaustion which stacks via level)
    __table_args__ = (
        UniqueConstraint(
            "entity_id", "condition",
            name="uq_entity_condition",
        ),
    )

    def __repr__(self) -> str:
        duration_str = f" ({self.rounds_remaining}r)" if self.rounds_remaining else ""
        level_str = f" L{self.exhaustion_level}" if self.exhaustion_level else ""
        return f"<EntityCondition {self.condition.value}{level_str}{duration_str}>"
