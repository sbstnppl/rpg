"""LangGraph StateGraph builder for RPG game orchestration.

This module defines two game pipelines:

1. **Legacy Flow** (build_game_graph):
   context_compiler → game_master → [routing] → persistence
   - LLM decides what happens AND narrates it
   - Requires post-hoc entity extraction
   - Risk of state/narrative drift

2. **System-Authority Flow** (build_system_authority_graph):
   context_compiler → parse_intent → validate_actions → complication_oracle
   → execute_actions → narrator → persistence
   - System decides what happens (mechanically)
   - LLM only describes outcomes
   - Guaranteed consistency, no drift

The System-Authority flow is the preferred approach for new games.
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

# System-Authority pipeline nodes
from src.agents.nodes.parse_intent_node import parse_intent_node
from src.agents.nodes.validate_actions_node import validate_actions_node
from src.agents.nodes.dynamic_planner_node import dynamic_planner_node
from src.agents.nodes.complication_oracle_node import complication_oracle_node
from src.agents.nodes.execute_actions_node import execute_actions_node
from src.agents.nodes.state_validator_node import state_validator_node
from src.agents.nodes.narrator_node import narrator_node


# Map of agent names to node functions (legacy flow)
AGENT_NODES = {
    "context_compiler": context_compiler_node,
    "game_master": game_master_node,
    "entity_extractor": entity_extractor_node,
    "npc_generator": npc_generator_node,
    "combat_resolver": combat_resolver_node,
    "world_simulator": world_simulator_node,
    "persistence": persistence_node,
}

# System-Authority pipeline nodes
SYSTEM_AUTHORITY_NODES = {
    "context_compiler": context_compiler_node,
    "parse_intent": parse_intent_node,
    "validate_actions": validate_actions_node,
    "dynamic_planner": dynamic_planner_node,
    "complication_oracle": complication_oracle_node,
    "execute_actions": execute_actions_node,
    "state_validator": state_validator_node,
    "narrator": narrator_node,
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


def build_system_authority_graph() -> StateGraph:
    """Build the System-Authority game orchestration graph.

    This is the new pipeline that ensures mechanical consistency:
    - System decides what happens (mechanically)
    - Dynamic planner transforms CUSTOM actions into structured plans
    - Oracle adds creative complications (without breaking mechanics)
    - State validator ensures data integrity after execution
    - LLM describes it (narratively)

    Graph structure:
        START
          |
          v
        context_compiler (gather scene context)
          |
          v
        parse_intent (convert input to actions)
          |
          v
        validate_actions (check if actions are possible)
          |
          v
        dynamic_planner (transform CUSTOM actions into execution plans)
          |
          v
        complication_oracle (optionally add narrative complications)
          |
          v
        execute_actions (apply mechanical changes)
          |
          v
        state_validator (ensure data integrity, auto-fix issues)
          |
          v
        narrator (generate prose from facts)
          |
          v
        persistence (save state changes)
          |
          v
        END

    Returns:
        Configured StateGraph ready to compile.
    """
    # Create graph with GameState schema
    graph = StateGraph(GameState)

    # Add all nodes
    for name, func in SYSTEM_AUTHORITY_NODES.items():
        graph.add_node(name, func)

    # Set entry point
    graph.set_entry_point("context_compiler")

    # Define linear flow
    graph.add_edge("context_compiler", "parse_intent")
    graph.add_edge("parse_intent", "validate_actions")
    graph.add_edge("validate_actions", "dynamic_planner")
    graph.add_edge("dynamic_planner", "complication_oracle")
    graph.add_edge("complication_oracle", "execute_actions")
    graph.add_edge("execute_actions", "state_validator")
    graph.add_edge("state_validator", "narrator")
    graph.add_edge("narrator", "persistence")
    graph.add_edge("persistence", END)

    return graph
