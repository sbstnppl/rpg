"""Tests for persistence_node."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from src.agents.state import create_initial_state, GameState
from src.agents.nodes.persistence_node import (
    persistence_node,
    create_persistence_node,
)


@pytest.fixture
def state_with_extractions(db_session, game_session, player_entity):
    """Create state with extraction results."""
    state = create_initial_state(
        session_id=game_session.id,
        player_id=player_entity.id,
        player_location="tavern",
        player_input="Talk to the bartender",
    )
    state["gm_response"] = "You approach the friendly bartender, Bob."
    state["extracted_entities"] = [
        {
            "entity_key": "bartender_bob",
            "display_name": "Bob",
            "entity_type": "npc",
            "description": "A friendly bartender",
        }
    ]
    state["extracted_facts"] = [
        {
            "subject": "bartender_bob",
            "predicate": "occupation",
            "value": "bartender",
        }
    ]
    state["relationship_changes"] = [
        {
            "entity_key": "bartender_bob",
            "dimension": "familiarity",
            "change": 5,
            "reason": "First meeting",
        }
    ]
    return state


class TestPersistenceNodeFactory:
    """Test the node factory function."""

    def test_factory_creates_callable(self, db_session, game_session):
        """Factory should return an async callable."""
        node = create_persistence_node(db_session, game_session)
        assert callable(node)


class TestPersistenceNode:
    """Test the persistence_node function."""

    @pytest.mark.asyncio
    async def test_persists_extracted_entities(
        self, db_session, game_session, player_entity, state_with_extractions
    ):
        """Should call EntityManager for extracted entities."""
        node = create_persistence_node(db_session, game_session)

        with patch(
            "src.agents.nodes.persistence_node.EntityManager"
        ) as MockEntityManager:
            mock_manager = MagicMock()
            # get_entity returns None so entity doesn't exist
            mock_manager.get_entity.return_value = None
            mock_manager.create_entity.return_value = MagicMock(id=100)
            MockEntityManager.return_value = mock_manager

            await node(state_with_extractions)

            # Should have called create_entity since entity doesn't exist
            mock_manager.create_entity.assert_called()

    @pytest.mark.asyncio
    async def test_persists_extracted_facts(
        self, db_session, game_session, player_entity, state_with_extractions
    ):
        """Should call FactManager for extracted facts."""
        node = create_persistence_node(db_session, game_session)

        with patch(
            "src.agents.nodes.persistence_node.FactManager"
        ) as MockFactManager:
            mock_manager = MagicMock()
            MockFactManager.return_value = mock_manager

            await node(state_with_extractions)

            mock_manager.record_fact.assert_called()

    @pytest.mark.asyncio
    async def test_returns_empty_update(
        self, db_session, game_session, player_entity
    ):
        """Should return minimal state update."""
        node = create_persistence_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Look around",
        )
        state["gm_response"] = "You see nothing special."

        result = await node(state)

        # Should not add errors for empty extractions
        assert "errors" not in result or len(result.get("errors", [])) == 0

    @pytest.mark.asyncio
    async def test_handles_empty_extractions(
        self, db_session, game_session, player_entity
    ):
        """Should handle state with no extractions gracefully."""
        node = create_persistence_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Look around",
        )

        result = await node(state)

        # Should complete without errors
        assert result is not None


class TestPersistenceNodeIntegration:
    """Integration tests with actual database."""

    @pytest.mark.asyncio
    async def test_creates_turn_record(
        self, db_session, game_session, player_entity
    ):
        """Should create Turn record in database."""
        from src.database.models.session import Turn

        node = create_persistence_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Test input",
        )
        state["gm_response"] = "Test response"

        initial_turn_count = (
            db_session.query(Turn)
            .filter(Turn.session_id == game_session.id)
            .count()
        )

        await node(state)

        new_turn_count = (
            db_session.query(Turn)
            .filter(Turn.session_id == game_session.id)
            .count()
        )

        assert new_turn_count == initial_turn_count + 1

    @pytest.mark.asyncio
    async def test_turn_contains_input_and_response(
        self, db_session, game_session, player_entity
    ):
        """Turn record should contain player input and GM response."""
        from src.database.models.session import Turn

        node = create_persistence_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Hello there!",
        )
        state["gm_response"] = "A voice echoes in the darkness."

        await node(state)

        turn = (
            db_session.query(Turn)
            .filter(Turn.session_id == game_session.id)
            .order_by(Turn.turn_number.desc())
            .first()
        )

        assert turn is not None
        assert turn.player_input == "Hello there!"
        assert turn.gm_response == "A voice echoes in the darkness."


class TestPersistenceNodeWithDefaultFunction:
    """Test the default persistence_node when db/session in state."""

    @pytest.mark.asyncio
    async def test_default_node_extracts_from_state(
        self, db_session, game_session, player_entity
    ):
        """Default node should work with db/game_session in state."""
        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Look around",
        )
        state["gm_response"] = "You see a cozy tavern."
        state["_db"] = db_session
        state["_game_session"] = game_session

        result = await persistence_node(state)

        # Should complete without errors
        assert result is not None
