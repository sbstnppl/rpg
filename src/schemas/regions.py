"""Region definitions with cultural traits for NPC generation.

This module defines regions with associated cultural traits used to generate
realistic NPCs with appropriate appearance, accent, food preferences, etc.
"""

from dataclasses import dataclass, field


@dataclass
class RegionCulture:
    """Cultural traits associated with a geographic region.

    Used to generate NPCs with culturally appropriate characteristics
    based on their birthplace/origin.
    """

    # Skin color probabilities (must sum to ~1.0)
    skin_color_weights: dict[str, float]

    # Voice/accent characteristics
    accent_style: str

    # Culinary preferences
    common_foods: list[str]
    common_drinks: list[str]

    # Naming conventions (used for fallback name generation)
    naming_style: str

    # Optional: Default height variance (some populations are taller/shorter)
    height_modifier_cm: int = 0


# =============================================================================
# Contemporary Setting Regions
# =============================================================================

REGIONS_CONTEMPORARY: dict[str, RegionCulture] = {
    "Northern Europe": RegionCulture(
        skin_color_weights={
            "fair": 0.35,
            "pale": 0.25,
            "light": 0.25,
            "freckled fair": 0.10,
            "ruddy": 0.05,
        },
        accent_style="Nordic or British",
        common_foods=[
            "fish", "potatoes", "bread", "cheese", "pickled herring",
            "meatballs", "rye bread", "smoked salmon",
        ],
        common_drinks=["beer", "coffee", "aquavit", "tea", "milk"],
        naming_style="Germanic/Anglo-Saxon",
        height_modifier_cm=3,  # Scandinavians are taller on average
    ),
    "Mediterranean": RegionCulture(
        skin_color_weights={
            "olive": 0.30,
            "tan": 0.25,
            "light": 0.20,
            "brown": 0.15,
            "fair": 0.10,
        },
        accent_style="Italian, Greek, or Spanish",
        common_foods=[
            "pasta", "olive oil", "wine", "seafood", "cheese",
            "tomatoes", "bread", "lamb",
        ],
        common_drinks=["wine", "espresso", "ouzo", "grappa", "limoncello"],
        naming_style="Latin/Romance",
    ),
    "Sub-Saharan Africa": RegionCulture(
        skin_color_weights={
            "dark brown": 0.35,
            "dark": 0.30,
            "brown": 0.25,
            "tan": 0.10,
        },
        accent_style="West African, East African, or South African",
        common_foods=[
            "jollof rice", "fufu", "injera", "grilled meats",
            "plantains", "yams", "groundnut stew",
        ],
        common_drinks=["palm wine", "hibiscus tea", "coffee", "millet beer", "ginger beer"],
        naming_style="African regional",
    ),
    "East Asia": RegionCulture(
        skin_color_weights={
            "light": 0.40,
            "tan": 0.30,
            "pale": 0.20,
            "fair": 0.10,
        },
        accent_style="Chinese, Japanese, or Korean",
        common_foods=[
            "rice", "noodles", "dumplings", "tofu", "seafood",
            "soy sauce", "vegetables", "pork",
        ],
        common_drinks=["tea", "sake", "soju", "baijiu", "plum wine"],
        naming_style="East Asian",
        height_modifier_cm=-3,  # Generally shorter average height
    ),
    "South Asia": RegionCulture(
        skin_color_weights={
            "brown": 0.35,
            "tan": 0.25,
            "dark brown": 0.20,
            "light": 0.15,
            "dark": 0.05,
        },
        accent_style="Indian, Pakistani, or Bangladeshi",
        common_foods=[
            "curry", "rice", "naan", "dal", "biryani",
            "samosa", "paneer", "chutney",
        ],
        common_drinks=["chai", "lassi", "coconut water", "mango juice"],
        naming_style="South Asian",
    ),
    "North America": RegionCulture(
        skin_color_weights={
            "fair": 0.25,
            "light": 0.20,
            "tan": 0.15,
            "brown": 0.15,
            "dark brown": 0.10,
            "olive": 0.10,
            "dark": 0.05,
        },
        accent_style="American (various regional)",
        common_foods=[
            "burgers", "steak", "pizza", "tacos", "BBQ",
            "fried chicken", "hot dogs", "mac and cheese",
        ],
        common_drinks=["coffee", "soda", "beer", "bourbon", "iced tea"],
        naming_style="Mixed Anglo/Hispanic",
    ),
    "Latin America": RegionCulture(
        skin_color_weights={
            "tan": 0.25,
            "brown": 0.25,
            "olive": 0.20,
            "light": 0.15,
            "dark brown": 0.10,
            "fair": 0.05,
        },
        accent_style="Spanish or Portuguese (Latin American)",
        common_foods=[
            "tacos", "rice and beans", "empanadas", "ceviche",
            "arepas", "tamales", "feijoada",
        ],
        common_drinks=["tequila", "rum", "coffee", "mate", "horchata"],
        naming_style="Hispanic/Portuguese",
    ),
    "Middle East": RegionCulture(
        skin_color_weights={
            "olive": 0.30,
            "tan": 0.25,
            "light": 0.20,
            "brown": 0.15,
            "fair": 0.10,
        },
        accent_style="Arabic, Persian, or Turkish",
        common_foods=[
            "hummus", "kebab", "falafel", "pita bread", "rice",
            "lamb", "dates", "baklava",
        ],
        common_drinks=["tea", "coffee", "ayran", "pomegranate juice"],
        naming_style="Arabic/Persian",
    ),
    "Southeast Asia": RegionCulture(
        skin_color_weights={
            "tan": 0.35,
            "brown": 0.30,
            "light": 0.20,
            "dark brown": 0.10,
            "olive": 0.05,
        },
        accent_style="Vietnamese, Thai, or Filipino",
        common_foods=[
            "pho", "pad thai", "rice", "seafood", "curry",
            "spring rolls", "satay", "noodles",
        ],
        common_drinks=["tea", "coconut water", "rice wine", "coffee", "fruit smoothies"],
        naming_style="Southeast Asian",
    ),
}


