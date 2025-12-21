"""World module for Scene-First Architecture.

This module contains components for simulating and building the game world:
- schemas: Pydantic models for world state
- constraints: Realistic constraint checking
- world_mechanics: World simulation engine (Phase 2)
- scene_builder: Scene generation (Phase 3)
- scene_persister: Database persistence (Phase 4)
"""

from src.world.schemas import (
    # Enums
    PresenceReason,
    ObservationLevel,
    ItemVisibility,
    NarrationType,
    # World Mechanics
    NPCSpec,
    NPCPlacement,
    NPCMovement,
    NewElement,
    WorldEvent,
    FactUpdate,
    WorldUpdate,
    # Scene Builder
    FurnitureSpec,
    ItemSpec,
    Atmosphere,
    SceneContents,
    SceneNPC,
    SceneManifest,
    # Narrator
    EntityRef,
    NarratorManifest,
    NarrationContext,
    NarrationResult,
    # Validation
    InvalidReference,
    UnkeyedReference,
    ValidationResult,
    # Resolution
    ResolutionResult,
    # Constraints
    SocialLimits,
    ConstraintResult,
    # Persistence
    PersistedNPC,
    PersistedItem,
    PersistedWorldUpdate,
    PersistedScene,
)

from src.world.constraints import (
    RealisticConstraintChecker,
)

__all__ = [
    # Enums
    "PresenceReason",
    "ObservationLevel",
    "ItemVisibility",
    "NarrationType",
    # World Mechanics
    "NPCSpec",
    "NPCPlacement",
    "NPCMovement",
    "NewElement",
    "WorldEvent",
    "FactUpdate",
    "WorldUpdate",
    # Scene Builder
    "FurnitureSpec",
    "ItemSpec",
    "Atmosphere",
    "SceneContents",
    "SceneNPC",
    "SceneManifest",
    # Narrator
    "EntityRef",
    "NarratorManifest",
    "NarrationContext",
    "NarrationResult",
    # Validation
    "InvalidReference",
    "UnkeyedReference",
    "ValidationResult",
    # Resolution
    "ResolutionResult",
    # Constraints
    "SocialLimits",
    "ConstraintResult",
    "RealisticConstraintChecker",
    # Persistence
    "PersistedNPC",
    "PersistedItem",
    "PersistedWorldUpdate",
    "PersistedScene",
]
