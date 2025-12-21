"""Realistic constraint checking for Scene-First Architecture.

This module enforces realistic limits on world mechanics:
- Social constraints (relationship limits, introduction rates)
- Event constraints (frequency, plausibility)
- Physical constraints (accessibility, time of day, location type)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING

from src.world.schemas import (
    ConstraintResult,
    NewElement,
    NPCPlacement,
    NPCSpec,
    PresenceReason,
    SocialLimits,
    WorldEvent,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from src.database.models import GameSession


@dataclass
class PhysicalLimits:
    """Physical plausibility limits."""

    # Time-based constraints
    earliest_visit_hour: int = 7  # Don't visit before 7am
    latest_visit_hour: int = 22  # Don't visit after 10pm
    sleep_start_hour: int = 23  # NPCs sleep after 11pm
    sleep_end_hour: int = 6  # NPCs wake at 6am

    # Location access constraints
    private_locations: set[str] = field(
        default_factory=lambda: {"bedroom", "bathroom", "private_room"}
    )
    public_locations: set[str] = field(
        default_factory=lambda: {"tavern", "market", "street", "plaza", "shop"}
    )


@dataclass
class EventLimits:
    """Event frequency and plausibility limits."""

    max_events_per_day: int = 3
    max_intrusions_per_week: int = 2
    min_hours_between_events: int = 2
    max_npcs_per_event: int = 5


class RealisticConstraintChecker:
    """Checks constraints for realistic world simulation.

    This class validates that World Mechanics decisions are realistic:
    - NPCs can't teleport or appear impossibly
    - Social relationships grow at realistic rates
    - Events happen at plausible frequencies
    - Physical access is respected (private vs public spaces)
    """

    def __init__(
        self,
        db: Session | None = None,
        game_session: GameSession | None = None,
        social_limits: SocialLimits | None = None,
        physical_limits: PhysicalLimits | None = None,
        event_limits: EventLimits | None = None,
    ) -> None:
        """Initialize the constraint checker.

        Args:
            db: Database session for querying current state
            game_session: Current game session
            social_limits: Social relationship limits (defaults used if None)
            physical_limits: Physical plausibility limits (defaults used if None)
            event_limits: Event frequency limits (defaults used if None)
        """
        self.db = db
        self.game_session = game_session
        self.social_limits = social_limits or SocialLimits()
        self.physical_limits = physical_limits or PhysicalLimits()
        self.event_limits = event_limits or EventLimits()

    def check_social_constraints(
        self,
        new_npc: NPCSpec | None,
        relationship_type: str | None = None,
        current_close_friends: int = 0,
        current_casual_friends: int = 0,
        current_acquaintances: int = 0,
        new_relationships_this_week: int = 0,
    ) -> ConstraintResult:
        """Check if introducing a new NPC relationship is allowed.

        Args:
            new_npc: Specification for the new NPC (None if existing NPC)
            relationship_type: Type of relationship being formed
            current_close_friends: Number of existing close friends
            current_casual_friends: Number of existing casual friends
            current_acquaintances: Number of existing acquaintances
            new_relationships_this_week: Number of new relationships this week

        Returns:
            ConstraintResult indicating if the introduction is allowed
        """
        # If no new NPC is being introduced, always allowed
        if new_npc is None:
            return ConstraintResult(allowed=True)

        limits = self.social_limits

        # Check rate limit for new relationships
        if new_relationships_this_week >= limits.max_new_relationships_per_week:
            return ConstraintResult(
                allowed=False,
                reason=f"Too many new relationships this week ({new_relationships_this_week})",
                violated_constraint="max_new_relationships_per_week",
                suggestion="Wait until next week or use an existing acquaintance",
            )

        # Check relationship type limits
        if relationship_type == "close_friend":
            if current_close_friends >= limits.max_close_friends:
                return ConstraintResult(
                    allowed=False,
                    reason=f"Maximum close friends reached ({limits.max_close_friends})",
                    violated_constraint="max_close_friends",
                    suggestion="Introduce as casual friend instead",
                )

        elif relationship_type == "casual_friend":
            if current_casual_friends >= limits.max_casual_friends:
                return ConstraintResult(
                    allowed=False,
                    reason=f"Maximum casual friends reached ({limits.max_casual_friends})",
                    violated_constraint="max_casual_friends",
                    suggestion="Introduce as acquaintance instead",
                )

        elif relationship_type == "acquaintance":
            if current_acquaintances >= limits.max_acquaintances:
                return ConstraintResult(
                    allowed=False,
                    reason=f"Maximum acquaintances reached ({limits.max_acquaintances})",
                    violated_constraint="max_acquaintances",
                    suggestion="Use an existing NPC instead",
                )

        return ConstraintResult(allowed=True)

    def check_physical_constraints(
        self,
        npc_placement: NPCPlacement,
        location_type: str,
        is_player_home: bool = False,
        current_hour: int = 12,
    ) -> ConstraintResult:
        """Check if an NPC can physically be at a location.

        Args:
            npc_placement: The NPC placement to check
            location_type: Type of location (bedroom, tavern, etc.)
            is_player_home: Whether this is the player's home
            current_hour: Current hour of day (0-23)

        Returns:
            ConstraintResult indicating if the placement is allowed
        """
        limits = self.physical_limits
        reason = npc_placement.presence_reason

        # Check sleeping hours
        if limits.sleep_start_hour <= current_hour or current_hour < limits.sleep_end_hour:
            # It's sleeping hours
            if reason == PresenceReason.VISITING:
                return ConstraintResult(
                    allowed=False,
                    reason=f"NPCs don't visit during sleeping hours ({current_hour}:00)",
                    violated_constraint="sleep_hours",
                    suggestion="Delay visit until morning or use STORY reason",
                )

        # Check private location access
        if location_type in limits.private_locations:
            # Private location - need good reason
            if is_player_home:
                # Player's private space
                allowed_reasons = {
                    PresenceReason.LIVES_HERE,
                    PresenceReason.EVENT,
                    PresenceReason.STORY,
                }
                if reason not in allowed_reasons:
                    return ConstraintResult(
                        allowed=False,
                        reason=f"NPCs can't casually enter player's {location_type}",
                        violated_constraint="private_location",
                        suggestion="NPC needs LIVES_HERE, EVENT, or STORY reason",
                    )
            else:
                # Someone else's private space
                allowed_reasons = {
                    PresenceReason.LIVES_HERE,
                    PresenceReason.SCHEDULE,
                    PresenceReason.EVENT,
                }
                if reason not in allowed_reasons:
                    return ConstraintResult(
                        allowed=False,
                        reason=f"NPCs can't casually enter others' {location_type}",
                        violated_constraint="private_location",
                        suggestion="Use LIVES_HERE, SCHEDULE, or EVENT reason",
                    )

        # Check visiting hours for non-emergency visits
        if reason == PresenceReason.VISITING:
            if current_hour < limits.earliest_visit_hour:
                return ConstraintResult(
                    allowed=False,
                    reason=f"Too early for visits ({current_hour}:00)",
                    violated_constraint="visiting_hours",
                    suggestion=f"Wait until {limits.earliest_visit_hour}:00 or use EVENT reason",
                )
            if current_hour >= limits.latest_visit_hour:
                return ConstraintResult(
                    allowed=False,
                    reason=f"Too late for visits ({current_hour}:00)",
                    violated_constraint="visiting_hours",
                    suggestion=f"Visit before {limits.latest_visit_hour}:00 or use EVENT reason",
                )

        return ConstraintResult(allowed=True)

    def check_event_constraints(
        self,
        event: WorldEvent,
        events_today: int = 0,
        intrusions_this_week: int = 0,
        hours_since_last_event: float = 24.0,
    ) -> ConstraintResult:
        """Check if a world event is plausible.

        Args:
            event: The event to check
            events_today: Number of events already today
            intrusions_this_week: Number of intrusion-type events this week
            hours_since_last_event: Hours since the last event

        Returns:
            ConstraintResult indicating if the event is allowed
        """
        limits = self.event_limits

        # Check daily event limit
        if events_today >= limits.max_events_per_day:
            return ConstraintResult(
                allowed=False,
                reason=f"Too many events today ({events_today})",
                violated_constraint="max_events_per_day",
                suggestion="Wait until tomorrow or combine with existing event",
            )

        # Check event frequency
        if hours_since_last_event < limits.min_hours_between_events:
            return ConstraintResult(
                allowed=False,
                reason=f"Too soon after last event ({hours_since_last_event:.1f}h ago)",
                violated_constraint="min_hours_between_events",
                suggestion=f"Wait at least {limits.min_hours_between_events} hours",
            )

        # Check intrusion limit
        if event.event_type == "intrusion":
            if intrusions_this_week >= limits.max_intrusions_per_week:
                return ConstraintResult(
                    allowed=False,
                    reason=f"Too many intrusions this week ({intrusions_this_week})",
                    violated_constraint="max_intrusions_per_week",
                    suggestion="Use a different event type or wait until next week",
                )

        # Check NPC count in event
        if len(event.npcs_involved) > limits.max_npcs_per_event:
            return ConstraintResult(
                allowed=False,
                reason=f"Too many NPCs in event ({len(event.npcs_involved)})",
                violated_constraint="max_npcs_per_event",
                suggestion=f"Limit to {limits.max_npcs_per_event} NPCs",
            )

        return ConstraintResult(allowed=True)

    def check_new_element(
        self,
        element: NewElement,
        current_close_friends: int = 0,
        current_casual_friends: int = 0,
        current_acquaintances: int = 0,
        new_relationships_this_week: int = 0,
    ) -> ConstraintResult:
        """Check if a new world element can be introduced.

        Args:
            element: The new element specification
            current_close_friends: Number of existing close friends
            current_casual_friends: Number of existing casual friends
            current_acquaintances: Number of existing acquaintances
            new_relationships_this_week: New relationships this week

        Returns:
            ConstraintResult indicating if the element is allowed
        """
        if element.element_type == "npc":
            # Extract NPC spec from specification
            spec = element.specification
            relationship_type = spec.get("relationship_type", "acquaintance")

            # Create NPCSpec for checking
            npc_spec = NPCSpec(
                display_name=spec.get("display_name", "Unknown"),
                gender=spec.get("gender"),
                occupation=spec.get("occupation"),
                personality_hints=spec.get("personality_hints", []),
                relationship_to_player=spec.get("relationship_to_player"),
                backstory_hints=spec.get("backstory_hints", []),
            )

            return self.check_social_constraints(
                new_npc=npc_spec,
                relationship_type=relationship_type,
                current_close_friends=current_close_friends,
                current_casual_friends=current_casual_friends,
                current_acquaintances=current_acquaintances,
                new_relationships_this_week=new_relationships_this_week,
            )

        elif element.element_type == "fact":
            # Facts are generally allowed
            return ConstraintResult(allowed=True)

        elif element.element_type == "relationship":
            # Check relationship makes sense
            spec = element.specification
            relationship_type = spec.get("type", "acquaintance")

            # Use social limits for relationship introduction
            return self.check_social_constraints(
                new_npc=None,  # Relationship between existing NPCs
                relationship_type=relationship_type,
                current_close_friends=current_close_friends,
                current_casual_friends=current_casual_friends,
                current_acquaintances=current_acquaintances,
                new_relationships_this_week=new_relationships_this_week,
            )

        # Unknown element type
        return ConstraintResult(
            allowed=False,
            reason=f"Unknown element type: {element.element_type}",
            violated_constraint="element_type",
            suggestion="Use 'npc', 'fact', or 'relationship'",
        )

    def check_all_placements(
        self,
        placements: list[NPCPlacement],
        location_type: str,
        is_player_home: bool = False,
        current_hour: int = 12,
        current_close_friends: int = 0,
        current_casual_friends: int = 0,
        current_acquaintances: int = 0,
        new_relationships_this_week: int = 0,
    ) -> list[tuple[NPCPlacement, ConstraintResult]]:
        """Check constraints for all NPC placements.

        Args:
            placements: List of NPC placements to check
            location_type: Type of location
            is_player_home: Whether this is player's home
            current_hour: Current hour of day
            current_close_friends: Number of close friends
            current_casual_friends: Number of casual friends
            current_acquaintances: Number of acquaintances
            new_relationships_this_week: New relationships this week

        Returns:
            List of (placement, result) tuples for each placement
        """
        results = []

        for placement in placements:
            # Check physical constraints
            physical_result = self.check_physical_constraints(
                npc_placement=placement,
                location_type=location_type,
                is_player_home=is_player_home,
                current_hour=current_hour,
            )

            if not physical_result.allowed:
                results.append((placement, physical_result))
                continue

            # Check social constraints if this is a new NPC
            if placement.new_npc is not None:
                relationship_type = placement.new_npc.relationship_to_player
                social_result = self.check_social_constraints(
                    new_npc=placement.new_npc,
                    relationship_type=relationship_type,
                    current_close_friends=current_close_friends,
                    current_casual_friends=current_casual_friends,
                    current_acquaintances=current_acquaintances,
                    new_relationships_this_week=new_relationships_this_week,
                )

                if not social_result.allowed:
                    results.append((placement, social_result))
                    continue

            # All constraints passed
            results.append((placement, ConstraintResult(allowed=True)))

        return results

    def filter_valid_placements(
        self,
        placements: list[NPCPlacement],
        **kwargs: object,
    ) -> list[NPCPlacement]:
        """Filter placements to only those that pass all constraints.

        Args:
            placements: List of NPC placements to filter
            **kwargs: Arguments to pass to check_all_placements

        Returns:
            List of valid placements
        """
        results = self.check_all_placements(placements, **kwargs)
        return [placement for placement, result in results if result.allowed]
