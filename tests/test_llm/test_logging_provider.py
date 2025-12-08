"""Tests for LLM logging provider wrapper."""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.llm.logging_provider import LoggingProvider
from src.llm.audit_logger import (
    LLMAuditContext,
    LLMAuditLogger,
    set_audit_context,
    get_audit_context,
)
from src.llm.message_types import Message
from src.llm.response_types import LLMResponse, UsageStats, ToolCall
from src.llm.tool_types import ToolDefinition, ToolParameter


class TestLoggingProvider:
    """Tests for LoggingProvider wrapper."""

    @pytest.fixture
    def mock_provider(self):
        """Create a mock LLM provider."""
        provider = MagicMock()
        provider.provider_name = "mock"
        provider.default_model = "mock-model"
        provider.complete = AsyncMock(
            return_value=LLMResponse(
                content="Test response",
                usage=UsageStats(10, 5, 15),
            )
        )
        provider.complete_with_tools = AsyncMock(
            return_value=LLMResponse(
                content="Tool response",
                tool_calls=(
                    ToolCall(id="call_123", name="test_tool", arguments={"arg": "value"}),
                ),
                usage=UsageStats(20, 10, 30),
            )
        )
        provider.complete_structured = AsyncMock(
            return_value=LLMResponse(
                content="",
                parsed_content={"key": "value"},
                usage=UsageStats(15, 8, 23),
            )
        )
        provider.count_tokens = MagicMock(return_value=10)
        return provider

    @pytest.fixture
    def mock_logger(self, tmp_path):
        """Create a mock audit logger."""
        logger = LLMAuditLogger(log_dir=tmp_path, enabled=True)
        return logger

    def test_provider_name_delegated(self, mock_provider, mock_logger):
        """Test that provider_name is delegated to wrapped provider."""
        logging_provider = LoggingProvider(mock_provider, mock_logger)
        assert logging_provider.provider_name == "mock"

    def test_default_model_delegated(self, mock_provider, mock_logger):
        """Test that default_model is delegated to wrapped provider."""
        logging_provider = LoggingProvider(mock_provider, mock_logger)
        assert logging_provider.default_model == "mock-model"

    @pytest.mark.asyncio
    async def test_complete_delegates_to_provider(self, mock_provider, mock_logger):
        """Test that complete() delegates to wrapped provider."""
        logging_provider = LoggingProvider(mock_provider, mock_logger)
        messages = [Message.user("Hello")]

        response = await logging_provider.complete(
            messages=messages,
            max_tokens=1000,
            temperature=0.7,
        )

        assert response.content == "Test response"
        mock_provider.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_logs_call(self, mock_provider, tmp_path):
        """Test that complete() logs the call."""
        logger = LLMAuditLogger(log_dir=tmp_path, enabled=True)
        logging_provider = LoggingProvider(mock_provider, logger)

        set_audit_context(session_id=42, turn_number=5, call_type="test")
        messages = [Message.user("Hello")]

        await logging_provider.complete(messages=messages)

        # Check that log file was created
        session_dir = tmp_path / "session_42"
        assert session_dir.exists()
        log_files = list(session_dir.glob("*.md"))
        assert len(log_files) == 1

        content = log_files[0].read_text()
        assert "test" in content
        assert "Hello" in content
        assert "Test response" in content

    @pytest.mark.asyncio
    async def test_complete_with_tools_delegates(self, mock_provider, mock_logger):
        """Test that complete_with_tools() delegates to wrapped provider."""
        logging_provider = LoggingProvider(mock_provider, mock_logger)
        messages = [Message.user("Use a tool")]
        tools = [
            ToolDefinition(
                name="test_tool",
                description="A test tool",
                parameters=[],
            )
        ]

        response = await logging_provider.complete_with_tools(
            messages=messages,
            tools=tools,
        )

        assert response.has_tool_calls
        assert response.tool_calls[0].name == "test_tool"
        mock_provider.complete_with_tools.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_with_tools_logs_call(self, mock_provider, tmp_path):
        """Test that complete_with_tools() logs the call including tools."""
        logger = LLMAuditLogger(log_dir=tmp_path, enabled=True)
        logging_provider = LoggingProvider(mock_provider, logger)

        set_audit_context(session_id=1, turn_number=1, call_type="gm")
        messages = [Message.user("Roll dice")]
        tools = [
            ToolDefinition(
                name="roll_dice",
                description="Roll dice",
                parameters=[],
            )
        ]

        await logging_provider.complete_with_tools(messages=messages, tools=tools)

        session_dir = tmp_path / "session_1"
        log_files = list(session_dir.glob("*.md"))
        content = log_files[0].read_text()

        assert "roll_dice" in content
        assert "Tool Calls" in content
        assert "test_tool" in content  # From mock response

    @pytest.mark.asyncio
    async def test_complete_structured_delegates(self, mock_provider, mock_logger):
        """Test that complete_structured() delegates to wrapped provider."""
        logging_provider = LoggingProvider(mock_provider, mock_logger)
        messages = [Message.user("Extract data")]

        response = await logging_provider.complete_structured(
            messages=messages,
            response_schema=dict,
        )

        assert response.parsed_content == {"key": "value"}
        mock_provider.complete_structured.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_structured_logs_call(self, mock_provider, tmp_path):
        """Test that complete_structured() logs the call."""
        logger = LLMAuditLogger(log_dir=tmp_path, enabled=True)
        logging_provider = LoggingProvider(mock_provider, logger)

        set_audit_context(session_id=2, turn_number=3, call_type="extractor")
        messages = [Message.user("Extract")]

        await logging_provider.complete_structured(
            messages=messages,
            response_schema=dict,
        )

        session_dir = tmp_path / "session_2"
        log_files = list(session_dir.glob("*.md"))
        content = log_files[0].read_text()

        assert "extractor" in content
        assert "complete_structured" in content

    @pytest.mark.asyncio
    async def test_logs_error_on_exception(self, mock_provider, tmp_path):
        """Test that errors are logged when provider raises exception."""
        mock_provider.complete = AsyncMock(side_effect=Exception("API Error"))
        logger = LLMAuditLogger(log_dir=tmp_path, enabled=True)
        logging_provider = LoggingProvider(mock_provider, logger)

        set_audit_context(session_id=1, turn_number=1, call_type="test")

        with pytest.raises(Exception, match="API Error"):
            await logging_provider.complete(messages=[Message.user("Hello")])

        # Error should still be logged
        session_dir = tmp_path / "session_1"
        log_files = list(session_dir.glob("*.md"))
        assert len(log_files) == 1

        content = log_files[0].read_text()
        assert "Error" in content
        assert "API Error" in content

    @pytest.mark.asyncio
    async def test_logs_duration(self, mock_provider, tmp_path):
        """Test that call duration is logged."""
        logger = LLMAuditLogger(log_dir=tmp_path, enabled=True)
        logging_provider = LoggingProvider(mock_provider, logger)

        set_audit_context(session_id=1, turn_number=1, call_type="test")
        await logging_provider.complete(messages=[Message.user("Hello")])

        session_dir = tmp_path / "session_1"
        log_files = list(session_dir.glob("*.md"))
        content = log_files[0].read_text()

        assert "Duration" in content
        assert "Total Time" in content

    def test_count_tokens_delegated(self, mock_provider, mock_logger):
        """Test that count_tokens is delegated to wrapped provider."""
        logging_provider = LoggingProvider(mock_provider, mock_logger)
        result = logging_provider.count_tokens("test text")

        assert result == 10
        mock_provider.count_tokens.assert_called_once_with("test text", None)

    @pytest.mark.asyncio
    async def test_logs_system_prompt(self, mock_provider, tmp_path):
        """Test that system prompt is logged."""
        logger = LLMAuditLogger(log_dir=tmp_path, enabled=True)
        logging_provider = LoggingProvider(mock_provider, logger)

        set_audit_context(session_id=1, turn_number=1, call_type="test")
        await logging_provider.complete(
            messages=[Message.user("Hello")],
            system_prompt="You are a helpful assistant.",
        )

        session_dir = tmp_path / "session_1"
        log_files = list(session_dir.glob("*.md"))
        content = log_files[0].read_text()

        assert "System Prompt" in content
        assert "You are a helpful assistant." in content

    @pytest.mark.asyncio
    async def test_disabled_logger_still_returns_response(self, mock_provider, tmp_path):
        """Test that disabled logger still returns provider response."""
        logger = LLMAuditLogger(log_dir=tmp_path, enabled=False)
        logging_provider = LoggingProvider(mock_provider, logger)

        response = await logging_provider.complete(messages=[Message.user("Hello")])

        assert response.content == "Test response"
        # No files should be created
        assert not any(tmp_path.iterdir())


