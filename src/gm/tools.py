"""Tools for the Simplified GM Pipeline.

Provides tool functions for skill checks, combat, and entity creation.
These tools are called by the GM LLM during generation.
"""

import logging
import random
from typing import Any, Callable, TYPE_CHECKING

from sqlalchemy.orm import Session

from src.database.models.entities import Entity, EntityAttribute, EntitySkill, NPCExtension
from src.database.models.enums import EntityType, StorageLocationType
from src.database.models.items import Item
from src.database.models.world import Location
from src.database.models.session import GameSession
from src.dice.checks import (
    make_skill_check,
    proficiency_to_modifier,
    calculate_ability_modifier,
)
from src.dice.types import AdvantageType
from src.gm.schemas import (
    SkillCheckResult as GMSkillCheckResult,
    AttackResult,
    DamageResult,
    CreateEntityResult,
    EntityType as GMEntityType,
)
from src.managers.entity_manager import EntityManager
from src.managers.item_manager import ItemManager
from src.managers.location_manager import LocationManager
from src.managers.relationship_manager import RelationshipManager
from src.managers.task_manager import TaskManager
from src.managers.needs import NeedsManager

if TYPE_CHECKING:
    from src.gm.grounding import GroundingManifest

logger = logging.getLogger(__name__)


class KeyResolver:
    """Resolves entity keys with fuzzy matching fallback.

    When the LLM hallucinates entity keys (e.g., uses 'farmer_001' instead
    of 'farmer_marcus'), this class attempts to find the correct key using
    fuzzy string matching.

    Attributes:
        manifest: The grounding manifest with valid entity keys.
        threshold: Minimum similarity score (0.0-1.0) to consider a match.
    """

    def __init__(
        self,
        manifest: "GroundingManifest",
        threshold: float = 0.6,
    ) -> None:
        """Initialize the key resolver.

        Args:
            manifest: Grounding manifest with valid entity keys.
            threshold: Minimum similarity score to accept a fuzzy match.
        """
        self.manifest = manifest
        self.threshold = threshold

    def resolve(self, key: str) -> tuple[str, bool]:
        """Resolve an entity key, with fuzzy matching fallback.

        Args:
            key: The entity key to resolve (possibly hallucinated).

        Returns:
            Tuple of (resolved_key, was_corrected). If was_corrected is True,
            the key was fuzzy-matched to a valid alternative.
        """
        # Exact match - return immediately
        if self.manifest.contains_key(key):
            return key, False

        # Fuzzy match
        similar = self.manifest.find_similar_key(key, self.threshold)
        if similar:
            logger.warning(f"Fuzzy matched entity key: '{key}' -> '{similar}'")
            return similar, True

        # No match found - return original (tool will fail with error)
        return key, False


