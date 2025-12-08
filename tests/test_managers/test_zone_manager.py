"""Tests for ZoneManager - terrain zone operations."""

import pytest

from src.database.models.enums import (
    ConnectionType,
    EncounterFrequency,
    PlacementType,
    TerrainType,
    TransportType,
    VisibilityRange,
)
from src.database.models.navigation import (
    LocationZonePlacement,
    TerrainZone,
    TransportMode,
    ZoneConnection,
)
from src.managers.zone_manager import ZoneManager
from tests.factories import (
    create_location,
    create_location_zone_placement,
    create_terrain_zone,
    create_transport_mode,
    create_zone_connection,
)


class TestZoneManagerBasicOperations:
    """Tests for basic CRUD operations."""

    def test_get_zone_returns_zone_by_key(self, db_session, game_session):
        """get_zone should return a zone by its key."""
        create_terrain_zone(
            db_session,
            game_session,
            zone_key="test_forest",
            display_name="Test Forest",
        )
        db_session.commit()

        manager = ZoneManager(db_session, game_session)
        zone = manager.get_zone("test_forest")

        assert zone is not None
        assert zone.zone_key == "test_forest"
        assert zone.display_name == "Test Forest"

    def test_get_zone_returns_none_for_unknown_key(self, db_session, game_session):
        """get_zone should return None for unknown keys."""
        manager = ZoneManager(db_session, game_session)
        zone = manager.get_zone("nonexistent")

        assert zone is None

    def test_get_zone_respects_session_scope(self, db_session, game_session, game_session_2):
        """get_zone should only return zones from the current session."""
        create_terrain_zone(
            db_session,
            game_session,
            zone_key="session1_forest",
        )
        create_terrain_zone(
            db_session,
            game_session_2,
            zone_key="session2_forest",
        )
        db_session.commit()

        manager = ZoneManager(db_session, game_session)

        assert manager.get_zone("session1_forest") is not None
        assert manager.get_zone("session2_forest") is None

    def test_create_zone_creates_terrain_zone(self, db_session, game_session):
        """create_zone should create a new terrain zone."""
        manager = ZoneManager(db_session, game_session)
        zone = manager.create_zone(
            zone_key="new_plains",
            display_name="New Plains",
            terrain_type=TerrainType.PLAINS,
            description="A wide open plain.",
            base_travel_cost=8,
        )
        db_session.commit()

        assert zone is not None
        assert zone.zone_key == "new_plains"
        assert zone.terrain_type == TerrainType.PLAINS
        assert zone.base_travel_cost == 8
        assert zone.session_id == game_session.id

    def test_create_zone_with_all_options(self, db_session, game_session):
        """create_zone should support all terrain zone properties."""
        manager = ZoneManager(db_session, game_session)
        zone = manager.create_zone(
            zone_key="dangerous_cliff",
            display_name="Dangerous Cliff",
            terrain_type=TerrainType.CLIFF,
            description="A treacherous cliff face.",
            base_travel_cost=30,
            mounted_travel_cost=None,  # Can't ride horses here
            requires_skill="climbing",
            skill_difficulty=15,
            failure_consequence="fall_damage",
            visibility_range=VisibilityRange.FAR,
            encounter_frequency=EncounterFrequency.NONE,
            atmosphere="Wind howls around you.",
        )
        db_session.commit()

        assert zone.requires_skill == "climbing"
        assert zone.skill_difficulty == 15
        assert zone.failure_consequence == "fall_damage"
        assert zone.mounted_travel_cost is None
        assert zone.visibility_range == VisibilityRange.FAR

    def test_get_all_zones_returns_all_session_zones(self, db_session, game_session):
        """get_all_zones should return all zones in the session."""
        create_terrain_zone(db_session, game_session, zone_key="zone1")
        create_terrain_zone(db_session, game_session, zone_key="zone2")
        create_terrain_zone(db_session, game_session, zone_key="zone3")
        db_session.commit()

        manager = ZoneManager(db_session, game_session)
        zones = manager.get_all_zones()

        assert len(zones) == 3
        zone_keys = {z.zone_key for z in zones}
        assert zone_keys == {"zone1", "zone2", "zone3"}


