"""Tests for world_simulator_node."""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import asdict

from src.agents.state import create_initial_state, GameState
from src.agents.nodes.world_simulator_node import (
    world_simulator_node,
    create_world_simulator_node,
)
from src.agents.world_simulator import SimulationResult, NPCMovement


@pytest.fixture
def mock_simulation_result():
    """Create a mock SimulationResult for testing."""
    return SimulationResult(
        hours_simulated=1.0,
        npc_movements=[
            NPCMovement(
                npc_id=1,
                npc_name="Bob",
                from_location="tavern",
                to_location="market",
                reason="Schedule",
            )
        ],
        needs_updated=[1, 2],
        mood_modifiers_expired=2,
    )


class TestWorldSimulatorNodeFactory:
    """Test the node factory function."""

    def test_factory_creates_callable(self, db_session, game_session):
        """Factory should return an async callable."""
        node = create_world_simulator_node(db_session, game_session)
        assert callable(node)


class TestWorldSimulatorNode:
    """Test the world_simulator_node function."""

    @pytest.mark.asyncio
    async def test_simulates_time_passage(
        self, db_session, game_session, player_entity, mock_simulation_result
    ):
        """Should call WorldSimulator.simulate_time_passage."""
        node = create_world_simulator_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Wait for an hour",
        )
        state["time_advance_minutes"] = 60

        with patch(
            "src.agents.nodes.world_simulator_node.WorldSimulator"
        ) as MockSimulator:
            mock_sim = MagicMock()
            mock_sim.simulate_time_passage.return_value = mock_simulation_result
            MockSimulator.return_value = mock_sim

            result = await node(state)

            # Should have called simulate_time_passage
            mock_sim.simulate_time_passage.assert_called_once()
            call_args = mock_sim.simulate_time_passage.call_args
            assert call_args[1]["hours"] == 1.0  # 60 minutes = 1 hour

    @pytest.mark.asyncio
    async def test_returns_simulation_result(
        self, db_session, game_session, player_entity, mock_simulation_result
    ):
        """Should return simulation result in state."""
        node = create_world_simulator_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Wait",
        )
        state["time_advance_minutes"] = 30

        with patch(
            "src.agents.nodes.world_simulator_node.WorldSimulator"
        ) as MockSimulator:
            mock_sim = MagicMock()
            mock_sim.simulate_time_passage.return_value = mock_simulation_result
            MockSimulator.return_value = mock_sim

            result = await node(state)

            assert "simulation_result" in result
            assert result["simulation_result"]["hours_simulated"] == 1.0

    @pytest.mark.asyncio
    async def test_handles_zero_time_advance(
        self, db_session, game_session, player_entity
    ):
        """Should handle zero time advance gracefully."""
        node = create_world_simulator_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Look around",
        )
        state["time_advance_minutes"] = 0

        result = await node(state)

        # Should skip simulation for zero time
        assert result.get("simulation_result") is None or result == {}

    @pytest.mark.asyncio
    async def test_handles_location_change(
        self, db_session, game_session, player_entity, mock_simulation_result
    ):
        """Should simulate on location change even with minimal time."""
        node = create_world_simulator_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="market",
            player_input="Go to market",
        )
        state["location_changed"] = True
        state["previous_location"] = "tavern"
        state["time_advance_minutes"] = 5  # Minimal travel time

        with patch(
            "src.agents.nodes.world_simulator_node.WorldSimulator"
        ) as MockSimulator:
            mock_sim = MagicMock()
            mock_sim.simulate_time_passage.return_value = mock_simulation_result
            MockSimulator.return_value = mock_sim

            result = await node(state)

            # Should still simulate even with minimal time
            mock_sim.simulate_time_passage.assert_called_once()


class TestWorldSimulatorNodeIntegration:
    """Integration tests with actual WorldSimulator."""

    @pytest.mark.asyncio
    async def test_with_real_simulator(
        self, db_session, game_session, player_entity
    ):
        """Test node with real WorldSimulator (no mocks)."""
        node = create_world_simulator_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Wait for a bit",
        )
        state["time_advance_minutes"] = 30

        result = await node(state)

        # Should return simulation result dict
        assert "simulation_result" in result
        assert isinstance(result["simulation_result"], dict)


class TestWorldSimulatorNodeWithDefaultFunction:
    """Test the default world_simulator_node when db/session in state."""

    @pytest.mark.asyncio
    async def test_default_node_extracts_from_state(
        self, db_session, game_session, player_entity, mock_simulation_result
    ):
        """Default node should work with db/game_session in state."""
        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Wait",
        )
        state["time_advance_minutes"] = 60
        state["_db"] = db_session
        state["_game_session"] = game_session

        with patch(
            "src.agents.nodes.world_simulator_node.WorldSimulator"
        ) as MockSimulator:
            mock_sim = MagicMock()
            mock_sim.simulate_time_passage.return_value = mock_simulation_result
            MockSimulator.return_value = mock_sim

            result = await world_simulator_node(state)

            assert "simulation_result" in result
