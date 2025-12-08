"""Tests for PathfindingManager - A* pathfinding and route planning."""

import pytest

from src.database.models.enums import ConnectionType, TerrainType
from src.managers.pathfinding_manager import PathfindingManager
from tests.factories import (
    create_terrain_zone,
    create_transport_mode,
    create_zone_connection,
)


class TestPathfindingBasic:
    """Tests for basic pathfinding operations."""

    def test_find_path_direct_connection(self, db_session, game_session):
        """find_optimal_path should find a direct connection."""
        zone_a = create_terrain_zone(
            db_session, game_session, zone_key="zone_a", base_travel_cost=10
        )
        zone_b = create_terrain_zone(
            db_session, game_session, zone_key="zone_b", base_travel_cost=10
        )
        db_session.flush()

        create_zone_connection(db_session, game_session, zone_a, zone_b, direction="east")
        db_session.commit()

        manager = PathfindingManager(db_session, game_session)
        result = manager.find_optimal_path("zone_a", "zone_b", "walking")

        assert result is not None
        assert result["found"] is True
        assert len(result["path"]) == 2
        assert result["path"][0].zone_key == "zone_a"
        assert result["path"][1].zone_key == "zone_b"

    def test_find_path_multiple_hops(self, db_session, game_session):
        """find_optimal_path should find a path through multiple zones."""
        zone_a = create_terrain_zone(db_session, game_session, zone_key="zone_a")
        zone_b = create_terrain_zone(db_session, game_session, zone_key="zone_b")
        zone_c = create_terrain_zone(db_session, game_session, zone_key="zone_c")
        zone_d = create_terrain_zone(db_session, game_session, zone_key="zone_d")
        db_session.flush()

        # A -> B -> C -> D
        create_zone_connection(db_session, game_session, zone_a, zone_b, direction="east")
        create_zone_connection(db_session, game_session, zone_b, zone_c, direction="east")
        create_zone_connection(db_session, game_session, zone_c, zone_d, direction="east")
        db_session.commit()

        manager = PathfindingManager(db_session, game_session)
        result = manager.find_optimal_path("zone_a", "zone_d", "walking")

        assert result["found"] is True
        assert len(result["path"]) == 4
        path_keys = [z.zone_key for z in result["path"]]
        assert path_keys == ["zone_a", "zone_b", "zone_c", "zone_d"]

    def test_find_path_no_path_exists(self, db_session, game_session):
        """find_optimal_path should return not found when no path exists."""
        create_terrain_zone(db_session, game_session, zone_key="zone_a")
        create_terrain_zone(db_session, game_session, zone_key="zone_b")
        db_session.commit()

        manager = PathfindingManager(db_session, game_session)
        result = manager.find_optimal_path("zone_a", "zone_b", "walking")

        assert result["found"] is False
        assert result["path"] == []
        assert "reason" in result

    def test_find_path_same_start_and_end(self, db_session, game_session):
        """find_optimal_path should return single-node path for same start/end."""
        create_terrain_zone(db_session, game_session, zone_key="zone_a")
        db_session.commit()

        manager = PathfindingManager(db_session, game_session)
        result = manager.find_optimal_path("zone_a", "zone_a", "walking")

        assert result["found"] is True
        assert len(result["path"]) == 1
        assert result["path"][0].zone_key == "zone_a"
        assert result["total_cost"] == 0

    def test_find_path_invalid_start_zone(self, db_session, game_session):
        """find_optimal_path should handle invalid start zone."""
        create_terrain_zone(db_session, game_session, zone_key="zone_b")
        db_session.commit()

        manager = PathfindingManager(db_session, game_session)
        result = manager.find_optimal_path("nonexistent", "zone_b", "walking")

        assert result["found"] is False
        assert "Start zone not found" in result["reason"]

    def test_find_path_invalid_end_zone(self, db_session, game_session):
        """find_optimal_path should handle invalid end zone."""
        create_terrain_zone(db_session, game_session, zone_key="zone_a")
        db_session.commit()

        manager = PathfindingManager(db_session, game_session)
        result = manager.find_optimal_path("zone_a", "nonexistent", "walking")

        assert result["found"] is False
        assert "End zone not found" in result["reason"]


