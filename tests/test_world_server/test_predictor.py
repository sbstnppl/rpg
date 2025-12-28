"""Tests for LocationPredictor."""

import pytest

from src.database.models.world import Location
from src.database.models.tasks import Task, TaskCategory
from src.database.models.entities import Entity, NPCExtension, EntityType
from src.world_server.predictor import LocationPredictor
from src.world_server.schemas import PredictionReason


class TestLocationPredictor:
    """Tests for LocationPredictor class."""

    def test_predict_adjacent_locations(self, db_session, game_session):
        """Test predicting adjacent locations from exits."""
        # Create locations with exits
        home = Location(
            session_id=game_session.id,
            location_key="home",
            display_name="Home",
            description="A cozy home",
            spatial_layout={"exits": ["street", "garden"]},
        )
        street = Location(
            session_id=game_session.id,
            location_key="street",
            display_name="Street",
            description="A quiet street",
            is_accessible=True,
        )
        garden = Location(
            session_id=game_session.id,
            location_key="garden",
            display_name="Garden",
            description="A peaceful garden",
            is_accessible=True,
        )
        db_session.add_all([home, street, garden])
        db_session.flush()

        predictor = LocationPredictor(db_session, game_session)
        predictions = predictor.predict_next_locations("home", max_predictions=5)

        assert len(predictions) == 2
        location_keys = [p.location_key for p in predictions]
        assert "street" in location_keys
        assert "garden" in location_keys

        # All should be ADJACENT reason
        assert all(p.reason == PredictionReason.ADJACENT for p in predictions)

    def test_predict_quest_target_locations(self, db_session, game_session):
        """Test predicting quest target locations."""
        # Create locations
        market = Location(
            session_id=game_session.id,
            location_key="market",
            display_name="Market Square",
            description="A bustling market square",
        )
        db_session.add(market)

        # Create active task with location target
        task = Task(
            session_id=game_session.id,
            description="Find the merchant",
            location="market",
            category=TaskCategory.QUEST,
            completed=False,
            created_turn=1,
        )
        db_session.add(task)
        db_session.flush()

        predictor = LocationPredictor(db_session, game_session)
        predictions = predictor.predict_next_locations("home", max_predictions=5)

        assert len(predictions) >= 1
        market_pred = next(
            (p for p in predictions if p.location_key == "market"),
            None
        )
        assert market_pred is not None
        assert market_pred.reason == PredictionReason.QUEST_TARGET

    def test_predict_mentioned_locations(self, db_session, game_session):
        """Test predicting locations mentioned in recent actions."""
        # Create locations
        tavern = Location(
            session_id=game_session.id,
            location_key="tavern",
            display_name="The Rusty Anchor",
            description="A popular tavern",
        )
        db_session.add(tavern)
        db_session.flush()

        predictor = LocationPredictor(db_session, game_session)
        predictions = predictor.predict_next_locations(
            "home",
            recent_actions=["Let's go to The Rusty Anchor tonight"],
            max_predictions=5,
        )

        tavern_pred = next(
            (p for p in predictions if p.location_key == "tavern"),
            None
        )
        assert tavern_pred is not None
        assert tavern_pred.reason == PredictionReason.MENTIONED

    def test_probability_boost_multiple_reasons(self, db_session, game_session):
        """Test that multiple reasons boost probability."""
        # Create location that is both adjacent AND quest target
        market = Location(
            session_id=game_session.id,
            location_key="market",
            display_name="Market Square",
            description="A bustling market",
            is_accessible=True,
        )
        home = Location(
            session_id=game_session.id,
            location_key="home",
            display_name="Home",
            description="A cozy home",
            spatial_layout={"exits": ["market"]},
        )
        db_session.add_all([market, home])

        task = Task(
            session_id=game_session.id,
            description="Buy supplies",
            location="market",
            completed=False,
            created_turn=1,
        )
        db_session.add(task)
        db_session.flush()

        predictor = LocationPredictor(db_session, game_session)
        predictions = predictor.predict_next_locations("home", max_predictions=5)

        market_pred = next(
            (p for p in predictions if p.location_key == "market"),
            None
        )
        assert market_pred is not None
        # Should be boosted above base ADJACENT probability (0.7)
        assert market_pred.probability > 0.7

    def test_predictions_sorted_by_probability(self, db_session, game_session):
        """Test that predictions are sorted by probability."""
        # Create locations with different probabilities
        loc1 = Location(
            session_id=game_session.id,
            location_key="loc1",
            display_name="Location 1",
            description="Location 1",
            is_accessible=True,
        )
        loc2 = Location(
            session_id=game_session.id,
            location_key="loc2",
            display_name="Location 2",
            description="Location 2",
            is_accessible=True,
        )
        home = Location(
            session_id=game_session.id,
            location_key="home",
            display_name="Home",
            description="A cozy home",
            spatial_layout={"exits": ["loc1", "loc2"]},
        )
        db_session.add_all([loc1, loc2, home])

        # Add quest target to loc1 to boost its probability
        task = Task(
            session_id=game_session.id,
            description="Go to loc1",
            location="loc1",
            completed=False,
            created_turn=1,
        )
        db_session.add(task)
        db_session.flush()

        predictor = LocationPredictor(db_session, game_session)
        predictions = predictor.predict_next_locations("home", max_predictions=5)

        # Should be sorted descending by probability
        for i in range(len(predictions) - 1):
            assert predictions[i].probability >= predictions[i + 1].probability

    def test_max_predictions_limit(self, db_session, game_session):
        """Test that max_predictions limits output."""
        # Create many adjacent locations
        home = Location(
            session_id=game_session.id,
            location_key="home",
            display_name="Home",
            description="A cozy home",
            spatial_layout={"exits": ["loc1", "loc2", "loc3", "loc4", "loc5"]},
        )
        db_session.add(home)

        for i in range(1, 6):
            loc = Location(
                session_id=game_session.id,
                location_key=f"loc{i}",
                display_name=f"Location {i}",
                description=f"Location {i}",
                is_accessible=True,
            )
            db_session.add(loc)
        db_session.flush()

        predictor = LocationPredictor(db_session, game_session)
        predictions = predictor.predict_next_locations("home", max_predictions=3)

        assert len(predictions) == 3

    def test_exits_as_dict(self, db_session, game_session):
        """Test handling exits as dictionary (direction -> location)."""
        home = Location(
            session_id=game_session.id,
            location_key="home",
            display_name="Home",
            description="A cozy home",
            spatial_layout={
                "exits": {
                    "north": "street",
                    "east": "garden",
                }
            },
        )
        street = Location(
            session_id=game_session.id,
            location_key="street",
            display_name="Street",
            description="A quiet street",
            is_accessible=True,
        )
        garden = Location(
            session_id=game_session.id,
            location_key="garden",
            display_name="Garden",
            description="A peaceful garden",
            is_accessible=True,
        )
        db_session.add_all([home, street, garden])
        db_session.flush()

        predictor = LocationPredictor(db_session, game_session)
        predictions = predictor.predict_next_locations("home", max_predictions=5)

        location_keys = [p.location_key for p in predictions]
        assert "street" in location_keys
        assert "garden" in location_keys

    def test_no_predictions_for_unknown_location(self, db_session, game_session):
        """Test handling unknown current location."""
        predictor = LocationPredictor(db_session, game_session)
        predictions = predictor.predict_next_locations(
            "nonexistent",
            max_predictions=5,
        )

        # Should return empty list, not crash
        assert predictions == []

    def test_player_home_prediction(self, db_session, game_session):
        """Test predicting player's home location."""
        # Create player entity with home
        player = Entity(
            session_id=game_session.id,
            entity_key="player",
            display_name="Hero",
            entity_type=EntityType.PLAYER,
        )
        db_session.add(player)
        db_session.flush()

        extension = NPCExtension(
            entity_id=player.id,
            home_location="home",
        )
        db_session.add(extension)

        home = Location(
            session_id=game_session.id,
            location_key="home",
            display_name="Home",
            description="A cozy home",
        )
        db_session.add(home)
        db_session.flush()

        predictor = LocationPredictor(db_session, game_session)
        predictions = predictor.predict_next_locations(
            "tavern",  # Not at home
            max_predictions=5,
        )

        home_pred = next(
            (p for p in predictions if p.location_key == "home"),
            None
        )
        assert home_pred is not None
        assert home_pred.reason == PredictionReason.HOME

    def test_home_not_predicted_when_already_there(self, db_session, game_session):
        """Test that home is not predicted when player is already there."""
        player = Entity(
            session_id=game_session.id,
            entity_key="player",
            display_name="Hero",
            entity_type=EntityType.PLAYER,
        )
        db_session.add(player)
        db_session.flush()

        extension = NPCExtension(
            entity_id=player.id,
            home_location="home",
        )
        db_session.add(extension)
        db_session.flush()

        predictor = LocationPredictor(db_session, game_session)
        predictions = predictor.predict_next_locations(
            "home",  # Already at home
            max_predictions=5,
        )

        # Home should not be in predictions when already there
        home_pred = next(
            (p for p in predictions if p.location_key == "home"),
            None
        )
        assert home_pred is None

    def test_get_prediction_stats(self, db_session, game_session):
        """Test getting prediction statistics."""
        # Create some tasks with locations
        task = Task(
            session_id=game_session.id,
            description="Test task",
            location="market",
            completed=False,
            created_turn=1,
        )
        db_session.add(task)

        # Create some locations
        for i in range(3):
            loc = Location(
                session_id=game_session.id,
                location_key=f"loc{i}",
                display_name=f"Location {i}",
                description=f"Description for location {i}",
            )
            db_session.add(loc)
        db_session.flush()

        predictor = LocationPredictor(db_session, game_session)
        stats = predictor.get_prediction_stats()

        assert stats["active_tasks_with_location"] == 1
        assert stats["total_locations"] == 3
        assert "has_player_home" in stats

    def test_word_boundary_matching(self, db_session, game_session):
        """Test that location matching uses word boundaries."""
        # Create location with name that could be substring of other words
        inn = Location(
            session_id=game_session.id,
            location_key="inn",
            display_name="Inn",
            description="A cozy roadside inn",
        )
        db_session.add(inn)
        db_session.flush()

        predictor = LocationPredictor(db_session, game_session)

        # "inn" should NOT match "winning" or "beginning"
        predictions = predictor.predict_next_locations(
            "home",
            recent_actions=["I keep winning at cards"],
            max_predictions=5,
        )

        inn_pred = next(
            (p for p in predictions if p.location_key == "inn"),
            None
        )
        assert inn_pred is None

        # But should match "the inn"
        predictions2 = predictor.predict_next_locations(
            "home",
            recent_actions=["Let's go to the inn"],
            max_predictions=5,
        )

        inn_pred2 = next(
            (p for p in predictions2 if p.location_key == "inn"),
            None
        )
        assert inn_pred2 is not None
