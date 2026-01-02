"""ItemManager for item and inventory management."""

from collections import defaultdict

from sqlalchemy.orm import Session

from src.database.models.enums import ItemType, ItemCondition, StorageLocationType
from src.database.models.items import Item, StorageLocation
from src.database.models.session import GameSession
from src.managers.base import BaseManager


# Durability thresholds for condition changes
CONDITION_THRESHOLDS = {
    80: ItemCondition.GOOD,
    50: ItemCondition.WORN,
    25: ItemCondition.DAMAGED,
    0: ItemCondition.BROKEN,
}


# Body slot definitions with max layers and descriptions
BODY_SLOTS = {
    # Head/Face
    "head": {"max_layers": 2, "desc": "Hat, helmet"},
    "face": {"max_layers": 1, "desc": "Mask, glasses"},
    "ear_left": {"max_layers": 2, "desc": "Earring, earbud"},
    "ear_right": {"max_layers": 2, "desc": "Earring, earbud"},
    "neck": {"max_layers": 2, "desc": "Necklace, scarf"},
    # Body (keep existing names for backwards compat)
    "torso": {"max_layers": 4, "desc": "Underwear → shirt → vest → jacket"},
    "legs": {"max_layers": 3, "desc": "Underwear → pants → outer"},
    "full_body": {"max_layers": 1, "desc": "Jumpsuit, wetsuit", "covers": ["torso", "legs"]},
    "back": {"max_layers": 2, "desc": "Backpack, cape"},
    "waist": {"max_layers": 2, "desc": "Belt, sash"},
    # Arms/Hands
    "forearm_left": {"max_layers": 2, "desc": "Watch, bracelet"},
    "forearm_right": {"max_layers": 2, "desc": "Watch, bracelet"},
    "hand_left": {"max_layers": 2, "desc": "Glove, held item"},
    "hand_right": {"max_layers": 2, "desc": "Glove, held item"},
    "main_hand": {"max_layers": 1, "desc": "Primary weapon/tool"},
    "off_hand": {"max_layers": 1, "desc": "Shield, secondary"},
    # Individual finger slots (10 total)
    "thumb_left": {"max_layers": 1, "desc": "Ring"},
    "index_left": {"max_layers": 1, "desc": "Ring"},
    "middle_left": {"max_layers": 1, "desc": "Ring"},
    "ring_left": {"max_layers": 1, "desc": "Ring"},
    "pinky_left": {"max_layers": 1, "desc": "Ring"},
    "thumb_right": {"max_layers": 1, "desc": "Ring"},
    "index_right": {"max_layers": 1, "desc": "Ring"},
    "middle_right": {"max_layers": 1, "desc": "Ring"},
    "ring_right": {"max_layers": 1, "desc": "Ring"},
    "pinky_right": {"max_layers": 1, "desc": "Ring"},
    # Feet
    "feet_socks": {"max_layers": 1, "desc": "Socks, stockings"},
    "feet_shoes": {"max_layers": 1, "desc": "Shoes, boots"},
}

# Bonus slots provided dynamically by worn items
BONUS_SLOTS = {
    "pocket_left": {"max_layers": 1, "desc": "Left front pocket"},
    "pocket_right": {"max_layers": 1, "desc": "Right front pocket"},
    "back_pocket_left": {"max_layers": 1, "desc": "Left back pocket"},
    "back_pocket_right": {"max_layers": 1, "desc": "Right back pocket"},
    "belt_pouch_1": {"max_layers": 1, "desc": "Belt pouch slot 1"},
    "belt_pouch_2": {"max_layers": 1, "desc": "Belt pouch slot 2"},
    "belt_pouch_3": {"max_layers": 1, "desc": "Belt pouch slot 3"},
    "backpack_main": {"max_layers": 1, "desc": "Backpack main compartment"},
    "backpack_side": {"max_layers": 1, "desc": "Backpack side pocket"},
}

# Slots that cover (hide) other slots when worn
SLOT_COVERS = {
    "full_body": ["torso", "legs"],
}


