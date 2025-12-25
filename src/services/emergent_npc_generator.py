"""Emergent NPC Generator Service.

This service creates NPCs with emergent traits - personality, preferences, and
attractions are generated randomly (with optional constraints) rather than
prescribed by the GM. The GM discovers who an NPC is rather than dictating it.

Key philosophy: "GM Discovers, Not Prescribes"
- Old: GM decides "I need a shy woman who likes the player"
- New: GM requests "I need a female customer" → System generates full personality
      → GM discovers she's shy AND attracted (or not!)
"""

from __future__ import annotations

import asyncio
import logging
import math
import random
import re
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from src.agents.schemas.npc_state import (
    AttractionScore,
    EnvironmentalReaction,
    ImmediateGoal,
    NPCAppearance,
    NPCBackground,
    NPCConstraints,
    NPCCurrentState,
    NPCFullState,
    NPCNeeds,
    NPCPersonality,
    NPCPreferences,
    NPCReactions,
    OccupationDetails,
    PlayerSummary,
    SceneContext,
    VisibleItem,
)
from src.llm.factory import get_creative_provider
from src.database.models.character_preferences import CharacterPreferences
from src.database.models.character_state import CharacterNeeds
from src.database.models.entities import Entity, EntitySkill, NPCExtension
from src.database.models.enums import (
    AlcoholTolerance,
    DriveLevel,
    EntityType,
    IntimacyStyle,
    ItemCondition,
    ItemType,
    SocialTendency,
)
from src.database.models.items import Item
from src.database.models.session import GameSession
from src.database.models.world import TimeState
from src.services.preference_calculator import (
    PHYSICAL_ATTRACTION_TRAITS,
    PERSONALITY_ATTRACTION_TRAITS,
    generate_gender_attraction,
    generate_age_offset,
    generate_preferences,
)

if TYPE_CHECKING:
    pass


logger = logging.getLogger(__name__)


# =============================================================================
# Generation Data Pools
# =============================================================================

# Names by gender (expandable)
NAMES_BY_GENDER: dict[str, list[str]] = {
    "male": [
        "Marcus", "Thomas", "Erik", "William", "Roland", "Geoffrey", "Aldric",
        "Garrett", "Edmund", "Cedric", "Frederick", "Heinrich", "Ludwig",
        "Bruno", "Otto", "Conrad", "Reinhardt", "Sebastian", "Victor", "Hugo",
        "Finn", "Declan", "Ronan", "Magnus", "Bjorn", "Sven", "Tobias", "Lukas",
        "Felix", "Max", "Leon", "Noah", "Elias", "Jonas", "Liam", "Oscar",
    ],
    "female": [
        "Elena", "Mira", "Sophia", "Isabella", "Clara", "Rosalind", "Adelaide",
        "Beatrice", "Catherine", "Diana", "Evangeline", "Fiona", "Giselle",
        "Helena", "Ingrid", "Josephine", "Katherine", "Lillian", "Margaret",
        "Nadia", "Ophelia", "Priscilla", "Rebecca", "Samantha", "Tabitha",
        "Ursula", "Victoria", "Wilhelmina", "Yvonne", "Zelda", "Astrid",
        "Elara", "Luna", "Aurora", "Celeste", "Ivy", "Violet", "Ruby", "Hazel",
    ],
    "neutral": [
        "Sage", "River", "Ash", "Rowan", "Quinn", "Morgan", "Riley", "Jordan",
        "Alex", "Sam", "Charlie", "Avery", "Casey", "Devon", "Ellis", "Finley",
    ],
}

SURNAMES = [
    "Thornwood", "Blackwood", "Ironforge", "Stoneheart", "Brightwater",
    "Shadowmere", "Goldleaf", "Silverbrook", "Oakenshield", "Ravencrest",
    "Winterbourne", "Summerfield", "Greenwood", "Whitmore", "Ashford",
    "Crawford", "Fletcher", "Cooper", "Miller", "Smith", "Baker", "Taylor",
    "Fisher", "Weaver", "Potter", "Carpenter", "Mason", "Thatcher", "Wright",
    "Porter", "Turner", "Ward", "Hunter", "Fowler", "Forester", "Gardner",
]

# =============================================================================
# Setting-Specific Name Pools
# =============================================================================

NAMES_BY_SETTING: dict[str, dict[str, list[str]]] = {
    "fantasy": {
        "male": [
            "Marcus", "Thomas", "Erik", "William", "Roland", "Geoffrey", "Aldric",
            "Garrett", "Edmund", "Cedric", "Frederick", "Heinrich", "Ludwig",
            "Bruno", "Otto", "Conrad", "Reinhardt", "Sebastian", "Victor", "Hugo",
            "Finn", "Declan", "Ronan", "Magnus", "Bjorn", "Sven", "Tobias", "Lukas",
            "Felix", "Max", "Leon", "Elias", "Jonas", "Liam", "Oscar",
        ],
        "female": [
            "Elena", "Mira", "Sophia", "Isabella", "Clara", "Rosalind", "Adelaide",
            "Beatrice", "Catherine", "Diana", "Evangeline", "Fiona", "Giselle",
            "Helena", "Ingrid", "Josephine", "Katherine", "Lillian", "Margaret",
            "Nadia", "Ophelia", "Priscilla", "Rebecca", "Tabitha",
            "Ursula", "Victoria", "Wilhelmina", "Yvonne", "Zelda", "Astrid",
            "Elara", "Luna", "Aurora", "Celeste", "Ivy", "Violet", "Ruby", "Hazel",
        ],
        "neutral": [
            "Sage", "River", "Ash", "Rowan", "Quinn", "Morgan", "Riley",
            "Avery", "Casey", "Devon", "Ellis", "Finley",
        ],
        "surnames": [
            "Thornwood", "Blackwood", "Ironforge", "Stoneheart", "Brightwater",
            "Shadowmere", "Goldleaf", "Silverbrook", "Oakenshield", "Ravencrest",
            "Winterbourne", "Summerfield", "Greenwood", "Whitmore", "Ashford",
            "Crawford", "Fletcher", "Cooper", "Miller", "Baker", "Taylor",
            "Fisher", "Weaver", "Potter", "Carpenter", "Mason", "Thatcher", "Wright",
        ],
    },
    "contemporary": {
        "male": [
            "James", "Michael", "David", "John", "Robert", "William", "Daniel",
            "Matthew", "Christopher", "Andrew", "Joseph", "Brian", "Kevin", "Steven",
            "Jason", "Ryan", "Anthony", "Eric", "Mark", "Timothy", "Jeffrey", "Scott",
            "Brandon", "Nicholas", "Justin", "Tyler", "Jacob", "Ethan", "Noah", "Mason",
            "Carlos", "Miguel", "Jose", "Luis", "Diego", "Jamal", "Marcus", "Tyrone",
            "Wei", "Hiroshi", "Raj", "Mohammed", "Ahmed", "Omar", "Aleksei", "Ivan",
        ],
        "female": [
            "Sarah", "Emily", "Jessica", "Amanda", "Jennifer", "Michelle", "Ashley",
            "Stephanie", "Nicole", "Elizabeth", "Megan", "Samantha", "Lauren", "Rachel",
            "Hannah", "Brittany", "Heather", "Christina", "Rebecca", "Amber", "Kimberly",
            "Tiffany", "Melissa", "Kelly", "Amy", "Lisa", "Angela", "Sophia", "Emma",
            "Maria", "Isabella", "Gabriela", "Rosa", "Keisha", "Aaliyah", "Jasmine",
            "Lin", "Yuki", "Priya", "Aisha", "Fatima", "Olga", "Natasha", "Ingrid",
        ],
        "neutral": [
            "Alex", "Sam", "Charlie", "Jordan", "Taylor", "Morgan", "Casey",
            "Jamie", "Drew", "Riley", "Quinn", "Avery", "Skylar", "Dakota",
        ],
        "surnames": [
            "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
            "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
            "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
            "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
            "Lewis", "Robinson", "Walker", "Young", "Allen", "King", "Wright",
            "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green", "Adams", "Nelson",
            "Baker", "Hall", "Rivera", "Campbell", "Mitchell", "Carter", "Roberts",
            "Chen", "Kim", "Patel", "Singh", "Yamamoto", "Tanaka", "Ivanov", "Petrov",
        ],
    },
    "scifi": {
        "male": [
            "Zex", "Kiran", "Axel", "Nova-7", "Ryder", "Jax", "Kane", "Orion",
            "Cyrus", "Phoenix", "Dax", "Zander", "Blaze", "Kai", "Rex", "Talon",
            "Vex", "Cade", "Neo", "Ryker", "Maddox", "Knox", "Atlas", "Titan",
            "Sigma", "Vector", "Prometheus", "Helios", "Zenith", "Flux", "Nexus",
        ],
        "female": [
            "Nova", "Zara", "Lyra", "Vex", "Aria", "Luna", "Stella", "Aurora",
            "Phoenix", "Ember", "Seren", "Celeste", "Astrid", "Freya", "Electra",
            "Nyx", "Echo", "Vega", "Jade", "Raven", "Storm", "Solara", "Nebula",
            "Zenith", "Delta", "Omega", "Andromeda", "Cassiopeia", "Oriana",
        ],
        "neutral": [
            "Zero", "Unit", "Cipher", "Null", "Binary", "Flux", "Quantum",
            "Vector", "Pixel", "Byte", "Nano", "Chrome", "Synth", "Ion",
        ],
        "surnames": [
            "Axiom", "Nexus", "Vortex", "Prime", "Vector", "Stellar", "Quantum",
            "Cyber", "Nova", "Flux", "Helix", "Prism", "Chrome", "Volt", "Pulse",
            "Zenith", "Arc", "Drift", "Core", "Matrix", "Spark", "Shade", "Void",
            "Null", "Byte", "Node", "Link", "Wave", "Beam", "Surge", "Jet",
            "7X", "K9", "X-12", "V-Prime", "Zero-One", "Alpha-7", "Omega-3",
        ],
    },
}

# Setting aliases for name lookup
_SETTING_NAME_ALIASES: dict[str, str] = {
    "fantasy": "fantasy",
    "medieval": "fantasy",
    "contemporary": "contemporary",
    "modern": "contemporary",
    "scifi": "scifi",
    "sci-fi": "scifi",
    "cyberpunk": "scifi",
    "space": "scifi",
}

# =============================================================================
# Location-Based Apprentice Roles
# =============================================================================

# Maps location keywords to context-appropriate youth occupations.
# Each location type has: (apprentice_role, young_helper_role)
# - apprentice_role: For ages 14-17 (actual apprenticeship)
# - young_helper_role: For ages under 14 (simpler tasks)

LOCATION_APPRENTICE_ROLES: dict[str, tuple[str, str]] = {
    # Crafts and trades
    "bakery": ("baker's apprentice", "baker's helper"),
    "baker": ("baker's apprentice", "baker's helper"),
    "blacksmith": ("blacksmith's apprentice", "forge helper"),
    "forge": ("blacksmith's apprentice", "forge helper"),
    "smithy": ("blacksmith's apprentice", "forge helper"),
    "tailor": ("tailor's apprentice", "tailor's helper"),
    "dressmaker": ("tailor's apprentice", "tailor's helper"),
    "cobbler": ("cobbler's apprentice", "cobbler's helper"),
    "shoemaker": ("cobbler's apprentice", "cobbler's helper"),
    "carpenter": ("carpenter's apprentice", "carpenter's helper"),
    "woodworker": ("carpenter's apprentice", "carpenter's helper"),
    "butcher": ("butcher's apprentice", "butcher's helper"),
    "tanner": ("tanner's apprentice", "tanner's helper"),
    "leatherworker": ("leatherworker's apprentice", "leather shop helper"),
    "potter": ("potter's apprentice", "potter's helper"),
    "jeweler": ("jeweler's apprentice", "shop assistant"),
    "goldsmith": ("goldsmith's apprentice", "shop assistant"),
    "weaver": ("weaver's apprentice", "weaver's helper"),
    "mason": ("mason's apprentice", "mason's helper"),
    "glassblower": ("glassblower's apprentice", "workshop helper"),

    # Food and hospitality
    "tavern": ("tavern worker", "pot boy"),
    "inn": ("inn servant", "pot boy"),
    "pub": ("barback", "pot boy"),
    "bar": ("barback", "cleaner"),
    "restaurant": ("kitchen apprentice", "busboy"),
    "kitchen": ("kitchen apprentice", "kitchen boy"),
    "brewery": ("brewer's apprentice", "barrel boy"),
    "winery": ("vintner's apprentice", "cellar helper"),
    "distillery": ("distiller's apprentice", "cellar helper"),

    # Animals and farming
    "stable": ("stable hand", "stable boy"),
    "stables": ("stable hand", "stable boy"),
    "farm": ("farm hand", "farm helper"),
    "ranch": ("ranch hand", "ranch helper"),
    "mill": ("miller's apprentice", "mill helper"),
    "fishmonger": ("fishmonger's apprentice", "fish runner"),
    "kennels": ("kennel assistant", "kennel boy"),

    # Commerce
    "shop": ("shop apprentice", "shop assistant"),
    "store": ("shop apprentice", "shop assistant"),
    "market": ("market runner", "market helper"),
    "merchant": ("merchant's apprentice", "shop assistant"),
    "warehouse": ("warehouse worker", "warehouse helper"),
    "trading": ("trader's apprentice", "runner"),

    # Services
    "apothecary": ("apothecary's apprentice", "shop assistant"),
    "herbalist": ("herbalist's apprentice", "herb gatherer"),
    "healer": ("healer's apprentice", "assistant"),
    "barber": ("barber's apprentice", "shop assistant"),
    "scribe": ("scribe's apprentice", "page"),
    "library": ("library assistant", "page"),
    "temple": ("acolyte", "temple helper"),
    "church": ("acolyte", "altar boy"),
    "shrine": ("shrine attendant", "shrine helper"),

    # Ships and docks
    "dock": ("dock worker", "dock runner"),
    "harbor": ("dock worker", "dock runner"),
    "ship": ("cabin boy", "ship's boy"),
    "shipyard": ("shipwright's apprentice", "yard helper"),

    # Military and guard
    "barracks": ("squire", "page"),
    "guard": ("trainee guard", "messenger"),
    "garrison": ("trainee guard", "runner"),
    "armory": ("armorer's apprentice", "armory helper"),

    # Entertainment
    "theater": ("stage hand", "theater runner"),
    "playhouse": ("stage hand", "theater runner"),
    "music": ("musician's apprentice", "music student"),
}