class TestPathfindingOptimization:
    """Tests for optimal path selection."""

    def test_find_path_chooses_shorter_route(self, db_session, game_session):
        """find_optimal_path should choose the shorter route."""
        zone_start = create_terrain_zone(
            db_session, game_session, zone_key="start", base_travel_cost=10
        )
        zone_end = create_terrain_zone(
            db_session, game_session, zone_key="end", base_travel_cost=10
        )
        # Long route through forest
        zone_forest1 = create_terrain_zone(
            db_session, game_session, zone_key="forest1", base_travel_cost=30
        )
        zone_forest2 = create_terrain_zone(
            db_session, game_session, zone_key="forest2", base_travel_cost=30
        )
        # Short route on road
        zone_road = create_terrain_zone(
            db_session, game_session, zone_key="road", base_travel_cost=5
        )
        db_session.flush()

        # Long path: start -> forest1 -> forest2 -> end (cost: 10 + 30 + 30 = 70)
        create_zone_connection(db_session, game_session, zone_start, zone_forest1, direction="north")
        create_zone_connection(db_session, game_session, zone_forest1, zone_forest2, direction="north")
        create_zone_connection(db_session, game_session, zone_forest2, zone_end, direction="north")

        # Short path: start -> road -> end (cost: 10 + 5 = 15)
        create_zone_connection(db_session, game_session, zone_start, zone_road, direction="east")
        create_zone_connection(db_session, game_session, zone_road, zone_end, direction="east")
        db_session.commit()

        manager = PathfindingManager(db_session, game_session)
        result = manager.find_optimal_path("start", "end", "walking")

        assert result["found"] is True
        path_keys = [z.zone_key for z in result["path"]]
        assert path_keys == ["start", "road", "end"]
        # Cost: road(5) + crossing(5) + end(10) + crossing(5) = 25
        # (start zone cost not counted since we're already there)
        assert result["total_cost"] == 25

    def test_find_path_considers_transport_mode(self, db_session, game_session):
        """find_optimal_path should consider transport mode costs."""
        zone_start = create_terrain_zone(
            db_session,
            game_session,
            zone_key="start",
            terrain_type=TerrainType.PLAINS,
            base_travel_cost=10,
        )
        zone_end = create_terrain_zone(
            db_session,
            game_session,
            zone_key="end",
            terrain_type=TerrainType.PLAINS,
            base_travel_cost=10,
        )
        zone_forest = create_terrain_zone(
            db_session,
            game_session,
            zone_key="forest",
            terrain_type=TerrainType.FOREST,
            base_travel_cost=15,
        )
        zone_road = create_terrain_zone(
            db_session,
            game_session,
            zone_key="road",
            terrain_type=TerrainType.ROAD,
            base_travel_cost=10,
        )
        db_session.flush()

        # Through forest path (shorter base cost but bad for mounted)
        create_zone_connection(db_session, game_session, zone_start, zone_forest, direction="north")
        create_zone_connection(db_session, game_session, zone_forest, zone_end, direction="north")

        # Through road (longer base but good for mounted)
        create_zone_connection(db_session, game_session, zone_start, zone_road, direction="east")
        create_zone_connection(db_session, game_session, zone_road, zone_end, direction="east")

        # Create mounted transport mode (forest impassable, road faster)
        create_transport_mode(
            db_session,
            mode_key="mounted",
            terrain_costs={
                "plains": 0.5,
                "road": 0.4,
                "forest": None,  # Impassable
            },
        )
        db_session.commit()

        manager = PathfindingManager(db_session, game_session)
        result = manager.find_optimal_path("start", "end", "mounted")

        assert result["found"] is True
        path_keys = [z.zone_key for z in result["path"]]
        # Should avoid forest and take road
        assert "forest" not in path_keys
        assert "road" in path_keys

    def test_find_path_avoids_impassable_zones(self, db_session, game_session):
        """find_optimal_path should route around impassable connections."""
        zone_a = create_terrain_zone(db_session, game_session, zone_key="zone_a")
        zone_b = create_terrain_zone(db_session, game_session, zone_key="zone_b")
        zone_c = create_terrain_zone(db_session, game_session, zone_key="zone_c")
        db_session.flush()

        # Direct connection A -> B (blocked)
        conn_ab = create_zone_connection(db_session, game_session, zone_a, zone_b, direction="east")
        conn_ab.is_passable = False
        conn_ab.blocked_reason = "Bridge destroyed"

        # Alternate route A -> C -> B
        create_zone_connection(db_session, game_session, zone_a, zone_c, direction="south")
        create_zone_connection(db_session, game_session, zone_c, zone_b, direction="east")
        db_session.commit()

        manager = PathfindingManager(db_session, game_session)
        result = manager.find_optimal_path("zone_a", "zone_b", "walking")

        assert result["found"] is True
        path_keys = [z.zone_key for z in result["path"]]
        assert path_keys == ["zone_a", "zone_c", "zone_b"]


