"""Manager classes for game logic and state management."""

from src.managers.base import BaseManager
from src.managers.cliffhanger_manager import (
    CliffhangerManager,
    CliffhangerSuggestion,
    DramaticMoment,
    SceneTensionAnalysis,
)
from src.managers.conflict_manager import ConflictManager, ConflictStatus
from src.managers.consistency import ConsistencyIssue, ConsistencyValidator, TemporalEffects
from src.managers.context_compiler import ContextCompiler, SceneContext
from src.managers.death import DeathManager, DeathSaveResult, RevivalResult
from src.managers.entity_manager import EntityManager
from src.managers.event_manager import EventManager
from src.managers.fact_manager import FactManager
from src.managers.goal_manager import GoalManager
from src.managers.grief import GriefManager, GriefStageInfo
from src.managers.injuries import ActivityImpact, InjuryManager, InjuryRecoveryTime
from src.managers.item_manager import ItemManager
from src.managers.location_manager import LocationManager
from src.managers.memory_manager import MemoryManager
from src.managers.mystery_manager import MysteryManager, MysteryStatus
from src.managers.needs import ActivityType, NeedDecayRates, NeedEffect, NeedsManager
from src.managers.achievement_manager import (
    AchievementManager,
    AchievementProgress,
    AchievementUnlock,
)
from src.managers.progression_manager import (
    AdvancementResult,
    ProgressionManager,
    SkillProgress,
)
from src.managers.relationship_manager import (
    MilestoneInfo,
    PersonalityModifiers,
    RelationshipManager,
)
from src.managers.reputation_manager import (
    FactionStanding,
    ReputationChange,
    ReputationManager,
)
from src.managers.equipment_manager import (
    ArmorStats,
    EquipmentManager,
    WeaponStats,
)
from src.managers.combat_condition_manager import (
    CombatConditionManager,
    ConditionEffect,
    ConditionInfo,
)
from src.managers.schedule_manager import ScheduleManager
from src.managers.secret_manager import BetrayalRisk, NPCSecret, SecretManager
from src.managers.story_arc_manager import ArcSummary, PacingHint, StoryArcManager
from src.managers.task_manager import TaskManager
from src.managers.time_manager import TimeManager

__all__ = [
    # Base
    "BaseManager",
    # Core Managers
    "TimeManager",
    "EntityManager",
    "LocationManager",
    "FactManager",
    "ItemManager",
    "ScheduleManager",
    "EventManager",
    "TaskManager",
    # Goals
    "GoalManager",
    # Needs
    "NeedsManager",
    "NeedEffect",
    "NeedDecayRates",
    "ActivityType",
    # Memory
    "MemoryManager",
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
    "MilestoneInfo",
    # Context
    "ContextCompiler",
    "SceneContext",
    # Consistency
    "ConsistencyValidator",
    "ConsistencyIssue",
    "TemporalEffects",
    # Narrative
    "StoryArcManager",
    "ArcSummary",
    "PacingHint",
    "MysteryManager",
    "MysteryStatus",
    "ConflictManager",
    "ConflictStatus",
    "SecretManager",
    "NPCSecret",
    "BetrayalRisk",
    "CliffhangerManager",
    "CliffhangerSuggestion",
    "DramaticMoment",
    "SceneTensionAnalysis",
    # Progression
    "ProgressionManager",
    "AdvancementResult",
    "SkillProgress",
    # Achievements
    "AchievementManager",
    "AchievementUnlock",
    "AchievementProgress",
    # Reputation
    "ReputationManager",
    "ReputationChange",
    "FactionStanding",
    # Equipment
    "EquipmentManager",
    "WeaponStats",
    "ArmorStats",
    # Combat Conditions
    "CombatConditionManager",
    "ConditionEffect",
    "ConditionInfo",
]
