"""LLM audit logging for prompt/response debugging.

Provides filesystem-based logging of all LLM calls for debugging
and prompt improvement. Logs are written as markdown files organized
by session and turn number.
"""

import asyncio
import contextvars
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from src.llm.response_types import LLMResponse


@dataclass
class LLMAuditContext:
    """Context for an LLM audit log entry.

    Attributes:
        session_id: Game session ID (None for orphan calls).
        turn_number: Turn number within session (None if not in a turn).
        call_type: Type of call (e.g., "game_master", "entity_extractor").
    """

    session_id: int | None = None
    turn_number: int | None = None
    call_type: str = "unknown"


@dataclass
class LLMAuditEntry:
    """Complete audit entry for an LLM call.

    Attributes:
        timestamp: When the call was made.
        context: Session/turn context.
        provider: LLM provider name (e.g., "anthropic").
        model: Model used for the call.
        method: API method (complete, complete_with_tools, complete_structured).
        system_prompt: System prompt if provided.
        messages: List of message dicts.
        tools: Tool definitions if provided.
        parameters: Call parameters (max_tokens, temperature, etc.).
        response: LLM response if successful.
        error: Error message if failed.
        duration_seconds: Time taken for the call.
        tool_rounds: List of tool call/result rounds for multi-turn tool use.
    """

    timestamp: datetime
    context: LLMAuditContext
    provider: str
    model: str
    method: str
    system_prompt: str | None
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None
    parameters: dict[str, Any]
    response: LLMResponse | None
    error: str | None
    duration_seconds: float
    tool_rounds: list[dict[str, Any]] = field(default_factory=list)


