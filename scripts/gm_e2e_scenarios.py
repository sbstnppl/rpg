"""GM Pipeline E2E Test Scenarios - Immersive Goal-Based Testing.

Defines goal-oriented scenarios for LLM-driven E2E testing.
Each scenario specifies a goal for the test player agent to achieve,
and success criteria to validate the outcome.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FocusArea(str, Enum):
    """Categories of gameplay mechanics being tested."""

    DIALOG = "dialog"
    HUNGER = "hunger"
    THIRST = "thirst"
    SLEEP = "sleep"
    HYGIENE = "hygiene"
    COMFORT = "comfort"
    STAMINA = "stamina"
    SOCIAL = "social"
    WELLNESS = "wellness"
    MORALE = "morale"
    PURPOSE = "purpose"
    INTIMACY = "intimacy"
    ITEM_TAKE = "item_take"
    ITEM_DROP = "item_drop"
    ITEM_GIVE = "item_give"
    ITEM_USE = "item_use"
    MOVEMENT_LOCAL = "movement_local"
    MOVEMENT_TRAVEL = "movement_travel"
    SKILL_CHECK = "skill_check"
    OOC = "ooc"
    QUEST = "quest"


@dataclass
class SuccessCriterion:
    """A single criterion for scenario success."""

    description: str
    check_type: str  # "db_change", "tool_called", "narrative_contains", "need_change"
    params: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.description


@dataclass
class ImmersiveScenario:
    """A goal-oriented test scenario for immersive testing.

    The test player agent will naturally pursue the goal through gameplay,
    and success is measured by the criteria rather than exact actions.
    """

    name: str
    goal: str  # What the player agent should try to achieve
    setup_context: str  # Describes the initial situation
    success_criteria: list[SuccessCriterion]
    min_turns: int = 3
    max_turns: int = 10
    focus_areas: list[FocusArea] = field(default_factory=list)
    priority: int = 1  # 1=critical, 2=important, 3=nice-to-have

    @property
    def criteria_descriptions(self) -> list[str]:
        """Return human-readable success criteria."""
        return [str(c) for c in self.success_criteria]


# =============================================================================
# HELPER FUNCTIONS FOR CREATING CRITERIA
# =============================================================================


def need_decreased(need_name: str, min_decrease: int = 10) -> SuccessCriterion:
    """Criterion: A need value decreased by at least min_decrease."""
    return SuccessCriterion(
        description=f"{need_name} need decreased by {min_decrease}+",
        check_type="need_change",
        params={"need": need_name, "direction": "decrease", "min_delta": min_decrease},
    )


def need_increased(need_name: str, min_increase: int = 10) -> SuccessCriterion:
    """Criterion: A need value increased by at least min_increase."""
    return SuccessCriterion(
        description=f"{need_name} need increased by {min_increase}+",
        check_type="need_change",
        params={"need": need_name, "direction": "increase", "min_delta": min_increase},
    )


def tool_called(tool_name: str) -> SuccessCriterion:
    """Criterion: A specific tool was called."""
    return SuccessCriterion(
        description=f"Tool '{tool_name}' was called",
        check_type="tool_called",
        params={"tool": tool_name},
    )


def item_taken() -> SuccessCriterion:
    """Criterion: An item was picked up by the player."""
    return SuccessCriterion(
        description="Item holder_id changed to player",
        check_type="db_change",
        params={"table": "items", "field": "holder_id", "expected": "player"},
    )


def item_dropped() -> SuccessCriterion:
    """Criterion: An item was dropped by the player."""
    return SuccessCriterion(
        description="Item holder_id changed to null/storage",
        check_type="db_change",
        params={"table": "items", "field": "holder_id", "expected": "null"},
    )


def dialog_occurred() -> SuccessCriterion:
    """Criterion: NPC dialog happened in narrative."""
    return SuccessCriterion(
        description="NPC spoke in response (dialog occurred)",
        check_type="narrative_contains",
        params={"patterns": ["says", "replies", "responds", "asks", "tells you"]},
    )


def time_passed(min_minutes: int = 1, max_minutes: int = 60) -> SuccessCriterion:
    """Criterion: Game time advanced within range."""
    return SuccessCriterion(
        description=f"Time passed: {min_minutes}-{max_minutes} minutes",
        check_type="time_passed",
        params={"min": min_minutes, "max": max_minutes},
    )


def narrative_quality() -> SuccessCriterion:
    """Criterion: Narrative meets quality standards."""
    return SuccessCriterion(
        description="Narrative is immersive (no breaks, proper length)",
        check_type="narrative_quality",
        params={"min_chars": 50},
    )


# =============================================================================
# DIALOG SCENARIOS (10+)
# =============================================================================

DIALOG_GREETING = ImmersiveScenario(
    name="Dialog: Simple Greeting",
    goal="Greet the person in the room and have a brief exchange",
    setup_context="Player is in a farmhouse with an NPC named Marcus",
    success_criteria=[
        dialog_occurred(),
        narrative_quality(),
        time_passed(1, 5),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.DIALOG],
    priority=1,
)

DIALOG_ASK_NAME = ImmersiveScenario(
    name="Dialog: Ask NPC's Name",
    goal="Learn the name of the person you're talking to",
    setup_context="Player is with an NPC, wants to know their name",
    success_criteria=[
        dialog_occurred(),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.DIALOG],
    priority=1,
)

DIALOG_ASK_LOCATION = ImmersiveScenario(
    name="Dialog: Ask About Location",
    goal="Ask the NPC about this place and learn something new",
    setup_context="Player wants information about the current location",
    success_criteria=[
        dialog_occurred(),
        tool_called("record_fact"),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=6,
    focus_areas=[FocusArea.DIALOG],
    priority=1,
)

DIALOG_EXTENDED_CHAT = ImmersiveScenario(
    name="Dialog: Extended Conversation",
    goal="Have a longer conversation with the NPC, at least 3 exchanges",
    setup_context="Player wants to build rapport through conversation",
    success_criteria=[
        dialog_occurred(),
        time_passed(5, 15),
        narrative_quality(),
    ],
    min_turns=4,
    max_turns=8,
    focus_areas=[FocusArea.DIALOG, FocusArea.SOCIAL],
    priority=2,
)

DIALOG_FAREWELL = ImmersiveScenario(
    name="Dialog: Polite Farewell",
    goal="End a conversation politely and say goodbye",
    setup_context="Player has been talking and wants to leave",
    success_criteria=[
        dialog_occurred(),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=4,
    focus_areas=[FocusArea.DIALOG],
    priority=2,
)

DIALOG_REQUEST_INFO = ImmersiveScenario(
    name="Dialog: Request Specific Information",
    goal="Ask the NPC for specific helpful information or advice",
    setup_context="Player needs guidance or directions",
    success_criteria=[
        dialog_occurred(),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.DIALOG],
    priority=2,
)

DIALOG_SHARE_STORY = ImmersiveScenario(
    name="Dialog: Share Stories",
    goal="Exchange stories or experiences with the NPC",
    setup_context="Player wants to bond through storytelling",
    success_criteria=[
        dialog_occurred(),
        time_passed(5, 20),
        narrative_quality(),
    ],
    min_turns=3,
    max_turns=8,
    focus_areas=[FocusArea.DIALOG, FocusArea.SOCIAL],
    priority=3,
)

DIALOG_NEGOTIATE = ImmersiveScenario(
    name="Dialog: Negotiate or Persuade",
    goal="Try to convince the NPC of something",
    setup_context="Player wants something from the NPC",
    success_criteria=[
        dialog_occurred(),
        tool_called("skill_check"),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=6,
    focus_areas=[FocusArea.DIALOG, FocusArea.SKILL_CHECK],
    priority=2,
)

DIALOG_COMFORT = ImmersiveScenario(
    name="Dialog: Offer Comfort",
    goal="Comfort or reassure the NPC emotionally",
    setup_context="Player notices the NPC seems troubled",
    success_criteria=[
        dialog_occurred(),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=6,
    focus_areas=[FocusArea.DIALOG, FocusArea.SOCIAL],
    priority=3,
)

DIALOG_HUMOR = ImmersiveScenario(
    name="Dialog: Light Humor",
    goal="Share a joke or lighten the mood with the NPC",
    setup_context="Player wants to make the conversation more pleasant",
    success_criteria=[
        dialog_occurred(),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.DIALOG, FocusArea.MORALE],
    priority=3,
)


# =============================================================================
# HUNGER SCENARIOS (5+)
# =============================================================================

HUNGER_EAT_BREAD = ImmersiveScenario(
    name="Hunger: Eat Available Bread",
    goal="Find and eat the bread to satisfy hunger",
    setup_context="Player is hungry, bread is visible on the table",
    success_criteria=[
        need_increased("hunger", 15),  # Higher hunger value = more satisfied
        time_passed(5, 20),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=6,
    focus_areas=[FocusArea.HUNGER, FocusArea.ITEM_TAKE],
    priority=1,
)

HUNGER_ASK_FOR_FOOD = ImmersiveScenario(
    name="Hunger: Ask NPC for Food",
    goal="Ask the NPC if they have any food to share",
    setup_context="Player is hungry and wants to ask for food",
    success_criteria=[
        dialog_occurred(),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=6,
    focus_areas=[FocusArea.HUNGER, FocusArea.DIALOG],
    priority=2,
)

HUNGER_SEARCH_FOOD = ImmersiveScenario(
    name="Hunger: Search for Food",
    goal="Search the area to find something to eat",
    setup_context="Player is hungry and looking for food",
    success_criteria=[
        tool_called("skill_check"),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=6,
    focus_areas=[FocusArea.HUNGER, FocusArea.SKILL_CHECK],
    priority=2,
)

HUNGER_ACCEPT_OFFERED = ImmersiveScenario(
    name="Hunger: Accept Offered Food",
    goal="Accept food if the NPC offers any during conversation",
    setup_context="Player is hungry and talking to hospitable NPC",
    success_criteria=[
        dialog_occurred(),
        narrative_quality(),
    ],
    min_turns=3,
    max_turns=8,
    focus_areas=[FocusArea.HUNGER, FocusArea.DIALOG],
    priority=2,
)

HUNGER_SHARE_MEAL = ImmersiveScenario(
    name="Hunger: Share a Meal",
    goal="Eat together with the NPC, making it a social experience",
    setup_context="Player wants to eat and socialize together",
    success_criteria=[
        dialog_occurred(),
        time_passed(10, 40),
        narrative_quality(),
    ],
    min_turns=3,
    max_turns=8,
    focus_areas=[FocusArea.HUNGER, FocusArea.SOCIAL],
    priority=3,
)


# =============================================================================
# THIRST SCENARIOS (5+)
# =============================================================================

THIRST_DRINK_WATER = ImmersiveScenario(
    name="Thirst: Drink Available Water",
    goal="Find and drink water to quench thirst",
    setup_context="Player is thirsty, water jug is visible",
    success_criteria=[
        need_increased("thirst", 15),  # Higher thirst value = more hydrated
        time_passed(1, 5),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.THIRST, FocusArea.ITEM_USE],
    priority=1,
)

THIRST_ASK_FOR_DRINK = ImmersiveScenario(
    name="Thirst: Ask for a Drink",
    goal="Ask the NPC for something to drink",
    setup_context="Player is thirsty and wants to ask for a drink",
    success_criteria=[
        dialog_occurred(),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.THIRST, FocusArea.DIALOG],
    priority=2,
)

THIRST_FIND_WATER = ImmersiveScenario(
    name="Thirst: Find Water Source",
    goal="Search for a water source like a well or stream",
    setup_context="Player is thirsty and needs to find water",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=6,
    focus_areas=[FocusArea.THIRST, FocusArea.MOVEMENT_LOCAL],
    priority=2,
)

THIRST_DRINK_TOGETHER = ImmersiveScenario(
    name="Thirst: Share Drinks Socially",
    goal="Have a drink together with the NPC",
    setup_context="Player wants to drink and chat",
    success_criteria=[
        dialog_occurred(),
        time_passed(5, 20),
        narrative_quality(),
    ],
    min_turns=3,
    max_turns=7,
    focus_areas=[FocusArea.THIRST, FocusArea.SOCIAL],
    priority=3,
)

THIRST_TAKE_SIP = ImmersiveScenario(
    name="Thirst: Quick Sip",
    goal="Take a quick sip of water without lingering",
    setup_context="Player is a bit thirsty, just needs a quick drink",
    success_criteria=[
        time_passed(1, 3),
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=3,
    focus_areas=[FocusArea.THIRST],
    priority=2,
)


# =============================================================================
# SLEEP SCENARIOS (5+)
# =============================================================================

SLEEP_TAKE_NAP = ImmersiveScenario(
    name="Sleep: Take a Short Nap",
    goal="Find a place to rest and take a short nap",
    setup_context="Player is tired and wants a quick rest",
    success_criteria=[
        need_decreased("sleep_pressure", 10),
        time_passed(20, 60),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.SLEEP],
    priority=1,
)

SLEEP_FULL_REST = ImmersiveScenario(
    name="Sleep: Full Night's Rest",
    goal="Get a full night's sleep to fully recover",
    setup_context="Player is exhausted and needs proper rest",
    success_criteria=[
        need_decreased("sleep_pressure", 30),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.SLEEP],
    priority=1,
)

SLEEP_FIND_BED = ImmersiveScenario(
    name="Sleep: Find a Bed",
    goal="Look for a bed or comfortable place to sleep",
    setup_context="Player needs to find where to sleep",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=6,
    focus_areas=[FocusArea.SLEEP, FocusArea.MOVEMENT_LOCAL],
    priority=2,
)

SLEEP_ASK_LODGING = ImmersiveScenario(
    name="Sleep: Ask About Lodging",
    goal="Ask the NPC where you could sleep for the night",
    setup_context="Player needs a place to stay",
    success_criteria=[
        dialog_occurred(),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.SLEEP, FocusArea.DIALOG],
    priority=2,
)

SLEEP_REST_EYES = ImmersiveScenario(
    name="Sleep: Close Eyes Briefly",
    goal="Just close your eyes and rest for a moment",
    setup_context="Player is a bit tired but doesn't need full sleep",
    success_criteria=[
        time_passed(5, 20),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=4,
    focus_areas=[FocusArea.SLEEP, FocusArea.STAMINA],
    priority=3,
)


# =============================================================================
# STAMINA SCENARIOS (5+)
# =============================================================================

STAMINA_SIT_REST = ImmersiveScenario(
    name="Stamina: Sit and Rest",
    goal="Sit down and catch your breath",
    setup_context="Player is winded and needs to recover stamina",
    success_criteria=[
        need_increased("stamina", 10),
        time_passed(5, 15),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.STAMINA],
    priority=1,
)

STAMINA_LEAN_WALL = ImmersiveScenario(
    name="Stamina: Lean Against Wall",
    goal="Find something to lean on and rest briefly",
    setup_context="Player needs a quick breather",
    success_criteria=[
        time_passed(2, 10),
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=4,
    focus_areas=[FocusArea.STAMINA],
    priority=2,
)

STAMINA_CATCH_BREATH = ImmersiveScenario(
    name="Stamina: Catch Your Breath",
    goal="Stop and take a moment to recover from exertion",
    setup_context="Player just did something tiring",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=3,
    focus_areas=[FocusArea.STAMINA],
    priority=2,
)

STAMINA_TAKE_BREAK = ImmersiveScenario(
    name="Stamina: Take a Proper Break",
    goal="Take a longer break to fully recover energy",
    setup_context="Player is quite tired from activity",
    success_criteria=[
        time_passed(10, 30),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.STAMINA],
    priority=2,
)

STAMINA_STRETCH = ImmersiveScenario(
    name="Stamina: Stretch and Relax",
    goal="Stretch your muscles and relax for a moment",
    setup_context="Player wants to loosen up",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=4,
    focus_areas=[FocusArea.STAMINA, FocusArea.COMFORT],
    priority=3,
)


# =============================================================================
# COMFORT SCENARIOS (5+)
# =============================================================================

COMFORT_SIT_BY_FIRE = ImmersiveScenario(
    name="Comfort: Sit by the Fire",
    goal="Sit by the fireplace and warm up",
    setup_context="There's a fire in the hearth, player wants warmth",
    success_criteria=[
        need_increased("comfort", 10),
        time_passed(5, 20),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.COMFORT],
    priority=1,
)

COMFORT_FIND_SHADE = ImmersiveScenario(
    name="Comfort: Find Shade",
    goal="Find a cool, shady spot to escape the heat",
    setup_context="Player is hot and seeking relief",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.COMFORT, FocusArea.MOVEMENT_LOCAL],
    priority=2,
)

COMFORT_ADJUST_CLOTHING = ImmersiveScenario(
    name="Comfort: Adjust Clothing",
    goal="Adjust your clothing to be more comfortable",
    setup_context="Player's clothes are uncomfortable",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=4,
    focus_areas=[FocusArea.COMFORT],
    priority=2,
)

COMFORT_RELAX_CHAIR = ImmersiveScenario(
    name="Comfort: Relax in Chair",
    goal="Find a comfortable seat and relax",
    setup_context="Player wants to sit comfortably",
    success_criteria=[
        time_passed(5, 20),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.COMFORT],
    priority=2,
)

COMFORT_SHELTER_RAIN = ImmersiveScenario(
    name="Comfort: Seek Shelter",
    goal="Find shelter from the elements",
    setup_context="Weather is unpleasant, player seeks cover",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=6,
    focus_areas=[FocusArea.COMFORT, FocusArea.MOVEMENT_LOCAL],
    priority=2,
)


# =============================================================================
# HYGIENE SCENARIOS (5+)
# =============================================================================

HYGIENE_WASH_HANDS = ImmersiveScenario(
    name="Hygiene: Wash Hands",
    goal="Find water and wash your hands",
    setup_context="Player's hands are dirty",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=4,
    focus_areas=[FocusArea.HYGIENE],
    priority=1,
)

HYGIENE_WASH_FACE = ImmersiveScenario(
    name="Hygiene: Wash Face",
    goal="Freshen up by washing your face",
    setup_context="Player wants to feel cleaner",
    success_criteria=[
        time_passed(2, 10),
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=4,
    focus_areas=[FocusArea.HYGIENE],
    priority=2,
)

HYGIENE_FULL_BATH = ImmersiveScenario(
    name="Hygiene: Take a Bath",
    goal="Take a proper bath to get fully clean",
    setup_context="Player needs a thorough cleaning",
    success_criteria=[
        need_decreased("hygiene", 20),
        time_passed(15, 45),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.HYGIENE],
    priority=1,
)

HYGIENE_FIND_WATER = ImmersiveScenario(
    name="Hygiene: Find Place to Wash",
    goal="Look for somewhere to wash up",
    setup_context="Player needs to find water for washing",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=6,
    focus_areas=[FocusArea.HYGIENE, FocusArea.MOVEMENT_LOCAL],
    priority=2,
)

HYGIENE_CLEAN_CLOTHES = ImmersiveScenario(
    name="Hygiene: Change Clothes",
    goal="Change into clean clothes if available",
    setup_context="Player's clothes are dirty",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.HYGIENE],
    priority=3,
)


# =============================================================================
# SOCIAL SCENARIOS (5+)
# =============================================================================

SOCIAL_CHAT = ImmersiveScenario(
    name="Social: Casual Chat",
    goal="Have a friendly casual chat with the NPC",
    setup_context="Player wants social interaction",
    success_criteria=[
        dialog_occurred(),
        time_passed(5, 15),
        narrative_quality(),
    ],
    min_turns=3,
    max_turns=7,
    focus_areas=[FocusArea.SOCIAL, FocusArea.DIALOG],
    priority=1,
)

SOCIAL_DEEP_TALK = ImmersiveScenario(
    name="Social: Heart-to-Heart",
    goal="Have a meaningful deeper conversation",
    setup_context="Player wants to connect on a deeper level",
    success_criteria=[
        dialog_occurred(),
        time_passed(10, 30),
        narrative_quality(),
    ],
    min_turns=4,
    max_turns=10,
    focus_areas=[FocusArea.SOCIAL, FocusArea.DIALOG],
    priority=2,
)

SOCIAL_SHARE_STORIES = ImmersiveScenario(
    name="Social: Share Stories",
    goal="Exchange stories and experiences with the NPC",
    setup_context="Player wants to bond through storytelling",
    success_criteria=[
        dialog_occurred(),
        time_passed(10, 25),
        narrative_quality(),
    ],
    min_turns=3,
    max_turns=8,
    focus_areas=[FocusArea.SOCIAL],
    priority=2,
)

SOCIAL_GROUP_TIME = ImmersiveScenario(
    name="Social: Spend Time Together",
    goal="Just spend quality time with the NPC",
    setup_context="Player enjoys the NPC's company",
    success_criteria=[
        time_passed(10, 40),
        narrative_quality(),
    ],
    min_turns=3,
    max_turns=8,
    focus_areas=[FocusArea.SOCIAL],
    priority=2,
)

SOCIAL_CATCH_UP = ImmersiveScenario(
    name="Social: Catch Up",
    goal="Catch up with the NPC about recent events",
    setup_context="Player wants to know what's been happening",
    success_criteria=[
        dialog_occurred(),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=6,
    focus_areas=[FocusArea.SOCIAL, FocusArea.DIALOG],
    priority=2,
)


# =============================================================================
# WELLNESS SCENARIOS (5+)
# =============================================================================

WELLNESS_BANDAGE = ImmersiveScenario(
    name="Wellness: Apply Bandage",
    goal="Tend to wounds with bandages",
    setup_context="Player has minor injuries",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.WELLNESS],
    priority=2,
)

WELLNESS_REST_HEAL = ImmersiveScenario(
    name="Wellness: Rest to Heal",
    goal="Rest quietly to help your body heal",
    setup_context="Player needs recovery time",
    success_criteria=[
        time_passed(30, 120),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.WELLNESS, FocusArea.SLEEP],
    priority=2,
)

WELLNESS_SEEK_HELP = ImmersiveScenario(
    name="Wellness: Ask NPC for Medical Help",
    goal="Ask the NPC for help with injuries or illness",
    setup_context="Player needs medical assistance",
    success_criteria=[
        dialog_occurred(),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=6,
    focus_areas=[FocusArea.WELLNESS, FocusArea.DIALOG],
    priority=2,
)

WELLNESS_TAKE_MEDICINE = ImmersiveScenario(
    name="Wellness: Take Medicine",
    goal="Take medicine or herbal remedy",
    setup_context="Player has access to medicine",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=4,
    focus_areas=[FocusArea.WELLNESS, FocusArea.ITEM_USE],
    priority=2,
)

WELLNESS_CLEAN_WOUND = ImmersiveScenario(
    name="Wellness: Clean a Wound",
    goal="Properly clean and care for a wound",
    setup_context="Player has a wound that needs cleaning",
    success_criteria=[
        time_passed(5, 20),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.WELLNESS, FocusArea.HYGIENE],
    priority=2,
)


# =============================================================================
# MORALE SCENARIOS (5+)
# =============================================================================

MORALE_CELEBRATE = ImmersiveScenario(
    name="Morale: Celebrate Success",
    goal="Celebrate a recent accomplishment",
    setup_context="Player has reason to be happy",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.MORALE],
    priority=2,
)

MORALE_ENJOY_MUSIC = ImmersiveScenario(
    name="Morale: Enjoy Music",
    goal="Listen to or make music for enjoyment",
    setup_context="There's an opportunity for music",
    success_criteria=[
        time_passed(5, 20),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.MORALE],
    priority=3,
)

MORALE_APPRECIATE_VIEW = ImmersiveScenario(
    name="Morale: Appreciate Surroundings",
    goal="Take a moment to appreciate something beautiful",
    setup_context="There's something nice to observe",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=4,
    focus_areas=[FocusArea.MORALE],
    priority=3,
)

MORALE_LAUGH = ImmersiveScenario(
    name="Morale: Share a Laugh",
    goal="Find something to laugh about with the NPC",
    setup_context="Player wants to lighten the mood",
    success_criteria=[
        dialog_occurred(),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.MORALE, FocusArea.SOCIAL],
    priority=2,
)

MORALE_REFLECT = ImmersiveScenario(
    name="Morale: Positive Reflection",
    goal="Reflect on positive memories or accomplishments",
    setup_context="Player takes time for positive reflection",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=4,
    focus_areas=[FocusArea.MORALE],
    priority=3,
)


# =============================================================================
# PURPOSE SCENARIOS (5+)
# =============================================================================

PURPOSE_SET_GOAL = ImmersiveScenario(
    name="Purpose: Set a Goal",
    goal="Decide on a clear goal or objective",
    setup_context="Player needs direction",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=4,
    focus_areas=[FocusArea.PURPOSE],
    priority=2,
)

PURPOSE_COMMIT = ImmersiveScenario(
    name="Purpose: Commit to a Cause",
    goal="Dedicate yourself to helping someone or something",
    setup_context="There's a cause worth committing to",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.PURPOSE, FocusArea.DIALOG],
    priority=2,
)

PURPOSE_REMEMBER = ImmersiveScenario(
    name="Purpose: Remember Your Mission",
    goal="Remind yourself why you're on this journey",
    setup_context="Player needs motivation",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=3,
    focus_areas=[FocusArea.PURPOSE],
    priority=3,
)

PURPOSE_PLAN = ImmersiveScenario(
    name="Purpose: Make a Plan",
    goal="Think through and plan your next steps",
    setup_context="Player needs to strategize",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=4,
    focus_areas=[FocusArea.PURPOSE],
    priority=2,
)

PURPOSE_HELP_OTHER = ImmersiveScenario(
    name="Purpose: Offer to Help",
    goal="Offer to help the NPC with something",
    setup_context="Player wants to be useful",
    success_criteria=[
        dialog_occurred(),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.PURPOSE, FocusArea.DIALOG],
    priority=2,
)


# =============================================================================
# INTIMACY SCENARIOS (5+)
# =============================================================================

INTIMACY_HOLD_HAND = ImmersiveScenario(
    name="Intimacy: Hold Hand",
    goal="Take the other person's hand gently",
    setup_context="There's an appropriate intimate moment",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=4,
    focus_areas=[FocusArea.INTIMACY],
    priority=3,
)

INTIMACY_EMBRACE = ImmersiveScenario(
    name="Intimacy: Give a Hug",
    goal="Embrace the other person warmly",
    setup_context="A hug would be appropriate",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=3,
    focus_areas=[FocusArea.INTIMACY],
    priority=3,
)

INTIMACY_COMFORT_TOUCH = ImmersiveScenario(
    name="Intimacy: Comforting Touch",
    goal="Offer a comforting touch on the shoulder",
    setup_context="The NPC needs comfort",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=4,
    focus_areas=[FocusArea.INTIMACY, FocusArea.SOCIAL],
    priority=3,
)

INTIMACY_SIT_CLOSE = ImmersiveScenario(
    name="Intimacy: Sit Close Together",
    goal="Sit close to the other person companionably",
    setup_context="Sharing a quiet moment",
    success_criteria=[
        time_passed(5, 20),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.INTIMACY, FocusArea.COMFORT],
    priority=3,
)

INTIMACY_SHARE_WARMTH = ImmersiveScenario(
    name="Intimacy: Share Warmth",
    goal="Huddle together for warmth",
    setup_context="It's cold and you're both there",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=4,
    focus_areas=[FocusArea.INTIMACY, FocusArea.COMFORT],
    priority=3,
)


# =============================================================================
# ITEM TAKE SCENARIOS (5+)
# =============================================================================

ITEM_TAKE_GROUND = ImmersiveScenario(
    name="Item: Pick Up From Ground",
    goal="Pick up an item you notice on the ground or table",
    setup_context="There are items available to pick up",
    success_criteria=[
        item_taken(),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.ITEM_TAKE],
    priority=1,
)

ITEM_TAKE_SEARCH = ImmersiveScenario(
    name="Item: Search and Take",
    goal="Search the area and take anything useful you find",
    setup_context="Player wants to search for items",
    success_criteria=[
        tool_called("skill_check"),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=6,
    focus_areas=[FocusArea.ITEM_TAKE, FocusArea.SKILL_CHECK],
    priority=1,
)

ITEM_TAKE_SPECIFIC = ImmersiveScenario(
    name="Item: Take Specific Item",
    goal="Take a specific item you've identified",
    setup_context="Player knows what they want to take",
    success_criteria=[
        item_taken(),
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=4,
    focus_areas=[FocusArea.ITEM_TAKE],
    priority=1,
)

ITEM_TAKE_STORAGE = ImmersiveScenario(
    name="Item: Take From Container",
    goal="Open a container and take something from it",
    setup_context="There's a container with items",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.ITEM_TAKE, FocusArea.ITEM_USE],
    priority=2,
)

ITEM_TAKE_ASK = ImmersiveScenario(
    name="Item: Ask to Take",
    goal="Ask the NPC if you can take something",
    setup_context="Items belong to the NPC",
    success_criteria=[
        dialog_occurred(),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.ITEM_TAKE, FocusArea.DIALOG],
    priority=2,
)


# =============================================================================
# ITEM DROP SCENARIOS (5+)
# =============================================================================

ITEM_DROP_GROUND = ImmersiveScenario(
    name="Item: Drop on Ground",
    goal="Put down something you're carrying",
    setup_context="Player wants to drop an item",
    success_criteria=[
        item_dropped(),
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=3,
    focus_areas=[FocusArea.ITEM_DROP],
    priority=1,
)

ITEM_DROP_TABLE = ImmersiveScenario(
    name="Item: Place on Surface",
    goal="Set an item down on a table or surface",
    setup_context="Player wants to put something down carefully",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=3,
    focus_areas=[FocusArea.ITEM_DROP],
    priority=2,
)

ITEM_DROP_STORAGE = ImmersiveScenario(
    name="Item: Put in Container",
    goal="Store an item in a container or storage",
    setup_context="Player wants to stow an item",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=4,
    focus_areas=[FocusArea.ITEM_DROP],
    priority=2,
)

ITEM_DROP_GIVE_BACK = ImmersiveScenario(
    name="Item: Return Item",
    goal="Return something you borrowed",
    setup_context="Player has something that belongs to another",
    success_criteria=[
        dialog_occurred(),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=4,
    focus_areas=[FocusArea.ITEM_DROP, FocusArea.ITEM_GIVE],
    priority=2,
)

ITEM_DROP_DISCARD = ImmersiveScenario(
    name="Item: Discard Unwanted",
    goal="Get rid of something you don't need",
    setup_context="Player wants to discard an item",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=3,
    focus_areas=[FocusArea.ITEM_DROP],
    priority=2,
)


# =============================================================================
# ITEM GIVE SCENARIOS (5+)
# =============================================================================

ITEM_GIVE_GIFT = ImmersiveScenario(
    name="Item: Give as Gift",
    goal="Give something to the NPC as a gift",
    setup_context="Player wants to be generous",
    success_criteria=[
        dialog_occurred(),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.ITEM_GIVE, FocusArea.DIALOG],
    priority=2,
)

ITEM_GIVE_SHARE = ImmersiveScenario(
    name="Item: Share Item",
    goal="Share something you have with the NPC",
    setup_context="Player wants to share",
    success_criteria=[
        dialog_occurred(),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=4,
    focus_areas=[FocusArea.ITEM_GIVE, FocusArea.SOCIAL],
    priority=2,
)

ITEM_GIVE_TRADE = ImmersiveScenario(
    name="Item: Trade Items",
    goal="Trade an item with the NPC",
    setup_context="Player wants to make a trade",
    success_criteria=[
        dialog_occurred(),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=6,
    focus_areas=[FocusArea.ITEM_GIVE, FocusArea.DIALOG],
    priority=2,
)

ITEM_GIVE_OFFER = ImmersiveScenario(
    name="Item: Offer Help Item",
    goal="Offer an item that might help the NPC",
    setup_context="NPC could use something you have",
    success_criteria=[
        dialog_occurred(),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.ITEM_GIVE, FocusArea.SOCIAL],
    priority=2,
)

ITEM_GIVE_LEND = ImmersiveScenario(
    name="Item: Lend Item",
    goal="Lend something to the NPC temporarily",
    setup_context="NPC needs to borrow something",
    success_criteria=[
        dialog_occurred(),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.ITEM_GIVE, FocusArea.DIALOG],
    priority=3,
)


# =============================================================================
# ITEM USE SCENARIOS (5+)
# =============================================================================

ITEM_USE_TOOL = ImmersiveScenario(
    name="Item: Use a Tool",
    goal="Use a tool for its intended purpose",
    setup_context="Player has a tool to use",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.ITEM_USE],
    priority=2,
)

ITEM_USE_OPEN = ImmersiveScenario(
    name="Item: Open Container",
    goal="Open a chest, door, or container",
    setup_context="There's something to open",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=4,
    focus_areas=[FocusArea.ITEM_USE],
    priority=1,
)

ITEM_USE_READ = ImmersiveScenario(
    name="Item: Read Something",
    goal="Read a book, note, or inscription",
    setup_context="There's something readable",
    success_criteria=[
        time_passed(2, 15),
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=4,
    focus_areas=[FocusArea.ITEM_USE],
    priority=2,
)

ITEM_USE_LIGHT = ImmersiveScenario(
    name="Item: Light Source",
    goal="Light a torch, candle, or lamp",
    setup_context="Player needs light",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=3,
    focus_areas=[FocusArea.ITEM_USE],
    priority=2,
)

ITEM_USE_EXAMINE = ImmersiveScenario(
    name="Item: Examine Closely",
    goal="Examine an item closely for details",
    setup_context="Player wants to inspect something",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=4,
    focus_areas=[FocusArea.ITEM_USE],
    priority=2,
)


# =============================================================================
# MOVEMENT LOCAL SCENARIOS (5+)
# =============================================================================

MOVE_LOCAL_EXIT = ImmersiveScenario(
    name="Movement: Exit Building",
    goal="Go outside from the current building",
    setup_context="Player wants to leave the building",
    success_criteria=[
        time_passed(1, 5),
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=4,
    focus_areas=[FocusArea.MOVEMENT_LOCAL],
    priority=1,
)

MOVE_LOCAL_ENTER = ImmersiveScenario(
    name="Movement: Enter Building",
    goal="Enter a nearby building or structure",
    setup_context="There's a building to enter",
    success_criteria=[
        time_passed(1, 5),
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=4,
    focus_areas=[FocusArea.MOVEMENT_LOCAL],
    priority=1,
)

MOVE_LOCAL_APPROACH = ImmersiveScenario(
    name="Movement: Approach Something",
    goal="Walk over to something or someone nearby",
    setup_context="Player wants to get closer to something",
    success_criteria=[
        time_passed(1, 3),
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=3,
    focus_areas=[FocusArea.MOVEMENT_LOCAL],
    priority=1,
)

MOVE_LOCAL_EXPLORE = ImmersiveScenario(
    name="Movement: Explore Area",
    goal="Move around and explore the immediate area",
    setup_context="Player wants to see what's around",
    success_criteria=[
        time_passed(2, 10),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.MOVEMENT_LOCAL],
    priority=1,
)

MOVE_LOCAL_REPOSITION = ImmersiveScenario(
    name="Movement: Change Position",
    goal="Move to a different spot in the current area",
    setup_context="Player wants to reposition",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=3,
    focus_areas=[FocusArea.MOVEMENT_LOCAL],
    priority=2,
)


# =============================================================================
# MOVEMENT TRAVEL SCENARIOS (5+)
# =============================================================================

MOVE_TRAVEL_NEARBY = ImmersiveScenario(
    name="Travel: Go to Nearby Location",
    goal="Travel to a nearby visible destination",
    setup_context="There's a place nearby to go to",
    success_criteria=[
        time_passed(5, 30),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.MOVEMENT_TRAVEL],
    priority=1,
)

MOVE_TRAVEL_ROAD = ImmersiveScenario(
    name="Travel: Follow the Road",
    goal="Travel along the road or path",
    setup_context="There's a road to follow",
    success_criteria=[
        time_passed(10, 60),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.MOVEMENT_TRAVEL],
    priority=2,
)

MOVE_TRAVEL_ASK = ImmersiveScenario(
    name="Travel: Ask for Directions",
    goal="Ask the NPC for directions to somewhere",
    setup_context="Player needs directions",
    success_criteria=[
        dialog_occurred(),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.MOVEMENT_TRAVEL, FocusArea.DIALOG],
    priority=1,
)

MOVE_TRAVEL_RETURN = ImmersiveScenario(
    name="Travel: Return from Where You Came",
    goal="Go back the way you came",
    setup_context="Player wants to backtrack",
    success_criteria=[
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.MOVEMENT_TRAVEL],
    priority=2,
)

MOVE_TRAVEL_DESTINATION = ImmersiveScenario(
    name="Travel: Head to Specific Place",
    goal="Travel to a specific named destination",
    setup_context="Player knows where they want to go",
    success_criteria=[
        time_passed(10, 120),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=6,
    focus_areas=[FocusArea.MOVEMENT_TRAVEL],
    priority=1,
)


# =============================================================================
# SKILL CHECK SCENARIOS (5+)
# =============================================================================

SKILL_STEALTH = ImmersiveScenario(
    name="Skill: Sneak Quietly",
    goal="Move stealthily without being noticed",
    setup_context="Player wants to be sneaky",
    success_criteria=[
        tool_called("skill_check"),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.SKILL_CHECK],
    priority=1,
)

SKILL_PERCEPTION = ImmersiveScenario(
    name="Skill: Listen Carefully",
    goal="Listen carefully for sounds or danger",
    setup_context="Player wants to detect something",
    success_criteria=[
        tool_called("skill_check"),
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=4,
    focus_areas=[FocusArea.SKILL_CHECK],
    priority=1,
)

SKILL_ATHLETICS = ImmersiveScenario(
    name="Skill: Physical Challenge",
    goal="Attempt a physical feat like climbing or jumping",
    setup_context="There's a physical challenge",
    success_criteria=[
        tool_called("skill_check"),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.SKILL_CHECK],
    priority=1,
)

SKILL_PERSUADE = ImmersiveScenario(
    name="Skill: Persuade Someone",
    goal="Convince the NPC of something through persuasion",
    setup_context="Player wants to persuade",
    success_criteria=[
        tool_called("skill_check"),
        dialog_occurred(),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=6,
    focus_areas=[FocusArea.SKILL_CHECK, FocusArea.DIALOG],
    priority=1,
)

SKILL_SEARCH = ImmersiveScenario(
    name="Skill: Search Thoroughly",
    goal="Search the area thoroughly for hidden things",
    setup_context="Player wants to find hidden items",
    success_criteria=[
        tool_called("skill_check"),
        narrative_quality(),
    ],
    min_turns=2,
    max_turns=5,
    focus_areas=[FocusArea.SKILL_CHECK],
    priority=1,
)


# =============================================================================
# OOC SCENARIOS (5+)
# =============================================================================

OOC_TIME = ImmersiveScenario(
    name="OOC: Check Game Time",
    goal="Ask what time it is in the game (out of character)",
    setup_context="Player wants to know game time",
    success_criteria=[
        time_passed(0, 0),  # OOC should not advance time
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=2,
    focus_areas=[FocusArea.OOC],
    priority=1,
)

OOC_INVENTORY = ImmersiveScenario(
    name="OOC: Check Inventory",
    goal="Ask what you're carrying (out of character)",
    setup_context="Player wants to check inventory",
    success_criteria=[
        time_passed(0, 0),
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=2,
    focus_areas=[FocusArea.OOC],
    priority=1,
)

OOC_NEEDS = ImmersiveScenario(
    name="OOC: Check Needs Status",
    goal="Ask about your character's needs (out of character)",
    setup_context="Player wants to know their status",
    success_criteria=[
        time_passed(0, 0),
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=2,
    focus_areas=[FocusArea.OOC],
    priority=1,
)

OOC_LOCATION = ImmersiveScenario(
    name="OOC: Check Location",
    goal="Ask where you are (out of character)",
    setup_context="Player wants location info",
    success_criteria=[
        time_passed(0, 0),
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=2,
    focus_areas=[FocusArea.OOC],
    priority=2,
)

OOC_SKILLS = ImmersiveScenario(
    name="OOC: Check Skills",
    goal="Ask about your character's skills (out of character)",
    setup_context="Player wants skill info",
    success_criteria=[
        time_passed(0, 0),
        narrative_quality(),
    ],
    min_turns=1,
    max_turns=2,
    focus_areas=[FocusArea.OOC],
    priority=2,
)


# =============================================================================
# ALL SCENARIOS COLLECTION
# =============================================================================

# Group all scenarios by category for easy access
DIALOG_SCENARIOS = [
    DIALOG_GREETING,
    DIALOG_ASK_NAME,
    DIALOG_ASK_LOCATION,
    DIALOG_EXTENDED_CHAT,
    DIALOG_FAREWELL,
    DIALOG_REQUEST_INFO,
    DIALOG_SHARE_STORY,
    DIALOG_NEGOTIATE,
    DIALOG_COMFORT,
    DIALOG_HUMOR,
]

HUNGER_SCENARIOS = [
    HUNGER_EAT_BREAD,
    HUNGER_ASK_FOR_FOOD,
    HUNGER_SEARCH_FOOD,
    HUNGER_ACCEPT_OFFERED,
    HUNGER_SHARE_MEAL,
]

THIRST_SCENARIOS = [
    THIRST_DRINK_WATER,
    THIRST_ASK_FOR_DRINK,
    THIRST_FIND_WATER,
    THIRST_DRINK_TOGETHER,
    THIRST_TAKE_SIP,
]

SLEEP_SCENARIOS = [
    SLEEP_TAKE_NAP,
    SLEEP_FULL_REST,
    SLEEP_FIND_BED,
    SLEEP_ASK_LODGING,
    SLEEP_REST_EYES,
]

STAMINA_SCENARIOS = [
    STAMINA_SIT_REST,
    STAMINA_LEAN_WALL,
    STAMINA_CATCH_BREATH,
    STAMINA_TAKE_BREAK,
    STAMINA_STRETCH,
]

COMFORT_SCENARIOS = [
    COMFORT_SIT_BY_FIRE,
    COMFORT_FIND_SHADE,
    COMFORT_ADJUST_CLOTHING,
    COMFORT_RELAX_CHAIR,
    COMFORT_SHELTER_RAIN,
]

HYGIENE_SCENARIOS = [
    HYGIENE_WASH_HANDS,
    HYGIENE_WASH_FACE,
    HYGIENE_FULL_BATH,
    HYGIENE_FIND_WATER,
    HYGIENE_CLEAN_CLOTHES,
]

SOCIAL_SCENARIOS = [
    SOCIAL_CHAT,
    SOCIAL_DEEP_TALK,
    SOCIAL_SHARE_STORIES,
    SOCIAL_GROUP_TIME,
    SOCIAL_CATCH_UP,
]

WELLNESS_SCENARIOS = [
    WELLNESS_BANDAGE,
    WELLNESS_REST_HEAL,
    WELLNESS_SEEK_HELP,
    WELLNESS_TAKE_MEDICINE,
    WELLNESS_CLEAN_WOUND,
]

MORALE_SCENARIOS = [
    MORALE_CELEBRATE,
    MORALE_ENJOY_MUSIC,
    MORALE_APPRECIATE_VIEW,
    MORALE_LAUGH,
    MORALE_REFLECT,
]

PURPOSE_SCENARIOS = [
    PURPOSE_SET_GOAL,
    PURPOSE_COMMIT,
    PURPOSE_REMEMBER,
    PURPOSE_PLAN,
    PURPOSE_HELP_OTHER,
]

INTIMACY_SCENARIOS = [
    INTIMACY_HOLD_HAND,
    INTIMACY_EMBRACE,
    INTIMACY_COMFORT_TOUCH,
    INTIMACY_SIT_CLOSE,
    INTIMACY_SHARE_WARMTH,
]

ITEM_TAKE_SCENARIOS = [
    ITEM_TAKE_GROUND,
    ITEM_TAKE_SEARCH,
    ITEM_TAKE_SPECIFIC,
    ITEM_TAKE_STORAGE,
    ITEM_TAKE_ASK,
]

ITEM_DROP_SCENARIOS = [
    ITEM_DROP_GROUND,
    ITEM_DROP_TABLE,
    ITEM_DROP_STORAGE,
    ITEM_DROP_GIVE_BACK,
    ITEM_DROP_DISCARD,
]

ITEM_GIVE_SCENARIOS = [
    ITEM_GIVE_GIFT,
    ITEM_GIVE_SHARE,
    ITEM_GIVE_TRADE,
    ITEM_GIVE_OFFER,
    ITEM_GIVE_LEND,
]

ITEM_USE_SCENARIOS = [
    ITEM_USE_TOOL,
    ITEM_USE_OPEN,
    ITEM_USE_READ,
    ITEM_USE_LIGHT,
    ITEM_USE_EXAMINE,
]

MOVEMENT_LOCAL_SCENARIOS = [
    MOVE_LOCAL_EXIT,
    MOVE_LOCAL_ENTER,
    MOVE_LOCAL_APPROACH,
    MOVE_LOCAL_EXPLORE,
    MOVE_LOCAL_REPOSITION,
]

MOVEMENT_TRAVEL_SCENARIOS = [
    MOVE_TRAVEL_NEARBY,
    MOVE_TRAVEL_ROAD,
    MOVE_TRAVEL_ASK,
    MOVE_TRAVEL_RETURN,
    MOVE_TRAVEL_DESTINATION,
]

SKILL_SCENARIOS = [
    SKILL_STEALTH,
    SKILL_PERCEPTION,
    SKILL_ATHLETICS,
    SKILL_PERSUADE,
    SKILL_SEARCH,
]

OOC_SCENARIOS = [
    OOC_TIME,
    OOC_INVENTORY,
    OOC_NEEDS,
    OOC_LOCATION,
    OOC_SKILLS,
]

# All scenarios combined
ALL_IMMERSIVE_SCENARIOS = (
    DIALOG_SCENARIOS
    + HUNGER_SCENARIOS
    + THIRST_SCENARIOS
    + SLEEP_SCENARIOS
    + STAMINA_SCENARIOS
    + COMFORT_SCENARIOS
    + HYGIENE_SCENARIOS
    + SOCIAL_SCENARIOS
    + WELLNESS_SCENARIOS
    + MORALE_SCENARIOS
    + PURPOSE_SCENARIOS
    + INTIMACY_SCENARIOS
    + ITEM_TAKE_SCENARIOS
    + ITEM_DROP_SCENARIOS
    + ITEM_GIVE_SCENARIOS
    + ITEM_USE_SCENARIOS
    + MOVEMENT_LOCAL_SCENARIOS
    + MOVEMENT_TRAVEL_SCENARIOS
    + SKILL_SCENARIOS
    + OOC_SCENARIOS
)

# Priority 1 scenarios for quick testing
PRIORITY_1_SCENARIOS = [s for s in ALL_IMMERSIVE_SCENARIOS if s.priority == 1]

# Quick test subset
QUICK_TEST_SCENARIOS = [
    DIALOG_GREETING,
    HUNGER_EAT_BREAD,
    THIRST_DRINK_WATER,
    ITEM_TAKE_GROUND,
    OOC_TIME,
]


# =============================================================================
# LEGACY COMPATIBILITY
# =============================================================================
# Keep old format for backwards compatibility during transition


@dataclass
class ActionExpectations:
    """Legacy: Expected outcomes for an action."""

    min_chars: int = 50
    max_chars: int | None = None
    min_time: int = 0
    max_time: int = 60
    expected_tools: list[str] | None = None
    forbidden_tools: list[str] | None = None
    expected_db_changes: list[str] | None = None


@dataclass
class TestAction:
    """Legacy: A single action in a test scenario."""

    input: str
    description: str
    expectations: ActionExpectations = field(default_factory=ActionExpectations)


@dataclass
class TestScenario:
    """Legacy: A complete test scenario with flowing actions."""

    name: str
    description: str
    actions: list[TestAction]


# Legacy scenarios for backwards compatibility
ALL_SCENARIOS = [
    TestScenario(
        name="Exploration and Dialog",
        description="Player explores area, discovers NPC, has conversation",
        actions=[
            TestAction(
                input="I look around",
                description="Initial scene exploration",
                expectations=ActionExpectations(min_chars=100, max_time=5),
            ),
            TestAction(
                input="I go to the person and say hello",
                description="Approach and greet NPC",
                expectations=ActionExpectations(
                    min_chars=50, max_time=5, expected_tools=["get_npc_attitude"]
                ),
            ),
        ],
    ),
]
