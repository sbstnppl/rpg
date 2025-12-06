"""Tests for GM tools - LLM function calling tools."""

import pytest
from unittest.mock import patch, MagicMock

from sqlalchemy.orm import Session

from src.database.models.session import GameSession
from src.database.models.entities import Entity
from src.database.models.enums import EntityType
from tests.factories import create_entity, create_relationship


class TestToolDefinitions:
    """Test tool definition schemas."""

    def test_skill_check_tool_defined(self):
        """skill_check tool should be properly defined."""
        from src.agents.tools.gm_tools import SKILL_CHECK_TOOL

        assert SKILL_CHECK_TOOL.name == "skill_check"
        assert "dc" in [p.name for p in SKILL_CHECK_TOOL.parameters]
        assert "skill_name" in [p.name for p in SKILL_CHECK_TOOL.parameters]

    def test_attack_roll_tool_defined(self):
        """attack_roll tool should be properly defined."""
        from src.agents.tools.gm_tools import ATTACK_ROLL_TOOL

        assert ATTACK_ROLL_TOOL.name == "attack_roll"
        assert "target_ac" in [p.name for p in ATTACK_ROLL_TOOL.parameters]

    def test_roll_damage_tool_defined(self):
        """roll_damage tool should be properly defined."""
        from src.agents.tools.gm_tools import ROLL_DAMAGE_TOOL

        assert ROLL_DAMAGE_TOOL.name == "roll_damage"
        assert "damage_dice" in [p.name for p in ROLL_DAMAGE_TOOL.parameters]

    def test_get_npc_attitude_tool_defined(self):
        """get_npc_attitude tool should be properly defined."""
        from src.agents.tools.gm_tools import GET_NPC_ATTITUDE_TOOL

        assert GET_NPC_ATTITUDE_TOOL.name == "get_npc_attitude"
        assert "from_entity" in [p.name for p in GET_NPC_ATTITUDE_TOOL.parameters]

    def test_update_npc_attitude_tool_defined(self):
        """update_npc_attitude tool should be properly defined."""
        from src.agents.tools.gm_tools import UPDATE_NPC_ATTITUDE_TOOL

        assert UPDATE_NPC_ATTITUDE_TOOL.name == "update_npc_attitude"
        assert "delta" in [p.name for p in UPDATE_NPC_ATTITUDE_TOOL.parameters]

    def test_gm_tools_list(self):
        """GM_TOOLS should contain all tools."""
        from src.agents.tools.gm_tools import GM_TOOLS

        assert len(GM_TOOLS) >= 5
        names = [t.name for t in GM_TOOLS]
        assert "skill_check" in names
        assert "attack_roll" in names
        assert "roll_damage" in names
        assert "get_npc_attitude" in names
        assert "update_npc_attitude" in names


