"""Service for extracting state adjectives from item display names.

This module separates item identity (base name) from state (adjectives),
enabling clean keys and state tracking via properties.

Example:
    >>> result = extract_state_from_name("Clean Linen Shirt")
    >>> result.base_name
    'Linen Shirt'
    >>> result.state
    {'cleanliness': 'clean'}
"""

from dataclasses import dataclass
from typing import TypedDict


class ItemState(TypedDict, total=False):
    """State properties extracted from item name."""

    cleanliness: str  # clean/dirty/filthy
    condition: str  # pristine/good/worn/damaged/broken
    freshness: str  # fresh/stale
    quality: str  # poor/common/good/fine/exceptional
    age: str  # new/old/ancient


@dataclass
class ExtractionResult:
    """Result of extracting state from display name."""

    base_name: str
    state: ItemState


# Adjectives that indicate state, mapped to (category, value)
# Ordered by most specific first for compound matching
STATE_ADJECTIVES: dict[str, tuple[str, str]] = {
    # Compound adjectives (hyphenated)
    "well-worn": ("condition", "worn"),
    "battle-worn": ("condition", "worn"),
    # Cleanliness
    "clean": ("cleanliness", "clean"),
    "dirty": ("cleanliness", "dirty"),
    "filthy": ("cleanliness", "filthy"),
    "muddy": ("cleanliness", "dirty"),
    "dusty": ("cleanliness", "dirty"),
    "grimy": ("cleanliness", "filthy"),
    # Condition
    "pristine": ("condition", "pristine"),
    "new": ("condition", "pristine"),
    "worn": ("condition", "worn"),
    "weathered": ("condition", "worn"),
    "patched": ("condition", "worn"),
    "damaged": ("condition", "damaged"),
    "rusty": ("condition", "damaged"),
    "tattered": ("condition", "damaged"),
    "broken": ("condition", "broken"),
    "decrepit": ("condition", "broken"),
    # Freshness (food)
    "fresh": ("freshness", "fresh"),
    "stale": ("freshness", "stale"),
    "rotten": ("freshness", "rotten"),
    "spoiled": ("freshness", "rotten"),
    # Quality
    "crude": ("quality", "poor"),
    "rough": ("quality", "poor"),
    "poor": ("quality", "poor"),
    "common": ("quality", "common"),
    "good": ("quality", "good"),
    "fine": ("quality", "fine"),
    "exceptional": ("quality", "exceptional"),
    "masterwork": ("quality", "exceptional"),
    "exquisite": ("quality", "exceptional"),
    # Age
    "old": ("age", "old"),
    "ancient": ("age", "ancient"),
}


def extract_state_from_name(display_name: str) -> ExtractionResult:
    """Extract state adjectives from item display name.

    Scans the display name for known state adjectives, extracts them
    into a state dictionary, and returns the base name without those
    adjectives.

    Args:
        display_name: Full display name (e.g., "Clean Linen Shirt")

    Returns:
        ExtractionResult with base_name and extracted state

    Example:
        >>> result = extract_state_from_name("Rusty Iron Sword")
        >>> result.base_name
        'Iron Sword'
        >>> result.state
        {'condition': 'damaged'}
    """
    words = display_name.split()
    state: ItemState = {}
    remaining_words: list[str] = []

    i = 0
    while i < len(words):
        word = words[i]
        word_lower = word.lower()

        # Check for hyphenated compound adjectives (e.g., "Well-Worn")
        if "-" in word_lower and word_lower in STATE_ADJECTIVES:
            category, value = STATE_ADJECTIVES[word_lower]
            state[category] = value
            i += 1
            continue

        # Check single-word adjectives
        if word_lower in STATE_ADJECTIVES:
            category, value = STATE_ADJECTIVES[word_lower]
            state[category] = value
            i += 1
            continue

        # Not a state adjective, keep the word
        remaining_words.append(word)
        i += 1

    base_name = " ".join(remaining_words)
    return ExtractionResult(base_name=base_name, state=state)
