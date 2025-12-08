"""ZoneManager for terrain zone operations and navigation."""

from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.database.models.enums import (
    ConnectionType,
    EncounterFrequency,
    PlacementType,
    TerrainType,
    VisibilityRange,
)
from src.database.models.navigation import (
    LocationZonePlacement,
    TerrainZone,
    TransportMode,
    ZoneConnection,
)
from src.database.models.session import GameSession
from src.database.models.world import Location
from src.managers.base import BaseManager


class ZoneManager(BaseManager):
    """Manager for terrain zone operations.

    Handles:
    - Zone CRUD operations
    - Zone connections (adjacencies)
    - Location placements within zones
    - Terrain cost calculations
    - Accessibility checks
    - Visibility queries
    """

    # =========================================================================
    # Basic Zone Operations
    # =========================================================================

    def get_zone(self, zone_key: str) -> TerrainZone | None:
        """Get a terrain zone by its key.

        Args:
            zone_key: Unique zone key.

        Returns:
            TerrainZone if found, None otherwise.
        """
        return (
            self.db.query(TerrainZone)
            .filter(
                TerrainZone.session_id == self.session_id,
                TerrainZone.zone_key == zone_key,
            )
            .first()
        )

    def create_zone(
        self,
        zone_key: str,
        display_name: str,
        terrain_type: TerrainType,
        description: str,
        base_travel_cost: int = 10,
        mounted_travel_cost: int | None = None,
        requires_skill: str | None = None,
        skill_difficulty: int | None = None,
        failure_consequence: str | None = None,
        visibility_range: VisibilityRange = VisibilityRange.MEDIUM,
        encounter_frequency: EncounterFrequency = EncounterFrequency.LOW,
        encounter_table_key: str | None = None,
        atmosphere: str | None = None,
        parent_zone_key: str | None = None,
    ) -> TerrainZone:
        """Create a new terrain zone.

        Args:
            zone_key: Unique key for the zone.
            display_name: Display name.
            terrain_type: Type of terrain.
            description: Full description.
            base_travel_cost: Base walking time in minutes per unit distance.
            mounted_travel_cost: Travel time on mount (None = impassable).
            requires_skill: Skill required to enter (e.g., 'swimming').
            skill_difficulty: DC for skill check if required.
            failure_consequence: What happens on failed check.
            visibility_range: How far player can see.
            encounter_frequency: How often encounters occur.
            encounter_table_key: Key to encounter table.
            atmosphere: Mood, sounds, smells.
            parent_zone_key: Optional parent zone key.

        Returns:
            Created TerrainZone.
        """
        parent_zone_id = None
        if parent_zone_key is not None:
            parent = self.get_zone(parent_zone_key)
            if parent is not None:
                parent_zone_id = parent.id

        zone = TerrainZone(
            session_id=self.session_id,
            zone_key=zone_key,
            display_name=display_name,
            terrain_type=terrain_type,
            description=description,
            base_travel_cost=base_travel_cost,
            mounted_travel_cost=mounted_travel_cost,
            requires_skill=requires_skill,
            skill_difficulty=skill_difficulty,
            failure_consequence=failure_consequence,
            visibility_range=visibility_range,
            encounter_frequency=encounter_frequency,
            encounter_table_key=encounter_table_key,
            atmosphere=atmosphere,
            parent_zone_id=parent_zone_id,
        )
        self.db.add(zone)
        self.db.flush()
        return zone

    def get_all_zones(self) -> list[TerrainZone]:
        """Get all terrain zones in the current session.

        Returns:
            List of all TerrainZones.
        """
        return (
            self.db.query(TerrainZone)
            .filter(TerrainZone.session_id == self.session_id)
            .all()
        )

    # =========================================================================
    # Zone Connections
    # =========================================================================

    def connect_zones(
        self,
        from_zone_key: str,
        to_zone_key: str,
        direction: str | None = None,
        connection_type: ConnectionType = ConnectionType.OPEN,
        crossing_minutes: int = 5,
        requires_skill: str | None = None,
        skill_difficulty: int | None = None,
        is_bidirectional: bool = True,
        is_visible: bool = True,
        description: str | None = None,
    ) -> ZoneConnection:
        """Create a connection between two zones.

        Args:
            from_zone_key: Source zone key.
            to_zone_key: Destination zone key.
            direction: Direction of travel (north, east, etc.).
            connection_type: Type of connection (open, path, bridge, etc.).
            crossing_minutes: Time to cross this connection.
            requires_skill: Skill required to cross.
            skill_difficulty: DC for crossing skill check.
            is_bidirectional: Whether travel is possible both ways.
            is_visible: Whether connection is visible (False for secret passages).
            description: Description of the path/passage.

        Returns:
            Created ZoneConnection.

        Raises:
            ValueError: If either zone is not found.
        """
        from_zone = self.get_zone(from_zone_key)
        if from_zone is None:
            raise ValueError(f"Zone not found: {from_zone_key}")

        to_zone = self.get_zone(to_zone_key)
        if to_zone is None:
            raise ValueError(f"Zone not found: {to_zone_key}")

        connection = ZoneConnection(
            session_id=self.session_id,
            from_zone_id=from_zone.id,
            to_zone_id=to_zone.id,
            direction=direction,
            connection_type=connection_type,
            crossing_minutes=crossing_minutes,
            requires_skill=requires_skill,
            skill_difficulty=skill_difficulty,
            is_bidirectional=is_bidirectional,
            is_visible=is_visible,
            description=description,
        )
        self.db.add(connection)
        self.db.flush()
        return connection

    def get_adjacent_zones(self, zone_key: str) -> list[TerrainZone]:
        """Get all zones reachable from a zone.

        Considers:
        - Outgoing connections
        - Incoming bidirectional connections
        - Connection passability

        Args:
            zone_key: Source zone key.

        Returns:
            List of adjacent TerrainZones.
        """
        zone = self.get_zone(zone_key)
        if zone is None:
            return []

        # Get zones via outgoing connections
        outgoing_zone_ids = (
            self.db.query(ZoneConnection.to_zone_id)
            .filter(
                ZoneConnection.session_id == self.session_id,
                ZoneConnection.from_zone_id == zone.id,
                ZoneConnection.is_passable == True,
            )
            .all()
        )
        outgoing_ids = {row[0] for row in outgoing_zone_ids}

        # Get zones via incoming bidirectional connections
        incoming_zone_ids = (
            self.db.query(ZoneConnection.from_zone_id)
            .filter(
                ZoneConnection.session_id == self.session_id,
                ZoneConnection.to_zone_id == zone.id,
                ZoneConnection.is_passable == True,
                ZoneConnection.is_bidirectional == True,
            )
            .all()
        )
        incoming_ids = {row[0] for row in incoming_zone_ids}

        # Combine and fetch zones
        all_adjacent_ids = outgoing_ids | incoming_ids
        if not all_adjacent_ids:
            return []

        return (
            self.db.query(TerrainZone)
            .filter(TerrainZone.id.in_(all_adjacent_ids))
            .all()
        )

    def get_adjacent_zones_with_directions(
        self, zone_key: str
    ) -> list[dict]:
        """Get adjacent zones with their direction info.

        Args:
            zone_key: Source zone key.

        Returns:
            List of dicts with 'zone', 'direction', 'connection' keys.
        """
        zone = self.get_zone(zone_key)
        if zone is None:
            return []

        results = []

        # Outgoing connections
        outgoing_connections = (
            self.db.query(ZoneConnection)
            .filter(
                ZoneConnection.session_id == self.session_id,
                ZoneConnection.from_zone_id == zone.id,
                ZoneConnection.is_passable == True,
            )
            .all()
        )

        for conn in outgoing_connections:
            to_zone = (
                self.db.query(TerrainZone)
                .filter(TerrainZone.id == conn.to_zone_id)
                .first()
            )
            if to_zone:
                results.append({
                    "zone": to_zone,
                    "direction": conn.direction,
                    "connection": conn,
                })

        # Incoming bidirectional connections
        incoming_connections = (
            self.db.query(ZoneConnection)
            .filter(
                ZoneConnection.session_id == self.session_id,
                ZoneConnection.to_zone_id == zone.id,
                ZoneConnection.is_passable == True,
                ZoneConnection.is_bidirectional == True,
            )
            .all()
        )

        for conn in incoming_connections:
            from_zone = (
                self.db.query(TerrainZone)
                .filter(TerrainZone.id == conn.from_zone_id)
                .first()
            )
            if from_zone:
                # Reverse direction for incoming connections
                reverse_direction = self._reverse_direction(conn.direction)
                results.append({
                    "zone": from_zone,
                    "direction": reverse_direction,
                    "connection": conn,
                })

        return results

    def _reverse_direction(self, direction: str | None) -> str | None:
        """Get the opposite direction.

        Args:
            direction: Original direction.

        Returns:
            Opposite direction or None.
        """
        if direction is None:
            return None

        opposites = {
            "north": "south",
            "south": "north",
            "east": "west",
            "west": "east",
            "up": "down",
            "down": "up",
            "inside": "outside",
            "outside": "inside",
            "northeast": "southwest",
            "southwest": "northeast",
            "northwest": "southeast",
            "southeast": "northwest",
        }
        return opposites.get(direction.lower(), direction)

    # =========================================================================
    # Location Placements
    # =========================================================================

    def place_location_in_zone(
        self,
        location_key: str,
        zone_key: str,
        placement_type: PlacementType = PlacementType.WITHIN,
        visibility: str = "visible_from_zone",
    ) -> LocationZonePlacement:
        """Place a location within a terrain zone.

        Args:
            location_key: Location key.
            zone_key: Zone key.
            placement_type: How the location relates to the zone.
            visibility: Visibility from the zone.

        Returns:
            Created LocationZonePlacement.

        Raises:
            ValueError: If location or zone not found.
        """
        zone = self.get_zone(zone_key)
        if zone is None:
            raise ValueError(f"Zone not found: {zone_key}")

        location = (
            self.db.query(Location)
            .filter(
                Location.session_id == self.session_id,
                Location.location_key == location_key,
            )
            .first()
        )
        if location is None:
            raise ValueError(f"Location not found: {location_key}")

        placement = LocationZonePlacement(
            session_id=self.session_id,
            location_id=location.id,
            zone_id=zone.id,
            placement_type=placement_type,
            visibility=visibility,
        )
        self.db.add(placement)
        self.db.flush()
        return placement

    def get_zone_locations(
        self,
        zone_key: str,
        visibility: str | None = None,
    ) -> list[Location]:
        """Get all locations within a zone.

        Args:
            zone_key: Zone key.
            visibility: Optional filter by visibility.

        Returns:
            List of Locations in the zone.
        """
        zone = self.get_zone(zone_key)
        if zone is None:
            return []

        query = (
            self.db.query(Location)
            .join(
                LocationZonePlacement,
                LocationZonePlacement.location_id == Location.id,
            )
            .filter(
                LocationZonePlacement.session_id == self.session_id,
                LocationZonePlacement.zone_id == zone.id,
            )
        )

        if visibility is not None:
            query = query.filter(LocationZonePlacement.visibility == visibility)

        return query.all()

    def get_location_zone(self, location_key: str) -> TerrainZone | None:
        """Get the zone a location is placed in.

        Args:
            location_key: Location key.

        Returns:
            TerrainZone if found, None otherwise.
        """
        location = (
            self.db.query(Location)
            .filter(
                Location.session_id == self.session_id,
                Location.location_key == location_key,
            )
            .first()
        )
        if location is None:
            return None

        placement = (
            self.db.query(LocationZonePlacement)
            .filter(
                LocationZonePlacement.session_id == self.session_id,
                LocationZonePlacement.location_id == location.id,
            )
            .first()
        )
        if placement is None:
            return None

        return (
            self.db.query(TerrainZone)
            .filter(TerrainZone.id == placement.zone_id)
            .first()
        )

    def get_visible_locations_from_zone(self, zone_key: str) -> list[Location]:
        """Get locations visible from a zone.

        Args:
            zone_key: Zone key.

        Returns:
            List of visible Locations.
        """
        return self.get_zone_locations(zone_key, visibility="visible_from_zone")

    # =========================================================================
    # Terrain Costs
    # =========================================================================

    def get_terrain_cost(
        self,
        zone_key: str,
        transport_mode_key: str,
    ) -> int | None:
        """Calculate travel cost through a zone for a transport mode.

        Args:
            zone_key: Zone key.
            transport_mode_key: Transport mode key (e.g., 'walking', 'mounted').

        Returns:
            Travel cost in minutes, or None if impassable.
        """
        zone = self.get_zone(zone_key)
        if zone is None:
            return None

        # Walking uses base cost
        if transport_mode_key == "walking":
            return zone.base_travel_cost

        # Check if zone has explicit mounted cost
        if transport_mode_key == "mounted" and zone.mounted_travel_cost is not None:
            return zone.mounted_travel_cost

        # Look up transport mode and apply terrain multiplier
        transport_mode = self.get_transport_mode(transport_mode_key)
        if transport_mode is None:
            return zone.base_travel_cost

        terrain_key = zone.terrain_type.value
        terrain_costs = transport_mode.terrain_costs or {}

        multiplier = terrain_costs.get(terrain_key)
        if multiplier is None:
            return None  # Impassable for this transport mode

        return int(zone.base_travel_cost * multiplier)

    # =========================================================================
    # Accessibility
    # =========================================================================

    def check_accessibility(
        self,
        zone_key: str,
        character_skills: dict[str, int],
    ) -> dict:
        """Check if a zone is accessible for a character.

        Args:
            zone_key: Zone key.
            character_skills: Dict of skill_name -> skill_level.

        Returns:
            Dict with keys:
            - accessible: bool
            - requires_check: bool
            - skill: str (if requires_check)
            - difficulty: int (if requires_check)
            - failure_consequence: str | None
            - reason: str (if not accessible)
        """
        zone = self.get_zone(zone_key)
        if zone is None:
            return {
                "accessible": False,
                "requires_check": False,
                "reason": "Zone not found",
            }

        # Check if zone is blocked
        if not zone.is_accessible:
            return {
                "accessible": False,
                "requires_check": False,
                "reason": zone.blocked_reason or "Zone is blocked",
            }

        # Check skill requirements
        if zone.requires_skill is not None:
            if zone.requires_skill not in character_skills:
                return {
                    "accessible": False,
                    "requires_check": False,
                    "reason": f"Requires {zone.requires_skill} skill",
                }

            # Character has the skill - they can attempt
            return {
                "accessible": True,
                "requires_check": True,
                "skill": zone.requires_skill,
                "difficulty": zone.skill_difficulty or 10,
                "failure_consequence": zone.failure_consequence,
            }

        # No requirements
        return {
            "accessible": True,
            "requires_check": False,
        }

    # =========================================================================
    # Visibility
    # =========================================================================

    def get_visible_from_zone(self, zone_key: str) -> list[TerrainZone]:
        """Get zones visible from a zone based on visibility range.

        Args:
            zone_key: Source zone key.

        Returns:
            List of visible TerrainZones.
        """
        zone = self.get_zone(zone_key)
        if zone is None:
            return []

        # For now, return adjacent zones
        # Future: Consider visibility_range for extended visibility
        return self.get_adjacent_zones(zone_key)

    # =========================================================================
    # Transport Modes
    # =========================================================================

    def get_transport_mode(self, mode_key: str) -> TransportMode | None:
        """Get a transport mode by key.

        Note: TransportMode is global (not session-scoped).

        Args:
            mode_key: Transport mode key.

        Returns:
            TransportMode if found, None otherwise.
        """
        return (
            self.db.query(TransportMode)
            .filter(TransportMode.mode_key == mode_key)
            .first()
        )

    def get_available_transport_modes(self, zone_key: str) -> list[TransportMode]:
        """Get transport modes usable in a zone.

        Args:
            zone_key: Zone key.

        Returns:
            List of TransportModes that can traverse this zone.
        """
        zone = self.get_zone(zone_key)
        if zone is None:
            return []

        terrain_key = zone.terrain_type.value

        # Get all transport modes and filter by terrain compatibility
        all_modes = self.db.query(TransportMode).all()

        available = []
        for mode in all_modes:
            terrain_costs = mode.terrain_costs or {}
            # Mode is available if terrain has a non-None cost
            if terrain_key in terrain_costs and terrain_costs[terrain_key] is not None:
                available.append(mode)

        return available
