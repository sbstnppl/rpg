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


# =============================================================================
# Character Preferences Enums
# =============================================================================


class AlcoholTolerance(str, Enum):
    """Alcohol tolerance levels."""

    NONE = "none"  # Cannot drink
    LOW = "low"  # Gets drunk easily
    MODERATE = "moderate"  # Average tolerance
    HIGH = "high"  # Can hold their liquor
    VERY_HIGH = "very_high"  # Barely affected


class SocialTendency(str, Enum):
    """Social preference tendencies."""

    INTROVERT = "introvert"  # Prefers solitude, drains from social
    AMBIVERT = "ambivert"  # Balanced
    EXTROVERT = "extrovert"  # Gains energy from social


class ModifierSource(str, Enum):
    """Source of a need modifier."""

    TRAIT = "trait"  # From character trait (e.g., greedy_eater)
    AGE = "age"  # From age-based calculation
    ADAPTATION = "adaptation"  # From adaptation to circumstances
    CUSTOM = "custom"  # Manually set
    TEMPORARY = "temporary"  # Temporary effect (spell, drug, etc.)


# =============================================================================
# Navigation & World Map Enums
# =============================================================================


class TerrainType(str, Enum):
    """Types of terrain zones."""

    PLAINS = "plains"  # Open grassland, easy travel
    FOREST = "forest"  # Dense trees, slow travel, limited visibility
    ROAD = "road"  # Maintained path, fastest travel
    TRAIL = "trail"  # Rough path, moderate speed
    MOUNTAIN = "mountain"  # Rocky terrain, requires climbing
    SWAMP = "swamp"  # Wet terrain, very slow
    DESERT = "desert"  # Hot, requires water
    LAKE = "lake"  # Body of water, requires swimming/boat
    RIVER = "river"  # Flowing water, may be crossable
    OCEAN = "ocean"  # Deep water, requires ship
    CLIFF = "cliff"  # Vertical terrain, requires climbing
    CAVE = "cave"  # Underground, limited visibility
    URBAN = "urban"  # City streets
    RUINS = "ruins"  # Abandoned structures


class ConnectionType(str, Enum):
    """Types of connections between zones."""

    OPEN = "open"  # No barrier, direct access
    PATH = "path"  # Trail or walkway
    BRIDGE = "bridge"  # Over water/chasm
    CLIMB = "climb"  # Requires climbing skill
    SWIM = "swim"  # Requires swimming skill
    DOOR = "door"  # May be locked
    GATE = "gate"  # May require permission
    HIDDEN = "hidden"  # Secret passage


class TransportType(str, Enum):
    """Types of transport modes."""

    WALKING = "walking"
    RUNNING = "running"
    MOUNTED = "mounted"  # Horse, camel, etc.
    SWIMMING = "swimming"
    CLIMBING = "climbing"
    FLYING = "flying"
    BOAT = "boat"
    SHIP = "ship"
    VEHICLE = "vehicle"  # Modern: car, truck


class MapType(str, Enum):
    """Types of maps (physical items)."""

    WORLD = "world"  # Shows continents, countries
    REGIONAL = "regional"  # Shows roads, cities, rivers
    CITY = "city"  # Shows streets, buildings
    DUNGEON = "dungeon"  # Shows rooms, corridors
    BUILDING = "building"  # Shows floor plan


class VisibilityRange(str, Enum):
    """How far you can see from a zone."""

    FAR = "far"  # Plains, open areas
    MEDIUM = "medium"  # Light forest, urban
    SHORT = "short"  # Dense forest, caves
    NONE = "none"  # Complete darkness


class EncounterFrequency(str, Enum):
    """How often random encounters occur."""

    NONE = "none"  # Safe zones (towns, roads)
    LOW = "low"  # Patrolled areas
    MEDIUM = "medium"  # Wilderness
    HIGH = "high"  # Dangerous areas
    VERY_HIGH = "very_high"  # Monster lairs


class DiscoveryMethod(str, Enum):
    """How a location/zone was discovered."""

    VISITED = "visited"  # Player went there
    TOLD_BY_NPC = "told_by_npc"  # NPC mentioned it
    MAP_VIEWED = "map_viewed"  # Saw it on a physical map
    DIGITAL_LOOKUP = "digital_lookup"  # Google Maps, GPS
    VISIBLE_FROM = "visible_from"  # Can see it from current location
    STARTING_KNOWLEDGE = "starting_knowledge"  # Character's background


class PlacementType(str, Enum):
    """How a location is placed within a zone."""

    WITHIN = "within"  # Fully inside the zone
    EDGE = "edge"  # At zone boundary
    LANDMARK = "landmark"  # Visible from afar


# =============================================================================
# Character Memory Enums
# =============================================================================


class MemoryType(str, Enum):
    """Types of memorable elements that can trigger emotional reactions."""

    PERSON = "person"  # Mother, friend, enemy, mentor
    ITEM = "item"  # Mother's hat, heirloom sword, childhood toy
    PLACE = "place"  # Hometown, battlefield, childhood home
    EVENT = "event"  # House fire, wedding, battle
    CREATURE = "creature"  # Red chicken, pet dog, monster that attacked
    CONCEPT = "concept"  # War, love, betrayal, magic


class EmotionalValence(str, Enum):
    """Emotional quality/direction of the memory."""

    POSITIVE = "positive"  # Joy, love, pride, gratitude
    NEGATIVE = "negative"  # Grief, fear, shame, anger
    MIXED = "mixed"  # Bittersweet, complex feelings
    NEUTRAL = "neutral"  # Curious, interesting but not emotional


# =============================================================================
# NPC Goal Enums
# =============================================================================


class GoalType(str, Enum):
    """Types of goals NPCs can pursue autonomously."""

    ACQUIRE = "acquire"  # Get item/resource (miller needs grain)
    MEET_PERSON = "meet_person"  # Find and interact with someone
    GO_TO = "go_to"  # Travel to location
    LEARN_INFO = "learn_info"  # Discover information
    AVOID = "avoid"  # Stay away from person/place
    PROTECT = "protect"  # Keep someone/something safe
    EARN_MONEY = "earn_money"  # Work, trade, sell
    ROMANCE = "romance"  # Pursue romantic interest
    SOCIAL = "social"  # Make friends, build relationships
    REVENGE = "revenge"  # Get back at someone
    SURVIVE = "survive"  # Meet basic needs (find food/water)
    DUTY = "duty"  # Fulfill obligation/job
    CRAFT = "craft"  # Create something
    HEAL = "heal"  # Recover from injury/illness


class GoalPriority(str, Enum):
    """Priority levels for NPC goals."""

    BACKGROUND = "background"  # Long-term, low urgency
    LOW = "low"  # Can wait
    MEDIUM = "medium"  # Should address soon
    HIGH = "high"  # Important, needs attention
    URGENT = "urgent"  # Must address immediately


class GoalStatus(str, Enum):
    """Status of an NPC goal."""

    ACTIVE = "active"  # Being pursued
    COMPLETED = "completed"  # Successfully achieved
    FAILED = "failed"  # Could not be achieved
    ABANDONED = "abandoned"  # NPC gave up
    BLOCKED = "blocked"  # Temporarily cannot proceed
