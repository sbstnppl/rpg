"""Database models package."""

from src.database.models.base import Base, SoftDeleteMixin, TimestampMixin
from src.database.models.enums import (
    AlcoholTolerance,
    AppointmentStatus,
    BodyPart,
    ConnectionType,
    DayOfWeek,
    DiscoveryMethod,
    DriveLevel,
    EmotionalValence,
    EncounterFrequency,
    EntityType,
    FactCategory,
    GoalPriority,
    GoalStatus,
    GoalType,
    GriefStage,
    InjurySeverity,
    InjuryType,
    IntimacyStyle,
    ItemCondition,
    ItemType,
    MapType,
    MemoryType,
    MentalConditionType,
    ModifierSource,
    PlacementType,
    QuestStatus,
    RelationshipDimension,
    SocialTendency,
    StorageLocationType,
    TaskCategory,
    TerrainType,
    TransportType,
    VisibilityRange,
    VitalStatus,
)
from src.database.models.entities import (
    Entity,
    EntityAttribute,
    EntitySkill,
    MonsterExtension,
    NPCExtension,
)
from src.database.models.items import Item, StorageLocation
from src.database.models.relationships import (
    Relationship,
    RelationshipChange,
    RelationshipMilestone,
)
from src.database.models.session import GameSession, Turn
from src.database.models.tasks import Appointment, Quest, QuestStage, Task
from src.database.models.world import (
    Fact,
    Location,
    LocationVisit,
    Schedule,
    TimeState,
    WorldEvent,
)

# New models for realism system
from src.database.models.character_state import CharacterNeeds, NeedsCommunicationLog
from src.database.models.character_memory import CharacterMemory
from src.database.models.character_preferences import (
    CharacterPreferences,
    NeedAdaptation,
    NeedModifier,
)
from src.database.models.injuries import ActivityRestriction, BodyInjury
from src.database.models.mental_state import GriefCondition, MentalCondition
from src.database.models.vital_state import EntityVitalState

# Navigation models for world map system
from src.database.models.navigation import (
    DigitalMapAccess,
    LocationDiscovery,
    LocationZonePlacement,
    MapItem,
    TerrainZone,
    TransportMode,
    ZoneConnection,
    ZoneDiscovery,
)

# NPC Goals for autonomous behavior
from src.database.models.goals import NPCGoal

# Narrative systems for story arcs, mysteries, and conflicts
from src.database.models.narrative import (
    ArcPhase,
    ArcStatus,
    ArcType,
    Conflict,
    ConflictLevel,
    Mystery,
    StoryArc,
)

# Progression systems for achievements and ranks
from src.database.models.progression import (
    Achievement,
    AchievementType,
    EntityAchievement,
)

# Faction and reputation systems
from src.database.models.faction import (
    EntityReputation,
    Faction,
    FactionRelationship,
    ReputationChange,
    ReputationTier,
)

# Equipment definitions for combat
from src.database.models.equipment import (
    ArmorCategory,
    ArmorDefinition,
    DamageType,
    WeaponCategory,
    WeaponDefinition,
    WeaponProperty,
    WeaponRange,
)

# Combat conditions
from src.database.models.combat_conditions import (
    CombatCondition,
    EntityCondition,
)

# Rumor system
from src.database.models.rumors import (
    Rumor,
    RumorKnowledge,
    RumorSentiment,
)

# Relationship arcs
from src.database.models.relationship_arcs import (
    RelationshipArc,
    RelationshipArcPhase,
    RelationshipArcType,
)

# Economy system
from src.database.models.economy import (
    DemandLevel,
    EconomicEvent,
    MarketPrice,
    RouteStatus,
    SupplyLevel,
    TradeRoute,
)

# Magic system
from src.database.models.magic import (
    CastingTime,
    EntityMagicProfile,
    MagicTradition,
    SpellCastRecord,
    SpellDefinition,
    SpellSchool,
)

# Destiny system
from src.database.models.destiny import (
    DestinyElement,
    DestinyElementType,
    Prophesy,
    ProphesyStatus,
)

