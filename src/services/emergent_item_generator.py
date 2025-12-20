"""Emergent Item Generator Service.

This service creates items with emergent properties - quality, condition,
value, and narrative hooks are generated based on context rather than
being fully prescribed by the GM.

Philosophy: Items have stories
- Every item can have history, previous owners, quirks
- Quality and condition emerge from context
- Items trigger needs (food triggers hunger, comfortable items trigger comfort)
"""

from __future__ import annotations

import logging
import random
import uuid
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database.models.enums import ItemCondition, ItemType
from src.database.models.items import Item
from src.database.models.session import GameSession

logger = logging.getLogger(__name__)


# =============================================================================
# Item Generation Schemas
# =============================================================================


class ItemFullState(BaseModel):
    """Complete item state returned by create_item tool."""

    item_key: str = Field(description="Unique identifier")
    display_name: str = Field(description="Display name")
    item_type: str = Field(description="Type: weapon, clothing, food, misc, etc.")
    description: str = Field(description="Detailed description")

    # Physical properties
    condition: str = Field(description="Condition: pristine, good, worn, damaged, broken")
    quality: str = Field(description="Quality: poor, common, good, fine, exceptional")

    # Value
    estimated_value: int = Field(
        ge=0,
        description="Estimated value in copper coins"
    )
    value_description: str = Field(
        description="Narrative value description, e.g. 'worth a few silvers'"
    )

    # History/provenance (emergent)
    age_description: str | None = Field(
        default=None,
        description="How old the item appears, e.g. 'well-worn', 'freshly made'"
    )
    provenance: str | None = Field(
        default=None,
        description="Hint at item's history, e.g. 'initials carved inside'"
    )

    # Special properties
    properties: dict[str, Any] = Field(
        default_factory=dict,
        description="Special properties (damage for weapons, nutrition for food, etc.)"
    )

    # Need triggers (what needs this item might satisfy or trigger)
    need_triggers: list[str] = Field(
        default_factory=list,
        description="Needs this item could trigger: hunger, thirst, comfort, etc."
    )

    # Narrative hooks
    narrative_hooks: list[str] = Field(
        default_factory=list,
        description="Story hooks: 'has strange markings', 'smells faintly of roses'"
    )


class ItemConstraints(BaseModel):
    """Optional constraints for item generation."""

    name: str | None = Field(default=None, description="Specific name")
    quality: str | None = Field(
        default=None,
        description="Force specific quality: poor, common, good, fine, exceptional"
    )
    condition: str | None = Field(
        default=None,
        description="Force specific condition: pristine, good, worn, damaged, broken"
    )
    value_range: tuple[int, int] | None = Field(
        default=None,
        description="Force value in copper range (min, max)"
    )
    has_history: bool | None = Field(
        default=None,
        description="Force item to have/not have backstory"
    )


# =============================================================================
# Item Data Pools
# =============================================================================

