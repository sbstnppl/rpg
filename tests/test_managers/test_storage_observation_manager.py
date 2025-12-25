"""Tests for StorageObservationManager class."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.enums import StorageLocationType
from src.database.models.session import GameSession
from src.database.models.world import StorageObservation
from src.managers.storage_observation_manager import StorageObservationManager
from tests.factories import (
    create_entity,
    create_storage_location,
)


class TestStorageObservationManagerRecordObservation:
    """Tests for recording storage observations."""

    def test_record_observation_creates_record(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify record_observation creates a new observation record."""
        player = create_entity(db_session, game_session, entity_key="player")
        storage = create_storage_location(
            db_session, game_session,
            location_key="chest_01",
            location_type=StorageLocationType.CONTAINER,
        )
        manager = StorageObservationManager(db_session, game_session)

        result = manager.record_observation(
            observer_id=player.id,
            storage_location_id=storage.id,
            contents=["sword_01", "potion_01"],
            turn=5,
            game_day=1,
            game_time="10:30",
        )

        assert result is not None
        assert result.observer_id == player.id
        assert result.storage_location_id == storage.id
        assert result.contents_snapshot == ["sword_01", "potion_01"]
        assert result.observed_at_turn == 5
        assert result.observed_at_game_day == 1
        assert result.observed_at_game_time == "10:30"

    def test_record_observation_is_idempotent(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify recording same observation twice returns existing record."""
        player = create_entity(db_session, game_session, entity_key="player")
        storage = create_storage_location(
            db_session, game_session,
            location_key="chest_01",
            location_type=StorageLocationType.CONTAINER,
        )
        manager = StorageObservationManager(db_session, game_session)

        # First observation
        first = manager.record_observation(
            observer_id=player.id,
            storage_location_id=storage.id,
            contents=["sword_01"],
            turn=5,
            game_day=1,
        )

        # Second observation with different contents - should return existing
        second = manager.record_observation(
            observer_id=player.id,
            storage_location_id=storage.id,
            contents=["sword_01", "armor_01"],  # Different contents
            turn=10,  # Different turn
            game_day=2,  # Different day
        )

        assert first.id == second.id
        # Original observation is preserved
        assert second.contents_snapshot == ["sword_01"]
        assert second.observed_at_turn == 5

    def test_record_observation_with_empty_contents(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify observation works with empty container."""
        player = create_entity(db_session, game_session, entity_key="player")
        storage = create_storage_location(
            db_session, game_session,
            location_key="empty_chest",
            location_type=StorageLocationType.CONTAINER,
        )
        manager = StorageObservationManager(db_session, game_session)

        result = manager.record_observation(
            observer_id=player.id,
            storage_location_id=storage.id,
            contents=[],
            turn=1,
            game_day=1,
        )

        assert result.contents_snapshot == []


class TestStorageObservationManagerHasObserved:
    """Tests for checking observation status."""

    def test_has_observed_returns_false_if_not_observed(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify has_observed returns False for unobserved storage."""
        player = create_entity(db_session, game_session, entity_key="player")
        storage = create_storage_location(
            db_session, game_session,
            location_key="chest_01",
            location_type=StorageLocationType.CONTAINER,
        )
        manager = StorageObservationManager(db_session, game_session)

        result = manager.has_observed(player.id, storage.id)

        assert result is False

    def test_has_observed_returns_true_after_observation(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify has_observed returns True after recording observation."""
        player = create_entity(db_session, game_session, entity_key="player")
        storage = create_storage_location(
            db_session, game_session,
            location_key="chest_01",
            location_type=StorageLocationType.CONTAINER,
        )
        manager = StorageObservationManager(db_session, game_session)

        manager.record_observation(
            observer_id=player.id,
            storage_location_id=storage.id,
            contents=["item_01"],
            turn=1,
            game_day=1,
        )

        result = manager.has_observed(player.id, storage.id)

        assert result is True


class TestStorageObservationManagerGetObservation:
    """Tests for retrieving observations."""

    def test_get_observation_returns_none_if_not_observed(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_observation returns None for unobserved storage."""
        player = create_entity(db_session, game_session, entity_key="player")
        storage = create_storage_location(
            db_session, game_session,
            location_key="chest_01",
            location_type=StorageLocationType.CONTAINER,
        )
        manager = StorageObservationManager(db_session, game_session)

        result = manager.get_observation(player.id, storage.id)

        assert result is None

    def test_get_observation_returns_record_after_observation(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_observation returns the observation record."""
        player = create_entity(db_session, game_session, entity_key="player")
        storage = create_storage_location(
            db_session, game_session,
            location_key="chest_01",
            location_type=StorageLocationType.CONTAINER,
        )
        manager = StorageObservationManager(db_session, game_session)

        manager.record_observation(
            observer_id=player.id,
            storage_location_id=storage.id,
            contents=["sword_01", "shield_01"],
            turn=5,
            game_day=2,
            game_time="14:00",
        )

        result = manager.get_observation(player.id, storage.id)

        assert result is not None
        assert result.contents_snapshot == ["sword_01", "shield_01"]
        assert result.observed_at_turn == 5


class TestStorageObservationManagerGetObservationContext:
    """Tests for getting observation context for GM."""

    def test_get_observation_context_first_time(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify context indicates first-time observation."""
        player = create_entity(db_session, game_session, entity_key="player")
        storage = create_storage_location(
            db_session, game_session,
            location_key="chest_01",
            location_type=StorageLocationType.CONTAINER,
        )
        manager = StorageObservationManager(db_session, game_session)

        result = manager.get_observation_context(player.id, storage.id)

        assert result["first_time"] is True
        assert result["original_contents"] is None
        assert result["observed_at_turn"] is None

    def test_get_observation_context_revisit(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify context indicates revisit with original contents."""
        player = create_entity(db_session, game_session, entity_key="player")
        storage = create_storage_location(
            db_session, game_session,
            location_key="chest_01",
            location_type=StorageLocationType.CONTAINER,
        )
        manager = StorageObservationManager(db_session, game_session)

        manager.record_observation(
            observer_id=player.id,
            storage_location_id=storage.id,
            contents=["sword_01", "potion_01"],
            turn=5,
            game_day=1,
        )

        result = manager.get_observation_context(player.id, storage.id)

        assert result["first_time"] is False
        assert result["original_contents"] == ["sword_01", "potion_01"]
        assert result["observed_at_turn"] == 5


class TestStorageObservationManagerSessionIsolation:
    """Tests for session isolation."""

    def test_observations_are_session_isolated(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify observations in one session don't affect another."""
        # Create another session
        from tests.factories import create_game_session
        other_session = create_game_session(db_session)

        player1 = create_entity(db_session, game_session, entity_key="player1")
        player2 = create_entity(db_session, other_session, entity_key="player2")

        storage1 = create_storage_location(
            db_session, game_session,
            location_key="chest_01",
            location_type=StorageLocationType.CONTAINER,
        )
        storage2 = create_storage_location(
            db_session, other_session,
            location_key="chest_01",  # Same key but different session
            location_type=StorageLocationType.CONTAINER,
        )

        manager1 = StorageObservationManager(db_session, game_session)
        manager2 = StorageObservationManager(db_session, other_session)

        # Record in first session
        manager1.record_observation(
            observer_id=player1.id,
            storage_location_id=storage1.id,
            contents=["item_01"],
            turn=1,
            game_day=1,
        )

        # Second session should not see it
        assert manager1.has_observed(player1.id, storage1.id) is True
        assert manager2.has_observed(player2.id, storage2.id) is False


class TestStorageObservationManagerGetStoragesByLocation:
    """Tests for getting storages at a location with observation status."""

    def test_get_storages_at_location_with_observation_status(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify we can get all storages at a location with first_time flags."""
        from tests.factories import create_location

        player = create_entity(db_session, game_session, entity_key="player")
        location = create_location(
            db_session, game_session, location_key="cottage"
        )

        # Create two storage containers at the location
        chest = create_storage_location(
            db_session, game_session,
            location_key="bedroom_chest",
            location_type=StorageLocationType.PLACE,
            world_location_id=location.id,
        )
        wardrobe = create_storage_location(
            db_session, game_session,
            location_key="wardrobe",
            location_type=StorageLocationType.PLACE,
            world_location_id=location.id,
        )

        manager = StorageObservationManager(db_session, game_session)

        # Observe only the chest
        manager.record_observation(
            observer_id=player.id,
            storage_location_id=chest.id,
            contents=["clothes_01"],
            turn=1,
            game_day=1,
        )

        result = manager.get_storages_at_location_with_status(
            observer_id=player.id,
            location_id=location.id,
        )

        assert len(result) == 2

        # Find chest and wardrobe in results
        chest_result = next(r for r in result if r["storage_key"] == "bedroom_chest")
        wardrobe_result = next(r for r in result if r["storage_key"] == "wardrobe")

        assert chest_result["first_time"] is False
        assert chest_result["original_contents"] == ["clothes_01"]

        assert wardrobe_result["first_time"] is True
        assert wardrobe_result["original_contents"] is None
