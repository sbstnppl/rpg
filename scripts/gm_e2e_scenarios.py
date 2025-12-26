"""GM Pipeline E2E Test Scenarios.

Defines flowing gameplay scenarios for natural E2E testing.
Each scenario is a sequence of actions that build context turn-by-turn.
"""

from dataclasses import dataclass, field


@dataclass
class ActionExpectations:
    """Expected outcomes for an action."""

    min_chars: int = 50
    max_chars: int | None = None
    min_time: int = 0
    max_time: int = 60
    expected_tools: list[str] | None = None
    forbidden_tools: list[str] | None = None
    expected_db_changes: list[str] | None = None


@dataclass
class TestAction:
    """A single action in a test scenario."""

    input: str
    description: str
    expectations: ActionExpectations = field(default_factory=ActionExpectations)


@dataclass
class TestScenario:
    """A complete test scenario with flowing actions."""

    name: str
    description: str
    actions: list[TestAction]


# =============================================================================
# SCENARIO 1: Exploration and Dialog
# =============================================================================

EXPLORATION_DIALOG = TestScenario(
    name="Exploration and Dialog",
    description="Player explores area, discovers NPC, has conversation",
    actions=[
        TestAction(
            input="I look around",
            description="Initial scene exploration",
            expectations=ActionExpectations(
                min_chars=100,
                max_time=5,
            ),
        ),
        TestAction(
            input="I go to the person and say hello",
            description="Approach and greet NPC",
            expectations=ActionExpectations(
                min_chars=50,
                max_time=5,
                expected_tools=["get_npc_attitude"],
            ),
        ),
        TestAction(
            input="What's your name?",
            description="Continue conversation - ask name",
            expectations=ActionExpectations(
                min_chars=30,
                max_time=3,
                forbidden_tools=["create_entity"],
            ),
        ),
        TestAction(
            input="Tell me about this place",
            description="Ask for information about location",
            expectations=ActionExpectations(
                min_chars=50,
                max_time=5,
                expected_tools=["record_fact"],
            ),
        ),
        TestAction(
            input="Thanks for your help, goodbye",
            description="End conversation politely",
            expectations=ActionExpectations(
                min_chars=30,
                max_time=2,
            ),
        ),
    ],
)


# =============================================================================
# SCENARIO 2: Item Discovery and Interaction
# =============================================================================

ITEM_INTERACTION = TestScenario(
    name="Item Discovery and Interaction",
    description="Player searches for items, takes and uses them",
    actions=[
        TestAction(
            input="I search the room carefully",
            description="Search for hidden items",
            expectations=ActionExpectations(
                min_chars=50,
                max_time=10,
                expected_tools=["skill_check"],
            ),
        ),
        TestAction(
            input="I take the most interesting item I find",
            description="Pick up discovered item",
            expectations=ActionExpectations(
                min_chars=30,
                max_time=2,
                expected_db_changes=["item.holder_id=player"],
            ),
        ),
        TestAction(
            input="I examine what I just picked up",
            description="Inspect the item",
            expectations=ActionExpectations(
                min_chars=50,
                max_time=3,
            ),
        ),
        TestAction(
            input="I put it down here",
            description="Drop the item",
            expectations=ActionExpectations(
                min_chars=30,
                max_time=2,
                expected_db_changes=["item.holder_id=null"],
            ),
        ),
    ],
)


# =============================================================================
# SCENARIO 3: Skill Challenges
# =============================================================================

SKILL_CHALLENGES = TestScenario(
    name="Skill Challenges",
    description="Player attempts various skill-based actions",
    actions=[
        TestAction(
            input="I try to sneak quietly across the room",
            description="Stealth check",
            expectations=ActionExpectations(
                min_chars=50,
                expected_tools=["skill_check"],
            ),
        ),
        TestAction(
            input="I listen carefully for any sounds or danger",
            description="Perception check",
            expectations=ActionExpectations(
                min_chars=50,
                expected_tools=["skill_check"],
            ),
        ),
        TestAction(
            input="I try to climb up to get a better view",
            description="Athletics check",
            expectations=ActionExpectations(
                min_chars=50,
                expected_tools=["skill_check"],
            ),
        ),
    ],
)


# =============================================================================
# SCENARIO 4: Needs and Activities
# =============================================================================

NEEDS_ACTIVITIES = TestScenario(
    name="Needs and Activities",
    description="Player addresses physical needs through activities",
    actions=[
        TestAction(
            input="I'm hungry, I eat some food",
            description="Satisfy hunger need",
            expectations=ActionExpectations(
                min_chars=30,
                min_time=5,
                max_time=30,
                expected_db_changes=["character_needs.hunger"],
            ),
        ),
        TestAction(
            input="I drink some water",
            description="Satisfy thirst need",
            expectations=ActionExpectations(
                min_chars=30,
                max_time=5,
                expected_db_changes=["character_needs.thirst"],
            ),
        ),
        TestAction(
            input="I sit down and rest for a bit",
            description="Recover stamina",
            expectations=ActionExpectations(
                min_chars=30,
                min_time=5,
                max_time=30,
                expected_db_changes=["character_needs.stamina"],
            ),
        ),
    ],
)


# =============================================================================
# SCENARIO 5: Movement and Travel
# =============================================================================

MOVEMENT_TRAVEL = TestScenario(
    name="Movement and Travel",
    description="Player moves locally and travels to new locations",
    actions=[
        TestAction(
            input="I go outside",
            description="Local movement - exit building",
            expectations=ActionExpectations(
                min_chars=50,
                max_time=5,
            ),
        ),
        TestAction(
            input="I look around to see what's nearby",
            description="Survey the area",
            expectations=ActionExpectations(
                min_chars=100,
                max_time=5,
            ),
        ),
        TestAction(
            input="I walk to the nearest path or road",
            description="Local movement - approach road",
            expectations=ActionExpectations(
                min_chars=50,
                max_time=5,
            ),
        ),
    ],
)


# =============================================================================
# SCENARIO 6: OOC Commands
# =============================================================================

OOC_COMMANDS = TestScenario(
    name="OOC Commands",
    description="Player uses out-of-character commands for info",
    actions=[
        TestAction(
            input="ooc: what time is it in the game?",
            description="Query game time",
            expectations=ActionExpectations(
                min_chars=10,
                max_time=0,
            ),
        ),
        TestAction(
            input="ooc: what am I carrying?",
            description="Query inventory",
            expectations=ActionExpectations(
                min_chars=10,
                max_time=0,
            ),
        ),
        TestAction(
            input="ooc: how hungry am I?",
            description="Query needs status",
            expectations=ActionExpectations(
                min_chars=10,
                max_time=0,
            ),
        ),
    ],
)


# =============================================================================
# ALL SCENARIOS
# =============================================================================

ALL_SCENARIOS = [
    EXPLORATION_DIALOG,
    ITEM_INTERACTION,
    SKILL_CHALLENGES,
    NEEDS_ACTIVITIES,
    MOVEMENT_TRAVEL,
    OOC_COMMANDS,
]

# Quick test subset for debugging
QUICK_TEST_SCENARIOS = [
    EXPLORATION_DIALOG,
]
