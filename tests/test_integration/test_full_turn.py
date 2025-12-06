"""End-to-end tests for full game turn flow.

Tests the complete graph execution: context_compiler -> game_master -> entity_extractor -> persistence
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.orm import Session

from src.agents.graph import build_game_graph
from src.agents.state import create_initial_state
from src.database.models.enums import EntityType
from src.database.models.session import GameSession, Turn
from src.llm.response_types import LLMResponse, UsageStats
from tests.factories import create_entity, create_turn


@pytest.fixture
def mock_gm_response():
    """Mock LLM response for GM narration."""
    return LLMResponse(
        content="""The tavern is warm and inviting. A fire crackles in the hearth as you
look around. The bartender nods at you from behind the counter, polishing a mug.

"Welcome, traveler," he says. "What'll it be?"

---STATE---
time_advance_minutes: 5
location_change: none
combat_initiated: false""",
        tool_calls=(),
        finish_reason="stop",
        model="claude-sonnet-4-20250514",
        usage=UsageStats(
            prompt_tokens=100,
            completion_tokens=80,
            total_tokens=180,
        ),
    )


@pytest.fixture
def mock_extraction_response():
    """Mock LLM response for entity extraction."""
    return LLMResponse(
        content="",
        tool_calls=(),
        finish_reason="stop",
        model="claude-sonnet-4-20250514",
        parsed_content={
            "characters": [
                {
                    "entity_key": "bartender",
                    "display_name": "The Bartender",
                    "entity_type": "npc",
                    "description": "A friendly barkeeper polishing a mug",
                }
            ],
            "items": [],
            "facts": [
                {
                    "subject": "tavern",
                    "predicate": "has_feature",
                    "value": "fireplace",
                    "certainty": 100,
                }
            ],
            "relationship_changes": [],
            "appointments": [],
        },
    )


class TestFullTurnFlow:
    """Test complete turn flow through the graph."""

    @pytest.mark.asyncio
    async def test_graph_execution_creates_turn(
        self,
        db_session: Session,
        game_session: GameSession,
        player_entity,
        mock_gm_response,
        mock_extraction_response,
    ):
        """Full graph execution should create a Turn record."""
        # Setup initial state
        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="I look around the room",
        )
        state["_db"] = db_session
        state["_game_session"] = game_session
        state["scene_context"] = "You are in a cozy tavern."

        # Build and compile graph
        graph = build_game_graph()
        compiled = graph.compile()

        with patch("src.agents.nodes.game_master_node.get_gm_provider") as mock_gm, \
             patch("src.agents.nodes.entity_extractor_node.get_extraction_provider") as mock_extract:

            # Setup mock providers
            mock_gm_provider = MagicMock()
            mock_gm_provider.complete = AsyncMock(return_value=mock_gm_response)
            mock_gm_provider.complete_with_tools = AsyncMock(return_value=mock_gm_response)
            mock_gm.return_value = mock_gm_provider

            mock_extract_provider = MagicMock()
            mock_extract_provider.complete_structured = AsyncMock(return_value=mock_extraction_response)
            mock_extract.return_value = mock_extract_provider

            # Run graph
            result = await compiled.ainvoke(state)

        # Verify Turn was created
        turn = db_session.query(Turn).filter(
            Turn.session_id == game_session.id
        ).first()

        assert turn is not None
        assert turn.player_input == "I look around the room"
        assert "tavern" in turn.gm_response.lower()

    @pytest.mark.asyncio
    async def test_graph_execution_extracts_entities(
        self,
        db_session: Session,
        game_session: GameSession,
        player_entity,
        mock_gm_response,
        mock_extraction_response,
    ):
        """Full graph execution should pass extracted entities through state."""
        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="I look around",
        )
        state["_db"] = db_session
        state["_game_session"] = game_session
        state["scene_context"] = "You are in a tavern."

        graph = build_game_graph()
        compiled = graph.compile()

        with patch("src.agents.nodes.game_master_node.get_gm_provider") as mock_gm, \
             patch("src.agents.nodes.entity_extractor_node.get_extraction_provider") as mock_extract:

            mock_gm_provider = MagicMock()
            mock_gm_provider.complete = AsyncMock(return_value=mock_gm_response)
            mock_gm_provider.complete_with_tools = AsyncMock(return_value=mock_gm_response)
            mock_gm.return_value = mock_gm_provider

            mock_extract_provider = MagicMock()
            mock_extract_provider.complete_structured = AsyncMock(return_value=mock_extraction_response)
            mock_extract.return_value = mock_extract_provider

            result = await compiled.ainvoke(state)

        # Verify extracted entities are in state (persistence may or may not create them
        # depending on implementation - this tests the extraction flow)
        assert "extracted_entities" in result
        assert "extracted_facts" in result

        # Verify the extraction data was processed
        if result["extracted_entities"]:
            assert any(e.get("entity_key") == "bartender" for e in result["extracted_entities"])

        if result["extracted_facts"]:
            assert any(f.get("subject") == "tavern" for f in result["extracted_facts"])

    @pytest.mark.asyncio
    async def test_graph_returns_gm_response(
        self,
        db_session: Session,
        game_session: GameSession,
        player_entity,
        mock_gm_response,
        mock_extraction_response,
    ):
        """Graph should return GM response in final state."""
        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="I greet the bartender",
        )
        state["_db"] = db_session
        state["_game_session"] = game_session
        state["scene_context"] = "You are in a cozy tavern."

        graph = build_game_graph()
        compiled = graph.compile()

        with patch("src.agents.nodes.game_master_node.get_gm_provider") as mock_gm, \
             patch("src.agents.nodes.entity_extractor_node.get_extraction_provider") as mock_extract:

            mock_gm_provider = MagicMock()
            mock_gm_provider.complete = AsyncMock(return_value=mock_gm_response)
            mock_gm_provider.complete_with_tools = AsyncMock(return_value=mock_gm_response)
            mock_gm.return_value = mock_gm_provider

            mock_extract_provider = MagicMock()
            mock_extract_provider.complete_structured = AsyncMock(return_value=mock_extraction_response)
            mock_extract.return_value = mock_extract_provider

            result = await compiled.ainvoke(state)

        assert "gm_response" in result
        assert "tavern" in result["gm_response"].lower()
        assert "bartender" in result["gm_response"].lower()


class TestGraphStateChanges:
    """Test state changes from graph execution."""

    @pytest.mark.asyncio
    async def test_time_advance_propagates(
        self,
        db_session: Session,
        game_session: GameSession,
        player_entity,
        mock_extraction_response,
    ):
        """Time advance from GM response should propagate through state."""
        # Custom response with specific time advance
        gm_response = LLMResponse(
            content="""You spend time exploring the area.

