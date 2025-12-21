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
from src.agents.nodes.subturn_processor_node import subturn_processor_node
from src.agents.nodes.state_validator_node import state_validator_node
from src.agents.nodes.info_formatter_node import info_formatter_node
from src.agents.nodes.narrator_node import narrator_node
from src.agents.nodes.narrative_validator_node import narrative_validator_node

# Scene-First Architecture nodes - imported lazily below to avoid circular imports


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
    "subturn_processor": subturn_processor_node,  # Replaces validate->planner->oracle->execute
    "state_validator": state_validator_node,
    "info_formatter": info_formatter_node,
    "narrator": narrator_node,
    "narrative_validator": narrative_validator_node,
    "persistence": persistence_node,
}

# Legacy nodes kept for reference/fallback (not used in main flow)
LEGACY_SYSTEM_AUTHORITY_NODES = {
    "validate_actions": validate_actions_node,
    "dynamic_planner": dynamic_planner_node,
    "complication_oracle": complication_oracle_node,
    "execute_actions": execute_actions_node,
}


def route_by_response_mode(
    state: GameState,
) -> Literal["info_formatter", "narrator"]:
    """Route based on response mode after state validation.

    INFO mode skips the narrator for concise factual answers.
    NARRATE mode goes through the full narrator pipeline.

    Args:
        state: Current game state with response_mode.

    Returns:
        "info_formatter" for INFO mode, "narrator" otherwise.
    """
    # Scene requests always go to narrator
    if state.get("is_scene_request"):
        return "narrator"

    mode = state.get("response_mode", "narrate")
    if mode == "info":
        return "info_formatter"
    return "narrator"


def route_after_narrative_validator(
    state: GameState,
) -> Literal["narrator", "persistence"]:
    """Route after narrative validation.

    If validation failed and retries remain, go back to narrator.
    Otherwise, proceed to persistence.

    Args:
        state: Current game state.

    Returns:
        "narrator" if re-narration needed, "persistence" otherwise.
    """
    if state.get("_route_to_narrator"):
        return "narrator"
    return "persistence"


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
    - Subturn processor handles multi-action chains with state updates
    - Complications are checked between subturns (can interrupt chains)
    - State validator ensures data integrity after execution
    - LLM describes it (narratively)

    Graph structure:
        START
          |
          v
        context_compiler (gather scene context)
          |
          v
        parse_intent (convert input to actions, handle continuations)
          |
          v
        subturn_processor (validate/execute actions with interrupts)
          |
          v
        state_validator (ensure data integrity, auto-fix issues)
          |
          v
        [route by response mode]
         /        \\
        v          v
    info_formatter narrator
        |          |
        |          v
        |    narrative_validator
        |         /     \\
        |        v       v
        |    narrator   persistence
        |    (retry)       |
        \\                  |
         \\________________/
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

    # Define simplified linear flow with subturn_processor
    graph.add_edge("context_compiler", "parse_intent")
    graph.add_edge("parse_intent", "subturn_processor")
    graph.add_edge("subturn_processor", "state_validator")

    # Route based on response mode: INFO skips narrator, NARRATE uses narrator
    graph.add_conditional_edges(
        "state_validator",
        route_by_response_mode,
        {
            "info_formatter": "info_formatter",
            "narrator": "narrator",
        },
    )

    # Info formatter goes directly to persistence (skip narrative validation)
    graph.add_edge("info_formatter", "persistence")

    # Narrator goes through narrative_validator
    graph.add_edge("narrator", "narrative_validator")

    # Narrative validator conditionally routes back to narrator or to persistence
    graph.add_conditional_edges(
        "narrative_validator",
        route_after_narrative_validator,
        {
            "narrator": "narrator",
            "persistence": "persistence",
        },
    )

    graph.add_edge("persistence", END)

    return graph


def _get_scene_first_nodes():
    """Get scene-first nodes with lazy imports to avoid circular imports."""
    from src.agents.nodes.world_mechanics_node import world_mechanics_node
    from src.agents.nodes.scene_builder_node import scene_builder_node
    from src.agents.nodes.persist_scene_node import persist_scene_node
    from src.agents.nodes.resolve_references_node import resolve_references_node
    from src.agents.nodes.constrained_narrator_node import constrained_narrator_node
    from src.agents.nodes.validate_narrator_node import validate_narrator_node

    return {
        "context_compiler": context_compiler_node,
        "parse_intent": parse_intent_node,
        "world_mechanics": world_mechanics_node,
        "scene_builder": scene_builder_node,
        "persist_scene": persist_scene_node,
        "resolve_references": resolve_references_node,
        "subturn_processor": subturn_processor_node,
        "state_validator": state_validator_node,
        "constrained_narrator": constrained_narrator_node,
        "validate_narrator": validate_narrator_node,
        "persistence": persistence_node,
    }


# Lazy-loaded node map (populated on first access)
SCENE_FIRST_NODES: dict = {}


