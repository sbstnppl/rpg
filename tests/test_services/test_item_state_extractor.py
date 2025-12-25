"""Tests for the ItemStateExtractor service."""

import pytest

from src.services.item_state_extractor import (
    extract_state_from_name,
    ExtractionResult,
    STATE_ADJECTIVES,
)


class TestExtractStateFromName:
    """Tests for extract_state_from_name function."""

    def test_clean_shirt_extracts_cleanliness(self):
        """Test 'Clean Linen Shirt' extracts cleanliness state."""
        result = extract_state_from_name("Clean Linen Shirt")
        assert result.base_name == "Linen Shirt"
        assert result.state == {"cleanliness": "clean"}

    def test_dirty_shirt_extracts_cleanliness(self):
        """Test 'Dirty Linen Shirt' extracts dirty state."""
        result = extract_state_from_name("Dirty Linen Shirt")
        assert result.base_name == "Linen Shirt"
        assert result.state == {"cleanliness": "dirty"}

    def test_rusty_sword_extracts_condition(self):
        """Test 'Rusty Iron Sword' extracts condition as damaged."""
        result = extract_state_from_name("Rusty Iron Sword")
        assert result.base_name == "Iron Sword"
        assert result.state == {"condition": "damaged"}

    def test_fresh_bread_extracts_freshness(self):
        """Test 'Fresh Bread' extracts freshness state."""
        result = extract_state_from_name("Fresh Bread")
        assert result.base_name == "Bread"
        assert result.state == {"freshness": "fresh"}

    def test_stale_bread_extracts_freshness(self):
        """Test 'Stale Bread' extracts stale freshness."""
        result = extract_state_from_name("Stale Bread")
        assert result.base_name == "Bread"
        assert result.state == {"freshness": "stale"}

    def test_fine_leather_extracts_quality(self):
        """Test 'Fine Leather Boots' extracts quality."""
        result = extract_state_from_name("Fine Leather Boots")
        assert result.base_name == "Leather Boots"
        assert result.state == {"quality": "fine"}

    def test_crude_extracts_poor_quality(self):
        """Test 'Crude Wooden Club' extracts poor quality."""
        result = extract_state_from_name("Crude Wooden Club")
        assert result.base_name == "Wooden Club"
        assert result.state == {"quality": "poor"}

    def test_old_extracts_age(self):
        """Test 'Old Map' extracts age state."""
        result = extract_state_from_name("Old Map")
        assert result.base_name == "Map"
        assert result.state == {"age": "old"}

    def test_ancient_extracts_age(self):
        """Test 'Ancient Tome' extracts ancient age."""
        result = extract_state_from_name("Ancient Tome")
        assert result.base_name == "Tome"
        assert result.state == {"age": "ancient"}

    def test_multiple_adjectives(self):
        """Test multiple state adjectives extracted correctly."""
        result = extract_state_from_name("Dirty Old Worn Cloak")
        assert result.base_name == "Cloak"
        assert result.state == {
            "cleanliness": "dirty",
            "age": "old",
            "condition": "worn",
        }

    def test_no_state_adjectives(self):
        """Test item with no state adjectives returns empty state."""
        result = extract_state_from_name("Iron Sword")
        assert result.base_name == "Iron Sword"
        assert result.state == {}

    def test_single_word_no_adjective(self):
        """Test single word item name."""
        result = extract_state_from_name("Bread")
        assert result.base_name == "Bread"
        assert result.state == {}

    def test_preserves_case_in_base_name(self):
        """Test base name preserves original case."""
        result = extract_state_from_name("Clean Dragon Scale")
        assert result.base_name == "Dragon Scale"

    def test_compound_adjective_well_worn(self):
        """Test compound adjective 'well-worn' as single unit."""
        result = extract_state_from_name("Well-Worn Boots")
        assert result.base_name == "Boots"
        assert result.state == {"condition": "worn"}

    def test_compound_adjective_battle_worn(self):
        """Test compound adjective 'battle-worn'."""
        result = extract_state_from_name("Battle-Worn Shield")
        assert result.base_name == "Shield"
        assert result.state == {"condition": "worn"}

    def test_pristine_extracts_condition(self):
        """Test 'Pristine' extracts pristine condition."""
        result = extract_state_from_name("Pristine Silver Ring")
        assert result.base_name == "Silver Ring"
        assert result.state == {"condition": "pristine"}

    def test_new_extracts_pristine_condition(self):
        """Test 'New' maps to pristine condition."""
        result = extract_state_from_name("New Leather Gloves")
        assert result.base_name == "Leather Gloves"
        assert result.state == {"condition": "pristine"}

    def test_broken_extracts_condition(self):
        """Test 'Broken' extracts broken condition."""
        result = extract_state_from_name("Broken Lantern")
        assert result.base_name == "Lantern"
        assert result.state == {"condition": "broken"}

    def test_damaged_extracts_condition(self):
        """Test 'Damaged' extracts damaged condition."""
        result = extract_state_from_name("Damaged Armor")
        assert result.base_name == "Armor"
        assert result.state == {"condition": "damaged"}

    def test_filthy_extracts_cleanliness(self):
        """Test 'Filthy' extracts filthy cleanliness."""
        result = extract_state_from_name("Filthy Rags")
        assert result.base_name == "Rags"
        assert result.state == {"cleanliness": "filthy"}

    def test_tattered_extracts_damaged_condition(self):
        """Test 'Tattered' extracts damaged condition."""
        result = extract_state_from_name("Tattered Cloak")
        assert result.base_name == "Cloak"
        assert result.state == {"condition": "damaged"}

    def test_weathered_extracts_worn_condition(self):
        """Test 'Weathered' extracts worn condition."""
        result = extract_state_from_name("Weathered Journal")
        assert result.base_name == "Journal"
        assert result.state == {"condition": "worn"}

    def test_case_insensitive_adjective_matching(self):
        """Test adjective matching is case-insensitive."""
        result = extract_state_from_name("CLEAN Shirt")
        assert result.base_name == "Shirt"
        assert result.state == {"cleanliness": "clean"}

    def test_lowercase_input(self):
        """Test lowercase input is handled correctly."""
        result = extract_state_from_name("dirty old sword")
        assert result.base_name == "sword"
        assert "cleanliness" in result.state
        assert "age" in result.state


