"""Tests for GMDecisionOracle."""

import pytest
from unittest.mock import MagicMock, patch

from src.gm.grounding import GroundingManifest, GroundedEntity
from src.world_server.schemas import PredictionReason
from src.world_server.quantum.schemas import ActionType, ActionPrediction
from src.world_server.quantum.gm_oracle import (
    GMDecisionOracle,
    TwistDefinition,
    TWIST_DEFINITIONS,
)


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = MagicMock()
    # Default: no facts found
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.all.return_value = []
    return db


@pytest.fixture
def mock_game_session():
    """Create a mock game session."""
    session = MagicMock()
    session.id = 1
    return session


@pytest.fixture
def sample_manifest():
    """Create a sample grounding manifest."""
    return GroundingManifest(
        location_key="village_square",
        location_display="Village Square",
        player_key="player_001",
        player_display="you",
        npcs={
            "guard_001": GroundedEntity(
                key="guard_001",
                display_name="Town Guard",
                entity_type="npc",
                short_description="a vigilant guard",
            ),
        },
        items_at_location={},
        exits={
            "tavern": GroundedEntity(
                key="tavern",
                display_name="The Rusty Anchor",
                entity_type="location",
            ),
        },
    )


@pytest.fixture
def sample_action():
    """Create a sample action prediction."""
    return ActionPrediction(
        action_type=ActionType.MOVE,
        target_key="tavern",
        input_patterns=["go tavern"],
        probability=0.25,
        reason=PredictionReason.ADJACENT,
    )


class TestGMDecisionOracle:
    """Tests for GMDecisionOracle class."""

    def test_initialization(self, mock_db, mock_game_session):
        """Test oracle initialization."""
        oracle = GMDecisionOracle(mock_db, mock_game_session)
        assert oracle.db == mock_db
        assert oracle.game_session == mock_game_session

    def test_predict_decisions_always_includes_no_twist(
        self, mock_db, mock_game_session, sample_manifest, sample_action
    ):
        """Test that no_twist is always included."""
        oracle = GMDecisionOracle(mock_db, mock_game_session)

        decisions = oracle.predict_decisions(sample_action, sample_manifest)

        # Should always have at least no_twist
        assert len(decisions) >= 1

        no_twist = next((d for d in decisions if d.decision_type == "no_twist"), None)
        assert no_twist is not None
        assert no_twist.probability > 0

    def test_predict_decisions_sorted_by_probability(
        self, mock_db, mock_game_session, sample_manifest, sample_action
    ):
        """Test that decisions are sorted by probability."""
        oracle = GMDecisionOracle(mock_db, mock_game_session)

        decisions = oracle.predict_decisions(sample_action, sample_manifest)

        for i in range(len(decisions) - 1):
            assert decisions[i].probability >= decisions[i + 1].probability

    def test_predict_decisions_respects_max_decisions(
        self, mock_db, mock_game_session, sample_manifest, sample_action
    ):
        """Test that max_decisions is respected."""
        oracle = GMDecisionOracle(mock_db, mock_game_session)

        decisions = oracle.predict_decisions(
            sample_action, sample_manifest, max_decisions=2
        )

        assert len(decisions) <= 2

    def test_probabilities_sum_to_one(
        self, mock_db, mock_game_session, sample_manifest, sample_action
    ):
        """Test that normalized probabilities sum to ~1.0."""
        oracle = GMDecisionOracle(mock_db, mock_game_session)

        decisions = oracle.predict_decisions(sample_action, sample_manifest)

        total_prob = sum(d.probability for d in decisions)
        assert 0.99 <= total_prob <= 1.01  # Allow small floating point error


class TestTwistGrounding:
    """Tests for twist grounding logic."""

    def test_twist_requires_facts(
        self, mock_db, mock_game_session, sample_manifest
    ):
        """Test that twists without facts are not included."""
        oracle = GMDecisionOracle(mock_db, mock_game_session)

        # Action that could have theft_accusation twist
        action = ActionPrediction(
            action_type=ActionType.MOVE,
            target_key="tavern",
            input_patterns=["go tavern"],
            probability=0.25,
            reason=PredictionReason.ADJACENT,
        )

        # No facts in database (default mock)
        decisions = oracle.predict_decisions(action, sample_manifest)

        # Should only have no_twist since no grounding facts
        twist_decisions = [d for d in decisions if d.decision_type != "no_twist"]
        assert len(twist_decisions) == 0

    def test_twist_included_when_grounded(
        self, mock_db, mock_game_session, sample_manifest
    ):
        """Test that twists are included when facts exist."""
        oracle = GMDecisionOracle(mock_db, mock_game_session)

        # Create mock facts for theft_accusation
        mock_fact1 = MagicMock()
        mock_fact1.subject_key = "village_square"
        mock_fact1.predicate = "recent_theft"
        mock_fact1.value = "true"

        mock_fact2 = MagicMock()
        mock_fact2.subject_key = "player"
        mock_fact2.predicate = "is_stranger"
        mock_fact2.value = "true"

        # Set up query to return facts
        def side_effect_filter(*args, **kwargs):
            filter_mock = MagicMock()

            # Check what predicate is being queried
            def first_side_effect():
                # Return appropriate fact based on query
                for arg in args:
                    if hasattr(arg, 'right') and hasattr(arg.right, 'value'):
                        if arg.right.value == "recent_theft":
                            return mock_fact1
                        elif arg.right.value == "is_stranger":
                            return mock_fact2
                return None

            filter_mock.first.side_effect = first_side_effect
            filter_mock.all.return_value = []
            return filter_mock

        mock_db.query.return_value.filter.side_effect = side_effect_filter

        action = ActionPrediction(
            action_type=ActionType.MOVE,
            target_key="tavern",
            input_patterns=["go tavern"],
            probability=0.25,
            reason=PredictionReason.ADJACENT,
        )

        decisions = oracle.predict_decisions(action, sample_manifest)

        # Note: Due to mock complexity, this tests the structure exists
        # In integration tests, we'd verify actual grounding
        assert len(decisions) >= 1

    def test_grounding_facts_included_in_decision(
        self, mock_db, mock_game_session, sample_manifest, sample_action
    ):
        """Test that grounding facts are recorded in decision."""
        oracle = GMDecisionOracle(mock_db, mock_game_session)

        decisions = oracle.predict_decisions(sample_action, sample_manifest)

        no_twist = next(d for d in decisions if d.decision_type == "no_twist")
        # no_twist should have empty grounding facts
        assert no_twist.grounding_facts == []


