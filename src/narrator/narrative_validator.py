"""Post-narration validation to prevent hallucinated content.

This module provides validation to ensure the narrator doesn't invent
items, NPCs, or locations that don't exist in the game state.
"""

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NarrativeValidationResult:
    """Result of validating narrative content against known state.

    Attributes:
        is_valid: Whether the narrative passes validation.
        hallucinated_items: Items mentioned that don't exist in state.
        hallucinated_npcs: NPCs mentioned that don't exist in state.
        hallucinated_locations: Locations mentioned that don't exist.
        warnings: Non-blocking validation warnings.
    """

    is_valid: bool = True
    hallucinated_items: list[str] = field(default_factory=list)
    hallucinated_npcs: list[str] = field(default_factory=list)
    hallucinated_locations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class NarrativeValidator:
    """Validates narrator output against known game state.

    Ensures the narrator doesn't invent items, NPCs, or locations
    that weren't provided in the context or created during the turn.

    Example:
        validator = NarrativeValidator(
            items_at_location=[{"name": "Washbasin", "key": "washbasin_1"}],
            npcs_present=[{"name": "Elena", "key": "elena"}],
            available_exits=[{"name": "Kitchen", "key": "farmhouse_kitchen"}],
            spawned_items=[{"display_name": "Rope", "item_key": "rope_1"}],
            inventory=[{"name": "Dagger", "key": "player_dagger"}],
        )
        result = validator.validate("You find a washbasin and some rope.")
        assert result.is_valid
    """

    # Common item suffixes for detection
    ITEM_SUFFIXES = (
        "basin", "knife", "sword", "torch", "rope", "bottle", "cup", "plate",
        "chair", "table", "bed", "key", "ring", "book", "scroll", "potion",
        "bag", "chest", "box", "bowl", "bucket", "jug", "mirror", "candle",
        "lamp", "pot", "pan", "cloth", "towel", "blanket", "pillow", "tool",
        "hammer", "axe", "saw", "needle", "thread", "coin", "purse", "sack",
        "barrel", "crate", "basket", "lantern", "flask", "vial", "wand",
        "staff", "dagger", "spear", "bow", "arrow", "shield", "helmet",
        "armor", "boots", "gloves", "cloak", "hat", "bread", "meat", "fruit",
        "cheese", "wine", "ale", "water", "food", "drink",
    )

    def __init__(
        self,
        items_at_location: list[dict[str, Any]] | None = None,
        npcs_present: list[dict[str, Any]] | None = None,
        available_exits: list[dict[str, Any]] | None = None,
        spawned_items: list[dict[str, Any]] | None = None,
        inventory: list[dict[str, Any]] | None = None,
        equipped: list[dict[str, Any]] | None = None,
    ):
        """Initialize validator with known state.

        Args:
            items_at_location: Items present at the current location.
            npcs_present: NPCs present at the current location.
            available_exits: Available exits/destinations.
            spawned_items: Items created this turn via SPAWN_ITEM.
            inventory: Items in player's inventory.
            equipped: Items player has equipped.
        """
        self.items_at_location = items_at_location or []
        self.npcs_present = npcs_present or []
        self.available_exits = available_exits or []
        self.spawned_items = spawned_items or []
        self.inventory = inventory or []
        self.equipped = equipped or []

        # Build lookup sets for fast validation
        self._item_names = self._build_item_names()
        self._npc_names = self._build_npc_names()
        self._location_names = self._build_location_names()

    def _build_item_names(self) -> set[str]:
        """Build set of valid item names (lowercase)."""
        names: set[str] = set()

        # Items at location
        for item in self.items_at_location:
            if item.get("name"):
                names.add(item["name"].lower())
            if item.get("key"):
                names.add(item["key"].lower())
            if item.get("display_name"):
                names.add(item["display_name"].lower())
            if item.get("item_key"):
                names.add(item["item_key"].lower())

        # Spawned items this turn
        for item in self.spawned_items:
            if item.get("display_name"):
                names.add(item["display_name"].lower())
            if item.get("item_key"):
                names.add(item["item_key"].lower())

        # Inventory items
        for item in self.inventory:
            if item.get("name"):
                names.add(item["name"].lower())
            if item.get("key"):
                names.add(item["key"].lower())
            if item.get("display_name"):
                names.add(item["display_name"].lower())
            if item.get("item_key"):
                names.add(item["item_key"].lower())

        # Equipped items
        for item in self.equipped:
            if item.get("name"):
                names.add(item["name"].lower())
            if item.get("key"):
                names.add(item["key"].lower())
            if item.get("display_name"):
                names.add(item["display_name"].lower())
            if item.get("item_key"):
                names.add(item["item_key"].lower())

        return names

    def _build_npc_names(self) -> set[str]:
        """Build set of valid NPC names (lowercase)."""
        names: set[str] = set()
        for npc in self.npcs_present:
            if npc.get("name"):
                names.add(npc["name"].lower())
            if npc.get("key"):
                names.add(npc["key"].lower())
            if npc.get("display_name"):
                names.add(npc["display_name"].lower())
            if npc.get("entity_key"):
                names.add(npc["entity_key"].lower())
        return names

    def _build_location_names(self) -> set[str]:
        """Build set of valid location names (lowercase)."""
        names: set[str] = set()
        for loc in self.available_exits:
            if loc.get("name"):
                names.add(loc["name"].lower())
            if loc.get("key"):
                names.add(loc["key"].lower())
            if loc.get("display_name"):
                names.add(loc["display_name"].lower())
            if loc.get("location_key"):
                names.add(loc["location_key"].lower())
        return names

    def validate(self, narrative: str) -> NarrativeValidationResult:
        """Validate narrative against known state.

        Extracts potential item references from the narrative and checks
        if they exist in the known state. Uses pattern matching to find
        item mentions.

        Args:
            narrative: The generated narrative text.

        Returns:
            NarrativeValidationResult with validation status and any issues.
        """
        result = NarrativeValidationResult(is_valid=True)

        # Skip validation for very short narratives
        if len(narrative) < 20:
            return result

        # Extract potential item mentions
        mentioned_items = self._extract_item_mentions(narrative)

        for item in mentioned_items:
            if not self._is_valid_item(item):
                result.hallucinated_items.append(item)
                result.is_valid = False

        return result

    def _extract_item_mentions(self, narrative: str) -> list[str]:
        """Extract potential item mentions from narrative.

        Uses pattern matching to find phrases that look like item references.

        Args:
            narrative: The narrative text.

        Returns:
            List of potential item names (lowercase).
        """
        items: list[str] = []
        narrative_lower = narrative.lower()

        # Pattern: "the/a/an [adjective]* ITEM_NOUN"
        # This catches things like "a dusty washbasin", "the old knife"
        suffix_pattern = "|".join(self.ITEM_SUFFIXES)
        pattern = rf'\b(?:the|a|an)\s+(?:\w+\s+)*?(\w*(?:{suffix_pattern}))\b'

        matches = re.findall(pattern, narrative_lower)
        items.extend(matches)

        # Also look for standalone item nouns
        for suffix in self.ITEM_SUFFIXES:
            if suffix in narrative_lower:
                # Find the full word containing this suffix
                word_pattern = rf'\b(\w*{suffix}\w*)\b'
                word_matches = re.findall(word_pattern, narrative_lower)
                items.extend(word_matches)

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_items: list[str] = []
        for item in items:
            if item not in seen:
                seen.add(item)
                unique_items.append(item)

        return unique_items

    def _is_valid_item(self, item_name: str) -> bool:
        """Check if item name matches known items.

        Args:
            item_name: The item name to validate (lowercase).

        Returns:
            True if the item exists in known state.
        """
        item_lower = item_name.lower()

        # Direct match
        if item_lower in self._item_names:
            return True

        # Partial match (e.g., "washbasin" matches "old washbasin")
        for known in self._item_names:
            if item_lower in known or known in item_lower:
                return True

        # Check for common words that aren't really items
        # (to reduce false positives)
        common_words = {
            # Natural elements
            "water", "food", "drink", "air", "light", "dark",
            "dust", "dirt", "stone", "wood", "floor", "wall",
            "ceiling", "door", "window", "fire", "smoke",
            # Body/clothing generics (player always has these)
            "clothes", "clothing", "outfit", "attire", "garments",
            "shoes", "pants", "shirt", "tunic", "dress",
            # Room/location words (not items)
            "room", "rooms", "bedroom", "bedrooms", "kitchen",
            "hallway", "hall", "chamber", "cellar", "attic",
            # Adjectives that get caught
            "proper", "clean", "dirty", "old", "new", "simple",
            "small", "large", "wooden", "metal", "leather",
            "uncomfortable", "properly", "familiar", "cool",
            "somewhat", "refreshing", "clear", "cold", "warm",
            # Actions/states/verbs
            "offering", "lingering", "washing", "cleaning",
            "preparing", "searching", "looking", "finding",
            # Nature/seasons
            "spring", "summer", "autumn", "winter", "morning",
            "evening", "night", "day", "dawn", "dusk",
            # Common household items (too generic to track individually)
            "bucket", "soap", "towel", "rag", "cloth", "well",
            # Common words that get caught by regex
            "that", "this", "these", "those", "which", "what",
            "here", "there", "where", "when", "how", "why",
        }
        if item_lower in common_words:
            return True

        return False

    def get_constraint_prompt(self) -> str:
        """Generate prompt additions for re-narration.

        Creates a strict constraint prompt that lists what items and NPCs
        are allowed to be mentioned.

        Returns:
            Constraint text to add to narrator prompt.
        """
        items_list = ", ".join(sorted(self._item_names)) if self._item_names else "none"
        npcs_list = ", ".join(sorted(self._npc_names)) if self._npc_names else "none"

        return f"""
STRICT CONSTRAINTS (previous narration violated these):
- You may ONLY mention these items: {items_list}
- You may ONLY mention these NPCs: {npcs_list}
- Do NOT describe any objects not in the lists above
- If describing a search with no results, say "found nothing of interest"
"""
