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
        "or an NPC attempts an action that requires a roll, like picking a lock, "
        "persuading someone, or climbing a wall. The system will automatically look up "
        "the character's skill proficiency and relevant attribute modifier."
    ),
    parameters=[
        ToolParameter(
            name="entity_key",
            param_type="string",
            description="Entity key of who is making the check (e.g., 'player', 'npc_guard')",
        ),
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
            name="description",
            param_type="string",
            description="Brief description of the action being attempted (shown to player)",
            required=False,
        ),
        ToolParameter(
            name="attribute_key",
            param_type="string",
            description="Override the default governing attribute (e.g., use 'strength' for a brute-force lockpick)",
            required=False,
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
        "Update a character need when they perform an action. Use POSITIVE actions "
        "(eating, sleeping, bathing) to satisfy needs, or NEGATIVE actions "
        "(get_dirty, rejection, get_cold) when adverse events occur. The action_type "
        "determines whether the need increases or decreases, and character preferences "
        "and traits automatically adjust the amount."
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
                "thirst",
                "stamina",
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
                "Type of action. Positive: hunger (snack/light_meal/full_meal/feast), "
                "stamina (quick_rest/short_rest/long_rest/full_rest/sleep), "
                "hygiene (quick_wash/partial_bath/full_bath), "
                "social (chat/conversation/group_activity/bonding), "
                "comfort (change_clothes/shelter/luxury), "
                "wellness (minor_remedy/medicine/treatment), "
                "morale (minor_victory/achievement/major_success), "
                "purpose (accept_quest/progress/complete_quest), "
                "intimacy (flirtation/affection/intimate_encounter). "
                "Negative: hygiene (sweat/get_dirty/mud/blood/filth), "
                "comfort (get_wet/get_cold/freezing/pain), "
                "social (snub/argument/rejection/betrayal/isolation), "
                "morale (setback/failure/embarrassment/tragedy), "
                "intimacy (rebuff/romantic_rejection/heartbreak)"
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


# Mark Need Communicated Tool - for signal-based needs narration
MARK_NEED_COMMUNICATED_TOOL = ToolDefinition(
    name="mark_need_communicated",
    description=(
        "Call this AFTER narrating a character need (hunger, tiredness, etc.) to prevent "
        "repetitive mentions. When you describe how a character feels hungry, tired, or "
        "otherwise affected by a need, use this tool to record that communication. The "
        "system will then avoid alerting you about that same need until the state changes "
        "or significant time has passed."
    ),
    parameters=[
        ToolParameter(
            name="entity_key",
            param_type="string",
            description="Entity key of the character whose need was narrated (e.g., 'player', 'npc_guard')",
        ),
        ToolParameter(
            name="need_name",
            param_type="string",
            description="Which need was communicated in the narration",
            enum=[
                "hunger",
                "thirst",
                "stamina",
                "sleep_pressure",
                "hygiene",
                "comfort",
                "wellness",
                "social_connection",
                "morale",
                "sense_of_purpose",
                "intimacy",
            ],
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


# Apply Stimulus Tool
APPLY_STIMULUS_TOOL = ToolDefinition(
    name="apply_stimulus",
    description=(
        "Apply a stimulus effect to a character's needs when describing scenes that "
        "would trigger cravings or emotional reactions. Use when the scene contains "
        "something that would naturally make a character crave something: seeing food "
        "when hungry, seeing a comfortable bed when tired, seeing something that "
        "reminds them of a painful memory. The stimulus creates a craving boost that "
        "makes the need feel more urgent than its actual physiological level."
    ),
    parameters=[
        ToolParameter(
            name="entity_key",
            param_type="string",
            description="Entity key of the character affected (e.g., 'player', 'npc_guard')",
        ),
        ToolParameter(
            name="stimulus_type",
            param_type="string",
            description="What kind of stimulus is affecting the character",
            enum=[
                "food_sight",  # Seeing/smelling food
                "drink_sight",  # Seeing drinks/water
                "rest_opportunity",  # Seeing bed/rest area
                "social_atmosphere",  # Warm social environment
                "intimacy_trigger",  # Romantic/attractive presence
                "memory_trigger",  # Something triggering a memory
            ],
        ),
        ToolParameter(
            name="stimulus_description",
            param_type="string",
            description="Brief description of the stimulus (e.g., 'a plate of fresh roast chicken', 'a wide-brimmed straw hat')",
        ),
        ToolParameter(
            name="intensity",
            param_type="string",
            description="How strongly this affects the character",
            required=False,
            enum=["mild", "moderate", "strong"],
            default="moderate",
        ),
        ToolParameter(
            name="memory_emotion",
            param_type="string",
            description="For memory triggers: the emotion evoked (grief, nostalgia, fear, joy, etc.)",
            required=False,
        ),
    ],
)


# View Map Tool
VIEW_MAP_TOOL = ToolDefinition(
    name="view_map",
    description=(
        "Have a character examine a map item to discover new locations and zones. "
        "Use when the player examines, studies, or consults a map. Returns the zones "
        "and locations discovered from viewing the map."
    ),
    parameters=[
        ToolParameter(
            name="item_key",
            param_type="string",
            description="The key of the map item to examine (e.g., 'regional_map', 'treasure_map')",
        ),
        ToolParameter(
            name="viewer_entity_key",
            param_type="string",
            description="Entity key of who is viewing the map (default: 'player')",
            required=False,
            default="player",
        ),
    ],
)


# Acquire Item Tool
ACQUIRE_ITEM_TOOL = ToolDefinition(
    name="acquire_item",
    description=(
        "Give an item to an entity (player or NPC). Validates slot availability and "
        "weight limits before acquisition. Use this when a character picks up, receives, "
        "or otherwise acquires an item. The tool will return success/failure with a reason "
        "that you should incorporate into the narrative."
    ),
    parameters=[
        ToolParameter(
            name="entity_key",
            param_type="string",
            description="Entity key of who acquires the item (e.g., 'player', 'npc_merchant')",
        ),
        ToolParameter(
            name="display_name",
            param_type="string",
            description="Display name of the item (e.g., 'Iron Sword', 'Bundle of Branches')",
        ),
        ToolParameter(
            name="item_type",
            param_type="string",
            description="Type of item",
            enum=["weapon", "armor", "clothing", "consumable", "container", "misc"],
        ),
        ToolParameter(
            name="item_key",
            param_type="string",
            description="Unique key for existing item, or leave empty for auto-generated key",
            required=False,
        ),
        ToolParameter(
            name="slot",
            param_type="string",
            description="Specific body slot to place item (auto-assigned if not specified)",
            required=False,
        ),
        ToolParameter(
            name="item_size",
            param_type="string",
            description="Size hint for auto-slot assignment",
            required=False,
            enum=["small", "medium", "large"],
            default="small",
        ),
        ToolParameter(
            name="description",
            param_type="string",
            description="Item description",
            required=False,
        ),
        ToolParameter(
            name="weight",
            param_type="number",
            description="Weight in pounds (for encumbrance checking)",
            required=False,
            default=0,
        ),
        ToolParameter(
            name="quantity",
            param_type="integer",
            description="Number of items (for stackable items)",
            required=False,
            default=1,
        ),
    ],
)


# Drop Item Tool
DROP_ITEM_TOOL = ToolDefinition(
    name="drop_item",
    description=(
        "Have an entity drop or put down an item they are carrying. Use when a character "
        "sets something down, discards an item, or gives something away."
    ),
    parameters=[
        ToolParameter(
            name="entity_key",
            param_type="string",
            description="Entity key of who is dropping the item",
        ),
        ToolParameter(
            name="item_key",
            param_type="string",
            description="Key of the item to drop",
        ),
        ToolParameter(
            name="transfer_to",
            param_type="string",
            description="Entity key to transfer item to (for giving items), leave empty to drop on ground",
            required=False,
        ),
    ],
)


# =============================================================================
# State Management Tools (replace STATE block parsing)
# =============================================================================

ADVANCE_TIME_TOOL = ToolDefinition(
    name="advance_time",
    description=(
        "Advance game time. Call this to indicate time passing during the scene. "
        "This REPLACES putting time in the STATE block - use this tool instead."
    ),
    parameters=[
        ToolParameter(
            name="minutes",
            param_type="integer",
            description="Minutes to advance (1-480). Typical: 1-10 for dialogue, 15-60 for activities",
        ),
        ToolParameter(
            name="reason",
            param_type="string",
            description="Brief reason for time passing (e.g., 'conversation', 'walking to forge')",
            required=False,
        ),
    ],
)


ENTITY_MOVE_TOOL = ToolDefinition(
    name="entity_move",
    description=(
        "Move an entity (player or NPC) to a new location. Use this when anyone physically "
        "moves from one area to another. For the player, this also updates game state tracking. "
        "This REPLACES putting location_change in the STATE block."
    ),
    parameters=[
        ToolParameter(
            name="entity_key",
            param_type="string",
            description="Who is moving (e.g., 'player', 'npc_blacksmith', 'npc_guard')",
        ),
        ToolParameter(
            name="location_key",
            param_type="string",
            description="Destination location key (e.g., 'village_square', 'forge_interior', 'inn_common_room')",
        ),
        ToolParameter(
            name="create_if_missing",
            param_type="boolean",
            description="Create the location if it doesn't exist yet",
            required=False,
            default=True,
        ),
    ],
)


START_COMBAT_TOOL = ToolDefinition(
    name="start_combat",
    description=(
        "Initiate a combat encounter. Call this when combat begins between the player "
        "and enemies. This REPLACES setting combat_initiated in the STATE block."
    ),
    parameters=[
        ToolParameter(
            name="enemy_keys",
            param_type="array",
            description="Entity keys of enemies entering combat (e.g., ['npc_bandit_1', 'npc_bandit_2'])",
        ),
        ToolParameter(
            name="surprise",
            param_type="string",
            description="Who (if anyone) is surprised at combat start",
            required=False,
            enum=["none", "enemies", "player"],
            default="none",
        ),
        ToolParameter(
            name="reason",
            param_type="string",
            description="How/why combat started (e.g., 'ambush', 'provoked attack', 'caught stealing')",
        ),
    ],
)


END_COMBAT_TOOL = ToolDefinition(
    name="end_combat",
    description="End the current combat encounter and record the outcome.",
    parameters=[
        ToolParameter(
            name="outcome",
            param_type="string",
            description="How combat ended",
            enum=["victory", "defeat", "fled", "negotiated"],
        ),
        ToolParameter(
            name="summary",
            param_type="string",
            description="Brief summary of combat resolution",
            required=False,
        ),
    ],
)


# === Quest Management Tools ===

ASSIGN_QUEST_TOOL = ToolDefinition(
    name="assign_quest",
    description=(
        "Create and assign a new quest to the player. Use when an NPC gives the player "
        "a quest or mission, or when the player discovers a quest objective."
    ),
    parameters=[
        ToolParameter(
            name="quest_key",
            param_type="string",
            description="Unique identifier for this quest (e.g., 'find_lost_ring', 'rescue_merchant')",
        ),
        ToolParameter(
            name="title",
            param_type="string",
            description="Display title of the quest (e.g., 'The Lost Ring', 'Rescue the Merchant')",
        ),
        ToolParameter(
            name="description",
            param_type="string",
            description="Full description of the quest objective and context",
        ),
        ToolParameter(
            name="giver_entity_key",
            param_type="string",
            description="Entity key of the NPC who gave this quest (if applicable)",
            required=False,
        ),
        ToolParameter(
            name="rewards",
            param_type="string",
            description="Description of promised rewards (e.g., '50 gold coins', 'a family heirloom')",
            required=False,
        ),
    ],
)


UPDATE_QUEST_TOOL = ToolDefinition(
    name="update_quest",
    description=(
        "Update progress on an existing quest. Use when the player completes an objective, "
        "discovers new information, or advances to the next stage."
    ),
    parameters=[
        ToolParameter(
            name="quest_key",
            param_type="string",
            description="Key of the quest to update",
        ),
        ToolParameter(
            name="new_stage",
            param_type="integer",
            description="New stage number (0-indexed)",
            required=False,
        ),
        ToolParameter(
            name="stage_name",
            param_type="string",
            description="Name of the new stage (e.g., 'Find the witness', 'Return to the village')",
            required=False,
        ),
        ToolParameter(
            name="stage_description",
            param_type="string",
            description="Description of what to do in this stage",
            required=False,
        ),
        ToolParameter(
            name="notes",
            param_type="string",
            description="Additional notes about progress or discoveries",
            required=False,
        ),
    ],
)


COMPLETE_QUEST_TOOL = ToolDefinition(
    name="complete_quest",
    description=(
        "Mark a quest as completed or failed. Use when the player finishes a quest "
        "objective successfully or when a quest becomes impossible to complete."
    ),
    parameters=[
        ToolParameter(
            name="quest_key",
            param_type="string",
            description="Key of the quest to complete",
        ),
        ToolParameter(
            name="outcome",
            param_type="string",
            description="How the quest ended",
            enum=["completed", "failed"],
        ),
        ToolParameter(
            name="outcome_notes",
            param_type="string",
            description="Description of how the quest was resolved",
            required=False,
        ),
    ],
)


# === World Fact Tools ===

RECORD_FACT_TOOL = ToolDefinition(
    name="record_fact",
    description=(
        "Record a fact about the world that the player has learned or discovered. "
        "Use the Subject-Predicate-Value pattern. This helps track world knowledge "
        "for narrative consistency. Examples: 'npc_marta has_job innkeeper', "
        "'location_forge is_closed_on sundays', 'player knows_secret blacksmith_past'."
    ),
    parameters=[
        ToolParameter(
            name="subject_type",
            param_type="string",
            description="Type of thing the fact is about",
            enum=["entity", "location", "world", "item", "group"],
        ),
        ToolParameter(
            name="subject_key",
            param_type="string",
            description="Key of the subject (e.g., 'npc_marta', 'village_square', 'iron_sword')",
        ),
        ToolParameter(
            name="predicate",
            param_type="string",
            description="What aspect this fact describes (e.g., 'has_job', 'is_allergic_to', 'was_born_in')",
        ),
        ToolParameter(
            name="value",
            param_type="string",
            description="The value of the fact (e.g., 'innkeeper', 'shellfish', 'the capital city')",
        ),
        ToolParameter(
            name="is_secret",
            param_type="boolean",
            description="Whether this is a secret the player should not know yet",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="confidence",
            param_type="integer",
            description="Confidence level 0-100 (how certain this fact is)",
            required=False,
            default=80,
        ),
    ],
)


# === NPC Scene Management Tools ===

INTRODUCE_NPC_TOOL = ToolDefinition(
    name="introduce_npc",
    description=(
        "Introduce a new NPC into the scene. Use when a new character appears for the "
        "first time or when an existing NPC enters the current location. This creates "
        "or updates the NPC record and marks them as present at the current location."
    ),
    parameters=[
        ToolParameter(
            name="entity_key",
            param_type="string",
            description="Unique key for this NPC (e.g., 'npc_blacksmith_tom', 'npc_guard_1')",
        ),
        ToolParameter(
            name="display_name",
            param_type="string",
            description="The NPC's name as displayed (e.g., 'Tom the Blacksmith', 'Village Guard')",
        ),
        ToolParameter(
            name="description",
            param_type="string",
            description="Physical description and notable traits",
        ),
        ToolParameter(
            name="location_key",
            param_type="string",
            description="Location where the NPC appears",
        ),
        ToolParameter(
            name="occupation",
            param_type="string",
            description="NPC's job or role (e.g., 'blacksmith', 'guard', 'merchant')",
            required=False,
        ),
        ToolParameter(
            name="initial_attitude",
            param_type="string",
            description="Starting attitude toward the player",
            required=False,
            enum=["hostile", "unfriendly", "neutral", "friendly", "warm"],
            default="neutral",
        ),
    ],
)


NPC_LEAVES_TOOL = ToolDefinition(
    name="npc_leaves",
    description=(
        "Have an NPC leave the current scene. Use when an NPC walks away, exits a "
        "building, or otherwise departs from the player's location."
    ),
    parameters=[
        ToolParameter(
            name="entity_key",
            param_type="string",
            description="Entity key of the NPC leaving",
        ),
        ToolParameter(
            name="destination",
            param_type="string",
            description="Where the NPC is going (location key or description)",
            required=False,
        ),
        ToolParameter(
            name="reason",
            param_type="string",
            description="Why the NPC is leaving (for narrative context)",
            required=False,
        ),
    ],
)


# World Spawning Tools

SPAWN_STORAGE_TOOL = ToolDefinition(
    name="spawn_storage",
    description=(
        "Create a storage surface or container at the current location. "
        "Use when entering a new interior location to establish furniture like tables, "
        "shelves, chests, or counters. These become visible in /nearby and are required "
        "before placing items on them with spawn_item."
    ),
    parameters=[
        ToolParameter(
            name="container_type",
            param_type="string",
            description="Type of storage surface",
            enum=["table", "shelf", "chest", "counter", "barrel", "crate", "cupboard", "floor", "ground"],
        ),
        ToolParameter(
            name="description",
            param_type="string",
            description="Description of the storage, e.g. 'A sturdy oak table'",
            required=False,
        ),
        ToolParameter(
            name="storage_key",
            param_type="string",
            description="Unique key for this storage (auto-generated if not provided)",
            required=False,
        ),
        ToolParameter(
            name="is_fixed",
            param_type="boolean",
            description="Whether the storage cannot be moved (default: true for furniture)",
            required=False,
            default=True,
        ),
        ToolParameter(
            name="capacity",
            param_type="integer",
            description="Maximum number of items this can hold (default: 20)",
            required=False,
            default=20,
        ),
    ],
)


SPAWN_ITEM_TOOL = ToolDefinition(
    name="spawn_item",
    description=(
        "Create an item at the current location. Use this when describing discoverable items "
        "that the player could potentially interact with (pick up, use, eat, etc.). Items "
        "spawned this way appear in /nearby. Do NOT use for ambient decorations that can't be "
        "interacted with. The storage surface must exist first (use spawn_storage if needed)."
    ),
    parameters=[
        ToolParameter(
            name="display_name",
            param_type="string",
            description="Item name, e.g. 'Half-loaf of Brown Bread', 'Rusty Sword'",
        ),
        ToolParameter(
            name="description",
            param_type="string",
            description="Brief item description for when examined",
        ),
        ToolParameter(
            name="item_type",
            param_type="string",
            description="Type of item",
            enum=["consumable", "container", "misc", "tool", "weapon", "armor", "clothing"],
        ),
        ToolParameter(
            name="surface",
            param_type="string",
            description="Where to place: 'table', 'shelf', 'floor', 'counter', etc. Must be spawned first.",
            required=False,
            default="floor",
        ),
        ToolParameter(
            name="item_key",
            param_type="string",
            description="Unique key for this item (auto-generated if not provided)",
            required=False,
        ),
        ToolParameter(
            name="quantity",
            param_type="integer",
            description="Number of items (for stackable items like coins, arrows)",
            required=False,
            default=1,
        ),
        ToolParameter(
            name="weight",
            param_type="number",
            description="Weight in pounds (for encumbrance)",
            required=False,
            default=0.5,
        ),
    ],
)


# All GM tools
GM_TOOLS = [
    # Dice and checks
    SKILL_CHECK_TOOL,
    ATTACK_ROLL_TOOL,
    ROLL_DAMAGE_TOOL,
    # Relationships
    GET_NPC_ATTITUDE_TOOL,
    UPDATE_NPC_ATTITUDE_TOOL,
    # Needs
    SATISFY_NEED_TOOL,
    APPLY_STIMULUS_TOOL,
    MARK_NEED_COMMUNICATED_TOOL,
    # Navigation
    CHECK_ROUTE_TOOL,
    START_TRAVEL_TOOL,
    MOVE_TO_ZONE_TOOL,
    CHECK_TERRAIN_TOOL,
    DISCOVER_ZONE_TOOL,
    DISCOVER_LOCATION_TOOL,
    VIEW_MAP_TOOL,
    # Items
    ACQUIRE_ITEM_TOOL,
    DROP_ITEM_TOOL,
    # World spawning
    SPAWN_STORAGE_TOOL,
    SPAWN_ITEM_TOOL,
    # State management (replace STATE block)
    ADVANCE_TIME_TOOL,
    ENTITY_MOVE_TOOL,
    START_COMBAT_TOOL,
    END_COMBAT_TOOL,
    # Quest management
    ASSIGN_QUEST_TOOL,
    UPDATE_QUEST_TOOL,
    COMPLETE_QUEST_TOOL,
    # World facts
    RECORD_FACT_TOOL,
    # NPC scene management
    INTRODUCE_NPC_TOOL,
    NPC_LEAVES_TOOL,
]
