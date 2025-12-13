"""NPC Generator Service for creating full character data for NPCs.

This service generates comprehensive NPC data including appearance, background,
skills, inventory, preferences, and needs when an NPC is first introduced.

NOTE: This service is used by the npc_generator_node in the LangGraph pipeline
for post-extraction NPC enrichment. For tool-based NPC creation (CREATE_NPC_TOOL),
use EmergentNPCGenerator from src/services/emergent_npc_generator.py instead,
which follows the "GM Discovers, Not Prescribes" philosophy.
"""

import logging
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from src.agents.schemas.npc_generation import (
    NPCAppearance,
    NPCBackground,
    NPCGenerationResult,
    NPCInitialNeeds,
    NPCInventoryItem,
    NPCPreferences,
    NPCSkill,
)
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
from src.llm.factory import get_extraction_provider
from src.llm.message_types import Message
from src.services.preference_calculator import generate_preferences


logger = logging.getLogger(__name__)


# Template path
TEMPLATE_PATH = (
    Path(__file__).parent.parent.parent / "data" / "templates" / "npc_generator.md"
)


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
}


# Occupation-based inventory templates
OCCUPATION_INVENTORY: dict[str, list[dict[str, Any]]] = {
    "merchant": [
        {"item_key": "coin_purse", "display_name": "Coin Purse", "item_type": "container"},
        {"item_key": "ledger", "display_name": "Account Ledger", "item_type": "misc"},
        {"item_key": "merchant_clothes", "display_name": "Merchant's Clothes", "item_type": "clothing", "body_slot": "torso", "is_equipped": True},
    ],
    "guard": [
        {"item_key": "sword", "display_name": "Short Sword", "item_type": "weapon", "body_slot": "main_hand"},
        {"item_key": "guard_uniform", "display_name": "Guard Uniform", "item_type": "armor", "body_slot": "torso", "is_equipped": True},
        {"item_key": "whistle", "display_name": "Guard Whistle", "item_type": "misc"},
    ],
    "innkeeper": [
        {"item_key": "apron", "display_name": "Stained Apron", "item_type": "clothing", "body_slot": "torso", "is_equipped": True},
        {"item_key": "keys", "display_name": "Ring of Keys", "item_type": "misc"},
        {"item_key": "coin_purse", "display_name": "Coin Purse", "item_type": "container"},
    ],
    "blacksmith": [
        {"item_key": "hammer", "display_name": "Smith's Hammer", "item_type": "misc"},
        {"item_key": "apron", "display_name": "Leather Apron", "item_type": "clothing", "body_slot": "torso", "is_equipped": True},
        {"item_key": "tongs", "display_name": "Smithing Tongs", "item_type": "misc"},
    ],
    "farmer": [
        {"item_key": "work_clothes", "display_name": "Work Clothes", "item_type": "clothing", "body_slot": "torso", "is_equipped": True},
        {"item_key": "straw_hat", "display_name": "Straw Hat", "item_type": "clothing", "body_slot": "head", "is_equipped": True},
    ],
    "hunter": [
        {"item_key": "bow", "display_name": "Hunting Bow", "item_type": "weapon", "body_slot": "main_hand"},
        {"item_key": "arrows", "display_name": "Quiver of Arrows", "item_type": "weapon", "quantity": 12},
        {"item_key": "hunting_clothes", "display_name": "Hunting Clothes", "item_type": "clothing", "body_slot": "torso", "is_equipped": True},
        {"item_key": "skinning_knife", "display_name": "Skinning Knife", "item_type": "weapon"},
    ],
    "healer": [
        {"item_key": "healer_robes", "display_name": "Healer's Robes", "item_type": "clothing", "body_slot": "torso", "is_equipped": True},
        {"item_key": "herb_pouch", "display_name": "Herb Pouch", "item_type": "container"},
        {"item_key": "bandages", "display_name": "Clean Bandages", "item_type": "consumable", "quantity": 5},
    ],
    "scholar": [
        {"item_key": "scholar_robes", "display_name": "Scholar's Robes", "item_type": "clothing", "body_slot": "torso", "is_equipped": True},
        {"item_key": "book", "display_name": "Leather-bound Book", "item_type": "misc"},
        {"item_key": "quill", "display_name": "Writing Quill", "item_type": "misc"},
    ],
    "noble": [
        {"item_key": "fine_clothes", "display_name": "Fine Noble Attire", "item_type": "clothing", "body_slot": "torso", "is_equipped": True},
        {"item_key": "signet_ring", "display_name": "Signet Ring", "item_type": "misc", "body_slot": "ring_right", "is_equipped": True},
        {"item_key": "coin_purse", "display_name": "Heavy Coin Purse", "item_type": "container"},
    ],
}


