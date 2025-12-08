"""Tests for MapManager - map item creation and management."""

import pytest

from src.database.models.enums import MapType, TerrainType
from src.database.models.navigation import DigitalMapAccess, MapItem
from src.managers.map_manager import MapManager
from tests.factories import (
    create_item,
    create_location,
    create_terrain_zone,
)


class TestMapManagerCreateMap:
    """Tests for creating map items."""

    def test_create_map_item(self, db_session, game_session):
        """create_map_item should create both Item and MapItem records."""
        zone1 = create_terrain_zone(db_session, game_session, zone_key="zone1")
        zone2 = create_terrain_zone(db_session, game_session, zone_key="zone2")
        db_session.commit()

        manager = MapManager(db_session, game_session)
        result = manager.create_map_item(
            item_key="regional_map",
            display_name="Regional Map",
            map_type=MapType.REGIONAL,
            revealed_zone_keys=["zone1", "zone2"],
        )

        assert result["success"] is True
        assert result["item"] is not None
        assert result["map_item"] is not None
        assert result["item"].item_key == "regional_map"
        assert result["map_item"].map_type == MapType.REGIONAL

    def test_create_map_with_locations(self, db_session, game_session):
        """create_map_item should support revealing locations."""
        loc1 = create_location(db_session, game_session, location_key="castle")
        loc2 = create_location(db_session, game_session, location_key="village")
        db_session.commit()

        manager = MapManager(db_session, game_session)
        result = manager.create_map_item(
            item_key="treasure_map",
            display_name="Treasure Map",
            map_type=MapType.DUNGEON,
            revealed_location_keys=["castle", "village"],
        )

        assert result["success"] is True
        assert result["map_item"].revealed_location_ids is not None
        assert len(result["map_item"].revealed_location_ids) == 2

    def test_create_map_with_coverage_zone(self, db_session, game_session):
        """create_map_item should support coverage zone for hierarchical maps."""
        region = create_terrain_zone(db_session, game_session, zone_key="darkwood_region")
        db_session.commit()

        manager = MapManager(db_session, game_session)
        result = manager.create_map_item(
            item_key="darkwood_map",
            display_name="Map of Darkwood",
            map_type=MapType.REGIONAL,
            coverage_zone_key="darkwood_region",
        )

        assert result["success"] is True
        assert result["map_item"].coverage_zone_id == region.id

    def test_create_incomplete_map(self, db_session, game_session):
        """create_map_item should support incomplete/damaged maps."""
        zone = create_terrain_zone(db_session, game_session, zone_key="partial_zone")
        db_session.commit()

        manager = MapManager(db_session, game_session)
        result = manager.create_map_item(
            item_key="torn_map",
            display_name="Torn Map Fragment",
            map_type=MapType.CITY,
            revealed_zone_keys=["partial_zone"],
            is_complete=False,
        )

        assert result["success"] is True
        assert result["map_item"].is_complete is False


class TestMapManagerGetMaps:
    """Tests for querying map items."""

    def test_get_map_item(self, db_session, game_session):
        """get_map_item should return map data for an item."""
        manager = MapManager(db_session, game_session)
        manager.create_map_item(
            item_key="world_map",
            display_name="World Map",
            map_type=MapType.WORLD,
        )
        db_session.commit()

        map_data = manager.get_map_item("world_map")

        assert map_data is not None
        assert map_data["item_key"] == "world_map"
        assert map_data["map_type"] == MapType.WORLD

    def test_get_map_item_not_a_map(self, db_session, game_session):
        """get_map_item should return None for non-map items."""
        create_item(db_session, game_session, item_key="sword")
        db_session.commit()

        manager = MapManager(db_session, game_session)
        map_data = manager.get_map_item("sword")

        assert map_data is None

    def test_is_map_item(self, db_session, game_session):
        """is_map_item should correctly identify map items."""
        manager = MapManager(db_session, game_session)
        manager.create_map_item(
            item_key="city_map",
            display_name="City Map",
            map_type=MapType.CITY,
        )
        create_item(db_session, game_session, item_key="potion")
        db_session.commit()

        assert manager.is_map_item("city_map") is True
        assert manager.is_map_item("potion") is False
        assert manager.is_map_item("nonexistent") is False

    def test_get_all_maps(self, db_session, game_session):
        """get_all_maps should return all map items in session."""
        manager = MapManager(db_session, game_session)
        manager.create_map_item("map1", "Map 1", MapType.CITY)
        manager.create_map_item("map2", "Map 2", MapType.REGIONAL)
        manager.create_map_item("map3", "Map 3", MapType.WORLD)
        create_item(db_session, game_session, item_key="not_a_map")
        db_session.commit()

        maps = manager.get_all_maps()

        assert len(maps) == 3
        map_keys = {m["item_key"] for m in maps}
        assert map_keys == {"map1", "map2", "map3"}


