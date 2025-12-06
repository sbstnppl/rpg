"""Entity models (characters, NPCs, monsters)."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base, TimestampMixin
from src.database.models.enums import EntityType

if TYPE_CHECKING:
    from src.database.models.session import GameSession


class Entity(Base, TimestampMixin):
    """Base entity for all characters, creatures, and monsters."""

    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Identity
    entity_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Lowercase unique key (e.g., 'bartender_joe')",
    )
    display_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Display name (e.g., 'Joe the Bartender')",
    )
    entity_type: Mapped[EntityType] = mapped_column(
        Enum(EntityType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )

    # Appearance (persistent)
    appearance: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Physical description: height, build, hair, eyes, etc.",
    )

    # Background/personality
    background: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Character backstory",
    )
    personality_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Personality traits and quirks",
    )

    # Status
    is_alive: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Tracking
    first_appeared_turn: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Turn number when entity was first mentioned",
    )

    # Relationships
    session: Mapped["GameSession"] = relationship(
        back_populates="entities",
        foreign_keys=[session_id],
    )
    attributes: Mapped[list["EntityAttribute"]] = relationship(
        back_populates="entity",
        cascade="all, delete-orphan",
    )
    skills: Mapped[list["EntitySkill"]] = relationship(
        back_populates="entity",
        cascade="all, delete-orphan",
    )
    npc_extension: Mapped["NPCExtension | None"] = relationship(
        back_populates="entity",
        uselist=False,
        cascade="all, delete-orphan",
    )
    monster_extension: Mapped["MonsterExtension | None"] = relationship(
        back_populates="entity",
        uselist=False,
        cascade="all, delete-orphan",
    )
    schedules: Mapped[list["Schedule"]] = relationship(
        back_populates="entity",
        cascade="all, delete-orphan",
        foreign_keys="Schedule.entity_id",
    )

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("session_id", "entity_key", name="uq_entity_session_key"),
    )

    def __repr__(self) -> str:
        return f"<Entity {self.entity_key} ({self.entity_type.value})>"


class EntityAttribute(Base):
    """Flexible attribute system (not locked to D&D stats)."""

    __tablename__ = "entity_attributes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    attribute_key: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Attribute name: strength, charisma, magic_power, etc.",
    )
    value: Mapped[int] = mapped_column(
        nullable=False,
        comment="Current value",
    )
    max_value: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Maximum value (if applicable)",
    )
    temporary_modifier: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="Temporary buff/debuff",
    )

    # Relationships
    entity: Mapped["Entity"] = relationship(back_populates="attributes")

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("entity_id", "attribute_key", name="uq_entity_attribute"),
    )

    def __repr__(self) -> str:
        return f"<EntityAttribute {self.attribute_key}={self.value}>"


class EntitySkill(Base):
    """Skills an entity has learned."""

    __tablename__ = "entity_skills"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    skill_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Skill name: swordfighting, persuasion, lockpicking",
    )
    proficiency_level: Mapped[int] = mapped_column(
        default=1,
        nullable=False,
        comment="1-100 or level-based",
    )
    experience_points: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    # Relationships
    entity: Mapped["Entity"] = relationship(back_populates="skills")

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("entity_id", "skill_key", name="uq_entity_skill"),
    )

    def __repr__(self) -> str:
        return f"<EntitySkill {self.skill_key} L{self.proficiency_level}>"


class NPCExtension(Base, TimestampMixin):
    """NPC-specific data (schedules, jobs, hobbies)."""

    __tablename__ = "npc_extensions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Work/life
    job: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Occupation",
    )
    workplace: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Where they work",
    )
    home_location: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Where they live",
    )
    hobbies: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="List of hobbies",
    )

    # Current state
    current_activity: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="What they're currently doing",
    )
    current_location: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Where they currently are",
    )
    current_mood: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Current emotional state",
    )

    # Voice/speech
    speech_pattern: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="How they speak (accent, vocabulary, quirks)",
    )

    # Personality traits affecting relationship dynamics
    personality_traits: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Traits affecting relationships: suspicious, forgiving, shy, prideful, etc.",
    )

    # Relationships
    entity: Mapped["Entity"] = relationship(back_populates="npc_extension")

    def __repr__(self) -> str:
        return f"<NPCExtension entity={self.entity_id}>"


class MonsterExtension(Base, TimestampMixin):
    """Monster/Animal-specific data (combat stats, loot)."""

    __tablename__ = "monster_extensions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Combat
    is_hostile: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    challenge_rating: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Difficulty rating",
    )
    hit_points: Mapped[int] = mapped_column(
        default=10,
        nullable=False,
    )
    max_hit_points: Mapped[int] = mapped_column(
        default=10,
        nullable=False,
    )
    armor_class: Mapped[int] = mapped_column(
        default=10,
        nullable=False,
    )

    # Loot
    loot_table: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="[{item: name, chance: 0.5, amount: '1d10'}]",
    )

    # Behavior
    behavior_pattern: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="AI instructions for behavior",
    )

    # Relationships
    entity: Mapped["Entity"] = relationship(back_populates="monster_extension")

    def __repr__(self) -> str:
        return f"<MonsterExtension entity={self.entity_id} HP={self.hit_points}/{self.max_hit_points}>"


# Import Schedule here to avoid circular import at runtime
from src.database.models.world import Schedule
