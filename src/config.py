"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql://localhost/rpg_game"

    # LLM Providers
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_provider: Literal["anthropic", "openai"] = "anthropic"
    openai_base_url: str | None = None  # Custom endpoint for Ollama/vLLM/DeepSeek

    # Model Selection
    gm_model: str = "claude-sonnet-4-20250514"  # Primary narrative model
    extraction_model: str = "claude-sonnet-4-20250514"  # Entity extraction
    cheap_model: str = "claude-3-5-haiku-20241022"  # For quick/cheap operations

    # Game Settings
    default_setting: str = "fantasy"
    checkpoint_interval: int = 15  # Turns between checkpoints

    # Debug
    debug: bool = False
    log_llm_calls: bool = False


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience alias
settings = get_settings()
