"""Anthropic Claude provider implementation."""

import json
from typing import Any, Callable, Sequence

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

        # Track pending tool results to combine into single message
        pending_tool_results: list[dict[str, Any]] = []

        def flush_tool_results() -> None:
            """Add accumulated tool results as a single user message."""
            nonlocal pending_tool_results
            if pending_tool_results:
                api_messages.append({
                    "role": "user",
                    "content": pending_tool_results,
                })
                pending_tool_results = []

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                # Extract system message to system parameter
                if isinstance(msg.content, str):
                    system_prompt = msg.content
                continue

            role = "user" if msg.role == MessageRole.USER else "assistant"

            if msg.role == MessageRole.TOOL:
                # Accumulate tool results to combine into single message
                pending_tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id,
                    "content": msg.content if isinstance(msg.content, str) else "",
                })
                continue  # Don't add yet, wait for next non-TOOL message

            # Flush any pending tool results before adding new message
            flush_tool_results()

            if isinstance(msg.content, str):
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
                    elif block.type == "tool_use":
                        content_blocks.append({
                            "type": "tool_use",
                            "id": block.tool_use_id,
                            "name": block.tool_name,
                            "input": block.tool_input or {},
                        })
                    elif block.type == "tool_result":
                        content_blocks.append({
                            "type": "tool_result",
                            "tool_use_id": block.tool_use_id,
                            "content": block.tool_result or "",
                        })
                api_messages.append({
                    "role": role,
                    "content": content_blocks,
                })

        # Flush any remaining tool results at end
        flush_tool_results()

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
        think: bool = False,  # Ignored for Anthropic (no extended thinking for tool calls)
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
                # Use cache_control to enable prompt caching for system prompt
                # This dramatically reduces latency on subsequent calls
                kwargs["system"] = [
                    {
                        "type": "text",
                        "text": final_system,
                        "cache_control": {"type": "ephemeral"},
                    }
                ]

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

    async def complete_with_tools_streaming(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolDefinition],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tool_choice: str | dict[str, Any] = "auto",
        system_prompt: str | None = None,
        on_token: Callable[[str], None] | None = None,
    ) -> LLMResponse:
        """Generate a completion with streaming token output.

        Same as complete_with_tools but streams tokens via callback.

        Args:
            messages: Conversation history.
            tools: Available tools/functions.
            model: Model to use.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            tool_choice: "auto", "any", "none", or specific tool.
            system_prompt: System-level instructions.
            on_token: Callback for each streamed text token.

        Returns:
            LLMResponse with text and/or tool_calls.
        """
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
                # Use cache_control to enable prompt caching for system prompt
                # This dramatically reduces latency on subsequent calls
                kwargs["system"] = [
                    {
                        "type": "text",
                        "text": final_system,
                        "cache_control": {"type": "ephemeral"},
                    }
                ]

            # Handle tool_choice
            if isinstance(tool_choice, str):
                if tool_choice == "any":
                    kwargs["tool_choice"] = {"type": "any"}
                elif tool_choice == "none":
                    del kwargs["tools"]
            elif isinstance(tool_choice, dict):
                kwargs["tool_choice"] = tool_choice

            # Use streaming API
            async with self._get_client().messages.stream(**kwargs) as stream:
                # Stream text tokens
                async for event in stream:
                    if event.type == "content_block_delta":
                        if hasattr(event.delta, "text") and event.delta.text:
                            if on_token:
                                on_token(event.delta.text)

                # Get final message with full response
                final_message = await stream.get_final_message()
                return self._parse_response(final_message)

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
        """Generate a structured response matching a schema.

        Uses Anthropic's tool_use feature to force structured output.
        For Pydantic models, generates proper JSON schema with nested types.
        """
        extracted_system, api_messages = self._convert_messages(messages)
        final_system = system_prompt or extracted_system

        # Create tool definition with proper JSON schema
        tool_dict = self._schema_to_anthropic_tool(response_schema)
        tool_name = tool_dict["name"]

        try:
            kwargs: dict[str, Any] = {
                "model": model or self._default_model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": api_messages,
                "tools": [tool_dict],
                "tool_choice": {"type": "tool", "name": tool_name},
            }
            if final_system:
                kwargs["system"] = final_system

            response = await self._get_client().messages.create(**kwargs)
            parsed_response = self._parse_response(response)

            # Extract structured content from tool call
            if parsed_response.has_tool_calls:
                parsed_content = parsed_response.tool_calls[0].arguments
                return LLMResponse(
                    content="",
                    parsed_content=parsed_content,
                    finish_reason=parsed_response.finish_reason,
                    model=parsed_response.model,
                    usage=parsed_response.usage,
                    raw_response=parsed_response.raw_response,
                )

            raise StructuredOutputError(
                "Model did not return structured output",
                raw_output=parsed_response.content,
            )
        except StructuredOutputError:
            raise
        except Exception as e:
            await self._handle_api_error(e)
            raise

    def _schema_to_anthropic_tool(self, schema: type) -> dict[str, Any]:
        """Convert a type/schema to Anthropic tool format with proper JSON schema.

        For Pydantic models, uses model_json_schema() to get full nested schema.
        This properly handles list[Model], Optional[Model], Literal types, etc.

        Args:
            schema: The type to convert (Pydantic model, dataclass, or dict).

        Returns:
            Dict in Anthropic's tool format with proper input_schema.
        """
        schema_name = getattr(schema, "__name__", "Data")

        # Handle Pydantic models - use built-in JSON schema generation
        if hasattr(schema, "model_json_schema"):
            json_schema = schema.model_json_schema()
            # Remove $defs key and inline definitions for cleaner schema
            # Anthropic handles $defs but inlining can be clearer
            return {
                "name": "extract_data",
                "description": f"Extract {schema_name} from the input. Return valid JSON matching the schema.",
                "input_schema": json_schema,
            }

        # Handle dict type (simple case)
        if schema is dict:
            return {
                "name": "extract_data",
                "description": "Extract structured data from the input",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": True,
                },
            }

        # Handle dataclasses
        if hasattr(schema, "__dataclass_fields__"):
            from dataclasses import fields
            properties: dict[str, Any] = {}
            required: list[str] = []

            for field in fields(schema):
                field_schema = self._python_type_to_json_schema(field.type)
                field_schema["description"] = f"The {field.name} field"
                properties[field.name] = field_schema
                # Dataclass fields are required unless they have defaults
                if field.default is field.default_factory:
                    required.append(field.name)

            return {
                "name": "extract_data",
                "description": f"Extract {schema_name} data",
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            }

        # Fallback for unknown types
        return {
            "name": "extract_data",
            "description": f"Extract {schema_name} data",
            "input_schema": {"type": "object", "properties": {}},
        }

    def _python_type_to_json_schema(self, python_type: Any) -> dict[str, Any]:
        """Convert a Python type annotation to JSON Schema.

        Args:
            python_type: Python type annotation.

        Returns:
            JSON Schema dict for the type.
        """
        import typing
        from typing import get_origin, get_args

        # Handle None
        if python_type is type(None):
            return {"type": "null"}

        # Handle basic types
        if python_type is str or python_type == "str":
            return {"type": "string"}
        if python_type is int or python_type == "int":
            return {"type": "integer"}
        if python_type is float or python_type == "float":
            return {"type": "number"}
        if python_type is bool or python_type == "bool":
            return {"type": "boolean"}

        # Handle generic types (List, Optional, etc.)
        origin = get_origin(python_type)
        args = get_args(python_type)

        # Handle Optional (Union with None)
        if origin is typing.Union:
            # Filter out None type
            non_none_args = [a for a in args if a is not type(None)]
            if len(non_none_args) == 1:
                # This is Optional[X]
                inner_schema = self._python_type_to_json_schema(non_none_args[0])
                return inner_schema  # JSON Schema handles null implicitly
            # Multiple types - use anyOf
            return {"anyOf": [self._python_type_to_json_schema(a) for a in args]}

        # Handle List/list
        if origin is list:
            if args:
                return {
                    "type": "array",
                    "items": self._python_type_to_json_schema(args[0]),
                }
            return {"type": "array"}

        # Handle Dict/dict
        if origin is dict:
            return {"type": "object"}

        # Handle Literal (enum-like)
        if origin is typing.Literal:
            return {"type": "string", "enum": list(args)}

        # Default to string for unknown types
        return {"type": "string"}

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