# Item type templates with base properties
ITEM_TEMPLATES: dict[str, dict[str, Any]] = {
    "weapon": {
        "subtypes": {
            "sword": {"damage": "1d8", "base_value": 1000, "weight": "medium"},
            "dagger": {"damage": "1d4", "base_value": 200, "weight": "light"},
            "axe": {"damage": "1d10", "base_value": 1200, "weight": "heavy"},
            "bow": {"damage": "1d6", "base_value": 800, "requires": "arrows"},
            "staff": {"damage": "1d6", "base_value": 100, "weight": "medium"},
            "club": {"damage": "1d4", "base_value": 10, "weight": "medium"},
            "spear": {"damage": "1d6", "base_value": 100, "weight": "medium", "reach": True},
        },
        "need_triggers": [],
    },
    "armor": {
        "subtypes": {
            "leather_armor": {"ac_bonus": 1, "base_value": 500},
            "chainmail": {"ac_bonus": 3, "base_value": 2000},
            "plate_armor": {"ac_bonus": 5, "base_value": 5000},
            "shield": {"ac_bonus": 1, "base_value": 300},
            "helmet": {"ac_bonus": 1, "base_value": 200},
        },
        "need_triggers": ["comfort"],
    },
    "clothing": {
        "subtypes": {
            "shirt": {"base_value": 50, "slot": "torso"},
            "pants": {"base_value": 50, "slot": "legs"},
            "dress": {"base_value": 100, "slot": "torso"},
            "cloak": {"base_value": 150, "slot": "back"},
            "boots": {"base_value": 100, "slot": "feet"},
            "hat": {"base_value": 30, "slot": "head"},
            "gloves": {"base_value": 25, "slot": "hands"},
        },
        "need_triggers": ["comfort"],
    },
    "food": {
        "subtypes": {
            "bread": {"nutrition": 20, "base_value": 5, "perishable": True},
            "meat": {"nutrition": 40, "base_value": 20, "perishable": True},
            "fruit": {"nutrition": 15, "base_value": 10, "perishable": True},
            "cheese": {"nutrition": 25, "base_value": 15, "perishable": True},
            "rations": {"nutrition": 30, "base_value": 25, "perishable": False},
            "cake": {"nutrition": 15, "base_value": 30, "morale_bonus": 5},
            "stew": {"nutrition": 35, "base_value": 15, "perishable": True},
        },
        "need_triggers": ["hunger"],
    },
    "drink": {
        "subtypes": {
            "water": {"hydration": 30, "base_value": 1},
            "ale": {"hydration": 20, "base_value": 5, "alcohol": True},
            "wine": {"hydration": 15, "base_value": 50, "alcohol": True},
            "milk": {"hydration": 25, "base_value": 5},
            "tea": {"hydration": 25, "base_value": 10, "morale_bonus": 2},
            "potion": {"hydration": 10, "base_value": 100, "magical": True},
        },
        "need_triggers": ["thirst"],
    },
    "tool": {
        "subtypes": {
            "hammer": {"base_value": 50, "skill": "smithing"},
            "pickaxe": {"base_value": 100, "skill": "mining"},
            "rope": {"base_value": 25, "length": 50},
            "lantern": {"base_value": 75, "fuel_hours": 6},
            "lockpicks": {"base_value": 150, "skill": "lockpicking"},
            "compass": {"base_value": 200, "skill": "navigation"},
        },
        "need_triggers": [],
    },
    "container": {
        "subtypes": {
            "backpack": {"capacity": 20, "base_value": 100},
            "pouch": {"capacity": 5, "base_value": 25},
            "chest": {"capacity": 50, "base_value": 200, "lockable": True},
            "bottle": {"capacity": 1, "base_value": 5, "for_liquids": True},
            "sack": {"capacity": 15, "base_value": 10},
        },
        "need_triggers": [],
    },
    "misc": {
        "subtypes": {
            "book": {"base_value": 50, "readable": True},
            "candle": {"base_value": 1, "burn_hours": 4},
            "mirror": {"base_value": 100},
            "jewelry": {"base_value": 200},
            "coin_purse": {"base_value": 10},
            "key": {"base_value": 5},
        },
        "need_triggers": [],
    },
}

# Quality affects value and properties
QUALITY_MULTIPLIERS = {
    "poor": 0.5,
    "common": 1.0,
    "good": 1.5,
    "fine": 2.5,
    "exceptional": 5.0,
}

QUALITY_DESCRIPTIONS = {
    "poor": ["crude", "roughly made", "barely functional", "cheap"],
    "common": ["ordinary", "standard", "unremarkable", "serviceable"],
    "good": ["well-made", "quality", "solid", "reliable"],
    "fine": ["expertly crafted", "elegant", "superior", "masterwork"],
    "exceptional": ["exquisite", "legendary", "peerless", "magnificent"],
}

# Condition affects value and appearance
CONDITION_MULTIPLIERS = {
    "pristine": 1.0,
    "good": 0.9,
    "worn": 0.7,
    "damaged": 0.4,
    "broken": 0.1,
}

CONDITION_TO_ENUM = {
    "pristine": ItemCondition.GOOD,  # Pristine maps to GOOD (best we have)
    "good": ItemCondition.GOOD,
    "worn": ItemCondition.WORN,
    "damaged": ItemCondition.DAMAGED,
    "broken": ItemCondition.BROKEN,
}

# Provenance options (hints at item history)
PROVENANCE_OPTIONS = [
    "has initials carved inside",
    "bears a faded maker's mark",
    "shows signs of careful maintenance",
    "has a small repair visible",
    "worn smooth from years of use",
    "still has the original price tag",
    "smells faintly of perfume",
    "has an unusual patina",
    "contains a hidden compartment",
    "once belonged to someone important",
    "was clearly well-loved",
    "shows battle scars",
    "has been recently polished",
    "carries a faint magical aura",
    None,  # No special provenance
    None,
    None,  # Weighted toward no provenance
]

