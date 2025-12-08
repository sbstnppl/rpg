"""TravelManager for journey simulation and travel mechanics."""

import random
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from src.database.models.enums import EncounterFrequency, TerrainType
from src.database.models.navigation import TerrainZone, ZoneConnection
from src.database.models.session import GameSession
from src.managers.base import BaseManager
from src.managers.pathfinding_manager import PathfindingManager
from src.managers.zone_manager import ZoneManager


@dataclass
class JourneyState:
    """Tracks the state of an ongoing journey."""

    # Route info
    path: list[TerrainZone]
    path_index: int = 0
    destination_zone_key: str = ""
    transport_mode: str = "walking"

    # Current position
    current_zone_key: str = ""

    # Progress tracking
    elapsed_minutes: int = 0
    total_estimated_minutes: int = 0
    visited_zones: list[str] = field(default_factory=list)

    # State flags
    is_complete: bool = False
    is_interrupted: bool = False
    interrupt_reason: str | None = None

    @property
    def progress_percent(self) -> float:
        """Calculate journey progress as percentage."""
        if len(self.path) <= 1:
            return 100.0 if self.is_complete else 0.0
        return (self.path_index / (len(self.path) - 1)) * 100

    @property
    def zones_remaining(self) -> int:
        """Calculate number of zones left to traverse."""
        return max(0, len(self.path) - 1 - self.path_index)


# Encounter thresholds by frequency (roll must be >= threshold to trigger)
ENCOUNTER_THRESHOLDS = {
    EncounterFrequency.NONE: 101,  # Never triggers
    EncounterFrequency.LOW: 85,
    EncounterFrequency.MEDIUM: 65,
    EncounterFrequency.HIGH: 40,
    EncounterFrequency.VERY_HIGH: 20,
}


