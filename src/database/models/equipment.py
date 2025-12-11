"""Equipment definition models for weapons and armor.

These models define weapon and armor templates that can be referenced
by Item instances. They provide the mechanical properties needed for combat.
"""

from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
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

if TYPE_CHECKING:
    from src.database.models.session import GameSession


class DamageType(PyEnum):
    """Types of damage that can be dealt."""

    # Physical
    SLASHING = "slashing"
    PIERCING = "piercing"
    BLUDGEONING = "bludgeoning"

    # Elemental
    FIRE = "fire"
    COLD = "cold"
    LIGHTNING = "lightning"
    ACID = "acid"
    POISON = "poison"

    # Special
    PSYCHIC = "psychic"
    RADIANT = "radiant"
    NECROTIC = "necrotic"
    FORCE = "force"
    THUNDER = "thunder"


class WeaponProperty(PyEnum):
    """Weapon properties that affect usage."""

    # Melee properties
    FINESSE = "finesse"  # Can use DEX instead of STR
    HEAVY = "heavy"  # Small creatures have disadvantage
    LIGHT = "light"  # Usable for two-weapon fighting
    REACH = "reach"  # +5 ft melee range
    TWO_HANDED = "two_handed"  # Requires two hands
    VERSATILE = "versatile"  # Can use one or two hands

    # Ranged properties
    AMMUNITION = "ammunition"  # Requires ammo
    LOADING = "loading"  # Can only fire once per action
    THROWN = "thrown"  # Can be thrown

    # Special
    SPECIAL = "special"  # Has unique rules
    SILVERED = "silvered"  # Overcomes certain resistances
    MAGICAL = "magical"  # Counts as magical damage


class WeaponCategory(PyEnum):
    """Categories of weapons."""

    SIMPLE_MELEE = "simple_melee"
    SIMPLE_RANGED = "simple_ranged"
    MARTIAL_MELEE = "martial_melee"
    MARTIAL_RANGED = "martial_ranged"
    EXOTIC = "exotic"
    IMPROVISED = "improvised"
    NATURAL = "natural"  # Claws, bite, etc.


class WeaponRange(PyEnum):
    """Range type of weapon."""

    MELEE = "melee"  # Standard melee (5 ft)
    REACH = "reach"  # Extended melee (10 ft)
    RANGED = "ranged"  # Ranged only
    THROWN = "thrown"  # Can be thrown or used in melee


class ArmorCategory(PyEnum):
    """Categories of armor."""

    LIGHT = "light"  # Full DEX bonus to AC
    MEDIUM = "medium"  # Max +2 DEX bonus to AC
    HEAVY = "heavy"  # No DEX bonus to AC
    SHIELD = "shield"  # AC bonus, held in hand


class WeaponDefinition(Base, TimestampMixin):
    """Definition of a weapon type.

    This defines the template for a weapon. Actual weapon items reference
    this definition for their combat properties.
    """

    __tablename__ = "weapon_definitions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Identity
    weapon_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Unique key within session (e.g., 'longsword', 'shortbow')",
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Display name",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Classification
    category: Mapped[WeaponCategory] = mapped_column(
        Enum(WeaponCategory, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )

    # Damage
    damage_dice: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Damage dice notation (e.g., '1d8', '2d6')",
    )
    damage_type: Mapped[DamageType] = mapped_column(
        Enum(DamageType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    versatile_dice: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Damage dice when used two-handed (for versatile weapons)",
    )

    # Properties (stored as JSON list of property string values)
    properties: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="List of weapon property values (use WeaponProperty.value)",
    )

    # Range
    range_type: Mapped[WeaponRange] = mapped_column(
        Enum(WeaponRange, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=WeaponRange.MELEE,
    )
    range_normal: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Normal range in feet (for ranged/thrown)",
    )
    range_long: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Long range in feet (disadvantage beyond normal)",
    )

    # Physical properties
    weight: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Weight in pounds",
    )

    # Relationships
    session: Mapped["GameSession"] = relationship()

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("session_id", "weapon_key", name="uq_weapon_definition_key"),
    )

    def __repr__(self) -> str:
        return f"<WeaponDefinition {self.weapon_key}: {self.name}>"


class ArmorDefinition(Base, TimestampMixin):
    """Definition of an armor type.

    This defines the template for armor. Actual armor items reference
    this definition for their defensive properties.
    """

    __tablename__ = "armor_definitions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Identity
    armor_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Unique key within session (e.g., 'leather', 'chainmail')",
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Display name",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Classification
    category: Mapped[ArmorCategory] = mapped_column(
        Enum(ArmorCategory, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )

    # Defense
    base_ac: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Base AC (or AC bonus for shields)",
    )
    max_dex_bonus: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum DEX bonus to AC (None = unlimited, 0 = none)",
    )

    # Requirements
    strength_required: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Minimum STR to wear without speed penalty",
    )

    # Penalties
    stealth_disadvantage: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Disadvantage on stealth checks",
    )

    # Physical properties
    weight: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Weight in pounds",
    )

    # Relationships
    session: Mapped["GameSession"] = relationship()

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("session_id", "armor_key", name="uq_armor_definition_key"),
    )

    def __repr__(self) -> str:
        return f"<ArmorDefinition {self.armor_key}: {self.name}>"