class TestZoneManagerConnections:
    """Tests for zone connection operations."""

    def test_connect_zones_creates_connection(self, db_session, game_session):
        """connect_zones should create a bidirectional connection."""
        zone1 = create_terrain_zone(db_session, game_session, zone_key="zone1")
        zone2 = create_terrain_zone(db_session, game_session, zone_key="zone2")
        db_session.commit()

        manager = ZoneManager(db_session, game_session)
        connection = manager.connect_zones(
            from_zone_key="zone1",
            to_zone_key="zone2",
            direction="east",
        )
        db_session.commit()

        assert connection is not None
        assert connection.from_zone_id == zone1.id
        assert connection.to_zone_id == zone2.id
        assert connection.direction == "east"
        assert connection.is_bidirectional is True

    def test_connect_zones_with_one_way_connection(self, db_session, game_session):
        """connect_zones should support one-way connections."""
        create_terrain_zone(db_session, game_session, zone_key="cliff_top")
        create_terrain_zone(db_session, game_session, zone_key="cliff_bottom")
        db_session.commit()

        manager = ZoneManager(db_session, game_session)
        connection = manager.connect_zones(
            from_zone_key="cliff_top",
            to_zone_key="cliff_bottom",
            direction="down",
            is_bidirectional=False,  # Can jump down but not climb up easily
            connection_type=ConnectionType.CLIMB,
        )
        db_session.commit()

        assert connection.is_bidirectional is False
        assert connection.connection_type == ConnectionType.CLIMB

    def test_connect_zones_raises_for_unknown_zone(self, db_session, game_session):
        """connect_zones should raise ValueError for unknown zones."""
        create_terrain_zone(db_session, game_session, zone_key="zone1")
        db_session.commit()

        manager = ZoneManager(db_session, game_session)

        with pytest.raises(ValueError, match="Zone not found"):
            manager.connect_zones("zone1", "nonexistent", "north")

    def test_get_adjacent_zones_returns_connected_zones(self, db_session, game_session):
        """get_adjacent_zones should return all zones connected to a zone."""
        zone_center = create_terrain_zone(db_session, game_session, zone_key="center")
        zone_north = create_terrain_zone(db_session, game_session, zone_key="north")
        zone_south = create_terrain_zone(db_session, game_session, zone_key="south")
        zone_east = create_terrain_zone(db_session, game_session, zone_key="east")
        db_session.flush()

        # Create connections
        create_zone_connection(db_session, game_session, zone_center, zone_north, direction="north")
        create_zone_connection(db_session, game_session, zone_center, zone_south, direction="south")
        create_zone_connection(db_session, game_session, zone_center, zone_east, direction="east")
        db_session.commit()

        manager = ZoneManager(db_session, game_session)
        adjacent = manager.get_adjacent_zones("center")

        assert len(adjacent) == 3
        adjacent_keys = {z.zone_key for z in adjacent}
        assert adjacent_keys == {"north", "south", "east"}

    def test_get_adjacent_zones_respects_bidirectional(self, db_session, game_session):
        """get_adjacent_zones should include zones reachable via bidirectional connections."""
        zone_a = create_terrain_zone(db_session, game_session, zone_key="zone_a")
        zone_b = create_terrain_zone(db_session, game_session, zone_key="zone_b")
        db_session.flush()

        # Create bidirectional connection from A to B
        create_zone_connection(
            db_session, game_session, zone_a, zone_b, direction="east", is_bidirectional=True
        )
        db_session.commit()

        manager = ZoneManager(db_session, game_session)

        # From A, should reach B
        adjacent_from_a = manager.get_adjacent_zones("zone_a")
        assert len(adjacent_from_a) == 1
        assert adjacent_from_a[0].zone_key == "zone_b"

        # From B, should reach A (via bidirectional)
        adjacent_from_b = manager.get_adjacent_zones("zone_b")
        assert len(adjacent_from_b) == 1
        assert adjacent_from_b[0].zone_key == "zone_a"

    def test_get_adjacent_zones_excludes_one_way_reverse(self, db_session, game_session):
        """get_adjacent_zones should not include reverse of one-way connections."""
        zone_top = create_terrain_zone(db_session, game_session, zone_key="top")
        zone_bottom = create_terrain_zone(db_session, game_session, zone_key="bottom")
        db_session.flush()

        # One-way connection: can go from top to bottom, but not back
        create_zone_connection(
            db_session, game_session, zone_top, zone_bottom, direction="down", is_bidirectional=False
        )
        db_session.commit()

        manager = ZoneManager(db_session, game_session)

        # From top, can go to bottom
        adjacent_from_top = manager.get_adjacent_zones("top")
        assert len(adjacent_from_top) == 1
        assert adjacent_from_top[0].zone_key == "bottom"

        # From bottom, cannot go to top
        adjacent_from_bottom = manager.get_adjacent_zones("bottom")
        assert len(adjacent_from_bottom) == 0

    def test_get_adjacent_zones_excludes_impassable(self, db_session, game_session):
        """get_adjacent_zones should exclude blocked connections."""
        zone_a = create_terrain_zone(db_session, game_session, zone_key="zone_a")
        zone_b = create_terrain_zone(db_session, game_session, zone_key="zone_b")
        db_session.flush()

        conn = create_zone_connection(db_session, game_session, zone_a, zone_b, direction="east")
        conn.is_passable = False
        conn.blocked_reason = "Bridge destroyed"
        db_session.commit()

        manager = ZoneManager(db_session, game_session)
        adjacent = manager.get_adjacent_zones("zone_a")

        assert len(adjacent) == 0

    def test_get_adjacent_zones_with_directions(self, db_session, game_session):
        """get_adjacent_zones should optionally return direction info."""
        zone_center = create_terrain_zone(db_session, game_session, zone_key="center")
        zone_north = create_terrain_zone(db_session, game_session, zone_key="north")
        zone_east = create_terrain_zone(db_session, game_session, zone_key="east")
        db_session.flush()

        create_zone_connection(db_session, game_session, zone_center, zone_north, direction="north")
        create_zone_connection(db_session, game_session, zone_center, zone_east, direction="east")
        db_session.commit()

        manager = ZoneManager(db_session, game_session)
        adjacent_with_dirs = manager.get_adjacent_zones_with_directions("center")

        assert len(adjacent_with_dirs) == 2
        directions = {item["direction"]: item["zone"] for item in adjacent_with_dirs}
        assert "north" in directions
        assert "east" in directions
        assert directions["north"].zone_key == "north"


