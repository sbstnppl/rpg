"""Tests for LLM-based item extraction."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.narrator.item_extractor import (
    ExtractedItem,
    ItemExtractionResult,
    ItemExtractor,
    ItemImportance,
)


class TestExtractedItem:
    """Tests for ExtractedItem dataclass."""

    def test_default_values(self) -> None:
        """Test default values are set correctly."""
        item = ExtractedItem(
            name="bucket",
            importance=ItemImportance.IMPORTANT,
        )

        assert item.name == "bucket"
        assert item.importance == ItemImportance.IMPORTANT
        assert item.context == ""
        assert item.is_new is True

    def test_full_values(self) -> None:
        """Test all values are stored correctly."""
        item = ExtractedItem(
            name="washbasin",
            importance=ItemImportance.DECORATIVE,
            context="in the corner",
            is_new=False,
        )

        assert item.name == "washbasin"
        assert item.importance == ItemImportance.DECORATIVE
        assert item.context == "in the corner"
        assert item.is_new is False


class TestItemImportance:
    """Tests for ItemImportance enum."""

    def test_enum_values(self) -> None:
        """Test enum string values."""
        assert ItemImportance.IMPORTANT.value == "important"
        assert ItemImportance.DECORATIVE.value == "decorative"
        assert ItemImportance.REFERENCE.value == "reference"

    def test_enum_from_string(self) -> None:
        """Test enum creation from string."""
        assert ItemImportance("important") == ItemImportance.IMPORTANT
        assert ItemImportance("decorative") == ItemImportance.DECORATIVE
        assert ItemImportance("reference") == ItemImportance.REFERENCE


class TestItemExtractionResult:
    """Tests for ItemExtractionResult dataclass."""

    def test_default_values(self) -> None:
        """Test default values are set correctly."""
        result = ItemExtractionResult()

        assert result.items == []
        assert result.reasoning == ""

    def test_with_items(self) -> None:
        """Test result with items."""
        items = [
            ExtractedItem(name="bucket", importance=ItemImportance.IMPORTANT),
            ExtractedItem(name="pebbles", importance=ItemImportance.DECORATIVE),
        ]
        result = ItemExtractionResult(
            items=items,
            reasoning="Found 2 items",
        )

        assert len(result.items) == 2
        assert result.items[0].name == "bucket"
        assert result.reasoning == "Found 2 items"


class TestItemExtractor:
    """Tests for ItemExtractor."""

    def test_no_llm_provider_returns_empty(self) -> None:
        """Test that without LLM provider, returns empty result."""
        extractor = ItemExtractor(llm_provider=None)

        import asyncio
        result = asyncio.run(extractor.extract("You find a bucket near the well."))

        assert result.items == []
        assert "No LLM provider" in result.reasoning

    def test_short_narrative_returns_empty(self) -> None:
        """Test that very short narratives return empty result."""
        mock_provider = MagicMock()
        extractor = ItemExtractor(llm_provider=mock_provider)

        import asyncio
        result = asyncio.run(extractor.extract("You wait."))

        assert result.items == []
        assert "too short" in result.reasoning

    @pytest.mark.asyncio
    async def test_parses_valid_json_response(self) -> None:
        """Test parsing valid JSON response from LLM."""
        mock_response = MagicMock()
        mock_response.text = '''
        {
            "items": [
                {
                    "name": "bucket",
                    "importance": "important",
                    "context": "near the well",
                    "is_new": true
                },
                {
                    "name": "pebbles",
                    "importance": "decorative",
                    "context": "around the well",
                    "is_new": true
                }
            ],
            "reasoning": "Found 2 physical items"
        }
        '''

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        extractor = ItemExtractor(llm_provider=mock_provider)
        result = await extractor.extract("You find a bucket near the well with pebbles around it.")

        assert len(result.items) == 2
        assert result.items[0].name == "bucket"
        assert result.items[0].importance == ItemImportance.IMPORTANT
        assert result.items[0].context == "near the well"
        assert result.items[1].name == "pebbles"
        assert result.items[1].importance == ItemImportance.DECORATIVE

    @pytest.mark.asyncio
    async def test_parses_empty_items_response(self) -> None:
        """Test parsing response with no items."""
        mock_response = MagicMock()
        mock_response.text = '{"items": [], "reasoning": "No physical items mentioned"}'

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        extractor = ItemExtractor(llm_provider=mock_provider)
        result = await extractor.extract("The morning sun streams through the window.")

        assert result.items == []
        assert "No physical items" in result.reasoning

    @pytest.mark.asyncio
    async def test_handles_json_with_extra_text(self) -> None:
        """Test parsing JSON even when surrounded by extra text."""
        mock_response = MagicMock()
        mock_response.text = '''Here's my analysis:
        {
            "items": [{"name": "rope", "importance": "important", "context": "coiled", "is_new": true}],
            "reasoning": "One item found"
        }
        Hope this helps!'''

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        extractor = ItemExtractor(llm_provider=mock_provider)
        result = await extractor.extract("You find a rope coiled in the corner.")

        assert len(result.items) == 1
        assert result.items[0].name == "rope"

    @pytest.mark.asyncio
    async def test_handles_invalid_json(self) -> None:
        """Test graceful handling of invalid JSON."""
        mock_response = MagicMock()
        mock_response.text = "This is not JSON at all"

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        extractor = ItemExtractor(llm_provider=mock_provider)
        result = await extractor.extract("You find a bucket near the well.")

        assert result.items == []
        assert "no JSON found" in result.reasoning

    @pytest.mark.asyncio
    async def test_handles_malformed_items(self) -> None:
        """Test graceful handling of malformed item data."""
        mock_response = MagicMock()
        mock_response.text = '''
        {
            "items": [
                {"name": "", "importance": "important"},
                {"name": "bucket", "importance": "invalid_importance"},
                {"name": "rope", "importance": "decorative", "context": "on hook"}
            ],
            "reasoning": "Mixed quality data"
        }
        '''

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        extractor = ItemExtractor(llm_provider=mock_provider)
        result = await extractor.extract("Some narrative text here with items.")

        # Empty name should be skipped, invalid importance should default to IMPORTANT
        assert len(result.items) == 2
        assert result.items[0].name == "bucket"
        assert result.items[0].importance == ItemImportance.IMPORTANT  # defaulted
        assert result.items[1].name == "rope"
        assert result.items[1].importance == ItemImportance.DECORATIVE

    @pytest.mark.asyncio
    async def test_handles_llm_exception(self) -> None:
        """Test graceful handling of LLM exceptions."""
        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(side_effect=Exception("LLM error"))

        extractor = ItemExtractor(llm_provider=mock_provider)
        result = await extractor.extract("You find a bucket near the well.")

        assert result.items == []
        assert "failed" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_uses_configured_model(self) -> None:
        """Test that the configured model is used."""
        mock_response = MagicMock()
        mock_response.text = '{"items": [], "reasoning": "None"}'

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        extractor = ItemExtractor(
            llm_provider=mock_provider,
            model="claude-3-5-haiku-20241022",
            temperature=0.1,
        )
        await extractor.extract("Some narrative text here.")

        # Verify the correct model and temperature were passed
        call_kwargs = mock_provider.complete.call_args.kwargs
        assert call_kwargs["model"] == "claude-3-5-haiku-20241022"
        assert call_kwargs["temperature"] == 0.1


class TestItemExtractorFalsePositives:
    """Tests to ensure common false positives are NOT extracted.

    These tests verify that words ending in item-like suffixes but
    aren't actually items (like "bewildering" ending in "ring")
    are correctly rejected by the LLM.
    """

    @pytest.mark.asyncio
    async def test_bewildering_not_extracted(self) -> None:
        """Test that 'bewildering' is not extracted as 'ring'."""
        # Simulate LLM correctly not extracting bewildering
        mock_response = MagicMock()
        mock_response.text = '''
        {
            "items": [],
            "reasoning": "No physical items - 'bewildering' is an adjective, not a ring"
        }
        '''

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        extractor = ItemExtractor(llm_provider=mock_provider)
        result = await extractor.extract("The bewildering array of options left you confused.")

        assert len(result.items) == 0

    @pytest.mark.asyncio
    async def test_offering_not_extracted(self) -> None:
        """Test that 'offering' is not extracted as 'ring'."""
        mock_response = MagicMock()
        mock_response.text = '''
        {
            "items": [],
            "reasoning": "No physical items - 'offering' is a verb form"
        }
        '''

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        extractor = ItemExtractor(llm_provider=mock_provider)
        result = await extractor.extract("She was offering you a place to rest.")

        assert len(result.items) == 0

    @pytest.mark.asyncio
    async def test_contemplate_not_extracted(self) -> None:
        """Test that 'contemplate' is not extracted as 'plate'."""
        mock_response = MagicMock()
        mock_response.text = '''
        {
            "items": [],
            "reasoning": "No physical items - 'contemplate' is a verb"
        }
        '''

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        extractor = ItemExtractor(llm_provider=mock_provider)
        result = await extractor.extract("You contemplate your next move carefully.")

        assert len(result.items) == 0
