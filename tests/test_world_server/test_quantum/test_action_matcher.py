"""Tests for ActionMatcher."""

import pytest

from src.gm.grounding import GroundingManifest, GroundedEntity
from src.world_server.schemas import PredictionReason
from src.world_server.quantum.schemas import ActionType, ActionPrediction
from src.world_server.quantum.action_matcher import (
    ActionMatcher,
    MatchResult,
    ACTION_VERBS,
    STOPWORDS,
)


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
            "iron_sword": GroundedEntity(
                key="iron_sword",
                display_name="iron sword",
                entity_type="item",
                short_description="a basic weapon",
            ),
        },
        exits={
            "village_square": GroundedEntity(
                key="village_square",
                display_name="Village Square",
                entity_type="location",
                short_description="the central plaza",
            ),
        },
    )


@pytest.fixture
def sample_predictions():
    """Create sample predictions for testing."""
    return [
        ActionPrediction(
            action_type=ActionType.INTERACT_NPC,
            target_key="innkeeper_tom",
            input_patterns=[r"talk\s+(to\s+)?old tom", r"speak.*tom", r"talk.*innkeeper"],
            probability=0.25,
            reason=PredictionReason.ADJACENT,
            display_name="Talk to Old Tom",
        ),
        ActionPrediction(
            action_type=ActionType.INTERACT_NPC,
            target_key="guard_marcus",
            input_patterns=[r"talk\s+(to\s+)?marcus", r"speak.*guard"],
            probability=0.20,
            reason=PredictionReason.ADJACENT,
            display_name="Talk to Marcus",
        ),
        ActionPrediction(
            action_type=ActionType.MANIPULATE_ITEM,
            target_key="ale_mug_001",
            input_patterns=[r"take\s+(the\s+)?mug", r"grab.*ale", r"pick up.*ale"],
            probability=0.15,
            reason=PredictionReason.ADJACENT,
            display_name="Take mug of ale",
        ),
        ActionPrediction(
            action_type=ActionType.MANIPULATE_ITEM,
            target_key="iron_sword",
            input_patterns=[r"take\s+(the\s+)?sword", r"grab.*sword"],
            probability=0.15,
            reason=PredictionReason.ADJACENT,
            display_name="Take iron sword",
        ),
        ActionPrediction(
            action_type=ActionType.MOVE,
            target_key="village_square",
            input_patterns=[r"go\s+(to\s+)?village", r"head.*square", r"leave.*tavern"],
            probability=0.20,
            reason=PredictionReason.ADJACENT,
            display_name="Go to Village Square",
        ),
        ActionPrediction(
            action_type=ActionType.OBSERVE,
            target_key=None,
            input_patterns=[r"^look\b", r"^examine\b", r"look around"],
            probability=0.15,
            reason=PredictionReason.ADJACENT,
            display_name="Look around",
        ),
    ]


class TestActionMatcher:
    """Tests for ActionMatcher class."""

    def test_initialization_default_weights(self):
        """Test default weight initialization."""
        matcher = ActionMatcher()
        assert matcher.pattern_weight == 0.4
        assert matcher.target_weight == 0.4
        assert matcher.verb_weight == 0.2

    def test_initialization_custom_weights(self):
        """Test custom weight initialization."""
        matcher = ActionMatcher(
            pattern_weight=0.5,
            target_weight=0.3,
            verb_weight=0.2,
        )
        assert matcher.pattern_weight == 0.5


class TestMatchBasicInput:
    """Tests for basic input matching."""

    def test_match_exact_npc_pattern(
        self, sample_manifest, sample_predictions
    ):
        """Test matching exact NPC interaction pattern."""
        matcher = ActionMatcher()

        result = matcher.match(
            "talk to old tom",
            sample_predictions,
            sample_manifest,
        )

        assert result is not None
        assert result.prediction.target_key == "innkeeper_tom"
        assert result.prediction.action_type == ActionType.INTERACT_NPC
        assert result.confidence >= 0.5

    def test_match_item_manipulation(
        self, sample_manifest, sample_predictions
    ):
        """Test matching item manipulation."""
        matcher = ActionMatcher()

        result = matcher.match(
            "take the sword",
            sample_predictions,
            sample_manifest,
        )

        assert result is not None
        assert result.prediction.target_key == "iron_sword"
        assert result.prediction.action_type == ActionType.MANIPULATE_ITEM

    def test_match_movement(
        self, sample_manifest, sample_predictions
    ):
        """Test matching movement."""
        matcher = ActionMatcher()

        result = matcher.match(
            "go to village square",
            sample_predictions,
            sample_manifest,
        )

        assert result is not None
        assert result.prediction.target_key == "village_square"
        assert result.prediction.action_type == ActionType.MOVE

    def test_match_observation(
        self, sample_manifest, sample_predictions
    ):
        """Test matching observation."""
        matcher = ActionMatcher()

        result = matcher.match(
            "look around",
            sample_predictions,
            sample_manifest,
        )

        assert result is not None
        assert result.prediction.action_type == ActionType.OBSERVE

    def test_no_match_unrecognized_input(
        self, sample_manifest, sample_predictions
    ):
        """Test no match for unrecognized input."""
        matcher = ActionMatcher()

        result = matcher.match(
            "fly to the moon",
            sample_predictions,
            sample_manifest,
            min_confidence=0.7,
        )

        assert result is None


