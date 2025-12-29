"""Tests for Quantum Branching schemas."""

import pytest
from datetime import datetime, timedelta

from src.world_server.schemas import PredictionReason
from src.world_server.quantum.schemas import (
    ActionType,
    VariantType,
    DeltaType,
    StateDelta,
    ActionPrediction,
    OutcomeVariant,
    GMDecision,
    QuantumBranch,
    QuantumMetrics,
)


class TestActionPrediction:
    """Tests for ActionPrediction dataclass."""

    def test_create_valid_prediction(self):
        """Test creating a valid action prediction."""
        pred = ActionPrediction(
            action_type=ActionType.INTERACT_NPC,
            target_key="innkeeper_tom",
            input_patterns=[r"talk.*tom", r"speak.*innkeeper"],
            probability=0.3,
            reason=PredictionReason.ADJACENT,
        )
        assert pred.action_type == ActionType.INTERACT_NPC
        assert pred.target_key == "innkeeper_tom"
        assert len(pred.input_patterns) == 2
        assert pred.probability == 0.3

    def test_prediction_without_target(self):
        """Test prediction for actions without a target (observe, wait)."""
        pred = ActionPrediction(
            action_type=ActionType.OBSERVE,
            target_key=None,
            input_patterns=["look", "examine"],
            probability=0.2,
            reason=PredictionReason.ADJACENT,
        )
        assert pred.target_key is None
        assert pred.action_type == ActionType.OBSERVE

    def test_probability_validation_too_high(self):
        """Test that probability > 1.0 raises error."""
        with pytest.raises(ValueError, match="Probability must be"):
            ActionPrediction(
                action_type=ActionType.MOVE,
                target_key="market",
                input_patterns=["go market"],
                probability=1.5,
                reason=PredictionReason.QUEST_TARGET,
            )

    def test_probability_validation_negative(self):
        """Test that negative probability raises error."""
        with pytest.raises(ValueError, match="Probability must be"):
            ActionPrediction(
                action_type=ActionType.MANIPULATE_ITEM,
                target_key="sword",
                input_patterns=["take sword"],
                probability=-0.1,
                reason=PredictionReason.MENTIONED,
            )

    def test_prediction_with_context(self):
        """Test prediction with additional context."""
        pred = ActionPrediction(
            action_type=ActionType.DIALOGUE,
            target_key="guard_001",
            input_patterns=["ask.*about"],
            probability=0.4,
            reason=PredictionReason.NPC_LOCATION,
            context={"dialogue_topic": "quest"},
            display_name="Talk to Guard",
        )
        assert pred.context == {"dialogue_topic": "quest"}
        assert pred.display_name == "Talk to Guard"


class TestStateDelta:
    """Tests for StateDelta dataclass."""

    def test_create_delta(self):
        """Test creating a state delta."""
        delta = StateDelta(
            delta_type=DeltaType.CREATE_ENTITY,
            target_key="sword_001",
            changes={"name": "Iron Sword", "item_type": "weapon"},
        )
        assert delta.delta_type == DeltaType.CREATE_ENTITY
        assert delta.target_key == "sword_001"
        assert delta.changes["name"] == "Iron Sword"

    def test_delta_validate_no_expected_state(self):
        """Test validation passes when no expected state."""
        delta = StateDelta(
            delta_type=DeltaType.UPDATE_ENTITY,
            target_key="player",
            changes={"health": 80},
        )
        assert delta.validate({"health": 100}) is True

    def test_delta_validate_matching_state(self):
        """Test validation passes when state matches."""
        delta = StateDelta(
            delta_type=DeltaType.TRANSFER_ITEM,
            target_key="gold_pouch",
            changes={"holder_id": "player"},
            expected_state={"holder_id": "merchant"},
        )
        assert delta.validate({"holder_id": "merchant"}) is True

    def test_delta_validate_mismatched_state(self):
        """Test validation fails when state doesn't match."""
        delta = StateDelta(
            delta_type=DeltaType.TRANSFER_ITEM,
            target_key="gold_pouch",
            changes={"holder_id": "player"},
            expected_state={"holder_id": "merchant"},
        )
        assert delta.validate({"holder_id": "thief"}) is False