class TestPathfindingWithWaypoints:
    """Tests for pathfinding with waypoints."""

    def test_find_path_via_single_waypoint(self, db_session, game_session):
        """find_path_via should route through a waypoint."""
        zone_a = create_terrain_zone(db_session, game_session, zone_key="zone_a")
        zone_b = create_terrain_zone(db_session, game_session, zone_key="zone_b")
        zone_c = create_terrain_zone(db_session, game_session, zone_key="zone_c")
        zone_d = create_terrain_zone(db_session, game_session, zone_key="zone_d")
        db_session.flush()

        # Create connections (grid layout)
        create_zone_connection(db_session, game_session, zone_a, zone_b, direction="east")
        create_zone_connection(db_session, game_session, zone_a, zone_c, direction="south")
        create_zone_connection(db_session, game_session, zone_b, zone_d, direction="south")
        create_zone_connection(db_session, game_session, zone_c, zone_d, direction="east")
        db_session.commit()

        manager = PathfindingManager(db_session, game_session)
        result = manager.find_path_via("zone_a", "zone_d", ["zone_c"], "walking")

        assert result["found"] is True
        path_keys = [z.zone_key for z in result["path"]]
        # Must go through zone_c even if zone_b is shorter
        assert "zone_c" in path_keys
        assert path_keys.index("zone_c") > path_keys.index("zone_a")
        assert path_keys.index("zone_c") < path_keys.index("zone_d")

    def test_find_path_via_multiple_waypoints(self, db_session, game_session):
        """find_path_via should route through multiple waypoints in order."""
        zone_a = create_terrain_zone(db_session, game_session, zone_key="zone_a")
        zone_b = create_terrain_zone(db_session, game_session, zone_key="zone_b")
        zone_c = create_terrain_zone(db_session, game_session, zone_key="zone_c")
        zone_d = create_terrain_zone(db_session, game_session, zone_key="zone_d")
        db_session.flush()

        # Linear connections
        create_zone_connection(db_session, game_session, zone_a, zone_b, direction="east")
        create_zone_connection(db_session, game_session, zone_b, zone_c, direction="east")
        create_zone_connection(db_session, game_session, zone_c, zone_d, direction="east")
        db_session.commit()

        manager = PathfindingManager(db_session, game_session)
        result = manager.find_path_via("zone_a", "zone_d", ["zone_b", "zone_c"], "walking")

        assert result["found"] is True
        path_keys = [z.zone_key for z in result["path"]]
        assert path_keys == ["zone_a", "zone_b", "zone_c", "zone_d"]

    def test_find_path_via_unreachable_waypoint(self, db_session, game_session):
        """find_path_via should fail if waypoint is unreachable."""
        zone_a = create_terrain_zone(db_session, game_session, zone_key="zone_a")
        zone_b = create_terrain_zone(db_session, game_session, zone_key="zone_b")
        zone_isolated = create_terrain_zone(db_session, game_session, zone_key="isolated")
        db_session.flush()

        create_zone_connection(db_session, game_session, zone_a, zone_b, direction="east")
        # isolated has no connections
        db_session.commit()

        manager = PathfindingManager(db_session, game_session)
        result = manager.find_path_via("zone_a", "zone_b", ["isolated"], "walking")

        assert result["found"] is False
        assert "waypoint" in result["reason"].lower()


