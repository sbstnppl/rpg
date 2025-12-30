"""Tests for BranchCollapseManager."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock

from src.dice.types import (
    AdvantageType,
    DiceExpression,
    OutcomeTier,
    RollResult,
    SkillCheckResult,
)
from src.world_server.schemas import PredictionReason
from src.world_server.quantum.schemas import (
    ActionPrediction,
    ActionType,
    DeltaType,
    GMDecision,
    OutcomeVariant,
    QuantumBranch,
    QuantumMetrics,
    StateDelta,
    VariantType,
)
from src.world_server.quantum.collapse import (
    BranchCollapseManager,
    CollapseResult,
    DeltaApplicationResult,
    StaleStateError,
    extract_entity_references,
    format_skill_check_result,
    strip_entity_references,
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
def sample_action():
    """Create a sample action prediction."""
    return ActionPrediction(
        action_type=ActionType.INTERACT_NPC,
        target_key="guard_001",
        input_patterns=["talk.*guard"],
        probability=0.25,
        reason=PredictionReason.ADJACENT,
    )


@pytest.fixture
def sample_gm_decision():
    """Create a sample GM decision."""
    return GMDecision(
        decision_type="no_twist",
        probability=0.7,
        grounding_facts=[],
    )


@pytest.fixture
def sample_branch_no_dice(sample_action, sample_gm_decision):
    """Create a branch that doesn't require dice."""
    return QuantumBranch(
        branch_key="village::interact_npc::guard_001::no_twist",
        action=sample_action,
        gm_decision=sample_gm_decision,
        variants={
            "success": OutcomeVariant(
                variant_type=VariantType.SUCCESS,
                requires_dice=False,
                narrative="You approach [guard_001:the guard] and strike up a conversation.",
                state_deltas=[],
                time_passed_minutes=5,
            ),
        },
        generated_at=datetime.now(),
        generation_time_ms=50.0,
    )


@pytest.fixture
def sample_branch_with_dice(sample_action, sample_gm_decision):
    """Create a branch that requires dice."""
    return QuantumBranch(
        branch_key="village::interact_npc::guard_001::no_twist",
        action=sample_action,
        gm_decision=sample_gm_decision,
        variants={
            "success": OutcomeVariant(
                variant_type=VariantType.SUCCESS,
                requires_dice=True,
                skill="persuasion",
                dc=15,
                narrative="[guard_001:The guard] nods and agrees to help you.",
                state_deltas=[],
                time_passed_minutes=5,
            ),
            "failure": OutcomeVariant(
                variant_type=VariantType.FAILURE,
                requires_dice=True,
                skill="persuasion",
                dc=15,
                narrative="[guard_001:The guard] shakes his head dismissively.",
                state_deltas=[],
                time_passed_minutes=5,
            ),
            "critical_success": OutcomeVariant(
                variant_type=VariantType.CRITICAL_SUCCESS,
                requires_dice=True,
                skill="persuasion",
                dc=15,
                narrative="[guard_001:The guard] is impressed and offers extra information!",
                state_deltas=[],
                time_passed_minutes=5,
            ),
            "critical_failure": OutcomeVariant(
                variant_type=VariantType.CRITICAL_FAILURE,
                requires_dice=True,
                skill="persuasion",
                dc=15,
                narrative="[guard_001:The guard] becomes suspicious and hostile.",
                state_deltas=[],
                time_passed_minutes=5,
            ),
        },
        generated_at=datetime.now(),
        generation_time_ms=100.0,
    )


def create_skill_check_result(
    total: int,
    dc: int,
    is_critical_success: bool = False,
    is_critical_failure: bool = False,
    is_auto_success: bool = False,
) -> SkillCheckResult:
    """Helper to create skill check results for testing."""
    success = total >= dc

    if is_auto_success:
        return SkillCheckResult(
            roll_result=None,
            dc=dc,
            success=True,
            margin=total - dc,
            is_critical_success=False,
            is_critical_failure=False,
            advantage_type=AdvantageType.NORMAL,
            outcome_tier=OutcomeTier.CLEAR_SUCCESS,
            is_auto_success=True,
        )

    roll_result = RollResult(
        expression=DiceExpression(num_dice=2, die_size=10, modifier=0),
        individual_rolls=(10, 10) if is_critical_success else (1, 1) if is_critical_failure else (5, 5),
        modifier=0,
        total=total,
    )

    return SkillCheckResult(
        roll_result=roll_result,
        dc=dc,
        success=success,
        margin=total - dc,
        is_critical_success=is_critical_success,
        is_critical_failure=is_critical_failure,
        advantage_type=AdvantageType.NORMAL,
        outcome_tier=OutcomeTier.CLEAR_SUCCESS if success else OutcomeTier.CLEAR_FAILURE,
        is_auto_success=False,
    )


