"""Delta Translator for the Quantum Pipeline (Phase 3).

Phase 3 of the split architecture. Converts semantic outcomes to state deltas.
This is DETERMINISTIC CODE - no LLM calls.

Responsibilities:
1. Generate entity keys for new things (display name → unique key)
2. Ensure CREATE deltas come before TRANSFER/UPDATE
3. Map display names to entity keys
4. Validate against the grounding manifest
5. Build StateDelta objects for the collapse phase

The key insight is that the reasoning model (Phase 2) works with display names,
and this translator converts them to entity keys that the database understands.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime

from src.world_server.quantum.reasoning import (
    SemanticOutcome,
    SemanticChange,
    time_description_to_minutes,
)
from src.world_server.quantum.schemas import (
    StateDelta,
    DeltaType,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Key Mapping Result
# =============================================================================


@dataclass
class TranslationResult:
    """Result of translating a semantic outcome to state deltas.

    Contains both the ordered deltas and the key mapping for narration.
    """

    deltas: list[StateDelta]
    key_mapping: dict[str, str]  # display_name -> entity_key
    time_minutes: int
    errors: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Check if translation had errors."""
        return len(self.errors) > 0


# =============================================================================
# Grounding Manifest Interface
# =============================================================================


@dataclass
class ManifestContext:
    """Context from the grounding manifest for translation.

    Provides existing entity keys so we can resolve references
    and avoid creating duplicates.
    """

    # Existing entities by display name (lowercase)
    npcs: dict[str, str]  # display_name.lower() -> entity_key
    items: dict[str, str]  # display_name.lower() -> entity_key
    locations: dict[str, str]  # display_name.lower() -> location_key

    # Current location
    current_location_key: str

    # Player key
    player_key: str = "player"

    def get_npc_key(self, display_name: str) -> str | None:
        """Get entity key for an NPC by display name."""
        return self.npcs.get(display_name.lower())

    def get_item_key(self, display_name: str) -> str | None:
        """Get entity key for an item by display name."""
        return self.items.get(display_name.lower())

    def get_location_key(self, display_name: str) -> str | None:
        """Get location key by display name."""
        return self.locations.get(display_name.lower())

    def resolve_target(self, display_name: str) -> str | None:
        """Try to resolve a display name to any known entity key."""
        lower = display_name.lower()

        # Check player references
        if lower in ("player", "the player", "you", "yourself"):
            return self.player_key

        # Check NPCs first (most common target)
        if key := self.npcs.get(lower):
            return key

        # Check items
        if key := self.items.get(lower):
            return key

        # Check locations
        if key := self.locations.get(lower):
            return key

        return None


# =============================================================================
# Key Generator
# =============================================================================


class EntityKeyGenerator:
    """Generates unique entity keys from display names.

    Keys follow the pattern: type_normalized-name_timestamp
    Example: "a mug of honeyed ale" -> "item_honeyed_ale_1704067200"
    """

    def __init__(self) -> None:
        """Initialize with timestamp for uniqueness."""
        self._counter = 0
        self._base_timestamp = int(datetime.now().timestamp())

    def generate_item_key(self, display_name: str) -> str:
        """Generate a unique key for an item."""
        normalized = self._normalize_name(display_name)
        self._counter += 1
        return f"item_{normalized}_{self._base_timestamp}_{self._counter:03d}"

    def generate_npc_key(self, display_name: str) -> str:
        """Generate a unique key for an NPC."""
        normalized = self._normalize_name(display_name)
        self._counter += 1
        return f"npc_{normalized}_{self._base_timestamp}_{self._counter:03d}"

    def generate_location_key(self, display_name: str) -> str:
        """Generate a unique key for a location."""
        normalized = self._normalize_name(display_name)
        self._counter += 1
        return f"loc_{normalized}_{self._base_timestamp}_{self._counter:03d}"

    def _normalize_name(self, name: str) -> str:
        """Normalize display name to valid key component.

        - Remove articles (a, an, the)
        - Convert to lowercase
        - Replace spaces with underscores
        - Remove special characters
        - Truncate to reasonable length
        """
        # Remove common articles
        lower = name.lower().strip()
        for article in ("a ", "an ", "the ", "some "):
            if lower.startswith(article):
                lower = lower[len(article) :]

        # Keep only alphanumeric and spaces
        cleaned = re.sub(r"[^a-z0-9\s]", "", lower)

        # Replace spaces with underscores
        key = re.sub(r"\s+", "_", cleaned.strip())

        # Truncate to reasonable length
        if len(key) > 30:
            key = key[:30]

        return key or "unknown"


