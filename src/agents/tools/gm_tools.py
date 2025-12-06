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


# All GM tools
GM_TOOLS = [
    SKILL_CHECK_TOOL,
    ATTACK_ROLL_TOOL,
    ROLL_DAMAGE_TOOL,
    GET_NPC_ATTITUDE_TOOL,
    UPDATE_NPC_ATTITUDE_TOOL,
]
