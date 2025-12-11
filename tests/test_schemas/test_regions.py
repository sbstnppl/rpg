"""Tests for the regions module."""

import pytest

from src.schemas.regions import (
    REGIONS_CONTEMPORARY,
    REGIONS_FANTASY,
    REGIONS_SCIFI,
    RegionCulture,
    get_default_region_for_setting,
    get_regions_for_setting,
)


class TestRegionCulture:
    """Tests for RegionCulture dataclass."""

    def test_skin_color_weights_sum_to_approximately_one(self):
        """Test that skin color weights sum to approximately 1.0."""
        for regions in [REGIONS_CONTEMPORARY, REGIONS_FANTASY, REGIONS_SCIFI]:
            for region_name, culture in regions.items():
                total = sum(culture.skin_color_weights.values())
                assert 0.99 <= total <= 1.01, (
                    f"Region {region_name} skin weights sum to {total}, expected ~1.0"
                )

    def test_all_regions_have_required_fields(self):
        """Test that all regions have non-empty required fields."""
        for regions in [REGIONS_CONTEMPORARY, REGIONS_FANTASY, REGIONS_SCIFI]:
            for region_name, culture in regions.items():
                assert len(culture.skin_color_weights) > 0, f"{region_name} has no skin colors"
                assert culture.accent_style, f"{region_name} has no accent style"
                assert len(culture.common_foods) > 0, f"{region_name} has no common foods"
                assert len(culture.common_drinks) > 0, f"{region_name} has no common drinks"
                assert culture.naming_style, f"{region_name} has no naming style"


class TestRegionsContemporary:
    """Tests for contemporary setting regions."""

    def test_has_major_world_regions(self):
        """Test that major world regions are represented."""
        expected_regions = [
            "Northern Europe",
            "Mediterranean",
            "Sub-Saharan Africa",
            "East Asia",
            "South Asia",
            "North America",
            "Latin America",
        ]
        for region in expected_regions:
            assert region in REGIONS_CONTEMPORARY, f"Missing region: {region}"

    def test_northern_europe_has_fair_skin_bias(self):
        """Test Northern Europe has appropriate skin color distribution."""
        culture = REGIONS_CONTEMPORARY["Northern Europe"]
        fair_weight = culture.skin_color_weights.get("fair", 0)
        pale_weight = culture.skin_color_weights.get("pale", 0)
        assert fair_weight + pale_weight >= 0.5, "Northern Europe should have majority fair/pale"

    def test_sub_saharan_africa_has_dark_skin_bias(self):
        """Test Sub-Saharan Africa has appropriate skin color distribution."""
        culture = REGIONS_CONTEMPORARY["Sub-Saharan Africa"]
        dark_weight = culture.skin_color_weights.get("dark", 0)
        dark_brown_weight = culture.skin_color_weights.get("dark brown", 0)
        brown_weight = culture.skin_color_weights.get("brown", 0)
        assert dark_weight + dark_brown_weight + brown_weight >= 0.7


class TestRegionsFantasy:
    """Tests for fantasy setting regions."""

    def test_has_typical_fantasy_regions(self):
        """Test that typical fantasy regions are represented."""
        expected_regions = [
            "Northern Kingdoms",
            "Elven Lands",
            "Dwarven Mountains",
            "Central Plains",
        ]
        for region in expected_regions:
            assert region in REGIONS_FANTASY, f"Missing region: {region}"

    def test_dwarven_mountains_has_height_modifier(self):
        """Test dwarves have negative height modifier."""
        culture = REGIONS_FANTASY["Dwarven Mountains"]
        assert culture.height_modifier_cm < 0, "Dwarves should be shorter"

    def test_elven_lands_has_height_modifier(self):
        """Test elves have positive height modifier."""
        culture = REGIONS_FANTASY["Elven Lands"]
        assert culture.height_modifier_cm > 0, "Elves should be taller"


class TestRegionsScifi:
    """Tests for sci-fi setting regions."""

    def test_has_typical_scifi_regions(self):
        """Test that typical sci-fi regions are represented."""
        expected_regions = [
            "Earth Standard",
            "Martian Colonies",
            "Outer Rim",
        ]
        for region in expected_regions:
            assert region in REGIONS_SCIFI, f"Missing region: {region}"

    def test_alien_homeworlds_has_exotic_skin_colors(self):
        """Test alien regions have non-standard skin colors."""
        culture = REGIONS_SCIFI["Alien Homeworlds"]
        exotic_colors = ["pale blue", "green-tinged", "purple-hued", "iridescent"]
        has_exotic = any(color in culture.skin_color_weights for color in exotic_colors)
        assert has_exotic, "Alien homeworlds should have exotic skin colors"


class TestGetRegionsForSetting:
    """Tests for get_regions_for_setting function."""

    def test_fantasy_setting(self):
        """Test fantasy setting returns fantasy regions."""
        regions = get_regions_for_setting("fantasy")
        assert "Central Plains" in regions
        assert "Elven Lands" in regions

    def test_contemporary_setting(self):
        """Test contemporary setting returns contemporary regions."""
        regions = get_regions_for_setting("contemporary")
        assert "North America" in regions
        assert "Northern Europe" in regions

    def test_scifi_setting(self):
        """Test scifi setting returns scifi regions."""
        regions = get_regions_for_setting("scifi")
        assert "Earth Standard" in regions
        assert "Martian Colonies" in regions

    def test_case_insensitive(self):
        """Test that setting lookup is case-insensitive."""
        assert get_regions_for_setting("FANTASY") == get_regions_for_setting("fantasy")
        assert get_regions_for_setting("SciFi") == get_regions_for_setting("scifi")

    def test_unknown_setting_defaults_to_contemporary(self):
        """Test that unknown settings default to contemporary."""
        regions = get_regions_for_setting("unknown_setting")
        assert "North America" in regions


class TestGetDefaultRegion:
    """Tests for get_default_region_for_setting function."""

    def test_fantasy_default(self):
        """Test fantasy default region."""
        assert get_default_region_for_setting("fantasy") == "Central Plains"

    def test_contemporary_default(self):
        """Test contemporary default region."""
        assert get_default_region_for_setting("contemporary") == "North America"

    def test_scifi_default(self):
        """Test scifi default region."""
        assert get_default_region_for_setting("scifi") == "Earth Standard"
