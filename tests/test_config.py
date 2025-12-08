"""Tests for application configuration."""

import os
from unittest.mock import patch

import pytest

from src.config import Settings, get_settings


class TestSettingsDefaults:
    """Tests for default configuration values."""

    def test_default_database_url(self):
        """Default database URL should be PostgreSQL localhost."""
        # Create settings without reading .env file or env vars
        # by using _env_file=None and clearing DATABASE_URL from env
        import os
        env_backup = os.environ.get("DATABASE_URL")
        try:
            if "DATABASE_URL" in os.environ:
                del os.environ["DATABASE_URL"]
            # Create settings without .env file
            settings = Settings(_env_file=None)
            assert settings.database_url == "postgresql://localhost/rpg_game"
        finally:
            if env_backup is not None:
                os.environ["DATABASE_URL"] = env_backup

    def test_default_llm_provider_is_anthropic(self):
        """Default LLM provider should be Anthropic."""
        settings = Settings()
        assert settings.llm_provider == "anthropic"

    def test_default_gm_model(self):
        """Default GM model should be Claude Sonnet."""
        settings = Settings()
        assert "claude" in settings.gm_model.lower()
        assert "sonnet" in settings.gm_model.lower()

    def test_default_cheap_model(self):
        """Default cheap model should be Claude Haiku."""
        settings = Settings()
        assert "claude" in settings.cheap_model.lower()
        assert "haiku" in settings.cheap_model.lower()

    def test_default_setting_is_fantasy(self):
        """Default game setting should be fantasy."""
        settings = Settings()
        assert settings.default_setting == "fantasy"

    def test_default_checkpoint_interval(self):
        """Default checkpoint interval should be 15 turns."""
        settings = Settings()
        assert settings.checkpoint_interval == 15

    def test_default_debug_is_false(self):
        """Debug mode should be off by default."""
        settings = Settings()
        assert settings.debug is False


class TestSettingsValidation:
    """Tests for configuration validation."""

    def test_llm_provider_must_be_valid(self):
        """LLM provider must be 'anthropic' or 'openai'."""
        # Valid providers should work
        with patch.dict(os.environ, {"LLM_PROVIDER": "anthropic"}, clear=False):
            settings = Settings()
            assert settings.llm_provider == "anthropic"

        with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}, clear=False):
            settings = Settings()
            assert settings.llm_provider == "openai"

    def test_model_names_follow_claude_format(self):
        """Model names should follow Claude naming convention."""
        settings = Settings()

        # GM model should be valid Claude model
        assert settings.gm_model.startswith("claude-")

        # Cheap model should be valid Claude model
        assert settings.cheap_model.startswith("claude-")

        # Extraction model should be valid Claude model
        assert settings.extraction_model.startswith("claude-")


class TestSettingsEnvironment:
    """Tests for environment variable loading."""

    def test_loads_anthropic_api_key_from_env(self):
        """Should load Anthropic API key from environment."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-123"}, clear=False):
            settings = Settings()
            assert settings.anthropic_api_key == "test-key-123"

    def test_loads_openai_api_key_from_env(self):
        """Should load OpenAI API key from environment."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-456"}, clear=False):
            settings = Settings()
            assert settings.openai_api_key == "sk-test-456"

    def test_loads_database_url_from_env(self):
        """Should load database URL from environment."""
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://user:pass@host/db"},
            clear=False,
        ):
            settings = Settings()
            assert settings.database_url == "postgresql://user:pass@host/db"

    def test_env_overrides_defaults(self):
        """Environment variables should override default values."""
        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "openai",
                "DEFAULT_SETTING": "scifi",
                "DEBUG": "true",
            },
            clear=False,
        ):
            settings = Settings()
            assert settings.llm_provider == "openai"
            assert settings.default_setting == "scifi"
            assert settings.debug is True


class TestGetSettings:
    """Tests for the get_settings function."""

    def test_get_settings_returns_settings_instance(self):
        """get_settings should return a Settings instance."""
        # Clear the cache first
        get_settings.cache_clear()
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_get_settings_is_cached(self):
        """get_settings should return cached instance."""
        get_settings.cache_clear()
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2
