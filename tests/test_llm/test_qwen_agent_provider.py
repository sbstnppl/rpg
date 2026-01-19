"""Tests for Qwen-Agent provider."""

import pytest
from unittest.mock import MagicMock, patch

from src.llm.qwen_agent_provider import QwenAgentProvider
from src.llm.message_types import Message, MessageRole
from src.llm.tool_types import ToolDefinition, ToolParameter
from src.llm.base import LLMProvider


# =============================================================================
# Initialization Tests
# =============================================================================


class TestQwenAgentProviderInit:
    """Tests for QwenAgentProvider initialization."""

    def test_create_with_defaults(self):
        """Test creating provider with default settings."""
        provider = QwenAgentProvider()
        assert provider.provider_name == "qwen-agent"
        assert provider.default_model == "qwen3"
        assert provider._base_url == "http://localhost:11434/v1"
        assert provider._api_key == "EMPTY"

    def test_custom_base_url(self):
        """Test creating provider with custom base URL."""
        provider = QwenAgentProvider(base_url="http://192.168.1.100:11434/v1")
        assert provider._base_url == "http://192.168.1.100:11434/v1"

    def test_custom_default_model(self):
        """Test creating provider with custom default model."""
        provider = QwenAgentProvider(default_model="qwen3-32b")
        assert provider.default_model == "qwen3-32b"

    def test_custom_api_key(self):
        """Test creating provider with custom API key."""
        provider = QwenAgentProvider(api_key="my-api-key")
        assert provider._api_key == "my-api-key"

    def test_lazy_llm_loading(self):
        """Test that LLM is not loaded until accessed."""
        provider = QwenAgentProvider()
        assert provider._llm is None

    def test_implements_protocol(self):
        """Test that QwenAgentProvider implements LLMProvider protocol."""
        provider = QwenAgentProvider()
        assert isinstance(provider, LLMProvider)


class TestQwenAgentProviderLazyLoading:
    """Tests for lazy LLM loading."""

    def test_llm_property_initializes_on_access(self):
        """Test that accessing llm property initializes the client."""
        with patch("src.llm.qwen_agent_provider.get_chat_model") as mock_get_chat_model:
            mock_llm = MagicMock()
            mock_get_chat_model.return_value = mock_llm

            provider = QwenAgentProvider()
            assert provider._llm is None

            # Access llm property
            llm = provider.llm

            # Should have called get_chat_model
            mock_get_chat_model.assert_called_once_with({
                "model": "qwen3",
                "model_server": "http://localhost:11434/v1",
                "api_key": "EMPTY",
            })
            assert llm is mock_llm
            assert provider._llm is mock_llm

    def test_llm_property_caches_instance(self):
        """Test that LLM instance is cached after first access."""
        with patch("src.llm.qwen_agent_provider.get_chat_model") as mock_get_chat_model:
            mock_llm = MagicMock()
            mock_get_chat_model.return_value = mock_llm

            provider = QwenAgentProvider()

            # Access twice
            llm1 = provider.llm
            llm2 = provider.llm

            # Should only create once
            mock_get_chat_model.assert_called_once()
            assert llm1 is llm2


# =============================================================================
# Thinking Block Stripping Tests
# =============================================================================


class TestThinkingBlockStripping:
    """Tests for _strip_thinking static method."""

    def test_strip_complete_thinking_block(self):
        """Test stripping complete <think>...</think> blocks."""
        content = "<think>Let me think about this...</think>Here is my answer."
        result = QwenAgentProvider._strip_thinking(content)
        assert result == "Here is my answer."

    def test_strip_multiple_thinking_blocks(self):
        """Test stripping multiple thinking blocks."""
        content = "<think>First thought</think>Part 1<think>Second thought</think>Part 2"
        result = QwenAgentProvider._strip_thinking(content)
        assert result == "Part 1Part 2"

    def test_strip_thinking_with_newlines(self):
        """Test stripping thinking blocks containing newlines."""
        content = """<think>
Let me think...
This is complex.
</think>Here is the answer."""
        result = QwenAgentProvider._strip_thinking(content)
        assert result == "Here is the answer."

    def test_strip_incomplete_thinking_block(self):
        """Test stripping incomplete/cut-off thinking blocks."""
        content = "Some text<think>Incomplete thought that got cut"
        result = QwenAgentProvider._strip_thinking(content)
        assert result == "Some text"

    def test_no_thinking_blocks(self):
        """Test content without thinking blocks is unchanged."""
        content = "Just regular content."
        result = QwenAgentProvider._strip_thinking(content)
        assert result == "Just regular content."

    def test_empty_content(self):
        """Test empty content returns empty string."""
        result = QwenAgentProvider._strip_thinking("")
        assert result == ""


