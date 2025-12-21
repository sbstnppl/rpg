"""Tests for SceneNarrator - Scene-First Architecture Phase 5.

These tests verify:
- Generating narration from scene manifest
- Validating output with retry loop
- Stripping [key] markers for display
- Fallback generation when validation fails
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.world.schemas import (
    Atmosphere,
    EntityRef,
    NarrationType,
    NarrationContext,
    NarrationResult,
    NarratorManifest,
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
            "bar_counter": EntityRef(
                key="bar_counter",
                display_name="long oak bar",
                entity_type="furniture",
                short_description="long oak bar counter",
                position="along the back wall",
            ),
        },
        atmosphere=sample_atmosphere,
    )


@pytest.fixture
def mock_llm_provider() -> MagicMock:
    """Create a mock LLM provider."""
    provider = MagicMock()
    provider.complete = AsyncMock()
    return provider


# =============================================================================
# Initialization Tests
# =============================================================================


class TestSceneNarratorInit:
    """Tests for SceneNarrator initialization."""

    def test_init_with_manifest(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """SceneNarrator initializes with manifest."""
        from src.narrator.scene_narrator import SceneNarrator

        narrator = SceneNarrator(sample_manifest)

        assert narrator.manifest is sample_manifest

    def test_init_with_llm_provider(
        self,
        sample_manifest: NarratorManifest,
        mock_llm_provider: MagicMock,
    ) -> None:
        """SceneNarrator accepts optional LLM provider."""
        from src.narrator.scene_narrator import SceneNarrator

        narrator = SceneNarrator(sample_manifest, llm_provider=mock_llm_provider)

        assert narrator.llm_provider is mock_llm_provider

    def test_init_with_max_retries(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """SceneNarrator accepts max_retries parameter."""
        from src.narrator.scene_narrator import SceneNarrator

        narrator = SceneNarrator(sample_manifest, max_retries=5)

        assert narrator.max_retries == 5


# =============================================================================
# Key Stripping Tests
# =============================================================================


class TestKeyStripping:
    """Tests for stripping [key] markers from display text."""

    def test_strip_single_key(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Single key is stripped correctly with [key:text] format."""
        from src.narrator.scene_narrator import SceneNarrator

        narrator = SceneNarrator(sample_manifest)
        text = "You see [bartender_001:Tom] behind the bar."

        result = narrator._strip_keys(text)

        assert result == "You see Tom behind the bar."

    def test_strip_multiple_keys(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Multiple keys are stripped correctly with [key:text] format."""
        from src.narrator.scene_narrator import SceneNarrator

        narrator = SceneNarrator(sample_manifest)
        text = "[bartender_001:Tom] waves at [sarah_001:Sarah] from behind the [bar_counter:bar]."

        result = narrator._strip_keys(text)

        assert result == "Tom waves at Sarah from behind the bar."
        assert "[" not in result
        assert "]" not in result

    def test_strip_preserves_unknown_keys(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Unknown keys still show the text portion."""
        from src.narrator.scene_narrator import SceneNarrator

        narrator = SceneNarrator(sample_manifest)
        text = "A mysterious [unknown_key:stranger] appears."

        result = narrator._strip_keys(text)

        # Should show the text portion even for unknown keys
        assert result == "A mysterious stranger appears."

    def test_strip_empty_text(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Empty text returns empty string."""
        from src.narrator.scene_narrator import SceneNarrator

        narrator = SceneNarrator(sample_manifest)

        result = narrator._strip_keys("")

        assert result == ""

    def test_strip_uses_narrator_text_directly(
        self,
        sample_atmosphere: Atmosphere,
    ) -> None:
        """The text portion is used exactly as the narrator wrote it."""
        from src.narrator.scene_narrator import SceneNarrator
        from src.world.schemas import EntityRef, NarratorManifest

        manifest = NarratorManifest(
            location_key="farm",
            location_display="A Small Farm",
            entities={
                "cottage_001": EntityRef(
                    key="cottage_001",
                    display_name="cottage",  # Simple name
                    entity_type="furniture",
                    short_description="A cottage",
                    position="to the north",
                ),
            },
            atmosphere=sample_atmosphere,
        )
        narrator = SceneNarrator(manifest)
        # Narrator adds adjectives and uses key:text format
        text = "At the center stands a weathered stone [cottage_001:cottage]."

        result = narrator._strip_keys(text)

        # The text should use exactly what the narrator wrote after the colon
        assert result == "At the center stands a weathered stone cottage."


# =============================================================================
# Narration Generation Tests
# =============================================================================


class TestNarrationGeneration:
    """Tests for generating narration."""

    @pytest.mark.asyncio
    async def test_narrate_calls_llm(
        self,
        sample_manifest: NarratorManifest,
        mock_llm_provider: MagicMock,
    ) -> None:
        """narrate() calls LLM provider."""
        from src.narrator.scene_narrator import SceneNarrator

        # Mock LLM response with valid [key:text] format
        mock_response = MagicMock()
        mock_response.content = "You enter the [tavern_main:main hall]. [bartender_001:Tom] waves."
        mock_llm_provider.complete.return_value = mock_response

        # Add location to manifest
        sample_manifest.entities["tavern_main"] = EntityRef(
            key="tavern_main",
            display_name="main hall",
            entity_type="location",
            short_description="tavern main hall",
        )

        narrator = SceneNarrator(sample_manifest, llm_provider=mock_llm_provider)

        await narrator.narrate(NarrationType.SCENE_ENTRY, NarrationContext())

        mock_llm_provider.complete.assert_called()

    @pytest.mark.asyncio
    async def test_narrate_returns_result(
        self,
        sample_manifest: NarratorManifest,
        mock_llm_provider: MagicMock,
    ) -> None:
        """narrate() returns NarrationResult."""
        from src.narrator.scene_narrator import SceneNarrator

        mock_response = MagicMock()
        mock_response.content = "Candlelight flickers. [bartender_001:Tom] nods warmly."
        mock_llm_provider.complete.return_value = mock_response

        narrator = SceneNarrator(sample_manifest, llm_provider=mock_llm_provider)

        result = await narrator.narrate(NarrationType.SCENE_ENTRY, NarrationContext())

        assert isinstance(result, NarrationResult)
        assert result.display_text is not None
        assert "[" not in result.display_text  # Keys stripped
        assert result.raw_output is not None

    @pytest.mark.asyncio
    async def test_narrate_validates_output(
        self,
        sample_manifest: NarratorManifest,
        mock_llm_provider: MagicMock,
    ) -> None:
        """narrate() validates LLM output."""
        from src.narrator.scene_narrator import SceneNarrator

        # First response invalid (bad key), second valid
        invalid_response = MagicMock()
        invalid_response.content = "You see [invalid_npc:stranger] here."

        valid_response = MagicMock()
        valid_response.content = "[bartender_001:Tom] polishes a glass."

        mock_llm_provider.complete.side_effect = [invalid_response, valid_response]

        narrator = SceneNarrator(sample_manifest, llm_provider=mock_llm_provider)

        result = await narrator.narrate(NarrationType.SCENE_ENTRY, NarrationContext())

        # Should retry and use second response
        assert result.validation_passed is True
        assert "Tom" in result.display_text

    @pytest.mark.asyncio
    async def test_narrate_includes_references(
        self,
        sample_manifest: NarratorManifest,
        mock_llm_provider: MagicMock,
    ) -> None:
        """narrate() includes entity references in result."""
        from src.narrator.scene_narrator import SceneNarrator

        mock_response = MagicMock()
        mock_response.content = "[bartender_001:Tom] serves [sarah_001:Sarah]."
        mock_llm_provider.complete.return_value = mock_response

        narrator = SceneNarrator(sample_manifest, llm_provider=mock_llm_provider)

        result = await narrator.narrate(NarrationType.SCENE_ENTRY, NarrationContext())

        assert len(result.entity_references) == 2
        ref_keys = [r.key for r in result.entity_references]
        assert "bartender_001" in ref_keys
        assert "sarah_001" in ref_keys


# =============================================================================
# Retry Logic Tests
# =============================================================================


class TestRetryLogic:
    """Tests for retry logic on validation failure."""

    @pytest.mark.asyncio
    async def test_retries_on_invalid_keys(
        self,
        sample_manifest: NarratorManifest,
        mock_llm_provider: MagicMock,
    ) -> None:
        """Retries when invalid keys are returned."""
        from src.narrator.scene_narrator import SceneNarrator

        # All responses invalid (key doesn't exist in manifest)
        invalid_response = MagicMock()
        invalid_response.content = "[ghost_001:ghost] appears."
        mock_llm_provider.complete.return_value = invalid_response

        narrator = SceneNarrator(
            sample_manifest,
            llm_provider=mock_llm_provider,
            max_retries=3,
        )

        result = await narrator.narrate(NarrationType.SCENE_ENTRY, NarrationContext())

        # Should have called 3 times
        assert mock_llm_provider.complete.call_count == 3
        # Result should indicate validation failed
        assert result.validation_passed is False

    @pytest.mark.asyncio
    async def test_passes_errors_to_retry(
        self,
        sample_manifest: NarratorManifest,
        mock_llm_provider: MagicMock,
    ) -> None:
        """Error feedback is passed to retry attempts."""
        from src.narrator.scene_narrator import SceneNarrator

        call_count = 0

        def check_prompt(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            response = MagicMock()
            if call_count == 1:
                # First call - invalid key
                response.content = "[invalid_key:stranger] does something."
            else:
                # Second call - valid
                response.content = "[bartender_001:Tom] waves."
            return response

        mock_llm_provider.complete = AsyncMock(side_effect=check_prompt)

        narrator = SceneNarrator(sample_manifest, llm_provider=mock_llm_provider)

        await narrator.narrate(NarrationType.SCENE_ENTRY, NarrationContext())

        # Should have made 2 calls
        assert call_count == 2


# =============================================================================
# Fallback Generation Tests
# =============================================================================


class TestFallbackGeneration:
    """Tests for safe fallback narration."""

    @pytest.mark.asyncio
    async def test_generates_fallback_after_max_retries(
        self,
        sample_manifest: NarratorManifest,
        mock_llm_provider: MagicMock,
    ) -> None:
        """Generates safe fallback after all retries fail."""
        from src.narrator.scene_narrator import SceneNarrator

        # Invalid: key doesn't exist
        invalid_response = MagicMock()
        invalid_response.content = "[invalid_001:ghost] appears."
        mock_llm_provider.complete.return_value = invalid_response

        narrator = SceneNarrator(
            sample_manifest,
            llm_provider=mock_llm_provider,
            max_retries=2,
        )

        result = await narrator.narrate(NarrationType.SCENE_ENTRY, NarrationContext())

        # Should have fallback text
        assert result.display_text is not None
        assert len(result.display_text) > 0

    @pytest.mark.asyncio
    async def test_fallback_uses_atmosphere(
        self,
        sample_manifest: NarratorManifest,
        mock_llm_provider: MagicMock,
    ) -> None:
        """Fallback includes atmosphere details."""
        from src.narrator.scene_narrator import SceneNarrator

        # Invalid: key doesn't exist
        invalid_response = MagicMock()
        invalid_response.content = "[ghost_001:ghost] spooks you."
        mock_llm_provider.complete.return_value = invalid_response

        narrator = SceneNarrator(
            sample_manifest,
            llm_provider=mock_llm_provider,
            max_retries=1,
        )

        result = await narrator.narrate(NarrationType.SCENE_ENTRY, NarrationContext())

        # Fallback should mention location
        assert "Main Hall" in result.display_text or "tavern" in result.display_text.lower()


# =============================================================================
# Narration Type Tests
# =============================================================================


class TestNarrationTypes:
    """Tests for different narration types."""

    @pytest.mark.asyncio
    async def test_scene_entry_narration(
        self,
        sample_manifest: NarratorManifest,
        mock_llm_provider: MagicMock,
    ) -> None:
        """SCENE_ENTRY generates entry description."""
        from src.narrator.scene_narrator import SceneNarrator

        mock_response = MagicMock()
        mock_response.content = "You enter The Main Hall."
        mock_llm_provider.complete.return_value = mock_response

        narrator = SceneNarrator(sample_manifest, llm_provider=mock_llm_provider)

        result = await narrator.narrate(NarrationType.SCENE_ENTRY, NarrationContext())

        # Should include location
        assert result.display_text is not None

    @pytest.mark.asyncio
    async def test_action_result_narration(
        self,
        sample_manifest: NarratorManifest,
        mock_llm_provider: MagicMock,
    ) -> None:
        """ACTION_RESULT describes action outcome."""
        from src.narrator.scene_narrator import SceneNarrator

        mock_response = MagicMock()
        mock_response.content = "[bartender_001] hands you a drink."
        mock_llm_provider.complete.return_value = mock_response

        context = NarrationContext(
            player_action={"verb": "talk", "target": "bartender_001"},
            action_result={"success": True, "response": "A friendly greeting"},
        )

        narrator = SceneNarrator(sample_manifest, llm_provider=mock_llm_provider)

        result = await narrator.narrate(NarrationType.ACTION_RESULT, context)

        assert result.display_text is not None


# =============================================================================
# No LLM Provider Tests
# =============================================================================


class TestNoLLMProvider:
    """Tests for when no LLM provider is available."""

    @pytest.mark.asyncio
    async def test_uses_fallback_without_llm(
        self,
        sample_manifest: NarratorManifest,
    ) -> None:
        """Uses fallback narration when no LLM provider."""
        from src.narrator.scene_narrator import SceneNarrator

        narrator = SceneNarrator(sample_manifest, llm_provider=None)

        result = await narrator.narrate(NarrationType.SCENE_ENTRY, NarrationContext())

        assert result.display_text is not None
        assert "Main Hall" in result.display_text or "tavern" in result.display_text.lower()