# Generic fallback roles for unknown locations
_GENERIC_APPRENTICE_ROLES: list[str] = [
    "apprentice", "trainee", "assistant", "helper",
]

_GENERIC_YOUNG_ROLES: list[str] = [
    "errand runner", "helper", "messenger", "page",
]

# Personality trait pools
PERSONALITY_TRAITS = [
    "shy", "confident", "curious", "cautious", "bold", "timid", "friendly",
    "suspicious", "optimistic", "pessimistic", "romantic", "practical",
    "hardworking", "lazy", "generous", "greedy", "honest", "deceptive",
    "patient", "impatient", "calm", "anxious", "stoic", "emotional",
    "loyal", "fickle", "adventurous", "cautious", "idealistic", "cynical",
    "humble", "proud", "gentle", "aggressive", "forgiving", "vengeful",
    "trusting", "paranoid", "witty", "serious", "playful", "stern",
]

VALUES = [
    "honesty", "loyalty", "family", "friendship", "adventure", "security",
    "freedom", "justice", "knowledge", "wisdom", "wealth", "power",
    "beauty", "love", "respect", "honor", "tradition", "progress",
    "nature", "spirituality", "duty", "pleasure", "independence", "community",
]

FLAWS = [
    "indecisive", "too trusting", "stubborn", "impatient", "overthinks",
    "holds grudges", "easily distracted", "procrastinator", "perfectionist",
    "arrogant", "insecure", "jealous", "gossips", "gullible", "cowardly",
    "reckless", "manipulative", "judgmental", "self-centered", "closed-minded",
    "hypocritical", "vain", "pessimistic", "passive-aggressive", "temperamental",
]

QUIRKS = [
    "touches hair when nervous", "hums while working", "talks to self",
    "cracks knuckles", "taps foot when impatient", "bites lip when thinking",
    "always late", "compulsively tidy", "collects odd trinkets",
    "speaks in rhymes when drunk", "laughs at inappropriate times",
    "can't sit still", "always hungry", "superstitious about certain things",
    "refers to self in third person", "whistles off-key", "gestures wildly",
    "speaks very quietly", "speaks very loudly", "uses big words incorrectly",
]

# Physical trait pools
BUILDS = ["slender", "average", "athletic", "stocky", "muscular", "heavyset", "wiry", "petite"]
HAIR_COLORS = ["black", "dark brown", "brown", "auburn", "red", "blonde", "light brown", "gray", "white", "silver"]
HAIR_STYLES = [
    "short and neat", "long and loose", "in a braid", "in a ponytail", "cropped close",
    "wavy", "curly", "straight", "tousled", "carefully styled", "practical bun",
    "wild and unkempt", "shaved on sides", "adorned with pins", "tucked under cap",
]
EYE_COLORS = ["brown", "dark brown", "hazel", "green", "blue", "gray", "amber", "light blue", "dark green"]
SKIN_TONES = [
    "fair", "pale", "light", "olive", "tan", "bronze", "brown", "dark brown", "dark",
    "freckled fair", "ruddy", "weathered", "sun-kissed",
]

# Height growth percentages by age (percentage of adult height)
# Based on standard pediatric growth curves
GROWTH_PERCENTAGES: dict[int, float] = {
    5: 0.55, 6: 0.58, 7: 0.61, 8: 0.64, 9: 0.67,
    10: 0.70, 11: 0.74, 12: 0.78, 13: 0.83, 14: 0.88,
    15: 0.93, 16: 0.96, 17: 0.98,
}

# Voice pools by age category
VOICES_CHILD = ["high and clear", "piping", "soft", "childlike", "bright"]
VOICES_TEEN = ["youthful", "clear", "light", "bright", "unbroken"]

# Occupation-based skill templates
OCCUPATION_SKILLS: dict[str, list[str]] = {
    "merchant": ["haggling", "appraisal", "persuasion", "accounting"],
    "guard": ["swordfighting", "intimidation", "perception", "endurance"],
    "innkeeper": ["cooking", "brewing", "hospitality", "gossip"],
    "blacksmith": ["smithing", "appraisal", "endurance", "haggling"],
    "farmer": ["agriculture", "animal_handling", "weather_sense", "endurance"],
    "hunter": ["tracking", "archery", "survival", "stealth"],
    "healer": ["medicine", "herbalism", "diagnosis", "empathy"],
    "scholar": ["research", "languages", "history", "teaching"],
    "thief": ["lockpicking", "stealth", "pickpocketing", "perception"],
    "soldier": ["swordfighting", "tactics", "endurance", "discipline"],
    "sailor": ["sailing", "navigation", "swimming", "knots"],
    "craftsman": ["crafting", "appraisal", "haggling", "patience"],
    "noble": ["etiquette", "politics", "leadership", "fencing"],
    "priest": ["theology", "ritual", "counseling", "persuasion"],
    "bard": ["music", "storytelling", "persuasion", "performance"],
    "herbalist": ["herbalism", "botany", "medicine", "foraging"],
    "baker": ["baking", "cooking", "business", "early_rising"],
    "tailor": ["sewing", "fashion", "haggling", "appraisal"],
    "servant": ["etiquette", "discretion", "cleaning", "cooking"],
    "beggar": ["begging", "streetwise", "survival", "stealth"],
    # Youth/child roles
    "apprentice": ["learning", "chores", "observation", "patience"],
    "stable_boy": ["animal_handling", "riding", "cleaning", "endurance"],
    "kitchen_boy": ["cooking", "cleaning", "carrying", "observation"],
    "errand_boy": ["running", "navigation", "memory", "streetwise"],
    "street_urchin": ["stealth", "begging", "pickpocketing", "streetwise"],
    "page": ["etiquette", "carrying", "observation", "memorization"],
    "squire": ["swordfighting", "riding", "etiquette", "endurance"],
    "choir_boy": ["singing", "reading", "memorization", "discipline"],
    "farm_hand": ["agriculture", "animal_handling", "endurance", "chores"],
    "fisher_boy": ["fishing", "swimming", "knots", "patience"],
    "shepherd_boy": ["animal_handling", "patience", "navigation", "survival"],
    "miller_boy": ["carrying", "counting", "endurance", "mechanics"],
    "child": ["playing", "curiosity", "running", "hiding"],
    "youth": ["learning", "chores", "running", "observation"],
    "customer": ["haggling", "observation"],  # Generic role
    "visitor": ["observation", "etiquette"],  # Generic role
    "passerby": ["observation"],  # Generic role
}

# Occupation-based inventory templates
OCCUPATION_INVENTORY: dict[str, list[dict[str, Any]]] = {
    "merchant": [
        {"item_key": "coin_purse", "display_name": "Coin Purse", "item_type": "container"},
        {"item_key": "ledger", "display_name": "Account Ledger", "item_type": "misc"},
    ],
    "guard": [
        {"item_key": "sword", "display_name": "Short Sword", "item_type": "weapon"},
        {"item_key": "whistle", "display_name": "Guard Whistle", "item_type": "misc"},
    ],
    "innkeeper": [
        {"item_key": "keys", "display_name": "Ring of Keys", "item_type": "misc"},
        {"item_key": "coin_purse", "display_name": "Coin Purse", "item_type": "container"},
    ],
    "blacksmith": [
        {"item_key": "hammer", "display_name": "Smith's Hammer", "item_type": "misc"},
        {"item_key": "tongs", "display_name": "Smithing Tongs", "item_type": "misc"},
    ],
    "farmer": [
        {"item_key": "straw_hat", "display_name": "Straw Hat", "item_type": "clothing"},
    ],
    "hunter": [
        {"item_key": "bow", "display_name": "Hunting Bow", "item_type": "weapon"},
        {"item_key": "skinning_knife", "display_name": "Skinning Knife", "item_type": "weapon"},
    ],
    "healer": [
        {"item_key": "herb_pouch", "display_name": "Herb Pouch", "item_type": "container"},
        {"item_key": "bandages", "display_name": "Clean Bandages", "item_type": "consumable"},
    ],
    "scholar": [
        {"item_key": "book", "display_name": "Leather-bound Book", "item_type": "misc"},
        {"item_key": "quill", "display_name": "Writing Quill", "item_type": "misc"},
    ],
    "noble": [
        {"item_key": "signet_ring", "display_name": "Signet Ring", "item_type": "misc"},
        {"item_key": "coin_purse", "display_name": "Heavy Coin Purse", "item_type": "container"},
    ],
    "herbalist": [
        {"item_key": "herb_pouch", "display_name": "Herb Pouch", "item_type": "container"},
        {"item_key": "mortar", "display_name": "Mortar and Pestle", "item_type": "misc"},
    ],
    # Youth/child roles
    "apprentice": [
        {"item_key": "tool_pouch", "display_name": "Apprentice's Tool Pouch", "item_type": "container"},
    ],
    "stable_boy": [
        {"item_key": "brush", "display_name": "Horse Brush", "item_type": "misc"},
    ],
    "kitchen_boy": [
        {"item_key": "apron", "display_name": "Kitchen Apron", "item_type": "clothing"},
    ],
    "errand_boy": [
        {"item_key": "satchel", "display_name": "Messenger Satchel", "item_type": "container"},
    ],
    "street_urchin": [
        {"item_key": "stick", "display_name": "Sturdy Stick", "item_type": "misc"},
    ],
    "page": [
        {"item_key": "livery", "display_name": "House Livery Badge", "item_type": "misc"},
    ],
    "squire": [
        {"item_key": "practice_sword", "display_name": "Practice Sword", "item_type": "weapon"},
    ],
    "choir_boy": [
        {"item_key": "hymnal", "display_name": "Small Hymnal", "item_type": "misc"},
    ],
    "farm_hand": [
        {"item_key": "straw_hat", "display_name": "Straw Hat", "item_type": "clothing"},
    ],
    "fisher_boy": [
        {"item_key": "fishing_line", "display_name": "Fishing Line and Hook", "item_type": "misc"},
    ],
    "shepherd_boy": [
        {"item_key": "staff", "display_name": "Shepherd's Crook", "item_type": "weapon"},
    ],
    "miller_boy": [
        {"item_key": "apron", "display_name": "Dusty Apron", "item_type": "clothing"},
    ],
    "child": [
        {"item_key": "toy", "display_name": "Wooden Toy", "item_type": "misc"},
    ],
    "youth": [
        {"item_key": "pouch", "display_name": "Small Pouch", "item_type": "container"},
    ],
}

# Physical and personality attraction traits are imported from preference_calculator


# =============================================================================
# Age Range Definitions
# =============================================================================

AGE_RANGES: dict[str, tuple[int, int, str]] = {
    "child": (6, 9, "child"),
    "teen": (10, 17, "teenager"),
    "young_adult": (18, 30, "young adult"),
    "middle_aged": (31, 55, "middle-aged"),
    "elderly": (56, 85, "elderly"),
}


def age_to_description(age: int) -> str:
    """Convert numeric age to narrative description."""
    if age < 10:
        return "a child"
    elif age < 18:
        return "teenage"
    elif age < 25:
        return "early twenties"
    elif age < 30:
        return "late twenties"
    elif age < 40:
        return "thirties"
    elif age < 50:
        return "forties"
    elif age < 60:
        return "fifties"
    elif age < 70:
        return "sixties"
    else:
        return "elderly"


def height_to_description(height_cm: int, gender: str) -> str:
    """Convert height in cm to narrative description."""
    # Average heights differ by gender
    if gender == "female":
        if height_cm < 155:
            return "short"
        elif height_cm < 165:
            return "average height"
        elif height_cm < 175:
            return "tall"
        else:
            return "very tall"
    else:  # male or other
        if height_cm < 165:
            return "short"
        elif height_cm < 175:
            return "average height"
        elif height_cm < 185:
            return "tall"
        else:
            return "very tall"


