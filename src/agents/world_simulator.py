"""World simulator for time passage and background world updates.

This module handles:
- Time-based need decay for all characters
- NPC schedule-driven position updates
- Mood modifier expiration
- Missed appointment checking
- Temporal consistency effects

Can be used directly as a manager or wrapped as a LangGraph agent node.
"""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from src.database.models.entities import Entity
from src.database.models.enums import EntityType
from src.database.models.session import GameSession
from src.database.models.world import Schedule, TimeState, WorldEvent
from src.managers.base import BaseManager
from src.managers.consistency import ConsistencyValidator
from src.managers.needs import ActivityType, NeedsManager
from src.managers.relationship_manager import RelationshipManager


@dataclass
class NPCMovement:
    """Record of an NPC movement."""

    npc_id: int
    npc_name: str
    from_location: str | None
    to_location: str
    reason: str


@dataclass
class SimulationResult:
    """Results of a world simulation step."""

    hours_simulated: float
    npc_movements: list[NPCMovement] = field(default_factory=list)
    needs_updated: list[int] = field(default_factory=list)  # Entity IDs
    mood_modifiers_expired: int = 0
    missed_appointments: list[dict] = field(default_factory=list)
    lighting_change: str | None = None
    crowd_change: str | None = None
    items_spoiled: list[int] = field(default_factory=list)
    items_cleaned: list[int] = field(default_factory=list)
    random_events: list[dict] = field(default_factory=list)


