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
    candidate_locations: dict[str, GroundedEntity] = Field(
        default_factory=dict,
        description="Locations matching player's destination that aren't direct exits (for context-aware resolution)",
    )
    additional_valid_keys: set[str] = Field(
        default_factory=set,
        description="Keys created mid-turn (e.g., via create_entity) that should be valid",
    )
    session_id: int | None = Field(
        default=None,
        description="Session ID for tracking which session this manifest belongs to",
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

        # Check keys created mid-turn (e.g., via create_entity tool)
        if key in self.additional_valid_keys:
            return True

        # Check all entity categories
        return (
            key in self.npcs
            or key in self.items_at_location
            or key in self.inventory
            or key in self.equipped
            or key in self.storages
            or key in self.exits
            or key in self.candidate_locations
        )

    def all_keys(self) -> set[str]:
        """Get all valid entity keys.

        Returns:
            Set of all valid keys including location, player, and mid-turn created keys.
        """
        keys = {self.location_key, self.player_key}
        keys.update(self.npcs.keys())
        keys.update(self.items_at_location.keys())
        keys.update(self.inventory.keys())
        keys.update(self.equipped.keys())
        keys.update(self.storages.keys())
        keys.update(self.exits.keys())
        keys.update(self.candidate_locations.keys())
        keys.update(self.additional_valid_keys)
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
        result.update(self.candidate_locations)
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
            self.candidate_locations,
        ):
            if key in category:
                return category[key]
        return None

    def find_similar_key(
        self, invalid_key: str, threshold: float = 0.6
    ) -> str | None:
        """Find a valid key similar to an invalid one using fuzzy matching.

        Used to suggest corrections when the LLM hallucinates entity keys.
        For example, if the model uses 'farmer_001' but 'farmer_marcus' exists,
        this will find and suggest the correct key.

        Args:
            invalid_key: The hallucinated/invalid key to match.
            threshold: Minimum similarity score (0.0-1.0) to consider a match.
                       Default 0.6 balances finding typos vs false positives.

        Returns:
            The most similar valid key if above threshold, None otherwise.
        """
        from difflib import SequenceMatcher

        best_match: str | None = None
        best_score = threshold

        for valid_key in self.all_keys():
            score = SequenceMatcher(None, invalid_key.lower(), valid_key.lower()).ratio()
            if score > best_score:
                best_match = valid_key
                best_score = score

        return best_match

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
            "### TOOL KEY REMINDER (CRITICAL!)",
            "Copy the KEY= value EXACTLY when calling tools. NEVER invent keys!",
            "",
            "Format: KEY=actual_key | Display Name",
            "- For 'KEY=bread_001 | Bread' → item_key=\"bread_001\"",
            "- For 'KEY=farmer_marcus | Marcus' → from_entity=\"farmer_marcus\"",
            "",
            "CORRECT: take_item(item_key=\"bread_001\")",
            "WRONG:   take_item(item_key=\"bread\") ← invented from display name!",
            "",
            "### Available Entities",
            "",
        ]

        # NPCs - with tool call reminder
        if self.npcs:
            lines.append("**NPCs at location** (use KEY= value in tools):")
            for key, entity in self.npcs.items():
                desc = f" ({entity.short_description})" if entity.short_description else ""
                lines.append(f"- KEY={key} | {entity.display_name}{desc}")
            # Add example with first NPC key
            first_npc = next(iter(self.npcs.keys()), None)
            if first_npc:
                lines.append(f"  → Example: get_npc_attitude(from_entity=\"{first_npc}\")")
            lines.append("")

        # Items at location - with tool call reminder
        if self.items_at_location:
            lines.append("**Items at location** (use KEY= value in take_item):")
            for key, entity in self.items_at_location.items():
                lines.append(f"- KEY={key} | {entity.display_name}")
            # Add example with first item key
            first_item = next(iter(self.items_at_location.keys()), None)
            if first_item:
                lines.append(f"  → Example: take_item(item_key=\"{first_item}\")")
            lines.append("")

        # Player inventory - with tool call reminder
        if self.inventory:
            lines.append("**Your inventory** (use KEY= value in drop_item, give_item):")
            for key, entity in self.inventory.items():
                lines.append(f"- KEY={key} | {entity.display_name}")
            lines.append("")

        # Equipped items
        if self.equipped:
            lines.append("**Equipped/wearing:**")
            for key, entity in self.equipped.items():
                lines.append(f"- KEY={key} | {entity.display_name}")
            lines.append("")

        # Storage containers
        if self.storages:
            lines.append("**Storage containers:**")
            for key, entity in self.storages.items():
                lines.append(f"- KEY={key} | {entity.display_name}")
            lines.append("")

        # Exits (directly accessible)
        if self.exits:
            lines.append("**Exits/accessible locations (directly adjacent):**")
            for key, entity in self.exits.items():
                lines.append(f"- KEY={key} | {entity.display_name}")
            lines.append("")

        # Candidate locations (not directly adjacent but known/mentioned)
        if self.candidate_locations:
            lines.append("**Other known locations (may require travel):**")
            for key, entity in self.candidate_locations.items():
                desc = f" ({entity.short_description})" if entity.short_description else ""
                lines.append(f"- KEY={key} | {entity.display_name}{desc}")
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

    def error_feedback(
        self, manifest: "GroundingManifest | None" = None
    ) -> str:
        """Format errors for retry prompt with suggestions.

        Args:
            manifest: Optional manifest for fuzzy matching suggestions.
                     If provided, will suggest similar valid keys.

        Returns:
            Human-readable error message for LLM retry.
        """
        if self.valid:
            return ""

        lines = ["The following grounding errors were found:", ""]

        if self.invalid_keys:
            lines.append("**Invalid keys (not in manifest):**")
            for err in self.invalid_keys:
                suggestion = ""
                if manifest:
                    similar = manifest.find_similar_key(err.key)
                    if similar:
                        entity = manifest.get_entity(similar)
                        name = entity.display_name if entity else similar
                        suggestion = f" → Did you mean: {similar} ({name})?"
                lines.append(
                    f"- [{err.key}:{err.text}] - key '{err.key}' does not exist{suggestion}"
                )

            # Show valid keys of the detected entity types
            if manifest:
                lines.append("")
                lines.append("**Valid keys you can use:**")
                if manifest.npcs:
                    lines.append("NPCs:")
                    for key, entity in list(manifest.npcs.items())[:5]:
                        lines.append(f"  - {key}: {entity.display_name}")
                if manifest.items_at_location:
                    lines.append("Items at location:")
                    for key, entity in list(manifest.items_at_location.items())[:5]:
                        lines.append(f"  - {key}: {entity.display_name}")
                if manifest.inventory:
                    lines.append("Inventory:")
                    for key, entity in list(manifest.inventory.items())[:5]:
                        lines.append(f"  - {key}: {entity.display_name}")
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
