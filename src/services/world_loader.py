"""World loader service for importing worlds from YAML/JSON files.

This service handles loading world data from external files and
creating the corresponding database records.
"""

import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from src.database.models.enums import (
    ConnectionType,
    PlacementType,
    TerrainType,
    VisibilityRange,
)
from src.database.models.navigation import TerrainZone, ZoneConnection
from src.database.models.session import GameSession
from src.database.models.world import Location
from src.managers.location_manager import LocationManager
from src.managers.zone_manager import ZoneManager
from src.schemas.world_template import (
    ConnectionTemplate,
    LocationTemplate,
    WorldTemplate,
    ZoneTemplate,
)


class WorldLoadError(Exception):
    """Error during world loading."""

    pass


def load_world_from_file(
    db: Session,
    game_session: GameSession,
    file_path: Path,
) -> dict[str, Any]:
    """Load world data from a YAML or JSON file.

    Creates zones, connections, and locations in the database
    based on the template file.

    Args:
        db: Database session.
        game_session: Current game session.
        file_path: Path to YAML or JSON file.

    Returns:
        Dict with counts: zones, connections, locations created.

    Raises:
        WorldLoadError: If file cannot be parsed or data is invalid.
        FileNotFoundError: If file does not exist.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"World file not found: {file_path}")

    # Load and parse file
    suffix = file_path.suffix.lower()
    try:
        with open(file_path) as f:
            if suffix in (".yaml", ".yml"):
                import yaml

                data = yaml.safe_load(f)
            elif suffix == ".json":
                data = json.load(f)
            else:
                raise WorldLoadError(
                    f"Unsupported file format: {suffix}. Use .yaml, .yml, or .json"
                )
    except (json.JSONDecodeError, Exception) as e:
        raise WorldLoadError(f"Failed to parse {file_path}: {e}")

    # Validate with Pydantic
    try:
        template = WorldTemplate.model_validate(data)
    except Exception as e:
        raise WorldLoadError(f"Invalid world template: {e}")

    # Create managers
    zone_manager = ZoneManager(db, game_session)
    location_manager = LocationManager(db, game_session)

    results = {
        "zones": 0,
        "connections": 0,
        "locations": 0,
        "errors": [],
    }

    # First pass: Create zones (to establish IDs for parent references)
    zone_key_to_id: dict[str, int] = {}
    for zone_template in template.zones:
        try:
            zone = _create_zone(zone_manager, zone_template)
            zone_key_to_id[zone.zone_key] = zone.id
            results["zones"] += 1
        except Exception as e:
            results["errors"].append(f"Failed to create zone {zone_template.zone_key}: {e}")

    db.flush()

    # Second pass: Set parent zone relationships
    for zone_template in template.zones:
        if zone_template.parent_zone_key:
            try:
                _set_zone_parent(
                    db,
                    game_session,
                    zone_template.zone_key,
                    zone_template.parent_zone_key,
                    zone_key_to_id,
                )
            except Exception as e:
                results["errors"].append(
                    f"Failed to set parent for zone {zone_template.zone_key}: {e}"
                )

    db.flush()

    # Create connections
    for conn_template in template.connections:
        try:
            _create_connection(zone_manager, conn_template, zone_key_to_id)
            results["connections"] += 1
            # If bidirectional, count both
            if conn_template.bidirectional:
                results["connections"] += 1
        except Exception as e:
            results["errors"].append(
                f"Failed to create connection {conn_template.from_zone} -> "
                f"{conn_template.to_zone}: {e}"
            )

    # Create locations
    for loc_template in template.locations:
        try:
            _create_location(location_manager, zone_manager, loc_template, zone_key_to_id)
            results["locations"] += 1
        except Exception as e:
            results["errors"].append(
                f"Failed to create location {loc_template.location_key}: {e}"
            )

    db.commit()

    return results


def _create_zone(
    zone_manager: ZoneManager,
    template: ZoneTemplate,
) -> TerrainZone:
    """Create a terrain zone from template."""
    # Map terrain type string to enum
    terrain_type = _parse_terrain_type(template.terrain_type)
    visibility = _parse_visibility_range(template.visibility_range)

    # Provide default description if not specified
    description = template.description or f"A {template.terrain_type} area."

    return zone_manager.create_zone(
        zone_key=template.zone_key,
        display_name=template.display_name,
        terrain_type=terrain_type,
        description=description,
        base_travel_cost=template.base_travel_cost,
        requires_skill=template.requires_skill,
        skill_difficulty=template.skill_difficulty,
        visibility_range=visibility,
    )


def _set_zone_parent(
    db: Session,
    game_session: GameSession,
    zone_key: str,
    parent_key: str,
    zone_key_to_id: dict[str, int],
) -> None:
    """Set a zone's parent zone."""
    if zone_key not in zone_key_to_id:
        raise ValueError(f"Zone not found: {zone_key}")
    if parent_key not in zone_key_to_id:
        raise ValueError(f"Parent zone not found: {parent_key}")

    zone = (
        db.query(TerrainZone)
        .filter(
            TerrainZone.session_id == game_session.id,
            TerrainZone.zone_key == zone_key,
        )
        .first()
    )
    if zone:
        zone.parent_zone_id = zone_key_to_id[parent_key]


