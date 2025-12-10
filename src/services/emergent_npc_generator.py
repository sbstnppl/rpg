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
from src.llm.factory import get_cheap_provider
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

# Physical attraction traits
PHYSICAL_ATTRACTION_TRAITS = [
    "lean build", "muscular build", "athletic build", "soft curves",
    "dark hair", "light hair", "red hair", "long hair", "short hair",
    "tall stature", "average height", "shorter stature",
    "sharp features", "soft features", "strong jaw", "delicate features",
    "bright eyes", "dark eyes", "expressive face", "mysterious look",
    "well-groomed", "rugged appearance", "elegant bearing", "warm smile",
]

# Personality attraction traits
PERSONALITY_ATTRACTION_TRAITS = [
    "confidence", "kindness", "wit", "humor", "intelligence", "strength",
    "gentleness", "passion", "ambition", "creativity", "mystery", "warmth",
    "stability", "adventurousness", "wisdom", "charm", "honesty", "loyalty",
    "protectiveness", "sensitivity", "assertiveness", "playfulness",
]


# =============================================================================
# Age Range Definitions
# =============================================================================

AGE_RANGES: dict[str, tuple[int, int, str]] = {
    "child": (6, 12, "child"),
    "teen": (13, 17, "teenager"),
    "young_adult": (18, 30, "young adult"),
    "middle_aged": (31, 55, "middle-aged"),
    "elderly": (56, 85, "elderly"),
}


