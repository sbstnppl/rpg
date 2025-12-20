"""Tests for world tools - LLM function calling tools for world simulation."""

import pytest


class TestWorldToolDefinitions:
    """Test world tool definition schemas."""

    def test_advance_time_tool_defined(self):
        """advance_time tool should be properly defined."""
        from src.agents.tools.world_tools import ADVANCE_TIME_TOOL

        assert ADVANCE_TIME_TOOL.name == "advance_time"
        param_names = [p.name for p in ADVANCE_TIME_TOOL.parameters]
        assert "minutes" in param_names

    def test_move_npc_tool_defined(self):
        """move_npc tool should be properly defined."""
        from src.agents.tools.world_tools import MOVE_NPC_TOOL

        assert MOVE_NPC_TOOL.name == "move_npc"
        param_names = [p.name for p in MOVE_NPC_TOOL.parameters]
        assert "entity_key" in param_names
        assert "location_key" in param_names

    def test_change_weather_tool_defined(self):
        """change_weather tool should be properly defined."""
        from src.agents.tools.world_tools import CHANGE_WEATHER_TOOL

        assert CHANGE_WEATHER_TOOL.name == "change_weather"
        param_names = [p.name for p in CHANGE_WEATHER_TOOL.parameters]
        assert "weather" in param_names

    def test_create_world_event_tool_defined(self):
        """create_world_event tool should be properly defined."""
        from src.agents.tools.world_tools import CREATE_WORLD_EVENT_TOOL

        assert CREATE_WORLD_EVENT_TOOL.name == "create_world_event"
        param_names = [p.name for p in CREATE_WORLD_EVENT_TOOL.parameters]
        assert "event_type" in param_names
        assert "summary" in param_names

    def test_update_npc_need_tool_defined(self):
        """update_npc_need tool should be properly defined."""
        from src.agents.tools.world_tools import UPDATE_NPC_NEED_TOOL

        assert UPDATE_NPC_NEED_TOOL.name == "update_npc_need"
        param_names = [p.name for p in UPDATE_NPC_NEED_TOOL.parameters]
        assert "entity_key" in param_names
        assert "need" in param_names
        assert "delta" in param_names

    def test_set_location_state_tool_defined(self):
        """set_location_state tool should be properly defined."""
        from src.agents.tools.world_tools import SET_LOCATION_STATE_TOOL

        assert SET_LOCATION_STATE_TOOL.name == "set_location_state"
        param_names = [p.name for p in SET_LOCATION_STATE_TOOL.parameters]
        assert "location_key" in param_names

    def test_world_tools_list(self):
        """WORLD_TOOLS should contain all tools."""
        from src.agents.tools.world_tools import WORLD_TOOLS

        assert len(WORLD_TOOLS) >= 6
        names = [t.name for t in WORLD_TOOLS]
        assert "advance_time" in names
        assert "move_npc" in names
        assert "change_weather" in names
        assert "create_world_event" in names
        assert "update_npc_need" in names
        assert "set_location_state" in names


class TestWorldToolSchemas:
    """Test world tool JSON schema generation."""

    def test_advance_time_to_json_schema(self):
        """Tool should generate valid JSON schema."""
        from src.agents.tools.world_tools import ADVANCE_TIME_TOOL

        schema = ADVANCE_TIME_TOOL.to_json_schema()

        assert "properties" in schema
        assert "minutes" in schema["properties"]
        assert schema["properties"]["minutes"]["type"] == "integer"

    def test_move_npc_to_anthropic_format(self):
        """Tool should convert to Anthropic format."""
        from src.agents.tools.world_tools import MOVE_NPC_TOOL

        anthropic_tool = MOVE_NPC_TOOL.to_anthropic_format()

        assert anthropic_tool["name"] == "move_npc"
        assert "input_schema" in anthropic_tool

    def test_weather_has_enum(self):
        """weather parameter should have enum constraint."""
        from src.agents.tools.world_tools import CHANGE_WEATHER_TOOL

        weather_param = next(
            p for p in CHANGE_WEATHER_TOOL.parameters if p.name == "weather"
        )
        assert weather_param.enum is not None
        assert "clear" in weather_param.enum
        assert "rain" in weather_param.enum
        assert "storm" in weather_param.enum

    def test_event_type_has_enum(self):
        """event_type parameter should have enum constraint."""
        from src.agents.tools.world_tools import CREATE_WORLD_EVENT_TOOL

        event_type_param = next(
            p for p in CREATE_WORLD_EVENT_TOOL.parameters if p.name == "event_type"
        )
        assert event_type_param.enum is not None
        assert "social" in event_type_param.enum
        assert "environmental" in event_type_param.enum

    def test_need_has_enum(self):
        """need parameter should have enum constraint."""
        from src.agents.tools.world_tools import UPDATE_NPC_NEED_TOOL

        need_param = next(
            p for p in UPDATE_NPC_NEED_TOOL.parameters if p.name == "need"
        )
        assert need_param.enum is not None
        assert "hunger" in need_param.enum
        assert "stamina" in need_param.enum
        assert "sleep_pressure" in need_param.enum
