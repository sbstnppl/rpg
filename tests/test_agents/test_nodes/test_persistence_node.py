"""Tests for persistence_node."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from src.agents.state import create_initial_state, GameState
from src.agents.nodes.persistence_node import (
    persistence_node,
    create_persistence_node,
)


@pytest.fixture
def state_with_extractions(db_session, game_session, player_entity):
    """Create state with extraction results."""
    state = create_initial_state(
        session_id=game_session.id,
        player_id=player_entity.id,
        player_location="tavern",
        player_input="Talk to the bartender",
    )
    state["gm_response"] = "You approach the friendly bartender, Bob."
    state["extracted_entities"] = [
        {
            "entity_key": "bartender_bob",
            "display_name": "Bob",
            "entity_type": "npc",
            "description": "A friendly bartender",
        }
    ]
    state["extracted_facts"] = [
        {
            "subject": "bartender_bob",
            "predicate": "occupation",
            "value": "bartender",
        }
    ]
    state["relationship_changes"] = [
        {
            "entity_key": "bartender_bob",
            "dimension": "familiarity",
            "change": 5,
            "reason": "First meeting",
        }
    ]
    return state


class TestPersistenceNodeFactory:
    """Test the node factory function."""

    def test_factory_creates_callable(self, db_session, game_session):
        """Factory should return an async callable."""
        node = create_persistence_node(db_session, game_session)
        assert callable(node)


class TestPersistenceNode:
    """Test the persistence_node function."""

    @pytest.mark.asyncio
    async def test_persists_extracted_entities(
        self, db_session, game_session, player_entity, state_with_extractions
    ):
        """Should call EntityManager for extracted entities."""
        node = create_persistence_node(db_session, game_session)

        with patch(
            "src.agents.nodes.persistence_node.EntityManager"
        ) as MockEntityManager:
            mock_manager = MagicMock()
            # get_entity returns None so entity doesn't exist by key
            mock_manager.get_entity.return_value = None
            # get_entity_by_display_name returns None so entity doesn't exist by name
            mock_manager.get_entity_by_display_name.return_value = None
            mock_manager.create_entity.return_value = MagicMock(id=100)
            MockEntityManager.return_value = mock_manager

            await node(state_with_extractions)

            # Should have called create_entity since entity doesn't exist
            mock_manager.create_entity.assert_called()

    @pytest.mark.asyncio
    async def test_persists_extracted_facts(
        self, db_session, game_session, player_entity, state_with_extractions
    ):
        """Should call FactManager for extracted facts."""
        node = create_persistence_node(db_session, game_session)

        with patch(
            "src.agents.nodes.persistence_node.FactManager"
        ) as MockFactManager:
            mock_manager = MagicMock()
            MockFactManager.return_value = mock_manager

            await node(state_with_extractions)

            mock_manager.record_fact.assert_called()

    @pytest.mark.asyncio
    async def test_returns_empty_update(
        self, db_session, game_session, player_entity
    ):
        """Should return minimal state update."""
        node = create_persistence_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Look around",
        )
        state["gm_response"] = "You see nothing special."

        result = await node(state)

        # Should not add errors for empty extractions
        assert "errors" not in result or len(result.get("errors", [])) == 0

    @pytest.mark.asyncio
    async def test_handles_empty_extractions(
        self, db_session, game_session, player_entity
    ):
        """Should handle state with no extractions gracefully."""
        node = create_persistence_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Look around",
        )

        result = await node(state)

        # Should complete without errors
        assert result is not None


class TestPersistenceNodeIntegration:
    """Integration tests with actual database."""

    @pytest.mark.asyncio
    async def test_creates_turn_record(
        self, db_session, game_session, player_entity
    ):
        """Should create Turn record in database."""
        from src.database.models.session import Turn

        node = create_persistence_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Test input",
        )
        state["gm_response"] = "Test response"

        initial_turn_count = (
            db_session.query(Turn)
            .filter(Turn.session_id == game_session.id)
            .count()
        )

        await node(state)

        new_turn_count = (
            db_session.query(Turn)
            .filter(Turn.session_id == game_session.id)
            .count()
        )

        assert new_turn_count == initial_turn_count + 1

    @pytest.mark.asyncio
    async def test_turn_contains_input_and_response(
        self, db_session, game_session, player_entity
    ):
        """Turn record should contain player input and GM response."""
        from src.database.models.session import Turn

        node = create_persistence_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Hello there!",
        )
        state["gm_response"] = "A voice echoes in the darkness."

        await node(state)

        turn = (
            db_session.query(Turn)
            .filter(Turn.session_id == game_session.id)
            .order_by(Turn.turn_number.desc())
            .first()
        )

        assert turn is not None
        assert turn.player_input == "Hello there!"
        assert turn.gm_response == "A voice echoes in the darkness."


class TestPersistenceNodeWithDefaultFunction:
    """Test the default persistence_node when db/session in state."""

    @pytest.mark.asyncio
    async def test_default_node_extracts_from_state(
        self, db_session, game_session, player_entity
    ):
        """Default node should work with db/game_session in state."""
        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Look around",
        )
        state["gm_response"] = "You see a cozy tavern."
        state["_db"] = db_session
        state["_game_session"] = game_session

        result = await persistence_node(state)

        # Should complete without errors
        assert result is not None


class TestPersistenceNodeAutoStorage:
    """Tests for automatic storage creation during persistence."""

    @pytest.mark.asyncio
    async def test_creates_body_storage_for_new_entity(
        self, db_session, game_session, player_entity
    ):
        """Should auto-create ON_PERSON storage when entity is persisted."""
        from src.database.models.items import StorageLocation
        from src.database.models.entities import Entity

        node = create_persistence_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Talk to the innkeeper",
        )
        state["gm_response"] = "You see Martha the innkeeper."
        state["extracted_entities"] = [
            {
                "entity_key": "innkeeper_martha",
                "display_name": "Martha",
                "entity_type": "npc",
                # Note: description field causes error - Entity doesn't have it
            }
        ]

        await node(state)

        # Verify entity was created
        entity = (
            db_session.query(Entity)
            .filter(
                Entity.session_id == game_session.id,
                Entity.entity_key == "innkeeper_martha",
            )
            .first()
        )
        assert entity is not None

        # Verify ON_PERSON storage was auto-created
        body_storage = (
            db_session.query(StorageLocation)
            .filter(
                StorageLocation.session_id == game_session.id,
                StorageLocation.owner_entity_id == entity.id,
            )
            .first()
        )
        assert body_storage is not None, "Body storage should be auto-created for entity"
        assert body_storage.location_type.value == "on_person"

    @pytest.mark.asyncio
    async def test_creates_container_storage_for_container_item(
        self, db_session, game_session, player_entity
    ):
        """Should auto-create linked storage when container item is persisted."""
        from src.database.models.items import Item, StorageLocation

        node = create_persistence_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="market",
            player_input="Buy a backpack",
        )
        state["gm_response"] = "You buy a sturdy leather backpack."
        state["extracted_items"] = [
            {
                "item_key": "player_backpack",
                "display_name": "Leather Backpack",
                "item_type": "container",
                "action": "acquired",
            }
        ]

        await node(state)

        # Verify item was created
        item = (
            db_session.query(Item)
            .filter(
                Item.session_id == game_session.id,
                Item.item_key == "player_backpack",
            )
            .first()
        )
        assert item is not None

        # Verify container storage was auto-created and linked
        container_storage = (
            db_session.query(StorageLocation)
            .filter(
                StorageLocation.session_id == game_session.id,
                StorageLocation.container_item_id == item.id,
            )
            .first()
        )
        assert container_storage is not None, "Container storage should be auto-created"
        assert container_storage.location_type.value == "container"

    @pytest.mark.asyncio
    async def test_creates_location_from_extraction(
        self, db_session, game_session, player_entity
    ):
        """Should create Location when extracted_locations contains new location."""
        from src.database.models.world import Location

        node = create_persistence_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="forest_clearing",
            player_input="Look for shelter",
        )
        state["gm_response"] = "You find the Weary Traveler inn."
        state["extracted_locations"] = [
            {
                "location_key": "weary_traveler_inn",
                "display_name": "The Weary Traveler Inn",
                "category": "establishment",
                "description": "A cozy roadside inn with warm lights glowing in the windows.",
            }
        ]

        await node(state)

        # Verify location was created
        location = (
            db_session.query(Location)
            .filter(
                Location.session_id == game_session.id,
                Location.location_key == "weary_traveler_inn",
            )
            .first()
        )
        assert location is not None, "Location should be created from extraction"
        assert location.display_name == "The Weary Traveler Inn"
        assert location.category == "establishment"
        assert "cozy roadside inn" in location.description

    @pytest.mark.asyncio
    async def test_creates_location_with_parent(
        self, db_session, game_session, player_entity
    ):
        """Should link location to parent when parent_location_key provided."""
        from src.database.models.world import Location

        # First create the parent location
        from src.managers.location_manager import LocationManager

        loc_manager = LocationManager(db_session, game_session)
        parent = loc_manager.create_location(
            location_key="weary_traveler_inn",
            display_name="The Weary Traveler Inn",
            description="A roadside inn",
            category="establishment",
        )

        node = create_persistence_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="weary_traveler_inn",
            player_input="Go to the common room",
        )
        state["gm_response"] = "You enter the busy common room."
        state["extracted_locations"] = [
            {
                "location_key": "inn_common_room",
                "display_name": "Common Room",
                "category": "interior",
                "description": "A warm room with a crackling fireplace.",
                "parent_location_key": "weary_traveler_inn",
            }
        ]

        await node(state)

        # Verify child location was created with parent link
        child = (
            db_session.query(Location)
            .filter(
                Location.session_id == game_session.id,
                Location.location_key == "inn_common_room",
            )
            .first()
        )
        assert child is not None
        assert child.parent_location_id == parent.id

    @pytest.mark.asyncio
    async def test_skips_duplicate_location_by_key(
        self, db_session, game_session, player_entity
    ):
        """Should not create duplicate location when key already exists."""
        from src.database.models.world import Location
        from src.managers.location_manager import LocationManager

        # Create existing location
        loc_manager = LocationManager(db_session, game_session)
        loc_manager.create_location(
            location_key="forest_clearing",
            display_name="Forest Clearing",
            description="Original description",
            category="wilderness",
        )

        node = create_persistence_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="forest",
            player_input="Look around",
        )
        state["gm_response"] = "You see a clearing."
        state["extracted_locations"] = [
            {
                "location_key": "forest_clearing",
                "display_name": "Forest Clearing",
                "category": "wilderness",
                "description": "New description - should not overwrite",
            }
        ]

        await node(state)

        # Should still have only one location with original description
        locations = (
            db_session.query(Location)
            .filter(
                Location.session_id == game_session.id,
                Location.location_key == "forest_clearing",
            )
            .all()
        )
        assert len(locations) == 1
        assert locations[0].description == "Original description"

    @pytest.mark.asyncio
    async def test_skips_duplicate_location_by_display_name(
        self, db_session, game_session, player_entity
    ):
        """Should not create duplicate location when display_name already exists."""
        from src.database.models.world import Location
        from src.managers.location_manager import LocationManager

        # Create existing location
        loc_manager = LocationManager(db_session, game_session)
        loc_manager.create_location(
            location_key="weary_traveler",
            display_name="The Weary Traveler Inn",
            description="Original inn",
            category="establishment",
        )

        node = create_persistence_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="road",
            player_input="Look at the inn",
        )
        state["gm_response"] = "You see the Weary Traveler Inn."
        state["extracted_locations"] = [
            {
                # Different key, same display name
                "location_key": "weary_traveler_inn",
                "display_name": "The Weary Traveler Inn",
                "category": "establishment",
                "description": "Different key but same name - should skip",
            }
        ]

        await node(state)

        # Should still have only one location
        locations = (
            db_session.query(Location)
            .filter(
                Location.session_id == game_session.id,
                Location.display_name == "The Weary Traveler Inn",
            )
            .all()
        )
        assert len(locations) == 1
        assert locations[0].location_key == "weary_traveler"  # Original key


class TestTurnTimestampPopulation:
    """Tests for turn timestamp (game_day_at_turn, game_time_at_turn) population."""

    @pytest.mark.asyncio
    async def test_new_turn_gets_timestamp_from_time_state(
        self, db_session, game_session, player_entity
    ):
        """New turn should get game_day_at_turn and game_time_at_turn from TimeState."""
        from src.database.models.session import Turn
        from src.database.models.world import TimeState

        # Create TimeState for this session
        time_state = TimeState(
            session_id=game_session.id,
            current_day=3,
            current_time="14:30",
            day_of_week="Wednesday",
            season="Summer",
            weather="Sunny",
        )
        db_session.add(time_state)
        db_session.flush()

        node = create_persistence_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Look around",
        )
        state["gm_response"] = "You see a cozy tavern."

        await node(state)

        turn = (
            db_session.query(Turn)
            .filter(Turn.session_id == game_session.id)
            .order_by(Turn.turn_number.desc())
            .first()
        )

        assert turn is not None
        assert turn.game_day_at_turn == 3
        assert turn.game_time_at_turn == "14:30"

    @pytest.mark.asyncio
    async def test_turn_without_time_state_gets_null_timestamp(
        self, db_session, game_session, player_entity
    ):
        """Turn should have null timestamps if TimeState doesn't exist."""
        from src.database.models.session import Turn

        # No TimeState created for this session

        node = create_persistence_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Look around",
        )
        state["gm_response"] = "You see a cozy tavern."

        await node(state)

        turn = (
            db_session.query(Turn)
            .filter(Turn.session_id == game_session.id)
            .order_by(Turn.turn_number.desc())
            .first()
        )

        assert turn is not None
        assert turn.game_day_at_turn is None
        assert turn.game_time_at_turn is None

    @pytest.mark.asyncio
    async def test_existing_turn_gets_timestamp_if_not_set(
        self, db_session, game_session, player_entity
    ):
        """Existing turn without timestamp should get it populated."""
        from src.database.models.session import Turn
        from src.database.models.world import TimeState

        # Create TimeState
        time_state = TimeState(
            session_id=game_session.id,
            current_day=5,
            current_time="09:15",
            day_of_week="Friday",
            season="Fall",
            weather="Cloudy",
        )
        db_session.add(time_state)

        # Create existing turn without timestamp
        existing_turn = Turn(
            session_id=game_session.id,
            turn_number=1,
            player_input="Hello",
            gm_response="Hi there",
            game_day_at_turn=None,  # Explicitly null
            game_time_at_turn=None,
        )
        db_session.add(existing_turn)
        db_session.flush()

        node = create_persistence_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Hello",
        )
        state["gm_response"] = "Hi there"
        state["turn_number"] = 1  # Same turn number to trigger update path

        await node(state)

        turn = (
            db_session.query(Turn)
            .filter(
                Turn.session_id == game_session.id,
                Turn.turn_number == 1,
            )
            .first()
        )

        assert turn is not None
        assert turn.game_day_at_turn == 5
        assert turn.game_time_at_turn == "09:15"

    @pytest.mark.asyncio
    async def test_existing_turn_keeps_timestamp_if_already_set(
        self, db_session, game_session, player_entity
    ):
        """Existing turn with timestamp should not have it overwritten."""
        from src.database.models.session import Turn
        from src.database.models.world import TimeState

        # Create TimeState with different time
        time_state = TimeState(
            session_id=game_session.id,
            current_day=10,
            current_time="20:00",
            day_of_week="Sunday",
            season="Winter",
            weather="Snowy",
        )
        db_session.add(time_state)

        # Create existing turn WITH timestamp already set
        existing_turn = Turn(
            session_id=game_session.id,
            turn_number=1,
            player_input="Hello",
            gm_response="Hi there",
            game_day_at_turn=2,  # Already set
            game_time_at_turn="08:00",  # Already set
        )
        db_session.add(existing_turn)
        db_session.flush()

        node = create_persistence_node(db_session, game_session)

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="Hello",
        )
        state["gm_response"] = "Hi there"
        state["turn_number"] = 1

        await node(state)

        turn = (
            db_session.query(Turn)
            .filter(
                Turn.session_id == game_session.id,
                Turn.turn_number == 1,
            )
            .first()
        )

        # Should keep original timestamp, not update to current TimeState
        assert turn is not None
        assert turn.game_day_at_turn == 2
        assert turn.game_time_at_turn == "08:00"