class TestToolExecutor:
    """Test GMToolExecutor execution."""

    def test_execute_skill_check(self, db_session: Session, game_session: GameSession):
        """Execute skill_check tool."""
        from src.agents.tools.executor import GMToolExecutor

        executor = GMToolExecutor(db_session, game_session)

        with patch('src.agents.tools.executor.make_skill_check') as mock_check:
            mock_check.return_value = MagicMock(
                success=True,
                roll_result=MagicMock(total=18, individual_rolls=(15,)),
                margin=3,
                is_critical_success=False,
                is_critical_failure=False,
            )

            result = executor.execute("skill_check", {
                "dc": 15,
                "skill_name": "stealth",
                "attribute_modifier": 2,
            })

        assert result["success"] is True
        assert result["roll"] == 18
        assert "stealth" in result["description"].lower()

    def test_execute_attack_roll_hit(self, db_session: Session, game_session: GameSession):
        """Execute attack_roll tool that hits."""
        from src.agents.tools.executor import GMToolExecutor

        executor = GMToolExecutor(db_session, game_session)

        with patch('src.agents.tools.executor.make_attack_roll') as mock_attack:
            mock_attack.return_value = MagicMock(
                hit=True,
                is_critical_hit=False,
                roll_result=MagicMock(total=18, individual_rolls=(15,)),
            )

            result = executor.execute("attack_roll", {
                "target_ac": 15,
                "attack_bonus": 3,
            })

        assert result["hit"] is True
        assert result["roll"] == 18

    def test_execute_attack_roll_miss(self, db_session: Session, game_session: GameSession):
        """Execute attack_roll tool that misses."""
        from src.agents.tools.executor import GMToolExecutor

        executor = GMToolExecutor(db_session, game_session)

        with patch('src.agents.tools.executor.make_attack_roll') as mock_attack:
            mock_attack.return_value = MagicMock(
                hit=False,
                is_critical_hit=False,
                roll_result=MagicMock(total=10, individual_rolls=(7,)),
            )

            result = executor.execute("attack_roll", {
                "target_ac": 15,
                "attack_bonus": 3,
            })

        assert result["hit"] is False

    def test_execute_roll_damage(self, db_session: Session, game_session: GameSession):
        """Execute roll_damage tool."""
        from src.agents.tools.executor import GMToolExecutor

        executor = GMToolExecutor(db_session, game_session)

        with patch('src.agents.tools.executor.roll_damage') as mock_damage:
            mock_damage.return_value = MagicMock(
                roll_result=MagicMock(total=8, individual_rolls=(5, 3)),
                damage_type="slashing",
                is_critical=False,
            )

            result = executor.execute("roll_damage", {
                "damage_dice": "2d6",
                "damage_type": "slashing",
                "bonus": 2,
            })

        assert result["total"] == 8
        assert result["damage_type"] == "slashing"

    def test_execute_get_npc_attitude(self, db_session: Session, game_session: GameSession):
        """Execute get_npc_attitude tool."""
        from src.agents.tools.executor import GMToolExecutor

        npc = create_entity(db_session, game_session, entity_type=EntityType.NPC,
                           entity_key="bartender")
        player = create_entity(db_session, game_session, entity_type=EntityType.PLAYER,
                              entity_key="hero")
        create_relationship(db_session, game_session, npc, player,
                          trust=60, liking=70, respect=50)

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("get_npc_attitude", {
            "from_entity": "bartender",
            "to_entity": "hero",
        })

        assert result["trust"] == 60
        assert result["liking"] == 70
        assert result["respect"] == 50

    def test_execute_update_npc_attitude(self, db_session: Session, game_session: GameSession):
        """Execute update_npc_attitude tool."""
        from src.agents.tools.executor import GMToolExecutor

        npc = create_entity(db_session, game_session, entity_type=EntityType.NPC,
                           entity_key="bartender")
        player = create_entity(db_session, game_session, entity_type=EntityType.PLAYER,
                              entity_key="hero")
        rel = create_relationship(db_session, game_session, npc, player,
                                 trust=50, liking=50, familiarity=50)

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("update_npc_attitude", {
            "from_entity": "bartender",
            "to_entity": "hero",
            "dimension": "trust",
            "delta": 10,
            "reason": "Player helped fix the bar",
        })

        assert result["new_value"] == 60
        assert result["delta"] == 10

    def test_execute_unknown_tool_raises(self, db_session: Session, game_session: GameSession):
        """Unknown tool should raise ValueError."""
        from src.agents.tools.executor import GMToolExecutor

        executor = GMToolExecutor(db_session, game_session)

        with pytest.raises(ValueError, match="Unknown tool"):
            executor.execute("unknown_tool", {})


class TestToolSchemas:
    """Test tool JSON schema generation."""

    def test_skill_check_to_json_schema(self):
        """Tool should generate valid JSON schema."""
        from src.agents.tools.gm_tools import SKILL_CHECK_TOOL

        schema = SKILL_CHECK_TOOL.to_json_schema()

        assert "properties" in schema
        assert "dc" in schema["properties"]
        assert schema["properties"]["dc"]["type"] == "integer"

    def test_attack_roll_to_anthropic_format(self):
        """Tool should convert to Anthropic format."""
        from src.agents.tools.gm_tools import ATTACK_ROLL_TOOL

        anthropic_tool = ATTACK_ROLL_TOOL.to_anthropic_format()

        assert anthropic_tool["name"] == "attack_roll"
        assert "input_schema" in anthropic_tool
