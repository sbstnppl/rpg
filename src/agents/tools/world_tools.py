"""World simulation tool definitions for LLM function calling.

These tools allow the World Simulator LLM to manage time passage,
NPC movements, and background world events.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from src.agents.tools.gm_tools import ToolDefinition, ToolParameter


# Advance Time Tool
ADVANCE_TIME_TOOL = ToolDefinition(
    name="advance_time",
    description=(
        "Advance the game clock. Triggers NPC schedule updates, need decay, "
        "and environmental changes."
    ),
    parameters=[
        ToolParameter(
            name="minutes",
            param_type="integer",
            description="Number of minutes to advance (1-480)",
        ),
        ToolParameter(
            name="reason",
            param_type="string",
            description="Why time is passing (e.g., 'travel', 'rest', 'activity')",
            required=False,
        ),
    ],
)


# Move NPC Tool
MOVE_NPC_TOOL = ToolDefinition(
    name="move_npc",
    description=(
        "Move an NPC to a new location. Updates their current_location."
    ),
    parameters=[
        ToolParameter(
            name="entity_key",
            param_type="string",
            description="Entity key of the NPC to move",
        ),
        ToolParameter(
            name="location_key",
            param_type="string",
            description="Destination location key",
        ),
        ToolParameter(
            name="reason",
            param_type="string",
            description="Why the NPC is moving (e.g., 'schedule', 'need', 'event')",
            required=False,
        ),
    ],
)


# Change Weather Tool
CHANGE_WEATHER_TOOL = ToolDefinition(
    name="change_weather",
    description=(
        "Change the current weather conditions. Affects NPC behavior and activities."
    ),
    parameters=[
        ToolParameter(
            name="weather",
            param_type="string",
            description="New weather condition",
            enum=["clear", "cloudy", "rain", "storm", "snow", "fog", "wind"],
        ),
        ToolParameter(
            name="intensity",
            param_type="string",
            description="Weather intensity",
            enum=["light", "moderate", "heavy"],
            required=False,
            default="moderate",
        ),
    ],
)


# Create World Event Tool
CREATE_WORLD_EVENT_TOOL = ToolDefinition(
    name="create_world_event",
    description=(
        "Create a background world event. Events can affect NPCs, locations, "
        "or the general atmosphere."
    ),
    parameters=[
        ToolParameter(
            name="event_type",
            param_type="string",
            description="Category of event",
            enum=["social", "environmental", "economic", "political", "random"],
        ),
        ToolParameter(
            name="summary",
            param_type="string",
            description="Brief description of what happened",
        ),
        ToolParameter(
            name="location_key",
            param_type="string",
            description="Location where event occurred",
            required=False,
        ),
        ToolParameter(
            name="affected_entities",
            param_type="array",
            description="Entity keys involved in or affected by the event",
            required=False,
        ),
        ToolParameter(
            name="is_public",
            param_type="boolean",
            description="Whether the event is publicly known or hidden",
            required=False,
            default=True,
        ),
    ],
)


# Update NPC Need Tool
UPDATE_NPC_NEED_TOOL = ToolDefinition(
    name="update_npc_need",
    description=(
        "Update an NPC's need level. Use when needs change due to activities."
    ),
    parameters=[
        ToolParameter(
            name="entity_key",
            param_type="string",
            description="Entity key of the NPC",
        ),
        ToolParameter(
            name="need",
            param_type="string",
            description="Which need to update",
            enum=["hunger", "stamina", "sleep_pressure", "hygiene", "comfort", "morale", "wellness"],
        ),
        ToolParameter(
            name="delta",
            param_type="integer",
            description="Change amount (positive = need increases/improves, negative = decreases)",
        ),
        ToolParameter(
            name="reason",
            param_type="string",
            description="Why the need changed",
            required=False,
        ),
    ],
)


# Set Location State Tool
SET_LOCATION_STATE_TOOL = ToolDefinition(
    name="set_location_state",
    description=(
        "Update the state of a location. Affects atmosphere and available interactions."
    ),
    parameters=[
        ToolParameter(
            name="location_key",
            param_type="string",
            description="Location to update",
        ),
        ToolParameter(
            name="crowd_level",
            param_type="string",
            description="How crowded the location is",
            enum=["empty", "sparse", "moderate", "busy", "packed"],
            required=False,
        ),
        ToolParameter(
            name="lighting",
            param_type="string",
            description="Current lighting conditions",
            enum=["dark", "dim", "normal", "bright"],
            required=False,
        ),
        ToolParameter(
            name="atmosphere",
            param_type="string",
            description="General mood/vibe of the location",
            required=False,
        ),
    ],
)


# All world simulation tools
WORLD_TOOLS = [
    ADVANCE_TIME_TOOL,
    MOVE_NPC_TOOL,
    CHANGE_WEATHER_TOOL,
    CREATE_WORLD_EVENT_TOOL,
    UPDATE_NPC_NEED_TOOL,
    SET_LOCATION_STATE_TOOL,
]
