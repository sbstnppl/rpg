"""MapManager for map item creation and digital map access management."""

from sqlalchemy.orm import Session

from src.database.models.enums import ItemType, MapType
from src.database.models.items import Item
from src.database.models.navigation import (
    DigitalMapAccess,
    MapItem,
    TerrainZone,
)
from src.database.models.session import GameSession
from src.database.models.world import Location
from src.managers.base import BaseManager
from src.managers.zone_manager import ZoneManager


# Digital map service configurations by setting
DIGITAL_MAP_CONFIGS = {
    "contemporary": [
        {
            "service_key": "google_maps",
            "display_name": "Google Maps",
            "coverage_level": MapType.CITY,
            "requires_device": True,
            "requires_connection": True,
        },
        {
            "service_key": "offline_maps",
            "display_name": "Offline Maps",
            "coverage_level": MapType.REGIONAL,
            "requires_device": True,
            "requires_connection": False,
        },
    ],
    "scifi": [
        {
            "service_key": "starship_nav",
            "display_name": "Starship Navigation",
            "coverage_level": MapType.WORLD,
            "requires_device": False,
            "requires_connection": False,
        },
        {
            "service_key": "planetary_survey",
            "display_name": "Planetary Survey Database",
            "coverage_level": MapType.REGIONAL,
            "requires_device": True,
            "requires_connection": True,
        },
    ],
    "cyberpunk": [
        {
            "service_key": "ar_overlay",
            "display_name": "AR Navigation Overlay",
            "coverage_level": MapType.CITY,
            "requires_device": True,
            "requires_connection": True,
        },
        {
            "service_key": "dark_net_maps",
            "display_name": "Darknet Location Database",
            "coverage_level": MapType.BUILDING,
            "requires_device": True,
            "requires_connection": True,
        },
    ],
    # Fantasy and historical settings have no digital maps
    "fantasy": [],
    "medieval": [],
    "historical": [],
}