class TravelManager(BaseManager):
    """Manager for journey simulation and travel mechanics.

    Handles:
    - Starting and managing journeys
    - Step-by-step travel advancement
    - Encounter rolling
    - Skill check detection for hazardous terrain
    - Journey interruption and resumption
    - Detours to adjacent zones
    """

    def __init__(self, db: Session, game_session: GameSession) -> None:
        """Initialize TravelManager.

        Args:
            db: SQLAlchemy database session.
            game_session: Current game session.
        """
        super().__init__(db, game_session)
        self._zone_manager = ZoneManager(db, game_session)
        self._pathfinding_manager = PathfindingManager(db, game_session)

    # =========================================================================
    # Journey Management
    # =========================================================================

    def start_journey(
        self,
        from_zone_key: str,
        to_zone_key: str,
        transport_mode: str,
        avoid_terrain: list[TerrainType] | None = None,
        prefer_roads: bool = False,
    ) -> dict:
        """Start a new journey between two zones.

        Args:
            from_zone_key: Starting zone key.
            to_zone_key: Destination zone key.
            transport_mode: Transport mode (e.g., 'walking', 'mounted').
            avoid_terrain: Terrain types to avoid in routing.
            prefer_roads: Whether to prefer roads in routing.

        Returns:
            Dict with:
            - success: bool
            - journey: JourneyState (if success)
            - reason: str (if not success)
            - route_summary: dict (if success)
        """
        # Find optimal path
        path_result = self._pathfinding_manager.find_optimal_path(
            from_zone_key,
            to_zone_key,
            transport_mode,
            avoid_terrain=avoid_terrain,
            prefer_roads=prefer_roads,
        )

        if not path_result["found"]:
            return {
                "success": False,
                "reason": f"No path found: {path_result.get('reason', 'unknown')}",
            }

        # Check if destination is blocked
        dest_zone = self._zone_manager.get_zone(to_zone_key)
        if dest_zone and not dest_zone.is_accessible:
            return {
                "success": False,
                "reason": f"Destination blocked: {dest_zone.blocked_reason}",
            }

        # Create journey state
        journey = JourneyState(
            path=path_result["path"],
            path_index=0,
            destination_zone_key=to_zone_key,
            transport_mode=transport_mode,
            current_zone_key=from_zone_key,
            total_estimated_minutes=path_result["total_cost"],
            visited_zones=[from_zone_key],
        )

        # Get route summary
        route_summary = self._pathfinding_manager.get_route_summary(
            path_result["path"], transport_mode
        )

        return {
            "success": True,
            "journey": journey,
            "route_summary": route_summary,
        }

    def advance_travel(self, journey: JourneyState) -> dict:
        """Advance the journey to the next zone.

        Args:
            journey: Current journey state.

        Returns:
            Dict with:
            - success: bool
            - arrived: bool (if reached destination)
            - zone_info: dict (info about entered zone)
            - encounter_check: dict (encounter roll info)
            - skill_check: dict (if hazardous terrain)
            - elapsed_minutes: int
        """
        if journey.is_complete:
            return {
                "success": False,
                "reason": "Journey already complete",
            }

        if journey.is_interrupted:
            return {
                "success": False,
                "reason": "Journey interrupted - resume or cancel first",
            }

        # Check if we can advance
        if journey.path_index >= len(journey.path) - 1:
            journey.is_complete = True
            return {
                "success": True,
                "arrived": True,
                "zone_info": self._get_zone_info(journey.path[-1]),
                "encounter_check": {"rolled": 0, "threshold": 0, "triggered": False},
            }

        # Get next zone
        next_index = journey.path_index + 1
        next_zone = journey.path[next_index]

        # Check if next zone is accessible
        if not next_zone.is_accessible:
            return {
                "success": False,
                "reason": f"Path blocked: {next_zone.blocked_reason}",
                "blocked_at": next_zone.zone_key,
            }

        # Calculate travel time for this segment
        current_zone = journey.path[journey.path_index]
        segment_time = self._calculate_segment_time(
            current_zone, next_zone, journey.transport_mode
        )

        # Move to next zone
        journey.path_index = next_index
        journey.current_zone_key = next_zone.zone_key
        journey.elapsed_minutes += segment_time

        # Track visited
        if next_zone.zone_key not in journey.visited_zones:
            journey.visited_zones.append(next_zone.zone_key)

        # Check for arrival
        arrived = journey.path_index >= len(journey.path) - 1
        if arrived:
            journey.is_complete = True

        # Roll for encounter
        encounter_check = self._roll_encounter(next_zone)

        # Check for skill requirements
        skill_check = self._check_skill_requirement(next_zone)

        return {
            "success": True,
            "arrived": arrived,
            "zone_info": self._get_zone_info(next_zone),
            "encounter_check": encounter_check,
            "skill_check": skill_check,
            "elapsed_minutes": segment_time,
        }

    def interrupt_travel(self, journey: JourneyState, reason: str) -> dict:
        """Interrupt the current journey.

        Args:
            journey: Current journey state.
            reason: Reason for interruption (e.g., 'explore', 'rest', 'combat').

        Returns:
            Dict with:
            - success: bool
            - current_zone: dict (info about current zone)
        """
        if journey.is_complete:
            return {
                "success": False,
                "reason": "Journey already complete",
            }

        journey.is_interrupted = True
        journey.interrupt_reason = reason

        current_zone = self._zone_manager.get_zone(journey.current_zone_key)
        current_zone_info = self._get_zone_info(current_zone) if current_zone else {}

        return {
            "success": True,
            "current_zone": current_zone_info,
            "message": f"Journey interrupted at {journey.current_zone_key}",
        }

    def resume_journey(self, journey: JourneyState) -> dict:
        """Resume an interrupted journey.

        Args:
            journey: Interrupted journey state.

        Returns:
            Dict with:
            - success: bool
            - journey: JourneyState
        """
        if journey.is_complete:
            return {
                "success": False,
                "reason": "Journey already complete",
            }

        if not journey.is_interrupted:
            return {
                "success": False,
                "reason": "Journey is not interrupted",
            }

        journey.is_interrupted = False
        journey.interrupt_reason = None

        return {
            "success": True,
            "journey": journey,
            "message": f"Journey resumed from {journey.current_zone_key}",
        }

    def get_journey_state(self, journey: JourneyState) -> dict:
        """Get current journey progress information.

        Args:
            journey: Current journey state.

        Returns:
            Dict with progress information.
        """
        return {
            "current_zone": journey.current_zone_key,
            "destination": journey.destination_zone_key,
            "progress_percent": journey.progress_percent,
            "zones_remaining": journey.zones_remaining,
            "elapsed_minutes": journey.elapsed_minutes,
            "total_estimated_minutes": journey.total_estimated_minutes,
            "is_complete": journey.is_complete,
            "is_interrupted": journey.is_interrupted,
            "visited_zones": journey.visited_zones,
            "transport_mode": journey.transport_mode,
        }

    # =========================================================================
    # Detours and Exploration
    # =========================================================================

    def detour_to_zone(self, journey: JourneyState, zone_key: str) -> dict:
        """Detour from the current path to an adjacent zone.

        Args:
            journey: Current journey state.
            zone_key: Zone to detour to.

        Returns:
            Dict with:
            - success: bool
            - reason: str (if not success)
        """
        # Check if zone is adjacent to current position
        adjacent_zones = self._zone_manager.get_adjacent_zones(journey.current_zone_key)
        adjacent_keys = {z.zone_key for z in adjacent_zones}

        if zone_key not in adjacent_keys:
            return {
                "success": False,
                "reason": f"Zone '{zone_key}' is not adjacent to current location",
            }

        # Get the target zone
        target_zone = self._zone_manager.get_zone(zone_key)
        if target_zone is None:
            return {
                "success": False,
                "reason": f"Zone not found: {zone_key}",
            }

        # Check accessibility
        if not target_zone.is_accessible:
            return {
                "success": False,
                "reason": f"Zone blocked: {target_zone.blocked_reason}",
            }

        # Calculate travel time
        current_zone = self._zone_manager.get_zone(journey.current_zone_key)
        segment_time = self._calculate_segment_time(
            current_zone, target_zone, journey.transport_mode
        ) if current_zone else target_zone.base_travel_cost

        # Update journey state
        journey.current_zone_key = zone_key
        journey.elapsed_minutes += segment_time
        journey.is_interrupted = True
        journey.interrupt_reason = "detour"

        if zone_key not in journey.visited_zones:
            journey.visited_zones.append(zone_key)

        return {
            "success": True,
            "zone_info": self._get_zone_info(target_zone),
            "elapsed_minutes": segment_time,
        }

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _get_zone_info(self, zone: TerrainZone | None) -> dict:
        """Get displayable info about a zone.

        Args:
            zone: The zone to describe.

        Returns:
            Dict with zone information.
        """
        if zone is None:
            return {}

        return {
            "zone_key": zone.zone_key,
            "display_name": zone.display_name,
            "terrain_type": zone.terrain_type.value,
            "description": zone.description,
            "atmosphere": zone.atmosphere,
            "visibility_range": zone.visibility_range.value,
            "encounter_frequency": zone.encounter_frequency.value,
        }

    def _calculate_segment_time(
        self,
        from_zone: TerrainZone | None,
        to_zone: TerrainZone,
        transport_mode: str,
    ) -> int:
        """Calculate travel time for a segment.

        Args:
            from_zone: Starting zone.
            to_zone: Destination zone.
            transport_mode: Transport mode being used.

        Returns:
            Travel time in minutes.
        """
        # Get zone traversal cost
        zone_cost = self._zone_manager.get_terrain_cost(to_zone.zone_key, transport_mode)
        if zone_cost is None:
            zone_cost = to_zone.base_travel_cost

        # Find connection crossing time
        crossing_time = 5  # Default
        if from_zone:
            connection = self._find_connection(from_zone, to_zone)
            if connection:
                crossing_time = connection.crossing_minutes

        return zone_cost + crossing_time

    def _find_connection(
        self, from_zone: TerrainZone, to_zone: TerrainZone
    ) -> ZoneConnection | None:
        """Find the connection between two zones.

        Args:
            from_zone: Source zone.
            to_zone: Destination zone.

        Returns:
            ZoneConnection if found.
        """
        # Check outgoing
        connection = (
            self.db.query(ZoneConnection)
            .filter(
                ZoneConnection.session_id == self.session_id,
                ZoneConnection.from_zone_id == from_zone.id,
                ZoneConnection.to_zone_id == to_zone.id,
            )
            .first()
        )

        if connection:
            return connection

        # Check bidirectional incoming
        connection = (
            self.db.query(ZoneConnection)
            .filter(
                ZoneConnection.session_id == self.session_id,
                ZoneConnection.from_zone_id == to_zone.id,
                ZoneConnection.to_zone_id == from_zone.id,
                ZoneConnection.is_bidirectional == True,
            )
            .first()
        )

        return connection

    def _roll_encounter(self, zone: TerrainZone) -> dict:
        """Roll for a random encounter in a zone.

        Args:
            zone: The zone to roll in.

        Returns:
            Dict with roll info.
        """
        threshold = ENCOUNTER_THRESHOLDS.get(
            zone.encounter_frequency, ENCOUNTER_THRESHOLDS[EncounterFrequency.LOW]
        )
        rolled = random.randint(1, 100)
        triggered = rolled >= threshold

        return {
            "rolled": rolled,
            "threshold": threshold,
            "triggered": triggered,
            "encounter_frequency": zone.encounter_frequency.value,
            "encounter_table_key": zone.encounter_table_key,
        }

    def _check_skill_requirement(self, zone: TerrainZone) -> dict:
        """Check if a zone requires a skill check.

        Args:
            zone: The zone to check.

        Returns:
            Dict with skill check info.
        """
        if zone.requires_skill is None:
            return {"required": False}

        return {
            "required": True,
            "skill": zone.requires_skill,
            "difficulty": zone.skill_difficulty or 10,
            "failure_consequence": zone.failure_consequence,
        }