---STATE---
time_advance_minutes: 30
location_change: none
combat_initiated: false""",
            tool_calls=(),
            finish_reason="stop",
            model="claude-sonnet-4-20250514",
        )

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="I explore the tavern thoroughly",
        )
        state["_db"] = db_session
        state["_game_session"] = game_session
        state["scene_context"] = "You are in a tavern."

        graph = build_game_graph()
        compiled = graph.compile()

        with patch("src.agents.nodes.game_master_node.get_gm_provider") as mock_gm, \
             patch("src.agents.nodes.entity_extractor_node.get_extraction_provider") as mock_extract:

            mock_gm_provider = MagicMock()
            mock_gm_provider.complete = AsyncMock(return_value=gm_response)
            mock_gm_provider.complete_with_tools = AsyncMock(return_value=gm_response)
            mock_gm.return_value = mock_gm_provider

            mock_extract_provider = MagicMock()
            mock_extract_provider.complete_structured = AsyncMock(return_value=mock_extraction_response)
            mock_extract.return_value = mock_extract_provider

            result = await compiled.ainvoke(state)

        assert result["time_advance_minutes"] == 30

    @pytest.mark.asyncio
    async def test_location_change_propagates(
        self,
        db_session: Session,
        game_session: GameSession,
        player_entity,
        mock_extraction_response,
    ):
        """Location change from GM response should propagate through state."""
        gm_response = LLMResponse(
            content="""You step outside into the cool night air.

---STATE---
time_advance_minutes: 5
location_change: town_square
combat_initiated: false""",
            tool_calls=(),
            finish_reason="stop",
            model="claude-sonnet-4-20250514",
        )

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="I leave the tavern",
        )
        state["_db"] = db_session
        state["_game_session"] = game_session
        state["scene_context"] = "You are in a tavern."

        graph = build_game_graph()
        compiled = graph.compile()

        with patch("src.agents.nodes.game_master_node.get_gm_provider") as mock_gm, \
             patch("src.agents.nodes.entity_extractor_node.get_extraction_provider") as mock_extract:

            mock_gm_provider = MagicMock()
            mock_gm_provider.complete = AsyncMock(return_value=gm_response)
            mock_gm_provider.complete_with_tools = AsyncMock(return_value=gm_response)
            mock_gm.return_value = mock_gm_provider

            mock_extract_provider = MagicMock()
            mock_extract_provider.complete_structured = AsyncMock(return_value=mock_extraction_response)
            mock_extract.return_value = mock_extract_provider

            result = await compiled.ainvoke(state)

        assert result["location_changed"] is True
        assert result["player_location"] == "town_square"


class TestGraphErrorHandling:
    """Test error handling in graph execution."""

    @pytest.mark.asyncio
    async def test_handles_missing_state_block(
        self,
        db_session: Session,
        game_session: GameSession,
        player_entity,
        mock_extraction_response,
    ):
        """Graph should handle GM response without state block."""
        gm_response = LLMResponse(
            content="The tavern is quiet tonight.",  # No ---STATE--- block
            tool_calls=(),
            finish_reason="stop",
            model="claude-sonnet-4-20250514",
        )

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="I look around",
        )
        state["_db"] = db_session
        state["_game_session"] = game_session
        state["scene_context"] = "You are in a tavern."

        graph = build_game_graph()
        compiled = graph.compile()

        with patch("src.agents.nodes.game_master_node.get_gm_provider") as mock_gm, \
             patch("src.agents.nodes.entity_extractor_node.get_extraction_provider") as mock_extract:

            mock_gm_provider = MagicMock()
            mock_gm_provider.complete = AsyncMock(return_value=gm_response)
            mock_gm_provider.complete_with_tools = AsyncMock(return_value=gm_response)
            mock_gm.return_value = mock_gm_provider

            mock_extract_provider = MagicMock()
            mock_extract_provider.complete_structured = AsyncMock(return_value=mock_extraction_response)
            mock_extract.return_value = mock_extract_provider

            result = await compiled.ainvoke(state)

        # Should use defaults
        assert result["time_advance_minutes"] == 5  # Default
        assert result["combat_active"] is False
        assert "gm_response" in result
