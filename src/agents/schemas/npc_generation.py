"""Pydantic schemas for NPC character generation.

These schemas define the structured output format for the NPC generator
agent's LLM calls when creating full character data for newly introduced NPCs.
"""

from typing import Literal

from pydantic import BaseModel, Field


class NPCAppearance(BaseModel):
    """Physical appearance details for an NPC.

    All 12 appearance fields that match the Entity model's dedicated columns.
    """

    age: int | None = Field(
        default=None,
        ge=0,
        le=1000,
        description="Actual age in years",
    )
    age_apparent: str | None = Field(
        default=None,
        description="Apparent age description (e.g., 'early 20s', 'middle-aged', 'elderly')",
    )
    gender: str | None = Field(
        default=None,
        description="Gender identity (free-text for inclusivity)",
    )
    height: str | None = Field(
        default=None,
        description="Height description (e.g., '5\\'10\"', 'tall', 'short')",
    )
    build: str | None = Field(
        default=None,
        description="Body build (e.g., 'athletic', 'slim', 'stocky', 'heavyset')",
    )
    hair_color: str | None = Field(
        default=None,
        description="Hair color (e.g., 'blonde', 'dark brown', 'gray', 'bald')",
    )
    hair_style: str | None = Field(
        default=None,
        description="Hair style (e.g., 'long wavy', 'buzz cut', 'ponytail', 'braided')",
    )
    eye_color: str | None = Field(
        default=None,
        description="Eye color (e.g., 'blue', 'brown', 'green', 'amber')",
    )
    skin_tone: str | None = Field(
        default=None,
        description="Skin tone (e.g., 'fair', 'tan', 'dark', 'olive', 'pale')",
    )
    species: str | None = Field(
        default=None,
        description="Species or race (e.g., 'human', 'half-elf', 'dwarf')",
    )
    distinguishing_features: str | None = Field(
        default=None,
        description="Notable physical marks (scars, tattoos, birthmarks, missing limbs)",
    )
    voice_description: str | None = Field(
        default=None,
        description="Voice characteristics (e.g., 'deep and gravelly', 'high-pitched', 'soft-spoken')",
    )


class NPCBackground(BaseModel):
    """Background information for an NPC."""

    backstory: str = Field(
        description="Brief backstory (2-3 sentences) explaining their role and history",
    )
    occupation: str = Field(
        description="Primary occupation or role (e.g., 'blacksmith', 'guard', 'merchant')",
    )
    occupation_years: int | None = Field(
        default=None,
        ge=0,
        description="Years spent in this occupation",
    )
    personality_notes: str = Field(
        description="Personality traits, quirks, and mannerisms for roleplay",
    )


class NPCSkill(BaseModel):
    """A skill possessed by an NPC."""

    skill_key: str = Field(
        description="Skill identifier (lowercase, underscores, e.g., 'swordfighting', 'haggling')",
    )
    proficiency_level: int = Field(
        ge=1,
        le=100,
        description="Proficiency level: novice=10-30, journeyman=40-60, expert=70-85, master=90+",
    )


class NPCInventoryItem(BaseModel):
    """An item in the NPC's inventory."""

    item_key: str = Field(
        description="Unique item identifier (lowercase, underscores)",
    )
    display_name: str = Field(
        description="Display name for the item",
    )
    item_type: Literal[
        "weapon", "armor", "clothing", "consumable", "container", "misc", "currency"
    ] = Field(
        default="misc",
        description="Type of item",
    )
    description: str | None = Field(
        default=None,
        description="Brief item description",
    )
    body_slot: str | None = Field(
        default=None,
        description="Where item is equipped (head, torso, legs, feet, hands, main_hand, off_hand)",
    )
    body_layer: int = Field(
        default=0,
        ge=0,
        le=3,
        description="Layer for clothing (0=skin, 1=underwear, 2=main, 3=outer)",
    )
    properties: dict | None = Field(
        default=None,
        description="Item-specific properties (e.g., {'damage': '1d6', 'gold_value': 10})",
    )
    is_equipped: bool = Field(
        default=False,
        description="Whether the item is currently equipped/worn",
    )
    quantity: int = Field(
        default=1,
        ge=1,
        description="Number of this item (for stackable items like coins, arrows)",
    )


