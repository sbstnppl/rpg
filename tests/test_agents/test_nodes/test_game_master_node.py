"""Tests for game_master_node."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.state import create_initial_state, GameState
from src.agents.nodes.game_master_node import (
    game_master_node,
    create_game_master_node,
    parse_state_block,
)
from src.llm.response_types import LLMResponse, UsageStats, ToolCall


@pytest.fixture
def mock_llm_response():
    """Create a mock LLM response."""
    return LLMResponse(
        content="""You step into the dimly lit tavern. The smell of ale and woodsmoke fills your nostrils.

A burly bartender looks up from wiping the counter. "Welcome, stranger. What'll it be?"

---STATE---
time_advance_minutes: 2
location_change: none
combat_initiated: false""",
        tool_calls=(),
        parsed_content=None,
        finish_reason="stop",
        usage=UsageStats(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        ),
    )


class TestParseStateBlock:
    """Test the state block parser."""

    def test_parses_time_advance(self):
        """Should extract time_advance_minutes."""
        text = """Some narrative...

---STATE---
time_advance_minutes: 15
location_change: none
combat_initiated: false"""

        result = parse_state_block(text)
        assert result["time_advance_minutes"] == 15

    def test_parses_location_change(self):
        """Should extract location_change."""
        text = """Narrative here.

---STATE---
time_advance_minutes: 5
location_change: market_square
combat_initiated: false"""

        result = parse_state_block(text)
        assert result["location_change"] == "market_square"
        assert result["location_changed"] is True

    def test_parses_combat_initiated(self):
        """Should extract combat_initiated."""
        text = """Combat description!

---STATE---
time_advance_minutes: 0
location_change: none
combat_initiated: true"""

        result = parse_state_block(text)
        assert result["combat_active"] is True

    def test_handles_missing_state_block(self):
        """Should return defaults if no state block."""
        text = "Just a narrative without state block."

        result = parse_state_block(text)
        assert result["time_advance_minutes"] == 5  # Default
        assert result["location_changed"] is False

    def test_extracts_narrative_without_state_block(self):
        """Should extract narrative portion."""
        text = """The narrative content here.

---STATE---
time_advance_minutes: 3
location_change: none
combat_initiated: false"""

        narrative, _ = parse_state_block(text, return_narrative=True)
        assert narrative.strip() == "The narrative content here."


class TestGameMasterNodeFactory:
    """Test the node factory function."""

    def test_factory_creates_callable(self, db_session, game_session):
        """Factory should return an async callable."""
        node = create_game_master_node(db_session, game_session)
        assert callable(node)


class TestGameMasterNode:
    """Test the game_master_node function."""

    @pytest.mark.asyncio
    async def test_calls_llm_provider(
        self, db_session, game_session, player_entity, mock_llm_response
    ):
        """Should call LLM provider with scene context."""
        node = create_game_master_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Look around",
        )
        state["scene_context"] = "## Current Scene\nYou are in a tavern."

        with patch(
            "src.agents.nodes.game_master_node.get_gm_provider"
        ) as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.complete = AsyncMock(return_value=mock_llm_response)
            mock_get_provider.return_value = mock_provider

            result = await node(state)

            mock_provider.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_gm_response(
        self, db_session, game_session, player_entity, mock_llm_response
    ):
        """Should return gm_response in state."""
        node = create_game_master_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Enter the tavern",
        )
        state["scene_context"] = "Scene context here."

        with patch(
            "src.agents.nodes.game_master_node.get_gm_provider"
        ) as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.complete = AsyncMock(return_value=mock_llm_response)
            mock_get_provider.return_value = mock_provider

            result = await node(state)

            assert "gm_response" in result
            assert "tavern" in result["gm_response"].lower()

    @pytest.mark.asyncio
    async def test_parses_state_changes(
        self, db_session, game_session, player_entity, mock_llm_response
    ):
        """Should parse state changes from response."""
        node = create_game_master_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Look around",
        )
        state["scene_context"] = "Scene context here."

        with patch(
            "src.agents.nodes.game_master_node.get_gm_provider"
        ) as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.complete = AsyncMock(return_value=mock_llm_response)
            mock_get_provider.return_value = mock_provider

            result = await node(state)

            assert result["time_advance_minutes"] == 2


class TestGameMasterNodeWithDefaultFunction:
    """Test the default game_master_node when db/session in state."""

    @pytest.mark.asyncio
    async def test_default_node_extracts_from_state(
        self, db_session, game_session, player_entity, mock_llm_response
    ):
        """Default node should work with db/game_session in state."""
        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Hello",
        )
        state["scene_context"] = "Scene here."
        state["_db"] = db_session
        state["_game_session"] = game_session

        with patch(
            "src.agents.nodes.game_master_node.get_gm_provider"
        ) as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.complete = AsyncMock(return_value=mock_llm_response)
            mock_provider.complete_with_tools = AsyncMock(return_value=mock_llm_response)
            mock_get_provider.return_value = mock_provider

            result = await game_master_node(state)

            assert "gm_response" in result


class TestGameMasterNodeWithToolCalls:
    """Test GM node with multi-round tool calling."""

    @pytest.mark.asyncio
    async def test_accumulates_narrative_across_tool_rounds(
        self, db_session, game_session, player_entity
    ):
        """Narrative from tool-calling round should be preserved.

        When LLM returns narrative + tool call in one response, then
        only STATE block after the tool result, the narrative should
        still be included in the final response.
        """
        # First response: narrative + tool call
        first_response = LLMResponse(
            content='"Greetings!" you call out warmly. The villager smiles.',
            tool_calls=(
                ToolCall(
                    id="tool_123",
                    name="satisfy_need",
                    arguments={
                        "entity_key": "player",
                        "need_name": "social_connection",
                        "action_type": "chat",
                        "quality": "good",
                    },
                ),
            ),
            finish_reason="tool_use",
            usage=UsageStats(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        )

        # Second response: only STATE block (narrative already written)
        second_response = LLMResponse(
            content="""---STATE---
time_advance_minutes: 3
location_change: none
combat_initiated: false""",
            tool_calls=(),
            finish_reason="end_turn",
            usage=UsageStats(prompt_tokens=200, completion_tokens=20, total_tokens=220),
        )

        state = {
            "session_id": game_session.id,
            "player_id": player_entity.id,
            "player_location": "village",
            "player_input": "Greet the villager",
            "scene_context": "You are in a village square.",
            "_db": db_session,
            "_game_session": game_session,
        }

        with patch(
            "src.agents.nodes.game_master_node.get_gm_provider"
        ) as mock_get_provider:
            mock_provider = MagicMock()
            # Return first_response, then second_response
            mock_provider.complete_with_tools = AsyncMock(
                side_effect=[first_response, second_response]
            )
            mock_get_provider.return_value = mock_provider

            result = await game_master_node(state)

            # Narrative from first response should be preserved
            assert "gm_response" in result
            assert "Greetings" in result["gm_response"]
            assert "villager smiles" in result["gm_response"]
            # Should not have empty response error
            assert "errors" not in result or not any(
                "empty response" in err for err in result.get("errors", [])
            )