class WorldSimulator(BaseManager):
    """Simulates world changes due to time passage and location changes.

    Integrates with:
    - NeedsManager for hunger/fatigue/etc decay
    - RelationshipManager for mood modifier expiration
    - ConsistencyValidator for temporal effects
    - Schedule system for NPC movements
    """

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        needs_manager: NeedsManager | None = None,
        relationship_manager: RelationshipManager | None = None,
        consistency_validator: ConsistencyValidator | None = None,
    ) -> None:
        """Initialize with optional manager references."""
        super().__init__(db, game_session)
        self._needs_manager = needs_manager
        self._relationship_manager = relationship_manager
        self._consistency_validator = consistency_validator

    @property
    def needs_manager(self) -> NeedsManager:
        if self._needs_manager is None:
            self._needs_manager = NeedsManager(self.db, self.game_session)
        return self._needs_manager

    @property
    def relationship_manager(self) -> RelationshipManager:
        if self._relationship_manager is None:
            self._relationship_manager = RelationshipManager(self.db, self.game_session)
        return self._relationship_manager

    @property
    def consistency_validator(self) -> ConsistencyValidator:
        if self._consistency_validator is None:
            self._consistency_validator = ConsistencyValidator(self.db, self.game_session)
        return self._consistency_validator

    def simulate_time_passage(
        self,
        hours: float,
        player_id: int,
        player_activity: ActivityType = ActivityType.ACTIVE,
        player_location: str | None = None,
        is_player_alone: bool = False,
    ) -> SimulationResult:
        """Simulate world changes for time passage.

        This is the main entry point. Call this whenever time advances
        in the game (after GM describes time passing).

        Args:
            hours: In-game hours that passed
            player_id: Player entity ID
            player_activity: What the player was doing
            player_location: Current player location key
            is_player_alone: Whether player was alone (affects social need)

        Returns:
            SimulationResult with all changes made
        """
        result = SimulationResult(hours_simulated=hours)

        # 1. Apply need decay to player
        self._apply_player_needs(player_id, hours, player_activity, is_player_alone, result)

        # 2. Apply need decay to NPCs
        self._apply_npc_needs(hours, player_location, result)

        # 3. Calculate temporal effects (spoilage, cleaning, lighting)
        if player_location:
            self._apply_temporal_effects(hours, player_location, result)

        # 4. Update NPC positions per schedules
        self._update_npc_positions(hours, result)

        # 5. Expire mood modifiers
        result.mood_modifiers_expired = self.relationship_manager.expire_mood_modifiers()

        # 6. Check missed appointments (TODO: when TaskManager is available)
        # self._check_missed_appointments(result)

        # 7. Advance game time
        self._advance_time(hours)

        self.db.flush()
        return result

    def _apply_player_needs(
        self,
        player_id: int,
        hours: float,
        activity: ActivityType,
        is_alone: bool,
        result: SimulationResult,
    ) -> None:
        """Apply need decay to player."""
        self.needs_manager.apply_time_decay(
            entity_id=player_id,
            hours=hours,
            activity=activity,
            is_alone=is_alone,
        )
        result.needs_updated.append(player_id)

    def _apply_npc_needs(
        self,
        hours: float,
        player_location: str | None,
        result: SimulationResult,
    ) -> None:
        """Apply need decay to NPCs.

        NPCs at player's location use ACTIVE activity type.
        Off-screen NPCs use their scheduled activity.
        """
        # Get all active NPCs
        npcs = (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.session_id,
                Entity.entity_type == EntityType.NPC,
                Entity.is_alive == True,
                Entity.is_active == True,
            )
            .all()
        )

        for npc in npcs:
            # Determine activity type
            # TODO: Use proper location tracking when available
            activity = self._get_npc_activity_type(npc.id, hours)

            # Apply decay
            self.needs_manager.apply_time_decay(
                entity_id=npc.id,
                hours=hours,
                activity=activity,
                is_alone=False,  # NPCs are usually not "alone" in social sense
            )
            result.needs_updated.append(npc.id)

    def _get_npc_activity_type(self, npc_id: int, hours: float) -> ActivityType:
        """Determine NPC activity type based on schedule or urgency.

        Returns activity type affecting need decay rates.
        """
        # Check if NPC has urgent need that overrides schedule
        urgency = self.needs_manager.get_npc_urgency(npc_id)
        need_name, urgency_level = urgency

        if urgency_level > 70:
            # Urgent need overrides schedule
            if need_name == "hunger":
                return ActivityType.ACTIVE  # Seeking food
            elif need_name == "fatigue":
                return ActivityType.RESTING  # Trying to rest
            elif need_name == "social_connection":
                return ActivityType.SOCIALIZING
            elif need_name == "intimacy":
                return ActivityType.ACTIVE  # Seeking companionship

        # Default: check schedule
        time_state = self._get_time_state()
        if time_state:
            # Get current schedule entry for NPC
            schedule = self._get_current_schedule(npc_id, time_state)
            if schedule:
                return self._schedule_to_activity_type(schedule.activity)

        # Default activity
        return ActivityType.ACTIVE

    def _schedule_to_activity_type(self, activity_description: str) -> ActivityType:
        """Map schedule activity description to ActivityType."""
        activity_lower = activity_description.lower()

        if any(word in activity_lower for word in ["sleep", "rest", "nap"]):
            return ActivityType.SLEEPING
        elif any(word in activity_lower for word in ["relax", "sit", "read", "wait"]):
            return ActivityType.RESTING
        elif any(word in activity_lower for word in ["talk", "chat", "meet", "visit", "party"]):
            return ActivityType.SOCIALIZING
        elif any(word in activity_lower for word in ["fight", "train", "spar", "battle"]):
            return ActivityType.COMBAT
        else:
            return ActivityType.ACTIVE

    def _apply_temporal_effects(
        self,
        hours: float,
        location_key: str,
        result: SimulationResult,
    ) -> None:
        """Apply temporal effects from ConsistencyValidator."""
        effects = self.consistency_validator.calculate_temporal_effects(
            hours_passed=hours,
            current_location=location_key,
        )

        result.lighting_change = effects.lighting_change
        result.crowd_change = effects.crowd_change
        result.items_spoiled = effects.items_spoiled
        result.items_cleaned = effects.items_cleaned

    def _update_npc_positions(
        self,
        hours: float,
        result: SimulationResult,
    ) -> None:
        """Update NPC positions based on schedules.

        For significant time passage (30+ min), NPCs should move
        to their scheduled locations.
        """
        if hours < 0.5:  # Less than 30 minutes
            return

        time_state = self._get_time_state()
        if not time_state:
            return

        # Get all NPCs with schedules
        npcs_with_schedules = (
            self.db.query(Entity)
            .join(Schedule, Entity.id == Schedule.entity_id)
            .filter(
                Entity.session_id == self.session_id,
                Entity.entity_type == EntityType.NPC,
                Entity.is_alive == True,
                Entity.is_active == True,
            )
            .distinct()
            .all()
        )

        for npc in npcs_with_schedules:
            movement = self._update_npc_position(npc, time_state)
            if movement:
                result.npc_movements.append(movement)

    def _update_npc_position(
        self,
        npc: Entity,
        time_state: TimeState,
    ) -> NPCMovement | None:
        """Update a single NPC's position based on schedule.

        Returns NPCMovement if they moved, None otherwise.
        """
        schedule = self._get_current_schedule(npc.id, time_state)
        if not schedule or not schedule.location_key:
            return None

        # Get current location from NPC extension
        current_location = None
        if npc.npc_extension:
            current_location = npc.npc_extension.current_location

        # Check if already at scheduled location
        if current_location == schedule.location_key:
            return None

        # Check if urgent need overrides schedule
        need_name, urgency = self.needs_manager.get_npc_urgency(npc.id)
        if urgency > 70:
            # Don't move per schedule, need takes priority
            return None

        # Move NPC
        if npc.npc_extension:
            npc.npc_extension.current_location = schedule.location_key
            npc.npc_extension.current_activity = schedule.activity

        return NPCMovement(
            npc_id=npc.id,
            npc_name=npc.display_name,
            from_location=current_location,
            to_location=schedule.location_key,
            reason=f"schedule: {schedule.activity}",
        )

    def _get_current_schedule(
        self,
        entity_id: int,
        time_state: TimeState,
    ) -> Schedule | None:
        """Get the current schedule entry for an entity."""
        from src.database.models.enums import DayOfWeek

        # Parse current time
        current_time = time_state.current_time  # "HH:MM"

        # Map day of week string to enum
        day_mapping = {
            "monday": DayOfWeek.MONDAY,
            "tuesday": DayOfWeek.TUESDAY,
            "wednesday": DayOfWeek.WEDNESDAY,
            "thursday": DayOfWeek.THURSDAY,
            "friday": DayOfWeek.FRIDAY,
            "saturday": DayOfWeek.SATURDAY,
            "sunday": DayOfWeek.SUNDAY,
        }
        current_day = day_mapping.get(time_state.day_of_week.lower())

        if not current_day:
            return None

        # Query schedules that apply now
        # Match: day_pattern is current day (or DAILY) AND time is in range
        schedules = (
            self.db.query(Schedule)
            .filter(
                Schedule.entity_id == entity_id,
                Schedule.session_id == self.session_id,
                Schedule.day_pattern.in_([current_day, DayOfWeek.DAILY]),
                Schedule.start_time <= current_time,
                Schedule.end_time >= current_time,
            )
            .order_by(Schedule.priority.desc())
            .first()
        )

        return schedules

    def _get_time_state(self) -> TimeState | None:
        """Get current time state."""
        return (
            self.db.query(TimeState)
            .filter(TimeState.session_id == self.session_id)
            .first()
        )

    def _advance_time(self, hours: float) -> None:
        """Advance the game clock by the specified hours."""
        time_state = self._get_time_state()
        if not time_state:
            return

        # Parse current time
        current_hour, current_minute = map(int, time_state.current_time.split(":"))

        # Add hours
        total_minutes = current_hour * 60 + current_minute + int(hours * 60)
        days_passed = total_minutes // (24 * 60)
        remaining_minutes = total_minutes % (24 * 60)

        new_hour = remaining_minutes // 60
        new_minute = remaining_minutes % 60

        # Update time
        time_state.current_time = f"{new_hour:02d}:{new_minute:02d}"

        # Update day if needed
        if days_passed > 0:
            time_state.current_day += days_passed

            # Advance day of week
            days_of_week = [
                "monday", "tuesday", "wednesday", "thursday",
                "friday", "saturday", "sunday"
            ]
            current_idx = days_of_week.index(time_state.day_of_week.lower())
            new_idx = (current_idx + days_passed) % 7
            time_state.day_of_week = days_of_week[new_idx]

    def on_location_change(
        self,
        player_id: int,
        from_location: str | None,
        to_location: str,
        travel_time_hours: float = 0.0,
    ) -> SimulationResult:
        """Handle player location change.

        Called when player moves to a new location. Applies travel time
        and triggers location-specific updates.

        Args:
            player_id: Player entity ID
            from_location: Previous location key (None if unknown)
            to_location: New location key
            travel_time_hours: Time spent traveling

        Returns:
            SimulationResult with changes
        """
        result = SimulationResult(hours_simulated=travel_time_hours)

        if travel_time_hours > 0:
            # Simulate time passing during travel
            result = self.simulate_time_passage(
                hours=travel_time_hours,
                player_id=player_id,
                player_activity=ActivityType.ACTIVE,
                player_location=to_location,
                is_player_alone=True,  # Usually alone while traveling
            )

        # TODO: Check what changed at new location since last visit
        # - Items that should be there
        # - NPCs who should be there
        # - Any events that happened

        return result

    def create_world_event(
        self,
        event_type: str,
        summary: str,
        details: dict | None = None,
        location_key: str | None = None,
        affected_entities: list[str] | None = None,
    ) -> WorldEvent:
        """Create a world event record.

        Use for random events, NPC actions, etc.
        """
        time_state = self._get_time_state()

        event = WorldEvent(
            session_id=self.session_id,
            event_type=event_type,
            summary=summary,
            details=details,
            game_day=time_state.current_day if time_state else 1,
            game_time=time_state.current_time if time_state else None,
            location_key=location_key,
            affected_entities=affected_entities,
            is_processed=False,
        )
        self.db.add(event)
        self.db.flush()
        return event


