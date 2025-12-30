"""Tests for the SubturnProcessor class.

Tests cover:
- Sequential action processing with state updates
- Continuation evaluation logic
- Complication interrupt handling
- State snapshot management
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.executor.subturn_processor import (
    ChainedTurnResult,
    ContinuationStatus,
    SubturnProcessor,
    SubturnResult,
)
from src.parser.action_types import Action, ActionType


class TestContinuationStatus:
    """Tests for the ContinuationStatus enum."""

    def test_continue_value(self):
        """Test CONTINUE has correct value."""
        assert ContinuationStatus.CONTINUE.value == "continue"

    def test_offer_choice_value(self):
        """Test OFFER_CHOICE has correct value."""
        assert ContinuationStatus.OFFER_CHOICE.value == "offer_choice"

    def test_abandon_value(self):
        """Test ABANDON has correct value."""
        assert ContinuationStatus.ABANDON.value == "abandon"


class TestSubturnResult:
    """Tests for the SubturnResult dataclass."""

    def test_to_dict_success(self):
        """Test serialization of successful subturn."""
        from src.validators.action_validator import ValidationResult
        from src.executor.action_executor import ExecutionResult

        action = Action(type=ActionType.MOVE, target="well")
        validation = ValidationResult(action=action, valid=True)
        execution = ExecutionResult(
            action=action,
            success=True,
            outcome="You walk to the well.",
            state_changes=["location_changed"],
        )

        subturn = SubturnResult(
            action=action,
            validation=validation,
            execution=execution,
            complication=None,
            state_snapshot={"player_location": "well"},
            continuation_status=ContinuationStatus.CONTINUE,
        )

        result = subturn.to_dict()

        assert result["action"]["type"] == "move"
        assert result["action"]["target"] == "well"
        assert result["validation"]["valid"] is True
        assert result["execution"]["success"] is True
        assert result["execution"]["outcome"] == "You walk to the well."
        assert result["complication"] is None
        assert result["continuation_status"] == "continue"

    def test_to_dict_failed_validation(self):
        """Test serialization of failed validation."""
        from src.validators.action_validator import ValidationResult

        action = Action(type=ActionType.USE, target="bucket")
        validation = ValidationResult(
            action=action,
            valid=False,
            reason="No bucket here.",
        )

        subturn = SubturnResult(
            action=action,
            validation=validation,
            execution=None,
            complication=None,
            state_snapshot={"player_location": "kitchen"},
            continuation_status=ContinuationStatus.CONTINUE,
        )

        result = subturn.to_dict()

        assert result["validation"]["valid"] is False
        assert result["validation"]["reason"] == "No bucket here."
        assert result["execution"] is None

    def test_from_dict_roundtrip(self):
        """Test deserialization round-trip."""
        from src.validators.action_validator import ValidationResult
        from src.executor.action_executor import ExecutionResult

        action = Action(type=ActionType.TAKE, target="sword")
        validation = ValidationResult(action=action, valid=True, warnings=["Heavy"])
        execution = ExecutionResult(
            action=action,
            success=True,
            outcome="You take the sword.",
            state_changes=[],
        )

        original = SubturnResult(
            action=action,
            validation=validation,
            execution=execution,
            complication=None,
            state_snapshot={"inventory_changed": True},
            continuation_status=ContinuationStatus.CONTINUE,
        )

        data = original.to_dict()
        restored = SubturnResult.from_dict(data)

        assert restored.action.type == ActionType.TAKE
        assert restored.action.target == "sword"
        assert restored.validation.valid is True
        assert restored.execution.success is True
        assert restored.continuation_status == ContinuationStatus.CONTINUE


class TestChainedTurnResult:
    """Tests for the ChainedTurnResult dataclass."""

    def test_empty_result(self):
        """Test empty chained result properties."""
        result = ChainedTurnResult()

        assert result.all_successful is True  # vacuously true
        assert result.was_interrupted is False
        assert result.completed_count == 0

    def test_all_successful_property(self):
        """Test all_successful with mixed results."""
        from src.validators.action_validator import ValidationResult
        from src.executor.action_executor import ExecutionResult

        action1 = Action(type=ActionType.MOVE, target="well")
        action2 = Action(type=ActionType.USE, target="bucket")

        subturn1 = SubturnResult(
            action=action1,
            validation=ValidationResult(action=action1, valid=True),
            execution=ExecutionResult(
                action=action1, success=True, outcome="Moved.", state_changes=[]
            ),
            complication=None,
            state_snapshot={},
            continuation_status=ContinuationStatus.CONTINUE,
        )

        subturn2 = SubturnResult(
            action=action2,
            validation=ValidationResult(action=action2, valid=False, reason="No bucket"),
            execution=None,
            complication=None,
            state_snapshot={},
            continuation_status=ContinuationStatus.CONTINUE,
        )

        result = ChainedTurnResult(subturns=[subturn1, subturn2])

        # All VALID subturns succeeded (invalid ones don't count)
        assert result.all_successful is True
        assert result.completed_count == 1

    def test_was_interrupted_property(self):
        """Test was_interrupted with complication."""
        from src.oracle.complication_types import Complication, ComplicationType

        complication = Complication(
            type=ComplicationType.INTERRUPTION,
            description="A snake blocks your path.",
            mechanical_effects=[],
        )

        result = ChainedTurnResult(
            subturns=[],
            interrupting_complication=complication,
        )

        assert result.was_interrupted is True

    def test_to_dict_with_remaining_actions(self):
        """Test serialization with remaining actions."""
        remaining = [
            Action(type=ActionType.USE, target="bucket"),
            Action(type=ActionType.DRINK, target="water"),
        ]

        result = ChainedTurnResult(
            subturns=[],
            remaining_actions=remaining,
            continuation_offered=True,
            continuation_prompt="Do you want to continue?",
        )

        data = result.to_dict()

        assert len(data["remaining_actions"]) == 2
        assert data["remaining_actions"][0]["type"] == "use"
        assert data["remaining_actions"][1]["type"] == "drink"
        assert data["continuation_offered"] is True
        assert data["continuation_prompt"] == "Do you want to continue?"

    def test_from_dict_roundtrip(self):
        """Test deserialization round-trip."""
        remaining = [Action(type=ActionType.LOOK, target=None)]

        original = ChainedTurnResult(
            subturns=[],
            remaining_actions=remaining,
            final_state_snapshot={"player_location": "garden"},
            continuation_offered=False,
        )

        data = original.to_dict()
        restored = ChainedTurnResult.from_dict(data)

        assert len(restored.remaining_actions) == 1
        assert restored.remaining_actions[0].type == ActionType.LOOK
        assert restored.final_state_snapshot["player_location"] == "garden"


class TestSubturnProcessor:
    """Tests for the SubturnProcessor class."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = MagicMock()
        db.flush = MagicMock()
        return db

    @pytest.fixture
    def mock_game_session(self):
        """Create a mock game session."""
        session = MagicMock()
        session.id = 1
        return session

    @pytest.fixture
    def mock_actor(self):
        """Create a mock actor entity."""
        actor = MagicMock()
        actor.id = 1
        actor.entity_key = "player"
        return actor

    @pytest.fixture
    def mock_validator(self):
        """Create a mock action validator."""
        from src.validators.action_validator import ValidationResult

        validator = MagicMock()

        def mock_validate(action, actor, actor_location=None):
            # Default to valid
            return ValidationResult(action=action, valid=True, risk_tags=[])

        validator.validate = MagicMock(side_effect=mock_validate)
        return validator

    @pytest.fixture
    def mock_executor(self):
        """Create a mock action executor."""
        from src.executor.action_executor import ExecutionResult

        executor = MagicMock()

        async def mock_execute(validation, actor):
            action = validation.action
            return ExecutionResult(
                action=action,
                success=True,
                outcome=f"You {action.type.value} successfully.",
                state_changes=[],
                metadata={"to_location": action.target} if action.type == ActionType.MOVE else {},
            )

        executor._execute_action = AsyncMock(side_effect=mock_execute)
        return executor

    @pytest.fixture
    def processor(self, mock_db, mock_game_session, mock_validator, mock_executor):
        """Create a SubturnProcessor with mocked dependencies."""
        return SubturnProcessor(
            db=mock_db,
            game_session=mock_game_session,
            oracle=None,  # No oracle for basic tests
            validator=mock_validator,
            executor=mock_executor,
        )

    @pytest.mark.asyncio
    async def test_process_single_action(self, processor, mock_actor):
        """Test processing a single action."""
        actions = [Action(type=ActionType.LOOK, target=None)]
        initial_state = {"player_location": "kitchen"}

        result = await processor.process_chain(
            actions=actions,
            actor=mock_actor,
            initial_state=initial_state,
        )

        assert len(result.subturns) == 1
        assert result.subturns[0].execution.success is True
        assert result.all_successful is True
        assert not result.was_interrupted

    @pytest.mark.asyncio
    async def test_process_multiple_actions_sequentially(
        self, processor, mock_actor
    ):
        """Test processing multiple actions with state updates."""
        actions = [
            Action(type=ActionType.MOVE, target="well"),
            Action(type=ActionType.USE, target="bucket"),
        ]
        initial_state = {"player_location": "kitchen"}

        result = await processor.process_chain(
            actions=actions,
            actor=mock_actor,
            initial_state=initial_state,
        )

        assert len(result.subturns) == 2
        assert result.completed_count == 2

        # Check state was updated between subturns
        assert result.subturns[0].state_snapshot["player_location"] == "well"
        assert result.final_state_snapshot["player_location"] == "well"

    @pytest.mark.asyncio
    async def test_failed_validation_continues_chain(
        self, processor, mock_actor, mock_validator
    ):
        """Test that failed validation doesn't stop the chain."""
        from src.validators.action_validator import ValidationResult

        # First action fails, second succeeds
        call_count = [0]

        def mixed_validate(action, actor, actor_location=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return ValidationResult(action=action, valid=False, reason="No target")
            return ValidationResult(action=action, valid=True)

        mock_validator.validate = MagicMock(side_effect=mixed_validate)

        actions = [
            Action(type=ActionType.USE, target="nonexistent"),
            Action(type=ActionType.LOOK, target=None),
        ]

        result = await processor.process_chain(
            actions=actions,
            actor=mock_actor,
            initial_state={"player_location": "kitchen"},
        )

        assert len(result.subturns) == 2
        assert result.subturns[0].validation.valid is False
        assert result.subturns[0].execution is None
        assert result.subturns[1].validation.valid is True
        assert result.subturns[1].execution.success is True

    @pytest.mark.asyncio
    async def test_state_updates_location_on_move(self, processor, mock_actor):
        """Test that MOVE updates the location state."""
        actions = [Action(type=ActionType.MOVE, target="garden")]
        initial_state = {"player_location": "kitchen"}

        result = await processor.process_chain(
            actions=actions,
            actor=mock_actor,
            initial_state=initial_state,
        )

        assert result.final_state_snapshot["player_location"] == "garden"
        assert result.final_state_snapshot.get("location_changed") is True
        assert result.final_state_snapshot.get("previous_location") == "kitchen"


class TestContinuationEvaluation:
    """Tests for continuation evaluation logic."""

    @pytest.fixture
    def processor(self):
        """Create a processor for testing continuation logic."""
        return SubturnProcessor(
            db=MagicMock(),
            game_session=MagicMock(),
        )

    def test_has_incapacitating_effect_unconscious(self, processor):
        """Test that unconscious status is detected."""
        from src.oracle.complication_types import (
            Complication,
            ComplicationType,
            Effect,
            EffectType,
        )

        complication = Complication(
            type=ComplicationType.COST,
            description="You fall unconscious.",
            mechanical_effects=[
                Effect(type=EffectType.STATUS_ADD, value="unconscious"),
            ],
        )

        assert processor._has_incapacitating_effect(complication) is True

    def test_has_incapacitating_effect_none(self, processor):
        """Test that HP loss is not incapacitating."""
        from src.oracle.complication_types import (
            Complication,
            ComplicationType,
            Effect,
            EffectType,
        )

        complication = Complication(
            type=ComplicationType.COST,
            description="You stub your toe.",
            mechanical_effects=[
                Effect(type=EffectType.HP_LOSS, value=1),
            ],
        )

        assert processor._has_incapacitating_effect(complication) is False

    def test_actions_still_plausible_no_spawn(self, processor):
        """Test that actions are plausible without entity spawn."""
        from src.oracle.complication_types import (
            Complication,
            ComplicationType,
        )

        complication = Complication(
            type=ComplicationType.DISCOVERY,
            description="You find a coin.",
            mechanical_effects=[],
        )

        actions = [Action(type=ActionType.MOVE, target="garden")]

        assert processor._actions_still_plausible(actions, complication) is True

    def test_actions_still_plausible_hostile_spawn_with_combat(self, processor):
        """Test that combat actions are plausible after hostile spawn."""
        from src.oracle.complication_types import (
            Complication,
            ComplicationType,
            Effect,
            EffectType,
        )

        complication = Complication(
            type=ComplicationType.INTERRUPTION,
            description="A wolf appears!",
            mechanical_effects=[
                Effect(type=EffectType.SPAWN_ENTITY, value="wolf"),
            ],
        )

        actions = [Action(type=ActionType.ATTACK, target="wolf")]

        assert processor._actions_still_plausible(actions, complication) is True

    def test_actions_still_plausible_hostile_spawn_with_non_combat(self, processor):
        """Test that non-combat actions are implausible after hostile spawn."""
        from src.oracle.complication_types import (
            Complication,
            ComplicationType,
            Effect,
            EffectType,
        )

        complication = Complication(
            type=ComplicationType.INTERRUPTION,
            description="A wolf appears!",
            mechanical_effects=[
                Effect(type=EffectType.SPAWN_ENTITY, value="wolf"),
            ],
        )

        actions = [Action(type=ActionType.MOVE, target="garden")]

        assert processor._actions_still_plausible(actions, complication) is False

    def test_has_significant_cost_hp_loss(self, processor):
        """Test that HP loss is significant cost."""
        from src.oracle.complication_types import (
            Complication,
            ComplicationType,
            Effect,
            EffectType,
        )

        complication = Complication(
            type=ComplicationType.COST,
            description="You slip and hurt yourself.",
            mechanical_effects=[
                Effect(type=EffectType.HP_LOSS, value=5),
            ],
        )

        assert processor._has_significant_cost(complication) is True

    def test_has_significant_cost_discovery(self, processor):
        """Test that discovery is not significant cost."""
        from src.oracle.complication_types import (
            Complication,
            ComplicationType,
        )

        complication = Complication(
            type=ComplicationType.DISCOVERY,
            description="You notice something shiny.",
            mechanical_effects=[],
        )

        assert processor._has_significant_cost(complication) is False


class TestLocationDanger:
    """Tests for location danger level detection."""

    @pytest.fixture
    def processor(self):
        """Create a processor for testing."""
        db = MagicMock()
        game_session = MagicMock()
        return SubturnProcessor(db=db, game_session=game_session)

    def test_default_neutral(self, processor):
        """Test that unknown location defaults to neutral."""
        with patch("src.managers.location_manager.LocationManager") as mock_lm:
            mock_instance = MagicMock()
            mock_instance.get_location.return_value = None
            mock_lm.return_value = mock_instance

            danger = processor._get_location_danger("unknown_place")
            assert danger == "neutral"

    def test_safe_keyword_detection(self, processor):
        """Test that 'home' keyword triggers safe."""
        with patch("src.managers.location_manager.LocationManager") as mock_lm:
            mock_instance = MagicMock()
            mock_instance.get_location.return_value = None
            mock_lm.return_value = mock_instance

            danger = processor._get_location_danger("player_home")
            assert danger == "safe"

    def test_dangerous_keyword_detection(self, processor):
        """Test that 'dungeon' keyword triggers dangerous."""
        with patch("src.managers.location_manager.LocationManager") as mock_lm:
            mock_instance = MagicMock()
            mock_instance.get_location.return_value = None
            mock_lm.return_value = mock_instance

            danger = processor._get_location_danger("ancient_dungeon")
            assert danger == "dangerous"

    def test_risky_keyword_detection(self, processor):
        """Test that 'forest' keyword triggers risky."""
        with patch("src.managers.location_manager.LocationManager") as mock_lm:
            mock_instance = MagicMock()
            mock_instance.get_location.return_value = None
            mock_lm.return_value = mock_instance

            danger = processor._get_location_danger("dark_forest")
            assert danger == "risky"


class TestContinuationPrompt:
    """Tests for continuation prompt generation."""

    @pytest.fixture
    def processor(self):
        """Create a processor for testing."""
        return SubturnProcessor(
            db=MagicMock(),
            game_session=MagicMock(),
        )

    def test_build_prompt_with_actions(self, processor):
        """Test prompt generation with remaining actions."""
        from src.oracle.complication_types import Complication, ComplicationType

        remaining = [
            Action(type=ActionType.USE, target="bucket"),
            Action(type=ActionType.DRINK, target="water"),
        ]
        complication = Complication(
            type=ComplicationType.COST,
            description="Test",
            mechanical_effects=[],
        )

        prompt = processor._build_continuation_prompt(remaining, complication)

        assert "use" in prompt.lower()
        assert "bucket" in prompt.lower()
        assert "continue" in prompt.lower()

    def test_build_prompt_empty_actions(self, processor):
        """Test prompt generation with no remaining actions."""
        from src.oracle.complication_types import Complication, ComplicationType

        complication = Complication(
            type=ComplicationType.COST,
            description="Test",
            mechanical_effects=[],
        )

        prompt = processor._build_continuation_prompt([], complication)

        assert prompt == ""
