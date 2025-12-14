"""Service for generating visual properties for clothing and items.

This module provides randomized visual attribute generation for items,
using setting-specific palettes to ensure thematic consistency.
"""

import random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ClothingPalette:
    """Setting-specific palette for generating clothing visuals.

    Attributes:
        materials: Available fabric/material types (e.g., "linen", "denim").
        colors: Base color options (e.g., "brown", "blue").
        color_modifiers: Modifiers for colors (e.g., "faded", "dark").
        fits: Fit styles (e.g., "loose", "fitted").
        styles: Overall style categories (e.g., "simple", "elegant").
        condition_looks: Visual condition states (e.g., "pristine", "worn").
        details_by_type: Item-type-specific detail options.
    """

    materials: list[str] = field(default_factory=lambda: ["cloth"])
    colors: list[str] = field(default_factory=lambda: ["grey", "brown"])
    color_modifiers: list[str] = field(default_factory=lambda: ["", "dark", "light"])
    fits: list[str] = field(default_factory=lambda: ["loose", "fitted"])
    styles: list[str] = field(default_factory=lambda: ["simple", "practical"])
    condition_looks: list[str] = field(
        default_factory=lambda: ["pristine", "clean", "worn", "well-worn", "tattered"]
    )
    details_by_type: dict[str, list[str]] = field(default_factory=dict)


# Default palettes for each setting
FANTASY_PALETTE = ClothingPalette(
    materials=["linen", "wool", "leather", "silk", "cotton", "velvet", "fur", "hide", "canvas"],
    colors=["brown", "grey", "white", "cream", "blue", "green", "red", "black", "tan", "beige"],
    color_modifiers=["", "faded", "dark", "light", "dusty", "sun-bleached", "dyed"],
    fits=["loose", "fitted", "baggy", "tailored", "flowing"],
    styles=["simple", "ornate", "rugged", "elegant", "practical", "peasant", "noble"],
    condition_looks=["pristine", "clean", "worn", "well-worn", "patched", "tattered", "travel-stained"],
    details_by_type={
        "tunic": ["leather ties", "embroidered hem", "patch pockets", "wooden buttons", "rope belt"],
        "shirt": ["laced collar", "billowing sleeves", "embroidered cuffs"],
        "trousers": ["drawstring waist", "reinforced knees", "side pockets", "leather patches"],
        "pants": ["drawstring waist", "reinforced knees", "side pockets", "leather patches"],
        "boots": ["worn soles", "brass buckles", "fur lining", "leather straps", "iron-shod heels"],
        "shoes": ["leather laces", "worn heels", "simple stitching"],
        "cloak": ["hooded", "fur-trimmed", "brass clasp", "embroidered edge", "travel-worn"],
        "dress": ["laced bodice", "flowing skirt", "embroidered neckline", "gathered waist"],
        "robe": ["wide sleeves", "deep hood", "silver trim", "mystic symbols"],
        "hat": ["wide brim", "feathered", "pointed", "leather band"],
        "belt": ["brass buckle", "leather pouches", "worn notches", "iron rings"],
        "gloves": ["leather palms", "fur-lined", "fingerless"],
        "socks": ["wool knit", "darned heels", "thick weave"],
        "undershirt": ["thin linen", "sleeveless", "sweat-stained"],
        "smallclothes": ["simple cotton", "linen drawstring"],
    },
)

