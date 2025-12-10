"""GM Response schemas for structured output.

These schemas define the structured output format for GM responses,
enabling single-pass generation with narrative + manifest.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# Import goal-related schemas from goals.py to avoid duplication
from src.agents.schemas.goals import GoalCreation, GoalUpdate


class NPCAction(BaseModel):
    """An action taken by an NPC in the scene."""

    entity_key: str = Field(description="NPC entity key from registry")
    action: str = Field(description="What the NPC did (e.g., 'approaches_player', 'leaves')")
    motivation: list[str] = Field(
        default_factory=list,
        description="Why the NPC did this (e.g., ['goal:find_food', 'need:hunger'])"
    )
    dialogue: str | None = Field(
        default=None,
        description="What the NPC said, if they spoke"
    )


class ItemChange(BaseModel):
    """A change to an item's state."""

    item_key: str = Field(description="Item key from registry")
    action: str = Field(description="What happened (e.g., 'picked_up', 'dropped', 'consumed', 'given')")
    recipient: str | None = Field(
        default=None,
        description="Entity key of recipient, if item was given/traded"
    )


class RelationshipChange(BaseModel):
    """A change in relationship between entities."""

    from_entity: str = Field(description="Entity key of who feels differently")
    to_entity: str = Field(description="Entity key of who they feel about")
    dimension: str = Field(description="Which dimension changed (trust, liking, respect, romantic_interest, fear)")
    delta: int = Field(description="Change amount (-100 to +100)")
    reason: str = Field(description="Why this changed")


class FactRevealed(BaseModel):
    """A fact that was revealed or learned."""

    subject: str = Field(description="Entity or location key the fact is about")
    predicate: str = Field(description="The relationship or property")
    value: str = Field(description="The fact value")
    is_secret: bool = Field(default=False, description="Whether this is a secret fact")


class Stimulus(BaseModel):
    """A stimulus that affects an entity's needs."""

    target: str = Field(description="Entity key affected")
    need: str = Field(description="Which need is affected (hunger, thirst, etc.)")
    intensity: str = Field(description="How strong: 'mild', 'moderate', 'strong'")
    source: str = Field(description="What caused this (e.g., 'smell of bread')")


class GMManifest(BaseModel):
    """Structured manifest of changes from GM response.

    This captures all state changes implied by the narrative,
    enabling precise persistence without extraction LLM calls.
    """

    # Entities in scene
    npcs_in_scene: list[str] = Field(
        default_factory=list,
        description="Entity keys of NPCs present in this scene"
    )
    items_introduced: list[str] = Field(
        default_factory=list,
        description="Item keys of new items introduced"
    )

    # Actions and changes
    npc_actions: list[NPCAction] = Field(
        default_factory=list,
        description="Actions taken by NPCs"
    )
    item_changes: list[ItemChange] = Field(
        default_factory=list,
        description="Changes to item ownership/state"
    )
    relationship_changes: list[RelationshipChange] = Field(
        default_factory=list,
        description="Relationship changes between entities"
    )

    # World state
    facts_revealed: list[FactRevealed] = Field(
        default_factory=list,
        description="Facts learned or revealed"
    )
    stimuli: list[Stimulus] = Field(
        default_factory=list,
        description="Stimuli affecting entity needs"
    )

    # Goal management
    goals_created: list[GoalCreation] = Field(
        default_factory=list,
        description="New goals created for NPCs"
    )
    goal_updates: list[GoalUpdate] = Field(
        default_factory=list,
        description="Updates to existing goals"
    )


class GMState(BaseModel):
    """State changes from GM response."""

    time_advance_minutes: int = Field(
        default=0,
        description="Minutes of game time that passed"
    )
    location_change: str | None = Field(
        default=None,
        description="New location key if player moved"
    )
    combat_initiated: bool = Field(
        default=False,
        description="Whether combat was initiated"
    )


class GMResponse(BaseModel):
    """Complete structured GM response.

    Combines narrative prose with structured state changes,
    enabling single-pass generation without extraction.
    """

    narrative: str = Field(
        description="Pure prose narrative - vivid, immersive storytelling without tags"
    )
    state: GMState = Field(
        default_factory=GMState,
        description="State changes from this turn"
    )
    manifest: GMManifest = Field(
        default_factory=GMManifest,
        description="Detailed manifest of all changes"
    )

    def get_narrative_only(self) -> str:
        """Get just the narrative for display to player."""
        return self.narrative

    def has_state_changes(self) -> bool:
        """Check if there are any state changes."""
        return (
            self.state.time_advance_minutes > 0
            or self.state.location_change is not None
            or self.state.combat_initiated
        )

    def has_manifest_changes(self) -> bool:
        """Check if there are any manifest changes."""
        m = self.manifest
        return (
            len(m.npc_actions) > 0
            or len(m.item_changes) > 0
            or len(m.relationship_changes) > 0
            or len(m.facts_revealed) > 0
            or len(m.goals_created) > 0
            or len(m.goal_updates) > 0
        )
