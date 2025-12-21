"""Pydantic schemas for Scene-First Architecture.

This module contains all data models for:
- World Mechanics output (WorldUpdate, NPCPlacement, etc.)
- Scene Builder output (SceneManifest, FurnitureSpec, etc.)
- Narrator input/output (NarratorManifest, NarrationResult, etc.)
- Validation (ValidationResult, InvalidReference, etc.)
- Resolution (ResolutionResult)
- Constraints (SocialLimits, ConstraintResult)
- Persistence (PersistedNPC, PersistedScene, etc.)
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class PresenceReason(str, Enum):
    """Why an NPC is at a location."""

    LIVES_HERE = "lives_here"  # This is their home
    SCHEDULE = "schedule"  # NPC schedule says they're here
    EVENT = "event"  # World event placed them here
    STORY = "story"  # Narrative logic placed them here
    VISITING = "visiting"  # Came to see someone


class ObservationLevel(str, Enum):
    """How closely the player is observing."""

    NONE = "none"  # No new observation this turn
    ENTRY = "entry"  # Just arrived, see obvious things
    LOOK = "look"  # Actively looking around
    SEARCH = "search"  # Thoroughly searching
    EXAMINE = "examine"  # Examining specific target


class ItemVisibility(str, Enum):
    """How visible an item is."""

    OBVIOUS = "obvious"  # Seen on entry
    DISCOVERABLE = "discoverable"  # Seen on look/examine
    HIDDEN = "hidden"  # Only found on search


class NarrationType(str, Enum):
    """Type of narration being generated."""

    SCENE_ENTRY = "scene_entry"  # Entering a location
    ACTION_RESULT = "action_result"  # Outcome of player action
    DIALOGUE = "dialogue"  # NPC speech
    CLARIFICATION = "clarification"  # Asking for clarification
    AMBIENT = "ambient"  # General scene description


# =============================================================================
# World Mechanics Schemas
# =============================================================================


class NPCSpec(BaseModel):
    """Specification for creating a new NPC."""

    display_name: str = Field(description="Display name for the NPC")
    gender: str | None = Field(default=None, description="male, female, or None")
    occupation: str | None = Field(default=None)
    personality_hints: list[str] = Field(default_factory=list)
    relationship_to_player: str | None = Field(
        default=None, description="e.g., 'school friend', 'neighbor', 'stranger'"
    )
    backstory_hints: list[str] = Field(default_factory=list)


class NPCPlacement(BaseModel):
    """An NPC's presence at a location."""

    entity_key: str | None = Field(
        default=None, description="Existing NPC key, or None if new NPC"
    )
    new_npc: NPCSpec | None = Field(
        default=None, description="Spec for new NPC if entity_key is None"
    )
    presence_reason: PresenceReason
    presence_justification: str = Field(
        description="Human-readable explanation for why they're here"
    )
    activity: str = Field(description="What they're doing: 'sitting on bed', 'cleaning'")
    mood: str = Field(default="neutral")
    position_in_scene: str = Field(description="Where in the scene: 'by window', 'at desk'")
    will_initiate_conversation: bool = Field(default=False)

    def model_post_init(self, __context: object) -> None:
        """Validate that either entity_key or new_npc is provided."""
        if self.entity_key is None and self.new_npc is None:
            raise ValueError("Either entity_key or new_npc must be provided")


class NPCMovement(BaseModel):
    """An NPC moving from one location to another."""

    entity_key: str
    from_location: str
    to_location: str
    reason: str


class NewElement(BaseModel):
    """A new world element being introduced."""

    element_type: str = Field(description="'npc', 'fact', 'relationship'")
    specification: dict = Field(description="Type-specific data")
    justification: str = Field(description="Why this is appropriate now")
    constraints_checked: list[str] = Field(
        default_factory=list, description="Which constraints were verified"
    )
    narrative_purpose: str = Field(description="How this serves the story")


class WorldEvent(BaseModel):
    """An event occurring in the world."""

    event_type: str = Field(description="'intrusion', 'arrival', 'accident', etc.")
    event_key: str = Field(description="Unique key for this event")
    description: str
    npcs_involved: list[str] = Field(default_factory=list)
    items_involved: list[str] = Field(default_factory=list)
    location: str
    immediate_effects: list[str] = Field(default_factory=list)
    player_will_notice: bool = Field(default=True)


class FactUpdate(BaseModel):
    """A fact being added or modified."""

    subject: str
    predicate: str
    value: str
    source: str = Field(description="Where this fact came from")


class WorldUpdate(BaseModel):
    """Output from World Mechanics processing."""

    # NPC movements based on schedules
    scheduled_movements: list[NPCMovement] = Field(default_factory=list)

    # NPCs at player's current location
    npcs_at_location: list[NPCPlacement] = Field(default_factory=list)

    # New elements introduced
    new_elements: list[NewElement] = Field(default_factory=list)

    # Events occurring
    events: list[WorldEvent] = Field(default_factory=list)

    # Facts discovered/changed
    fact_updates: list[FactUpdate] = Field(default_factory=list)


