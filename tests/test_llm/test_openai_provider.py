"""Tests for OpenAI provider."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.llm.openai_provider import OpenAIProvider
from src.llm.message_types import Message
from src.llm.tool_types import ToolDefinition, ToolParameter
from src.llm.base import LLMProvider
from src.llm.exceptions import (
    AuthenticationError,
    RateLimitError,
)


@pytest.fixture
def mock_openai_response():
    """Create a mock OpenAI API response."""
    choice = MagicMock()
    choice.message = MagicMock()
    choice.message.content = "Hello, world!"
    choice.message.tool_calls = None
    choice.finish_reason = "stop"

    response = MagicMock()
    response.choices = [choice]
    response.model = "gpt-4o"
    response.usage = MagicMock(
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
    )
    return response


@pytest.fixture
def mock_openai_tool_response():
    """Create a mock OpenAI API response with tool calls."""
    tool_call = MagicMock()
    tool_call.id = "call_123"
    tool_call.type = "function"
    tool_call.function = MagicMock()
    tool_call.function.name = "get_weather"
    tool_call.function.arguments = '{"city": "Paris"}'

    choice = MagicMock()
    choice.message = MagicMock()
    choice.message.content = None
    choice.message.tool_calls = [tool_call]
    choice.finish_reason = "tool_calls"

    response = MagicMock()
    response.choices = [choice]
    response.model = "gpt-4o"
    response.usage = MagicMock(
        prompt_tokens=20,
        completion_tokens=15,
        total_tokens=35,
    )
    return response


@pytest.fixture
def mock_client(mock_openai_response):
    """Create a mock OpenAI client."""
    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
    return client


class TestOpenAIProviderInit:
    """Tests for OpenAIProvider initialization."""

    def test_create_with_api_key(self):
        """Test creating provider with explicit API key."""
        provider = OpenAIProvider(api_key="test-key")
        assert provider.provider_name == "openai"

    def test_default_model(self):
        """Test default model is set."""
        provider = OpenAIProvider(api_key="test-key")
        assert provider.default_model == "gpt-4o"

    def test_custom_default_model(self):
        """Test setting a custom default model."""
        provider = OpenAIProvider(
            api_key="test-key",
            default_model="gpt-4-turbo",
        )
        assert provider.default_model == "gpt-4-turbo"

    def test_custom_base_url(self):
        """Test setting a custom base URL for compatible APIs."""
        provider = OpenAIProvider(
            api_key="test-key",
            base_url="https://api.deepseek.com",
        )
        # Provider name reflects it's OpenAI-compatible
        assert provider.provider_name == "openai"

    def test_implements_protocol(self):
        """Test that OpenAIProvider implements LLMProvider protocol."""
        provider = OpenAIProvider(api_key="test-key")
        assert isinstance(provider, LLMProvider)


class TestOpenAIProviderComplete:
    """Tests for OpenAIProvider.complete method."""

    @pytest.mark.asyncio
    async def test_complete_basic(self, mock_client):
        """Test basic completion."""
        provider = OpenAIProvider(api_key="test-key", client=mock_client)

        messages = [Message.user("Hello")]
        response = await provider.complete(messages)

        assert response.content == "Hello, world!"
        assert response.finish_reason == "stop"
        assert response.model == "gpt-4o"

    @pytest.mark.asyncio
    async def test_complete_with_system_prompt(self, mock_client):
        """Test completion with system prompt."""
        provider = OpenAIProvider(api_key="test-key", client=mock_client)

        messages = [Message.user("Hello")]
        await provider.complete(messages, system_prompt="You are helpful.", think=True)

        # Verify system prompt was added as first message
        call_args = mock_client.chat.completions.create.call_args
        api_messages = call_args.kwargs["messages"]
        assert api_messages[0]["role"] == "system"
        assert api_messages[0]["content"] == "You are helpful."

    @pytest.mark.asyncio
    async def test_complete_with_parameters(self, mock_client):
        """Test completion with custom parameters."""
        provider = OpenAIProvider(api_key="test-key", client=mock_client)

        messages = [Message.user("Hello")]
        await provider.complete(
            messages,
            model="gpt-4-turbo",
            max_tokens=1000,
            temperature=0.5,
        )

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["model"] == "gpt-4-turbo"
        assert call_args.kwargs["max_tokens"] == 1000
        assert call_args.kwargs["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_complete_usage_stats(self, mock_client):
        """Test that usage stats are captured."""
        provider = OpenAIProvider(api_key="test-key", client=mock_client)

        messages = [Message.user("Hello")]
        response = await provider.complete(messages)

        assert response.usage is not None
        assert response.usage.prompt_tokens == 10
        assert response.usage.completion_tokens == 5
        assert response.usage.total_tokens == 15


class TestOpenAIProviderCompleteWithTools:
    """Tests for OpenAIProvider.complete_with_tools method."""

    @pytest.mark.asyncio
    async def test_complete_with_tools_returns_tool_call(self, mock_openai_tool_response):
        """Test that tool calls are parsed correctly."""
        mock_client = MagicMock()
        mock_client.chat = MagicMock()
        mock_client.chat.completions = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_tool_response)

        provider = OpenAIProvider(api_key="test-key", client=mock_client)

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
        """Test that tools are formatted correctly for OpenAI API."""
        provider = OpenAIProvider(api_key="test-key", client=mock_client)

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

        call_args = mock_client.chat.completions.create.call_args
        api_tools = call_args.kwargs["tools"]
        assert len(api_tools) == 1
        assert api_tools[0]["type"] == "function"
        assert api_tools[0]["function"]["name"] == "test_tool"


class TestOpenAIProviderMessageConversion:
    """Tests for message format conversion."""

    @pytest.mark.asyncio
    async def test_user_message_conversion(self, mock_client):
        """Test user message conversion."""
        provider = OpenAIProvider(api_key="test-key", client=mock_client)

        messages = [Message.user("Hello")]
        await provider.complete(messages, think=True)

        call_args = mock_client.chat.completions.create.call_args
        api_messages = call_args.kwargs["messages"]
        assert api_messages[0]["role"] == "user"
        assert api_messages[0]["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_assistant_message_conversion(self, mock_client):
        """Test assistant message conversion."""
        provider = OpenAIProvider(api_key="test-key", client=mock_client)

        messages = [
            Message.user("Hello"),
            Message.assistant("Hi there!"),
            Message.user("How are you?"),
        ]
        await provider.complete(messages, think=True)

        call_args = mock_client.chat.completions.create.call_args
        api_messages = call_args.kwargs["messages"]
        assert api_messages[0]["role"] == "user"
        assert api_messages[1]["role"] == "assistant"
        assert api_messages[2]["role"] == "user"

    @pytest.mark.asyncio
    async def test_system_message_in_messages(self, mock_client):
        """Test that system messages are included in messages array."""
        provider = OpenAIProvider(api_key="test-key", client=mock_client)

        messages = [
            Message.system("You are helpful."),
            Message.user("Hello"),
        ]
        await provider.complete(messages, think=True)

        call_args = mock_client.chat.completions.create.call_args
        api_messages = call_args.kwargs["messages"]
        assert api_messages[0]["role"] == "system"
        assert api_messages[0]["content"] == "You are helpful."
        assert api_messages[1]["role"] == "user"


class TestOpenAIProviderErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_authentication_error(self):
        """Test authentication error handling."""
        from openai import AuthenticationError as OpenAIAuthError

        mock_client = MagicMock()
        mock_client.chat = MagicMock()
        mock_client.chat.completions = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=OpenAIAuthError(
                message="Invalid API key",
                response=MagicMock(status_code=401),
                body={"error": {"message": "Invalid API key"}},
            )
        )

        provider = OpenAIProvider(api_key="invalid-key", client=mock_client)

        messages = [Message.user("Hello")]
        with pytest.raises(AuthenticationError):
            await provider.complete(messages)

    @pytest.mark.asyncio
    async def test_rate_limit_error(self):
        """Test rate limit error handling."""
        from openai import RateLimitError as OpenAIRateLimitError

        mock_client = MagicMock()
        mock_client.chat = MagicMock()
        mock_client.chat.completions = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=OpenAIRateLimitError(
                message="Rate limit exceeded",
                response=MagicMock(status_code=429),
                body={"error": {"message": "Rate limit exceeded"}},
            )
        )

        provider = OpenAIProvider(api_key="test-key", client=mock_client)

        messages = [Message.user("Hello")]
        with pytest.raises(RateLimitError):
            await provider.complete(messages)


class TestOpenAIProviderTokenCounting:
    """Tests for token counting."""

    def test_count_tokens_basic(self):
        """Test basic token counting with tiktoken."""
        provider = OpenAIProvider(api_key="test-key")
        count = provider.count_tokens("Hello, world!")
        assert isinstance(count, int)
        assert count > 0

    def test_count_tokens_empty(self):
        """Test token counting for empty string."""
        provider = OpenAIProvider(api_key="test-key")
        count = provider.count_tokens("")
        assert count == 0

    def test_count_tokens_long_text(self):
        """Test token counting for longer text."""
        provider = OpenAIProvider(api_key="test-key")
        text = "This is a longer piece of text that should result in more tokens. " * 10
        count = provider.count_tokens(text)
        assert count > 50


class TestOpenAICompatibleAPIs:
    """Tests for OpenAI-compatible APIs (DeepSeek, Ollama, etc.)."""

    def test_deepseek_configuration(self):
        """Test configuration for DeepSeek API."""
        provider = OpenAIProvider(
            api_key="deepseek-key",
            base_url="https://api.deepseek.com",
            default_model="deepseek-chat",
        )
        assert provider.default_model == "deepseek-chat"

    def test_ollama_configuration(self):
        """Test configuration for local Ollama."""
        provider = OpenAIProvider(
            api_key="ollama",  # Ollama doesn't need real key
            base_url="http://localhost:11434/v1",
            default_model="llama2",
        )
        assert provider.default_model == "llama2"


class TestOpenAIProviderThinkingMode:
    """Tests for thinking mode (Qwen3-style /nothink prefix)."""

    @pytest.mark.asyncio
    async def test_complete_default_nothink(self, mock_client):
        """Test that complete() defaults to think=False and adds /nothink prefix."""
        provider = OpenAIProvider(api_key="test-key", client=mock_client)

        messages = [Message.user("Hello")]
        await provider.complete(messages, system_prompt="You are helpful.")

        call_args = mock_client.chat.completions.create.call_args
        api_messages = call_args.kwargs["messages"]
        assert api_messages[0]["role"] == "system"
        assert api_messages[0]["content"] == "/nothink\nYou are helpful."

    @pytest.mark.asyncio
    async def test_complete_think_true_no_prefix(self, mock_client):
        """Test that think=True does not add /nothink prefix."""
        provider = OpenAIProvider(api_key="test-key", client=mock_client)

        messages = [Message.user("Hello")]
        await provider.complete(messages, system_prompt="You are helpful.", think=True)

        call_args = mock_client.chat.completions.create.call_args
        api_messages = call_args.kwargs["messages"]
        assert api_messages[0]["role"] == "system"
        assert api_messages[0]["content"] == "You are helpful."

    @pytest.mark.asyncio
    async def test_complete_nothink_without_system_prompt(self, mock_client):
        """Test that /nothink is added even without system prompt."""
        provider = OpenAIProvider(api_key="test-key", client=mock_client)

        messages = [Message.user("Hello")]
        await provider.complete(messages)

        call_args = mock_client.chat.completions.create.call_args
        api_messages = call_args.kwargs["messages"]
        assert api_messages[0]["role"] == "system"
        assert api_messages[0]["content"] == "/nothink"

    @pytest.mark.asyncio
    async def test_complete_with_tools_default_think(self, mock_client):
        """Test that complete_with_tools() defaults to think=True."""
        provider = OpenAIProvider(api_key="test-key", client=mock_client)

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
        await provider.complete_with_tools(
            messages, tools, system_prompt="You are helpful."
        )

        call_args = mock_client.chat.completions.create.call_args
        api_messages = call_args.kwargs["messages"]
        assert api_messages[0]["role"] == "system"
        # Default think=True means no /nothink prefix
        assert api_messages[0]["content"] == "You are helpful."

    @pytest.mark.asyncio
    async def test_complete_with_tools_think_false(self, mock_client):
        """Test that complete_with_tools(think=False) adds /nothink prefix."""
        provider = OpenAIProvider(api_key="test-key", client=mock_client)

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
        await provider.complete_with_tools(
            messages, tools, system_prompt="You are helpful.", think=False
        )

        call_args = mock_client.chat.completions.create.call_args
        api_messages = call_args.kwargs["messages"]
        assert api_messages[0]["role"] == "system"
        assert api_messages[0]["content"] == "/nothink\nYou are helpful."

    def test_strip_thinking_complete_block(self):
        """Test stripping complete <think>...</think> blocks."""
        content = "<think>Let me think about this...</think>Here is my answer."
        result = OpenAIProvider._strip_thinking(content)
        assert result == "Here is my answer."

    def test_strip_thinking_multiple_blocks(self):
        """Test stripping multiple thinking blocks."""
        content = "<think>First thought</think>Part 1 <think>Second thought</think>Part 2"
        result = OpenAIProvider._strip_thinking(content)
        assert result == "Part 1 Part 2"

    def test_strip_thinking_incomplete_block(self):
        """Test stripping incomplete thinking block (cut off)."""
        content = "Start of response <think>incomplete thinking that was cut off"
        result = OpenAIProvider._strip_thinking(content)
        assert result == "Start of response"

    def test_strip_thinking_no_thinking(self):
        """Test that content without thinking tags is unchanged."""
        content = "Just a normal response without any thinking."
        result = OpenAIProvider._strip_thinking(content)
        assert result == "Just a normal response without any thinking."

    def test_strip_thinking_multiline(self):
        """Test stripping multiline thinking blocks."""
        content = """<think>
This is a long
multiline
thinking block
</think>Final answer here."""
        result = OpenAIProvider._strip_thinking(content)
        assert result == "Final answer here."
