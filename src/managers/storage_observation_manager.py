"""Manager for tracking player observations of storage containers.

This manager tracks when a player first observed a storage container's contents,
enabling the GM to distinguish between first-time discovery (freely invent contents)
and revisits (reference established contents only).
"""

from sqlalchemy.orm import Session

from src.database.models.items import StorageLocation
from src.database.models.session import GameSession
from src.database.models.world import StorageObservation
from src.managers.base import BaseManager


class StorageObservationManager(BaseManager):
    """Manager for storage observation tracking.

    Provides methods to:
    - Record when a player first observes a container's contents
    - Check if a container has been observed before
    - Get observation context for GM prompts (first_time flag)
    - Get all storages at a location with observation status
    """

    def record_observation(
        self,
        observer_id: int,
        storage_location_id: int,
        contents: list[str],
        turn: int,
        game_day: int,
        game_time: str | None = None,
    ) -> StorageObservation:
        """Record first-time observation of a storage container.

        If the observer has already seen this storage, returns the existing
        observation record (idempotent behavior - first observation is preserved).

        Args:
            observer_id: ID of the observing entity (usually player)
            storage_location_id: ID of the StorageLocation being observed
            contents: List of item_keys present at observation time
            turn: Current turn number
            game_day: Current in-game day
            game_time: Current in-game time (HH:MM format, optional)

        Returns:
            The observation record (existing or newly created)
        """
        # Check for existing observation
        existing = self.get_observation(observer_id, storage_location_id)
        if existing:
            return existing

        # Create new observation
        observation = StorageObservation(
            session_id=self.session_id,
            observer_id=observer_id,
            storage_location_id=storage_location_id,
            contents_snapshot=contents,
            observed_at_turn=turn,
            observed_at_game_day=game_day,
            observed_at_game_time=game_time,
        )
        self.db.add(observation)
        self.db.flush()
        return observation

    def get_observation(
        self,
        observer_id: int,
        storage_location_id: int,
    ) -> StorageObservation | None:
        """Get existing observation if any.

        Args:
            observer_id: ID of the observing entity
            storage_location_id: ID of the StorageLocation

        Returns:
            The observation record if exists, None otherwise
        """
        return (
            self.db.query(StorageObservation)
            .filter(
                StorageObservation.session_id == self.session_id,
                StorageObservation.observer_id == observer_id,
                StorageObservation.storage_location_id == storage_location_id,
            )
            .first()
        )

    def has_observed(
        self,
        observer_id: int,
        storage_location_id: int,
    ) -> bool:
        """Check if observer has seen this storage before.

        Args:
            observer_id: ID of the observing entity
            storage_location_id: ID of the StorageLocation

        Returns:
            True if observer has seen this storage, False otherwise
        """
        return self.get_observation(observer_id, storage_location_id) is not None

    def get_observation_context(
        self,
        observer_id: int,
        storage_location_id: int,
    ) -> dict:
        """Get observation context for GM prompt.

        Returns a dict with:
        - first_time: True if this is first observation, False if revisit
        - original_contents: List of item_keys from first observation (or None)
        - observed_at_turn: Turn when first observed (or None)

        Args:
            observer_id: ID of the observing entity
            storage_location_id: ID of the StorageLocation

        Returns:
            Context dict for GM prompt
        """
        observation = self.get_observation(observer_id, storage_location_id)

        if observation is None:
            return {
                "first_time": True,
                "original_contents": None,
                "observed_at_turn": None,
            }

        return {
            "first_time": False,
            "original_contents": observation.contents_snapshot,
            "observed_at_turn": observation.observed_at_turn,
        }

    def get_storages_at_location_with_status(
        self,
        observer_id: int,
        location_id: int,
    ) -> list[dict]:
        """Get all storages at a location with observation status.

        Returns a list of dicts, each containing:
        - storage_id: ID of the StorageLocation
        - storage_key: Key of the StorageLocation
        - first_time: True if never observed, False if revisit
        - original_contents: Contents from first observation (or None)

        Args:
            observer_id: ID of the observing entity
            location_id: ID of the world Location

        Returns:
            List of storage dicts with observation status
        """
        # Get all storages at this location
        storages = (
            self.db.query(StorageLocation)
            .filter(
                StorageLocation.session_id == self.session_id,
                StorageLocation.world_location_id == location_id,
            )
            .all()
        )

        results = []
        for storage in storages:
            context = self.get_observation_context(observer_id, storage.id)
            results.append({
                "storage_id": storage.id,
                "storage_key": storage.location_key,
                "first_time": context["first_time"],
                "original_contents": context["original_contents"],
            })

        return results
