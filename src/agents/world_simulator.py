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
from src.database.models.enums import EntityType, GoalPriority, GoalStatus, GoalType
from src.database.models.goals import NPCGoal
from src.database.models.session import GameSession
from src.database.models.world import Schedule, TimeState, WorldEvent
from src.managers.base import BaseManager
from src.managers.consistency import ConsistencyValidator
from src.managers.goal_manager import GoalManager
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
class GoalStepResult:
    """Result of executing a single goal step."""

    goal_id: int
    entity_id: int
    step_executed: str
    success: bool
    npc_moved: bool = False
    new_location: str | None = None
    goal_completed: bool = False
    goal_blocked: bool = False
    narrative_hook: str | None = None


@dataclass
class GoalCreatedEvent:
    """Record of a goal being created from needs."""

    entity_id: int
    entity_name: str
    goal_type: str
    target: str
    motivation: str
    priority: str


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
    # Goal-related results
    goals_created: list[GoalCreatedEvent] = field(default_factory=list)
    goal_steps_executed: list[GoalStepResult] = field(default_factory=list)
    goals_completed: list[int] = field(default_factory=list)  # Goal IDs
    goals_failed: list[int] = field(default_factory=list)  # Goal IDs


class WorldSimulator(BaseManager):
    """Simulates world changes due to time passage and location changes.

    Integrates with:
    - NeedsManager for hunger/energy/etc decay
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
        goal_manager: GoalManager | None = None,
    ) -> None:
        """Initialize with optional manager references."""
        super().__init__(db, game_session)
        self._needs_manager = needs_manager
        self._relationship_manager = relationship_manager
        self._consistency_validator = consistency_validator
        self._goal_manager = goal_manager

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

    @property
    def goal_manager(self) -> GoalManager:
        if self._goal_manager is None:
            self._goal_manager = GoalManager(self.db, self.game_session)
        return self._goal_manager

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

        # 4. Check for need-driven goal creation
        self._check_need_driven_goals(result)

        # 5. Process NPC goals (may cause movement)
        self._process_npc_goals(hours, result)

        # 6. Update NPC positions per schedules (for NPCs not pursuing goals)
        self._update_npc_positions(hours, result)

        # 7. Expire mood modifiers
        result.mood_modifiers_expired = self.relationship_manager.expire_mood_modifiers()

        # 8. Check missed appointments (TODO: when TaskManager is available)
        # self._check_missed_appointments(result)

        # 9. Advance game time
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
            elif need_name == "energy":
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
        # Note: Schedule doesn't have session_id - entities are session-scoped
        schedules = (
            self.db.query(Schedule)
            .filter(
                Schedule.entity_id == entity_id,
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

    # =========================================================================
    # Goal Processing
    # =========================================================================

    def _check_need_driven_goals(self, result: SimulationResult) -> None:
        """Create goals for NPCs with urgent unmet needs.

        When an NPC has a need above threshold and no active goal to address it,
        a new goal is created. This drives autonomous NPC behavior.
        """
        # Threshold for creating need-driven goals
        URGENT_THRESHOLD = 75

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
            # Check for urgent needs
            urgency = self.needs_manager.get_npc_urgency(npc.id)
            need_name, urgency_level = urgency

            if urgency_level < URGENT_THRESHOLD:
                continue

            # Map need to goal type
            need_to_goal_type = {
                "hunger": GoalType.SURVIVE,
                "thirst": GoalType.SURVIVE,
                "energy": GoalType.SURVIVE,
                "social_connection": GoalType.SOCIAL,
                "intimacy": GoalType.ROMANCE,
            }

            goal_type = need_to_goal_type.get(need_name, GoalType.SURVIVE)

            # Check if NPC already has an active goal for this need
            existing_goals = self.goal_manager.get_active_goals(
                entity_id=npc.id,
                goal_type=goal_type,
            )

            # Skip if already pursuing a goal for this need
            has_matching_goal = False
            for goal in existing_goals:
                if need_name in (goal.motivation or []):
                    has_matching_goal = True
                    break

            if has_matching_goal:
                continue

            # Create a new goal
            target_map = {
                "hunger": "food",
                "thirst": "drink",
                "energy": "rest",
                "social_connection": "companionship",
                "intimacy": "intimate_partner",
            }

            description_map = {
                "hunger": "Find something to eat",
                "thirst": "Find something to drink",
                "energy": "Find a place to rest",
                "social_connection": "Find someone to talk to",
                "intimacy": "Seek intimate companionship",
            }

            target = target_map.get(need_name, need_name)
            description = description_map.get(need_name, f"Address {need_name} need")

            # Determine priority based on urgency
            if urgency_level >= 90:
                priority = GoalPriority.URGENT
            elif urgency_level >= 80:
                priority = GoalPriority.HIGH
            else:
                priority = GoalPriority.MEDIUM

            # Create the goal
            goal = self.goal_manager.create_goal(
                entity_id=npc.id,
                goal_type=goal_type,
                target=target,
                description=description,
                success_condition=f"{need_name} drops below {URGENT_THRESHOLD - 20}",
                motivation=[need_name],
                triggered_by=f"need_urgency_{urgency_level}",
                priority=priority,
                strategies=[
                    f"look for {target}",
                    f"acquire {target}",
                    f"use {target} to satisfy {need_name}",
                ],
            )

            result.goals_created.append(GoalCreatedEvent(
                entity_id=npc.id,
                entity_name=npc.display_name,
                goal_type=goal_type.value,
                target=target,
                motivation=need_name,
                priority=priority.value,
            ))

    def _process_npc_goals(self, hours: float, result: SimulationResult) -> None:
        """Process active NPC goals and execute steps.

        For significant time passages (30+ min), NPCs can make progress
        on their goals. This may result in NPC movement, information
        gathering, or goal completion.
        """
        if hours < 0.5:  # Less than 30 minutes, no significant goal progress
            return

        # Get all active goals ordered by priority
        active_goals = self.goal_manager.get_active_goals()

        # Group goals by NPC (each NPC processes their highest priority goal)
        npc_goals: dict[int, NPCGoal] = {}
        for goal in active_goals:
            if goal.entity_id not in npc_goals:
                npc_goals[goal.entity_id] = goal

        # Process each NPC's primary goal
        for entity_id, goal in npc_goals.items():
            npc = self.db.query(Entity).filter(Entity.id == entity_id).first()
            if not npc:
                continue

            step_result = self._execute_goal_step(npc, goal, hours)
            if step_result:
                result.goal_steps_executed.append(step_result)

                if step_result.goal_completed:
                    result.goals_completed.append(goal.id)

                if step_result.npc_moved and step_result.new_location:
                    result.npc_movements.append(NPCMovement(
                        npc_id=npc.id,
                        npc_name=npc.display_name,
                        from_location=npc.npc_extension.current_location if npc.npc_extension else None,
                        to_location=step_result.new_location,
                        reason=f"goal: {goal.description}",
                    ))

    def _execute_goal_step(
        self,
        npc: Entity,
        goal: NPCGoal,
        hours: float,
    ) -> GoalStepResult | None:
        """Execute one step of an NPC's goal pursuit.

        Args:
            npc: The NPC entity.
            goal: The goal being pursued.
            hours: Time available for pursuit.

        Returns:
            GoalStepResult or None if no step was executed.
        """
        if not goal.strategies or goal.current_step >= len(goal.strategies):
            # No more steps or no strategy defined
            return None

        current_step_desc = goal.strategies[goal.current_step]

        # Determine success based on goal type and step
        step_success = self._evaluate_step_success(npc, goal, current_step_desc)

        result = GoalStepResult(
            goal_id=goal.id,
            entity_id=npc.id,
            step_executed=current_step_desc,
            success=step_success,
        )

        if step_success:
            # Advance to next step
            goal.current_step += 1

            # Check if goal is complete
            if goal.current_step >= len(goal.strategies):
                # All steps completed
                self.goal_manager.complete_goal(
                    goal.id,
                    f"Completed all steps for: {goal.description}"
                )
                result.goal_completed = True
            else:
                # Check for location-changing steps
                next_step = goal.strategies[goal.current_step] if goal.current_step < len(goal.strategies) else ""
                move_result = self._check_step_for_movement(npc, current_step_desc, next_step)
                if move_result:
                    result.npc_moved = True
                    result.new_location = move_result
                    # Update NPC location
                    if npc.npc_extension:
                        npc.npc_extension.current_location = move_result
        else:
            # Step failed - mark goal as blocked if repeated failures
            result.goal_blocked = True
            self.goal_manager.block_goal(goal.id, f"Failed step: {current_step_desc}")

        self.db.flush()
        return result

    def _evaluate_step_success(
        self,
        npc: Entity,
        goal: NPCGoal,
        step_description: str,
    ) -> bool:
        """Evaluate if a goal step succeeds.

        This is a simplified simulation - real success depends on
        world state, NPC skills, etc. For now, we use probability
        based on goal priority (urgent goals have higher success).
        """
        import random

        step_lower = step_description.lower()

        # Base success rates by step type
        if "look for" in step_lower or "search" in step_lower:
            base_rate = 0.7
        elif "acquire" in step_lower or "get" in step_lower:
            base_rate = 0.6
        elif "use" in step_lower or "consume" in step_lower:
            base_rate = 0.9  # Usually succeeds once acquired
        elif "talk" in step_lower or "ask" in step_lower:
            base_rate = 0.5
        elif "travel" in step_lower or "go to" in step_lower:
            base_rate = 0.8
        else:
            base_rate = 0.6

        # Priority bonus
        priority_bonus = {
            GoalPriority.URGENT: 0.2,
            GoalPriority.HIGH: 0.1,
            GoalPriority.MEDIUM: 0.0,
            GoalPriority.LOW: -0.1,
            GoalPriority.BACKGROUND: -0.2,
        }
        modifier = priority_bonus.get(goal.priority, 0.0)

        success_rate = min(0.95, max(0.1, base_rate + modifier))
        return random.random() < success_rate

    def _check_step_for_movement(
        self,
        npc: Entity,
        current_step: str,
        next_step: str,
    ) -> str | None:
        """Check if a step implies NPC movement.

        Returns new location key if NPC should move, None otherwise.
        """
        step_lower = current_step.lower()

        # Simple heuristics for movement
        if "tavern" in step_lower:
            return "tavern"
        elif "inn" in step_lower:
            return "inn"
        elif "market" in step_lower:
            return "market"
        elif "shop" in step_lower:
            return "general_store"
        elif "home" in step_lower:
            return f"home_{npc.entity_key}"
        elif "temple" in step_lower:
            return "temple"
        elif "guild" in step_lower:
            return "guild_hall"

        # Check next step for location hints
        next_lower = next_step.lower()
        if "at the" in next_lower:
            # Extract location from "at the X"
            for loc in ["tavern", "inn", "market", "shop", "temple", "guild"]:
                if loc in next_lower:
                    return loc

        return None


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
            # Goal-related results
            "goals_created": [
                {
                    "entity_name": g.entity_name,
                    "goal_type": g.goal_type,
                    "target": g.target,
                    "motivation": g.motivation,
                    "priority": g.priority,
                }
                for g in result.goals_created
            ],
            "goal_steps_executed": [
                {
                    "goal_id": s.goal_id,
                    "step": s.step_executed,
                    "success": s.success,
                    "goal_completed": s.goal_completed,
                }
                for s in result.goal_steps_executed
            ],
            "goals_completed_count": len(result.goals_completed),
            "goals_failed_count": len(result.goals_failed),
        }

    return state
