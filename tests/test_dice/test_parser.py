"""Tests for dice notation parser."""

import pytest

from src.dice.parser import parse_dice, DiceParseError
from src.dice.types import DiceExpression


class TestParseDiceBasic:
    """Tests for basic dice notation parsing."""

    def test_parse_1d20(self):
        """Test parsing standard d20."""
        expr = parse_dice("1d20")
        assert expr == DiceExpression(num_dice=1, die_size=20, modifier=0)

    def test_parse_2d6(self):
        """Test parsing multiple dice."""
        expr = parse_dice("2d6")
        assert expr == DiceExpression(num_dice=2, die_size=6, modifier=0)

    def test_parse_d100(self):
        """Test parsing d100 without leading number."""
        expr = parse_dice("d100")
        assert expr == DiceExpression(num_dice=1, die_size=100, modifier=0)

    def test_parse_d20_implicit_one(self):
        """Test parsing d20 implies 1d20."""
        expr = parse_dice("d20")
        assert expr == DiceExpression(num_dice=1, die_size=20, modifier=0)

    def test_parse_4d6(self):
        """Test parsing 4d6."""
        expr = parse_dice("4d6")
        assert expr == DiceExpression(num_dice=4, die_size=6, modifier=0)


class TestParseDiceWithModifiers:
    """Tests for dice notation with modifiers."""

    def test_parse_positive_modifier(self):
        """Test parsing with positive modifier."""
        expr = parse_dice("2d6+3")
        assert expr == DiceExpression(num_dice=2, die_size=6, modifier=3)

    def test_parse_negative_modifier(self):
        """Test parsing with negative modifier."""
        expr = parse_dice("4d6-2")
        assert expr == DiceExpression(num_dice=4, die_size=6, modifier=-2)

    def test_parse_large_modifier(self):
        """Test parsing with large modifier."""
        expr = parse_dice("1d20+15")
        assert expr == DiceExpression(num_dice=1, die_size=20, modifier=15)

    def test_parse_modifier_with_spaces(self):
        """Test parsing with spaces around modifier."""
        expr = parse_dice("1d20 + 5")
        assert expr == DiceExpression(num_dice=1, die_size=20, modifier=5)

    def test_parse_modifier_negative_with_spaces(self):
        """Test parsing negative modifier with spaces."""
        expr = parse_dice("2d8 - 3")
        assert expr == DiceExpression(num_dice=2, die_size=8, modifier=-3)


class TestParseDiceVariousSizes:
    """Tests for various die sizes."""

    def test_parse_d4(self):
        """Test parsing d4."""
        expr = parse_dice("1d4")
        assert expr.die_size == 4

    def test_parse_d6(self):
        """Test parsing d6."""
        expr = parse_dice("3d6")
        assert expr.die_size == 6

    def test_parse_d8(self):
        """Test parsing d8."""
        expr = parse_dice("1d8")
        assert expr.die_size == 8

    def test_parse_d10(self):
        """Test parsing d10."""
        expr = parse_dice("2d10")
        assert expr.die_size == 10

    def test_parse_d12(self):
        """Test parsing d12."""
        expr = parse_dice("1d12")
        assert expr.die_size == 12

    def test_parse_d20(self):
        """Test parsing d20."""
        expr = parse_dice("1d20")
        assert expr.die_size == 20

    def test_parse_d100(self):
        """Test parsing d100 (percentile)."""
        expr = parse_dice("1d100")
        assert expr.die_size == 100


class TestParseDiceCaseInsensitive:
    """Tests for case insensitivity."""

    def test_parse_uppercase_d(self):
        """Test parsing with uppercase D."""
        expr = parse_dice("2D6")
        assert expr == DiceExpression(num_dice=2, die_size=6, modifier=0)

    def test_parse_mixed_case(self):
        """Test parsing with mixed case."""
        expr = parse_dice("1D20+5")
        assert expr == DiceExpression(num_dice=1, die_size=20, modifier=5)


class TestParseDiceErrors:
    """Tests for invalid dice notation."""

    def test_parse_empty_string_raises(self):
        """Test that empty string raises error."""
        with pytest.raises(DiceParseError, match="empty"):
            parse_dice("")

    def test_parse_just_d_raises(self):
        """Test that just 'd' raises error."""
        with pytest.raises(DiceParseError, match="Invalid"):
            parse_dice("d")

    def test_parse_no_die_size_raises(self):
        """Test that missing die size raises error."""
        with pytest.raises(DiceParseError, match="Invalid"):
            parse_dice("2d")

    def test_parse_zero_dice_raises(self):
        """Test that zero dice raises error."""
        with pytest.raises(DiceParseError, match="at least 1"):
            parse_dice("0d6")

    def test_parse_zero_die_size_raises(self):
        """Test that zero die size raises error."""
        with pytest.raises(DiceParseError, match="at least 1"):
            parse_dice("1d0")

    def test_parse_negative_dice_raises(self):
        """Test that negative dice count raises error."""
        with pytest.raises(DiceParseError, match="Invalid"):
            parse_dice("-1d6")

    def test_parse_non_numeric_raises(self):
        """Test that non-numeric input raises error."""
        with pytest.raises(DiceParseError, match="Invalid"):
            parse_dice("abc")

    def test_parse_no_d_raises(self):
        """Test that missing 'd' raises error."""
        with pytest.raises(DiceParseError, match="Invalid"):
            parse_dice("26")

    def test_parse_invalid_modifier_raises(self):
        """Test that invalid modifier raises error."""
        with pytest.raises(DiceParseError, match="Invalid"):
            parse_dice("1d20+abc")
