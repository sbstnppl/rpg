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
        """Recalculate is_visible for all equipped items based on layers.

        Items at the highest layer for each body slot are visible.
        Items at lower layers are covered (not visible).

        Args:
            entity_id: Entity ID.
        """
        equipped = self.get_equipped_items(entity_id)

        # Group by body slot
        slots: dict[str, list[Item]] = defaultdict(list)
        for item in equipped:
            if item.body_slot:
                slots[item.body_slot].append(item)

        # For each slot, find max layer
        for slot, items in slots.items():
            if not items:
                continue
            max_layer = max(i.body_layer for i in items)

            # Set visibility based on layer
            for item in items:
                item.is_visible = (item.body_layer == max_layer)

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