CONTEMPORARY_PALETTE = ClothingPalette(
    materials=["cotton", "denim", "polyester", "wool", "leather", "silk", "nylon", "fleece", "linen"],
    colors=["black", "white", "grey", "navy", "blue", "brown", "khaki", "olive", "red", "pink"],
    color_modifiers=["", "dark", "light", "faded", "washed", "bright", "muted"],
    fits=["slim", "regular", "relaxed", "oversized", "fitted", "skinny", "loose"],
    styles=["casual", "formal", "sporty", "business", "streetwear", "vintage", "minimalist"],
    condition_looks=["new", "clean", "worn", "vintage", "distressed", "faded"],
    details_by_type={
        "shirt": ["button-down collar", "chest pocket", "rolled sleeves", "printed logo"],
        "t-shirt": ["crew neck", "v-neck", "graphic print", "plain"],
        "jeans": ["belt loops", "five pockets", "distressed knees", "raw hem"],
        "pants": ["pleated front", "zip fly", "side pockets", "cuffed hem"],
        "jacket": ["zip front", "snap buttons", "hood", "lined interior"],
        "hoodie": ["kangaroo pocket", "drawstring hood", "ribbed cuffs"],
        "shoes": ["rubber soles", "lace-up", "velcro straps", "cushioned insole"],
        "sneakers": ["rubber soles", "mesh panels", "brand logo", "cushioned sole"],
        "boots": ["lug sole", "zip side", "leather upper", "steel toe"],
        "dress": ["A-line cut", "fitted waist", "midi length", "sleeveless"],
        "skirt": ["pleated", "pencil cut", "A-line", "midi length"],
        "coat": ["double-breasted", "wool blend", "belt tie", "lined"],
        "socks": ["ankle length", "crew length", "cushioned sole", "athletic"],
        "underwear": ["cotton blend", "elastic waistband"],
    },
)

URBAN_FANTASY_PALETTE = ClothingPalette(
    materials=["cotton", "leather", "denim", "silk", "wool", "synthetic", "enchanted fabric"],
    colors=["black", "grey", "purple", "crimson", "silver", "midnight blue", "forest green", "white"],
    color_modifiers=["", "dark", "faded", "iridescent", "metallic", "deep"],
    fits=["fitted", "flowing", "layered", "slim", "dramatic"],
    styles=["gothic", "modern", "arcane", "punk", "elegant", "mysterious", "tactical"],
    condition_looks=["pristine", "worn", "weathered", "battle-worn", "enchanted shimmer"],
    details_by_type={
        "jacket": ["silver studs", "hidden pockets", "rune stitching", "asymmetric zip"],
        "coat": ["high collar", "sweeping hem", "concealed weapon loops", "mystic lining"],
        "boots": ["silver buckles", "reinforced toe", "silent soles", "ankle holster"],
        "shirt": ["mandarin collar", "hidden buttons", "arcane embroidery"],
        "pants": ["cargo pockets", "reinforced knees", "tactical straps"],
        "gloves": ["fingerless", "rune-etched", "leather palms", "touch-screen tips"],
        "dress": ["asymmetric hem", "corset back", "hidden pockets", "slit skirt"],
        "cloak": ["deep hood", "silver clasp", "shadow-woven", "enchanted hem"],
    },
)

SCIFI_PALETTE = ClothingPalette(
    materials=["synth-fiber", "nano-weave", "smart-fabric", "carbon-mesh", "bio-polymer", "metallic weave"],
    colors=["white", "grey", "black", "silver", "blue", "cyan", "orange", "neon green"],
    color_modifiers=["", "metallic", "matte", "holographic", "illuminated", "reactive"],
    fits=["form-fitting", "utilitarian", "sleek", "bulky", "articulated"],
    styles=["minimalist", "tactical", "corporate", "utilitarian", "high-tech", "military"],
    condition_looks=["factory-new", "standard", "scuffed", "battle-damaged", "modified"],
    details_by_type={
        "jumpsuit": ["magnetic seals", "integrated display", "utility pockets", "ventilation panels"],
        "jacket": ["integrated heating", "smart pockets", "reflective strips", "armor inserts"],
        "boots": ["magnetic soles", "shock absorbers", "sealed seams", "power assist"],
        "gloves": ["haptic feedback", "grip enhancement", "data ports", "thermal regulation"],
        "suit": ["life support ready", "radiation shielding", "comm integration"],
        "helmet": ["HUD visor", "air filtration", "comm system", "light amplification"],
        "pants": ["cargo pockets", "knee padding", "tool loops", "sealed cuffs"],
        "shirt": ["moisture-wicking", "temperature regulation", "ID chip pocket"],
    },
)