# Item type mapping
ITEM_TYPE_MAP = {
    "weapon": ItemType.WEAPON,
    "armor": ItemType.ARMOR,
    "clothing": ItemType.CLOTHING,
    "consumable": ItemType.CONSUMABLE,
    "container": ItemType.CONTAINER,
    "misc": ItemType.MISC,
    "currency": ItemType.MISC,  # Map currency to misc
}


def infer_npc_initial_needs(
    occupation: str,
    game_time: str,
    game_day: int,
    backstory: str = "",
) -> dict[str, int]:
    """Infer starting need values from NPC context.

    Args:
        occupation: NPC's occupation.
        game_time: Current game time (HH:MM format).
        game_day: Current game day.
        backstory: Optional backstory text.

    Returns:
        Dictionary of need values (0-100).
    """
    # Parse hour from time
    try:
        hour = int(game_time.split(":")[0])
    except (ValueError, IndexError):
        hour = 12  # Default to midday

    # Base values
    needs = {
        "hunger": 70,
        "thirst": 70,
        "energy": 70,
        "hygiene": 70,
        "comfort": 70,
        "wellness": 100,
        "social_connection": 60,
        "morale": 65,
        "sense_of_purpose": 60,
        "intimacy": 60,
    }

    # Time-based adjustments
    if 6 <= hour < 9:
        # Early morning: needs breakfast
        needs["hunger"] = 55
        needs["energy"] = 70
    elif 11 <= hour < 14:
        # Midday: needs lunch
        needs["hunger"] = 55
        needs["energy"] = 65
    elif 17 <= hour < 20:
        # Evening: needs dinner, getting tired
        needs["hunger"] = 55
        needs["energy"] = 55
    elif 20 <= hour < 23:
        # Late evening: tired
        needs["energy"] = 45
    elif hour >= 23 or hour < 6:
        # Night: very tired
        needs["energy"] = 35
        needs["hunger"] = 50

    # Occupation-based adjustments
    occupation_lower = occupation.lower()

    # Service occupations have better food/drink access
    if occupation_lower in ("innkeeper", "cook", "baker", "tavern_keeper"):
        needs["hunger"] = min(needs["hunger"] + 15, 85)
        needs["thirst"] = min(needs["thirst"] + 15, 85)

    # Physical labor occupations
    if occupation_lower in ("farmer", "blacksmith", "miner", "laborer", "soldier"):
        needs["energy"] = max(needs["energy"] - 10, 40)
        needs["hunger"] = max(needs["hunger"] - 5, 50)
        needs["thirst"] = max(needs["thirst"] - 5, 50)

    # Scholarly/sedentary occupations
    if occupation_lower in ("scholar", "scribe", "merchant", "noble"):
        needs["energy"] = min(needs["energy"] + 5, 80)

    # Social occupations
    if occupation_lower in ("bard", "innkeeper", "merchant", "noble"):
        needs["social_connection"] = min(needs["social_connection"] + 10, 75)

    # Solitary occupations
    if occupation_lower in ("hermit", "hunter", "shepherd", "lighthouse_keeper"):
        needs["social_connection"] = max(needs["social_connection"] - 15, 40)

    return needs


