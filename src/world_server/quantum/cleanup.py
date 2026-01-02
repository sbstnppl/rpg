"""Cleanup Module for the Quantum Pipeline (Phase 5).

Phase 5 of the split architecture. Performs final string processing:
1. Strip [key:display] format → display text only
2. Replace player entity key → "you"
3. Normalize whitespace
4. Fix common formatting issues

This is DETERMINISTIC CODE - no LLM calls.

The output is player-ready prose with no entity keys visible.
"""

import re
from dataclasses import dataclass


# =============================================================================
# Regex Patterns
# =============================================================================

# Match [key:display] format
ENTITY_REF_PATTERN = re.compile(r"\[([^:\]]+):([^\]]+)\]")

# Match multiple spaces
MULTI_SPACE_PATTERN = re.compile(r" +")

# Match multiple newlines
MULTI_NEWLINE_PATTERN = re.compile(r"\n{3,}")


# =============================================================================
# Cleanup Result
# =============================================================================


@dataclass
class CleanupResult:
    """Result of cleaning up narrative prose."""

    text: str
    entities_found: list[str]  # Entity keys found during cleanup
    replacements_made: int


# =============================================================================
# Cleanup Functions
# =============================================================================


def strip_entity_refs(text: str, player_key: str = "player") -> CleanupResult:
    """Strip [key:display] format, keeping only display text.

    Args:
        text: Narrative with [key:display] format.
        player_key: The player's entity key to recognize.

    Returns:
        CleanupResult with cleaned text and metadata.

    Examples:
        >>> strip_entity_refs("[npc_tom:Old Tom] waves.")
        CleanupResult(text="Old Tom waves.", entities_found=["npc_tom"], ...)

        >>> strip_entity_refs("[hero_001:you] pick up the sword.", "hero_001")
        CleanupResult(text="you pick up the sword.", entities_found=["hero_001"], ...)
    """
    entities_found: list[str] = []
    replacements = 0

    def replace_ref(match: re.Match) -> str:
        nonlocal replacements
        key = match.group(1)
        display = match.group(2)

        entities_found.append(key)
        replacements += 1

        # Player key always shows as "you"
        if key == player_key:
            return display  # Already "you" from narrator
        return display

    result = ENTITY_REF_PATTERN.sub(replace_ref, text)

    return CleanupResult(
        text=result,
        entities_found=entities_found,
        replacements_made=replacements,
    )


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace in text.

    - Collapses multiple spaces to single space
    - Collapses 3+ newlines to 2 newlines
    - Strips leading/trailing whitespace
    - Fixes space before punctuation

    Args:
        text: Text to normalize.

    Returns:
        Normalized text.
    """
    # Collapse multiple spaces
    result = MULTI_SPACE_PATTERN.sub(" ", text)

    # Collapse multiple newlines to max 2
    result = MULTI_NEWLINE_PATTERN.sub("\n\n", result)

    # Fix space before punctuation
    result = re.sub(r" +([.,!?;:])", r"\1", result)

    # Strip leading/trailing whitespace
    result = result.strip()

    return result


def fix_capitalization(text: str) -> str:
    """Fix common capitalization issues.

    - Capitalize first letter after sentence-ending punctuation
    - Fix "you" capitalization at start of sentences

    Args:
        text: Text to fix.

    Returns:
        Text with fixed capitalization.
    """
    if not text:
        return text

    # Capitalize first character
    result = text[0].upper() + text[1:] if len(text) > 1 else text.upper()

    # Capitalize after sentence endings
    result = re.sub(
        r"([.!?])\s+([a-z])",
        lambda m: m.group(1) + " " + m.group(2).upper(),
        result,
    )

    return result


def fix_pronouns(text: str, player_key: str = "player") -> str:
    """Fix pronoun usage for second-person narrative.

    - Replace any remaining player_key references with "you"
    - Fix "the player" → "you"

    Args:
        text: Text to fix.
        player_key: The player's entity key.

    Returns:
        Text with fixed pronouns.
    """
    result = text

    # Replace "The player" at start of sentence with "You"
    result = re.sub(r"\bThe player\b", "You", result)

    # Replace "the player" elsewhere with "you"
    result = re.sub(r"\bthe player\b", "you", result)

    # Replace bare player key if it somehow got through
    if player_key != "player":  # Avoid double-replacing if key is "player"
        result = result.replace(player_key, "you")

    return result


def cleanup_narrative(
    text: str,
    player_key: str = "player",
    normalize: bool = True,
    fix_caps: bool = True,
    fix_player_refs: bool = True,
) -> CleanupResult:
    """Full cleanup pipeline for narrative text.

    Performs all cleanup steps in order:
    1. Strip entity references
    2. Normalize whitespace
    3. Fix capitalization
    4. Fix pronouns

    Args:
        text: Raw narrative with [key:display] format.
        player_key: The player's entity key.
        normalize: Whether to normalize whitespace.
        fix_caps: Whether to fix capitalization.
        fix_player_refs: Whether to fix player references.

    Returns:
        CleanupResult with fully cleaned text.
    """
    # Step 1: Strip entity refs
    result = strip_entity_refs(text, player_key)
    cleaned = result.text

    # Step 2: Normalize whitespace
    if normalize:
        cleaned = normalize_whitespace(cleaned)

    # Step 3: Fix capitalization
    if fix_caps:
        cleaned = fix_capitalization(cleaned)

    # Step 4: Fix pronouns
    if fix_player_refs:
        cleaned = fix_pronouns(cleaned, player_key)

    return CleanupResult(
        text=cleaned,
        entities_found=result.entities_found,
        replacements_made=result.replacements_made,
    )


# =============================================================================
# Entity Reference Utilities
# =============================================================================


def extract_entity_keys(text: str) -> list[str]:
    """Extract all entity keys from [key:display] formatted text.

    Args:
        text: Text with [key:display] format.

    Returns:
        List of entity keys found.
    """
    matches = ENTITY_REF_PATTERN.findall(text)
    return [m[0] for m in matches]


def validate_entity_refs(
    text: str,
    valid_keys: set[str],
    player_key: str = "player",
) -> list[str]:
    """Validate that all entity references use valid keys.

    Args:
        text: Text with [key:display] format.
        valid_keys: Set of valid entity keys.
        player_key: The player's key (always valid).

    Returns:
        List of invalid keys found.
    """
    found_keys = extract_entity_keys(text)
    valid_with_player = valid_keys | {player_key}
    return [k for k in found_keys if k not in valid_with_player]


def replace_entity_key(
    text: str,
    old_key: str,
    new_key: str,
) -> str:
    """Replace an entity key in [key:display] format.

    Args:
        text: Text with [key:display] format.
        old_key: Key to replace.
        new_key: New key to use.

    Returns:
        Text with replaced key.
    """
    pattern = re.compile(rf"\[{re.escape(old_key)}:([^\]]+)\]")
    return pattern.sub(rf"[{new_key}:\1]", text)


def add_entity_ref(text: str, display: str, key: str) -> str:
    """Add [key:display] format to plain display text.

    Only replaces exact matches (whole words).

    Args:
        text: Plain text.
        display: Display text to wrap.
        key: Entity key to use.

    Returns:
        Text with entity reference added.
    """
    # Use word boundaries to avoid partial matches
    pattern = re.compile(rf"\b{re.escape(display)}\b")
    return pattern.sub(f"[{key}:{display}]", text, count=1)