# =============================================================================
# Tool Call Extraction Tests
# =============================================================================


class TestToolCallExtraction:
    """Tests for _extract_and_strip_tool_calls static method."""

    def test_extract_single_tool_call(self):
        """Test extracting a single tool call JSON from content."""
        content = 'I need to make a skill check. {"name": "skill_check", "arguments": {"skill": "stealth", "target": 15}}'
        cleaned, tool_calls = QwenAgentProvider._extract_and_strip_tool_calls(content)

        assert cleaned == "I need to make a skill check."
        assert len(tool_calls) == 1
        assert tool_calls[0].name == "skill_check"
        assert tool_calls[0].arguments == {"skill": "stealth", "target": 15}
        assert tool_calls[0].id == "skill_check"

    def test_extract_multiple_tool_calls(self):
        """Test extracting multiple tool call JSONs from content."""
        content = '{"name": "attack_roll", "arguments": {"weapon": "sword"}} Attack! {"name": "damage_entity", "arguments": {"amount": 5}}'
        cleaned, tool_calls = QwenAgentProvider._extract_and_strip_tool_calls(content)

        assert cleaned == "Attack!"
        assert len(tool_calls) == 2
        assert tool_calls[0].name == "attack_roll"
        assert tool_calls[1].name == "damage_entity"

    def test_no_tool_calls_in_content(self):
        """Test content without tool calls returns empty list."""
        content = "Just regular text without any tool calls."
        cleaned, tool_calls = QwenAgentProvider._extract_and_strip_tool_calls(content)

        assert cleaned == "Just regular text without any tool calls."
        assert len(tool_calls) == 0

    def test_invalid_json_ignored(self):
        """Test that invalid JSON is ignored."""
        content = 'Some text {"name": "broken, "arguments": oops}'
        _, tool_calls = QwenAgentProvider._extract_and_strip_tool_calls(content)

        # Invalid JSON should remain in content or be stripped without creating tool call
        assert len(tool_calls) == 0

    def test_raw_arguments_stored(self):
        """Test that raw_arguments contains JSON string."""
        content = '{"name": "test_tool", "arguments": {"key": "value"}}'
        _, tool_calls = QwenAgentProvider._extract_and_strip_tool_calls(content)

        assert len(tool_calls) == 1
        assert tool_calls[0].raw_arguments == '{"key": "value"}'


# =============================================================================
# Message Conversion Tests
# =============================================================================


