"""Anthropic Claude provider implementation."""

import json
from typing import Any, Sequence

from anthropic import AsyncAnthropic
from anthropic import (
    AuthenticationError as AnthropicAuthError,
    RateLimitError as AnthropicRateLimitError,
    BadRequestError as AnthropicBadRequestError,
    APIError as AnthropicAPIError,
)

from src.llm.base import LLMProvider
from src.llm.message_types import Message, MessageRole, MessageContent
from src.llm.response_types import LLMResponse, ToolCall, UsageStats
from src.llm.tool_types import ToolDefinition
from src.llm.exceptions import (
    AuthenticationError,
    RateLimitError,
    ContentPolicyError,
    ContextLengthError,
    ProviderError,
    StructuredOutputError,
)


class AnthropicProvider:
    """Anthropic Claude implementation.

    Supports:
    - Claude 3.5 Sonnet, Claude 3 Haiku, Claude 3 Opus
    - Tool use / function calling
    - Prompt caching (for long system prompts)
    - Vision (image inputs)
    """

    CHARS_PER_TOKEN = 4  # Rough estimate for token counting

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str = "claude-sonnet-4-20250514",
        client: AsyncAnthropic | None = None,
    ) -> None:
        """Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key. If not provided, will use
                     ANTHROPIC_API_KEY environment variable.
            default_model: Default model to use for completions.
            client: Optional pre-configured client (for testing).
        """
        self._api_key = api_key
        self._default_model = default_model
        self._client_instance: AsyncAnthropic | None = client

    @property
    def provider_name(self) -> str:
        """Return provider identifier."""
        return "anthropic"

    @property
    def default_model(self) -> str:
        """Return default model for this provider."""
        return self._default_model

    def _get_client(self) -> AsyncAnthropic:
        """Get or create the async client."""
        if self._client_instance is None:
            self._client_instance = AsyncAnthropic(api_key=self._api_key)
        return self._client_instance

    def _convert_messages(
        self, messages: Sequence[Message]
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Convert our Message types to Anthropic format.

        Returns:
            Tuple of (system_prompt, messages_list)
        """
        system_prompt: str | None = None
        api_messages: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                # Extract system message to system parameter
                if isinstance(msg.content, str):
                    system_prompt = msg.content
                continue

            role = "user" if msg.role == MessageRole.USER else "assistant"

            if msg.role == MessageRole.TOOL:
                # Tool results need special handling
                api_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.tool_call_id,
                            "content": msg.content if isinstance(msg.content, str) else "",
                        }
                    ],
                })
            elif isinstance(msg.content, str):
                api_messages.append({
                    "role": role,
                    "content": msg.content,
                })
            else:
                # Handle content blocks (images, etc.)
                content_blocks = []
                for block in msg.content:
                    if block.type == "text":
                        content_blocks.append({
                            "type": "text",
                            "text": block.text,
                        })
                    elif block.type == "image":
                        if block.image_base64:
                            content_blocks.append({
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": block.media_type or "image/png",
                                    "data": block.image_base64,
                                },
                            })
                        elif block.image_url:
                            content_blocks.append({
                                "type": "image",
                                "source": {
                                    "type": "url",
                                    "url": block.image_url,
                                },
                            })
                api_messages.append({
                    "role": role,
                    "content": content_blocks,
                })

        return system_prompt, api_messages

    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse Anthropic API response into LLMResponse."""
        content = ""
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                content = block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input,
                        raw_arguments=json.dumps(block.input),
                    )
                )

        usage = None
        if response.usage:
            usage = UsageStats(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
                cache_read_tokens=getattr(response.usage, "cache_read_input_tokens", 0) or 0,
                cache_creation_tokens=getattr(response.usage, "cache_creation_input_tokens", 0) or 0,
            )

        return LLMResponse(
            content=content,
            tool_calls=tuple(tool_calls),
            finish_reason=response.stop_reason,
            model=response.model,
            usage=usage,
            raw_response=response,
        )

    async def _handle_api_error(self, error: Exception) -> None:
        """Convert Anthropic exceptions to our exception types."""
        if isinstance(error, AnthropicAuthError):
            raise AuthenticationError(str(error))
        elif isinstance(error, AnthropicRateLimitError):
            raise RateLimitError(str(error))
        elif isinstance(error, AnthropicBadRequestError):
            error_str = str(error).lower()
            if "context" in error_str or "token" in error_str:
                raise ContextLengthError(str(error))
            elif "content" in error_str or "policy" in error_str:
                raise ContentPolicyError(str(error))
            raise ProviderError(str(error), is_retryable=False)
        elif isinstance(error, AnthropicAPIError):
            # 5xx errors are retryable
            status_code = getattr(error, "status_code", None)
            is_retryable = status_code is not None and status_code >= 500
            raise ProviderError(str(error), is_retryable=is_retryable, status_code=status_code)
        raise error

    async def complete(
        self,
        messages: Sequence[Message],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        stop_sequences: Sequence[str] | None = None,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Generate a completion from messages."""
        extracted_system, api_messages = self._convert_messages(messages)
        final_system = system_prompt or extracted_system

        try:
            kwargs: dict[str, Any] = {
                "model": model or self._default_model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": api_messages,
            }
            if final_system:
                kwargs["system"] = final_system
            if stop_sequences:
                kwargs["stop_sequences"] = list(stop_sequences)

            response = await self._get_client().messages.create(**kwargs)
            return self._parse_response(response)
        except Exception as e:
            await self._handle_api_error(e)
            raise  # Should not reach here

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
        """Generate a completion that may include tool calls."""
        extracted_system, api_messages = self._convert_messages(messages)
        final_system = system_prompt or extracted_system

        # Convert tools to Anthropic format
        api_tools = [tool.to_anthropic_format() for tool in tools]

        try:
            kwargs: dict[str, Any] = {
                "model": model or self._default_model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": api_messages,
                "tools": api_tools,
            }
            if final_system:
                kwargs["system"] = final_system

            # Handle tool_choice
            if isinstance(tool_choice, str):
                if tool_choice == "any":
                    kwargs["tool_choice"] = {"type": "any"}
                elif tool_choice == "none":
                    # Don't include tools if none
                    del kwargs["tools"]
                # "auto" is default
            elif isinstance(tool_choice, dict):
                kwargs["tool_choice"] = tool_choice

            response = await self._get_client().messages.create(**kwargs)
            return self._parse_response(response)
        except Exception as e:
            await self._handle_api_error(e)
            raise

    async def complete_structured(
        self,
        messages: Sequence[Message],
        response_schema: type,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Generate a structured response matching a schema."""
        # Use tool_use to force structured output
        # Create a tool from the schema
        tool = self._schema_to_tool(response_schema)

        response = await self.complete_with_tools(
            messages=messages,
            tools=[tool],
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            tool_choice={"type": "tool", "name": tool.name},
            system_prompt=system_prompt,
        )

        # Extract structured content from tool call
        if response.has_tool_calls:
            parsed_content = response.tool_calls[0].arguments
            return LLMResponse(
                content="",
                parsed_content=parsed_content,
                finish_reason=response.finish_reason,
                model=response.model,
                usage=response.usage,
                raw_response=response.raw_response,
            )

        raise StructuredOutputError(
            "Model did not return structured output",
            raw_output=response.content,
        )

    def _schema_to_tool(self, schema: type) -> ToolDefinition:
        """Convert a type/schema to a ToolDefinition for structured output."""
        # Handle dict type (simple case)
        if schema is dict:
            return ToolDefinition(
                name="extract_data",
                description="Extract structured data from the input",
            )

        # Handle dataclasses and Pydantic models
        params: list[ToolParameter] = []
        from src.llm.tool_types import ToolParameter

        if hasattr(schema, "__dataclass_fields__"):
            # Dataclass
            from dataclasses import fields
            for field in fields(schema):
                field_type = "string"
                if field.type in (int, "int"):
                    field_type = "integer"
                elif field.type in (bool, "bool"):
                    field_type = "boolean"
                params.append(
                    ToolParameter(
                        name=field.name,
                        type=field_type,
                        description=f"The {field.name} field",
                    )
                )
        elif hasattr(schema, "model_fields"):
            # Pydantic model
            for name, field_info in schema.model_fields.items():
                field_type = "string"
                annotation = field_info.annotation
                if annotation in (int, "int"):
                    field_type = "integer"
                elif annotation in (bool, "bool"):
                    field_type = "boolean"
                params.append(
                    ToolParameter(
                        name=name,
                        type=field_type,
                        description=field_info.description or f"The {name} field",
                        required=field_info.is_required(),
                    )
                )

        return ToolDefinition(
            name="extract_data",
            description=f"Extract {schema.__name__} data",
            parameters=tuple(params),
        )

    def count_tokens(
        self,
        text: str,
        model: str | None = None,
    ) -> int:
        """Count tokens in text (rough estimate).

        Anthropic doesn't provide a public tokenizer, so we use a heuristic.
        """
        if not text:
            return 0
        return len(text) // self.CHARS_PER_TOKEN
