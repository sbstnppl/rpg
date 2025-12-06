"""Tests for combat tools - LLM function calling tools for combat resolution."""

import pytest


class TestCombatToolDefinitions:
    """Test combat tool definition schemas."""

    def test_roll_initiative_tool_defined(self):
        """roll_initiative tool should be properly defined."""
        from src.agents.tools.combat_tools import ROLL_INITIATIVE_TOOL

        assert ROLL_INITIATIVE_TOOL.name == "roll_initiative"
        param_names = [p.name for p in ROLL_INITIATIVE_TOOL.parameters]
        assert "combatant_ids" in param_names

    def test_resolve_attack_tool_defined(self):
        """resolve_attack tool should be properly defined."""
        from src.agents.tools.combat_tools import RESOLVE_ATTACK_TOOL

        assert RESOLVE_ATTACK_TOOL.name == "resolve_attack"
        param_names = [p.name for p in RESOLVE_ATTACK_TOOL.parameters]
        assert "attacker_id" in param_names
        assert "target_id" in param_names

    def test_apply_damage_tool_defined(self):
        """apply_damage tool should be properly defined."""
        from src.agents.tools.combat_tools import APPLY_DAMAGE_TOOL

        assert APPLY_DAMAGE_TOOL.name == "apply_damage"
        param_names = [p.name for p in APPLY_DAMAGE_TOOL.parameters]
        assert "target_id" in param_names
        assert "damage" in param_names
        assert "damage_type" in param_names

    def test_apply_healing_tool_defined(self):
        """apply_healing tool should be properly defined."""
        from src.agents.tools.combat_tools import APPLY_HEALING_TOOL

        assert APPLY_HEALING_TOOL.name == "apply_healing"
        param_names = [p.name for p in APPLY_HEALING_TOOL.parameters]
        assert "target_id" in param_names
        assert "amount" in param_names

    def test_apply_status_tool_defined(self):
        """apply_status tool should be properly defined."""
        from src.agents.tools.combat_tools import APPLY_STATUS_TOOL

        assert APPLY_STATUS_TOOL.name == "apply_status"
        param_names = [p.name for p in APPLY_STATUS_TOOL.parameters]
        assert "target_id" in param_names
        assert "status" in param_names

    def test_end_combat_tool_defined(self):
        """end_combat tool should be properly defined."""
        from src.agents.tools.combat_tools import END_COMBAT_TOOL

        assert END_COMBAT_TOOL.name == "end_combat"
        param_names = [p.name for p in END_COMBAT_TOOL.parameters]
        assert "outcome" in param_names

    def test_advance_turn_tool_defined(self):
        """advance_turn tool should be properly defined."""
        from src.agents.tools.combat_tools import ADVANCE_TURN_TOOL

        assert ADVANCE_TURN_TOOL.name == "advance_turn"
        # This tool has no parameters
        assert len(ADVANCE_TURN_TOOL.parameters) == 0

    def test_combat_tools_list(self):
        """COMBAT_TOOLS should contain all tools."""
        from src.agents.tools.combat_tools import COMBAT_TOOLS

        assert len(COMBAT_TOOLS) >= 7
        names = [t.name for t in COMBAT_TOOLS]
        assert "roll_initiative" in names
        assert "resolve_attack" in names
        assert "apply_damage" in names
        assert "apply_healing" in names
        assert "apply_status" in names
        assert "end_combat" in names
        assert "advance_turn" in names


class TestCombatToolSchemas:
    """Test combat tool JSON schema generation."""

    def test_apply_damage_to_json_schema(self):
        """Tool should generate valid JSON schema."""
        from src.agents.tools.combat_tools import APPLY_DAMAGE_TOOL

        schema = APPLY_DAMAGE_TOOL.to_json_schema()

        assert "properties" in schema
        assert "target_id" in schema["properties"]
        assert schema["properties"]["target_id"]["type"] == "integer"
        assert schema["properties"]["damage"]["type"] == "integer"

    def test_end_combat_to_anthropic_format(self):
        """Tool should convert to Anthropic format."""
        from src.agents.tools.combat_tools import END_COMBAT_TOOL

        anthropic_tool = END_COMBAT_TOOL.to_anthropic_format()

        assert anthropic_tool["name"] == "end_combat"
        assert "input_schema" in anthropic_tool

    def test_status_has_enum(self):
        """status parameter should have enum constraint."""
        from src.agents.tools.combat_tools import APPLY_STATUS_TOOL

        status_param = next(
            p for p in APPLY_STATUS_TOOL.parameters if p.name == "status"
        )
        assert status_param.enum is not None
        assert "stunned" in status_param.enum
        assert "poisoned" in status_param.enum

    def test_outcome_has_enum(self):
        """outcome parameter should have enum constraint."""
        from src.agents.tools.combat_tools import END_COMBAT_TOOL

        outcome_param = next(
            p for p in END_COMBAT_TOOL.parameters if p.name == "outcome"
        )
        assert outcome_param.enum is not None
        assert "victory" in outcome_param.enum
        assert "defeat" in outcome_param.enum
        assert "fled" in outcome_param.enum
