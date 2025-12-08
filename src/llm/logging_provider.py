"""Logging wrapper for LLM providers.

Wraps any LLM provider to add audit logging of all calls.
"""

import time
from datetime import datetime
from typing import Any, Sequence

from src.llm.base import LLMProvider
from src.llm.message_types import Message
from src.llm.response_types import LLMResponse
from src.llm.tool_types import ToolDefinition
from src.llm.audit_logger import (
    LLMAuditEntry,
    LLMAuditLogger,
    get_audit_context,
)


class LoggingProvider:
    """Wrapper that adds audit logging to any LLM provider.

    Delegates all calls to the wrapped provider while logging
    the full request and response for debugging.

    Args:
        provider: The LLM provider to wrap.
        logger: The audit logger to use (optional, uses global if not provided).
    """

    def __init__(
        self,
        provider: LLMProvider,
        logger: LLMAuditLogger | None = None,
    ) -> None:
        """Initialize the logging provider.

        Args:
            provider: The LLM provider to wrap.
            logger: The audit logger to use.
        """
        self._provider = provider
        self._logger = logger

    @property
    def provider_name(self) -> str:
        """Return provider identifier."""
        return self._provider.provider_name

    @property
    def default_model(self) -> str:
        """Return default model for this provider."""
        return self._provider.default_model

    def _get_logger(self) -> LLMAuditLogger:
        """Get the audit logger.

        Returns:
            LLMAuditLogger instance.
        """
        if self._logger is not None:
            return self._logger
        from src.llm.audit_logger import get_audit_logger
        return get_audit_logger()

    def _messages_to_dicts(self, messages: Sequence[Message]) -> list[dict[str, Any]]:
        """Convert Message objects to dicts for logging.

        Args:
            messages: Sequence of Message objects.

        Returns:
            List of message dicts.
        """
        result = []
        for msg in messages:
            result.append({
                "role": msg.role.value,
                "content": msg.content if isinstance(msg.content, str) else str(msg.content),
            })
        return result

    def _tools_to_dicts(
        self, tools: Sequence[ToolDefinition] | None
    ) -> list[dict[str, Any]] | None:
        """Convert ToolDefinition objects to dicts for logging.

        Args:
            tools: Sequence of ToolDefinition objects.

        Returns:
            List of tool dicts or None.
        """
        if tools is None:
            return None
        return [
            {"name": tool.name, "description": tool.description}
            for tool in tools
        ]

    async def complete(
        self,
        messages: Sequence[Message],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        stop_sequences: Sequence[str] | None = None,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Generate a completion from messages with logging.

        Args:
            messages: Conversation history.
            model: Model to use.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            stop_sequences: Sequences that stop generation.
            system_prompt: System-level instructions.

        Returns:
            LLMResponse with text and metadata.
        """
        start_time = time.perf_counter()
        timestamp = datetime.now()
        context = get_audit_context()

        response = None
        error = None

        try:
            response = await self._provider.complete(
                messages=messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                stop_sequences=stop_sequences,
                system_prompt=system_prompt,
            )
            return response
        except Exception as e:
            error = str(e)
            raise
        finally:
            duration = time.perf_counter() - start_time
            entry = LLMAuditEntry(
                timestamp=timestamp,
                context=context,
                provider=self._provider.provider_name,
                model=model or self._provider.default_model,
                method="complete",
                system_prompt=system_prompt,
                messages=self._messages_to_dicts(messages),
                tools=None,
                parameters={
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stop_sequences": list(stop_sequences) if stop_sequences else None,
                },
                response=response,
                error=error,
                duration_seconds=duration,
            )
            await self._get_logger().log(entry)

    async def complete_with_tools(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolDefinition],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tool_choice: str | dict[str, Any] = "auto",
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Generate a completion that may include tool calls with logging.

        Args:
            messages: Conversation history.
            tools: Available tools/functions.
            model: Model to use.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            tool_choice: Tool selection mode.
            system_prompt: System-level instructions.

        Returns:
            LLMResponse with text and/or tool_calls.
        """
        start_time = time.perf_counter()
        timestamp = datetime.now()
        context = get_audit_context()

        response = None
        error = None

        try:
            response = await self._provider.complete_with_tools(
                messages=messages,
                tools=tools,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                tool_choice=tool_choice,
                system_prompt=system_prompt,
            )
            return response
        except Exception as e:
            error = str(e)
            raise
        finally:
            duration = time.perf_counter() - start_time
            entry = LLMAuditEntry(
                timestamp=timestamp,
                context=context,
                provider=self._provider.provider_name,
                model=model or self._provider.default_model,
                method="complete_with_tools",
                system_prompt=system_prompt,
                messages=self._messages_to_dicts(messages),
                tools=self._tools_to_dicts(tools),
                parameters={
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "tool_choice": tool_choice,
                },
                response=response,
                error=error,
                duration_seconds=duration,
            )
            await self._get_logger().log(entry)

    async def complete_structured(
        self,
        messages: Sequence[Message],
        response_schema: type,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Generate a structured response matching a schema with logging.

        Args:
            messages: Conversation history.
            response_schema: Pydantic model or dataclass for output.
            model: Model to use.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            system_prompt: System-level instructions.

        Returns:
            LLMResponse with parsed_content containing the structured data.
        """
        start_time = time.perf_counter()
        timestamp = datetime.now()
        context = get_audit_context()

        response = None
        error = None

        try:
            response = await self._provider.complete_structured(
                messages=messages,
                response_schema=response_schema,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system_prompt=system_prompt,
            )
            return response
        except Exception as e:
            error = str(e)
            raise
        finally:
            duration = time.perf_counter() - start_time
            entry = LLMAuditEntry(
                timestamp=timestamp,
                context=context,
                provider=self._provider.provider_name,
                model=model or self._provider.default_model,
                method="complete_structured",
                system_prompt=system_prompt,
                messages=self._messages_to_dicts(messages),
                tools=None,
                parameters={
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "response_schema": response_schema.__name__ if hasattr(response_schema, "__name__") else str(response_schema),
                },
                response=response,
                error=error,
                duration_seconds=duration,
            )
            await self._get_logger().log(entry)

    def count_tokens(
        self,
        text: str,
        model: str | None = None,
    ) -> int:
        """Count tokens in text for context window management.

        Args:
            text: Text to count tokens for.
            model: Model to use for tokenization.

        Returns:
            Token count.
        """
        return self._provider.count_tokens(text, model)
