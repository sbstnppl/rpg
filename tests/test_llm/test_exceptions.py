"""Tests for LLM exceptions."""

import pytest

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


class TestLLMError:
    """Tests for base LLMError."""

    def test_llm_error_is_exception(self):
        """Test that LLMError is an Exception."""
        error = LLMError("Something went wrong")
        assert isinstance(error, Exception)

    def test_llm_error_message(self):
        """Test error message."""
        error = LLMError("Test error message")
        assert str(error) == "Test error message"


class TestProviderError:
    """Tests for ProviderError."""

    def test_provider_error_default(self):
        """Test default provider error."""
        error = ProviderError("Provider failed")
        assert str(error) == "Provider failed"
        assert error.is_retryable is False
        assert error.status_code is None

    def test_provider_error_retryable(self):
        """Test retryable provider error."""
        error = ProviderError("Temporary failure", is_retryable=True)
        assert error.is_retryable is True

    def test_provider_error_with_status_code(self):
        """Test provider error with status code."""
        error = ProviderError("Server error", is_retryable=True, status_code=500)
        assert error.status_code == 500

    def test_provider_error_is_llm_error(self):
        """Test that ProviderError inherits from LLMError."""
        error = ProviderError("Test")
        assert isinstance(error, LLMError)


class TestRateLimitError:
    """Tests for RateLimitError."""

    def test_rate_limit_error_default(self):
        """Test default rate limit error."""
        error = RateLimitError()
        assert str(error) == "Rate limit exceeded"
        assert error.is_retryable is True
        assert error.status_code == 429
        assert error.retry_after is None

    def test_rate_limit_error_with_retry_after(self):
        """Test rate limit with retry-after header."""
        error = RateLimitError(retry_after=30.0)
        assert error.retry_after == 30.0

    def test_rate_limit_error_custom_message(self):
        """Test custom rate limit message."""
        error = RateLimitError("Too many requests, slow down")
        assert str(error) == "Too many requests, slow down"

    def test_rate_limit_error_is_provider_error(self):
        """Test that RateLimitError inherits from ProviderError."""
        error = RateLimitError()
        assert isinstance(error, ProviderError)


class TestAuthenticationError:
    """Tests for AuthenticationError."""

    def test_auth_error_default(self):
        """Test default authentication error."""
        error = AuthenticationError()
        assert str(error) == "Authentication failed"
        assert error.is_retryable is False
        assert error.status_code == 401

    def test_auth_error_custom_message(self):
        """Test custom authentication error message."""
        error = AuthenticationError("Invalid API key")
        assert str(error) == "Invalid API key"

    def test_auth_error_is_not_retryable(self):
        """Test that auth errors are not retryable."""
        error = AuthenticationError()
        assert error.is_retryable is False


class TestContentPolicyError:
    """Tests for ContentPolicyError."""

    def test_content_policy_error_default(self):
        """Test default content policy error."""
        error = ContentPolicyError()
        assert str(error) == "Content policy violation"
        assert error.is_retryable is False

    def test_content_policy_error_custom_message(self):
        """Test custom content policy message."""
        error = ContentPolicyError("Content flagged for violence")
        assert str(error) == "Content flagged for violence"


class TestContextLengthError:
    """Tests for ContextLengthError."""

    def test_context_length_error(self):
        """Test context length error."""
        error = ContextLengthError("Input too long")
        assert str(error) == "Input too long"
        assert error.is_retryable is False
        assert error.max_tokens is None

    def test_context_length_error_with_max_tokens(self):
        """Test context length error with max tokens."""
        error = ContextLengthError("Context exceeds limit", max_tokens=100000)
        assert error.max_tokens == 100000


class TestUnsupportedProviderError:
    """Tests for UnsupportedProviderError."""

    def test_unsupported_provider_error(self):
        """Test unsupported provider error."""
        error = UnsupportedProviderError("Provider 'gemini' not supported")
        assert str(error) == "Provider 'gemini' not supported"

    def test_unsupported_provider_is_llm_error(self):
        """Test that UnsupportedProviderError inherits from LLMError."""
        error = UnsupportedProviderError("Test")
        assert isinstance(error, LLMError)


class TestStructuredOutputError:
    """Tests for StructuredOutputError."""

    def test_structured_output_error(self):
        """Test structured output error."""
        error = StructuredOutputError("Failed to parse JSON")
        assert str(error) == "Failed to parse JSON"
        assert error.raw_output is None

    def test_structured_output_error_with_raw(self):
        """Test structured output error with raw output."""
        error = StructuredOutputError(
            "Invalid JSON",
            raw_output="{invalid json",
        )
        assert error.raw_output == "{invalid json"

    def test_structured_output_error_is_llm_error(self):
        """Test that StructuredOutputError inherits from LLMError."""
        error = StructuredOutputError("Test")
        assert isinstance(error, LLMError)


class TestExceptionHierarchy:
    """Tests for exception inheritance hierarchy."""

    def test_all_inherit_from_llm_error(self):
        """Test that all custom exceptions inherit from LLMError."""
        exceptions = [
            ProviderError("test"),
            RateLimitError(),
            AuthenticationError(),
            ContentPolicyError(),
            ContextLengthError("test"),
            UnsupportedProviderError("test"),
            StructuredOutputError("test"),
        ]
        for exc in exceptions:
            assert isinstance(exc, LLMError), f"{type(exc).__name__} should inherit from LLMError"

    def test_provider_errors_inherit_from_provider_error(self):
        """Test that provider-specific errors inherit from ProviderError."""
        exceptions = [
            RateLimitError(),
            AuthenticationError(),
            ContentPolicyError(),
            ContextLengthError("test"),
        ]
        for exc in exceptions:
            assert isinstance(exc, ProviderError), f"{type(exc).__name__} should inherit from ProviderError"
