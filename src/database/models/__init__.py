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
from src.database.models.relationships import Relationship, RelationshipChange
from src.database.models.session import GameSession, Turn
from src.database.models.tasks import Appointment, Quest, QuestStage, Task
from src.database.models.world import Fact, Location, Schedule, TimeState, WorldEvent

# New models for realism system
from src.database.models.character_state import CharacterNeeds
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
    # World
    "Location",
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
]