__all__ = [
    # Base
    "Base",
    "TimestampMixin",
    "SoftDeleteMixin",
    # Enums
    "EntityType",
    "ItemType",
    "ItemCondition",
    "StorageLocationType",
    "TaskCategory",
    "AppointmentStatus",
    "QuestStatus",
    "DayOfWeek",
    "FactCategory",
    "RelationshipDimension",
    # New enums
    "VitalStatus",
    "InjuryType",
    "InjurySeverity",
    "BodyPart",
    "GriefStage",
    "IntimacyStyle",
    "DriveLevel",
    "MentalConditionType",
    # Character preferences enums
    "AlcoholTolerance",
    "SocialTendency",
    "ModifierSource",
    # Character memory enums
    "MemoryType",
    "EmotionalValence",
    # Goal enums
    "GoalType",
    "GoalPriority",
    "GoalStatus",
    # Session
    "GameSession",
    "Turn",
    # Entities
    "Entity",
    "EntityAttribute",
    "EntitySkill",
    "NPCExtension",
    "MonsterExtension",
    # Items
    "Item",
    "StorageLocation",
    # Relationships
    "Relationship",
    "RelationshipChange",
    "RelationshipMilestone",
    # World
    "Location",
    "LocationVisit",
    "Schedule",
    "TimeState",
    "Fact",
    "WorldEvent",
    # Tasks
    "Task",
    "Appointment",
    "Quest",
    "QuestStage",
    # Character state (new)
    "CharacterNeeds",
    "NeedsCommunicationLog",
    # Character memory (new)
    "CharacterMemory",
    # Character preferences (new)
    "CharacterPreferences",
    "NeedModifier",
    "NeedAdaptation",
    # Injuries (new)
    "BodyInjury",
    "ActivityRestriction",
    # Vital state (new)
    "EntityVitalState",
    # Mental state (new)
    "MentalCondition",
    "GriefCondition",
    # Navigation enums (new)
    "TerrainType",
    "ConnectionType",
    "TransportType",
    "MapType",
    "VisibilityRange",
    "EncounterFrequency",
    "DiscoveryMethod",
    "PlacementType",
    # Navigation models (new)
    "TerrainZone",
    "ZoneConnection",
    "LocationZonePlacement",
    "TransportMode",
    "ZoneDiscovery",
    "LocationDiscovery",
    "MapItem",
    "DigitalMapAccess",
    # NPC Goals
    "NPCGoal",
    # Narrative enums
    "ArcType",
    "ArcPhase",
    "ArcStatus",
    "ConflictLevel",
    # Narrative models
    "StoryArc",
    "Mystery",
    "Conflict",
    # Progression enums
    "AchievementType",
    # Progression models
    "Achievement",
    "EntityAchievement",
    # Faction models
    "Faction",
    "FactionRelationship",
    "EntityReputation",
    "ReputationChange",
    "ReputationTier",
    # Equipment enums
    "DamageType",
    "WeaponProperty",
    "WeaponCategory",
    "WeaponRange",
    "ArmorCategory",
    # Equipment models
    "WeaponDefinition",
    "ArmorDefinition",
    # Combat conditions
    "CombatCondition",
    "EntityCondition",
    # Rumor system
    "Rumor",
    "RumorKnowledge",
    "RumorSentiment",
    # Relationship arcs
    "RelationshipArc",
    "RelationshipArcPhase",
    "RelationshipArcType",
    # Economy enums
    "SupplyLevel",
    "DemandLevel",
    "RouteStatus",
    # Economy models
    "MarketPrice",
    "TradeRoute",
    "EconomicEvent",
    # Magic enums
    "MagicTradition",
    "SpellSchool",
    "CastingTime",
    # Magic models
    "SpellDefinition",
    "EntityMagicProfile",
    "SpellCastRecord",
    # Destiny enums
    "ProphesyStatus",
    "DestinyElementType",
    # Destiny models
    "Prophesy",
    "DestinyElement",
]
