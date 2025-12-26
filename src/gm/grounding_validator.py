"""GroundingValidator for GM Pipeline.

This module validates GM output to ensure:
- All [key:text] references exist in the manifest
- Entity names aren't mentioned without [key:text] format
- Output is grounded in known entities

The validator is deterministic (no LLM) and fast, enabling
validation passes during the GM tool loop.
"""

from __future__ import annotations

import logging
import re

from src.gm.grounding import (
    GroundingManifest,
    GroundingValidationResult,
    InvalidKeyReference,
    UnkeyedMention,
)

logger = logging.getLogger(__name__)

# Pattern to match [key:text] references
# Captures: group(1)=key, group(2)=display text
KEY_PATTERN = re.compile(r"\[([a-z0-9_]+):([^\]]+)\]")


class GroundingValidator:
    """Validates GM output against a grounding manifest.

    This class checks that:
    1. All [key:text] references exist in the manifest
    2. Entity names aren't mentioned without [key:text] format
    3. Output follows the grounding contract

    Usage:
        validator = GroundingValidator(manifest)
        result = validator.validate(narrative)
        if not result.valid:
            # Handle errors, retry with feedback
    """

    def __init__(self, manifest: GroundingManifest) -> None:
        """Initialize validator with manifest.

        Args:
            manifest: The grounding manifest containing valid entities.
        """
        self.manifest = manifest
        self._build_name_index()

    def _build_name_index(self) -> None:
        """Build index for efficient name lookups."""
        # Map display names to keys for detection
        self._name_to_key: dict[str, str] = {}

        for key, entity in self.manifest.all_entities().items():
            # Full display name
            self._name_to_key[entity.display_name.lower()] = key

            # Individual words from display name (for partial matches)
            words = entity.display_name.lower().split()
            for word in words:
                # Only index meaningful words (skip articles, prepositions)
                if len(word) > 3 and word not in {
                    "the",
                    "and",
                    "for",
                    "with",
                    "from",
                    "into",
                    "onto",
                    "some",
                    "worn",
                }:
                    if word not in self._name_to_key:
                        self._name_to_key[word] = key

    def validate(self, text: str) -> GroundingValidationResult:
        """Validate GM output for grounding issues.

        Args:
            text: The GM's narrative output text.

        Returns:
            GroundingValidationResult with validation status and any errors.
        """
        invalid_keys: list[InvalidKeyReference] = []
        unkeyed_mentions: list[UnkeyedMention] = []

        # Extract and validate [key:text] references
        key_refs = self._extract_key_references(text)

        for key, display_text, position in key_refs:
            if not self.manifest.contains_key(key):
                # Invalid key - not in manifest
                context = self._get_context(text, position)
                invalid_keys.append(
                    InvalidKeyReference(
                        key=key,
                        text=display_text,
                        position=position,
                        context=context,
                    )
                )

        # Check for unkeyed entity mentions
        unkeyed = self._detect_unkeyed_mentions(text, key_refs)
        unkeyed_mentions.extend(unkeyed)

        return GroundingValidationResult(
            valid=len(invalid_keys) == 0 and len(unkeyed_mentions) == 0,
            invalid_keys=invalid_keys,
            unkeyed_mentions=unkeyed_mentions,
        )

    def _extract_key_references(self, text: str) -> list[tuple[str, str, int]]:
        """Extract all [key:text] references from text.

        Args:
            text: The text to search.

        Returns:
            List of (key, display_text, position) tuples.
        """
        matches = []
        for match in KEY_PATTERN.finditer(text):
            key = match.group(1)
            display_text = match.group(2)
            position = match.start()
            matches.append((key, display_text, position))
        return matches

    def _get_context(self, text: str, position: int, window: int = 30) -> str:
        """Get surrounding context for error reporting.

        Args:
            text: Full text.
            position: Position of the error.
            window: Characters to include on each side.

        Returns:
            Context string with ellipsis if truncated.
        """
        start = max(0, position - window)
        end = min(len(text), position + window)

        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(text) else ""

        return f"{prefix}{text[start:end]}{suffix}"

    def _detect_unkeyed_mentions(
        self,
        text: str,
        keyed_refs: list[tuple[str, str, int]],
    ) -> list[UnkeyedMention]:
        """Detect entity mentions without [key:text] format.

        Args:
            text: The text to check.
            keyed_refs: Already extracted keyed references.

        Returns:
            List of UnkeyedMention errors.
        """
        errors = []
        text_lower = text.lower()

        # Get the keys that were properly used
        used_keys = {key for key, _, _ in keyed_refs}

        # Check each entity's names
        for key, entity in self.manifest.all_entities().items():
            # If this key was used properly, skip checking its name
            if key in used_keys:
                continue

            display_lower = entity.display_name.lower()

            # Use word boundary to find standalone mentions
            pattern = rf"\b{re.escape(display_lower)}\b"
            match = re.search(pattern, text_lower)

            if match:
                pos = match.start()
                # Check if there's a [key: pattern within 50 chars before
                before_text = text[max(0, pos - 50) : pos]
                if f"[{key}:" not in before_text.lower():
                    context = self._get_context(text, pos)
                    errors.append(
                        UnkeyedMention(
                            expected_key=key,
                            display_name=entity.display_name,
                            position=pos,
                            context=context,
                        )
                    )
                    continue

            # Check for significant name parts for NPCs
            # (first name, last name - not just articles)
            name_parts = display_lower.split()
            for part in name_parts:
                if len(part) > 3 and part not in {
                    "the",
                    "and",
                    "for",
                    "with",
                    "from",
                    "into",
                    "onto",
                    "some",
                }:
                    pattern = rf"\b{re.escape(part)}\b"
                    match = re.search(pattern, text_lower)
                    if match:
                        pos = match.start()
                        before_text = text[max(0, pos - 50) : pos]
                        if f"[{key}:" not in before_text.lower():
                            context = self._get_context(text, pos)
                            errors.append(
                                UnkeyedMention(
                                    expected_key=key,
                                    display_name=entity.display_name,
                                    position=pos,
                                    context=context,
                                )
                            )
                            break  # Only report once per entity

        return errors


def strip_key_references(text: str) -> str:
    """Strip [key:text] format from text, leaving just the text.

    Args:
        text: Text containing [key:text] references.

    Returns:
        Text with [key:text] replaced by just text.

    Example:
        "[marcus_001:Marcus] waves at you" → "Marcus waves at you"
    """
    return KEY_PATTERN.sub(r"\2", text)
