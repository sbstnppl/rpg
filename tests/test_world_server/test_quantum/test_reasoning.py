"""Tests for the Reasoning Engine (Phase 2 of split architecture)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.world_server.quantum.reasoning import (
    ReasoningEngine,
    ReasoningContext,
    ReasoningResponse,
    SemanticOutcome,
    SemanticChange,
    build_reasoning_context,
    difficulty_to_dc,
    time_description_to_minutes,
)
from src.world_server.quantum.schemas import ActionType, VariantType


class TestSemanticChange:
    """Tests for SemanticChange schema."""

    def test_basic_creation(self):
        change = SemanticChange(
            change_type="give_item",
            description="Old Tom gives the player a mug of ale",
            actor="Old Tom",
            target="the player",
            object_involved="a mug of ale",
        )
        assert change.change_type == "give_item"
        assert "Old Tom" in change.description
        assert change.actor == "Old Tom"
        assert change.object_involved == "a mug of ale"

    def test_minimal_creation(self):
        change = SemanticChange(
            change_type="learn_info",
            description="The player learns about the recent robbery",
        )
        assert change.change_type == "learn_info"
        assert change.actor is None
        assert change.target is None


class TestSemanticOutcome:
    """Tests for SemanticOutcome schema."""

    def test_basic_creation(self):
        outcome = SemanticOutcome(
            what_happens="The bartender serves the player a mug of honeyed ale",
            outcome_type="success",
            new_things=["a mug of honeyed ale"],
            changes=[
                SemanticChange(
                    change_type="give_item",
                    description="Tom gives ale to player",
                )
            ],
            time_description="a few minutes",
        )
        assert outcome.what_happens.startswith("The bartender")
        assert outcome.outcome_type == "success"
        assert "a mug of honeyed ale" in outcome.new_things
        assert len(outcome.changes) == 1

    def test_skill_check_outcome(self):
        outcome = SemanticOutcome(
            what_happens="The player picks the lock",
            outcome_type="success",
            requires_skill_check=True,
            skill_name="Lockpicking",
            difficulty="medium",
            time_description="a minute or two",
        )
        assert outcome.requires_skill_check is True
        assert outcome.skill_name == "Lockpicking"
        assert outcome.difficulty == "medium"

    def test_default_values(self):
        outcome = SemanticOutcome(
            what_happens="Something happens",
            outcome_type="success",
        )
        assert outcome.new_things == []
        assert outcome.changes == []
        assert outcome.requires_skill_check is False
        assert outcome.skill_name is None
        assert outcome.time_description == "a moment"


class TestReasoningResponse:
    """Tests for ReasoningResponse schema."""

    def test_simple_response(self):
        """Test response for action without skill check."""
        response = ReasoningResponse(
            requires_skill_check=False,
            success=SemanticOutcome(
                what_happens="Player talks to Tom",
                outcome_type="success",
            ),
        )
        assert response.requires_skill_check is False
        assert response.success.what_happens == "Player talks to Tom"
        assert response.failure is None

    def test_skill_check_response(self):
        """Test response for action with skill check variants."""
        response = ReasoningResponse(
            requires_skill_check=True,
            skill_name="Athletics",
            difficulty="hard",
            success=SemanticOutcome(
                what_happens="Player climbs the wall successfully",
                outcome_type="success",
            ),
            failure=SemanticOutcome(
                what_happens="Player slips and falls",
                outcome_type="failure",
            ),
            critical_success=SemanticOutcome(
                what_happens="Player climbs gracefully and finds a hidden ledge",
                outcome_type="critical_success",
            ),
            critical_failure=SemanticOutcome(
                what_happens="Player falls and twists their ankle",
                outcome_type="critical_failure",
            ),
        )
        assert response.requires_skill_check is True
        assert response.skill_name == "Athletics"
        assert response.difficulty == "hard"
        assert response.success is not None
        assert response.failure is not None
        assert response.critical_success is not None
        assert response.critical_failure is not None


class TestReasoningContext:
    """Tests for ReasoningContext dataclass."""

    def test_basic_creation(self):
        context = ReasoningContext(
            action_type=ActionType.INTERACT_NPC,
            action_summary="talk to Old Tom about ale",
            topic="ale",
            location_display="The Rusty Tankard",
            npcs_present=["Old Tom", "Patron"],
            items_available=["Ale Mug"],
            exits_available=["Village Square"],
        )
        assert context.action_type == ActionType.INTERACT_NPC
        assert "Old Tom" in context.action_summary
        assert context.topic == "ale"


class TestBuildReasoningContext:
    """Tests for build_reasoning_context helper."""

    def test_builds_correct_structure(self):
        context = build_reasoning_context(
            action_type=ActionType.MANIPULATE_ITEM,
            action_summary="pick up the sword",
            location_display="Armory",
            location_description="A dusty room full of weapons",
            npcs=["Guard"],
            items=["Rusty Sword", "Shield"],
            exits=["Hallway"],
            topic=None,
            recent_events=["Entered the castle"],
        )
        assert context.action_type == ActionType.MANIPULATE_ITEM
        assert context.action_summary == "pick up the sword"
        assert context.location_display == "Armory"
        assert "Guard" in context.npcs_present
        assert "Rusty Sword" in context.items_available
        assert "Entered the castle" in context.recent_events


class TestDifficultyToDC:
    """Tests for difficulty_to_dc helper."""

    def test_trivial(self):
        assert difficulty_to_dc("trivial") == 5

    def test_easy(self):
        assert difficulty_to_dc("easy") == 10

    def test_medium(self):
        assert difficulty_to_dc("medium") == 15

    def test_hard(self):
        assert difficulty_to_dc("hard") == 20

    def test_very_hard(self):
        assert difficulty_to_dc("very_hard") == 25

    def test_extreme(self):
        assert difficulty_to_dc("extreme") == 30

    def test_none_defaults_to_medium(self):
        assert difficulty_to_dc(None) == 15

    def test_unknown_defaults_to_medium(self):
        assert difficulty_to_dc("impossible") == 15


class TestTimeDescriptionToMinutes:
    """Tests for time_description_to_minutes helper."""

    def test_moment(self):
        assert time_description_to_minutes("a moment") == 1
        assert time_description_to_minutes("just a moment") == 1

    def test_instant(self):
        assert time_description_to_minutes("instant") == 1

    def test_seconds(self):
        assert time_description_to_minutes("a few seconds") == 1

    def test_minute_or_two(self):
        assert time_description_to_minutes("a minute or two") == 2

    def test_several_minutes(self):
        assert time_description_to_minutes("several minutes") == 10
        assert time_description_to_minutes("a few minutes") == 10

    def test_half_hour(self):
        assert time_description_to_minutes("about half an hour") == 30
        assert time_description_to_minutes("half hour") == 30

    def test_hour(self):
        assert time_description_to_minutes("about an hour") == 60

    def test_few_hours(self):
        assert time_description_to_minutes("a few hours") == 180

    def test_default(self):
        assert time_description_to_minutes("some time") == 5


class TestReasoningEngine:
    """Tests for ReasoningEngine class."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM provider."""
        llm = MagicMock()
        llm.complete_structured = AsyncMock()
        return llm

    @pytest.fixture
    def engine(self, mock_llm):
        """Create engine with mock LLM."""
        return ReasoningEngine(llm=mock_llm)

    @pytest.fixture
    def sample_context(self):
        """Create sample reasoning context."""
        return ReasoningContext(
            action_type=ActionType.INTERACT_NPC,
            action_summary="talk to Old Tom about ale",
            topic="ale",
            location_display="The Rusty Tankard",
            location_description="A cozy tavern with a roaring fire",
            npcs_present=["Old Tom", "Patron"],
            items_available=["Ale Mug"],
            exits_available=["Village Square"],
        )

    @pytest.mark.asyncio
    async def test_reason_simple_action(self, engine, mock_llm, sample_context):
        """Test reasoning for a simple action without skill check."""
        mock_response = MagicMock()
        mock_response.parsed_content = ReasoningResponse(
            requires_skill_check=False,
            success=SemanticOutcome(
                what_happens="Old Tom tells the player about local ales",
                outcome_type="success",
                new_things=["a mug of honeyed ale"],
                changes=[
                    SemanticChange(
                        change_type="give_item",
                        description="Tom gives ale to player",
                        actor="Old Tom",
                        target="the player",
                        object_involved="a mug of honeyed ale",
                    )
                ],
                time_description="a few minutes",
            ),
        )
        mock_llm.complete_structured.return_value = mock_response

        result = await engine.reason(sample_context)

        assert result.requires_skill_check is False
        assert result.success.what_happens.startswith("Old Tom")
        assert "a mug of honeyed ale" in result.success.new_things

    @pytest.mark.asyncio
    async def test_reason_skill_check_action(self, engine, mock_llm):
        """Test reasoning for an action requiring skill check."""
        context = ReasoningContext(
            action_type=ActionType.SKILL_USE,
            action_summary="pick the lock on the chest",
            location_display="Storage Room",
            items_available=["Locked Chest"],
        )

        mock_response = MagicMock()
        mock_response.parsed_content = ReasoningResponse(
            requires_skill_check=True,
            skill_name="Lockpicking",
            difficulty="medium",
            success=SemanticOutcome(
                what_happens="The player picks the lock and opens the chest",
                outcome_type="success",
                new_things=["a small pouch of gold"],
                time_description="a minute or two",
            ),
            failure=SemanticOutcome(
                what_happens="The lockpick snaps, leaving part in the lock",
                outcome_type="failure",
                changes=[
                    SemanticChange(
                        change_type="destroy_item",
                        description="Lockpick breaks",
                    )
                ],
                time_description="a minute or two",
            ),
        )
        mock_llm.complete_structured.return_value = mock_response

        result = await engine.reason(context)

        assert result.requires_skill_check is True
        assert result.skill_name == "Lockpicking"
        assert result.difficulty == "medium"
        assert result.success is not None
        assert result.failure is not None

    @pytest.mark.asyncio
    async def test_fallback_on_error(self, engine, mock_llm, sample_context):
        """Test fallback response when LLM fails."""
        mock_llm.complete_structured.side_effect = Exception("LLM error")

        result = await engine.reason(sample_context)

        assert result is not None
        assert result.success.what_happens.startswith("The player attempts to")
        assert result.requires_skill_check is False

    @pytest.mark.asyncio
    async def test_fallback_on_no_content(self, engine, mock_llm, sample_context):
        """Test fallback response when LLM returns no content."""
        mock_response = MagicMock()
        mock_response.parsed_content = None
        mock_llm.complete_structured.return_value = mock_response

        result = await engine.reason(sample_context)

        assert result is not None
        assert result.success is not None

    def test_outcome_to_variant_type(self, engine):
        """Test conversion from outcome_type to VariantType."""
        success = SemanticOutcome(what_happens="...", outcome_type="success")
        failure = SemanticOutcome(what_happens="...", outcome_type="failure")
        critical = SemanticOutcome(what_happens="...", outcome_type="critical_success")
        partial = SemanticOutcome(what_happens="...", outcome_type="partial_success")

        assert engine.outcome_to_variant_type(success) == VariantType.SUCCESS
        assert engine.outcome_to_variant_type(failure) == VariantType.FAILURE
        assert engine.outcome_to_variant_type(critical) == VariantType.CRITICAL_SUCCESS
        assert engine.outcome_to_variant_type(partial) == VariantType.PARTIAL_SUCCESS
