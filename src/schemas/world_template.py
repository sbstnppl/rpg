"""World template schemas for YAML/JSON import.

This module defines Pydantic models for importing world data
from YAML or JSON files. Use with world_loader service.
"""

from pydantic import BaseModel, Field


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