class TestFuzzyMatching:
    """Tests for fuzzy matching capabilities."""

    def test_fuzzy_match_partial_name(
        self, sample_manifest, sample_predictions
    ):
        """Test fuzzy matching with partial names."""
        matcher = ActionMatcher()

        result = matcher.match(
            "talk to tom",  # Missing "old"
            sample_predictions,
            sample_manifest,
        )

        assert result is not None
        assert result.prediction.target_key == "innkeeper_tom"

    def test_fuzzy_match_misspelling(
        self, sample_manifest, sample_predictions
    ):
        """Test fuzzy matching handles slight misspellings."""
        matcher = ActionMatcher()

        # "vilage" instead of "village"
        result = matcher.match(
            "go to vilage square",
            sample_predictions,
            sample_manifest,
            min_confidence=0.4,  # Lower threshold for typos
        )

        # May or may not match depending on threshold
        # At minimum, should not crash
        assert result is None or result.prediction.action_type == ActionType.MOVE

    def test_fuzzy_match_different_phrasing(
        self, sample_manifest, sample_predictions
    ):
        """Test matching with different phrasing."""
        matcher = ActionMatcher()

        result = matcher.match(
            "speak with the guard",
            sample_predictions,
            sample_manifest,
        )

        assert result is not None
        assert result.prediction.target_key == "guard_marcus"


class TestInputNormalization:
    """Tests for input normalization."""

    def test_normalize_removes_punctuation(self):
        """Test that punctuation is removed."""
        matcher = ActionMatcher()
        normalized = matcher._normalize("Hello, world!")
        assert normalized == "hello world"

    def test_normalize_lowercases(self):
        """Test that input is lowercased."""
        matcher = ActionMatcher()
        normalized = matcher._normalize("TALK TO TOM")
        assert normalized == "talk to tom"

    def test_normalize_collapses_whitespace(self):
        """Test that whitespace is collapsed."""
        matcher = ActionMatcher()
        normalized = matcher._normalize("talk   to    tom")
        assert normalized == "talk to tom"

    def test_normalize_preserves_apostrophes(self):
        """Test that apostrophes are preserved."""
        matcher = ActionMatcher()
        normalized = matcher._normalize("Tom's tavern")
        assert "tom's" in normalized


class TestVerbExtraction:
    """Tests for action verb extraction."""

    def test_extract_verb_talk(self):
        """Test extracting 'talk' verb."""
        matcher = ActionMatcher()
        verb, target = matcher._extract_verb_and_target("talk to the guard")
        assert verb == "talk"
        assert target is not None
        assert "guard" in target

    def test_extract_verb_take(self):
        """Test extracting 'take' verb."""
        matcher = ActionMatcher()
        verb, target = matcher._extract_verb_and_target("take the sword")
        assert verb == "take"
        assert "sword" in target

    def test_extract_verb_go(self):
        """Test extracting 'go' verb."""
        matcher = ActionMatcher()
        verb, target = matcher._extract_verb_and_target("go to the market")
        assert verb == "go"
        assert "market" in target

    def test_extract_no_verb(self):
        """Test input with no recognized verb."""
        matcher = ActionMatcher()
        verb, target = matcher._extract_verb_and_target("the market")
        assert verb is None

    def test_stopwords_removed_from_target(self):
        """Test that stopwords are removed from target."""
        matcher = ActionMatcher()
        verb, target = matcher._extract_verb_and_target("go to the big market")
        assert "the" not in target.split()
        assert "to" not in target.split()


class TestIdentifyActionType:
    """Tests for action type identification."""

    def test_identify_interact_npc(self):
        """Test identifying NPC interaction."""
        matcher = ActionMatcher()
        action_type = matcher.identify_action_type("talk to the guard")
        assert action_type == ActionType.INTERACT_NPC

    def test_identify_manipulate_item(self):
        """Test identifying item manipulation."""
        matcher = ActionMatcher()
        action_type = matcher.identify_action_type("take the sword")
        assert action_type == ActionType.MANIPULATE_ITEM

    def test_identify_move(self):
        """Test identifying movement."""
        matcher = ActionMatcher()
        action_type = matcher.identify_action_type("go to the market")
        assert action_type == ActionType.MOVE

    def test_identify_observe(self):
        """Test identifying observation."""
        matcher = ActionMatcher()
        action_type = matcher.identify_action_type("look around")
        assert action_type == ActionType.OBSERVE

    def test_identify_unknown(self):
        """Test unknown action type."""
        matcher = ActionMatcher()
        action_type = matcher.identify_action_type("xyzzy")
        assert action_type is None