class TestMessageConversion:
    """Tests for _convert_messages method."""

    def test_convert_user_message(self):
        """Test converting user message to qwen-agent format."""
        provider = QwenAgentProvider()
        messages = [Message.user("Hello")]
        result = provider._convert_messages(messages)

        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello"

    def test_convert_assistant_message(self):
        """Test converting assistant message to qwen-agent format."""
        provider = QwenAgentProvider()
        messages = [Message.assistant("Hi there!")]
        result = provider._convert_messages(messages)

        assert len(result) == 1
        assert result[0]["role"] == "assistant"
        assert result[0]["content"] == "Hi there!"

    def test_convert_system_message(self):
        """Test converting system message to qwen-agent format."""
        provider = QwenAgentProvider()
        messages = [Message.system("You are helpful.")]
        result = provider._convert_messages(messages)

        assert len(result) == 1
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "You are helpful."

    def test_convert_with_system_prompt(self):
        """Test that system_prompt is prepended."""
        provider = QwenAgentProvider()
        messages = [Message.user("Hello")]
        result = provider._convert_messages(messages, system_prompt="Be helpful.")

        assert len(result) == 2
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "Be helpful."
        assert result[1]["role"] == "user"

    def test_convert_tool_result_message(self):
        """Test converting tool result message to qwen-agent format."""
        provider = QwenAgentProvider()
        messages = [
            Message(
                role=MessageRole.TOOL,
                content='{"result": 15}',
                tool_call_id="skill_check",
                name="skill_check",
            )
        ]
        result = provider._convert_messages(messages)

        assert len(result) == 1
        assert result[0]["role"] == "function"
        assert result[0]["name"] == "skill_check"
        assert result[0]["content"] == '{"result": 15}'

    def test_convert_tool_result_uses_tool_call_id_as_fallback(self):
        """Test that tool_call_id is used as name fallback."""
        provider = QwenAgentProvider()
        messages = [
            Message(
                role=MessageRole.TOOL,
                content="result",
                tool_call_id="call_123",
                name=None,
            )
        ]
        result = provider._convert_messages(messages)

        assert result[0]["name"] == "call_123"

    def test_convert_mixed_conversation(self):
        """Test converting a full conversation."""
        provider = QwenAgentProvider()
        messages = [
            Message.user("What's the weather?"),
            Message.assistant("Let me check that for you."),
            Message.user("Thanks!"),
        ]
        result = provider._convert_messages(messages)

        assert len(result) == 3
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"
        assert result[2]["role"] == "user"


# =============================================================================
# Function Extraction Tests
# =============================================================================


class TestFunctionExtraction:
    """Tests for _extract_functions method."""

    def test_extract_single_function(self):
        """Test converting single ToolDefinition to function format."""
        provider = QwenAgentProvider()
        tools = [
            ToolDefinition(
                name="skill_check",
                description="Roll a skill check",
                parameters=(
                    ToolParameter(name="skill", type="string", description="Skill name"),
                    ToolParameter(name="target", type="integer", description="Target DC"),
                ),
            )
        ]
        result = provider._extract_functions(tools)

        assert len(result) == 1
        assert result[0]["name"] == "skill_check"
        assert result[0]["description"] == "Roll a skill check"
        assert "properties" in result[0]["parameters"]
        assert "skill" in result[0]["parameters"]["properties"]

    def test_extract_multiple_functions(self):
        """Test converting multiple ToolDefinitions."""
        provider = QwenAgentProvider()
        tools = [
            ToolDefinition(name="tool1", description="First tool", parameters=()),
            ToolDefinition(name="tool2", description="Second tool", parameters=()),
        ]
        result = provider._extract_functions(tools)

        assert len(result) == 2
        assert result[0]["name"] == "tool1"
        assert result[1]["name"] == "tool2"


# =============================================================================
# Response Parsing Tests
# =============================================================================


