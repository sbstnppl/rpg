"""LLM tool type definitions.

Immutable dataclasses for tool/function calling definitions.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolParameter:
    """Parameter definition for a tool.

    Attributes:
        name: Parameter name.
        type: JSON Schema type (string, integer, boolean, array, object).
        description: What this parameter does.
        required: Whether the parameter is required.
        enum: Allowed values (if constrained).
        default: Default value if not provided.
        items: Schema for array items (when type="array").
    """

    name: str
    type: str
    description: str
    required: bool = True
    enum: tuple[str, ...] | None = None
    default: Any = None
    items: dict[str, Any] | None = None


@dataclass(frozen=True)
class ToolDefinition:
    """Definition of a tool/function the LLM can call.

    Attributes:
        name: Unique tool name.
        description: What the tool does.
        parameters: Parameter definitions.
    """

    name: str
    description: str
    parameters: tuple[ToolParameter, ...] = field(default_factory=tuple)

    def to_json_schema(self) -> dict[str, Any]:
        """Convert to JSON Schema format.

        Returns:
            JSON Schema object with properties and required fields.
        """
        properties: dict[str, Any] = {}
        required: list[str] = []

        for param in self.parameters:
            prop: dict[str, Any] = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = list(param.enum)
            if param.items:
                prop["items"] = param.items
            properties[param.name] = prop

            if param.required:
                required.append(param.name)

        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    def to_anthropic_format(self) -> dict[str, Any]:
        """Convert to Anthropic's tool format.

        Returns:
            Dict in Anthropic's expected tool structure.
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.to_json_schema(),
        }

    def to_openai_format(self) -> dict[str, Any]:
        """Convert to OpenAI's function calling format.

        Returns:
            Dict in OpenAI's expected function structure.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.to_json_schema(),
            },
        }