class TestStripEntityReferences:
    """Tests for strip_entity_references function."""

    def test_strip_single_reference(self):
        """Test stripping a single entity reference."""
        text = "You talk to [guard_001:the guard]."
        result = strip_entity_references(text)
        assert result == "You talk to the guard."

    def test_strip_multiple_references(self):
        """Test stripping multiple entity references."""
        text = "[innkeeper:Tom] hands you [ale_mug:a mug of ale]."
        result = strip_entity_references(text)
        assert result == "Tom hands you a mug of ale."

    def test_no_references(self):
        """Test text with no entity references."""
        text = "You walk down the street."
        result = strip_entity_references(text)
        assert result == "You walk down the street."

    def test_preserve_formatting(self):
        """Test that other formatting is preserved."""
        text = "The [guard:guard] says, \"Hello, traveler!\""
        result = strip_entity_references(text)
        assert result == "The guard says, \"Hello, traveler!\""

    def test_complex_display_text(self):
        """Test with complex display text containing spaces."""
        text = "[ancient_sword_001:the ancient gleaming sword]"
        result = strip_entity_references(text)
        assert result == "the ancient gleaming sword"


class TestExtractEntityReferences:
    """Tests for extract_entity_references function."""

    def test_extract_single(self):
        """Test extracting a single reference."""
        text = "You see [guard_001:the guard]."
        result = extract_entity_references(text)
        assert result == [("guard_001", "the guard")]

    def test_extract_multiple(self):
        """Test extracting multiple references."""
        text = "[npc_001:Tom] talks to [npc_002:Sara]."
        result = extract_entity_references(text)
        assert result == [("npc_001", "Tom"), ("npc_002", "Sara")]

    def test_extract_none(self):
        """Test extracting from text with no references."""
        text = "Nothing special here."
        result = extract_entity_references(text)
        assert result == []


class TestCollapseManagerInit:
    """Tests for BranchCollapseManager initialization."""

    def test_initialization(self, mock_db, mock_game_session):
        """Test basic initialization."""
        manager = BranchCollapseManager(mock_db, mock_game_session)

        assert manager.db == mock_db
        assert manager.game_session == mock_game_session
        assert manager.metrics is not None

    def test_initialization_with_metrics(self, mock_db, mock_game_session):
        """Test initialization with custom metrics."""
        metrics = QuantumMetrics()
        manager = BranchCollapseManager(mock_db, mock_game_session, metrics=metrics)

        assert manager.metrics is metrics


class TestCollapseNoDice:
    """Tests for collapsing branches without dice rolls."""

    @pytest.mark.asyncio
    async def test_collapse_no_dice_branch(
        self, mock_db, mock_game_session, sample_branch_no_dice
    ):
        """Test collapsing a branch that doesn't require dice."""
        manager = BranchCollapseManager(mock_db, mock_game_session)

        result = await manager.collapse_branch(
            branch=sample_branch_no_dice,
            player_input="talk to guard",
            turn_number=1,
            apply_deltas=False,
        )

        assert result is not None
        assert result.selected_variant == VariantType.SUCCESS
        assert result.skill_check_result is None
        assert "the guard" in result.narrative
        assert "[guard_001:" not in result.narrative  # References stripped
        assert "[guard_001:" in result.raw_narrative  # Preserved in raw

    @pytest.mark.asyncio
    async def test_collapse_updates_branch(
        self, mock_db, mock_game_session, sample_branch_no_dice
    ):
        """Test that collapsing marks the branch as collapsed."""
        manager = BranchCollapseManager(mock_db, mock_game_session)

        assert not sample_branch_no_dice.is_collapsed

        await manager.collapse_branch(
            branch=sample_branch_no_dice,
            player_input="talk to guard",
            turn_number=1,
            apply_deltas=False,
        )

        assert sample_branch_no_dice.is_collapsed
        assert sample_branch_no_dice.collapsed_variant == "success"