# LangGraph node function (for future integration)
def world_simulator_node(state: dict) -> dict:
    """LangGraph node wrapper for WorldSimulator.

    Expected state keys:
    - db: SQLAlchemy session
    - game_session: GameSession object
    - time_advance_minutes: Minutes to simulate
    - player_id: Player entity ID
    - player_activity: Activity type string
    - player_location: Current location key

    Returns updated state with simulation_result.
    """
    db = state["db"]
    game_session = state["game_session"]

    simulator = WorldSimulator(db, game_session)

    hours = state.get("time_advance_minutes", 0) / 60
    if hours > 0:
        result = simulator.simulate_time_passage(
            hours=hours,
            player_id=state["player_id"],
            player_activity=ActivityType(state.get("player_activity", "active")),
            player_location=state.get("player_location"),
            is_player_alone=state.get("is_player_alone", False),
        )

        state["simulation_result"] = {
            "hours_simulated": result.hours_simulated,
            "npc_movements": [
                {
                    "npc_name": m.npc_name,
                    "from": m.from_location,
                    "to": m.to_location,
                    "reason": m.reason,
                }
                for m in result.npc_movements
            ],
            "needs_updated_count": len(result.needs_updated),
            "mood_modifiers_expired": result.mood_modifiers_expired,
            "lighting_change": result.lighting_change,
            "crowd_change": result.crowd_change,
        }

    return state
