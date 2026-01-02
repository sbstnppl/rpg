"""Reference-based manifest for quantum pipeline.

This module provides a ref-based entity system where entities get single-letter
references ([A], [B], [C]) for unambiguous identification in LLM reasoning.

Key benefits:
- No fuzzy matching needed: "A" maps to exactly one entity
- Deterministic resolution: invalid ref = clear error
- Reduced tokens: single letters vs long display names
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.gm.grounding import GroundedEntity, GroundingManifest


@dataclass
class RefEntry:
    """An entity with its assigned reference letter.

    Attributes:
        ref: Single letter reference like "A", "B", or "A1" for overflow.
        entity_key: Database entity key like "rusty_sword_01".
        display_name: Human-readable name like "rusty sword".
        entity_type: Type of entity: "npc", "item", "storage", "exit".
        location_hint: Where the entity is, like "on the table".
        short_description: Brief context like "the blacksmith".
    """

    ref: str
    entity_key: str
    display_name: str
    entity_type: str
    location_hint: str = ""
    short_description: str = ""

    def format_for_prompt(self) -> str:
        """Format this entry for the reasoning prompt.

        Returns:
            String like "[A] rusty sword - on the wooden table"
        """
        parts = [f"[{self.ref}] {self.display_name}"]

        if self.short_description:
            parts.append(f"({self.short_description})")

        if self.location_hint:
            parts.append(f"- {self.location_hint}")

        return " ".join(parts)


@dataclass
class RefManifest:
    """Manifest with single-letter refs for entity disambiguation.

    This wraps a GroundingManifest and assigns single-letter references
    to each entity, enabling unambiguous entity resolution in LLM output.

    Example:
        manifest = RefManifest.from_grounding_manifest(grounding)
        entry = manifest.resolve_ref("A")
        if entry:
            entity_key = entry.entity_key

    Attributes:
        entries: Map of ref → RefEntry for all entities.
        key_to_ref: Reverse map of entity_key → ref.
        location_key: Current location's entity key.
        location_display: Current location's display name.
        player_key: Player's entity key.
        exit_refs: Map of ref → location_key for exits.
        exit_displays: Map of ref → display name for exits.
    """

    entries: dict[str, RefEntry] = field(default_factory=dict)
    key_to_ref: dict[str, str] = field(default_factory=dict)
    location_key: str = ""
    location_display: str = ""
    player_key: str = "player"
    exit_refs: dict[str, str] = field(default_factory=dict)  # ref → location_key
    exit_displays: dict[str, str] = field(default_factory=dict)  # ref → display

    @classmethod
    def from_grounding_manifest(
        cls,
        manifest: GroundingManifest,
        include_exits_as_refs: bool = False,
    ) -> RefManifest:
        """Create RefManifest from a GroundingManifest.

        Assigns single-letter refs (A, B, C...) to each entity.
        If more than 26 entities, uses A1, A2, etc.

        Args:
            manifest: Source GroundingManifest with entities.
            include_exits_as_refs: If True, exits get refs too.
                                   If False, exits use location_key directly.

        Returns:
            RefManifest with all entities assigned refs.
        """
        result = cls(
            location_key=manifest.location_key,
            location_display=manifest.location_display,
            player_key=manifest.player_key,
        )

        ref_gen = _RefGenerator()

        # Process entities in consistent order for deterministic refs
        # NPCs first (most likely to be referenced)
        for key, entity in manifest.npcs.items():
            ref = ref_gen.next_ref()
            result._add_entry(ref, key, entity, "npc", _get_location_hint(entity, "present"))

        # Items at location
        for key, entity in manifest.items_at_location.items():
            ref = ref_gen.next_ref()
            result._add_entry(ref, key, entity, "item", _get_location_hint(entity, "here"))

        # Player inventory
        for key, entity in manifest.inventory.items():
            ref = ref_gen.next_ref()
            result._add_entry(ref, key, entity, "item", "in your inventory")

        # Equipped items
        for key, entity in manifest.equipped.items():
            ref = ref_gen.next_ref()
            result._add_entry(ref, key, entity, "item", "equipped")

        # Storage containers
        for key, entity in manifest.storages.items():
            ref = ref_gen.next_ref()
            result._add_entry(ref, key, entity, "storage", _get_location_hint(entity, "here"))

        # Exits - optionally as refs or just store for reference
        if include_exits_as_refs:
            for key, entity in manifest.exits.items():
                ref = ref_gen.next_ref()
                result._add_entry(ref, key, entity, "exit", "")
                result.exit_refs[ref] = key
                result.exit_displays[ref] = entity.display_name
        else:
            # Store exits without refs (use location_key directly)
            for key, entity in manifest.exits.items():
                result.exit_refs[key] = key  # key → key (identity)
                result.exit_displays[key] = entity.display_name

        return result

    def _add_entry(
        self,
        ref: str,
        key: str,
        entity: GroundedEntity,
        entity_type: str,
        location_hint: str,
    ) -> None:
        """Add an entry to the manifest."""
        entry = RefEntry(
            ref=ref,
            entity_key=key,
            display_name=entity.display_name,
            entity_type=entity_type,
            location_hint=location_hint,
            short_description=entity.short_description,
        )
        self.entries[ref] = entry
        self.key_to_ref[key] = ref

    def resolve_ref(self, ref: str) -> RefEntry | None:
        """Look up entity by ref.

        Args:
            ref: Reference letter like "A" or "A1".

        Returns:
            RefEntry if found, None otherwise.
        """
        # Normalize: accept both "A" and "[A]"
        clean_ref = ref.strip("[]").upper()
        return self.entries.get(clean_ref)

    def resolve_ref_to_key(self, ref: str) -> str | None:
        """Look up entity key by ref.

        Args:
            ref: Reference letter like "A" or "A1".

        Returns:
            Entity key if found, None otherwise.
        """
        entry = self.resolve_ref(ref)
        return entry.entity_key if entry else None

    def get_ref_for_key(self, entity_key: str) -> str | None:
        """Look up ref by entity key.

        Args:
            entity_key: Entity key like "rusty_sword_01".

        Returns:
            Ref letter if found, None otherwise.
        """
        return self.key_to_ref.get(entity_key)

    def resolve_exit(self, ref_or_key_or_display: str) -> str | None:
        """Look up exit location key.

        Args:
            ref_or_key_or_display: A ref letter, location key, or display name.

        Returns:
            Location key if found, None otherwise.
        """
        # Try direct lookup by ref or key
        if ref_or_key_or_display in self.exit_refs:
            return self.exit_refs[ref_or_key_or_display]
        if ref_or_key_or_display.upper() in self.exit_refs:
            return self.exit_refs[ref_or_key_or_display.upper()]

        # Try lookup by display name (case-insensitive)
        search = ref_or_key_or_display.lower()
        for key, display in self.exit_displays.items():
            if display.lower() == search:
                return self.exit_refs.get(key, key)

        return None

    def format_for_reasoning_prompt(self) -> str:
        """Format manifest for the reasoning LLM prompt.

        Returns:
            Formatted string showing entities with refs and exits.
        """
        lines = []

        # Group entries by type for readability
        npcs = [e for e in self.entries.values() if e.entity_type == "npc"]
        items = [e for e in self.entries.values() if e.entity_type == "item"]
        storages = [e for e in self.entries.values() if e.entity_type == "storage"]

        if npcs:
            lines.append("CHARACTERS:")
            for entry in npcs:
                lines.append(f"  {entry.format_for_prompt()}")
            lines.append("")

        if items:
            lines.append("ITEMS:")
            for entry in items:
                lines.append(f"  {entry.format_for_prompt()}")
            lines.append("")

        if storages:
            lines.append("CONTAINERS:")
            for entry in storages:
                lines.append(f"  {entry.format_for_prompt()}")
            lines.append("")

        # Exits without refs (use location key directly)
        if self.exit_displays:
            lines.append("EXITS:")
            for key, display in self.exit_displays.items():
                # If exits have refs, show them; otherwise show key
                if key in self.entries:
                    entry = self.entries[key]
                    lines.append(f"  [{entry.ref}] {display}")
                else:
                    lines.append(f"  -> {display} (use: \"{key}\")")
            lines.append("")

        return "\n".join(lines).strip()

    def all_refs(self) -> list[str]:
        """Get all valid refs.

        Returns:
            List of all ref letters in order.
        """
        return list(self.entries.keys())

    def entity_count(self) -> int:
        """Get total number of entities with refs.

        Returns:
            Number of entities (excluding exits if not ref'd).
        """
        return len(self.entries)


class _RefGenerator:
    """Generates sequential refs: A, B, C... Z, A1, B1... Z1, A2..."""

    def __init__(self) -> None:
        self._index = 0

    def next_ref(self) -> str:
        """Get the next ref in sequence.

        Returns:
            Next ref like "A", "B", ... "Z", "A1", "B1", etc.
        """
        letter_index = self._index % 26
        overflow = self._index // 26

        letter = chr(ord("A") + letter_index)
        ref = letter if overflow == 0 else f"{letter}{overflow}"

        self._index += 1
        return ref


def _get_location_hint(entity: GroundedEntity, default: str) -> str:
    """Extract location hint from entity description or use default.

    Args:
        entity: Entity to get hint for.
        default: Default hint if none found.

    Returns:
        Location hint string.
    """
    # Could parse entity.short_description for location info
    # For now, just use the default
    return default
