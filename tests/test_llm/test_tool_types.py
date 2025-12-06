"""Tests for LLM tool types."""

import pytest
from dataclasses import FrozenInstanceError

from src.llm.tool_types import ToolParameter, ToolDefinition


class TestToolParameter:
    """Tests for ToolParameter dataclass."""

    def test_create_required_string_parameter(self):
        """Test creating a required string parameter."""
        param = ToolParameter(
            name="location",
            type="string",
            description="The city name",
        )
        assert param.name == "location"
        assert param.type == "string"
        assert param.description == "The city name"
        assert param.required is True
        assert param.enum is None
        assert param.default is None

    def test_create_optional_parameter(self):
        """Test creating an optional parameter with default."""
        param = ToolParameter(
            name="unit",
            type="string",
            description="Temperature unit",
            required=False,
            default="celsius",
        )
        assert param.required is False
        assert param.default == "celsius"

    def test_create_enum_parameter(self):
        """Test creating a parameter with enum constraint."""
        param = ToolParameter(
            name="unit",
            type="string",
            description="Temperature unit",
            enum=("celsius", "fahrenheit"),
        )
        assert param.enum == ("celsius", "fahrenheit")

    def test_create_integer_parameter(self):
        """Test creating an integer parameter."""
        param = ToolParameter(
            name="count",
            type="integer",
            description="Number of results",
        )
        assert param.type == "integer"

    def test_create_boolean_parameter(self):
        """Test creating a boolean parameter."""
        param = ToolParameter(
            name="include_details",
            type="boolean",
            description="Include extra details",
            required=False,
            default=False,
        )
        assert param.type == "boolean"
        assert param.default is False

    def test_create_array_parameter(self):
        """Test creating an array parameter."""
        param = ToolParameter(
            name="tags",
            type="array",
            description="List of tags",
            items={"type": "string"},
        )
        assert param.type == "array"
        assert param.items == {"type": "string"}

    def test_parameter_is_immutable(self):
        """Test that ToolParameter is frozen."""
        param = ToolParameter(
            name="location",
            type="string",
            description="The city",
        )
        with pytest.raises(FrozenInstanceError):
            param.name = "city"

    def test_parameter_equality(self):
        """Test that equal parameters are equal."""
        param1 = ToolParameter(name="loc", type="string", description="City")
        param2 = ToolParameter(name="loc", type="string", description="City")
        assert param1 == param2


class TestToolDefinition:
    """Tests for ToolDefinition dataclass."""

    def test_create_tool_without_parameters(self):
        """Test creating a tool with no parameters."""
        tool = ToolDefinition(
            name="get_time",
            description="Get the current time",
        )
        assert tool.name == "get_time"
        assert tool.description == "Get the current time"
        assert tool.parameters == ()

    def test_create_tool_with_parameters(self):
        """Test creating a tool with parameters."""
        params = (
            ToolParameter(name="city", type="string", description="City name"),
            ToolParameter(
                name="unit",
                type="string",
                description="Temperature unit",
                required=False,
                enum=("celsius", "fahrenheit"),
            ),
        )
        tool = ToolDefinition(
            name="get_weather",
            description="Get weather for a city",
            parameters=params,
        )
        assert tool.name == "get_weather"
        assert len(tool.parameters) == 2
        assert tool.parameters[0].name == "city"
        assert tool.parameters[1].required is False

    def test_tool_is_immutable(self):
        """Test that ToolDefinition is frozen."""
        tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
        )
        with pytest.raises(FrozenInstanceError):
            tool.name = "new_name"


class TestToolDefinitionJsonSchema:
    """Tests for ToolDefinition JSON schema conversion."""

    def test_to_json_schema_empty_params(self):
        """Test JSON schema with no parameters."""
        tool = ToolDefinition(
            name="get_time",
            description="Get current time",
        )
        schema = tool.to_json_schema()
        assert schema == {
            "type": "object",
            "properties": {},
            "required": [],
        }

    def test_to_json_schema_with_required_param(self):
        """Test JSON schema with required parameter."""
        tool = ToolDefinition(
            name="get_weather",
            description="Get weather",
            parameters=(
                ToolParameter(name="city", type="string", description="City name"),
            ),
        )
        schema = tool.to_json_schema()
        assert schema == {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name",
                },
            },
            "required": ["city"],
        }

    def test_to_json_schema_with_optional_param(self):
        """Test JSON schema with optional parameter."""
        tool = ToolDefinition(
            name="search",
            description="Search for items",
            parameters=(
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="Max results",
                    required=False,
                ),
            ),
        )
        schema = tool.to_json_schema()
        assert "limit" not in schema["required"]
        assert schema["properties"]["limit"]["type"] == "integer"

    def test_to_json_schema_with_enum(self):
        """Test JSON schema with enum constraint."""
        tool = ToolDefinition(
            name="set_mode",
            description="Set mode",
            parameters=(
                ToolParameter(
                    name="mode",
                    type="string",
                    description="The mode",
                    enum=("fast", "slow", "normal"),
                ),
            ),
        )
        schema = tool.to_json_schema()
        assert schema["properties"]["mode"]["enum"] == ["fast", "slow", "normal"]

    def test_to_json_schema_with_array(self):
        """Test JSON schema with array parameter."""
        tool = ToolDefinition(
            name="add_tags",
            description="Add tags",
            parameters=(
                ToolParameter(
                    name="tags",
                    type="array",
                    description="Tags to add",
                    items={"type": "string"},
                ),
            ),
        )
        schema = tool.to_json_schema()
        assert schema["properties"]["tags"]["type"] == "array"
        assert schema["properties"]["tags"]["items"] == {"type": "string"}


class TestToolDefinitionProviderFormats:
    """Tests for ToolDefinition provider-specific formats."""

    def test_to_anthropic_format(self):
        """Test conversion to Anthropic tool format."""
        tool = ToolDefinition(
            name="get_weather",
            description="Get weather for a location",
            parameters=(
                ToolParameter(name="city", type="string", description="City name"),
            ),
        )
        anthropic_format = tool.to_anthropic_format()
        assert anthropic_format == {
            "name": "get_weather",
            "description": "Get weather for a location",
            "input_schema": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"},
                },
                "required": ["city"],
            },
        }

    def test_to_openai_format(self):
        """Test conversion to OpenAI function format."""
        tool = ToolDefinition(
            name="get_weather",
            description="Get weather for a location",
            parameters=(
                ToolParameter(name="city", type="string", description="City name"),
            ),
        )
        openai_format = tool.to_openai_format()
        assert openai_format == {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "City name"},
                    },
                    "required": ["city"],
                },
            },
        }


class TestToolHashability:
    """Tests for tool type hashability."""

    def test_tool_parameter_is_hashable(self):
        """Test that ToolParameter can be hashed."""
        param = ToolParameter(name="test", type="string", description="A test")
        assert isinstance(hash(param), int)

    def test_tool_definition_is_hashable(self):
        """Test that ToolDefinition can be hashed."""
        tool = ToolDefinition(name="test", description="A test tool")
        assert isinstance(hash(tool), int)
