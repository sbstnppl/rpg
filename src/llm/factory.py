"""LLM provider factory.

Factory functions for creating LLM provider instances.
Supports task-specific provider:model configuration.
"""

from typing import TYPE_CHECKING

from src.config import settings, ProviderConfig, ProviderType
from src.llm.base import LLMProvider
from src.llm.anthropic_provider import AnthropicProvider
from src.llm.openai_provider import OpenAIProvider
from src.llm.exceptions import UnsupportedProviderError

if TYPE_CHECKING:
    from src.llm.logging_provider import LoggingProvider


def _create_provider(config: ProviderConfig) -> LLMProvider:
    """Create an LLM provider from a ProviderConfig.

    Args:
        config: Parsed provider configuration with provider type and model.

    Returns:
        Configured LLMProvider instance.

    Raises:
        UnsupportedProviderError: If provider type is not supported.
    """
    if config.provider == "anthropic":
        provider: LLMProvider = AnthropicProvider(
            api_key=settings.anthropic_api_key,
            default_model=config.model,
        )
    elif config.provider == "openai":
        provider = OpenAIProvider(
            api_key=settings.openai_api_key,
            default_model=config.model,
            base_url=settings.openai_base_url,
        )
    elif config.provider == "ollama":
        from src.llm.ollama_provider import OllamaProvider

        provider = OllamaProvider(
            base_url=settings.ollama_base_url,
            default_model=config.model,
        )
    elif config.provider == "qwen-agent":
        from src.llm.qwen_agent_provider import QwenAgentProvider

        ollama_base = settings.ollama_base_url
        if not ollama_base.endswith("/v1"):
            ollama_base = f"{ollama_base}/v1"
        provider = QwenAgentProvider(
            base_url=ollama_base,
            default_model=config.model,
        )
    else:
        raise UnsupportedProviderError(f"Provider '{config.provider}' is not supported")

    # Wrap with logging if enabled
    if settings.log_llm_calls:
        from src.llm.logging_provider import LoggingProvider
        from src.llm.audit_logger import get_audit_logger

        provider = LoggingProvider(provider, get_audit_logger())

    return provider


# =============================================================================
# Task-Specific Providers (use NARRATOR, REASONING, CHEAP env vars)
# =============================================================================


def get_narrator_provider() -> LLMProvider:
    """Get provider configured for prose narration.

    Uses the NARRATOR env var (format: provider:model).
    Default: ollama:magmell:32b

    Best for:
    - Scene introductions
    - LOOK descriptions
    - Atmospheric prose

    Returns:
        LLMProvider configured for narration.
    """
    return _create_provider(settings.narrator_config)


def get_reasoning_provider() -> LLMProvider:
    """Get provider configured for reasoning tasks.

    Uses the REASONING env var (format: provider:model).
    Default: ollama:qwen3:32b

    Best for:
    - Combat resolution
    - Tool calling
    - Entity extraction
    - Intent classification

    Returns:
        LLMProvider configured for reasoning.
    """
    return _create_provider(settings.reasoning_config)


def get_creative_provider() -> LLMProvider:
    """Get provider configured for creative tasks.

    Uses the same config as reasoning provider.
    Caller should pass `think=False` for faster creative output.

    Best for:
    - NPC dialogue generation
    - Character trait generation
    - Lore/world-building

    Returns:
        LLMProvider configured for creative tasks.
    """
    return get_reasoning_provider()


def get_cheap_provider() -> LLMProvider:
    """Get provider configured for cheap/fast operations.

    Uses the CHEAP env var (format: provider:model).
    Default: ollama:qwen3:32b

    Best for:
    - Summaries
    - Quick decisions
    - Background tasks

    Returns:
        LLMProvider configured for cheap operations.
    """
    return _create_provider(settings.cheap_config)


# =============================================================================
# Legacy Providers (for backwards compatibility)
# =============================================================================


def get_provider(
    provider: ProviderType | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> LLMProvider:
    """Get an LLM provider instance (legacy API).

    Prefer using get_narrator_provider(), get_reasoning_provider(), or
    get_cheap_provider() for new code.

    Args:
        provider: Provider name (defaults to settings.llm_provider).
        model: Default model for the provider.
        base_url: Custom base URL (for OpenAI-compatible APIs).

    Returns:
        Configured LLMProvider instance.
    """
    provider_type = provider or settings.llm_provider

    if provider_type == "anthropic":
        llm_provider: LLMProvider = AnthropicProvider(
            api_key=settings.anthropic_api_key,
            default_model=model or settings.gm_model,
        )
    elif provider_type == "openai":
        llm_provider = OpenAIProvider(
            api_key=settings.openai_api_key,
            default_model=model or settings.gm_model,
            base_url=base_url or settings.openai_base_url,
        )
    elif provider_type == "ollama":
        from src.llm.ollama_provider import OllamaProvider

        llm_provider = OllamaProvider(
            base_url=base_url or settings.ollama_base_url,
            default_model=model or settings.reasoning_config.model,
        )
    elif provider_type == "qwen-agent":
        from src.llm.qwen_agent_provider import QwenAgentProvider

        ollama_base = base_url or settings.ollama_base_url
        if not ollama_base.endswith("/v1"):
            ollama_base = f"{ollama_base}/v1"
        llm_provider = QwenAgentProvider(
            base_url=ollama_base,
            default_model=model or settings.reasoning_config.model,
        )
    else:
        raise UnsupportedProviderError(f"Provider '{provider_type}' is not supported")

    if settings.log_llm_calls:
        from src.llm.logging_provider import LoggingProvider
        from src.llm.audit_logger import get_audit_logger

        llm_provider = LoggingProvider(llm_provider, get_audit_logger())

    return llm_provider


def get_gm_provider() -> LLMProvider:
    """Get provider for GameMaster (legacy, uses reasoning provider)."""
    return get_reasoning_provider()


def get_extraction_provider() -> LLMProvider:
    """Get provider for extraction (legacy, uses reasoning provider)."""
    return get_reasoning_provider()
