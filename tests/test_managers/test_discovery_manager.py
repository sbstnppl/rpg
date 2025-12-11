"""Tests for DiscoveryManager - fog of war and discovery mechanics."""

import pytest

from src.database.models.enums import DiscoveryMethod, MapType, TerrainType, VisibilityRange
from src.database.models.navigation import LocationDiscovery, ZoneDiscovery
from src.managers.discovery_manager import DiscoveryManager
from tests.factories import (
    create_item,
    create_location,
    create_location_zone_placement,
    create_map_item,
    create_terrain_zone,
    create_zone_connection,
    create_entity,
)


class TestDiscoveryManagerZones:
    """Tests for zone discovery."""

    def test_discover_zone_creates_record(self, db_session, game_session):
        """discover_zone should create a ZoneDiscovery record."""
        zone = create_terrain_zone(db_session, game_session, zone_key="forest")
        db_session.commit()

        manager = DiscoveryManager(db_session, game_session)
        result = manager.discover_zone(
            "forest",
            method=DiscoveryMethod.VISITED,
        )
        db_session.commit()

        assert result["success"] is True
        assert result["newly_discovered"] is True

        # Verify record exists
        discovery = (
            db_session.query(ZoneDiscovery)
            .filter(
                ZoneDiscovery.session_id == game_session.id,
                ZoneDiscovery.zone_id == zone.id,
            )
            .first()
        )
        assert discovery is not None
        assert discovery.discovery_method == DiscoveryMethod.VISITED

    def test_discover_zone_already_known(self, db_session, game_session):
        """discover_zone should return success but not newly_discovered for known zones."""
        zone = create_terrain_zone(db_session, game_session, zone_key="forest")
        db_session.commit()

        manager = DiscoveryManager(db_session, game_session)
        manager.discover_zone("forest", method=DiscoveryMethod.VISITED)
        db_session.commit()

        # Discover again
        result = manager.discover_zone("forest", method=DiscoveryMethod.TOLD_BY_NPC)

        assert result["success"] is True
        assert result["newly_discovered"] is False

    def test_discover_zone_with_source_entity(self, db_session, game_session):
        """discover_zone should track the source entity when told by NPC."""
        zone = create_terrain_zone(db_session, game_session, zone_key="forest")
        npc = create_entity(db_session, game_session, entity_key="guide_npc")
        db_session.commit()

        manager = DiscoveryManager(db_session, game_session)
        result = manager.discover_zone(
            "forest",
            method=DiscoveryMethod.TOLD_BY_NPC,
            source_entity_key="guide_npc",
        )
        db_session.commit()

        assert result["success"] is True

        discovery = (
            db_session.query(ZoneDiscovery)
            .filter(ZoneDiscovery.zone_id == zone.id)
            .first()
        )
        assert discovery.source_entity_id == npc.id

    def test_is_zone_discovered(self, db_session, game_session):
        """is_zone_discovered should return correct status."""
        create_terrain_zone(db_session, game_session, zone_key="known_zone")
        create_terrain_zone(db_session, game_session, zone_key="unknown_zone")
        db_session.commit()

        manager = DiscoveryManager(db_session, game_session)
        manager.discover_zone("known_zone", method=DiscoveryMethod.VISITED)
        db_session.commit()

        assert manager.is_zone_discovered("known_zone") is True
        assert manager.is_zone_discovered("unknown_zone") is False

    def test_get_known_zones(self, db_session, game_session):
        """get_known_zones should return all discovered zones."""
        create_terrain_zone(db_session, game_session, zone_key="zone1")
        create_terrain_zone(db_session, game_session, zone_key="zone2")
        create_terrain_zone(db_session, game_session, zone_key="zone3")
        db_session.commit()

        manager = DiscoveryManager(db_session, game_session)
        manager.discover_zone("zone1", method=DiscoveryMethod.VISITED)
        manager.discover_zone("zone2", method=DiscoveryMethod.MAP_VIEWED)
        db_session.commit()

        known = manager.get_known_zones()
        known_keys = {z.zone_key for z in known}

        assert known_keys == {"zone1", "zone2"}
        assert "zone3" not in known_keys