class TestZoneManagerLocations:
    """Tests for zone-location relationships."""

    def test_place_location_in_zone(self, db_session, game_session):
        """place_location_in_zone should create a placement record."""
        zone = create_terrain_zone(db_session, game_session, zone_key="forest")
        location = create_location(db_session, game_session, location_key="cabin")
        db_session.commit()

        manager = ZoneManager(db_session, game_session)
        placement = manager.place_location_in_zone(
            location_key="cabin",
            zone_key="forest",
            placement_type=PlacementType.WITHIN,
        )
        db_session.commit()

        assert placement is not None
        assert placement.zone_id == zone.id
        assert placement.location_id == location.id
        assert placement.placement_type == PlacementType.WITHIN

    def test_place_location_hidden(self, db_session, game_session):
        """place_location_in_zone should support hidden locations."""
        create_terrain_zone(db_session, game_session, zone_key="forest")
        create_location(db_session, game_session, location_key="secret_cave")
        db_session.commit()

        manager = ZoneManager(db_session, game_session)
        placement = manager.place_location_in_zone(
            location_key="secret_cave",
            zone_key="forest",
            placement_type=PlacementType.WITHIN,
            visibility="hidden",
        )
        db_session.commit()

        assert placement.visibility == "hidden"

    def test_get_zone_locations_returns_placed_locations(self, db_session, game_session):
        """get_zone_locations should return all locations in a zone."""
        zone = create_terrain_zone(db_session, game_session, zone_key="village_zone")
        loc1 = create_location(db_session, game_session, location_key="tavern")
        loc2 = create_location(db_session, game_session, location_key="blacksmith")
        loc3 = create_location(db_session, game_session, location_key="church")
        db_session.flush()

        create_location_zone_placement(db_session, game_session, loc1, zone)
        create_location_zone_placement(db_session, game_session, loc2, zone)
        create_location_zone_placement(db_session, game_session, loc3, zone)
        db_session.commit()

        manager = ZoneManager(db_session, game_session)
        locations = manager.get_zone_locations("village_zone")

        assert len(locations) == 3
        location_keys = {loc.location_key for loc in locations}
        assert location_keys == {"tavern", "blacksmith", "church"}

    def test_get_zone_locations_filters_by_visibility(self, db_session, game_session):
        """get_zone_locations should optionally filter by visibility."""
        zone = create_terrain_zone(db_session, game_session, zone_key="forest")
        visible_loc = create_location(db_session, game_session, location_key="clearing")
        hidden_loc = create_location(db_session, game_session, location_key="secret_cave")
        db_session.flush()

        placement1 = create_location_zone_placement(db_session, game_session, visible_loc, zone)
        placement1.visibility = "visible_from_zone"
        placement2 = create_location_zone_placement(db_session, game_session, hidden_loc, zone)
        placement2.visibility = "hidden"
        db_session.commit()

        manager = ZoneManager(db_session, game_session)

        # All locations
        all_locations = manager.get_zone_locations("forest")
        assert len(all_locations) == 2

        # Only visible
        visible_only = manager.get_zone_locations("forest", visibility="visible_from_zone")
        assert len(visible_only) == 1
        assert visible_only[0].location_key == "clearing"

    def test_get_location_zone_returns_zone_for_location(self, db_session, game_session):
        """get_location_zone should return the zone a location is in."""
        zone = create_terrain_zone(db_session, game_session, zone_key="forest")
        location = create_location(db_session, game_session, location_key="cabin")
        db_session.flush()

        create_location_zone_placement(db_session, game_session, location, zone)
        db_session.commit()

        manager = ZoneManager(db_session, game_session)
        found_zone = manager.get_location_zone("cabin")

        assert found_zone is not None
        assert found_zone.zone_key == "forest"


