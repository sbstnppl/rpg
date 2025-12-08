"""Tests for LLM provider factory."""

import pytest
from unittest.mock import patch, MagicMock

from src.llm.factory import get_provider, get_gm_provider, get_cheap_provider
from src.llm.anthropic_provider import AnthropicProvider
from src.llm.openai_provider import OpenAIProvider
from src.llm.exceptions import UnsupportedProviderError


class TestGetProvider:
    """Tests for get_provider factory function."""

    def test_get_anthropic_provider(self):
        """Test getting Anthropic provider."""
        with patch("src.llm.factory.settings") as mock_settings:
            mock_settings.llm_provider = "anthropic"
            mock_settings.anthropic_api_key = "test-key"
            mock_settings.gm_model = "claude-sonnet-4-20250514"
            mock_settings.log_llm_calls = False

            provider = get_provider("anthropic")
            assert isinstance(provider, AnthropicProvider)
            assert provider.provider_name == "anthropic"

    def test_get_openai_provider(self):
        """Test getting OpenAI provider."""
        with patch("src.llm.factory.settings") as mock_settings:
            mock_settings.llm_provider = "openai"
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_base_url = None
            mock_settings.gm_model = "gpt-4o"
            mock_settings.log_llm_calls = False

            provider = get_provider("openai")
            assert isinstance(provider, OpenAIProvider)
            assert provider.provider_name == "openai"

    def test_get_default_provider_from_settings(self):
        """Test getting provider from settings."""
        with patch("src.llm.factory.settings") as mock_settings:
            mock_settings.llm_provider = "anthropic"
            mock_settings.anthropic_api_key = "test-key"
            mock_settings.gm_model = "claude-sonnet-4-20250514"
            mock_settings.log_llm_calls = False

            provider = get_provider()
            assert isinstance(provider, AnthropicProvider)

    def test_get_provider_with_custom_model(self):
        """Test getting provider with custom model."""
        with patch("src.llm.factory.settings") as mock_settings:
            mock_settings.anthropic_api_key = "test-key"
            mock_settings.gm_model = "claude-sonnet-4-20250514"
            mock_settings.log_llm_calls = False

            provider = get_provider("anthropic", model="claude-3-haiku-20240307")
            assert provider.default_model == "claude-3-haiku-20240307"

    def test_get_provider_with_base_url(self):
        """Test getting OpenAI provider with custom base URL."""
        with patch("src.llm.factory.settings") as mock_settings:
            mock_settings.openai_api_key = "deepseek-key"
            mock_settings.openai_base_url = None
            mock_settings.gm_model = "gpt-4o"
            mock_settings.log_llm_calls = False

            provider = get_provider(
                "openai",
                model="deepseek-chat",
                base_url="https://api.deepseek.com",
            )
            assert isinstance(provider, OpenAIProvider)
            assert provider.default_model == "deepseek-chat"

    def test_unsupported_provider_raises_error(self):
        """Test that unsupported provider raises error."""
        with pytest.raises(UnsupportedProviderError) as exc_info:
            get_provider("gemini")
        assert "gemini" in str(exc_info.value).lower()


class TestConvenienceFunctions:
    """Tests for convenience factory functions."""

    def test_get_gm_provider(self):
        """Test getting GM provider."""
        with patch("src.llm.factory.settings") as mock_settings:
            mock_settings.llm_provider = "anthropic"
            mock_settings.anthropic_api_key = "test-key"
            mock_settings.gm_model = "claude-sonnet-4-20250514"
            mock_settings.log_llm_calls = False

            provider = get_gm_provider()
            assert provider.default_model == "claude-sonnet-4-20250514"

    def test_get_cheap_provider(self):
        """Test getting cheap provider."""
        with patch("src.llm.factory.settings") as mock_settings:
            mock_settings.llm_provider = "anthropic"
            mock_settings.anthropic_api_key = "test-key"
            mock_settings.cheap_model = "claude-haiku-3"
            mock_settings.log_llm_calls = False

            provider = get_cheap_provider()
            assert provider.default_model == "claude-haiku-3"


class TestProviderCaching:
    """Tests for provider instance behavior."""

    def test_get_provider_returns_new_instance(self):
        """Test that get_provider returns new instances."""
        with patch("src.llm.factory.settings") as mock_settings:
            mock_settings.llm_provider = "anthropic"
            mock_settings.anthropic_api_key = "test-key"
            mock_settings.gm_model = "claude-sonnet-4-20250514"
            mock_settings.log_llm_calls = False

            provider1 = get_provider()
            provider2 = get_provider()
            # Each call should return a new provider instance
            assert provider1 is not provider2
