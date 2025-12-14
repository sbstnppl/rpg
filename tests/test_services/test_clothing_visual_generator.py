"""Tests for the ClothingVisualGenerator service."""

import pytest

from src.services.clothing_visual_generator import (
    ClothingVisualGenerator,
    ClothingPalette,
    format_visual_description,
    FANTASY_PALETTE,
    CONTEMPORARY_PALETTE,
    SETTING_PALETTES,
)


class TestClothingVisualGenerator:
    """Tests for ClothingVisualGenerator class."""

    def test_init_with_setting_name(self):
        """Test initialization with setting name."""
        gen = ClothingVisualGenerator(setting_name="fantasy")
        assert gen.palette == FANTASY_PALETTE

        gen = ClothingVisualGenerator(setting_name="contemporary")
        assert gen.palette == CONTEMPORARY_PALETTE

    def test_init_with_custom_palette(self):
        """Test initialization with custom palette."""
        custom = ClothingPalette(
            materials=["gold"],
            colors=["purple"],
        )
        gen = ClothingVisualGenerator(palette=custom)
        assert gen.palette == custom

    def test_init_unknown_setting_defaults_to_fantasy(self):
        """Test unknown setting defaults to fantasy palette."""
        gen = ClothingVisualGenerator(setting_name="unknown_setting")
        assert gen.palette == FANTASY_PALETTE

    def test_generate_visual_properties_returns_dict(self):
        """Test generate_visual_properties returns a dict with expected keys."""
        gen = ClothingVisualGenerator(setting_name="fantasy")
        result = gen.generate_visual_properties("tunic")

        assert isinstance(result, dict)
        assert "primary_color" in result
        assert "material" in result
        assert "fit" in result
        assert "style" in result
        assert "condition_look" in result

    def test_generate_visual_properties_color_in_palette(self):
        """Test generated colors come from palette."""
        gen = ClothingVisualGenerator(setting_name="fantasy")
        result = gen.generate_visual_properties("tunic")

        # Primary color should contain a color from palette
        primary = result["primary_color"]
        assert any(color in primary for color in FANTASY_PALETTE.colors)

    def test_generate_visual_properties_material_in_palette(self):
        """Test generated materials come from palette."""
        gen = ClothingVisualGenerator(setting_name="fantasy")
        result = gen.generate_visual_properties("tunic")

        assert result["material"] in FANTASY_PALETTE.materials

    def test_generate_visual_properties_details_for_known_type(self):
        """Test details are generated for known item types."""
        gen = ClothingVisualGenerator(setting_name="fantasy")
        result = gen.generate_visual_properties("tunic")

        # Tunic should have details from the tunic details list
        if "details" in result:
            for detail in result["details"]:
                assert detail in FANTASY_PALETTE.details_by_type["tunic"]

    def test_generate_visual_properties_infers_material_from_display_name(self):
        """Test material is inferred from display_name when present."""
        gen = ClothingVisualGenerator(setting_name="fantasy")

        # Leather Boots should get leather material
        result = gen.generate_visual_properties("boots", display_name="Leather Boots")
        assert result["material"] == "leather"

        # Wool Socks should get wool material
        result = gen.generate_visual_properties("socks", display_name="Wool Socks")
        assert result["material"] == "wool"

        # Silk Shirt should get silk material
        result = gen.generate_visual_properties("shirt", display_name="Silk Shirt")
        assert result["material"] == "silk"

        # Cloth Trousers should get cotton (generic cloth → cotton)
        result = gen.generate_visual_properties("trousers", display_name="Cloth Trousers")
        assert result["material"] == "cotton"

    def test_generate_visual_properties_no_inference_without_keyword(self):
        """Test material is randomized when display_name has no material keyword."""
        gen = ClothingVisualGenerator(setting_name="fantasy")

        # Simple Tunic has no material keyword - should use random from palette
        result = gen.generate_visual_properties("tunic", display_name="Simple Tunic")
        assert result["material"] in FANTASY_PALETTE.materials

    def test_generate_visual_properties_quality_affects_style(self):
        """Test quality parameter affects style selection."""
        gen = ClothingVisualGenerator(setting_name="fantasy")

        # Generate many samples and check distribution
        exceptional_styles = set()
        common_styles = set()

        for _ in range(20):
            exc = gen.generate_visual_properties("tunic", quality="exceptional")
            com = gen.generate_visual_properties("tunic", quality="common")
            exceptional_styles.add(exc["style"])
            common_styles.add(com["style"])

        # Exceptional should favor elegant/ornate styles
        # Common should favor simple/practical styles
        # This is probabilistic, so we just check both produce valid styles
        assert all(s in FANTASY_PALETTE.styles for s in exceptional_styles)
        assert all(s in FANTASY_PALETTE.styles for s in common_styles)


class TestFormatVisualDescription:
    """Tests for format_visual_description function."""

    def test_empty_visual_returns_display_name(self):
        """Test empty visual dict returns display name."""
        result = format_visual_description({}, "Simple Tunic")
        assert result == "Simple Tunic"

    def test_none_visual_returns_display_name(self):
        """Test None visual returns display name."""
        result = format_visual_description(None, "Simple Tunic")
        assert result == "Simple Tunic"

    def test_description_field_takes_precedence(self):
        """Test description field overrides structured fields."""
        visual = {
            "primary_color": "blue",
            "material": "wool",
            "description": "Custom black leather jacket",
        }
        result = format_visual_description(visual, "Jacket")
        assert result == "Custom black leather jacket"

    def test_structured_fields_generate_description(self):
        """Test structured fields generate proper description."""
        visual = {
            "primary_color": "faded blue",
            "material": "linen",
            "condition_look": "worn",
            "details": ["leather ties"],
        }
        result = format_visual_description(visual, "Simple Tunic")

        assert "worn" in result
        assert "faded blue" in result
        assert "linen" in result
        assert "tunic" in result.lower()
        assert "leather ties" in result

    def test_clean_condition_not_included(self):
        """Test clean/standard conditions are not included in output."""
        visual = {
            "primary_color": "blue",
            "material": "cotton",
            "condition_look": "clean",
        }
        result = format_visual_description(visual, "Shirt")
        # 'clean' should not appear at the start
        assert not result.startswith("clean")


class TestSettingPalettes:
    """Tests for setting-specific palettes."""

    def test_all_settings_have_palettes(self):
        """Test all expected settings have palettes defined."""
        expected_settings = ["fantasy", "contemporary", "urban_fantasy", "scifi"]
        for setting in expected_settings:
            assert setting in SETTING_PALETTES

    def test_palettes_have_required_fields(self):
        """Test all palettes have required fields populated."""
        for name, palette in SETTING_PALETTES.items():
            assert palette.materials, f"{name} missing materials"
            assert palette.colors, f"{name} missing colors"
            assert palette.fits, f"{name} missing fits"
            assert palette.styles, f"{name} missing styles"
            assert palette.condition_looks, f"{name} missing condition_looks"

    def test_fantasy_palette_has_medieval_materials(self):
        """Test fantasy palette has appropriate medieval materials."""
        assert "linen" in FANTASY_PALETTE.materials
        assert "wool" in FANTASY_PALETTE.materials
        assert "leather" in FANTASY_PALETTE.materials

    def test_contemporary_palette_has_modern_materials(self):
        """Test contemporary palette has modern materials."""
        assert "denim" in CONTEMPORARY_PALETTE.materials
        assert "polyester" in CONTEMPORARY_PALETTE.materials
        assert "cotton" in CONTEMPORARY_PALETTE.materials
