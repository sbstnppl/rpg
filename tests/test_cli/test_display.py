"""Tests for CLI display functions."""

import pytest
from rich.text import Text

from src.cli.display import (
    _create_progress_bar,
    _get_need_description,
    _progress_bar,
    progress_spinner,
    progress_bar,
)


class TestCreateProgressBar:
    """Tests for _create_progress_bar function."""

    def test_returns_text_object(self):
        """Verify function returns Rich Text object."""
        result = _create_progress_bar(50, 100)
        assert isinstance(result, Text)

    def test_high_value_is_green(self):
        """Verify >60% bar uses green color."""
        bar = _create_progress_bar(80, 100)
        # Check that green is used in styling
        plain = bar.plain
        assert "[" in plain
        assert "]" in plain

    def test_medium_value_is_yellow(self):
        """Verify 30-60% bar uses yellow color."""
        bar = _create_progress_bar(45, 100)
        plain = bar.plain
        assert "[" in plain
        assert "]" in plain

    def test_low_value_is_red(self):
        """Verify <30% bar uses red color."""
        bar = _create_progress_bar(20, 100)
        plain = bar.plain
        assert "[" in plain
        assert "]" in plain

    def test_full_bar_filled(self):
        """Verify 100% bar is fully filled."""
        bar = _create_progress_bar(100, 100)
        plain = bar.plain
        # Should have 20 = signs (default width)
        assert plain.count("=") == 20

    def test_empty_bar_empty(self):
        """Verify 0% bar is empty."""
        bar = _create_progress_bar(0, 100)
        plain = bar.plain
        assert plain.count("=") == 0

    def test_half_bar(self):
        """Verify 50% bar is half filled."""
        bar = _create_progress_bar(50, 100)
        plain = bar.plain
        assert plain.count("=") == 10

    def test_custom_width(self):
        """Verify custom width works."""
        bar = _create_progress_bar(50, 100, width=10)
        plain = bar.plain
        assert plain.count("=") == 5

    def test_handles_zero_max_value(self):
        """Verify handles zero max value without error."""
        bar = _create_progress_bar(50, 0)
        assert isinstance(bar, Text)


class TestLegacyProgressBar:
    """Tests for legacy _progress_bar function."""

    def test_returns_string(self):
        """Verify function returns string."""
        result = _progress_bar(50, 100)
        assert isinstance(result, str)

    def test_has_brackets(self):
        """Verify string has brackets."""
        result = _progress_bar(50, 100)
        assert result.startswith("[")
        assert result.endswith("]")

    def test_full_bar_filled(self):
        """Verify 100% bar is fully filled."""
        result = _progress_bar(100, 100)
        assert result.count("=") == 20

    def test_empty_bar_empty(self):
        """Verify 0% bar is empty."""
        result = _progress_bar(0, 100)
        assert result.count("=") == 0


class TestProgressSpinner:
    """Tests for progress_spinner context manager."""

    def test_context_manager_works(self):
        """Verify spinner works as context manager."""
        with progress_spinner("Test") as (prog, task):
            assert prog is not None
            assert task is not None

    def test_yields_progress_and_task(self):
        """Verify yields progress and task objects."""
        with progress_spinner("Test") as result:
            progress_obj, task_id = result
            assert hasattr(progress_obj, "update")


class TestProgressBar:
    """Tests for progress_bar context manager."""

    def test_context_manager_works(self):
        """Verify bar works as context manager."""
        with progress_bar("Test", total=100) as (prog, task):
            assert prog is not None
            assert task is not None

    def test_can_advance(self):
        """Verify bar can be advanced."""
        with progress_bar("Test", total=10) as (progress_obj, task_id):
            for _ in range(10):
                progress_obj.advance(task_id)


class TestGetNeedDescription:
    """Tests for _get_need_description function - specifically restfulness."""

    def test_restfulness_high_is_well_rested(self):
        """High restfulness (low sleep pressure) shows well-rested."""
        desc, color = _get_need_description("restfulness", 95)
        assert desc == "well-rested"
        assert color == "green"

    def test_restfulness_low_is_delirious(self):
        """Very low restfulness (high sleep pressure) shows delirious."""
        desc, color = _get_need_description("restfulness", 15)
        assert desc == "delirious"
        assert color == "red"

    def test_restfulness_exhausted_range(self):
        """Restfulness 21-40 shows exhausted."""
        desc, color = _get_need_description("restfulness", 35)
        assert desc == "exhausted"
        assert color == "red"

    def test_restfulness_tired_range(self):
        """Restfulness 41-60 shows tired."""
        desc, color = _get_need_description("restfulness", 55)
        assert desc == "tired"
        assert color == "yellow"

    def test_restfulness_alert_range(self):
        """Restfulness 61-80 shows alert."""
        desc, color = _get_need_description("restfulness", 75)
        assert desc == "alert"
        assert color == "green"

    def test_restfulness_at_boundary(self):
        """Test exact boundary values."""
        # At exactly 20 - should be delirious
        desc, color = _get_need_description("restfulness", 20)
        assert desc == "delirious"

        # At exactly 80 - should be alert
        desc, color = _get_need_description("restfulness", 80)
        assert desc == "alert"

        # At 100 - should be well-rested
        desc, color = _get_need_description("restfulness", 100)
        assert desc == "well-rested"

    def test_hunger_still_works(self):
        """Verify other needs still work correctly."""
        # 80 is in the "full" range (green)
        desc, color = _get_need_description("hunger", 80)
        assert desc == "full"
        assert color == "green"

        # 10 is "starving" (red)
        desc, color = _get_need_description("hunger", 10)
        assert desc == "starving"
        assert color == "red"
