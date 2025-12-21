"""NarratorValidator for Scene-First Architecture.

This module validates narrator output to ensure:
- All [key:text] references exist in the manifest
- Entity names aren't mentioned without [key:text] format
- Output is suitable for display after key stripping

The validator is deterministic (no LLM) and fast, enabling
multiple validation passes during the narrator retry loop.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from src.world.schemas import (
    EntityRef,
    InvalidReference,
    NarratorManifest,
    UnkeyedReference,
    ValidationResult,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Pattern to match [key:text] references
# Captures: group(1)=key, group(2)=display text
KEY_PATTERN = re.compile(r"\[([a-z0-9_]+):([^\]]+)\]")


class NarratorValidator:
    """Validates narrator output against a manifest.

    This class checks that:
    1. All [key:text] references exist in the manifest
    2. Entity names aren't mentioned without [key:text] format
    3. Output follows the constrained narrator contract

    Usage:
        validator = NarratorValidator(manifest)
        result = validator.validate(narrator_output)
        if not result.valid:
            # Handle errors, retry with feedback
    """

    def __init__(self, manifest: NarratorManifest) -> None:
        """Initialize validator with manifest.

        Args:
            manifest: The narrator manifest containing valid entities.
        """
        self.manifest = manifest
        self._build_name_index()

    def _build_name_index(self) -> None:
        """Build index for efficient name lookups."""
        # Map display names and partial names to keys
        self._name_to_key: dict[str, str] = {}

        for key, entity in self.manifest.entities.items():
            # Full display name
            self._name_to_key[entity.display_name.lower()] = key

            # Individual words from display name (for partial matches)
            words = entity.display_name.lower().split()
            for word in words:
                # Only index meaningful words (skip articles, prepositions)
                if len(word) > 2 and word not in {"the", "and", "for", "with"}:
                    if word not in self._name_to_key:
                        self._name_to_key[word] = key

    def validate(self, text: str) -> ValidationResult:
        """Validate narrator output.

        Args:
            text: The narrator's output text.

        Returns:
            ValidationResult with validation status and any errors.
        """
        errors: list[InvalidReference | UnkeyedReference] = []
        valid_refs: list[EntityRef] = []

        # Extract and validate [key] references
        key_refs = self._extract_key_references(text)

        for key, position in key_refs:
            if key in self.manifest.entities:
                valid_refs.append(self.manifest.entities[key])
            else:
                # Invalid key
                context = self._get_context(text, position)
                errors.append(
                    InvalidReference(
                        key=key,
                        position=position,
                        context=context,
                        error=f"Key [{key}] not found in manifest",
                    )
                )

        # Check for unkeyed entity mentions
        unkeyed = self._detect_unkeyed_references(text, key_refs)
        errors.extend(unkeyed)

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            references=valid_refs,
        )

    def _extract_key_references(self, text: str) -> list[tuple[str, int]]:
        """Extract all [key:text] references from text.

        Args:
            text: The text to search.

        Returns:
            List of (key, position) tuples.
        """
        matches = []
        for match in KEY_PATTERN.finditer(text):
            key = match.group(1)  # Just the key part, not the display text
            position = match.start()
            matches.append((key, position))
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

    def _detect_unkeyed_references(
        self,
        text: str,
        keyed_refs: list[tuple[str, int]],
    ) -> list[UnkeyedReference]:
        """Detect entity mentions without [key:text] format.

        Args:
            text: The text to check.
            keyed_refs: Already extracted keyed references.

        Returns:
            List of UnkeyedReference errors.
        """
        errors = []
        text_lower = text.lower()

        # Get the keys that were properly used
        used_keys = {key for key, _ in keyed_refs}

        # Check each entity's names
        for key, entity in self.manifest.entities.items():
            # If this key was used properly, skip checking its name
            if key in used_keys:
                continue

            # Check for display name mention (simple name like "cottage")
            display_lower = entity.display_name.lower()

            # Use word boundary to find standalone mentions
            pattern = rf"\b{re.escape(display_lower)}\b"
            if re.search(pattern, text_lower):
                # Check it's not inside a [key:text] reference
                # by looking for the key nearby
                match = re.search(pattern, text_lower)
                if match:
                    pos = match.start()
                    # Check if there's a [key: pattern within 50 chars before
                    before_text = text[max(0, pos - 50) : pos]
                    if f"[{key}:" not in before_text.lower():
                        errors.append(
                            UnkeyedReference(
                                entity_key=key,
                                display_name=entity.display_name,
                                error=f"'{entity.display_name}' mentioned without [key:text] format. Use [{key}:{entity.display_name}].",
                            )
                        )
                        continue

            # Check for significant name parts for NPCs
            # (first name, last name - not just articles)
            name_parts = display_lower.split()
            for part in name_parts:
                if len(part) > 3 and part not in {"the", "and", "for", "with", "from"}:
                    # Check if this part appears as a standalone word
                    pattern = rf"\b{re.escape(part)}\b"
                    if re.search(pattern, text_lower):
                        match = re.search(pattern, text_lower)
                        if match:
                            pos = match.start()
                            # Check if there's a [key: pattern within 50 chars before
                            before_text = text[max(0, pos - 50) : pos]
                            if f"[{key}:" not in before_text.lower():
                                errors.append(
                                    UnkeyedReference(
                                        entity_key=key,
                                        display_name=entity.display_name,
                                        error=f"'{part}' (from {entity.display_name}) mentioned without [key:text] format. Use [{key}:{part}].",
                                    )
                                )
                                break  # Only report once per entity

        return errors