def age_to_description(age: int) -> str:
    """Convert numeric age to narrative description."""
    if age < 13:
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
        current_needs = NPCNeeds(
            hunger=100 - (needs_record.hunger if needs_record else 70),
            thirst=100 - (needs_record.thirst if needs_record else 70),
            fatigue=100 - (needs_record.energy if needs_record else 70),
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
        """Generate full name."""
        if constraints and constraints.name:
            return constraints.name

        # Pick first name based on gender
        name_pool = NAMES_BY_GENDER.get(gender, NAMES_BY_GENDER["neutral"])
        first_name = random.choice(name_pool)

        # 70% chance of having a surname
        if random.random() < 0.7:
            surname = random.choice(SURNAMES)
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

    def _generate_appearance(
        self,
        gender: str,
        age: int,
        role: str,
        constraints: NPCConstraints | None,
    ) -> NPCAppearance:
        """Generate physical appearance."""
        # Height based on gender with some randomness
        if gender == "female":
            height_cm = random.randint(150, 180)
        else:
            height_cm = random.randint(160, 195)

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
            skin=random.choice(SKIN_TONES),
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
        """Generate voice description."""
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

        if age > 60:
            return random.choice(voices_elderly)
        elif gender == "female":
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

        Returns:
            OccupationDetails with occupation, skills, typical_items, education,
            background_summary, and wealth_level.
        """
        try:
            # Run async LLM call in sync context
            return asyncio.run(
                self._generate_occupation_from_llm_async(
                    role_hint, setting, location_context, age, gender
                )
            )
        except RuntimeError as e:
            # Handle case where event loop is already running
            if "cannot be called from a running event loop" in str(e):
                logger.warning("Event loop already running, using fallback")
                return self._generate_occupation_fallback(role_hint, age, setting)
            raise
        except Exception as e:
            logger.warning(f"LLM occupation generation failed: {e}, using fallback")
            return self._generate_occupation_fallback(role_hint, age, setting)

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

        provider = get_cheap_provider()
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
    ) -> OccupationDetails:
        """Fallback occupation generation when LLM fails.

        Uses hardcoded pools for fantasy setting, generic defaults for others.
        """
        # For youth, use age-appropriate occupations
        if age < 14:
            occupation = random.choice(["child", "youth", "street_urchin"])
        elif age < 18:
            youth_occupations = [
                "apprentice", "stable_boy", "kitchen_boy", "errand_boy",
                "farm_hand", "fisher_boy", "shepherd_boy", "page",
            ]
            occupation = random.choice(youth_occupations)
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

    def _generate_birthplace(self) -> str:
        """Generate birthplace."""
        places = [
            "this very town", "a nearby village", "the capital",
            "a farming community", "a coastal settlement", "the mountains",
            "a trading town", "foreign lands", "unknown", "a small hamlet",
        ]
        return random.choice(places)

    def _generate_family_situation(self, age: int) -> str:
        """Generate family situation based on age."""
        if age < 20:
            situations = [
                "lives with parents", "orphaned young", "raised by grandparents",
                "large family with many siblings", "only child",
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

        Based on real-world statistics:
        - ~90-95% heterosexual
        - ~3-5% homosexual
        - ~2-4% bisexual

        Args:
            npc_gender: The NPC's gender.

        Returns:
            List of genders the NPC is attracted to.
        """
        roll = random.random()

        if npc_gender == "male":
            if roll < 0.92:
                return ["female"]           # Heterosexual
            elif roll < 0.97:
                return ["male"]             # Homosexual
            else:
                return ["male", "female"]   # Bisexual
        elif npc_gender == "female":
            if roll < 0.90:
                return ["male"]             # Heterosexual
            elif roll < 0.96:
                return ["female"]           # Homosexual
            else:
                return ["male", "female"]   # Bisexual
        else:
            # Non-binary or other: random distribution
            return random.choice([["male"], ["female"], ["male", "female"]])

    def _generate_age_attraction(self, npc_age: int) -> tuple[int, tuple[int, int]]:
        """Generate preferred age using offset + range system.

        Returns: (offset, (range_min, range_max))

        Target age center = npc_age + offset
        Acceptable range = (center + range_min, center + range_max)

        Most NPCs prefer similar ages (offset ~0), but some have preferences
        for older/younger partners.

        Args:
            npc_age: The NPC's age.

        Returns:
            Tuple of (offset, (range_min, range_max)).
        """
        if npc_age < 18:
            # Minors: strict same-age preference
            offset = 0
            age_range = (-2, 2)
        elif npc_age < 25:
            # Young adults: mostly similar age, occasionally older preference
            roll = random.random()
            if roll < 0.85:
                offset = random.randint(-2, 3)  # Similar age
                age_range = (-3, 5)
            else:
                offset = random.randint(5, 15)  # Prefers older
                age_range = (-5, 10)
        elif npc_age < 40:
            # Adults: wider variety
            roll = random.random()
            if roll < 0.70:
                offset = random.randint(-3, 3)  # Similar age
                age_range = (-5, 8)
            elif roll < 0.90:
                offset = random.randint(-8, -3)  # Prefers younger
                age_range = (-5, 5)
            else:
                offset = random.randint(5, 15)  # Prefers older
                age_range = (-5, 10)
        else:
            # Older adults: often prefer younger
            roll = random.random()
            if roll < 0.60:
                offset = random.randint(-15, -5)  # Prefers younger
                age_range = (-10, 5)
            else:
                offset = random.randint(-5, 5)  # Similar age
                age_range = (-8, 8)

        return (offset, age_range)

    def _generate_preferences(
        self,
        gender: str,
        age: int,
        personality: NPCPersonality,
    ) -> NPCPreferences:
        """Generate preferences including attraction traits.

        Args:
            gender: NPC's gender for attraction generation.
            age: NPC's age for age-attraction preferences.
            personality: NPC's personality traits.

        Returns:
            NPCPreferences with all preference fields populated.
        """
        # Gender and age attraction
        attracted_to_genders = self._generate_gender_attraction(gender)
        offset, age_range = self._generate_age_attraction(age)

        # Physical attraction (2-4 traits)
        attracted_physical = random.sample(PHYSICAL_ATTRACTION_TRAITS, random.randint(2, 4))

        # Personality attraction (2-4 traits)
        attracted_personality = random.sample(PERSONALITY_ATTRACTION_TRAITS, random.randint(2, 4))

        # Food/drink lists
        all_foods = [
            "honey cakes", "roasted chicken", "fresh bread", "apple pie",
            "stew", "grilled fish", "cheese", "berries", "meat pies",
            "porridge", "liver", "onions", "turnips", "bitter greens",
            "pickled vegetables", "boiled cabbage", "fish stew", "mutton",
        ]
        all_drinks = [
            "ale", "wine", "mead", "cider", "water", "milk", "tea",
            "herbal tea", "fruit juice", "hot chocolate", "coffee",
        ]

        # Favorites
        favorite_foods = random.sample(all_foods[:9], random.randint(1, 3))
        favorite_drinks = random.sample(all_drinks, random.randint(1, 2))

        # Disliked (exclude favorites)
        available_for_dislike = [f for f in all_foods if f not in favorite_foods]
        disliked_foods = random.sample(available_for_dislike, random.randint(1, 3))
        available_drinks_dislike = [d for d in all_drinks if d not in favorite_drinks]
        disliked_drinks = random.sample(available_drinks_dislike, random.randint(0, 2))

        favorite_activities = random.sample([
            "reading", "music", "gardening", "cooking", "dancing",
            "hunting", "crafting", "storytelling", "exploring", "games",
        ], random.randint(1, 3))

        # Dislikes (personality/behavior dislikes)
        dislikes = random.sample([
            "arrogance", "cruelty", "loud crowds", "dishonesty", "rudeness",
            "laziness", "cowardice", "waste", "violence", "prejudice",
        ], random.randint(2, 4))

        # Fears (1-2)
        fears = random.sample([
            "rejection", "being alone", "failure", "heights", "darkness",
            "crowds", "death", "poverty", "embarrassment", "losing loved ones",
        ], random.randint(1, 2))

        # Food preferences (booleans) - low probability for special diets
        is_vegetarian = random.random() < 0.08
        is_vegan = random.random() < 0.02 if not is_vegetarian else False
        is_greedy_eater = random.random() < 0.15
        is_picky_eater = random.random() < 0.20 if not is_greedy_eater else False

        # Food allergies (5% chance)
        food_allergies: list[str] = []
        if random.random() < 0.05:
            allergy_options = ["nuts", "shellfish", "dairy", "eggs", "wheat"]
            food_allergies = random.sample(allergy_options, random.randint(1, 2))

        # Alcohol preferences - correlated with age
        if age < 18:
            is_alcoholic = False
            is_teetotaler = random.random() < 0.80  # Most minors don't drink
        else:
            is_alcoholic = random.random() < 0.05
            is_teetotaler = random.random() < 0.15 if not is_alcoholic else False

        # Intimacy preferences
        drive_roll = random.random()
        if age < 18:
            # Minors have lower/developing drive
            drive_level = "low"
            drive_threshold = 70 + random.randint(0, 20)  # Higher threshold
            is_actively_seeking = False
        else:
            if drive_roll < 0.25:
                drive_level = "low"
                drive_threshold = 60 + random.randint(0, 30)
            elif drive_roll < 0.75:
                drive_level = "moderate"
                drive_threshold = 40 + random.randint(0, 30)
            else:
                drive_level = "high"
                drive_threshold = 20 + random.randint(0, 30)
            is_actively_seeking = random.random() < 0.30

        # Partnership status (correlates with age)
        if age < 18:
            has_regular_partner = random.random() < 0.10  # Young crushes
        elif age < 30:
            has_regular_partner = random.random() < 0.35
        elif age < 50:
            has_regular_partner = random.random() < 0.65
        else:
            has_regular_partner = random.random() < 0.55

        # Stamina/sleep preferences
        has_high_stamina = random.random() < 0.20
        has_low_stamina = random.random() < 0.20 if not has_high_stamina else False
        is_insomniac = random.random() < 0.10
        is_heavy_sleeper = random.random() < 0.15 if not is_insomniac else False

        return NPCPreferences(
            attracted_to_genders=attracted_to_genders,
            attracted_age_offset=offset,
            attracted_age_range=age_range,
            attracted_to_physical=attracted_physical,
            attracted_to_personality=attracted_personality,
            favorite_foods=favorite_foods,
            disliked_foods=disliked_foods,
            is_vegetarian=is_vegetarian,
            is_vegan=is_vegan,
            food_allergies=food_allergies,
            is_greedy_eater=is_greedy_eater,
            is_picky_eater=is_picky_eater,
            favorite_drinks=favorite_drinks,
            disliked_drinks=disliked_drinks,
            is_alcoholic=is_alcoholic,
            is_teetotaler=is_teetotaler,
            favorite_activities=favorite_activities,
            dislikes=dislikes,
            fears=fears,
            drive_level=drive_level,
            drive_threshold=drive_threshold,
            has_regular_partner=has_regular_partner,
            is_actively_seeking=is_actively_seeking,
            has_high_stamina=has_high_stamina,
            has_low_stamina=has_low_stamina,
            is_insomniac=is_insomniac,
            is_heavy_sleeper=is_heavy_sleeper,
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

    def _calculate_age_attraction_factor(
        self,
        npc_age: int,
        player_age: int,
        offset: int,
        age_range: tuple[int, int],
    ) -> float:
        """Calculate age-based attraction factor (0.0 to 1.0).

        Uses gradual falloff outside preferred range:
        - Inside range: 1.0 (no penalty)
        - Outside range: decreases gradually based on distance
        - Very far outside: approaches 0

        Example: 18yo with offset=5, range=(-5,+10) → prefers 18-33
        - 30yo player: 1.0 (in range)
        - 34yo player: ~0.95 (1 year outside)
        - 40yo player: ~0.70 (7 years outside)
        - 80yo player: ~0.05 (47 years outside)

        Args:
            npc_age: The NPC's age.
            player_age: The player's age.
            offset: Offset from NPC's age to center of preferred range.
            age_range: (min, max) range around the offset center.

        Returns:
            Float from 0.02 to 1.0 representing age compatibility.
        """
        # Calculate preferred age range
        center = npc_age + offset
        min_preferred = center + age_range[0]
        max_preferred = center + age_range[1]

        # Ensure minimum age is at least 18 for adults, or appropriate for minors
        if npc_age >= 18:
            min_preferred = max(18, min_preferred)

        # Check if in range
        if min_preferred <= player_age <= max_preferred:
            return 1.0  # Perfect match, no penalty

        # Calculate distance outside range
        if player_age < min_preferred:
            distance = min_preferred - player_age
        else:
            distance = player_age - max_preferred

        # Gradual falloff using exponential decay
        # decay_rate controls how quickly attraction falls off
        # 0.1 means ~90% at 1 year, ~60% at 5 years, ~35% at 10 years, ~5% at 30 years
        decay_rate = 0.1
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
                age_range=preferences.attracted_age_range,
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
        extension = NPCExtension(
            entity_id=entity.id,
            job=npc_state.background.occupation,
            current_activity=npc_state.current_state.current_activity,
            current_location=npc_state.current_state.current_location,
            current_mood=npc_state.current_state.mood,
            speech_pattern=npc_state.personality.speech_pattern,
            personality_traits={trait: True for trait in npc_state.personality.traits},
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
                "age_range": list(preferences.attracted_age_range),  # Convert tuple to list for JSON
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
            energy=100 - current_needs.fatigue,
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
        age_range = (-5, 5)

        if record.attraction_preferences:
            attracted_physical = record.attraction_preferences.get("physical", [])
            attracted_personality = record.attraction_preferences.get("personality", [])
            attracted_genders = record.attraction_preferences.get("genders", ["male", "female"])
            age_offset = record.attraction_preferences.get("age_offset", 0)
            age_range_list = record.attraction_preferences.get("age_range", [-5, 5])
            if isinstance(age_range_list, list) and len(age_range_list) == 2:
                age_range = (age_range_list[0], age_range_list[1])

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
            attracted_age_range=age_range,
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
