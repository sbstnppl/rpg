"""Tests for LLM audit logging."""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from src.llm.audit_logger import (
    LLMAuditContext,
    LLMAuditEntry,
    LLMAuditLogger,
    get_audit_logger,
    set_audit_context,
    get_audit_context,
)
from src.llm.response_types import LLMResponse, UsageStats, ToolCall
from src.llm.message_types import Message


class TestLLMAuditContext:
    """Tests for LLMAuditContext dataclass."""

    def test_default_values(self):
        """Test default context values."""
        ctx = LLMAuditContext()
        assert ctx.session_id is None
        assert ctx.turn_number is None
        assert ctx.call_type == "unknown"

    def test_with_values(self):
        """Test context with explicit values."""
        ctx = LLMAuditContext(
            session_id=42,
            turn_number=5,
            call_type="game_master",
        )
        assert ctx.session_id == 42
        assert ctx.turn_number == 5
        assert ctx.call_type == "game_master"


class TestLLMAuditEntry:
    """Tests for LLMAuditEntry dataclass."""

    def test_basic_entry(self):
        """Test creating a basic audit entry."""
        entry = LLMAuditEntry(
            timestamp=datetime(2024, 12, 8, 14, 30, 22),
            context=LLMAuditContext(session_id=42, turn_number=5, call_type="game_master"),
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            method="complete",
            system_prompt="You are a GM",
            messages=[{"role": "user", "content": "Hello"}],
            tools=None,
            parameters={"max_tokens": 2048, "temperature": 0.8},
            response=LLMResponse(
                content="Hello!",
                usage=UsageStats(10, 5, 15),
            ),
            error=None,
            duration_seconds=1.5,
        )

        assert entry.provider == "anthropic"
        assert entry.context.session_id == 42
        assert entry.response.content == "Hello!"

    def test_entry_with_tool_calls(self):
        """Test entry with tool calls in response."""
        entry = LLMAuditEntry(
            timestamp=datetime.now(),
            context=LLMAuditContext(),
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            method="complete_with_tools",
            system_prompt=None,
            messages=[],
            tools=[{"name": "roll_dice", "description": "Roll dice"}],
            parameters={},
            response=LLMResponse(
                content="",
                tool_calls=(
                    ToolCall(id="call_123", name="roll_dice", arguments={"dice": "1d20"}),
                ),
            ),
            error=None,
            duration_seconds=0.5,
        )

        assert entry.response.has_tool_calls
        assert entry.response.tool_calls[0].name == "roll_dice"

    def test_entry_with_error(self):
        """Test entry with error."""
        entry = LLMAuditEntry(
            timestamp=datetime.now(),
            context=LLMAuditContext(),
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            method="complete",
            system_prompt=None,
            messages=[],
            tools=None,
            parameters={},
            response=None,
            error="Rate limit exceeded",
            duration_seconds=0.1,
        )

        assert entry.error == "Rate limit exceeded"
        assert entry.response is None


