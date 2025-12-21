"""Reference resolver module for Scene-First Architecture.

This module resolves player references to entity keys:
- Exact key match
- Display name match
- Pronoun resolution
- Descriptor matching
"""

from src.resolver.reference_resolver import ReferenceResolver

__all__ = [
    "ReferenceResolver",
]
