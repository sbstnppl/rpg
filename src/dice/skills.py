"""Skill-to-attribute mappings for skill checks.

Maps skill keys to their governing attributes. Unknown skills
default to Intelligence as a general learning/knowledge attribute.
"""

# Default skill-to-attribute mappings
# Keys are lowercase skill_key values, values are attribute keys
DEFAULT_SKILL_ATTRIBUTES: dict[str, str] = {
    # Strength-based skills
    "athletics": "strength",
    "climbing": "strength",
    "swimming": "strength",
    "lifting": "strength",
    "grappling": "strength",
    # Dexterity-based skills
    "acrobatics": "dexterity",
    "stealth": "dexterity",
    "sleight_of_hand": "dexterity",
    "lockpicking": "dexterity",
    "pickpocket": "dexterity",
    "archery": "dexterity",
    "throwing": "dexterity",
    "balance": "dexterity",
    "escape_artist": "dexterity",
    # Constitution-based skills
    "endurance": "constitution",
    "concentration": "constitution",
    "holding_breath": "constitution",
    # Intelligence-based skills
    "arcana": "intelligence",
    "history": "intelligence",
    "investigation": "intelligence",
    "nature": "intelligence",
    "religion": "intelligence",
    "alchemy": "intelligence",
    "herbalism": "intelligence",
    "medicine": "intelligence",
    "engineering": "intelligence",
    "linguistics": "intelligence",
    "cartography": "intelligence",
    "appraisal": "intelligence",
    # Wisdom-based skills
    "animal_handling": "wisdom",
    "insight": "wisdom",
    "perception": "wisdom",
    "survival": "wisdom",
    "tracking": "wisdom",
    "navigation": "wisdom",
    "foraging": "wisdom",
    "fishing": "wisdom",
    "farming": "wisdom",
    # Charisma-based skills
    "deception": "charisma",
    "intimidation": "charisma",
    "performance": "charisma",
    "persuasion": "charisma",
    "seduction": "charisma",
    "diplomacy": "charisma",
    "leadership": "charisma",
    "bargaining": "charisma",
    "acting": "charisma",
    "singing": "charisma",
    # Craft skills (typically Dexterity or Intelligence)
    "blacksmithing": "strength",
    "woodworking": "dexterity",
    "carpentry": "dexterity",
    "leatherworking": "dexterity",
    "tailoring": "dexterity",
    "cooking": "wisdom",
    "brewing": "intelligence",
    "pottery": "dexterity",
    "jewelry": "dexterity",
    "painting": "dexterity",
    "sculpting": "dexterity",
    # Combat skills (typically governed by weapon type)
    "swordfighting": "strength",
    "fencing": "dexterity",
    "wrestling": "strength",
    "boxing": "strength",
    "martial_arts": "dexterity",
    "shield_use": "strength",
    "parrying": "dexterity",
}

# Default attribute when skill is not in mapping
DEFAULT_ATTRIBUTE = "intelligence"


def get_attribute_for_skill(skill_key: str) -> str:
    """Get the governing attribute for a skill.

    Looks up the skill in the default mappings. If not found,
    returns Intelligence as the default (representing general
    knowledge and learning ability).

    Args:
        skill_key: The skill key (e.g., "stealth", "persuasion").

    Returns:
        The attribute key (e.g., "dexterity", "charisma").

    Examples:
        >>> get_attribute_for_skill("stealth")
        'dexterity'
        >>> get_attribute_for_skill("persuasion")
        'charisma'
        >>> get_attribute_for_skill("unknown_skill")
        'intelligence'
    """
    # Normalize: lowercase and replace spaces/hyphens with underscores
    normalized = skill_key.lower().replace(" ", "_").replace("-", "_")
    return DEFAULT_SKILL_ATTRIBUTES.get(normalized, DEFAULT_ATTRIBUTE)


def get_skills_for_attribute(attribute_key: str) -> list[str]:
    """Get all skills governed by a specific attribute.

    Args:
        attribute_key: The attribute key (e.g., "dexterity").

    Returns:
        List of skill keys governed by that attribute.

    Examples:
        >>> skills = get_skills_for_attribute("charisma")
        >>> "persuasion" in skills
        True
    """
    normalized = attribute_key.lower()
    return [
        skill
        for skill, attr in DEFAULT_SKILL_ATTRIBUTES.items()
        if attr == normalized
    ]