# =============================================================================
# Fantasy Setting Regions
# =============================================================================

REGIONS_FANTASY: dict[str, RegionCulture] = {
    "Northern Kingdoms": RegionCulture(
        skin_color_weights={
            "fair": 0.35,
            "pale": 0.30,
            "light": 0.20,
            "ruddy": 0.10,
            "freckled fair": 0.05,
        },
        accent_style="Nordic or Germanic",
        common_foods=[
            "mead hall fare", "roast meat", "bread", "cheese",
            "fish", "root vegetables", "porridge",
        ],
        common_drinks=["mead", "ale", "mulled wine", "cider"],
        naming_style="Nordic/Germanic",
        height_modifier_cm=2,
    ),
    "Elven Lands": RegionCulture(
        skin_color_weights={
            "fair": 0.40,
            "pale": 0.35,
            "light": 0.15,
            "bronze": 0.05,
            "olive": 0.05,
        },
        accent_style="Elvish (melodic and flowing)",
        common_foods=[
            "lembas", "forest fruits", "honey cakes", "wine",
            "nuts", "herbs", "light salads",
        ],
        common_drinks=["elven wine", "spring water", "herbal tea", "nectar"],
        naming_style="Elvish",
        height_modifier_cm=5,
    ),
    "Dwarven Mountains": RegionCulture(
        skin_color_weights={
            "ruddy": 0.35,
            "tan": 0.25,
            "fair": 0.20,
            "weathered": 0.15,
            "light": 0.05,
        },
        accent_style="Dwarven (gruff and guttural)",
        common_foods=[
            "roast boar", "mushroom stew", "stone bread", "cheese",
            "pickled vegetables", "smoked meats",
        ],
        common_drinks=["dwarven ale", "stout", "mineral water", "whiskey"],
        naming_style="Dwarven",
        height_modifier_cm=-20,  # Dwarves are short
    ),
    "Southern Deserts": RegionCulture(
        skin_color_weights={
            "bronze": 0.30,
            "tan": 0.25,
            "dark brown": 0.20,
            "olive": 0.15,
            "brown": 0.10,
        },
        accent_style="Desert nomad (flowing and rhythmic)",
        common_foods=[
            "dates", "flatbread", "spiced lamb", "couscous",
            "dried fruits", "honey pastries",
        ],
        common_drinks=["mint tea", "coffee", "fruit juices", "camel milk"],
        naming_style="Desert/Arabic-style",
    ),
    "Eastern Empire": RegionCulture(
        skin_color_weights={
            "olive": 0.30,
            "tan": 0.25,
            "light": 0.25,
            "bronze": 0.15,
            "fair": 0.05,
        },
        accent_style="Eastern (formal and precise)",
        common_foods=[
            "rice", "dumplings", "tea", "noodles", "fish",
            "vegetables", "tofu", "sweet cakes",
        ],
        common_drinks=["tea", "rice wine", "plum wine", "herbal infusions"],
        naming_style="Eastern/Asian-style",
    ),
    "Jungle Tribes": RegionCulture(
        skin_color_weights={
            "dark brown": 0.35,
            "brown": 0.30,
            "dark": 0.20,
            "bronze": 0.10,
            "tan": 0.05,
        },
        accent_style="Tribal (rhythmic and musical)",
        common_foods=[
            "tropical fruits", "roast game", "cassava", "fish",
            "coconut", "spiced stews", "plantains",
        ],
        common_drinks=["fruit juices", "coconut milk", "fermented drinks", "herbal brews"],
        naming_style="Tribal/Nature-based",
    ),
    "Central Plains": RegionCulture(
        skin_color_weights={
            "tan": 0.30,
            "light": 0.25,
            "fair": 0.20,
            "olive": 0.15,
            "brown": 0.10,
        },
        accent_style="Common tongue (neutral)",
        common_foods=[
            "bread", "cheese", "ale", "roast chicken", "vegetables",
            "pies", "stews", "apples",
        ],
        common_drinks=["ale", "cider", "wine", "water", "milk"],
        naming_style="Common/Mixed",
    ),
}