class MapManager(BaseManager):
    """Manager for map item operations and digital map access.

    Handles:
    - Creating map items that reveal zones/locations
    - Managing digital map services (modern/sci-fi settings)
    - Querying map contents
    - Setting-based digital access configuration
    """

    def __init__(self, db: Session, game_session: GameSession) -> None:
        """Initialize MapManager.

        Args:
            db: SQLAlchemy database session.
            game_session: Current game session.
        """
        super().__init__(db, game_session)
        self._zone_manager = ZoneManager(db, game_session)

    # =========================================================================
    # Map Item Creation
    # =========================================================================

    def create_map_item(
        self,
        item_key: str,
        display_name: str,
        map_type: MapType,
        description: str | None = None,
        revealed_zone_keys: list[str] | None = None,
        revealed_location_keys: list[str] | None = None,
        coverage_zone_key: str | None = None,
        is_complete: bool = True,
    ) -> dict:
        """Create a map item that reveals zones and/or locations.

        Args:
            item_key: Unique key for the item.
            display_name: Display name for the map.
            map_type: Type of map (world, regional, city, etc.).
            description: Optional description.
            revealed_zone_keys: Zone keys this map reveals.
            revealed_location_keys: Location keys this map reveals.
            coverage_zone_key: Root zone for hierarchical coverage.
            is_complete: Whether the map is complete or partial/damaged.

        Returns:
            Dict with:
            - success: bool
            - item: Item
            - map_item: MapItem
        """
        # Create the base item
        item = Item(
            session_id=self.session_id,
            item_key=item_key,
            display_name=display_name,
            item_type=ItemType.MISC,
            description=description or f"A {map_type.value} map.",
        )
        self.db.add(item)
        self.db.flush()

        # Resolve zone IDs
        revealed_zone_ids = None
        if revealed_zone_keys:
            revealed_zone_ids = []
            for zone_key in revealed_zone_keys:
                zone = self._zone_manager.get_zone(zone_key)
                if zone:
                    revealed_zone_ids.append(zone.id)

        # Resolve location IDs
        revealed_location_ids = None
        if revealed_location_keys:
            revealed_location_ids = []
            for location_key in revealed_location_keys:
                location = (
                    self.db.query(Location)
                    .filter(
                        Location.session_id == self.session_id,
                        Location.location_key == location_key,
                    )
                    .first()
                )
                if location:
                    revealed_location_ids.append(location.id)

        # Resolve coverage zone
        coverage_zone_id = None
        if coverage_zone_key:
            coverage_zone = self._zone_manager.get_zone(coverage_zone_key)
            if coverage_zone:
                coverage_zone_id = coverage_zone.id

        # Create the map extension
        map_item = MapItem(
            session_id=self.session_id,
            item_id=item.id,
            map_type=map_type,
            coverage_zone_id=coverage_zone_id,
            is_complete=is_complete,
            revealed_zone_ids=revealed_zone_ids,
            revealed_location_ids=revealed_location_ids,
        )
        self.db.add(map_item)
        self.db.flush()

        return {
            "success": True,
            "item": item,
            "map_item": map_item,
        }

    # =========================================================================
    # Map Item Queries
    # =========================================================================

    def get_map_item(self, item_key: str) -> dict | None:
        """Get map data for an item.

        Args:
            item_key: Item key.

        Returns:
            Dict with map data, or None if not a map.
        """
        item = (
            self.db.query(Item)
            .filter(
                Item.session_id == self.session_id,
                Item.item_key == item_key,
            )
            .first()
        )
        if item is None:
            return None

        map_item = (
            self.db.query(MapItem)
            .filter(MapItem.item_id == item.id)
            .first()
        )
        if map_item is None:
            return None

        return {
            "item_key": item.item_key,
            "display_name": item.display_name,
            "map_type": map_item.map_type,
            "is_complete": map_item.is_complete,
            "coverage_zone_id": map_item.coverage_zone_id,
            "revealed_zone_ids": map_item.revealed_zone_ids,
            "revealed_location_ids": map_item.revealed_location_ids,
        }

    def is_map_item(self, item_key: str) -> bool:
        """Check if an item is a map.

        Args:
            item_key: Item key.

        Returns:
            True if the item is a map.
        """
        return self.get_map_item(item_key) is not None

    def get_all_maps(self) -> list[dict]:
        """Get all map items in the session.

        Returns:
            List of map data dicts.
        """
        map_items = (
            self.db.query(MapItem)
            .filter(MapItem.session_id == self.session_id)
            .all()
        )

        result = []
        for map_item in map_items:
            item = (
                self.db.query(Item)
                .filter(Item.id == map_item.item_id)
                .first()
            )
            if item:
                result.append({
                    "item_key": item.item_key,
                    "display_name": item.display_name,
                    "map_type": map_item.map_type,
                    "is_complete": map_item.is_complete,
                })

        return result

    def get_map_zones(self, item_key: str) -> list[TerrainZone]:
        """Get zones revealed by a map.

        Args:
            item_key: Map item key.

        Returns:
            List of TerrainZones.
        """
        map_data = self.get_map_item(item_key)
        if map_data is None:
            return []

        zone_ids = map_data.get("revealed_zone_ids") or []
        if not zone_ids:
            return []

        return (
            self.db.query(TerrainZone)
            .filter(TerrainZone.id.in_(zone_ids))
            .all()
        )

    def get_map_locations(self, item_key: str) -> list[Location]:
        """Get locations revealed by a map.

        Args:
            item_key: Map item key.

        Returns:
            List of Locations.
        """
        map_data = self.get_map_item(item_key)
        if map_data is None:
            return []

        location_ids = map_data.get("revealed_location_ids") or []
        if not location_ids:
            return []

        return (
            self.db.query(Location)
            .filter(Location.id.in_(location_ids))
            .all()
        )

    # =========================================================================
    # Digital Map Access
    # =========================================================================

    def setup_digital_access(
        self,
        service_key: str,
        display_name: str,
        coverage_level: MapType,
        requires_device: bool = True,
        requires_connection: bool = True,
    ) -> dict:
        """Set up a digital map service for the session.

        Args:
            service_key: Unique key for the service.
            display_name: Display name.
            coverage_level: Detail level the service provides.
            requires_device: Whether a device is needed.
            requires_connection: Whether network connection is needed.

        Returns:
            Dict with:
            - success: bool
            - service: DigitalMapAccess
        """
        # Check if already exists
        existing = (
            self.db.query(DigitalMapAccess)
            .filter(
                DigitalMapAccess.session_id == self.session_id,
                DigitalMapAccess.service_key == service_key,
            )
            .first()
        )

        if existing:
            return {
                "success": True,
                "service": existing,
                "already_existed": True,
            }

        service = DigitalMapAccess(
            session_id=self.session_id,
            service_key=service_key,
            display_name=display_name,
            coverage_map_type=coverage_level,
            requires_device=requires_device,
            requires_connection=requires_connection,
            is_available=True,
        )
        self.db.add(service)
        self.db.flush()

        return {
            "success": True,
            "service": service,
            "already_existed": False,
        }

    def setup_digital_access_for_setting(self, setting: str) -> dict:
        """Configure digital map access based on game setting.

        Args:
            setting: Game setting (fantasy, contemporary, scifi, etc.).

        Returns:
            Dict with:
            - services_created: int
            - services: list[DigitalMapAccess]
        """
        configs = DIGITAL_MAP_CONFIGS.get(setting.lower(), [])

        services = []
        for config in configs:
            result = self.setup_digital_access(
                service_key=config["service_key"],
                display_name=config["display_name"],
                coverage_level=config["coverage_level"],
                requires_device=config.get("requires_device", True),
                requires_connection=config.get("requires_connection", True),
            )
            if result["success"] and not result.get("already_existed"):
                services.append(result["service"])

        return {
            "services_created": len(services),
            "services": services,
        }

    def toggle_digital_access(
        self,
        service_key: str,
        available: bool,
        reason: str | None = None,
    ) -> dict:
        """Toggle availability of a digital map service.

        Args:
            service_key: Service key.
            available: Whether the service should be available.
            reason: Reason for unavailability (if disabling).

        Returns:
            Dict with:
            - success: bool
        """
        service = (
            self.db.query(DigitalMapAccess)
            .filter(
                DigitalMapAccess.session_id == self.session_id,
                DigitalMapAccess.service_key == service_key,
            )
            .first()
        )

        if service is None:
            return {
                "success": False,
                "reason": f"Service not found: {service_key}",
            }

        service.is_available = available
        if available:
            service.unavailable_reason = None
        else:
            service.unavailable_reason = reason

        self.db.flush()

        return {
            "success": True,
            "service": service,
        }