class TestDiscoveryManagerLocations:
    """Tests for location discovery."""

    def test_discover_location_creates_record(self, db_session, game_session):
        """discover_location should create a LocationDiscovery record."""
        location = create_location(db_session, game_session, location_key="tavern")
        db_session.commit()

        manager = DiscoveryManager(db_session, game_session)
        result = manager.discover_location(
            "tavern",
            method=DiscoveryMethod.VISITED,
        )
        db_session.commit()

        assert result["success"] is True
        assert result["newly_discovered"] is True

        discovery = (
            db_session.query(LocationDiscovery)
            .filter(
                LocationDiscovery.session_id == game_session.id,
                LocationDiscovery.location_id == location.id,
            )
            .first()
        )
        assert discovery is not None

    def test_discover_location_already_known(self, db_session, game_session):
        """discover_location should handle already-known locations."""
        create_location(db_session, game_session, location_key="tavern")
        db_session.commit()

        manager = DiscoveryManager(db_session, game_session)
        manager.discover_location("tavern", method=DiscoveryMethod.VISITED)
        db_session.commit()

        result = manager.discover_location("tavern", method=DiscoveryMethod.TOLD_BY_NPC)

        assert result["success"] is True
        assert result["newly_discovered"] is False

    def test_is_location_discovered(self, db_session, game_session):
        """is_location_discovered should return correct status."""
        create_location(db_session, game_session, location_key="known_loc")
        create_location(db_session, game_session, location_key="unknown_loc")
        db_session.commit()

        manager = DiscoveryManager(db_session, game_session)
        manager.discover_location("known_loc", method=DiscoveryMethod.VISITED)
        db_session.commit()

        assert manager.is_location_discovered("known_loc") is True
        assert manager.is_location_discovered("unknown_loc") is False

    def test_get_known_locations(self, db_session, game_session):
        """get_known_locations should return all discovered locations."""
        create_location(db_session, game_session, location_key="loc1")
        create_location(db_session, game_session, location_key="loc2")
        create_location(db_session, game_session, location_key="loc3")
        db_session.commit()

        manager = DiscoveryManager(db_session, game_session)
        manager.discover_location("loc1", method=DiscoveryMethod.VISITED)
        manager.discover_location("loc2", method=DiscoveryMethod.MAP_VIEWED)
        db_session.commit()

        known = manager.get_known_locations()
        known_keys = {loc.location_key for loc in known}

        assert known_keys == {"loc1", "loc2"}


class TestDiscoveryManagerAutoDiscover:
    """Tests for automatic discovery on zone entry."""

    def test_auto_discover_current_zone(self, db_session, game_session):
        """auto_discover_surroundings should discover the current zone."""
        create_terrain_zone(db_session, game_session, zone_key="current_zone")
        db_session.commit()

        manager = DiscoveryManager(db_session, game_session)
        result = manager.auto_discover_surroundings("current_zone")
        db_session.commit()

        assert result["current_zone_discovered"] is True
        assert manager.is_zone_discovered("current_zone")

    def test_auto_discover_adjacent_zones(self, db_session, game_session):
        """auto_discover_surroundings should discover visible adjacent zones."""
        center = create_terrain_zone(
            db_session,
            game_session,
            zone_key="center",
            visibility_range=VisibilityRange.FAR,
        )
        zone_north = create_terrain_zone(db_session, game_session, zone_key="north")
        zone_south = create_terrain_zone(db_session, game_session, zone_key="south")
        db_session.flush()

        create_zone_connection(db_session, game_session, center, zone_north, direction="north")
        create_zone_connection(db_session, game_session, center, zone_south, direction="south")
        db_session.commit()

        manager = DiscoveryManager(db_session, game_session)
        result = manager.auto_discover_surroundings("center")
        db_session.commit()

        assert len(result["adjacent_zones_discovered"]) >= 2
        assert manager.is_zone_discovered("north")
        assert manager.is_zone_discovered("south")

    def test_auto_discover_visible_locations(self, db_session, game_session):
        """auto_discover_surroundings should discover visible locations in zone."""
        zone = create_terrain_zone(db_session, game_session, zone_key="village_zone")
        visible_loc = create_location(db_session, game_session, location_key="windmill")
        hidden_loc = create_location(db_session, game_session, location_key="secret_cave")
        db_session.flush()

        placement1 = create_location_zone_placement(db_session, game_session, visible_loc, zone)
        placement1.visibility = "visible_from_zone"
        placement2 = create_location_zone_placement(db_session, game_session, hidden_loc, zone)
        placement2.visibility = "hidden"
        db_session.commit()

        manager = DiscoveryManager(db_session, game_session)
        result = manager.auto_discover_surroundings("village_zone")
        db_session.commit()

        assert manager.is_location_discovered("windmill")
        assert not manager.is_location_discovered("secret_cave")


