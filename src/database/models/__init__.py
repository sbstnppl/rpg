"""Database models package."""

from src.database.models.base import Base, SoftDeleteMixin, TimestampMixin
from src.database.models.enums import (
    AppointmentStatus,
    DayOfWeek,
    EntityType,
    FactCategory,
    ItemCondition,
    ItemType,
    QuestStatus,
    RelationshipDimension,
    StorageLocationType,
    TaskCategory,
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
]
