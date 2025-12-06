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
    FAMILIARITY = "familiarity"
    FEAR = "fear"
    SOCIAL_DEBT = "social_debt"


class VitalStatus(str, Enum):
    """Progressive death states for characters."""

    HEALTHY = "healthy"
    WOUNDED = "wounded"  # Can function with penalties
    CRITICAL = "critical"  # Unconscious, dying in X turns
    DYING = "dying"  # Death saves required
    DEAD = "dead"  # No vital signs
    CLINICALLY_DEAD = "clinically_dead"  # Dead but revivable (fantasy/scifi)
    PERMANENTLY_DEAD = "permanently_dead"  # No coming back


class InjuryType(str, Enum):
    """Types of injuries with different healing behaviors."""

    # Tissue damage
    BRUISE = "bruise"  # Mild, 2-5 days
    CUT = "cut"  # Bleeding, infection risk, 5-10 days
    LACERATION = "laceration"  # Deep cut, scarring, 10-20 days
    BURN = "burn"  # Degrees 1-3, scarring

    # Bone/joint
    SPRAIN = "sprain"  # Joint, 1-3 weeks
    STRAIN = "strain"  # Muscle, 3-10 days
    FRACTURE = "fracture"  # Bone break, 6-12 weeks
    DISLOCATION = "dislocation"  # Joint, instant fix but lingering pain

    # Muscle
    MUSCLE_SORE = "muscle_sore"  # Post-exercise, 1-3 days
    MUSCLE_TEAR = "muscle_tear"  # Partial, 3-6 weeks
    MUSCLE_RUPTURE = "muscle_rupture"  # Complete, surgery, 3-6 months

    # Severe
    CONCUSSION = "concussion"  # Head, cognitive effects
    INTERNAL_BLEEDING = "internal_bleeding"  # Life-threatening
    NERVE_DAMAGE = "nerve_damage"  # Numbness, weakness


class InjurySeverity(str, Enum):
    """Severity levels affecting impairment and recovery."""

    MINOR = "minor"  # 0-25% impairment
    MODERATE = "moderate"  # 26-50% impairment
    SEVERE = "severe"  # 51-75% impairment
    CRITICAL = "critical"  # 76-100% impairment (unusable)


class BodyPart(str, Enum):
    """Body parts that can be injured."""

    # Core
    HEAD = "head"
    TORSO = "torso"
    BACK = "back"

    # Arms
    LEFT_SHOULDER = "left_shoulder"
    RIGHT_SHOULDER = "right_shoulder"
    LEFT_ARM = "left_arm"
    RIGHT_ARM = "right_arm"
    LEFT_HAND = "left_hand"
    RIGHT_HAND = "right_hand"

    # Legs
    LEFT_HIP = "left_hip"
    RIGHT_HIP = "right_hip"
    LEFT_LEG = "left_leg"
    RIGHT_LEG = "right_leg"
    LEFT_FOOT = "left_foot"
    RIGHT_FOOT = "right_foot"

    # Specific
    EYES = "eyes"
    EARS = "ears"


class GriefStage(str, Enum):
    """Kübler-Ross grief stages for NPCs who lost someone."""

    SHOCK = "shock"  # 1-3 days: -20 morale, can't focus
    DENIAL = "denial"  # 3-7 days: -15 morale
    ANGER = "anger"  # 1-2 weeks: irritable, +10 to aggressive actions
    BARGAINING = "bargaining"  # Variable
    DEPRESSION = "depression"  # 2-4 weeks: -25 morale, low energy
    ACCEPTANCE = "acceptance"  # Gradual recovery


class IntimacyStyle(str, Enum):
    """How characters approach intimate relationships."""

    CASUAL = "casual"  # Prefers one-night stands
    EMOTIONAL = "emotional"  # Requires emotional connection first
    MONOGAMOUS = "monogamous"  # Only with committed partner
    POLYAMOROUS = "polyamorous"  # Multiple partners OK


class DriveLevel(str, Enum):
    """Level of intimacy drive affecting need decay rate."""

    ASEXUAL = "asexual"  # No drive, need stays at 0
    VERY_LOW = "very_low"  # +1/day
    LOW = "low"  # +3/day
    MODERATE = "moderate"  # +5/day
    HIGH = "high"  # +7/day
    VERY_HIGH = "very_high"  # +10/day


class MentalConditionType(str, Enum):
    """Types of mental health conditions."""

    PTSD_COMBAT = "ptsd_combat"
    PTSD_NEAR_DEATH = "ptsd_near_death"
    PTSD_TRAUMA = "ptsd_trauma"
    DEPRESSION = "depression"
    ANXIETY = "anxiety"
    PHOBIA = "phobia"
    DEATH_ANXIETY = "death_anxiety"
    SURVIVORS_GUILT = "survivors_guilt"
    EXISTENTIAL_CRISIS = "existential_crisis"  # From revival in sci-fi
