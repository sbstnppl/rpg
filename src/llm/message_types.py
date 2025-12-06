"""LLM message type definitions.

Immutable dataclasses for messages, content blocks, and conversation history.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class MessageRole(str, Enum):
    """Role of a message in the conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True)
class MessageContent:
    """Content block within a message.

    Supports text, images, tool use, and tool results.

    Attributes:
        type: Content type ("text", "image", "tool_use", "tool_result").
        text: Text content (for type="text").
        image_url: URL to an image (for type="image").
        image_base64: Base64-encoded image data (for type="image").
        media_type: MIME type for images (e.g., "image/png").
        tool_use_id: Unique ID for tool use/result matching.
        tool_name: Name of the tool being called.
        tool_input: Arguments passed to the tool.
        tool_result: Result returned from tool execution.
        is_error: Whether the tool result is an error.
    """

    type: str
    text: str | None = None
    image_url: str | None = None
    image_base64: str | None = None
    media_type: str | None = None
    tool_use_id: str | None = None
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    tool_result: str | None = None
    is_error: bool = False


@dataclass(frozen=True)
class Message:
    """A message in a conversation.

    Attributes:
        role: Who sent the message (system, user, assistant, tool).
        content: Text content or tuple of content blocks.
        name: Optional name for the participant.
        tool_call_id: ID linking tool result to its call.
    """

    role: MessageRole
    content: str | tuple[MessageContent, ...] = ""
    name: str | None = None
    tool_call_id: str | None = None

    @classmethod
    def system(cls, content: str) -> "Message":
        """Create a system message.

        Args:
            content: System instructions/context.

        Returns:
            A Message with role=SYSTEM.
        """
        return cls(role=MessageRole.SYSTEM, content=content)

    @classmethod
    def user(cls, content: str, name: str | None = None) -> "Message":
        """Create a user message.

        Args:
            content: User's message text.
            name: Optional name for the user.

        Returns:
            A Message with role=USER.
        """
        return cls(role=MessageRole.USER, content=content, name=name)

    @classmethod
    def assistant(cls, content: str) -> "Message":
        """Create an assistant message.

        Args:
            content: Assistant's response text.

        Returns:
            A Message with role=ASSISTANT.
        """
        return cls(role=MessageRole.ASSISTANT, content=content)

    @classmethod
    def tool_result(
        cls,
        tool_call_id: str,
        content: str,
        is_error: bool = False,
    ) -> "Message":
        """Create a tool result message.

        Args:
            tool_call_id: ID of the tool call this responds to.
            content: Result from tool execution.
            is_error: Whether the result is an error.

        Returns:
            A Message with role=TOOL.
        """
        return cls(
            role=MessageRole.TOOL,
            content=content,
            tool_call_id=tool_call_id,
        )