# Map setting names to palettes
SETTING_PALETTES: dict[str, ClothingPalette] = {
    "fantasy": FANTASY_PALETTE,
    "contemporary": CONTEMPORARY_PALETTE,
    "urban_fantasy": URBAN_FANTASY_PALETTE,
    "scifi": SCIFI_PALETTE,
}


class ClothingVisualGenerator:
    """Generates randomized visual properties for clothing items.

    Uses setting-specific palettes to generate thematically appropriate
    visual descriptions for items.
    """

    def __init__(self, palette: ClothingPalette | None = None, setting_name: str = "fantasy"):
        """Initialize the generator with a palette.

        Args:
            palette: Custom palette to use. If None, uses setting_name to look up.
            setting_name: Setting name for default palette lookup.
        """
        if palette:
            self.palette = palette
        else:
            self.palette = SETTING_PALETTES.get(setting_name, FANTASY_PALETTE)

    def generate_visual_properties(
        self,
        item_type: str,
        quality: str = "common",
        item_key: str = "",
        display_name: str = "",
    ) -> dict[str, Any]:
        """Generate visual properties for an item.

        Args:
            item_type: Type of item (e.g., "tunic", "boots", "sword").
            quality: Quality tier affecting style/condition (common, fine, exceptional).
            item_key: Item key for additional context.
            display_name: Item's display name for inferring material/color.

        Returns:
            Dict with visual properties for storage in item.properties["visual"].
        """
        # Determine condition based on quality
        condition_weights = self._get_condition_weights(quality)

        # Generate color with optional modifier
        # Avoid awkward combinations like "dark white" or "light black"
        base_color = random.choice(self.palette.colors)
        incompatible_modifiers = {
            "white": ["dark", "light"],
            "black": ["dark", "light"],
            "cream": ["dark"],
            "beige": ["dark"],
        }
        excluded = incompatible_modifiers.get(base_color, [])
        valid_modifiers = [m for m in self.palette.color_modifiers if m not in excluded]
        color_modifier = random.choice(valid_modifiers) if valid_modifiers else ""
        primary_color = f"{color_modifier} {base_color}".strip() if color_modifier else base_color

        # Optional secondary color (30% chance)
        secondary_color = None
        if random.random() < 0.3:
            secondary_color = random.choice(
                [c for c in self.palette.colors if c != base_color]
            ) if len(self.palette.colors) > 1 else None

        # Infer material from display_name if possible, otherwise randomize
        material = self._infer_material(display_name or item_type)
        fit = random.choice(self.palette.fits)
        style = self._get_style_for_quality(quality)
        condition_look = random.choices(
            self.palette.condition_looks,
            weights=condition_weights,
            k=1
        )[0]

        # Get item-specific details
        details = self._get_details_for_type(item_type)

        visual = {
            "primary_color": primary_color,
            "material": material,
            "fit": fit,
            "style": style,
            "condition_look": condition_look,
        }

        if secondary_color:
            visual["secondary_color"] = secondary_color

        if details:
            visual["details"] = details

        return visual

    def _infer_material(self, text: str) -> str:
        """Infer material from item name/type if possible.

        Args:
            text: Item display_name or item_type to analyze.

        Returns:
            Inferred material if found, otherwise random from palette.
        """
        text_lower = text.lower()

        # Material keywords to detect - order matters (more specific first)
        material_keywords = [
            ("leather", "leather"),
            ("wool", "wool"),
            ("woolen", "wool"),
            ("cotton", "cotton"),
            ("silk", "silk"),
            ("silken", "silk"),
            ("linen", "linen"),
            ("velvet", "velvet"),
            ("fur", "fur"),
            ("canvas", "canvas"),
            ("cloth", "cotton"),  # Generic cloth → cotton
            ("denim", "denim"),
            ("polyester", "polyester"),
            ("nylon", "nylon"),
            ("fleece", "fleece"),
            ("synth", "synth-fiber"),
            ("nano", "nano-weave"),
            ("carbon", "carbon-mesh"),
        ]

        for keyword, material in material_keywords:
            if keyword in text_lower:
                # Only use if material exists in palette
                if material in self.palette.materials:
                    return material

        # No inference possible, randomize
        return random.choice(self.palette.materials)

    def _get_condition_weights(self, quality: str) -> list[float]:
        """Get weighted probabilities for condition_look based on quality.

        Args:
            quality: Quality tier (common, fine, exceptional).

        Returns:
            List of weights matching palette.condition_looks order.
        """
        n_conditions = len(self.palette.condition_looks)

        if quality == "exceptional":
            # Heavily favor pristine/clean conditions
            weights = [5.0, 3.0] + [0.5] * (n_conditions - 2)
        elif quality == "fine":
            # Favor clean conditions
            weights = [3.0, 4.0, 2.0] + [0.5] * (n_conditions - 3)
        else:  # common
            # More even distribution, slightly favoring middle conditions
            weights = [1.0, 2.0, 3.0, 2.0] + [1.0] * (n_conditions - 4)

        # Ensure we have enough weights
        while len(weights) < n_conditions:
            weights.append(1.0)

        return weights[:n_conditions]

    def _get_style_for_quality(self, quality: str) -> str:
        """Get appropriate style based on quality.

        Args:
            quality: Quality tier.

        Returns:
            Style string from palette.
        """
        styles = self.palette.styles

        if quality == "exceptional":
            # Prefer elegant/ornate styles
            preferred = [s for s in styles if s in ("elegant", "ornate", "noble", "formal", "high-tech")]
            if preferred:
                return random.choice(preferred)
        elif quality == "common":
            # Prefer practical/simple styles
            preferred = [s for s in styles if s in ("simple", "practical", "peasant", "casual", "utilitarian")]
            if preferred:
                return random.choice(preferred)

        return random.choice(styles)

    def _get_details_for_type(self, item_type: str) -> list[str]:
        """Get item-specific details.

        Args:
            item_type: Type of item.

        Returns:
            List of 1-2 detail strings, or empty list.
        """
        # Normalize item type (remove prefixes like "simple_", "cloth_")
        normalized = item_type.lower()
        for prefix in ["simple_", "cloth_", "leather_", "wool_", "silk_"]:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]

        # Check for matching details
        details_list = self.palette.details_by_type.get(normalized, [])

        if not details_list:
            # Try partial matches
            for key, details in self.palette.details_by_type.items():
                if key in normalized or normalized in key:
                    details_list = details
                    break

        if not details_list:
            return []

        # Pick 1-2 random details
        n_details = min(random.randint(1, 2), len(details_list))
        return random.sample(details_list, n_details)


def format_visual_description(visual: dict[str, Any], display_name: str) -> str:
    """Format visual properties into a human-readable description.

    Args:
        visual: Visual properties dict from item.properties["visual"].
        display_name: Item's display name for fallback.

    Returns:
        Formatted description string for portrait prompts.
    """
    if not visual:
        return display_name

    # If there's a free-text description override, use it
    if visual.get("description"):
        return visual["description"]

    # Build description from structured fields
    parts = []

    # Color + material + item type
    color = visual.get("primary_color", "")
    material = visual.get("material", "")
    condition = visual.get("condition_look", "")

    # Start with condition if notable
    if condition and condition not in ("clean", "standard", "new"):
        parts.append(condition)

    # Color
    if color:
        parts.append(color)

    # Material
    if material:
        parts.append(material)

    # Base item name (simplified)
    base_name = display_name.lower()
    for prefix in ["simple ", "cloth ", "leather ", "basic "]:
        if base_name.startswith(prefix):
            base_name = base_name[len(prefix):]
    parts.append(base_name)

    # Details
    details = visual.get("details", [])
    if details:
        parts.append(f"with {', '.join(details)}")

    return " ".join(parts)