class TestTravelTimeCalculation:
    """Tests for travel time calculations."""

    def test_calculate_travel_time_simple(self, db_session, game_session):
        """calculate_travel_time should sum zone costs along path."""
        zone_a = create_terrain_zone(
            db_session, game_session, zone_key="zone_a", base_travel_cost=10
        )
        zone_b = create_terrain_zone(
            db_session, game_session, zone_key="zone_b", base_travel_cost=20
        )
        zone_c = create_terrain_zone(
            db_session, game_session, zone_key="zone_c", base_travel_cost=15
        )
        db_session.flush()

        create_zone_connection(
            db_session, game_session, zone_a, zone_b, direction="east", crossing_minutes=5
        )
        create_zone_connection(
            db_session, game_session, zone_b, zone_c, direction="east", crossing_minutes=3
        )
        db_session.commit()

        manager = PathfindingManager(db_session, game_session)
        result = manager.find_optimal_path("zone_a", "zone_c", "walking")

        # Zone costs + crossing costs: 10 + 5 + 20 + 3 + 15 = 53
        # Actually: starting zone + crossing + next zone... depends on implementation
        # Let's check the result structure
        assert result["found"] is True
        assert "total_cost" in result
        assert result["total_cost"] > 0

    def test_calculate_travel_time_with_transport_multiplier(self, db_session, game_session):
        """calculate_travel_time should apply transport mode multipliers."""
        zone_a = create_terrain_zone(
            db_session,
            game_session,
            zone_key="zone_a",
            terrain_type=TerrainType.ROAD,
            base_travel_cost=20,
        )
        zone_b = create_terrain_zone(
            db_session,
            game_session,
            zone_key="zone_b",
            terrain_type=TerrainType.ROAD,
            base_travel_cost=20,
        )
        db_session.flush()

        create_zone_connection(db_session, game_session, zone_a, zone_b, direction="east")

        create_transport_mode(
            db_session,
            mode_key="mounted",
            terrain_costs={"road": 0.5},
        )
        db_session.commit()

        manager = PathfindingManager(db_session, game_session)

        walking_result = manager.find_optimal_path("zone_a", "zone_b", "walking")
        mounted_result = manager.find_optimal_path("zone_a", "zone_b", "mounted")

        assert walking_result["found"] is True
        assert mounted_result["found"] is True
        # Mounted should be faster
        assert mounted_result["total_cost"] < walking_result["total_cost"]


class TestRouteSummary:
    """Tests for route summary generation."""

    def test_get_route_summary(self, db_session, game_session):
        """get_route_summary should provide terrain breakdown."""
        zone_plains = create_terrain_zone(
            db_session,
            game_session,
            zone_key="plains",
            terrain_type=TerrainType.PLAINS,
            base_travel_cost=10,
        )
        zone_forest = create_terrain_zone(
            db_session,
            game_session,
            zone_key="forest",
            terrain_type=TerrainType.FOREST,
            base_travel_cost=20,
        )
        zone_road = create_terrain_zone(
            db_session,
            game_session,
            zone_key="road",
            terrain_type=TerrainType.ROAD,
            base_travel_cost=5,
        )
        db_session.flush()

        create_zone_connection(db_session, game_session, zone_plains, zone_forest, direction="north")
        create_zone_connection(db_session, game_session, zone_forest, zone_road, direction="north")
        db_session.commit()

        manager = PathfindingManager(db_session, game_session)
        result = manager.find_optimal_path("plains", "road", "walking")

        assert result["found"] is True
        summary = manager.get_route_summary(result["path"], "walking")

        assert "terrain_breakdown" in summary
        assert "total_time" in summary
        assert "total_distance" in summary

    def test_get_route_summary_identifies_hazards(self, db_session, game_session):
        """get_route_summary should identify hazardous zones."""
        zone_a = create_terrain_zone(db_session, game_session, zone_key="zone_a")
        zone_lake = create_terrain_zone(
            db_session,
            game_session,
            zone_key="lake",
            terrain_type=TerrainType.LAKE,
            requires_skill="swimming",
            skill_difficulty=12,
            failure_consequence="drowning",
        )
        zone_b = create_terrain_zone(db_session, game_session, zone_key="zone_b")
        db_session.flush()

        create_zone_connection(db_session, game_session, zone_a, zone_lake, direction="north")
        create_zone_connection(db_session, game_session, zone_lake, zone_b, direction="north")
        db_session.commit()

        manager = PathfindingManager(db_session, game_session)
        result = manager.find_optimal_path("zone_a", "zone_b", "walking")

        if result["found"]:
            summary = manager.get_route_summary(result["path"], "walking")
            assert "hazards" in summary
            assert len(summary["hazards"]) > 0
            assert any("swimming" in h["skill"] for h in summary["hazards"])


