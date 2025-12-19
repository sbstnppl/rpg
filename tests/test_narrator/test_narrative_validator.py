"""Tests for narrative validation."""

import pytest
from src.narrator.narrative_validator import NarrativeValidator, NarrativeValidationResult


class TestNarrativeValidator:
    """Tests for NarrativeValidator."""

    def test_validates_known_items(self) -> None:
        """Test validation passes for known items."""
        validator = NarrativeValidator(
            items_at_location=[{"name": "Washbasin", "key": "washbasin_1"}],
            npcs_present=[],
            available_exits=[],
        )

        narrative = "You find the washbasin in the corner of the room."
        result = validator.validate(narrative)

        assert result.is_valid
        assert len(result.hallucinated_items) == 0

    def test_validates_spawned_items(self) -> None:
        """Test validation passes for spawned items."""
        validator = NarrativeValidator(
            items_at_location=[],
            npcs_present=[],
            available_exits=[],
            spawned_items=[{"display_name": "Washbasin", "item_key": "washbasin_1"}],
        )

        narrative = "You discover a simple washbasin near the window."
        result = validator.validate(narrative)

        assert result.is_valid
        assert len(result.hallucinated_items) == 0

    def test_validates_inventory_items(self) -> None:
        """Test validation passes for inventory items."""
        validator = NarrativeValidator(
            items_at_location=[],
            npcs_present=[],
            available_exits=[],
            inventory=[{"name": "Dagger", "key": "player_dagger"}],
        )

        narrative = "You grip your dagger tightly."
        result = validator.validate(narrative)

        assert result.is_valid
        assert len(result.hallucinated_items) == 0

    def test_detects_hallucinated_items(self) -> None:
        """Test detection of items not in context."""
        validator = NarrativeValidator(
            items_at_location=[],
            npcs_present=[],
            available_exits=[],
        )

        narrative = "You find a dusty mirror on the shelf and an old book nearby."
        result = validator.validate(narrative)

        assert not result.is_valid
        # Should detect at least 'mirror' or 'book'
        assert len(result.hallucinated_items) > 0

    def test_partial_match_allowed(self) -> None:
        """Test that partial matches work (e.g., 'washbasin' matches 'old washbasin')."""
        validator = NarrativeValidator(
            items_at_location=[{"name": "Old Washbasin", "key": "washbasin_1"}],
        )

        narrative = "You notice the washbasin in the corner."
        result = validator.validate(narrative)

        assert result.is_valid

    def test_common_words_not_flagged(self) -> None:
        """Test that common environmental words aren't flagged as hallucinations."""
        validator = NarrativeValidator(
            items_at_location=[],
            npcs_present=[],
            available_exits=[],
        )

        # Words like "water", "stone", "wood" should not be flagged
        narrative = "You see water dripping from the stone wall."
        result = validator.validate(narrative)

        # Should not flag these common environmental words
        assert result.is_valid

    def test_clothing_and_room_words_not_flagged(self) -> None:
        """Test that clothes, rooms, and adjectives aren't flagged as hallucinations."""
        validator = NarrativeValidator(
            items_at_location=[],
            npcs_present=[],
            available_exits=[],
        )

        # Words like "clothes", "bedrooms", "proper" should not be flagged
        narrative = (
            "Your clothes feel grimy as you stand in the bedroom. "
            "You need a proper wash to feel clean."
        )
        result = validator.validate(narrative)

        # Should not flag these common words
        assert result.is_valid
        assert len(result.hallucinated_items) == 0

    def test_short_narrative_skipped(self) -> None:
        """Test that very short narratives skip validation."""
        validator = NarrativeValidator(
            items_at_location=[],
            npcs_present=[],
            available_exits=[],
        )

        narrative = "You wait."
        result = validator.validate(narrative)

        # Short narratives should pass
        assert result.is_valid


class TestConstraintPrompt:
    """Tests for constraint prompt generation."""

    def test_constraint_prompt_with_items(self) -> None:
        """Test constraint prompt includes known items."""
        validator = NarrativeValidator(
            items_at_location=[{"name": "Washbasin", "key": "washbasin_1"}],
            npcs_present=[{"name": "Elena", "key": "elena"}],
        )

        prompt = validator.get_constraint_prompt()

        assert "washbasin" in prompt.lower()
        assert "elena" in prompt.lower()
        assert "STRICT CONSTRAINTS" in prompt

    def test_constraint_prompt_empty_state(self) -> None:
        """Test constraint prompt with empty state."""
        validator = NarrativeValidator(
            items_at_location=[],
            npcs_present=[],
            available_exits=[],
        )

        prompt = validator.get_constraint_prompt()

        assert "none" in prompt.lower()
        assert "STRICT CONSTRAINTS" in prompt


class TestNarrativeValidationResult:
    """Tests for NarrativeValidationResult dataclass."""

    def test_default_values(self) -> None:
        """Test default values are set correctly."""
        result = NarrativeValidationResult()

        assert result.is_valid is True
        assert result.hallucinated_items == []
        assert result.hallucinated_npcs == []
        assert result.hallucinated_locations == []
        assert result.warnings == []

    def test_custom_values(self) -> None:
        """Test custom values are stored correctly."""
        result = NarrativeValidationResult(
            is_valid=False,
            hallucinated_items=["mirror", "book"],
            warnings=["Some warning"],
        )

        assert result.is_valid is False
        assert result.hallucinated_items == ["mirror", "book"]
        assert result.warnings == ["Some warning"]