class TestResponseParsing:
    """Tests for _parse_response method."""

    def test_parse_text_response(self):
        """Test parsing simple text response."""
        provider = QwenAgentProvider()
        response_messages = [
            {"role": "assistant", "content": "Hello, how can I help?"}
        ]
        result = provider._parse_response(response_messages, "qwen3")

        assert result.content == "Hello, how can I help?"
        assert len(result.tool_calls) == 0
        assert result.model == "qwen3"

    def test_parse_response_with_thinking(self):
        """Test that thinking blocks are stripped from response."""
        provider = QwenAgentProvider()
        response_messages = [
            {"role": "assistant", "content": "<think>Internal reasoning</think>The answer is 42."}
        ]
        result = provider._parse_response(response_messages, "qwen3")

        assert result.content == "The answer is 42."

    def test_parse_response_with_function_call(self):
        """Test parsing response with structured function_call."""
        provider = QwenAgentProvider()
        response_messages = [
            {
                "role": "assistant",
                "content": "Let me check that.",
                "function_call": {
                    "name": "skill_check",
                    "arguments": '{"skill": "perception", "target": 12}',
                }
            }
        ]
        result = provider._parse_response(response_messages, "qwen3")

        assert result.content == "Let me check that."
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "skill_check"
        assert result.tool_calls[0].arguments == {"skill": "perception", "target": 12}

    def test_parse_response_with_dict_arguments(self):
        """Test parsing function_call with dict arguments (already parsed)."""
        provider = QwenAgentProvider()
        response_messages = [
            {
                "role": "assistant",
                "content": "",
                "function_call": {
                    "name": "attack_roll",
                    "arguments": {"weapon": "sword", "modifier": 3},
                }
            }
        ]
        result = provider._parse_response(response_messages, "qwen3")

        assert result.tool_calls[0].arguments == {"weapon": "sword", "modifier": 3}
        assert result.tool_calls[0].raw_arguments == '{"weapon": "sword", "modifier": 3}'

    def test_parse_response_with_json_in_content(self):
        """Test parsing response with tool call JSON in content."""
        provider = QwenAgentProvider()
        response_messages = [
            {
                "role": "assistant",
                "content": 'I will roll. {"name": "skill_check", "arguments": {"skill": "stealth"}}'
            }
        ]
        result = provider._parse_response(response_messages, "qwen3")

        assert result.content == "I will roll."
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "skill_check"

    def test_parse_empty_response(self):
        """Test parsing empty response."""
        provider = QwenAgentProvider()
        response_messages = []
        result = provider._parse_response(response_messages, "qwen3")

        assert result.content == ""
        assert len(result.tool_calls) == 0

    def test_parse_response_no_usage_stats(self):
        """Test that usage stats are None (qwen-agent limitation)."""
        provider = QwenAgentProvider()
        response_messages = [
            {"role": "assistant", "content": "Response"}
        ]
        result = provider._parse_response(response_messages, "qwen3")

        assert result.usage is None


# =============================================================================
# Complete Method Tests (with mocking)
# =============================================================================


class TestQwenAgentProviderComplete:
    """Tests for QwenAgentProvider.complete method."""

    @pytest.mark.asyncio
    async def test_complete_basic(self):
        """Test basic completion."""
        with patch("src.llm.qwen_agent_provider.get_chat_model") as mock_get_chat_model:
            mock_llm = MagicMock()
            mock_llm.chat.return_value = [
                {"role": "assistant", "content": "Hello from Qwen!"}
            ]
            mock_get_chat_model.return_value = mock_llm

            provider = QwenAgentProvider()
            messages = [Message.user("Hello")]
            response = await provider.complete(messages)

            assert response.content == "Hello from Qwen!"
            assert response.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_complete_with_system_prompt(self):
        """Test completion with system prompt."""
        with patch("src.llm.qwen_agent_provider.get_chat_model") as mock_get_chat_model:
            mock_llm = MagicMock()
            mock_llm.chat.return_value = [
                {"role": "assistant", "content": "I am helpful."}
            ]
            mock_get_chat_model.return_value = mock_llm

            provider = QwenAgentProvider()
            messages = [Message.user("Hello")]
            await provider.complete(messages, system_prompt="You are helpful.")

            # Verify chat was called with system message
            call_kwargs = mock_llm.chat.call_args.kwargs
            qwen_messages = call_kwargs["messages"]
            assert qwen_messages[0]["role"] == "system"
            assert qwen_messages[0]["content"] == "You are helpful."

    @pytest.mark.asyncio
    async def test_complete_uses_default_model(self):
        """Test that default model is used when not specified."""
        with patch("src.llm.qwen_agent_provider.get_chat_model") as mock_get_chat_model:
            mock_llm = MagicMock()
            mock_llm.chat.return_value = [
                {"role": "assistant", "content": "Response"}
            ]
            mock_get_chat_model.return_value = mock_llm

            provider = QwenAgentProvider(default_model="qwen3-32b")
            messages = [Message.user("Hello")]
            response = await provider.complete(messages)

            assert response.model == "qwen3-32b"

    @pytest.mark.asyncio
    async def test_complete_uses_specified_model(self):
        """Test that specified model overrides default."""
        with patch("src.llm.qwen_agent_provider.get_chat_model") as mock_get_chat_model:
            mock_llm = MagicMock()
            mock_llm.chat.return_value = [
                {"role": "assistant", "content": "Response"}
            ]
            mock_get_chat_model.return_value = mock_llm

            provider = QwenAgentProvider(default_model="qwen3")
            messages = [Message.user("Hello")]
            response = await provider.complete(messages, model="qwen3-72b")

            assert response.model == "qwen3-72b"

    @pytest.mark.asyncio
    async def test_complete_handles_string_response(self):
        """Test handling when chat returns raw string."""
        with patch("src.llm.qwen_agent_provider.get_chat_model") as mock_get_chat_model:
            mock_llm = MagicMock()
            # Some models return raw strings
            mock_llm.chat.return_value = ["Raw string response"]
            mock_get_chat_model.return_value = mock_llm

            provider = QwenAgentProvider()
            messages = [Message.user("Hello")]
            response = await provider.complete(messages)

            assert response.content == "Raw string response"


