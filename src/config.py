"""Application configuration using pydantic-settings."""

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


ProviderType = Literal["anthropic", "openai", "ollama", "qwen-agent"]


@dataclass
class ProviderConfig:
    """Parsed provider:model configuration."""

    provider: ProviderType
    model: str


def parse_provider_config(value: str, default_provider: ProviderType = "ollama") -> ProviderConfig:
    """Parse 'provider:model' format into ProviderConfig.

    Args:
        value: String in format 'provider:model' or just 'model'.
        default_provider: Provider to use if only model is specified.

    Returns:
        ProviderConfig with provider and model.

    Examples:
        >>> parse_provider_config("ollama:magmell:32b")
        ProviderConfig(provider='ollama', model='magmell:32b')

        >>> parse_provider_config("qwen-agent:qwen3:32b")
        ProviderConfig(provider='qwen-agent', model='qwen3:32b')

        >>> parse_provider_config("anthropic:claude-3-5-haiku-20241022")
        ProviderConfig(provider='anthropic', model='claude-3-5-haiku-20241022')

        >>> parse_provider_config("magmell:32b")  # No provider prefix
        ProviderConfig(provider='ollama', model='magmell:32b')
    """
    valid_providers = ("anthropic", "openai", "ollama", "qwen-agent")

    # Check if first part is a known provider
    if ":" in value:
        first_part = value.split(":")[0]
        if first_part in valid_providers:
            provider = first_part
            model = value[len(first_part) + 1 :]  # Everything after 'provider:'
            return ProviderConfig(provider=provider, model=model)  # type: ignore

    # No provider prefix - use default
    return ProviderConfig(provider=default_provider, model=value)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql://localhost/rpg_game"

    # API Keys
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    openai_base_url: str | None = None  # Custom endpoint for vLLM/DeepSeek

    # Ollama Settings
    ollama_base_url: str = "http://localhost:11434"

    # ==========================================================================
    # Task-Specific LLM Configuration (provider:model format)
    # ==========================================================================
    # Format: "provider:model" where provider is one of:
    #   - ollama (local Ollama)
    #   - qwen-agent (Ollama with qwen-agent tool calling)
    #   - anthropic (Claude API)
    #   - openai (OpenAI API or compatible)
    #
    # Examples:
    #   NARRATOR=ollama:magmell:32b
    #   REASONING=qwen-agent:qwen3:32b
    #   CHEAP=anthropic:claude-3-5-haiku-20241022

    narrator: str = "ollama:magmell:32b"  # Prose narration, scene descriptions
    reasoning: str = "ollama:qwen3:32b"  # Combat, tools, extraction, intent parsing
    cheap: str = "ollama:qwen3:32b"  # Summaries, quick decisions

    # ==========================================================================
    # Legacy Settings (kept for backwards compatibility)
    # ==========================================================================
    llm_provider: ProviderType = "anthropic"  # Default for get_provider()
    gm_model: str = "claude-sonnet-4-20250514"
    extraction_model: str = "claude-sonnet-4-20250514"
    cheap_model: str = "claude-3-5-haiku-20241022"

    # Game Settings
    default_setting: str = "fantasy"
    checkpoint_interval: int = 15  # Turns between checkpoints
    pipeline: Literal["legacy", "system-authority", "scene-first"] = "system-authority"

    # Debug
    debug: bool = False
    log_llm_calls: bool = False
    llm_log_dir: str = "logs/llm"

    # ==========================================================================
    # World Server / Anticipation Settings
    # ==========================================================================
    # Enable anticipatory scene generation (pre-generates likely next scenes)
    anticipation_enabled: bool = False  # Disabled by default until stable
    anticipation_cache_size: int = 5  # Max number of pre-generated scenes to cache

    # Minimal Context Mode (for local LLMs)
    # None = auto-detect based on provider (enabled for ollama/qwen-agent)
    # True = always use minimal context
    # False = always use full context
    use_minimal_context: bool | None = None

    # ==========================================================================
    # Parsed Configuration Properties
    # ==========================================================================

    @property
    def narrator_config(self) -> ProviderConfig:
        """Get parsed narrator provider config."""
        return parse_provider_config(self.narrator)

    @property
    def reasoning_config(self) -> ProviderConfig:
        """Get parsed reasoning provider config."""
        return parse_provider_config(self.reasoning)

    @property
    def cheap_config(self) -> ProviderConfig:
        """Get parsed cheap provider config."""
        return parse_provider_config(self.cheap)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience alias
settings = get_settings()
