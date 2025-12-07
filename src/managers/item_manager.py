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

        Finds items in storage locations linked to the given world location.

        Args:
            location_key: World location key.

        Returns:
            List of Items at the location.
        """
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

        if not storage_ids:
            return []

        storage_id_list = [s.id for s in storage_ids]

        # Return items in those storage locations (no holder)
        return (
            self.db.query(Item)
            .filter(
                Item.session_id == self.session_id,
                Item.storage_location_id.in_(storage_id_list),
                Item.holder_id.is_(None),
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

    def format_outfit_description(self, entity_id: int) -> str:
        """Generate human-readable outfit description for GM context.

        Only includes visible items (outermost layer, not covered).

        Args:
            entity_id: Entity ID.

        Returns:
            Human-readable outfit description string.
        """
        visible = self.get_visible_equipment(entity_id)

        if not visible:
            return "Not wearing anything notable."

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
            if slot in ("head", "face"):
                categories["head_wear"].append(item.display_name)
            elif slot in ("torso", "full_body"):
                categories["torso_wear"].append(item.display_name)
            elif slot == "legs":
                categories["leg_wear"].append(item.display_name)
            elif slot in ("feet_socks", "feet_shoes"):
                categories["foot_wear"].append(item.display_name)
            elif slot in ("main_hand", "off_hand", "back"):
                categories["carried"].append(item.display_name)
            else:
                categories["accessories"].append(item.display_name)

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
