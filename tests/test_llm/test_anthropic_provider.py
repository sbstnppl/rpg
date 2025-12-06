"""Tests for Anthropic provider."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.llm.anthropic_provider import AnthropicProvider
from src.llm.message_types import Message
from src.llm.tool_types import ToolDefinition, ToolParameter
from src.llm.base import LLMProvider
from src.llm.exceptions import (
    AuthenticationError,
    RateLimitError,
)


@pytest.fixture
def mock_anthropic_response():
    """Create a mock Anthropic API response."""
    response = MagicMock()
    response.content = [MagicMock(type="text", text="Hello, world!")]
    response.stop_reason = "end_turn"
    response.model = "claude-sonnet-4-20250514"
    response.usage = MagicMock(
        input_tokens=10,
        output_tokens=5,
    )
    return response


@pytest.fixture
def mock_anthropic_tool_response():
    """Create a mock Anthropic API response with tool use."""
    tool_use = MagicMock()
    tool_use.type = "tool_use"
    tool_use.id = "call_123"
    tool_use.name = "get_weather"
    tool_use.input = {"city": "Paris"}

    response = MagicMock()
    response.content = [tool_use]
    response.stop_reason = "tool_use"
    response.model = "claude-sonnet-4-20250514"
    response.usage = MagicMock(input_tokens=20, output_tokens=15)
    return response


@pytest.fixture
def mock_client(mock_anthropic_response):
    """Create a mock Anthropic client."""
    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = AsyncMock(return_value=mock_anthropic_response)
    return client


class TestAnthropicProviderInit:
    """Tests for AnthropicProvider initialization."""

    def test_create_with_api_key(self):
        """Test creating provider with explicit API key."""
        provider = AnthropicProvider(api_key="test-key")
        assert provider.provider_name == "anthropic"

    def test_default_model(self):
        """Test default model is set."""
        provider = AnthropicProvider(api_key="test-key")
        assert provider.default_model == "claude-sonnet-4-20250514"

    def test_custom_default_model(self):
        """Test setting a custom default model."""
        provider = AnthropicProvider(
            api_key="test-key",
            default_model="claude-3-haiku-20240307",
        )
        assert provider.default_model == "claude-3-haiku-20240307"

    def test_implements_protocol(self):
        """Test that AnthropicProvider implements LLMProvider protocol."""
        provider = AnthropicProvider(api_key="test-key")
        assert isinstance(provider, LLMProvider)


class TestAnthropicProviderComplete:
    """Tests for AnthropicProvider.complete method."""

    @pytest.mark.asyncio
    async def test_complete_basic(self, mock_client, mock_anthropic_response):
        """Test basic completion."""
        provider = AnthropicProvider(api_key="test-key", client=mock_client)

        messages = [Message.user("Hello")]
        response = await provider.complete(messages)

        assert response.content == "Hello, world!"
        assert response.finish_reason == "end_turn"
        assert response.model == "claude-sonnet-4-20250514"

    @pytest.mark.asyncio
    async def test_complete_with_system_prompt(self, mock_client):
        """Test completion with system prompt."""
        provider = AnthropicProvider(api_key="test-key", client=mock_client)

        messages = [Message.user("Hello")]
        await provider.complete(messages, system_prompt="You are helpful.")

        # Verify system prompt was passed
        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs["system"] == "You are helpful."

    @pytest.mark.asyncio
    async def test_complete_with_parameters(self, mock_client):
        """Test completion with custom parameters."""
        provider = AnthropicProvider(api_key="test-key", client=mock_client)

        messages = [Message.user("Hello")]
        await provider.complete(
            messages,
            model="claude-3-opus-20240229",
            max_tokens=1000,
            temperature=0.5,
        )

        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs["model"] == "claude-3-opus-20240229"
        assert call_args.kwargs["max_tokens"] == 1000
        assert call_args.kwargs["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_complete_usage_stats(self, mock_client):
        """Test that usage stats are captured."""
        provider = AnthropicProvider(api_key="test-key", client=mock_client)

        messages = [Message.user("Hello")]
        response = await provider.complete(messages)

        assert response.usage is not None
        assert response.usage.prompt_tokens == 10
        assert response.usage.completion_tokens == 5
        assert response.usage.total_tokens == 15


class TestAnthropicProviderCompleteWithTools:
    """Tests for AnthropicProvider.complete_with_tools method."""

    @pytest.mark.asyncio
    async def test_complete_with_tools_returns_tool_call(self, mock_anthropic_tool_response):
        """Test that tool calls are parsed correctly."""
        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_anthropic_tool_response)

        provider = AnthropicProvider(api_key="test-key", client=mock_client)

        messages = [Message.user("What's the weather in Paris?")]
        tools = [
            ToolDefinition(
                name="get_weather",
                description="Get weather for a city",
                parameters=(
                    ToolParameter(name="city", type="string", description="City name"),
                ),
            ),
        ]
        response = await provider.complete_with_tools(messages, tools)

        assert response.has_tool_calls
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].id == "call_123"
        assert response.tool_calls[0].name == "get_weather"
        assert response.tool_calls[0].arguments == {"city": "Paris"}

    @pytest.mark.asyncio
    async def test_complete_with_tools_format(self, mock_client):
        """Test that tools are formatted correctly for Anthropic API."""
        provider = AnthropicProvider(api_key="test-key", client=mock_client)

        messages = [Message.user("Hello")]
        tools = [
            ToolDefinition(
                name="test_tool",
                description="A test tool",
                parameters=(
                    ToolParameter(name="arg1", type="string", description="First arg"),
                ),
            ),
        ]
        await provider.complete_with_tools(messages, tools)

        call_args = mock_client.messages.create.call_args
        api_tools = call_args.kwargs["tools"]
        assert len(api_tools) == 1
        assert api_tools[0]["name"] == "test_tool"
        assert "input_schema" in api_tools[0]


class TestAnthropicProviderMessageConversion:
    """Tests for message format conversion."""

    @pytest.mark.asyncio
    async def test_user_message_conversion(self, mock_client):
        """Test user message conversion."""
        provider = AnthropicProvider(api_key="test-key", client=mock_client)

        messages = [Message.user("Hello")]
        await provider.complete(messages)

        call_args = mock_client.messages.create.call_args
        api_messages = call_args.kwargs["messages"]
        assert api_messages[0]["role"] == "user"
        assert api_messages[0]["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_assistant_message_conversion(self, mock_client):
        """Test assistant message conversion."""
        provider = AnthropicProvider(api_key="test-key", client=mock_client)

        messages = [
            Message.user("Hello"),
            Message.assistant("Hi there!"),
            Message.user("How are you?"),
        ]
        await provider.complete(messages)

        call_args = mock_client.messages.create.call_args
        api_messages = call_args.kwargs["messages"]
        assert api_messages[0]["role"] == "user"
        assert api_messages[1]["role"] == "assistant"
        assert api_messages[2]["role"] == "user"

    @pytest.mark.asyncio
    async def test_system_message_extraction(self, mock_client):
        """Test that system messages are extracted to system parameter."""
        provider = AnthropicProvider(api_key="test-key", client=mock_client)

        messages = [
            Message.system("You are helpful."),
            Message.user("Hello"),
        ]
        await provider.complete(messages)

        call_args = mock_client.messages.create.call_args
        # System message should be passed as system parameter
        assert call_args.kwargs["system"] == "You are helpful."
        # Only user message in messages list
        api_messages = call_args.kwargs["messages"]
        assert len(api_messages) == 1
        assert api_messages[0]["role"] == "user"


class TestAnthropicProviderErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_authentication_error(self):
        """Test authentication error handling."""
        from anthropic import AuthenticationError as AnthropicAuthError
        import httpx

        # Create a mock response for the exception
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 401
        mock_response.headers = {}

        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(
            side_effect=AnthropicAuthError(
                message="Invalid API key",
                response=mock_response,
                body={"error": {"message": "Invalid API key"}},
            )
        )

        provider = AnthropicProvider(api_key="invalid-key", client=mock_client)

        messages = [Message.user("Hello")]
        with pytest.raises(AuthenticationError):
            await provider.complete(messages)

    @pytest.mark.asyncio
    async def test_rate_limit_error(self):
        """Test rate limit error handling."""
        from anthropic import RateLimitError as AnthropicRateLimitError
        import httpx

        # Create a mock response for the exception
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 429
        mock_response.headers = {}

        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(
            side_effect=AnthropicRateLimitError(
                message="Rate limit exceeded",
                response=mock_response,
                body={"error": {"message": "Rate limit exceeded"}},
            )
        )

        provider = AnthropicProvider(api_key="test-key", client=mock_client)

        messages = [Message.user("Hello")]
        with pytest.raises(RateLimitError):
            await provider.complete(messages)


class TestAnthropicProviderTokenCounting:
    """Tests for token counting."""

    def test_count_tokens_basic(self):
        """Test basic token counting."""
        provider = AnthropicProvider(api_key="test-key")
        count = provider.count_tokens("Hello, world!")
        assert isinstance(count, int)
        assert count > 0

    def test_count_tokens_empty(self):
        """Test token counting for empty string."""
        provider = AnthropicProvider(api_key="test-key")
        count = provider.count_tokens("")
        assert count == 0

    def test_count_tokens_long_text(self):
        """Test token counting for longer text."""
        provider = AnthropicProvider(api_key="test-key")
        text = "This is a longer piece of text that should result in more tokens. " * 10
        count = provider.count_tokens(text)
        assert count > 50  # Should be significantly more than short text