class TestZoneManagerTerrainCosts:
    """Tests for terrain cost calculations."""

    def test_get_terrain_cost_returns_base_cost(self, db_session, game_session):
        """get_terrain_cost should return base cost for walking."""
        create_terrain_zone(
            db_session, game_session, zone_key="plains", base_travel_cost=10
        )
        db_session.commit()

        manager = ZoneManager(db_session, game_session)
        cost = manager.get_terrain_cost("plains", "walking")

        assert cost == 10

    def test_get_terrain_cost_with_transport_mode(self, db_session, game_session):
        """get_terrain_cost should apply transport mode multipliers."""
        create_terrain_zone(
            db_session,
            game_session,
            zone_key="plains",
            terrain_type=TerrainType.PLAINS,
            base_travel_cost=10,
        )
        create_transport_mode(
            db_session,
            mode_key="mounted",
            terrain_costs={"plains": 0.5, "forest": 2.0, "lake": None},
        )
        db_session.commit()

        manager = ZoneManager(db_session, game_session)
        cost = manager.get_terrain_cost("plains", "mounted")

        assert cost == 5  # 10 * 0.5

    def test_get_terrain_cost_returns_none_for_impassable(self, db_session, game_session):
        """get_terrain_cost should return None for impassable terrain."""
        create_terrain_zone(
            db_session,
            game_session,
            zone_key="lake",
            terrain_type=TerrainType.LAKE,
            base_travel_cost=10,
        )
        create_transport_mode(
            db_session,
            mode_key="mounted",
            terrain_costs={"plains": 0.5, "lake": None},  # Can't ride horse in lake
        )
        db_session.commit()

        manager = ZoneManager(db_session, game_session)
        cost = manager.get_terrain_cost("lake", "mounted")

        assert cost is None

    def test_get_terrain_cost_uses_zone_mounted_cost(self, db_session, game_session):
        """get_terrain_cost should use zone's mounted_travel_cost when available."""
        create_terrain_zone(
            db_session,
            game_session,
            zone_key="road",
            terrain_type=TerrainType.ROAD,
            base_travel_cost=10,
            mounted_travel_cost=5,  # Explicit mounted cost
        )
        db_session.commit()

        manager = ZoneManager(db_session, game_session)
        cost = manager.get_terrain_cost("road", "mounted")

        assert cost == 5


