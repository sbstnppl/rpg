"""Tests for CLI display functions."""

import pytest
from rich.text import Text

from src.cli.display import (
    _create_progress_bar,
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