class TestAuditContextInLoggingProvider:
    """Tests for audit context usage in logging provider."""

    @pytest.fixture
    def mock_provider(self):
        """Create a mock LLM provider."""
        provider = MagicMock()
        provider.provider_name = "mock"
        provider.default_model = "mock-model"
        provider.complete = AsyncMock(
            return_value=LLMResponse(content="Response", usage=UsageStats(10, 5, 15))
        )
        return provider

    @pytest.mark.asyncio
    async def test_uses_current_audit_context(self, mock_provider, tmp_path):
        """Test that logging uses current audit context."""
        logger = LLMAuditLogger(log_dir=tmp_path, enabled=True)
        logging_provider = LoggingProvider(mock_provider, logger)

        # Set specific context
        set_audit_context(session_id=99, turn_number=42, call_type="special")

        await logging_provider.complete(messages=[Message.user("Test")])

        # Verify correct directory was used
        session_dir = tmp_path / "session_99"
        assert session_dir.exists()

        log_files = list(session_dir.glob("*.md"))
        assert len(log_files) == 1
        assert "turn_042" in log_files[0].name
        assert "special" in log_files[0].name

    @pytest.mark.asyncio
    async def test_orphan_when_no_session_id(self, mock_provider, tmp_path):
        """Test that calls without session_id go to orphan directory."""
        logger = LLMAuditLogger(log_dir=tmp_path, enabled=True)
        logging_provider = LoggingProvider(mock_provider, logger)

        # Set context without session_id
        set_audit_context(session_id=None, call_type="orphan_call")

        await logging_provider.complete(messages=[Message.user("Test")])

        # Should go to orphan directory
        orphan_dir = tmp_path / "orphan"
        assert orphan_dir.exists()
        log_files = list(orphan_dir.glob("*.md"))
        assert len(log_files) == 1
