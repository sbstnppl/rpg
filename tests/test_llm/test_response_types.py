"""Tests for LLM response types."""

import pytest
from dataclasses import FrozenInstanceError

from src.llm.response_types import ToolCall, UsageStats, LLMResponse


class TestToolCall:
    """Tests for ToolCall dataclass."""

    def test_create_tool_call(self):
        """Test creating a tool call."""
        call = ToolCall(
            id="call_123",
            name="get_weather",
            arguments={"city": "Paris"},
        )
        assert call.id == "call_123"
        assert call.name == "get_weather"
        assert call.arguments == {"city": "Paris"}
        assert call.raw_arguments == ""

    def test_create_tool_call_with_raw_arguments(self):
        """Test creating tool call with raw JSON."""
        call = ToolCall(
            id="call_456",
            name="search",
            arguments={"query": "dragons"},
            raw_arguments='{"query": "dragons"}',
        )
        assert call.raw_arguments == '{"query": "dragons"}'

    def test_tool_call_is_immutable(self):
        """Test that ToolCall is frozen."""
        call = ToolCall(
            id="call_123",
            name="test",
            arguments={},
        )
        with pytest.raises(FrozenInstanceError):
            call.name = "other"

    def test_tool_call_equality(self):
        """Test that equal tool calls are equal."""
        call1 = ToolCall(id="123", name="test", arguments={"a": 1})
        call2 = ToolCall(id="123", name="test", arguments={"a": 1})
        assert call1 == call2


class TestUsageStats:
    """Tests for UsageStats dataclass."""

    def test_create_usage_stats(self):
        """Test creating usage statistics."""
        usage = UsageStats(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150
        assert usage.cache_read_tokens == 0
        assert usage.cache_creation_tokens == 0

    def test_create_usage_with_caching(self):
        """Test creating usage stats with cache info."""
        usage = UsageStats(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cache_read_tokens=80,
            cache_creation_tokens=20,
        )
        assert usage.cache_read_tokens == 80
        assert usage.cache_creation_tokens == 20

    def test_usage_is_immutable(self):
        """Test that UsageStats is frozen."""
        usage = UsageStats(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        with pytest.raises(FrozenInstanceError):
            usage.prompt_tokens = 200


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_create_text_response(self):
        """Test creating a simple text response."""
        response = LLMResponse(content="Hello, world!")
        assert response.content == "Hello, world!"
        assert response.tool_calls == ()
        assert response.parsed_content is None
        assert response.finish_reason == "stop"
        assert response.model == ""
        assert response.usage is None

    def test_create_response_with_metadata(self):
        """Test creating response with full metadata."""
        usage = UsageStats(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        response = LLMResponse(
            content="The answer is 42.",
            finish_reason="end_turn",
            model="claude-sonnet-4-20250514",
            usage=usage,
        )
        assert response.finish_reason == "end_turn"
        assert response.model == "claude-sonnet-4-20250514"
        assert response.usage.total_tokens == 150

    def test_create_response_with_tool_calls(self):
        """Test creating response with tool calls."""
        tool_calls = (
            ToolCall(id="call_1", name="get_weather", arguments={"city": "Paris"}),
            ToolCall(id="call_2", name="get_time", arguments={}),
        )
        response = LLMResponse(
            content="",
            tool_calls=tool_calls,
            finish_reason="tool_use",
        )
        assert len(response.tool_calls) == 2
        assert response.tool_calls[0].name == "get_weather"
        assert response.tool_calls[1].name == "get_time"

    def test_create_response_with_parsed_content(self):
        """Test creating response with parsed structured content."""
        response = LLMResponse(
            content="",
            parsed_content={"name": "Dragon", "level": 10},
        )
        assert response.parsed_content == {"name": "Dragon", "level": 10}

    def test_response_is_immutable(self):
        """Test that LLMResponse is frozen."""
        response = LLMResponse(content="Hello")
        with pytest.raises(FrozenInstanceError):
            response.content = "World"


class TestLLMResponseProperties:
    """Tests for LLMResponse property methods."""

    def test_has_tool_calls_true(self):
        """Test has_tool_calls when tools were called."""
        response = LLMResponse(
            content="",
            tool_calls=(
                ToolCall(id="call_1", name="test", arguments={}),
            ),
        )
        assert response.has_tool_calls is True

    def test_has_tool_calls_false(self):
        """Test has_tool_calls when no tools were called."""
        response = LLMResponse(content="Just text")
        assert response.has_tool_calls is False

    def test_has_tool_calls_empty_tuple(self):
        """Test has_tool_calls with explicit empty tuple."""
        response = LLMResponse(content="Text", tool_calls=())
        assert response.has_tool_calls is False


class TestLLMResponseHashability:
    """Tests for LLMResponse hashability."""

    def test_response_is_hashable(self):
        """Test that LLMResponse can be hashed."""
        response = LLMResponse(content="Hello")
        assert isinstance(hash(response), int)

    def test_tool_call_is_hashable(self):
        """Test that ToolCall can be hashed."""
        call = ToolCall(id="123", name="test", arguments={"a": 1})
        assert isinstance(hash(call), int)

    def test_usage_stats_is_hashable(self):
        """Test that UsageStats can be hashed."""
        usage = UsageStats(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        assert isinstance(hash(usage), int)
