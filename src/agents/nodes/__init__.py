"""Agent node functions for LangGraph orchestration.

Each node function takes GameState and returns a partial state update.
Node factories allow dependency injection of database sessions.
"""

from src.agents.nodes.context_compiler_node import (
    context_compiler_node,
    create_context_compiler_node,
)
from src.agents.nodes.entity_extractor_node import (
    entity_extractor_node,
    create_entity_extractor_node,
)
from src.agents.nodes.game_master_node import (
    game_master_node,
    create_game_master_node,
    parse_state_block,
)
from src.agents.nodes.persistence_node import (
    persistence_node,
    create_persistence_node,
)
from src.agents.nodes.world_simulator_node import (
    world_simulator_node,
    create_world_simulator_node,
)

__all__ = [
    "context_compiler_node",
    "create_context_compiler_node",
    "entity_extractor_node",
    "create_entity_extractor_node",
    "game_master_node",
    "create_game_master_node",
    "parse_state_block",
    "persistence_node",
    "create_persistence_node",
    "world_simulator_node",
    "create_world_simulator_node",
    # Scene-First Architecture (import lazily to avoid circular imports)
    "world_mechanics_node",
    "scene_builder_node",
    "persist_scene_node",
    "resolve_references_node",
    "constrained_narrator_node",
    "validate_narrator_node",
]


# Lazy imports for scene-first nodes to avoid circular imports
def __getattr__(name):
    """Lazy import of scene-first nodes."""
    if name == "world_mechanics_node":
        from src.agents.nodes.world_mechanics_node import world_mechanics_node
        return world_mechanics_node
    elif name == "scene_builder_node":
        from src.agents.nodes.scene_builder_node import scene_builder_node
        return scene_builder_node
    elif name == "persist_scene_node":
        from src.agents.nodes.persist_scene_node import persist_scene_node
        return persist_scene_node
    elif name == "resolve_references_node":
        from src.agents.nodes.resolve_references_node import resolve_references_node
        return resolve_references_node
    elif name == "constrained_narrator_node":
        from src.agents.nodes.constrained_narrator_node import constrained_narrator_node
        return constrained_narrator_node
    elif name == "validate_narrator_node":
        from src.agents.nodes.validate_narrator_node import validate_narrator_node
        return validate_narrator_node
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