class TestLLMAuditLogger:
    """Tests for LLMAuditLogger."""

    @pytest.fixture
    def logger(self, tmp_path):
        """Create a logger with temp directory."""
        return LLMAuditLogger(log_dir=tmp_path, enabled=True)

    @pytest.fixture
    def sample_entry(self):
        """Create a sample audit entry."""
        return LLMAuditEntry(
            timestamp=datetime(2024, 12, 8, 14, 30, 22),
            context=LLMAuditContext(session_id=42, turn_number=5, call_type="game_master"),
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            method="complete",
            system_prompt="You are a GM for a fantasy RPG.",
            messages=[{"role": "user", "content": "I look around the tavern."}],
            tools=None,
            parameters={"max_tokens": 2048, "temperature": 0.8},
            response=LLMResponse(
                content="The tavern is dimly lit...",
                usage=UsageStats(150, 50, 200),
            ),
            error=None,
            duration_seconds=1.5,
        )

    @pytest.mark.asyncio
    async def test_log_creates_session_directory(self, logger, sample_entry, tmp_path):
        """Test that logging creates session directory."""
        await logger.log(sample_entry)

        session_dir = tmp_path / "session_42"
        assert session_dir.exists()
        assert session_dir.is_dir()

    @pytest.mark.asyncio
    async def test_log_creates_file_with_correct_name(self, logger, sample_entry, tmp_path):
        """Test that logging creates file with expected name pattern."""
        await logger.log(sample_entry)

        session_dir = tmp_path / "session_42"
        files = list(session_dir.glob("*.md"))
        assert len(files) == 1

        filename = files[0].name
        assert filename.startswith("turn_005_")
        assert "game_master" in filename
        assert filename.endswith(".md")

    @pytest.mark.asyncio
    async def test_log_file_contains_metadata(self, logger, sample_entry, tmp_path):
        """Test that log file contains metadata section."""
        await logger.log(sample_entry)

        session_dir = tmp_path / "session_42"
        log_file = list(session_dir.glob("*.md"))[0]
        content = log_file.read_text()

        assert "# LLM Call: game_master" in content
        assert "Session ID" in content
        assert "42" in content
        assert "Turn Number" in content
        assert "5" in content
        assert "anthropic" in content
        assert "claude-sonnet-4-20250514" in content

    @pytest.mark.asyncio
    async def test_log_file_contains_system_prompt(self, logger, sample_entry, tmp_path):
        """Test that log file contains system prompt."""
        await logger.log(sample_entry)

        session_dir = tmp_path / "session_42"
        log_file = list(session_dir.glob("*.md"))[0]
        content = log_file.read_text()

        assert "## System Prompt" in content
        assert "You are a GM for a fantasy RPG." in content

    @pytest.mark.asyncio
    async def test_log_file_contains_messages(self, logger, sample_entry, tmp_path):
        """Test that log file contains messages."""
        await logger.log(sample_entry)

        session_dir = tmp_path / "session_42"
        log_file = list(session_dir.glob("*.md"))[0]
        content = log_file.read_text()

        assert "## Messages" in content
        assert "I look around the tavern." in content

    @pytest.mark.asyncio
    async def test_log_file_contains_response(self, logger, sample_entry, tmp_path):
        """Test that log file contains response."""
        await logger.log(sample_entry)

        session_dir = tmp_path / "session_42"
        log_file = list(session_dir.glob("*.md"))[0]
        content = log_file.read_text()

        assert "## Response" in content
        assert "The tavern is dimly lit..." in content

    @pytest.mark.asyncio
    async def test_log_file_contains_usage_stats(self, logger, sample_entry, tmp_path):
        """Test that log file contains usage statistics."""
        await logger.log(sample_entry)

        session_dir = tmp_path / "session_42"
        log_file = list(session_dir.glob("*.md"))[0]
        content = log_file.read_text()

        assert "## Usage" in content
        assert "150" in content  # prompt tokens
        assert "50" in content  # completion tokens

    @pytest.mark.asyncio
    async def test_disabled_logger_does_not_write(self, tmp_path):
        """Test that disabled logger creates no files."""
        logger = LLMAuditLogger(log_dir=tmp_path, enabled=False)
        entry = LLMAuditEntry(
            timestamp=datetime.now(),
            context=LLMAuditContext(session_id=1),
            provider="anthropic",
            model="test",
            method="complete",
            system_prompt=None,
            messages=[],
            tools=None,
            parameters={},
            response=LLMResponse(content="test"),
            error=None,
            duration_seconds=0.1,
        )

        await logger.log(entry)

        # No files should be created
        assert not any(tmp_path.iterdir())

    @pytest.mark.asyncio
    async def test_orphan_logs_without_session(self, logger, tmp_path):
        """Test that calls without session_id go to orphan directory."""
        entry = LLMAuditEntry(
            timestamp=datetime(2024, 12, 8, 14, 30, 22),
            context=LLMAuditContext(session_id=None, call_type="character_inference"),
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            method="complete",
            system_prompt=None,
            messages=[],
            tools=None,
            parameters={},
            response=LLMResponse(content="test"),
            error=None,
            duration_seconds=0.1,
        )

        await logger.log(entry)

        orphan_dir = tmp_path / "orphan"
        assert orphan_dir.exists()
        files = list(orphan_dir.glob("*.md"))
        assert len(files) == 1
        assert "character_inference" in files[0].name

    @pytest.mark.asyncio
    async def test_log_with_tool_calls(self, logger, tmp_path):
        """Test logging entry with tool calls."""
        entry = LLMAuditEntry(
            timestamp=datetime(2024, 12, 8, 14, 30, 22),
            context=LLMAuditContext(session_id=1, turn_number=1, call_type="game_master"),
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            method="complete_with_tools",
            system_prompt=None,
            messages=[{"role": "user", "content": "Roll for initiative"}],
            tools=[{"name": "roll_dice", "description": "Roll dice"}],
            parameters={},
            response=LLMResponse(
                content="Rolling initiative...",
                tool_calls=(
                    ToolCall(
                        id="call_abc123",
                        name="roll_dice",
                        arguments={"dice": "1d20", "modifier": 2},
                    ),
                ),
            ),
            error=None,
            duration_seconds=0.5,
        )

        await logger.log(entry)

        session_dir = tmp_path / "session_1"
        log_file = list(session_dir.glob("*.md"))[0]
        content = log_file.read_text()

        assert "## Tools Available" in content
        assert "roll_dice" in content
        assert "## Tool Calls" in content
        assert "call_abc123" in content
        assert "1d20" in content

    @pytest.mark.asyncio
    async def test_log_with_error(self, logger, tmp_path):
        """Test logging entry with error."""
        entry = LLMAuditEntry(
            timestamp=datetime(2024, 12, 8, 14, 30, 22),
            context=LLMAuditContext(session_id=1, turn_number=1, call_type="game_master"),
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            method="complete",
            system_prompt=None,
            messages=[],
            tools=None,
            parameters={},
            response=None,
            error="API rate limit exceeded",
            duration_seconds=0.1,
        )

        await logger.log(entry)

        session_dir = tmp_path / "session_1"
        log_file = list(session_dir.glob("*.md"))[0]
        content = log_file.read_text()

        assert "## Error" in content
        assert "API rate limit exceeded" in content


