"""Magic system database models."""

from enum import Enum

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base, TimestampMixin


class MagicTradition(str, Enum):
    """Types of magic traditions."""

    ARCANE = "arcane"  # Learned magic (wizards)
    DIVINE = "divine"  # Granted by deity (clerics)
    PRIMAL = "primal"  # Nature magic (druids)
    PSIONIC = "psionic"  # Mental powers (sci-fi/psions)
    OCCULT = "occult"  # Forbidden knowledge (warlocks)


class SpellSchool(str, Enum):
    """Schools of magic."""

    ABJURATION = "abjuration"  # Protection
    CONJURATION = "conjuration"  # Summoning
    DIVINATION = "divination"  # Knowledge
    ENCHANTMENT = "enchantment"  # Mind control
    EVOCATION = "evocation"  # Energy/damage
    ILLUSION = "illusion"  # Deception
    NECROMANCY = "necromancy"  # Death/undeath
    TRANSMUTATION = "transmutation"  # Transformation


class CastingTime(str, Enum):
    """Spell casting times."""

    ACTION = "action"
    BONUS = "bonus_action"
    REACTION = "reaction"
    RITUAL = "ritual"  # 10 minutes, no resource cost


class SpellDefinition(Base, TimestampMixin):
    """Template for a spell."""

    __tablename__ = "spell_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    spell_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Unique spell identifier within session",
    )
    display_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Human-readable spell name",
    )
    tradition: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Magic tradition: arcane, divine, primal, psionic, occult",
    )
    school: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Spell school: abjuration, conjuration, etc.",
    )
    level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Spell level (0 = cantrip, 1-9 = spell levels)",
    )
    base_cost: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Base mana cost to cast",
    )
    casting_time: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Casting time: action, bonus_action, reaction, ritual",
    )
    range_description: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Range: self, touch, 60 feet, etc.",
    )
    duration: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Duration: instantaneous, 1 minute, concentration, etc.",
    )
    components: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        comment="Required components: verbal, somatic, material",
    )
    material_component: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Specific material component if required",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full spell description",
    )
    effects: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        comment="Structured spell effects (damage, healing, conditions, etc.)",
    )
    scaling: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="How spell scales at higher levels",
    )

    # Relationships
    game_session = relationship("GameSession", back_populates="spell_definitions")

    __table_args__ = (
        {"comment": "Spell templates for the magic system"},
    )


class EntityMagicProfile(Base, TimestampMixin):
    """Magic capabilities for an entity."""

    __tablename__ = "entity_magic_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tradition: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Primary magic tradition",
    )
    max_mana: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Maximum mana pool",
    )
    current_mana: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Current mana available",
    )
    mana_regen_per_rest: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Mana restored per long rest",
    )
    known_spells: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        comment="List of spell_keys the entity knows",
    )
    prepared_spells: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="List of prepared spell_keys (for preparation casters)",
    )

    # Relationships
    game_session = relationship("GameSession", back_populates="entity_magic_profiles")
    entity = relationship("Entity", back_populates="magic_profile")

    __table_args__ = (
        {"comment": "Magic capabilities for entities"},
    )


class SpellCastRecord(Base, TimestampMixin):
    """History of spell casts."""

    __tablename__ = "spell_cast_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    caster_entity_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    spell_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="The spell that was cast",
    )
    turn_cast: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Game turn when spell was cast",
    )
    target_entity_keys: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        comment="Entity keys of targets",
    )
    mana_spent: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Mana consumed by this cast",
    )
    success: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment="Whether the spell succeeded",
    )
    outcome_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Description of spell outcome",
    )

    # Relationships
    game_session = relationship("GameSession", back_populates="spell_cast_records")
    caster = relationship("Entity", back_populates="spell_casts")

    __table_args__ = (
        {"comment": "History of spell casts"},
    )
