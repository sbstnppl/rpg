"""PathfindingManager for A* pathfinding and route planning."""

import heapq
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from src.database.models.enums import TerrainType
from src.database.models.navigation import TerrainZone, TransportMode, ZoneConnection
from src.database.models.session import GameSession
from src.managers.base import BaseManager
from src.managers.zone_manager import ZoneManager


@dataclass(order=True)
class PriorityItem:
    """Priority queue item for A* algorithm."""

    priority: float
    zone_id: int = field(compare=False)
    zone: Any = field(compare=False)


class PathfindingManager(BaseManager):
    """Manager for pathfinding operations using A* algorithm.

    Handles:
    - Optimal path finding between zones
    - Path finding with waypoints
    - Travel time calculation
    - Route summaries with terrain breakdown
    - Route preferences (avoid terrain, prefer roads)
    """

    def __init__(self, db: Session, game_session: GameSession) -> None:
        """Initialize PathfindingManager.

        Args:
            db: SQLAlchemy database session.
            game_session: Current game session.
        """
        super().__init__(db, game_session)
        self._zone_manager = ZoneManager(db, game_session)

    # =========================================================================
    # Core Pathfinding
    # =========================================================================

    def find_optimal_path(
        self,
        from_zone_key: str,
        to_zone_key: str,
        transport_mode_key: str,
        avoid_terrain: list[TerrainType] | None = None,
        prefer_roads: bool = False,
    ) -> dict:
        """Find the optimal path between two zones using A* algorithm.

        Args:
            from_zone_key: Starting zone key.
            to_zone_key: Destination zone key.
            transport_mode_key: Transport mode (e.g., 'walking', 'mounted').
            avoid_terrain: List of terrain types to avoid.
            prefer_roads: If True, bias toward road terrain.

        Returns:
            Dict with keys:
            - found: bool
            - path: list[TerrainZone] (from start to end)
            - total_cost: int (total travel time in minutes)
            - reason: str (if not found)
        """
        start_zone = self._zone_manager.get_zone(from_zone_key)
        if start_zone is None:
            return {
                "found": False,
                "path": [],
                "total_cost": 0,
                "reason": "Start zone not found",
            }

        end_zone = self._zone_manager.get_zone(to_zone_key)
        if end_zone is None:
            return {
                "found": False,
                "path": [],
                "total_cost": 0,
                "reason": "End zone not found",
            }

        # Same start and end
        if start_zone.id == end_zone.id:
            return {
                "found": True,
                "path": [start_zone],
                "total_cost": 0,
            }

        # Get transport mode
        transport_mode = self._zone_manager.get_transport_mode(transport_mode_key)

        # Run A* algorithm
        path, total_cost = self._astar(
            start_zone,
            end_zone,
            transport_mode_key,
            transport_mode,
            avoid_terrain or [],
            prefer_roads,
        )

        if path is None:
            return {
                "found": False,
                "path": [],
                "total_cost": 0,
                "reason": "No path exists between the zones",
            }

        return {
            "found": True,
            "path": path,
            "total_cost": total_cost,
        }

    def find_path_via(
        self,
        from_zone_key: str,
        to_zone_key: str,
        waypoints: list[str],
        transport_mode_key: str,
    ) -> dict:
        """Find a path that passes through specified waypoints.

        Args:
            from_zone_key: Starting zone key.
            to_zone_key: Destination zone key.
            waypoints: List of zone keys to pass through in order.
            transport_mode_key: Transport mode.

        Returns:
            Dict with keys:
            - found: bool
            - path: list[TerrainZone]
            - total_cost: int
            - reason: str (if not found)
        """
        # Build list of all points: start -> waypoints -> end
        all_points = [from_zone_key] + waypoints + [to_zone_key]

        full_path: list[TerrainZone] = []
        total_cost = 0

        # Find path between each consecutive pair
        for i in range(len(all_points) - 1):
            segment_result = self.find_optimal_path(
                all_points[i],
                all_points[i + 1],
                transport_mode_key,
            )

            if not segment_result["found"]:
                return {
                    "found": False,
                    "path": [],
                    "total_cost": 0,
                    "reason": f"Cannot reach waypoint {all_points[i + 1]} from {all_points[i]}",
                }

            # Append path segment (skip first zone if not first segment to avoid duplicates)
            if i == 0:
                full_path.extend(segment_result["path"])
            else:
                full_path.extend(segment_result["path"][1:])

            total_cost += segment_result["total_cost"]

        return {
            "found": True,
            "path": full_path,
            "total_cost": total_cost,
        }

    # =========================================================================
    # Route Summary
    # =========================================================================

    def get_route_summary(
        self,
        path: list[TerrainZone],
        transport_mode_key: str,
    ) -> dict:
        """Generate a summary of a route.

        Args:
            path: List of zones in the route.
            transport_mode_key: Transport mode being used.

        Returns:
            Dict with:
            - terrain_breakdown: dict[TerrainType, int] (count by terrain)
            - total_time: int (minutes)
            - total_distance: int (number of zones)
            - hazards: list[dict] (zones requiring skill checks)
        """
        if not path:
            return {
                "terrain_breakdown": {},
                "total_time": 0,
                "total_distance": 0,
                "hazards": [],
            }

        terrain_breakdown: dict[str, int] = {}
        total_time = 0
        hazards = []

        transport_mode = self._zone_manager.get_transport_mode(transport_mode_key)

        for zone in path:
            # Count terrain types
            terrain_key = zone.terrain_type.value
            terrain_breakdown[terrain_key] = terrain_breakdown.get(terrain_key, 0) + 1

            # Calculate time
            cost = self._get_zone_cost(zone, transport_mode_key, transport_mode)
            if cost is not None:
                total_time += cost

            # Track hazards
            if zone.requires_skill is not None:
                hazards.append({
                    "zone_key": zone.zone_key,
                    "zone_name": zone.display_name,
                    "skill": zone.requires_skill,
                    "difficulty": zone.skill_difficulty or 10,
                    "failure_consequence": zone.failure_consequence,
                })

        return {
            "terrain_breakdown": terrain_breakdown,
            "total_time": total_time,
            "total_distance": len(path),
            "hazards": hazards,
        }

    # =========================================================================
    # A* Algorithm Implementation
    # =========================================================================

    def _astar(
        self,
        start: TerrainZone,
        goal: TerrainZone,
        transport_mode_key: str,
        transport_mode: TransportMode | None,
        avoid_terrain: list[TerrainType],
        prefer_roads: bool,
    ) -> tuple[list[TerrainZone] | None, int]:
        """A* pathfinding algorithm.

        Args:
            start: Starting zone.
            goal: Destination zone.
            transport_mode_key: Transport mode key.
            transport_mode: Transport mode object (or None).
            avoid_terrain: Terrain types to avoid.
            prefer_roads: Whether to prefer roads.

        Returns:
            Tuple of (path, total_cost) or (None, 0) if no path found.
        """
        # Priority queue: (f_score, zone_id, zone)
        open_set: list[PriorityItem] = []
        heapq.heappush(open_set, PriorityItem(0, start.id, start))

        # Track where each zone was reached from
        came_from: dict[int, tuple[TerrainZone, int]] = {}  # zone_id -> (from_zone, edge_cost)

        # Best known cost to reach each zone
        g_score: dict[int, int] = {start.id: 0}

        # Set of zones in open_set for quick lookup
        open_set_ids: set[int] = {start.id}

        # Set of zones we've fully processed
        closed_set: set[int] = set()

        while open_set:
            current_item = heapq.heappop(open_set)
            current = current_item.zone
            open_set_ids.discard(current.id)

            if current.id == goal.id:
                # Reconstruct path
                return self._reconstruct_path(came_from, current, g_score[current.id])

            closed_set.add(current.id)

            # Get neighbors
            neighbors = self._get_neighbors(current, transport_mode_key, transport_mode)

            for neighbor, edge_cost in neighbors:
                if neighbor.id in closed_set:
                    continue

                # Check if terrain should be avoided
                if neighbor.terrain_type in avoid_terrain:
                    continue

                # Calculate tentative g_score
                tentative_g = g_score[current.id] + edge_cost

                # Apply road preference bonus
                if prefer_roads and neighbor.terrain_type == TerrainType.ROAD:
                    tentative_g = int(tentative_g * 0.7)  # 30% bonus for roads

                if neighbor.id not in g_score or tentative_g < g_score[neighbor.id]:
                    # This is a better path
                    came_from[neighbor.id] = (current, edge_cost)
                    g_score[neighbor.id] = tentative_g

                    # f_score = g_score + heuristic (we use 0 heuristic for simplicity)
                    f_score = tentative_g

                    if neighbor.id not in open_set_ids:
                        heapq.heappush(open_set, PriorityItem(f_score, neighbor.id, neighbor))
                        open_set_ids.add(neighbor.id)

        # No path found
        return None, 0

    def _get_neighbors(
        self,
        zone: TerrainZone,
        transport_mode_key: str,
        transport_mode: TransportMode | None,
    ) -> list[tuple[TerrainZone, int]]:
        """Get neighboring zones with travel costs.

        Args:
            zone: Current zone.
            transport_mode_key: Transport mode key.
            transport_mode: Transport mode object.

        Returns:
            List of (neighbor_zone, edge_cost) tuples.
        """
        neighbors = []

        # Get outgoing connections
        outgoing = (
            self.db.query(ZoneConnection)
            .filter(
                ZoneConnection.session_id == self.session_id,
                ZoneConnection.from_zone_id == zone.id,
                ZoneConnection.is_passable == True,
            )
            .all()
        )

        for conn in outgoing:
            neighbor = (
                self.db.query(TerrainZone)
                .filter(TerrainZone.id == conn.to_zone_id)
                .first()
            )
            if neighbor:
                cost = self._calculate_edge_cost(
                    neighbor, conn, transport_mode_key, transport_mode
                )
                if cost is not None:
                    neighbors.append((neighbor, cost))

        # Get incoming bidirectional connections
        incoming = (
            self.db.query(ZoneConnection)
            .filter(
                ZoneConnection.session_id == self.session_id,
                ZoneConnection.to_zone_id == zone.id,
                ZoneConnection.is_passable == True,
                ZoneConnection.is_bidirectional == True,
            )
            .all()
        )

        for conn in incoming:
            neighbor = (
                self.db.query(TerrainZone)
                .filter(TerrainZone.id == conn.from_zone_id)
                .first()
            )
            if neighbor:
                cost = self._calculate_edge_cost(
                    neighbor, conn, transport_mode_key, transport_mode
                )
                if cost is not None:
                    neighbors.append((neighbor, cost))

        return neighbors

    def _calculate_edge_cost(
        self,
        to_zone: TerrainZone,
        connection: ZoneConnection,
        transport_mode_key: str,
        transport_mode: TransportMode | None,
    ) -> int | None:
        """Calculate the cost to traverse to a zone.

        Args:
            to_zone: Destination zone.
            connection: The connection being used.
            transport_mode_key: Transport mode key.
            transport_mode: Transport mode object.

        Returns:
            Cost in minutes, or None if impassable.
        """
        # Get zone traversal cost
        zone_cost = self._get_zone_cost(to_zone, transport_mode_key, transport_mode)
        if zone_cost is None:
            return None

        # Add connection crossing cost
        total_cost = zone_cost + connection.crossing_minutes

        return total_cost

    def _get_zone_cost(
        self,
        zone: TerrainZone,
        transport_mode_key: str,
        transport_mode: TransportMode | None,
    ) -> int | None:
        """Get the cost to traverse a zone.

        Args:
            zone: The zone to traverse.
            transport_mode_key: Transport mode key.
            transport_mode: Transport mode object.

        Returns:
            Cost in minutes, or None if impassable.
        """
        # Walking uses base cost
        if transport_mode_key == "walking":
            return zone.base_travel_cost

        # Check zone's explicit mounted cost
        if transport_mode_key == "mounted" and zone.mounted_travel_cost is not None:
            return zone.mounted_travel_cost

        # Apply transport mode multiplier
        if transport_mode is not None:
            terrain_key = zone.terrain_type.value
            terrain_costs = transport_mode.terrain_costs or {}

            multiplier = terrain_costs.get(terrain_key)
            if multiplier is None:
                return None  # Impassable

            return int(zone.base_travel_cost * multiplier)

        return zone.base_travel_cost

    def _reconstruct_path(
        self,
        came_from: dict[int, tuple[TerrainZone, int]],
        current: TerrainZone,
        total_cost: int,
    ) -> tuple[list[TerrainZone], int]:
        """Reconstruct the path from came_from data.

        Args:
            came_from: Dict mapping zone_id to (previous_zone, edge_cost).
            current: The goal zone.
            total_cost: Total path cost.

        Returns:
            Tuple of (path, total_cost).
        """
        path = [current]

        while current.id in came_from:
            current, _ = came_from[current.id]
            path.append(current)

        path.reverse()
        return path, total_cost
