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


class DynamicActionType(str, Enum):
    """Categories of dynamic actions."""

    STATE_CHANGE = "state_change"  # Modifies game state
    RECALL = "recall"  # Knowledge query (reads state, no changes)
    NARRATIVE_ONLY = "narrative_only"  # Pure flavor, no mechanical effect


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
        description="New value to set"
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
    """Current state relevant to planning an action.

    Passed to the LLM planner so it can make informed decisions
    about what changes are needed (or if action is already done).
    """

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
        description="Facts the player character knows"
    )
    entity_state: dict[str, Any] = Field(
        default_factory=dict,
        description="Player's current temporary state (posture, etc.)"
    )
    background: str | None = Field(
        default=None,
        description="Player's background story (for RECALL actions)"
    )
