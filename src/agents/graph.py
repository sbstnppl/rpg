"""LangGraph StateGraph builder for RPG game orchestration.

This module defines the game's agent graph structure and routing logic.
The graph flows through: context_compiler -> game_master -> [routing] -> persistence.
"""

from typing import Literal

from langgraph.graph import END, StateGraph

from src.agents.state import GameState


# Routing threshold for triggering world simulation
TIME_THRESHOLD_MINUTES = 30


def route_after_gm(state: GameState) -> Literal[
    "combat_resolver", "entity_extractor", "world_simulator"
]:
    """Determine next agent based on GameMaster response analysis.

    Routing priority:
    1. Combat (if combat_active is True)
    2. World simulation (if location changed or significant time passed)
    3. Entity extraction (default)

    Args:
        state: Current game state.

    Returns:
        Name of next agent to route to.
    """
    # Combat takes highest priority
    if state.get("combat_active", False):
        return "combat_resolver"

    # World simulation for location changes or significant time passage
    if state.get("location_changed", False):
        return "world_simulator"
    if state.get("time_advance_minutes", 0) >= TIME_THRESHOLD_MINUTES:
        return "world_simulator"

    # Default: extract entities from response
    return "entity_extractor"


def route_after_world_sim(state: GameState) -> Literal["entity_extractor"]:
    """Route after world simulation - always goes to entity extractor.

    Args:
        state: Current game state.

    Returns:
        Always returns "entity_extractor".
    """
    return "entity_extractor"


def route_after_combat(state: GameState) -> Literal["entity_extractor", "game_master"]:
    """Route after combat resolution.

    Args:
        state: Current game state.

    Returns:
        Next agent - back to GM if combat continues, else to extractor.
    """
    # If combat is still active, return to GM for next round narration
    if state.get("combat_active", False):
        return "game_master"
    return "entity_extractor"


# Import actual node implementations
from src.agents.nodes.context_compiler_node import context_compiler_node
from src.agents.nodes.game_master_node import game_master_node
from src.agents.nodes.entity_extractor_node import entity_extractor_node
from src.agents.nodes.npc_generator_node import npc_generator_node
from src.agents.nodes.persistence_node import persistence_node
from src.agents.nodes.world_simulator_node import world_simulator_node
from src.agents.nodes.combat_resolver_node import combat_resolver_node


# Map of agent names to node functions
AGENT_NODES = {
    "context_compiler": context_compiler_node,
    "game_master": game_master_node,
    "entity_extractor": entity_extractor_node,
    "npc_generator": npc_generator_node,
    "combat_resolver": combat_resolver_node,
    "world_simulator": world_simulator_node,
    "persistence": persistence_node,
}


def build_game_graph() -> StateGraph:
    """Build the game orchestration graph.

    Graph structure:
        START
          |
          v
        context_compiler
          |
          v
        game_master
          |
          v
        [route_after_gm]
         /     |      \\
        v      v       v
    combat  entity   world
    resolver extractor simulator
        |      |       |
        |      v       |
        |  npc_generator
        |      |       |
        v      v       v
        [converge at persistence]
          |
          v
        END

    Returns:
        Configured StateGraph ready to compile.
    """
    # Create graph with GameState schema
    graph = StateGraph(GameState)

    # Add all agent nodes
    for name, func in AGENT_NODES.items():
        graph.add_node(name, func)

    # Set entry point
    graph.set_entry_point("context_compiler")

    # Define edges
    # context_compiler -> game_master
    graph.add_edge("context_compiler", "game_master")

    # game_master -> conditional routing
    graph.add_conditional_edges(
        "game_master",
        route_after_gm,
        {
            "combat_resolver": "combat_resolver",
            "entity_extractor": "entity_extractor",
            "world_simulator": "world_simulator",
        },
    )

    # combat_resolver -> conditional (back to GM or to extractor)
    graph.add_conditional_edges(
        "combat_resolver",
        route_after_combat,
        {
            "game_master": "game_master",
            "entity_extractor": "entity_extractor",
        },
    )

    # world_simulator -> entity_extractor
    graph.add_edge("world_simulator", "entity_extractor")

    # entity_extractor -> npc_generator
    graph.add_edge("entity_extractor", "npc_generator")

    # npc_generator -> persistence
    graph.add_edge("npc_generator", "persistence")

    # persistence -> END
    graph.add_edge("persistence", END)

    return graph