class TestCollapseWithDice:
    """Tests for collapsing branches with dice rolls."""

    @pytest.mark.asyncio
    async def test_collapse_success(
        self, mock_db, mock_game_session, sample_branch_with_dice
    ):
        """Test collapsing with a successful roll."""
        manager = BranchCollapseManager(mock_db, mock_game_session)

        # Mock dice roll to return success
        with patch("src.world_server.quantum.collapse.make_skill_check") as mock_check:
            mock_check.return_value = create_skill_check_result(
                total=18, dc=15, is_critical_success=False
            )

            result = await manager.collapse_branch(
                branch=sample_branch_with_dice,
                player_input="persuade guard",
                turn_number=1,
                apply_deltas=False,
            )

        assert result.selected_variant == VariantType.SUCCESS
        assert result.skill_check_result is not None
        assert result.skill_check_result.success
        assert "agrees to help" in result.narrative

    @pytest.mark.asyncio
    async def test_collapse_failure(
        self, mock_db, mock_game_session, sample_branch_with_dice
    ):
        """Test collapsing with a failed roll."""
        manager = BranchCollapseManager(mock_db, mock_game_session)

        with patch("src.world_server.quantum.collapse.make_skill_check") as mock_check:
            mock_check.return_value = create_skill_check_result(
                total=10, dc=15, is_critical_success=False
            )

            result = await manager.collapse_branch(
                branch=sample_branch_with_dice,
                player_input="persuade guard",
                turn_number=1,
                apply_deltas=False,
            )

        assert result.selected_variant == VariantType.FAILURE
        assert not result.skill_check_result.success
        assert "shakes his head" in result.narrative

    @pytest.mark.asyncio
    async def test_collapse_critical_success(
        self, mock_db, mock_game_session, sample_branch_with_dice
    ):
        """Test collapsing with a critical success (double-10)."""
        manager = BranchCollapseManager(mock_db, mock_game_session)

        with patch("src.world_server.quantum.collapse.make_skill_check") as mock_check:
            mock_check.return_value = create_skill_check_result(
                total=20, dc=15, is_critical_success=True
            )

            result = await manager.collapse_branch(
                branch=sample_branch_with_dice,
                player_input="persuade guard",
                turn_number=1,
                apply_deltas=False,
            )

        assert result.selected_variant == VariantType.CRITICAL_SUCCESS
        assert result.skill_check_result.is_critical_success
        assert "extra information" in result.narrative

    @pytest.mark.asyncio
    async def test_collapse_critical_failure(
        self, mock_db, mock_game_session, sample_branch_with_dice
    ):
        """Test collapsing with a critical failure (double-1)."""
        manager = BranchCollapseManager(mock_db, mock_game_session)

        with patch("src.world_server.quantum.collapse.make_skill_check") as mock_check:
            mock_check.return_value = create_skill_check_result(
                total=2, dc=15, is_critical_failure=True
            )

            result = await manager.collapse_branch(
                branch=sample_branch_with_dice,
                player_input="persuade guard",
                turn_number=1,
                apply_deltas=False,
            )

        assert result.selected_variant == VariantType.CRITICAL_FAILURE
        assert result.skill_check_result.is_critical_failure
        assert "suspicious and hostile" in result.narrative


class TestVariantSelection:
    """Tests for variant selection logic."""

    @pytest.mark.asyncio
    async def test_fallback_to_success_for_missing_critical(
        self, mock_db, mock_game_session, sample_action, sample_gm_decision
    ):
        """Test fallback when critical variant is missing."""
        # Branch with only success/failure, no critical variants
        branch = QuantumBranch(
            branch_key="test::interact_npc::npc::no_twist",
            action=sample_action,
            gm_decision=sample_gm_decision,
            variants={
                "success": OutcomeVariant(
                    variant_type=VariantType.SUCCESS,
                    requires_dice=True,
                    dc=15,
                    narrative="Success!",
                ),
                "failure": OutcomeVariant(
                    variant_type=VariantType.FAILURE,
                    requires_dice=True,
                    dc=15,
                    narrative="Failure!",
                ),
            },
            generated_at=datetime.now(),
        )

        manager = BranchCollapseManager(mock_db, mock_game_session)

        # Critical success should fall back to regular success
        with patch("src.world_server.quantum.collapse.make_skill_check") as mock_check:
            mock_check.return_value = create_skill_check_result(
                total=20, dc=15, is_critical_success=True
            )

            result = await manager.collapse_branch(
                branch=branch,
                player_input="test",
                turn_number=1,
                apply_deltas=False,
            )

        assert result.selected_variant == VariantType.SUCCESS

    @pytest.mark.asyncio
    async def test_fallback_to_failure_for_missing_critical_failure(
        self, mock_db, mock_game_session, sample_action, sample_gm_decision
    ):
        """Test fallback when critical_failure variant is missing."""
        branch = QuantumBranch(
            branch_key="test::interact_npc::npc::no_twist",
            action=sample_action,
            gm_decision=sample_gm_decision,
            variants={
                "success": OutcomeVariant(
                    variant_type=VariantType.SUCCESS,
                    requires_dice=True,
                    dc=15,
                    narrative="Success!",
                ),
                "failure": OutcomeVariant(
                    variant_type=VariantType.FAILURE,
                    requires_dice=True,
                    dc=15,
                    narrative="Failure!",
                ),
            },
            generated_at=datetime.now(),
        )

        manager = BranchCollapseManager(mock_db, mock_game_session)

        with patch("src.world_server.quantum.collapse.make_skill_check") as mock_check:
            mock_check.return_value = create_skill_check_result(
                total=2, dc=15, is_critical_failure=True
            )

            result = await manager.collapse_branch(
                branch=branch,
                player_input="test",
                turn_number=1,
                apply_deltas=False,
            )

        assert result.selected_variant == VariantType.FAILURE


