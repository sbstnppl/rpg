"""Database models package."""

from src.database.models.base import Base, SoftDeleteMixin, TimestampMixin
from src.database.models.enums import (
    AppointmentStatus,
    BodyPart,
    DayOfWeek,
    DriveLevel,
    EntityType,
    FactCategory,
    GriefStage,
    InjurySeverity,
    InjuryType,
    IntimacyStyle,
    ItemCondition,
    ItemType,
    MentalConditionType,
    QuestStatus,
    RelationshipDimension,
    StorageLocationType,
    TaskCategory,
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
from src.database.models.character_state import CharacterNeeds, IntimacyProfile
from src.database.models.injuries import ActivityRestriction, BodyInjury
from src.database.models.mental_state import GriefCondition, MentalCondition
from src.database.models.vital_state import EntityVitalState

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
    "IntimacyProfile",
    # Injuries (new)
    "BodyInjury",
    "ActivityRestriction",
    # Vital state (new)
    "EntityVitalState",
    # Mental state (new)
    "MentalCondition",
    "GriefCondition",
]
