"""StorageManager for storage location management."""

from sqlalchemy.orm import Session

from src.database.models.enums import StorageLocationType
from src.database.models.items import Item, StorageLocation
from src.database.models.session import GameSession
from src.managers.base import BaseManager


class StorageManager(BaseManager):
    """Manager for storage location operations.

    Handles:
    - Portability checking (fixed vs movable)
    - Hierarchy/nesting (containers within containers)
    - Location queries (storages at a world location)
    - Moving storage with contents
    """

    def get_storage(self, storage_key: str) -> StorageLocation | None:
        """Get storage location by key.

        Args:
            storage_key: Unique storage key.

        Returns:
            StorageLocation if found, None otherwise.
        """
        return (
            self.db.query(StorageLocation)
            .filter(
                StorageLocation.session_id == self.session_id,
                StorageLocation.location_key == storage_key,
            )
            .first()
        )

    # ==================== Portability Operations ====================

    def can_move_storage(self, storage_key: str) -> bool:
        """Check if storage location can be moved.

        Args:
            storage_key: Storage location key.

        Returns:
            True if movable (not fixed), False if fixed.

        Raises:
            ValueError: If storage not found.
        """
        storage = self.get_storage(storage_key)
        if storage is None:
            raise ValueError(f"Storage not found: {storage_key}")

        return not storage.is_fixed

    def get_move_difficulty(self, storage_key: str) -> float | None:
        """Get the difficulty (weight) to move storage.

        For strength checks - weight_to_move indicates how heavy
        the container is to move. Returns:
        - None: Easily movable (no check needed)
        - float: Weight for strength check
        - infinity: Fixed, cannot be moved

        Args:
            storage_key: Storage location key.

        Returns:
            Weight for strength check, None if easy, infinity if fixed.

        Raises:
            ValueError: If storage not found.
        """
        storage = self.get_storage(storage_key)
        if storage is None:
            raise ValueError(f"Storage not found: {storage_key}")

        if storage.is_fixed:
            return float("inf")

        return storage.weight_to_move

    # ==================== Hierarchy Operations ====================

    def get_storage_hierarchy(self, storage_key: str) -> list[StorageLocation]:
        """Get parent chain for nested storage.

        Returns the list of parent containers from immediate parent
        to the root (top-level) storage.

        Args:
            storage_key: Storage location key.

        Returns:
            List of parent StorageLocations, empty if top-level.

        Raises:
            ValueError: If storage not found.
        """
        storage = self.get_storage(storage_key)
        if storage is None:
            raise ValueError(f"Storage not found: {storage_key}")

        parents = []
        current = storage

        while current.parent_location_id is not None:
            parent = (
                self.db.query(StorageLocation)
                .filter(StorageLocation.id == current.parent_location_id)
                .first()
            )
            if parent is None:
                break
            parents.append(parent)
            current = parent

        return parents

    def get_child_storages(self, storage_key: str) -> list[StorageLocation]:
        """Get direct child containers nested within this storage.

        Args:
            storage_key: Storage location key.

        Returns:
            List of child StorageLocations.

        Raises:
            ValueError: If storage not found.
        """
        storage = self.get_storage(storage_key)
        if storage is None:
            raise ValueError(f"Storage not found: {storage_key}")

        return (
            self.db.query(StorageLocation)
            .filter(
                StorageLocation.session_id == self.session_id,
                StorageLocation.parent_location_id == storage.id,
            )
            .all()
        )

    def get_nested_contents(self, storage_key: str) -> list[Item]:
        """Get all items in storage including nested containers.

        Recursively collects items from this storage and all
        nested child containers.

        Args:
            storage_key: Storage location key.

        Returns:
            List of all Items (direct and nested).

        Raises:
            ValueError: If storage not found.
        """
        storage = self.get_storage(storage_key)
        if storage is None:
            raise ValueError(f"Storage not found: {storage_key}")

        all_items = []

        # Get direct items
        direct_items = (
            self.db.query(Item)
            .filter(
                Item.session_id == self.session_id,
                Item.storage_location_id == storage.id,
            )
            .all()
        )
        all_items.extend(direct_items)

        # Recursively get items from child storages
        children = self.get_child_storages(storage_key)
        for child in children:
            nested_items = self.get_nested_contents(child.location_key)
            all_items.extend(nested_items)

        return all_items

    # ==================== Nesting Operations ====================

    def nest_storage(
        self,
        storage_key: str,
        parent_key: str,
    ) -> StorageLocation:
        """Nest one storage inside another (container in container).

        Args:
            storage_key: Storage location to nest.
            parent_key: Parent storage to nest inside.

        Returns:
            Updated StorageLocation.

        Raises:
            ValueError: If either storage not found.
        """
        storage = self.get_storage(storage_key)
        if storage is None:
            raise ValueError(f"Storage not found: {storage_key}")

        parent = self.get_storage(parent_key)
        if parent is None:
            raise ValueError(f"Parent storage not found: {parent_key}")

        storage.parent_location_id = parent.id
        self.db.flush()
        return storage

    def unnest_storage(self, storage_key: str) -> StorageLocation:
        """Remove storage from its parent container.

        Args:
            storage_key: Storage location to unnest.

        Returns:
            Updated StorageLocation.

        Raises:
            ValueError: If storage not found.
        """
        storage = self.get_storage(storage_key)
        if storage is None:
            raise ValueError(f"Storage not found: {storage_key}")

        storage.parent_location_id = None
        self.db.flush()
        return storage

    # ==================== Location Operations ====================

    def get_all_storages_at_location(
        self,
        location_id: int,
    ) -> list[StorageLocation]:
        """Get all storage locations at a world location.

        Args:
            location_id: World location ID.

        Returns:
            List of StorageLocations at that location.
        """
        return (
            self.db.query(StorageLocation)
            .filter(
                StorageLocation.session_id == self.session_id,
                StorageLocation.world_location_id == location_id,
            )
            .all()
        )

    def move_storage_to_location(
        self,
        storage_key: str,
        to_location_id: int,
    ) -> StorageLocation:
        """Move storage to a new world location.

        Only works for portable (non-fixed) storage.

        Args:
            storage_key: Storage location key.
            to_location_id: Target world location ID.

        Returns:
            Updated StorageLocation.

        Raises:
            ValueError: If storage not found or is fixed.
        """
        storage = self.get_storage(storage_key)
        if storage is None:
            raise ValueError(f"Storage not found: {storage_key}")

        if storage.is_fixed:
            raise ValueError(f"Cannot move fixed storage: {storage_key}")

        storage.world_location_id = to_location_id
        self.db.flush()
        return storage
