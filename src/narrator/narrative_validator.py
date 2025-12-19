"""Post-narration validation to prevent hallucinated content.

This module provides validation to ensure the narrator doesn't invent
items, NPCs, or locations that don't exist in the game state.

Two validation modes are supported:
1. LLM-based (async): Uses ItemExtractor for accurate item detection
2. Regex-based (sync): Legacy fallback using pattern matching

The LLM-based approach eliminates false positives like "bewildering"
(which ends in "ring" but isn't a ring).
"""

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.narrator.item_extractor import ExtractedItem, ItemExtractor
    from src.narrator.npc_extractor import ExtractedNPC, NPCExtractor

logger = logging.getLogger(__name__)


@dataclass
class NarrativeValidationResult:
    """Result of validating narrative content against known state.

    Attributes:
        is_valid: Whether the narrative passes validation.
        hallucinated_items: Items mentioned that don't exist in state.
            For LLM-based validation, contains ExtractedItem objects.
            For regex-based validation, contains item name strings.
        hallucinated_npcs: NPCs mentioned that don't exist in state.
            For LLM-based validation, contains ExtractedNPC objects.
            For regex-based validation, contains NPC name strings.
        hallucinated_locations: Locations mentioned that don't exist.
        warnings: Non-blocking validation warnings.
        extracted_items: All items extracted from narrative (LLM mode only).
        extracted_npcs: All NPCs extracted from narrative (LLM mode only).
    """

    is_valid: bool = True
    hallucinated_items: list[Any] = field(default_factory=list)  # ExtractedItem or str
    hallucinated_npcs: list[Any] = field(default_factory=list)  # ExtractedNPC or str
    hallucinated_locations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    extracted_items: list[Any] = field(default_factory=list)  # All ExtractedItem objects
    extracted_npcs: list[Any] = field(default_factory=list)  # All ExtractedNPC objects


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
        item_extractor: "ItemExtractor | None" = None,
        npc_extractor: "NPCExtractor | None" = None,
        current_location: str = "unknown",
        player_name: str = "the player",
    ):
        """Initialize validator with known state.

        Args:
            items_at_location: Items present at the current location.
            npcs_present: NPCs present at the current location.
            available_exits: Available exits/destinations.
            spawned_items: Items created this turn via SPAWN_ITEM.
            inventory: Items in player's inventory.
            equipped: Items player has equipped.
            item_extractor: Optional LLM-based item extractor for accurate detection.
                If provided, validate_async() will use it instead of regex.
            npc_extractor: Optional LLM-based NPC extractor for accurate detection.
                If provided, validate_async() will use it to find hallucinated NPCs.
            current_location: Current scene location for extraction context.
            player_name: The player character's name (to exclude from NPC extraction).
        """
        self.items_at_location = items_at_location or []
        self.npcs_present = npcs_present or []
        self.available_exits = available_exits or []
        self.spawned_items = spawned_items or []
        self.inventory = inventory or []
        self.equipped = equipped or []
        self.item_extractor = item_extractor
        self.npc_extractor = npc_extractor
        self.current_location = current_location
        self.player_name = player_name

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
        """Validate narrative against known state (sync/regex-based).

        Extracts potential item references from the narrative and checks
        if they exist in the known state. Uses pattern matching to find
        item mentions.

        Note: This is the legacy regex-based method. For more accurate
        validation, use validate_async() with an ItemExtractor.

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

    async def validate_async(self, narrative: str) -> NarrativeValidationResult:
        """Validate narrative against known state (async/LLM-based).

        Uses LLM-based item and NPC extraction for accurate detection, avoiding
        false positives like "bewildering" (ends in "ring" but isn't a ring).

        Falls back to regex-based validation if no ItemExtractor is configured.

        Args:
            narrative: The generated narrative text.

        Returns:
            NarrativeValidationResult with validation status and extracted entities.
        """
        # Fall back to sync validation if no extractor
        if self.item_extractor is None:
            logger.debug("No ItemExtractor configured, falling back to regex validation")
            return self.validate(narrative)

        result = NarrativeValidationResult(is_valid=True)

        # Skip validation for very short narratives
        if len(narrative) < 20:
            return result

        # Extract items using LLM
        from src.narrator.item_extractor import ItemImportance

        extraction_result = await self.item_extractor.extract(
            narrative,
            current_location=self.current_location,
        )
        result.extracted_items = extraction_result.items

        # Check each extracted item against known state
        for item in extraction_result.items:
            # Skip REFERENCE items (talked about but not present)
            if item.importance == ItemImportance.REFERENCE:
                continue

            # Check if item exists in known state
            if not self._is_valid_item(item.name):
                result.hallucinated_items.append(item)
                result.is_valid = False
                logger.debug(
                    f"Hallucinated item detected: {item.name} "
                    f"(importance={item.importance.value}, context={item.context})"
                )

        # Extract NPCs using LLM if extractor configured
        if self.npc_extractor is not None:
            await self._validate_npcs(narrative, result)

        return result

    async def _validate_npcs(
        self,
        narrative: str,
        result: NarrativeValidationResult,
    ) -> None:
        """Validate NPCs in narrative against known state.

        Extracts NPCs using LLM and checks them against known NPCs.

        Args:
            narrative: The generated narrative text.
            result: The validation result to update.
        """
        from src.narrator.npc_extractor import NPCImportance

        # Get list of known NPC names for exclusion
        known_npc_names = [
            npc.get("name") or npc.get("display_name") or ""
            for npc in self.npcs_present
        ]

        npc_result = await self.npc_extractor.extract(
            narrative,
            current_location=self.current_location,
            player_name=self.player_name,
            known_npcs=known_npc_names,
        )
        result.extracted_npcs = npc_result.npcs

        # Check each extracted NPC against known state
        for npc in npc_result.npcs:
            # Skip REFERENCE NPCs (talked about but not present)
            if npc.importance == NPCImportance.REFERENCE:
                continue

            # Check if NPC exists in known state
            if not self._is_valid_npc(npc.name):
                result.hallucinated_npcs.append(npc)
                # Note: We don't set is_valid=False for NPCs because
                # we handle them differently - spawning or deferring
                # rather than re-narrating
                logger.debug(
                    f"Hallucinated NPC detected: {npc.name} "
                    f"(importance={npc.importance.value}, is_named={npc.is_named})"
                )

    def _is_valid_npc(self, npc_name: str) -> bool:
        """Check if NPC name matches known NPCs.

        Args:
            npc_name: The NPC name to validate.

        Returns:
            True if the NPC exists in known state.
        """
        npc_lower = npc_name.lower()

        # Direct match
        if npc_lower in self._npc_names:
            return True

        # Partial match (e.g., "Aldric" matches "Master Aldric")
        for known in self._npc_names:
            if npc_lower in known or known in npc_lower:
                return True

        return False

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

        # Also look for standalone item nouns (must END with suffix, not just contain it)
        # This avoids false positives like "contemplate" matching "plate"
        for suffix in self.ITEM_SUFFIXES:
            if suffix in narrative_lower:
                # Find words that END with this suffix (not contain it anywhere)
                word_pattern = rf'\b(\w*{suffix})\b'
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
            # Verbs that end with item suffixes (contemplate ends with 'plate', etc.)
            "contemplate", "template", "update", "create", "separate",
            "bring", "string", "fling", "swing", "cling", "wring",
            "think", "shrink", "blink", "drink", "sink", "link",
            "overlook", "mistook", "undertook", "forsook",
            "comfortable", "suitable", "notable", "portable", "vegetable",
            "enable", "disable", "stable", "unstable", "table",
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