class TestDiscoveryManagerMaps:
    """Tests for map-based discovery."""

    def test_view_map_discovers_zones(self, db_session, game_session):
        """view_map should discover zones covered by the map."""
        # Create zones
        region = create_terrain_zone(db_session, game_session, zone_key="region")
        zone1 = create_terrain_zone(db_session, game_session, zone_key="zone1")
        zone2 = create_terrain_zone(db_session, game_session, zone_key="zone2")
        db_session.flush()

        # Create a map item
        item = create_item(db_session, game_session, item_key="regional_map")
        map_item = create_map_item(
            db_session,
            game_session,
            item=item,
            map_type=MapType.REGIONAL,
            revealed_zone_ids=[zone1.id, zone2.id],
        )
        db_session.commit()

        manager = DiscoveryManager(db_session, game_session)
        result = manager.view_map("regional_map")
        db_session.commit()

        assert result["success"] is True
        assert len(result["zones_discovered"]) == 2
        assert manager.is_zone_discovered("zone1")
        assert manager.is_zone_discovered("zone2")

    def test_view_map_discovers_locations(self, db_session, game_session):
        """view_map should discover locations marked on the map."""
        loc1 = create_location(db_session, game_session, location_key="castle")
        loc2 = create_location(db_session, game_session, location_key="village")
        db_session.flush()

        item = create_item(db_session, game_session, item_key="treasure_map")
        map_item = create_map_item(
            db_session,
            game_session,
            item=item,
            map_type=MapType.CITY,
            revealed_location_ids=[loc1.id, loc2.id],
        )
        db_session.commit()

        manager = DiscoveryManager(db_session, game_session)
        result = manager.view_map("treasure_map")
        db_session.commit()

        assert result["success"] is True
        assert manager.is_location_discovered("castle")
        assert manager.is_location_discovered("village")

    def test_view_map_invalid_item(self, db_session, game_session):
        """view_map should fail for non-existent map items."""
        manager = DiscoveryManager(db_session, game_session)
        result = manager.view_map("nonexistent_map")

        assert result["success"] is False
        assert "not found" in result["reason"].lower()

    def test_view_map_coverage_zone_discovers_descendants(self, db_session, game_session):
        """view_map with coverage_zone should discover zone and all descendants."""
        # Create hierarchical zones: region -> sub_region -> village
        region = create_terrain_zone(db_session, game_session, zone_key="northern_region")
        db_session.flush()

        sub_region = create_terrain_zone(db_session, game_session, zone_key="highland_sub")
        sub_region.parent_zone_id = region.id
        db_session.flush()

        village_zone = create_terrain_zone(db_session, game_session, zone_key="village_area")
        village_zone.parent_zone_id = sub_region.id
        db_session.flush()

        # Create a map that covers the region (should discover all children)
        item = create_item(db_session, game_session, item_key="northern_map")
        map_item = create_map_item(
            db_session,
            game_session,
            item=item,
            map_type=MapType.REGIONAL,
        )
        map_item.coverage_zone_id = region.id
        db_session.commit()

        manager = DiscoveryManager(db_session, game_session)
        result = manager.view_map("northern_map")
        db_session.commit()

        assert result["success"] is True
        # Should have discovered: region + sub_region + village_area = 3 zones
        assert len(result["zones_discovered"]) == 3
        assert manager.is_zone_discovered("northern_region")
        assert manager.is_zone_discovered("highland_sub")
        assert manager.is_zone_discovered("village_area")


