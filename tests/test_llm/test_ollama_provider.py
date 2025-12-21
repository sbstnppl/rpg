"""Tests for Ollama provider."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.llm.ollama_provider import OllamaProvider
from src.llm.message_types import Message
from src.llm.tool_types import ToolDefinition, ToolParameter
from src.llm.base import LLMProvider


@pytest.fixture
def mock_ollama_response():
    """Create a mock LangChain AIMessage response."""
    response = MagicMock()
    response.content = "Hello from Ollama!"
    response.tool_calls = None
    return response


@pytest.fixture
def mock_ollama_tool_response():
    """Create a mock LangChain AIMessage response with tool calls."""
    response = MagicMock()
    response.content = ""
    response.tool_calls = [
        {
            "id": "call_123",
            "name": "get_weather",
            "args": {"city": "Paris"},
        }
    ]
    return response


@pytest.fixture
def mock_chat_ollama(mock_ollama_response):
    """Create a mock ChatOllama client."""
    mock_client = MagicMock()
    mock_client.ainvoke = AsyncMock(return_value=mock_ollama_response)
    return mock_client


class TestOllamaProviderInit:
    """Tests for OllamaProvider initialization."""

    def test_create_with_defaults(self):
        """Test creating provider with default settings."""
        provider = OllamaProvider()
        assert provider.provider_name == "ollama"
        assert provider.default_model == "llama3"

    def test_custom_base_url(self):
        """Test creating provider with custom base URL."""
        provider = OllamaProvider(base_url="http://192.168.1.100:11434")
        assert provider._base_url == "http://192.168.1.100:11434"

    def test_custom_default_model(self):
        """Test creating provider with custom default model."""
        provider = OllamaProvider(default_model="llama3.1")
        assert provider.default_model == "llama3.1"

    def test_implements_protocol(self):
        """Test that OllamaProvider implements LLMProvider protocol."""
        provider = OllamaProvider()
        assert isinstance(provider, LLMProvider)


class TestOllamaProviderComplete:
    """Tests for OllamaProvider.complete method."""

    @pytest.mark.asyncio
    async def test_complete_basic(self, mock_ollama_response):
        """Test basic completion."""
        with patch("src.llm.ollama_provider.ChatOllama") as MockChatOllama:
            mock_instance = MagicMock()
            mock_instance.ainvoke = AsyncMock(return_value=mock_ollama_response)
            MockChatOllama.return_value = mock_instance

            provider = OllamaProvider()
            messages = [Message.user("Hello")]
            response = await provider.complete(messages)

            assert response.content == "Hello from Ollama!"
            assert response.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_complete_with_system_prompt(self, mock_ollama_response):
        """Test completion with system prompt."""
        with patch("src.llm.ollama_provider.ChatOllama") as MockChatOllama:
            mock_instance = MagicMock()
            mock_instance.ainvoke = AsyncMock(return_value=mock_ollama_response)
            MockChatOllama.return_value = mock_instance

            provider = OllamaProvider()
            messages = [Message.user("Hello")]
            # Use think=True to avoid /nothink injection for this test
            await provider.complete(messages, system_prompt="You are helpful.", think=True)

            # Verify ChatOllama was called
            MockChatOllama.assert_called_once()

            # Verify ainvoke was called with messages
            mock_instance.ainvoke.assert_called_once()
            call_args = mock_instance.ainvoke.call_args[0][0]
            # First message should be system message
            assert call_args[0].content == "You are helpful."

    @pytest.mark.asyncio
    async def test_complete_with_parameters(self, mock_ollama_response):
        """Test completion with custom parameters."""
        with patch("src.llm.ollama_provider.ChatOllama") as MockChatOllama:
            mock_instance = MagicMock()
            mock_instance.ainvoke = AsyncMock(return_value=mock_ollama_response)
            MockChatOllama.return_value = mock_instance

            provider = OllamaProvider()
            messages = [Message.user("Hello")]
            await provider.complete(
                messages,
                model="llama3.1",
                max_tokens=1000,
                temperature=0.5,
            )

            # Verify ChatOllama was initialized with correct params
            call_kwargs = MockChatOllama.call_args.kwargs
            assert call_kwargs["model"] == "llama3.1"
            assert call_kwargs["temperature"] == 0.5
            assert call_kwargs["num_predict"] == 1000


class TestOllamaProviderCompleteWithTools:
    """Tests for OllamaProvider.complete_with_tools method."""

    @pytest.mark.asyncio
    async def test_complete_with_tools_returns_tool_call(self, mock_ollama_tool_response):
        """Test that tool calls are parsed correctly."""
        with patch("src.llm.ollama_provider.ChatOllama") as MockChatOllama:
            mock_instance = MagicMock()
            mock_with_tools = MagicMock()
            mock_with_tools.ainvoke = AsyncMock(return_value=mock_ollama_tool_response)
            mock_instance.bind_tools = MagicMock(return_value=mock_with_tools)
            MockChatOllama.return_value = mock_instance

            provider = OllamaProvider()
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
    async def test_complete_with_tools_binds_tools(self, mock_ollama_response):
        """Test that tools are bound to the client."""
        with patch("src.llm.ollama_provider.ChatOllama") as MockChatOllama:
            mock_instance = MagicMock()
            mock_with_tools = MagicMock()
            mock_with_tools.ainvoke = AsyncMock(return_value=mock_ollama_response)
            mock_instance.bind_tools = MagicMock(return_value=mock_with_tools)
            MockChatOllama.return_value = mock_instance

            provider = OllamaProvider()
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

            # Verify bind_tools was called with tool schemas
            mock_instance.bind_tools.assert_called_once()
            bound_tools = mock_instance.bind_tools.call_args[0][0]
            assert len(bound_tools) == 1
            assert bound_tools[0]["name"] == "test_tool"


class TestOllamaProviderCompleteStructured:
    """Tests for OllamaProvider.complete_structured method."""

    @pytest.mark.asyncio
    async def test_complete_structured_with_pydantic(self):
        """Test structured output with Pydantic model."""
        from pydantic import BaseModel

        class Person(BaseModel):
            name: str
            age: int

        mock_result = Person(name="Alice", age=30)

        with patch("src.llm.ollama_provider.ChatOllama") as MockChatOllama:
            mock_instance = MagicMock()
            mock_structured = MagicMock()
            mock_structured.ainvoke = AsyncMock(return_value=mock_result)
            mock_instance.with_structured_output = MagicMock(return_value=mock_structured)
            MockChatOllama.return_value = mock_instance

            provider = OllamaProvider()
            messages = [Message.user("Tell me about Alice")]
            response = await provider.complete_structured(messages, Person)

            assert response.parsed_content == {"name": "Alice", "age": 30}
            mock_instance.with_structured_output.assert_called_once_with(Person)

    @pytest.mark.asyncio
    async def test_complete_structured_with_dict_result(self):
        """Test structured output that returns a dict."""
        from pydantic import BaseModel

        class Result(BaseModel):
            value: str

        mock_result = {"value": "test"}

        with patch("src.llm.ollama_provider.ChatOllama") as MockChatOllama:
            mock_instance = MagicMock()
            mock_structured = MagicMock()
            mock_structured.ainvoke = AsyncMock(return_value=mock_result)
            mock_instance.with_structured_output = MagicMock(return_value=mock_structured)
            MockChatOllama.return_value = mock_instance

            provider = OllamaProvider()
            messages = [Message.user("Get value")]
            response = await provider.complete_structured(messages, Result)

            assert response.parsed_content == {"value": "test"}


class TestOllamaProviderMessageConversion:
    """Tests for message format conversion."""

    @pytest.mark.asyncio
    async def test_user_message_conversion(self, mock_ollama_response):
        """Test user message conversion to LangChain format."""
        with patch("src.llm.ollama_provider.ChatOllama") as MockChatOllama:
            mock_instance = MagicMock()
            mock_instance.ainvoke = AsyncMock(return_value=mock_ollama_response)
            MockChatOllama.return_value = mock_instance

            provider = OllamaProvider()
            messages = [Message.user("Hello")]
            # Use think=True to avoid /nothink system message
            await provider.complete(messages, think=True)

            call_args = mock_instance.ainvoke.call_args[0][0]
            assert len(call_args) == 1
            assert call_args[0].content == "Hello"

    @pytest.mark.asyncio
    async def test_user_message_with_nothink(self, mock_ollama_response):
        """Test that /nothink is added as system message when think=False."""
        with patch("src.llm.ollama_provider.ChatOllama") as MockChatOllama:
            mock_instance = MagicMock()
            mock_instance.ainvoke = AsyncMock(return_value=mock_ollama_response)
            MockChatOllama.return_value = mock_instance

            provider = OllamaProvider()
            messages = [Message.user("Hello")]
            # Default think=False should add /nothink
            await provider.complete(messages)

            call_args = mock_instance.ainvoke.call_args[0][0]
            assert len(call_args) == 2  # /nothink system + user
            assert call_args[0].content == "/nothink"
            assert call_args[1].content == "Hello"

    @pytest.mark.asyncio
    async def test_assistant_message_conversion(self, mock_ollama_response):
        """Test assistant message conversion."""
        with patch("src.llm.ollama_provider.ChatOllama") as MockChatOllama:
            mock_instance = MagicMock()
            mock_instance.ainvoke = AsyncMock(return_value=mock_ollama_response)
            MockChatOllama.return_value = mock_instance

            provider = OllamaProvider()
            messages = [
                Message.user("Hello"),
                Message.assistant("Hi there!"),
                Message.user("How are you?"),
            ]
            # Use think=True to avoid /nothink system message
            await provider.complete(messages, think=True)

            call_args = mock_instance.ainvoke.call_args[0][0]
            assert len(call_args) == 3

    @pytest.mark.asyncio
    async def test_system_message_in_messages(self, mock_ollama_response):
        """Test system messages in messages array."""
        with patch("src.llm.ollama_provider.ChatOllama") as MockChatOllama:
            mock_instance = MagicMock()
            mock_instance.ainvoke = AsyncMock(return_value=mock_ollama_response)
            MockChatOllama.return_value = mock_instance

            provider = OllamaProvider()
            messages = [
                Message.system("You are helpful."),
                Message.user("Hello"),
            ]
            # Use think=True to avoid /nothink system message
            await provider.complete(messages, think=True)

            call_args = mock_instance.ainvoke.call_args[0][0]
            assert len(call_args) == 2
            assert call_args[0].content == "You are helpful."


class TestOllamaProviderTokenCounting:
    """Tests for token counting."""

    def test_count_tokens_basic(self):
        """Test basic token counting (heuristic)."""
        provider = OllamaProvider()
        count = provider.count_tokens("Hello, world!")
        assert isinstance(count, int)
        assert count > 0

    def test_count_tokens_empty(self):
        """Test token counting for empty string."""
        provider = OllamaProvider()
        count = provider.count_tokens("")
        assert count == 0

    def test_count_tokens_long_text(self):
        """Test token counting for longer text."""
        provider = OllamaProvider()
        text = "This is a longer piece of text that should result in more tokens. " * 10
        count = provider.count_tokens(text)
        assert count > 50


class TestOllamaProviderErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_connection_error(self):
        """Test handling of connection errors."""
        from src.llm.exceptions import ProviderError

        with patch("src.llm.ollama_provider.ChatOllama") as MockChatOllama:
            mock_instance = MagicMock()
            mock_instance.ainvoke = AsyncMock(side_effect=Exception("Connection refused"))
            MockChatOllama.return_value = mock_instance

            provider = OllamaProvider()
            messages = [Message.user("Hello")]

            with pytest.raises(ProviderError) as exc_info:
                await provider.complete(messages)

            assert "Connection refused" in str(exc_info.value)