# =============================================================================
# Item Type Mapping
# =============================================================================

ITEM_TYPE_MAP = {
    "weapon": ItemType.WEAPON,
    "armor": ItemType.ARMOR,
    "clothing": ItemType.CLOTHING,
    "consumable": ItemType.CONSUMABLE,
    "container": ItemType.CONTAINER,
    "misc": ItemType.MISC,
}


# =============================================================================
# Emergent NPC Generator Service
# =============================================================================


class EmergentNPCGenerator:
    """Service for generating NPCs with emergent traits.

    Generates NPCs whose personality, preferences, and attractions are
    determined by the system rather than prescribed by the GM. This creates
    more authentic, surprising interactions.

    Usage:
        generator = EmergentNPCGenerator(db, game_session)

        # Create new NPC
        npc_state = await generator.create_npc(
            role="customer",
            location_key="general_store",
            scene_context=scene_context,
        )

        # Query existing NPC's reactions
        reactions = generator.query_npc_reactions(
            entity_key="customer_elara",
            scene_context=scene_context,
        )
    """

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
    ) -> None:
        """Initialize the emergent NPC generator.

        Args:
            db: Database session.
            game_session: Current game session.
        """
        self.db = db
        self.game_session = game_session
        self.session_id = game_session.id

    # =========================================================================
    # Public API
    # =========================================================================

    def create_npc(
        self,
        role: str,
        location_key: str,
        scene_context: SceneContext,
        constraints: NPCConstraints | None = None,
    ) -> NPCFullState:
        """Create a new NPC with emergent traits.

        Args:
            role: NPC's role/occupation, e.g. "shopkeeper", "customer", "guard"
            location_key: Where the NPC is appearing
            scene_context: Current scene context for situational awareness
            constraints: Optional hard requirements when GM needs specific traits

        Returns:
            NPCFullState with full character data and environmental reactions.
            The NPC is also persisted to the database.
        """
        # Generate identity
        gender = self._generate_gender(constraints)
        name = self._generate_name(gender, constraints)
        entity_key = self._generate_entity_key(role, name)

        # Check if already exists
        existing = self._get_existing_entity(entity_key)
        if existing:
            logger.info(f"NPC {entity_key} already exists, returning existing state")
            return self._build_full_state_from_entity(existing, scene_context)

        # Generate all components
        age = self._generate_age(constraints, role)
        appearance = self._generate_appearance(gender, age, role, constraints)
        background = self._generate_background(role, age, gender, scene_context, constraints)
        personality = self._generate_personality(constraints)
        preferences = self._generate_preferences(gender, age, personality)
        current_needs = self._generate_needs(role, scene_context)
        current_state = self._generate_current_state(role, location_key, scene_context)

        # Calculate environmental reactions (including attraction to player)
        environmental_reactions = self._calculate_environmental_reactions(
            preferences=preferences,
            personality=personality,
            current_needs=current_needs,
            scene_context=scene_context,
            npc_age=age,
            constraints=constraints,
        )

        # Generate immediate goals based on situation
        immediate_goals = self._generate_immediate_goals(
            role=role,
            current_needs=current_needs,
            environmental_reactions=environmental_reactions,
            personality=personality,
        )

        # Generate behavioral prediction
        behavioral_prediction = self._generate_behavioral_prediction(
            personality=personality,
            environmental_reactions=environmental_reactions,
            immediate_goals=immediate_goals,
        )

        # Create the full state
        npc_state = NPCFullState(
            entity_key=entity_key,
            display_name=name,
            appearance=appearance,
            background=background,
            personality=personality,
            preferences=preferences,
            current_needs=current_needs,
            current_state=current_state,
            environmental_reactions=environmental_reactions,
            immediate_goals=immediate_goals,
            behavioral_prediction=behavioral_prediction,
        )

        # Persist to database
        self._persist_npc(npc_state)

        return npc_state

    def create_backstory_npc(
        self,
        shadow_data: dict,
        player_name: str,
    ) -> NPCFullState:
        """Create full NPC from backstory extraction data.

        Used during character creation to generate complete NPCs from
        family, friends, and other relationships mentioned in the player's
        backstory. These NPCs get full personality, preferences, needs,
        and skills - just like gameplay-generated NPCs.

        Args:
            shadow_data: Extracted shadow entity dict with fields:
                - entity_key: Unique identifier
                - display_name: Display name
                - relationship_to_player: family/friend/colleague/etc.
                - relationship_role: Specific role (younger brother, mother, etc.)
                - relationship_context: Emotional context (idolizes player, etc.)
                - age: Estimated age
                - gender: male/female
                - occupation: Job or role
                - personality_traits: List of traits
                - brief_appearance: Physical description
                - brief_description: Summary from backstory
            player_name: The player character's name for relationship context.

        Returns:
            NPCFullState with complete character data.
        """
        # Extract data from shadow_data with defaults
        entity_key = shadow_data.get("entity_key", "unknown_npc")
        name = shadow_data.get("display_name", entity_key.replace("_", " ").title())
        gender = shadow_data.get("gender", "male")
        age = shadow_data.get("age", 30)
        occupation = shadow_data.get("occupation", "commoner")
        relationship_role = shadow_data.get("relationship_role", "acquaintance")
        relationship_context = shadow_data.get("relationship_context", "")
        personality_traits = shadow_data.get("personality_traits", [])
        brief_appearance = shadow_data.get("brief_appearance", "")
        brief_description = shadow_data.get("brief_description", "")

        # Check if already exists
        existing = self._get_existing_entity(entity_key)
        if existing:
            logger.info(f"Backstory NPC {entity_key} already exists")
            # Return minimal state for existing entity
            return self._build_minimal_state_from_entity(existing)

        # Build constraints from extracted data
        constraints = NPCConstraints(
            name=name,
            gender=gender,
            age_exact=age,
            occupation=occupation,
            personality=personality_traits if personality_traits else None,
            friendly_to_player=True,  # Backstory NPCs know the player
            relationship_role=relationship_role,
            relationship_context=relationship_context,
            brief_appearance=brief_appearance,
        )

        # Generate appearance (using brief_appearance from extraction)
        appearance = self._generate_backstory_appearance(
            gender=gender,
            age=age,
            brief_appearance=brief_appearance,
        )

        # Generate background (incorporating relationship context)
        background = self._generate_backstory_background(
            occupation=occupation,
            age=age,
            relationship_role=relationship_role,
            relationship_context=relationship_context,
            brief_description=brief_description,
            player_name=player_name,
        )

        # Generate personality (using extracted traits)
        personality = self._generate_backstory_personality(
            traits=personality_traits,
            relationship_context=relationship_context,
        )

        # Generate preferences (based on age, gender, personality)
        preferences = self._generate_preferences(gender, age, personality)

        # Generate needs (reasonable defaults for backstory NPCs)
        current_needs = self._generate_backstory_needs(occupation, age)

        # Generate current state (simple defaults)
        current_state = NPCCurrentState(
            current_activity="going about daily routine",
            mood="content",
            current_location="unknown",  # Will be updated when they appear in game
        )

        # Create the full state (no environmental reactions for backstory NPCs)
        npc_state = NPCFullState(
            entity_key=entity_key,
            display_name=name,
            appearance=appearance,
            background=background,
            personality=personality,
            preferences=preferences,
            current_needs=current_needs,
            current_state=current_state,
            environmental_reactions=[],  # No scene yet
            immediate_goals=[],
            behavioral_prediction="",
        )

        # Persist to database
        self._persist_npc(npc_state)

        return npc_state

    def _generate_backstory_appearance(
        self,
        gender: str,
        age: int,
        brief_appearance: str,
    ) -> NPCAppearance:
        """Generate appearance for backstory NPC.

        Uses brief_appearance from extraction and fills in missing details.
        """
        # Parse age description
        if age < 13:
            age_description = "child"
        elif age < 20:
            age_description = "teenager"
        elif age < 30:
            age_description = "young adult"
        elif age < 50:
            age_description = "middle-aged"
        else:
            age_description = "elderly"

        # Height based on age (cm and description)
        if age < 14:
            height_description = "short"
            height_cm = random.randint(100, 150)
            build = "slight"
        elif age < 18:
            height_description = "average"
            height_cm = random.randint(150, 170)
            build = "lean"
        else:
            height_description = random.choice(["short", "average", "average", "tall"])
            height_cm = {
                "short": random.randint(150, 165),
                "average": random.randint(165, 180),
                "tall": random.randint(180, 200),
            }[height_description]
            build = random.choice(["slight", "average", "average", "sturdy", "muscular"])

        # Generate appearance features with some variety
        hair_colors = ["black", "brown", "dark brown", "auburn", "sandy brown", "blonde", "red", "gray"]
        hair_styles = ["short", "long", "braided", "tied back", "loose", "messy", "neat"]
        eye_colors = ["brown", "dark brown", "blue", "green", "hazel", "gray"]
        skin_tones = ["fair", "olive", "tan", "dark", "pale", "weathered"]

        # Adjust for age
        if age > 50:
            hair_colors = ["gray", "silver", "white", "graying brown", "graying black"]

        # Pick random features
        hair = f"{random.choice(hair_colors)}, {random.choice(hair_styles)}"
        eyes = random.choice(eye_colors)
        skin = random.choice(skin_tones)

        # Simple occupation-appropriate clothing
        clothing = "simple peasant clothes"

        # Parse notable features from brief_appearance
        notable_features = []
        if brief_appearance:
            notable_features.append(brief_appearance)

        return NPCAppearance(
            age=age,
            age_description=age_description,
            gender=gender,
            height_cm=height_cm,
            height_description=height_description,
            build=build,
            hair=hair,
            eyes=eyes,
            skin=skin,
            clothing=clothing,
            notable_features=notable_features,
            species="human",  # Default for fantasy setting
        )

    def _generate_backstory_background(
        self,
        occupation: str,
        age: int,
        relationship_role: str,
        relationship_context: str,
        brief_description: str,
        player_name: str,
    ) -> NPCBackground:
        """Generate background for backstory NPC.

        Incorporates relationship context into the background summary.
        """
        # Calculate occupation years
        if occupation.lower() in ["child", "baby", "infant"]:
            occupation_years = 0
        else:
            max_years = max(1, age - 14)
            occupation_years = min(max_years, random.randint(1, 20))

        # Build relationship-aware summary
        if relationship_context:
            summary = f"{relationship_role.title()} of {player_name}. {relationship_context}. {brief_description}"
        else:
            summary = f"{relationship_role.title()} of {player_name}. {brief_description}"

        return NPCBackground(
            occupation=occupation,
            occupation_years=occupation_years,
            birthplace=self._generate_birthplace(),
            family=f"Has connection to {player_name} ({relationship_role})",
            education=self._generate_education(occupation),
            background_summary=summary.strip(),
        )

    def _generate_backstory_personality(
        self,
        traits: list[str],
        relationship_context: str,
    ) -> NPCPersonality:
        """Generate personality for backstory NPC.

        Uses extracted traits and relationship context.
        """
        # Use extracted traits or generate defaults (2-6 traits required)
        if traits:
            personality_traits = traits[:6]
            # Ensure minimum of 2 traits
            if len(personality_traits) < 2:
                personality_traits.extend(["reserved", "practical"][:2 - len(personality_traits)])
        else:
            personality_traits = ["reserved", "practical"]

        # Generate values based on relationship
        values = ["loyalty", "family"]  # Backstory NPCs value their relationship

        # Generate flaws (1-4 required)
        common_flaws = ["stubborn", "impatient", "overly cautious", "too trusting", "proud", "worrier"]
        flaws = [random.choice(common_flaws)]

        # Generate optional quirks based on relationship context
        quirks = []
        if relationship_context:
            quirks.append(f"Acts based on {relationship_context}")

        return NPCPersonality(
            traits=personality_traits,
            values=values,
            flaws=flaws,
            quirks=quirks,
        )

    def _generate_backstory_needs(
        self,
        occupation: str,
        age: int,
    ) -> NPCNeeds:
        """Generate starting needs for backstory NPC.

        Returns reasonable defaults based on role.
        """
        # Children have different need patterns
        if age < 14:
            return NPCNeeds(
                hunger=20,  # Low urgency = well-fed
                thirst=15,
                fatigue=10,  # Kids have energy
                social=15,
                comfort=20,
            )

        # Adults have moderate needs
        return NPCNeeds(
            hunger=25,
            thirst=20,
            fatigue=30,
            social=25,
            comfort=25,
        )

    def _build_minimal_state_from_entity(
        self,
        entity: Entity,
    ) -> NPCFullState:
        """Build minimal NPCFullState from existing entity.

        Used when a backstory NPC already exists in database.
        """
        # Get NPC extension for personality
        npc_ext = (
            self.db.query(NPCExtension)
            .filter(NPCExtension.entity_id == entity.id)
            .first()
        )

        appearance = entity.appearance or {}
        return NPCFullState(
            entity_key=entity.entity_key,
            display_name=entity.display_name,
            appearance=NPCAppearance(
                age=appearance.get("age", 30),
                age_apparent=appearance.get("age_apparent", "adult"),
                gender=appearance.get("gender", "unknown"),
                height=appearance.get("height", "average"),
                build=appearance.get("build", "average"),
                species=appearance.get("species", "human"),
            ),
            background=NPCBackground(
                occupation=entity.occupation or "unknown",
                occupation_years=entity.occupation_years or 1,
                background_summary=entity.background or "",
            ),
            personality=NPCPersonality(
                primary_traits=npc_ext.personality_traits if npc_ext and npc_ext.personality_traits else [],
            ),
            preferences=NPCPreferences(),
            current_needs=NPCNeeds(),
            current_state=NPCCurrentState(
                current_activity="unknown",
                current_mood="neutral",
            ),
            environmental_reactions=None,
            immediate_goals=[],
            behavioral_prediction="",
        )

    def query_npc_reactions(
        self,
        entity_key: str,
        scene_context: SceneContext,
    ) -> NPCReactions | None:
        """Query an existing NPC's reactions to the current scene.

        Use this when the scene changes and you need to know how an
        existing NPC would react.

        Args:
            entity_key: The NPC's entity key
            scene_context: Current scene context

        Returns:
            NPCReactions with updated state and reactions, or None if not found.
        """
        entity = self._get_existing_entity(entity_key)
        if not entity:
            return None

        # Get current needs from database
        needs_record = (
            self.db.query(CharacterNeeds)
            .filter(
                CharacterNeeds.session_id == self.session_id,
                CharacterNeeds.entity_id == entity.id,
            )
            .first()
        )

        # Get preferences for attraction calculation
        prefs_record = (
            self.db.query(CharacterPreferences)
            .filter(
                CharacterPreferences.session_id == self.session_id,
                CharacterPreferences.entity_id == entity.id,
            )
            .first()
        )

        # Build current needs
        # Note: CharacterNeeds uses "high = good" (e.g., hunger 90 = well-fed)
        # NPCNeeds schema uses "high = urgent" (e.g., hunger 90 = very hungry)
        # So we invert all values: urgency = 100 - satisfaction
        # Exception: sleep_pressure is already urgency-based (higher = worse)
        current_needs = NPCNeeds(
            hunger=100 - (needs_record.hunger if needs_record else 70),
            thirst=100 - (needs_record.thirst if needs_record else 70),
            fatigue=needs_record.sleep_pressure if needs_record else 20,  # sleep_pressure already urgency-based
            social=100 - (needs_record.social_connection if needs_record else 60),
            comfort=100 - (needs_record.comfort if needs_record else 70),
            hygiene=100 - (needs_record.hygiene if needs_record else 70),
            morale=100 - (needs_record.morale if needs_record else 65),
            intimacy=100 - (needs_record.intimacy if needs_record else 60),
        )

        # Build preferences for reaction calculation
        preferences = self._preferences_from_record(prefs_record)

        # Get personality from extension
        personality = self._personality_from_entity(entity)

        # Calculate environmental reactions
        environmental_reactions = self._calculate_environmental_reactions(
            preferences=preferences,
            personality=personality,
            current_needs=current_needs,
            scene_context=scene_context,
            npc_age=entity.age or 30,
        )

        # Get current mood
        current_mood = "neutral"
        if entity.npc_extension:
            current_mood = entity.npc_extension.current_mood or "neutral"

        # Generate behavioral prediction
        immediate_goals = self._generate_immediate_goals(
            role=entity.occupation or "unknown",
            current_needs=current_needs,
            environmental_reactions=environmental_reactions,
            personality=personality,
        )

        behavioral_prediction = self._generate_behavioral_prediction(
            personality=personality,
            environmental_reactions=environmental_reactions,
            immediate_goals=immediate_goals,
        )

        return NPCReactions(
            entity_key=entity_key,
            current_needs=current_needs,
            current_mood=current_mood,
            environmental_reactions=environmental_reactions,
            behavioral_prediction=behavioral_prediction,
        )

    # =========================================================================
    # Generation Methods
    # =========================================================================

    def _generate_gender(self, constraints: NPCConstraints | None) -> str:
        """Generate gender, with constraint override."""
        if constraints and constraints.gender:
            return constraints.gender
        return random.choice(["male", "female"])

    def _generate_name(self, gender: str, constraints: NPCConstraints | None) -> str:
        """Generate full name using setting-appropriate name pools.

        Uses the game session's setting to select culturally appropriate names.
        Falls back to fantasy names for unknown settings.

        Args:
            gender: Character's gender (male, female, neutral)
            constraints: Optional constraints that may include a specific name

        Returns:
            Full name string (first name, or first + surname)
        """
        if constraints and constraints.name:
            return constraints.name

        # Get setting-specific name pool
        setting = self.game_session.setting.lower() if self.game_session.setting else "fantasy"
        canonical_setting = _SETTING_NAME_ALIASES.get(setting, "fantasy")
        name_pool_data = NAMES_BY_SETTING.get(canonical_setting, NAMES_BY_SETTING["fantasy"])

        # Pick first name based on gender
        gender_key = gender if gender in name_pool_data else "neutral"
        name_pool = name_pool_data.get(gender_key, name_pool_data.get("neutral", []))

        # Fallback to old NAMES_BY_GENDER if pool is empty
        if not name_pool:
            name_pool = NAMES_BY_GENDER.get(gender, NAMES_BY_GENDER["neutral"])

        first_name = random.choice(name_pool)

        # 70% chance of having a surname
        if random.random() < 0.7:
            surnames = name_pool_data.get("surnames", SURNAMES)
            surname = random.choice(surnames)
            return f"{first_name} {surname}"
        return first_name

    def _generate_entity_key(self, role: str, name: str) -> str:
        """Generate unique entity key."""
        # Clean name for key
        name_clean = name.lower().split()[0]  # First name only
        role_clean = role.lower().replace(" ", "_")
        unique_id = uuid.uuid4().hex[:4]
        return f"{role_clean}_{name_clean}_{unique_id}"

    def _generate_age(self, constraints: NPCConstraints | None, role: str) -> int:
        """Generate age based on constraints and role."""
        if constraints and constraints.age_exact is not None:
            return constraints.age_exact

        if constraints and constraints.age_range:
            min_age, max_age, _ = AGE_RANGES[constraints.age_range]
            return random.randint(min_age, max_age)

        # Default: role-appropriate age
        if role in ("child", "urchin", "apprentice_young"):
            return random.randint(8, 14)
        elif role in ("student", "apprentice"):
            return random.randint(15, 22)
        elif role in ("elder", "sage", "grandmother", "grandfather"):
            return random.randint(60, 80)
        else:
            # Most adults are 20-50
            return random.randint(20, 50)

    def _calculate_height(self, gender: str, age: int) -> int:
        """Calculate height in cm based on gender and age.

        Uses growth percentages to scale child/teen heights appropriately.
        Adults (18+) get full adult height ranges.

        Args:
            gender: "male" or "female"
            age: Character's age in years

        Returns:
            Height in centimeters
        """
        # Adult base heights and variance
        if gender == "female":
            adult_base = 170
            adult_variance = 15
        else:
            adult_base = 180
            adult_variance = 15

        # Calculate what the adult height would be
        adult_height = random.randint(
            adult_base - adult_variance,
            adult_base + adult_variance,
        )

        # Adults (18+) get full height
        if age >= 18:
            return adult_height

        # Children/teens get percentage of adult height based on growth curve
        percentage = GROWTH_PERCENTAGES.get(age, 0.50 if age < 5 else 1.0)
        return int(adult_height * percentage)

    def _generate_appearance(
        self,
        gender: str,
        age: int,
        role: str,
        constraints: NPCConstraints | None,
    ) -> NPCAppearance:
        """Generate physical appearance."""
        # Height based on gender and age
        height_cm = self._calculate_height(gender, age)

        # Build influenced by occupation
        build = self._role_appropriate_build(role)

        # Hair
        hair_color = random.choice(HAIR_COLORS)
        if age > 50 and random.random() < 0.4:
            hair_color = random.choice(["gray", "white", "silver", f"graying {hair_color}"])
        hair_style = random.choice(HAIR_STYLES)

        # Clothing based on role
        clothing = self._role_appropriate_clothing(role, constraints)

        # Notable features (30% chance of having one)
        notable_features = []
        if random.random() < 0.3:
            notable_features.append(self._generate_notable_feature(role))

        # Determine species (from constraints or default to human)
        species = "human"
        if constraints and constraints.species:
            species = constraints.species

        # Generate birthplace region and derive skin color from it
        birthplace_region = self._generate_birthplace()
        skin_color = self._generate_skin_color_from_birthplace(birthplace_region)

        return NPCAppearance(
            age=age,
            gender=gender,
            height_cm=height_cm,
            species=species,
            age_description=age_to_description(age),
            height_description=height_to_description(height_cm, gender),
            build=build,
            hair=f"{hair_color}, {hair_style}",
            eyes=random.choice(EYE_COLORS),
            skin=skin_color,
            notable_features=notable_features,
            clothing=clothing,
            voice=self._generate_voice(gender, age),
        )

    def _role_appropriate_build(self, role: str) -> str:
        """Get appropriate build for role."""
        physical_roles = {"blacksmith", "guard", "soldier", "farmer", "hunter", "laborer"}
        sedentary_roles = {"scholar", "scribe", "merchant", "noble"}

        if role.lower() in physical_roles:
            return random.choice(["muscular", "athletic", "stocky", "wiry"])
        elif role.lower() in sedentary_roles:
            return random.choice(["slender", "average", "heavyset", "soft"])
        else:
            return random.choice(BUILDS)

    def _role_appropriate_clothing(self, role: str, constraints: NPCConstraints | None) -> str:
        """Generate clothing description based on role and wealth."""
        wealth = "modest"
        if constraints and constraints.wealth_level:
            wealth = constraints.wealth_level

        clothing_by_role = {
            "merchant": "well-made merchant's clothes",
            "guard": "guard uniform with city colors",
            "innkeeper": "practical apron over simple clothes",
            "blacksmith": "leather apron, sleeves rolled up",
            "farmer": "worn work clothes, sturdy boots",
            "hunter": "practical hunting leathers",
            "healer": "clean robes with herb stains",
            "scholar": "dusty scholar's robes",
            "noble": "fine clothing with embroidery",
            "servant": "neat servant's livery",
            "beggar": "ragged, patched clothing",
            "herbalist": "simple dress with many pockets",
            "baker": "flour-dusted apron",
        }

        base = clothing_by_role.get(role.lower(), "simple practical clothes")

        if wealth in ("wealthy", "rich"):
            base = base.replace("simple", "fine").replace("worn", "quality")
        elif wealth in ("poor", "destitute"):
            base = base.replace("well-made", "worn").replace("fine", "threadbare")

        return base

    def _generate_notable_feature(self, role: str) -> str:
        """Generate a notable physical feature."""
        features = [
            "small scar on chin",
            "calloused hands from work",
            "missing finger tip",
            "birthmark on neck",
            "crooked nose from old break",
            "laugh lines around eyes",
            "worry lines on forehead",
            "dimples when smiling",
            "prominent freckles",
            "unusual eye color flecks",
        ]

        # Role-specific features
        if role.lower() == "blacksmith":
            features.extend(["burn scars on forearms", "incredibly strong grip"])
        elif role.lower() in ("guard", "soldier"):
            features.extend(["old sword scar", "military bearing"])
        elif role.lower() == "scholar":
            features.extend(["ink-stained fingers", "squinting habit from reading"])

        return random.choice(features)

    def _generate_voice(self, gender: str, age: int) -> str:
        """Generate voice description based on gender and age.

        Handles different voice categories:
        - Children (<10): High, childlike voices
        - Pre-voice-break teens: Youthful, unbroken voices
          - Males: voice breaks around age 15
          - Females: voice breaks around age 13
        - Adults: Full adult voice characteristics
        - Elderly (60+): Age-affected voices

        Args:
            gender: "male" or "female"
            age: Character's age in years

        Returns:
            Voice description string
        """
        voices_male = [
            "deep and resonant", "gravelly", "warm baritone", "quiet and measured",
            "booming", "soft-spoken", "rough from shouting", "melodic",
        ]
        voices_female = [
            "melodic", "warm and inviting", "soft and gentle", "clear and bright",
            "husky", "sharp and precise", "lilting", "quiet but firm",
        ]
        voices_elderly = [
            "thin and reedy", "surprisingly strong", "warm and weathered",
            "crackling", "patient and slow",
        ]

        # Children under 10 have childlike voices regardless of gender
        if age < 10:
            return random.choice(VOICES_CHILD)

        # Pre-voice-break: males ~15, females ~13
        voice_break_age = 15 if gender == "male" else 13
        if age < voice_break_age:
            return random.choice(VOICES_TEEN)

        # Elderly voices
        if age >= 60:
            return random.choice(voices_elderly)

        # Adult voices by gender
        if gender == "female":
            return random.choice(voices_female)
        else:
            return random.choice(voices_male)

    def _generate_occupation_from_llm(
        self,
        role_hint: str,
        setting: str,
        location_context: str,
        age: int,
        gender: str,
        location_key: str | None = None,
    ) -> OccupationDetails:
        """Query LLM for setting-appropriate occupation.

        The LLM generates a contextually appropriate occupation based on the setting,
        location, and character demographics. This replaces hardcoded occupation pools
        to support any setting (fantasy, contemporary, sci-fi, etc.).

        Args:
            role_hint: General role hint like "customer", "worker", "authority figure"
            setting: Setting type like "fantasy", "contemporary", "scifi"
            location_context: Description of location, e.g. "tavern in medieval village"
            age: Character's age (affects occupation appropriateness)
            gender: Character's gender
            location_key: Optional location key for context-aware fallback

        Returns:
            OccupationDetails with occupation, skills, typical_items, education,
            background_summary, and wealth_level.
        """
        # Check if event loop is already running (common in async contexts like LangGraph)
        try:
            asyncio.get_running_loop()
            # Loop is running - use fallback to avoid nested async issues
            logger.debug("Event loop already running, using occupation fallback")
            return self._generate_occupation_fallback(
                role_hint, age, setting, location_key
            )
        except RuntimeError:
            # No running loop - safe to use asyncio.run()
            pass

        try:
            # Run async LLM call in sync context
            return asyncio.run(
                self._generate_occupation_from_llm_async(
                    role_hint, setting, location_context, age, gender
                )
            )
        except Exception as e:
            logger.warning(f"LLM occupation generation failed: {e}, using fallback")
            return self._generate_occupation_fallback(
                role_hint, age, setting, location_key
            )

    async def _generate_occupation_from_llm_async(
        self,
        role_hint: str,
        setting: str,
        location_context: str,
        age: int,
        gender: str,
    ) -> OccupationDetails:
        """Async implementation of LLM occupation generation."""
        # Build the prompt
        prompt = f"""Generate a realistic occupation for a character in an RPG.

Setting: {setting}
Location context: {location_context}
Character: {age}-year-old {gender}
Role hint: {role_hint}

Consider:
- What occupations are common in this setting and location?
- Age-appropriate work (a 12-year-old wouldn't be a lawyer, an 80-year-old probably isn't a construction worker)
- The role hint suggests what they're doing at this location, but their occupation may be different
  (e.g., role_hint="customer" at a tavern could be a farmer, merchant, or off-duty soldier)

Generate occupation details that fit naturally in this setting."""

        provider = get_creative_provider()
        result = await provider.complete_structured(
            prompt=prompt,
            output_schema=OccupationDetails,
            system_prompt=(
                "You are a creative RPG character generator. Generate realistic, "
                "setting-appropriate occupations with relevant skills and items. "
                "Be creative but grounded - occupations should make sense for the "
                "character's age and the setting."
            ),
        )
        return result

    def _generate_occupation_fallback(
        self,
        role_hint: str,
        age: int,
        setting: str,
        location_key: str | None = None,
    ) -> OccupationDetails:
        """Fallback occupation generation when LLM fails.

        Uses hardcoded pools for fantasy setting, generic defaults for others.
        For youth occupations (ages under 18), uses location-aware apprentice
        generation when location_key is provided.

        Args:
            role_hint: Role hint like "customer", "worker"
            age: Character's age
            setting: Setting type (fantasy, contemporary, scifi)
            location_key: Optional location key for context-aware youth roles

        Returns:
            OccupationDetails with occupation, skills, items, etc.
        """
        # For youth, use context-aware apprentice generation
        if age < 18:
            if location_key:
                occupation = self._generate_context_aware_apprentice(location_key, age)
            elif age < 14:
                occupation = random.choice(["child", "youth", "street_urchin"])
            else:
                # Generic fallback for ages 14-17 without location context
                occupation = random.choice(_GENERIC_APPRENTICE_ROLES)
        elif role_hint in OCCUPATION_SKILLS:
            occupation = role_hint
        else:
            # Use common adult occupations
            common_occupations = [
                "merchant", "farmer", "craftsman", "servant", "guard",
                "innkeeper", "baker", "tailor", "hunter",
            ]
            occupation = random.choice(common_occupations)

        # Get skills from pool or use defaults
        skills = OCCUPATION_SKILLS.get(occupation, ["observation", "general labor"])

        # Get items from pool or empty
        items_data = OCCUPATION_INVENTORY.get(occupation, [])
        typical_items = [
            {"name": item.get("display_name", "Item"), "description": item.get("item_type", "misc")}
            for item in items_data
        ]

        # Generate education based on occupation
        education = self._generate_education(occupation)

        # Generate summary
        max_years = max(1, age - 14)
        years = random.randint(1, min(max_years, 20))
        background_summary = self._generate_background_summary(occupation, years)

        # Wealth level based on occupation
        wealthy_occupations = {"noble", "merchant"}
        poor_occupations = {"beggar", "street_urchin", "servant", "farm_hand"}
        if occupation in wealthy_occupations:
            wealth_level = random.choice(["comfortable", "wealthy"])
        elif occupation in poor_occupations:
            wealth_level = random.choice(["destitute", "poor"])
        else:
            wealth_level = random.choice(["poor", "modest", "modest", "comfortable"])

        return OccupationDetails(
            occupation=occupation,
            skills=list(skills),
            typical_items=typical_items,
            education=education,
            background_summary=background_summary,
            wealth_level=wealth_level,
        )

    def _generate_context_aware_apprentice(
        self,
        location_key: str,
        age: int,
    ) -> str:
        """Generate a context-aware apprentice/youth occupation based on location.

        Uses the location key to determine what type of trade or business is nearby,
        then generates an appropriate apprentice or helper role for that trade.

        Args:
            location_key: The key of the current location (e.g., "bakery", "tavern")
            age: Character's age (affects whether they get apprentice vs helper role)

        Returns:
            Context-appropriate occupation string like "baker's apprentice" or "pot boy"
        """
        location_lower = location_key.lower()

        # Try to find a matching location type
        matched_role = None
        for keyword, roles in LOCATION_APPRENTICE_ROLES.items():
            if keyword in location_lower:
                matched_role = roles
                break

        if matched_role:
            apprentice_role, young_role = matched_role
            # Age 14+ gets apprentice role, younger gets helper role
            return apprentice_role if age >= 14 else young_role

        # Fallback: generic youth roles
        if age < 14:
            return random.choice(_GENERIC_YOUNG_ROLES)
        return random.choice(_GENERIC_APPRENTICE_ROLES)

    def _generate_background(
        self,
        role: str,
        age: int,
        gender: str,
        scene_context: SceneContext,
        constraints: NPCConstraints | None,
    ) -> NPCBackground:
        """Generate backstory and history using LLM for occupation.

        Args:
            role: Role hint like "customer", "worker", "guard"
            age: Character's age
            gender: Character's gender
            scene_context: Current scene context for location info
            constraints: Optional hard requirements (may include specific occupation)

        Returns:
            NPCBackground with LLM-generated or fallback occupation details.
        """
        # If occupation is constrained, use it directly with fallback generation
        if constraints and constraints.occupation:
            occupation_details = self._generate_occupation_fallback(
                constraints.occupation, age, self.game_session.setting
            )
            # Override with constrained occupation name
            occupation = constraints.occupation
        else:
            # Use LLM to generate occupation based on context
            setting = self.game_session.setting
            location_context = (
                f"{scene_context.location_description} "
                f"(location: {scene_context.location_key})"
            )
            occupation_details = self._generate_occupation_from_llm(
                role_hint=role,
                setting=setting,
                location_context=location_context,
                age=age,
                gender=gender,
                location_key=scene_context.location_key,
            )
            occupation = occupation_details.occupation

        # Calculate years in occupation (proportional to age)
        max_years = max(1, age - 14)  # Can't work before ~14
        occupation_years = random.randint(1, min(max_years, 30))

        return NPCBackground(
            occupation=occupation,
            occupation_years=occupation_years,
            birthplace=self._generate_birthplace(),
            family=self._generate_family_situation(age),
            education=occupation_details.education or self._generate_education(occupation),
            background_summary=occupation_details.background_summary,
        )

    def _generate_birthplace(
        self,
        local_region: str | None = None,
        regions: dict | None = None,
    ) -> str:
        """Generate birthplace region.

        Most NPCs (85-90%) are born locally, with a small percentage (10-15%)
        being migrants from other regions.

        Args:
            local_region: The local region where the NPC is located.
                If None, uses a default based on setting.
            regions: Dictionary of region name to RegionCulture.
                If None, uses regions for the current setting.

        Returns:
            Region name (e.g., "Northern Europe", "Central Plains")
        """
        from src.schemas.regions import get_default_region_for_setting, get_regions_for_setting

        # Get setting from game session if available
        setting = "fantasy"  # Default
        if self.game_session and hasattr(self.game_session, 'setting_type'):
            setting = self.game_session.setting_type or "fantasy"

        # Use provided regions or get from setting
        if regions is None:
            regions = get_regions_for_setting(setting)

        # Use provided local region or get default for setting
        if local_region is None:
            local_region = get_default_region_for_setting(setting)

        # Ensure local_region is valid
        if local_region not in regions:
            local_region = get_default_region_for_setting(setting)

        # 87% chance of being local, 13% chance of being a migrant
        if random.random() < 0.87:
            return local_region
        else:
            # Migrant from another region
            other_regions = [r for r in regions if r != local_region]
            if other_regions:
                return random.choice(other_regions)
            return local_region

    def _generate_skin_color_from_birthplace(
        self,
        birthplace: str,
        regions: dict | None = None,
    ) -> str:
        """Generate skin color based on birthplace region demographics.

        Uses weighted random selection based on the region's skin color
        distribution.

        Args:
            birthplace: Region name (e.g., "Northern Europe")
            regions: Dictionary of region name to RegionCulture.
                If None, uses regions for the current setting.

        Returns:
            Skin color string (e.g., "fair", "olive", "dark brown")
        """
        from src.schemas.regions import get_regions_for_setting

        # Get setting from game session if available
        setting = "fantasy"  # Default
        if self.game_session and hasattr(self.game_session, 'setting_type'):
            setting = self.game_session.setting_type or "fantasy"

        # Use provided regions or get from setting
        if regions is None:
            regions = get_regions_for_setting(setting)

        # Get region culture
        region_culture = regions.get(birthplace)
        if region_culture is None:
            # Fallback to random skin tone
            return random.choice(SKIN_TONES)

        # Weighted random selection
        colors = list(region_culture.skin_color_weights.keys())
        weights = list(region_culture.skin_color_weights.values())
        return random.choices(colors, weights=weights, k=1)[0]

    def _generate_family_situation(self, age: int) -> str:
        """Generate family situation based on age."""
        if age < 18:
            situations = [
                "lives with parents", "orphaned young", "raised by grandparents",
                "large family with many siblings", "only child",
            ]
        elif age < 25:
            situations = [
                "lives with parents", "large family with many siblings",
                "married with children", "single", "widowed", "divorced",
                "engaged", "married, no children", "caring for aging parents",
            ]
        elif age < 40:
            situations = [
                "married with children", "single", "widowed", "divorced",
                "engaged", "married, no children", "caring for aging parents",
            ]
        else:
            situations = [
                "grown children", "widowed", "longtime spouse",
                "estranged from family", "large extended family",
                "no living relatives", "doting grandparent",
            ]
        return random.choice(situations)

    def _generate_education(self, occupation: str) -> str:
        """Generate education/training."""
        educated_roles = {"scholar", "noble", "priest", "healer", "merchant"}
        apprentice_roles = {"blacksmith", "tailor", "baker", "craftsman"}

        if occupation.lower() in educated_roles:
            return random.choice(["formally educated", "tutored privately", "self-taught scholar"])
        elif occupation.lower() in apprentice_roles:
            return f"apprenticed as {occupation}"
        else:
            return random.choice(["no formal education", "basic literacy", "learned from family"])

    def _generate_background_summary(self, occupation: str, years: int) -> str:
        """Generate a brief public background summary."""
        summaries = [
            f"A {occupation} for {years} years, known for hard work",
            f"Has worked as a {occupation} since youth",
            f"Came to town {years} years ago to work as a {occupation}",
            f"Third generation {occupation} following family tradition",
            f"Former adventurer turned {occupation}",
            f"Started as an apprentice, now an experienced {occupation}",
        ]
        return random.choice(summaries)

    def _generate_personality(self, constraints: NPCConstraints | None) -> NPCPersonality:
        """Generate personality with emergent traits."""
        # Use constrained traits or generate randomly
        if constraints and constraints.personality:
            traits = constraints.personality[:6]  # Max 6 traits
        else:
            num_traits = random.randint(3, 5)
            traits = random.sample(PERSONALITY_TRAITS, num_traits)

        # Generate values (2-4)
        num_values = random.randint(2, 4)
        values = random.sample(VALUES, num_values)

        # Generate flaws (1-3)
        num_flaws = random.randint(1, 3)
        flaws = random.sample(FLAWS, num_flaws)

        # Maybe add quirks (50% chance)
        quirks = []
        if random.random() < 0.5:
            quirks = random.sample(QUIRKS, random.randint(1, 2))

        return NPCPersonality(
            traits=traits,
            values=values,
            flaws=flaws,
            quirks=quirks,
            speech_pattern=self._generate_speech_pattern(traits),
        )

    def _generate_speech_pattern(self, traits: list[str]) -> str | None:
        """Generate speech pattern based on traits."""
        patterns = []

        if "shy" in traits:
            patterns.append("speaks softly, often trails off")
        if "confident" in traits:
            patterns.append("speaks with authority")
        if "nervous" in traits or "anxious" in traits:
            patterns.append("tends to ramble when nervous")
        if "witty" in traits:
            patterns.append("peppers speech with wordplay")
        if "serious" in traits:
            patterns.append("rarely jokes")

        if patterns:
            return random.choice(patterns)
        return None

    def _generate_gender_attraction(self, npc_gender: str) -> list[str]:
        """Generate attracted-to genders with realistic probability distribution.

        Delegates to shared preference_calculator module.

        Args:
            npc_gender: The NPC's gender.

        Returns:
            List of genders the NPC is attracted to.
        """
        return generate_gender_attraction(npc_gender)

    def _generate_age_offset(self, npc_age: int) -> int:
        """Generate fixed age preference offset at character creation.

        Delegates to shared preference_calculator module.

        Args:
            npc_age: The NPC's age.

        Returns:
            Integer offset from NPC's age to their preferred partner age.
            Example: offset=5 means NPC prefers partners 5 years older.
        """
        return generate_age_offset(npc_age)

    def _generate_preferences(
        self,
        gender: str,
        age: int,
        personality: NPCPersonality,
    ) -> NPCPreferences:
        """Generate preferences including attraction traits.

        Delegates to shared preference_calculator module and converts
        to NPCPreferences Pydantic model.

        Args:
            gender: NPC's gender for attraction generation.
            age: NPC's age for age-attraction preferences.
            personality: NPC's personality traits (currently unused but kept for API).

        Returns:
            NPCPreferences with all preference fields populated.
        """
        # Generate preferences using shared calculator
        prefs = generate_preferences(gender, age)

        # Convert dataclass to Pydantic model
        return NPCPreferences(
            attracted_to_genders=prefs.attracted_to_genders,
            attracted_age_offset=prefs.attracted_age_offset,
            attracted_to_physical=prefs.attracted_to_physical,
            attracted_to_personality=prefs.attracted_to_personality,
            favorite_foods=prefs.favorite_foods,
            disliked_foods=prefs.disliked_foods,
            is_vegetarian=prefs.is_vegetarian,
            is_vegan=prefs.is_vegan,
            food_allergies=prefs.food_allergies,
            is_greedy_eater=prefs.is_greedy_eater,
            is_picky_eater=prefs.is_picky_eater,
            favorite_drinks=prefs.favorite_drinks,
            disliked_drinks=prefs.disliked_drinks,
            is_alcoholic=prefs.is_alcoholic,
            is_teetotaler=prefs.is_teetotaler,
            favorite_activities=prefs.favorite_activities,
            dislikes=prefs.dislikes,
            fears=prefs.fears,
            drive_level=prefs.drive_level,
            drive_threshold=prefs.drive_threshold,
            has_regular_partner=prefs.has_regular_partner,
            is_actively_seeking=prefs.is_actively_seeking,
            has_high_stamina=prefs.has_high_stamina,
            has_low_stamina=prefs.has_low_stamina,
            is_insomniac=prefs.is_insomniac,
            is_heavy_sleeper=prefs.is_heavy_sleeper,
        )

    def _generate_needs(
        self,
        role: str,
        scene_context: SceneContext,
    ) -> NPCNeeds:
        """Generate current need levels based on context."""
        # Base needs (inverted - higher = more urgent)
        needs = {
            "hunger": 30,
            "thirst": 30,
            "fatigue": 20,
            "social": 40,
            "comfort": 30,
            "hygiene": 30,
            "morale": 30,
            "intimacy": 30,
        }

        # Time-based adjustments
        if scene_context.time_of_day:
            time_str = scene_context.time_of_day.lower()
            if "morning" in time_str or "6" in time_str or "7" in time_str or "8" in time_str:
                needs["hunger"] = random.randint(40, 60)  # Needs breakfast
            elif "noon" in time_str or "12" in time_str or "13" in time_str:
                needs["hunger"] = random.randint(50, 70)  # Lunch time
            elif "evening" in time_str or "18" in time_str or "19" in time_str:
                needs["hunger"] = random.randint(50, 70)
                needs["fatigue"] = random.randint(40, 60)
            elif "night" in time_str or any(h in time_str for h in ["21", "22", "23"]):
                needs["fatigue"] = random.randint(60, 80)

        # Role adjustments
        physical_roles = {"blacksmith", "guard", "soldier", "farmer", "hunter", "laborer"}
        if role.lower() in physical_roles:
            needs["fatigue"] = min(100, needs["fatigue"] + random.randint(10, 30))
            needs["thirst"] = min(100, needs["thirst"] + random.randint(10, 20))

        # Environment adjustments
        if scene_context.environment:
            env_lower = [e.lower() for e in scene_context.environment]
            if any("hot" in e or "warm" in e for e in env_lower):
                needs["thirst"] = min(100, needs["thirst"] + 20)
            if any("cold" in e for e in env_lower):
                needs["comfort"] = min(100, needs["comfort"] + 20)
            if any("smell" in e and ("food" in e or "bread" in e) for e in env_lower):
                needs["hunger"] = min(100, needs["hunger"] + 15)

        # Add some randomness
        for key in needs:
            needs[key] = max(0, min(100, needs[key] + random.randint(-10, 10)))

        return NPCNeeds(**needs)

    def _generate_current_state(
        self,
        role: str,
        location_key: str,
        scene_context: SceneContext,
    ) -> NPCCurrentState:
        """Generate current situational state."""
        # Generate mood
        moods = [
            "neutral", "content", "bored", "busy", "distracted",
            "pleasant", "tired but functional", "alert", "relaxed",
        ]
        mood = random.choice(moods)

        # Generate activity based on role and location
        activity = self._generate_activity(role, location_key)

        return NPCCurrentState(
            mood=mood,
            health="healthy",
            conditions=[],
            current_activity=activity,
            current_location=location_key,
        )

    def _generate_activity(self, role: str, location_key: str) -> str:
        """Generate current activity."""
        activities_by_role = {
            "merchant": ["organizing wares", "counting coins", "helping a customer", "restocking shelves"],
            "guard": ["patrolling", "watching the area", "checking papers", "standing watch"],
            "innkeeper": ["cleaning mugs", "serving drinks", "chatting with patrons", "checking rooms"],
            "blacksmith": ["hammering metal", "stoking the forge", "examining a piece", "talking to a customer"],
            "customer": ["browsing wares", "looking at goods", "shopping", "comparing prices"],
            "herbalist": ["sorting herbs", "preparing remedies", "consulting notes", "helping someone"],
        }

        activities = activities_by_role.get(role.lower(), [
            "going about their business", "waiting", "looking around", "passing through"
        ])
        return random.choice(activities)

    # =========================================================================
    # Environmental Reaction Calculation
    # =========================================================================

    def _calculate_environmental_reactions(
        self,
        preferences: NPCPreferences,
        personality: NPCPersonality,
        current_needs: NPCNeeds,
        scene_context: SceneContext,
        npc_age: int,
        constraints: NPCConstraints | None = None,
    ) -> list[EnvironmentalReaction]:
        """Calculate NPC's reactions to things in the environment.

        Args:
            preferences: NPC's preferences.
            personality: NPC's personality traits.
            current_needs: NPC's current need levels.
            scene_context: Context about the current scene.
            npc_age: NPC's age for attraction calculations.
            constraints: Optional constraints that may force attraction.

        Returns:
            List of environmental reactions.
        """
        reactions = []

        # Check player if present
        if scene_context.player_visible_state:
            player_reaction = self._calculate_player_reaction(
                preferences=preferences,
                personality=personality,
                player_state=scene_context.player_visible_state,
                npc_age=npc_age,
                constraints=constraints,
            )
            if player_reaction:
                reactions.append(player_reaction)

        # Check visible items for need triggers
        for item in scene_context.visible_items:
            item_reaction = self._calculate_item_reaction(
                item=item,
                current_needs=current_needs,
                personality=personality,
                preferences=preferences,
            )
            if item_reaction:
                reactions.append(item_reaction)

        # Check environment for reactions
        for env_factor in scene_context.environment:
            env_reaction = self._calculate_environment_reaction(
                factor=env_factor,
                current_needs=current_needs,
                preferences=preferences,
            )
            if env_reaction:
                reactions.append(env_reaction)

        return reactions

    def _calculate_age_decay_rate(self, npc_age: int) -> float:
        """Calculate age-relative decay rate for attraction falloff.

        Younger NPCs are pickier about age gaps - a 5-year gap means more
        to an 18yo than to a 60yo.

        Formula: decay_rate = 0.1 * (40 / npc_age), clamped to [0.03, 0.30]

        Examples:
            - 18yo: decay_rate = 0.22 (5yr gap → 33% attraction)
            - 25yo: decay_rate = 0.16 (5yr gap → 45% attraction)
            - 40yo: decay_rate = 0.10 (5yr gap → 61% attraction)
            - 60yo: decay_rate = 0.07 (5yr gap → 72% attraction)

        Args:
            npc_age: The NPC's age.

        Returns:
            Decay rate between 0.03 and 0.30.
        """
        raw = 0.1 * (40 / max(npc_age, 15))
        return max(0.03, min(0.30, raw))

    # Perfect match range: +/- this many years from preferred age = 100% attraction
    PERFECT_MATCH_RANGE = 2

    def _calculate_age_attraction_factor(
        self,
        npc_age: int,
        player_age: int,
        offset: int,
    ) -> float:
        """Calculate age-based attraction factor (0.02 to 1.0).

        Uses age-relative decay - younger NPCs are pickier about age gaps.
        A small "perfect match" range (+/-2 years) gives 100% before decay starts.

        Example: 30yo NPC with offset=5 → prefers 35yo
        - 33-37yo: 1.0 (within +/-2 perfect match range)
        - 40yo: decay based on 3 years outside (40-37=3)

        Args:
            npc_age: The NPC's age.
            player_age: The player's age.
            offset: Offset from NPC's age to preferred age center.

        Returns:
            Float from 0.02 to 1.0 representing age compatibility.
        """
        preferred_age = npc_age + offset
        raw_distance = abs(player_age - preferred_age)

        # Perfect match within +/-2 years
        if raw_distance <= self.PERFECT_MATCH_RANGE:
            return 1.0

        # Decay starts after the flat zone
        distance = raw_distance - self.PERFECT_MATCH_RANGE
        decay_rate = self._calculate_age_decay_rate(npc_age)
        factor = math.exp(-decay_rate * distance)

        # Floor at 0.02 (never completely zero, just very unlikely)
        return max(0.02, factor)

    def _calculate_player_reaction(
        self,
        preferences: NPCPreferences,
        personality: NPCPersonality,
        player_state: PlayerSummary,
        npc_age: int,
        constraints: NPCConstraints | None = None,
    ) -> EnvironmentalReaction | None:
        """Calculate NPC's reaction to the player.

        Args:
            preferences: NPC's preferences including attraction preferences.
            personality: NPC's personality traits.
            player_state: Visible state of the player.
            npc_age: The NPC's age for age-based attraction calculation.
            constraints: Optional constraints that may force attraction.

        Returns:
            EnvironmentalReaction if attraction is notable, None otherwise.
        """
        # Extract player info from appearance summary
        # Try to detect gender and age from appearance description
        appearance_lower = player_state.appearance_summary.lower()

        # Simple gender detection from appearance
        player_gender = "unknown"
        if any(word in appearance_lower for word in ["man", "male", "boy", "he ", "his "]):
            player_gender = "male"
        elif any(word in appearance_lower for word in ["woman", "female", "girl", "she ", "her "]):
            player_gender = "female"

        # Check gender compatibility (unless forced by constraints)
        if constraints and constraints.attracted_to_player:
            pass  # Skip gender check if attraction is forced
        elif player_gender != "unknown" and player_gender not in preferences.attracted_to_genders:
            # Not attracted to this gender at all - no reaction
            return None

        # Calculate physical match
        physical_match = self._calculate_trait_match(
            player_state.appearance_summary,
            preferences.attracted_to_physical,
        )

        # For personality, we'd need more info about player behavior
        # For now, use a random factor that could be refined
        personality_match = random.uniform(0.2, 0.6)

        # Check if attraction is forced by constraints
        if constraints and constraints.attracted_to_player:
            physical_match = max(physical_match, 0.6)
            personality_match = max(personality_match, 0.5)

        # Calculate base attraction (physical 40%, personality 60%)
        base_attraction = physical_match * 0.4 + personality_match * 0.6

        # Apply age-based attraction factor
        # Try to extract player age from appearance (default to 25 if unknown)
        player_age = 25
        age_match = re.search(r'\b(\d{1,2})\s*(?:year|yo|years old)', appearance_lower)
        if age_match:
            player_age = int(age_match.group(1))

        # Skip age factor if attraction is forced by constraints
        if constraints and constraints.attracted_to_player:
            age_factor = 1.0  # No age penalty when attraction is forced
        else:
            age_factor = self._calculate_age_attraction_factor(
                npc_age=npc_age,
                player_age=player_age,
                offset=preferences.attracted_age_offset,
            )

        # Combine scores: age factor MULTIPLIES the base score
        overall = base_attraction * age_factor

        # Only create attraction reaction if notable
        if overall < 0.3:
            return None

        attraction_score = AttractionScore(
            physical=round(physical_match, 2),
            personality=round(personality_match, 2),
            overall=round(overall, 2),
        )

        # Generate internal thought based on attraction level
        if overall > 0.7:
            thought = random.choice([
                "My heart skipped a beat...",
                "They're quite attractive...",
                "I can't help but stare...",
            ])
            behavior = "clearly interested, may initiate contact"
        elif overall > 0.5:
            thought = random.choice([
                "They seem interesting...",
                "Not bad looking...",
                "I wonder who they are...",
            ])
            behavior = "shows subtle interest, might be open to conversation"
        else:
            thought = "They seem decent enough"
            behavior = "neutral but not uninterested"

        # Modify behavior based on drive_level
        drive_level = preferences.drive_level
        if drive_level == "high":
            # More likely to act on attraction
            if overall > 0.5:
                behavior = "noticeably interested, may find excuses to interact"
        elif drive_level == "low":
            # Suppresses attraction behavior
            behavior = behavior.replace("initiate contact", "admire from afar")
            behavior = behavior.replace("clearly interested", "quietly appreciative")

        # Further modify behavior based on personality
        if "shy" in personality.traits:
            behavior = behavior.replace("initiate contact", "hope they approach")
            behavior = behavior.replace("might be open", "would be flattered by")
            behavior = behavior.replace("find excuses to interact", "steal glances")

        # Modify based on partnership status
        if preferences.has_regular_partner:
            if overall > 0.5:
                thought = random.choice([
                    "Attractive, but I'm spoken for...",
                    "Can't help but notice them, but I'm committed...",
                ])
                behavior = "appreciates looks but maintains distance"

        return EnvironmentalReaction(
            notices="the stranger (player)",
            reaction_type="attraction",
            attraction_score=attraction_score,
            internal_thought=thought,
            likely_behavior=behavior,
        )

    def _calculate_trait_match(self, description: str, preferred_traits: list[str]) -> float:
        """Calculate how well a description matches preferred traits."""
        if not description or not preferred_traits:
            return random.uniform(0.2, 0.5)  # Default moderate

        description_lower = description.lower()
        matches = sum(1 for trait in preferred_traits if trait.lower() in description_lower)

        # Base score from matches + some randomness
        base_score = min(1.0, matches * 0.25)
        random_factor = random.uniform(-0.15, 0.25)

        return max(0.0, min(1.0, base_score + random_factor))

    def _calculate_item_reaction(
        self,
        item: VisibleItem,
        current_needs: NPCNeeds,
        personality: NPCPersonality,
        preferences: NPCPreferences,
    ) -> EnvironmentalReaction | None:
        """Calculate reaction to a visible item.

        Args:
            item: The visible item.
            current_needs: NPC's current need levels.
            personality: NPC's personality traits.
            preferences: NPC's preferences including favorite/disliked foods.

        Returns:
            EnvironmentalReaction if item triggers a reaction, None otherwise.
        """
        item_lower = item.display_name.lower()
        description_lower = item.brief_description.lower()

        # Check for favorite foods - creates STRONG reactions even at lower hunger
        for fav_food in preferences.favorite_foods:
            if fav_food.lower() in item_lower or fav_food.lower() in description_lower:
                # Favorite foods trigger at lower hunger threshold
                if current_needs.hunger > 30:
                    intensity = "strong" if current_needs.hunger > 50 else "moderate"
                    return EnvironmentalReaction(
                        notices=item.display_name,
                        reaction_type="need_triggered",
                        need_triggered="hunger",
                        intensity=intensity,
                        internal_thought=f"Oh! {fav_food}... I love that!",
                        likely_behavior="eyes light up, visibly tempted",
                    )

        # Check for disliked foods - creates negative reaction
        for disliked_food in preferences.disliked_foods:
            if disliked_food.lower() in item_lower or disliked_food.lower() in description_lower:
                return EnvironmentalReaction(
                    notices=item.display_name,
                    reaction_type="discomfort",
                    internal_thought=f"Ugh, {disliked_food}... not my thing",
                    likely_behavior="slight grimace, looks away",
                )

        # Check for food allergies
        for allergy in preferences.food_allergies:
            if allergy.lower() in item_lower or allergy.lower() in description_lower:
                return EnvironmentalReaction(
                    notices=item.display_name,
                    reaction_type="discomfort",
                    internal_thought=f"Can't have that - allergic to {allergy}",
                    likely_behavior="avoids item, may mention allergy if offered",
                )

        # Generic food items
        if any(word in item_lower or word in description_lower
               for word in ["food", "bread", "meat", "fruit", "cake"]):
            # Check vegetarian/vegan preferences
            if preferences.is_vegetarian and any(
                meat in item_lower for meat in ["meat", "chicken", "beef", "pork", "fish"]
            ):
                return EnvironmentalReaction(
                    notices=item.display_name,
                    reaction_type="discomfort",
                    internal_thought="That's meat... I don't eat that",
                    likely_behavior="politely declines if offered",
                )

            if current_needs.hunger > 50:
                intensity = self._need_to_intensity(current_needs.hunger)
                thought = "That looks delicious..." if current_needs.hunger > 70 else "Food..."
                if preferences.is_greedy_eater:
                    thought = "I could definitely eat right now..."
                elif preferences.is_picky_eater:
                    thought = "Hmm, I wonder if that's any good..."
                return EnvironmentalReaction(
                    notices=item.display_name,
                    reaction_type="need_triggered",
                    need_triggered="hunger",
                    intensity=intensity,
                    internal_thought=thought,
                    likely_behavior=self._hunger_behavior(current_needs.hunger, personality),
                )

        # Check for favorite drinks
        for fav_drink in preferences.favorite_drinks:
            if fav_drink.lower() in item_lower or fav_drink.lower() in description_lower:
                if current_needs.thirst > 30:
                    intensity = "strong" if current_needs.thirst > 50 else "moderate"
                    return EnvironmentalReaction(
                        notices=item.display_name,
                        reaction_type="need_triggered",
                        need_triggered="thirst",
                        intensity=intensity,
                        internal_thought=f"Oh, {fav_drink}! My favorite!",
                        likely_behavior="perks up, clearly interested",
                    )

        # Check for disliked drinks
        for disliked_drink in preferences.disliked_drinks:
            if disliked_drink.lower() in item_lower or disliked_drink.lower() in description_lower:
                return EnvironmentalReaction(
                    notices=item.display_name,
                    reaction_type="discomfort",
                    internal_thought=f"Not a fan of {disliked_drink}...",
                    likely_behavior="shows disinterest",
                )

        # Generic drink items
        if any(word in item_lower or word in description_lower
               for word in ["water", "drink", "ale", "wine", "bottle", "mead", "cider"]):
            # Check for alcohol-specific reactions
            is_alcoholic_drink = any(
                alc in item_lower for alc in ["ale", "wine", "mead", "whiskey", "rum", "beer"]
            )

            if is_alcoholic_drink:
                if preferences.is_teetotaler:
                    return EnvironmentalReaction(
                        notices=item.display_name,
                        reaction_type="discomfort",
                        internal_thought="I don't drink alcohol",
                        likely_behavior="politely declines if offered",
                    )
                if preferences.is_alcoholic and current_needs.thirst > 20:
                    return EnvironmentalReaction(
                        notices=item.display_name,
                        reaction_type="need_triggered",
                        need_triggered="thirst",
                        intensity="strong",
                        internal_thought="I could really use a drink right now...",
                        likely_behavior="eyeing the drink intently, may ask for one",
                    )

            if current_needs.thirst > 50:
                intensity = self._need_to_intensity(current_needs.thirst)
                return EnvironmentalReaction(
                    notices=item.display_name,
                    reaction_type="need_triggered",
                    need_triggered="thirst",
                    intensity=intensity,
                    internal_thought="I could really use a drink..." if current_needs.thirst > 70 else "That looks refreshing",
                    likely_behavior=self._thirst_behavior(current_needs.thirst, personality),
                )

        return None

    def _need_to_intensity(self, need_level: int) -> str:
        """Convert need level to intensity string."""
        if need_level >= 80:
            return "overwhelming"
        elif need_level >= 60:
            return "strong"
        elif need_level >= 40:
            return "moderate"
        else:
            return "mild"

    def _hunger_behavior(self, hunger: int, personality: NPCPersonality) -> str:
        """Generate behavior prediction for hunger."""
        if hunger >= 80:
            if "shy" in personality.traits:
                return "stomach growling audibly, looking embarrassed"
            return "likely to ask about food or buy some"
        elif hunger >= 60:
            return "keeps glancing at food, might mention being hungry"
        else:
            return "notices food but not urgently"

    def _thirst_behavior(self, thirst: int, personality: NPCPersonality) -> str:
        """Generate behavior prediction for thirst."""
        if thirst >= 80:
            if "shy" in personality.traits:
                return "keeps licking lips, eyeing drink hopefully"
            return "likely to ask for a drink or buy one"
        elif thirst >= 60:
            return "keeps glancing at drink"
        else:
            return "notices drink but not urgently"

    def _calculate_environment_reaction(
        self,
        factor: str,
        current_needs: NPCNeeds,
        preferences: NPCPreferences,
    ) -> EnvironmentalReaction | None:
        """Calculate reaction to environmental factor."""
        factor_lower = factor.lower()

        # Smell of food
        if "smell" in factor_lower and any(
            food in factor_lower for food in ["bread", "food", "cooking", "baking"]
        ):
            if current_needs.hunger > 40:
                return EnvironmentalReaction(
                    notices=factor,
                    reaction_type="need_triggered",
                    need_triggered="hunger",
                    intensity=self._need_to_intensity(current_needs.hunger),
                    internal_thought="That smells wonderful...",
                    likely_behavior="mouth watering, distracted by smell",
                )

        # Comfortable environment
        if any(word in factor_lower for word in ["warm", "cozy", "comfortable"]):
            return EnvironmentalReaction(
                notices=factor,
                reaction_type="comfort",
                internal_thought="This is nice...",
                likely_behavior="relaxes slightly, seems at ease",
            )

        return None

    # =========================================================================
    # Goal Generation
    # =========================================================================

    def _generate_immediate_goals(
        self,
        role: str,
        current_needs: NPCNeeds,
        environmental_reactions: list[EnvironmentalReaction],
        personality: NPCPersonality,
    ) -> list[ImmediateGoal]:
        """Generate immediate goals based on situation."""
        goals = []

        # Primary goal from role
        role_goals = {
            "merchant": "complete current transaction",
            "customer": "find what they're looking for",
            "guard": "maintain security",
            "innkeeper": "serve customers",
            "blacksmith": "finish current work",
            "herbalist": "prepare remedies",
        }
        primary = role_goals.get(role.lower(), "go about their business")
        goals.append(ImmediateGoal(goal=primary, priority="primary"))

        # Urgent needs become goals
        if current_needs.thirst >= 70:
            goals.append(ImmediateGoal(goal="get something to drink", priority="urgent"))
        if current_needs.hunger >= 70:
            goals.append(ImmediateGoal(goal="find something to eat", priority="urgent"))
        if current_needs.fatigue >= 80:
            goals.append(ImmediateGoal(goal="find a place to rest", priority="urgent"))

        # Opportunity goals from reactions
        for reaction in environmental_reactions:
            if reaction.reaction_type == "attraction" and reaction.attraction_score:
                if reaction.attraction_score.overall > 0.5:
                    if "shy" in personality.traits:
                        goals.append(ImmediateGoal(
                            goal="work up courage to talk to interesting stranger",
                            priority="opportunity"
                        ))
                    else:
                        goals.append(ImmediateGoal(
                            goal="find excuse to talk to interesting stranger",
                            priority="opportunity"
                        ))

        return goals[:4]  # Limit to 4 goals

    def _generate_behavioral_prediction(
        self,
        personality: NPCPersonality,
        environmental_reactions: list[EnvironmentalReaction],
        immediate_goals: list[ImmediateGoal],
    ) -> str:
        """Generate behavioral prediction for GM guidance."""
        parts = []

        # Check for urgent needs
        urgent_goals = [g for g in immediate_goals if g.priority == "urgent"]
        if urgent_goals:
            parts.append(f"Urgently needs to {urgent_goals[0].goal}")

        # Check for attraction
        attraction_reactions = [r for r in environmental_reactions if r.reaction_type == "attraction"]
        if attraction_reactions and attraction_reactions[0].attraction_score:
            score = attraction_reactions[0].attraction_score
            if score.overall > 0.6:
                if "shy" in personality.traits:
                    parts.append("Attracted to player but too shy to act directly")
                else:
                    parts.append("Noticeably attracted, likely to be friendly")
            elif score.overall > 0.4:
                parts.append("Mildly interested in player")

        # Personality-based prediction
        if "suspicious" in personality.traits:
            parts.append("Will be cautious with strangers")
        if "friendly" in personality.traits:
            parts.append("Naturally inclined to be welcoming")
        if "nervous" in personality.traits or "anxious" in personality.traits:
            parts.append("May seem fidgety or uneasy")

        if not parts:
            parts.append("Will behave according to role and situation")

        return ". ".join(parts)

    # =========================================================================
    # Persistence
    # =========================================================================

    def _persist_npc(self, npc_state: NPCFullState) -> Entity:
        """Persist NPC to database."""
        # Create entity
        entity = Entity(
            session_id=self.session_id,
            entity_key=npc_state.entity_key,
            display_name=npc_state.display_name,
            entity_type=EntityType.NPC,
            is_alive=True,
            is_active=True,
            # Appearance
            age=npc_state.appearance.age,
            age_apparent=npc_state.appearance.age_description,
            gender=npc_state.appearance.gender,
            height=f"{npc_state.appearance.height_cm}cm",
            build=npc_state.appearance.build,
            hair_color=npc_state.appearance.hair.split(",")[0] if "," in npc_state.appearance.hair else npc_state.appearance.hair,
            hair_style=npc_state.appearance.hair.split(",")[1].strip() if "," in npc_state.appearance.hair else None,
            eye_color=npc_state.appearance.eyes,
            skin_tone=npc_state.appearance.skin,
            species=npc_state.appearance.species,
            distinguishing_features=", ".join(npc_state.appearance.notable_features) if npc_state.appearance.notable_features else None,
            voice_description=npc_state.appearance.voice,
            # Background
            background=npc_state.background.background_summary,
            personality_notes=", ".join(npc_state.personality.traits),
            hidden_backstory=npc_state.background.hidden_backstory,
            occupation=npc_state.background.occupation,
            occupation_years=npc_state.background.occupation_years,
        )
        self.db.add(entity)
        self.db.flush()

        # Create NPC extension
        # Set workplace to where NPC was generated (their work location)
        # Set home_location for occupations that typically live on-site
        generation_location = npc_state.current_state.current_location
        occupation_lower = npc_state.background.occupation.lower() if npc_state.background.occupation else ""

        # Occupations that typically live at their workplace
        residential_occupations = {
            "farmer", "innkeeper", "miller", "blacksmith", "baker",
            "shepherd", "fisherman", "lighthouse keeper", "hermit",
            "caretaker", "servant", "cook", "stable hand", "farmhand",
        }
        is_residential = any(occ in occupation_lower for occ in residential_occupations)

        extension = NPCExtension(
            entity_id=entity.id,
            job=npc_state.background.occupation,
            current_activity=npc_state.current_state.current_activity,
            current_location=generation_location,
            current_mood=npc_state.current_state.mood,
            speech_pattern=npc_state.personality.speech_pattern,
            personality_traits={trait: True for trait in npc_state.personality.traits},
            workplace=generation_location,  # NPCs are generated at their workplace
            home_location=generation_location if is_residential else None,
        )
        self.db.add(extension)

        # Create skills based on occupation
        occupation = npc_state.background.occupation.lower()
        skills = OCCUPATION_SKILLS.get(occupation, [])
        for skill in skills:
            level = random.randint(30, 70)
            entity_skill = EntitySkill(
                entity_id=entity.id,
                skill_key=skill,
                proficiency_level=level,
                experience_points=0,
            )
            self.db.add(entity_skill)

        # Create inventory based on occupation
        items = OCCUPATION_INVENTORY.get(occupation, [])
        for item_template in items:
            item = Item(
                session_id=self.session_id,
                item_key=f"{entity.entity_key}_{item_template['item_key']}",
                display_name=item_template["display_name"],
                item_type=ITEM_TYPE_MAP.get(item_template["item_type"], ItemType.MISC),
                owner_id=entity.id,
                holder_id=entity.id,
                condition=ItemCondition.GOOD,
            )
            self.db.add(item)

        # Create preferences
        self._persist_preferences(entity.id, npc_state.preferences, npc_state.personality)

        # Create needs
        self._persist_needs(entity.id, npc_state.current_needs)

        self.db.flush()
        return entity

    def _persist_preferences(
        self,
        entity_id: int,
        preferences: NPCPreferences,
        personality: NPCPersonality,
    ) -> CharacterPreferences:
        """Persist NPC preferences to database."""
        # Determine social tendency from personality
        social_tendency = SocialTendency.AMBIVERT
        if "shy" in personality.traits or "introverted" in personality.traits:
            social_tendency = SocialTendency.INTROVERT
        elif "outgoing" in personality.traits or "social" in personality.traits:
            social_tendency = SocialTendency.EXTROVERT

        # Map drive_level string to enum
        drive_level_map = {
            "low": DriveLevel.LOW,
            "moderate": DriveLevel.MODERATE,
            "high": DriveLevel.HIGH,
        }
        drive_level = drive_level_map.get(preferences.drive_level, DriveLevel.MODERATE)

        prefs = CharacterPreferences(
            session_id=self.session_id,
            entity_id=entity_id,
            # Food preferences
            favorite_foods=preferences.favorite_foods,
            disliked_foods=preferences.disliked_foods if preferences.disliked_foods else None,
            is_vegetarian=preferences.is_vegetarian,
            is_vegan=preferences.is_vegan,
            food_allergies=preferences.food_allergies if preferences.food_allergies else None,
            is_greedy_eater=preferences.is_greedy_eater,
            is_picky_eater=preferences.is_picky_eater,
            # Drink preferences
            favorite_drinks=preferences.favorite_drinks if preferences.favorite_drinks else None,
            disliked_drinks=preferences.disliked_drinks if preferences.disliked_drinks else None,
            is_alcoholic=preferences.is_alcoholic,
            is_teetotaler=preferences.is_teetotaler,
            alcohol_tolerance=AlcoholTolerance.MODERATE,
            # Social preferences
            social_tendency=social_tendency,
            preferred_group_size=random.randint(2, 5),
            is_social_butterfly="outgoing" in personality.traits,
            is_loner="loner" in personality.traits or "antisocial" in personality.traits,
            # Intimacy preferences
            drive_level=drive_level,
            drive_threshold=preferences.drive_threshold,
            intimacy_style=IntimacyStyle.EMOTIONAL,
            has_regular_partner=preferences.has_regular_partner,
            is_actively_seeking=preferences.is_actively_seeking,
            # Stamina preferences
            has_high_stamina=preferences.has_high_stamina,
            has_low_stamina=preferences.has_low_stamina,
            is_insomniac=preferences.is_insomniac,
            is_heavy_sleeper=preferences.is_heavy_sleeper,
            # Attraction preferences (extended JSON)
            attraction_preferences={
                "physical": preferences.attracted_to_physical,
                "personality": preferences.attracted_to_personality,
                "genders": preferences.attracted_to_genders,
                "age_offset": preferences.attracted_age_offset,
            },
            # Extra preferences
            extra_preferences=preferences.extra_preferences if preferences.extra_preferences else None,
        )
        self.db.add(prefs)
        return prefs

    def _persist_needs(self, entity_id: int, current_needs: NPCNeeds) -> CharacterNeeds:
        """Persist NPC needs to database."""
        # Convert from "urgency" (higher = more urgent) to "satisfaction" (higher = more satisfied)
        needs = CharacterNeeds(
            session_id=self.session_id,
            entity_id=entity_id,
            hunger=100 - current_needs.hunger,
            thirst=100 - current_needs.thirst,
            stamina=80,  # Default fresh stamina
            sleep_pressure=current_needs.fatigue,  # fatigue is already urgency-based
            hygiene=100 - current_needs.hygiene,
            comfort=100 - current_needs.comfort,
            wellness=100,
            social_connection=100 - current_needs.social,
            morale=100 - current_needs.morale,
            sense_of_purpose=70,
            intimacy=100 - current_needs.intimacy,
        )
        self.db.add(needs)
        return needs

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _get_existing_entity(self, entity_key: str) -> Entity | None:
        """Get existing entity by key."""
        return (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.session_id,
                Entity.entity_key == entity_key,
            )
            .first()
        )

    def _build_full_state_from_entity(
        self,
        entity: Entity,
        scene_context: SceneContext,
    ) -> NPCFullState:
        """Build NPCFullState from existing entity."""
        # This would reconstruct the full state from database records
        # For now, return a simplified version
        reactions = self.query_npc_reactions(entity.entity_key, scene_context)

        appearance = NPCAppearance(
            age=entity.age or 30,
            gender=entity.gender or "unknown",
            height_cm=int(entity.height.replace("cm", "")) if entity.height and "cm" in entity.height else 170,
            species=entity.species or "human",
            age_description=entity.age_apparent or age_to_description(entity.age or 30),
            height_description=height_to_description(170, entity.gender or "unknown"),
            build=entity.build or "average",
            hair=f"{entity.hair_color or 'brown'}, {entity.hair_style or 'practical'}",
            eyes=entity.eye_color or "brown",
            skin=entity.skin_tone or "average",
            notable_features=entity.distinguishing_features.split(", ") if entity.distinguishing_features else [],
            clothing="practical clothes",
        )

        background = NPCBackground(
            occupation=entity.occupation or "unknown",
            occupation_years=entity.occupation_years or 1,
            background_summary=entity.background or "Unknown background",
        )

        personality_traits = []
        if entity.npc_extension and entity.npc_extension.personality_traits:
            personality_traits = list(entity.npc_extension.personality_traits.keys())

        personality = NPCPersonality(
            traits=personality_traits or ["neutral"],
            values=["duty"],
            flaws=["unknown"],
        )

        prefs_record = (
            self.db.query(CharacterPreferences)
            .filter(
                CharacterPreferences.session_id == self.session_id,
                CharacterPreferences.entity_id == entity.id,
            )
            .first()
        )
        preferences = self._preferences_from_record(prefs_record)

        return NPCFullState(
            entity_key=entity.entity_key,
            display_name=entity.display_name,
            appearance=appearance,
            background=background,
            personality=personality,
            preferences=preferences,
            current_needs=reactions.current_needs if reactions else NPCNeeds(),
            current_state=NPCCurrentState(
                mood=reactions.current_mood if reactions else "neutral",
                health="healthy",
                conditions=[],
                current_activity=entity.npc_extension.current_activity if entity.npc_extension else "unknown",
                current_location=entity.npc_extension.current_location if entity.npc_extension else "unknown",
            ),
            environmental_reactions=reactions.environmental_reactions if reactions else [],
            immediate_goals=[],
            behavioral_prediction=reactions.behavioral_prediction if reactions else "Unknown",
        )

    def _preferences_from_record(
        self,
        record: CharacterPreferences | None,
    ) -> NPCPreferences:
        """Build NPCPreferences from database record."""
        if not record:
            return NPCPreferences()

        # Extract attraction preferences from JSON
        attracted_physical = []
        attracted_personality = []
        attracted_genders = ["male", "female"]  # Default bisexual if not stored
        age_offset = 0

        if record.attraction_preferences:
            attracted_physical = record.attraction_preferences.get("physical", [])
            attracted_personality = record.attraction_preferences.get("personality", [])
            attracted_genders = record.attraction_preferences.get("genders", ["male", "female"])
            age_offset = record.attraction_preferences.get("age_offset", 0)

        # Map drive_level enum to string
        drive_level_str = "moderate"
        if record.drive_level == DriveLevel.LOW:
            drive_level_str = "low"
        elif record.drive_level == DriveLevel.HIGH:
            drive_level_str = "high"

        return NPCPreferences(
            # Gender/age attraction
            attracted_to_genders=attracted_genders,
            attracted_age_offset=age_offset,
            # Physical/personality attraction
            attracted_to_physical=attracted_physical,
            attracted_to_personality=attracted_personality,
            # Food preferences
            favorite_foods=record.favorite_foods or [],
            disliked_foods=record.disliked_foods or [],
            is_vegetarian=record.is_vegetarian,
            is_vegan=record.is_vegan,
            food_allergies=record.food_allergies or [],
            is_greedy_eater=record.is_greedy_eater,
            is_picky_eater=record.is_picky_eater,
            # Drink preferences
            favorite_drinks=record.favorite_drinks or [],
            disliked_drinks=record.disliked_drinks or [],
            is_alcoholic=record.is_alcoholic,
            is_teetotaler=record.is_teetotaler,
            # Activities and dislikes
            favorite_activities=[],  # Not stored in database
            dislikes=[],  # Not stored in database - personality dislikes are regenerated
            fears=[],  # Not stored in database
            # Intimacy preferences
            drive_level=drive_level_str,
            drive_threshold=record.drive_threshold,
            has_regular_partner=record.has_regular_partner,
            is_actively_seeking=record.is_actively_seeking,
            # Stamina preferences
            has_high_stamina=record.has_high_stamina,
            has_low_stamina=record.has_low_stamina,
            is_insomniac=record.is_insomniac,
            is_heavy_sleeper=record.is_heavy_sleeper,
            # Extra preferences
            extra_preferences=record.extra_preferences or {},
        )

    def _personality_from_entity(self, entity: Entity) -> NPCPersonality:
        """Build NPCPersonality from entity."""
        traits = []
        if entity.npc_extension and entity.npc_extension.personality_traits:
            traits = list(entity.npc_extension.personality_traits.keys())

        return NPCPersonality(
            traits=traits or ["neutral"],
            values=["duty"],
            flaws=["unknown"],
        )
