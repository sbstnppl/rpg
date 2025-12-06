"""Extraction tool definitions for LLM function calling.

These tools allow the Entity Extractor LLM to create entities, facts, items,
and relationship changes during narrative processing.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from src.agents.tools.gm_tools import ToolDefinition, ToolParameter


# Create Entity Tool
CREATE_ENTITY_TOOL = ToolDefinition(
    name="create_entity",
    description=(
        "Create a new entity (NPC, monster, or animal) that was introduced in the narrative. "
        "Use this when a new character is mentioned for the first time."
    ),
    parameters=[
        ToolParameter(
            name="entity_key",
            param_type="string",
            description="Unique identifier (lowercase, underscores, e.g., 'bartender_bob')",
        ),
        ToolParameter(
            name="display_name",
            param_type="string",
            description="How the character is addressed (e.g., 'Bob the Bartender')",
        ),
        ToolParameter(
            name="entity_type",
            param_type="string",
            description="Type of entity",
            enum=["npc", "monster", "animal"],
        ),
        ToolParameter(
            name="description",
            param_type="string",
            description="Physical description if mentioned",
            required=False,
        ),
        ToolParameter(
            name="current_location",
            param_type="string",
            description="Location key where entity is found",
            required=False,
        ),
        ToolParameter(
            name="current_activity",
            param_type="string",
            description="What the entity is currently doing",
            required=False,
        ),
        ToolParameter(
            name="personality_traits",
            param_type="array",
            description="Observable personality traits",
            required=False,
        ),
    ],
)


# Record Fact Tool
RECORD_FACT_TOOL = ToolDefinition(
    name="record_fact",
    description=(
        "Record a fact about an entity or the world using Subject-Predicate-Value format. "
        "Use this when new information is revealed in the narrative."
    ),
    parameters=[
        ToolParameter(
            name="subject_key",
            param_type="string",
            description="Entity key or topic this fact is about",
        ),
        ToolParameter(
            name="predicate",
            param_type="string",
            description="What aspect (e.g., 'occupation', 'lives_at', 'knows_about', 'fears')",
        ),
        ToolParameter(
            name="value",
            param_type="string",
            description="The actual information",
        ),
        ToolParameter(
            name="category",
            param_type="string",
            description="Category of fact",
            required=False,
            enum=["character", "world", "history", "relationship", "secret"],
        ),
        ToolParameter(
            name="is_secret",
            param_type="boolean",
            description="True if this is GM-only information the player doesn't know",
            required=False,
            default=False,
        ),
    ],
)


# Create Item Tool
CREATE_ITEM_TOOL = ToolDefinition(
    name="create_item",
    description=(
        "Create an item that was introduced or acquired in the narrative. "
        "Use this when a new item appears or is given to someone."
    ),
    parameters=[
        ToolParameter(
            name="item_key",
            param_type="string",
            description="Unique identifier (lowercase, underscores, e.g., 'rusty_sword')",
        ),
        ToolParameter(
            name="display_name",
            param_type="string",
            description="Item name as displayed (e.g., 'Rusty Sword')",
        ),
        ToolParameter(
            name="item_type",
            param_type="string",
            description="Type of item",
            enum=["weapon", "armor", "clothing", "consumable", "container", "tool", "misc"],
        ),
        ToolParameter(
            name="description",
            param_type="string",
            description="Physical description if provided",
            required=False,
        ),
        ToolParameter(
            name="owner_key",
            param_type="string",
            description="Entity key of the owner",
            required=False,
        ),
        ToolParameter(
            name="location_key",
            param_type="string",
            description="Location key if item is at a location (not held by someone)",
            required=False,
        ),
    ],
)


# Update Relationship Tool
UPDATE_RELATIONSHIP_TOOL = ToolDefinition(
    name="update_relationship",
    description=(
        "Record a change in relationship between entities based on narrative events. "
        "Use this when interactions affect how one entity feels about another."
    ),
    parameters=[
        ToolParameter(
            name="from_entity",
            param_type="string",
            description="Entity key whose attitude changed",
        ),
        ToolParameter(
            name="to_entity",
            param_type="string",
            description="Entity key toward whom attitude changed",
        ),
        ToolParameter(
            name="dimension",
            param_type="string",
            description="Which attitude dimension changed",
            enum=["trust", "liking", "respect", "romantic_interest", "fear", "familiarity"],
        ),
        ToolParameter(
            name="delta",
            param_type="integer",
            description="Amount of change (-20 to +20)",
        ),
        ToolParameter(
            name="reason",
            param_type="string",
            description="Brief explanation of why this change occurred",
        ),
    ],
)


# Create Appointment Tool
CREATE_APPOINTMENT_TOOL = ToolDefinition(
    name="create_appointment",
    description=(
        "Create an appointment or commitment made in the narrative. "
        "Use this when characters agree to meet or do something at a specific time."
    ),
    parameters=[
        ToolParameter(
            name="description",
            param_type="string",
            description="What the appointment is for",
        ),
        ToolParameter(
            name="game_day",
            param_type="integer",
            description="Game day number when the appointment is scheduled",
        ),
        ToolParameter(
            name="time_of_day",
            param_type="string",
            description="Time of day (e.g., 'morning', '14:00', 'evening')",
        ),
        ToolParameter(
            name="location_key",
            param_type="string",
            description="Where the appointment will take place",
            required=False,
        ),
        ToolParameter(
            name="participants",
            param_type="array",
            description="Entity keys of participants",
            required=False,
        ),
    ],
)


# All extraction tools
EXTRACTION_TOOLS = [
    CREATE_ENTITY_TOOL,
    RECORD_FACT_TOOL,
    CREATE_ITEM_TOOL,
    UPDATE_RELATIONSHIP_TOOL,
    CREATE_APPOINTMENT_TOOL,
]
