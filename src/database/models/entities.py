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

    # Appearance JSON (for extras and image generation cache)
    appearance: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Extended appearance data and setting-specific extras",
    )

    # Dedicated appearance columns (for queryability and type safety)
    # These are synced to appearance JSON via property setters
    age: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Numeric age in years",
    )
    age_apparent: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Apparent age description (e.g., 'early 20s', 'elderly')",
    )
    gender: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Gender identity (free-text for inclusivity)",
    )
    height: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Height (e.g., '5\\'10\"', 'tall', 'short')",
    )
    build: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Body build (e.g., 'athletic', 'slim', 'stocky')",
    )
    hair_color: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Hair color (e.g., 'blonde', 'dark brown')",
    )
    hair_style: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Hair style (e.g., 'long wavy', 'buzz cut', 'ponytail')",
    )
    eye_color: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Eye color (e.g., 'blue', 'brown', 'heterochromatic')",
    )
    skin_tone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Skin tone (e.g., 'fair', 'tan', 'dark', 'olive')",
    )
    species: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Species/race (e.g., 'human', 'half-elf', 'android')",
    )
    distinguishing_features: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Notable features (scars, tattoos, birthmarks, etc.)",
    )
    voice_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Voice characteristics (e.g., 'deep and gravelly', 'melodic')",
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
    hidden_backstory: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Secret backstory elements (destiny, hidden powers) - never shown to player",
    )

    # Hidden potential stats (innate genetic gifts, rolled randomly, never shown to player)
    # Used for character growth mechanics - current stats are calculated from these
    potential_strength: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Innate strength potential (hidden from player)",
    )
    potential_dexterity: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Innate dexterity potential (hidden from player)",
    )
    potential_constitution: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Innate constitution potential (hidden from player)",
    )
    potential_intelligence: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Innate intelligence potential (hidden from player)",
    )
    potential_wisdom: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Innate wisdom potential (hidden from player)",
    )
    potential_charisma: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Innate charisma potential (hidden from player)",
    )

    # Occupation data for attribute calculation
    occupation: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Primary occupation/profession (e.g., 'blacksmith', 'farmer', 'scholar')",
    )
    occupation_years: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Years spent in the occupation (affects attribute modifiers)",
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

    # List of appearance fields that sync to JSON
    APPEARANCE_FIELDS = [
        "age", "age_apparent", "gender", "height", "build",
        "hair_color", "hair_style", "eye_color", "skin_tone",
        "species", "distinguishing_features", "voice_description",
    ]

    def __repr__(self) -> str:
        return f"<Entity {self.entity_key} ({self.entity_type.value})>"

    def sync_appearance_to_json(self) -> None:
        """Sync all dedicated appearance columns to the JSON appearance field.

        Call this after bulk updates to ensure JSON stays in sync.
        The JSON field contains both the synced columns AND any extras.
        """
        if self.appearance is None:
            self.appearance = {}

        for field in self.APPEARANCE_FIELDS:
            value = getattr(self, field)
            if value is not None:
                self.appearance[field] = value
            elif field in self.appearance:
                # Remove from JSON if column is None
                del self.appearance[field]

    def set_appearance_field(self, field: str, value: str | int | None) -> None:
        """Set an appearance field and sync to JSON.

        Args:
            field: Field name (must be in APPEARANCE_FIELDS)
            value: Value to set (or None to clear)

        Raises:
            ValueError: If field is not a valid appearance field
        """
        if field not in self.APPEARANCE_FIELDS:
            raise ValueError(f"Unknown appearance field: {field}")

        setattr(self, field, value)

        # Sync to JSON
        if self.appearance is None:
            self.appearance = {}

        if value is not None:
            self.appearance[field] = value
        elif field in self.appearance:
            del self.appearance[field]

    def get_appearance_summary(self) -> str:
        """Generate a readable appearance summary for GM context.

        Returns:
            Human-readable description of the entity's appearance.
        """
        parts = []

        # Demographics
        if self.age:
            parts.append(f"{self.age} years old")
        elif self.age_apparent:
            parts.append(self.age_apparent)

        if self.gender:
            parts.append(self.gender)

        if self.species and self.species.lower() != "human":
            parts.append(self.species)

        # Physical
        if self.height:
            parts.append(self.height)
        if self.build:
            parts.append(f"{self.build} build")

        # Features
        features = []
        if self.hair_color or self.hair_style:
            hair = " ".join(filter(None, [self.hair_color, self.hair_style, "hair"]))
            features.append(hair)
        if self.eye_color:
            features.append(f"{self.eye_color} eyes")
        if self.skin_tone:
            features.append(f"{self.skin_tone} skin")

        if features:
            parts.append(", ".join(features))

        if self.distinguishing_features:
            parts.append(self.distinguishing_features)

        return ". ".join(parts) if parts else "No appearance description available."


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

    # Companion tracking (for NPCs traveling with player)
    is_companion: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether NPC is currently traveling with player (needs decay tracked)",
    )
    companion_since_turn: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Turn when NPC joined as companion",
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