# Narrative hooks (things that make items interesting)
NARRATIVE_HOOKS = [
    "has strange markings on it",
    "feels slightly warm to the touch",
    "makes a faint humming sound",
    "seems heavier than it should be",
    "catches the light oddly",
    "has a small gemstone embedded",
    "bears a family crest",
    "has writing in an unknown language",
    "smells of old smoke",
    "is wrapped in fine silk",
]

# Value descriptions
def value_to_description(copper: int) -> str:
    """Convert copper value to narrative description."""
    if copper < 10:
        return "nearly worthless"
    elif copper < 50:
        return "worth a few coppers"
    elif copper < 100:
        return "worth several coppers"
    elif copper < 500:
        return "worth a handful of silver"
    elif copper < 1000:
        return "worth several silver coins"
    elif copper < 5000:
        return "worth a gold piece or two"
    elif copper < 10000:
        return "worth several gold pieces"
    elif copper < 50000:
        return "quite valuable"
    else:
        return "extremely valuable"


# =============================================================================
# Emergent Item Generator
# =============================================================================


class EmergentItemGenerator:
    """Service for generating items with emergent properties."""

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
    ) -> None:
        """Initialize the emergent item generator.

        Args:
            db: Database session.
            game_session: Current game session.
        """
        self.db = db
        self.game_session = game_session
        self.session_id = game_session.id

    def create_item(
        self,
        item_type: str,
        context: str,
        location_key: str,
        owner_entity_id: int | None = None,
        constraints: ItemConstraints | None = None,
    ) -> ItemFullState:
        """Create a new item with emergent properties.

        Args:
            item_type: Type of item (weapon, food, clothing, etc.)
            context: Description of the item context, e.g. "hunting knife on display"
            location_key: Where the item is appearing
            owner_entity_id: Optional entity who owns this item
            constraints: Optional hard requirements

        Returns:
            ItemFullState with full item data and narrative hooks.
            The item is also persisted to the database.
        """
        # Parse context to extract subtype hints
        subtype = self._infer_subtype(item_type, context)

        # Get template data
        template = ITEM_TEMPLATES.get(item_type, ITEM_TEMPLATES["misc"])
        subtype_data = template.get("subtypes", {}).get(subtype, {})

        # Generate identity
        display_name = constraints.name if constraints and constraints.name else self._generate_name(item_type, subtype, context)
        item_key = self._generate_item_key(item_type, display_name)

        # Generate quality and condition (emergent)
        quality = self._generate_quality(constraints, context)
        condition = self._generate_condition(constraints, context)

        # Calculate value
        base_value = subtype_data.get("base_value", 50)
        estimated_value = int(
            base_value
            * QUALITY_MULTIPLIERS[quality]
            * CONDITION_MULTIPLIERS[condition]
        )
        if constraints and constraints.value_range:
            min_val, max_val = constraints.value_range
            estimated_value = max(min_val, min(max_val, estimated_value))

        # Generate description
        description = self._generate_description(
            item_type, subtype, quality, condition, context
        )

        # Generate properties from template
        properties = dict(subtype_data)
        properties.pop("base_value", None)

        # Get need triggers
        need_triggers = template.get("need_triggers", [])

        # Generate provenance and narrative hooks
        provenance = None
        narrative_hooks = []

        should_have_history = (
            constraints.has_history if constraints and constraints.has_history is not None
            else random.random() < 0.3  # 30% chance of having history
        )

        if should_have_history:
            provenance = random.choice([p for p in PROVENANCE_OPTIONS if p is not None])
            if random.random() < 0.2:  # 20% chance of narrative hook
                narrative_hooks.append(random.choice(NARRATIVE_HOOKS))

        # Generate age description
        age_description = self._generate_age_description(condition, quality)

        # Build full state
        item_state = ItemFullState(
            item_key=item_key,
            display_name=display_name,
            item_type=item_type,
            description=description,
            condition=condition,
            quality=quality,
            estimated_value=estimated_value,
            value_description=value_to_description(estimated_value),
            age_description=age_description,
            provenance=provenance,
            properties=properties,
            need_triggers=need_triggers,
            narrative_hooks=narrative_hooks,
        )

        # Persist to database
        self._persist_item(item_state, owner_entity_id, location_key)

        return item_state

    def _infer_subtype(self, item_type: str, context: str) -> str:
        """Infer specific subtype from context."""
        context_lower = context.lower()

        template = ITEM_TEMPLATES.get(item_type, {})
        subtypes = template.get("subtypes", {})

        # Check if context mentions a specific subtype
        for subtype in subtypes:
            if subtype.replace("_", " ") in context_lower:
                return subtype

        # Default to first subtype or generic
        if subtypes:
            return list(subtypes.keys())[0]
        return "generic"

    def _generate_name(self, item_type: str, subtype: str, context: str) -> str:
        """Generate display name for item."""
        # Use subtype as base name
        base_name = subtype.replace("_", " ").title()

        # Add descriptors based on context
        context_lower = context.lower()

        adjectives = []
        if "old" in context_lower or "ancient" in context_lower:
            adjectives.append("Old")
        elif "new" in context_lower or "fresh" in context_lower:
            adjectives.append("Fresh")

        if "fine" in context_lower or "quality" in context_lower:
            adjectives.append("Fine")
        elif "rusty" in context_lower or "worn" in context_lower:
            adjectives.append("Worn")

        if adjectives:
            return f"{' '.join(adjectives)} {base_name}"
        return base_name

    def _generate_item_key(self, item_type: str, display_name: str) -> str:
        """Generate unique item key."""
        name_clean = display_name.lower().replace(" ", "_")[:20]
        unique_id = uuid.uuid4().hex[:6]
        return f"{item_type}_{name_clean}_{unique_id}"

    def _generate_quality(self, constraints: ItemConstraints | None, context: str) -> str:
        """Generate item quality."""
        if constraints and constraints.quality:
            return constraints.quality

        context_lower = context.lower()

        # Infer from context
        if any(word in context_lower for word in ["fine", "exquisite", "masterwork", "legendary"]):
            return random.choice(["fine", "exceptional"])
        elif any(word in context_lower for word in ["quality", "well-made", "good"]):
            return random.choice(["good", "fine"])
        elif any(word in context_lower for word in ["cheap", "crude", "rough", "poor"]):
            return random.choice(["poor", "common"])

        # Random with common being most likely
        return random.choices(
            ["poor", "common", "good", "fine", "exceptional"],
            weights=[10, 50, 25, 10, 5],
            k=1
        )[0]

    def _generate_condition(self, constraints: ItemConstraints | None, context: str) -> str:
        """Generate item condition."""
        if constraints and constraints.condition:
            return constraints.condition

        context_lower = context.lower()

        # Infer from context
        if any(word in context_lower for word in ["new", "pristine", "fresh", "unused"]):
            return "pristine"
        elif any(word in context_lower for word in ["worn", "used", "old"]):
            return "worn"
        elif any(word in context_lower for word in ["damaged", "broken", "rusty"]):
            return random.choice(["damaged", "broken"])

        # Random with good being most common
        return random.choices(
            ["pristine", "good", "worn", "damaged", "broken"],
            weights=[10, 40, 30, 15, 5],
            k=1
        )[0]

    def _generate_description(
        self,
        item_type: str,
        subtype: str,
        quality: str,
        condition: str,
        context: str,
    ) -> str:
        """Generate item description."""
        quality_adj = random.choice(QUALITY_DESCRIPTIONS.get(quality, ["ordinary"]))

        condition_notes = {
            "pristine": "in perfect condition",
            "good": "well-maintained",
            "worn": "showing signs of use",
            "damaged": "noticeably damaged",
            "broken": "barely functional",
        }
        condition_desc = condition_notes.get(condition, "")

        base = subtype.replace("_", " ")

        return f"A {quality_adj} {base}, {condition_desc}."

    def _generate_age_description(self, condition: str, quality: str) -> str:
        """Generate age description based on condition."""
        if condition == "pristine":
            return random.choice(["freshly made", "brand new", "recently crafted"])
        elif condition == "worn":
            return random.choice(["well-used", "seasoned", "showing its age"])
        elif condition in ("damaged", "broken"):
            return random.choice(["ancient", "weathered", "battle-worn", "decrepit"])
        else:
            return random.choice(["of indeterminate age", "neither new nor old"])

    def _persist_item(
        self,
        item_state: ItemFullState,
        owner_entity_id: int | None,
        location_key: str,
    ) -> Item:
        """Persist item to database.

        If no owner_entity_id is provided, the item is treated as an environmental
        item owned by the location (e.g., a bucket at a well).
        """
        from src.database.models.world import Location

        # Map item type string to enum
        type_map = {
            "weapon": ItemType.WEAPON,
            "armor": ItemType.ARMOR,
            "clothing": ItemType.CLOTHING,
            "food": ItemType.CONSUMABLE,
            "drink": ItemType.CONSUMABLE,
            "tool": ItemType.MISC,
            "container": ItemType.CONTAINER,
            "misc": ItemType.MISC,
        }

        # Look up location ID for environmental items (no entity owner)
        owner_location_id = None
        storage_location_id = None
        if owner_entity_id is None and location_key:
            location = (
                self.db.query(Location)
                .filter(
                    Location.session_id == self.session_id,
                    Location.location_key == location_key,
                )
                .first()
            )
            if location:
                owner_location_id = location.id
                # Find or create a storage location at this world location
                storage_location_id = self._get_or_create_ground_storage(location)

        item = Item(
            session_id=self.session_id,
            item_key=item_state.item_key,
            display_name=item_state.display_name,
            description=item_state.description,
            item_type=type_map.get(item_state.item_type, ItemType.MISC),
            owner_id=owner_entity_id,
            holder_id=owner_entity_id,  # Initially holder = owner
            storage_location_id=storage_location_id,  # Physical placement
            owner_location_id=owner_location_id,  # Environmental items owned by location
            condition=CONDITION_TO_ENUM.get(item_state.condition, ItemCondition.GOOD),
            properties={
                **item_state.properties,
                "quality": item_state.quality,
                "estimated_value": item_state.estimated_value,
                "provenance": item_state.provenance,
                "narrative_hooks": item_state.narrative_hooks,
            },
        )
        self.db.add(item)
        self.db.flush()
        return item

    def _get_or_create_ground_storage(self, location: "Location") -> int:
        """Get or create a ground/surface storage location at a world location.

        Args:
            location: The world location to find/create storage at.

        Returns:
            Storage location ID.
        """
        from src.database.models.items import StorageLocation, StorageLocationType

        # Try to find an existing ground storage at this location
        storage_key = f"{location.location_key}_ground"
        existing = (
            self.db.query(StorageLocation)
            .filter(
                StorageLocation.session_id == self.session_id,
                StorageLocation.location_key == storage_key,
            )
            .first()
        )

        if existing:
            return existing.id

        # Create a new ground storage location (PLACE type for static world locations)
        storage = StorageLocation(
            session_id=self.session_id,
            location_key=storage_key,
            location_type=StorageLocationType.PLACE,
            world_location_id=location.id,
            is_temporary=False,
        )
        self.db.add(storage)
        self.db.flush()
        return storage.id

    def get_item_state(self, item_key: str) -> ItemFullState | None:
        """Get full state for an existing item."""
        item = (
            self.db.query(Item)
            .filter(
                Item.session_id == self.session_id,
                Item.item_key == item_key,
            )
            .first()
        )

        if item is None:
            return None

        properties = item.properties or {}

        # Map condition enum back to string
        condition_map = {
            ItemCondition.GOOD: "good",
            ItemCondition.WORN: "worn",
            ItemCondition.DAMAGED: "damaged",
            ItemCondition.BROKEN: "broken",
        }

        return ItemFullState(
            item_key=item.item_key,
            display_name=item.display_name,
            item_type=item.item_type.value,
            description=item.description or "",
            condition=condition_map.get(item.condition, "good"),
            quality=properties.get("quality", "common"),
            estimated_value=properties.get("estimated_value", 0),
            value_description=value_to_description(properties.get("estimated_value", 0)),
            age_description=None,
            provenance=properties.get("provenance"),
            properties={k: v for k, v in properties.items()
                       if k not in ("quality", "estimated_value", "provenance", "narrative_hooks")},
            need_triggers=[],
            narrative_hooks=properties.get("narrative_hooks", []),
        )