def _create_connection(
    zone_manager: ZoneManager,
    template: ConnectionTemplate,
    zone_key_to_id: dict[str, int],
) -> ZoneConnection:
    """Create a zone connection from template."""
    if template.from_zone not in zone_key_to_id:
        raise ValueError(f"Source zone not found: {template.from_zone}")
    if template.to_zone not in zone_key_to_id:
        raise ValueError(f"Destination zone not found: {template.to_zone}")

    conn_type = _parse_connection_type(template.connection_type)

    return zone_manager.connect_zones(
        from_zone_key=template.from_zone,
        to_zone_key=template.to_zone,
        direction=template.direction,
        crossing_minutes=template.crossing_minutes,
        connection_type=conn_type,
        is_bidirectional=template.bidirectional,
    )


def _create_location(
    location_manager: LocationManager,
    zone_manager: ZoneManager,
    template: LocationTemplate,
    zone_key_to_id: dict[str, int],
) -> Location:
    """Create a location from template and place it in its zone."""
    if template.zone_key not in zone_key_to_id:
        raise ValueError(f"Zone not found: {template.zone_key}")

    # Create the location
    location = location_manager.create_location(
        location_key=template.location_key,
        display_name=template.display_name,
        description=template.description or f"A {template.category or 'location'}",
        category=template.category,
        atmosphere=template.atmosphere,
        typical_crowd=template.typical_crowd,
    )

    # Place in zone with visibility
    visibility = _parse_placement_visibility(template.visibility)
    zone_manager.place_location_in_zone(
        location_key=template.location_key,
        zone_key=template.zone_key,
        visibility=visibility,
    )

    return location


def _parse_terrain_type(value: str) -> TerrainType:
    """Parse terrain type string to enum."""
    value_lower = value.lower().strip()
    mapping = {
        # Direct enum mappings
        "plains": TerrainType.PLAINS,
        "grassland": TerrainType.PLAINS,  # Alias
        "forest": TerrainType.FOREST,
        "dense_forest": TerrainType.FOREST,  # Alias
        "road": TerrainType.ROAD,
        "trail": TerrainType.TRAIL,
        "mountain": TerrainType.MOUNTAIN,
        "hill": TerrainType.MOUNTAIN,  # Alias
        "swamp": TerrainType.SWAMP,
        "desert": TerrainType.DESERT,
        "lake": TerrainType.LAKE,
        "river": TerrainType.RIVER,
        "ocean": TerrainType.OCEAN,
        "coastal": TerrainType.OCEAN,  # Alias
        "cliff": TerrainType.CLIFF,
        "cave": TerrainType.CAVE,
        "underground": TerrainType.CAVE,  # Alias
        "urban": TerrainType.URBAN,
        "city": TerrainType.URBAN,  # Alias
        "ruins": TerrainType.RUINS,
    }
    return mapping.get(value_lower, TerrainType.PLAINS)


def _parse_visibility_range(value: str) -> VisibilityRange:
    """Parse visibility range string to enum."""
    value_lower = value.lower().strip()
    mapping = {
        # Actual enum values
        "far": VisibilityRange.FAR,
        "medium": VisibilityRange.MEDIUM,
        "short": VisibilityRange.SHORT,
        "none": VisibilityRange.NONE,
        # Common aliases
        "close": VisibilityRange.SHORT,  # Alias
        "extreme": VisibilityRange.FAR,  # Alias
    }
    return mapping.get(value_lower, VisibilityRange.MEDIUM)


def _parse_connection_type(value: str) -> ConnectionType:
    """Parse connection type string to enum."""
    value_lower = value.lower().strip()
    mapping = {
        # Actual enum values
        "open": ConnectionType.OPEN,
        "path": ConnectionType.PATH,
        "bridge": ConnectionType.BRIDGE,
        "climb": ConnectionType.CLIMB,
        "swim": ConnectionType.SWIM,
        "door": ConnectionType.DOOR,
        "gate": ConnectionType.GATE,
        "hidden": ConnectionType.HIDDEN,
        # Common aliases
        "road": ConnectionType.PATH,  # Alias
        "trail": ConnectionType.PATH,  # Alias
        "walkway": ConnectionType.PATH,  # Alias
        "river": ConnectionType.SWIM,  # Alias - requires swimming
        "stairs": ConnectionType.CLIMB,  # Alias
        "ladder": ConnectionType.CLIMB,  # Alias
        "portal": ConnectionType.OPEN,  # Alias - treat as open passage
        "secret": ConnectionType.HIDDEN,  # Alias
    }
    return mapping.get(value_lower, ConnectionType.OPEN)


def _parse_placement_visibility(value: str) -> str:
    """Parse placement visibility string."""
    value_lower = value.lower().strip()
    if value_lower in ("hidden", "visible_from_zone", "landmark"):
        return value_lower
    return "visible_from_zone"
