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


class TestLocationBasedActivity:
    """Tests for location-based NPC activity inference."""

    def test_get_location_activities_returns_activities_for_known_category(self):
        """Should return activities for known location categories."""
        from src.schemas.settings import get_location_activities

        activities = get_location_activities("tavern")
        assert "socializing" in activities
        assert "resting" in activities

    def test_get_location_activities_returns_default_for_unknown_category(self):
        """Should return default activity for unknown categories."""
        from src.schemas.settings import get_location_activities

        activities = get_location_activities("unknown_category")
        assert activities == ["active"]

    def test_get_location_activities_returns_default_for_none(self):
        """Should return default activity for None category."""
        from src.schemas.settings import get_location_activities

        activities = get_location_activities(None)
        assert activities == ["active"]

    def test_world_simulator_uses_location_for_activity(
        self, db_session, game_session
    ):
        """WorldSimulator should infer activity from NPC location."""
        from tests.factories import create_entity, create_location, create_npc_extension

        from src.agents.world_simulator import WorldSimulator
        from src.database.models.enums import EntityType
        from src.managers.needs import ActivityType

        # Create NPC with extension pointing to a tavern
        npc = create_entity(
            db_session, game_session, entity_key="bartender", entity_type=EntityType.NPC
        )
        tavern = create_location(db_session, game_session, location_key="main_tavern")
        tavern.category = "tavern"
        db_session.flush()

        extension = create_npc_extension(db_session, npc)
        extension.current_location = "main_tavern"
        db_session.commit()

        simulator = WorldSimulator(db_session, game_session)

        # NPC at tavern should get SOCIALIZING activity
        activity = simulator._get_npc_activity_type(npc.id, 1.0)

        # Tavern primary activity is socializing
        assert activity == ActivityType.SOCIALIZING


class TestLocationChangeTracking:
    """Tests for location visit tracking and change detection."""

    def test_on_location_change_records_visit(
        self, db_session, game_session, player_entity
    ):
        """on_location_change should record visit to previous location."""
        from tests.factories import create_location

        from src.agents.world_simulator import WorldSimulator
        from src.database.models.world import LocationVisit

        # Create locations
        tavern = create_location(db_session, game_session, location_key="tavern")
        market = create_location(db_session, game_session, location_key="market")
        db_session.commit()

        simulator = WorldSimulator(db_session, game_session)

        # Move from tavern to market
        result = simulator.on_location_change(
            player_id=player_entity.id,
            from_location="tavern",
            to_location="market",
            travel_time_hours=0.0,
        )

        # Should have recorded visit to tavern
        visit = db_session.query(LocationVisit).filter(
            LocationVisit.session_id == game_session.id,
            LocationVisit.location_key == "tavern",
        ).first()
        assert visit is not None

    def test_check_location_changes_detects_first_visit(
        self, db_session, game_session, player_entity
    ):
        """First visit to a location should be flagged."""
        from tests.factories import create_location

        from src.agents.world_simulator import WorldSimulator

        # Create location
        tavern = create_location(db_session, game_session, location_key="tavern")
        db_session.commit()

        simulator = WorldSimulator(db_session, game_session)

        # Check changes for first visit
        changes = simulator._check_location_changes("tavern")

        assert changes["first_visit"] is True

    def test_check_location_changes_detects_npc_changes(
        self, db_session, game_session, player_entity
    ):
        """Should detect NPCs who arrived or left since last visit."""
        from tests.factories import create_entity, create_location, create_npc_extension

        from src.agents.world_simulator import WorldSimulator
        from src.database.models.enums import EntityType
        from src.database.models.world import LocationVisit

        # Create location and NPC
        tavern = create_location(db_session, game_session, location_key="tavern")
        bartender = create_entity(
            db_session, game_session,
            entity_key="bartender",
            entity_type=EntityType.NPC
        )
        extension = create_npc_extension(db_session, bartender)
        extension.current_location = "tavern"
        db_session.flush()

        # Create old visit record with no NPCs
        visit = LocationVisit(
            session_id=game_session.id,
            location_key="tavern",
            last_visit_turn=1,
            items_snapshot=[],
            npcs_snapshot=[],  # No NPCs before
        )
        db_session.add(visit)
        db_session.commit()

        simulator = WorldSimulator(db_session, game_session)
        changes = simulator._check_location_changes("tavern")

        # Bartender should be marked as arrived
        assert "bartender" in changes["npcs_arrived"]
        assert changes["first_visit"] is False
