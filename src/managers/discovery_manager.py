"""DiscoveryManager for fog of war and location discovery mechanics."""

from sqlalchemy.orm import Session

from src.database.models.enums import DiscoveryMethod
from src.database.models.entities import Entity
from src.database.models.items import Item
from src.database.models.navigation import (
    DigitalMapAccess,
    LocationDiscovery,
    LocationZonePlacement,
    MapItem,
    TerrainZone,
    ZoneDiscovery,
)
from src.database.models.session import GameSession
from src.database.models.world import Location
from src.managers.base import BaseManager
from src.managers.zone_manager import ZoneManager


class DiscoveryManager(BaseManager):
    """Manager for fog of war and discovery mechanics.

    Handles:
    - Zone discovery (revealing terrain zones)
    - Location discovery (revealing specific locations)
    - Map viewing (batch discovery from maps)
    - Auto-discovery on zone entry
    - Digital map access (modern/sci-fi settings)
    - Querying known zones/locations
    """

    def __init__(self, db: Session, game_session: GameSession) -> None:
        """Initialize DiscoveryManager.

        Args:
            db: SQLAlchemy database session.
            game_session: Current game session.
        """
        super().__init__(db, game_session)
        self._zone_manager = ZoneManager(db, game_session)

    # =========================================================================
    # Zone Discovery
    # =========================================================================

    def discover_zone(
        self,
        zone_key: str,
        method: DiscoveryMethod,
        source_entity_key: str | None = None,
        source_map_key: str | None = None,
        source_zone_key: str | None = None,
    ) -> dict:
        """Discover a terrain zone.

        Args:
            zone_key: Zone key to discover.
            method: How the zone was discovered.
            source_entity_key: Entity who revealed it (if told by NPC).
            source_map_key: Map item that revealed it (if from map).
            source_zone_key: Zone it was visible from (if seen from zone).

        Returns:
            Dict with:
            - success: bool
            - newly_discovered: bool
            - zone: TerrainZone
        """
        zone = self._zone_manager.get_zone(zone_key)
        if zone is None:
            return {
                "success": False,
                "newly_discovered": False,
                "reason": f"Zone not found: {zone_key}",
            }

        # Check if already discovered
        existing = (
            self.db.query(ZoneDiscovery)
            .filter(
                ZoneDiscovery.session_id == self.session_id,
                ZoneDiscovery.zone_id == zone.id,
            )
            .first()
        )

        if existing:
            return {
                "success": True,
                "newly_discovered": False,
                "zone": zone,
            }

        # Resolve source IDs
        source_entity_id = None
        if source_entity_key:
            entity = (
                self.db.query(Entity)
                .filter(
                    Entity.session_id == self.session_id,
                    Entity.entity_key == source_entity_key,
                )
                .first()
            )
            if entity:
                source_entity_id = entity.id

        source_map_id = None
        if source_map_key:
            item = (
                self.db.query(Item)
                .filter(
                    Item.session_id == self.session_id,
                    Item.item_key == source_map_key,
                )
                .first()
            )
            if item:
                source_map_id = item.id

        source_zone_id = None
        if source_zone_key:
            source_zone = self._zone_manager.get_zone(source_zone_key)
            if source_zone:
                source_zone_id = source_zone.id

        # Create discovery record
        discovery = ZoneDiscovery(
            session_id=self.session_id,
            zone_id=zone.id,
            discovered_turn=self.current_turn,
            discovery_method=method,
            source_entity_id=source_entity_id,
            source_map_id=source_map_id,
            source_zone_id=source_zone_id,
        )
        self.db.add(discovery)
        self.db.flush()

        return {
            "success": True,
            "newly_discovered": True,
            "zone": zone,
        }

    def is_zone_discovered(self, zone_key: str) -> bool:
        """Check if a zone has been discovered.

        Args:
            zone_key: Zone key to check.

        Returns:
            True if zone is known, False otherwise.
        """
        zone = self._zone_manager.get_zone(zone_key)
        if zone is None:
            return False

        exists = (
            self.db.query(ZoneDiscovery)
            .filter(
                ZoneDiscovery.session_id == self.session_id,
                ZoneDiscovery.zone_id == zone.id,
            )
            .first()
        )
        return exists is not None

    def get_known_zones(
        self,
        method: DiscoveryMethod | None = None,
    ) -> list[TerrainZone]:
        """Get all discovered zones.

        Args:
            method: Optional filter by discovery method.

        Returns:
            List of discovered TerrainZones.
        """
        query = (
            self.db.query(TerrainZone)
            .join(ZoneDiscovery, ZoneDiscovery.zone_id == TerrainZone.id)
            .filter(ZoneDiscovery.session_id == self.session_id)
        )

        if method is not None:
            query = query.filter(ZoneDiscovery.discovery_method == method)

        return query.all()

    # =========================================================================
    # Location Discovery
    # =========================================================================

    def discover_location(
        self,
        location_key: str,
        method: DiscoveryMethod,
        source_entity_key: str | None = None,
        source_map_key: str | None = None,
    ) -> dict:
        """Discover a location.

        Args:
            location_key: Location key to discover.
            method: How the location was discovered.
            source_entity_key: Entity who revealed it (if told by NPC).
            source_map_key: Map item that revealed it (if from map).

        Returns:
            Dict with:
            - success: bool
            - newly_discovered: bool
            - location: Location
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
            return {
                "success": False,
                "newly_discovered": False,
                "reason": f"Location not found: {location_key}",
            }

        # Check if already discovered
        existing = (
            self.db.query(LocationDiscovery)
            .filter(
                LocationDiscovery.session_id == self.session_id,
                LocationDiscovery.location_id == location.id,
            )
            .first()
        )

        if existing:
            return {
                "success": True,
                "newly_discovered": False,
                "location": location,
            }

        # Resolve source IDs
        source_entity_id = None
        if source_entity_key:
            entity = (
                self.db.query(Entity)
                .filter(
                    Entity.session_id == self.session_id,
                    Entity.entity_key == source_entity_key,
                )
                .first()
            )
            if entity:
                source_entity_id = entity.id

        source_map_id = None
        if source_map_key:
            item = (
                self.db.query(Item)
                .filter(
                    Item.session_id == self.session_id,
                    Item.item_key == source_map_key,
                )
                .first()
            )
            if item:
                source_map_id = item.id

        # Create discovery record
        discovery = LocationDiscovery(
            session_id=self.session_id,
            location_id=location.id,
            discovered_turn=self.current_turn,
            discovery_method=method,
            source_entity_id=source_entity_id,
            source_map_id=source_map_id,
        )
        self.db.add(discovery)
        self.db.flush()

        return {
            "success": True,
            "newly_discovered": True,
            "location": location,
        }

    def is_location_discovered(self, location_key: str) -> bool:
        """Check if a location has been discovered.

        Args:
            location_key: Location key to check.

        Returns:
            True if location is known, False otherwise.
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
            return False

        exists = (
            self.db.query(LocationDiscovery)
            .filter(
                LocationDiscovery.session_id == self.session_id,
                LocationDiscovery.location_id == location.id,
            )
            .first()
        )
        return exists is not None

    def get_known_locations(
        self,
        method: DiscoveryMethod | None = None,
        zone_key: str | None = None,
    ) -> list[Location]:
        """Get all discovered locations.

        Args:
            method: Optional filter by discovery method.
            zone_key: Optional filter to locations in a specific zone.

        Returns:
            List of discovered Locations.
        """
        query = (
            self.db.query(Location)
            .join(LocationDiscovery, LocationDiscovery.location_id == Location.id)
            .filter(LocationDiscovery.session_id == self.session_id)
        )

        if method is not None:
            query = query.filter(LocationDiscovery.discovery_method == method)

        if zone_key is not None:
            zone = self._zone_manager.get_zone(zone_key)
            if zone:
                query = query.join(
                    LocationZonePlacement,
                    LocationZonePlacement.location_id == Location.id,
                ).filter(LocationZonePlacement.zone_id == zone.id)

        return query.all()

    # =========================================================================
    # Auto-Discovery
    # =========================================================================

    def auto_discover_surroundings(self, zone_key: str) -> dict:
        """Auto-discover the current zone and visible surroundings.

        Called when entering a new zone. Discovers:
        - The current zone
        - Adjacent zones (based on visibility)
        - Visible locations in the current zone

        Args:
            zone_key: Current zone key.

        Returns:
            Dict with discovered zones and locations.
        """
        zone = self._zone_manager.get_zone(zone_key)
        if zone is None:
            return {
                "current_zone_discovered": False,
                "adjacent_zones_discovered": [],
                "locations_discovered": [],
            }

        # Discover current zone
        current_result = self.discover_zone(
            zone_key,
            method=DiscoveryMethod.VISITED,
        )

        # Discover adjacent zones (visible from here)
        adjacent_zones = self._zone_manager.get_adjacent_zones(zone_key)
        adjacent_discovered = []
        for adj_zone in adjacent_zones:
            result = self.discover_zone(
                adj_zone.zone_key,
                method=DiscoveryMethod.VISIBLE_FROM,
                source_zone_key=zone_key,
            )
            if result["newly_discovered"]:
                adjacent_discovered.append(adj_zone.zone_key)

        # Discover visible locations in this zone
        visible_locations = self._zone_manager.get_visible_locations_from_zone(zone_key)
        locations_discovered = []
        for location in visible_locations:
            result = self.discover_location(
                location.location_key,
                method=DiscoveryMethod.VISITED,
            )
            if result["newly_discovered"]:
                locations_discovered.append(location.location_key)

        return {
            "current_zone_discovered": current_result.get("newly_discovered", False),
            "adjacent_zones_discovered": adjacent_discovered,
            "locations_discovered": locations_discovered,
        }

    # =========================================================================
    # Map Viewing
    # =========================================================================

    def view_map(self, item_key: str) -> dict:
        """View a map item and discover its contents.

        Args:
            item_key: Map item key.

        Returns:
            Dict with:
            - success: bool
            - zones_discovered: list[str]
            - locations_discovered: list[str]
        """
        # Find the item
        item = (
            self.db.query(Item)
            .filter(
                Item.session_id == self.session_id,
                Item.item_key == item_key,
            )
            .first()
        )
        if item is None:
            return {
                "success": False,
                "reason": f"Item not found: {item_key}",
                "zones_discovered": [],
                "locations_discovered": [],
            }

        # Find the map extension
        map_item = (
            self.db.query(MapItem)
            .filter(MapItem.item_id == item.id)
            .first()
        )
        if map_item is None:
            return {
                "success": False,
                "reason": f"Item '{item_key}' is not a map",
                "zones_discovered": [],
                "locations_discovered": [],
            }

        zones_discovered = []
        locations_discovered = []

        # Discover zones on the map
        if map_item.revealed_zone_ids:
            for zone_id in map_item.revealed_zone_ids:
                zone = (
                    self.db.query(TerrainZone)
                    .filter(TerrainZone.id == zone_id)
                    .first()
                )
                if zone:
                    result = self.discover_zone(
                        zone.zone_key,
                        method=DiscoveryMethod.MAP_VIEWED,
                        source_map_key=item_key,
                    )
                    if result["newly_discovered"]:
                        zones_discovered.append(zone.zone_key)

        # Discover locations on the map
        if map_item.revealed_location_ids:
            for location_id in map_item.revealed_location_ids:
                location = (
                    self.db.query(Location)
                    .filter(Location.id == location_id)
                    .first()
                )
                if location:
                    result = self.discover_location(
                        location.location_key,
                        method=DiscoveryMethod.MAP_VIEWED,
                        source_map_key=item_key,
                    )
                    if result["newly_discovered"]:
                        locations_discovered.append(location.location_key)

        return {
            "success": True,
            "zones_discovered": zones_discovered,
            "locations_discovered": locations_discovered,
            "map_type": map_item.map_type.value,
        }

    # =========================================================================
    # Digital Map Access
    # =========================================================================

    def check_digital_access(
        self,
        include_unavailable: bool = False,
    ) -> list[DigitalMapAccess]:
        """Check what digital map services are available.

        Args:
            include_unavailable: If True, include unavailable services.

        Returns:
            List of DigitalMapAccess records.
        """
        query = self.db.query(DigitalMapAccess).filter(
            DigitalMapAccess.session_id == self.session_id
        )

        if not include_unavailable:
            query = query.filter(DigitalMapAccess.is_available == True)

        return query.all()