class TestMapManagerDigitalAccess:
    """Tests for digital map access management."""

    def test_setup_digital_access(self, db_session, game_session):
        """setup_digital_access should create a DigitalMapAccess record."""
        manager = MapManager(db_session, game_session)
        result = manager.setup_digital_access(
            service_key="google_maps",
            display_name="Google Maps",
            coverage_level=MapType.CITY,
            requires_device=True,
            requires_connection=True,
        )
        db_session.commit()

        assert result["success"] is True
        assert result["service"].service_key == "google_maps"
        assert result["service"].requires_device is True

    def test_setup_digital_access_for_setting(self, db_session, game_session):
        """setup_digital_access_for_setting should configure based on game setting."""
        manager = MapManager(db_session, game_session)

        # Modern setting should have digital maps
        result = manager.setup_digital_access_for_setting("contemporary")

        assert result["services_created"] > 0

    def test_setup_digital_access_fantasy_setting(self, db_session, game_session):
        """Fantasy settings should not have digital maps by default."""
        manager = MapManager(db_session, game_session)

        result = manager.setup_digital_access_for_setting("fantasy")

        assert result["services_created"] == 0

    def test_toggle_digital_access(self, db_session, game_session):
        """toggle_digital_access should enable/disable a service."""
        manager = MapManager(db_session, game_session)
        manager.setup_digital_access(
            service_key="gps",
            display_name="GPS",
            coverage_level=MapType.REGIONAL,
        )
        db_session.commit()

        # Disable
        result = manager.toggle_digital_access("gps", available=False, reason="No signal")

        assert result["success"] is True

        service = (
            db_session.query(DigitalMapAccess)
            .filter(DigitalMapAccess.service_key == "gps")
            .first()
        )
        assert service.is_available is False
        assert service.unavailable_reason == "No signal"

        # Re-enable
        manager.toggle_digital_access("gps", available=True)
        db_session.refresh(service)
        assert service.is_available is True


class TestMapManagerMapContents:
    """Tests for querying map contents."""

    def test_get_map_zones(self, db_session, game_session):
        """get_map_zones should return zones revealed by a map."""
        zone1 = create_terrain_zone(db_session, game_session, zone_key="zone1")
        zone2 = create_terrain_zone(db_session, game_session, zone_key="zone2")
        db_session.commit()

        manager = MapManager(db_session, game_session)
        manager.create_map_item(
            item_key="test_map",
            display_name="Test Map",
            map_type=MapType.REGIONAL,
            revealed_zone_keys=["zone1", "zone2"],
        )
        db_session.commit()

        zones = manager.get_map_zones("test_map")

        assert len(zones) == 2
        zone_keys = {z.zone_key for z in zones}
        assert zone_keys == {"zone1", "zone2"}

    def test_get_map_locations(self, db_session, game_session):
        """get_map_locations should return locations revealed by a map."""
        loc1 = create_location(db_session, game_session, location_key="loc1")
        loc2 = create_location(db_session, game_session, location_key="loc2")
        db_session.commit()

        manager = MapManager(db_session, game_session)
        manager.create_map_item(
            item_key="location_map",
            display_name="Location Map",
            map_type=MapType.CITY,
            revealed_location_keys=["loc1", "loc2"],
        )
        db_session.commit()

        locations = manager.get_map_locations("location_map")

        assert len(locations) == 2
        loc_keys = {loc.location_key for loc in locations}
        assert loc_keys == {"loc1", "loc2"}