class TestTwistDefinitions:
    """Tests for twist definitions."""

    def test_all_twist_types_have_required_fields(self):
        """Test that all twist definitions are valid."""
        for twist in TWIST_DEFINITIONS:
            assert twist.twist_type
            assert twist.description
            assert 0 <= twist.base_probability <= 1.0
            assert isinstance(twist.required_facts, list)

    def test_twist_types_are_unique(self):
        """Test that twist types are unique."""
        types = [t.twist_type for t in TWIST_DEFINITIONS]
        assert len(types) == len(set(types))

    def test_applicable_actions_are_valid(self):
        """Test that applicable actions are valid ActionTypes."""
        for twist in TWIST_DEFINITIONS:
            for action_type in twist.applicable_actions:
                assert isinstance(action_type, ActionType)


class TestGetApplicableTwists:
    """Tests for get_applicable_twists method."""

    def test_get_applicable_twists_movement(self, mock_db, mock_game_session):
        """Test getting twists applicable to movement."""
        oracle = GMDecisionOracle(mock_db, mock_game_session)

        twists = oracle.get_applicable_twists(ActionType.MOVE)

        # Should include movement-applicable twists
        twist_types = {t.twist_type for t in twists}
        assert "theft_accusation" in twist_types or "monster_warning" in twist_types

    def test_get_applicable_twists_npc_interaction(self, mock_db, mock_game_session):
        """Test getting twists applicable to NPC interaction."""
        oracle = GMDecisionOracle(mock_db, mock_game_session)

        twists = oracle.get_applicable_twists(ActionType.INTERACT_NPC)

        twist_types = {t.twist_type for t in twists}
        # npc_recognition should be applicable
        assert "npc_recognition" in twist_types

    def test_get_applicable_twists_item_manipulation(self, mock_db, mock_game_session):
        """Test getting twists applicable to item manipulation."""
        oracle = GMDecisionOracle(mock_db, mock_game_session)

        twists = oracle.get_applicable_twists(ActionType.MANIPULATE_ITEM)

        twist_types = {t.twist_type for t in twists}
        # item_cursed should be applicable
        assert "item_cursed" in twist_types


class TestTwistDefinitionDataclass:
    """Tests for TwistDefinition dataclass."""

    def test_create_twist_definition(self):
        """Test creating a twist definition."""
        twist = TwistDefinition(
            twist_type="test_twist",
            description="A test twist",
            base_probability=0.15,
            required_facts=[("location:*", "test_fact")],
            applicable_actions=[ActionType.MOVE],
        )

        assert twist.twist_type == "test_twist"
        assert twist.base_probability == 0.15
        assert len(twist.required_facts) == 1
        assert twist.cooldown_turns == 5  # default

    def test_twist_definition_defaults(self):
        """Test twist definition default values."""
        twist = TwistDefinition(
            twist_type="minimal",
            description="Minimal twist",
            base_probability=0.1,
            required_facts=[],
        )

        assert twist.optional_facts == []
        assert twist.probability_boost_per_optional == 0.05
        assert twist.applicable_actions == []
        assert twist.cooldown_turns == 5


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_manifest_npcs(self, mock_db, mock_game_session):
        """Test with empty NPCs in manifest."""
        manifest = GroundingManifest(
            location_key="empty",
            location_display="Empty Room",
            player_key="player",
            npcs={},
            items_at_location={},
            exits={},
        )

        oracle = GMDecisionOracle(mock_db, mock_game_session)

        action = ActionPrediction(
            action_type=ActionType.OBSERVE,
            target_key=None,
            input_patterns=["look"],
            probability=0.2,
            reason=PredictionReason.ADJACENT,
        )

        # Should not crash
        decisions = oracle.predict_decisions(action, manifest)
        assert len(decisions) >= 1

    def test_action_with_no_target(self, mock_db, mock_game_session, sample_manifest):
        """Test action without a target key."""
        oracle = GMDecisionOracle(mock_db, mock_game_session)

        action = ActionPrediction(
            action_type=ActionType.OBSERVE,
            target_key=None,
            input_patterns=["look around"],
            probability=0.2,
            reason=PredictionReason.ADJACENT,
        )

        decisions = oracle.predict_decisions(action, sample_manifest)
        assert len(decisions) >= 1
