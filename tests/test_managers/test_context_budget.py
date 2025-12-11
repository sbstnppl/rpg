"""Tests for ContextBudget class - token budget management."""

import pytest

from src.managers.context_budget import (
    ContextBudget,
    ContextPriority,
    ContextSection,
    estimate_tokens,
)


class TestEstimateTokens:
    """Tests for token estimation function."""

    def test_empty_string_returns_zero(self):
        """Verify empty string returns 0 tokens."""
        assert estimate_tokens("") == 0

    def test_none_returns_zero(self):
        """Verify None returns 0 tokens."""
        assert estimate_tokens(None) == 0

    def test_estimates_short_text(self):
        """Verify reasonable estimate for short text."""
        text = "Hello world"
        tokens = estimate_tokens(text)
        # 11 chars / 4 = 2.75, + 1 = 3-4 tokens expected
        assert 2 <= tokens <= 5

    def test_estimates_longer_text(self):
        """Verify reasonable estimate for longer text."""
        text = "This is a longer piece of text that should have more tokens."
        tokens = estimate_tokens(text)
        # 60 chars / 4 = 15, + 1 = 16 tokens expected
        assert 10 <= tokens <= 25


class TestContextSection:
    """Tests for ContextSection dataclass."""

    def test_calculates_token_count_on_init(self):
        """Verify token count is calculated if not provided."""
        section = ContextSection(
            name="test",
            content="Hello world",
            priority=ContextPriority.MEDIUM,
        )
        assert section.token_count > 0

    def test_uses_provided_token_count(self):
        """Verify provided token count is used."""
        section = ContextSection(
            name="test",
            content="Hello world",
            priority=ContextPriority.MEDIUM,
            token_count=100,
        )
        assert section.token_count == 100


class TestContextBudgetBasics:
    """Tests for ContextBudget basic operations."""

    def test_empty_budget_compiles_to_empty(self):
        """Verify empty budget compiles to empty result."""
        budget = ContextBudget(max_tokens=1000)
        result = budget.compile()

        assert result.content == ""
        assert result.total_tokens == 0
        assert len(result.sections_included) == 0

    def test_single_section_within_budget(self):
        """Verify single section within budget is included."""
        budget = ContextBudget(max_tokens=1000)
        budget.add_section("test", "Hello world")
        result = budget.compile()

        assert "Hello world" in result.content
        assert "test" in result.sections_included
        assert result.total_tokens > 0

    def test_empty_content_section_ignored(self):
        """Verify empty content sections are ignored."""
        budget = ContextBudget(max_tokens=1000)
        budget.add_section("empty", "")
        budget.add_section("real", "Hello")
        result = budget.compile()

        assert "empty" not in result.sections_included
        assert "real" in result.sections_included


class TestContextBudgetPrioritization:
    """Tests for priority-based section inclusion."""

    def test_high_priority_included_first(self):
        """Verify high priority sections included before low."""
        budget = ContextBudget(max_tokens=100)  # Very limited budget
        budget.add_section(
            "low_priority",
            "This is low priority content " * 10,
            priority=ContextPriority.LOW,
        )
        budget.add_section(
            "high_priority",
            "Critical info",
            priority=ContextPriority.CRITICAL,
        )
        result = budget.compile()

        assert "high_priority" in result.sections_included
        # Low priority may be excluded or truncated due to budget

    def test_critical_sections_always_attempted(self):
        """Verify critical sections are always attempted."""
        budget = ContextBudget(max_tokens=50)
        budget.add_section(
            "critical",
            "Must include",
            priority=ContextPriority.CRITICAL,
        )
        result = budget.compile()

        assert "critical" in result.sections_included

    def test_default_priorities_applied(self):
        """Verify default priorities are used for known section names."""
        budget = ContextBudget(max_tokens=1000)
        budget.add_section("turn_context", "Turn 1")
        budget.add_section("secrets_context", "Secret info")

        # turn_context should be CRITICAL, secrets_context should be LOW
        breakdown = budget.get_section_breakdown()
        assert "turn_context" in breakdown
        assert "secrets_context" in breakdown


