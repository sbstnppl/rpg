"""Schemas for the Simplified GM Pipeline.

Defines structured output formats for the GM LLM, including
narrative responses, state changes, and tool results.
"""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class EntityType(str, Enum):
    """Types of entities that can be created."""

    NPC = "npc"
    ITEM = "item"
    LOCATION = "location"


class StateChangeType(str, Enum):
    """Types of state changes the GM can request."""

    MOVE = "move"  # Player moves to location
    TAKE = "take"  # Player takes item
    DROP = "drop"  # Player drops item
    GIVE = "give"  # Player gives item to NPC
    EQUIP = "equip"  # Player equips item
    UNEQUIP = "unequip"  # Player unequips item
    CONSUME = "consume"  # Player eats/drinks (affects needs)
    DAMAGE = "damage"  # Entity takes damage
    HEAL = "heal"  # Entity heals
    RELATIONSHIP = "relationship"  # Relationship change
    FACT = "fact"  # New fact established
    TIME_SKIP = "time_skip"  # Significant time passes
    ITEM_PROPERTY = "item_property"  # Modify item property


# =============================================================================
# Tool Result Schemas
# =============================================================================


class SkillCheckResult(BaseModel):
    """Result of a skill check roll."""

    # Set when roll_mode="manual" - game loop handles animation
    pending: bool = False

    # The skill being checked
    skill: str = ""

    # Difficulty class
    dc: int = 0

    # Player's modifier for this skill
    modifier: int = 0

    # The actual die roll (1-20)
    roll: int | None = None

    # Total = roll + modifier
    total: int | None = None

    # Whether the check succeeded
    success: bool | None = None

    # Special outcomes
    critical_success: bool = False  # Natural 20
    critical_failure: bool = False  # Natural 1


class AttackResult(BaseModel):
    """Result of an attack roll."""

    # Set when roll_mode="manual"
    pending: bool = False

    # Who is attacking
    attacker: str = "player"

    # Target entity key
    target: str = ""

    # Weapon used
    weapon: str = "unarmed"

    # Attack bonus
    attack_bonus: int = 0

    # Target's armor class
    target_ac: int = 10

    # The die roll (1-20)
    roll: int | None = None

    # Whether the attack hit
    hits: bool | None = None

    # Critical hit (natural 20)
    critical: bool = False

    # Damage dealt (if hit)
    damage: int = 0

    # Damage type
    damage_type: str = "physical"


class DamageResult(BaseModel):
    """Result of applying damage to an entity."""

    # Target entity key
    target: str

    # Damage taken
    damage_taken: int

    # Remaining HP after damage
    remaining_hp: int

    # Status
    unconscious: bool = False
    dead: bool = False


class CreateEntityResult(BaseModel):
    """Result of creating a new entity."""

    # The generated entity key
    entity_key: str

    # Entity type
    entity_type: EntityType

    # Display name
    display_name: str

    # Whether creation succeeded
    success: bool = True

    # Error message if failed
    error: str | None = None

    # For items: storage location key if placed in storage
    storage_location_key: str | None = None


# =============================================================================
# State Change Schemas
# =============================================================================


class StateChange(BaseModel):
    """A single state change to apply after GM response."""

    change_type: StateChangeType = Field(
        description="Type of state change"
    )
    target: str = Field(
        description="Entity key being affected"
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Type-specific details"
    )

    class Config:
        use_enum_values = True


class NewEntity(BaseModel):
    """A new entity introduced by the GM via create_entity tool."""

    entity_type: EntityType = Field(
        description="Type of entity: npc, item, or location"
    )
    key: str = Field(
        description="Entity key (set by create_entity tool)"
    )
    display_name: str = Field(
        description="Human-readable name"
    )
    description: str = Field(
        description="Detailed description"
    )

    # NPC-specific
    gender: str | None = None
    occupation: str | None = None
    appearance: dict[str, Any] | None = None

    # Item-specific
    item_type: str | None = None  # weapon, armor, clothing, tool, misc
    properties: dict[str, Any] | None = None
    storage_location_key: str | None = None  # Storage container key

    # Location-specific
    category: str | None = None  # interior, exterior, underground
    parent_location: str | None = None

    class Config:
        use_enum_values = True


# =============================================================================
# GM Response Schema
# =============================================================================


class GMResponse(BaseModel):
    """Complete structured response from the GM LLM.

    This is the output format the GM produces, combining:
    - Narrative text for the player
    - Entity references for grounding validation
    - State changes to apply
    - Time passage
    """

    # The narrative shown to the player (2-5 sentences, second person)
    narrative: str = Field(
        description="Narrative text describing what happens"
    )

    # Whether this is an out-of-character response (meta/lore question)
    is_ooc: bool = Field(
        default=False,
        description="True if this is an OOC response - no time passes, different display styling"
    )

    # Grounding: existing entities mentioned in narrative
    referenced_entities: list[str] = Field(
        default_factory=list,
        description="Keys of existing entities mentioned"
    )

    # New entities created via create_entity tool
    new_entities: list[NewEntity] = Field(
        default_factory=list,
        description="New entities introduced in this response"
    )

    # Mechanical effects
    state_changes: list[StateChange] = Field(
        default_factory=list,
        description="State changes to apply"
    )

    # Time passage
    time_passed_minutes: int = Field(
        default=1,
        description="In-game minutes that passed"
    )

    # Scene mood for continuity
    mood: str | None = Field(
        default=None,
        description="Scene mood: tense, calm, mysterious, jovial, etc."
    )

    # Tool call results (populated by tool execution)
    tool_results: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Results from tool calls during generation"
    )


# =============================================================================
# Validation Schemas
# =============================================================================


class ValidationIssue(BaseModel):
    """A single validation issue found in GM response."""

    category: str  # "grounding", "state_change", "logic"
    message: str
    severity: Literal["error", "warning"] = "error"


class ValidationResult(BaseModel):
    """Result of validating a GM response."""

    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)