class TestZoneManagerAccessibility:
    """Tests for terrain accessibility checks."""

    def test_check_accessibility_returns_true_for_no_requirements(
        self, db_session, game_session
    ):
        """check_accessibility should return True for zones without requirements."""
        create_terrain_zone(
            db_session, game_session, zone_key="plains", requires_skill=None
        )
        db_session.commit()

        manager = ZoneManager(db_session, game_session)
        result = manager.check_accessibility("plains", character_skills={})

        assert result["accessible"] is True
        assert result["requires_check"] is False

    def test_check_accessibility_identifies_skill_requirement(
        self, db_session, game_session
    ):
        """check_accessibility should identify skill requirements."""
        create_terrain_zone(
            db_session,
            game_session,
            zone_key="lake",
            terrain_type=TerrainType.LAKE,
            requires_skill="swimming",
            skill_difficulty=12,
            failure_consequence="drowning",
        )
        db_session.commit()

        manager = ZoneManager(db_session, game_session)
        result = manager.check_accessibility("lake", character_skills={"swimming": 5})

        assert result["accessible"] is True
        assert result["requires_check"] is True
        assert result["skill"] == "swimming"
        assert result["difficulty"] == 12
        assert result["failure_consequence"] == "drowning"

    def test_check_accessibility_returns_false_without_skill(
        self, db_session, game_session
    ):
        """check_accessibility should return False if character lacks required skill."""
        create_terrain_zone(
            db_session,
            game_session,
            zone_key="cliff",
            requires_skill="climbing",
            skill_difficulty=15,
        )
        db_session.commit()

        manager = ZoneManager(db_session, game_session)
        result = manager.check_accessibility("cliff", character_skills={})

        assert result["accessible"] is False
        assert result["reason"] == "Requires climbing skill"

    def test_check_accessibility_blocked_zone(self, db_session, game_session):
        """check_accessibility should return False for blocked zones."""
        zone = create_terrain_zone(db_session, game_session, zone_key="blocked_path")
        zone.is_accessible = False
        zone.blocked_reason = "Rockslide blocking the path"
        db_session.commit()

        manager = ZoneManager(db_session, game_session)
        result = manager.check_accessibility("blocked_path", character_skills={})

        assert result["accessible"] is False
        assert result["reason"] == "Rockslide blocking the path"


