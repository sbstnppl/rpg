"""OpenAI provider implementation.

Supports OpenAI API and OpenAI-compatible APIs (DeepSeek, Ollama, vLLM).
"""

import json
from typing import Any, Sequence

from openai import AsyncOpenAI
from openai import (
    AuthenticationError as OpenAIAuthError,
    RateLimitError as OpenAIRateLimitError,
    BadRequestError as OpenAIBadRequestError,
    APIError as OpenAIAPIError,
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


class OpenAIProvider:
    """OpenAI GPT implementation.

    Supports:
    - GPT-4o, GPT-4 Turbo, GPT-3.5 Turbo
    - Function calling
    - JSON mode / structured outputs
    - Vision (image inputs)
    - OpenAI-compatible APIs via custom base_url (DeepSeek, Ollama, vLLM)
    """

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str = "gpt-4o",
        base_url: str | None = None,
        client: AsyncOpenAI | None = None,
    ) -> None:
        """Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key. If not provided, will use
                     OPENAI_API_KEY environment variable.
            default_model: Default model to use for completions.
            base_url: Custom base URL for OpenAI-compatible APIs.
            client: Optional pre-configured client (for testing).
        """
        self._api_key = api_key
        self._default_model = default_model
        self._base_url = base_url
        self._client_instance: AsyncOpenAI | None = client

    @property
    def provider_name(self) -> str:
        """Return provider identifier."""
        return "openai"

    @property
    def default_model(self) -> str:
        """Return default model for this provider."""
        return self._default_model

    def _get_client(self) -> AsyncOpenAI:
        """Get or create the async client."""
        if self._client_instance is None:
            kwargs: dict[str, Any] = {}
            if self._api_key:
                kwargs["api_key"] = self._api_key
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client_instance = AsyncOpenAI(**kwargs)
        return self._client_instance

    def _convert_messages(
        self, messages: Sequence[Message], system_prompt: str | None = None
    ) -> list[dict[str, Any]]:
        """Convert our Message types to OpenAI format."""
        api_messages: list[dict[str, Any]] = []

        # Add system prompt first if provided
        if system_prompt:
            api_messages.append({
                "role": "system",
                "content": system_prompt,
            })

        for msg in messages:
            role = msg.role.value

            if msg.role == MessageRole.TOOL:
                # Tool results need special handling
                api_messages.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content if isinstance(msg.content, str) else "",
                })
            elif isinstance(msg.content, str):
                api_messages.append({
                    "role": role,
                    "content": msg.content,
                })
            else:
                # Handle content blocks (images, etc.)
                content_blocks: list[dict[str, Any]] = []
                for block in msg.content:
                    if block.type == "text":
                        content_blocks.append({
                            "type": "text",
                            "text": block.text,
                        })
                    elif block.type == "image":
                        if block.image_url:
                            content_blocks.append({
                                "type": "image_url",
                                "image_url": {"url": block.image_url},
                            })
                        elif block.image_base64:
                            data_url = f"data:{block.media_type or 'image/png'};base64,{block.image_base64}"
                            content_blocks.append({
                                "type": "image_url",
                                "image_url": {"url": data_url},
                            })
                api_messages.append({
                    "role": role,
                    "content": content_blocks,
                })

        return api_messages

    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse OpenAI API response into LLMResponse."""
        choice = response.choices[0]
        message = choice.message

        content = message.content or ""
        tool_calls: list[ToolCall] = []

        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    arguments = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=arguments,
                        raw_arguments=tc.function.arguments,
                    )
                )

        usage = None
        if response.usage:
            usage = UsageStats(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )

        return LLMResponse(
            content=content,
            tool_calls=tuple(tool_calls),
            finish_reason=choice.finish_reason,
            model=response.model,
            usage=usage,
            raw_response=response,
        )

    async def _handle_api_error(self, error: Exception) -> None:
        """Convert OpenAI exceptions to our exception types."""
        if isinstance(error, OpenAIAuthError):
            raise AuthenticationError(str(error))
        elif isinstance(error, OpenAIRateLimitError):
            raise RateLimitError(str(error))
        elif isinstance(error, OpenAIBadRequestError):
            error_str = str(error).lower()
            if "context" in error_str or "token" in error_str or "length" in error_str:
                raise ContextLengthError(str(error))
            elif "content" in error_str or "policy" in error_str:
                raise ContentPolicyError(str(error))
            raise ProviderError(str(error), is_retryable=False)
        elif isinstance(error, OpenAIAPIError):
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
        api_messages = self._convert_messages(messages, system_prompt)

        try:
            kwargs: dict[str, Any] = {
                "model": model or self._default_model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": api_messages,
            }
            if stop_sequences:
                kwargs["stop"] = list(stop_sequences)

            response = await self._get_client().chat.completions.create(**kwargs)
            return self._parse_response(response)
        except Exception as e:
            await self._handle_api_error(e)
            raise

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
        api_messages = self._convert_messages(messages, system_prompt)

        # Convert tools to OpenAI format
        api_tools = [tool.to_openai_format() for tool in tools]

        try:
            kwargs: dict[str, Any] = {
                "model": model or self._default_model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": api_messages,
                "tools": api_tools,
            }

            # Handle tool_choice
            if isinstance(tool_choice, str):
                if tool_choice == "any":
                    kwargs["tool_choice"] = "required"
                elif tool_choice == "none":
                    del kwargs["tools"]
                # "auto" is default
            elif isinstance(tool_choice, dict):
                kwargs["tool_choice"] = tool_choice

            response = await self._get_client().chat.completions.create(**kwargs)
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
        # Use function calling to force structured output
        tool = self._schema_to_tool(response_schema)

        response = await self.complete_with_tools(
            messages=messages,
            tools=[tool],
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            tool_choice={"type": "function", "function": {"name": tool.name}},
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
        from src.llm.tool_types import ToolParameter

        # Handle dict type (simple case)
        if schema is dict:
            return ToolDefinition(
                name="extract_data",
                description="Extract structured data from the input",
            )

        # Handle dataclasses and Pydantic models
        params: list[ToolParameter] = []

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
        """Count tokens in text using tiktoken."""
        if not text:
            return 0

        try:
            import tiktoken
            model_name = model or self._default_model
            try:
                encoding = tiktoken.encoding_for_model(model_name)
            except KeyError:
                # Fall back to cl100k_base for unknown models
                encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except ImportError:
            # Fallback if tiktoken not available
            return len(text) // 4
