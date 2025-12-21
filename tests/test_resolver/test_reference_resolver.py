"""Tests for ReferenceResolver - Scene-First Architecture Phase 6.

These tests verify:
- Exact key resolution
- Display name resolution
- Pronoun resolution (he/she/it/they)
- Descriptor resolution (the bartender, the big one)
- Ambiguity detection
- Unknown reference handling
"""

import pytest

from src.world.schemas import (
    Atmosphere,
    EntityRef,
    NarratorManifest,
    ResolutionResult,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_atmosphere() -> Atmosphere:
    """Create a sample atmosphere for testing."""
    return Atmosphere(
        lighting="dim candlelight",
        lighting_source="candles",
        sounds=["murmured conversations"],
        smells=["wood smoke"],
        temperature="warm",
        overall_mood="cozy",
    )


@pytest.fixture
def sample_manifest(sample_atmosphere: Atmosphere) -> NarratorManifest:
    """Create a sample narrator manifest with entities."""
    return NarratorManifest(
        location_key="tavern_main",
        location_display="The Main Hall",
        entities={
            "bartender_001": EntityRef(
                key="bartender_001",
                display_name="Tom the Bartender",
                entity_type="npc",
                short_description="Tom, polishing glasses",
                pronouns="he/him",
                position="behind the bar",
            ),
            "sarah_001": EntityRef(
                key="sarah_001",
                display_name="Sarah",
                entity_type="npc",
                short_description="Sarah, sitting at a table",
                pronouns="she/her",
                position="at a corner table",
            ),
            "guard_001": EntityRef(
                key="guard_001",
                display_name="Marcus the Guard",
                entity_type="npc",
                short_description="A stern-looking guard",
                pronouns="he/him",
                position="by the door",
            ),
            "bar_counter": EntityRef(
                key="bar_counter",
                display_name="long oak bar",
                entity_type="furniture",
                short_description="long oak bar counter",
                position="along the back wall",
            ),
            "mug_001": EntityRef(
                key="mug_001",
                display_name="pewter mug",
                entity_type="item",
                short_description="pewter mug of ale",
                position="on the bar",
            ),
            "book_001": EntityRef(
                key="book_001",
                display_name="leather-bound book",
                entity_type="item",
                short_description="an old leather-bound book",
                position="on Sarah's table",
            ),
        },
        atmosphere=sample_atmosphere,
    )


# =============================================================================
# Initialization Tests
# =============================================================================


class TestReferenceResolverInit:
    """Tests for ReferenceResolver initialization."""

    def test_init_with_manifest(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """ReferenceResolver initializes with manifest."""
        from src.resolver.reference_resolver import ReferenceResolver

        resolver = ReferenceResolver(sample_manifest)

        assert resolver.manifest is sample_manifest


# =============================================================================
# Exact Key Resolution Tests
# =============================================================================


class TestExactKeyResolution:
    """Tests for resolving exact entity keys."""

    def test_resolve_exact_key(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Exact key match resolves correctly."""
        from src.resolver.reference_resolver import ReferenceResolver

        resolver = ReferenceResolver(sample_manifest)

        result = resolver.resolve("bartender_001")

        assert isinstance(result, ResolutionResult)
        assert result.resolved is True
        assert result.entity.key == "bartender_001"

    def test_resolve_key_case_insensitive(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Key resolution is case-insensitive."""
        from src.resolver.reference_resolver import ReferenceResolver

        resolver = ReferenceResolver(sample_manifest)

        result = resolver.resolve("BARTENDER_001")

        assert result.resolved is True
        assert result.entity.key == "bartender_001"


# =============================================================================
# Display Name Resolution Tests
# =============================================================================


class TestDisplayNameResolution:
    """Tests for resolving display names."""

    def test_resolve_full_display_name(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Full display name resolves correctly."""
        from src.resolver.reference_resolver import ReferenceResolver

        resolver = ReferenceResolver(sample_manifest)

        result = resolver.resolve("Tom the Bartender")

        assert result.resolved is True
        assert result.entity.key == "bartender_001"

    def test_resolve_partial_name(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Partial name resolves when unique."""
        from src.resolver.reference_resolver import ReferenceResolver

        resolver = ReferenceResolver(sample_manifest)

        result = resolver.resolve("Sarah")

        assert result.resolved is True
        assert result.entity.key == "sarah_001"

    def test_resolve_with_articles(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Names with articles resolve correctly."""
        from src.resolver.reference_resolver import ReferenceResolver

        resolver = ReferenceResolver(sample_manifest)

        result = resolver.resolve("the bartender")

        assert result.resolved is True
        assert result.entity.key == "bartender_001"

    def test_resolve_display_name_case_insensitive(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Display name resolution is case-insensitive."""
        from src.resolver.reference_resolver import ReferenceResolver

        resolver = ReferenceResolver(sample_manifest)

        result = resolver.resolve("tom")

        assert result.resolved is True
        assert result.entity.key == "bartender_001"


# =============================================================================
# Pronoun Resolution Tests
# =============================================================================


class TestPronounResolution:
    """Tests for resolving pronouns."""

    def test_resolve_he_single_male(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """'he' resolves when only one male NPC present."""
        from src.resolver.reference_resolver import ReferenceResolver

        # Create manifest with only one male
        manifest = NarratorManifest(
            location_key="test",
            location_display="Test",
            entities={
                "npc_001": EntityRef(
                    key="npc_001",
                    display_name="John",
                    entity_type="npc",
                    short_description="John standing around",
                    pronouns="he/him",
                ),
            },
            atmosphere=sample_manifest.atmosphere,
        )

        resolver = ReferenceResolver(manifest)

        result = resolver.resolve("him")

        assert result.resolved is True
        assert result.entity.key == "npc_001"

    def test_resolve_she_single_female(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """'she' resolves when only one female NPC present."""
        from src.resolver.reference_resolver import ReferenceResolver

        resolver = ReferenceResolver(sample_manifest)

        result = resolver.resolve("her")

        assert result.resolved is True
        assert result.entity.key == "sarah_001"

    def test_resolve_it_for_item(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """'it' is ambiguous with multiple items."""
        from src.resolver.reference_resolver import ReferenceResolver

        resolver = ReferenceResolver(sample_manifest)

        result = resolver.resolve("it")

        # Should be ambiguous (multiple items/furniture)
        assert result.ambiguous is True
        assert len(result.candidates) > 1

    def test_he_ambiguous_multiple_males(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """'he' is ambiguous when multiple male NPCs present."""
        from src.resolver.reference_resolver import ReferenceResolver

        resolver = ReferenceResolver(sample_manifest)

        result = resolver.resolve("him")

        # Both bartender and guard are male
        assert result.ambiguous is True
        assert len(result.candidates) == 2


# =============================================================================
# Descriptor Resolution Tests
# =============================================================================


class TestDescriptorResolution:
    """Tests for resolving descriptors."""

    def test_resolve_role_descriptor(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Role-based descriptor resolves correctly."""
        from src.resolver.reference_resolver import ReferenceResolver

        resolver = ReferenceResolver(sample_manifest)

        result = resolver.resolve("the guard")

        assert result.resolved is True
        assert result.entity.key == "guard_001"

    def test_resolve_item_descriptor(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Item descriptor resolves correctly."""
        from src.resolver.reference_resolver import ReferenceResolver

        resolver = ReferenceResolver(sample_manifest)

        result = resolver.resolve("the mug")

        assert result.resolved is True
        assert result.entity.key == "mug_001"

    def test_resolve_book_descriptor(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Book descriptor resolves correctly."""
        from src.resolver.reference_resolver import ReferenceResolver

        resolver = ReferenceResolver(sample_manifest)

        result = resolver.resolve("book")

        assert result.resolved is True
        assert result.entity.key == "book_001"

    def test_resolve_furniture_descriptor(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Furniture descriptor resolves correctly."""
        from src.resolver.reference_resolver import ReferenceResolver

        resolver = ReferenceResolver(sample_manifest)

        result = resolver.resolve("the bar")

        assert result.resolved is True
        assert result.entity.key == "bar_counter"


# =============================================================================
# Ambiguity Tests
# =============================================================================


class TestAmbiguity:
    """Tests for ambiguous reference detection."""

    def test_ambiguous_returns_candidates(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Ambiguous references return candidate list."""
        from src.resolver.reference_resolver import ReferenceResolver

        resolver = ReferenceResolver(sample_manifest)

        # "him" is ambiguous (bartender and guard are both male)
        result = resolver.resolve("him")

        assert result.ambiguous is True
        assert len(result.candidates) >= 2
        candidate_keys = [c.key for c in result.candidates]
        assert "bartender_001" in candidate_keys
        assert "guard_001" in candidate_keys

    def test_ambiguous_resolved_is_false(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Ambiguous resolution has resolved=False."""
        from src.resolver.reference_resolver import ReferenceResolver

        resolver = ReferenceResolver(sample_manifest)

        result = resolver.resolve("him")

        assert result.resolved is False
        assert result.entity is None


# =============================================================================
# Unknown Reference Tests
# =============================================================================


class TestUnknownReference:
    """Tests for unknown reference handling."""

    def test_unknown_reference(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Unknown references are handled gracefully."""
        from src.resolver.reference_resolver import ReferenceResolver

        resolver = ReferenceResolver(sample_manifest)

        result = resolver.resolve("the dragon")

        assert result.resolved is False
        assert result.ambiguous is False
        assert result.entity is None
        assert len(result.candidates) == 0

    def test_empty_reference(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Empty reference is handled."""
        from src.resolver.reference_resolver import ReferenceResolver

        resolver = ReferenceResolver(sample_manifest)

        result = resolver.resolve("")

        assert result.resolved is False


# =============================================================================
# Context-Aware Resolution Tests
# =============================================================================


class TestContextAwareResolution:
    """Tests for context-aware resolution with last mentioned."""

    def test_resolve_with_last_mentioned(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Pronouns resolve using last_mentioned context."""
        from src.resolver.reference_resolver import ReferenceResolver

        resolver = ReferenceResolver(sample_manifest)

        # Set context that Sarah was last mentioned
        result = resolver.resolve("her", last_mentioned="sarah_001")

        assert result.resolved is True
        assert result.entity.key == "sarah_001"

    def test_resolve_he_with_last_mentioned(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """'he' resolves to last mentioned male."""
        from src.resolver.reference_resolver import ReferenceResolver

        resolver = ReferenceResolver(sample_manifest)

        # Set context that guard was last mentioned
        result = resolver.resolve("him", last_mentioned="guard_001")

        assert result.resolved is True
        assert result.entity.key == "guard_001"


# =============================================================================
# Multiple Word Reference Tests
# =============================================================================


class TestMultiWordReferences:
    """Tests for multi-word references."""

    def test_resolve_multi_word_descriptor(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Multi-word descriptors resolve correctly."""
        from src.resolver.reference_resolver import ReferenceResolver

        resolver = ReferenceResolver(sample_manifest)

        result = resolver.resolve("leather-bound book")

        assert result.resolved is True
        assert result.entity.key == "book_001"

    def test_resolve_with_prepositions(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """References with prepositions extract the entity."""
        from src.resolver.reference_resolver import ReferenceResolver

        resolver = ReferenceResolver(sample_manifest)

        result = resolver.resolve("pewter mug")

        assert result.resolved is True
        assert result.entity.key == "mug_001"


# =============================================================================
# Resolution Method Tests
# =============================================================================


class TestResolutionMethod:
    """Tests for resolution method tracking."""

    def test_tracks_resolution_method(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Result includes how resolution was achieved."""
        from src.resolver.reference_resolver import ReferenceResolver

        resolver = ReferenceResolver(sample_manifest)

        result = resolver.resolve("bartender_001")

        assert result.method == "exact_key"

    def test_tracks_display_name_method(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Display name resolution is tracked."""
        from src.resolver.reference_resolver import ReferenceResolver

        resolver = ReferenceResolver(sample_manifest)

        result = resolver.resolve("Tom the Bartender")

        assert result.method == "display_name"

    def test_tracks_partial_match_method(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Partial match resolution is tracked."""
        from src.resolver.reference_resolver import ReferenceResolver

        resolver = ReferenceResolver(sample_manifest)

        result = resolver.resolve("the guard")

        # "guard" is part of display name "Marcus the Guard"
        assert result.method in ("partial_match", "descriptor", "display_name")