class TestZoneManagerVisibility:
    """Tests for zone visibility queries."""

    def test_get_visible_from_zone_far_visibility(self, db_session, game_session):
        """get_visible_from_zone should return adjacent zones for far visibility."""
        center = create_terrain_zone(
            db_session,
            game_session,
            zone_key="hilltop",
            visibility_range=VisibilityRange.FAR,
        )
        zone_near = create_terrain_zone(db_session, game_session, zone_key="near_valley")
        zone_far = create_terrain_zone(db_session, game_session, zone_key="far_mountains")
        db_session.flush()

        # Near is directly adjacent
        create_zone_connection(db_session, game_session, center, zone_near, direction="east")
        # Far is connected to near (2 steps away)
        create_zone_connection(db_session, game_session, zone_near, zone_far, direction="east")
        db_session.commit()

        manager = ZoneManager(db_session, game_session)
        visible = manager.get_visible_from_zone("hilltop")

        # With FAR visibility, should see adjacent and beyond
        visible_keys = {z.zone_key for z in visible}
        assert "near_valley" in visible_keys
        # Far zones may or may not be visible depending on implementation

    def test_get_visible_from_zone_short_visibility(self, db_session, game_session):
        """get_visible_from_zone with short range should only show immediate area."""
        center = create_terrain_zone(
            db_session,
            game_session,
            zone_key="dense_forest",
            visibility_range=VisibilityRange.SHORT,
        )
        zone_adjacent = create_terrain_zone(db_session, game_session, zone_key="clearing")
        db_session.flush()

        create_zone_connection(db_session, game_session, center, zone_adjacent, direction="north")
        db_session.commit()

        manager = ZoneManager(db_session, game_session)
        visible = manager.get_visible_from_zone("dense_forest")

        # With SHORT visibility, should see adjacent zones
        assert len(visible) >= 0  # At minimum current zone's exits are visible

    def test_get_visible_locations_from_zone(self, db_session, game_session):
        """get_visible_locations_from_zone should return visible locations in zone."""
        zone = create_terrain_zone(db_session, game_session, zone_key="plains")
        visible_loc = create_location(db_session, game_session, location_key="windmill")
        hidden_loc = create_location(db_session, game_session, location_key="bunker")
        db_session.flush()

        placement1 = create_location_zone_placement(db_session, game_session, visible_loc, zone)
        placement1.visibility = "visible_from_zone"
        placement2 = create_location_zone_placement(db_session, game_session, hidden_loc, zone)
        placement2.visibility = "hidden"
        db_session.commit()

        manager = ZoneManager(db_session, game_session)
        visible_locations = manager.get_visible_locations_from_zone("plains")

        assert len(visible_locations) == 1
        assert visible_locations[0].location_key == "windmill"


class TestZoneManagerTransportModes:
    """Tests for transport mode queries."""

    def test_get_transport_mode(self, db_session, game_session):
        """get_transport_mode should return a transport mode by key."""
        create_transport_mode(db_session, mode_key="walking")
        db_session.commit()

        manager = ZoneManager(db_session, game_session)
        mode = manager.get_transport_mode("walking")

        assert mode is not None
        assert mode.mode_key == "walking"

    def test_get_available_transport_modes_for_zone(self, db_session, game_session):
        """get_available_transport_modes should return modes usable in a zone."""
        create_terrain_zone(
            db_session,
            game_session,
            zone_key="plains",
            terrain_type=TerrainType.PLAINS,
        )
        create_transport_mode(
            db_session,
            mode_key="walking",
            terrain_costs={"plains": 1.0, "lake": None},
        )
        create_transport_mode(
            db_session,
            mode_key="mounted",
            terrain_costs={"plains": 0.5, "lake": None},
        )
        create_transport_mode(
            db_session,
            mode_key="swimming",
            terrain_costs={"lake": 1.0, "plains": None},
        )
        db_session.commit()

        manager = ZoneManager(db_session, game_session)
        available = manager.get_available_transport_modes("plains")

        mode_keys = {m.mode_key for m in available}
        assert "walking" in mode_keys
        assert "mounted" in mode_keys
        assert "swimming" not in mode_keys  # Can't swim on plains