class LLMAuditLogger:
    """Async audit logger for LLM calls.

    Writes audit logs as markdown files to the filesystem, organized
    by session ID and turn number.

    Args:
        log_dir: Directory to write log files to.
        enabled: Whether logging is enabled.
    """

    def __init__(
        self,
        log_dir: Path | str = "logs/llm",
        enabled: bool = True,
    ) -> None:
        """Initialize the audit logger.

        Args:
            log_dir: Directory to write log files to.
            enabled: Whether logging is enabled.
        """
        self.log_dir = Path(log_dir)
        self.enabled = enabled

    async def log(self, entry: LLMAuditEntry) -> None:
        """Log an audit entry asynchronously.

        Args:
            entry: The audit entry to log.
        """
        if not self.enabled:
            return

        file_path = self._get_file_path(entry)
        content = self._format_entry(entry)

        await self._write_async(file_path, content)

    def _get_file_path(self, entry: LLMAuditEntry) -> Path:
        """Generate file path for audit entry.

        Args:
            entry: The audit entry.

        Returns:
            Path to the log file.
        """
        timestamp_str = entry.timestamp.strftime("%Y%m%d_%H%M%S")

        if entry.context.session_id is not None:
            session_dir = self.log_dir / f"session_{entry.context.session_id}"
            if entry.context.turn_number is not None:
                turn_str = f"turn_{entry.context.turn_number:03d}"
            else:
                turn_str = "turn_000"
            filename = f"{turn_str}_{timestamp_str}_{entry.context.call_type}.md"
        else:
            session_dir = self.log_dir / "orphan"
            filename = f"{timestamp_str}_{entry.context.call_type}.md"

        return session_dir / filename

    def _format_entry(self, entry: LLMAuditEntry) -> str:
        """Format entry as markdown.

        Args:
            entry: The audit entry to format.

        Returns:
            Markdown-formatted string.
        """
        lines = [f"# LLM Call: {entry.context.call_type}", ""]

        # Metadata section
        lines.append("## Metadata")
        lines.append(f"- **Timestamp**: {entry.timestamp.isoformat()}")
        if entry.context.session_id is not None:
            lines.append(f"- **Session ID**: {entry.context.session_id}")
        if entry.context.turn_number is not None:
            lines.append(f"- **Turn Number**: {entry.context.turn_number}")
        lines.append(f"- **Provider**: {entry.provider}")
        lines.append(f"- **Model**: {entry.model}")
        lines.append(f"- **Method**: {entry.method}")
        lines.append("")

        # Parameters section
        if entry.parameters:
            lines.append("## Parameters")
            for key, value in entry.parameters.items():
                lines.append(f"- **{key}**: {value}")
            lines.append("")

        # System prompt section
        if entry.system_prompt:
            lines.append("## System Prompt")
            lines.append("```")
            lines.append(entry.system_prompt)
            lines.append("```")
            lines.append("")

        # Messages section
        if entry.messages:
            lines.append("## Messages")
            for msg in entry.messages:
                role = msg.get("role", "unknown").upper()
                content = msg.get("content", "")
                lines.append(f"### [{role}]")
                lines.append("```")
                if isinstance(content, str):
                    lines.append(content)
                else:
                    lines.append(json.dumps(content, indent=2))
                lines.append("```")
                lines.append("")

        # Tools section
        if entry.tools:
            lines.append("## Tools Available")
            for tool in entry.tools:
                name = tool.get("name", "unknown")
                desc = tool.get("description", "")
                lines.append(f"- **{name}**: {desc}")
            lines.append("")

        # Error section
        if entry.error:
            lines.append("## Error")
            lines.append("```")
            lines.append(entry.error)
            lines.append("```")
            lines.append("")

        # Response section
        if entry.response:
            lines.append("## Response")
            if entry.response.content:
                lines.append("### Content")
                lines.append("```")
                lines.append(entry.response.content)
                lines.append("```")
                lines.append("")

            # Tool calls
            if entry.response.has_tool_calls:
                lines.append("## Tool Calls")
                for i, tool_call in enumerate(entry.response.tool_calls, 1):
                    lines.append(f"### {i}. {tool_call.name} (`{tool_call.id}`)")
                    lines.append("```json")
                    lines.append(json.dumps(tool_call.arguments, indent=2))
                    lines.append("```")
                    lines.append("")

        # Usage stats
        if entry.response and entry.response.usage:
            usage = entry.response.usage
            lines.append("## Usage")
            lines.append(f"- **Prompt Tokens**: {usage.prompt_tokens}")
            lines.append(f"- **Completion Tokens**: {usage.completion_tokens}")
            lines.append(f"- **Total Tokens**: {usage.total_tokens}")
            if usage.cache_read_tokens:
                lines.append(f"- **Cache Read Tokens**: {usage.cache_read_tokens}")
            if usage.cache_creation_tokens:
                lines.append(f"- **Cache Creation Tokens**: {usage.cache_creation_tokens}")
            lines.append("")

        # Duration
        lines.append("## Duration")
        lines.append(f"- **Total Time**: {entry.duration_seconds:.2f}s")
        lines.append("")

        return "\n".join(lines)

    async def _write_async(self, path: Path, content: str) -> None:
        """Write content to file asynchronously.

        Args:
            path: Path to write to.
            content: Content to write.
        """

        def write_file() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

        await asyncio.to_thread(write_file)


# Context variable for tracking current session/turn
_audit_context: contextvars.ContextVar[LLMAuditContext] = contextvars.ContextVar(
    "audit_context",
    default=LLMAuditContext(),
)


def set_audit_context(
    session_id: int | None = None,
    turn_number: int | None = None,
    call_type: str = "unknown",
) -> None:
    """Set audit context for subsequent LLM calls.

    Args:
        session_id: Game session ID.
        turn_number: Turn number within session.
        call_type: Type of call (e.g., "game_master").
    """
    _audit_context.set(
        LLMAuditContext(
            session_id=session_id,
            turn_number=turn_number,
            call_type=call_type,
        )
    )


def get_audit_context() -> LLMAuditContext:
    """Get current audit context.

    Returns:
        Current LLMAuditContext.
    """
    return _audit_context.get()


# Global logger instance
_audit_logger: LLMAuditLogger | None = None


def get_audit_logger() -> LLMAuditLogger:
    """Get or create global audit logger.

    Returns:
        LLMAuditLogger instance.
    """
    global _audit_logger
    if _audit_logger is None:
        from src.config import settings

        _audit_logger = LLMAuditLogger(
            log_dir=settings.llm_log_dir,
            enabled=settings.log_llm_calls,
        )
    return _audit_logger
