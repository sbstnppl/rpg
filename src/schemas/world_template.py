"""World template schemas for YAML/JSON import.

This module defines Pydantic models for importing world data
from YAML or JSON files. Use with world_loader service.
"""

from pydantic import BaseModel, Field
from typing import Any


class ZoneTemplate(BaseModel):
    """Template for a terrain zone."""

    zone_key: str = Field(..., description="Unique key for the zone")
    display_name: str = Field(..., description="Human-readable name")
    terrain_type: str = Field(
        default="grassland",
        description="Terrain type (forest, mountain, desert, etc.)",
    )
    base_travel_cost: int = Field(
        default=15,
        description="Base travel time in minutes to cross zone",
    )
    description: str | None = Field(
        default=None,
        description="Zone description",
    )
    requires_skill: str | None = Field(
        default=None,
        description="Skill required to enter (e.g., 'climbing')",
    )
    skill_difficulty: int | None = Field(
        default=None,
        description="DC for required skill check",
    )
    visibility_range: str = Field(
        default="medium",
        description="How far you can see (close, medium, far, extreme)",
    )
    parent_zone_key: str | None = Field(
        default=None,
        description="Key of parent zone for hierarchical organization",
    )


class ConnectionTemplate(BaseModel):
    """Template for a zone connection."""

    from_zone: str = Field(..., description="Source zone key")
    to_zone: str = Field(..., description="Destination zone key")
    direction: str | None = Field(
        default=None,
        description="Cardinal direction (north, east, south, west)",
    )
    crossing_minutes: int = Field(
        default=5,
        description="Time to cross this connection",
    )
    bidirectional: bool = Field(
        default=True,
        description="Whether connection works both ways",
    )
    connection_type: str = Field(
        default="road",
        description="Type of connection (road, trail, river, etc.)",
    )


class LocationTemplate(BaseModel):
    """Template for a location within a zone."""

    location_key: str = Field(..., description="Unique key for the location")
    display_name: str = Field(..., description="Human-readable name")
    zone_key: str = Field(..., description="Zone where this location exists")
    category: str | None = Field(
        default=None,
        description="Location category (tavern, market, temple, etc.)",
    )
    description: str | None = Field(
        default=None,
        description="Location description",
    )
    atmosphere: str | None = Field(
        default=None,
        description="Mood, lighting, sounds, smells",
    )
    typical_crowd: str | None = Field(
        default=None,
        description="Who's usually here",
    )
    visibility: str = Field(
        default="visible_from_zone",
        description="How visible is this location (hidden, visible_from_zone, landmark)",
    )


class WorldTemplate(BaseModel):
    """Complete world template for import."""

    name: str = Field(..., description="Name of this world/region")
    description: str | None = Field(
        default=None,
        description="Overall description of the world",
    )
    starting_zone: str | None = Field(
        default=None,
        description="Key of the starting zone for new players",
    )
    starting_location: str | None = Field(
        default=None,
        description="Key of the starting location for new players",
    )
    zones: list[ZoneTemplate] = Field(
        default_factory=list,
        description="Terrain zones in this world",
    )
    connections: list[ConnectionTemplate] = Field(
        default_factory=list,
        description="Connections between zones",
    )
    locations: list[LocationTemplate] = Field(
        default_factory=list,
        description="Notable locations within zones",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Grimhaven Region",
                "description": "A dark forest region with ancient ruins",
                "starting_zone": "village_outskirts",
                "zones": [
                    {
                        "zone_key": "village_outskirts",
                        "display_name": "Village Outskirts",
                        "terrain_type": "grassland",
                        "description": "Rolling hills around the village",
                    },
                    {
                        "zone_key": "dark_forest",
                        "display_name": "The Dark Forest",
                        "terrain_type": "forest",
                        "base_travel_cost": 30,
                    },
                ],
                "connections": [
                    {
                        "from_zone": "village_outskirts",
                        "to_zone": "dark_forest",
                        "direction": "north",
                    }
                ],
                "locations": [
                    {
                        "location_key": "village_tavern",
                        "display_name": "The Rusty Tankard",
                        "zone_key": "village_outskirts",
                        "category": "tavern",
                    }
                ],
            }
        }


# =============================================================================
# NPC Templates
# =============================================================================


class NPCExtensionTemplate(BaseModel):
    """Template for NPC extension data."""

    job: str | None = Field(default=None, description="Occupation")
    workplace: str | None = Field(default=None, description="Where they work")
    home_location: str | None = Field(default=None, description="Where they live")
    hobbies: list[str] | None = Field(default=None, description="List of hobbies")
    speech_pattern: str | None = Field(
        default=None, description="How they speak (accent, vocabulary, quirks)"
    )
    personality_traits: dict[str, bool] | None = Field(
        default=None, description="Personality traits affecting relationships"
    )
    dark_secret: str | None = Field(
        default=None, description="Something the NPC is hiding"
    )
    hidden_goal: str | None = Field(
        default=None, description="What the NPC truly wants"
    )
    betrayal_conditions: str | None = Field(
        default=None, description="Conditions that would cause NPC to betray player"
    )


class KnowledgeAreaTemplate(BaseModel):
    """Template for an NPC knowledge area."""

    description: str = Field(..., description="What this knowledge area covers")
    disclosure_threshold: int = Field(
        default=50, description="Trust level required to learn this (0-100)"
    )
    sample_content: str | None = Field(
        default=None, description="Example of what the NPC might say"
    )


