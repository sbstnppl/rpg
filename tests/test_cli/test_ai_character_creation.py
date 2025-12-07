"""Tests for AI-assisted character creation."""

import json
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from src.schemas.settings import get_setting_schema


class TestParseAttributeSuggestion:
    """Tests for _parse_attribute_suggestion function."""

    def test_parses_json_with_suggested_attributes(self):
        """Should parse JSON block with suggested_attributes key."""
        from src.cli.commands.character import _parse_attribute_suggestion

        response = """
        Based on your concept, I suggest these attributes:

        {"suggested_attributes": {"strength": 15, "dexterity": 14, "constitution": 13, "intelligence": 10, "wisdom": 12, "charisma": 8}}

        This build emphasizes physical prowess.
        """

        result = _parse_attribute_suggestion(response)

        assert result is not None
        assert result["strength"] == 15
        assert result["dexterity"] == 14

    def test_parses_simple_attribute_json(self):
        """Should parse simple JSON with attribute keys."""
        from src.cli.commands.character import _parse_attribute_suggestion

        response = """
        {"strength": 14, "dexterity": 12, "constitution": 15, "intelligence": 10, "wisdom": 8, "charisma": 13}
        """

        result = _parse_attribute_suggestion(response)

        assert result is not None
        assert result["strength"] == 14

    def test_returns_none_for_no_json(self):
        """Should return None when no JSON found."""
        from src.cli.commands.character import _parse_attribute_suggestion

        response = "Let me think about your character concept. What kind of playstyle do you prefer?"

        result = _parse_attribute_suggestion(response)

        assert result is None

    def test_returns_none_for_invalid_json(self):
        """Should return None for malformed JSON."""
        from src.cli.commands.character import _parse_attribute_suggestion

        response = '{"strength": invalid}'

        result = _parse_attribute_suggestion(response)

        assert result is None


class TestValidateAIAttributes:
    """Tests for _validate_ai_attributes function."""

    def test_valid_attributes_pass(self):
        """Should accept valid point-buy attributes."""
        from src.cli.commands.character import _validate_ai_attributes

        schema = get_setting_schema("fantasy")
        attributes = {
            "strength": 15,
            "dexterity": 14,
            "constitution": 13,
            "intelligence": 12,
            "wisdom": 10,
            "charisma": 8,
        }

        is_valid, error = _validate_ai_attributes(attributes, schema)

        assert is_valid is True
        assert error is None

    def test_missing_attribute_fails(self):
        """Should reject attributes with missing keys."""
        from src.cli.commands.character import _validate_ai_attributes

        schema = get_setting_schema("fantasy")
        attributes = {
            "strength": 15,
            "dexterity": 14,
            # Missing other attributes
        }

        is_valid, error = _validate_ai_attributes(attributes, schema)

        assert is_valid is False
        assert "Missing" in error

    def test_extra_attribute_fails(self):
        """Should reject attributes with extra keys."""
        from src.cli.commands.character import _validate_ai_attributes

        schema = get_setting_schema("fantasy")
        attributes = {
            "strength": 15,
            "dexterity": 14,
            "constitution": 13,
            "intelligence": 12,
            "wisdom": 10,
            "charisma": 8,
            "luck": 10,  # Extra attribute
        }

        is_valid, error = _validate_ai_attributes(attributes, schema)

        assert is_valid is False
        assert "Extra" in error


class TestParseCharacterComplete:
    """Tests for _parse_character_complete function."""

    def test_parses_complete_character(self):
        """Should parse character_complete JSON."""
        from src.cli.commands.character import _parse_character_complete

        response = '''
        Your character is ready!

        {"character_complete": true, "name": "Aragorn", "background": "A ranger from the north"}
        '''

        result = _parse_character_complete(response)

        assert result is not None
        assert result["character_complete"] is True
        assert result["name"] == "Aragorn"

    def test_returns_none_when_not_complete(self):
        """Should return None when character_complete is false."""
        from src.cli.commands.character import _parse_character_complete

        response = '{"character_complete": false}'

        result = _parse_character_complete(response)

        assert result is None

    def test_returns_none_for_no_json(self):
        """Should return None when no JSON found."""
        from src.cli.commands.character import _parse_character_complete

        response = "Let's continue developing your character."

        result = _parse_character_complete(response)

        assert result is None


