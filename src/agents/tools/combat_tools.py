"""Combat tool definitions for LLM function calling.

These tools allow the Combat Resolver LLM to manage combat encounters,
apply damage, and track combat state.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from src.agents.tools.gm_tools import ToolDefinition, ToolParameter


# Roll Initiative Tool
ROLL_INITIATIVE_TOOL = ToolDefinition(
    name="roll_initiative",
    description=(
        "Roll initiative for all combatants at the start of combat. "
        "Determines turn order for the encounter."
    ),
    parameters=[
        ToolParameter(
            name="combatant_ids",
            param_type="array",
            description="Entity IDs of all combatants participating in combat",
        ),
    ],
)


# Resolve Attack Tool
RESOLVE_ATTACK_TOOL = ToolDefinition(
    name="resolve_attack",
    description=(
        "Resolve an attack action from one combatant to another. "
        "Rolls attack and damage if hit."
    ),
    parameters=[
        ToolParameter(
            name="attacker_id",
            param_type="integer",
            description="Entity ID of the attacker",
        ),
        ToolParameter(
            name="target_id",
            param_type="integer",
            description="Entity ID of the target",
        ),
        ToolParameter(
            name="attack_type",
            param_type="string",
            description="Type of attack",
            enum=["melee", "ranged", "spell"],
            required=False,
            default="melee",
        ),
        ToolParameter(
            name="advantage",
            param_type="string",
            description="Attack advantage state",
            enum=["normal", "advantage", "disadvantage"],
            required=False,
            default="normal",
        ),
    ],
)


# Apply Damage Tool
APPLY_DAMAGE_TOOL = ToolDefinition(
    name="apply_damage",
    description=(
        "Apply damage to a combatant. Updates HP and may trigger death saves."
    ),
    parameters=[
        ToolParameter(
            name="target_id",
            param_type="integer",
            description="Entity ID of the target taking damage",
        ),
        ToolParameter(
            name="damage",
            param_type="integer",
            description="Amount of damage to apply",
        ),
        ToolParameter(
            name="damage_type",
            param_type="string",
            description="Type of damage (e.g., 'slashing', 'fire', 'necrotic')",
            required=False,
            default="untyped",
        ),
        ToolParameter(
            name="source_id",
            param_type="integer",
            description="Entity ID of damage source (for tracking)",
            required=False,
        ),
    ],
)


# Apply Healing Tool
APPLY_HEALING_TOOL = ToolDefinition(
    name="apply_healing",
    description=(
        "Apply healing to a combatant. Restores HP up to maximum."
    ),
    parameters=[
        ToolParameter(
            name="target_id",
            param_type="integer",
            description="Entity ID of the target being healed",
        ),
        ToolParameter(
            name="amount",
            param_type="integer",
            description="Amount of HP to restore",
        ),
        ToolParameter(
            name="source",
            param_type="string",
            description="Source of healing (e.g., 'potion', 'spell', 'rest')",
            required=False,
        ),
    ],
)


# Apply Status Effect Tool
APPLY_STATUS_TOOL = ToolDefinition(
    name="apply_status",
    description=(
        "Apply a status effect to a combatant. Effects may last multiple rounds."
    ),
    parameters=[
        ToolParameter(
            name="target_id",
            param_type="integer",
            description="Entity ID of the target",
        ),
        ToolParameter(
            name="status",
            param_type="string",
            description="Status effect to apply",
            enum=["stunned", "poisoned", "frightened", "prone", "restrained", "blinded", "deafened"],
        ),
        ToolParameter(
            name="duration_rounds",
            param_type="integer",
            description="How many rounds the effect lasts",
            required=False,
            default=1,
        ),
        ToolParameter(
            name="source_id",
            param_type="integer",
            description="Entity ID of effect source",
            required=False,
        ),
    ],
)


# End Combat Tool
END_COMBAT_TOOL = ToolDefinition(
    name="end_combat",
    description=(
        "End the current combat encounter. Awards XP/loot on victory."
    ),
    parameters=[
        ToolParameter(
            name="outcome",
            param_type="string",
            description="How combat ended",
            enum=["victory", "defeat", "fled", "negotiated"],
        ),
        ToolParameter(
            name="loot_items",
            param_type="array",
            description="Item keys to add to player inventory on victory",
            required=False,
        ),
        ToolParameter(
            name="xp_awarded",
            param_type="integer",
            description="Experience points to award on victory",
            required=False,
            default=0,
        ),
    ],
)


# Advance Turn Tool
ADVANCE_TURN_TOOL = ToolDefinition(
    name="advance_turn",
    description=(
        "Advance to the next combatant's turn. Handles end-of-round effects."
    ),
    parameters=[],
)


# All combat tools
COMBAT_TOOLS = [
    ROLL_INITIATIVE_TOOL,
    RESOLVE_ATTACK_TOOL,
    APPLY_DAMAGE_TOOL,
    APPLY_HEALING_TOOL,
    APPLY_STATUS_TOOL,
    END_COMBAT_TOOL,
    ADVANCE_TURN_TOOL,
]