# =============================================================================
# Delta Translator
# =============================================================================


@dataclass
class DeltaTranslator:
    """Translates semantic outcomes to state deltas.

    This is the bridge between LLM reasoning (display names) and
    the database (entity keys). It:
    1. Generates keys for new entities
    2. Resolves existing entities via manifest
    3. Creates properly ordered StateDelta objects
    4. Validates references exist
    """

    key_generator: EntityKeyGenerator = field(default_factory=EntityKeyGenerator)

    def translate(
        self,
        outcome: SemanticOutcome,
        manifest: ManifestContext,
    ) -> TranslationResult:
        """Translate a semantic outcome to state deltas.

        Args:
            outcome: The semantic outcome from the reasoning engine.
            manifest: Context for resolving existing entities.

        Returns:
            TranslationResult with ordered deltas and key mapping.
        """
        errors: list[str] = []
        key_mapping: dict[str, str] = {}
        create_deltas: list[StateDelta] = []
        other_deltas: list[StateDelta] = []

        # Phase 1: Generate keys for new things
        for new_thing in outcome.new_things:
            if new_thing not in key_mapping:
                key = self.key_generator.generate_item_key(new_thing)
                key_mapping[new_thing] = key

                # Create CREATE_ENTITY delta for new items
                create_deltas.append(
                    StateDelta(
                        delta_type=DeltaType.CREATE_ENTITY,
                        target_key=key,
                        changes={
                            "entity_type": "item",
                            "display_name": new_thing,
                            "location_key": manifest.current_location_key,
                        },
                    )
                )

        # Phase 2: Process semantic changes
        for change in outcome.changes:
            delta = self._translate_change(change, manifest, key_mapping, errors)
            if delta:
                if delta.delta_type == DeltaType.CREATE_ENTITY:
                    create_deltas.append(delta)
                else:
                    other_deltas.append(delta)

        # Phase 3: Add time delta if significant
        time_minutes = time_description_to_minutes(outcome.time_description)
        if time_minutes > 0:
            other_deltas.append(
                StateDelta(
                    delta_type=DeltaType.ADVANCE_TIME,
                    target_key="time",
                    changes={"minutes": time_minutes},
                )
            )

        # Combine: CREATE deltas first, then others
        ordered_deltas = create_deltas + other_deltas

        return TranslationResult(
            deltas=ordered_deltas,
            key_mapping=key_mapping,
            time_minutes=time_minutes,
            errors=errors,
        )

    def _translate_change(
        self,
        change: SemanticChange,
        manifest: ManifestContext,
        key_mapping: dict[str, str],
        errors: list[str],
    ) -> StateDelta | None:
        """Translate a single semantic change to a state delta."""
        change_type = change.change_type.lower()

        if change_type == "give_item":
            return self._translate_give_item(change, manifest, key_mapping, errors)
        elif change_type == "take_item":
            return self._translate_take_item(change, manifest, key_mapping, errors)
        elif change_type == "create_item":
            return self._translate_create_item(change, manifest, key_mapping, errors)
        elif change_type == "destroy_item":
            return self._translate_destroy_item(change, manifest, key_mapping, errors)
        elif change_type == "move_entity":
            return self._translate_move_entity(change, manifest, key_mapping, errors)
        elif change_type == "learn_info":
            return self._translate_learn_info(change, manifest, key_mapping, errors)
        elif change_type == "change_relationship":
            return self._translate_change_relationship(
                change, manifest, key_mapping, errors
            )
        elif change_type == "change_state":
            return self._translate_change_state(change, manifest, key_mapping, errors)
        else:
            errors.append(f"Unknown change type: {change_type}")
            return None

    def _translate_give_item(
        self,
        change: SemanticChange,
        manifest: ManifestContext,
        key_mapping: dict[str, str],
        errors: list[str],
    ) -> StateDelta | None:
        """Translate give_item to TRANSFER_ITEM delta."""
        # Resolve item key
        item_key = None
        if change.object_involved:
            item_key = key_mapping.get(change.object_involved)
            if not item_key:
                item_key = manifest.get_item_key(change.object_involved)

        if not item_key:
            errors.append(
                f"Cannot resolve item for give_item: {change.object_involved}"
            )
            return None

        # Resolve target (recipient)
        target_key = manifest.player_key  # Default to player
        if change.target:
            resolved = manifest.resolve_target(change.target)
            if resolved:
                target_key = resolved

        return StateDelta(
            delta_type=DeltaType.TRANSFER_ITEM,
            target_key=item_key,
            changes={
                "to_entity": target_key,
                "from_entity": (
                    manifest.resolve_target(change.actor) if change.actor else None
                ),
            },
        )

    def _translate_take_item(
        self,
        change: SemanticChange,
        manifest: ManifestContext,
        key_mapping: dict[str, str],
        errors: list[str],
    ) -> StateDelta | None:
        """Translate take_item to TRANSFER_ITEM delta."""
        item_key = None
        if change.object_involved:
            item_key = key_mapping.get(change.object_involved)
            if not item_key:
                item_key = manifest.get_item_key(change.object_involved)

        if not item_key:
            errors.append(
                f"Cannot resolve item for take_item: {change.object_involved}"
            )
            return None

        # Actor takes the item (usually player)
        taker_key = manifest.player_key
        if change.actor:
            resolved = manifest.resolve_target(change.actor)
            if resolved:
                taker_key = resolved

        return StateDelta(
            delta_type=DeltaType.TRANSFER_ITEM,
            target_key=item_key,
            changes={
                "to_entity": taker_key,
                "from_location": manifest.current_location_key,
            },
        )

    def _translate_create_item(
        self,
        change: SemanticChange,
        manifest: ManifestContext,
        key_mapping: dict[str, str],
        errors: list[str],
    ) -> StateDelta | None:
        """Translate create_item to CREATE_ENTITY delta."""
        display_name = change.object_involved or change.description
        if not display_name:
            errors.append("create_item requires object_involved or description")
            return None

        # Check if already in mapping (from new_things)
        if display_name in key_mapping:
            return None  # Already handled

        # Generate new key
        key = self.key_generator.generate_item_key(display_name)
        key_mapping[display_name] = key

        return StateDelta(
            delta_type=DeltaType.CREATE_ENTITY,
            target_key=key,
            changes={
                "entity_type": "item",
                "display_name": display_name,
                "location_key": manifest.current_location_key,
            },
        )

    def _translate_destroy_item(
        self,
        change: SemanticChange,
        manifest: ManifestContext,
        key_mapping: dict[str, str],
        errors: list[str],
    ) -> StateDelta | None:
        """Translate destroy_item to DELETE_ENTITY delta."""
        item_key = None
        if change.object_involved:
            item_key = key_mapping.get(change.object_involved)
            if not item_key:
                item_key = manifest.get_item_key(change.object_involved)

        if not item_key:
            errors.append(
                f"Cannot resolve item for destroy_item: {change.object_involved}"
            )
            return None

        return StateDelta(
            delta_type=DeltaType.DELETE_ENTITY,
            target_key=item_key,
            changes={"reason": change.description},
        )

    def _translate_move_entity(
        self,
        change: SemanticChange,
        manifest: ManifestContext,
        key_mapping: dict[str, str],
        errors: list[str],
    ) -> StateDelta | None:
        """Translate move_entity to UPDATE_LOCATION delta."""
        # Who is moving?
        entity_key = manifest.player_key
        if change.actor:
            resolved = manifest.resolve_target(change.actor)
            if resolved:
                entity_key = resolved

        # Where to?
        target_location = change.target
        if not target_location:
            errors.append("move_entity requires target location")
            return None

        # Try to resolve location key
        location_key = manifest.get_location_key(target_location)
        if not location_key:
            # Use the display name as-is, collapse phase will validate
            location_key = target_location.lower().replace(" ", "_")

        return StateDelta(
            delta_type=DeltaType.UPDATE_LOCATION,
            target_key=entity_key,
            changes={"location_key": location_key},
        )

    def _translate_learn_info(
        self,
        change: SemanticChange,
        manifest: ManifestContext,
        key_mapping: dict[str, str],
        errors: list[str],
    ) -> StateDelta | None:
        """Translate learn_info to RECORD_FACT delta."""
        return StateDelta(
            delta_type=DeltaType.RECORD_FACT,
            target_key=manifest.player_key,
            changes={
                "subject": change.actor or "world",
                "predicate": "knows",
                "value": change.description,
            },
        )

    def _translate_change_relationship(
        self,
        change: SemanticChange,
        manifest: ManifestContext,
        key_mapping: dict[str, str],
        errors: list[str],
    ) -> StateDelta | None:
        """Translate change_relationship to UPDATE_RELATIONSHIP delta."""
        # Who is the relationship with?
        target_key = None
        if change.target:
            target_key = manifest.resolve_target(change.target)

        if not target_key:
            errors.append(f"Cannot resolve target for relationship: {change.target}")
            return None

        # Parse relationship change from description
        # This is a simplified parser - could be enhanced
        delta_value = 5  # Default small positive change
        if "worse" in change.description.lower() or "angry" in change.description.lower():
            delta_value = -10
        elif "better" in change.description.lower() or "friendly" in change.description.lower():
            delta_value = 10
        elif "trust" in change.description.lower():
            delta_value = 5

        return StateDelta(
            delta_type=DeltaType.UPDATE_RELATIONSHIP,
            target_key=target_key,
            changes={
                "from_entity": manifest.player_key,
                "delta_trust": delta_value,
                "reason": change.description,
            },
        )

    def _translate_change_state(
        self,
        change: SemanticChange,
        manifest: ManifestContext,
        key_mapping: dict[str, str],
        errors: list[str],
    ) -> StateDelta | None:
        """Translate change_state to UPDATE_ENTITY delta."""
        target_key = None
        if change.target:
            target_key = key_mapping.get(change.target)
            if not target_key:
                target_key = manifest.resolve_target(change.target)

        if not target_key:
            errors.append(f"Cannot resolve target for state change: {change.target}")
            return None

        return StateDelta(
            delta_type=DeltaType.UPDATE_ENTITY,
            target_key=target_key,
            changes={
                "state_change": change.description,
            },
        )


