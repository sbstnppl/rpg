"""Tests for entity_extractor_node."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.state import create_initial_state, GameState
from src.agents.nodes.entity_extractor_node import (
    entity_extractor_node,
    create_entity_extractor_node,
)
from src.agents.schemas.extraction import ExtractionResult, CharacterExtraction
from src.llm.response_types import LLMResponse, UsageStats


@pytest.fixture
def mock_extraction_result():
    """Create a mock extraction result."""
    return ExtractionResult(
        characters=[
            CharacterExtraction(
                entity_key="bartender_bob",
                display_name="Bob",
                entity_type="npc",
                description="A burly man with a friendly smile",
                current_activity="Wiping the counter",
            )
        ],
        items=[],
        facts=[],
        relationship_changes=[],
        appointments=[],
        time_advance_minutes=5,
        location_change=None,
    )


@pytest.fixture
def mock_llm_response(mock_extraction_result):
    """Create a mock LLM response with parsed content."""
    return LLMResponse(
        content="",
        tool_calls=(),
        parsed_content=mock_extraction_result,
        finish_reason="stop",
        usage=UsageStats(
            prompt_tokens=200,
            completion_tokens=100,
            total_tokens=300,
        ),
    )


class TestEntityExtractorNodeFactory:
    """Test the node factory function."""

    def test_factory_creates_callable(self, db_session, game_session):
        """Factory should return an async callable."""
        node = create_entity_extractor_node(db_session, game_session)
        assert callable(node)


class TestEntityExtractorNode:
    """Test the entity_extractor_node function."""

    @pytest.mark.asyncio
    async def test_calls_llm_with_structured_output(
        self, db_session, game_session, player_entity, mock_llm_response
    ):
        """Should call LLM with structured output schema."""
        node = create_entity_extractor_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Talk to the bartender",
        )
        state["gm_response"] = "The bartender Bob greets you warmly."

        with patch(
            "src.agents.nodes.entity_extractor_node.get_extraction_provider"
        ) as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.complete_structured = AsyncMock(
                return_value=mock_llm_response
            )
            mock_get_provider.return_value = mock_provider

            result = await node(state)

            mock_provider.complete_structured.assert_called_once()

    @pytest.mark.asyncio
    async def test_extracts_characters(
        self, db_session, game_session, player_entity, mock_llm_response
    ):
        """Should extract characters from GM response."""
        node = create_entity_extractor_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Look around",
        )
        state["gm_response"] = "Bob the bartender waves at you."

        with patch(
            "src.agents.nodes.entity_extractor_node.get_extraction_provider"
        ) as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.complete_structured = AsyncMock(
                return_value=mock_llm_response
            )
            mock_get_provider.return_value = mock_provider

            result = await node(state)

            assert "extracted_entities" in result
            assert len(result["extracted_entities"]) == 1
            assert result["extracted_entities"][0]["entity_key"] == "bartender_bob"

    @pytest.mark.asyncio
    async def test_handles_empty_response(
        self, db_session, game_session, player_entity
    ):
        """Should handle state with no gm_response."""
        node = create_entity_extractor_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Look around",
        )
        # No gm_response set

        result = await node(state)

        # Should return empty extractions
        assert result.get("extracted_entities", []) == []

    @pytest.mark.asyncio
    async def test_sets_next_agent_to_persistence(
        self, db_session, game_session, player_entity, mock_llm_response
    ):
        """Should route to persistence node next."""
        node = create_entity_extractor_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Test",
        )
        state["gm_response"] = "A response."

        with patch(
            "src.agents.nodes.entity_extractor_node.get_extraction_provider"
        ) as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.complete_structured = AsyncMock(
                return_value=mock_llm_response
            )
            mock_get_provider.return_value = mock_provider

            result = await node(state)

            assert result.get("next_agent") == "persistence"


class TestEntityExtractorNodeWithDefaultFunction:
    """Test the default entity_extractor_node when db/session in state."""

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
        state["gm_response"] = "The bartender nods."
        state["_db"] = db_session
        state["_game_session"] = game_session

        with patch(
            "src.agents.nodes.entity_extractor_node.get_extraction_provider"
        ) as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.complete_structured = AsyncMock(
                return_value=mock_llm_response
            )
            mock_get_provider.return_value = mock_provider

            result = await entity_extractor_node(state)

            assert "extracted_entities" in result
