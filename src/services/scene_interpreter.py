"""Scene interpretation service for character-relevant reactions.

Analyzes scenes to detect:
- Need stimuli (food → hunger craving, water → thirst craving)
- Memory triggers (item that reminds of deceased mother)
- Professional interests (fisherman sees masterpiece rod)
- Preference matches (favorite food/color)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from src.database.models.character_memory import CharacterMemory
from src.database.models.character_preferences import CharacterPreferences
from src.database.models.character_state import CharacterNeeds
from src.database.models.entities import Entity, EntitySkill
from src.database.models.enums import EmotionalValence
from src.database.models.items import Item
from src.database.models.session import GameSession
from src.managers.memory_manager import MemoryManager


class ReactionType(str, Enum):
    """Types of reactions to scene elements."""

    CRAVING = "craving"  # Need-based craving boost
    MEMORY_POSITIVE = "memory_positive"  # Positive memory triggered
    MEMORY_NEGATIVE = "memory_negative"  # Negative memory triggered (grief, trauma)
    MEMORY_MIXED = "memory_mixed"  # Bittersweet memory
    PROFESSIONAL_INTEREST = "professional_interest"  # Skill/occupation interest
    PREFERENCE_MATCH = "preference_match"  # Favorite food/color/etc


@dataclass
class SceneReaction:
    """A reaction the character should have to something in the scene."""

    trigger: str  # What triggered this ("red chicken", "apple", "fishing rod")
    reaction_type: ReactionType

    # For cravings (need-based)
    need_affected: str | None = None  # "hunger", "thirst", etc.
    craving_boost: int = 0  # How much to boost craving (0-50)

    # For emotional/memory reactions
    memory_id: int | None = None  # Which CharacterMemory was triggered
    memory_subject: str | None = None  # Subject of the memory for context
    emotion: str | None = None  # "grief", "nostalgia", "fear"
    intensity: int = 0  # 1-10 strength of reaction

    # For professional interest
    skill_key: str | None = None  # "fishing", "blacksmithing"

    # Effects
    morale_change: int = 0  # +/- morale adjustment
    stat_effects: dict[str, int] = field(default_factory=dict)  # Temporary stat changes

    # Narrative hints for GM
    narrative_hint: str = ""  # "You notice a hat that reminds you of your mother"


@dataclass
class NeedSatisfaction:
    """Detected need satisfaction from narration."""

    need_name: str
    satisfaction_amount: int
    action_detected: str  # "ate meal", "drank water", etc.
    confidence: float  # 0.0-1.0


class SceneInterpreter:
    """Analyzes scenes for character-relevant elements.

    Uses a combination of:
    - Rule-based matching for common patterns
    - Memory keyword matching
    - LLM-based semantic analysis for complex cases
    """

    # Food-related keywords that trigger hunger craving
    FOOD_KEYWORDS = {
        "food", "meal", "dish", "plate", "feast", "breakfast", "lunch", "dinner",
        "supper", "snack", "bread", "meat", "cheese", "fruit", "vegetable", "pie",
        "cake", "soup", "stew", "roast", "fish", "chicken", "beef", "pork", "lamb",
        "pastry", "cooking", "baking", "aroma", "smell", "delicious", "tasty",
        "savory", "sweet", "spicy", "herb", "spice", "kitchen", "tavern", "inn",
        "restaurant", "bakery", "apple", "orange", "berry", "grape", "honey",
    }

    # Drink-related keywords that trigger thirst craving
    DRINK_KEYWORDS = {
        "water", "drink", "ale", "beer", "wine", "mead", "tea", "coffee", "juice",
        "flask", "tankard", "goblet", "cup", "well", "spring", "stream", "fountain",
        "thirst", "parched", "refreshing", "cool", "cold", "beverage", "liquid",
        "pour", "sip", "gulp", "tavern", "inn", "bar",
    }

    # Rest-related keywords (for scene detection, not cravings)
    # Note: stamina/sleep_pressure are physical states without psychological cravings
    REST_KEYWORDS = {
        "bed", "sleep", "rest", "tired", "exhausted", "fatigue", "weary", "drowsy",
        "yawn", "pillow", "blanket", "mattress", "inn", "bedroom", "chamber",
        "nap", "slumber", "hammock", "couch", "comfortable", "cozy",
    }

    # Social keywords that trigger social craving
    SOCIAL_KEYWORDS = {
        "friend", "family", "companion", "party", "gathering", "celebration",
        "festival", "crowd", "laughter", "conversation", "chat", "talk",
        "together", "welcome", "embrace", "hug", "company", "lonely", "alone",
    }

    # Intimacy keywords
    INTIMACY_KEYWORDS = {
        "attractive", "beautiful", "handsome", "romantic", "love", "desire",
        "passion", "kiss", "embrace", "partner", "lover", "intimate", "sensual",
        "seductive", "flirt", "charming", "alluring",
    }

    def __init__(self, db: Session, game_session: GameSession) -> None:
        """Initialize the SceneInterpreter.

        Args:
            db: Database session
            game_session: Current game session
        """
        self.db = db
        self.game_session = game_session
        self.memory_manager = MemoryManager(db, game_session)

    def analyze_scene(
        self,
        scene_description: str,
        scene_items: list[Item] | None = None,
        scene_entities: list[Entity] | None = None,
        character: Entity | None = None,
        character_needs: CharacterNeeds | None = None,
        character_preferences: CharacterPreferences | None = None,
        character_memories: list[CharacterMemory] | None = None,
        character_skills: list[EntitySkill] | None = None,
    ) -> list[SceneReaction]:
        """Comprehensive scene analysis for character reactions.

        Checks for:
        1. Need stimuli (food → hunger, water → thirst)
        2. Memory triggers (mother's hat → grief)
        3. Professional interest (fishing rod → fisherman excited)
        4. Preference matches (favorite color/food)

        Args:
            scene_description: Text description of the current scene
            scene_items: Items present in the scene
            scene_entities: NPCs/creatures in the scene
            character: The character whose reactions to check
            character_needs: Character's current needs state
            character_preferences: Character's preferences
            character_memories: Character's significant memories
            character_skills: Character's skills/profession

        Returns:
            List of SceneReaction objects, sorted by intensity/importance
        """
        reactions: list[SceneReaction] = []

        # Combine all text sources for analysis
        all_text = self._build_analysis_text(
            scene_description, scene_items, scene_entities
        )

        # Check need stimuli
        if character_needs:
            need_reactions = self._check_need_stimuli(
                all_text, character_needs, character_preferences
            )
            reactions.extend(need_reactions)

        # Check memory triggers
        if character and character_memories:
            memory_reactions = self._check_memory_triggers(
                all_text, character, character_memories
            )
            reactions.extend(memory_reactions)

        # Check professional interest
        if character_skills:
            skill_reactions = self._check_professional_interest(
                all_text, scene_items or [], character_skills
            )
            reactions.extend(skill_reactions)

        # Sort by intensity/importance (highest first)
        reactions.sort(key=lambda r: r.intensity + abs(r.morale_change), reverse=True)

        return reactions

    def _build_analysis_text(
        self,
        scene_description: str,
        scene_items: list[Item] | None,
        scene_entities: list[Entity] | None,
    ) -> str:
        """Build combined text for analysis.

        Args:
            scene_description: Main scene description
            scene_items: Items in scene
            scene_entities: Entities in scene

        Returns:
            Combined lowercase text for keyword matching
        """
        parts = [scene_description.lower()]

        if scene_items:
            for item in scene_items:
                parts.append(item.display_name.lower())
                if item.description:
                    parts.append(item.description.lower())

        if scene_entities:
            for entity in scene_entities:
                parts.append(entity.display_name.lower())
                # Entity doesn't have description field - use distinguishing_features
                if entity.distinguishing_features:
                    parts.append(entity.distinguishing_features.lower())

        return " ".join(parts)

    def _check_need_stimuli(
        self,
        text: str,
        needs: CharacterNeeds,
        preferences: CharacterPreferences | None,
    ) -> list[SceneReaction]:
        """Check scene for need-triggering stimuli.

        Args:
            text: Combined scene text (lowercase)
            needs: Character's current needs
            preferences: Character's preferences (for amplification)

        Returns:
            List of craving-type reactions
        """
        reactions: list[SceneReaction] = []

        # Check hunger stimuli
        food_matches = self._count_keyword_matches(text, self.FOOD_KEYWORDS)
        if food_matches > 0:
            # More urgent if already hungry
            base_craving = 100 - needs.hunger
            relevance = min(1.0, food_matches / 3)  # Cap at 3 keywords
            boost = self._calculate_craving_boost(base_craving, relevance)

            if boost >= 5:  # Only report significant cravings
                reactions.append(SceneReaction(
                    trigger="food in scene",
                    reaction_type=ReactionType.CRAVING,
                    need_affected="hunger",
                    craving_boost=boost,
                    intensity=min(10, boost // 5),
                    narrative_hint=self._get_craving_hint("hunger", boost),
                ))

        # Check thirst stimuli
        drink_matches = self._count_keyword_matches(text, self.DRINK_KEYWORDS)
        if drink_matches > 0:
            base_craving = 100 - needs.thirst
            relevance = min(1.0, drink_matches / 3)
            boost = self._calculate_craving_boost(base_craving, relevance)

            if boost >= 5:
                reactions.append(SceneReaction(
                    trigger="drink in scene",
                    reaction_type=ReactionType.CRAVING,
                    need_affected="thirst",
                    craving_boost=boost,
                    intensity=min(10, boost // 5),
                    narrative_hint=self._get_craving_hint("thirst", boost),
                ))

        # Note: stamina/sleep_pressure are physical states without psychological cravings,
        # so we don't check for rest stimuli like we do for hunger/thirst.

        # Check social stimuli
        social_matches = self._count_keyword_matches(text, self.SOCIAL_KEYWORDS)
        if social_matches > 0:
            base_craving = 100 - needs.social_connection
            relevance = min(1.0, social_matches / 3)
            boost = self._calculate_craving_boost(base_craving, relevance)

            if boost >= 5:
                reactions.append(SceneReaction(
                    trigger="social atmosphere",
                    reaction_type=ReactionType.CRAVING,
                    need_affected="social_connection",
                    craving_boost=boost,
                    intensity=min(10, boost // 5),
                    narrative_hint=self._get_craving_hint("social", boost),
                ))

        # Check intimacy stimuli
        intimacy_matches = self._count_keyword_matches(text, self.INTIMACY_KEYWORDS)
        if intimacy_matches > 0:
            base_craving = 100 - needs.intimacy
            relevance = min(1.0, intimacy_matches / 3)
            boost = self._calculate_craving_boost(base_craving, relevance)

            if boost >= 5:
                reactions.append(SceneReaction(
                    trigger="romantic atmosphere",
                    reaction_type=ReactionType.CRAVING,
                    need_affected="intimacy",
                    craving_boost=boost,
                    intensity=min(10, boost // 5),
                    narrative_hint=self._get_craving_hint("intimacy", boost),
                ))

        return reactions

    def _count_keyword_matches(self, text: str, keywords: set[str]) -> int:
        """Count how many keywords from a set appear in text.

        Args:
            text: Text to search (should be lowercase)
            keywords: Set of keywords to match

        Returns:
            Count of unique keyword matches
        """
        return sum(1 for kw in keywords if kw in text)

    def _calculate_craving_boost(
        self,
        base_craving: int,
        relevance: float,
        attention: float = 0.6,
    ) -> int:
        """Calculate craving boost from stimulus.

        Formula: boost = relevance * attention * base_craving * 0.6
        Capped at 50.

        Args:
            base_craving: 100 - current_need (how much "room" for craving)
            relevance: How relevant the stimulus is (0.0-1.0)
            attention: How much attention is drawn (default 0.6)

        Returns:
            Craving boost amount (0-50)
        """
        boost = int(relevance * attention * base_craving * 0.6)
        return min(boost, 50)

    def _get_craving_hint(self, need: str, boost: int) -> str:
        """Get narrative hint for a craving.

        Args:
            need: The need being affected
            boost: The craving boost amount

        Returns:
            Narrative hint for the GM
        """
        intensity = "slightly" if boost < 15 else "noticeably" if boost < 30 else "strongly"

        hints = {
            "hunger": f"The sight/smell of food {intensity} whets the appetite.",
            "thirst": f"The presence of drinks {intensity} makes the mouth feel dry.",
            "social": f"The social atmosphere {intensity} draws attention.",
            "intimacy": f"The romantic atmosphere {intensity} stirs feelings.",
        }

        return hints.get(need, f"The scene {intensity} affects {need}.")

    def _check_memory_triggers(
        self,
        text: str,
        character: Entity,
        memories: list[CharacterMemory],
    ) -> list[SceneReaction]:
        """Check scene for memory-triggering elements.

        Args:
            text: Combined scene text (lowercase)
            character: The character
            memories: Character's significant memories

        Returns:
            List of memory-triggered reactions
        """
        reactions: list[SceneReaction] = []

        for memory in memories:
            relevance = memory.matches_keywords(text)

            if relevance >= 0.3:  # Threshold for triggering
                # Determine reaction type based on valence
                if memory.valence == EmotionalValence.POSITIVE:
                    reaction_type = ReactionType.MEMORY_POSITIVE
                    morale_change = min(15, memory.intensity * 2)
                elif memory.valence == EmotionalValence.NEGATIVE:
                    reaction_type = ReactionType.MEMORY_NEGATIVE
                    morale_change = -min(20, memory.intensity * 2)
                elif memory.valence == EmotionalValence.MIXED:
                    reaction_type = ReactionType.MEMORY_MIXED
                    morale_change = 0  # Mixed feelings cancel out
                else:
                    reaction_type = ReactionType.MEMORY_POSITIVE  # Neutral = curiosity
                    morale_change = 2

                # Stat effects for intense trauma
                stat_effects: dict[str, int] = {}
                if (
                    memory.valence == EmotionalValence.NEGATIVE
                    and memory.intensity >= 8
                ):
                    # Trauma can cause WIS penalty
                    stat_effects["WIS"] = -1

                # Build narrative hint
                hint = self._get_memory_hint(memory)

                reactions.append(SceneReaction(
                    trigger=f"memory trigger: {memory.subject}",
                    reaction_type=reaction_type,
                    memory_id=memory.id,
                    memory_subject=memory.subject,
                    emotion=memory.emotion,
                    intensity=memory.intensity,
                    morale_change=morale_change,
                    stat_effects=stat_effects,
                    narrative_hint=hint,
                ))

                # Record the trigger
                self.memory_manager.record_trigger(memory.id)

        return reactions

    def _get_memory_hint(self, memory: CharacterMemory) -> str:
        """Generate narrative hint for a memory trigger.

        Args:
            memory: The triggered memory

        Returns:
            Narrative hint for the GM
        """
        valence_phrases = {
            EmotionalValence.POSITIVE: "brings back fond memories of",
            EmotionalValence.NEGATIVE: "painfully reminds of",
            EmotionalValence.MIXED: "evokes complex feelings about",
            EmotionalValence.NEUTRAL: "reminds of",
        }

        phrase = valence_phrases.get(memory.valence, "reminds of")
        return f"Something here {phrase} {memory.subject}. ({memory.context})"

    def _check_professional_interest(
        self,
        text: str,
        items: list[Item],
        skills: list[EntitySkill],
    ) -> list[SceneReaction]:
        """Check scene for professional interest triggers.

        Args:
            text: Combined scene text
            items: Items in the scene
            skills: Character's skills

        Returns:
            List of professional interest reactions
        """
        reactions: list[SceneReaction] = []

        # Build skill keyword map
        skill_keywords = {
            "fishing": {"fish", "rod", "hook", "line", "bait", "tackle", "reel", "net"},
            "blacksmithing": {"forge", "anvil", "hammer", "smith", "metal", "sword", "armor"},
            "carpentry": {"wood", "plank", "saw", "chisel", "carpentry", "furniture"},
            "alchemy": {"potion", "herb", "alchemist", "brew", "vial", "ingredient"},
            "cooking": {"recipe", "chef", "cook", "kitchen", "ingredient", "spice"},
            "hunting": {"bow", "arrow", "trap", "hunt", "game", "deer", "prey"},
            "herbalism": {"herb", "plant", "flower", "root", "medicinal", "remedy"},
            "mining": {"ore", "mine", "pickaxe", "gem", "stone", "vein"},
            "tailoring": {"cloth", "needle", "thread", "fabric", "sew", "garment"},
            "enchanting": {"enchant", "magical", "rune", "glyph", "arcane"},
        }

        # Check each skill against scene
        for skill in skills:
            skill_key = skill.skill_key.lower()
            keywords = skill_keywords.get(skill_key, set())

            if keywords:
                matches = self._count_keyword_matches(text, keywords)
                if matches >= 2:  # At least 2 keywords for professional interest
                    # Higher proficiency = more excitement
                    intensity = min(10, 3 + skill.proficiency_level)
                    morale_boost = min(5, skill.proficiency_level)

                    reactions.append(SceneReaction(
                        trigger=f"professional interest: {skill_key}",
                        reaction_type=ReactionType.PROFESSIONAL_INTEREST,
                        skill_key=skill_key,
                        intensity=intensity,
                        morale_change=morale_boost,
                        narrative_hint=(
                            f"As a skilled {skill_key.replace('_', ' ')}, "
                            f"you notice the quality/details others might miss."
                        ),
                    ))

        return reactions

    def get_reactions_summary(
        self,
        reactions: list[SceneReaction],
    ) -> dict[str, Any]:
        """Summarize reactions for GM context.

        Args:
            reactions: List of scene reactions

        Returns:
            Summary dictionary with counts and effects
        """
        if not reactions:
            return {
                "has_reactions": False,
                "total_reactions": 0,
                "narrative_hints": [],
            }

        # Group by type
        by_type: dict[str, list[SceneReaction]] = {}
        for r in reactions:
            key = r.reaction_type.value
            if key not in by_type:
                by_type[key] = []
            by_type[key].append(r)

        # Calculate total effects
        total_morale = sum(r.morale_change for r in reactions)
        total_cravings = {
            r.need_affected: r.craving_boost
            for r in reactions
            if r.reaction_type == ReactionType.CRAVING
        }

        return {
            "has_reactions": True,
            "total_reactions": len(reactions),
            "by_type": {k: len(v) for k, v in by_type.items()},
            "total_morale_change": total_morale,
            "cravings_to_apply": total_cravings,
            "narrative_hints": [r.narrative_hint for r in reactions if r.narrative_hint],
            "strongest_reaction": reactions[0] if reactions else None,
        }