class NPCGeneratorService:
    """Service for generating full character data for NPCs.

    Generates comprehensive NPC data including appearance, background,
    skills, inventory, preferences, and needs when an NPC is first introduced.
    """

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        llm_client: Any = None,
    ) -> None:
        """Initialize the NPC Generator Service.

        Args:
            db: Database session.
            game_session: Current game session.
            llm_client: Optional LLM client for testing.
        """
        self.db = db
        self.game_session = game_session
        self.session_id = game_session.id
        self._llm_client = llm_client

    async def generate_npc(
        self,
        entity_key: str,
        display_name: str,
        entity_type: EntityType,
        description: str | None,
        personality_traits: list[str],
        current_activity: str | None,
        current_location: str | None,
    ) -> Entity:
        """Generate full NPC data and persist to database.

        Args:
            entity_key: Unique entity key.
            display_name: Display name for the NPC.
            entity_type: Type of entity (NPC, ANIMAL, MONSTER).
            description: Physical description from extraction.
            personality_traits: Personality traits from extraction.
            current_activity: What the NPC is currently doing.
            current_location: Where the NPC is located.

        Returns:
            Created Entity with all related records.
        """
        # Check if entity already exists
        existing = (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.session_id,
                Entity.entity_key == entity_key,
            )
            .first()
        )
        if existing:
            logger.info(f"Entity {entity_key} already exists, skipping generation")
            return existing

        # Get game context
        time_state = (
            self.db.query(TimeState)
            .filter(TimeState.session_id == self.session_id)
            .first()
        )
        game_time = time_state.current_time if time_state else "12:00"
        game_day = time_state.current_day if time_state else 1

        try:
            # Call LLM to generate NPC data
            generation_result = await self._call_llm_for_generation(
                entity_key=entity_key,
                display_name=display_name,
                entity_type=entity_type,
                description=description,
                personality_traits=personality_traits,
                current_activity=current_activity,
                current_location=current_location,
                game_time=game_time,
                game_day=game_day,
            )

            # Create all records
            entity = self._create_entity_with_appearance(
                entity_key=entity_key,
                display_name=display_name,
                entity_type=entity_type,
                appearance=generation_result.appearance,
                description=description,
            )

            self._create_npc_extension(
                entity=entity,
                background=generation_result.background,
                current_activity=current_activity,
                current_location=current_location,
                personality_traits=personality_traits,
            )

            self._create_npc_skills(entity.id, generation_result.skills)
            self._create_npc_inventory(entity, generation_result.inventory)

            # Generate preferences using formula-based calculator (not LLM)
            gender = generation_result.appearance.gender or "other"
            age = generation_result.appearance.age or 25
            formula_prefs = generate_preferences(gender, age)

            # Convert to NPCPreferences schema for _create_npc_preferences
            npc_preferences = NPCPreferences(
                social_tendency=formula_prefs.social_tendency,
                preferred_group_size=formula_prefs.preferred_group_size,
                drive_level=formula_prefs.drive_level,
                intimacy_style=formula_prefs.intimacy_style,
                alcohol_tolerance=formula_prefs.alcohol_tolerance,
                favorite_foods=formula_prefs.favorite_foods,
                disliked_foods=formula_prefs.disliked_foods,
                is_greedy_eater=formula_prefs.is_greedy_eater,
                is_picky_eater=formula_prefs.is_picky_eater,
                is_social_butterfly=formula_prefs.is_social_butterfly,
                is_loner=formula_prefs.is_loner,
                has_high_stamina=formula_prefs.has_high_stamina,
                has_low_stamina=formula_prefs.has_low_stamina,
            )

            self._create_npc_preferences(entity.id, npc_preferences)
            self._create_npc_needs(entity.id, generation_result.initial_needs)

            self.db.flush()
            return entity

        except Exception as e:
            logger.error(f"NPC generation failed for {entity_key}: {e}")
            # Fallback: create minimal entity
            return self._create_fallback_entity(
                entity_key=entity_key,
                display_name=display_name,
                entity_type=entity_type,
                description=description,
                current_activity=current_activity,
                current_location=current_location,
                personality_traits=personality_traits,
            )

    def _create_entity_with_appearance(
        self,
        entity_key: str,
        display_name: str,
        entity_type: EntityType,
        appearance: NPCAppearance,
        description: str | None,
    ) -> Entity:
        """Create entity with all appearance fields populated.

        Args:
            entity_key: Unique entity key.
            display_name: Display name.
            entity_type: Type of entity.
            appearance: Appearance data from generation.
            description: Physical description.

        Returns:
            Created Entity.
        """
        entity = Entity(
            session_id=self.session_id,
            entity_key=entity_key,
            display_name=display_name,
            entity_type=entity_type,
            is_alive=True,
            is_active=True,
            # Appearance fields
            age=appearance.age,
            age_apparent=appearance.age_apparent,
            gender=appearance.gender,
            height=appearance.height,
            build=appearance.build,
            hair_color=appearance.hair_color,
            hair_style=appearance.hair_style,
            eye_color=appearance.eye_color,
            skin_tone=appearance.skin_tone,
            species=appearance.species,
            distinguishing_features=appearance.distinguishing_features,
            voice_description=appearance.voice_description,
        )
        self.db.add(entity)
        self.db.flush()
        return entity

    def _create_npc_extension(
        self,
        entity: Entity,
        background: NPCBackground,
        current_activity: str | None,
        current_location: str | None,
        personality_traits: list[str],
    ) -> NPCExtension:
        """Create NPCExtension with job, location, and personality.

        Args:
            entity: Parent entity.
            background: Background data from generation.
            current_activity: Current activity.
            current_location: Current location.
            personality_traits: Personality traits.

        Returns:
            Created NPCExtension.
        """
        # Update entity with background info
        entity.background = background.backstory
        entity.personality_notes = background.personality_notes
        entity.occupation = background.occupation
        entity.occupation_years = background.occupation_years

        # Create extension
        extension = NPCExtension(
            entity_id=entity.id,
            job=background.occupation,
            current_activity=current_activity,
            current_location=current_location,
            current_mood="neutral",
            personality_traits={
                trait: True for trait in personality_traits
            } if personality_traits else None,
        )
        self.db.add(extension)
        self.db.flush()
        return extension

    def _create_npc_skills(
        self,
        entity_id: int,
        skills: list[NPCSkill],
    ) -> list[EntitySkill]:
        """Create skill records for NPC.

        Args:
            entity_id: Entity ID.
            skills: Skills from generation.

        Returns:
            List of created EntitySkill records.
        """
        created = []
        for skill in skills:
            entity_skill = EntitySkill(
                entity_id=entity_id,
                skill_key=skill.skill_key,
                proficiency_level=skill.proficiency_level,
                experience_points=0,
            )
            self.db.add(entity_skill)
            created.append(entity_skill)
        return created

    def _create_npc_inventory(
        self,
        entity: Entity,
        items: list[NPCInventoryItem],
    ) -> list[Item]:
        """Create inventory items for NPC.

        Args:
            entity: Parent entity.
            items: Items from generation.

        Returns:
            List of created Item records.
        """
        created = []
        for item_data in items:
            # Map item type string to enum
            item_type = ITEM_TYPE_MAP.get(item_data.item_type, ItemType.MISC)

            item = Item(
                session_id=self.session_id,
                item_key=f"{entity.entity_key}_{item_data.item_key}",
                display_name=item_data.display_name,
                item_type=item_type,
                description=item_data.description,
                owner_id=entity.id,
                holder_id=entity.id,
                body_slot=item_data.body_slot,
                body_layer=item_data.body_layer,
                condition=ItemCondition.GOOD,
                quantity=item_data.quantity,
                properties=item_data.properties,
            )
            self.db.add(item)
            created.append(item)
        return created

    def _create_npc_preferences(
        self,
        entity_id: int,
        preferences: NPCPreferences,
    ) -> CharacterPreferences:
        """Create preferences record for NPC.

        Args:
            entity_id: Entity ID.
            preferences: Preferences from generation.

        Returns:
            Created CharacterPreferences record.
        """
        # Map string values to enums
        social_tendency = SocialTendency(preferences.social_tendency)
        drive_level = DriveLevel(preferences.drive_level)
        intimacy_style = IntimacyStyle(preferences.intimacy_style)
        alcohol_tolerance = AlcoholTolerance(preferences.alcohol_tolerance)

        prefs = CharacterPreferences(
            session_id=self.session_id,
            entity_id=entity_id,
            # Social
            social_tendency=social_tendency,
            preferred_group_size=preferences.preferred_group_size,
            is_social_butterfly=preferences.is_social_butterfly,
            is_loner=preferences.is_loner,
            # Intimacy
            drive_level=drive_level,
            intimacy_style=intimacy_style,
            # Alcohol
            alcohol_tolerance=alcohol_tolerance,
            # Food
            favorite_foods=preferences.favorite_foods or None,
            disliked_foods=preferences.disliked_foods or None,
            is_greedy_eater=preferences.is_greedy_eater,
            is_picky_eater=preferences.is_picky_eater,
            # Stamina
            has_high_stamina=preferences.has_high_stamina,
            has_low_stamina=preferences.has_low_stamina,
        )
        self.db.add(prefs)
        return prefs

    def _create_npc_needs(
        self,
        entity_id: int,
        initial_needs: NPCInitialNeeds,
    ) -> CharacterNeeds:
        """Create needs record for NPC.

        Args:
            entity_id: Entity ID.
            initial_needs: Initial need values from generation.

        Returns:
            Created CharacterNeeds record.
        """
        needs = CharacterNeeds(
            session_id=self.session_id,
            entity_id=entity_id,
            hunger=initial_needs.hunger,
            thirst=initial_needs.thirst,
            energy=initial_needs.energy,
            hygiene=initial_needs.hygiene,
            comfort=initial_needs.comfort,
            wellness=initial_needs.wellness,
            social_connection=initial_needs.social_connection,
            morale=initial_needs.morale,
            sense_of_purpose=initial_needs.sense_of_purpose,
            intimacy=initial_needs.intimacy,
            # Cravings default to 0
            hunger_craving=0,
            thirst_craving=0,
            energy_craving=0,
            social_craving=0,
            intimacy_craving=0,
        )
        self.db.add(needs)
        return needs

    def _create_fallback_entity(
        self,
        entity_key: str,
        display_name: str,
        entity_type: EntityType,
        description: str | None,
        current_activity: str | None,
        current_location: str | None,
        personality_traits: list[str],
    ) -> Entity:
        """Create minimal entity as fallback when generation fails.

        Args:
            entity_key: Unique entity key.
            display_name: Display name.
            entity_type: Type of entity.
            description: Physical description.
            current_activity: Current activity.
            current_location: Current location.
            personality_traits: Personality traits.

        Returns:
            Created Entity with minimal data.
        """
        entity = Entity(
            session_id=self.session_id,
            entity_key=entity_key,
            display_name=display_name,
            entity_type=entity_type,
            is_alive=True,
            is_active=True,
        )
        self.db.add(entity)
        self.db.flush()

        # Create basic extension
        extension = NPCExtension(
            entity_id=entity.id,
            current_activity=current_activity,
            current_location=current_location,
            current_mood="neutral",
            personality_traits={
                trait: True for trait in personality_traits
            } if personality_traits else None,
        )
        self.db.add(extension)
        self.db.flush()

        return entity

    async def _call_llm_for_generation(
        self,
        entity_key: str,
        display_name: str,
        entity_type: EntityType,
        description: str | None,
        personality_traits: list[str],
        current_activity: str | None,
        current_location: str | None,
        game_time: str,
        game_day: int,
    ) -> NPCGenerationResult:
        """Call LLM to generate NPC data.

        Args:
            entity_key: Unique entity key.
            display_name: Display name.
            entity_type: Type of entity.
            description: Physical description.
            personality_traits: Personality traits.
            current_activity: Current activity.
            current_location: Current location.
            game_time: Current game time.
            game_day: Current game day.

        Returns:
            NPCGenerationResult with all generated data.
        """
        # Load template
        template = self._load_template()

        # Format prompt
        prompt = template.format(
            setting=self.game_session.setting,
            display_name=display_name,
            entity_type=entity_type.value,
            description=description or "No description provided",
            personality_traits=", ".join(personality_traits) if personality_traits else "Not specified",
            current_activity=current_activity or "Not specified",
            current_location=current_location or "Unknown",
            game_day=game_day,
            game_time=game_time,
            occupation_skills=self._format_occupation_templates(OCCUPATION_SKILLS),
            occupation_inventory=self._format_occupation_templates(OCCUPATION_INVENTORY),
        )

        # Call LLM
        provider = get_extraction_provider()

        response = await provider.complete_structured(
            messages=[Message.user(prompt)],
            response_schema=NPCGenerationResult,
            max_tokens=2000,
            temperature=0.7,  # Some creativity for NPC variety
        )

        # Parse response
        raw_result = response.parsed_content

        if isinstance(raw_result, dict):
            # Ensure entity_key matches
            raw_result["entity_key"] = entity_key
            return NPCGenerationResult.model_validate(raw_result)
        elif isinstance(raw_result, NPCGenerationResult):
            return raw_result
        else:
            raise ValueError(f"Unexpected response type: {type(raw_result)}")

    def _load_template(self) -> str:
        """Load the NPC generation prompt template.

        Returns:
            Template string.
        """
        if TEMPLATE_PATH.exists():
            return TEMPLATE_PATH.read_text()

        # Fallback inline template
        return """Generate comprehensive character data for an NPC.

## NPC Context
- Name: {display_name}
- Type: {entity_type}
- Description: {description}
- Personality: {personality_traits}
- Activity: {current_activity}
- Location: {current_location}

## Setting
{setting}

## Time
Day {game_day}, {game_time}

## Instructions
Generate all NPC data including appearance, background, skills, inventory, preferences, and needs.
Consider the setting, time of day, and NPC's role when generating appropriate values.

Return JSON matching NPCGenerationResult schema."""

    def _format_occupation_templates(self, templates: dict) -> str:
        """Format occupation templates for prompt inclusion.

        Args:
            templates: Occupation templates dict.

        Returns:
            Formatted string.
        """
        lines = []
        for occupation, items in templates.items():
            if isinstance(items, list) and items:
                if isinstance(items[0], str):
                    lines.append(f"- {occupation}: {', '.join(items)}")
                else:
                    names = [i.get("display_name", i.get("item_key", "")) for i in items]
                    lines.append(f"- {occupation}: {', '.join(names)}")
        return "\n".join(lines)