class GMTools:
    """Tool provider for the GM LLM.

    Handles skill checks, combat rolls, and entity creation.
    Supports both auto mode (immediate results) and manual mode
    (returns pending for player roll animation).
    """

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        player_id: int,
        roll_mode: str = "auto",
        location_key: str | None = None,
        turn_number: int = 1,
        manifest: "GroundingManifest | None" = None,
    ) -> None:
        """Initialize tools.

        Args:
            db: Database session.
            game_session: Current game session.
            player_id: Player entity ID.
            roll_mode: "auto" for background rolls, "manual" for player animation.
            location_key: Current location key (for placing created items).
            turn_number: Current turn number for recording facts.
            manifest: Optional grounding manifest for fuzzy key matching.
        """
        self.db = db
        self.game_session = game_session
        self.session_id = game_session.id
        self.player_id = player_id
        self.roll_mode = roll_mode
        self.location_key = location_key
        self.turn_number = turn_number
        self.manifest = manifest
        self.resolver = KeyResolver(manifest) if manifest else None

        self._entity_manager: EntityManager | None = None
        self._item_manager: ItemManager | None = None
        self._location_manager: LocationManager | None = None
        self._relationship_manager: RelationshipManager | None = None
        self._task_manager: TaskManager | None = None
        self._needs_manager: NeedsManager | None = None

    @property
    def entity_manager(self) -> EntityManager:
        if self._entity_manager is None:
            self._entity_manager = EntityManager(self.db, self.game_session)
        return self._entity_manager

    @property
    def item_manager(self) -> ItemManager:
        if self._item_manager is None:
            self._item_manager = ItemManager(self.db, self.game_session)
        return self._item_manager

    @property
    def location_manager(self) -> LocationManager:
        if self._location_manager is None:
            self._location_manager = LocationManager(self.db, self.game_session)
        return self._location_manager

    @property
    def relationship_manager(self) -> RelationshipManager:
        if self._relationship_manager is None:
            self._relationship_manager = RelationshipManager(self.db, self.game_session)
        return self._relationship_manager

    @property
    def task_manager(self) -> TaskManager:
        if self._task_manager is None:
            self._task_manager = TaskManager(self.db, self.game_session)
        return self._task_manager

    @property
    def needs_manager(self) -> NeedsManager:
        if self._needs_manager is None:
            self._needs_manager = NeedsManager(self.db, self.game_session)
        return self._needs_manager

    def _resolve_key(self, key: str) -> str:
        """Resolve an entity key, applying fuzzy matching if available.

        Args:
            key: Entity key (possibly hallucinated by the LLM).

        Returns:
            Resolved key (may be auto-corrected if fuzzy match found).
        """
        if not self.resolver:
            return key
        resolved, _ = self.resolver.resolve(key)
        return resolved

    def _get_valid_params(self, tool_name: str) -> set[str]:
        """Get valid parameter names for a tool from its definition.

        Args:
            tool_name: Name of the tool.

        Returns:
            Set of valid parameter names.
        """
        for tool in self.get_tool_definitions():
            if tool["name"] == tool_name:
                return set(tool["input_schema"].get("properties", {}).keys())
        return set()

    def _filter_tool_input(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Filter tool input to only valid parameters.

        Prevents crashes when LLM hallucinates extra parameters.

        Args:
            tool_name: Name of the tool.
            tool_input: Raw input from LLM.

        Returns:
            Filtered input with only valid parameters.
        """
        valid_params = self._get_valid_params(tool_name)
        if not valid_params:
            # Unknown tool, return as-is
            return tool_input

        filtered = {k: v for k, v in tool_input.items() if k in valid_params}

        # Log any filtered params for debugging
        extra_params = set(tool_input.keys()) - valid_params
        if extra_params:
            import logging
            logging.getLogger(__name__).warning(
                f"Tool {tool_name}: Ignored hallucinated params: {extra_params}"
            )

        return filtered

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get tool definitions for Claude API.

        Returns:
            List of tool definitions in Claude's format.
        """
        return [
            {
                "name": "skill_check",
                "description": (
                    "Roll a skill check when outcome is uncertain. "
                    "Returns success/failure with roll details."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "skill": {
                            "type": "string",
                            "description": "Skill being checked (e.g., stealth, perception, lockpick)",
                        },
                        "dc": {
                            "type": "integer",
                            "description": "Difficulty Class (10=easy, 15=medium, 20=hard, 25=very hard)",
                        },
                        "context": {
                            "type": "string",
                            "description": "Optional context for the check",
                        },
                    },
                    "required": ["skill", "dc"],
                },
            },
            {
                "name": "attack_roll",
                "description": (
                    "Make an attack against a target. "
                    "Returns hit/miss and damage if hit."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "Entity key of the target",
                        },
                        "weapon": {
                            "type": "string",
                            "description": "Weapon item key (or 'unarmed')",
                        },
                        "attacker": {
                            "type": "string",
                            "description": "Entity key of attacker (default: player)",
                        },
                    },
                    "required": ["target"],
                },
            },
            {
                "name": "damage_entity",
                "description": (
                    "Apply damage to an entity after a hit. "
                    "Returns remaining HP and status."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "Entity key of the target",
                        },
                        "amount": {
                            "type": "integer",
                            "description": "Damage amount to apply",
                        },
                        "damage_type": {
                            "type": "string",
                            "description": "Type of damage (physical, fire, cold, poison)",
                        },
                    },
                    "required": ["target", "amount"],
                },
            },
            {
                "name": "create_entity",
                "description": (
                    "Create a new NPC, item, location, or storage container. "
                    "Use this to introduce new things that don't exist yet."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "entity_type": {
                            "type": "string",
                            "enum": ["npc", "item", "location", "storage"],
                            "description": "Type of entity to create",
                        },
                        "name": {
                            "type": "string",
                            "description": "Display name for the entity",
                        },
                        "description": {
                            "type": "string",
                            "description": "Detailed description",
                        },
                        "gender": {
                            "type": "string",
                            "description": "For NPCs: male, female, or other",
                        },
                        "occupation": {
                            "type": "string",
                            "description": "For NPCs: their job/role",
                        },
                        "item_type": {
                            "type": "string",
                            "description": "For items: weapon, armor, clothing, tool, misc",
                        },
                        "storage_location": {
                            "type": "string",
                            "description": "For items: storage container key where item is placed (e.g., clothes_chest_001)",
                        },
                        "category": {
                            "type": "string",
                            "description": "For locations: interior, exterior, underground",
                        },
                        "parent_location": {
                            "type": "string",
                            "description": "For locations: parent location key",
                        },
                        "container_type": {
                            "type": "string",
                            "enum": ["container", "place"],
                            "description": "For storage: 'container' (chest, barrel, bag) or 'place' (table, shelf, floor)",
                        },
                        "capacity": {
                            "type": "integer",
                            "description": "For storage: max items it can hold (default: unlimited)",
                        },
                    },
                    "required": ["entity_type", "name", "description"],
                },
            },
            {
                "name": "record_fact",
                "description": (
                    "Record a fact about the world using Subject-Predicate-Value pattern. "
                    "Use this when inventing or revealing lore, especially during OOC responses. "
                    "Examples: 'widow_brennan has_occupation herbalist', 'village was_founded 200_years_ago'."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "subject_type": {
                            "type": "string",
                            "enum": ["entity", "location", "world", "item", "group"],
                            "description": "Type of thing the fact is about",
                        },
                        "subject_key": {
                            "type": "string",
                            "description": "Key of the subject (e.g., npc_marcus, village_eldoria)",
                        },
                        "predicate": {
                            "type": "string",
                            "description": "What aspect this describes (e.g., has_occupation, was_born_in, knows_secret)",
                        },
                        "value": {
                            "type": "string",
                            "description": "The value of the fact",
                        },
                        "is_secret": {
                            "type": "boolean",
                            "description": "Whether this is GM-only knowledge (hidden from player)",
                        },
                    },
                    "required": ["subject_type", "subject_key", "predicate", "value"],
                },
            },
            # ===================================================================
            # Relationship Tools
            # ===================================================================
            {
                "name": "get_npc_attitude",
                "description": (
                    "Query an NPC's attitude toward another entity. "
                    "Use before generating NPC dialogue to understand their feelings."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "from_entity": {
                            "type": "string",
                            "description": (
                                "EXACT NPC entity key from context (copy the text BEFORE the colon). "
                                "Example: for 'farmer_marcus: Marcus', use 'farmer_marcus'."
                            ),
                        },
                        "to_entity": {
                            "type": "string",
                            "description": (
                                "Target entity key. Use the player's entity key from context, "
                                "NOT just 'player'. Example: 'test_hero' or 'hero_001'."
                            ),
                        },
                    },
                    "required": ["from_entity", "to_entity"],
                },
            },
            # ===================================================================
            # Quest Tools
            # ===================================================================
            {
                "name": "assign_quest",
                "description": (
                    "Create and assign a new quest to the player. "
                    "Use when an NPC gives the player a mission."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "quest_key": {
                            "type": "string",
                            "description": "Unique quest identifier (e.g., 'find_lost_ring')",
                        },
                        "title": {
                            "type": "string",
                            "description": "Display title for the quest",
                        },
                        "description": {
                            "type": "string",
                            "description": "Quest description and objective",
                        },
                        "giver_entity_key": {
                            "type": "string",
                            "description": "Entity key of the quest giver (optional)",
                        },
                        "rewards": {
                            "type": "string",
                            "description": "Description of rewards (optional)",
                        },
                    },
                    "required": ["quest_key", "title", "description"],
                },
            },
            {
                "name": "update_quest",
                "description": (
                    "Advance a quest to the next stage. "
                    "Use when player completes an objective."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "quest_key": {
                            "type": "string",
                            "description": "Quest key to update",
                        },
                        "notes": {
                            "type": "string",
                            "description": "Progress notes (optional)",
                        },
                    },
                    "required": ["quest_key"],
                },
            },
            {
                "name": "complete_quest",
                "description": "Mark a quest as completed or failed.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "quest_key": {
                            "type": "string",
                            "description": "Quest key to complete",
                        },
                        "outcome": {
                            "type": "string",
                            "enum": ["completed", "failed"],
                            "description": "Whether quest was completed or failed",
                        },
                        "outcome_notes": {
                            "type": "string",
                            "description": "Notes about the outcome (optional)",
                        },
                    },
                    "required": ["quest_key", "outcome"],
                },
            },
            # ===================================================================
            # Task & Appointment Tools
            # ===================================================================
            {
                "name": "create_task",
                "description": (
                    "Add a task/goal for the player to track. "
                    "Use when player accepts a goal or needs a reminder."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "Task description",
                        },
                        "category": {
                            "type": "string",
                            "enum": ["goal", "appointment", "reminder"],
                            "description": "Type of task",
                        },
                        "priority": {
                            "type": "integer",
                            "enum": [1, 2, 3],
                            "description": "Priority: 1=low, 2=medium, 3=high",
                        },
                        "in_game_day": {
                            "type": "integer",
                            "description": "Day number for scheduled tasks (optional)",
                        },
                        "in_game_time": {
                            "type": "string",
                            "description": "Time for scheduled tasks, e.g., '4pm' (optional)",
                        },
                        "location": {
                            "type": "string",
                            "description": "Location for the task (optional)",
                        },
                    },
                    "required": ["description", "category"],
                },
            },
            {
                "name": "complete_task",
                "description": "Mark a task as completed.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "integer",
                            "description": "Task ID to complete",
                        },
                    },
                    "required": ["task_id"],
                },
            },
            {
                "name": "create_appointment",
                "description": (
                    "Schedule a meeting/event with an NPC. "
                    "Use when an NPC or player sets up a future meeting."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "Appointment description",
                        },
                        "game_day": {
                            "type": "integer",
                            "description": "Day number for the appointment",
                        },
                        "game_time": {
                            "type": "string",
                            "description": "Time for the appointment, e.g., '2pm'",
                        },
                        "participants": {
                            "type": "string",
                            "description": "Comma-separated participant names",
                        },
                        "location_name": {
                            "type": "string",
                            "description": "Location for the appointment (optional)",
                        },
                        "initiated_by": {
                            "type": "string",
                            "description": "Who suggested this meeting (optional)",
                        },
                    },
                    "required": ["description", "game_day", "participants"],
                },
            },
            {
                "name": "complete_appointment",
                "description": "Mark an appointment as kept, missed, or cancelled.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "appointment_id": {
                            "type": "integer",
                            "description": "Appointment ID",
                        },
                        "outcome": {
                            "type": "string",
                            "enum": ["kept", "missed", "cancelled"],
                            "description": "What happened with the appointment",
                        },
                        "outcome_notes": {
                            "type": "string",
                            "description": "Notes about the outcome (optional)",
                        },
                    },
                    "required": ["appointment_id", "outcome"],
                },
            },
            # ===================================================================
            # Needs Tools (Tier 3)
            # ===================================================================
            {
                "name": "apply_stimulus",
                "description": (
                    "Create a craving when player sees/smells tempting things. "
                    "Use when describing scenes with food, comfortable beds, etc."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "entity_key": {
                            "type": "string",
                            "description": "Entity key (usually 'player')",
                        },
                        "stimulus_type": {
                            "type": "string",
                            "enum": ["food_sight", "drink_sight", "rest_opportunity",
                                     "social_atmosphere", "intimacy_trigger"],
                            "description": "Type of stimulus",
                        },
                        "stimulus_description": {
                            "type": "string",
                            "description": "What the character sees/smells",
                        },
                        "intensity": {
                            "type": "string",
                            "enum": ["mild", "moderate", "strong"],
                            "description": "How tempting it is",
                        },
                    },
                    "required": ["entity_key", "stimulus_type", "stimulus_description"],
                },
            },
            {
                "name": "mark_need_communicated",
                "description": (
                    "Mark that a need was just mentioned to prevent repetition. "
                    "Call after narrating a character's hunger, thirst, etc."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "entity_key": {
                            "type": "string",
                            "description": "Entity key",
                        },
                        "need_name": {
                            "type": "string",
                            "enum": ["hunger", "thirst", "stamina", "hygiene", "comfort",
                                     "wellness", "social_connection", "morale",
                                     "sense_of_purpose", "intimacy"],
                            "description": "Which need was mentioned",
                        },
                    },
                    "required": ["entity_key", "need_name"],
                },
            },
            # ===================================================================
            # Item Manipulation Tools
            # ===================================================================
            {
                "name": "take_item",
                "description": (
                    "Transfer an item to the player's inventory. "
                    "Use when player explicitly takes, picks up, or grabs an item."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "item_key": {
                            "type": "string",
                            "description": (
                                "EXACT item key from context (copy the text BEFORE the colon). "
                                "Example: for 'bread_001: Bread', use 'bread_001' NOT 'bread'."
                            ),
                        },
                    },
                    "required": ["item_key"],
                },
            },
            {
                "name": "drop_item",
                "description": (
                    "Drop an item from player's inventory at the current location. "
                    "Use when player explicitly drops, puts down, or discards an item."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "item_key": {
                            "type": "string",
                            "description": (
                                "EXACT item key from inventory (copy the text BEFORE the colon). "
                                "Example: for 'sword_001: Iron Sword', use 'sword_001'."
                            ),
                        },
                    },
                    "required": ["item_key"],
                },
            },
            {
                "name": "give_item",
                "description": (
                    "Give an item from player's inventory to an NPC. "
                    "Use when player explicitly gives, hands, or offers an item to someone."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "item_key": {
                            "type": "string",
                            "description": (
                                "EXACT item key from inventory (copy the text BEFORE the colon)."
                            ),
                        },
                        "recipient_key": {
                            "type": "string",
                            "description": (
                                "EXACT NPC entity key from context (copy the text BEFORE the colon). "
                                "Example: for 'farmer_marcus: Marcus', use 'farmer_marcus'."
                            ),
                        },
                    },
                    "required": ["item_key", "recipient_key"],
                },
            },
            {
                "name": "move_to",
                "description": (
                    "Move the player to a new location. Use when player travels to a different area.\n\n"
                    "TRIGGER WORDS: go, walk, leave, travel, head, enter, exit, return, move to, explore\n\n"
                    "Examples:\n"
                    "- 'I leave the tavern' -> move_to(destination='village_square')\n"
                    "- 'I go to the well' -> move_to(destination='the well')\n"
                    "- 'I head home' -> move_to(destination='player_home')\n\n"
                    "The tool will resolve the destination (fuzzy match or create new), "
                    "calculate realistic travel time, and update the player's location."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "destination": {
                            "type": "string",
                            "description": "Location key or display name to travel to",
                        },
                        "travel_method": {
                            "type": "string",
                            "enum": ["walk", "run", "sneak"],
                            "description": "How player is traveling (default: walk)",
                        },
                    },
                    "required": ["destination"],
                },
            },
            {
                "name": "satisfy_need",
                "description": (
                    "Satisfy a character need through an activity or consumption.\n\n"
                    "ACTIVITY-TO-NEED MAPPING (use these exact mappings):\n"
                    "- Eating/food/meal/bread → need=\"hunger\"\n"
                    "- Drinking/water/ale/wine/beverage → need=\"thirst\"\n"
                    "- Resting/sitting/relaxing → need=\"stamina\"\n"
                    "- Sleeping/napping/dozing → need=\"sleep_pressure\"\n"
                    "- Bathing/washing/cleaning → need=\"hygiene\"\n"
                    "- Talking/socializing/chatting → need=\"social_connection\"\n\n"
                    "AMOUNT GUIDE: 10=snack/sip, 25=light meal/drink, 40=full meal, 65=feast."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "need": {
                            "type": "string",
                            "enum": ["hunger", "thirst", "stamina", "hygiene", "comfort",
                                     "wellness", "social_connection", "morale",
                                     "sense_of_purpose", "intimacy"],
                            "description": "Which need is being satisfied",
                        },
                        "amount": {
                            "type": "integer",
                            "description": "Satisfaction amount (10=snack, 25=drink, 40=meal, 60=feast, 100=full)",
                        },
                        "activity": {
                            "type": "string",
                            "description": "Activity description (e.g., 'eating bread', 'taking a bath')",
                        },
                        "item_key": {
                            "type": "string",
                            "description": "Item key if consuming an item (optional)",
                        },
                        "destroys_item": {
                            "type": "boolean",
                            "description": "Whether the item is consumed/destroyed (default: true)",
                        },
                    },
                    "required": ["need", "amount", "activity"],
                },
            },
            # Context-fetching tools for minimal context mode (local LLMs)
            {
                "name": "get_rules",
                "description": (
                    "Get detailed game rules for a category. "
                    "Categories: needs, combat, time, entity_format, examples, storage, items, npc_dialogue"
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "enum": ["needs", "combat", "time", "entity_format", "examples",
                                     "storage", "items", "npc_dialogue"],
                            "description": "Rule category to retrieve",
                        },
                    },
                    "required": ["category"],
                },
            },
            {
                "name": "get_scene_details",
                "description": (
                    "Get full scene details including location description, "
                    "NPCs present, items visible, and available exits."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "get_player_state",
                "description": (
                    "Get the player's current state including inventory, "
                    "equipped items, needs levels, and relationships."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "get_story_context",
                "description": (
                    "Get narrative context including background story, "
                    "recent events summary, and known facts."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "get_time",
                "description": (
                    "Get current game time and elapsed time. "
                    "Use for OOC time queries like 'what time is it' or "
                    "'how long have I been here'."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]

    def execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool call.

        Args:
            tool_name: Name of the tool to execute.
            tool_input: Input parameters for the tool.

        Returns:
            Tool result as a dictionary.
        """
        # Filter input to prevent LLM hallucinated params
        filtered = self._filter_tool_input(tool_name, tool_input)

        if tool_name == "skill_check":
            return self.skill_check(**filtered).model_dump()
        elif tool_name == "attack_roll":
            return self.attack_roll(**filtered).model_dump()
        elif tool_name == "damage_entity":
            return self.damage_entity(**filtered).model_dump()
        elif tool_name == "create_entity":
            # Normalize parameter aliases - LLM sometimes uses shorthand names
            if "type" in tool_input and "entity_type" not in tool_input:
                tool_input["entity_type"] = tool_input.pop("type")
            if "location" in tool_input and "storage_location" not in tool_input:
                tool_input["storage_location"] = tool_input.pop("location")
            if "container" in tool_input and "container_type" not in tool_input:
                tool_input["container_type"] = tool_input.pop("container")
            # Filter to valid parameters only
            allowed_create = {
                "entity_type", "name", "description", "gender", "occupation",
                "item_type", "storage_location", "category", "parent_location",
                "container_type", "capacity"
            }
            tool_input = {k: v for k, v in tool_input.items() if k in allowed_create}

            # Validate required parameters
            if "entity_type" not in tool_input:
                return {
                    "success": False,
                    "error": "Missing required parameter: entity_type",
                    "hint": "create_entity requires entity_type (npc, item, furniture, location)",
                }
            if "name" not in tool_input:
                return {
                    "success": False,
                    "error": "Missing required parameter: name",
                    "hint": "create_entity requires a name for the entity",
                }

            try:
                return self.create_entity(**tool_input).model_dump()
            except Exception as e:
                logger.error(f"create_entity failed with input {tool_input}: {e}")
                return {
                    "success": False,
                    "error": f"Failed to create entity: {str(e)}",
                }
        elif tool_name == "record_fact":
            # Normalize parameter aliases
            if "fact" in tool_input and "value" not in tool_input:
                # LLM sometimes sends {"fact": "..."} instead of structured params
                # Try to parse as value
                tool_input["value"] = tool_input.pop("fact")
            # Filter to valid parameters
            allowed_fact = {"subject_type", "subject_key", "predicate", "value", "is_secret"}
            tool_input = {k: v for k, v in tool_input.items() if k in allowed_fact}

            # Validate required parameters before calling
            required_fact = {"subject_type", "subject_key", "predicate", "value"}
            missing = required_fact - set(tool_input.keys())
            if missing:
                return {
                    "success": False,
                    "error": f"Missing required parameters for record_fact: {', '.join(sorted(missing))}",
                    "hint": "record_fact requires: subject_type, subject_key, predicate, value",
                }

            try:
                return self.record_fact(**tool_input)
            except Exception as e:
                logger.error(f"record_fact failed with input {tool_input}: {e}")
                return {
                    "success": False,
                    "error": f"Failed to record fact: {str(e)}",
                }
        # Relationship tools
        elif tool_name == "get_npc_attitude":
            return self.get_npc_attitude(**filtered)
        # Quest tools
        elif tool_name == "assign_quest":
            return self.assign_quest(**filtered)
        elif tool_name == "update_quest":
            return self.update_quest(**filtered)
        elif tool_name == "complete_quest":
            return self.complete_quest(**filtered)
        # Task & Appointment tools
        elif tool_name == "create_task":
            return self.create_task(**filtered)
        elif tool_name == "complete_task":
            return self.complete_task(**filtered)
        elif tool_name == "create_appointment":
            return self.create_appointment(**filtered)
        elif tool_name == "complete_appointment":
            return self.complete_appointment(**filtered)
        # Needs tools (Tier 3)
        elif tool_name == "apply_stimulus":
            return self.apply_stimulus(**filtered)
        elif tool_name == "mark_need_communicated":
            return self.mark_need_communicated(**filtered)
        # Item manipulation tools
        elif tool_name == "take_item":
            return self.take_item(**filtered)
        elif tool_name == "drop_item":
            return self.drop_item(**filtered)
        elif tool_name == "give_item":
            return self.give_item(**filtered)
        # Need satisfaction tool
        elif tool_name == "satisfy_need":
            return self.satisfy_need(**filtered)
        # Context-fetching tools for minimal context mode
        elif tool_name == "get_rules":
            return self._get_rules(**filtered)
        elif tool_name == "get_scene_details":
            return self._get_scene_details()
        elif tool_name == "get_player_state":
            return self._get_player_state()
        elif tool_name == "get_story_context":
            return self._get_story_context()
        elif tool_name == "get_time":
            return self._get_time()
        else:
            return {"error": f"Unknown tool: {tool_name}"}

    def skill_check(
        self,
        skill: str,
        dc: int,
        context: str = "",
    ) -> GMSkillCheckResult:
        """Execute a skill check.

        Args:
            skill: The skill being checked.
            dc: Difficulty Class.
            context: Optional context for the check.

        Returns:
            SkillCheckResult with roll details.
        """
        # Get player's skill modifier
        skill_modifier = self._get_skill_modifier(self.player_id, skill)
        attribute_modifier = self._get_related_attribute_modifier(self.player_id, skill)

        # Manual mode: return pending for player to roll
        if self.roll_mode == "manual":
            return GMSkillCheckResult(
                pending=True,
                skill=skill,
                dc=dc,
                modifier=skill_modifier + attribute_modifier,
            )

        # Auto mode: roll immediately using the dice system
        result = make_skill_check(
            dc=dc,
            attribute_modifier=attribute_modifier,
            skill_modifier=skill_modifier,
            advantage_type=AdvantageType.NORMAL,
        )

        # Extract roll value (2d10 system)
        if result.roll_result:
            roll = result.roll_result.total - (skill_modifier + attribute_modifier)
        else:
            roll = 11  # Auto-success average

        return GMSkillCheckResult(
            pending=False,
            skill=skill,
            dc=dc,
            modifier=skill_modifier + attribute_modifier,
            roll=roll,
            total=result.roll_result.total if result.roll_result else roll + skill_modifier + attribute_modifier,
            success=result.success,
            critical_success=result.is_critical_success,
            critical_failure=result.is_critical_failure,
        )

    def attack_roll(
        self,
        target: str,
        weapon: str = "unarmed",
        attacker: str | None = None,
    ) -> AttackResult:
        """Make an attack roll.

        Args:
            target: Entity key of the target.
            weapon: Weapon item key or "unarmed".
            attacker: Attacker entity key (default: player).

        Returns:
            AttackResult with hit/miss and damage.
        """
        # Get attacker
        if attacker is None or attacker == "player":
            attacker_entity = self.db.query(Entity).filter(Entity.id == self.player_id).first()
            attacker_key = attacker_entity.entity_key if attacker_entity else "player"
        else:
            attacker_entity = self.entity_manager.get_entity(attacker)
            attacker_key = attacker

        # Get target
        target_entity = self.entity_manager.get_entity(target)
        if not target_entity:
            return AttackResult(
                target=target,
                weapon=weapon,
                attacker=attacker_key,
                roll=0,
                hits=False,
            )

        # Calculate attack bonus
        attack_bonus = self._get_attack_bonus(attacker_entity, weapon)

        # Get target AC (from attributes or default)
        target_ac = self._get_armor_class(target_entity)

        # Manual mode: return pending
        if self.roll_mode == "manual":
            return AttackResult(
                pending=True,
                attacker=attacker_key,
                target=target,
                weapon=weapon,
                attack_bonus=attack_bonus,
                target_ac=target_ac,
            )

        # Auto mode: roll attack
        # Use 2d10 for attack (to be consistent with skill checks)
        roll = random.randint(1, 10) + random.randint(1, 10)
        total = roll + attack_bonus
        hits = total >= target_ac
        critical = roll == 20  # Double 10s

        # Calculate damage if hit
        damage = 0
        if hits:
            damage = self._roll_weapon_damage(weapon, critical)

        return AttackResult(
            pending=False,
            attacker=attacker_key,
            target=target,
            weapon=weapon,
            attack_bonus=attack_bonus,
            target_ac=target_ac,
            roll=roll,
            hits=hits,
            critical=critical,
            damage=damage,
        )

    def damage_entity(
        self,
        target: str,
        amount: int,
        damage_type: str = "physical",
    ) -> DamageResult:
        """Apply damage to an entity.

        Args:
            target: Entity key of the target.
            amount: Damage amount.
            damage_type: Type of damage.

        Returns:
            DamageResult with remaining HP.
        """
        target_entity = self.entity_manager.get_entity(target)
        if not target_entity:
            return DamageResult(
                target=target,
                damage_taken=0,
                remaining_hp=0,
                unconscious=False,
                dead=False,
            )

        # Get current HP (from attributes or default)
        current_hp = self._get_entity_hp(target_entity)
        new_hp = max(0, current_hp - amount)

        # Update HP in database
        self._set_entity_hp(target_entity, new_hp)

        return DamageResult(
            target=target,
            damage_taken=amount,
            remaining_hp=new_hp,
            unconscious=new_hp == 0,
            dead=new_hp <= -10,  # Using negative HP death threshold
        )

    def create_entity(
        self,
        entity_type: str,
        name: str,
        description: str,
        gender: str | None = None,
        occupation: str | None = None,
        item_type: str | None = None,
        storage_location: str | None = None,
        category: str | None = None,
        parent_location: str | None = None,
        container_type: str | None = None,
        capacity: int | None = None,
    ) -> CreateEntityResult:
        """Create a new entity.

        Args:
            entity_type: Type of entity (npc, item, location, storage).
            name: Display name.
            description: Detailed description.
            gender: For NPCs.
            occupation: For NPCs.
            item_type: For items.
            storage_location: For items - key of storage container.
            category: For locations.
            parent_location: For locations.
            container_type: For storage - 'container' or 'place'.
            capacity: For storage - max items.

        Returns:
            CreateEntityResult with the new entity key.
        """
        # For items, extract state adjectives first to get clean base name
        extracted_state = None
        if entity_type == "item":
            from src.services.item_state_extractor import extract_state_from_name
            extraction = extract_state_from_name(name)
            base_name = extraction.base_name
            extracted_state = extraction.state
            # Use base name for key and display
            name = base_name

        # Generate a unique key
        base_key = name.lower().replace(" ", "_").replace("'", "")
        entity_key = f"{base_key}_{random.randint(100, 999)}"

        try:
            if entity_type == "npc":
                # Create the entity with proper EntityType
                entity = self.entity_manager.create_entity(
                    entity_key=entity_key,
                    display_name=name,
                    entity_type=EntityType.NPC,
                    gender=gender or "unknown",
                )
                # Create NPCExtension for location/activity tracking
                npc_extension = NPCExtension(
                    entity_id=entity.id,
                    job=occupation,
                    current_location=self.location_key,
                )
                self.db.add(npc_extension)
                self.db.flush()

                return CreateEntityResult(
                    entity_key=entity_key,
                    entity_type=GMEntityType.NPC,
                    display_name=name,
                    success=True,
                )

            elif entity_type == "item":
                # Get current location ID for placing the item
                owner_location_id = None
                storage_location_id = None

                if self.location_key:
                    location = self.db.query(Location).filter(
                        Location.session_id == self.session_id,
                        Location.location_key == self.location_key,
                    ).first()
                    if location:
                        owner_location_id = location.id

                # Handle storage location if specified
                if storage_location:
                    from src.database.models.items import StorageLocation
                    storage = self.db.query(StorageLocation).filter(
                        StorageLocation.session_id == self.session_id,
                        StorageLocation.location_key == storage_location,
                    ).first()
                    if storage:
                        storage_location_id = storage.id
                        # Track this storage for observation recording
                        if not hasattr(self, '_accessed_storages'):
                            self._accessed_storages = []
                        self._accessed_storages.append(storage.id)

                # Build properties with extracted state
                item_properties = {}
                if extracted_state:
                    item_properties["state"] = dict(extracted_state)

                item = self.item_manager.create_item(
                    item_key=entity_key,
                    display_name=name,
                    description=description,
                    item_type=item_type or "misc",
                    owner_location_id=owner_location_id,
                    storage_location_id=storage_location_id,
                    properties=item_properties if item_properties else None,
                )
                return CreateEntityResult(
                    entity_key=entity_key,
                    entity_type=GMEntityType.ITEM,
                    display_name=name,
                    success=True,
                    storage_location_key=storage_location,
                )

            elif entity_type == "location":
                from src.managers.location_manager import LocationManager
                location_manager = LocationManager(self.db, self.game_session)
                location = location_manager.create_location(
                    location_key=entity_key,
                    display_name=name,
                    description=description,
                    parent_key=parent_location,
                    category=category or "interior",
                )
                return CreateEntityResult(
                    entity_key=entity_key,
                    entity_type=GMEntityType.LOCATION,
                    display_name=name,
                    success=True,
                )

            elif entity_type == "storage":
                # Map container_type string to StorageLocationType enum
                storage_type_map = {
                    "container": StorageLocationType.CONTAINER,
                    "place": StorageLocationType.PLACE,
                }
                storage_type = storage_type_map.get(
                    container_type or "place", StorageLocationType.PLACE
                )

                # Create storage location
                # The 'name' becomes the container_type (e.g., "wooden chest")
                storage = self.item_manager.create_storage(
                    location_key=entity_key,
                    location_type=storage_type,
                    container_type=name,  # Store the name as container type
                    capacity=capacity,
                )
                return CreateEntityResult(
                    entity_key=entity_key,
                    entity_type=GMEntityType.STORAGE,
                    display_name=name,
                    success=True,
                )

            else:
                return CreateEntityResult(
                    entity_key=entity_key,
                    entity_type=GMEntityType.ITEM,  # Default
                    display_name=name,
                    success=False,
                    error=f"Unknown entity type: {entity_type}",
                )

        except Exception as e:
            return CreateEntityResult(
                entity_key=entity_key,
                entity_type=GMEntityType.NPC,
                display_name=name,
                success=False,
                error=str(e),
            )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _get_skill_modifier(self, entity_id: int, skill: str) -> int:
        """Get skill modifier for an entity."""
        skill_record = (
            self.db.query(EntitySkill)
            .filter(
                EntitySkill.entity_id == entity_id,
                EntitySkill.skill_key == skill.lower(),
            )
            .first()
        )

        if skill_record:
            return proficiency_to_modifier(skill_record.proficiency_level)

        return 0  # No proficiency

    def _get_related_attribute_modifier(self, entity_id: int, skill: str) -> int:
        """Get the attribute modifier related to a skill.

        Maps skills to their governing attributes.
        """
        # Skill to attribute mapping
        skill_attributes = {
            "stealth": "dexterity",
            "perception": "wisdom",
            "lockpick": "dexterity",
            "persuasion": "charisma",
            "intimidation": "charisma",
            "athletics": "strength",
            "acrobatics": "dexterity",
            "survival": "wisdom",
            "medicine": "wisdom",
            "investigation": "intelligence",
            "deception": "charisma",
        }

        attribute_key = skill_attributes.get(skill.lower(), "dexterity")

        attribute = (
            self.db.query(EntityAttribute)
            .filter(
                EntityAttribute.entity_id == entity_id,
                EntityAttribute.attribute_key == attribute_key,
            )
            .first()
        )

        if attribute:
            return calculate_ability_modifier(attribute.value)

        return 0  # Default modifier

    def _get_attack_bonus(self, entity: Entity | None, weapon: str) -> int:
        """Calculate attack bonus for an entity with a weapon."""
        if not entity:
            return 0

        # Get strength or dexterity modifier based on weapon
        # For now, use strength for melee, dexterity for ranged
        # TODO: Check weapon properties

        strength_attr = (
            self.db.query(EntityAttribute)
            .filter(
                EntityAttribute.entity_id == entity.id,
                EntityAttribute.attribute_key == "strength",
            )
            .first()
        )

        modifier = 0
        if strength_attr:
            modifier = calculate_ability_modifier(strength_attr.value)

        # Add proficiency bonus (simplified: +2 for most characters)
        return modifier + 2

    def _get_armor_class(self, entity: Entity) -> int:
        """Calculate armor class for an entity."""
        # Base AC is 10
        ac = 10

        # Add dexterity modifier
        dex_attr = (
            self.db.query(EntityAttribute)
            .filter(
                EntityAttribute.entity_id == entity.id,
                EntityAttribute.attribute_key == "dexterity",
            )
            .first()
        )

        if dex_attr:
            ac += calculate_ability_modifier(dex_attr.value)

        # TODO: Add armor bonuses from equipped items

        return ac

    def _roll_weapon_damage(self, weapon: str, critical: bool = False) -> int:
        """Roll damage for a weapon."""
        # Default unarmed damage: 1d4
        if weapon == "unarmed":
            damage = random.randint(1, 4)
        else:
            # TODO: Look up weapon damage from item
            # Default weapon damage: 1d8
            damage = random.randint(1, 8)

        if critical:
            damage *= 2

        return damage

    def _get_entity_hp(self, entity: Entity) -> int:
        """Get current HP for an entity."""
        # Check for HP attribute
        hp_attr = (
            self.db.query(EntityAttribute)
            .filter(
                EntityAttribute.entity_id == entity.id,
                EntityAttribute.attribute_key == "hp",
            )
            .first()
        )

        if hp_attr:
            return hp_attr.value

        # Default HP based on entity type
        if entity.entity_type == EntityType.NPC:
            return 10  # Default NPC HP
        return 20  # Default player HP

    def _set_entity_hp(self, entity: Entity, hp: int) -> None:
        """Set HP for an entity."""
        hp_attr = (
            self.db.query(EntityAttribute)
            .filter(
                EntityAttribute.entity_id == entity.id,
                EntityAttribute.attribute_key == "hp",
            )
            .first()
        )

        if hp_attr:
            hp_attr.value = hp
        else:
            # Create HP attribute
            new_attr = EntityAttribute(
                entity_id=entity.id,
                attribute_key="hp",
                value=hp,
            )
            self.db.add(new_attr)

        self.db.commit()

    def record_fact(
        self,
        subject_type: str,
        subject_key: str,
        predicate: str,
        value: str,
        is_secret: bool = False,
    ) -> dict[str, Any]:
        """Record a fact about the world using SPV pattern.

        Args:
            subject_type: Type of subject (entity, location, world, item, group).
            subject_key: Key of the subject.
            predicate: What aspect this describes.
            value: The value of the fact.
            is_secret: Whether this is GM-only knowledge.

        Returns:
            Result dict with success status.
        """
        from src.database.models.world import Fact
        from src.database.models.enums import FactCategory

        # Check for existing fact with same subject and predicate
        existing = (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.session_id,
                Fact.subject_key == subject_key,
                Fact.predicate == predicate,
            )
            .first()
        )

        if existing:
            # Update existing fact
            existing.value = value
            existing.is_secret = is_secret
            self.db.flush()
            return {
                "success": True,
                "updated": True,
                "message": f"Updated: {subject_key}.{predicate} = {value}",
            }

        # Create new fact
        fact = Fact(
            session_id=self.session_id,
            subject_type=subject_type,
            subject_key=subject_key,
            predicate=predicate,
            value=value,
            category=FactCategory.PERSONAL,
            is_secret=is_secret,
            confidence=80,
            source_turn=self.turn_number,
        )
        self.db.add(fact)
        self.db.flush()

        return {
            "success": True,
            "created": True,
            "message": f"Recorded: {subject_key}.{predicate} = {value}",
        }

    # =========================================================================
    # Relationship Tools
    # =========================================================================

    def get_npc_attitude(
        self,
        from_entity: str,
        to_entity: str,
    ) -> dict[str, Any]:
        """Get NPC attitude toward another entity.

        Args:
            from_entity: NPC entity key whose attitude to check.
            to_entity: Target entity key.

        Returns:
            Dict with attitude dimensions.
        """
        # Resolve keys (fuzzy match if needed)
        from_entity = self._resolve_key(from_entity)
        # Don't resolve "player" - it's a special keyword
        if to_entity != "player":
            to_entity = self._resolve_key(to_entity)

        from_ent = self.entity_manager.get_entity(from_entity)
        if not from_ent:
            return {"error": f"Entity '{from_entity}' not found"}

        # Handle 'player' as target
        if to_entity == "player":
            to_ent_id = self.player_id
        else:
            to_ent = self.entity_manager.get_entity(to_entity)
            if not to_ent:
                return {"error": f"Entity '{to_entity}' not found"}
            to_ent_id = to_ent.id

        attitude = self.relationship_manager.get_attitude(from_ent.id, to_ent_id)

        return {
            "from_entity": from_entity,
            "to_entity": to_entity,
            "knows": attitude.get("knows", False),
            "trust": attitude.get("trust", 50),
            "liking": attitude.get("liking", 50),
            "respect": attitude.get("respect", 50),
            "romantic_interest": attitude.get("romantic_interest", 0),
            "familiarity": attitude.get("familiarity", 0),
            "fear": attitude.get("fear", 0),
            "effective_liking": attitude.get("effective_liking", 50),
        }

    # =========================================================================
    # Quest Tools
    # =========================================================================

    def assign_quest(
        self,
        quest_key: str,
        title: str,
        description: str,
        giver_entity_key: str | None = None,
        rewards: str | None = None,
    ) -> dict[str, Any]:
        """Create and assign a new quest.

        Args:
            quest_key: Unique quest identifier.
            title: Display title.
            description: Quest description.
            giver_entity_key: Quest giver entity key (optional).
            rewards: Reward description (optional).

        Returns:
            Result dict with quest info.
        """
        # Check if quest already exists
        existing = self.task_manager.get_quest(quest_key)
        if existing:
            return {"error": f"Quest '{quest_key}' already exists"}

        # Get giver entity ID if specified
        giver_id = None
        if giver_entity_key:
            giver = self.entity_manager.get_entity(giver_entity_key)
            if giver:
                giver_id = giver.id

        # Create and start quest
        rewards_dict = {"description": rewards} if rewards else None
        quest = self.task_manager.create_quest(
            quest_key=quest_key,
            name=title,
            description=description,
            giver_entity_id=giver_id,
            rewards=rewards_dict,
        )
        self.task_manager.start_quest(quest_key)

        return {
            "success": True,
            "quest_key": quest_key,
            "title": title,
            "message": f"Quest assigned: {title}",
        }

    def update_quest(
        self,
        quest_key: str,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Advance a quest to the next stage.

        Args:
            quest_key: Quest key to update.
            notes: Progress notes (optional).

        Returns:
            Result dict with quest status.
        """
        quest = self.task_manager.get_quest(quest_key)
        if not quest:
            return {"error": f"Quest '{quest_key}' not found"}

        try:
            updated_quest = self.task_manager.complete_quest_stage(quest_key)
            return {
                "success": True,
                "quest_key": quest_key,
                "current_stage": updated_quest.current_stage,
                "status": updated_quest.status.value,
                "message": f"Quest advanced to stage {updated_quest.current_stage}",
            }
        except ValueError as e:
            return {"error": str(e)}

    def complete_quest(
        self,
        quest_key: str,
        outcome: str,
        outcome_notes: str | None = None,
    ) -> dict[str, Any]:
        """Mark a quest as completed or failed.

        Args:
            quest_key: Quest key to complete.
            outcome: 'completed' or 'failed'.
            outcome_notes: Notes about outcome (optional).

        Returns:
            Result dict with final status.
        """
        quest = self.task_manager.get_quest(quest_key)
        if not quest:
            return {"error": f"Quest '{quest_key}' not found"}

        try:
            if outcome == "completed":
                # Complete all remaining stages
                while quest.status.value == "active":
                    quest = self.task_manager.complete_quest_stage(quest_key)
            else:
                quest = self.task_manager.fail_quest(quest_key)

            return {
                "success": True,
                "quest_key": quest_key,
                "status": quest.status.value,
                "message": f"Quest {outcome}: {quest.name}",
            }
        except ValueError as e:
            return {"error": str(e)}

    # =========================================================================
    # Task & Appointment Tools
    # =========================================================================

    def create_task(
        self,
        description: str,
        category: str,
        priority: int = 2,
        in_game_day: int | None = None,
        in_game_time: str | None = None,
        location: str | None = None,
    ) -> dict[str, Any]:
        """Create a new task for the player.

        Args:
            description: Task description.
            category: 'goal', 'appointment', or 'reminder'.
            priority: 1=low, 2=medium, 3=high.
            in_game_day: Optional day number.
            in_game_time: Optional time string.
            location: Optional location.

        Returns:
            Result dict with task ID.
        """
        from src.database.models.enums import TaskCategory

        # Map category string to enum
        category_map = {
            "goal": TaskCategory.GOAL,
            "appointment": TaskCategory.APPOINTMENT,
            "reminder": TaskCategory.REMINDER,
        }
        task_category = category_map.get(category.lower(), TaskCategory.GOAL)

        task = self.task_manager.create_task(
            description=description,
            category=task_category,
            priority=priority,
            in_game_day=in_game_day,
            in_game_time=in_game_time,
            location=location,
        )

        return {
            "success": True,
            "task_id": task.id,
            "description": description,
            "message": f"Task created: {description}",
        }

    def complete_task(
        self,
        task_id: int,
    ) -> dict[str, Any]:
        """Mark a task as completed.

        Args:
            task_id: Task ID to complete.

        Returns:
            Result dict with status.
        """
        try:
            task = self.task_manager.complete_task(task_id)
            return {
                "success": True,
                "task_id": task_id,
                "message": f"Task completed: {task.description}",
            }
        except ValueError as e:
            return {"error": str(e)}

    def create_appointment(
        self,
        description: str,
        game_day: int,
        participants: str,
        game_time: str | None = None,
        location_name: str | None = None,
        initiated_by: str | None = None,
    ) -> dict[str, Any]:
        """Create a new appointment.

        Args:
            description: Appointment description.
            game_day: Day number.
            participants: Comma-separated participant names.
            game_time: Time string (optional).
            location_name: Location (optional).
            initiated_by: Who suggested this (optional).

        Returns:
            Result dict with appointment ID.
        """
        appointment = self.task_manager.create_appointment(
            description=description,
            game_day=game_day,
            participants=participants,
            game_time=game_time,
            location_name=location_name,
            initiated_by=initiated_by,
        )

        return {
            "success": True,
            "appointment_id": appointment.id,
            "game_day": game_day,
            "message": f"Appointment scheduled for day {game_day}: {description}",
        }

    def complete_appointment(
        self,
        appointment_id: int,
        outcome: str,
        outcome_notes: str | None = None,
    ) -> dict[str, Any]:
        """Mark an appointment as kept, missed, or cancelled.

        Args:
            appointment_id: Appointment ID.
            outcome: 'kept', 'missed', or 'cancelled'.
            outcome_notes: Notes about outcome (optional).

        Returns:
            Result dict with status.
        """
        try:
            if outcome == "kept":
                appointment = self.task_manager.complete_appointment(
                    appointment_id, outcome=outcome_notes
                )
            elif outcome == "missed":
                appointment = self.task_manager.mark_appointment_missed(appointment_id)
            elif outcome == "cancelled":
                appointment = self.task_manager.cancel_appointment(appointment_id)
            else:
                return {"error": f"Invalid outcome: {outcome}"}

            return {
                "success": True,
                "appointment_id": appointment_id,
                "status": appointment.status.value,
                "message": f"Appointment {outcome}",
            }
        except ValueError as e:
            return {"error": str(e)}

    # =========================================================================
    # Needs Tools (Tier 3)
    # =========================================================================

    def apply_stimulus(
        self,
        entity_key: str,
        stimulus_type: str,
        stimulus_description: str,
        intensity: str = "moderate",
    ) -> dict[str, Any]:
        """Apply a stimulus to create cravings.

        Args:
            entity_key: Entity key (usually 'player').
            stimulus_type: Type of stimulus.
            stimulus_description: What the character sees/smells.
            intensity: 'mild', 'moderate', or 'strong'.

        Returns:
            Result dict with craving info.
        """
        # Get entity
        if entity_key == "player":
            entity_id = self.player_id
        else:
            entity = self.entity_manager.get_entity(entity_key)
            if not entity:
                return {"error": f"Entity '{entity_key}' not found"}
            entity_id = entity.id

        # Map stimulus type to need
        stimulus_to_need = {
            "food_sight": "hunger",
            "drink_sight": "thirst",
            "rest_opportunity": "stamina",
            "social_atmosphere": "social_connection",
            "intimacy_trigger": "intimacy",
        }
        need_name = stimulus_to_need.get(stimulus_type)
        if not need_name:
            return {"error": f"Unknown stimulus type: {stimulus_type}"}

        # Map intensity to relevance (0.0-1.0) and attention values
        # intensity affects both how relevant and how prominent the stimulus is
        intensity_map = {
            "mild": (0.3, 0.3),      # background, low relevance
            "moderate": (0.6, 0.6),  # described in scene
            "strong": (0.9, 1.0),    # directly offered/prominent
        }
        relevance, attention = intensity_map.get(intensity, (0.6, 0.6))

        # Apply craving via NeedsManager
        try:
            craving_boost = self.needs_manager.apply_craving(
                entity_id,
                need_name,
                relevance=relevance,
                attention=attention,
            )
            return {
                "success": True,
                "entity_key": entity_key,
                "need": need_name,
                "craving_boost": craving_boost,
                "message": f"Applied {intensity} {stimulus_type} craving",
            }
        except Exception as e:
            return {"error": str(e)}

    def mark_need_communicated(
        self,
        entity_key: str,
        need_name: str,
    ) -> dict[str, Any]:
        """Mark that a need was just mentioned to prevent repetition.

        This is a no-op stub for now - the NeedsManager doesn't track
        communication timing yet. Returns success to allow GM to call it.

        Args:
            entity_key: Entity key.
            need_name: Which need was mentioned.

        Returns:
            Result dict with status.
        """
        # Validate entity exists
        if entity_key != "player":
            entity = self.entity_manager.get_entity(entity_key)
            if not entity:
                return {"error": f"Entity '{entity_key}' not found"}

        # TODO: Implement actual tracking in NeedsManager
        # For now, return success without doing anything
        return {
            "success": True,
            "entity_key": entity_key,
            "need_name": need_name,
            "message": f"Marked {need_name} as communicated",
        }

    # ===================================================================
    # Item Manipulation Tools
    # ===================================================================

    def take_item(self, item_key: str) -> dict[str, Any]:
        """Transfer item to player's inventory.

        Args:
            item_key: Item key to take.

        Returns:
            Result dict with success status.
        """
        # Resolve key (fuzzy match if needed)
        item_key = self._resolve_key(item_key)

        item = self.item_manager.get_item(item_key)
        if not item:
            return {"error": f"Item not found: {item_key}"}

        # Check if item is available (not held by another entity)
        if item.holder_id and item.holder_id != self.player_id:
            # Get holder name for error message
            holder = self.entity_manager.get_entity_by_id(item.holder_id)
            holder_name = holder.display_name if holder else "someone"
            return {"error": f"Item is held by {holder_name}"}

        # Transfer to player
        self.item_manager.transfer_item(item_key, to_entity_id=self.player_id)

        return {
            "success": True,
            "item_key": item_key,
            "item_name": item.display_name,
            "message": f"Took {item.display_name}",
        }

    def drop_item(self, item_key: str) -> dict[str, Any]:
        """Drop item at current location.

        Args:
            item_key: Item key to drop.

        Returns:
            Result dict with success status.
        """
        # Resolve key (fuzzy match if needed)
        item_key = self._resolve_key(item_key)

        item = self.item_manager.get_item(item_key)
        if not item:
            return {"error": f"Item not found: {item_key}"}

        # Check if player holds the item
        if item.holder_id != self.player_id:
            return {"error": f"Player does not have {item.display_name}"}

        # Drop at current location
        if not self.location_key:
            return {"error": "No current location"}

        self.item_manager.drop_item(item_key, self.location_key)

        return {
            "success": True,
            "item_key": item_key,
            "item_name": item.display_name,
            "location": self.location_key,
            "message": f"Dropped {item.display_name}",
        }

    def give_item(self, item_key: str, recipient_key: str) -> dict[str, Any]:
        """Give item to an NPC.

        Args:
            item_key: Item key to give.
            recipient_key: Recipient NPC entity key.

        Returns:
            Result dict with success status.
        """
        # Resolve keys (fuzzy match if needed)
        item_key = self._resolve_key(item_key)
        recipient_key = self._resolve_key(recipient_key)

        item = self.item_manager.get_item(item_key)
        if not item:
            return {"error": f"Item not found: {item_key}"}

        if item.holder_id != self.player_id:
            return {"error": f"Player does not have {item.display_name}"}

        recipient = self.entity_manager.get_entity(recipient_key)
        if not recipient:
            return {"error": f"Recipient not found: {recipient_key}"}

        self.item_manager.transfer_item(item_key, to_entity_id=recipient.id)

        return {
            "success": True,
            "item_key": item_key,
            "item_name": item.display_name,
            "recipient_key": recipient_key,
            "recipient_name": recipient.display_name,
            "message": f"Gave {item.display_name} to {recipient.display_name}",
        }

    def satisfy_need(
        self,
        need: str,
        amount: int,
        activity: str,
        item_key: str | None = None,
        destroys_item: bool = True,
    ) -> dict[str, Any]:
        """Satisfy a character need.

        Args:
            need: Need name to satisfy.
            amount: Satisfaction amount.
            activity: Description of the activity.
            item_key: Optional item being consumed.
            destroys_item: Whether item is destroyed.

        Returns:
            Result dict with updated need value.
        """
        # Get current need value
        needs_record = self.needs_manager.get_needs(self.player_id)
        if not needs_record:
            return {"error": "No needs record for player"}

        if not hasattr(needs_record, need):
            return {"error": f"Unknown need: {need}"}

        old_value = getattr(needs_record, need)

        # Apply satisfaction
        self.needs_manager.satisfy_need(
            self.player_id,
            need,
            amount,
            turn=self.game_session.total_turns,
        )

        # Handle item consumption
        if item_key:
            item = self.item_manager.get_item(item_key)
            if item:
                if destroys_item:
                    self.item_manager.delete_item(item_key)
            else:
                return {"error": f"Item not found: {item_key}"}

        # Get new value
        needs_record = self.needs_manager.get_needs(self.player_id)
        new_value = getattr(needs_record, need)

        return {
            "success": True,
            "need": need,
            "activity": activity,
            "old_value": old_value,
            "new_value": new_value,
            "change": new_value - old_value,
            "item_consumed": item_key if (item_key and destroys_item) else None,
            "message": f"Satisfied {need}: {old_value} -> {new_value}",
        }

    def move_to(
        self,
        destination: str,
        travel_method: str = "walk",
    ) -> dict[str, Any]:
        """Move player to a new location.

        Args:
            destination: Location key or display name to travel to.
            travel_method: How to travel (walk, run, sneak).

        Returns:
            Result dict with new location info and travel time.
        """
        if not destination:
            return {"success": False, "error": "No destination provided"}

        original_location = self.location_key

        # Try to fuzzy match existing location
        location = self.location_manager.fuzzy_match_location(destination)

        if not location:
            # Auto-create new location
            location = self.location_manager.resolve_or_create_location(
                location_text=destination,
                parent_hint=self.location_key,
                category="exterior",
                description=f"A location known as {destination}.",
            )

        # Calculate realistic travel time
        travel_time = self._calculate_travel_time(
            self.location_key,
            location.location_key,
            travel_method,
        )

        # Update player location
        self.location_manager.set_player_location(location.location_key)

        # Update instance location_key for subsequent tools in same turn
        self.location_key = location.location_key

        return {
            "success": True,
            "from_location": original_location,
            "to_location": location.location_key,
            "display_name": location.display_name,
            "description": location.description or "",
            "travel_time_minutes": travel_time,
            "message": f"Traveled to {location.display_name} ({travel_time} min)",
        }

    def _calculate_travel_time(
        self,
        from_key: str | None,
        to_key: str,
        method: str,
    ) -> int:
        """Calculate realistic travel time between locations.

        Uses location hierarchy to determine distance:
        - Same location: 0 min
        - Same parent (adjacent rooms/areas): 2 min base
        - Parent-child (entering/exiting): 2 min base
        - Different areas: 10 min base

        Travel method modifiers:
        - walk: 1.0x
        - run: 0.5x
        - sneak: 2.0x

        Args:
            from_key: Origin location key.
            to_key: Destination location key.
            method: Travel method (walk, run, sneak).

        Returns:
            Travel time in minutes (minimum 1).
        """
        # Same location edge case
        if from_key == to_key:
            return 0

        # Default base time if we can't determine relationship
        base_time = 5

        if from_key:
            from_loc = self.location_manager.get_location(from_key)
            to_loc = self.location_manager.get_location(to_key)

            if from_loc and to_loc:
                # Same parent (adjacent rooms/areas): 2 min
                if (
                    from_loc.parent_location_id is not None
                    and from_loc.parent_location_id == to_loc.parent_location_id
                ):
                    base_time = 2
                # Parent-child relationship (entering/exiting): 2 min
                elif (
                    from_loc.parent_location_id == to_loc.id
                    or to_loc.parent_location_id == from_loc.id
                ):
                    base_time = 2
                # Different areas: 10 min
                else:
                    base_time = 10

        # Apply travel method modifier
        method_multipliers = {
            "walk": 1.0,
            "run": 0.5,
            "sneak": 2.0,
        }
        multiplier = method_multipliers.get(method, 1.0)

        return max(1, int(base_time * multiplier))

    # =========================================================================
    # Context-Fetching Tools for Minimal Context Mode
    # =========================================================================

    def _get_rules(self, category: str) -> dict[str, Any]:
        """Get rule content for a category.

        Args:
            category: Rule category (needs, combat, time, entity_format, examples, etc.)

        Returns:
            Dict with rule content or error.
        """
        from src.gm.rule_content import get_rule_content, get_all_categories

        content = get_rule_content(category)
        if content is None:
            return {
                "error": f"Unknown category: {category}",
                "available": get_all_categories(),
            }

        return {"category": category, "content": content}

    def _get_scene_details(self) -> dict[str, Any]:
        """Get full scene details for current location.

        Returns:
            Dict with location, NPCs, items, and exits.
        """
        if not self.location_key:
            return {"error": "No location set"}

        # Get location
        location = (
            self.db.query(Location)
            .filter(
                Location.session_id == self.session_id,
                Location.location_key == self.location_key,
            )
            .first()
        )

        location_info = {
            "key": self.location_key,
            "name": location.display_name if location else self.location_key,
            "description": location.description if location else "No description",
            "atmosphere": location.atmosphere if location else None,
        }

        # Get NPCs
        npcs = self.entity_manager.get_npcs_in_scene(self.location_key)
        npc_list = []
        for npc in npcs[:10]:
            npc_info = {
                "key": npc.entity_key,
                "name": npc.display_name,
            }
            if npc.occupation:
                npc_info["occupation"] = npc.occupation
            if npc.npc_extension and npc.npc_extension.current_mood:
                npc_info["mood"] = npc.npc_extension.current_mood
            npc_list.append(npc_info)

        # Get items at location
        items = self.item_manager.get_items_at_location(self.location_key)
        item_list = [{"key": i.item_key, "name": i.display_name} for i in items[:15]]

        # Get exits
        from src.managers.location_manager import LocationManager
        loc_manager = LocationManager(self.db, self.game_session)
        try:
            accessible = loc_manager.get_accessible_locations(self.location_key)
            exits = [{"key": loc.location_key, "name": loc.display_name} for loc in accessible]
        except Exception:
            exits = []

        return {
            "location": location_info,
            "npcs": npc_list,
            "items": item_list,
            "exits": exits,
        }

    def _get_player_state(self) -> dict[str, Any]:
        """Get player's current state.

        Returns:
            Dict with inventory, equipped, needs, and relationships.
        """
        # Get inventory
        inventory_items = self.item_manager.get_inventory(self.player_id)
        inventory = [{"key": i.item_key, "name": i.display_name} for i in inventory_items[:20]]

        # Get equipped items
        equipped_items = self.item_manager.get_equipped_items(self.player_id)
        equipped = []
        for item in equipped_items:
            equipped.append({
                "key": item.item_key,
                "name": item.display_name,
                "slot": item.body_slot or "unknown",
            })

        # Get needs
        needs_record = self.needs_manager.get_needs(self.player_id)
        needs = {}
        if needs_record:
            needs = {
                "hunger": needs_record.hunger,
                "thirst": needs_record.thirst,
                "stamina": needs_record.stamina,
                "hygiene": needs_record.hygiene,
                "comfort": needs_record.comfort,
                "wellness": needs_record.wellness,
                "sleep_pressure": needs_record.sleep_pressure,
            }

        # Get relationships
        relationships_data = self.relationship_manager.get_relationships_for_entity(
            self.player_id, direction="to"
        )
        relationships = []
        for rel in relationships_data[:10]:
            if rel.knows:
                npc = self.db.query(Entity).filter(Entity.id == rel.from_entity_id).first()
                if npc:
                    relationships.append({
                        "npc": npc.display_name,
                        "trust": rel.trust or 50,
                        "liking": rel.liking or 50,
                    })

        return {
            "inventory": inventory,
            "equipped": equipped,
            "needs": needs,
            "relationships": relationships,
        }

    def _get_story_context(self) -> dict[str, Any]:
        """Get narrative context.

        Returns:
            Dict with story summary, recent events, and known facts.
        """
        from src.database.models.world import Fact
        from src.managers.summary_manager import SummaryManager

        summary_manager = SummaryManager(self.db, self.game_session)

        # Get story and recent summaries
        story_summary = summary_manager.get_story_summary() or "Story just beginning"
        recent_summary = summary_manager.get_recent_summary() or "No recent events"

        # Get known facts
        facts = (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.session_id,
                Fact.is_secret == False,
            )
            .limit(20)
            .all()
        )
        fact_list = [
            {"subject": f.subject_key, "predicate": f.predicate, "value": f.value}
            for f in facts
        ]

        return {
            "story_summary": story_summary,
            "recent_events": recent_summary,
            "known_facts": fact_list,
        }

    def _get_time(self) -> dict[str, Any]:
        """Get current game time information.

        Returns:
            Dict with current_day, current_time, day_of_week, period,
            elapsed_today (human-readable), and elapsed_minutes.
        """
        from src.managers.time_manager import TimeManager

        tm = TimeManager(self.db, self.game_session)
        day, time_str = tm.get_current_time()
        dow = tm.get_day_of_week()
        period = tm.get_period_of_day()
        elapsed = tm.calculate_elapsed_minutes()

        # Format elapsed as human-readable
        if elapsed < 0:
            elapsed_str = "before session start"
        elif elapsed == 0:
            elapsed_str = "just started"
        elif elapsed < 60:
            elapsed_str = f"{elapsed} minute{'s' if elapsed != 1 else ''}"
        else:
            hours = elapsed // 60
            mins = elapsed % 60
            elapsed_str = f"{hours} hour{'s' if hours != 1 else ''}"
            if mins > 0:
                elapsed_str += f" and {mins} minute{'s' if mins != 1 else ''}"

        return {
            "current_day": day,
            "current_time": time_str,
            "day_of_week": dow.value,
            "period": period,
            "elapsed_today": elapsed_str,
            "elapsed_minutes": elapsed,
        }
