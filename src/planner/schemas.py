"""Schemas for the Dynamic Action Planner.

Defines the structured output format that the LLM planner produces,
which can then be executed mechanically by the action executor.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class StateChangeType(str, Enum):
    """Types of state changes that can be applied."""

    ITEM_PROPERTY = "item_property"  # Update item.properties JSON
    ENTITY_STATE = "entity_state"  # Update entity.temporary_state JSON
    FACT = "fact"  # Record a new fact in facts table
    KNOWLEDGE_QUERY = "knowledge_query"  # Query existing knowledge (no change)
    SPAWN_ITEM = "spawn_item"  # Create a new emergent item at location


class DynamicActionType(str, Enum):
    """Categories of dynamic actions."""

    STATE_CHANGE = "state_change"  # Modifies game state
    RECALL = "recall"  # Knowledge query (reads state, no changes)
    NARRATIVE_ONLY = "narrative_only"  # Pure flavor, no mechanical effect


class ResponseMode(str, Enum):
    """How to format the response to the player.

    INFO: Direct answer, bypasses narrator for factual queries.
    NARRATE: Full narrative pipeline with style hints.
    """

    INFO = "info"
    NARRATE = "narrate"


class NarrativeStyle(str, Enum):
    """Style hint for narrator (when mode=NARRATE).

    Controls verbosity and focus of the narrative output.
    """

    OBSERVE = "observe"    # Perception, 2-4 sentences, sensory details
    ACTION = "action"      # State change, 1-3 sentences, outcome + atmosphere
    DIALOGUE = "dialogue"  # NPC speech focus, direct quotes
    COMBAT = "combat"      # Mechanical result + brief flavor, 1-2 sentences
    EMOTE = "emote"        # 1 sentence acknowledgment only


class SpawnItemSpec(BaseModel):
    """Specification for creating an emergent item during gameplay.

    Used with SPAWN_ITEM state changes to let the GM autonomously
    create contextually appropriate items when players search.
    """

    item_type: str = Field(
        description="Item category: weapon, armor, clothing, tool, food, drink, misc"
    )
    context: str = Field(
        description="Context for EmergentItemGenerator, e.g. 'washbasin in bedroom corner'"
    )
    display_name: str | None = Field(
        default=None,
        description="Optional specific name (otherwise generated from context)"
    )
    quality: str | None = Field(
        default=None,
        description="Quality constraint: poor, common, good, fine, exceptional"
    )
    condition: str | None = Field(
        default=None,
        description="Condition constraint: pristine, good, worn, damaged, broken"
    )


class StateChange(BaseModel):
    """A single state change to apply.

    Represents one atomic modification to game state that can be
    executed mechanically without LLM interpretation.
    """

    change_type: StateChangeType = Field(
        description="Type of state change (item_property, entity_state, fact)"
    )
    target_type: str = Field(
        description="Type of target: 'item', 'entity', or 'world'"
    )
    target_key: str = Field(
        description="Key of the target (item_key, entity_key, or subject_key)"
    )
    property_name: str = Field(
        description="Name of property to modify (e.g., 'buttoned', 'posture')"
    )
    old_value: Any | None = Field(
        default=None,
        description="Previous value (for context/validation)"
    )
    new_value: Any = Field(
        default=None,
        description="New value to set (None for SPAWN_ITEM)"
    )
    spawn_spec: SpawnItemSpec | None = Field(
        default=None,
        description="For SPAWN_ITEM: specification for the new item"
    )

    class Config:
        use_enum_values = True


class DynamicActionPlan(BaseModel):
    """Structured plan for executing a dynamic action.

    This is the output of the LLM planner. It contains everything needed
    to execute the action mechanically and narrate the result.
    """

    action_type: DynamicActionType = Field(
        description="Category of action (state_change, recall, narrative_only)"
    )
    response_mode: ResponseMode = Field(
        default=ResponseMode.NARRATE,
        description="How to format response: 'info' for direct answers, 'narrate' for prose"
    )
    narrative_style: NarrativeStyle = Field(
        default=NarrativeStyle.ACTION,
        description="Style hint for narrator: observe, action, dialogue, combat, emote"
    )
    requires_roll: bool = Field(
        default=False,
        description="Whether this action requires a skill/attribute check"
    )
    roll_type: str | None = Field(
        default=None,
        description="Type of roll if required (e.g., 'strength', 'dexterity')"
    )
    roll_dc: int | None = Field(
        default=None,
        description="Difficulty class for the roll"
    )
    state_changes: list[StateChange] = Field(
        default_factory=list,
        description="List of state changes to apply (empty for narrative_only/recall)"
    )
    narrator_facts: list[str] = Field(
        description="Facts for narrator to include in response (MUST be included)"
    )
    failure_facts: list[str] | None = Field(
        default=None,
        description="Facts to narrate if roll fails"
    )
    already_true: bool = Field(
        default=False,
        description="Set to true if the requested state is already the case"
    )
    already_true_message: str | None = Field(
        default=None,
        description="Message if action is redundant (e.g., 'shirt is already buttoned')"
    )

    class Config:
        use_enum_values = True


class RelevantState(BaseModel):
    """Current state relevant to planning an action or answering a query.

    Passed to the LLM planner so it can make informed decisions
    about what changes are needed (or if action is already done),
    and to answer player queries about their character and environment.

    Information boundaries are enforced - only observable/known data is included.
    """

    # Existing fields - Player's own state
    inventory: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Items in player inventory with properties"
    )
    equipped: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Currently equipped items with properties"
    )
    known_facts: list[dict[str, str]] = Field(
        default_factory=list,
        description="Facts the player character knows (is_secret=False only)"
    )
    entity_state: dict[str, Any] = Field(
        default_factory=dict,
        description="Player's current temporary state (posture, etc.)"
    )
    background: str | None = Field(
        default=None,
        description="Player's background story (for RECALL actions)"
    )

    # NEW - Character State
    character_needs: dict[str, int] = Field(
        default_factory=dict,
        description="Needs: hunger/thirst/energy/wellness (0=critical, 100=satisfied)"
    )
    visible_injuries: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Injuries on visible body parts only (head, arms, legs)"
    )
    character_memories: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Emotional memories (subject, emotion, context)"
    )

    # NEW - Environment Perception (visibility-filtered)
    npcs_present: list[dict[str, Any]] = Field(
        default_factory=list,
        description="NPCs with VISIBLE info only (appearance, mood, visible equipment)"
    )
    items_at_location: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Items on location surfaces (not in closed containers)"
    )
    available_exits: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Exits with accessibility (blocked_reason, access_requirements)"
    )

    # NEW - Knowledge (what player has discovered/experienced)
    discovered_locations: list[str] = Field(
        default_factory=list,
        description="Location keys player has discovered"
    )
    relationships: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Attitudes toward NPCs player has MET (knows=True only)"
    )

    # NEW - Enrichment Context (already-established details)
    location_details: dict[str, str] = Field(
        default_factory=dict,
        description="Already-established facts about current location (floor_type, lighting, ambient_smell, etc.)"
    )
    world_facts: dict[str, str] = Field(
        default_factory=dict,
        description="World-level facts (weather, currency, customs, local_ruler, etc.)"
    )
    recent_actions: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Recent player actions from turn history (for memory queries like 'what did I eat?')"
    )
