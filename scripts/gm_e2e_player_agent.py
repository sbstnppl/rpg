"""Test Player Agent for Immersive E2E Testing.

Uses local Ollama (qwen3:32b) to generate natural player actions
based on GM responses, simulating real gameplay.
"""

import asyncio
import re
from dataclasses import dataclass
from typing import Any

from src.llm.ollama_provider import OllamaProvider
from src.llm.message_types import Message


@dataclass
class PlayerDecision:
    """Result of the player agent's decision."""

    action: str  # The player action to take
    reasoning: str  # Why this action was chosen (for logging)
    is_done: bool = False  # True if goal appears achieved


class TestPlayerAgent:
    """LLM-powered test player that generates natural gameplay actions.

    Uses Ollama with qwen3:32b to read GM responses and decide
    contextually appropriate next actions, simulating a real player.
    """

    # Default model for player agent (fast, capable)
    DEFAULT_MODEL = "qwen3:32b"
    FALLBACK_MODEL = "gpt-oss:120b"

    # Verb categories for semantic repetition detection
    OBSERVE_VERBS = {"look", "examine", "inspect", "observe", "scan", "study", "scrutinize", "check"}
    DIALOG_VERBS = {"say", "greet", "speak", "talk", "ask", "tell", "reply"}

    # System prompt for the test player
    SYSTEM_PROMPT = """You are a human player in a fantasy RPG. You're playing the game naturally.

CRITICAL RULES:
1. Write ONLY what the player says/does - no meta-commentary
2. Keep actions short (1-2 sentences max)
3. Respond to what the GM just narrated
4. If an NPC spoke, respond to them conversationally
5. If you see something interesting, interact with it DIRECTLY
6. Pursue the given goal naturally through gameplay
7. Don't repeat the same action twice in a row
8. Be specific - use names and items mentioned by the GM
9. If NPCs are present and your goal involves talking, GREET THEM FIRST
10. After your first turn, AVOID purely observational actions - take CONCRETE actions toward your goal
11. If your goal involves eating/drinking, ACTUALLY EAT OR DRINK the food/water you see
12. If your goal involves picking up items, ACTUALLY PICK THEM UP - don't just "reach for" or "search"

BAD examples (don't do these):
- "I decide to look around" (too meta)
- "I reach for the nearest item" (too vague - SAY WHICH ITEM)
- "I search for something useful" (vague - be specific)
- "I check the area" (observational when action is needed)

GOOD examples:
- "I walk over to Marcus and say hello"
- "I pick up the bread and eat it"
- "I grab the water jug and take a drink"
- "I take the sword from the table"
- "What's going on here?" (direct speech to NPC)

Write your action now. Just the action, nothing else."""

    def __init__(
        self,
        model: str | None = None,
        ollama_url: str = "http://localhost:11434",
    ):
        """Initialize the test player agent.

        Args:
            model: Ollama model to use. Defaults to qwen3:32b.
            ollama_url: Ollama server URL.
        """
        self.model = model or self.DEFAULT_MODEL
        self.provider = OllamaProvider(
            base_url=ollama_url,
            default_model=self.model,
        )
        self._action_history: list[str] = []

    def reset(self) -> None:
        """Reset agent state for a new scenario."""
        self._action_history = []

    async def decide_action(
        self,
        goal: str,
        gm_response: str,
        player_state: dict[str, Any] | None = None,
        max_retries: int = 2,
    ) -> PlayerDecision:
        """Decide the next player action based on GM response.

        Args:
            goal: The current scenario goal (e.g., "Find food and eat").
            gm_response: The GM's last narrative response.
            player_state: Optional state info (location, needs, inventory).
            max_retries: Number of retries on bad response.

        Returns:
            PlayerDecision with the action to take.
        """
        # Build the context prompt
        context_parts = [f"YOUR GOAL: {goal}"]

        if player_state:
            if player_state.get("location"):
                context_parts.append(f"Location: {player_state['location']}")
            if player_state.get("needs"):
                needs_str = ", ".join(
                    f"{k}: {v}" for k, v in player_state["needs"].items()
                )
                context_parts.append(f"Your needs: {needs_str}")
            if player_state.get("inventory"):
                inv_str = ", ".join(player_state["inventory"])
                context_parts.append(f"Inventory: {inv_str}")

        # Add action history (last 5)
        if self._action_history:
            recent = self._action_history[-5:]
            history_str = "\n".join(f"- {a}" for a in recent)
            context_parts.append(f"Your recent actions:\n{history_str}")

        context_parts.append(f"GM's narration:\n\"{gm_response}\"")

        # Add goal-specific hints to guide action type
        goal_lower = goal.lower()
        if any(kw in goal_lower for kw in ["greet", "talk", "speak", "ask", "conversation", "exchange"]):
            context_parts.append("HINT: This is a dialog goal - engage with NPCs directly!")
        elif any(kw in goal_lower for kw in ["take", "find", "get", "pick", "item"]):
            context_parts.append("HINT: This is an item goal - search for and interact with objects!")

        context_parts.append("What do you do?")

        user_content = "\n\n".join(context_parts)

        # Call the LLM
        for attempt in range(max_retries + 1):
            try:
                response = await self.provider.complete(
                    messages=[Message.user(user_content)],
                    system_prompt=self.SYSTEM_PROMPT,
                    model=self.model,
                    temperature=0.7,
                    max_tokens=200,
                )

                action = self._clean_action(response.content)

                if not action or len(action) < 3:
                    if attempt < max_retries:
                        continue
                    action = "I look around"  # Fallback

                # Check for repetition
                if self._action_history and self._is_repetitive(action):
                    if attempt < max_retries:
                        user_content += "\n\n(You already did that. Try something different.)"
                        continue
                    # Force variation (goal-aware)
                    action = self._vary_action(action, goal)

                # Store in history
                self._action_history.append(action)

                # Check if goal might be achieved
                is_done = self._check_goal_achieved(goal, gm_response, action)

                return PlayerDecision(
                    action=action,
                    reasoning=f"Based on GM response about: {gm_response[:50]}...",
                    is_done=is_done,
                )

            except Exception as e:
                if attempt < max_retries:
                    continue
                # Return goal-aware fallback on all failures
                fallback = self._vary_action("fallback", goal)
                self._action_history.append(fallback)
                return PlayerDecision(
                    action=fallback,
                    reasoning=f"Fallback due to error: {e}",
                    is_done=False,
                )

        # Should not reach here, but just in case
        return PlayerDecision(
            action="I wait and observe",
            reasoning="Exhausted retries",
            is_done=False,
        )

    def _clean_action(self, raw: str) -> str:
        """Clean the raw LLM output to extract just the action.

        Args:
            raw: Raw LLM response.

        Returns:
            Cleaned action string.
        """
        if not raw:
            return ""

        # Remove thinking tags if present
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
        raw = raw.strip()

        # Remove common prefixes
        prefixes_to_strip = [
            "Player:",
            "Action:",
            "I would",
            "I decide to",
            "As a player,",
            "My action:",
        ]
        for prefix in prefixes_to_strip:
            if raw.lower().startswith(prefix.lower()):
                raw = raw[len(prefix):].strip()

        # Take first sentence if too long
        if len(raw) > 200:
            sentences = re.split(r"[.!?]\s+", raw)
            if sentences:
                raw = sentences[0]
                if not raw.endswith((".", "!", "?")):
                    raw += "."

        # Remove quotes if the whole thing is quoted
        if raw.startswith('"') and raw.endswith('"'):
            raw = raw[1:-1]

        return raw.strip()

    def _is_repetitive(self, action: str) -> bool:
        """Check if the action is too similar to recent actions.

        Checks against last 3 actions with semantic matching for action verbs.

        Args:
            action: The proposed action.

        Returns:
            True if repetitive.
        """
        if not self._action_history:
            return False

        action_lower = action.lower().strip()
        action_words_list = action_lower.split()

        # Get the actual verb (skip "I" if present)
        if action_words_list and action_words_list[0] == "i":
            action_verb = action_words_list[1] if len(action_words_list) > 1 else ""
        else:
            action_verb = action_words_list[0] if action_words_list else ""

        # Check against last 3 actions (not just last 1)
        for prev in self._action_history[-3:]:
            prev_lower = prev.lower().strip()

            # Exact match
            if action_lower == prev_lower:
                return True

            # Semantic similarity: both are observational actions
            prev_words_list = prev_lower.split()
            # Get the actual verb (skip "I" if present)
            if prev_words_list and prev_words_list[0] == "i":
                prev_verb = prev_words_list[1] if len(prev_words_list) > 1 else ""
            else:
                prev_verb = prev_words_list[0] if prev_words_list else ""

            if action_verb in self.OBSERVE_VERBS and prev_verb in self.OBSERVE_VERBS:
                return True  # Both are observational → repetitive

        # Word overlap check (lowered from 0.8 to 0.6)
        action_words = set(action_lower.split())
        for prev in self._action_history[-3:]:
            prev_words = set(prev.lower().split())
            if len(action_words) > 2 and len(prev_words) > 2:
                overlap = len(action_words & prev_words)
                min_len = min(len(action_words), len(prev_words))
                if min_len > 0 and overlap / min_len > 0.6:
                    return True

        return False

    def _vary_action(self, action: str, goal: str = "") -> str:
        """Create a goal-appropriate variation of a repetitive action.

        Args:
            action: The repetitive action.
            goal: The current scenario goal (used to pick appropriate variations).

        Returns:
            A varied version appropriate for the goal type.
        """
        goal_lower = goal.lower()

        # Dialog goals → dialog actions
        if any(kw in goal_lower for kw in ["greet", "talk", "speak", "ask", "conversation", "exchange"]):
            variations = [
                "I say hello to the person nearby",
                "I greet them with a friendly nod",
                "I clear my throat and introduce myself",
                "'Hello there!' I call out",
            ]
        # Hunger/eat goals → explicit eating actions
        elif any(kw in goal_lower for kw in ["eat", "hunger", "food"]):
            variations = [
                "I pick up the bread and take a bite",
                "I grab the bread from the table and eat it",
                "I take the bread and eat some",
                "I eat the bread I see on the table",
            ]
        # Thirst/drink goals → explicit drinking actions
        elif any(kw in goal_lower for kw in ["drink", "thirst", "water"]):
            variations = [
                "I pick up the water jug and take a drink",
                "I grab the jug and drink some water",
                "I drink from the water jug on the table",
                "I take the jug and drink from it",
            ]
        # Item pickup goals → explicit take actions
        elif any(kw in goal_lower for kw in ["pick up", "take", "grab"]):
            variations = [
                "I pick up the bread from the table",
                "I grab the water jug",
                "I take the item I see nearby",
                "I pick up what's on the table",
            ]
        # Generic item/find goals → search then take
        elif any(kw in goal_lower for kw in ["find", "get", "item"]):
            variations = [
                "I pick up the nearest useful item",
                "I take the bread from the table",
                "I grab the water jug from the table",
                "I pick up what I found",
            ]
        # Default observational (existing)
        else:
            variations = [
                "I examine my surroundings more carefully",
                "I check if there's anything I missed",
                "I wait and listen for a moment",
                "I look for another way forward",
            ]

        # Pick based on action history length to add variety
        idx = len(self._action_history) % len(variations)
        return variations[idx]

    def _check_goal_achieved(
        self, goal: str, gm_response: str, action: str
    ) -> bool:
        """Heuristic check if the goal might be achieved.

        Args:
            goal: The scenario goal.
            gm_response: The GM's last response.
            action: The action taken.

        Returns:
            True if goal appears achieved.
        """
        goal_lower = goal.lower()
        response_lower = gm_response.lower()

        # Simple keyword matching for common goals
        goal_indicators = {
            "eat": ["eat", "ate", "eating", "food", "meal", "satisfied your hunger"],
            "drink": ["drink", "drank", "drinking", "water", "quench"],
            "sleep": ["sleep", "slept", "rest", "nap", "wake", "refreshed"],
            "talk": ["says", "replies", "responds", "tells you", "conversation"],
            "take": ["pick up", "take", "grabbed", "now holding", "in your inventory"],
            "find": ["find", "discover", "notice", "see", "spot"],
        }

        for keyword, indicators in goal_indicators.items():
            if keyword in goal_lower:
                for ind in indicators:
                    if ind in response_lower:
                        return True

        return False


async def _test_player_agent():
    """Quick test of the player agent."""
    agent = TestPlayerAgent()

    # Test scenario
    gm_response = """You find yourself in a cozy farmhouse. A fire crackles in the hearth,
    casting dancing shadows on the wooden walls. A sturdy farmer named Marcus
    stands near the fireplace, warming his hands. On the table nearby, you see
    a fresh loaf of bread and a jug of water."""

    decision = await agent.decide_action(
        goal="Greet the farmer and learn about the area",
        gm_response=gm_response,
        player_state={
            "location": "test_farmhouse",
            "needs": {"hunger": 30, "thirst": 40},
        },
    )

    print(f"Action: {decision.action}")
    print(f"Reasoning: {decision.reasoning}")
    print(f"Is done: {decision.is_done}")


if __name__ == "__main__":
    asyncio.run(_test_player_agent())
