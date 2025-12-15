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


class TestTurnPersistence:
    """Test turn persistence including extracted entities."""

    @pytest.mark.asyncio
    async def test_entities_extracted_persisted_on_turn_record(
        self,
        db_session: Session,
        game_session: GameSession,
        player_entity,
        mock_gm_response,
        mock_extraction_response,
    ):
        """Turn record should have entities_extracted populated after graph execution.

        Regression test for bug where persistence_node.py didn't set entities_extracted
        when creating new Turn records, only when updating existing ones.
        """
        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="I look around the room",
        )
        state["_db"] = db_session
        state["_game_session"] = game_session
        state["scene_context"] = "You are in a cozy tavern."
        state["turn_number"] = game_session.total_turns + 1

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

        # Commit and refresh to ensure we're reading persisted data
        db_session.commit()

        # Query for the turn record
        turn = db_session.query(Turn).filter(
            Turn.session_id == game_session.id,
        ).order_by(Turn.turn_number.desc()).first()

        assert turn is not None, "Turn record should exist after graph execution"

        # THIS IS THE KEY ASSERTION - entities_extracted should NOT be None
        assert turn.entities_extracted is not None, (
            "Turn.entities_extracted should be populated after graph execution, "
            "not None. This was a regression where persistence_node only set "
            "entities_extracted when updating existing turns, not when creating new ones."
        )

        # It should be a list (possibly empty if no entities extracted)
        assert isinstance(turn.entities_extracted, list), (
            "Turn.entities_extracted should be a list"
        )


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


class TestToolStateManagement:
    """Test that tool calls properly propagate state updates."""

    @pytest.mark.asyncio
    async def test_advance_time_tool_propagates_to_state(
        self,
        db_session: Session,
        game_session: GameSession,
        player_entity,
    ):
        """When GM calls advance_time tool, state should reflect time_advance_minutes.

        This tests the new tool-based state management that replaces STATE block parsing.
        """
        from src.llm.response_types import ToolCall

        # Create a mock response that includes an advance_time tool call
        gm_response_with_tool = LLMResponse(
            content="You spend some time exploring the area.",
            tool_calls=(
                ToolCall(
                    id="tool_1",
                    name="advance_time",
                    arguments={"minutes": 45, "reason": "exploring"},
                ),
            ),
            finish_reason="tool_use",
            model="claude-sonnet-4-20250514",
        )

        # Final response after tool execution
        gm_response_final = LLMResponse(
            content="After exploring for a while, you feel you know the area better.",
            tool_calls=(),
            finish_reason="stop",
            model="claude-sonnet-4-20250514",
        )

        mock_extraction_response = LLMResponse(
            content="",
            tool_calls=(),
            finish_reason="stop",
            model="claude-sonnet-4-20250514",
            parsed_content={
                "characters": [],
                "items": [],
                "facts": [],
                "relationship_changes": [],
                "appointments": [],
            },
        )

        # Create TimeState so advance_time can update it
        from src.database.models.world import TimeState
        time_state = TimeState(
            session_id=game_session.id,
            current_day=1,
            current_time="10:00",
        )
        db_session.add(time_state)
        db_session.flush()

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
            # First call returns tool use, second returns final response
            mock_gm_provider.complete_with_tools = AsyncMock(
                side_effect=[gm_response_with_tool, gm_response_final]
            )
            mock_gm.return_value = mock_gm_provider

            mock_extract_provider = MagicMock()
            mock_extract_provider.complete_structured = AsyncMock(return_value=mock_extraction_response)
            mock_extract.return_value = mock_extract_provider

            result = await compiled.ainvoke(state)

        # The key assertion: tool-based time advance should be in state
        assert result["time_advance_minutes"] == 45, (
            "Tool-based advance_time(minutes=45) should propagate to state. "
            "This tests the pending_state_updates mechanism."
        )

    @pytest.mark.asyncio
    async def test_entity_move_tool_propagates_to_state(
        self,
        db_session: Session,
        game_session: GameSession,
        player_entity,
    ):
        """When GM calls entity_move tool for player, state should reflect location change.

        This tests that tool-based location changes take precedence over STATE block.
        """
        from src.llm.response_types import ToolCall
        from src.database.models.world import Location

        # Create destination location
        location = Location(
            session_id=game_session.id,
            location_key="village_square",
            display_name="Village Square",
            description="The central square of the village.",
        )
        db_session.add(location)
        db_session.flush()

        # Create a mock response that includes an entity_move tool call
        # Note: The fixture uses entity_key="player_hero", but entity_move checks for "player"
        # So we need to create a player entity with the correct key
        from src.database.models.entities import Entity
        from src.database.models.enums import EntityType

        # The player_entity fixture uses "player_hero", so create one with "player" key
        player = Entity(
            session_id=game_session.id,
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.add(player)
        db_session.flush()

        gm_response_with_tool = LLMResponse(
            content="You head outside to the village square.",
            tool_calls=(
                ToolCall(
                    id="tool_1",
                    name="entity_move",
                    arguments={
                        "entity_key": "player",
                        "location_key": "village_square",
                    },
                ),
            ),
            finish_reason="tool_use",
            model="claude-sonnet-4-20250514",
        )

        gm_response_final = LLMResponse(
            content="The village square bustles with activity.",
            tool_calls=(),
            finish_reason="stop",
            model="claude-sonnet-4-20250514",
        )

        mock_extraction_response = LLMResponse(
            content="",
            tool_calls=(),
            finish_reason="stop",
            model="claude-sonnet-4-20250514",
            parsed_content={
                "characters": [],
                "items": [],
                "facts": [],
                "relationship_changes": [],
                "appointments": [],
            },
        )

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="inn_common_room",
            player_input="I go to the village square",
        )
        state["_db"] = db_session
        state["_game_session"] = game_session
        state["scene_context"] = "You are in the inn common room."

        graph = build_game_graph()
        compiled = graph.compile()

        with patch("src.agents.nodes.game_master_node.get_gm_provider") as mock_gm, \
             patch("src.agents.nodes.entity_extractor_node.get_extraction_provider") as mock_extract:

            mock_gm_provider = MagicMock()
            mock_gm_provider.complete_with_tools = AsyncMock(
                side_effect=[gm_response_with_tool, gm_response_final]
            )
            mock_gm.return_value = mock_gm_provider

            mock_extract_provider = MagicMock()
            mock_extract_provider.complete_structured = AsyncMock(return_value=mock_extraction_response)
            mock_extract.return_value = mock_extract_provider

            result = await compiled.ainvoke(state)

        # The key assertions: tool-based location change should be in state
        assert result["location_changed"] is True, (
            "Tool-based entity_move should set location_changed=True"
        )
        assert result["player_location"] == "village_square", (
            "Tool-based entity_move should update player_location"
        )