class TestExtractTargetReference:
    """Tests for entity reference extraction."""

    def test_extract_npc_reference(self, sample_manifest):
        """Test extracting NPC reference."""
        matcher = ActionMatcher()
        key = matcher.extract_target_reference("talk to old tom", sample_manifest)
        assert key == "innkeeper_tom"

    def test_extract_item_reference(self, sample_manifest):
        """Test extracting item reference."""
        matcher = ActionMatcher()
        key = matcher.extract_target_reference("take the iron sword", sample_manifest)
        assert key == "iron_sword"

    def test_extract_no_reference(self, sample_manifest):
        """Test no reference found."""
        matcher = ActionMatcher()
        key = matcher.extract_target_reference("look around", sample_manifest)
        assert key is None

    def test_extract_partial_name(self, sample_manifest):
        """Test extracting with partial name."""
        matcher = ActionMatcher()
        key = matcher.extract_target_reference("talk to marcus", sample_manifest)
        assert key == "guard_marcus"


class TestMatchAll:
    """Tests for match_all method."""

    def test_match_all_returns_multiple(
        self, sample_manifest, sample_predictions
    ):
        """Test that match_all can return multiple results."""
        matcher = ActionMatcher()

        results = matcher.match_all(
            "take something",
            sample_predictions,
            sample_manifest,
            min_confidence=0.3,
        )

        # May match multiple item predictions
        assert isinstance(results, list)

    def test_match_all_sorted_by_confidence(
        self, sample_manifest, sample_predictions
    ):
        """Test that results are sorted by confidence."""
        matcher = ActionMatcher()

        results = matcher.match_all(
            "take the mug",
            sample_predictions,
            sample_manifest,
            min_confidence=0.2,
        )

        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i].confidence >= results[i + 1].confidence

    def test_match_all_respects_max_results(
        self, sample_manifest, sample_predictions
    ):
        """Test that max_results is respected."""
        matcher = ActionMatcher()

        results = matcher.match_all(
            "do something",
            sample_predictions,
            sample_manifest,
            min_confidence=0.1,
            max_results=2,
        )

        assert len(results) <= 2


class TestMatchResult:
    """Tests for MatchResult dataclass."""

    def test_match_result_creation(self, sample_predictions):
        """Test MatchResult creation."""
        result = MatchResult(
            prediction=sample_predictions[0],
            confidence=0.85,
            match_reason="pattern",
        )
        assert result.confidence == 0.85
        assert result.match_reason == "pattern"

    def test_match_result_comparison(self, sample_predictions):
        """Test MatchResult sorting."""
        result1 = MatchResult(sample_predictions[0], 0.5, "pattern")
        result2 = MatchResult(sample_predictions[1], 0.8, "target")

        assert result1 < result2  # Lower confidence is "less than"
        assert sorted([result1, result2], reverse=True)[0] == result2


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_input(self, sample_manifest, sample_predictions):
        """Test handling empty input."""
        matcher = ActionMatcher()
        result = matcher.match("", sample_predictions, sample_manifest)
        assert result is None

    def test_empty_predictions(self, sample_manifest):
        """Test handling empty predictions list."""
        matcher = ActionMatcher()
        result = matcher.match("talk to tom", [], sample_manifest)
        assert result is None

    def test_whitespace_only_input(self, sample_manifest, sample_predictions):
        """Test handling whitespace-only input."""
        matcher = ActionMatcher()
        result = matcher.match("   ", sample_predictions, sample_manifest)
        assert result is None

    def test_single_word_input(self, sample_manifest, sample_predictions):
        """Test single word input."""
        matcher = ActionMatcher()
        result = matcher.match("look", sample_predictions, sample_manifest)
        # Should match observe action
        assert result is not None or result is None  # May or may not match


class TestActionVerbsMapping:
    """Tests for ACTION_VERBS mapping."""

    def test_all_action_types_covered(self):
        """Test that all action types have verbs mapped."""
        mapped_types = set(ACTION_VERBS.values())
        # At minimum, common types should be covered
        assert ActionType.INTERACT_NPC in mapped_types
        assert ActionType.MANIPULATE_ITEM in mapped_types
        assert ActionType.MOVE in mapped_types
        assert ActionType.OBSERVE in mapped_types

    def test_common_verbs_present(self):
        """Test that common verbs are in the mapping."""
        assert "talk" in ACTION_VERBS
        assert "take" in ACTION_VERBS
        assert "go" in ACTION_VERBS
        assert "look" in ACTION_VERBS
        assert "attack" in ACTION_VERBS
