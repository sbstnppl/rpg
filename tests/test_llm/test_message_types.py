"""Tests for LLM message types."""

import pytest
from dataclasses import FrozenInstanceError

from src.llm.message_types import (
    MessageRole,
    MessageContent,
    Message,
)


class TestMessageRole:
    """Tests for MessageRole enum."""

    def test_role_values(self):
        """Test message role enum values."""
        assert MessageRole.SYSTEM.value == "system"
        assert MessageRole.USER.value == "user"
        assert MessageRole.ASSISTANT.value == "assistant"
        assert MessageRole.TOOL.value == "tool"

    def test_role_is_string_enum(self):
        """Test that MessageRole is a string enum."""
        assert isinstance(MessageRole.USER, str)
        assert MessageRole.USER == "user"


class TestMessageContent:
    """Tests for MessageContent dataclass."""

    def test_create_text_content(self):
        """Test creating text content."""
        content = MessageContent(type="text", text="Hello, world!")
        assert content.type == "text"
        assert content.text == "Hello, world!"
        assert content.image_url is None

    def test_create_image_url_content(self):
        """Test creating image URL content."""
        content = MessageContent(
            type="image",
            image_url="https://example.com/image.png",
            media_type="image/png",
        )
        assert content.type == "image"
        assert content.image_url == "https://example.com/image.png"
        assert content.media_type == "image/png"

    def test_create_image_base64_content(self):
        """Test creating base64 image content."""
        content = MessageContent(
            type="image",
            image_base64="iVBORw0KGgo...",
            media_type="image/png",
        )
        assert content.image_base64 == "iVBORw0KGgo..."

    def test_create_tool_use_content(self):
        """Test creating tool use content."""
        content = MessageContent(
            type="tool_use",
            tool_use_id="call_123",
            tool_name="get_weather",
            tool_input={"location": "Paris"},
        )
        assert content.type == "tool_use"
        assert content.tool_use_id == "call_123"
        assert content.tool_name == "get_weather"
        assert content.tool_input == {"location": "Paris"}

    def test_create_tool_result_content(self):
        """Test creating tool result content."""
        content = MessageContent(
            type="tool_result",
            tool_use_id="call_123",
            tool_result="The weather in Paris is sunny.",
            is_error=False,
        )
        assert content.type == "tool_result"
        assert content.tool_result == "The weather in Paris is sunny."
        assert content.is_error is False

    def test_create_tool_error_content(self):
        """Test creating tool error content."""
        content = MessageContent(
            type="tool_result",
            tool_use_id="call_123",
            tool_result="Error: Location not found",
            is_error=True,
        )
        assert content.is_error is True

    def test_content_is_immutable(self):
        """Test that MessageContent is frozen."""
        content = MessageContent(type="text", text="Hello")
        with pytest.raises(FrozenInstanceError):
            content.text = "World"

    def test_content_equality(self):
        """Test that equal content blocks are equal."""
        content1 = MessageContent(type="text", text="Hello")
        content2 = MessageContent(type="text", text="Hello")
        assert content1 == content2


class TestMessage:
    """Tests for Message dataclass."""

    def test_create_message_with_string_content(self):
        """Test creating a message with string content."""
        msg = Message(role=MessageRole.USER, content="Hello!")
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello!"
        assert msg.name is None
        assert msg.tool_call_id is None

    def test_create_message_with_content_blocks(self):
        """Test creating a message with content blocks."""
        blocks = (
            MessageContent(type="text", text="Check this image:"),
            MessageContent(type="image", image_url="https://example.com/img.png"),
        )
        msg = Message(role=MessageRole.USER, content=blocks)
        assert isinstance(msg.content, tuple)
        assert len(msg.content) == 2
        assert msg.content[0].text == "Check this image:"

    def test_create_message_with_name(self):
        """Test creating a message with a name."""
        msg = Message(role=MessageRole.USER, content="Hello!", name="Alice")
        assert msg.name == "Alice"

    def test_message_is_immutable(self):
        """Test that Message is frozen."""
        msg = Message(role=MessageRole.USER, content="Hello!")
        with pytest.raises(FrozenInstanceError):
            msg.content = "World"

    def test_message_equality(self):
        """Test that equal messages are equal."""
        msg1 = Message(role=MessageRole.USER, content="Hello!")
        msg2 = Message(role=MessageRole.USER, content="Hello!")
        assert msg1 == msg2


class TestMessageFactoryMethods:
    """Tests for Message factory class methods."""

    def test_system_message(self):
        """Test creating a system message."""
        msg = Message.system("You are a helpful assistant.")
        assert msg.role == MessageRole.SYSTEM
        assert msg.content == "You are a helpful assistant."

    def test_user_message(self):
        """Test creating a user message."""
        msg = Message.user("What's the weather?")
        assert msg.role == MessageRole.USER
        assert msg.content == "What's the weather?"

    def test_user_message_with_name(self):
        """Test creating a user message with name."""
        msg = Message.user("Hello!", name="Bob")
        assert msg.role == MessageRole.USER
        assert msg.name == "Bob"

    def test_assistant_message(self):
        """Test creating an assistant message."""
        msg = Message.assistant("The weather is sunny.")
        assert msg.role == MessageRole.ASSISTANT
        assert msg.content == "The weather is sunny."

    def test_tool_result_message(self):
        """Test creating a tool result message."""
        msg = Message.tool_result(
            tool_call_id="call_123",
            content="Temperature: 72°F",
        )
        assert msg.role == MessageRole.TOOL
        assert msg.content == "Temperature: 72°F"
        assert msg.tool_call_id == "call_123"

    def test_tool_error_message(self):
        """Test creating a tool error message."""
        msg = Message.tool_result(
            tool_call_id="call_456",
            content="API rate limit exceeded",
            is_error=True,
        )
        assert msg.role == MessageRole.TOOL
        assert msg.tool_call_id == "call_456"


class TestMessageHashability:
    """Tests for Message hashability (for use in sets/dicts)."""

    def test_message_is_hashable(self):
        """Test that Message can be hashed."""
        msg = Message.user("Hello!")
        hash_value = hash(msg)
        assert isinstance(hash_value, int)

    def test_equal_messages_have_same_hash(self):
        """Test that equal messages have the same hash."""
        msg1 = Message.user("Hello!")
        msg2 = Message.user("Hello!")
        assert hash(msg1) == hash(msg2)

    def test_messages_can_be_set_members(self):
        """Test that messages can be added to sets."""
        msg1 = Message.user("Hello!")
        msg2 = Message.user("World!")
        msg_set = {msg1, msg2}
        assert len(msg_set) == 2

    def test_messages_can_be_dict_keys(self):
        """Test that messages can be dict keys."""
        msg = Message.user("Hello!")
        msg_dict = {msg: "greeting"}
        assert msg_dict[msg] == "greeting"
