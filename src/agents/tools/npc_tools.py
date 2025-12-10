"""NPC creation and query tools for GM function calling.

These tools allow the Game Master LLM to create NPCs with emergent traits
and query existing NPCs for their current state and reactions.

Philosophy: GM Discovers, Not Prescribes
- GM requests "I need a customer" -> System generates full personality
- GM discovers NPC's traits, preferences, and attractions
- NPCs have emergent behavior based on their generated state
"""

from dataclasses import field

from src.agents.tools.gm_tools import ToolDefinition, ToolParameter


# =============================================================================
# Create NPC Tool
# =============================================================================

CREATE_NPC_TOOL = ToolDefinition(
    name="create_npc",
    description=(
        "Create a new NPC with emergent personality, preferences, and environmental reactions. "
        "Use this when a new character appears in the scene. The system generates full character "
        "data including appearance, background, personality traits, and calculates their reactions "
        "to the current scene (including attraction to player if applicable). "
        "The GM DISCOVERS who the NPC is rather than prescribing it. "
        "Use constraints only when the story absolutely requires specific traits."
    ),
    parameters=[
        ToolParameter(
            name="role",
            param_type="string",
            description=(
                "The NPC's role or occupation. Examples: 'customer', 'shopkeeper', 'guard', "
                "'innkeeper', 'farmer', 'merchant', 'blacksmith', 'healer', 'beggar', 'noble'"
            ),
        ),
        ToolParameter(
            name="location_key",
            param_type="string",
            description="Location key where the NPC appears (e.g., 'general_store', 'town_square')",
        ),
        # Optional constraints - use sparingly
        ToolParameter(
            name="constraint_name",
            param_type="string",
            description="Optional: Specific name if story requires it",
            required=False,
        ),
        ToolParameter(
            name="constraint_gender",
            param_type="string",
            description="Optional: Specific gender if story requires it",
            required=False,
            enum=["male", "female"],
        ),
        ToolParameter(
            name="constraint_age_range",
            param_type="string",
            description="Optional: Age range if story requires it",
            required=False,
            enum=["child", "teen", "young_adult", "middle_aged", "elderly"],
        ),
        ToolParameter(
            name="constraint_occupation",
            param_type="string",
            description="Optional: Specific occupation (different from role) if needed",
            required=False,
        ),
        ToolParameter(
            name="constraint_personality",
            param_type="array",
            description=(
                "Optional: Required personality traits (e.g., ['shy', 'suspicious']). "
                "Use sparingly - let traits emerge naturally!"
            ),
            required=False,
        ),
        ToolParameter(
            name="constraint_hostile",
            param_type="boolean",
            description="Optional: Force NPC to be hostile to player",
            required=False,
        ),
        ToolParameter(
            name="constraint_friendly",
            param_type="boolean",
            description="Optional: Force NPC to be welcoming to player",
            required=False,
        ),
        ToolParameter(
            name="constraint_attracted",
            param_type="boolean",
            description="Optional: Force positive attraction to player (use very sparingly!)",
            required=False,
        ),
    ],
)


# =============================================================================
# Query NPC Tool
# =============================================================================

QUERY_NPC_TOOL = ToolDefinition(
    name="query_npc",
    description=(
        "Query an existing NPC's current state and reactions to the scene. "
        "Use this when the scene changes and you need to know how an NPC would react, "
        "or to refresh your understanding of an NPC's current mood, needs, and behavior. "
        "Returns updated environmental reactions including attraction scores."
    ),
    parameters=[
        ToolParameter(
            name="entity_key",
            param_type="string",
            description="Entity key of the NPC to query (e.g., 'customer_elara')",
        ),
    ],
)


# =============================================================================
# Create Item Tool
# =============================================================================

CREATE_ITEM_TOOL = ToolDefinition(
    name="create_item",
    description=(
        "Create a new item with emergent properties - quality, condition, value, and narrative "
        "hooks are generated based on context rather than being fully prescribed. "
        "Items can have history, previous owners, quirks. They trigger needs (food triggers "
        "hunger, drinks trigger thirst). Use this when introducing a new item to the scene."
    ),
    parameters=[
        ToolParameter(
            name="item_type",
            param_type="string",
            description=(
                "Type of item. Options: 'weapon', 'armor', 'clothing', 'food', 'drink', "
                "'tool', 'container', 'misc'"
            ),
            enum=["weapon", "armor", "clothing", "food", "drink", "tool", "container", "misc"],
        ),
        ToolParameter(
            name="context",
            param_type="string",
            description=(
                "Description of the item context. Examples: 'hunting knife on display', "
                "'fresh bread cooling on the counter', 'old rusty sword in the corner', "
                "'fine leather boots for sale'. Context influences quality and condition."
            ),
        ),
        ToolParameter(
            name="location_key",
            param_type="string",
            description="Location key where the item appears (e.g., 'blacksmith_shop')",
        ),
        # Optional constraints
        ToolParameter(
            name="constraint_name",
            param_type="string",
            description="Optional: Specific name for the item",
            required=False,
        ),
        ToolParameter(
            name="constraint_quality",
            param_type="string",
            description="Optional: Force specific quality level",
            required=False,
            enum=["poor", "common", "good", "fine", "exceptional"],
        ),
        ToolParameter(
            name="constraint_condition",
            param_type="string",
            description="Optional: Force specific condition",
            required=False,
            enum=["pristine", "good", "worn", "damaged", "broken"],
        ),
        ToolParameter(
            name="constraint_has_history",
            param_type="boolean",
            description="Optional: Force item to have interesting backstory/provenance",
            required=False,
        ),
        ToolParameter(
            name="owner_entity_key",
            param_type="string",
            description="Optional: Entity key of who owns this item (e.g., 'shopkeeper_greta')",
            required=False,
        ),
    ],
)


# =============================================================================
# All Entity Creation Tools
# =============================================================================

NPC_TOOLS = [
    CREATE_NPC_TOOL,
    QUERY_NPC_TOOL,
]

ITEM_TOOLS = [
    CREATE_ITEM_TOOL,
]

ENTITY_TOOLS = [
    CREATE_NPC_TOOL,
    QUERY_NPC_TOOL,
    CREATE_ITEM_TOOL,
]