class TestOutcomeVariant:
    """Tests for OutcomeVariant dataclass."""

    def test_create_success_variant(self):
        """Test creating a success variant."""
        variant = OutcomeVariant(
            variant_type=VariantType.SUCCESS,
            requires_dice=False,
            narrative="You successfully pick up the [sword_001:iron sword].",
            state_deltas=[
                StateDelta(
                    delta_type=DeltaType.TRANSFER_ITEM,
                    target_key="sword_001",
                    changes={"holder_id": "player"},
                )
            ],
            time_passed_minutes=1,
        )
        assert variant.variant_type == VariantType.SUCCESS
        assert variant.requires_dice is False
        assert len(variant.state_deltas) == 1

    def test_create_skill_check_variant(self):
        """Test creating a variant that requires dice."""
        variant = OutcomeVariant(
            variant_type=VariantType.SUCCESS,
            requires_dice=True,
            skill="lockpicking",
            dc=15,
            modifier_reason="darkness: -2",
            narrative="The lock clicks open.",
        )
        assert variant.requires_dice is True
        assert variant.skill == "lockpicking"
        assert variant.dc == 15

    def test_create_critical_failure_variant(self):
        """Test creating a critical failure variant."""
        variant = OutcomeVariant(
            variant_type=VariantType.CRITICAL_FAILURE,
            requires_dice=True,
            skill="stealth",
            dc=12,
            narrative="You trip and crash into a display of pottery!",
            state_deltas=[],
            time_passed_minutes=2,
        )
        assert variant.variant_type == VariantType.CRITICAL_FAILURE


class TestGMDecision:
    """Tests for GMDecision dataclass."""

    def test_create_no_twist(self):
        """Test creating a no-twist decision."""
        decision = GMDecision(
            decision_type="no_twist",
            probability=0.7,
        )
        assert decision.decision_type == "no_twist"
        assert decision.probability == 0.7
        assert decision.grounding_facts == []

    def test_create_grounded_twist(self):
        """Test creating a twist with grounding facts."""
        decision = GMDecision(
            decision_type="theft_accusation",
            probability=0.15,
            grounding_facts=["recent_theft", "player_is_stranger"],
            context={"accuser": "guard_001"},
        )
        assert decision.decision_type == "theft_accusation"
        assert len(decision.grounding_facts) == 2
        assert "recent_theft" in decision.grounding_facts

    def test_probability_validation(self):
        """Test probability validation."""
        with pytest.raises(ValueError, match="Probability must be"):
            GMDecision(
                decision_type="test",
                probability=1.5,
            )


class TestQuantumBranch:
    """Tests for QuantumBranch dataclass."""

    def test_create_branch(self):
        """Test creating a quantum branch."""
        action = ActionPrediction(
            action_type=ActionType.INTERACT_NPC,
            target_key="merchant",
            input_patterns=["talk merchant"],
            probability=0.3,
            reason=PredictionReason.ADJACENT,
        )
        decision = GMDecision(
            decision_type="no_twist",
            probability=0.7,
        )
        variants = {
            "success": OutcomeVariant(
                variant_type=VariantType.SUCCESS,
                requires_dice=False,
                narrative="The merchant smiles warmly.",
            ),
        }

        branch = QuantumBranch(
            branch_key="tavern::interact_npc::merchant::no_twist",
            action=action,
            gm_decision=decision,
            variants=variants,
            generation_time_ms=1500.0,
        )

        assert branch.branch_key == "tavern::interact_npc::merchant::no_twist"
        assert branch.action == action
        assert branch.gm_decision == decision
        assert len(branch.variants) == 1
        assert branch.is_collapsed is False

    def test_is_stale_fresh(self):
        """Test is_stale returns False for fresh branch."""
        branch = QuantumBranch(
            branch_key="test::observe::none::no_twist",
            action=ActionPrediction(
                action_type=ActionType.OBSERVE,
                target_key=None,
                input_patterns=["look"],
                probability=0.2,
                reason=PredictionReason.ADJACENT,
            ),
            gm_decision=GMDecision(decision_type="no_twist", probability=0.7),
            variants={},
            generated_at=datetime.now(),
        )
        assert branch.is_stale() is False

    def test_is_stale_expired(self):
        """Test is_stale returns True for expired branch."""
        branch = QuantumBranch(
            branch_key="test::observe::none::no_twist",
            action=ActionPrediction(
                action_type=ActionType.OBSERVE,
                target_key=None,
                input_patterns=["look"],
                probability=0.2,
                reason=PredictionReason.ADJACENT,
            ),
            gm_decision=GMDecision(decision_type="no_twist", probability=0.7),
            variants={},
            generated_at=datetime.now() - timedelta(seconds=200),
            expiry_seconds=180,
        )
        assert branch.is_stale() is True

    def test_create_key(self):
        """Test branch key creation."""
        key = QuantumBranch.create_key(
            location_key="tavern",
            action_type=ActionType.INTERACT_NPC,
            target_key="bartender",
            gm_decision_type="no_twist",
        )
        assert key == "tavern::interact_npc::bartender::no_twist"

    def test_create_key_no_target(self):
        """Test branch key creation with no target."""
        key = QuantumBranch.create_key(
            location_key="forest",
            action_type=ActionType.OBSERVE,
            target_key=None,
            gm_decision_type="monster_encounter",
        )
        assert key == "forest::observe::none::monster_encounter"

    def test_get_variant(self):
        """Test getting a variant by type."""
        success_variant = OutcomeVariant(
            variant_type=VariantType.SUCCESS,
            requires_dice=False,
            narrative="Success!",
        )
        failure_variant = OutcomeVariant(
            variant_type=VariantType.FAILURE,
            requires_dice=False,
            narrative="Failure!",
        )

        branch = QuantumBranch(
            branch_key="test",
            action=ActionPrediction(
                action_type=ActionType.SKILL_USE,
                target_key="lock",
                input_patterns=["pick lock"],
                probability=0.3,
                reason=PredictionReason.MENTIONED,
            ),
            gm_decision=GMDecision(decision_type="no_twist", probability=0.7),
            variants={
                "success": success_variant,
                "failure": failure_variant,
            },
        )

        assert branch.get_variant(VariantType.SUCCESS) == success_variant
        assert branch.get_variant(VariantType.FAILURE) == failure_variant
        assert branch.get_variant(VariantType.CRITICAL_SUCCESS) is None


