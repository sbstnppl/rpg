"""Pydantic schemas for entity extraction from GM responses.

These schemas define the structured output format for the EntityExtractor
agent's LLM calls.
"""

from typing import Literal

from pydantic import BaseModel, Field


class CharacterExtraction(BaseModel):
    """Extracted character information."""

    entity_key: str = Field(
        description="Unique identifier (lowercase, underscores, e.g. 'bartender_bob')"
    )
    display_name: str = Field(description="Display name for the character")
    entity_type: Literal["npc", "monster", "animal"] = Field(
        default="npc",
        description="Type of character",
    )
    description: str | None = Field(
        default=None,
        description="Physical description if mentioned",
    )
    personality_traits: list[str] = Field(
        default_factory=list,
        description="Notable personality traits mentioned",
    )
    current_activity: str | None = Field(
        default=None,
        description="What the character is currently doing",
    )
    current_location: str | None = Field(
        default=None,
        description="Where the character is located",
    )


class ItemExtraction(BaseModel):
    """Extracted item information."""

    item_key: str = Field(
        description="Unique identifier (lowercase, underscores)"
    )
    display_name: str = Field(description="Display name for the item")
    item_type: Literal[
        "weapon", "armor", "clothing", "consumable", "container", "misc"
    ] = Field(
        default="misc",
        description="Type of item",
    )
    description: str | None = Field(
        default=None,
        description="Item description if mentioned",
    )
    owner_key: str | None = Field(
        default=None,
        description="Entity key of the owner",
    )
    action: Literal[
        "acquired", "dropped", "transferred", "equipped", "mentioned"
    ] = Field(
        default="mentioned",
        description="What happened with the item",
    )


class FactExtraction(BaseModel):
    """Extracted fact about the world or characters."""

    subject: str = Field(
        description="Entity or topic the fact is about (entity_key or general topic)"
    )
    predicate: str = Field(
        description="Aspect being described (e.g. 'occupation', 'lives_at', 'knows_secret')"
    )
    value: str = Field(description="The actual information")
    is_secret: bool = Field(
        default=False,
        description="Whether this is GM-only information the player shouldn't know",
    )


class RelationshipChange(BaseModel):
    """Extracted relationship change between characters."""

    from_entity: str = Field(
        description="Entity key of character whose attitude changed"
    )
    to_entity: str = Field(
        description="Entity key of character toward whom attitude changed"
    )
    dimension: Literal[
        "trust", "liking", "respect", "romantic_interest", "fear", "familiarity"
    ] = Field(description="Which relationship dimension changed")
    delta: int = Field(
        ge=-20,
        le=20,
        description="Change amount (-20 to +20)",
    )
    reason: str = Field(description="Why the attitude changed")


class AppointmentExtraction(BaseModel):
    """Extracted appointment or commitment."""

    description: str = Field(description="What the appointment is for")
    day: int = Field(description="Game day number")
    time: str = Field(description="Time of day (e.g. '14:00', 'evening')")
    location_key: str | None = Field(
        default=None,
        description="Where the appointment is",
    )
    participants: list[str] = Field(
        default_factory=list,
        description="Entity keys of participants",
    )


class LocationExtraction(BaseModel):
    """Extracted location information for new places."""

    location_key: str = Field(
        description="Unique identifier (lowercase, underscores, e.g. 'weary_traveler_inn')"
    )
    display_name: str = Field(description="Display name for the location")
    category: Literal[
        "wilderness", "settlement", "establishment", "interior", "public"
    ] = Field(
        default="interior",
        description="Type of location",
    )
    description: str = Field(
        description="Description of the location (atmosphere, features, etc.)"
    )
    parent_location_key: str | None = Field(
        default=None,
        description="Key of parent location (e.g. inn_common_room -> weary_traveler_inn)",
    )


class ExtractionResult(BaseModel):
    """Complete extraction result from GM response analysis."""

    characters: list[CharacterExtraction] = Field(
        default_factory=list,
        description="New characters mentioned",
    )
    items: list[ItemExtraction] = Field(
        default_factory=list,
        description="Items mentioned or interacted with",
    )
    locations: list[LocationExtraction] = Field(
        default_factory=list,
        description="New locations introduced or described",
    )
    facts: list[FactExtraction] = Field(
        default_factory=list,
        description="Facts revealed about characters or world",
    )
    relationship_changes: list[RelationshipChange] = Field(
        default_factory=list,
        description="Attitude changes between characters",
    )
    appointments: list[AppointmentExtraction] = Field(
        default_factory=list,
        description="Appointments or commitments made",
    )
    time_advance_minutes: int = Field(
        default=0,
        ge=0,
        description="How many minutes passed during this interaction",
    )
    location_change: str | None = Field(
        default=None,
        description="New location key if player moved",
    )
