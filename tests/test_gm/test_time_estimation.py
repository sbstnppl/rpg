"""Tests for GM time estimation functionality.

The time estimation system uses a hybrid approach:
1. Activity keywords from player input (eating, resting, etc.)
2. Tool call results (satisfy_need, skill_check, etc.)
Takes the maximum of all estimates for realistic game time.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.gm.gm_node import (
    GMNode,
    ACTIVITY_PATTERNS,
    TIME_MODIFIERS,
)
from src.gm.schemas import StateChange, StateChangeType


class TestActivityPatterns:
    """Tests for ACTIVITY_PATTERNS constant."""

    def test_all_patterns_have_valid_structure(self):
        """Each pattern should have (frozenset, int) structure."""
        for category, (keywords, minutes) in ACTIVITY_PATTERNS.items():
            assert isinstance(keywords, frozenset), f"{category} keywords not frozenset"
            assert isinstance(minutes, int), f"{category} minutes not int"
            assert minutes > 0, f"{category} minutes should be positive"

    def test_eating_has_realistic_time(self):
        """Eating a meal should take 25 minutes base."""
        _, minutes = ACTIVITY_PATTERNS["eating"]
        assert minutes == 25, "Full meal should be 25 minutes"

    def test_snacking_faster_than_eating(self):
        """Snacking should be faster than eating."""
        _, snack_time = ACTIVITY_PATTERNS["snacking"]
        _, eat_time = ACTIVITY_PATTERNS["eating"]
        assert snack_time < eat_time, "Snacking should be faster than eating"


class TestTimeModifiers:
    """Tests for TIME_MODIFIERS constant."""

    def test_quick_modifiers_reduce_time(self):
        """Quick/fast modifiers should reduce time (< 1.0)."""
        assert TIME_MODIFIERS["quickly"] < 1.0
        assert TIME_MODIFIERS["fast"] < 1.0
        assert TIME_MODIFIERS["briefly"] < 1.0

    def test_thorough_modifiers_increase_time(self):
        """Thorough/careful modifiers should increase time (> 1.0)."""
        assert TIME_MODIFIERS["thoroughly"] > 1.0
        assert TIME_MODIFIERS["carefully"] > 1.0
        assert TIME_MODIFIERS["leisurely"] > 1.0


class TestEstimateActivityTime:
    """Tests for _estimate_activity_time method."""

    @pytest.fixture
    def mock_gm_node(self):
        """Create a minimal GMNode for testing time estimation."""
        with patch.object(GMNode, "__init__", lambda x: None):
            node = GMNode()
            node.tool_results = []
            return node

    # === EATING TESTS ===

    def test_eat_meal_returns_25_minutes(self, mock_gm_node):
        """'Eat a meal' should return 25 minutes base."""
        time = mock_gm_node._estimate_activity_time("eat a meal")
        assert time == 25

    def test_eating_verb_form(self, mock_gm_node):
        """'Eating' should stem to 'eat' and match."""
        time = mock_gm_node._estimate_activity_time("I am eating dinner")
        assert time == 25

    def test_eat_hearty_meal_returns_32_minutes(self, mock_gm_node):
        """'Hearty' modifier should increase time by 1.3x."""
        time = mock_gm_node._estimate_activity_time("eat a hearty meal")
        assert time == 32  # 25 * 1.3 = 32.5 -> 32

    def test_quick_meal_returns_17_minutes(self, mock_gm_node):
        """'Quick' modifier should reduce time by 0.7x."""
        time = mock_gm_node._estimate_activity_time("eat a quick meal")
        assert time == 17  # 25 * 0.7 = 17.5 -> 17

    def test_breakfast_matches_eating(self, mock_gm_node):
        """Breakfast should match eating pattern."""
        time = mock_gm_node._estimate_activity_time("have breakfast")
        assert time == 25

    # === SNACKING TESTS ===

    def test_snack_returns_7_minutes(self, mock_gm_node):
        """Snacking should be quick."""
        time = mock_gm_node._estimate_activity_time("grab a snack")
        assert time == 7

    # === DRINKING TESTS ===

    def test_drink_ale_returns_5_minutes(self, mock_gm_node):
        """Drinking should take a few minutes."""
        time = mock_gm_node._estimate_activity_time("drink some ale")
        assert time == 5

    def test_quick_drink_returns_3_minutes(self, mock_gm_node):
        """Quick drink should be faster."""
        time = mock_gm_node._estimate_activity_time("take a quick drink")
        assert time == 3  # 5 * 0.7 = 3.5 -> 3

    # === RESTING TESTS ===

    def test_rest_by_fire_returns_15_minutes(self, mock_gm_node):
        """Resting should take ~15 minutes."""
        time = mock_gm_node._estimate_activity_time("rest by the fire")
        assert time == 15

    def test_long_rest_returns_22_minutes(self, mock_gm_node):
        """Long rest should take more time."""
        time = mock_gm_node._estimate_activity_time("take a long rest")
        assert time == 22  # 15 * 1.5 = 22.5 -> 22

    # === SLEEPING TESTS ===

    def test_nap_returns_30_minutes(self, mock_gm_node):
        """Napping has a minimum duration."""
        time = mock_gm_node._estimate_activity_time("take a nap")
        assert time == 30

    # === EXPLORATION TESTS ===

    def test_explore_village_returns_10_minutes(self, mock_gm_node):
        """Exploration should take some time."""
        time = mock_gm_node._estimate_activity_time("explore the village")
        assert time == 10

    def test_search_thoroughly_returns_14_minutes(self, mock_gm_node):
        """Thorough search takes longer."""
        time = mock_gm_node._estimate_activity_time("search thoroughly")
        assert time == 14  # 10 * 1.4 = 14

    # === MOVEMENT TESTS ===

    def test_leave_tavern_returns_5_minutes(self, mock_gm_node):
        """Simple movement should be quick."""
        time = mock_gm_node._estimate_activity_time("leave the tavern")
        assert time == 5

    def test_walk_to_market(self, mock_gm_node):
        """Walking somewhere takes a few minutes."""
        time = mock_gm_node._estimate_activity_time("walk to the market")
        assert time == 5

    # === OBSERVATION TESTS ===

    def test_look_around_returns_3_minutes(self, mock_gm_node):
        """Looking around is quick."""
        time = mock_gm_node._estimate_activity_time("look around")
        assert time == 3

    def test_examine_carefully_returns_4_minutes(self, mock_gm_node):
        """Careful examination takes a bit longer."""
        time = mock_gm_node._estimate_activity_time("examine the door carefully")
        assert time == 3  # 3 * 1.3 = 3.9 -> 3

    # === CONVERSATION TESTS ===

    def test_talk_to_npc_returns_8_minutes(self, mock_gm_node):
        """Talking should take several minutes."""
        time = mock_gm_node._estimate_activity_time("talk to the bartender")
        assert time == 8

    def test_greet_returns_8_minutes(self, mock_gm_node):
        """Greeting is a social interaction."""
        time = mock_gm_node._estimate_activity_time("greet the merchant")
        assert time == 8

    # === TRADING TESTS ===

    def test_buy_item_returns_10_minutes(self, mock_gm_node):
        """Shopping takes time."""
        time = mock_gm_node._estimate_activity_time("buy a sword")
        assert time == 10

    # === READING TESTS ===

    def test_read_scroll_returns_12_minutes(self, mock_gm_node):
        """Reading takes focus time."""
        time = mock_gm_node._estimate_activity_time("read the scroll")
        assert time == 12

    # === CRAFTING TESTS ===

    def test_repair_armor_returns_25_minutes(self, mock_gm_node):
        """Crafting/repair takes significant time."""
        time = mock_gm_node._estimate_activity_time("repair my armor")
        assert time == 25

    # === NO MATCH TESTS ===

    def test_unrecognized_returns_zero(self, mock_gm_node):
        """Unrecognized input returns 0 (defer to default)."""
        time = mock_gm_node._estimate_activity_time("xyzzy")
        assert time == 0

    def test_random_nonsense_returns_zero(self, mock_gm_node):
        """Random input returns 0."""
        time = mock_gm_node._estimate_activity_time("abc def ghi")
        assert time == 0


class TestEstimateToolTime:
    """Tests for _estimate_tool_time method."""

    @pytest.fixture
    def mock_gm_node(self):
        """Create a minimal GMNode for testing time estimation."""
        with patch.object(GMNode, "__init__", lambda x: None):
            node = GMNode()
            node.tool_results = []
            return node

    def test_no_tools_returns_zero(self, mock_gm_node):
        """No tool calls should return 0."""
        mock_gm_node.tool_results = []
        time = mock_gm_node._estimate_tool_time()
        assert time == 0

    def test_satisfy_need_hunger_returns_20(self, mock_gm_node):
        """Satisfying hunger via tool returns 20 minutes."""
        mock_gm_node.tool_results = [
            {
                "tool": "satisfy_need",
                "arguments": {"need": "hunger"},
                "result": {"success": True},
            }
        ]
        time = mock_gm_node._estimate_tool_time()
        assert time == 20

    def test_satisfy_need_thirst_returns_5(self, mock_gm_node):
        """Satisfying thirst via tool returns 5 minutes."""
        mock_gm_node.tool_results = [
            {
                "tool": "satisfy_need",
                "arguments": {"need": "thirst"},
                "result": {"success": True},
            }
        ]
        time = mock_gm_node._estimate_tool_time()
        assert time == 5

    def test_satisfy_need_sleep_pressure_returns_30(self, mock_gm_node):
        """Satisfying sleep pressure via tool returns 30 minutes."""
        mock_gm_node.tool_results = [
            {
                "tool": "satisfy_need",
                "arguments": {"need": "sleep_pressure"},
                "result": {"success": True},
            }
        ]
        time = mock_gm_node._estimate_tool_time()
        assert time == 30

    def test_skill_check_returns_3(self, mock_gm_node):
        """Skill check returns 3 minutes."""
        mock_gm_node.tool_results = [
            {
                "tool": "skill_check",
                "arguments": {"skill": "perception"},
                "result": {"success": True},
            }
        ]
        time = mock_gm_node._estimate_tool_time()
        assert time == 3

    def test_multiple_tools_returns_max(self, mock_gm_node):
        """Multiple tools should return maximum time."""
        mock_gm_node.tool_results = [
            {
                "tool": "skill_check",
                "arguments": {"skill": "perception"},
                "result": {"success": True},
            },
            {
                "tool": "satisfy_need",
                "arguments": {"need": "hunger"},
                "result": {"success": True},
            },
        ]
        time = mock_gm_node._estimate_tool_time()
        assert time == 20  # max(3, 20)


class TestHybridTimeEstimation:
    """Tests for the hybrid _estimate_time_passed combining activity + tools."""

    @pytest.fixture
    def mock_gm_node(self):
        """Create a minimal GMNode for testing time estimation."""
        with patch.object(GMNode, "__init__", lambda x: None):
            node = GMNode()
            node.tool_results = []
            return node

    def test_activity_time_when_no_tools(self, mock_gm_node):
        """Activity time used when no tools called."""
        mock_gm_node.tool_results = []
        time = mock_gm_node._estimate_time_passed("eat a hearty meal", [])
        assert time == 32  # Activity-based (25 * 1.3)

    def test_tool_time_when_no_activity(self, mock_gm_node):
        """Tool time used when no activity keywords match."""
        mock_gm_node.tool_results = [
            {
                "tool": "satisfy_need",
                "arguments": {"need": "hunger"},
                "result": {"success": True},
            }
        ]
        time = mock_gm_node._estimate_time_passed("xyzzy", [])
        assert time == 20  # Tool-based

    def test_hybrid_takes_max_of_activity_and_tool(self, mock_gm_node):
        """Hybrid should take maximum of activity and tool times."""
        mock_gm_node.tool_results = [
            {
                "tool": "satisfy_need",
                "arguments": {"need": "hunger"},
                "result": {"success": True},
            }
        ]
        # Activity: 25, Tool: 20, Max: 25
        time = mock_gm_node._estimate_time_passed("eat a meal", [])
        assert time == 25

    def test_hearty_meal_beats_tool(self, mock_gm_node):
        """Hearty meal modifier should win over tool time."""
        mock_gm_node.tool_results = [
            {
                "tool": "satisfy_need",
                "arguments": {"need": "hunger"},
                "result": {"success": True},
            }
        ]
        # Activity: 32 (25*1.3), Tool: 20, Max: 32
        time = mock_gm_node._estimate_time_passed("eat a hearty meal", [])
        assert time == 32

    def test_combat_always_returns_1_minute(self, mock_gm_node):
        """Combat always returns 1 minute per round."""
        mock_gm_node.tool_results = []
        damage_change = StateChange(
            change_type=StateChangeType.DAMAGE,
            target="enemy",
            details={"amount": 10},
        )
        time = mock_gm_node._estimate_time_passed("attack the goblin", [damage_change])
        assert time == 1

    def test_no_activity_no_tools_returns_default(self, mock_gm_node):
        """When nothing matches, return 1 minute default."""
        mock_gm_node.tool_results = []
        time = mock_gm_node._estimate_time_passed("xyzzy", [])
        assert time == 1

    def test_uses_correct_tool_keys(self, mock_gm_node):
        """Tool results should use 'tool' and 'arguments' keys (not 'name'/'input')."""
        # This tests the bug fix - old keys would fail silently
        mock_gm_node.tool_results = [
            {
                "tool": "satisfy_need",
                "arguments": {"need": "thirst"},
                "result": {"success": True},
            }
        ]
        time = mock_gm_node._estimate_time_passed("drink water", [])
        # Activity: 5, Tool: 5, Max: 5
        assert time == 5


class TestRealWorldScenarios:
    """Integration tests with realistic player inputs."""

    @pytest.fixture
    def mock_gm_node(self):
        """Create a minimal GMNode for testing time estimation."""
        with patch.object(GMNode, "__init__", lambda x: None):
            node = GMNode()
            node.tool_results = []
            return node

    def test_scenario_eat_hearty_meal_at_tavern(self, mock_gm_node):
        """Eating a hearty meal at a tavern should take 30+ minutes."""
        # This was the original bug: returned 1 minute
        time = mock_gm_node._estimate_time_passed("eat a hearty meal at the tavern", [])
        assert time >= 30, f"Expected 30+ min, got {time}"

    def test_scenario_rest_by_fire(self, mock_gm_node):
        """Resting by the fire should take 10+ minutes."""
        time = mock_gm_node._estimate_time_passed("rest by the fire", [])
        assert time >= 10, f"Expected 10+ min, got {time}"

    def test_scenario_explore_village(self, mock_gm_node):
        """Exploring the village should take 8+ minutes."""
        time = mock_gm_node._estimate_time_passed("leave the tavern and explore the village", [])
        # "explore" is in exploration pattern (10 min)
        # "leave" is in movement pattern (5 min) but exploration matches first
        assert time >= 5, f"Expected 5+ min, got {time}"

    def test_scenario_quick_look_around(self, mock_gm_node):
        """Quick look around should be fast."""
        time = mock_gm_node._estimate_time_passed("take a quick look around", [])
        # "look" = observation (3 min), "quick" = 0.7 modifier
        assert time == 2  # 3 * 0.7 = 2.1 -> 2

    def test_scenario_leisurely_meal(self, mock_gm_node):
        """A leisurely meal should take 35+ minutes."""
        time = mock_gm_node._estimate_time_passed("enjoy a leisurely meal", [])
        # "meal" = eating (25 min), "leisurely" = 1.5 modifier
        assert time == 37  # 25 * 1.5 = 37.5 -> 37