class TestExtractionResult:
    """Tests for ExtractionResult dataclass."""

    def test_dataclass_fields(self):
        """Test ExtractionResult has expected fields."""
        result = ExtractionResult(base_name="Test", state={"key": "value"})
        assert result.base_name == "Test"
        assert result.state == {"key": "value"}


class TestStateAdjectives:
    """Tests for STATE_ADJECTIVES constant."""

    def test_cleanliness_adjectives_exist(self):
        """Test cleanliness adjectives are defined."""
        assert "clean" in STATE_ADJECTIVES
        assert "dirty" in STATE_ADJECTIVES
        assert "filthy" in STATE_ADJECTIVES

    def test_condition_adjectives_exist(self):
        """Test condition adjectives are defined."""
        assert "pristine" in STATE_ADJECTIVES
        assert "worn" in STATE_ADJECTIVES
        assert "damaged" in STATE_ADJECTIVES
        assert "broken" in STATE_ADJECTIVES
        assert "rusty" in STATE_ADJECTIVES

    def test_freshness_adjectives_exist(self):
        """Test freshness adjectives are defined."""
        assert "fresh" in STATE_ADJECTIVES
        assert "stale" in STATE_ADJECTIVES

    def test_quality_adjectives_exist(self):
        """Test quality adjectives are defined."""
        assert "crude" in STATE_ADJECTIVES
        assert "fine" in STATE_ADJECTIVES

    def test_adjective_format(self):
        """Test adjectives map to (category, value) tuples."""
        category, value = STATE_ADJECTIVES["clean"]
        assert category == "cleanliness"
        assert value == "clean"
