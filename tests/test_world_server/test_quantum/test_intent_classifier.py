"""Tests for the Intent Classifier (Phase 1 of split architecture)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.world_server.quantum.intent import (
    IntentType,
    IntentClassification,
    IntentClassifierInput,
    CachedBranchSummary,
)
from src.world_server.quantum.intent_classifier import (
    IntentClassifier,
    IntentClassificationResponse,
    build_classifier_input,
)
from src.world_server.quantum.schemas import ActionType


class TestIntentType:
    """Tests for IntentType enum."""

    def test_action_type(self):
        assert IntentType.ACTION.value == "action"

    def test_question_type(self):
        assert IntentType.QUESTION.value == "question"

    def test_hypothetical_type(self):
        assert IntentType.HYPOTHETICAL.value == "hypothetical"

    def test_ooc_type(self):
        assert IntentType.OUT_OF_CHARACTER.value == "ooc"

    def test_ambiguous_type(self):
        assert IntentType.AMBIGUOUS.value == "ambiguous"


class TestIntentClassification:
    """Tests for IntentClassification dataclass."""

    def test_basic_creation(self):
        classification = IntentClassification(
            intent_type=IntentType.ACTION,
            confidence=0.9,
            raw_input="talk to Tom",
        )
        assert classification.intent_type == IntentType.ACTION
        assert classification.confidence == 0.9
        assert classification.raw_input == "talk to Tom"

    def test_is_action_property(self):
        action = IntentClassification(
            intent_type=IntentType.ACTION,
            confidence=0.9,
        )
        question = IntentClassification(
            intent_type=IntentType.QUESTION,
            confidence=0.9,
        )
        assert action.is_action is True
        assert question.is_action is False

    def test_is_informational_property(self):
        question = IntentClassification(
            intent_type=IntentType.QUESTION,
            confidence=0.9,
        )
        hypothetical = IntentClassification(
            intent_type=IntentType.HYPOTHETICAL,
            confidence=0.9,
        )
        action = IntentClassification(
            intent_type=IntentType.ACTION,
            confidence=0.9,
        )
        assert question.is_informational is True
        assert hypothetical.is_informational is True
        assert action.is_informational is False

    def test_is_cache_hit_property(self):
        with_hit = IntentClassification(
            intent_type=IntentType.ACTION,
            confidence=0.9,
            matched_branch_key="test_branch",
            match_confidence=0.8,
        )
        without_hit = IntentClassification(
            intent_type=IntentType.ACTION,
            confidence=0.9,
        )
        low_confidence = IntentClassification(
            intent_type=IntentType.ACTION,
            confidence=0.9,
            matched_branch_key="test_branch",
            match_confidence=0.5,  # Below 0.7 threshold
        )
        assert with_hit.is_cache_hit is True
        assert without_hit.is_cache_hit is False
        assert low_confidence.is_cache_hit is False

    def test_needs_clarification_property(self):
        ambiguous = IntentClassification(
            intent_type=IntentType.AMBIGUOUS,
            confidence=0.8,
        )
        low_confidence = IntentClassification(
            intent_type=IntentType.ACTION,
            confidence=0.3,  # Below 0.5
        )
        confident = IntentClassification(
            intent_type=IntentType.ACTION,
            confidence=0.9,
        )
        assert ambiguous.needs_clarification is True
        assert low_confidence.needs_clarification is True
        assert confident.needs_clarification is False

    def test_confidence_validation(self):
        with pytest.raises(ValueError):
            IntentClassification(
                intent_type=IntentType.ACTION,
                confidence=1.5,  # Invalid: > 1.0
            )
        with pytest.raises(ValueError):
            IntentClassification(
                intent_type=IntentType.ACTION,
                confidence=-0.1,  # Invalid: < 0.0
            )


class TestIntentClassifierInput:
    """Tests for IntentClassifierInput dataclass."""

    def test_basic_creation(self):
        input_data = IntentClassifierInput(
            player_input="talk to Tom",
            location_display="The Rusty Tankard",
            location_key="village_tavern",
            npcs_present=["Old Tom", "Patron"],
            items_available=["Ale Mug"],
            exits_available=["Village Square"],
        )
        assert input_data.player_input == "talk to Tom"
        assert "Old Tom" in input_data.npcs_present


class TestBuildClassifierInput:
    """Tests for build_classifier_input helper."""

    def test_builds_correct_structure(self):
        result = build_classifier_input(
            player_input="talk to Tom",
            location_display="Tavern",
            location_key="tavern_001",
            npcs=["Tom", "Jane"],
            items=["sword", "shield"],
            exits=["north", "south"],
        )
        assert result.player_input == "talk to Tom"
        assert result.location_display == "Tavern"
        assert result.npcs_present == ["Tom", "Jane"]
        assert result.items_available == ["sword", "shield"]
        assert result.exits_available == ["north", "south"]


class TestIntentClassifier:
    """Tests for IntentClassifier class."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM provider."""
        llm = MagicMock()
        llm.complete_structured = AsyncMock()
        return llm

    @pytest.fixture
    def classifier(self, mock_llm):
        """Create classifier with mock LLM."""
        return IntentClassifier(llm=mock_llm)

    @pytest.fixture
    def sample_input(self):
        """Create sample classifier input."""
        return IntentClassifierInput(
            player_input="talk to Tom about ale",
            location_display="The Rusty Tankard",
            location_key="village_tavern",
            npcs_present=["Old Tom", "Patron"],
            items_available=["Ale Mug"],
            exits_available=["Village Square"],
        )

    @pytest.mark.asyncio
    async def test_classify_action(self, classifier, mock_llm, sample_input):
        """Test classification of an action intent."""
        mock_response = MagicMock()
        mock_response.parsed_content = IntentClassificationResponse(
            intent_type="action",
            confidence=0.95,
            action_type="interact_npc",
            target="Old Tom",
            topic="ale",
            matched_option=None,
            match_confidence=0.0,
        )
        mock_llm.complete_structured.return_value = mock_response

        result = await classifier.classify(sample_input)

        assert result.intent_type == IntentType.ACTION
        assert result.confidence == 0.95
        assert result.action_type == ActionType.INTERACT_NPC
        assert result.target_display == "Old Tom"
        assert result.topic == "ale"

    @pytest.mark.asyncio
    async def test_classify_question(self, classifier, mock_llm, sample_input):
        """Test classification of a question intent."""
        sample_input.player_input = "Could I talk to Tom?"

        mock_response = MagicMock()
        mock_response.parsed_content = IntentClassificationResponse(
            intent_type="question",
            confidence=0.9,
            action_type="interact_npc",
            target="Old Tom",
            topic=None,
            matched_option=None,
            match_confidence=0.0,
        )
        mock_llm.complete_structured.return_value = mock_response

        result = await classifier.classify(sample_input)

        assert result.intent_type == IntentType.QUESTION
        assert result.is_informational is True

    @pytest.mark.asyncio
    async def test_fallback_on_error(self, classifier, mock_llm, sample_input):
        """Test fallback classification when LLM fails."""
        mock_llm.complete_structured.side_effect = Exception("LLM error")

        result = await classifier.classify(sample_input)

        # Should return a fallback classification
        assert result is not None
        assert result.confidence < 0.5  # Low confidence

    def test_fallback_ooc_detection(self, classifier):
        """Test fallback detection of OOC intent."""
        result = classifier._fallback_classification("ooc: what time is it?")
        assert result.intent_type == IntentType.OUT_OF_CHARACTER
        assert result.confidence == 0.9

    def test_fallback_question_detection(self, classifier):
        """Test fallback detection of question intent."""
        result = classifier._fallback_classification("Could I pick up the sword?")
        assert result.intent_type == IntentType.QUESTION
        assert result.confidence == 0.6

    def test_fallback_default_action(self, classifier):
        """Test fallback defaults to action with low confidence."""
        result = classifier._fallback_classification("do something random")
        assert result.intent_type == IntentType.ACTION
        assert result.confidence == 0.4  # Low confidence


class TestIntentClassificationResponse:
    """Tests for the Pydantic response schema."""

    def test_valid_response(self):
        response = IntentClassificationResponse(
            intent_type="action",
            confidence=0.9,
            action_type="interact_npc",
            target="Tom",
            topic="ale",
            matched_option=1,
            match_confidence=0.8,
        )
        assert response.intent_type == "action"
        assert response.confidence == 0.9

    def test_minimal_response(self):
        response = IntentClassificationResponse(
            intent_type="ambiguous",
            confidence=0.3,
        )
        assert response.action_type is None
        assert response.target is None
        assert response.matched_option is None

    def test_confidence_bounds(self):
        with pytest.raises(ValueError):
            IntentClassificationResponse(
                intent_type="action",
                confidence=1.5,  # Invalid
            )
