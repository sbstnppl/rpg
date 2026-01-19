"""Post-processing layer for quantum branch deltas.

This module provides repair and validation for LLM-generated state deltas.
The principle is: "Fix what we can, regenerate what we can't."

Fixable issues (auto-repaired):
- Missing CREATE_ENTITY before TRANSFER_ITEM
- Out-of-range values (clamped to 0-100)
- Invalid entity_type (mapped/defaulted)
- Invalid fact category (defaulted)
- Wrong delta ordering (CREATE before others)

Unfixable issues (trigger regeneration):
- Conflicting deltas (CREATE + DELETE same entity)
- Duplicate CREATE_ENTITY for same key
- Negative time advancement
- Unknown entity keys for UPDATE operations
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

from src.gm.grounding import GroundingManifest
from src.world_server.quantum.schemas import DeltaType, StateDelta

if TYPE_CHECKING:
    from src.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class RegenerationNeeded(Exception):
    """Raised when deltas are too broken to repair.

    The caller should catch this and trigger a new LLM generation
    rather than using the broken branch.
    """

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Branch regeneration needed: {reason}")


@dataclass
class PostProcessResult:
    """Result of delta post-processing."""

    deltas: list[StateDelta]
    """Fixed deltas ready for use."""

    repairs_made: list[str] = field(default_factory=list)
    """Log of repairs for debugging."""

    needs_regeneration: bool = False
    """True if deltas have unfixable issues."""

    regeneration_reason: str | None = None
    """Reason regeneration is needed (if applicable)."""


# Type hints for entity types
ITEM_TYPE_HINTS: dict[str, str] = {
    # Keys
    "key": "key",
    # Weapons
    "sword": "weapon",
    "axe": "weapon",
    "dagger": "weapon",
    "bow": "weapon",
    "staff": "weapon",
    "mace": "weapon",
    "spear": "weapon",
    # Food
    "bread": "food",
    "apple": "food",
    "meat": "food",
    "cheese": "food",
    "fish": "food",
    "stew": "food",
    "pie": "food",
    "cake": "food",
    # Drinks
    "ale": "drink",
    "water": "drink",
    "wine": "drink",
    "mead": "drink",
    "beer": "drink",
    "cider": "drink",
    # Consumables
    "potion": "consumable",
    "elixir": "consumable",
    "tonic": "consumable",
    # Misc
    "coin": "misc",
    "gold": "misc",
    "silver": "misc",
    "copper": "misc",
    "book": "misc",
    "scroll": "misc",
    "letter": "misc",
    "note": "misc",
    "map": "misc",
    "gem": "misc",
    "ring": "accessory",
    "necklace": "accessory",
    "amulet": "accessory",
    "badge": "accessory",
    # Common NPC-given items (drinks in containers)
    "mug": "drink",
    "tankard": "drink",
    "goblet": "drink",
    "cup": "drink",
    "flask": "drink",
    # Common NPC-given items (food in containers)
    "bowl": "food",
    "plate": "food",
    "loaf": "food",
    "portion": "food",
    "serving": "food",
    # Common NPC-given items (misc)
    "parchment": "misc",
    "document": "misc",
    "token": "misc",
    # Containers
    "chest": "container",
    "box": "container",
    "bag": "container",
    "pouch": "container",
    "crate": "container",
    "barrel": "container",
    # Tools
    "rope": "tool",
    "torch": "tool",
    "lantern": "tool",
    "pickaxe": "tool",
    "hammer": "tool",
    # Clothing
    "cloak": "clothing",
    "robe": "clothing",
    "tunic": "clothing",
    "boots": "clothing",
    "gloves": "clothing",
    "hat": "clothing",
    "hood": "clothing",
    # Armor
    "armor": "armor",
    "shield": "armor",
    "helmet": "armor",
    "gauntlet": "armor",
}

# NPC type hints for auto-creation from narrative
NPC_KEY_HINTS: set[str] = {
    "patron", "traveler", "stranger", "guard", "merchant",
    "villager", "farmer", "laborer", "beggar", "servant",
    "worker", "visitor", "customer", "guest", "passerby",
}

VALID_NEEDS = {"hunger", "thirst", "stamina", "sleep_pressure", "wellness", "hygiene", "social_connection"}
VALID_RELATIONSHIP_ATTRS = {"trust", "liking", "respect", "romantic_interest", "knows"}
VALID_FACT_CATEGORIES = {
    "personal",
    "secret",
    "preference",
    "skill",
    "history",
    "relationship",
    "location",
    "world",
}


class DeltaPostProcessor:
    """Post-processor for LLM-generated state deltas.

    Repairs common LLM errors and flags unfixable issues.

    Usage:
        processor = DeltaPostProcessor(manifest)
        result = processor.process(deltas)

        if result.needs_regeneration:
            raise RegenerationNeeded(result.regeneration_reason)

        fixed_deltas = result.deltas
    """

    def __init__(self, manifest: GroundingManifest):
        """Initialize the post-processor.

        Args:
            manifest: Grounding manifest for entity validation.
        """
        self.manifest = manifest
        self.repairs_made: list[str] = []

    def process(
        self, deltas: list[StateDelta], narrative: str | None = None
    ) -> PostProcessResult:
        """Process deltas, fixing what we can.

        Args:
            deltas: Raw deltas from LLM.
            narrative: Optional narrative text to parse for NPC references.

        Returns:
            PostProcessResult with fixed deltas or regeneration flag.
        """
        self.repairs_made = []

        # First check for unfixable conflicts
        needs_regen, reason = self._check_conflicts(deltas)
        if needs_regen:
            return PostProcessResult(
                deltas=deltas,
                needs_regeneration=True,
                regeneration_reason=reason,
            )

        # Check for unknown keys in UPDATE operations
        needs_regen, reason = self._check_unknown_keys(deltas)
        if needs_regen:
            return PostProcessResult(
                deltas=deltas,
                needs_regeneration=True,
                regeneration_reason=reason,
            )

        # Apply repairs
        fixed = deltas

        # Inject missing NPC creates from narrative [key:display] patterns
        fixed = self._inject_missing_npc_creates(fixed, narrative)

        # Inject missing CREATE_ENTITY for TRANSFER_ITEM
        fixed = self._inject_missing_creates(fixed)

        # Reorder: CREATE first
        fixed = self._reorder_deltas(fixed)

        # Normalize entity types in CREATE_ENTITY
        fixed = self._normalize_entity_types(fixed)

        # Fix fact categories
        fixed = self._fix_fact_categories(fixed)

        # Clamp numeric values
        fixed = self._clamp_values(fixed)

        if self.repairs_made:
            logger.info(f"Delta post-processor made {len(self.repairs_made)} repairs")
            for repair in self.repairs_made:
                logger.debug(f"  - {repair}")

        return PostProcessResult(
            deltas=fixed,
            repairs_made=self.repairs_made,
        )

    def _check_conflicts(self, deltas: list[StateDelta]) -> tuple[bool, str | None]:
        """Check for unfixable conflicts.

        Returns:
            (needs_regeneration, reason) tuple.
        """
        targets: dict[str, list[DeltaType]] = {}

        for delta in deltas:
            key = delta.target_key
            if key not in targets:
                targets[key] = []
            targets[key].append(delta.delta_type)

        for key, types in targets.items():
            # CREATE + DELETE conflict
            if DeltaType.CREATE_ENTITY in types and DeltaType.DELETE_ENTITY in types:
                return True, f"Conflicting CREATE and DELETE for '{key}'"

            # Duplicate CREATE
            if types.count(DeltaType.CREATE_ENTITY) > 1:
                return True, f"Duplicate CREATE_ENTITY for '{key}'"

        # Check for negative time
        for delta in deltas:
            if delta.delta_type == DeltaType.ADVANCE_TIME:
                minutes = delta.changes.get("minutes", 0)
                if isinstance(minutes, (int, float)) and minutes < 0:
                    return True, f"Negative time advancement: {minutes}"

        return False, None

    def _check_unknown_keys(self, deltas: list[StateDelta]) -> tuple[bool, str | None]:
        """Check for UPDATE operations referencing unknown entities.

        TRANSFER_ITEM for unknown items is OK (we can auto-create).
        UPDATE_ENTITY/RELATIONSHIP for unknown entities is NOT OK.

        Returns:
            (needs_regeneration, reason) tuple.
        """
        # Collect keys that will be created by CREATE_ENTITY deltas
        will_create = {
            d.target_key for d in deltas if d.delta_type == DeltaType.CREATE_ENTITY
        }

        for delta in deltas:
            # Check UPDATE_ENTITY
            if delta.delta_type == DeltaType.UPDATE_ENTITY:
                key = delta.target_key
                if not self.manifest.contains_key(key) and key not in will_create:
                    return True, f"UPDATE_ENTITY references unknown entity '{key}'"

            # Check UPDATE_RELATIONSHIP
            if delta.delta_type == DeltaType.UPDATE_RELATIONSHIP:
                from_key = delta.changes.get("from_key")
                to_key = delta.changes.get("to_key")

                if from_key and not self.manifest.contains_key(from_key):
                    if from_key not in will_create:
                        return (
                            True,
                            f"UPDATE_RELATIONSHIP from_key '{from_key}' unknown",
                        )

                if to_key and not self.manifest.contains_key(to_key):
                    if to_key not in will_create:
                        return (
                            True,
                            f"UPDATE_RELATIONSHIP to_key '{to_key}' unknown",
                        )

            # Check UPDATE_LOCATION (entity must exist AND destination must exist)
            if delta.delta_type == DeltaType.UPDATE_LOCATION:
                entity_key = delta.target_key
                if not self.manifest.contains_key(entity_key):
                    if entity_key not in will_create:
                        return (
                            True,
                            f"UPDATE_LOCATION for unknown entity '{entity_key}'",
                        )

                # Validate destination location exists in exits or candidate_locations
                destination = delta.changes.get("location_key")
                valid_destinations = set(self.manifest.exits.keys()) | set(self.manifest.candidate_locations.keys())
                if destination and destination not in valid_destinations:
                    return (
                        True,
                        f"UPDATE_LOCATION to unknown destination '{destination}'. "
                        f"Valid locations: {list(valid_destinations)}",
                    )

        return False, None

    def _check_unknown_locations(
        self, deltas: list[StateDelta]
    ) -> tuple[bool, str | None]:
        """Check for UPDATE_LOCATION deltas referencing non-existent destinations.

        Unlike entity keys which can be clarified via LLM, location destinations
        must exist in the manifest's exits or candidate_locations. Invalid
        locations cannot be fixed and require regeneration.

        NOTE: This method is kept for backwards compatibility with sync process().
        The async path uses _remove_invalid_location_deltas() instead for graceful handling.

        Returns:
            (needs_regeneration, reason) tuple.
        """
        valid_destinations = set(self.manifest.exits.keys()) | set(self.manifest.candidate_locations.keys())

        for delta in deltas:
            if delta.delta_type == DeltaType.UPDATE_LOCATION:
                destination = delta.changes.get("location_key")
                if destination and destination not in valid_destinations:
                    return (
                        True,
                        f"UPDATE_LOCATION to unknown destination '{destination}'. "
                        f"Valid locations: {list(valid_destinations)}",
                    )

        return False, None

    def _remove_invalid_location_deltas(
        self, deltas: list[StateDelta]
    ) -> list[StateDelta]:
        """Remove UPDATE_LOCATION deltas with invalid destinations.

        This handles cases where the LLM hallucinates locations that don't exist,
        or incorrectly treats position changes within a room as location changes.
        Rather than failing the entire branch, we remove the invalid delta and
        let the narrative proceed (the player just doesn't actually move).

        Common cases this fixes:
        - "sneak behind the bar" → LLM generates UPDATE_LOCATION to "tavern_cellar"
        - "climb to the rafters" → LLM generates UPDATE_LOCATION to "tavern_rafters"

        These are position changes within a room, not actual location moves.

        Args:
            deltas: List of state deltas to filter.

        Returns:
            Filtered list with invalid UPDATE_LOCATION deltas removed.
        """
        valid_destinations = set(self.manifest.exits.keys()) | set(
            self.manifest.candidate_locations.keys()
        )
        result = []

        for delta in deltas:
            if delta.delta_type == DeltaType.UPDATE_LOCATION:
                destination = delta.changes.get("location_key")
                if destination and destination not in valid_destinations:
                    logger.warning(
                        f"Removing invalid UPDATE_LOCATION to '{destination}'. "
                        f"Valid destinations: {list(valid_destinations)}. "
                        f"This was likely a position change within the room, not a location move."
                    )
                    self.repairs_made.append(
                        f"Removed invalid UPDATE_LOCATION to '{destination}'"
                    )
                    continue  # Skip this delta
            result.append(delta)

        return result

    def _inject_missing_creates(self, deltas: list[StateDelta]) -> list[StateDelta]:
        """Auto-create items referenced by TRANSFER_ITEM but not in manifest."""
        result = []
        created_keys: set[str] = set()

        # Collect keys that will be created by existing CREATE_ENTITY deltas
        existing_creates = {
            d.target_key for d in deltas if d.delta_type == DeltaType.CREATE_ENTITY
        }

        for delta in deltas:
            if delta.delta_type == DeltaType.TRANSFER_ITEM:
                item_key = delta.target_key

                # Check if item exists or will be created
                item_exists = self._item_exists(item_key)
                will_be_created = item_key in existing_creates or item_key in created_keys

                if not item_exists and not will_be_created:
                    # Inject CREATE_ENTITY
                    create_delta = StateDelta(
                        delta_type=DeltaType.CREATE_ENTITY,
                        target_key=item_key,
                        changes={
                            "entity_type": self._infer_entity_type(item_key),
                            "display_name": self._key_to_display_name(item_key),
                        },
                    )
                    result.append(create_delta)
                    created_keys.add(item_key)
                    self.repairs_made.append(f"Injected CREATE_ENTITY for '{item_key}'")

            result.append(delta)

        return result

    def _item_exists(self, key: str) -> bool:
        """Check if an item exists in the manifest."""
        return (
            key in self.manifest.items_at_location
            or key in self.manifest.inventory
            or key in self.manifest.equipped
            or key in self.manifest.additional_valid_keys
        )

    def _get_all_known_keys(self) -> set[str]:
        """Get all entity keys known to the manifest."""
        return set(self.manifest.all_keys())

    def _inject_missing_npc_creates(
        self, deltas: list[StateDelta], narrative: str | None
    ) -> list[StateDelta]:
        """Auto-create NPCs referenced in narrative [key:display] format but not in manifest.

        Parses narrative for [key:Display Name] patterns and creates NPC entities
        for keys that look like NPCs (based on NPC_KEY_HINTS) but don't exist.

        Args:
            deltas: Current delta list.
            narrative: Narrative text to parse for NPC references.

        Returns:
            Deltas with CREATE_ENTITY prepended for new NPC keys.
        """
        if not narrative:
            return deltas

        # Parse [key:Display Name] patterns
        pattern = r'\[([a-z][a-z0-9_]*):([^\]]+)\]'
        matches = re.findall(pattern, narrative)

        # Track what we've already created
        existing_keys = self._get_all_known_keys()
        pending_creates = {d.target_key for d in deltas if d.delta_type == DeltaType.CREATE_ENTITY}

        create_deltas = []
        seen_keys: set[str] = set()

        for key, display in matches:
            # Skip if known, pending, or already processed
            if key in existing_keys or key in pending_creates or key in seen_keys:
                continue

            # Check if this looks like an NPC key
            if any(hint in key for hint in NPC_KEY_HINTS):
                create_deltas.append(StateDelta(
                    delta_type=DeltaType.CREATE_ENTITY,
                    target_key=key,
                    changes={
                        "entity_type": "npc",
                        "display_name": self._key_to_display_name(key),
                        "location_key": self.manifest.location_key,
                    },
                ))
                self.repairs_made.append(f"Injected CREATE_ENTITY for NPC '{key}'")
                seen_keys.add(key)

        return create_deltas + deltas

    def _infer_entity_type(self, key: str) -> str:
        """Guess entity type from key name."""
        key_lower = key.lower()

        for hint, entity_type in ITEM_TYPE_HINTS.items():
            if hint in key_lower:
                return entity_type

        return "item"  # Safe default

    def _key_to_display_name(self, key: str) -> str:
        """Convert 'innkeeper_box_key' → 'Innkeeper Box Key'."""
        # Remove numeric suffix
        name = re.sub(r"_\d+$", "", key)
        # Replace underscores with spaces, title case
        return name.replace("_", " ").title()

    def _reorder_deltas(self, deltas: list[StateDelta]) -> list[StateDelta]:
        """Ensure CREATE comes before UPDATE/TRANSFER for same entity."""
        creates = []
        others = []

        for delta in deltas:
            if delta.delta_type == DeltaType.CREATE_ENTITY:
                creates.append(delta)
            else:
                others.append(delta)

        if creates and others:
            # Only log if we actually reordered
            original_order = [d.delta_type for d in deltas]
            new_order = [d.delta_type for d in creates + others]
            if original_order != new_order:
                self.repairs_made.append("Reordered deltas: CREATE_ENTITY first")

        return creates + others

    def _normalize_entity_types(self, deltas: list[StateDelta]) -> list[StateDelta]:
        """Normalize entity_type values in CREATE_ENTITY deltas."""
        valid_entity_types = set(ITEM_TYPE_HINTS.values()) | {
            "item",
            "npc",
            "location",
            "storage",
            "monster",
            "animal",
        }

        for delta in deltas:
            if delta.delta_type == DeltaType.CREATE_ENTITY:
                entity_type = delta.changes.get("entity_type", "")
                if entity_type and entity_type.lower() not in valid_entity_types:
                    # Try to infer from key
                    inferred = self._infer_entity_type(delta.target_key)
                    delta.changes["entity_type"] = inferred
                    self.repairs_made.append(
                        f"Normalized entity_type '{entity_type}' → '{inferred}' "
                        f"for '{delta.target_key}'"
                    )

        return deltas

    def _fix_fact_categories(self, deltas: list[StateDelta]) -> list[StateDelta]:
        """Fix invalid fact categories in RECORD_FACT deltas."""
        for delta in deltas:
            if delta.delta_type == DeltaType.RECORD_FACT:
                category = delta.changes.get("category", "personal")
                if category not in VALID_FACT_CATEGORIES:
                    delta.changes["category"] = "personal"
                    self.repairs_made.append(
                        f"Fixed fact category '{category}' → 'personal' "
                        f"for '{delta.target_key}'"
                    )

        return deltas

    def _clamp_values(self, deltas: list[StateDelta]) -> list[StateDelta]:
        """Clamp need/relationship values to 0-100."""
        for delta in deltas:
            if delta.delta_type == DeltaType.UPDATE_NEED:
                for key, value in delta.changes.items():
                    if key in VALID_NEEDS and isinstance(value, (int, float)):
                        clamped = max(0, min(100, value))
                        if clamped != value:
                            delta.changes[key] = clamped
                            self.repairs_made.append(
                                f"Clamped need {key}={value} → {clamped}"
                            )

            if delta.delta_type == DeltaType.UPDATE_RELATIONSHIP:
                for key, value in delta.changes.items():
                    if (
                        key in VALID_RELATIONSHIP_ATTRS
                        and key != "knows"
                        and isinstance(value, (int, float))
                    ):
                        clamped = max(0, min(100, value))
                        if clamped != value:
                            delta.changes[key] = clamped
                            self.repairs_made.append(
                                f"Clamped relationship {key}={value} → {clamped}"
                            )

        return deltas

    # =========================================================================
    # Async Processing with LLM Clarification
    # =========================================================================

    async def process_async(
        self,
        deltas: list[StateDelta],
        llm: LLMProvider,
        narrative: str | None = None,
    ) -> PostProcessResult:
        """Process deltas with async LLM clarification for unknown keys.

        This is the preferred entry point for production use. It asks the LLM
        to clarify unknown entity keys rather than triggering regeneration.

        Args:
            deltas: Raw deltas from LLM.
            llm: LLM provider for clarification queries.
            narrative: Optional narrative text to parse for NPC references.

        Returns:
            PostProcessResult with fixed deltas.
        """
        self.repairs_made = []

        # 1. Check for hard conflicts (CREATE+DELETE, duplicates, negative time)
        needs_regen, reason = self._check_conflicts(deltas)
        if needs_regen:
            return PostProcessResult(
                deltas=deltas,
                needs_regeneration=True,
                regeneration_reason=reason,
            )

        # 1b. Remove invalid UPDATE_LOCATION deltas gracefully
        # This handles cases where LLM confuses position changes (within room) with location moves
        # e.g., "sneak behind the bar" → hallucinated "tavern_cellar" location
        deltas = self._remove_invalid_location_deltas(deltas)

        # 2. Collect unknown keys that need clarification
        unknown_keys = self._collect_unknown_keys(deltas)

        # 3. Clarify each unknown key with LLM
        key_replacements: dict[str, str] = {}
        keys_to_create: set[str] = set()

        for unknown_key in unknown_keys:
            resolved_key, is_new = await self._clarify_unknown_key(unknown_key, llm)
            if is_new:
                keys_to_create.add(unknown_key)
                self.repairs_made.append(f"LLM confirmed new entity: '{unknown_key}'")
            else:
                key_replacements[unknown_key] = resolved_key
                self.repairs_made.append(
                    f"LLM clarified: '{unknown_key}' → '{resolved_key}'"
                )

        # 4. Apply key replacements
        fixed = self._apply_key_replacements(deltas, key_replacements)

        # 5. Inject CREATE_ENTITY for keys LLM wants to create
        fixed = self._inject_creates_for_keys(fixed, keys_to_create)

        # 6. Apply standard repairs (including NPC injection from narrative)
        fixed = self._inject_missing_npc_creates(fixed, narrative)
        fixed = self._inject_missing_creates(fixed)
        fixed = self._reorder_deltas(fixed)
        fixed = self._normalize_entity_types(fixed)
        fixed = self._fix_fact_categories(fixed)
        fixed = self._clamp_values(fixed)

        if self.repairs_made:
            logger.info(f"Delta post-processor made {len(self.repairs_made)} repairs")
            for repair in self.repairs_made:
                logger.debug(f"  - {repair}")

        return PostProcessResult(
            deltas=fixed,
            repairs_made=self.repairs_made,
        )

    def _collect_unknown_keys(self, deltas: list[StateDelta]) -> list[str]:
        """Collect unknown entity keys that need clarification.

        Returns:
            List of unknown keys (deduplicated).
        """
        unknown: set[str] = set()
        will_create = {
            d.target_key for d in deltas if d.delta_type == DeltaType.CREATE_ENTITY
        }

        for delta in deltas:
            # Check UPDATE_ENTITY
            if delta.delta_type == DeltaType.UPDATE_ENTITY:
                key = delta.target_key
                if not self.manifest.contains_key(key) and key not in will_create:
                    unknown.add(key)

            # Check UPDATE_RELATIONSHIP
            if delta.delta_type == DeltaType.UPDATE_RELATIONSHIP:
                from_key = delta.changes.get("from_key")
                to_key = delta.changes.get("to_key")

                if from_key and not self.manifest.contains_key(from_key):
                    if from_key not in will_create:
                        unknown.add(from_key)

                if to_key and not self.manifest.contains_key(to_key):
                    if to_key not in will_create:
                        unknown.add(to_key)

            # Check UPDATE_LOCATION
            if delta.delta_type == DeltaType.UPDATE_LOCATION:
                entity_key = delta.target_key
                if not self.manifest.contains_key(entity_key):
                    if entity_key not in will_create:
                        unknown.add(entity_key)

        return list(unknown)

    async def _clarify_unknown_key(
        self,
        unknown_key: str,
        llm: LLMProvider,
    ) -> tuple[str, bool]:
        """Ask LLM which key they meant.

        Args:
            unknown_key: The invalid key from the delta.
            llm: LLM provider for the clarification query.

        Returns:
            (resolved_key, is_new_entity) tuple.
            If is_new_entity is True, caller should create the entity.
        """
        from src.llm.message_types import Message

        # Find similar keys
        all_keys = list(self.manifest.all_keys())
        candidates = self._find_similar_keys(unknown_key, all_keys, limit=2)

        # Build options
        options = []
        for i, key in enumerate(candidates, 1):
            options.append(f"[{i}] {key}")

        create_option = len(candidates) + 1
        options.append(f"[{create_option}] None - create new entity '{unknown_key}'")

        prompt = f"""You referenced '{unknown_key}' but it doesn't exist.
Which did you mean?
{chr(10).join(options)}

Reply with just the number."""

        try:
            response = await llm.complete(
                messages=[Message.user(prompt)],
                max_tokens=5,  # Single token response
                temperature=0.0,  # Deterministic
            )

            choice = response.content.strip()
            if choice.isdigit():
                idx = int(choice)
                if 1 <= idx <= len(candidates):
                    return candidates[idx - 1], False  # Use existing key

            # Default: create new entity
            return unknown_key, True

        except Exception as e:
            logger.warning(f"LLM clarification failed: {e}, defaulting to create")
            return unknown_key, True

    def _find_similar_keys(
        self,
        unknown_key: str,
        all_keys: list[str],
        limit: int = 2,
        threshold: float = 0.6,
    ) -> list[str]:
        """Find keys similar to the unknown one using fuzzy matching.

        Args:
            unknown_key: The key to match against.
            all_keys: All valid keys in the manifest.
            limit: Maximum number of matches to return.
            threshold: Minimum similarity score (0.0-1.0).

        Returns:
            List of similar keys, sorted by similarity (best first).
        """
        matches: list[tuple[str, float]] = []

        for key in all_keys:
            ratio = SequenceMatcher(None, unknown_key.lower(), key.lower()).ratio()
            if ratio >= threshold:
                matches.append((key, ratio))

        # Sort by similarity (descending)
        matches.sort(key=lambda x: x[1], reverse=True)

        return [key for key, _ in matches[:limit]]

    def _apply_key_replacements(
        self,
        deltas: list[StateDelta],
        replacements: dict[str, str],
    ) -> list[StateDelta]:
        """Replace unknown keys with their resolved values.

        Args:
            deltas: Original deltas.
            replacements: Map of unknown_key → resolved_key.

        Returns:
            New list of deltas with keys replaced.
        """
        if not replacements:
            return deltas

        result = []
        for delta in deltas:
            # Create a new delta with replaced keys
            new_target = replacements.get(delta.target_key, delta.target_key)
            new_changes = dict(delta.changes)

            # Replace keys in changes dict
            if "from_key" in new_changes:
                new_changes["from_key"] = replacements.get(
                    new_changes["from_key"], new_changes["from_key"]
                )
            if "to_key" in new_changes:
                new_changes["to_key"] = replacements.get(
                    new_changes["to_key"], new_changes["to_key"]
                )

            result.append(
                StateDelta(
                    delta_type=delta.delta_type,
                    target_key=new_target,
                    changes=new_changes,
                )
            )

        return result

    def _inject_creates_for_keys(
        self,
        deltas: list[StateDelta],
        keys_to_create: set[str],
    ) -> list[StateDelta]:
        """Inject CREATE_ENTITY deltas for keys that need to be created.

        Args:
            deltas: Current delta list.
            keys_to_create: Keys that need CREATE_ENTITY deltas.

        Returns:
            Deltas with CREATE_ENTITY prepended for new keys.
        """
        if not keys_to_create:
            return deltas

        creates = []
        for key in keys_to_create:
            create_delta = StateDelta(
                delta_type=DeltaType.CREATE_ENTITY,
                target_key=key,
                changes={
                    "entity_type": self._infer_entity_type(key),
                    "display_name": self._key_to_display_name(key),
                },
            )
            creates.append(create_delta)
            self.repairs_made.append(f"Injected CREATE_ENTITY for new key '{key}'")

        return creates + deltas