# =============================================================================
# Helper Functions
# =============================================================================


def create_manifest_context(
    npcs: dict[str, str],
    items: dict[str, str],
    locations: dict[str, str],
    current_location_key: str,
    player_key: str = "player",
) -> ManifestContext:
    """Create a ManifestContext from dictionaries.

    Args:
        npcs: Display name -> entity key mapping for NPCs.
        items: Display name -> entity key mapping for items.
        locations: Display name -> location key mapping.
        current_location_key: Key of current location.
        player_key: Key of the player entity.

    Returns:
        ManifestContext ready for translation.
    """
    return ManifestContext(
        npcs={k.lower(): v for k, v in npcs.items()},
        items={k.lower(): v for k, v in items.items()},
        locations={k.lower(): v for k, v in locations.items()},
        current_location_key=current_location_key,
        player_key=player_key,
    )


# =============================================================================
# Ref-Based Delta Translator (New Architecture)
# =============================================================================


@dataclass
class RefDeltaTranslator:
    """Translates ref-based outcomes to state deltas.

    This is the ref-based version of DeltaTranslator. Key differences:
    - Uses direct ref lookup (no fuzzy matching)
    - Invalid refs produce errors (no guessing)
    - Refs are resolved via RefManifest

    This is DETERMINISTIC CODE - no LLM calls.
    """

    key_generator: EntityKeyGenerator = field(default_factory=EntityKeyGenerator)

    def translate(
        self,
        outcome: "RefBasedOutcome",
        manifest: "RefManifest",
    ) -> TranslationResult:
        """Translate a ref-based outcome to state deltas.

        Args:
            outcome: RefBasedOutcome from the reasoning engine.
            manifest: RefManifest for resolving refs to entity keys.

        Returns:
            TranslationResult with ordered deltas and key mapping.
        """
        from src.world_server.quantum.reasoning import RefBasedOutcome
        from src.world_server.quantum.ref_manifest import RefManifest

        errors: list[str] = []
        key_mapping: dict[str, str] = {}  # ref -> entity_key
        create_deltas: list[StateDelta] = []
        other_deltas: list[StateDelta] = []

        # Process each change
        for change in outcome.changes:
            delta = self._translate_change(change, manifest, key_mapping, errors)
            if delta:
                if delta.delta_type == DeltaType.CREATE_ENTITY:
                    create_deltas.append(delta)
                else:
                    other_deltas.append(delta)

        # Add time delta if significant
        time_minutes = time_description_to_minutes(outcome.time_description)
        if time_minutes > 0:
            other_deltas.append(
                StateDelta(
                    delta_type=DeltaType.ADVANCE_TIME,
                    target_key="time",
                    changes={"minutes": time_minutes},
                )
            )

        # Combine: CREATE deltas first, then others
        ordered_deltas = create_deltas + other_deltas

        return TranslationResult(
            deltas=ordered_deltas,
            key_mapping=key_mapping,
            time_minutes=time_minutes,
            errors=errors,
        )

    def _resolve_ref(
        self,
        ref: str | None,
        manifest: "RefManifest",
        errors: list[str],
        context: str = "entity",
    ) -> str | None:
        """Resolve a ref to an entity key.

        This is a DIRECT lookup - no fuzzy matching.
        Invalid refs produce errors.

        Args:
            ref: The ref to resolve (e.g., "A", "B").
            manifest: RefManifest for lookups.
            errors: List to append errors to.
            context: Context for error messages.

        Returns:
            Entity key if found, None otherwise.
        """
        from src.world_server.quantum.ref_manifest import RefManifest

        if not ref:
            return None

        # Handle "player" as a special case
        if ref.lower() in ("player", "the player", "you", "yourself"):
            return manifest.player_key

        # Direct ref lookup
        entry = manifest.resolve_ref(ref)
        if entry is None:
            errors.append(f"Invalid ref '{ref}' for {context} - not in manifest")
            return None

        return entry.entity_key

    def _translate_change(
        self,
        change: "RefBasedChange",
        manifest: "RefManifest",
        key_mapping: dict[str, str],
        errors: list[str],
    ) -> StateDelta | None:
        """Translate a single ref-based change to a state delta."""
        from src.world_server.quantum.reasoning import RefBasedChange
        from src.world_server.quantum.ref_manifest import RefManifest

        change_type = change.change_type.lower()

        if change_type == "take_item":
            return self._translate_take_item(change, manifest, key_mapping, errors)
        elif change_type == "give_item":
            return self._translate_give_item(change, manifest, key_mapping, errors)
        elif change_type == "destroy_item":
            return self._translate_destroy_item(change, manifest, key_mapping, errors)
        elif change_type == "change_state":
            return self._translate_change_state(change, manifest, key_mapping, errors)
        elif change_type == "change_relationship":
            return self._translate_change_relationship(change, manifest, key_mapping, errors)
        elif change_type == "advance_time":
            return self._translate_advance_time(change, manifest, key_mapping, errors)
        elif change_type == "move_to":
            return self._translate_move_to(change, manifest, key_mapping, errors)
        elif change_type == "learn_info":
            return self._translate_learn_info(change, manifest, key_mapping, errors)
        elif change_type == "update_need":
            return self._translate_update_need(change, manifest, key_mapping, errors)
        elif change_type == "create_entity":
            return self._translate_create_entity(change, manifest, key_mapping, errors)
        else:
            errors.append(f"Unknown change type: {change_type}")
            return None

    def _translate_take_item(
        self,
        change: "RefBasedChange",
        manifest: "RefManifest",
        key_mapping: dict[str, str],
        errors: list[str],
    ) -> StateDelta | None:
        """Translate take_item to TRANSFER_ITEM delta."""
        item_key = self._resolve_ref(change.entity, manifest, errors, "take_item entity")
        if not item_key:
            return None

        # Store in key_mapping
        if change.entity:
            key_mapping[change.entity] = item_key

        return StateDelta(
            delta_type=DeltaType.TRANSFER_ITEM,
            target_key=item_key,
            changes={
                "to_entity_key": manifest.player_key,
                "from_location_key": manifest.location_key,
            },
        )

    def _translate_give_item(
        self,
        change: "RefBasedChange",
        manifest: "RefManifest",
        key_mapping: dict[str, str],
        errors: list[str],
    ) -> StateDelta | None:
        """Translate give_item to TRANSFER_ITEM delta."""
        item_key = self._resolve_ref(change.entity, manifest, errors, "give_item entity")
        if not item_key:
            return None

        # Store in key_mapping
        if change.entity:
            key_mapping[change.entity] = item_key

        # Resolve source and target
        from_key = self._resolve_ref(change.from_entity, manifest, errors, "give_item from")
        to_key = self._resolve_ref(change.to_entity, manifest, errors, "give_item to")

        # Default to player if not specified
        if not to_key:
            to_key = manifest.player_key

        return StateDelta(
            delta_type=DeltaType.TRANSFER_ITEM,
            target_key=item_key,
            changes={
                "to_entity_key": to_key,
                "from_entity_key": from_key,
            },
        )

    def _translate_destroy_item(
        self,
        change: "RefBasedChange",
        manifest: "RefManifest",
        key_mapping: dict[str, str],
        errors: list[str],
    ) -> StateDelta | None:
        """Translate destroy_item to DELETE_ENTITY delta."""
        item_key = self._resolve_ref(change.entity, manifest, errors, "destroy_item entity")
        if not item_key:
            return None

        return StateDelta(
            delta_type=DeltaType.DELETE_ENTITY,
            target_key=item_key,
            changes={"reason": "destroyed"},
        )

    def _translate_change_state(
        self,
        change: "RefBasedChange",
        manifest: "RefManifest",
        key_mapping: dict[str, str],
        errors: list[str],
    ) -> StateDelta | None:
        """Translate change_state to UPDATE_ENTITY delta."""
        entity_key = self._resolve_ref(change.entity, manifest, errors, "change_state entity")
        if not entity_key:
            return None

        return StateDelta(
            delta_type=DeltaType.UPDATE_ENTITY,
            target_key=entity_key,
            changes={"state_change": change.new_state or "changed"},
        )

    def _translate_change_relationship(
        self,
        change: "RefBasedChange",
        manifest: "RefManifest",
        key_mapping: dict[str, str],
        errors: list[str],
    ) -> StateDelta | None:
        """Translate change_relationship to UPDATE_RELATIONSHIP delta."""
        npc_key = self._resolve_ref(change.npc, manifest, errors, "relationship npc")
        if not npc_key:
            return None

        # Parse delta from the delta field
        delta_value = self._parse_relationship_delta(change.delta)

        return StateDelta(
            delta_type=DeltaType.UPDATE_RELATIONSHIP,
            target_key=npc_key,
            changes={
                "from_entity": manifest.player_key,
                "delta_trust": delta_value,
                "reason": change.delta or "interaction",
            },
        )

    def _parse_relationship_delta(self, delta: str | None) -> int:
        """Parse relationship delta string to numeric value."""
        if not delta:
            return 5  # Default small positive

        lower = delta.lower()

        # Check for explicit +/- values
        if delta.startswith("+") or delta.startswith("-"):
            # Try to extract number
            import re
            match = re.search(r"[+-]?\d+", delta)
            if match:
                return int(match.group())

        # Keyword-based parsing
        if "trust" in lower:
            return 10 if "+" in delta or "increase" in lower else -10
        if "respect" in lower:
            return 8 if "+" in delta or "increase" in lower else -8
        if "like" in lower or "liking" in lower:
            return 5 if "+" in delta or "increase" in lower else -5
        if "worse" in lower or "decrease" in lower or "-" in delta:
            return -10
        if "better" in lower or "increase" in lower or "+" in delta:
            return 10

        return 5  # Default

    def _translate_advance_time(
        self,
        change: "RefBasedChange",
        manifest: "RefManifest",
        key_mapping: dict[str, str],
        errors: list[str],
    ) -> StateDelta | None:
        """Translate advance_time to ADVANCE_TIME delta."""
        duration = change.duration or "a moment"
        minutes = time_description_to_minutes(duration)

        return StateDelta(
            delta_type=DeltaType.ADVANCE_TIME,
            target_key="time",
            changes={"minutes": minutes},
        )

    def _translate_move_to(
        self,
        change: "RefBasedChange",
        manifest: "RefManifest",
        key_mapping: dict[str, str],
        errors: list[str],
    ) -> StateDelta | None:
        """Translate move_to to UPDATE_LOCATION delta."""
        destination = change.destination
        if not destination:
            errors.append("move_to requires destination")
            return None

        # Try to resolve via exit_refs
        location_key = manifest.resolve_exit(destination)
        if not location_key:
            # Use as-is (will be validated during collapse)
            location_key = destination

        return StateDelta(
            delta_type=DeltaType.UPDATE_LOCATION,
            target_key=manifest.player_key,
            changes={"location_key": location_key},
        )

    def _translate_learn_info(
        self,
        change: "RefBasedChange",
        manifest: "RefManifest",
        key_mapping: dict[str, str],
        errors: list[str],
    ) -> StateDelta | None:
        """Translate learn_info to RECORD_FACT delta."""
        fact = change.fact
        if not fact:
            errors.append("learn_info requires fact")
            return None

        return StateDelta(
            delta_type=DeltaType.RECORD_FACT,
            target_key=manifest.player_key,
            changes={
                "subject": manifest.player_key,
                "predicate": "knows",
                "value": fact,
            },
        )

    def _translate_update_need(
        self,
        change: "RefBasedChange",
        manifest: "RefManifest",
        key_mapping: dict[str, str],
        errors: list[str],
    ) -> StateDelta | None:
        """Translate update_need to UPDATE_NEED delta."""
        need = change.need
        if not need:
            errors.append("update_need requires need")
            return None

        # Parse the change value
        delta_value = self._parse_need_change(change.need_change)

        return StateDelta(
            delta_type=DeltaType.UPDATE_NEED,
            target_key=manifest.player_key,
            changes={
                "need_name": need,
                "delta_value": delta_value,
                "reason": change.need_change or "changed",
            },
        )

    def _parse_need_change(self, change: str | None) -> int:
        """Parse need change string to numeric delta."""
        if not change:
            return -10  # Default moderate decrease (needs satisfied)

        lower = change.lower()

        if "rested" in lower or "fully" in lower:
            return -100  # Full reset
        if "satisfied" in lower or "full" in lower:
            return -100
        if "increase" in lower or "hungry" in lower or "tired" in lower:
            return 20  # Need increases
        if "decrease" in lower or "less" in lower:
            return -20

        return -10  # Default moderate satisfaction

    # Valid entity types for CREATE_ENTITY
    # Maps LLM output -> valid type for collapse.py routing
    VALID_ENTITY_TYPES = {
        # Entity types (go to EntityManager)
        "npc": "npc",
        "monster": "monster",
        "animal": "animal",
        # Item types (go to ItemManager)
        "item": "item",
        "object": "item",  # "object" is a generic item
        "weapon": "weapon",
        "armor": "armor",
        "tool": "tool",
        "food": "food",
        "drink": "drink",
        "clothing": "clothing",
        "container": "container",
        "key": "key",
        # Location type (go to LocationManager)
        "location": "location",
        "room": "location",
        "place": "location",
    }

    def _translate_create_entity(
        self,
        change: "RefBasedChange",
        manifest: "RefManifest",
        key_mapping: dict[str, str],
        errors: list[str],
    ) -> StateDelta | None:
        """Translate create_entity to CREATE_ENTITY delta."""
        description = change.description
        if not description:
            errors.append("create_entity requires description")
            return None

        raw_type = (change.entity_type or "item").lower()

        # Validate and normalize entity_type
        entity_type = self.VALID_ENTITY_TYPES.get(raw_type)
        if entity_type is None:
            # Unknown type - default to item with warning
            logger.warning(
                f"Unknown entity_type '{raw_type}' for create_entity, defaulting to 'item'"
            )
            entity_type = "item"

        # Generate appropriate key based on type
        if entity_type == "npc":
            key = self.key_generator.generate_npc_key(description)
        elif entity_type == "location":
            key = self.key_generator.generate_location_key(description)
        else:
            key = self.key_generator.generate_item_key(description)

        # Store in key_mapping with description as key
        key_mapping[description] = key

        return StateDelta(
            delta_type=DeltaType.CREATE_ENTITY,
            target_key=key,
            changes={
                "entity_type": entity_type,
                "display_name": description,
                "location_key": manifest.location_key,
            },
        )