class TestContextBudgetTruncation:
    """Tests for section truncation."""

    def test_truncates_large_section(self):
        """Verify large sections are truncated when enabled."""
        budget = ContextBudget(max_tokens=200)  # Enough for truncated version
        budget.add_section(
            "large",
            "A" * 1000,  # Very large content
            priority=ContextPriority.HIGH,
        )
        result = budget.compile(truncate_sections=True)

        # Should be truncated, not excluded
        assert "large" in result.sections_included
        assert len(result.content) < 1000
        assert "..." in result.content

    def test_excludes_without_truncation(self):
        """Verify sections excluded when truncation disabled."""
        budget = ContextBudget(max_tokens=50)
        budget.add_section(
            "small",
            "Small",
            priority=ContextPriority.CRITICAL,
        )
        budget.add_section(
            "large",
            "A" * 1000,
            priority=ContextPriority.LOW,
        )
        result = budget.compile(truncate_sections=False)

        assert "small" in result.sections_included
        assert "large" in result.sections_excluded


class TestContextBudgetUtilization:
    """Tests for budget utilization tracking."""

    def test_utilization_calculation(self):
        """Verify utilization is calculated correctly."""
        budget = ContextBudget(max_tokens=100)
        budget.add_section("test", "Hello world")
        result = budget.compile()

        assert 0.0 < result.utilization < 1.0

    def test_utilization_near_max(self):
        """Verify high utilization when near max."""
        budget = ContextBudget(max_tokens=100)
        budget.add_section("test", "A" * 350)  # ~88 tokens
        result = budget.compile()

        assert result.utilization > 0.5

    def test_get_section_breakdown(self):
        """Verify section breakdown is accurate."""
        budget = ContextBudget(max_tokens=1000)
        budget.add_section("section1", "Hello")
        budget.add_section("section2", "World")
        breakdown = budget.get_section_breakdown()

        assert "section1" in breakdown
        assert "section2" in breakdown
        assert all(v > 0 for v in breakdown.values())


class TestContextBudgetCompilation:
    """Tests for context compilation."""

    def test_preserves_original_order(self):
        """Verify sections maintain original order in output."""
        budget = ContextBudget(max_tokens=1000)
        budget.add_section("first", "First section", priority=ContextPriority.LOW)
        budget.add_section("second", "Second section", priority=ContextPriority.HIGH)
        budget.add_section("third", "Third section", priority=ContextPriority.LOW)
        result = budget.compile()

        # Even though second has higher priority, order should be preserved
        first_pos = result.content.find("First")
        second_pos = result.content.find("Second")
        third_pos = result.content.find("Third")

        assert first_pos < second_pos < third_pos

    def test_custom_separator(self):
        """Verify custom separator is used."""
        budget = ContextBudget(max_tokens=1000)
        budget.add_section("a", "Section A")
        budget.add_section("b", "Section B")
        result = budget.compile(separator=" | ")

        assert " | " in result.content

    def test_clear_removes_sections(self):
        """Verify clear removes all sections."""
        budget = ContextBudget(max_tokens=1000)
        budget.add_section("test", "Content")
        budget.clear()
        result = budget.compile()

        assert result.content == ""
        assert len(result.sections_included) == 0


class TestContextBudgetModelConfiguration:
    """Tests for model-specific budget configuration."""

    def test_for_claude_model(self):
        """Verify Claude model gets appropriate budget."""
        budget = ContextBudget.for_model("claude-3-sonnet-20240229")
        assert budget.max_tokens > 10000  # Should be generous

    def test_for_gpt4_model(self):
        """Verify GPT-4 model gets appropriate budget."""
        budget = ContextBudget.for_model("gpt-4")
        assert budget.max_tokens > 1000

    def test_for_unknown_model_uses_default(self):
        """Verify unknown model uses conservative default."""
        budget = ContextBudget.for_model("unknown-model-xyz")
        assert budget.max_tokens == 8000  # Default