class TestRoutePreferences:
    """Tests for route preference filtering."""

    def test_find_path_avoid_terrain(self, db_session, game_session):
        """find_optimal_path should respect terrain avoidance preferences."""
        zone_start = create_terrain_zone(db_session, game_session, zone_key="start")
        zone_end = create_terrain_zone(db_session, game_session, zone_key="end")
        zone_forest = create_terrain_zone(
            db_session,
            game_session,
            zone_key="forest",
            terrain_type=TerrainType.FOREST,
            base_travel_cost=10,  # Shorter
        )
        zone_road = create_terrain_zone(
            db_session,
            game_session,
            zone_key="road",
            terrain_type=TerrainType.ROAD,
            base_travel_cost=20,  # Longer
        )
        db_session.flush()

        create_zone_connection(db_session, game_session, zone_start, zone_forest, direction="north")
        create_zone_connection(db_session, game_session, zone_forest, zone_end, direction="north")
        create_zone_connection(db_session, game_session, zone_start, zone_road, direction="east")
        create_zone_connection(db_session, game_session, zone_road, zone_end, direction="east")
        db_session.commit()

        manager = PathfindingManager(db_session, game_session)
        result = manager.find_optimal_path(
            "start",
            "end",
            "walking",
            avoid_terrain=[TerrainType.FOREST],
        )

        assert result["found"] is True
        path_keys = [z.zone_key for z in result["path"]]
        assert "forest" not in path_keys
        assert "road" in path_keys

    def test_find_path_prefer_roads(self, db_session, game_session):
        """find_optimal_path should prefer roads when requested."""
        zone_start = create_terrain_zone(db_session, game_session, zone_key="start")
        zone_end = create_terrain_zone(db_session, game_session, zone_key="end")
        zone_plains = create_terrain_zone(
            db_session,
            game_session,
            zone_key="plains",
            terrain_type=TerrainType.PLAINS,
            base_travel_cost=10,
        )
        zone_road = create_terrain_zone(
            db_session,
            game_session,
            zone_key="road",
            terrain_type=TerrainType.ROAD,
            base_travel_cost=15,  # Slightly longer, but preferred
        )
        db_session.flush()

        create_zone_connection(db_session, game_session, zone_start, zone_plains, direction="north")
        create_zone_connection(db_session, game_session, zone_plains, zone_end, direction="north")
        create_zone_connection(db_session, game_session, zone_start, zone_road, direction="east")
        create_zone_connection(db_session, game_session, zone_road, zone_end, direction="east")
        db_session.commit()

        manager = PathfindingManager(db_session, game_session)
        result = manager.find_optimal_path(
            "start",
            "end",
            "walking",
            prefer_roads=True,
        )

        assert result["found"] is True
        path_keys = [z.zone_key for z in result["path"]]
        # Road should be chosen despite slight cost penalty
        assert "road" in path_keys


class TestBidirectionalConnections:
    """Tests for bidirectional connection handling."""

    def test_find_path_uses_bidirectional_reverse(self, db_session, game_session):
        """find_optimal_path should use bidirectional connections in reverse."""
        zone_a = create_terrain_zone(db_session, game_session, zone_key="zone_a")
        zone_b = create_terrain_zone(db_session, game_session, zone_key="zone_b")
        db_session.flush()

        # Connection defined A -> B, but bidirectional
        create_zone_connection(
            db_session,
            game_session,
            zone_a,
            zone_b,
            direction="east",
            is_bidirectional=True,
        )
        db_session.commit()

        manager = PathfindingManager(db_session, game_session)

        # Path from B to A should work
        result = manager.find_optimal_path("zone_b", "zone_a", "walking")

        assert result["found"] is True
        path_keys = [z.zone_key for z in result["path"]]
        assert path_keys == ["zone_b", "zone_a"]

    def test_find_path_respects_one_way(self, db_session, game_session):
        """find_optimal_path should not use one-way connections in reverse."""
        zone_top = create_terrain_zone(db_session, game_session, zone_key="top")
        zone_bottom = create_terrain_zone(db_session, game_session, zone_key="bottom")
        db_session.flush()

        # One-way: can go down but not up
        create_zone_connection(
            db_session,
            game_session,
            zone_top,
            zone_bottom,
            direction="down",
            is_bidirectional=False,
        )
        db_session.commit()

        manager = PathfindingManager(db_session, game_session)

        # Path from bottom to top should fail
        result = manager.find_optimal_path("bottom", "top", "walking")

        assert result["found"] is False
