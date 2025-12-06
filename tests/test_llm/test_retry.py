"""Tests for LLM retry utilities."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from src.llm.retry import RetryConfig, with_retry
from src.llm.exceptions import RateLimitError, ProviderError, AuthenticationError


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""

    def test_default_config(self):
        """Test default retry configuration."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True

    def test_custom_config(self):
        """Test custom retry configuration."""
        config = RetryConfig(
            max_retries=5,
            initial_delay=0.5,
            max_delay=30.0,
            exponential_base=3.0,
            jitter=False,
        )
        assert config.max_retries == 5
        assert config.initial_delay == 0.5
        assert config.max_delay == 30.0


class TestWithRetry:
    """Tests for with_retry function."""

    @pytest.mark.asyncio
    async def test_successful_call_no_retry(self):
        """Test that successful calls don't retry."""
        mock_func = AsyncMock(return_value="success")

        result = await with_retry(mock_func)

        assert result == "success"
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self):
        """Test retry on rate limit error."""
        mock_func = AsyncMock(
            side_effect=[
                RateLimitError("Rate limited"),
                "success",
            ]
        )
        config = RetryConfig(initial_delay=0.01, jitter=False)

        result = await with_retry(mock_func, config=config)

        assert result == "success"
        assert mock_func.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_retryable_provider_error(self):
        """Test retry on retryable provider error."""
        mock_func = AsyncMock(
            side_effect=[
                ProviderError("Server error", is_retryable=True, status_code=500),
                "success",
            ]
        )
        config = RetryConfig(initial_delay=0.01, jitter=False)

        result = await with_retry(mock_func, config=config)

        assert result == "success"
        assert mock_func.call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_auth_error(self):
        """Test no retry on authentication error."""
        mock_func = AsyncMock(side_effect=AuthenticationError("Invalid key"))
        config = RetryConfig(initial_delay=0.01, jitter=False)

        with pytest.raises(AuthenticationError):
            await with_retry(mock_func, config=config)

        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_non_retryable_error(self):
        """Test no retry on non-retryable provider error."""
        mock_func = AsyncMock(
            side_effect=ProviderError("Bad request", is_retryable=False)
        )
        config = RetryConfig(initial_delay=0.01, jitter=False)

        with pytest.raises(ProviderError):
            await with_retry(mock_func, config=config)

        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test that max retries are respected."""
        mock_func = AsyncMock(side_effect=RateLimitError("Rate limited"))
        config = RetryConfig(max_retries=2, initial_delay=0.01, jitter=False)

        with pytest.raises(RateLimitError):
            await with_retry(mock_func, config=config)

        # Initial call + 2 retries = 3 total calls
        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_respects_retry_after(self):
        """Test that retry_after is respected."""
        mock_func = AsyncMock(
            side_effect=[
                RateLimitError("Rate limited", retry_after=0.02),
                "success",
            ]
        )
        config = RetryConfig(initial_delay=0.01, jitter=False)

        start_time = asyncio.get_event_loop().time()
        result = await with_retry(mock_func, config=config)
        elapsed = asyncio.get_event_loop().time() - start_time

        assert result == "success"
        # Should wait at least retry_after seconds
        assert elapsed >= 0.02

    @pytest.mark.asyncio
    async def test_passes_arguments(self):
        """Test that arguments are passed to the function."""
        mock_func = AsyncMock(return_value="success")

        await with_retry(mock_func, "arg1", "arg2", kwarg1="value1")

        mock_func.assert_called_once_with("arg1", "arg2", kwarg1="value1")

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Test exponential backoff timing."""
        call_times = []

        async def slow_fail():
            call_times.append(asyncio.get_event_loop().time())
            raise RateLimitError("Rate limited")

        mock_func = AsyncMock(side_effect=slow_fail)
        config = RetryConfig(
            max_retries=2,
            initial_delay=0.05,
            exponential_base=2.0,
            jitter=False,
        )

        with pytest.raises(RateLimitError):
            await with_retry(mock_func, config=config)

        # Check delays are approximately exponential
        # First retry: ~0.05s, Second retry: ~0.1s
        if len(call_times) >= 2:
            first_delay = call_times[1] - call_times[0]
            assert first_delay >= 0.04  # Allow some tolerance

        if len(call_times) >= 3:
            second_delay = call_times[2] - call_times[1]
            assert second_delay >= 0.08  # Should be roughly 2x first


class TestRetryWithCallable:
    """Tests for retry with different callable types."""

    @pytest.mark.asyncio
    async def test_retry_with_coroutine_function(self):
        """Test retry with a coroutine function."""
        call_count = 0

        async def my_coroutine():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RateLimitError("Rate limited")
            return "success"

        config = RetryConfig(initial_delay=0.01, jitter=False)
        result = await with_retry(my_coroutine, config=config)

        assert result == "success"
        assert call_count == 2
