"""Tests for LLM provider protocol."""

import pytest
from typing import Sequence

from src.llm.base import LLMProvider
from src.llm.message_types import Message
from src.llm.tool_types import ToolDefinition
from src.llm.response_types import LLMResponse


class MockProvider:
    """Mock implementation of LLMProvider for testing."""

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def default_model(self) -> str:
        return "mock-1.0"

    async def complete(
        self,
        messages: Sequence[Message],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        stop_sequences: Sequence[str] | None = None,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        return LLMResponse(content="Mock response")

    async def complete_with_tools(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolDefinition],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tool_choice: str | dict = "auto",
        system_prompt: str | None = None,
    ) -> LLMResponse:
        return LLMResponse(content="Mock response with tools")

    async def complete_structured(
        self,
        messages: Sequence[Message],
        response_schema: type,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        return LLMResponse(content="", parsed_content={"mock": True})

    def count_tokens(
        self,
        text: str,
        model: str | None = None,
    ) -> int:
        return len(text) // 4


class TestLLMProviderProtocol:
    """Tests for LLMProvider protocol."""

    def test_mock_implements_protocol(self):
        """Test that MockProvider satisfies LLMProvider protocol."""
        provider = MockProvider()
        assert isinstance(provider, LLMProvider)

    def test_provider_name_property(self):
        """Test provider_name property."""
        provider = MockProvider()
        assert provider.provider_name == "mock"

    def test_default_model_property(self):
        """Test default_model property."""
        provider = MockProvider()
        assert provider.default_model == "mock-1.0"

    @pytest.mark.asyncio
    async def test_complete_method(self):
        """Test complete method."""
        provider = MockProvider()
        messages = [Message.user("Hello")]
        response = await provider.complete(messages)
        assert response.content == "Mock response"

    @pytest.mark.asyncio
    async def test_complete_with_tools_method(self):
        """Test complete_with_tools method."""
        provider = MockProvider()
        messages = [Message.user("What's the weather?")]
        tools = [
            ToolDefinition(name="get_weather", description="Get weather"),
        ]
        response = await provider.complete_with_tools(messages, tools)
        assert response.content == "Mock response with tools"

    @pytest.mark.asyncio
    async def test_complete_structured_method(self):
        """Test complete_structured method."""
        provider = MockProvider()
        messages = [Message.user("Extract entity")]
        response = await provider.complete_structured(messages, dict)
        assert response.parsed_content == {"mock": True}

    def test_count_tokens_method(self):
        """Test count_tokens method."""
        provider = MockProvider()
        count = provider.count_tokens("Hello, world!")
        assert isinstance(count, int)
        assert count > 0


class TestProtocolTypeChecking:
    """Tests for protocol runtime type checking."""

    def test_incomplete_provider_not_protocol(self):
        """Test that incomplete implementation is not LLMProvider."""

        class IncompleteProvider:
            @property
            def provider_name(self) -> str:
                return "incomplete"

        provider = IncompleteProvider()
        # Should not be recognized as LLMProvider (missing methods)
        assert not isinstance(provider, LLMProvider)

    def test_protocol_is_runtime_checkable(self):
        """Test that LLMProvider is runtime checkable."""
        # LLMProvider should be usable with isinstance()
        provider = MockProvider()
        assert isinstance(provider, LLMProvider)