class TestQuantumMetrics:
    """Tests for QuantumMetrics dataclass."""

    def test_initial_state(self):
        """Test initial metrics state."""
        metrics = QuantumMetrics()
        assert metrics.predictions_made == 0
        assert metrics.cache_hits == 0
        assert metrics.cache_misses == 0
        assert metrics.branches_generated == 0
        assert metrics.hit_rate == 0.0

    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        metrics = QuantumMetrics()
        metrics.cache_hits = 6
        metrics.cache_misses = 4
        assert metrics.hit_rate == 0.6

    def test_success_rate_calculation(self):
        """Test player success rate calculation."""
        metrics = QuantumMetrics()
        metrics.successes = 5
        metrics.failures = 3
        metrics.critical_successes = 2
        metrics.critical_failures = 0
        # 7 successes out of 10 total
        assert metrics.success_rate == 0.7

    def test_avg_generation_time(self):
        """Test average generation time calculation."""
        metrics = QuantumMetrics()
        metrics.branches_generated = 5
        metrics.total_generation_time_ms = 10000
        assert metrics.avg_generation_time_ms == 2000

    def test_record_cache_hit(self):
        """Test recording cache hit."""
        metrics = QuantumMetrics()
        metrics.record_cache_hit(50.5)
        assert metrics.cache_hits == 1
        assert metrics.total_cache_hit_latency_ms == 50.5

    def test_record_branch_generated(self):
        """Test recording branch generation."""
        metrics = QuantumMetrics()
        metrics.record_branch_generated(1500.0)
        assert metrics.branches_generated == 1
        assert metrics.total_generation_time_ms == 1500.0

    def test_record_branch_collapsed(self):
        """Test recording branch collapse."""
        metrics = QuantumMetrics()

        # Success with twist
        metrics.record_branch_collapsed(
            variant_type=VariantType.SUCCESS,
            had_twist=True,
            collapse_time_ms=10.0,
        )
        assert metrics.branches_collapsed == 1
        assert metrics.successes == 1
        assert metrics.twists_applied == 1

        # Critical failure without twist
        metrics.record_branch_collapsed(
            variant_type=VariantType.CRITICAL_FAILURE,
            had_twist=False,
            collapse_time_ms=8.0,
        )
        assert metrics.branches_collapsed == 2
        assert metrics.critical_failures == 1
        assert metrics.no_twists == 1

    def test_to_dict(self):
        """Test conversion to dict."""
        metrics = QuantumMetrics()
        metrics.cache_hits = 6
        metrics.cache_misses = 4
        metrics.branches_generated = 10
        metrics.total_generation_time_ms = 20000

        result = metrics.to_dict()

        assert result["cache_hits"] == 6
        assert result["cache_misses"] == 4
        assert result["hit_rate"] == "60.0%"
        assert result["avg_generation_time_ms"] == "2000"
