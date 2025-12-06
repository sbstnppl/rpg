"""Manager classes for game logic and state management."""

from src.managers.base import BaseManager
from src.managers.consistency import ConsistencyIssue, ConsistencyValidator, TemporalEffects
from src.managers.context_compiler import ContextCompiler, SceneContext
from src.managers.death import DeathManager, DeathSaveResult, RevivalResult
from src.managers.grief import GriefManager, GriefStageInfo
from src.managers.injuries import ActivityImpact, InjuryManager, InjuryRecoveryTime
from src.managers.needs import ActivityType, NeedDecayRates, NeedEffect, NeedsManager
from src.managers.relationship_manager import (
    PersonalityModifiers,
    RelationshipManager,
)

__all__ = [
    # Base
    "BaseManager",
    # Needs
    "NeedsManager",
    "NeedEffect",
    "NeedDecayRates",
    "ActivityType",
    # Injuries
    "InjuryManager",
    "ActivityImpact",
    "InjuryRecoveryTime",
    # Death
    "DeathManager",
    "DeathSaveResult",
    "RevivalResult",
    # Grief
    "GriefManager",
    "GriefStageInfo",
    # Relationships
    "RelationshipManager",
    "PersonalityModifiers",
    # Context
    "ContextCompiler",
    "SceneContext",
    # Consistency
    "ConsistencyValidator",
    "ConsistencyIssue",
    "TemporalEffects",
]
