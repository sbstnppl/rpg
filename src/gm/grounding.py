"""Grounding schemas for GM Pipeline.

This module contains data models for entity grounding validation:
- GroundingManifest: All entities the GM is allowed to reference
- GroundedEntity: Reference info for a single entity
- GroundingValidationResult: Result of grounding validation

The GM uses [key:text] format for entity references, matching
the narrator's format for consistency across the system.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class GroundedEntity(BaseModel):
    """Reference info for an entity the GM can mention."""

    key: str = Field(description="Unique entity key, e.g. 'marcus_001'")
    display_name: str = Field(description="How to display, e.g. 'Marcus'")
    entity_type: str = Field(description="'npc', 'item', 'storage', 'location'")
    short_description: str = Field(
        default="", description="Brief context, e.g. 'the blacksmith'"
    )


class GroundingManifest(BaseModel):
    """All entities the GM is allowed to reference.

    The GM must use [key:text] format when mentioning entities.
    This manifest defines which keys are valid for the current scene.

    Example usage in narrative:
        "[marcus_001:Marcus] waves at you from behind the counter."
        "You pick up [sword_001:the iron sword]."

    Validation checks that all [key:...] references exist in this manifest.
    """

    # Current location
    location_key: str = Field(description="Key of current location")
    location_display: str = Field(description="Display name of location")

    # Player info
    player_key: str = Field(description="Player entity key")
    player_display: str = Field(default="you", description="How to refer to player")

    # All entities grouped by type (key → entity)
    npcs: dict[str, GroundedEntity] = Field(
        default_factory=dict, description="NPCs present at location"
    )
    items_at_location: dict[str, GroundedEntity] = Field(
        default_factory=dict, description="Items visible at location"
    )
    inventory: dict[str, GroundedEntity] = Field(
        default_factory=dict, description="Items in player inventory"
    )
    equipped: dict[str, GroundedEntity] = Field(
        default_factory=dict, description="Items player is wearing/holding"
    )
    storages: dict[str, GroundedEntity] = Field(
        default_factory=dict, description="Storage containers at location"
    )
    exits: dict[str, GroundedEntity] = Field(
        default_factory=dict, description="Accessible locations/exits"
    )

    def contains_key(self, key: str) -> bool:
        """Check if a key exists in the manifest.

        Args:
            key: Entity key to check.

        Returns:
            True if key exists in any category.
        """
        # Check special keys
        if key in (self.location_key, self.player_key):
            return True

        # Check all entity categories
        return (
            key in self.npcs
            or key in self.items_at_location
            or key in self.inventory
            or key in self.equipped
            or key in self.storages
            or key in self.exits
        )

    def all_keys(self) -> set[str]:
        """Get all valid entity keys.

        Returns:
            Set of all valid keys including location and player.
        """
        keys = {self.location_key, self.player_key}
        keys.update(self.npcs.keys())
        keys.update(self.items_at_location.keys())
        keys.update(self.inventory.keys())
        keys.update(self.equipped.keys())
        keys.update(self.storages.keys())
        keys.update(self.exits.keys())
        return keys

    def all_entities(self) -> dict[str, GroundedEntity]:
        """Get all entities as a flat dict.

        Returns:
            Dict of key → GroundedEntity for all entities.
        """
        result: dict[str, GroundedEntity] = {}
        result.update(self.npcs)
        result.update(self.items_at_location)
        result.update(self.inventory)
        result.update(self.equipped)
        result.update(self.storages)
        result.update(self.exits)
        return result

    def get_entity(self, key: str) -> GroundedEntity | None:
        """Look up entity by key.

        Args:
            key: Entity key to find.

        Returns:
            GroundedEntity if found, None otherwise.
        """
        for category in (
            self.npcs,
            self.items_at_location,
            self.inventory,
            self.equipped,
            self.storages,
            self.exits,
        ):
            if key in category:
                return category[key]
        return None

    def format_for_prompt(self) -> str:
        """Format manifest for inclusion in GM system prompt.

        Returns:
            Formatted string showing available entities and [key:text] format.
        """
        lines = [
            "## ENTITY REFERENCES",
            "",
            "Use [key:text] format when mentioning entities:",
            "- [marcus_001:Marcus] waves at you.",
            "- You pick up [sword_001:the iron sword].",
            "",
            "### Available Entities",
            "",
        ]

        # NPCs
        if self.npcs:
            lines.append("**NPCs at location:**")
            for key, entity in self.npcs.items():
                desc = f" ({entity.short_description})" if entity.short_description else ""
                lines.append(f"- {key}: {entity.display_name}{desc}")
            lines.append("")

        # Items at location
        if self.items_at_location:
            lines.append("**Items at location:**")
            for key, entity in self.items_at_location.items():
                lines.append(f"- {key}: {entity.display_name}")
            lines.append("")

        # Player inventory
        if self.inventory:
            lines.append("**Your inventory:**")
            for key, entity in self.inventory.items():
                lines.append(f"- {key}: {entity.display_name}")
            lines.append("")

        # Equipped items
        if self.equipped:
            lines.append("**Equipped/wearing:**")
            for key, entity in self.equipped.items():
                lines.append(f"- {key}: {entity.display_name}")
            lines.append("")

        # Storage containers
        if self.storages:
            lines.append("**Storage containers:**")
            for key, entity in self.storages.items():
                lines.append(f"- {key}: {entity.display_name}")
            lines.append("")

        # Exits
        if self.exits:
            lines.append("**Exits/accessible locations:**")
            for key, entity in self.exits.items():
                lines.append(f"- {key}: {entity.display_name}")
            lines.append("")

        lines.append(
            "If referencing something NOT listed above, "
            "you MUST create it first with create_entity tool."
        )

        return "\n".join(lines)


class InvalidKeyReference(BaseModel):
    """An invalid [key:text] reference found in GM output."""

    key: str = Field(description="The invalid key that was referenced")
    text: str = Field(description="The display text used")
    position: int = Field(description="Character position in narrative")
    context: str = Field(description="Surrounding text for debugging")


class UnkeyedMention(BaseModel):
    """An entity mentioned without [key:text] format."""

    expected_key: str = Field(description="The key that should have been used")
    display_name: str = Field(description="The name that was mentioned")
    position: int = Field(description="Character position in narrative")
    context: str = Field(description="Surrounding text for debugging")


class GroundingValidationResult(BaseModel):
    """Result of grounding validation on GM output."""

    valid: bool = Field(description="Whether all references are valid")
    invalid_keys: list[InvalidKeyReference] = Field(
        default_factory=list, description="Keys not found in manifest"
    )
    unkeyed_mentions: list[UnkeyedMention] = Field(
        default_factory=list, description="Entity names without [key:text] format"
    )

    @property
    def error_count(self) -> int:
        """Total number of grounding errors."""
        return len(self.invalid_keys) + len(self.unkeyed_mentions)

    def error_feedback(self) -> str:
        """Format errors for retry prompt.

        Returns:
            Human-readable error message for LLM retry.
        """
        if self.valid:
            return ""

        lines = ["The following grounding errors were found:", ""]

        if self.invalid_keys:
            lines.append("**Invalid keys (not in manifest):**")
            for err in self.invalid_keys:
                lines.append(f"- [{err.key}:{err.text}] - key '{err.key}' does not exist")
            lines.append("")

        if self.unkeyed_mentions:
            lines.append("**Unkeyed entity mentions (must use [key:text] format):**")
            for err in self.unkeyed_mentions:
                lines.append(
                    f"- '{err.display_name}' should be [{err.expected_key}:{err.display_name}]"
                )
            lines.append("")

        lines.append("Please fix these errors and respond again.")
        return "\n".join(lines)
