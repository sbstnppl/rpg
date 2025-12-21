"""WorldMechanics for Scene-First Architecture.

This module handles the simulation of the game world:
- Determining which NPCs are present at locations
- Applying realistic constraints to NPC placement
- Processing world events
- Introducing new elements with validation

WorldMechanics operates BEFORE the narrator - it decides what exists,
then the narrator describes it.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from src.database.models.enums import DayOfWeek, EntityType
from src.database.models.entities import Entity, NPCExtension
from src.database.models.relationships import Relationship
from src.database.models.world import Schedule, TimeState
from src.managers.base import BaseManager
from src.world.constraints import RealisticConstraintChecker
from src.world.schemas import (
    ConstraintResult,
    NewElement,
    NPCPlacement,
    PresenceReason,
    SocialLimits,
    WorldUpdate,
)

if TYPE_CHECKING:
    from src.database.models.session import GameSession
    from src.llm.base import LLMProvider

logger = logging.getLogger(__name__)


# Days that count as weekdays
WEEKDAYS = {
    DayOfWeek.MONDAY,
    DayOfWeek.TUESDAY,
    DayOfWeek.WEDNESDAY,
    DayOfWeek.THURSDAY,
    DayOfWeek.FRIDAY,
}

# Days that count as weekend
WEEKEND = {
    DayOfWeek.SATURDAY,
    DayOfWeek.SUNDAY,
}


# Relationship thresholds for categorization
CLOSE_FRIEND_THRESHOLD = 70  # liking + trust >= this * 2
CASUAL_FRIEND_THRESHOLD = 50


class WorldMechanics(BaseManager):
    """Handles world simulation for Scene-First Architecture.

    This class determines:
    - Which NPCs are present at locations (from schedules, residence, events)
    - Whether NPC placements are physically and socially valid
    - When new elements can be introduced

    It operates before narration, building the world state that the
    narrator will then describe.
    """

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        llm_provider: LLMProvider | None = None,
        social_limits: SocialLimits | None = None,
    ) -> None:
        """Initialize WorldMechanics.

        Args:
            db: Database session.
            game_session: Current game session.
            llm_provider: Optional LLM provider for story-driven decisions.
            social_limits: Optional custom social limits (uses defaults if None).
        """
        super().__init__(db, game_session)
        self.llm_provider = llm_provider
        self.social_limits = social_limits or SocialLimits()
        self.constraint_checker = RealisticConstraintChecker(
            db=db,
            game_session=game_session,
            social_limits=self.social_limits,
        )

    # =========================================================================
    # Time Management
    # =========================================================================

    def get_time_state(self) -> TimeState:
        """Get or create the current time state.

        Returns:
            TimeState for this session.
        """
        time_state = (
            self.db.query(TimeState)
            .filter(TimeState.session_id == self.session_id)
            .first()
        )

        if time_state is None:
            # Create default time state
            time_state = TimeState(
                session_id=self.session_id,
                current_day=1,
                current_time="08:00",
                day_of_week="monday",
            )
            self.db.add(time_state)
            self.db.flush()

        return time_state

    def get_current_hour(self) -> int:
        """Get the current hour of day (0-23).

        Returns:
            Current hour.
        """
        time_state = self.get_time_state()
        try:
            hour = int(time_state.current_time.split(":")[0])
            return hour
        except (ValueError, IndexError):
            return 12  # Default to noon

    def get_day_of_week(self) -> DayOfWeek:
        """Get current day of week.

        Returns:
            DayOfWeek enum value.
        """
        time_state = self.get_time_state()
        day_str = time_state.day_of_week.lower()
        try:
            return DayOfWeek(day_str)
        except ValueError:
            return DayOfWeek.MONDAY

    # =========================================================================
    # Scheduled NPCs
    # =========================================================================

    def get_scheduled_npcs(self, location_key: str) -> list[NPCPlacement]:
        """Get NPCs scheduled to be at a location at current time.

        Args:
            location_key: The location to check.

        Returns:
            List of NPCPlacement for scheduled NPCs.
        """
        time_state = self.get_time_state()
        current_time = time_state.current_time
        current_day = self.get_day_of_week()

        # Query all schedules for this location
        schedules = (
            self.db.query(Schedule)
            .filter(Schedule.location_key == location_key)
            .all()
        )

        placements = []
        for schedule in schedules:
            # Check if day matches
            if not self._day_matches(current_day, schedule.day_pattern):
                continue

            # Check if time is in range
            if not self._time_in_range(
                current_time,
                schedule.start_time,
                schedule.end_time,
            ):
                continue

            # Get the entity
            entity = self.db.query(Entity).filter(
                Entity.id == schedule.entity_id,
                Entity.session_id == self.session_id,
            ).first()

            if entity is None:
                continue

            # Create placement
            placement = NPCPlacement(
                entity_key=entity.entity_key,
                presence_reason=PresenceReason.SCHEDULE,
                presence_justification=f"Scheduled: {schedule.activity}",
                activity=schedule.activity,
                mood="neutral",
                position_in_scene="at their usual spot",
            )
            placements.append(placement)

        return placements

    def _day_matches(self, current_day: DayOfWeek, pattern: DayOfWeek) -> bool:
        """Check if current day matches schedule pattern.

        Args:
            current_day: The current day of week.
            pattern: The schedule's day pattern.

        Returns:
            True if day matches pattern.
        """
        if pattern == DayOfWeek.DAILY:
            return True
        if pattern == DayOfWeek.WEEKDAY:
            return current_day in WEEKDAYS
        if pattern == DayOfWeek.WEEKEND:
            return current_day in WEEKEND
        return current_day == pattern

    def _time_in_range(self, current: str, start: str, end: str) -> bool:
        """Check if current time is within schedule range.

        Handles midnight crossing (e.g., 22:00 to 06:00).

        Args:
            current: Current time in HH:MM format.
            start: Range start in HH:MM format.
            end: Range end in HH:MM format.

        Returns:
            True if current is in range.
        """
        def to_minutes(t: str) -> int:
            h, m = map(int, t.split(":"))
            return h * 60 + m

        current_mins = to_minutes(current)
        start_mins = to_minutes(start)
        end_mins = to_minutes(end)

        if start_mins <= end_mins:
            # Same day range
            return start_mins <= current_mins < end_mins
        else:
            # Crosses midnight
            return current_mins >= start_mins or current_mins < end_mins

    # =========================================================================
    # Resident NPCs
    # =========================================================================

    def get_resident_npcs(self, location_key: str) -> list[NPCPlacement]:
        """Get NPCs who live at a location.

        Args:
            location_key: The location to check.

        Returns:
            List of NPCPlacement for resident NPCs.
        """
        # Query entities via their NPC extensions with matching home_location
        results = (
            self.db.query(Entity, NPCExtension)
            .join(NPCExtension, Entity.id == NPCExtension.entity_id)
            .filter(
                Entity.session_id == self.session_id,
                Entity.entity_type == EntityType.NPC,
                NPCExtension.home_location == location_key,
            )
            .all()
        )

        placements = []
        for entity, ext in results:
            placement = NPCPlacement(
                entity_key=entity.entity_key,
                presence_reason=PresenceReason.LIVES_HERE,
                presence_justification="This is their home",
                activity="going about their day",
                mood="neutral",
                position_in_scene="in their home",
            )
            placements.append(placement)

        return placements

    def get_current_location_npcs(self, location_key: str) -> list[NPCPlacement]:
        """Get NPCs whose current_location matches this location.

        This catches NPCs who are at a location but aren't:
        - Scheduled to be there
        - Residents
        - Event-driven

        Args:
            location_key: The location to check.

        Returns:
            List of NPCPlacement for NPCs at this location.
        """
        # Query entities via their NPC extensions with matching current_location
        results = (
            self.db.query(Entity, NPCExtension)
            .join(NPCExtension, Entity.id == NPCExtension.entity_id)
            .filter(
                Entity.session_id == self.session_id,
                Entity.entity_type == EntityType.NPC,
                Entity.is_alive == True,
                NPCExtension.current_location == location_key,
            )
            .all()
        )

        placements = []
        for entity, ext in results:
            placement = NPCPlacement(
                entity_key=entity.entity_key,
                presence_reason=PresenceReason.VISITING,
                presence_justification="Currently at this location",
                activity=ext.current_activity or "present",
                mood=ext.current_mood or "neutral",
                position_in_scene="in the area",
            )
            placements.append(placement)

        return placements

    # =========================================================================
    # Event-Driven NPCs
    # =========================================================================

    def get_event_driven_npcs(self, location_key: str) -> list[NPCPlacement]:
        """Get NPCs from active events at a location.

        Events can trigger NPC appearances. For example:
        - A robbery event might bring guards
        - A festival event might bring merchants
        - A delivery event might bring a courier

        Args:
            location_key: The location to check.

        Returns:
            List of NPCPlacement for event-driven NPCs.
        """
        from src.managers.event_manager import EventManager

        event_manager = EventManager(self.db, self.game_session)
        events = event_manager.get_events_at_location(location_key, include_processed=False)

        placements = []
        for event in events:
            # Check if event has affected entities that should appear
            if not event.affected_entities:
                continue

            for entity_key in event.affected_entities:
                # Check if entity exists
                entity = self.db.query(Entity).filter(
                    Entity.session_id == self.session_id,
                    Entity.entity_key == entity_key,
                ).first()

                if entity is None:
                    continue

                # Create placement from event
                placement = NPCPlacement(
                    entity_key=entity_key,
                    presence_reason=PresenceReason.EVENT,
                    presence_justification=f"Event: {event.summary}",
                    activity=event.details.get("activity", "responding to event") if event.details else "responding to event",
                    mood=event.details.get("mood", "concerned") if event.details else "concerned",
                    position_in_scene=event.details.get("position", "at the scene") if event.details else "at the scene",
                )
                placements.append(placement)

        return placements

    # =========================================================================
    # Story-Driven NPCs (LLM-based)
    # =========================================================================

    async def get_story_driven_npcs(
        self,
        location_key: str,
        location_type: str,
        scene_context: str = "",
    ) -> list[NPCPlacement]:
        """Get NPCs that should appear based on story needs.

        Uses LLM to determine if narrative pacing or story progression
        requires an NPC to appear. This is for organic encounters that
        aren't scheduled or event-driven.

        Args:
            location_key: The location to check.
            location_type: Type of location (tavern, shop, etc.).
            scene_context: Optional context from recent turns.

        Returns:
            List of NPCPlacement for story-driven NPCs.
        """
        if not self.llm_provider:
            return []

        # Call LLM for story-driven decisions
        world_update = await self._call_world_mechanics_llm(
            location_key=location_key,
            location_type=location_type,
            scene_context=scene_context,
        )

        if world_update is None:
            return []

        # Return story-driven NPCs from the update
        return [
            npc for npc in world_update.npcs_at_location
            if npc.presence_reason == PresenceReason.STORY
        ]

    async def _call_world_mechanics_llm(
        self,
        location_key: str,
        location_type: str,
        scene_context: str = "",
    ) -> WorldUpdate | None:
        """Call LLM for world mechanics decisions.

        Uses structured output to get WorldUpdate with:
        - Story-driven NPC appearances
        - World events
        - Fact updates

        Args:
            location_key: The location to check.
            location_type: Type of location.
            scene_context: Optional context from recent turns.

        Returns:
            WorldUpdate from LLM or None if call fails.
        """
        if not self.llm_provider:
            return None

        from jinja2 import Environment, FileSystemLoader
        from pathlib import Path

        try:
            # Load the template
            template_dir = Path(__file__).parent.parent.parent / "data" / "templates"
            env = Environment(loader=FileSystemLoader(template_dir))
            template = env.get_template("world_mechanics.jinja2")

            # Get player info
            player = self._get_player_entity()

            # Get time state
            time_state = self.get_time_state()

            # Get relationship counts
            counts = self.get_relationship_counts(player.id) if player else {
                "close_friends": 0,
                "casual_friends": 0,
                "acquaintances": 0,
                "new_this_week": 0,
            }

            # Render prompt
            prompt = template.render(
                location={
                    "display_name": location_key.replace("_", " ").title(),
                    "location_key": location_key,
                    "location_type": location_type,
                },
                game_time={
                    "display": time_state.current_time,
                    "day_name": time_state.day_of_week.title(),
                },
                player={
                    "display_name": player.display_name if player else "Unknown",
                    "personality": player.personality if player else None,
                },
                relationships=[],  # Could populate from relationship queries
                counts=counts,
                limits=self.social_limits,
                scheduled_npcs=[],  # Already handled separately
                resident_npcs=[],  # Already handled separately
                recent_events=[],  # Could populate from event queries
                active_plots=[],  # Could populate from task queries
                recent_turns_summary=scene_context,
            )

            # Call LLM with structured output
            from src.llm.schema_models import Message

            response = await self.llm_provider.complete_structured(
                messages=[Message.user(prompt)],
                response_schema=WorldUpdate,
                temperature=0.3,
            )

            if response and response.parsed_content:
                # Convert dict to Pydantic model if needed
                if isinstance(response.parsed_content, dict):
                    return WorldUpdate.model_validate(response.parsed_content)
                return response.parsed_content

        except Exception as e:
            logger.warning(f"World mechanics LLM call failed: {e}")

        return None

    # =========================================================================
    # All NPCs at Location
    # =========================================================================

    def get_npcs_at_location(self, location_key: str) -> list[NPCPlacement]:
        """Get all NPCs at a location from all sources.

        Combines:
        - Scheduled NPCs
        - Resident NPCs
        - NPCs with current_location set to this location
        - Event-driven NPCs

        Note: Story-driven NPCs require async call - use get_npcs_at_location_async().

        Args:
            location_key: The location to check.

        Returns:
            List of NPCPlacement for all NPCs.
        """
        placements = []

        # Add scheduled NPCs
        placements.extend(self.get_scheduled_npcs(location_key))

        # Add residents (avoiding duplicates)
        existing_keys = {p.entity_key for p in placements}
        for resident in self.get_resident_npcs(location_key):
            if resident.entity_key not in existing_keys:
                placements.append(resident)
                existing_keys.add(resident.entity_key)

        # Add NPCs with current_location set
        for current_npc in self.get_current_location_npcs(location_key):
            if current_npc.entity_key not in existing_keys:
                placements.append(current_npc)
                existing_keys.add(current_npc.entity_key)

        # Add event-driven NPCs
        for event_npc in self.get_event_driven_npcs(location_key):
            if event_npc.entity_key not in existing_keys:
                placements.append(event_npc)
                existing_keys.add(event_npc.entity_key)

        return placements

    async def get_npcs_at_location_async(
        self,
        location_key: str,
        location_type: str = "general",
        scene_context: str = "",
    ) -> list[NPCPlacement]:
        """Get all NPCs at a location including story-driven (async version).

        Combines:
        - Scheduled NPCs
        - Resident NPCs
        - Event-driven NPCs
        - Story-driven NPCs (LLM-based)

        Args:
            location_key: The location to check.
            location_type: Type of location.
            scene_context: Optional context from recent turns.

        Returns:
            List of NPCPlacement for all NPCs.
        """
        # Get sync sources first
        placements = self.get_npcs_at_location(location_key)
        existing_keys = {p.entity_key for p in placements}

        # Add story-driven NPCs (requires LLM)
        if self.llm_provider:
            story_npcs = await self.get_story_driven_npcs(
                location_key=location_key,
                location_type=location_type,
                scene_context=scene_context,
            )
            for story_npc in story_npcs:
                if story_npc.entity_key not in existing_keys:
                    placements.append(story_npc)
                    existing_keys.add(story_npc.entity_key)

        return placements

    # =========================================================================
    # Constraint Checking
    # =========================================================================

    def check_placement_constraints(
        self,
        placement: NPCPlacement,
        location_type: str,
        is_player_home: bool = False,
    ) -> ConstraintResult:
        """Check if an NPC placement is valid.

        Args:
            placement: The NPC placement to check.
            location_type: Type of location (bedroom, tavern, etc.).
            is_player_home: Whether this is the player's home.

        Returns:
            ConstraintResult indicating validity.
        """
        current_hour = self.get_current_hour()

        # Check physical constraints
        physical_result = self.constraint_checker.check_physical_constraints(
            npc_placement=placement,
            location_type=location_type,
            is_player_home=is_player_home,
            current_hour=current_hour,
        )

        if not physical_result.allowed:
            return physical_result

        # Check social constraints if this is a new NPC
        if placement.new_npc is not None:
            # Get current relationship counts
            player = self._get_player_entity()
            if player:
                counts = self.get_relationship_counts(player.id)
            else:
                counts = {
                    "close_friends": 0,
                    "casual_friends": 0,
                    "acquaintances": 0,
                    "new_this_week": 0,
                }

            social_result = self.constraint_checker.check_social_constraints(
                new_npc=placement.new_npc,
                relationship_type=placement.new_npc.relationship_to_player,
                current_close_friends=counts["close_friends"],
                current_casual_friends=counts["casual_friends"],
                current_acquaintances=counts["acquaintances"],
                new_relationships_this_week=counts.get("new_this_week", 0),
            )

            if not social_result.allowed:
                return social_result

        return ConstraintResult(allowed=True)

    # =========================================================================
    # Advance World
    # =========================================================================

    def advance_world(
        self,
        location_key: str,
        location_type: str | None = None,
        is_player_home: bool = False,
    ) -> WorldUpdate:
        """Main entry point for world mechanics processing.

        Determines the current world state at a location:
        - Which NPCs are present
        - Any events occurring
        - New facts to establish

        Args:
            location_key: The player's current location.
            location_type: Type of location (optional, derived if not provided).
            is_player_home: Whether this is the player's home.

        Returns:
            WorldUpdate with the current world state.
        """
        # Get all potential NPCs at location
        all_placements = self.get_npcs_at_location(location_key)

        # Filter by constraints
        valid_placements = []
        for placement in all_placements:
            result = self.check_placement_constraints(
                placement,
                location_type=location_type or "general",
                is_player_home=is_player_home,
            )
            if result.allowed:
                valid_placements.append(placement)
            else:
                logger.debug(
                    f"Filtered out {placement.entity_key}: {result.reason}"
                )

        return WorldUpdate(
            npcs_at_location=valid_placements,
            scheduled_movements=[],
            new_elements=[],
            events=[],
            fact_updates=[],
        )

    # =========================================================================
    # New Element Introduction
    # =========================================================================

    def maybe_introduce_element(self, element: NewElement) -> ConstraintResult:
        """Check if a new world element can be introduced.

        Args:
            element: The element to potentially introduce.

        Returns:
            ConstraintResult indicating if introduction is allowed.
        """
        # Get current relationship counts
        player = self._get_player_entity()
        if player:
            counts = self.get_relationship_counts(player.id)
        else:
            counts = {
                "close_friends": 0,
                "casual_friends": 0,
                "acquaintances": 0,
                "new_this_week": 0,
            }

        return self.constraint_checker.check_new_element(
            element=element,
            current_close_friends=counts["close_friends"],
            current_casual_friends=counts["casual_friends"],
            current_acquaintances=counts["acquaintances"],
            new_relationships_this_week=counts.get("new_this_week", 0),
        )

    # =========================================================================
    # Relationship Counting
    # =========================================================================

    def get_relationship_counts(self, entity_id: int) -> dict[str, int]:
        """Count relationships by category for an entity.

        Categories:
        - close_friends: High liking AND trust (>= 70)
        - casual_friends: Moderate liking (>= 50, < 70)
        - acquaintances: Known but not friends (< 50)
        - new_this_week: Relationships formed this week

        Args:
            entity_id: The entity to count relationships for.

        Returns:
            Dict with counts for each category.
        """
        relationships = (
            self.db.query(Relationship)
            .filter(
                Relationship.session_id == self.session_id,
                Relationship.from_entity_id == entity_id,
                Relationship.knows == True,  # noqa: E712
            )
            .all()
        )

        close_friends = 0
        casual_friends = 0
        acquaintances = 0

        for rel in relationships:
            # Classify by liking and trust levels
            if rel.liking >= CLOSE_FRIEND_THRESHOLD and rel.trust >= CLOSE_FRIEND_THRESHOLD:
                close_friends += 1
            elif rel.liking >= CASUAL_FRIEND_THRESHOLD:
                casual_friends += 1
            else:
                acquaintances += 1

        # TODO: Track new_this_week from relationship creation timestamps
        # For now, return 0
        new_this_week = 0

        return {
            "close_friends": close_friends,
            "casual_friends": casual_friends,
            "acquaintances": acquaintances,
            "new_this_week": new_this_week,
        }

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _get_player_entity(self) -> Entity | None:
        """Get the player entity for this session.

        Returns:
            Player Entity or None if not found.
        """
        return (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.session_id,
                Entity.entity_type == EntityType.PLAYER,
            )
            .first()
        )