class TestAuditContextManagement:
    """Tests for context variable management."""

    def test_set_and_get_audit_context(self):
        """Test setting and getting audit context."""
        set_audit_context(session_id=42, turn_number=5, call_type="game_master")
        ctx = get_audit_context()

        assert ctx.session_id == 42
        assert ctx.turn_number == 5
        assert ctx.call_type == "game_master"

    def test_default_audit_context(self):
        """Test default audit context values."""
        # Reset to default
        set_audit_context()
        ctx = get_audit_context()

        assert ctx.session_id is None
        assert ctx.turn_number is None
        assert ctx.call_type == "unknown"


class TestGetAuditLogger:
    """Tests for get_audit_logger factory."""

    def test_get_audit_logger_returns_instance(self):
        """Test that get_audit_logger returns a logger instance."""
        import src.llm.audit_logger as audit_module

        # Reset the cached logger
        audit_module._audit_logger = None

        with patch("src.config.settings") as mock_settings:
            mock_settings.log_llm_calls = True
            mock_settings.llm_log_dir = "logs/llm"

            logger = get_audit_logger()
            assert isinstance(logger, LLMAuditLogger)
            assert logger.enabled is True

        # Clean up
        audit_module._audit_logger = None

    def test_get_audit_logger_respects_disabled_setting(self):
        """Test that logger respects disabled setting."""
        import src.llm.audit_logger as audit_module

        # Reset the cached logger
        audit_module._audit_logger = None

        with patch("src.config.settings") as mock_settings:
            mock_settings.log_llm_calls = False
            mock_settings.llm_log_dir = "logs/llm"

            logger = get_audit_logger()
            assert logger.enabled is False

        # Clean up
        audit_module._audit_logger = None
