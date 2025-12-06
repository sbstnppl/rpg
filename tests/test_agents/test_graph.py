"""Tests for LangGraph StateGraph builder."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from langgraph.graph import StateGraph

from src.agents.state import GameState, create_initial_state
from src.agents.graph import (
    build_game_graph,
    route_after_gm,
    AGENT_NODES,
)


class TestRouteAfterGM:
    """Test routing logic after GameMaster node."""

    def test_routes_to_combat_when_combat_active(self):
        """Should route to combat_resolver when combat is active."""
        state = create_initial_state(
            session_id=1,
            player_id=10,
            player_location="tavern",
            player_input="Attack the goblin!",
        )
        state["combat_active"] = True

        result = route_after_gm(state)
        assert result == "combat_resolver"

    def test_routes_to_world_simulator_on_location_change(self):
        """Should route to world_simulator when location changed."""
        state = create_initial_state(
            session_id=1,
            player_id=10,
            player_location="market",
            player_input="Go to the market",
        )
        state["location_changed"] = True

        result = route_after_gm(state)
        assert result == "world_simulator"

    def test_routes_to_world_simulator_on_significant_time(self):
        """Should route to world_simulator when time advances significantly."""
        state = create_initial_state(
            session_id=1,
            player_id=10,
            player_location="tavern",
            player_input="Wait for an hour",
        )
        state["time_advance_minutes"] = 60

        result = route_after_gm(state)
        assert result == "world_simulator"

    def test_routes_to_entity_extractor_by_default(self):
        """Should route to entity_extractor by default."""
        state = create_initial_state(
            session_id=1,
            player_id=10,
            player_location="tavern",
            player_input="Look around",
        )

        result = route_after_gm(state)
        assert result == "entity_extractor"

    def test_combat_takes_priority_over_location_change(self):
        """Combat should take priority over location change."""
        state = create_initial_state(
            session_id=1,
            player_id=10,
            player_location="dungeon",
            player_input="Fight!",
        )
        state["combat_active"] = True
        state["location_changed"] = True

        result = route_after_gm(state)
        assert result == "combat_resolver"


class TestBuildGameGraph:
    """Test graph builder function."""

    def test_returns_state_graph(self):
        """Should return a StateGraph instance."""
        graph = build_game_graph()
        assert isinstance(graph, StateGraph)

    def test_graph_has_all_nodes(self):
        """Graph should have all required agent nodes."""
        graph = build_game_graph()
        # Access the underlying builder to check nodes
        # StateGraph.nodes contains the registered nodes
        node_names = set(graph.nodes.keys())

        expected_nodes = {
            "context_compiler",
            "game_master",
            "entity_extractor",
            "combat_resolver",
            "world_simulator",
            "persistence",
        }
        assert expected_nodes.issubset(node_names)


class TestAgentNodes:
    """Test that agent node functions are properly defined."""

    def test_agent_nodes_dict_exists(self):
        """AGENT_NODES should be a dict mapping names to functions."""
        assert isinstance(AGENT_NODES, dict)

    def test_all_nodes_are_callable(self):
        """All node functions should be callable."""
        for name, func in AGENT_NODES.items():
            assert callable(func), f"Node {name} is not callable"


class TestGraphCompilation:
    """Test graph compilation and execution."""

    @pytest.mark.asyncio
    async def test_graph_compiles(self):
        """Graph should compile without errors."""
        graph = build_game_graph()
        compiled = graph.compile()
        assert compiled is not None

    @pytest.mark.asyncio
    async def test_graph_has_entry_point(self):
        """Graph should start at context_compiler."""
        graph = build_game_graph()
        # The entry point should be set in the builder
        # We verify by checking if context_compiler is in the graph
        assert "context_compiler" in graph.nodes


class TestGraphWithMockedNodes:
    """Test graph execution with mocked node functions."""

    @pytest.mark.asyncio
    async def test_simple_flow_through_graph(self):
        """Test a simple flow: context -> gm -> extractor -> persistence."""
        # Create mocked node functions
        mock_context = AsyncMock(return_value={
            "scene_context": "A dark tavern...",
            "next_agent": "game_master",
        })
        mock_gm = AsyncMock(return_value={
            "gm_response": "You see a bartender.",
            "next_agent": "entity_extractor",
            "time_advance_minutes": 5,
            "location_changed": False,
            "combat_active": False,
        })
        mock_extractor = AsyncMock(return_value={
            "extracted_entities": [{"name": "Bartender"}],
            "next_agent": "persistence",
        })
        mock_persistence = AsyncMock(return_value={
            "next_agent": "end",
        })
        mock_combat = AsyncMock(return_value={})
        mock_world = AsyncMock(return_value={})

        # Patch the node functions
        with patch.dict("src.agents.graph.AGENT_NODES", {
            "context_compiler": mock_context,
            "game_master": mock_gm,
            "entity_extractor": mock_extractor,
            "persistence": mock_persistence,
            "combat_resolver": mock_combat,
            "world_simulator": mock_world,
        }):
            from src.agents.graph import build_game_graph

            graph = build_game_graph()
            compiled = graph.compile()

            initial_state = create_initial_state(
                session_id=1,
                player_id=10,
                player_location="tavern",
                player_input="Look around",
            )

            result = await compiled.ainvoke(initial_state)

            # Verify the flow happened
            mock_context.assert_called_once()
            mock_gm.assert_called_once()
            mock_extractor.assert_called_once()
            mock_persistence.assert_called_once()

            # Verify extraction accumulated
            assert "Bartender" in str(result.get("extracted_entities", []))