# =============================================================================
# Sci-Fi Setting Regions
# =============================================================================

REGIONS_SCIFI: dict[str, RegionCulture] = {
    "Earth Standard": RegionCulture(
        skin_color_weights={
            "light": 0.20,
            "tan": 0.20,
            "brown": 0.20,
            "fair": 0.15,
            "olive": 0.10,
            "dark brown": 0.10,
            "dark": 0.05,
        },
        accent_style="Global English (various)",
        common_foods=[
            "synthesized proteins", "vertical farm produce", "cultured meat",
            "algae supplements", "traditional cuisines",
        ],
        common_drinks=["synth-coffee", "purified water", "energy drinks", "traditional beverages"],
        naming_style="Global/Mixed",
    ),
    "Martian Colonies": RegionCulture(
        skin_color_weights={
            "pale": 0.35,
            "light": 0.30,
            "fair": 0.20,
            "tan": 0.10,
            "ruddy": 0.05,
        },
        accent_style="Martian (clipped and efficient)",
        common_foods=[
            "hydroponic vegetables", "protein bars", "algae paste",
            "recycled nutrients", "dome-grown fruit",
        ],
        common_drinks=["recycled water", "nutrient shakes", "synth-tea", "dome wine"],
        naming_style="Corporate/Technical",
        height_modifier_cm=5,  # Lower gravity = taller
    ),
    "Outer Rim": RegionCulture(
        skin_color_weights={
            "tan": 0.25,
            "weathered": 0.20,
            "light": 0.20,
            "brown": 0.15,
            "dark brown": 0.10,
            "olive": 0.10,
        },
        accent_style="Spacer (drawling and informal)",
        common_foods=[
            "ration packs", "station food", "trader goods",
            "preserved meats", "ship-grown vegetables",
        ],
        common_drinks=["synth-whiskey", "station brew", "recycled water", "smuggled goods"],
        naming_style="Spacer/Frontier",
    ),
    "Cyborg Enclaves": RegionCulture(
        skin_color_weights={
            "pale": 0.30,
            "metallic": 0.25,
            "light": 0.20,
            "fair": 0.15,
            "luminescent": 0.10,
        },
        accent_style="Synthetic (precise and modulated)",
        common_foods=[
            "nutrient paste", "electrolyte solutions", "bio-fuel supplements",
            "organic matter", "processed proteins",
        ],
        common_drinks=["bio-coolant", "electrolyte mix", "neural stimulants", "purified water"],
        naming_style="Alphanumeric/Technical",
    ),
    "Alien Homeworlds": RegionCulture(
        skin_color_weights={
            "pale blue": 0.25,
            "green-tinged": 0.20,
            "grey": 0.15,
            "purple-hued": 0.15,
            "iridescent": 0.15,
            "dark": 0.10,
        },
        accent_style="Alien (varied and unusual)",
        common_foods=[
            "exotic proteins", "bioluminescent fungi", "crystal extracts",
            "alien vegetation", "synthesized nutrients",
        ],
        common_drinks=["alien beverages", "mineral solutions", "bio-luminescent drinks", "nectar"],
        naming_style="Alien/Exotic",
    ),
}


# =============================================================================
# Region Lookup by Setting
# =============================================================================

REGIONS_BY_SETTING: dict[str, dict[str, RegionCulture]] = {
    "fantasy": REGIONS_FANTASY,
    "medieval": REGIONS_FANTASY,
    "contemporary": REGIONS_CONTEMPORARY,
    "modern": REGIONS_CONTEMPORARY,
    "scifi": REGIONS_SCIFI,
    "sci-fi": REGIONS_SCIFI,
    "cyberpunk": REGIONS_SCIFI,
    "space": REGIONS_SCIFI,
}


def get_regions_for_setting(setting: str) -> dict[str, RegionCulture]:
    """Get region definitions for a setting type.

    Args:
        setting: Setting type (fantasy, contemporary, scifi, etc.)

    Returns:
        Dictionary of region name to RegionCulture
    """
    setting_lower = setting.lower()
    return REGIONS_BY_SETTING.get(setting_lower, REGIONS_CONTEMPORARY)


def get_default_region_for_setting(setting: str) -> str:
    """Get the default/most common region for a setting.

    Args:
        setting: Setting type

    Returns:
        Default region name
    """
    setting_lower = setting.lower()
    if setting_lower in ("fantasy", "medieval"):
        return "Central Plains"
    elif setting_lower in ("scifi", "sci-fi", "cyberpunk", "space"):
        return "Earth Standard"
    else:
        return "North America"
