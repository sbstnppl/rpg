"""Constrained narrator for generating prose from mechanical results.

The narrator MUST include all mechanical facts in its narrative
and CANNOT add events that aren't in the facts.
"""

from dataclasses import dataclass
from typing import Any, Protocol


class LLMProviderProtocol(Protocol):
    """Protocol for LLM providers."""

    async def complete(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> Any:
        """Complete a prompt."""
        ...


NARRATOR_TEMPLATE = """You are narrating a turn in a fantasy RPG.

MECHANICAL FACTS (you MUST include ALL of these):
{facts}

SCENE CONTEXT:
{scene_context}

PLAYER'S MANNER: {ambient_flavor}

Write 2-4 sentences narrating this turn.

RULES:
- Include every mechanical fact naturally in the prose
- Match the player's manner/tone if provided
- Add atmospheric detail and sensory description
- Do NOT add events that aren't in the facts
- Do NOT contradict any mechanical outcome
- Write in second person ("You grab the sword...")
"""


@dataclass
class NarratorResult:
    """Result of narration."""

    narrative: str
    facts_included: list[str]
    warnings: list[str]


class ConstrainedNarrator:
    """Generates narrative prose constrained by mechanical facts."""

    def __init__(
        self,
        llm_provider: LLMProviderProtocol | None = None,
        temperature: float = 0.8,
        max_tokens: int = 500,
    ) -> None:
        """Initialize the narrator.

        Args:
            llm_provider: LLM provider for generation. If None, uses fallback.
            temperature: Generation temperature (higher = more creative).
            max_tokens: Maximum tokens in response.
        """
        self.llm_provider = llm_provider
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def narrate(
        self,
        turn_result: dict[str, Any],
        scene_context: str = "",
        ambient_flavor: str | None = None,
    ) -> NarratorResult:
        """Generate narrative from turn result.

        Args:
            turn_result: Dict with executions, failed_actions, etc.
            scene_context: Description of current scene.
            ambient_flavor: How the player is acting (e.g., "nervously").

        Returns:
            NarratorResult with generated narrative.
        """
        facts = self._extract_facts(turn_result)

        # If no LLM, use simple fallback
        if self.llm_provider is None:
            narrative = self._fallback_narrate(facts, ambient_flavor)
            return NarratorResult(
                narrative=narrative,
                facts_included=facts,
                warnings=[],
            )

        # Build prompt
        prompt = NARRATOR_TEMPLATE.format(
            facts="\n".join(f"- {fact}" for fact in facts),
            scene_context=scene_context or "A generic fantasy setting.",
            ambient_flavor=ambient_flavor or "neutral tone",
        )

        # Generate with LLM
        response = await self.llm_provider.complete(
            prompt=prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        narrative = response.content if hasattr(response, "content") else str(response)

        # Validate narrative includes required facts
        warnings = self._validate_narrative(narrative, facts)

        return NarratorResult(
            narrative=narrative,
            facts_included=facts,
            warnings=warnings,
        )

    def _extract_facts(self, turn_result: dict[str, Any]) -> list[str]:
        """Extract required facts from turn result.

        Args:
            turn_result: The turn result dict.

        Returns:
            List of fact strings that must be included.
        """
        facts = []

        # Extract from executions
        for execution in turn_result.get("executions", []):
            outcome = execution.get("outcome", "")
            if outcome:
                facts.append(outcome)

            # Add state changes as facts
            for change in execution.get("state_changes", []):
                if change and not change.startswith("Time"):
                    facts.append(change)

        # Extract from failed actions
        for failed in turn_result.get("failed_actions", []):
            action = failed.get("action", {})
            reason = failed.get("reason", "")
            action_type = action.get("type", "action")
            target = action.get("target", "")

            if reason:
                facts.append(f"FAILED {action_type} {target}: {reason}")

        # Extract complication if present
        complication = turn_result.get("complication")
        if complication:
            comp_type = complication.get("type", "event")
            comp_desc = complication.get("description", "")
            if comp_desc:
                facts.append(f"COMPLICATION ({comp_type}): {comp_desc}")

        return facts

    def _fallback_narrate(
        self,
        facts: list[str],
        ambient_flavor: str | None = None,
    ) -> str:
        """Generate simple narrative without LLM.

        Args:
            facts: List of mechanical facts.
            ambient_flavor: Player's manner.

        Returns:
            Simple narrative string.
        """
        if not facts:
            return "Nothing happens."

        # Simple narrative: just join facts with connecting words
        parts = []
        for i, fact in enumerate(facts):
            if i == 0:
                parts.append(fact.capitalize())
            elif fact.startswith("FAILED"):
                # Format failed actions
                parts.append(f"However, {fact.lower()}")
            elif fact.startswith("COMPLICATION"):
                parts.append(f"Then, unexpectedly, {fact.lower()}")
            else:
                parts.append(fact)

        narrative = ". ".join(parts)
        if not narrative.endswith("."):
            narrative += "."

        return narrative

    def _validate_narrative(
        self,
        narrative: str,
        facts: list[str],
    ) -> list[str]:
        """Validate that narrative includes all required facts.

        Args:
            narrative: Generated narrative.
            facts: List of facts that should be included.

        Returns:
            List of warning messages for missing facts.
        """
        warnings = []
        narrative_lower = narrative.lower()

        for fact in facts:
            # Check if key terms from fact appear in narrative
            # This is a simple check - could be more sophisticated
            key_words = self._extract_key_words(fact)
            if not any(word in narrative_lower for word in key_words):
                warnings.append(f"Fact may be missing: {fact}")

        return warnings

    def _extract_key_words(self, fact: str) -> list[str]:
        """Extract key words from a fact for validation.

        Args:
            fact: The fact string.

        Returns:
            List of key words to look for.
        """
        # Remove common words and extract nouns/verbs
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "has", "have",
            "for", "to", "of", "in", "on", "at", "by", "with", "from",
        }

        words = fact.lower().split()
        key_words = [w for w in words if w not in stopwords and len(w) > 2]

        return key_words[:3]  # Return top 3 key words