# =============================================================================
# Scene Builder Schemas
# =============================================================================


class FurnitureSpec(BaseModel):
    """Specification for furniture in a scene."""

    furniture_key: str = Field(description="Unique key for this furniture")
    display_name: str
    furniture_type: str = Field(description="bed, desk, closet, chair, table, etc.")
    material: str = Field(default="wood")
    condition: str = Field(default="good", description="good, worn, damaged, etc.")
    position_in_room: str = Field(description="Where in room: 'center', 'by window'")
    is_container: bool = Field(default=False)
    container_state: str | None = Field(
        default=None, description="If container: 'closed', 'open', 'locked'"
    )
    description_hints: list[str] = Field(default_factory=list)


class ItemSpec(BaseModel):
    """Specification for an item in a scene."""

    item_key: str = Field(description="Unique key for this item")
    display_name: str
    item_type: str = Field(description="book, tool, container, clothing, etc.")
    position: str = Field(description="Where: 'on desk', 'in closet', 'on wall'")
    visibility: ItemVisibility = Field(default=ItemVisibility.OBVIOUS)
    material: str | None = Field(default=None)
    condition: str | None = Field(default=None)
    properties: dict = Field(default_factory=dict)
    description_hints: list[str] = Field(default_factory=list)


class Atmosphere(BaseModel):
    """Sensory details for a scene."""

    lighting: str = Field(description="'dim candlelight', 'bright morning sun'")
    lighting_source: str = Field(description="'window', 'candles', 'fireplace'")
    sounds: list[str] = Field(default_factory=list)
    smells: list[str] = Field(default_factory=list)
    temperature: str = Field(default="comfortable")
    weather_effects: str | None = Field(
        default=None, description="'rain pattering on window'"
    )
    time_of_day_notes: str = Field(default="")
    overall_mood: str = Field(default="neutral", description="'cozy', 'tense', 'peaceful'")


class SceneContents(BaseModel):
    """Physical contents of a scene (before NPC overlay)."""

    furniture: list[FurnitureSpec] = Field(default_factory=list)
    items: list[ItemSpec] = Field(default_factory=list)
    atmosphere: Atmosphere
    discoverable_hints: list[str] = Field(
        default_factory=list,
        description="Hints for things player might find on closer look",
    )


class SceneNPC(BaseModel):
    """An NPC in the scene for narrator."""

    entity_key: str
    display_name: str
    gender: str | None = Field(default=None)
    presence_reason: PresenceReason
    activity: str
    mood: str
    position_in_scene: str
    appearance_notes: str = Field(default="")
    will_initiate: bool = Field(default=False)
    pronouns: str | None = Field(default=None, description="'he/him', 'she/her'")


class SceneManifest(BaseModel):
    """Complete scene state from Scene Builder."""

    location_key: str
    location_display: str
    location_type: str = Field(description="bedroom, tavern, forest, etc.")

    # Physical contents
    furniture: list[FurnitureSpec] = Field(default_factory=list)
    items: list[ItemSpec] = Field(default_factory=list)

    # NPCs (from World Mechanics)
    npcs: list[SceneNPC] = Field(default_factory=list)

    # Atmosphere
    atmosphere: Atmosphere

    # Observation state
    observation_level: ObservationLevel = Field(default=ObservationLevel.ENTRY)
    undiscovered_hints: list[str] = Field(default_factory=list)

    # Generation tracking
    is_first_visit: bool = Field(default=True)
    generated_at: str | None = Field(default=None, description="ISO timestamp")


# =============================================================================
# Narrator Schemas
# =============================================================================


class EntityRef(BaseModel):
    """Reference info for an entity the narrator can use."""

    key: str
    display_name: str
    entity_type: str = Field(description="'npc', 'item', 'furniture'")
    short_description: str
    pronouns: str | None = Field(default=None)
    position: str | None = Field(default=None)


class NarratorManifest(BaseModel):
    """Everything the narrator is allowed to reference."""

    location_key: str
    location_display: str

    # All entities with keys
    entities: dict[str, EntityRef] = Field(default_factory=dict)

    # Atmosphere (free to use)
    atmosphere: Atmosphere

    # What just happened
    world_events: list[str] = Field(default_factory=list)

    # Player action being narrated
    player_action: dict | None = Field(default=None)

    # For clarification
    clarification_context: dict | None = Field(default=None)

    def get_reference_guide(self) -> str:
        """Format for narrator prompt."""
        lines = ["## Entities You May Reference (EXACT KEYS)", ""]
        lines.append("Use EXACTLY these [key] values - do not modify or invent keys:")
        lines.append("")

        # Group by type
        npcs = [e for e in self.entities.values() if e.entity_type == "npc"]
        furniture = [e for e in self.entities.values() if e.entity_type == "furniture"]
        items = [e for e in self.entities.values() if e.entity_type == "item"]

        if npcs:
            lines.append("**NPCs:**")
            for e in npcs:
                pronouns = f" ({e.pronouns})" if e.pronouns else ""
                pos = f" - {e.position}" if e.position else ""
                lines.append(f"- [{e.key}] {e.display_name}{pronouns}{pos}")
            lines.append("")

        if furniture:
            lines.append("**Furniture:**")
            for e in furniture:
                pos = f" - {e.position}" if e.position else ""
                lines.append(f"- [{e.key}] {e.display_name}{pos}")
            lines.append("")

        if items:
            lines.append("**Items:**")
            for e in items:
                pos = f" - {e.position}" if e.position else ""
                lines.append(f"- [{e.key}] {e.display_name}{pos}")
            lines.append("")

        return "\n".join(lines)


