"""Qwen-Agent provider for Qwen3 tool calling via Ollama.

Uses qwen-agent library to handle tool calling templates internally,
bypassing Ollama's native tool API limitation (which doesn't support Qwen3 yet).
"""

import json
import re
from typing import Any, Sequence

from qwen_agent.llm import get_chat_model

from src.llm.message_types import Message, MessageRole
from src.llm.response_types import LLMResponse, ToolCall, UsageStats
from src.llm.tool_types import ToolDefinition
from src.llm.exceptions import ProviderError, StructuredOutputError


class QwenAgentProvider:
    """Qwen-Agent LLM provider for Qwen3 with tool calling support.

    Uses qwen-agent's internal Hermes tool format templates to enable
    tool calling for Qwen3 models via Ollama (which doesn't natively
    support Qwen3 tools yet).

    Supports:
    - Qwen3 via Ollama (primary use case)
    - Direct Qwen API (optional)
    - Tool calling via Hermes format
    - Structured output via tool schemas

    Note:
    - Token counting is approximate (no direct tokenizer access)
    - Usage stats not available from qwen-agent
    """

    CHARS_PER_TOKEN = 4  # Rough estimate for token counting
    # Match complete thinking blocks
    THINKING_PATTERN = re.compile(r"<think>.*?</think>\s*", re.DOTALL)
    # Match incomplete thinking blocks (cut off before closing tag)
    THINKING_INCOMPLETE = re.compile(r"<think>.*$", re.DOTALL)

    @staticmethod
    def _strip_thinking(content: str) -> str:
        """Remove <think>...</think> tags from response content.

        Handles both complete and incomplete (cut-off) thinking blocks.
        """
        # First remove complete blocks
        result = QwenAgentProvider.THINKING_PATTERN.sub("", content)
        # Then remove any incomplete block at the end
        result = QwenAgentProvider.THINKING_INCOMPLETE.sub("", result)
        return result.strip()

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        default_model: str = "qwen3",
        api_key: str = "EMPTY",
    ) -> None:
        """Initialize Qwen-Agent provider.

        Args:
            base_url: Ollama OpenAI-compatible endpoint (with /v1).
            default_model: Default model to use for completions.
            api_key: API key (use "EMPTY" for local Ollama).
        """
        self._base_url = base_url
        self._default_model = default_model
        self._api_key = api_key
        self._llm = None

    @property
    def provider_name(self) -> str:
        """Return provider identifier."""
        return "qwen-agent"

    @property
    def default_model(self) -> str:
        """Return default model for this provider."""
        return self._default_model

    @property
    def llm(self):
        """Lazy-load the LLM instance."""
        if self._llm is None:
            self._llm = get_chat_model({
                "model": self._default_model,
                "model_server": self._base_url,
                "api_key": self._api_key,
            })
        return self._llm

    def _convert_messages(
        self,
        messages: Sequence[Message],
        system_prompt: str | None = None,
    ) -> list[dict[str, Any]]:
        """Convert our Message types to qwen-agent message format."""
        qwen_messages: list[dict[str, Any]] = []

        # Add system prompt first if provided
        if system_prompt:
            qwen_messages.append({
                "role": "system",
                "content": system_prompt,
            })

        for msg in messages:
            content = msg.content if isinstance(msg.content, str) else str(msg.content)

            if msg.role == MessageRole.USER:
                qwen_messages.append({
                    "role": "user",
                    "content": content,
                })
            elif msg.role == MessageRole.ASSISTANT:
                qwen_messages.append({
                    "role": "assistant",
                    "content": content,
                })
            elif msg.role == MessageRole.SYSTEM:
                # System messages are already handled above if passed separately
                qwen_messages.append({
                    "role": "system",
                    "content": content,
                })
            elif msg.role == MessageRole.TOOL:
                # qwen-agent uses "function" role for tool results
                qwen_messages.append({
                    "role": "function",
                    "name": msg.name or msg.tool_call_id or "unknown",
                    "content": content,
                })

        return qwen_messages

    def _extract_functions(self, tools: Sequence[ToolDefinition]) -> list[dict[str, Any]]:
        """Convert ToolDefinitions to qwen-agent function format."""
        functions = []
        for tool in tools:
            functions.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.to_json_schema(),
            })
        return functions

    def _parse_response(
        self,
        response_messages: list[dict[str, Any]],
        model: str,
    ) -> LLMResponse:
        """Parse qwen-agent response into LLMResponse."""
        tool_calls: list[ToolCall] = []
        content = ""

        for msg in response_messages:
            if msg.get("role") == "assistant":
                raw_content = msg.get("content", "")
                content = self._strip_thinking(raw_content) if raw_content else ""

                # Check for function_call
                if fn_call := msg.get("function_call"):
                    # Parse arguments (may be JSON string)
                    args_raw = fn_call.get("arguments", "{}")
                    if isinstance(args_raw, str):
                        try:
                            args = json.loads(args_raw)
                        except json.JSONDecodeError:
                            args = {}
                    else:
                        args = args_raw

                    tool_calls.append(ToolCall(
                        id=fn_call.get("name", "unknown"),  # Use name as ID
                        name=fn_call["name"],
                        arguments=args,
                        raw_arguments=args_raw if isinstance(args_raw, str) else json.dumps(args),
                    ))

        return LLMResponse(
            content=content,
            tool_calls=tuple(tool_calls),
            finish_reason="stop",
            model=model,
            usage=None,  # qwen-agent doesn't expose token counts
        )

    async def complete(
        self,
        messages: Sequence[Message],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        stop_sequences: Sequence[str] | None = None,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Generate a completion from messages.

        Args:
            messages: Conversation messages.
            model: Model to use (defaults to provider's default).
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            stop_sequences: Stop sequences (not directly supported).
            system_prompt: System prompt to prepend.
        """
        qwen_messages = self._convert_messages(messages, system_prompt)
        model_name = model or self._default_model

        try:
            # qwen-agent's chat() returns a generator
            response_messages = []
            for response in self.llm.chat(
                messages=qwen_messages,
                stream=False,
            ):
                # Handle both list and single message responses
                if isinstance(response, list):
                    response_messages.extend(response)
                elif isinstance(response, dict):
                    response_messages.append(response)
                elif isinstance(response, str):
                    response_messages.append({"role": "assistant", "content": response})
                else:
                    if hasattr(response, "__iter__") and not isinstance(response, str):
                        response_messages.extend(response)
                    else:
                        response_messages.append({"role": "assistant", "content": str(response)})

            return self._parse_response(response_messages, model_name)
        except Exception as e:
            raise ProviderError(str(e), is_retryable=True)

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
        """Generate a completion that may include tool calls.

        Uses qwen-agent's internal Hermes tool format to enable
        tool calling for Qwen3 via Ollama.

        Args:
            messages: Conversation messages.
            tools: Available tool definitions.
            model: Model to use (defaults to provider's default).
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            tool_choice: Tool selection mode (not directly used).
            system_prompt: System prompt to prepend.
        """
        qwen_messages = self._convert_messages(messages, system_prompt)
        model_name = model or self._default_model
        functions = self._extract_functions(tools)

        try:
            # qwen-agent's chat() with functions returns a generator
            response_messages = []
            for response in self.llm.chat(
                messages=qwen_messages,
                functions=functions,
                stream=False,
            ):
                # Debug: log what we're getting
                import logging
                logging.getLogger(__name__).debug(
                    f"qwen-agent response type: {type(response)}, value: {response!r}"
                )
                # Handle both list and single message responses
                if isinstance(response, list):
                    response_messages.extend(response)
                elif isinstance(response, dict):
                    response_messages.append(response)
                elif isinstance(response, str):
                    # Response is raw text - wrap it in assistant message format
                    response_messages.append({"role": "assistant", "content": response})
                else:
                    # Try to handle Message objects from qwen-agent
                    if hasattr(response, "__iter__") and not isinstance(response, str):
                        response_messages.extend(response)
                    else:
                        response_messages.append({"role": "assistant", "content": str(response)})

            return self._parse_response(response_messages, model_name)
        except Exception as e:
            raise ProviderError(str(e), is_retryable=True)

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

        Uses tool calling to enforce JSON schema output.

        Args:
            messages: Conversation messages.
            response_schema: Pydantic model or dataclass for output.
            model: Model to use.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            system_prompt: System prompt to prepend.
        """
        # Get JSON schema from Pydantic model
        if hasattr(response_schema, "model_json_schema"):
            schema = response_schema.model_json_schema()
        elif hasattr(response_schema, "__dataclass_fields__"):
            # Dataclass - build schema manually
            schema = {
                "type": "object",
                "properties": {},
                "required": [],
            }
            for name, field in response_schema.__dataclass_fields__.items():
                schema["properties"][name] = {"type": "string"}
                schema["required"].append(name)
        else:
            raise StructuredOutputError(
                f"Cannot generate schema for {response_schema}",
                raw_output="",
            )

        # Create a tool that outputs the structured response
        tool = ToolDefinition(
            name="respond",
            description="Provide your response in the required format.",
            parameters=tuple(),  # Will use raw schema
        )

        # Build function definition with schema
        functions = [{
            "name": "respond",
            "description": "Provide your response in the required format.",
            "parameters": schema,
        }]

        qwen_messages = self._convert_messages(messages, system_prompt)
        model_name = model or self._default_model

        try:
            response_messages = []
            for response in self.llm.chat(
                messages=qwen_messages,
                functions=functions,
                stream=False,
            ):
                response_messages.extend(response)

            llm_response = self._parse_response(response_messages, model_name)

            # Extract structured content from tool call
            if llm_response.has_tool_calls:
                parsed_content = llm_response.tool_calls[0].arguments
            else:
                # Try to parse content as JSON
                try:
                    parsed_content = json.loads(llm_response.content)
                except json.JSONDecodeError:
                    raise StructuredOutputError(
                        "Failed to parse structured output",
                        raw_output=llm_response.content,
                    )

            return LLMResponse(
                content="",
                parsed_content=parsed_content,
                finish_reason=llm_response.finish_reason,
                model=model_name,
                usage=None,
            )
        except StructuredOutputError:
            raise
        except Exception as e:
            raise StructuredOutputError(str(e), raw_output=str(e))

    def count_tokens(
        self,
        text: str,
        model: str | None = None,
    ) -> int:
        """Count tokens in text (rough estimate).

        qwen-agent doesn't provide a public tokenizer, so we use a heuristic
        of approximately 4 characters per token.
        """
        if not text:
            return 0
        return len(text) // self.CHARS_PER_TOKEN
