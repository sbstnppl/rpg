"""LLM exception definitions.

Custom exception hierarchy for LLM operations.
"""


class LLMError(Exception):
    """Base exception for LLM operations."""

    pass


class ProviderError(LLMError):
    """Error from the LLM provider.

    Attributes:
        is_retryable: Whether this error can be retried.
        status_code: HTTP status code if applicable.
    """

    def __init__(
        self,
        message: str,
        is_retryable: bool = False,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.is_retryable = is_retryable
        self.status_code = status_code


class RateLimitError(ProviderError):
    """Rate limit exceeded.

    Attributes:
        retry_after: Seconds to wait before retrying.
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, is_retryable=True, status_code=429)
        self.retry_after = retry_after


class AuthenticationError(ProviderError):
    """Invalid API key or authentication failed."""

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message, is_retryable=False, status_code=401)


class ContentPolicyError(ProviderError):
    """Content violated provider's usage policies."""

    def __init__(self, message: str = "Content policy violation") -> None:
        super().__init__(message, is_retryable=False)


class ContextLengthError(ProviderError):
    """Input exceeds model's context window.

    Attributes:
        max_tokens: Maximum tokens for the model.
    """

    def __init__(self, message: str, max_tokens: int | None = None) -> None:
        super().__init__(message, is_retryable=False)
        self.max_tokens = max_tokens


class UnsupportedProviderError(LLMError):
    """Requested provider is not supported."""

    pass


class StructuredOutputError(LLMError):
    """Failed to parse structured output.

    Attributes:
        raw_output: The raw output that failed to parse.
    """

    def __init__(self, message: str, raw_output: str | None = None) -> None:
        super().__init__(message)
        self.raw_output = raw_output
