"""LLM provider abstraction layer.

This module provides a unified interface for interacting with various LLM providers
including Anthropic, OpenAI, and OpenAI-compatible APIs (DeepSeek, Ollama, vLLM).

Quick Start:
    from src.llm import get_provider, Message

    provider = get_provider()  # Uses default from settings
    response = await provider.complete(
        messages=[Message.user("Tell me about dragons")],
        max_tokens=500,
    )
    print(response.content)

For OpenAI-compatible APIs:
    provider = get_provider(
        "openai",
        model="deepseek-chat",
        base_url="https://api.deepseek.com",
    )
"""

# Message types
from src.llm.message_types import Message, MessageContent, MessageRole

# Tool types
from src.llm.tool_types import ToolDefinition, ToolParameter

# Response types
from src.llm.response_types import LLMResponse, ToolCall, UsageStats

# Protocol
from src.llm.base import LLMProvider

# Providers
from src.llm.anthropic_provider import AnthropicProvider
from src.llm.openai_provider import OpenAIProvider
from src.llm.ollama_provider import OllamaProvider

# Factory
from src.llm.factory import (
    get_provider,
    get_gm_provider,
    get_extraction_provider,
    get_cheap_provider,
)

# Retry utilities
from src.llm.retry import RetryConfig, with_retry

# Audit logging
from src.llm.audit_logger import (
    set_audit_context,
    get_audit_context,
    get_audit_logger,
    LLMAuditContext,
    LLMAuditEntry,
    LLMAuditLogger,
)
from src.llm.logging_provider import LoggingProvider

# Exceptions
from src.llm.exceptions import (
    LLMError,
    ProviderError,
    RateLimitError,
    AuthenticationError,
    ContentPolicyError,
    ContextLengthError,
    UnsupportedProviderError,
    StructuredOutputError,
)

__all__ = [
    # Message types
    "Message",
    "MessageContent",
    "MessageRole",
    # Tool types
    "ToolDefinition",
    "ToolParameter",
    # Response types
    "LLMResponse",
    "ToolCall",
    "UsageStats",
    # Protocol
    "LLMProvider",
    # Providers
    "AnthropicProvider",
    "OpenAIProvider",
    "OllamaProvider",
    # Factory
    "get_provider",
    "get_gm_provider",
    "get_extraction_provider",
    "get_cheap_provider",
    # Retry
    "RetryConfig",
    "with_retry",
    # Audit logging
    "set_audit_context",
    "get_audit_context",
    "get_audit_logger",
    "LLMAuditContext",
    "LLMAuditEntry",
    "LLMAuditLogger",
    "LoggingProvider",
    # Exceptions
    "LLMError",
    "ProviderError",
    "RateLimitError",
    "AuthenticationError",
    "ContentPolicyError",
    "ContextLengthError",
    "UnsupportedProviderError",
    "StructuredOutputError",
]
