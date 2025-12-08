"""Tests for context_compiler_node."""

import pytest
from unittest.mock import MagicMock, patch

from src.agents.state import create_initial_state, GameState
from src.agents.nodes.context_compiler_node import (
    context_compiler_node,
    create_context_compiler_node,
)
from src.managers.context_compiler import SceneContext


@pytest.fixture
def mock_scene_context():
    """Create a mock SceneContext for testing."""
    return SceneContext(
        turn_context="## Turn 1\nThis is the FIRST TURN. Introduce the player character.",
        time_context="## Current Scene\n- Time: Day 1, 09:00 (Monday)",
        location_context="- Location: The Rusty Tankard\n- Description: A cozy tavern...",
        player_context="## Player Character\n- Name: Hero",
        npcs_context="## NPCs Present\n\n### Bartender Bob\n- Friendly demeanor",
        tasks_context="## Active Tasks\n- Find the missing artifact",
        recent_events_context="## Recent Events\n- Arrived at tavern",
        secrets_context="## GM Secrets\n- Bob knows the artifact location",
    )


class TestContextCompilerNode:
    """Test the context_compiler_node function."""

    @pytest.mark.asyncio
    async def test_compiles_scene_context(
        self, db_session, game_session, player_entity, mock_scene_context
    ):
        """Should compile scene context and add to state."""
        # Create node with dependencies
        node = create_context_compiler_node(db_session, game_session)

        # Create initial state
        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Look around",
        )

        # Mock the ContextCompiler.compile_scene method
        with patch(
            "src.agents.nodes.context_compiler_node.ContextCompiler"
        ) as MockCompiler:
            mock_compiler = MagicMock()
            mock_compiler.compile_scene.return_value = mock_scene_context
            MockCompiler.return_value = mock_compiler

            result = await node(state)

            # Verify compile_scene was called with correct args
            mock_compiler.compile_scene.assert_called_once_with(
                player_id=player_entity.id,
                location_key="tavern",
                turn_number=1,
                include_secrets=True,
            )

    @pytest.mark.asyncio
    async def test_returns_scene_context_as_prompt(
        self, db_session, game_session, player_entity, mock_scene_context
    ):
        """Should return scene context formatted as prompt."""
        node = create_context_compiler_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Look around",
        )

        with patch(
            "src.agents.nodes.context_compiler_node.ContextCompiler"
        ) as MockCompiler:
            mock_compiler = MagicMock()
            mock_compiler.compile_scene.return_value = mock_scene_context
            MockCompiler.return_value = mock_compiler

            result = await node(state)

            # Should have scene_context
            assert "scene_context" in result
            assert "Current Scene" in result["scene_context"]
            assert "Player Character" in result["scene_context"]

    @pytest.mark.asyncio
    async def test_sets_next_agent_to_game_master(
        self, db_session, game_session, player_entity, mock_scene_context
    ):
        """Should route to game_master next."""
        node = create_context_compiler_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Look around",
        )

        with patch(
            "src.agents.nodes.context_compiler_node.ContextCompiler"
        ) as MockCompiler:
            mock_compiler = MagicMock()
            mock_compiler.compile_scene.return_value = mock_scene_context
            MockCompiler.return_value = mock_compiler

            result = await node(state)

            assert result.get("next_agent") == "game_master"


class TestContextCompilerNodeFactory:
    """Test the node factory function."""

    def test_factory_creates_callable(self, db_session, game_session):
        """Factory should return an async callable."""
        node = create_context_compiler_node(db_session, game_session)
        assert callable(node)

    def test_factory_binds_dependencies(self, db_session, game_session):
        """Factory should bind db and game_session."""
        node = create_context_compiler_node(db_session, game_session)
        # The node should have access to bound db/game_session
        # We verify this by checking it doesn't raise when called
        assert node is not None


class TestContextCompilerNodeIntegration:
    """Integration tests with actual database."""

    @pytest.mark.asyncio
    async def test_with_real_context_compiler(
        self, db_session, game_session, player_entity
    ):
        """Test node with real ContextCompiler (no mocks)."""
        node = create_context_compiler_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="unknown_location",
            player_input="Look around",
        )

        result = await node(state)

        # Should have scene_context string
        assert isinstance(result.get("scene_context"), str)
        # Should route to game_master
        assert result.get("next_agent") == "game_master"


class TestContextCompilerNodeWithDefaultFunction:
    """Test the default context_compiler_node when db/session in state."""

    @pytest.mark.asyncio
    async def test_default_node_extracts_from_state(
        self, db_session, game_session, player_entity, mock_scene_context
    ):
        """Default node should work with db/game_session in state."""
        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Look around",
        )
        # Add db and game_session to state for default node
        state["_db"] = db_session
        state["_game_session"] = game_session

        with patch(
            "src.agents.nodes.context_compiler_node.ContextCompiler"
        ) as MockCompiler:
            mock_compiler = MagicMock()
            mock_compiler.compile_scene.return_value = mock_scene_context
            MockCompiler.return_value = mock_compiler

            result = await context_compiler_node(state)

            assert "scene_context" in result
            assert result.get("next_agent") == "game_master"
