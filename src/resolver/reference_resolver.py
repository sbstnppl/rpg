"""ReferenceResolver for Scene-First Architecture.

This module resolves player references (like "the bartender", "her", "the mug")
to entity keys in the scene manifest.

Resolution strategies (in order):
1. Exact key match
2. Display name match
3. Pronoun match (with disambiguation context)
4. Partial/descriptor match

When ambiguous, returns all candidates for clarification prompt.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from src.world.schemas import (
    EntityRef,
    NarratorManifest,
    ResolutionResult,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Pronouns mapped to their gender/type
PRONOUN_GENDERS = {
    "he": "male",
    "him": "male",
    "his": "male",
    "she": "female",
    "her": "female",
    "hers": "female",
    "it": "neutral",
    "its": "neutral",
    "they": "neutral",
    "them": "neutral",
    "their": "neutral",
}

# Articles to strip from references
ARTICLES = {"the", "a", "an", "some"}


class ReferenceResolver:
    """Resolves player references to entity keys.

    This class takes a player's reference (like "the bartender" or "him")
    and resolves it to the appropriate entity key in the manifest.

    When resolution is ambiguous, it returns all possible candidates
    so the narrator can ask for clarification.

    Usage:
        resolver = ReferenceResolver(manifest)
        result = resolver.resolve("the bartender")
        if result.resolved:
            entity = result.entity
        elif result.ambiguous:
            candidates = result.candidates
    """

    def __init__(self, manifest: NarratorManifest) -> None:
        """Initialize ReferenceResolver.

        Args:
            manifest: The narrator manifest with entities.
        """
        self.manifest = manifest
        self._build_indices()

    def _build_indices(self) -> None:
        """Build indices for efficient lookups."""
        # Map lowercase keys to entities
        self._key_index: dict[str, EntityRef] = {
            key.lower(): entity for key, entity in self.manifest.entities.items()
        }

        # Map lowercase display names to keys
        self._display_name_index: dict[str, list[str]] = {}
        for key, entity in self.manifest.entities.items():
            name_lower = entity.display_name.lower()
            if name_lower not in self._display_name_index:
                self._display_name_index[name_lower] = []
            self._display_name_index[name_lower].append(key)

            # Also index individual words from display name
            words = name_lower.split()
            for word in words:
                if word not in ARTICLES and len(word) > 2:
                    if word not in self._display_name_index:
                        self._display_name_index[word] = []
                    if key not in self._display_name_index[word]:
                        self._display_name_index[word].append(key)

        # Group entities by pronoun (only NPCs for gendered pronouns)
        self._pronoun_index: dict[str, list[str]] = {
            "male": [],
            "female": [],
            "neutral": [],
        }
        for key, entity in self.manifest.entities.items():
            if entity.entity_type == "npc":
                if entity.pronouns:
                    # Split pronouns into parts to check properly
                    pronouns_lower = entity.pronouns.lower()
                    pronoun_parts = re.split(r"[/,\s]+", pronouns_lower)

                    is_male = any(p in ("he", "him", "his") for p in pronoun_parts)
                    is_female = any(p in ("she", "her", "hers") for p in pronoun_parts)

                    if is_male:
                        self._pronoun_index["male"].append(key)
                    if is_female:
                        self._pronoun_index["female"].append(key)
                    if not (is_male or is_female):
                        self._pronoun_index["neutral"].append(key)
            else:
                # Items and furniture are "neutral" (for "it")
                self._pronoun_index["neutral"].append(key)

    def resolve(
        self,
        reference: str,
        last_mentioned: str | None = None,
    ) -> ResolutionResult:
        """Resolve a reference to an entity.

        Args:
            reference: The player's reference text.
            last_mentioned: Optional key of last mentioned entity (for pronoun disambiguation).

        Returns:
            ResolutionResult with resolved entity or candidates.
        """
        if not reference or not reference.strip():
            return ResolutionResult(
                resolved=False,
                ambiguous=False,
                entity=None,
                candidates=[],
                method="none",
            )

        reference = reference.strip().lower()

        # Try exact key match first
        result = self._try_exact_key(reference)
        if result.resolved:
            return result

        # Try display name match
        result = self._try_display_name(reference)
        if result.resolved or result.ambiguous:
            return result

        # Try pronoun resolution
        result = self._try_pronoun(reference, last_mentioned)
        if result.resolved or result.ambiguous:
            return result

        # Try descriptor/partial match
        result = self._try_descriptor(reference)
        if result.resolved or result.ambiguous:
            return result

        # Nothing found
        return ResolutionResult(
            resolved=False,
            ambiguous=False,
            entity=None,
            candidates=[],
            method="none",
        )

    def _try_exact_key(self, reference: str) -> ResolutionResult:
        """Try exact key match.

        Args:
            reference: The reference (lowercase).

        Returns:
            ResolutionResult.
        """
        if reference in self._key_index:
            return ResolutionResult(
                resolved=True,
                ambiguous=False,
                entity=self._key_index[reference],
                candidates=[],
                method="exact_key",
            )

        return ResolutionResult(
            resolved=False,
            ambiguous=False,
            entity=None,
            candidates=[],
            method="exact_key",
        )

    def _try_display_name(self, reference: str) -> ResolutionResult:
        """Try display name match.

        Args:
            reference: The reference (lowercase).

        Returns:
            ResolutionResult.
        """
        # Strip articles
        clean_ref = " ".join(w for w in reference.split() if w not in ARTICLES)

        # Try exact display name match
        if clean_ref in self._display_name_index:
            keys = self._display_name_index[clean_ref]
            if len(keys) == 1:
                return ResolutionResult(
                    resolved=True,
                    ambiguous=False,
                    entity=self.manifest.entities[keys[0]],
                    candidates=[],
                    method="display_name",
                )
            else:
                return ResolutionResult(
                    resolved=False,
                    ambiguous=True,
                    entity=None,
                    candidates=[self.manifest.entities[k] for k in keys],
                    method="display_name",
                )

        # Try with original reference (in case articles were meaningful)
        if reference in self._display_name_index:
            keys = self._display_name_index[reference]
            if len(keys) == 1:
                return ResolutionResult(
                    resolved=True,
                    ambiguous=False,
                    entity=self.manifest.entities[keys[0]],
                    candidates=[],
                    method="display_name",
                )

        return ResolutionResult(
            resolved=False,
            ambiguous=False,
            entity=None,
            candidates=[],
            method="display_name",
        )

    def _try_pronoun(
        self,
        reference: str,
        last_mentioned: str | None = None,
    ) -> ResolutionResult:
        """Try pronoun resolution.

        Args:
            reference: The reference (lowercase).
            last_mentioned: Optional last mentioned entity key.

        Returns:
            ResolutionResult.
        """
        if reference not in PRONOUN_GENDERS:
            return ResolutionResult(
                resolved=False,
                ambiguous=False,
                entity=None,
                candidates=[],
                method="pronoun",
            )

        gender = PRONOUN_GENDERS[reference]

        # If we have context about last mentioned, use it
        if last_mentioned and last_mentioned in self.manifest.entities:
            entity = self.manifest.entities[last_mentioned]
            # Verify pronoun matches
            if entity.pronouns:
                if gender == "male" and "he" in entity.pronouns.lower():
                    return ResolutionResult(
                        resolved=True,
                        ambiguous=False,
                        entity=entity,
                        candidates=[],
                        method="pronoun",
                    )
                elif gender == "female" and "she" in entity.pronouns.lower():
                    return ResolutionResult(
                        resolved=True,
                        ambiguous=False,
                        entity=entity,
                        candidates=[],
                        method="pronoun",
                    )
                elif gender == "neutral":
                    return ResolutionResult(
                        resolved=True,
                        ambiguous=False,
                        entity=entity,
                        candidates=[],
                        method="pronoun",
                    )

        # Find all candidates of this gender
        candidates_keys = self._pronoun_index.get(gender, [])

        if len(candidates_keys) == 1:
            return ResolutionResult(
                resolved=True,
                ambiguous=False,
                entity=self.manifest.entities[candidates_keys[0]],
                candidates=[],
                method="pronoun",
            )
        elif len(candidates_keys) > 1:
            return ResolutionResult(
                resolved=False,
                ambiguous=True,
                entity=None,
                candidates=[self.manifest.entities[k] for k in candidates_keys],
                method="pronoun",
            )

        return ResolutionResult(
            resolved=False,
            ambiguous=False,
            entity=None,
            candidates=[],
            method="pronoun",
        )

    def _try_descriptor(self, reference: str) -> ResolutionResult:
        """Try descriptor/partial match.

        Args:
            reference: The reference (lowercase).

        Returns:
            ResolutionResult.
        """
        # Strip articles
        clean_ref = " ".join(w for w in reference.split() if w not in ARTICLES)

        candidates: list[tuple[str, int]] = []

        for key, entity in self.manifest.entities.items():
            score = self._match_score(clean_ref, entity)
            if score > 0:
                candidates.append((key, score))

        if not candidates:
            return ResolutionResult(
                resolved=False,
                ambiguous=False,
                entity=None,
                candidates=[],
                method="descriptor",
            )

        # Sort by score (highest first)
        candidates.sort(key=lambda x: x[1], reverse=True)

        # Check if top candidate is clearly better
        if len(candidates) == 1 or candidates[0][1] > candidates[1][1]:
            return ResolutionResult(
                resolved=True,
                ambiguous=False,
                entity=self.manifest.entities[candidates[0][0]],
                candidates=[],
                method="descriptor",
            )

        # Multiple candidates with same score
        top_score = candidates[0][1]
        tied_keys = [k for k, s in candidates if s == top_score]

        return ResolutionResult(
            resolved=False,
            ambiguous=True,
            entity=None,
            candidates=[self.manifest.entities[k] for k in tied_keys],
            method="descriptor",
        )

    def _match_score(self, reference: str, entity: EntityRef) -> int:
        """Calculate how well a reference matches an entity.

        Args:
            reference: The reference (lowercase, articles stripped).
            entity: The entity to match against.

        Returns:
            Match score (0 = no match, higher = better).
        """
        score = 0
        ref_words = set(reference.split())

        # Check display name
        display_lower = entity.display_name.lower()
        display_words = set(w for w in display_lower.split() if w not in ARTICLES)

        # Full display name match
        if reference == display_lower:
            score += 100

        # Check word overlap
        common = ref_words & display_words
        score += len(common) * 20

        # Check if reference is substring of display name
        if reference in display_lower:
            score += 30

        # Check if any word in reference is in display name
        for word in ref_words:
            if word in display_lower:
                score += 10

        # Check short description
        if entity.short_description:
            desc_lower = entity.short_description.lower()
            if reference in desc_lower:
                score += 15
            for word in ref_words:
                if len(word) > 3 and word in desc_lower:
                    score += 5

        return score
