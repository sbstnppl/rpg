"""GM tool definitions for LLM function calling.

These tools allow the Game Master LLM to invoke dice rolls and query/update
NPC attitudes during narration.
"""

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class ToolParameter:
    """Definition of a tool parameter."""

    name: str
    param_type: Literal["string", "integer", "number", "boolean", "array"]
    description: str
    required: bool = True
    enum: list[str] | None = None
    default: Any = None

    def to_json_schema(self) -> dict[str, Any]:
        """Convert to JSON Schema property definition."""
        schema: dict[str, Any] = {
            "type": self.param_type,
            "description": self.description,
        }
        if self.enum:
            schema["enum"] = self.enum
        if self.default is not None:
            schema["default"] = self.default
        return schema


@dataclass
class ToolDefinition:
    """Definition of a tool for LLM function calling."""

    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)

    def to_json_schema(self) -> dict[str, Any]:
        """Convert to JSON Schema for tool input validation."""
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = param.to_json_schema()
            if param.required:
                required.append(param.name)

        schema: dict[str, Any] = {
            "type": "object",
            "properties": properties,
        }
        if required:
            schema["required"] = required

        return schema

    def to_anthropic_format(self) -> dict[str, Any]:
        """Convert to Anthropic tool format for API calls."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.to_json_schema(),
        }


# Skill Check Tool
SKILL_CHECK_TOOL = ToolDefinition(
    name="skill_check",
    description=(
        "Roll a skill check against a difficulty class (DC). Use this when the player "
        "attempts an action that requires a roll, like picking a lock, persuading an NPC, "
        "or climbing a wall."
    ),
    parameters=[
        ToolParameter(
            name="dc",
            param_type="integer",
            description="Difficulty Class (5=trivial, 10=easy, 15=moderate, 20=hard, 25=very hard)",
        ),
        ToolParameter(
            name="skill_name",
            param_type="string",
            description="Name of the skill being tested (e.g., 'stealth', 'persuasion', 'athletics')",
        ),
        ToolParameter(
            name="attribute_modifier",
            param_type="integer",
            description="Modifier from relevant attribute (typically -5 to +5)",
            required=False,
            default=0,
        ),
        ToolParameter(
            name="advantage",
            param_type="string",
            description="Roll with advantage, disadvantage, or normal",
            required=False,
            enum=["normal", "advantage", "disadvantage"],
            default="normal",
        ),
    ],
)


# Attack Roll Tool
ATTACK_ROLL_TOOL = ToolDefinition(
    name="attack_roll",
    description=(
        "Roll an attack against a target's Armor Class. Returns whether the attack hits "
        "and if it was a critical hit."
    ),
    parameters=[
        ToolParameter(
            name="target_ac",
            param_type="integer",
            description="Target's Armor Class (typically 10-20)",
        ),
        ToolParameter(
            name="attack_bonus",
            param_type="integer",
            description="Attacker's attack bonus",
            required=False,
            default=0,
        ),
        ToolParameter(
            name="advantage",
            param_type="string",
            description="Roll with advantage, disadvantage, or normal",
            required=False,
            enum=["normal", "advantage", "disadvantage"],
            default="normal",
        ),
    ],
)


# Roll Damage Tool
ROLL_DAMAGE_TOOL = ToolDefinition(
    name="roll_damage",
    description="Roll damage dice after a successful attack.",
    parameters=[
        ToolParameter(
            name="damage_dice",
            param_type="string",
            description="Damage dice notation (e.g., '1d8', '2d6', '1d4+3')",
        ),
        ToolParameter(
            name="damage_type",
            param_type="string",
            description="Type of damage (slashing, piercing, bludgeoning, fire, cold, etc.)",
            required=False,
            default="untyped",
        ),
        ToolParameter(
            name="bonus",
            param_type="integer",
            description="Flat damage bonus to add",
            required=False,
            default=0,
        ),
        ToolParameter(
            name="is_critical",
            param_type="boolean",
            description="Whether this is critical hit damage (doubles dice)",
            required=False,
            default=False,
        ),
    ],
)


# Get NPC Attitude Tool
GET_NPC_ATTITUDE_TOOL = ToolDefinition(
    name="get_npc_attitude",
    description=(
        "Query an NPC's attitude toward another entity. Returns trust, liking, respect, "
        "and other relationship dimensions."
    ),
    parameters=[
        ToolParameter(
            name="from_entity",
            param_type="string",
            description="Entity key of the NPC whose attitude to check",
        ),
        ToolParameter(
            name="to_entity",
            param_type="string",
            description="Entity key of the entity they have attitude toward",
        ),
    ],
)


# Update NPC Attitude Tool
UPDATE_NPC_ATTITUDE_TOOL = ToolDefinition(
    name="update_npc_attitude",
    description=(
        "Modify an NPC's attitude toward another entity. Use this when player actions "
        "should affect how an NPC feels about them."
    ),
    parameters=[
        ToolParameter(
            name="from_entity",
            param_type="string",
            description="Entity key of the NPC whose attitude to update",
        ),
        ToolParameter(
            name="to_entity",
            param_type="string",
            description="Entity key of the entity they have attitude toward",
        ),
        ToolParameter(
            name="dimension",
            param_type="string",
            description="Which attitude dimension to change",
            enum=["trust", "liking", "respect", "romantic_interest", "familiarity", "fear"],
        ),
        ToolParameter(
            name="delta",
            param_type="integer",
            description="Amount to change (positive or negative, typically -20 to +20)",
        ),
        ToolParameter(
            name="reason",
            param_type="string",
            description="Why this attitude change is happening",
        ),
    ],
)


# Satisfy Need Tool
SATISFY_NEED_TOOL = ToolDefinition(
    name="satisfy_need",
    description=(
        "Satisfy a character need when they perform an action that addresses it "
        "(eating, sleeping, bathing, socializing, etc.). Use the action_type to "
        "estimate the satisfaction amount, which will be adjusted by character "
        "preferences and traits automatically."
    ),
    parameters=[
        ToolParameter(
            name="entity_key",
            param_type="string",
            description="Entity key of the character performing the action (e.g., 'player', 'npc_innkeeper')",
        ),
        ToolParameter(
            name="need_name",
            param_type="string",
            description="Which need is being satisfied",
            enum=[
                "hunger",
                "energy",
                "hygiene",
                "comfort",
                "wellness",
                "social_connection",
                "morale",
                "sense_of_purpose",
                "intimacy",
            ],
        ),
        ToolParameter(
            name="action_type",
            param_type="string",
            description=(
                "Type of action: hunger (snack/light_meal/full_meal/feast), "
                "energy (quick_nap/short_rest/full_sleep), "
                "hygiene (quick_wash/partial_bath/full_bath), "
                "social (chat/conversation/group_activity/bonding), "
                "comfort (change_clothes/shelter/luxury), "
                "wellness (minor_remedy/medicine/treatment), "
                "morale (minor_victory/achievement/major_success/setback), "
                "purpose (accept_quest/progress/complete_quest), "
                "intimacy (flirtation/affection/intimate_encounter)"
            ),
        ),
        ToolParameter(
            name="quality",
            param_type="string",
            description="Quality of the action or item (affects satisfaction amount)",
            required=False,
            enum=["poor", "basic", "good", "excellent", "exceptional"],
            default="basic",
        ),
        ToolParameter(
            name="base_amount",
            param_type="integer",
            description="Optional override for base satisfaction amount (if not provided, estimated from action_type)",
            required=False,
        ),
    ],
)


# Check Route Tool
CHECK_ROUTE_TOOL = ToolDefinition(
    name="check_route",
    description=(
        "Check the optimal route and travel time between two known zones. Use this when "
        "the player asks how to get somewhere or how long travel will take. Returns the "
        "path, travel time, and any hazards along the way."
    ),
    parameters=[
        ToolParameter(
            name="from_zone",
            param_type="string",
            description="Zone key where the journey starts (current zone if not specified)",
            required=False,
        ),
        ToolParameter(
            name="to_zone",
            param_type="string",
            description="Zone key of the destination",
        ),
        ToolParameter(
            name="transport_mode",
            param_type="string",
            description="How the player is traveling",
            required=False,
            enum=["walking", "mounted", "swimming", "climbing"],
            default="walking",
        ),
    ],
)


# Start Travel Tool
START_TRAVEL_TOOL = ToolDefinition(
    name="start_travel",
    description=(
        "Begin a journey to a destination zone. This initiates simulated travel where the "
        "player will progress through zones with encounters, weather, and skill checks. "
        "Use this when the player wants to travel to a known distant location."
    ),
    parameters=[
        ToolParameter(
            name="to_zone",
            param_type="string",
            description="Zone key of the destination",
        ),
        ToolParameter(
            name="transport_mode",
            param_type="string",
            description="How the player is traveling",
            required=False,
            enum=["walking", "mounted", "swimming", "climbing"],
            default="walking",
        ),
        ToolParameter(
            name="prefer_roads",
            param_type="boolean",
            description="Whether to prefer road routes even if slower",
            required=False,
            default=False,
        ),
    ],
)


# Move to Adjacent Zone Tool
MOVE_TO_ZONE_TOOL = ToolDefinition(
    name="move_to_zone",
    description=(
        "Move the player to an adjacent zone. Use this for immediate short-distance "
        "movement to a directly connected zone, not for long journeys. For distant "
        "destinations, use start_travel instead."
    ),
    parameters=[
        ToolParameter(
            name="zone_key",
            param_type="string",
            description="Zone key to move to (must be adjacent to current zone)",
        ),
        ToolParameter(
            name="transport_mode",
            param_type="string",
            description="How the player is moving",
            required=False,
            enum=["walking", "mounted", "swimming", "climbing"],
            default="walking",
        ),
    ],
)


# Check Terrain Accessibility Tool
CHECK_TERRAIN_TOOL = ToolDefinition(
    name="check_terrain",
    description=(
        "Check if terrain is accessible and what skills are required. Use before "
        "attempting to enter hazardous terrain like lakes (swimming), cliffs (climbing), "
        "or other skill-requiring areas."
    ),
    parameters=[
        ToolParameter(
            name="zone_key",
            param_type="string",
            description="Zone key to check accessibility for",
        ),
        ToolParameter(
            name="transport_mode",
            param_type="string",
            description="How the player intends to traverse it",
            required=False,
            enum=["walking", "mounted", "swimming", "climbing"],
            default="walking",
        ),
    ],
)


# Discover Zone Tool
DISCOVER_ZONE_TOOL = ToolDefinition(
    name="discover_zone",
    description=(
        "Mark a zone as discovered by the player. Use when an NPC tells the player "
        "about a location, or when the player finds a map or gains knowledge of an area."
    ),
    parameters=[
        ToolParameter(
            name="zone_key",
            param_type="string",
            description="Zone key to discover",
        ),
        ToolParameter(
            name="discovery_method",
            param_type="string",
            description="How the zone was discovered",
            enum=["told_by_npc", "map_viewed", "visible_from", "visited"],
        ),
        ToolParameter(
            name="source_entity",
            param_type="string",
            description="Entity key of NPC who told about the zone (if applicable)",
            required=False,
        ),
    ],
)


# Discover Location Tool
DISCOVER_LOCATION_TOOL = ToolDefinition(
    name="discover_location",
    description=(
        "Mark a location as discovered by the player. Use when the player learns "
        "about a specific place like a building, dungeon, or point of interest."
    ),
    parameters=[
        ToolParameter(
            name="location_key",
            param_type="string",
            description="Location key to discover",
        ),
        ToolParameter(
            name="discovery_method",
            param_type="string",
            description="How the location was discovered",
            enum=["told_by_npc", "map_viewed", "visible_from", "visited"],
        ),
        ToolParameter(
            name="source_entity",
            param_type="string",
            description="Entity key of NPC who told about the location (if applicable)",
            required=False,
        ),
    ],
)


# All GM tools
GM_TOOLS = [
    SKILL_CHECK_TOOL,
    ATTACK_ROLL_TOOL,
    ROLL_DAMAGE_TOOL,
    GET_NPC_ATTITUDE_TOOL,
    UPDATE_NPC_ATTITUDE_TOOL,
    SATISFY_NEED_TOOL,
    CHECK_ROUTE_TOOL,
    START_TRAVEL_TOOL,
    MOVE_TO_ZONE_TOOL,
    CHECK_TERRAIN_TOOL,
    DISCOVER_ZONE_TOOL,
    DISCOVER_LOCATION_TOOL,
]
