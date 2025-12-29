"""Tests for ActionPredictor."""

import pytest
from unittest.mock import MagicMock, patch

from src.gm.grounding import GroundingManifest, GroundedEntity
from src.world_server.quantum.schemas import ActionType
from src.world_server.quantum.action_predictor import (
    ActionPredictor,
    PredictionContext,
    DEFAULT_PROBABILITIES,
)


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture
def mock_game_session():
    """Create a mock game session."""
    session = MagicMock()
    session.id = 1
    return session


@pytest.fixture
def sample_manifest():
    """Create a sample grounding manifest for testing."""
    return GroundingManifest(
        location_key="tavern_main",
        location_display="The Rusty Anchor Tavern",
        player_key="player_001",
        player_display="you",
        npcs={
            "innkeeper_tom": GroundedEntity(
                key="innkeeper_tom",
                display_name="Old Tom",
                entity_type="npc",
                short_description="the friendly innkeeper",
            ),
            "guard_marcus": GroundedEntity(
                key="guard_marcus",
                display_name="Marcus",
                entity_type="npc",
                short_description="a watchful guard",
            ),
        },
        items_at_location={
            "ale_mug_001": GroundedEntity(
                key="ale_mug_001",
                display_name="mug of ale",
                entity_type="item",
                short_description="a frothy ale",
            ),
        },
        inventory={
            "gold_pouch": GroundedEntity(
                key="gold_pouch",
                display_name="gold pouch",
                entity_type="item",
                short_description="contains 50 gold coins",
            ),
        },
        exits={
            "village_square": GroundedEntity(
                key="village_square",
                display_name="Village Square",
                entity_type="location",
                short_description="the central plaza",
            ),
            "tavern_upstairs": GroundedEntity(
                key="tavern_upstairs",
                display_name="upstairs",
                entity_type="location",
                short_description="guest rooms above",
            ),
        },
    )


class TestPredictionContext:
    """Tests for PredictionContext dataclass."""

    def test_default_initialization(self):
        """Test default context is empty."""
        ctx = PredictionContext()
        assert ctx.recent_inputs == []
        assert ctx.recent_targets == set()
        assert ctx.mentioned_entities == set()
        assert ctx.current_quest_targets == set()

    def test_with_data(self):
        """Test context with data."""
        ctx = PredictionContext(
            recent_inputs=["talk to tom", "look around"],
            recent_targets={"innkeeper_tom"},
            mentioned_entities={"sword_001"},
        )
        assert len(ctx.recent_inputs) == 2
        assert "innkeeper_tom" in ctx.recent_targets


