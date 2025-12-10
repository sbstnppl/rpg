"""Pydantic schemas for LLM structured output."""

from src.agents.schemas.extraction import (
    CharacterExtraction,
    ItemExtraction,
    FactExtraction,
    RelationshipChange,
    AppointmentExtraction,
    ExtractionResult,
)
from src.agents.schemas.goals import (
    GoalType,
    GoalPriority,
    GoalStatus,
    NPCGoal,
    GoalCreation,
    GoalUpdate,
    GoalStepResult,
)
from src.agents.schemas.npc_state import (
    # Sub-components
    NPCAppearance,
    NPCBackground,
    NPCPersonality,
    NPCPreferences,
    NPCNeeds,
    NPCCurrentState,
    AttractionScore,
    EnvironmentalReaction,
    ImmediateGoal,
    # Main schemas
    NPCFullState,
    NPCReactions,
    # Scene context
    VisibleItem,
    PlayerSummary,
    SceneContext,
    # Constraints
    NPCConstraints,
)
from src.agents.schemas.gm_response import (
    # GM Response components
    NPCAction,
    ItemChange,
    RelationshipChange as GMRelationshipChange,
    FactRevealed,
    Stimulus,
    # GM Response main schemas
    GMManifest,
    GMState,
    GMResponse,
)

__all__ = [
    # Extraction schemas
    "CharacterExtraction",
    "ItemExtraction",
    "FactExtraction",
    "RelationshipChange",
    "AppointmentExtraction",
    "ExtractionResult",
    # Goal schemas
    "GoalType",
    "GoalPriority",
    "GoalStatus",
    "NPCGoal",
    "GoalCreation",
    "GoalUpdate",
    "GoalStepResult",
    # NPC State sub-components
    "NPCAppearance",
    "NPCBackground",
    "NPCPersonality",
    "NPCPreferences",
    "NPCNeeds",
    "NPCCurrentState",
    "AttractionScore",
    "EnvironmentalReaction",
    "ImmediateGoal",
    # NPC State main schemas
    "NPCFullState",
    "NPCReactions",
    # Scene context schemas
    "VisibleItem",
    "PlayerSummary",
    "SceneContext",
    # NPC creation constraints
    "NPCConstraints",
    # GM Response schemas
    "NPCAction",
    "ItemChange",
    "GMRelationshipChange",
    "FactRevealed",
    "Stimulus",
    "GMManifest",
    "GMState",
    "GMResponse",
]