class ItemManager(BaseManager):
    """Manager for item operations.

    Handles:
    - Item CRUD
    - Inventory queries
    - Item transfer (between entities/storage)
    - Equipment management (body slots, layers, visibility)
    - Condition tracking
    """

    def get_item(self, item_key: str) -> Item | None:
        """Get item by key.

        Args:
            item_key: Unique item key.

        Returns:
            Item if found, None otherwise.
        """
        return (
            self.db.query(Item)
            .filter(
                Item.session_id == self.session_id,
                Item.item_key == item_key,
            )
            .first()
        )

    def get_item_by_id(self, item_id: int) -> Item | None:
        """Get item by ID.

        Args:
            item_id: Item database ID.

        Returns:
            Item if found, None otherwise.
        """
        return (
            self.db.query(Item)
            .filter(
                Item.session_id == self.session_id,
                Item.id == item_id,
            )
            .first()
        )

    def get_item_property(
        self,
        item_key: str,
        property_name: str,
        default: any = None,
    ) -> any:
        """Get a property from item's properties JSON.

        Args:
            item_key: Item key.
            property_name: Property to get.
            default: Default value if property not found.

        Returns:
            Property value or default.
        """
        item = self.get_item(item_key)
        if item is None or item.properties is None:
            return default
        return item.properties.get(property_name, default)

    def update_item_property(
        self,
        item_key: str,
        property_name: str,
        value: any,
    ) -> Item:
        """Update a single property in item's properties JSON.

        Args:
            item_key: Item key.
            property_name: Property to update (e.g., "buttoned").
            value: New value for the property.

        Returns:
            Updated Item.

        Raises:
            ValueError: If item not found.
        """
        from sqlalchemy.orm.attributes import flag_modified

        item = self.get_item(item_key)
        if item is None:
            raise ValueError(f"Item not found: {item_key}")

        # Initialize properties if None
        if item.properties is None:
            item.properties = {}

        # Update the property
        item.properties[property_name] = value

        # Mark as modified for SQLAlchemy JSON tracking
        flag_modified(item, "properties")

        self.db.flush()
        return item

    def update_item_state(
        self,
        item_key: str,
        state_key: str,
        value: str,
    ) -> Item:
        """Update a state property in item's properties.state dict.

        State properties track mutable item characteristics like cleanliness,
        condition, freshness, etc. This method handles initialization of the
        state dict if it doesn't exist.

        Args:
            item_key: Item key.
            state_key: State category (e.g., "cleanliness", "condition").
            value: New value for the state.

        Returns:
            Updated Item.

        Raises:
            ValueError: If item not found.
        """
        from sqlalchemy.orm.attributes import flag_modified

        item = self.get_item(item_key)
        if item is None:
            raise ValueError(f"Item not found: {item_key}")

        # Initialize properties and state dict if needed
        if item.properties is None:
            item.properties = {}
        if "state" not in item.properties:
            item.properties["state"] = {}

        # Update the state
        item.properties["state"][state_key] = value

        # Mark as modified for SQLAlchemy JSON tracking
        flag_modified(item, "properties")

        self.db.flush()
        return item

    def create_item(
        self,
        item_key: str,
        display_name: str,
        item_type: ItemType = ItemType.MISC,
        owner_id: int | None = None,
        **kwargs,
    ) -> Item:
        """Create a new item.

        Args:
            item_key: Unique key for the item.
            display_name: Display name.
            item_type: Type of item.
            owner_id: Optional owner entity ID.
            **kwargs: Additional fields (description, properties, etc.)

        Returns:
            Created Item.
        """
        item = Item(
            session_id=self.session_id,
            item_key=item_key,
            display_name=display_name,
            item_type=item_type,
            owner_id=owner_id,
            **kwargs,
        )
        self.db.add(item)
        self.db.flush()
        return item

    def get_inventory(self, entity_id: int) -> list[Item]:
        """Get all items held by entity.

        Args:
            entity_id: Entity ID.

        Returns:
            List of Items held by the entity.
        """
        return (
            self.db.query(Item)
            .filter(
                Item.session_id == self.session_id,
                Item.holder_id == entity_id,
            )
            .all()
        )

    def get_owned_items(self, entity_id: int) -> list[Item]:
        """Get all items owned by entity (may be held by others).

        Args:
            entity_id: Entity ID.

        Returns:
            List of Items owned by the entity.
        """
        return (
            self.db.query(Item)
            .filter(
                Item.session_id == self.session_id,
                Item.owner_id == entity_id,
            )
            .all()
        )

    def transfer_item(
        self,
        item_key: str,
        to_entity_id: int | None = None,
        to_storage_key: str | None = None,
    ) -> Item:
        """Transfer item to entity or storage location.

        Args:
            item_key: Item key.
            to_entity_id: Target entity ID (if transferring to entity).
            to_storage_key: Target storage key (if transferring to storage).

        Returns:
            Updated Item.

        Raises:
            ValueError: If item not found.
        """
        item = self.get_item(item_key)
        if item is None:
            raise ValueError(f"Item not found: {item_key}")

        if to_entity_id is not None:
            item.holder_id = to_entity_id
            item.storage_location_id = None
        elif to_storage_key is not None:
            storage = (
                self.db.query(StorageLocation)
                .filter(
                    StorageLocation.session_id == self.session_id,
                    StorageLocation.location_key == to_storage_key,
                )
                .first()
            )
            if storage is None:
                raise ValueError(f"Storage not found: {to_storage_key}")
            item.storage_location_id = storage.id
            item.holder_id = None

        self.db.flush()
        return item

    def equip_item(
        self,
        item_key: str,
        entity_id: int,
        body_slot: str,
        body_layer: int = 0,
    ) -> Item:
        """Equip item to body slot.

        Args:
            item_key: Item key.
            entity_id: Entity ID.
            body_slot: Body slot (e.g., 'upper_body', 'feet').
            body_layer: Layer (0=innermost).

        Returns:
            Updated Item.

        Raises:
            ValueError: If item not found.
        """
        item = self.get_item(item_key)
        if item is None:
            raise ValueError(f"Item not found: {item_key}")

        item.holder_id = entity_id
        item.body_slot = body_slot
        item.body_layer = body_layer

        self.db.flush()
        return item

    def unequip_item(self, item_key: str) -> Item:
        """Remove item from body slot (move to held).

        Args:
            item_key: Item key.

        Returns:
            Updated Item.

        Raises:
            ValueError: If item not found.
        """
        item = self.get_item(item_key)
        if item is None:
            raise ValueError(f"Item not found: {item_key}")

        item.body_slot = None
        item.body_layer = 0

        self.db.flush()
        return item

    def drop_item(self, item_key: str, location_key: str) -> Item:
        """Drop item at a world location.

        Removes item from holder and places it at the specified location.

        Args:
            item_key: Item key.
            location_key: World location key where item is dropped.

        Returns:
            Updated Item.

        Raises:
            ValueError: If item not found.
        """
        item = self.get_item(item_key)
        if item is None:
            raise ValueError(f"Item not found: {item_key}")

        item.holder_id = None
        item.body_slot = None
        item.body_layer = 0

        # Find or create a storage location for this place
        storage = (
            self.db.query(StorageLocation)
            .filter(
                StorageLocation.session_id == self.session_id,
                StorageLocation.location_key == location_key,
                StorageLocation.location_type == StorageLocationType.PLACE,
            )
            .first()
        )

        if storage is None:
            storage = StorageLocation(
                session_id=self.session_id,
                location_key=location_key,
                location_type=StorageLocationType.PLACE,
            )
            self.db.add(storage)
            self.db.flush()

        # Point the item to this storage location
        item.storage_location_id = storage.id

        self.db.flush()
        return item

    def delete_item(self, item_key: str) -> None:
        """Delete an item from the game (consumed, destroyed, etc.).

        Also cleans up any associated storage location if it was a container.

        Args:
            item_key: Item key.

        Raises:
            ValueError: If item not found.
        """
        item = self.get_item(item_key)
        if item is None:
            raise ValueError(f"Item not found: {item_key}")

        # If this was a container, delete its storage location too
        if item.item_type == ItemType.CONTAINER:
            storage = (
                self.db.query(StorageLocation)
                .filter(
                    StorageLocation.session_id == self.session_id,
                    StorageLocation.container_item_id == item.id,
                )
                .first()
            )
            if storage:
                self.db.delete(storage)

        self.db.delete(item)
        self.db.flush()

    def get_equipped_items(self, entity_id: int) -> list[Item]:
        """Get all equipped items for entity.

        Args:
            entity_id: Entity ID.

        Returns:
            List of equipped Items.
        """
        return (
            self.db.query(Item)
            .filter(
                Item.session_id == self.session_id,
                Item.holder_id == entity_id,
                Item.body_slot.isnot(None),
            )
            .all()
        )

    def get_visible_equipment(self, entity_id: int) -> list[Item]:
        """Get only visible equipped items (outermost layer per slot).

        Args:
            entity_id: Entity ID.

        Returns:
            List of visible equipped Items.
        """
        return (
            self.db.query(Item)
            .filter(
                Item.session_id == self.session_id,
                Item.holder_id == entity_id,
                Item.body_slot.isnot(None),
                Item.is_visible == True,
            )
            .all()
        )

    def update_visibility(self, entity_id: int) -> None:
        """Recalculate is_visible for all equipped items based on layers and covering.

        Items at the highest layer for each body slot are visible, unless:
        - They are in a slot that is covered by another slot's item
        - e.g., full_body covers torso and legs

        Args:
            entity_id: Entity ID.
        """
        equipped = self.get_equipped_items(entity_id)

        # Group by body slot
        slots: dict[str, list[Item]] = defaultdict(list)
        for item in equipped:
            if item.body_slot:
                slots[item.body_slot].append(item)

        # Determine which slots are covered by other slots
        covered_slots: set[str] = set()
        for covering_slot, covered_list in SLOT_COVERS.items():
            if covering_slot in slots:  # Has item in covering slot
                covered_slots.update(covered_list)

        # For each slot, find max layer and set visibility
        for slot, items in slots.items():
            if not items:
                continue
            max_layer = max(i.body_layer for i in items)

            # Set visibility based on layer AND covering
            for item in items:
                is_at_max_layer = (item.body_layer == max_layer)
                is_in_covered_slot = (slot in covered_slots)
                item.is_visible = is_at_max_layer and not is_in_covered_slot

        self.db.flush()

    def get_items_at_storage(self, storage_key: str) -> list[Item]:
        """Get items in a storage location.

        Args:
            storage_key: Storage location key.

        Returns:
            List of Items in the storage.
        """
        storage = (
            self.db.query(StorageLocation)
            .filter(
                StorageLocation.session_id == self.session_id,
                StorageLocation.location_key == storage_key,
            )
            .first()
        )

        if storage is None:
            return []

        return (
            self.db.query(Item)
            .filter(
                Item.session_id == self.session_id,
                Item.storage_location_id == storage.id,
            )
            .all()
        )

    def get_items_at_location(self, location_key: str) -> list[Item]:
        """Get items at a world location (not held by anyone).

        Finds items either:
        1. In storage locations linked to the given world location
        2. With owner_location_id pointing to the world location

        Args:
            location_key: World location key.

        Returns:
            List of Items at the location.
        """
        from sqlalchemy import or_
        from src.database.models.world import Location

        # Find the world location
        location = (
            self.db.query(Location)
            .filter(
                Location.session_id == self.session_id,
                Location.location_key == location_key,
            )
            .first()
        )

        if location is None:
            return []

        # Find storage locations at this world location
        storage_ids = (
            self.db.query(StorageLocation.id)
            .filter(
                StorageLocation.session_id == self.session_id,
                StorageLocation.world_location_id == location.id,
            )
            .all()
        )

        storage_id_list = [s.id for s in storage_ids]

        # Build query conditions
        conditions = [
            # Items with owner_location_id pointing to this location
            Item.owner_location_id == location.id,
        ]

        if storage_id_list:
            # Items in storage locations at this world location
            conditions.append(Item.storage_location_id.in_(storage_id_list))

        # Return items matching any condition (no holder)
        return (
            self.db.query(Item)
            .filter(
                Item.session_id == self.session_id,
                Item.holder_id.is_(None),
                or_(*conditions),
            )
            .all()
        )

    def create_storage(
        self,
        location_key: str,
        location_type: StorageLocationType,
        owner_entity_id: int | None = None,
        **kwargs,
    ) -> StorageLocation:
        """Create storage location.

        Args:
            location_key: Unique storage key.
            location_type: Type of storage.
            owner_entity_id: Optional owner entity ID.
            **kwargs: Additional fields.

        Returns:
            Created StorageLocation.
        """
        storage = StorageLocation(
            session_id=self.session_id,
            location_key=location_key,
            location_type=location_type,
            owner_entity_id=owner_entity_id,
            **kwargs,
        )
        self.db.add(storage)
        self.db.flush()
        return storage

    def get_or_create_body_storage(self, entity_id: int) -> StorageLocation:
        """Get or create ON_PERSON storage for entity.

        Args:
            entity_id: Entity ID.

        Returns:
            StorageLocation for entity's body.
        """
        storage_key = f"body_{entity_id}"

        existing = (
            self.db.query(StorageLocation)
            .filter(
                StorageLocation.session_id == self.session_id,
                StorageLocation.location_key == storage_key,
            )
            .first()
        )

        if existing is not None:
            return existing

        return self.create_storage(
            location_key=storage_key,
            location_type=StorageLocationType.ON_PERSON,
            owner_entity_id=entity_id,
        )

    def set_item_condition(
        self, item_key: str, condition: ItemCondition
    ) -> Item:
        """Update item condition.

        Args:
            item_key: Item key.
            condition: New condition.

        Returns:
            Updated Item.

        Raises:
            ValueError: If item not found.
        """
        item = self.get_item(item_key)
        if item is None:
            raise ValueError(f"Item not found: {item_key}")

        item.condition = condition
        self.db.flush()
        return item

    def damage_item(self, item_key: str, damage: int) -> Item:
        """Reduce durability, update condition if thresholds crossed.

        Args:
            item_key: Item key.
            damage: Amount of durability to reduce.

        Returns:
            Updated Item.

        Raises:
            ValueError: If item not found.
        """
        item = self.get_item(item_key)
        if item is None:
            raise ValueError(f"Item not found: {item_key}")

        if item.durability is not None:
            item.durability = max(0, item.durability - damage)

            # Update condition based on durability
            for threshold, condition in sorted(
                CONDITION_THRESHOLDS.items(), reverse=True
            ):
                if item.durability >= threshold:
                    item.condition = condition
                    break

        self.db.flush()
        return item

    # ==================== Slot Management ====================

    def get_available_slots(self, entity_id: int) -> dict[str, dict]:
        """Get all available slots including bonus slots from worn items.

        Base slots are always available. Bonus slots are added dynamically
        when items that provide them are equipped (e.g., belt provides pouch slots).

        Args:
            entity_id: Entity ID.

        Returns:
            Dict of slot_key -> slot info dict.
        """
        # Start with base slots
        slots = dict(BODY_SLOTS)

        # Add bonus slots from worn items that provide them
        equipped = self.get_equipped_items(entity_id)
        for item in equipped:
            if item.provides_slots:
                for slot_key in item.provides_slots:
                    if slot_key in BONUS_SLOTS:
                        slots[slot_key] = BONUS_SLOTS[slot_key]

        return slots

    def get_outfit_by_slot(self, entity_id: int) -> dict[str, list[Item]]:
        """Get equipped items organized by body slot with layer ordering.

        Args:
            entity_id: Entity ID.

        Returns:
            Dict of slot_key -> list of Items sorted by layer (innermost first).
        """
        equipped = self.get_equipped_items(entity_id)

        by_slot: dict[str, list[Item]] = defaultdict(list)
        for item in equipped:
            if item.body_slot:
                by_slot[item.body_slot].append(item)

        # Sort each slot's items by layer
        for slot in by_slot:
            by_slot[slot].sort(key=lambda i: i.body_layer)

        return dict(by_slot)

    def format_outfit_description(self, entity_id: int, include_visuals: bool = True) -> str:
        """Generate human-readable outfit description for GM context.

        Only includes visible items (outermost layer, not covered).

        Args:
            entity_id: Entity ID.
            include_visuals: If True, use rich visual descriptions from item properties.

        Returns:
            Human-readable outfit description string.
        """
        from src.services.clothing_visual_generator import format_visual_description

        visible = self.get_visible_equipment(entity_id)

        if not visible:
            return "Not wearing anything notable."

        def get_item_description(item: Item) -> str:
            """Get description for an item, using visual props if available."""
            if include_visuals and item.properties and item.properties.get("visual"):
                return format_visual_description(item.properties["visual"], item.display_name)
            return item.display_name

        # Group visible items by category for natural description
        categories = {
            "head_wear": [],
            "torso_wear": [],
            "leg_wear": [],
            "foot_wear": [],
            "accessories": [],
            "carried": [],
        }

        for item in visible:
            slot = item.body_slot or ""
            desc = get_item_description(item)
            if slot in ("head", "face"):
                categories["head_wear"].append(desc)
            elif slot in ("torso", "full_body"):
                categories["torso_wear"].append(desc)
            elif slot == "legs":
                categories["leg_wear"].append(desc)
            elif slot in ("feet_socks", "feet_shoes"):
                categories["foot_wear"].append(desc)
            elif slot in ("main_hand", "off_hand", "back"):
                categories["carried"].append(desc)
            else:
                categories["accessories"].append(desc)

        # Build description
        parts = []

        if categories["torso_wear"]:
            parts.append(", ".join(categories["torso_wear"]))
        if categories["leg_wear"]:
            parts.append(", ".join(categories["leg_wear"]))
        if categories["foot_wear"]:
            parts.append(", ".join(categories["foot_wear"]))
        if categories["head_wear"]:
            parts.append(", ".join(categories["head_wear"]))
        if categories["accessories"]:
            parts.append(", ".join(categories["accessories"]))

        main_outfit = ", ".join(parts) if parts else "simple attire"

        carried = categories["carried"]
        if carried:
            return f"Wearing {main_outfit}. Carrying {', '.join(carried)}."
        else:
            return f"Wearing {main_outfit}."

    def get_visible_by_slot(self, entity_id: int) -> dict[str, Item]:
        """Get visible items indexed by slot.

        Args:
            entity_id: Entity ID.

        Returns:
            Dict of slot_key -> visible Item for that slot.
        """
        visible = self.get_visible_equipment(entity_id)
        return {item.body_slot: item for item in visible if item.body_slot}

    # ==================== Slot/Weight Validation ====================

    def check_slot_available(self, entity_id: int, slot: str) -> bool:
        """Check if a body slot is available for an item.

        Args:
            entity_id: Entity ID.
            slot: Body slot to check.

        Returns:
            True if slot is available, False if occupied.
        """
        item = self.get_item_in_slot(entity_id, slot)
        return item is None

    def get_item_in_slot(self, entity_id: int, slot: str) -> Item | None:
        """Get the item currently in a specific body slot.

        Args:
            entity_id: Entity ID.
            slot: Body slot to check.

        Returns:
            Item in the slot, or None if empty.
        """
        return (
            self.db.query(Item)
            .filter(
                Item.session_id == self.session_id,
                Item.holder_id == entity_id,
                Item.body_slot == slot,
            )
            .first()
        )

    def get_total_carried_weight(self, entity_id: int) -> float:
        """Calculate total weight of all items carried by entity.

        Args:
            entity_id: Entity ID.

        Returns:
            Total weight in pounds.
        """
        items = self.get_inventory(entity_id)
        total = 0.0
        for item in items:
            if item.weight:
                total += item.weight * item.quantity
        return total

    def can_carry_weight(
        self, entity_id: int, additional_weight: float, max_weight: float | None = None
    ) -> bool:
        """Check if entity can carry additional weight.

        Args:
            entity_id: Entity ID.
            additional_weight: Weight to add.
            max_weight: Maximum carry weight (default: 50 lbs).

        Returns:
            True if entity can carry the additional weight.
        """
        if max_weight is None:
            # Default max weight - could be based on Strength later
            max_weight = 50.0

        current_weight = self.get_total_carried_weight(entity_id)
        return (current_weight + additional_weight) <= max_weight

    def find_available_slot(
        self, entity_id: int, item_type: str, item_size: str = "small"
    ) -> str | None:
        """Find an available slot for an item based on type.

        Args:
            entity_id: Entity ID.
            item_type: Item type (weapon, armor, misc, consumable, etc.)
            item_size: Size hint (small, medium, large).

        Returns:
            Available slot key, or None if no slot available.
        """
        # Get all available slots (including bonus slots from worn items)
        available_slots = self.get_available_slots(entity_id)

        # Define slot priority by item type
        slot_priorities: dict[str, list[str]] = {
            "weapon": ["main_hand", "off_hand", "back"],
            "armor": [],  # Armor goes to specific body parts, not auto-assigned
            "clothing": [],  # Clothing goes to specific body parts
            "shield": ["off_hand", "back"],
            "consumable": ["belt_pouch_1", "belt_pouch_2", "belt_pouch_3",
                          "pocket_left", "pocket_right", "backpack_main"],
            "container": ["back", "waist"],
            "misc": [],  # Will be set based on size
        }

        # Misc items depend on size
        if item_type == "misc":
            if item_size == "large":
                slot_priorities["misc"] = ["main_hand", "off_hand", "back", "backpack_main"]
            else:  # small or medium
                slot_priorities["misc"] = [
                    "belt_pouch_1", "belt_pouch_2", "belt_pouch_3",
                    "pocket_left", "pocket_right",
                    "backpack_main", "backpack_side",
                    "main_hand", "off_hand",
                ]

        # Get priority list for this item type
        priorities = slot_priorities.get(item_type, slot_priorities["misc"])

        # Find first available slot in priority order
        for slot in priorities:
            if slot in available_slots and self.check_slot_available(entity_id, slot):
                return slot

        return None

    def get_inventory_summary(self, entity_id: int) -> dict:
        """Get a summary of entity's inventory state for GM context.

        Args:
            entity_id: Entity ID.

        Returns:
            Dict with slot usage, weight, and capacity info.
        """
        available_slots = self.get_available_slots(entity_id)
        equipped = self.get_equipped_items(entity_id)

        # Count occupied slots
        occupied_slots = {}
        for item in equipped:
            if item.body_slot:
                occupied_slots[item.body_slot] = item.display_name

        # Find free slots by category
        free_hand_slots = []
        free_storage_slots = []
        for slot in available_slots:
            if slot not in occupied_slots:
                if slot in ("main_hand", "off_hand", "hand_left", "hand_right"):
                    free_hand_slots.append(slot)
                elif slot in BONUS_SLOTS:
                    free_storage_slots.append(slot)

        return {
            "total_weight": self.get_total_carried_weight(entity_id),
            "max_weight": 50.0,  # Could be dynamic based on Strength
            "free_hand_slots": free_hand_slots,
            "free_storage_slots": free_storage_slots,
            "occupied_slots": occupied_slots,
            "can_hold_more": len(free_hand_slots) > 0 or len(free_storage_slots) > 0,
        }

    def get_carried_inventory(self, entity_id: int) -> dict:
        """Get structured inventory of items the entity is currently carrying.

        Returns items organized into three categories:
        - equipped: Items in body slots (weapons, armor, clothing)
        - held: Items held but not in a body slot (loose items)
        - containers: Worn containers with their contents

        Args:
            entity_id: Entity ID.

        Returns:
            Dict with equipped, held, and containers lists.
        """
        # Get all items the entity is currently holding
        held_items = (
            self.db.query(Item)
            .filter(
                Item.session_id == self.session_id,
                Item.holder_id == entity_id,
            )
            .all()
        )

        equipped = []
        held = []
        containers = []

        # Separate equipped items from held items
        for item in held_items:
            if item.body_slot is not None:
                equipped.append(item)
            else:
                held.append(item)

        # Get body storage for this entity (ON_PERSON storage)
        body_storage = self.get_or_create_body_storage(entity_id)

        # Find containers that are ON the player (equipped or in body storage)
        # A container is "on person" if:
        # 1. It has a body_slot (worn/equipped), OR
        # 2. It's in the body storage (ON_PERSON type)
        worn_container_ids = set()

        # Get equipped containers (like belt pouches)
        for item in equipped:
            if item.item_type == ItemType.CONTAINER:
                worn_container_ids.add(item.id)

        # Get containers in body storage
        items_in_body_storage = (
            self.db.query(Item)
            .filter(
                Item.session_id == self.session_id,
                Item.storage_location_id == body_storage.id,
            )
            .all()
        )

        for item in items_in_body_storage:
            if item.item_type == ItemType.CONTAINER:
                worn_container_ids.add(item.id)

        # For each worn container, get its storage and contents
        for container_id in worn_container_ids:
            container_item = self.db.query(Item).filter(Item.id == container_id).first()
            if container_item is None:
                continue

            # Find the StorageLocation linked to this container
            container_storage = (
                self.db.query(StorageLocation)
                .filter(
                    StorageLocation.session_id == self.session_id,
                    StorageLocation.container_item_id == container_id,
                )
                .first()
            )

            contents = []
            if container_storage:
                contents = (
                    self.db.query(Item)
                    .filter(
                        Item.session_id == self.session_id,
                        Item.storage_location_id == container_storage.id,
                    )
                    .all()
                )

            containers.append({
                "container": container_item,
                "storage": container_storage,
                "contents": contents,
            })

        return {
            "equipped": equipped,
            "held": held,
            "containers": containers,
        }

    # ==================== Theft Operations ====================

    def steal_item(
        self,
        item_key: str,
        thief_id: int,
        from_entity_id: int | None = None,
        from_location_id: int | None = None,
    ) -> Item:
        """Mark item as stolen and transfer to thief.

        Sets is_stolen=True, was_ever_stolen=True, and tracks who/where
        it was stolen from for potential return. Does NOT change owner_id
        (the item still legally belongs to the victim).

        Args:
            item_key: Item key.
            thief_id: Entity ID of the thief.
            from_entity_id: Entity the item was stolen from.
            from_location_id: Location/establishment the item was stolen from.

        Returns:
            Updated Item.

        Raises:
            ValueError: If item not found.
        """
        item = self.get_item(item_key)
        if item is None:
            raise ValueError(f"Item not found: {item_key}")

        item.is_stolen = True
        item.was_ever_stolen = True
        item.holder_id = thief_id
        item.storage_location_id = None  # Now held by thief

        if from_entity_id is not None:
            item.stolen_from_id = from_entity_id
        if from_location_id is not None:
            item.stolen_from_location_id = from_location_id

        self.db.flush()
        return item

    def return_stolen_item(
        self,
        item_key: str,
        to_entity_id: int | None = None,
    ) -> Item:
        """Return stolen item to original holder.

        Clears is_stolen and stolen_from tracking. The was_ever_stolen
        flag remains True (historical record).

        Args:
            item_key: Item key.
            to_entity_id: Override entity to return to (e.g., representative
                         of a location like an innkeeper).

        Returns:
            Updated Item.

        Raises:
            ValueError: If item not found.
        """
        item = self.get_item(item_key)
        if item is None:
            raise ValueError(f"Item not found: {item_key}")

        item.is_stolen = False

        # Determine who to return to
        if to_entity_id is not None:
            item.holder_id = to_entity_id
        elif item.stolen_from_id is not None:
            item.holder_id = item.stolen_from_id

        # Clear theft tracking (returned)
        item.stolen_from_id = None
        item.stolen_from_location_id = None

        self.db.flush()
        return item

    def legitimize_item(
        self,
        item_key: str,
        new_owner_id: int | None = None,
        new_owner_location_id: int | None = None,
    ) -> Item:
        """Clear stolen status via legitimate transfer (sale/gift).

        Clears is_stolen because the new owner acquired it legitimately.
        The was_ever_stolen flag remains True (affects value/reputation).

        Args:
            item_key: Item key.
            new_owner_id: New entity owner (mutually exclusive with location).
            new_owner_location_id: New location owner (mutually exclusive with entity).

        Returns:
            Updated Item.

        Raises:
            ValueError: If item not found.
        """
        item = self.get_item(item_key)
        if item is None:
            raise ValueError(f"Item not found: {item_key}")

        item.is_stolen = False
        item.stolen_from_id = None
        item.stolen_from_location_id = None

        if new_owner_id is not None:
            item.owner_id = new_owner_id
            item.owner_location_id = None
            item.holder_id = new_owner_id  # Transfer possession too
        elif new_owner_location_id is not None:
            item.owner_location_id = new_owner_location_id
            item.owner_id = None

        self.db.flush()
        return item

    # ==================== Container Operations ====================

    def create_container_item(
        self,
        item_key: str,
        display_name: str,
        owner_id: int | None = None,
        container_type: str = "container",
        capacity: int | None = None,
        weight_capacity: float | None = None,
        is_fixed: bool = False,
        world_location_id: int | None = None,
        **item_kwargs,
    ) -> tuple[Item, StorageLocation]:
        """Create an Item that is also a container.

        Atomically creates both the Item (CONTAINER type) and a linked
        StorageLocation. The storage uses the item_key + "_storage" as its key.

        Args:
            item_key: Unique key for the item.
            display_name: Display name.
            owner_id: Optional owner entity ID.
            container_type: Type of container (backpack, pouch, chest, etc.).
            capacity: Max item count.
            weight_capacity: Max weight in pounds.
            is_fixed: Cannot be moved (built-in closet).
            world_location_id: World location for fixed storage.
            **item_kwargs: Additional Item fields.

        Returns:
            Tuple of (Item, StorageLocation).
        """
        # Create the item
        item = self.create_item(
            item_key=item_key,
            display_name=display_name,
            item_type=ItemType.CONTAINER,
            owner_id=owner_id,
            **item_kwargs,
        )

        # Create the linked storage
        storage_key = f"{item_key}_storage"
        storage = self.create_storage(
            location_key=storage_key,
            location_type=StorageLocationType.CONTAINER,
            owner_entity_id=owner_id,
            container_type=container_type,
            capacity=capacity,
            weight_capacity=weight_capacity,
            is_fixed=is_fixed,
            world_location_id=world_location_id,
            container_item_id=item.id,
        )

        return item, storage

    def put_in_container(
        self,
        item_key: str,
        container_key: str,
    ) -> Item:
        """Move item into a container, checking capacity.

        Args:
            item_key: Item key.
            container_key: Storage location key of the container.

        Returns:
            Updated Item.

        Raises:
            ValueError: If item/container not found or capacity exceeded.
        """
        item = self.get_item(item_key)
        if item is None:
            raise ValueError(f"Item not found: {item_key}")

        storage = (
            self.db.query(StorageLocation)
            .filter(
                StorageLocation.session_id == self.session_id,
                StorageLocation.location_key == container_key,
            )
            .first()
        )
        if storage is None:
            raise ValueError(f"Container not found: {container_key}")

        # Check capacity
        count_remaining, weight_remaining = self.get_container_remaining_capacity(
            container_key
        )

        if count_remaining is not None and count_remaining <= 0:
            raise ValueError(f"Container {container_key} is at item capacity")

        if weight_remaining is not None and item.weight is not None:
            if item.weight > weight_remaining:
                raise ValueError(
                    f"Item weight ({item.weight}) exceeds remaining container "
                    f"weight capacity ({weight_remaining})"
                )

        # Move item to container
        item.storage_location_id = storage.id
        item.holder_id = None
        item.body_slot = None
        item.body_layer = 0

        self.db.flush()
        return item

    def get_container_remaining_capacity(
        self,
        storage_key: str,
    ) -> tuple[int | None, float | None]:
        """Get remaining item count and weight capacity.

        Args:
            storage_key: Storage location key.

        Returns:
            Tuple of (remaining_count, remaining_weight).
            None means unlimited.

        Raises:
            ValueError: If storage not found.
        """
        storage = (
            self.db.query(StorageLocation)
            .filter(
                StorageLocation.session_id == self.session_id,
                StorageLocation.location_key == storage_key,
            )
            .first()
        )
        if storage is None:
            raise ValueError(f"Storage not found: {storage_key}")

        # Get current items in storage
        items = self.get_items_at_storage(storage_key)

        # Calculate remaining count
        count_remaining = None
        if storage.capacity is not None:
            count_remaining = storage.capacity - len(items)

        # Calculate remaining weight
        weight_remaining = None
        if storage.weight_capacity is not None:
            current_weight = sum(
                (i.weight or 0) * i.quantity for i in items
            )
            weight_remaining = storage.weight_capacity - current_weight

        return count_remaining, weight_remaining

    # ==================== Temporary Storage Operations ====================

    def create_temporary_surface(
        self,
        surface_key: str,
        world_location_id: int,
        container_type: str = "surface",
        capacity: int | None = None,
        weight_capacity: float | None = None,
    ) -> StorageLocation:
        """Create a temporary surface for placing items.

        Temporary surfaces (tables, floors, counters) are auto-cleaned
        when empty via cleanup_empty_temporary_storage().

        Args:
            surface_key: Unique key for this surface.
            world_location_id: World location ID where surface exists.
            container_type: Type of surface (table, floor, counter, etc.).
            capacity: Optional max item count.
            weight_capacity: Optional max weight in pounds.

        Returns:
            Created StorageLocation with is_temporary=True.
        """
        return self.create_storage(
            location_key=surface_key,
            location_type=StorageLocationType.PLACE,
            world_location_id=world_location_id,
            container_type=container_type,
            capacity=capacity,
            weight_capacity=weight_capacity,
            is_temporary=True,
        )

    def get_or_create_surface(
        self,
        surface_key: str,
        world_location_id: int,
        container_type: str = "surface",
        capacity: int | None = None,
        weight_capacity: float | None = None,
    ) -> StorageLocation:
        """Get existing surface or create new temporary one.

        Use this when placing an item on a surface - if the surface
        doesn't exist, it will be created automatically.

        Args:
            surface_key: Unique key for this surface.
            world_location_id: World location ID where surface exists.
            container_type: Type of surface (table, floor, counter, etc.).
            capacity: Optional max item count (only used on creation).
            weight_capacity: Optional max weight (only used on creation).

        Returns:
            Existing or newly created StorageLocation.
        """
        existing = (
            self.db.query(StorageLocation)
            .filter(
                StorageLocation.session_id == self.session_id,
                StorageLocation.location_key == surface_key,
            )
            .first()
        )

        if existing is not None:
            return existing

        return self.create_temporary_surface(
            surface_key=surface_key,
            world_location_id=world_location_id,
            container_type=container_type,
            capacity=capacity,
            weight_capacity=weight_capacity,
        )

    def cleanup_empty_temporary_storage(
        self,
        location_id: int | None = None,
    ) -> int:
        """Remove empty temporary storage locations.

        Cleans up temporary surfaces (tables, floors) that no longer
        have any items. Called periodically or after items are removed.

        Args:
            location_id: Optional world location ID to filter cleanup.
                        If None, cleans all locations in session.

        Returns:
            Number of storage locations removed.
        """
        from sqlalchemy import func

        # Find temporary storage locations
        query = (
            self.db.query(StorageLocation)
            .filter(
                StorageLocation.session_id == self.session_id,
                StorageLocation.is_temporary == True,
            )
        )

        if location_id is not None:
            query = query.filter(StorageLocation.world_location_id == location_id)

        temp_storages = query.all()

        removed_count = 0
        for storage in temp_storages:
            # Check if empty (no items in this storage)
            item_count = (
                self.db.query(func.count(Item.id))
                .filter(Item.storage_location_id == storage.id)
                .scalar()
            )

            if item_count == 0:
                self.db.delete(storage)
                removed_count += 1

        self.db.flush()
        return removed_count

    # ==================== Stack Operations ====================

    def split_stack(self, item_key: str, quantity: int) -> Item:
        """Split quantity from a stackable item, creating a new item.

        The original item keeps its key with reduced quantity. A new item
        is created with the split quantity and a key derived from the
        original (e.g., "gold_coins_split_abc123").

        Args:
            item_key: Item key to split from.
            quantity: Amount to split off.

        Returns:
            Newly created Item with the split quantity.

        Raises:
            ValueError: If item not found, not stackable, or invalid quantity.
        """
        from uuid import uuid4

        item = self.get_item(item_key)
        if item is None:
            raise ValueError(f"Item not found: {item_key}")

        if not item.is_stackable:
            raise ValueError(f"Item '{item_key}' is not stackable")

        if quantity <= 0:
            raise ValueError("Split quantity must be greater than 0")

        if quantity >= item.quantity:
            if quantity == item.quantity:
                raise ValueError(
                    f"Split quantity ({quantity}) equals total quantity. "
                    "Use transfer instead of split."
                )
            raise ValueError(
                f"Split quantity ({quantity}) exceeds available ({item.quantity})"
            )

        # Reduce original item quantity
        item.quantity -= quantity

        # Generate unique key for split item
        new_key = f"{item_key}_split_{uuid4().hex[:6]}"

        # Create new item with split quantity
        split_item = Item(
            session_id=self.session_id,
            item_key=new_key,
            display_name=item.display_name,
            item_type=item.item_type,
            quantity=quantity,
            is_stackable=True,
            weight=item.weight,
            owner_id=item.owner_id,
            holder_id=item.holder_id,
            storage_location_id=item.storage_location_id,
            body_slot=item.body_slot,
            body_layer=item.body_layer,
            properties=dict(item.properties) if item.properties else None,
            condition=item.condition,
            durability=item.durability,
        )
        self.db.add(split_item)
        self.db.flush()

        return split_item

    def merge_stacks(self, target_key: str, source_key: str) -> Item:
        """Merge two stacks of the same item type into one.

        The source item is deleted after its quantity is added to the target.
        Both items must be stackable and have the same display_name.

        Args:
            target_key: Item key to merge into.
            source_key: Item key to merge from (will be deleted).

        Returns:
            Updated target Item with combined quantity.

        Raises:
            ValueError: If items not found, not stackable, or not same type.
        """
        target = self.get_item(target_key)
        if target is None:
            raise ValueError(f"Target item not found: {target_key}")

        source = self.get_item(source_key)
        if source is None:
            raise ValueError(f"Source item not found: {source_key}")

        if not target.is_stackable:
            raise ValueError(f"Target item '{target_key}' is not stackable")

        if not source.is_stackable:
            raise ValueError(f"Source item '{source_key}' is not stackable")

        if target.display_name != source.display_name:
            raise ValueError(
                f"Cannot merge items of different types: "
                f"'{target.display_name}' vs '{source.display_name}'. "
                "Items must be the same type to merge."
            )

        # Add source quantity to target
        target.quantity += source.quantity

        # Delete source item
        self.db.delete(source)
        self.db.flush()

        return target

    def find_mergeable_stack(
        self,
        holder_id: int,
        display_name: str,
    ) -> Item | None:
        """Find an existing stack in holder's inventory that can be merged.

        Searches for a stackable item with matching display_name that is
        held by the specified entity.

        Args:
            holder_id: Entity ID of the holder.
            display_name: Display name to match.

        Returns:
            Matching Item if found, None otherwise.
        """
        return (
            self.db.query(Item)
            .filter(
                Item.session_id == self.session_id,
                Item.holder_id == holder_id,
                Item.display_name == display_name,
                Item.is_stackable == True,
            )
            .first()
        )

    def transfer_quantity(
        self,
        item_key: str,
        quantity: int | None,
        to_entity_id: int | None = None,
        to_storage_key: str | None = None,
    ) -> Item:
        """Transfer quantity from item to entity or storage, with auto-merge.

        If quantity is None or equals item.quantity, transfers entire item.
        Otherwise splits stack first. When transferring to an entity, will
        attempt to merge with any existing stack of the same item type.

        Args:
            item_key: Item to transfer from.
            quantity: Amount to transfer (None = all).
            to_entity_id: Target entity ID.
            to_storage_key: Target storage key.

        Returns:
            The transferred Item (original, split, or merged).

        Raises:
            ValueError: If invalid quantity or transfer target.
        """
        item = self.get_item(item_key)
        if item is None:
            raise ValueError(f"Item not found: {item_key}")

        # Determine if we need to split
        needs_split = (
            quantity is not None
            and quantity < item.quantity
            and item.is_stackable
        )

        if needs_split:
            # Split off the quantity to transfer
            transferred_item = self.split_stack(item_key, quantity)
        else:
            # Transfer the whole item
            transferred_item = item

        # Perform the transfer
        if to_entity_id is not None:
            transferred_item.holder_id = to_entity_id
            transferred_item.storage_location_id = None

            # Check for mergeable stack at destination
            if transferred_item.is_stackable:
                existing_stack = self.find_mergeable_stack(
                    to_entity_id, transferred_item.display_name
                )
                if existing_stack and existing_stack.item_key != transferred_item.item_key:
                    # Merge into existing stack
                    transferred_item = self.merge_stacks(
                        existing_stack.item_key, transferred_item.item_key
                    )
        elif to_storage_key is not None:
            storage = (
                self.db.query(StorageLocation)
                .filter(
                    StorageLocation.session_id == self.session_id,
                    StorageLocation.location_key == to_storage_key,
                )
                .first()
            )
            if storage is None:
                raise ValueError(f"Storage not found: {to_storage_key}")
            transferred_item.storage_location_id = storage.id
            transferred_item.holder_id = None

        self.db.flush()
        return transferred_item