class NarrationContext(BaseModel):
    """Context for narrator."""

    turn_history: list[dict] = Field(default_factory=list)
    player_action: dict | None = Field(default=None)
    action_result: dict | None = Field(default=None)
    clarification_prompt: str | None = Field(default=None)
    previous_errors: list[str] = Field(default_factory=list)

    def with_errors(self, errors: list[str]) -> NarrationContext:
        """Return new context with errors added."""
        return NarrationContext(
            turn_history=self.turn_history,
            player_action=self.player_action,
            action_result=self.action_result,
            clarification_prompt=self.clarification_prompt,
            previous_errors=self.previous_errors + errors,
        )


class NarrationResult(BaseModel):
    """Result from narrator."""

    display_text: str = Field(description="Text shown to player (keys stripped)")
    raw_output: str = Field(description="Raw output with [key] markers")
    entity_references: list[EntityRef] = Field(default_factory=list)
    validation_passed: bool = Field(default=True)


# =============================================================================
# Validation Schemas
# =============================================================================


class InvalidReference(BaseModel):
    """An invalid [key] reference found in narrator output."""

    key: str
    position: int
    context: str = Field(description="Surrounding text for debugging")
    error: str


class UnkeyedReference(BaseModel):
    """An entity mentioned without [key] format."""

    entity_key: str
    display_name: str
    error: str


class ValidationResult(BaseModel):
    """Result of narrator output validation."""

    valid: bool
    errors: list[InvalidReference | UnkeyedReference] = Field(default_factory=list)
    references: list[EntityRef] = Field(default_factory=list)

    @property
    def error_messages(self) -> list[str]:
        """Get list of error message strings."""
        return [e.error for e in self.errors]


# =============================================================================
# Resolution Schemas
# =============================================================================


class ResolutionResult(BaseModel):
    """Result of resolving a player reference."""

    resolved: bool = Field(default=False)
    entity: EntityRef | None = Field(default=None)

    # Legacy fields for backwards compatibility
    entity_key: str | None = Field(default=None)
    entity_type: str | None = Field(default=None)

    # If ambiguous
    ambiguous: bool = Field(default=False)
    candidates: list[EntityRef] = Field(default_factory=list)
    clarification_needed: str | None = Field(default=None)

    # Resolution method used
    method: str = Field(default="none")

    # If failed
    error: str | None = Field(default=None)


# =============================================================================
# Constraint Schemas
# =============================================================================


class SocialLimits(BaseModel):
    """Realistic social relationship limits."""

    max_close_friends: int = Field(default=5)
    max_casual_friends: int = Field(default=15)
    max_acquaintances: int = Field(default=50)
    max_new_relationships_per_week: int = Field(default=3)
    min_interactions_for_friendship: int = Field(default=5)

    @classmethod
    def for_player(cls, personality: str | None = None) -> SocialLimits:
        """Adjust limits based on player personality."""
        if personality == "extrovert":
            return cls(
                max_close_friends=8,
                max_casual_friends=25,
                max_new_relationships_per_week=5,
            )
        elif personality == "introvert":
            return cls(
                max_close_friends=3,
                max_casual_friends=8,
                max_new_relationships_per_week=1,
            )
        return cls()


class ConstraintResult(BaseModel):
    """Result of constraint checking."""

    allowed: bool
    reason: str | None = Field(default=None)
    violated_constraint: str | None = Field(default=None)
    suggestion: str | None = Field(default=None)


# =============================================================================
# Persistence Schemas
# =============================================================================


class PersistedNPC(BaseModel):
    """NPC after persistence."""

    entity_key: str
    entity_id: int
    was_created: bool = Field(description="True if newly created this turn")


class PersistedItem(BaseModel):
    """Item after persistence."""

    item_key: str
    item_id: int
    storage_location_id: int | None = Field(default=None)
    was_created: bool


class PersistedWorldUpdate(BaseModel):
    """Result of persisting world update."""

    npcs: list[PersistedNPC] = Field(default_factory=list)
    events_created: list[str] = Field(default_factory=list)
    facts_stored: int = Field(default=0)


class PersistedScene(BaseModel):
    """Result of persisting scene."""

    furniture: list[PersistedItem] = Field(default_factory=list)
    items: list[PersistedItem] = Field(default_factory=list)
    location_marked_generated: bool = Field(default=False)