class TestQwenAgentProviderCompleteWithTools:
    """Tests for QwenAgentProvider.complete_with_tools method."""

    @pytest.mark.asyncio
    async def test_complete_with_tools_returns_tool_call(self):
        """Test that tool calls are parsed correctly."""
        with patch("src.llm.qwen_agent_provider.get_chat_model") as mock_get_chat_model:
            mock_llm = MagicMock()
            mock_llm.chat.return_value = [
                {
                    "role": "assistant",
                    "content": "Rolling skill check.",
                    "function_call": {
                        "name": "skill_check",
                        "arguments": '{"skill": "stealth", "target": 15}',
                    }
                }
            ]
            mock_get_chat_model.return_value = mock_llm

            provider = QwenAgentProvider()
            messages = [Message.user("Sneak past the guard")]
            tools = [
                ToolDefinition(
                    name="skill_check",
                    description="Roll a skill check",
                    parameters=(
                        ToolParameter(name="skill", type="string", description="Skill name"),
                        ToolParameter(name="target", type="integer", description="Target DC"),
                    ),
                ),
            ]
            response = await provider.complete_with_tools(messages, tools)

            assert response.has_tool_calls
            assert len(response.tool_calls) == 1
            assert response.tool_calls[0].name == "skill_check"
            assert response.tool_calls[0].arguments == {"skill": "stealth", "target": 15}

    @pytest.mark.asyncio
    async def test_complete_with_tools_passes_functions(self):
        """Test that tools are converted and passed to chat."""
        with patch("src.llm.qwen_agent_provider.get_chat_model") as mock_get_chat_model:
            mock_llm = MagicMock()
            mock_llm.chat.return_value = [
                {"role": "assistant", "content": "Done."}
            ]
            mock_get_chat_model.return_value = mock_llm

            provider = QwenAgentProvider()
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

            # Verify functions were passed to chat
            call_kwargs = mock_llm.chat.call_args.kwargs
            assert "functions" in call_kwargs
            assert len(call_kwargs["functions"]) == 1
            assert call_kwargs["functions"][0]["name"] == "test_tool"

    @pytest.mark.asyncio
    async def test_complete_with_tools_handles_json_in_content(self):
        """Test handling tool calls embedded in content text."""
        with patch("src.llm.qwen_agent_provider.get_chat_model") as mock_get_chat_model:
            mock_llm = MagicMock()
            mock_llm.chat.return_value = [
                {
                    "role": "assistant",
                    "content": 'Let me attack. {"name": "attack_roll", "arguments": {"weapon": "sword"}}'
                }
            ]
            mock_get_chat_model.return_value = mock_llm

            provider = QwenAgentProvider()
            messages = [Message.user("Attack!")]
            tools = [
                ToolDefinition(name="attack_roll", description="Roll attack", parameters=()),
            ]
            response = await provider.complete_with_tools(messages, tools)

            assert response.has_tool_calls
            assert response.tool_calls[0].name == "attack_roll"
            assert response.content == "Let me attack."