class NPCTemplate(BaseModel):
    """Template for an NPC entity."""

    entity_key: str = Field(..., description="Unique key for the entity")
    display_name: str = Field(..., description="Human-readable name")
    entity_type: str = Field(default="npc", description="Entity type")

    # Appearance fields
    age: int | None = Field(default=None, description="Numeric age in years")
    age_apparent: str | None = Field(
        default=None, description="Apparent age description"
    )
    gender: str | None = Field(default=None, description="Gender identity")
    height: str | None = Field(default=None, description="Height description")
    build: str | None = Field(default=None, description="Body build")
    hair_color: str | None = Field(default=None, description="Hair color")
    hair_style: str | None = Field(default=None, description="Hair style")
    eye_color: str | None = Field(default=None, description="Eye color")
    skin_tone: str | None = Field(default=None, description="Skin tone")
    species: str | None = Field(default=None, description="Species/race")
    distinguishing_features: str | None = Field(
        default=None, description="Notable features"
    )
    voice_description: str | None = Field(
        default=None, description="Voice characteristics"
    )

    # Background
    occupation: str | None = Field(default=None, description="Primary occupation")
    occupation_years: int | None = Field(
        default=None, description="Years spent in occupation"
    )
    background: str | None = Field(default=None, description="Character backstory")
    personality_notes: str | None = Field(
        default=None, description="Personality traits and quirks"
    )
    hidden_backstory: str | None = Field(
        default=None, description="Secret backstory elements"
    )

    # NPC-specific extension
    npc_extension: NPCExtensionTemplate | None = Field(
        default=None, description="NPC-specific data"
    )

    # Knowledge system
    knowledge_areas: dict[str, KnowledgeAreaTemplate] | None = Field(
        default=None, description="Areas of knowledge with trust thresholds"
    )


class NPCListTemplate(BaseModel):
    """Template for a list of NPCs."""

    npcs: list[NPCTemplate] = Field(
        default_factory=list, description="List of NPC definitions"
    )


# =============================================================================
# Schedule Templates
# =============================================================================


class ScheduleEntryTemplate(BaseModel):
    """Template for a single schedule entry."""

    day_pattern: str = Field(
        ..., description="Day pattern (daily, weekday, weekend, monday, etc.)"
    )
    start_time: str = Field(..., description="Start time (HH:MM)")
    end_time: str = Field(..., description="End time (HH:MM)")
    activity: str = Field(..., description="What they're doing")
    location_key: str | None = Field(default=None, description="Where they are")
    priority: int = Field(
        default=0, description="Priority for overlapping schedules"
    )


class NPCScheduleTemplate(BaseModel):
    """Template for an NPC's full schedule."""

    entity_key: str = Field(..., description="Entity key this schedule belongs to")
    entries: list[ScheduleEntryTemplate] = Field(
        default_factory=list, description="Schedule entries"
    )


class ScheduleListTemplate(BaseModel):
    """Template for a list of NPC schedules."""

    schedules: list[NPCScheduleTemplate] = Field(
        default_factory=list, description="List of NPC schedules"
    )


# =============================================================================
# Item Templates
# =============================================================================


class ItemTemplate(BaseModel):
    """Template for an item."""

    item_key: str = Field(..., description="Unique key for the item")
    display_name: str = Field(..., description="Human-readable name")
    item_type: str = Field(default="misc", description="Item type")
    description: str | None = Field(default=None, description="Item description")

    # Body placement
    body_slot: str | None = Field(default=None, description="Body slot when worn")
    body_layer: int = Field(default=0, description="Layer (0=innermost)")

    # Properties
    properties: dict[str, Any] | None = Field(
        default=None, description="Item-specific properties"
    )

    # Ownership
    owner_entity_key: str | None = Field(
        default=None, description="Entity key of owner"
    )
    holder_entity_key: str | None = Field(
        default=None, description="Entity key of current holder"
    )

    # Location (for items in the world)
    location_key: str | None = Field(
        default=None, description="Location where item is found"
    )
    location_description: str | None = Field(
        default=None, description="Where in the location to find the item"
    )

    # Flags
    starting_item: bool = Field(
        default=False, description="Whether this is a starting item for player"
    )


class ItemListTemplate(BaseModel):
    """Template for a list of items."""

    items: list[ItemTemplate] = Field(
        default_factory=list, description="List of item definitions"
    )


# =============================================================================
# Fact Templates
# =============================================================================


class FactTemplate(BaseModel):
    """Template for a world fact (SPV pattern)."""

    subject_type: str = Field(
        ..., description="Type of subject (entity, location, world, item)"
    )
    subject_key: str = Field(..., description="Key of the subject")
    predicate: str = Field(..., description="What aspect (job, likes, etc.)")
    value: str = Field(..., description="The value")

    category: str = Field(default="world", description="Fact category")
    confidence: int = Field(default=80, description="Confidence level (0-100)")
    is_secret: bool = Field(default=False, description="GM knows, player doesn't")
    player_believes: str | None = Field(
        default=None, description="What player thinks is true (if different)"
    )

    # Foreshadowing
    is_foreshadowing: bool = Field(default=False, description="Hint for future payoff")
    foreshadow_target: str | None = Field(
        default=None, description="What this foreshadows"
    )
    times_mentioned: int = Field(
        default=1, description="Times mentioned (rule of three)"
    )


class FactListTemplate(BaseModel):
    """Template for a list of world facts."""

    facts: list[FactTemplate] = Field(
        default_factory=list, description="List of fact definitions"
    )
