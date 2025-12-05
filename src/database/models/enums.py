"""Database enumerations."""

from enum import Enum


class EntityType(str, Enum):
    """Type of entity in the game world."""

    PLAYER = "player"
    NPC = "npc"
    MONSTER = "monster"
    ANIMAL = "animal"


class ItemType(str, Enum):
    """Item categories with different behaviors."""

    CLOTHING = "clothing"  # Wearable, can provide slots
    EQUIPMENT = "equipment"  # Carried (surfboard, backpack)
    ACCESSORY = "accessory"  # Wearable (watch, ring, necklace)
    CONSUMABLE = "consumable"  # Stackable (food, potions)
    CONTAINER = "container"  # Can hold other items
    TOOL = "tool"  # Usable for tasks
    WEAPON = "weapon"  # Combat items
    ARMOR = "armor"  # Defensive items
    MISC = "misc"  # Default


class ItemCondition(str, Enum):
    """Condition of an item."""

    PRISTINE = "pristine"
    GOOD = "good"
    WORN = "worn"
    DAMAGED = "damaged"
    BROKEN = "broken"


class StorageLocationType(str, Enum):
    """Type of storage location."""

    ON_PERSON = "on_person"  # Body slots with layers
    CONTAINER = "container"  # Backpack, bag, box (portable)
    PLACE = "place"  # Room, beach, car (static location)


class TaskCategory(str, Enum):
    """Category of player task."""

    APPOINTMENT = "appointment"  # Timed commitment
    GOAL = "goal"  # Open-ended goal
    REMINDER = "reminder"  # General reminder
    QUEST = "quest"  # Main story objectives


class AppointmentStatus(str, Enum):
    """Status of appointments."""

    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    MISSED = "missed"
    RESCHEDULED = "rescheduled"


class QuestStatus(str, Enum):
    """Status of quests."""

    AVAILABLE = "available"  # Can be started
    ACTIVE = "active"  # In progress
    COMPLETED = "completed"  # Successfully finished
    FAILED = "failed"  # Failed permanently


class DayOfWeek(str, Enum):
    """Days of the week for schedules."""

    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"
    WEEKDAY = "weekday"  # Mon-Fri
    WEEKEND = "weekend"  # Sat-Sun
    DAILY = "daily"  # Every day


class FactCategory(str, Enum):
    """Categories of facts."""

    PERSONAL = "personal"  # Personal info (job, age)
    SECRET = "secret"  # Hidden from player
    PREFERENCE = "preference"  # Likes/dislikes
    SKILL = "skill"  # Abilities
    HISTORY = "history"  # Past events
    RELATIONSHIP = "relationship"  # Connections to others
    LOCATION = "location"  # Where things are
    WORLD = "world"  # Global facts


class RelationshipDimension(str, Enum):
    """Dimensions of relationships."""

    TRUST = "trust"
    LIKING = "liking"
    RESPECT = "respect"
    ROMANTIC_INTEREST = "romantic_interest"
