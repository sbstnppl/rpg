"""LocationManager for location hierarchy and state management."""

from sqlalchemy.orm import Session

from src.database.models.items import StorageLocation
from src.database.models.session import GameSession
from src.database.models.world import Location
from src.managers.base import BaseManager


class LocationManager(BaseManager):
    """Manager for location operations.

    Handles:
    - Location CRUD
    - Hierarchical location queries
    - Visit tracking
    - State management
    - Accessibility control
    """

    def get_location(self, location_key: str) -> Location | None:
        """Get location by key.

        Args:
            location_key: Unique location key.

        Returns:
            Location if found, None otherwise.
        """
        return (
            self.db.query(Location)
            .filter(
                Location.session_id == self.session_id,
                Location.location_key == location_key,
            )
            .first()
        )

    def create_location(
        self,
        location_key: str,
        display_name: str,
        description: str,
        category: str | None = None,
        parent_key: str | None = None,
        **kwargs,
    ) -> Location:
        """Create a new location.

        Args:
            location_key: Unique key for the location.
            display_name: Display name.
            description: Full description.
            category: Optional category (city, building, room, etc.).
            parent_key: Optional parent location key.
            **kwargs: Additional fields (atmosphere, typical_crowd, etc.)

        Returns:
            Created Location.
        """
        parent_id = None
        if parent_key is not None:
            parent = self.get_location(parent_key)
            if parent is not None:
                parent_id = parent.id

        location = Location(
            session_id=self.session_id,
            location_key=location_key,
            display_name=display_name,
            description=description,
            category=category,
            parent_location_id=parent_id,
            is_accessible=True,
            **kwargs,
        )
        self.db.add(location)
        self.db.flush()
        return location

    def update_location(self, location_key: str, **updates) -> Location:
        """Update location properties.

        Args:
            location_key: Location key.
            **updates: Fields to update.

        Returns:
            Updated Location.

        Raises:
            ValueError: If location not found.
        """
        location = self.get_location(location_key)
        if location is None:
            raise ValueError(f"Location not found: {location_key}")

        for key, value in updates.items():
            setattr(location, key, value)

        self.db.flush()
        return location

    def get_parent_location(self, location_key: str) -> Location | None:
        """Get parent of a location.

        Args:
            location_key: Location key.

        Returns:
            Parent Location if exists, None otherwise.
        """
        location = self.get_location(location_key)
        if location is None or location.parent_location_id is None:
            return None

        return (
            self.db.query(Location)
            .filter(Location.id == location.parent_location_id)
            .first()
        )

    def get_child_locations(self, location_key: str) -> list[Location]:
        """Get all child locations.

        Args:
            location_key: Parent location key.

        Returns:
            List of child Locations.
        """
        parent = self.get_location(location_key)
        if parent is None:
            return []

        return (
            self.db.query(Location)
            .filter(
                Location.session_id == self.session_id,
                Location.parent_location_id == parent.id,
            )
            .all()
        )

    def get_location_chain(self, location_key: str) -> list[Location]:
        """Get full hierarchy from root to this location.

        Args:
            location_key: Target location key.

        Returns:
            List of Locations from root to target (inclusive).
        """
        location = self.get_location(location_key)
        if location is None:
            return []

        chain = [location]
        current = location

        while current.parent_location_id is not None:
            parent = (
                self.db.query(Location)
                .filter(Location.id == current.parent_location_id)
                .first()
            )
            if parent is None:
                break
            chain.insert(0, parent)
            current = parent

        return chain

    def record_visit(self, location_key: str) -> Location:
        """Record a player visit to a location.

        On first visit:
        - Sets first_visited_turn
        - Locks canonical_description from current description

        On all visits:
        - Updates last_visited_turn

        Args:
            location_key: Location key.

        Returns:
            Updated Location.

        Raises:
            ValueError: If location not found.
        """
        location = self.get_location(location_key)
        if location is None:
            raise ValueError(f"Location not found: {location_key}")

        # First visit
        if location.first_visited_turn is None:
            location.first_visited_turn = self.current_turn
            location.canonical_description = location.description

        # All visits
        location.last_visited_turn = self.current_turn

        self.db.flush()
        return location

    def update_state(
        self,
        location_key: str,
        state_notes: str,
        reason: str,
    ) -> Location:
        """Update location state and add to history.

        Args:
            location_key: Location key.
            state_notes: New state notes.
            reason: Reason for the change.

        Returns:
            Updated Location.

        Raises:
            ValueError: If location not found.
        """
        location = self.get_location(location_key)
        if location is None:
            raise ValueError(f"Location not found: {location_key}")

        # Update current state
        location.current_state_notes = state_notes

        # Add to history
        history_entry = {
            "turn": self.current_turn,
            "change": state_notes,
            "reason": reason,
        }

        if location.state_history is None:
            location.state_history = [history_entry]
        else:
            # SQLAlchemy needs a new list to detect the change
            location.state_history = location.state_history + [history_entry]

        self.db.flush()
        return location

    def get_accessible_locations(self, from_location_key: str) -> list[Location]:
        """Get locations accessible from current location.

        Uses spatial_layout["exits"] to determine connections.

        Args:
            from_location_key: Current location key.

        Returns:
            List of accessible Locations.
        """
        location = self.get_location(from_location_key)
        if location is None or location.spatial_layout is None:
            return []

        exits = location.spatial_layout.get("exits", [])
        if not exits:
            return []

        return (
            self.db.query(Location)
            .filter(
                Location.session_id == self.session_id,
                Location.location_key.in_(exits),
                Location.is_accessible == True,
            )
            .all()
        )

    def set_accessibility(
        self,
        location_key: str,
        accessible: bool,
        requirements: str | None = None,
    ) -> Location:
        """Update location accessibility.

        Args:
            location_key: Location key.
            accessible: Whether the location is accessible.
            requirements: Optional requirements description.

        Returns:
            Updated Location.

        Raises:
            ValueError: If location not found.
        """
        location = self.get_location(location_key)
        if location is None:
            raise ValueError(f"Location not found: {location_key}")

        location.is_accessible = accessible
        if requirements is not None:
            location.access_requirements = requirements

        self.db.flush()
        return location

    def get_storage_at_location(self, location_key: str) -> list[StorageLocation]:
        """Get all storage locations at a world location.

        Args:
            location_key: World location key.

        Returns:
            List of StorageLocations at the location.
        """
        # First find the location ID
        location = self.get_location(location_key)
        if location is None:
            return []

        return (
            self.db.query(StorageLocation)
            .filter(
                StorageLocation.session_id == self.session_id,
                StorageLocation.world_location_id == location.id,
            )
            .all()
        )