def route_after_parse_scene_first(
    state: GameState,
) -> Literal["world_mechanics", "resolve_references", "constrained_narrator"]:
    """Route after parsing - determine if scene needs building.

    If parser detected ambiguity, route to narrator for clarification.
    If player just entered a location, route to world_mechanics to build scene.
    Otherwise, route directly to resolve_references for action processing.

    Args:
        state: Current game state.

    Returns:
        "constrained_narrator" for clarification,
        "world_mechanics" for location changes,
        "resolve_references" otherwise.
    """
    # If parser detected clarification needed (e.g., ambiguous pronouns),
    # route directly to narrator to ask for clarification
    if state.get("needs_clarification"):
        return "constrained_narrator"

    # Scene requests always need world mechanics
    if state.get("is_scene_request"):
        return "world_mechanics"

    # Location changes need scene building
    if state.get("location_changed") or state.get("just_entered_location"):
        return "world_mechanics"

    # If no narrator_manifest exists, we need to build the scene first
    # This handles first turn at a location or fresh games
    if state.get("narrator_manifest") is None:
        return "world_mechanics"

    # LOOK actions always need fresh scene context
    parsed_actions = state.get("parsed_actions") or []
    for action in parsed_actions:
        if action.get("type", "").upper() == "LOOK":
            return "world_mechanics"

    # Other actions need reference resolution
    if parsed_actions:
        return "resolve_references"

    # Default to world mechanics for scene description
    return "world_mechanics"


def route_after_resolve(
    state: GameState,
) -> Literal["subturn_processor", "constrained_narrator"]:
    """Route after reference resolution.

    If clarification is needed, route to narrator for clarification prompt.
    Otherwise, route to subturn processor for action execution.

    Args:
        state: Current game state.

    Returns:
        "constrained_narrator" for clarification, "subturn_processor" otherwise.
    """
    if state.get("needs_clarification"):
        return "constrained_narrator"

    # Check if there are resolved actions to execute
    resolved_actions = state.get("resolved_actions") or []
    if resolved_actions:
        return "subturn_processor"

    # No actions - go to narrator for scene description
    return "constrained_narrator"


def route_after_validate_narrator(
    state: GameState,
) -> Literal["constrained_narrator", "persistence"]:
    """Route after narrator validation.

    If validation failed and retries remain, go back to narrator.
    Otherwise, proceed to persistence.

    Args:
        state: Current game state.

    Returns:
        "constrained_narrator" if re-narration needed, "persistence" otherwise.
    """
    if state.get("_route_to_narrator"):
        return "constrained_narrator"
    return "persistence"


def build_scene_first_graph() -> StateGraph:
    """Build the Scene-First game orchestration graph.

    This is the new pipeline that builds the world BEFORE narrating:
    - World Mechanics determines what exists (NPCs, events)
    - Scene Builder generates/loads scene contents
    - Persistence stores everything to DB
    - Reference Resolution matches player targets to entities
    - Constrained Narrator describes only what exists
    - Validation ensures narrator followed rules

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
        [route_after_parse]
         /              \\
        v                v
    world_mechanics    resolve_references
        |                    |
        v              [route_after_resolve]
    scene_builder       /        \\
        |              v          v
        v         subturn_    constrained_
    persist_scene processor   narrator
        |              |           |
        v              v           v
    resolve_refs  state_validator  |
        |              |           |
        v              v           |
    [rejoin] → constrained_narrator
                       |
                       v
                validate_narrator
                   /      \\
                  v        v
          constrained_  persistence
          narrator        |
          (retry)         v
                        END

    Returns:
        Configured StateGraph ready to compile.
    """
    # Create graph with GameState schema
    graph = StateGraph(GameState)

    # Get nodes (lazy import to avoid circular imports)
    nodes = _get_scene_first_nodes()

    # Add all nodes
    for name, func in nodes.items():
        graph.add_node(name, func)

    # Set entry point
    graph.set_entry_point("context_compiler")

    # Initial flow: context → parse
    graph.add_edge("context_compiler", "parse_intent")

    # After parse: route based on whether we need to build scene or ask clarification
    graph.add_conditional_edges(
        "parse_intent",
        route_after_parse_scene_first,
        {
            "world_mechanics": "world_mechanics",
            "resolve_references": "resolve_references",
            "constrained_narrator": "constrained_narrator",
        },
    )

    # Scene building flow: world_mechanics → scene_builder → persist_scene → resolve
    graph.add_edge("world_mechanics", "scene_builder")
    graph.add_edge("scene_builder", "persist_scene")
    graph.add_edge("persist_scene", "resolve_references")

    # After reference resolution: route based on clarification needs
    graph.add_conditional_edges(
        "resolve_references",
        route_after_resolve,
        {
            "subturn_processor": "subturn_processor",
            "constrained_narrator": "constrained_narrator",
        },
    )

    # Action execution flow: subturn → state_validator → narrator
    graph.add_edge("subturn_processor", "state_validator")
    graph.add_edge("state_validator", "constrained_narrator")

    # Narrator → validation
    graph.add_edge("constrained_narrator", "validate_narrator")

    # Validation routes back to narrator or to persistence
    graph.add_conditional_edges(
        "validate_narrator",
        route_after_validate_narrator,
        {
            "constrained_narrator": "constrained_narrator",
            "persistence": "persistence",
        },
    )

    graph.add_edge("persistence", END)

    return graph
