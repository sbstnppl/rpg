"""Tests for LocationManager class."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.enums import StorageLocationType
from src.database.models.session import GameSession
from src.database.models.world import Location
from src.managers.location_manager import LocationManager
from src.database.models.enums import EntityType
from tests.factories import (
    create_location,
    create_storage_location,
    create_entity,
    create_npc_extension,
    create_item,
)


class TestLocationManagerBasics:
    """Tests for LocationManager basic operations."""

    def test_get_location_returns_none_when_missing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_location returns None when location doesn't exist."""
        manager = LocationManager(db_session, game_session)

        result = manager.get_location("nonexistent")

        assert result is None

    def test_get_location_returns_existing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_location returns existing location by key."""
        location = create_location(
            db_session, game_session,
            location_key="tavern",
            display_name="The Golden Goose"
        )
        manager = LocationManager(db_session, game_session)

        result = manager.get_location("tavern")

        assert result is not None
        assert result.id == location.id
        assert result.display_name == "The Golden Goose"

    def test_create_location_basic(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify create_location creates new location."""
        manager = LocationManager(db_session, game_session)

        result = manager.create_location(
            location_key="market",
            display_name="Town Market",
            description="A bustling market square.",
        )

        assert result is not None
        assert result.location_key == "market"
        assert result.display_name == "Town Market"
        assert result.description == "A bustling market square."
        assert result.session_id == game_session.id
        assert result.is_accessible is True

    def test_create_location_with_category(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify create_location can set category."""
        manager = LocationManager(db_session, game_session)

        result = manager.create_location(
            location_key="castle",
            display_name="Royal Castle",
            description="A grand castle.",
            category="building",
        )

        assert result.category == "building"

    def test_create_location_with_parent(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify create_location can set parent location."""
        parent = create_location(
            db_session, game_session,
            location_key="city",
            display_name="The Great City"
        )
        manager = LocationManager(db_session, game_session)

        result = manager.create_location(
            location_key="city_square",
            display_name="City Square",
            description="The central square.",
            parent_key="city",
        )

        assert result.parent_location_id == parent.id

    def test_update_location(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify update_location updates location properties."""
        create_location(
            db_session, game_session,
            location_key="shop",
            display_name="Old Shop",
            is_accessible=True
        )
        manager = LocationManager(db_session, game_session)

        result = manager.update_location(
            "shop",
            display_name="Renovated Shop",
            atmosphere="Clean and inviting"
        )

        assert result.display_name == "Renovated Shop"
        assert result.atmosphere == "Clean and inviting"


class TestLocationManagerHierarchy:
    """Tests for location hierarchy operations."""

    def test_get_parent_location(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_parent_location returns parent."""
        parent = create_location(
            db_session, game_session,
            location_key="building"
        )
        child = create_location(
            db_session, game_session,
            location_key="room",
            parent_location_id=parent.id
        )
        manager = LocationManager(db_session, game_session)

        result = manager.get_parent_location("room")

        assert result is not None
        assert result.id == parent.id

    def test_get_parent_location_returns_none_for_root(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_parent_location returns None for root location."""
        create_location(db_session, game_session, location_key="root")
        manager = LocationManager(db_session, game_session)

        result = manager.get_parent_location("root")

        assert result is None

    def test_get_child_locations(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_child_locations returns all children."""
        parent = create_location(
            db_session, game_session,
            location_key="tavern"
        )
        child1 = create_location(
            db_session, game_session,
            location_key="main_room",
            parent_location_id=parent.id
        )
        child2 = create_location(
            db_session, game_session,
            location_key="kitchen",
            parent_location_id=parent.id
        )
        # Unrelated location
        create_location(db_session, game_session, location_key="other")
        manager = LocationManager(db_session, game_session)

        result = manager.get_child_locations("tavern")

        assert len(result) == 2
        keys = [loc.location_key for loc in result]
        assert "main_room" in keys
        assert "kitchen" in keys

    def test_get_location_chain_single(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_location_chain returns single location for root."""
        create_location(db_session, game_session, location_key="root")
        manager = LocationManager(db_session, game_session)

        result = manager.get_location_chain("root")

        assert len(result) == 1
        assert result[0].location_key == "root"

    def test_get_location_chain_hierarchy(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_location_chain returns full path from root to leaf."""
        city = create_location(db_session, game_session, location_key="city")
        district = create_location(
            db_session, game_session,
            location_key="district",
            parent_location_id=city.id
        )
        building = create_location(
            db_session, game_session,
            location_key="building",
            parent_location_id=district.id
        )
        room = create_location(
            db_session, game_session,
            location_key="room",
            parent_location_id=building.id
        )
        manager = LocationManager(db_session, game_session)

        result = manager.get_location_chain("room")

        assert len(result) == 4
        keys = [loc.location_key for loc in result]
        assert keys == ["city", "district", "building", "room"]


class TestLocationManagerVisits:
    """Tests for visit tracking."""

    def test_record_visit_sets_first_visited_turn(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify record_visit sets first_visited_turn on first visit."""
        create_location(db_session, game_session, location_key="new_place")
        manager = LocationManager(db_session, game_session)

        result = manager.record_visit("new_place")

        assert result.first_visited_turn == game_session.total_turns

    def test_record_visit_locks_canonical_description(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify record_visit saves canonical_description on first visit."""
        create_location(
            db_session, game_session,
            location_key="temple",
            description="A sacred temple with golden spires."
        )
        manager = LocationManager(db_session, game_session)

        result = manager.record_visit("temple")

        assert result.canonical_description == "A sacred temple with golden spires."

    def test_record_visit_updates_last_visited(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify record_visit updates last_visited_turn on subsequent visits."""
        create_location(
            db_session, game_session,
            location_key="inn",
            first_visited_turn=1,
            canonical_description="An old inn.",
            last_visited_turn=1
        )
        game_session.total_turns = 5
        manager = LocationManager(db_session, game_session)

        result = manager.record_visit("inn")

        # First visit should not be updated
        assert result.first_visited_turn == 1
        # But last visited should be updated
        assert result.last_visited_turn == 5

    def test_record_visit_does_not_overwrite_canonical(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify record_visit doesn't overwrite existing canonical_description."""
        create_location(
            db_session, game_session,
            location_key="library",
            description="Updated description",
            first_visited_turn=1,
            canonical_description="Original canonical description."
        )
        manager = LocationManager(db_session, game_session)

        result = manager.record_visit("library")

        assert result.canonical_description == "Original canonical description."


class TestLocationManagerState:
    """Tests for location state management."""

    def test_update_state_adds_history_entry(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify update_state updates notes and adds to history."""
        create_location(db_session, game_session, location_key="bridge")
        manager = LocationManager(db_session, game_session)

        result = manager.update_state(
            "bridge",
            state_notes="The bridge is damaged.",
            reason="A storm hit the area."
        )

        assert result.current_state_notes == "The bridge is damaged."
        assert result.state_history is not None
        assert len(result.state_history) == 1
        assert result.state_history[0]["change"] == "The bridge is damaged."
        assert result.state_history[0]["reason"] == "A storm hit the area."

    def test_update_state_appends_to_existing_history(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify update_state appends to existing history."""
        create_location(
            db_session, game_session,
            location_key="tower",
            state_history=[{"turn": 1, "change": "Built", "reason": "Construction"}]
        )
        manager = LocationManager(db_session, game_session)

        result = manager.update_state(
            "tower",
            state_notes="Tower is on fire!",
            reason="Dragon attack"
        )

        assert len(result.state_history) == 2
        assert result.state_history[1]["change"] == "Tower is on fire!"


class TestLocationManagerAccessibility:
    """Tests for accessibility management."""

    def test_set_accessibility_updates_status(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify set_accessibility updates is_accessible."""
        create_location(
            db_session, game_session,
            location_key="dungeon",
            is_accessible=True
        )
        manager = LocationManager(db_session, game_session)

        result = manager.set_accessibility("dungeon", accessible=False)

        assert result.is_accessible is False

    def test_set_accessibility_with_requirements(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify set_accessibility can set requirements."""
        create_location(
            db_session, game_session,
            location_key="vault",
            is_accessible=True
        )
        manager = LocationManager(db_session, game_session)

        result = manager.set_accessibility(
            "vault",
            accessible=False,
            requirements="Requires golden key"
        )

        assert result.is_accessible is False
        assert result.access_requirements == "Requires golden key"

    def test_get_accessible_locations(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_accessible_locations returns connected locations."""
        main = create_location(
            db_session, game_session,
            location_key="main_hall",
            spatial_layout={"exits": ["garden", "kitchen", "locked_room"]}
        )
        garden = create_location(
            db_session, game_session,
            location_key="garden",
            is_accessible=True
        )
        kitchen = create_location(
            db_session, game_session,
            location_key="kitchen",
            is_accessible=True
        )
        locked = create_location(
            db_session, game_session,
            location_key="locked_room",
            is_accessible=False
        )
        manager = LocationManager(db_session, game_session)

        result = manager.get_accessible_locations("main_hall")

        # Should only return accessible connected locations
        assert len(result) == 2
        keys = [loc.location_key for loc in result]
        assert "garden" in keys
        assert "kitchen" in keys
        assert "locked_room" not in keys


class TestLocationManagerStorage:
    """Tests for storage location queries."""

    def test_get_storage_at_location(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_storage_at_location returns storage locations."""
        # Create world locations first
        tavern = create_location(
            db_session, game_session,
            location_key="tavern_room"
        )
        other = create_location(
            db_session, game_session,
            location_key="other_room"
        )

        # Create storage locations at world locations
        create_storage_location(
            db_session, game_session,
            location_key="chest1",
            world_location_id=tavern.id,
            location_type=StorageLocationType.CONTAINER
        )
        create_storage_location(
            db_session, game_session,
            location_key="chest2",
            world_location_id=tavern.id,
            location_type=StorageLocationType.CONTAINER
        )
        # Storage in different location
        create_storage_location(
            db_session, game_session,
            location_key="other_chest",
            world_location_id=other.id,
            location_type=StorageLocationType.CONTAINER
        )
        manager = LocationManager(db_session, game_session)

        result = manager.get_storage_at_location("tavern_room")

        assert len(result) == 2
        keys = [s.location_key for s in result]
        assert "chest1" in keys
        assert "chest2" in keys


class TestLocationManagerSublocation:
    """Tests for sublocation operations."""

    def test_get_sublocation_returns_child(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_sublocation returns specific child location."""
        parent = create_location(
            db_session, game_session,
            location_key="tavern"
        )
        child = create_location(
            db_session, game_session,
            location_key="cellar",
            parent_location_id=parent.id
        )
        manager = LocationManager(db_session, game_session)

        result = manager.get_sublocation("tavern", "cellar")

        assert result is not None
        assert result.id == child.id

    def test_get_sublocation_returns_none_when_not_child(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_sublocation returns None when not a child."""
        parent = create_location(
            db_session, game_session,
            location_key="tavern"
        )
        # Location that is NOT a child of parent
        create_location(
            db_session, game_session,
            location_key="market"
        )
        manager = LocationManager(db_session, game_session)

        result = manager.get_sublocation("tavern", "market")

        assert result is None

    def test_get_sublocations_returns_all_children(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_sublocations returns all children."""
        parent = create_location(
            db_session, game_session,
            location_key="building"
        )
        create_location(
            db_session, game_session,
            location_key="room1",
            parent_location_id=parent.id
        )
        create_location(
            db_session, game_session,
            location_key="room2",
            parent_location_id=parent.id
        )
        manager = LocationManager(db_session, game_session)

        result = manager.get_sublocations("building")

        assert len(result) == 2
        keys = [loc.location_key for loc in result]
        assert "room1" in keys
        assert "room2" in keys


class TestLocationManagerEntityAndItemQueries:
    """Tests for get_entities_at_location and get_items_at_location."""

    def test_get_entities_at_location_returns_entities(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_entities_at_location delegates to EntityManager."""
        create_location(
            db_session, game_session,
            location_key="tavern"
        )
        entity = create_entity(db_session, game_session, entity_key="bartender")
        create_npc_extension(db_session, entity, current_location="tavern")
        manager = LocationManager(db_session, game_session)

        result = manager.get_entities_at_location("tavern")

        assert len(result) == 1
        assert result[0].entity_key == "bartender"

    def test_get_items_at_location_returns_items(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_items_at_location delegates to ItemManager."""
        location = create_location(
            db_session, game_session,
            location_key="tavern"
        )
        storage = create_storage_location(
            db_session, game_session,
            location_key="tavern_floor",
            location_type=StorageLocationType.PLACE,
            world_location_id=location.id
        )
        create_item(
            db_session, game_session,
            item_key="mug",
            storage_location_id=storage.id,
            holder_id=None
        )
        manager = LocationManager(db_session, game_session)

        result = manager.get_items_at_location("tavern")

        assert len(result) == 1
        assert result[0].item_key == "mug"


class TestLocationManagerSetPlayerLocation:
    """Tests for set_player_location."""

    def test_set_player_location_updates_player(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify set_player_location updates player's location."""
        create_location(
            db_session, game_session,
            location_key="tavern"
        )
        player = create_entity(
            db_session, game_session,
            entity_key="hero",
            entity_type=EntityType.PLAYER
        )
        create_npc_extension(db_session, player, current_location="start")
        manager = LocationManager(db_session, game_session)

        manager.set_player_location("tavern")

        # Refresh to get updated value
        db_session.refresh(player)
        assert player.npc_extension.current_location == "tavern"

    def test_set_player_location_raises_when_no_player(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify set_player_location raises when no player exists."""
        create_location(
            db_session, game_session,
            location_key="tavern"
        )
        manager = LocationManager(db_session, game_session)

        with pytest.raises(ValueError, match="No player entity found"):
            manager.set_player_location("tavern")

    def test_set_player_location_raises_when_location_missing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify set_player_location raises when location doesn't exist."""
        create_entity(
            db_session, game_session,
            entity_key="hero",
            entity_type=EntityType.PLAYER
        )
        manager = LocationManager(db_session, game_session)

        with pytest.raises(ValueError, match="Location not found"):
            manager.set_player_location("nonexistent")
