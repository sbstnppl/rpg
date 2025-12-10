"""Pydantic schemas for NPC goals and autonomous behavior.

These schemas define the structure for NPC goals that drive autonomous
behavior in the world simulation system.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# Goal type literals - what the NPC is trying to accomplish
GoalType = Literal[
    "acquire",        # Get item/resource (miller needs grain)
    "meet_person",    # Find and interact with someone (Elara wants to see player)
    "go_to",          # Travel to location
    "learn_info",     # Discover information
    "avoid",          # Stay away from person/place
    "protect",        # Keep someone/something safe
    "earn_money",     # Work, trade, sell
    "romance",        # Pursue romantic interest
    "social",         # Make friends, build relationships
    "revenge",        # Get back at someone
    "survive",        # Meet basic needs (find food/water)
    "duty",           # Fulfill obligation/job
    "craft",          # Create something
    "heal",           # Recover from injury/illness
]

# Goal priority levels
GoalPriority = Literal["background", "low", "medium", "high", "urgent"]

# Goal status
GoalStatus = Literal["active", "completed", "failed", "abandoned", "blocked"]


class NPCGoal(BaseModel):
    """A goal that an NPC is actively pursuing.

    Goals drive autonomous NPC behavior. They are created from:
    - Interactions with the player
    - Critical needs (hunger > 80 → find food)
    - Events in the world
    - NPC personality and values

    The World Simulator processes goals between turns, advancing NPCs
    through their strategies even when the player isn't watching.
    """

    goal_id: str = Field(
        description="Unique identifier for this goal (e.g., 'goal_elara_001')"
    )
    entity_key: str = Field(
        description="Entity key of the NPC who has this goal"
    )
    session_id: int = Field(
        description="Game session this goal belongs to"
    )

    # What they want
    goal_type: GoalType = Field(
        description="Category of goal - what the NPC is trying to accomplish"
    )
    target: str = Field(
        description="Target of the goal: entity_key, location_key, item_key, or description"
    )
    description: str = Field(
        description="Human-readable description of the goal"
    )

    # Why they want it
    motivation: list[str] = Field(
        default_factory=list,
        description="Reasons driving this goal (e.g., ['physical_attraction', 'thirst', 'duty'])"
    )
    triggered_by: str | None = Field(
        default=None,
        description="Event or turn that created this goal (e.g., 'positive_interaction_turn_5')"
    )

    # Priority and timing
    priority: GoalPriority = Field(
        default="medium",
        description="How important this goal is relative to other goals"
    )
    deadline: datetime | None = Field(
        default=None,
        description="Game time by which this goal should be completed"
    )
    deadline_description: str | None = Field(
        default=None,
        description="Human-readable deadline (e.g., 'before nightfall', 'within 3 days')"
    )

    # How they'll pursue it
    strategies: list[str] = Field(
        default_factory=list,
        description="Ordered steps to achieve the goal"
    )
    current_step: int = Field(
        default=0,
        ge=0,
        description="Index of the current strategy step being pursued"
    )
    blocked_reason: str | None = Field(
        default=None,
        description="Why the NPC cannot currently proceed (if blocked)"
    )

    # Completion conditions
    success_condition: str = Field(
        description="What must happen for this goal to be completed"
    )
    failure_condition: str | None = Field(
        default=None,
        description="What would cause this goal to fail"
    )

    # Status
    status: GoalStatus = Field(
        default="active",
        description="Current status of the goal"
    )

    # Metadata
    created_at_turn: int = Field(
        description="Turn number when this goal was created"
    )
    completed_at_turn: int | None = Field(
        default=None,
        description="Turn number when this goal was completed (if completed)"
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "goal_id": "goal_elara_001",
                "entity_key": "customer_elara",
                "session_id": 1,
                "goal_type": "romance",
                "target": "player",
                "description": "Get to know the interesting stranger better",
                "motivation": ["physical_attraction", "gratitude", "curiosity"],
                "triggered_by": "positive_interaction_turn_5",
                "priority": "medium",
                "deadline": None,
                "deadline_description": None,
                "strategies": [
                    "Find out where the stranger is staying",
                    "Learn his name and background",
                    "Visit places he might frequent",
                    "Create opportunity for conversation"
                ],
                "current_step": 0,
                "blocked_reason": None,
                "success_condition": "Have meaningful conversation and learn player's name",
                "failure_condition": "Player leaves town or shows clear disinterest",
                "status": "active",
                "created_at_turn": 5,
                "completed_at_turn": None
            }
        }


class GoalCreation(BaseModel):
    """Schema for creating a new goal in the GM manifest.

    Used when the GM's structured output indicates a new goal should be
    created for an NPC based on events in the narrative.
    """

    entity_key: str = Field(
        description="Entity key of the NPC who will have this goal"
    )
    goal_type: GoalType = Field(
        description="Category of goal"
    )
    target: str = Field(
        description="Target of the goal"
    )
    description: str = Field(
        description="Human-readable description of the goal"
    )
    priority: GoalPriority = Field(
        default="medium",
        description="Goal priority"
    )
    motivation: list[str] = Field(
        default_factory=list,
        description="Reasons driving this goal"
    )
    triggered_by: str = Field(
        description="What event triggered this goal"
    )
    strategies: list[str] = Field(
        default_factory=list,
        description="Ordered steps to achieve the goal (optional - can be generated)"
    )
    success_condition: str | None = Field(
        default=None,
        description="What must happen for completion (optional - can be generated)"
    )
    failure_condition: str | None = Field(
        default=None,
        description="What would cause failure (optional)"
    )
    deadline_description: str | None = Field(
        default=None,
        description="When this needs to be done by (optional)"
    )


class GoalUpdate(BaseModel):
    """Schema for updating an existing goal in the GM manifest.

    Used when the GM's structured output indicates a goal's status
    or progress has changed.
    """

    goal_id: str = Field(
        description="ID of the goal to update"
    )
    status: GoalStatus | None = Field(
        default=None,
        description="New status (if changed)"
    )
    current_step: int | None = Field(
        default=None,
        ge=0,
        description="New current step (if advanced)"
    )
    blocked_reason: str | None = Field(
        default=None,
        description="Why blocked (if status is 'blocked')"
    )
    outcome: str | None = Field(
        default=None,
        description="Description of outcome (if completed or failed)"
    )
    note: str | None = Field(
        default=None,
        description="Additional context about the update"
    )


class GoalStepResult(BaseModel):
    """Result of executing one step of goal pursuit.

    Returned by the World Simulator when an NPC attempts to advance
    their goal during off-screen simulation.
    """

    success: bool = Field(
        description="Whether the step was successful"
    )
    goal_completed: bool = Field(
        default=False,
        description="Whether the entire goal is now complete"
    )
    goal_failed: bool = Field(
        default=False,
        description="Whether the goal has failed"
    )

    # NPC state changes
    npc_moved: bool = Field(
        default=False,
        description="Whether the NPC moved to a new location"
    )
    new_location: str | None = Field(
        default=None,
        description="New location key if NPC moved"
    )
    time_consumed: int = Field(
        default=0,
        ge=0,
        description="Minutes consumed by this step"
    )

    # World state changes
    facts_learned: list[tuple[str, str, str]] = Field(
        default_factory=list,
        description="Facts learned as (subject, predicate, value) tuples"
    )
    items_acquired: list[str] = Field(
        default_factory=list,
        description="Item keys acquired during this step"
    )
    items_consumed: list[str] = Field(
        default_factory=list,
        description="Item keys consumed during this step"
    )

    # For narrative hooks
    narrative_hook: str | None = Field(
        default=None,
        description="Significant event that might be mentioned to player"
    )

    # Retry logic
    will_retry: bool = Field(
        default=False,
        description="Whether the NPC will retry this step"
    )
    retry_delay_minutes: int = Field(
        default=0,
        ge=0,
        description="How long before retrying"
    )

    note: str | None = Field(
        default=None,
        description="Additional context about what happened"
    )
