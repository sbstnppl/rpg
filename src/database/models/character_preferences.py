"""Character preferences and need modifier models."""

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
from src.database.models.enums import (
    AlcoholTolerance,
    DriveLevel,
    IntimacyStyle,
    ModifierSource,
    SocialTendency,
)

if TYPE_CHECKING:
    from src.database.models.entities import Entity


class CharacterPreferences(Base, TimestampMixin):
    """Character preferences for food, drink, intimacy, and social interactions.

    This table consolidates all character preferences into a single record,
    replacing the narrower IntimacyProfile table. It includes dedicated columns
    for common preferences and a flexible JSON column for setting-specific data.
    """

    __tablename__ = "character_preferences"

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

    # === FOOD PREFERENCES ===
    favorite_foods: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="List of preferred food types/items",
    )
    disliked_foods: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="List of disliked food types/items",
    )
    is_vegetarian: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_vegan: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    food_allergies: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Food allergies that cause adverse reactions",
    )

    # Food-related trait flags
    is_greedy_eater: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Eats faster, hunger decays 20-50% faster",
    )
    is_picky_eater: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Only likes specific foods, morale penalty for disliked",
    )

    # === DRINK PREFERENCES ===
    favorite_drinks: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="List of preferred drinks",
    )
    disliked_drinks: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="List of disliked drinks",
    )
    alcohol_tolerance: Mapped[AlcoholTolerance] = mapped_column(
        Enum(AlcoholTolerance, values_callable=lambda obj: [e.value for e in obj]),
        default=AlcoholTolerance.MODERATE,
        nullable=False,
        comment="How well they handle alcohol",
    )
    is_alcoholic: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Has alcohol addiction - may trigger alcohol_craving need",
    )
    is_teetotaler: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Refuses all alcohol",
    )

    # === INTIMACY PREFERENCES (migrated from IntimacyProfile) ===
    drive_level: Mapped[DriveLevel] = mapped_column(
        Enum(DriveLevel, values_callable=lambda obj: [e.value for e in obj]),
        default=DriveLevel.MODERATE,
        nullable=False,
        comment="Affects intimacy need decay rate",
    )
    drive_threshold: Mapped[int] = mapped_column(
        Integer,
        default=50,
        nullable=False,
        comment="When need triggers behavior (0-100)",
    )
    intimacy_style: Mapped[IntimacyStyle] = mapped_column(
        Enum(IntimacyStyle, values_callable=lambda obj: [e.value for e in obj]),
        default=IntimacyStyle.EMOTIONAL,
        nullable=False,
        comment="casual, emotional, monogamous, polyamorous",
    )
    attraction_preferences: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Preferred traits: {gender, age_range, traits}",
    )
    has_regular_partner: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_actively_seeking: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # === SOCIAL PREFERENCES ===
    social_tendency: Mapped[SocialTendency] = mapped_column(
        Enum(SocialTendency, values_callable=lambda obj: [e.value for e in obj]),
        default=SocialTendency.AMBIVERT,
        nullable=False,
        comment="introvert, ambivert, extrovert",
    )
    preferred_group_size: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
        comment="Optimal number of people in social settings",
    )
    is_social_butterfly: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Gains social faster, decays slower when alone",
    )
    is_loner: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Social need decays very slowly, prefers solitude",
    )

    # === STAMINA/ENERGY TRAITS ===
    has_high_stamina: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Fatigue accumulates slower",
    )
    has_low_stamina: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Fatigue accumulates faster",
    )
    is_insomniac: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Difficulty sleeping, fatigue recovery reduced",
    )
    is_heavy_sleeper: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Needs more sleep but recovers well",
    )

    # === FLEXIBLE JSON FOR SETTING-SPECIFIC PREFERENCES ===
    extra_preferences: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Setting-specific or unusual preferences",
    )

    # Relationships
    entity: Mapped["Entity"] = relationship(foreign_keys=[entity_id])

    def __repr__(self) -> str:
        return (
            f"<CharacterPreferences entity={self.entity_id} "
            f"social={self.social_tendency.value}>"
        )


class NeedModifier(Base, TimestampMixin):
    """Per-entity modifiers for need decay rates and intensity caps.

    Modifiers can come from multiple sources:
    - TRAIT: From character traits (e.g., greedy_eater -> hunger decay +35%)
    - AGE: From age-based calculations using normal distributions
    - ADAPTATION: From adaptation to circumstances over time
    - CUSTOM: Manually set by GM or game logic
    - TEMPORARY: Temporary effects (spells, drugs, conditions)
    """

    __tablename__ = "need_modifiers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    need_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Need to modify: hunger, fatigue, intimacy, etc.",
    )

    # Modifier source for audit/display
    modifier_source: Mapped[ModifierSource] = mapped_column(
        Enum(ModifierSource, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        comment="Source: trait, age, adaptation, custom, temporary",
    )
    source_detail: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Specific source (e.g., 'greedy_eater', 'age_18')",
    )

    # The actual modifiers
    decay_rate_multiplier: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
        comment="Multiplier for decay rate (1.0=normal, 1.5=50% faster)",
    )
    satisfaction_multiplier: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
        comment="Multiplier for satisfaction amount",
    )
    max_intensity_cap: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum need intensity (0-100, None=uncapped)",
    )
    threshold_adjustment: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Adjust urgency threshold (+/- points)",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    expires_at_turn: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Turn when modifier expires (None=permanent)",
    )

    # Relationships
    entity: Mapped["Entity"] = relationship(foreign_keys=[entity_id])

    __table_args__ = (
        UniqueConstraint(
            "entity_id", "need_name", "modifier_source", "source_detail",
            name="uq_need_modifier"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<NeedModifier entity={self.entity_id} "
            f"need={self.need_name} decay={self.decay_rate_multiplier}>"
        )


class NeedAdaptation(Base, TimestampMixin):
    """Tracks adaptation to circumstances affecting need baselines.

    Over time, characters can adapt to their environment:
    - A child separated from parents may adapt to lower social connection
    - Someone living rough may adapt to lower comfort expectations
    - Extended solitude may reduce social needs

    Adaptations can be:
    - Gradual (over days/weeks) or sudden (traumatic events)
    - Reversible or permanent
    - Positive (increased expectations) or negative (lowered expectations)
    """

    __tablename__ = "need_adaptations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    need_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Need being adapted: social_connection, comfort, etc.",
    )

    # The adaptation delta (cumulative changes to baseline expectation)
    adaptation_delta: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Change to baseline (-20=lowered expectations by 20)",
    )

    # Context about the adaptation
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Why adaptation occurred",
    )
    trigger_event: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Specific event that triggered adaptation",
    )

    # Timeline
    started_turn: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="Turn when adaptation started",
    )
    completed_turn: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Turn when adaptation was fully integrated",
    )
    is_gradual: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether this was gradual or sudden",
    )
    duration_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="How many days the adaptation took",
    )

    # Reversal tracking
    is_reversible: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    reversal_trigger: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="What would reverse this adaptation",
    )

    # Relationships
    entity: Mapped["Entity"] = relationship(foreign_keys=[entity_id])

    def __repr__(self) -> str:
        return (
            f"<NeedAdaptation entity={self.entity_id} "
            f"need={self.need_name} delta={self.adaptation_delta}>"
        )
