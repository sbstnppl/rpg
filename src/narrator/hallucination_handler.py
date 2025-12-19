"""Intelligent hallucination handler for narrative validation.

Instead of always rejecting hallucinated items, this module categorizes them
and can spawn reasonable environmental items to make the narrative valid.

Philosophy: Like a GM who says "actually yeah, there would be a washbasin there"
rather than rejecting the narrative outright.

Note: The categorize_item() and analyze_hallucinations() functions are
DEPRECATED in favor of LLM-based item extraction via ItemExtractor.
The new system uses ItemImportance (IMPORTANT, DECORATIVE, REFERENCE)
instead of HallucinationCategory (SPAWN_ALLOWED, SPAWN_FORBIDDEN, UNKNOWN).

The spawn_hallucinated_items() function is still used for spawning items.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from src.database.models.session import GameSession

logger = logging.getLogger(__name__)


class HallucinationCategory(str, Enum):
    """Categories for hallucinated items."""

    # Can be spawned - common environmental items
    SPAWN_ALLOWED = "spawn_allowed"

    # Cannot be spawned - threats, NPCs, valuables, quest items
    SPAWN_FORBIDDEN = "spawn_forbidden"

    # Unknown - not in either list, treat as forbidden for safety
    UNKNOWN = "unknown"


# Items that CAN be spawned as environmental details
# These are common items that would reasonably exist in most locations
SPAWNABLE_ITEMS = {
    # Washing/cleaning
    "washbasin", "basin", "bucket", "tub", "pitcher", "jug",
    "soap", "towel", "cloth", "rag", "sponge",
    # Lighting
    "candle", "candles", "candlestick", "lantern", "lamp", "torch",
    # Furniture (common)
    "chair", "stool", "bench", "table", "desk", "shelf", "shelves",
    "bed", "cot", "mattress", "pillow", "blanket",
    # Containers
    "box", "crate", "barrel", "basket", "sack", "bag",
    "chest", "trunk", "cabinet", "cupboard", "drawer",
    # Kitchen/dining
    "pot", "pan", "kettle", "bowl", "plate", "cup", "mug",
    "spoon", "fork", "knife", "ladle",
    # Common tools
    "broom", "mop", "rake", "shovel", "axe", "hammer", "saw",
    "rope", "twine", "string", "hook", "nail", "peg",
    # Writing/reading
    "paper", "parchment", "quill", "ink", "book", "scroll",
    # Misc common
    "mirror", "brush", "comb", "needle", "thread",
    "firewood", "kindling", "ash", "coal",
}

# Items that should NEVER be spawned - too significant
FORBIDDEN_ITEMS = {
    # Threats/creatures
    "dragon", "monster", "beast", "wolf", "bear", "snake", "spider",
    "demon", "ghost", "undead", "skeleton", "zombie",
    "bandit", "thief", "assassin", "enemy", "attacker",
    # NPCs (never spawn people)
    "guard", "soldier", "knight", "warrior", "fighter",
    "merchant", "vendor", "shopkeeper", "innkeeper",
    "stranger", "traveler", "visitor", "man", "woman", "person",
    "child", "boy", "girl", "elder", "old man", "old woman",
    # Valuable items
    "gold", "silver", "coin", "coins", "money", "treasure",
    "gem", "jewel", "diamond", "ruby", "emerald", "sapphire",
    "crown", "scepter", "throne",
    # Magic items
    "wand", "staff", "orb", "crystal", "amulet", "talisman",
    "potion", "elixir", "scroll", "spellbook", "artifact",
    # Weapons (should be placed intentionally)
    "sword", "dagger", "bow", "arrow", "arrows", "spear",
    "shield", "armor", "helmet", "gauntlet",
}


@dataclass
class HallucinationAnalysis:
    """Result of analyzing hallucinated items."""

    # Items that can be spawned
    spawnable: list[str] = field(default_factory=list)

    # Items that cannot be spawned (add to constraints)
    forbidden: list[str] = field(default_factory=list)

    # Overall recommendation
    can_fix_by_spawning: bool = False

    @property
    def needs_renarration(self) -> bool:
        """Whether re-narration is needed (has forbidden items)."""
        return len(self.forbidden) > 0


def categorize_item(item_name: str) -> HallucinationCategory:
    """Categorize a hallucinated item.

    DEPRECATED: Use ItemExtractor for LLM-based item extraction instead.
    This function uses hardcoded word lists which produce false positives.

    Args:
        item_name: The item name (lowercase).

    Returns:
        Category for the item.
    """
    import re

    item_lower = item_name.lower().strip()

    # Check forbidden list FIRST (more restrictive)
    if item_lower in FORBIDDEN_ITEMS:
        return HallucinationCategory.SPAWN_FORBIDDEN

    # Check for word-boundary matches in forbidden
    # (e.g., "the dragon" contains "dragon" as a word)
    for forbidden in FORBIDDEN_ITEMS:
        # Use word boundary matching to avoid "dragon" matching "rag"
        if re.search(rf'\b{re.escape(forbidden)}\b', item_lower):
            return HallucinationCategory.SPAWN_FORBIDDEN

    # Check spawnable list
    if item_lower in SPAWNABLE_ITEMS:
        return HallucinationCategory.SPAWN_ALLOWED

    # Check for word-boundary matches in spawnable
    # (e.g., "old washbasin" contains "washbasin" as a word)
    for spawnable in SPAWNABLE_ITEMS:
        if re.search(rf'\b{re.escape(spawnable)}\b', item_lower):
            return HallucinationCategory.SPAWN_ALLOWED

    # Unknown - treat as forbidden for safety
    logger.debug(f"Unknown hallucinated item, treating as forbidden: {item_name}")
    return HallucinationCategory.UNKNOWN


def analyze_hallucinations(hallucinated_items: list[str]) -> HallucinationAnalysis:
    """Analyze a list of hallucinated items.

    DEPRECATED: Use ItemExtractor for LLM-based item extraction instead.
    This function uses hardcoded word lists which produce false positives.

    Args:
        hallucinated_items: List of hallucinated item names.

    Returns:
        Analysis with categorized items and recommendation.
    """
    analysis = HallucinationAnalysis()

    for item in hallucinated_items:
        category = categorize_item(item)

        if category == HallucinationCategory.SPAWN_ALLOWED:
            analysis.spawnable.append(item)
        else:
            analysis.forbidden.append(item)

    # Can fix by spawning if ALL items are spawnable
    analysis.can_fix_by_spawning = (
        len(analysis.spawnable) > 0 and len(analysis.forbidden) == 0
    )

    return analysis


def spawn_hallucinated_items(
    db: Session,
    game_session: GameSession,
    items: list[str],
    location_key: str,
    context: str = "",
) -> list[dict[str, Any]]:
    """Spawn hallucinated items that are reasonable for the context.

    Args:
        db: Database session.
        game_session: Current game session.
        items: List of item names to spawn.
        location_key: Current location key.
        context: Context for item generation (e.g., "washbasin near well").

    Returns:
        List of spawned item info dicts.
    """
    from src.services.emergent_item_generator import EmergentItemGenerator, ItemConstraints

    spawned = []
    generator = EmergentItemGenerator(db, game_session)

    for item_name in items:
        try:
            # Determine item type from name
            item_type = _infer_item_type(item_name)

            # Build context
            item_context = f"{item_name} in {location_key}"
            if context:
                item_context = f"{item_name} - {context}"

            # Create constraints
            constraints = ItemConstraints(
                name=item_name.title(),
                quality="common",
                condition="good",
            )

            # Spawn the item
            item_state = generator.create_item(
                item_type=item_type,
                context=item_context,
                location_key=location_key,
                constraints=constraints,
            )

            spawned.append({
                "item_key": item_state.item_key,
                "display_name": item_state.display_name,
                "item_type": item_state.item_type,
                "spawned_reason": "hallucination_fix",
            })

            logger.info(
                f"Spawned hallucinated item: {item_state.display_name} "
                f"({item_state.item_key}) at {location_key}"
            )

        except Exception as e:
            logger.warning(f"Failed to spawn hallucinated item '{item_name}': {e}")

    return spawned


def _infer_item_type(item_name: str) -> str:
    """Infer item type from item name.

    Args:
        item_name: The item name.

    Returns:
        Item type string.
    """
    item_lower = item_name.lower()

    # Containers
    if any(x in item_lower for x in ["box", "crate", "barrel", "basket", "chest", "trunk"]):
        return "container"

    # Furniture
    if any(x in item_lower for x in ["chair", "table", "desk", "bed", "shelf", "bench", "stool"]):
        return "furniture"

    # Tools
    if any(x in item_lower for x in ["hammer", "saw", "axe", "shovel", "rake", "broom"]):
        return "tool"

    # Kitchen
    if any(x in item_lower for x in ["pot", "pan", "kettle", "bowl", "plate", "cup"]):
        return "container"  # Kitchen items are often containers

    # Default to misc
    return "misc"


def spawn_extracted_items(
    db: Session,
    game_session: GameSession,
    items: list,  # list[ExtractedItem]
    location_key: str,
) -> list[dict[str, Any]]:
    """Spawn items from ExtractedItem objects.

    Convenience wrapper for spawn_hallucinated_items that accepts
    ExtractedItem objects instead of plain strings.

    Args:
        db: Database session.
        game_session: Current game session.
        items: List of ExtractedItem objects to spawn.
        location_key: Current location key.

    Returns:
        List of spawned item info dicts.
    """
    item_names = [item.name for item in items]
    contexts = [item.context for item in items]

    # Build context string from all item contexts
    context = "; ".join(c for c in contexts if c)

    return spawn_hallucinated_items(
        db=db,
        game_session=game_session,
        items=item_names,
        location_key=location_key,
        context=context or "spawned to match narrative",
    )