# =============================================================================
# Complete Structured Tests
# =============================================================================


class TestQwenAgentProviderCompleteStructured:
    """Tests for QwenAgentProvider.complete_structured method."""

    @pytest.mark.asyncio
    async def test_complete_structured_with_pydantic(self):
        """Test structured output with Pydantic model."""
        from pydantic import BaseModel

        class Person(BaseModel):
            name: str
            age: int

        with patch("src.llm.qwen_agent_provider.get_chat_model") as mock_get_chat_model:
            mock_llm = MagicMock()
            mock_llm.chat.return_value = [
                {
                    "role": "assistant",
                    "content": "",
                    "function_call": {
                        "name": "respond",
                        "arguments": '{"name": "Alice", "age": 30}',
                    }
                }
            ]
            mock_get_chat_model.return_value = mock_llm

            provider = QwenAgentProvider()
            messages = [Message.user("Tell me about Alice")]
            response = await provider.complete_structured(messages, Person)

            assert response.parsed_content == {"name": "Alice", "age": 30}

    @pytest.mark.asyncio
    async def test_complete_structured_with_json_content(self):
        """Test structured output when model returns JSON in content."""
        from pydantic import BaseModel

        class Result(BaseModel):
            value: str

        with patch("src.llm.qwen_agent_provider.get_chat_model") as mock_get_chat_model:
            mock_llm = MagicMock()
            mock_llm.chat.return_value = [
                {
                    "role": "assistant",
                    "content": '{"value": "test"}'
                }
            ]
            mock_get_chat_model.return_value = mock_llm

            provider = QwenAgentProvider()
            messages = [Message.user("Get value")]
            response = await provider.complete_structured(messages, Result)

            assert response.parsed_content == {"value": "test"}


# =============================================================================
# Token Counting Tests
# =============================================================================


class TestQwenAgentProviderTokenCounting:
    """Tests for token counting."""

    def test_count_tokens_basic(self):
        """Test basic token counting (heuristic)."""
        provider = QwenAgentProvider()
        count = provider.count_tokens("Hello, world!")
        # 13 chars / 4 = 3 tokens
        assert count == 3

    def test_count_tokens_empty(self):
        """Test token counting for empty string."""
        provider = QwenAgentProvider()
        count = provider.count_tokens("")
        assert count == 0

    def test_count_tokens_long_text(self):
        """Test token counting for longer text."""
        provider = QwenAgentProvider()
        text = "This is a longer piece of text that should result in more tokens. " * 10
        count = provider.count_tokens(text)
        # ~670 chars / 4 = ~167 tokens
        assert count > 100


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestQwenAgentProviderErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_connection_error(self):
        """Test handling of connection errors."""
        from src.llm.exceptions import ProviderError

        with patch("src.llm.qwen_agent_provider.get_chat_model") as mock_get_chat_model:
            mock_llm = MagicMock()
            mock_llm.chat.side_effect = Exception("Connection refused")
            mock_get_chat_model.return_value = mock_llm

            provider = QwenAgentProvider()
            messages = [Message.user("Hello")]

            with pytest.raises(ProviderError) as exc_info:
                await provider.complete(messages)

            assert "Connection refused" in str(exc_info.value)
            assert exc_info.value.is_retryable is True

    @pytest.mark.asyncio
    async def test_structured_output_error(self):
        """Test handling of structured output failures."""
        from pydantic import BaseModel
        from src.llm.exceptions import StructuredOutputError

        class Schema(BaseModel):
            field: str

        with patch("src.llm.qwen_agent_provider.get_chat_model") as mock_get_chat_model:
            mock_llm = MagicMock()
            mock_llm.chat.return_value = [
                {"role": "assistant", "content": "Not valid JSON at all"}
            ]
            mock_get_chat_model.return_value = mock_llm

            provider = QwenAgentProvider()
            messages = [Message.user("Get data")]

            with pytest.raises(StructuredOutputError):
                await provider.complete_structured(messages, Schema)