class TestActionPredictor:
    """Tests for ActionPredictor class."""

    def test_initialization(self, mock_db, mock_game_session):
        """Test predictor initialization."""
        predictor = ActionPredictor(mock_db, mock_game_session)
        assert predictor.db == mock_db
        assert predictor.game_session == mock_game_session

    def test_predict_actions_returns_predictions(
        self, mock_db, mock_game_session, sample_manifest
    ):
        """Test that predictions are returned."""
        predictor = ActionPredictor(mock_db, mock_game_session)

        # Mock the query to return empty turns
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        predictions = predictor.predict_actions(
            location_key="tavern_main",
            manifest=sample_manifest,
            max_predictions=10,
        )

        assert len(predictions) > 0
        # Should include NPC interactions, item manipulations, movement, observe, wait
        action_types = {p.action_type for p in predictions}
        assert ActionType.INTERACT_NPC in action_types
        assert ActionType.MANIPULATE_ITEM in action_types
        assert ActionType.MOVE in action_types
        assert ActionType.OBSERVE in action_types

    def test_predict_npc_interactions(
        self, mock_db, mock_game_session, sample_manifest
    ):
        """Test NPC interaction predictions."""
        predictor = ActionPredictor(mock_db, mock_game_session)
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        predictions = predictor.predict_actions(
            location_key="tavern_main",
            manifest=sample_manifest,
        )

        # Find NPC predictions
        npc_preds = [p for p in predictions if p.action_type == ActionType.INTERACT_NPC]

        # Should have predictions for both NPCs
        assert len(npc_preds) == 2

        # Check innkeeper prediction
        tom_pred = next((p for p in npc_preds if p.target_key == "innkeeper_tom"), None)
        assert tom_pred is not None
        assert "Old Tom" in tom_pred.display_name
        assert len(tom_pred.input_patterns) > 0

    def test_predict_item_manipulations(
        self, mock_db, mock_game_session, sample_manifest
    ):
        """Test item manipulation predictions."""
        predictor = ActionPredictor(mock_db, mock_game_session)
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        predictions = predictor.predict_actions(
            location_key="tavern_main",
            manifest=sample_manifest,
        )

        # Find item predictions
        item_preds = [p for p in predictions if p.action_type == ActionType.MANIPULATE_ITEM]

        # Should have predictions for items at location and inventory
        assert len(item_preds) >= 2

        # Check ale mug prediction
        ale_pred = next((p for p in item_preds if p.target_key == "ale_mug_001"), None)
        assert ale_pred is not None
        assert "take" in ale_pred.context.get("action", "")

    def test_predict_movement(
        self, mock_db, mock_game_session, sample_manifest
    ):
        """Test movement predictions."""
        predictor = ActionPredictor(mock_db, mock_game_session)
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        predictions = predictor.predict_actions(
            location_key="tavern_main",
            manifest=sample_manifest,
        )

        # Find movement predictions
        move_preds = [p for p in predictions if p.action_type == ActionType.MOVE]

        # Should have predictions for both exits
        assert len(move_preds) == 2

        # Check village square prediction
        square_pred = next((p for p in move_preds if p.target_key == "village_square"), None)
        assert square_pred is not None
        assert len(square_pred.input_patterns) > 0

    def test_observe_prediction_always_present(
        self, mock_db, mock_game_session, sample_manifest
    ):
        """Test that observation is always predicted."""
        predictor = ActionPredictor(mock_db, mock_game_session)
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        predictions = predictor.predict_actions(
            location_key="tavern_main",
            manifest=sample_manifest,
        )

        observe_preds = [p for p in predictions if p.action_type == ActionType.OBSERVE]
        assert len(observe_preds) == 1
        assert observe_preds[0].target_key is None

    def test_predictions_sorted_by_probability(
        self, mock_db, mock_game_session, sample_manifest
    ):
        """Test that predictions are sorted by probability."""
        predictor = ActionPredictor(mock_db, mock_game_session)
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        predictions = predictor.predict_actions(
            location_key="tavern_main",
            manifest=sample_manifest,
        )

        # Verify sorted by probability (descending)
        for i in range(len(predictions) - 1):
            assert predictions[i].probability >= predictions[i + 1].probability

    def test_max_predictions_limit(
        self, mock_db, mock_game_session, sample_manifest
    ):
        """Test that max_predictions is respected."""
        predictor = ActionPredictor(mock_db, mock_game_session)
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        predictions = predictor.predict_actions(
            location_key="tavern_main",
            manifest=sample_manifest,
            max_predictions=3,
        )

        assert len(predictions) <= 3

    def test_probability_capped_at_95_percent(
        self, mock_db, mock_game_session, sample_manifest
    ):
        """Test that probabilities don't exceed 95%."""
        predictor = ActionPredictor(mock_db, mock_game_session)
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        predictions = predictor.predict_actions(
            location_key="tavern_main",
            manifest=sample_manifest,
        )

        for pred in predictions:
            assert pred.probability <= 0.95

    def test_input_patterns_are_valid_regex(
        self, mock_db, mock_game_session, sample_manifest
    ):
        """Test that input patterns are valid regex."""
        import re
        predictor = ActionPredictor(mock_db, mock_game_session)
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        predictions = predictor.predict_actions(
            location_key="tavern_main",
            manifest=sample_manifest,
        )

        for pred in predictions:
            for pattern in pred.input_patterns:
                # Should not raise
                re.compile(pattern, re.IGNORECASE)

    def test_get_prediction_stats(self, mock_db, mock_game_session):
        """Test prediction statistics."""
        predictor = ActionPredictor(mock_db, mock_game_session)
        stats = predictor.get_prediction_stats()

        assert "base_probabilities" in stats
        assert "recent_turns_analyzed" in stats


class TestNPCPatternBuilding:
    """Tests for NPC pattern building."""

    def test_patterns_include_display_name(
        self, mock_db, mock_game_session, sample_manifest
    ):
        """Test that patterns include NPC display name."""
        predictor = ActionPredictor(mock_db, mock_game_session)
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        predictions = predictor.predict_actions(
            location_key="tavern_main",
            manifest=sample_manifest,
        )

        tom_pred = next(
            (p for p in predictions if p.target_key == "innkeeper_tom"),
            None
        )
        assert tom_pred is not None

        # Check patterns contain variations of the name
        patterns_str = " ".join(tom_pred.input_patterns).lower()
        assert "tom" in patterns_str or "old" in patterns_str

    def test_patterns_include_role_keywords(
        self, mock_db, mock_game_session, sample_manifest
    ):
        """Test that patterns include role from description."""
        predictor = ActionPredictor(mock_db, mock_game_session)
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        predictions = predictor.predict_actions(
            location_key="tavern_main",
            manifest=sample_manifest,
        )

        tom_pred = next(
            (p for p in predictions if p.target_key == "innkeeper_tom"),
            None
        )
        assert tom_pred is not None

        # Should have innkeeper-related patterns
        patterns_str = " ".join(tom_pred.input_patterns).lower()
        assert "innkeeper" in patterns_str


class TestEmptyManifest:
    """Tests for edge cases with empty manifest sections."""

    def test_empty_npcs(self, mock_db, mock_game_session):
        """Test prediction with no NPCs."""
        manifest = GroundingManifest(
            location_key="empty_room",
            location_display="Empty Room",
            player_key="player_001",
            npcs={},
            items_at_location={},
            exits={},
        )

        predictor = ActionPredictor(mock_db, mock_game_session)
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        predictions = predictor.predict_actions(
            location_key="empty_room",
            manifest=manifest,
        )

        # Should still have observe and wait
        action_types = {p.action_type for p in predictions}
        assert ActionType.OBSERVE in action_types
        assert ActionType.WAIT in action_types

        # Should NOT have NPC interactions
        npc_preds = [p for p in predictions if p.action_type == ActionType.INTERACT_NPC]
        assert len(npc_preds) == 0
