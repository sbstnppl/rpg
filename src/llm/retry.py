"""Retry utilities for LLM operations.

Provides exponential backoff with jitter for handling transient failures.
"""

import asyncio
import random
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, TypeVar

from src.llm.exceptions import RateLimitError, ProviderError

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_retries: Maximum number of retry attempts.
        initial_delay: Initial delay in seconds.
        max_delay: Maximum delay between retries.
        exponential_base: Base for exponential backoff.
        jitter: Whether to add random jitter.
    """

    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


async def with_retry(
    func: Callable[..., Awaitable[T]],
    *args: Any,
    config: RetryConfig | None = None,
    **kwargs: Any,
) -> T:
    """Execute async function with retry on transient failures.

    Retries on:
    - Rate limit errors (with exponential backoff)
    - Transient API errors (5xx)

    Does not retry on:
    - Authentication errors
    - Invalid request errors
    - Content policy violations

    Args:
        func: Async function to execute.
        *args: Positional arguments for func.
        config: Retry configuration.
        **kwargs: Keyword arguments for func.

    Returns:
        Result from successful function call.

    Raises:
        The last exception if all retries fail.

    Example:
        response = await with_retry(
            provider.complete,
            messages=messages,
            max_tokens=1024,
            config=RetryConfig(max_retries=3),
        )
    """
    config = config or RetryConfig()
    last_error: Exception | None = None

    for attempt in range(config.max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except RateLimitError as e:
            last_error = e
            if attempt == config.max_retries:
                raise
            delay = _calculate_delay(attempt, config, e.retry_after)
            await asyncio.sleep(delay)
        except ProviderError as e:
            if not e.is_retryable:
                raise
            last_error = e
            if attempt == config.max_retries:
                raise
            delay = _calculate_delay(attempt, config)
            await asyncio.sleep(delay)

    # Should not reach here, but raise last error if we do
    if last_error:
        raise last_error
    raise RuntimeError("Max retries exceeded without error")


def _calculate_delay(
    attempt: int,
    config: RetryConfig,
    retry_after: float | None = None,
) -> float:
    """Calculate delay for the next retry attempt.

    Uses exponential backoff with optional jitter.

    Args:
        attempt: Current attempt number (0-indexed).
        config: Retry configuration.
        retry_after: Optional server-specified retry delay.

    Returns:
        Delay in seconds.
    """
    # Calculate exponential delay
    exponential_delay = config.initial_delay * (config.exponential_base ** attempt)

    # Cap at max_delay
    delay = min(exponential_delay, config.max_delay)

    # Respect retry-after if provided and larger
    if retry_after is not None:
        delay = max(delay, retry_after)

    # Add jitter if enabled
    if config.jitter:
        # Add random jitter between 0 and 25% of delay
        jitter = random.uniform(0, delay * 0.25)
        delay += jitter

    return delay