class NPCPreferences(BaseModel):
    """Character preferences for social, intimacy, and lifestyle choices."""

    # Social
    social_tendency: Literal["introvert", "ambivert", "extrovert"] = Field(
        default="ambivert",
        description="Social preference tendency",
    )
    preferred_group_size: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Optimal number of people in social settings",
    )

    # Intimacy
    drive_level: Literal[
        "asexual", "very_low", "low", "moderate", "high", "very_high"
    ] = Field(
        default="moderate",
        description="Level of intimacy drive",
    )
    intimacy_style: Literal["casual", "emotional", "monogamous", "polyamorous"] = Field(
        default="emotional",
        description="How they approach intimate relationships",
    )

    # Alcohol
    alcohol_tolerance: Literal["none", "low", "moderate", "high", "very_high"] = Field(
        default="moderate",
        description="How well they handle alcohol",
    )

    # Food preferences
    favorite_foods: list[str] = Field(
        default_factory=list,
        description="Preferred food types (e.g., ['roasted meat', 'fresh bread', 'stew'])",
    )
    disliked_foods: list[str] = Field(
        default_factory=list,
        description="Disliked food types",
    )

    # Trait flags
    is_greedy_eater: bool = Field(
        default=False,
        description="Eats faster, hunger decays faster",
    )
    is_picky_eater: bool = Field(
        default=False,
        description="Only likes specific foods",
    )
    is_social_butterfly: bool = Field(
        default=False,
        description="Gains social satisfaction faster",
    )
    is_loner: bool = Field(
        default=False,
        description="Prefers solitude, social need decays slowly",
    )
    has_high_stamina: bool = Field(
        default=False,
        description="Fatigue accumulates slower",
    )
    has_low_stamina: bool = Field(
        default=False,
        description="Fatigue accumulates faster",
    )


class NPCInitialNeeds(BaseModel):
    """Initial need values for an NPC based on context (time of day, occupation)."""

    hunger: int = Field(
        default=70,
        ge=0,
        le=100,
        description="0=starving, 50=satisfied, 100=stuffed",
    )
    thirst: int = Field(
        default=70,
        ge=0,
        le=100,
        description="0=dehydrated, 100=well-hydrated",
    )
    energy: int = Field(
        default=70,
        ge=0,
        le=100,
        description="0=exhausted, 100=energized",
    )
    hygiene: int = Field(
        default=70,
        ge=0,
        le=100,
        description="0=filthy, 100=spotless",
    )
    comfort: int = Field(
        default=70,
        ge=0,
        le=100,
        description="0=miserable, 100=luxurious",
    )
    wellness: int = Field(
        default=100,
        ge=0,
        le=100,
        description="0=agony (injuries), 100=pain-free",
    )
    social_connection: int = Field(
        default=60,
        ge=0,
        le=100,
        description="0=lonely, 100=socially fulfilled",
    )
    morale: int = Field(
        default=60,
        ge=0,
        le=100,
        description="0=depressed, 100=elated",
    )
    sense_of_purpose: int = Field(
        default=60,
        ge=0,
        le=100,
        description="0=aimless, 100=driven",
    )
    intimacy: int = Field(
        default=60,
        ge=0,
        le=100,
        description="0=desperate, 100=content",
    )


class NPCGenerationResult(BaseModel):
    """Complete NPC generation result from LLM.

    Contains all data needed to create a fully fleshed-out NPC entity.
    """

    entity_key: str = Field(
        description="Unique identifier matching the extracted entity_key",
    )
    appearance: NPCAppearance = Field(
        description="Physical appearance details",
    )
    background: NPCBackground = Field(
        description="Background and personality information",
    )
    skills: list[NPCSkill] = Field(
        default_factory=list,
        min_length=0,
        max_length=10,
        description="3-5 skills relevant to occupation/role",
    )
    inventory: list[NPCInventoryItem] = Field(
        default_factory=list,
        description="Items owned/carried by NPC",
    )
    preferences: NPCPreferences | None = Field(
        default=None,
        description="DEPRECATED: Preferences are now auto-generated by the system using probability distributions. LLM should not include this field.",
    )
    initial_needs: NPCInitialNeeds = Field(
        default_factory=NPCInitialNeeds,
        description="Context-aware starting need values",
    )