class TestAICharacterCreationAsync:
    """Tests for the async AI character creation function."""

    @pytest.fixture
    def mock_llm_response(self):
        """Create a mock LLM response."""
        response = MagicMock()
        response.content = "Welcome! What kind of character would you like to create?"
        return response

    @pytest.fixture
    def mock_provider(self, mock_llm_response):
        """Create a mock LLM provider."""
        provider = MagicMock()
        provider.complete = AsyncMock(return_value=mock_llm_response)
        return provider

    @pytest.fixture
    def patch_console(self):
        """Patch all console output functions."""
        with patch("src.cli.commands.character.console"):
            with patch("src.cli.commands.character.display_ai_message"):
                with patch("src.cli.commands.character.display_info"):
                    with patch("src.cli.commands.character.display_error"):
                        with patch("src.cli.commands.character.display_suggested_attributes"):
                            yield

    @pytest.mark.asyncio
    async def test_sends_initial_greeting(self, mock_provider, patch_console):
        """Should send initial greeting to LLM."""
        from src.cli.commands.character import _ai_character_creation_async
        import typer

        schema = get_setting_schema("fantasy")

        with patch("src.llm.factory.get_cheap_provider", return_value=mock_provider):
            with patch("src.cli.commands.character.prompt_ai_input", return_value="quit"):
                try:
                    await _ai_character_creation_async(schema)
                except typer.Exit:
                    pass  # Expected on quit

        # Verify LLM was called for initial greeting
        mock_provider.complete.assert_called()

    @pytest.mark.asyncio
    async def test_handles_quit_command(self, mock_provider, patch_console):
        """Should handle quit command gracefully."""
        from src.cli.commands.character import _ai_character_creation_async
        import typer

        schema = get_setting_schema("fantasy")

        with patch("src.llm.factory.get_cheap_provider", return_value=mock_provider):
            with patch("src.cli.commands.character.prompt_ai_input", return_value="quit"):
                with pytest.raises(typer.Exit) as exc_info:
                    await _ai_character_creation_async(schema)

        # Should exit with code 0 (clean exit)
        assert exc_info.value.exit_code == 0

    @pytest.mark.asyncio
    async def test_conversation_continues_on_input(self, mock_provider, patch_console):
        """Should continue conversation when user provides input."""
        from src.cli.commands.character import _ai_character_creation_async
        import typer

        schema = get_setting_schema("fantasy")

        # Simulate: user input -> response -> quit
        input_sequence = ["I want to be a warrior", "quit"]
        input_iter = iter(input_sequence)

        with patch("src.llm.factory.get_cheap_provider", return_value=mock_provider):
            with patch("src.cli.commands.character.prompt_ai_input", side_effect=lambda: next(input_iter)):
                try:
                    await _ai_character_creation_async(schema)
                except typer.Exit:
                    pass

        # Should have called LLM at least twice (initial + response to input)
        assert mock_provider.complete.call_count >= 2

    @pytest.mark.asyncio
    async def test_handles_llm_error(self, mock_provider, patch_console):
        """Should handle LLM errors gracefully."""
        from src.cli.commands.character import _ai_character_creation_async
        import typer

        schema = get_setting_schema("fantasy")

        # Make LLM raise an error on initial call
        mock_provider.complete = AsyncMock(side_effect=Exception("API Error"))

        with patch("src.llm.factory.get_cheap_provider", return_value=mock_provider):
            with pytest.raises(typer.Exit) as exc_info:
                await _ai_character_creation_async(schema)

        # Should exit with error code
        assert exc_info.value.exit_code == 1


class TestSlugify:
    """Tests for the slugify helper function."""

    def test_simple_name(self):
        """Should convert simple name to slug."""
        from src.cli.commands.character import slugify

        assert slugify("John") == "john"

    def test_name_with_spaces(self):
        """Should replace spaces with underscores."""
        from src.cli.commands.character import slugify

        assert slugify("John Smith") == "john_smith"

    def test_name_with_special_chars(self):
        """Should remove special characters."""
        from src.cli.commands.character import slugify

        assert slugify("John O'Brien") == "john_obrien"

    def test_name_with_accents(self):
        """Should normalize accented characters."""
        from src.cli.commands.character import slugify

        assert slugify("José García") == "jose_garcia"

    def test_multiple_spaces(self):
        """Should collapse multiple spaces."""
        from src.cli.commands.character import slugify

        assert slugify("John   Smith") == "john_smith"