class TestDiscoveryManagerDigitalAccess:
    """Tests for digital map access (modern/sci-fi settings)."""

    def test_check_digital_access_no_services(self, db_session, game_session):
        """check_digital_access should return empty list when no services exist."""
        manager = DiscoveryManager(db_session, game_session)
        services = manager.check_digital_access()

        assert services == []

    def test_check_digital_access_returns_available(self, db_session, game_session):
        """check_digital_access should return available digital services."""
        from tests.factories import create_digital_map_access

        create_digital_map_access(
            db_session,
            game_session,
            service_key="google_maps",
            is_available=True,
        )
        create_digital_map_access(
            db_session,
            game_session,
            service_key="offline_gps",
            is_available=False,
        )
        db_session.commit()

        manager = DiscoveryManager(db_session, game_session)
        services = manager.check_digital_access()

        assert len(services) == 1
        assert services[0].service_key == "google_maps"

    def test_check_digital_access_all(self, db_session, game_session):
        """check_digital_access with include_unavailable should return all."""
        from tests.factories import create_digital_map_access

        create_digital_map_access(
            db_session,
            game_session,
            service_key="google_maps",
            is_available=True,
        )
        create_digital_map_access(
            db_session,
            game_session,
            service_key="offline_gps",
            is_available=False,
        )
        db_session.commit()

        manager = DiscoveryManager(db_session, game_session)
        services = manager.check_digital_access(include_unavailable=True)

        assert len(services) == 2


class TestDiscoveryManagerFiltering:
    """Tests for filtering discovered content."""

    def test_get_known_zones_by_method(self, db_session, game_session):
        """get_known_zones should filter by discovery method."""
        create_terrain_zone(db_session, game_session, zone_key="visited_zone")
        create_terrain_zone(db_session, game_session, zone_key="mapped_zone")
        create_terrain_zone(db_session, game_session, zone_key="told_zone")
        db_session.commit()

        manager = DiscoveryManager(db_session, game_session)
        manager.discover_zone("visited_zone", method=DiscoveryMethod.VISITED)
        manager.discover_zone("mapped_zone", method=DiscoveryMethod.MAP_VIEWED)
        manager.discover_zone("told_zone", method=DiscoveryMethod.TOLD_BY_NPC)
        db_session.commit()

        visited_only = manager.get_known_zones(method=DiscoveryMethod.VISITED)
        assert len(visited_only) == 1
        assert visited_only[0].zone_key == "visited_zone"

    def test_get_known_locations_in_zone(self, db_session, game_session):
        """get_known_locations should filter by zone."""
        zone1 = create_terrain_zone(db_session, game_session, zone_key="zone1")
        zone2 = create_terrain_zone(db_session, game_session, zone_key="zone2")
        loc1 = create_location(db_session, game_session, location_key="loc1")
        loc2 = create_location(db_session, game_session, location_key="loc2")
        db_session.flush()

        create_location_zone_placement(db_session, game_session, loc1, zone1)
        create_location_zone_placement(db_session, game_session, loc2, zone2)
        db_session.commit()

        manager = DiscoveryManager(db_session, game_session)
        manager.discover_location("loc1", method=DiscoveryMethod.VISITED)
        manager.discover_location("loc2", method=DiscoveryMethod.VISITED)
        db_session.commit()

        locations_in_zone1 = manager.get_known_locations(zone_key="zone1")
        assert len(locations_in_zone1) == 1
        assert locations_in_zone1[0].location_key == "loc1"
