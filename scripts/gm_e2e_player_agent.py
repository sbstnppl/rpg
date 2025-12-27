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

    # System prompt for the test player
    SYSTEM_PROMPT = """You are a human player in a fantasy RPG. You're playing the game naturally.

CRITICAL RULES:
1. Write ONLY what the player says/does - no meta-commentary
2. Keep actions short (1-2 sentences max)
3. Respond to what the GM just narrated
4. If an NPC spoke, respond to them conversationally
5. If you see something interesting, interact with it
6. Pursue the given goal naturally through gameplay
7. Don't repeat the same action twice in a row
8. Be specific - use names and items mentioned by the GM

BAD examples (don't do these):
- "I decide to look around" (too meta)
- "As a player, I want to..." (meta-commentary)
- "I look around" then "I look around" (repetition)

GOOD examples:
- "I walk over to Marcus and say hello"
- "I pick up the bread and take a bite"
- "What's going on here?" (direct speech to NPC)
- "I try the door handle"

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
                    # Force variation
                    action = self._vary_action(action)

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
                # Return safe fallback on all failures
                fallback = "I look around carefully"
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

        Args:
            action: The proposed action.

        Returns:
            True if repetitive.
        """
        if not self._action_history:
            return False

        action_lower = action.lower().strip()
        last_action = self._action_history[-1].lower().strip()

        # Exact match
        if action_lower == last_action:
            return True

        # Check similarity (simple word overlap)
        action_words = set(action_lower.split())
        last_words = set(last_action.split())

        if len(action_words) > 2 and len(last_words) > 2:
            overlap = len(action_words & last_words)
            min_len = min(len(action_words), len(last_words))
            if min_len > 0 and overlap / min_len > 0.8:
                return True

        return False

    def _vary_action(self, action: str) -> str:
        """Create a variation of a repetitive action.

        Args:
            action: The repetitive action.

        Returns:
            A varied version.
        """
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