class TestDeltaValidation:
    """Tests for state delta validation."""

    @pytest.mark.asyncio
    async def test_collapse_with_valid_deltas(
        self, mock_db, mock_game_session, sample_action, sample_gm_decision
    ):
        """Test collapse with deltas that pass validation."""
        branch = QuantumBranch(
            branch_key="test::interact_npc::npc::no_twist",
            action=sample_action,
            gm_decision=sample_gm_decision,
            variants={
                "success": OutcomeVariant(
                    variant_type=VariantType.SUCCESS,
                    requires_dice=False,
                    narrative="You get the item.",
                    state_deltas=[
                        StateDelta(
                            delta_type=DeltaType.TRANSFER_ITEM,
                            target_key="sword_001",
                            changes={"from": "chest", "to": "player"},
                        ),
                    ],
                ),
            },
            generated_at=datetime.now(),
        )

        manager = BranchCollapseManager(mock_db, mock_game_session)

        # Should not raise
        result = await manager.collapse_branch(
            branch=branch,
            player_input="take sword",
            turn_number=1,
            apply_deltas=False,  # Skip actual application
            validate_deltas=True,
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_collapse_with_stale_delta_raises(
        self, mock_db, mock_game_session, sample_action, sample_gm_decision
    ):
        """Test that stale deltas raise StaleStateError."""
        branch = QuantumBranch(
            branch_key="test::interact_npc::npc::no_twist",
            action=sample_action,
            gm_decision=sample_gm_decision,
            variants={
                "success": OutcomeVariant(
                    variant_type=VariantType.SUCCESS,
                    requires_dice=False,
                    narrative="You get the item.",
                    state_deltas=[
                        StateDelta(
                            delta_type=DeltaType.TRANSFER_ITEM,
                            target_key="sword_001",
                            changes={"from": "chest", "to": "player"},
                            expected_state={"location": "chest"},  # This will fail
                        ),
                    ],
                ),
            },
            generated_at=datetime.now(),
        )

        manager = BranchCollapseManager(mock_db, mock_game_session)

        # Mock _get_current_state to return different state
        async def mock_get_state(key, delta_type):
            return {"location": "ground"}  # Different from expected

        manager._get_current_state = mock_get_state

        with pytest.raises(StaleStateError):
            await manager.collapse_branch(
                branch=branch,
                player_input="take sword",
                turn_number=1,
                validate_deltas=True,
            )


class TestMetricsTracking:
    """Tests for metrics tracking during collapse."""

    @pytest.mark.asyncio
    async def test_metrics_recorded_on_collapse(
        self, mock_db, mock_game_session, sample_branch_no_dice
    ):
        """Test that metrics are recorded on collapse."""
        metrics = QuantumMetrics()
        manager = BranchCollapseManager(mock_db, mock_game_session, metrics=metrics)

        await manager.collapse_branch(
            branch=sample_branch_no_dice,
            player_input="talk to guard",
            turn_number=1,
            apply_deltas=False,
        )

        assert metrics.branches_collapsed == 1
        assert metrics.no_twists == 1
        assert metrics.successes == 1

    @pytest.mark.asyncio
    async def test_twist_metrics_recorded(
        self, mock_db, mock_game_session, sample_action
    ):
        """Test that twist metrics are recorded."""
        twist_decision = GMDecision(
            decision_type="theft_accusation",
            probability=0.15,
            grounding_facts=["recent_theft"],
        )

        branch = QuantumBranch(
            branch_key="test::interact_npc::npc::theft_accusation",
            action=sample_action,
            gm_decision=twist_decision,
            variants={
                "success": OutcomeVariant(
                    variant_type=VariantType.SUCCESS,
                    requires_dice=False,
                    narrative="The guard accuses you!",
                ),
            },
            generated_at=datetime.now(),
        )

        metrics = QuantumMetrics()
        manager = BranchCollapseManager(mock_db, mock_game_session, metrics=metrics)

        result = await manager.collapse_branch(
            branch=branch,
            player_input="approach",
            turn_number=1,
            apply_deltas=False,
        )

        assert result.had_twist
        assert metrics.twists_applied == 1


class TestCollapseResult:
    """Tests for CollapseResult dataclass."""

    @pytest.mark.asyncio
    async def test_collapse_result_fields(
        self, mock_db, mock_game_session, sample_branch_no_dice
    ):
        """Test that CollapseResult has all expected fields."""
        manager = BranchCollapseManager(mock_db, mock_game_session)

        result = await manager.collapse_branch(
            branch=sample_branch_no_dice,
            player_input="talk to guard",
            turn_number=1,
            apply_deltas=False,
        )

        assert hasattr(result, "narrative")
        assert hasattr(result, "raw_narrative")
        assert hasattr(result, "state_deltas")
        assert hasattr(result, "time_passed_minutes")
        assert hasattr(result, "skill_check_result")
        assert hasattr(result, "selected_variant")
        assert hasattr(result, "collapse_time_ms")
        assert hasattr(result, "was_cache_hit")
        assert hasattr(result, "gm_decision")
        assert hasattr(result, "had_twist")

        assert result.time_passed_minutes == 5
        assert result.collapse_time_ms > 0


class TestFormatSkillCheckResult:
    """Tests for format_skill_check_result function."""

    def test_format_auto_success(self):
        """Test formatting auto-success."""
        result = create_skill_check_result(
            total=20, dc=10, is_auto_success=True
        )
        formatted = format_skill_check_result(result)
        assert "Auto-success" in formatted
        assert "DC 10" in formatted

    def test_format_regular_success(self):
        """Test formatting regular success."""
        result = create_skill_check_result(total=18, dc=15)
        formatted = format_skill_check_result(result)
        assert "DC 15" in formatted
        assert "18" in formatted
        assert "Success" in formatted

    def test_format_critical_success(self):
        """Test formatting critical success."""
        result = create_skill_check_result(
            total=20, dc=15, is_critical_success=True
        )
        formatted = format_skill_check_result(result)
        assert "Critical Success" in formatted

    def test_format_critical_failure(self):
        """Test formatting critical failure."""
        result = create_skill_check_result(
            total=2, dc=15, is_critical_failure=True
        )
        formatted = format_skill_check_result(result)
        assert "Critical Failure" in formatted


class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.asyncio
    async def test_empty_variants_fallback(
        self, mock_db, mock_game_session, sample_action, sample_gm_decision
    ):
        """Test handling of branch with minimal variants."""
        branch = QuantumBranch(
            branch_key="test::observe::none::no_twist",
            action=sample_action,
            gm_decision=sample_gm_decision,
            variants={
                "success": OutcomeVariant(
                    variant_type=VariantType.SUCCESS,
                    requires_dice=False,
                    narrative="You look around.",
                ),
            },
            generated_at=datetime.now(),
        )

        manager = BranchCollapseManager(mock_db, mock_game_session)

        result = await manager.collapse_branch(
            branch=branch,
            player_input="look",
            turn_number=1,
            apply_deltas=False,
        )

        assert result.narrative == "You look around."

    @pytest.mark.asyncio
    async def test_collapse_preserves_gm_decision(
        self, mock_db, mock_game_session, sample_branch_no_dice
    ):
        """Test that GM decision is preserved in result."""
        manager = BranchCollapseManager(mock_db, mock_game_session)

        result = await manager.collapse_branch(
            branch=sample_branch_no_dice,
            player_input="talk to guard",
            turn_number=1,
            apply_deltas=False,
        )

        assert result.gm_decision is not None
        assert result.gm_decision.decision_type == "no_twist"

    @pytest.mark.asyncio
    async def test_modifiers_passed_to_skill_check(
        self, mock_db, mock_game_session, sample_branch_with_dice
    ):
        """Test that attribute and skill modifiers are passed to dice roll."""
        manager = BranchCollapseManager(mock_db, mock_game_session)

        with patch("src.world_server.quantum.collapse.make_skill_check") as mock_check:
            mock_check.return_value = create_skill_check_result(total=20, dc=15)

            await manager.collapse_branch(
                branch=sample_branch_with_dice,
                player_input="persuade guard",
                turn_number=1,
                attribute_modifier=3,
                skill_modifier=5,
                advantage_type=AdvantageType.ADVANTAGE,
                apply_deltas=False,
            )

            # Verify core parameters; skill_name/attribute_key may vary
            mock_check.assert_called_once()
            call_kwargs = mock_check.call_args.kwargs
            assert call_kwargs["dc"] == 15
            assert call_kwargs["attribute_modifier"] == 3
            assert call_kwargs["skill_modifier"] == 5
            assert call_kwargs["advantage_type"] == AdvantageType.ADVANTAGE


class TestGetEntityId:
    """Tests for _get_entity_id helper method."""

    def test_get_entity_id_found(self, mock_db, mock_game_session):
        """Test getting entity ID when entity exists."""
        manager = BranchCollapseManager(mock_db, mock_game_session)

        with patch("src.world_server.quantum.collapse.EntityManager") as mock_em:
            mock_entity = MagicMock()
            mock_entity.id = 42
            mock_em.return_value.get_entity.return_value = mock_entity

            result = manager._get_entity_id("guard_001")

            assert result == 42
            mock_em.return_value.get_entity.assert_called_once_with("guard_001")

    def test_get_entity_id_not_found(self, mock_db, mock_game_session):
        """Test getting entity ID when entity doesn't exist."""
        manager = BranchCollapseManager(mock_db, mock_game_session)

        with patch("src.world_server.quantum.collapse.EntityManager") as mock_em:
            mock_em.return_value.get_entity.return_value = None

            result = manager._get_entity_id("nonexistent")

            assert result is None


class TestGetCurrentState:
    """Tests for _get_current_state method."""

    @pytest.mark.asyncio
    async def test_get_state_for_update_entity(self, mock_db, mock_game_session):
        """Test getting current state for UPDATE_ENTITY delta."""
        manager = BranchCollapseManager(mock_db, mock_game_session)

        with patch("src.world_server.quantum.collapse.EntityManager") as mock_em:
            mock_entity = MagicMock()
            mock_entity.location_key = "tavern_main"
            mock_entity.is_active = True
            mock_entity.activity = "drinking"
            mock_em.return_value.get_entity.return_value = mock_entity

            result = await manager._get_current_state("npc_001", DeltaType.UPDATE_ENTITY)

            assert result["location_key"] == "tavern_main"
            assert result["is_active"] is True
            assert result["activity"] == "drinking"

    @pytest.mark.asyncio
    async def test_get_state_for_transfer_item(self, mock_db, mock_game_session):
        """Test getting current state for TRANSFER_ITEM delta."""
        manager = BranchCollapseManager(mock_db, mock_game_session)

        with patch("src.world_server.quantum.collapse.ItemManager") as mock_im:
            mock_item = MagicMock()
            mock_item.holder_id = 10
            mock_item.owner_id = 5
            mock_im.return_value.get_item.return_value = mock_item

            result = await manager._get_current_state("sword_001", DeltaType.TRANSFER_ITEM)

            assert result["holder_id"] == 10
            assert result["owner_id"] == 5

    @pytest.mark.asyncio
    async def test_get_state_for_update_location(self, mock_db, mock_game_session):
        """Test getting current state for UPDATE_LOCATION delta."""
        manager = BranchCollapseManager(mock_db, mock_game_session)

        with patch("src.world_server.quantum.collapse.EntityManager") as mock_em:
            mock_entity = MagicMock()
            mock_entity.location_key = "village_square"
            mock_em.return_value.get_entity.return_value = mock_entity

            result = await manager._get_current_state("npc_001", DeltaType.UPDATE_LOCATION)

            assert result["location_key"] == "village_square"

    @pytest.mark.asyncio
    async def test_get_state_returns_empty_for_create_entity(self, mock_db, mock_game_session):
        """Test that CREATE_ENTITY returns empty dict (no validation needed)."""
        manager = BranchCollapseManager(mock_db, mock_game_session)

        result = await manager._get_current_state("new_entity", DeltaType.CREATE_ENTITY)

        assert result == {}


class TestApplySingleDelta:
    """Tests for _apply_single_delta method."""

    @pytest.mark.asyncio
    async def test_apply_create_entity(self, mock_db, mock_game_session):
        """Test applying CREATE_ENTITY delta."""
        manager = BranchCollapseManager(mock_db, mock_game_session)

        delta = StateDelta(
            delta_type=DeltaType.CREATE_ENTITY,
            target_key="new_npc_001",
            changes={
                "entity_key": "new_npc_001",
                "display_name": "A Mysterious Stranger",
                "entity_type": "npc",
                "location_key": "tavern_main",
            },
        )

        with patch("src.world_server.quantum.collapse.EntityManager") as mock_em:
            await manager._apply_single_delta(delta, turn_number=5)

            mock_em.return_value.create_entity.assert_called_once()
            call_kwargs = mock_em.return_value.create_entity.call_args.kwargs
            assert call_kwargs["entity_key"] == "new_npc_001"
            assert call_kwargs["display_name"] == "A Mysterious Stranger"

    @pytest.mark.asyncio
    async def test_apply_delete_entity(self, mock_db, mock_game_session):
        """Test applying DELETE_ENTITY delta."""
        manager = BranchCollapseManager(mock_db, mock_game_session)

        delta = StateDelta(
            delta_type=DeltaType.DELETE_ENTITY,
            target_key="npc_to_remove",
            changes={},
        )

        with patch("src.world_server.quantum.collapse.EntityManager") as mock_em:
            await manager._apply_single_delta(delta, turn_number=5)

            mock_em.return_value.mark_inactive.assert_called_once_with("npc_to_remove")

    @pytest.mark.asyncio
    async def test_apply_update_entity_location(self, mock_db, mock_game_session):
        """Test applying UPDATE_ENTITY delta with location change."""
        manager = BranchCollapseManager(mock_db, mock_game_session)

        delta = StateDelta(
            delta_type=DeltaType.UPDATE_ENTITY,
            target_key="npc_001",
            changes={"location_key": "market_square"},
        )

        with patch("src.world_server.quantum.collapse.EntityManager") as mock_em:
            await manager._apply_single_delta(delta, turn_number=5)

            mock_em.return_value.update_location.assert_called_once_with(
                "npc_001", "market_square"
            )

    @pytest.mark.asyncio
    async def test_apply_transfer_item(self, mock_db, mock_game_session):
        """Test applying TRANSFER_ITEM delta."""
        manager = BranchCollapseManager(mock_db, mock_game_session)

        delta = StateDelta(
            delta_type=DeltaType.TRANSFER_ITEM,
            target_key="sword_001",
            changes={"to_entity_key": "player_001"},
        )

        with patch("src.world_server.quantum.collapse.ItemManager") as mock_im:
            with patch.object(manager, "_get_entity_id", return_value=42):
                await manager._apply_single_delta(delta, turn_number=5)

                mock_im.return_value.transfer_item.assert_called_once()
                call_kwargs = mock_im.return_value.transfer_item.call_args.kwargs
                assert call_kwargs["item_key"] == "sword_001"
                assert call_kwargs["to_entity_id"] == 42

    @pytest.mark.asyncio
    async def test_apply_update_need(self, mock_db, mock_game_session):
        """Test applying UPDATE_NEED delta."""
        manager = BranchCollapseManager(mock_db, mock_game_session)

        delta = StateDelta(
            delta_type=DeltaType.UPDATE_NEED,
            target_key="player_001",
            changes={
                "entity_key": "player_001",
                "need_name": "hunger",
                "amount": 20,
            },
        )

        with patch("src.world_server.quantum.collapse.NeedsManager") as mock_nm:
            with patch.object(manager, "_get_entity_id", return_value=1):
                await manager._apply_single_delta(delta, turn_number=5)

                mock_nm.return_value.satisfy_need.assert_called_once_with(
                    entity_id=1,
                    need_name="hunger",
                    amount=20,
                    turn=5,
                )

    @pytest.mark.asyncio
    async def test_apply_update_relationship(self, mock_db, mock_game_session):
        """Test applying UPDATE_RELATIONSHIP delta."""
        manager = BranchCollapseManager(mock_db, mock_game_session)

        delta = StateDelta(
            delta_type=DeltaType.UPDATE_RELATIONSHIP,
            target_key="relationship",
            changes={
                "from_key": "npc_001",
                "to_key": "player_001",
                "dimension": "trust",
                "delta": 10,
                "reason": "helped in combat",
            },
        )

        with patch("src.world_server.quantum.collapse.RelationshipManager") as mock_rm:
            with patch.object(manager, "_get_entity_id", side_effect=[5, 1]):
                await manager._apply_single_delta(delta, turn_number=5)

                mock_rm.return_value.update_attitude.assert_called_once_with(
                    from_id=5,
                    to_id=1,
                    dimension="trust",
                    delta=10,
                    reason="helped in combat",
                )

    @pytest.mark.asyncio
    async def test_apply_record_fact(self, mock_db, mock_game_session):
        """Test applying RECORD_FACT delta."""
        manager = BranchCollapseManager(mock_db, mock_game_session)

        delta = StateDelta(
            delta_type=DeltaType.RECORD_FACT,
            target_key="npc_001",
            changes={
                "subject_type": "entity",
                "subject_key": "npc_001",
                "predicate": "knows_secret",
                "value": "the treasure location",
            },
        )

        with patch("src.world_server.quantum.collapse.FactManager") as mock_fm:
            await manager._apply_single_delta(delta, turn_number=5)

            mock_fm.return_value.record_fact.assert_called_once()
            call_kwargs = mock_fm.return_value.record_fact.call_args.kwargs
            assert call_kwargs["subject_key"] == "npc_001"
            assert call_kwargs["predicate"] == "knows_secret"
            assert call_kwargs["value"] == "the treasure location"

    @pytest.mark.asyncio
    async def test_apply_record_fact_skips_null_predicate(self, mock_db, mock_game_session):
        """Test that RECORD_FACT with null predicate is skipped gracefully."""
        manager = BranchCollapseManager(mock_db, mock_game_session)

        delta = StateDelta(
            delta_type=DeltaType.RECORD_FACT,
            target_key="npc_001",
            changes={
                "subject_type": "entity",
                "subject_key": "npc_001",
                "predicate": None,  # Invalid - null predicate
                "value": "some value",
            },
        )

        with patch("src.world_server.quantum.collapse.FactManager") as mock_fm:
            # Should not raise, just skip
            await manager._apply_single_delta(delta, turn_number=5)

            # FactManager should not have been called
            mock_fm.return_value.record_fact.assert_not_called()

    @pytest.mark.asyncio
    async def test_apply_record_fact_skips_null_value(self, mock_db, mock_game_session):
        """Test that RECORD_FACT with null value is skipped gracefully."""
        manager = BranchCollapseManager(mock_db, mock_game_session)

        delta = StateDelta(
            delta_type=DeltaType.RECORD_FACT,
            target_key="npc_001",
            changes={
                "subject_type": "entity",
                "subject_key": "npc_001",
                "predicate": "knows_secret",
                "value": None,  # Invalid - null value
            },
        )

        with patch("src.world_server.quantum.collapse.FactManager") as mock_fm:
            # Should not raise, just skip
            await manager._apply_single_delta(delta, turn_number=5)

            # FactManager should not have been called
            mock_fm.return_value.record_fact.assert_not_called()

    @pytest.mark.asyncio
    async def test_apply_record_fact_skips_missing_fields(self, mock_db, mock_game_session):
        """Test that RECORD_FACT with missing predicate/value is skipped gracefully."""
        manager = BranchCollapseManager(mock_db, mock_game_session)

        delta = StateDelta(
            delta_type=DeltaType.RECORD_FACT,
            target_key="npc_001",
            changes={
                "subject_type": "entity",
                "subject_key": "npc_001",
                # Both predicate and value are missing
            },
        )

        with patch("src.world_server.quantum.collapse.FactManager") as mock_fm:
            # Should not raise, just skip
            await manager._apply_single_delta(delta, turn_number=5)

            # FactManager should not have been called
            mock_fm.return_value.record_fact.assert_not_called()

    @pytest.mark.asyncio
    async def test_apply_advance_time(self, mock_db, mock_game_session):
        """Test applying ADVANCE_TIME delta."""
        manager = BranchCollapseManager(mock_db, mock_game_session)

        delta = StateDelta(
            delta_type=DeltaType.ADVANCE_TIME,
            target_key="time",
            changes={"minutes": 30},
        )

        with patch("src.world_server.quantum.collapse.TimeManager") as mock_tm:
            await manager._apply_single_delta(delta, turn_number=5)

            mock_tm.return_value.advance_time.assert_called_once_with(minutes=30)

    @pytest.mark.asyncio
    async def test_apply_update_location(self, mock_db, mock_game_session):
        """Test applying UPDATE_LOCATION delta."""
        manager = BranchCollapseManager(mock_db, mock_game_session)

        delta = StateDelta(
            delta_type=DeltaType.UPDATE_LOCATION,
            target_key="npc_001",
            changes={"location_key": "castle_entrance"},
        )

        with patch("src.world_server.quantum.collapse.EntityManager") as mock_em:
            await manager._apply_single_delta(delta, turn_number=5)

            mock_em.return_value.update_location.assert_called_once_with(
                entity_key="npc_001",
                location_key="castle_entrance",
            )
