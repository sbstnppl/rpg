"""Token budget management for context compilation.

Manages context size to fit within LLM token limits while
prioritizing critical information.
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable


class ContextPriority(IntEnum):
    """Priority levels for context sections.

    Higher numbers = higher priority (included first).
    """

    CRITICAL = 100  # Must include (turn context, player input)
    HIGH = 80  # Important (location, player character, NPCs)
    MEDIUM = 60  # Useful (tasks, recent events, navigation)
    LOW = 40  # Nice to have (secrets, detailed history)
    OPTIONAL = 20  # Can drop (extra details)


@dataclass
class ContextSection:
    """A section of context with metadata."""

    name: str
    content: str
    priority: ContextPriority
    token_count: int = 0
    is_included: bool = True

    def __post_init__(self) -> None:
        """Calculate token count if not provided."""
        if self.token_count == 0 and self.content:
            self.token_count = estimate_tokens(self.content)


@dataclass
class BudgetResult:
    """Result of budget compilation."""

    content: str
    total_tokens: int
    sections_included: list[str]
    sections_excluded: list[str]
    utilization: float  # 0.0 to 1.0


# Default section priorities
DEFAULT_PRIORITIES: dict[str, ContextPriority] = {
    "turn_context": ContextPriority.CRITICAL,
    "player_input": ContextPriority.CRITICAL,
    "constraint_context": ContextPriority.CRITICAL,
    "time_context": ContextPriority.HIGH,
    "location_context": ContextPriority.HIGH,
    "player_context": ContextPriority.HIGH,
    "npcs_context": ContextPriority.HIGH,
    "navigation_context": ContextPriority.MEDIUM,
    "tasks_context": ContextPriority.MEDIUM,
    "entity_registry_context": ContextPriority.MEDIUM,
    "recent_events_context": ContextPriority.LOW,
    "secrets_context": ContextPriority.LOW,
}


def estimate_tokens(text: str) -> int:
    """Estimate token count from text.

    Uses a simple heuristic: ~4 characters per token on average.
    This is a rough estimate for English text; actual counts vary by model.

    Args:
        text: Text to estimate tokens for.

    Returns:
        Estimated token count.
    """
    if not text:
        return 0
    # Average of ~4 chars per token for English text
    # This is conservative; Claude tends to be ~3.5-4 chars/token
    return len(text) // 4 + 1


class ContextBudget:
    """Manages token budget for context compilation.

    Ensures context fits within LLM token limits by:
    - Tracking token counts per section
    - Including sections in priority order
    - Trimming lower-priority content when over budget
    """

    def __init__(
        self,
        max_tokens: int = 8000,
        priorities: dict[str, ContextPriority] | None = None,
    ) -> None:
        """Initialize budget manager.

        Args:
            max_tokens: Maximum tokens allowed for context.
            priorities: Optional custom priority mapping.
        """
        self.max_tokens = max_tokens
        self.priorities = priorities or DEFAULT_PRIORITIES
        self._sections: list[ContextSection] = []

    def add_section(
        self,
        name: str,
        content: str,
        priority: ContextPriority | None = None,
    ) -> None:
        """Add a section to the budget.

        Args:
            name: Section name.
            content: Section content.
            priority: Optional override priority.
        """
        if not content:
            return

        section_priority = priority or self.priorities.get(name, ContextPriority.MEDIUM)
        section = ContextSection(
            name=name,
            content=content,
            priority=section_priority,
        )
        self._sections.append(section)

    def compile(
        self,
        separator: str = "\n\n",
        truncate_sections: bool = True,
    ) -> BudgetResult:
        """Compile sections within budget.

        Args:
            separator: String to join sections with.
            truncate_sections: If True, truncate large sections; if False, exclude entirely.

        Returns:
            BudgetResult with compiled content and metadata.
        """
        if not self._sections:
            return BudgetResult(
                content="",
                total_tokens=0,
                sections_included=[],
                sections_excluded=[],
                utilization=0.0,
            )

        # Sort by priority (highest first)
        sorted_sections = sorted(
            self._sections,
            key=lambda s: s.priority,
            reverse=True,
        )

        included: list[ContextSection] = []
        excluded: list[str] = []
        total_tokens = 0
        separator_tokens = estimate_tokens(separator)

        for section in sorted_sections:
            section_tokens = section.token_count

            # Account for separator tokens
            if included:
                section_tokens += separator_tokens

            # Check if section fits
            if total_tokens + section_tokens <= self.max_tokens:
                included.append(section)
                total_tokens += section_tokens
            elif truncate_sections and section.priority >= ContextPriority.HIGH:
                # Try to fit a truncated version of high-priority sections
                available_tokens = self.max_tokens - total_tokens - separator_tokens
                if available_tokens > 100:  # Only truncate if meaningful space
                    truncated_content = self._truncate_to_tokens(
                        section.content, available_tokens
                    )
                    truncated_section = ContextSection(
                        name=section.name,
                        content=truncated_content,
                        priority=section.priority,
                    )
                    included.append(truncated_section)
                    total_tokens += truncated_section.token_count + separator_tokens
                else:
                    excluded.append(section.name)
            else:
                excluded.append(section.name)

        # Build final content (preserve original order)
        original_order = {s.name: i for i, s in enumerate(self._sections)}
        included_sorted = sorted(included, key=lambda s: original_order.get(s.name, 0))

        content = separator.join(s.content for s in included_sorted if s.content)

        return BudgetResult(
            content=content,
            total_tokens=total_tokens,
            sections_included=[s.name for s in included],
            sections_excluded=excluded,
            utilization=total_tokens / self.max_tokens if self.max_tokens > 0 else 0.0,
        )

    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit within token limit.

        Args:
            text: Text to truncate.
            max_tokens: Maximum tokens.

        Returns:
            Truncated text with ellipsis.
        """
        if estimate_tokens(text) <= max_tokens:
            return text

        # Estimate character limit (4 chars per token)
        char_limit = max_tokens * 4 - 3  # Leave room for "..."

        if char_limit <= 0:
            return ""

        # Try to truncate at a natural break point
        truncated = text[:char_limit]

        # Find last sentence or paragraph break
        for break_char in ["\n\n", "\n", ". ", "! ", "? "]:
            last_break = truncated.rfind(break_char)
            if last_break > char_limit // 2:
                return truncated[:last_break + len(break_char)].rstrip() + "..."

        return truncated.rstrip() + "..."

    def get_utilization(self) -> float:
        """Get current budget utilization.

        Returns:
            Utilization as fraction of max_tokens used.
        """
        total = sum(s.token_count for s in self._sections)
        return total / self.max_tokens if self.max_tokens > 0 else 0.0

    def get_section_breakdown(self) -> dict[str, int]:
        """Get token count per section.

        Returns:
            Dict mapping section name to token count.
        """
        return {s.name: s.token_count for s in self._sections}

    def clear(self) -> None:
        """Clear all sections."""
        self._sections.clear()

    @staticmethod
    def for_model(model_name: str) -> "ContextBudget":
        """Create a budget configured for a specific model.

        Args:
            model_name: Model identifier (e.g., "claude-3-opus", "gpt-4").

        Returns:
            ContextBudget with appropriate max_tokens.
        """
        # Model context limits (conservative estimates for context, leaving room for response)
        model_limits = {
            "claude-3-opus": 150000,
            "claude-3-sonnet": 150000,
            "claude-opus-4": 150000,
            "claude-sonnet-4": 150000,
            "gpt-4": 6000,
            "gpt-4-turbo": 100000,
            "gpt-4o": 100000,
        }

        # Find matching model
        for model_key, limit in model_limits.items():
            if model_key in model_name.lower():
                # Use 60% of limit for context (leaving room for response)
                return ContextBudget(max_tokens=int(limit * 0.6))

        # Default to conservative limit
        return ContextBudget(max_tokens=8000)
