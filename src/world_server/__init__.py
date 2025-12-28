"""World Server - Background world simulation with anticipatory generation.

This module provides:
- AnticipationEngine: Pre-generates scenes for predicted player destinations
- PreGenerationCache: LRU cache for pre-generated scenes
- LocationPredictor: Predicts likely next player locations
- StateCollapseManager: Commits pre-generated state when player observes
- SceneGenerator: Generates scene data for anticipated locations

The key insight is that player reading time (48-120 seconds) approximately
matches LLM generation time (50-80 seconds), allowing us to hide latency
by pre-generating likely destinations in the background.
"""

from src.world_server.schemas import (
    AnticipationTask,
    GenerationStatus,
    LocationPrediction,
    PreGeneratedScene,
)
from src.world_server.cache import PreGenerationCache
from src.world_server.predictor import LocationPredictor
from src.world_server.anticipation import AnticipationEngine
from src.world_server.collapse import StateCollapseManager
from src.world_server.integration import (
    WorldServerManager,
    get_world_server_manager,
    shutdown_world_server,
)
from src.world_server.scene_generator import (
    SceneGenerator,
    create_scene_generator_callback,
)

__all__ = [
    # Schemas
    "AnticipationTask",
    "GenerationStatus",
    "LocationPrediction",
    "PreGeneratedScene",
    # Components
    "PreGenerationCache",
    "LocationPredictor",
    "AnticipationEngine",
    "StateCollapseManager",
    "SceneGenerator",
    # Integration
    "WorldServerManager",
    "get_world_server_manager",
    "shutdown_world_server",
    "create_scene_generator_callback",
]
