"""Tests for extraction tools - LLM function calling tools for entity extraction."""

import pytest


class TestExtractionToolDefinitions:
    """Test extraction tool definition schemas."""

    def test_create_entity_tool_defined(self):
        """create_entity tool should be properly defined."""
        from src.agents.tools.extraction_tools import CREATE_ENTITY_TOOL

        assert CREATE_ENTITY_TOOL.name == "create_entity"
        param_names = [p.name for p in CREATE_ENTITY_TOOL.parameters]
        assert "entity_key" in param_names
        assert "display_name" in param_names
        assert "entity_type" in param_names

    def test_record_fact_tool_defined(self):
        """record_fact tool should be properly defined."""
        from src.agents.tools.extraction_tools import RECORD_FACT_TOOL

        assert RECORD_FACT_TOOL.name == "record_fact"
        param_names = [p.name for p in RECORD_FACT_TOOL.parameters]
        assert "subject_key" in param_names
        assert "predicate" in param_names
        assert "value" in param_names

    def test_create_item_tool_defined(self):
        """create_item tool should be properly defined."""
        from src.agents.tools.extraction_tools import CREATE_ITEM_TOOL

        assert CREATE_ITEM_TOOL.name == "create_item"
        param_names = [p.name for p in CREATE_ITEM_TOOL.parameters]
        assert "item_key" in param_names
        assert "display_name" in param_names
        assert "item_type" in param_names

    def test_update_relationship_tool_defined(self):
        """update_relationship tool should be properly defined."""
        from src.agents.tools.extraction_tools import UPDATE_RELATIONSHIP_TOOL

        assert UPDATE_RELATIONSHIP_TOOL.name == "update_relationship"
        param_names = [p.name for p in UPDATE_RELATIONSHIP_TOOL.parameters]
        assert "from_entity" in param_names
        assert "to_entity" in param_names
        assert "dimension" in param_names
        assert "delta" in param_names

    def test_create_appointment_tool_defined(self):
        """create_appointment tool should be properly defined."""
        from src.agents.tools.extraction_tools import CREATE_APPOINTMENT_TOOL

        assert CREATE_APPOINTMENT_TOOL.name == "create_appointment"
        param_names = [p.name for p in CREATE_APPOINTMENT_TOOL.parameters]
        assert "description" in param_names
        assert "game_day" in param_names
        assert "time_of_day" in param_names

    def test_extraction_tools_list(self):
        """EXTRACTION_TOOLS should contain all tools."""
        from src.agents.tools.extraction_tools import EXTRACTION_TOOLS

        assert len(EXTRACTION_TOOLS) >= 5
        names = [t.name for t in EXTRACTION_TOOLS]
        assert "create_entity" in names
        assert "record_fact" in names
        assert "create_item" in names
        assert "update_relationship" in names
        assert "create_appointment" in names


class TestExtractionToolSchemas:
    """Test extraction tool JSON schema generation."""

    def test_create_entity_to_json_schema(self):
        """Tool should generate valid JSON schema."""
        from src.agents.tools.extraction_tools import CREATE_ENTITY_TOOL

        schema = CREATE_ENTITY_TOOL.to_json_schema()

        assert "properties" in schema
        assert "entity_key" in schema["properties"]
        assert schema["properties"]["entity_key"]["type"] == "string"

    def test_record_fact_to_anthropic_format(self):
        """Tool should convert to Anthropic format."""
        from src.agents.tools.extraction_tools import RECORD_FACT_TOOL

        anthropic_tool = RECORD_FACT_TOOL.to_anthropic_format()

        assert anthropic_tool["name"] == "record_fact"
        assert "input_schema" in anthropic_tool
        assert "properties" in anthropic_tool["input_schema"]

    def test_entity_type_has_enum(self):
        """entity_type parameter should have enum constraint."""
        from src.agents.tools.extraction_tools import CREATE_ENTITY_TOOL

        entity_type_param = next(
            p for p in CREATE_ENTITY_TOOL.parameters if p.name == "entity_type"
        )
        assert entity_type_param.enum is not None
        assert "npc" in entity_type_param.enum
        assert "monster" in entity_type_param.enum

    def test_item_type_has_enum(self):
        """item_type parameter should have enum constraint."""
        from src.agents.tools.extraction_tools import CREATE_ITEM_TOOL

        item_type_param = next(
            p for p in CREATE_ITEM_TOOL.parameters if p.name == "item_type"
        )
        assert item_type_param.enum is not None
        assert "weapon" in item_type_param.enum
        assert "armor" in item_type_param.enum
