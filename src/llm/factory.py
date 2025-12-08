"""LLM provider factory.

Factory functions for creating LLM provider instances.
"""

from typing import Literal, TYPE_CHECKING

from src.config import settings
from src.llm.base import LLMProvider
from src.llm.anthropic_provider import AnthropicProvider
from src.llm.openai_provider import OpenAIProvider
from src.llm.exceptions import UnsupportedProviderError

if TYPE_CHECKING:
    from src.llm.logging_provider import LoggingProvider


ProviderType = Literal["anthropic", "openai"]


def get_provider(
    provider: ProviderType | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> LLMProvider:
    """Get an LLM provider instance.

    Args:
        provider: Provider name (defaults to settings.llm_provider).
        model: Default model for the provider.
        base_url: Custom base URL (for OpenAI-compatible APIs).

    Returns:
        Configured LLMProvider instance. If log_llm_calls is enabled,
        returns a LoggingProvider wrapper.

    Raises:
        UnsupportedProviderError: If provider is not supported.

    Examples:
        # Default provider from settings
        provider = get_provider()

        # Specific provider
        provider = get_provider("anthropic", model="claude-3-haiku-20240307")

        # DeepSeek (OpenAI-compatible)
        provider = get_provider(
            "openai",
            model="deepseek-chat",
            base_url="https://api.deepseek.com",
        )

        # Local Ollama
        provider = get_provider(
            "openai",
            model="llama2",
            base_url="http://localhost:11434/v1",
        )
    """
    provider = provider or settings.llm_provider

    if provider == "anthropic":
        llm_provider: LLMProvider = AnthropicProvider(
            api_key=settings.anthropic_api_key,
            default_model=model or settings.gm_model,
        )
    elif provider == "openai":
        llm_provider = OpenAIProvider(
            api_key=settings.openai_api_key,
            default_model=model or settings.gm_model,
            base_url=base_url or settings.openai_base_url,
        )
    else:
        raise UnsupportedProviderError(f"Provider '{provider}' is not supported")

    # Wrap with logging if enabled
    if settings.log_llm_calls:
        from src.llm.logging_provider import LoggingProvider
        from src.llm.audit_logger import get_audit_logger

        llm_provider = LoggingProvider(llm_provider, get_audit_logger())

    return llm_provider


def get_gm_provider() -> LLMProvider:
    """Get provider configured for GameMaster (narrative generation).

    Uses the gm_model from settings for high-quality narrative output.

    Returns:
        LLMProvider configured for GM use.
    """
    return get_provider(model=settings.gm_model)


def get_extraction_provider() -> LLMProvider:
    """Get provider configured for entity extraction.

    Uses the extraction_model from settings.

    Returns:
        LLMProvider configured for extraction.
    """
    return get_provider(model=settings.extraction_model)


def get_cheap_provider() -> LLMProvider:
    """Get provider configured for cheap/fast operations.

    Uses the cheap_model from settings for cost-effective operations.

    Returns:
        LLMProvider configured for cheap operations.
    """
    return get_provider(model=settings.cheap_model)
