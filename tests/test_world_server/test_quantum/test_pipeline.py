"""Tests for QuantumPipeline."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.dice.types import AdvantageType
from src.gm.grounding import GroundedEntity, GroundingManifest
from src.world_server.schemas import PredictionReason
from src.world_server.quantum.schemas import (
    ActionPrediction,
    ActionType,
    GMDecision,
    OutcomeVariant,
    QuantumBranch,
    QuantumMetrics,
    VariantType,
)
from src.world_server.quantum.collapse import CollapseResult
from src.world_server.quantum.pipeline import (
    AnticipationConfig,
    QuantumPipeline,
    TurnResult,
)


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.all.return_value = []
    db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
    return db


@pytest.fixture
def mock_game_session():
    """Create a mock game session."""
    session = MagicMock()
    session.id = 1
    return session


@pytest.fixture
def mock_llm_provider():
    """Create a mock LLM provider."""
    provider = MagicMock()
    provider.complete_structured = AsyncMock()
    return provider


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
            "merchant_001": GroundedEntity(
                key="merchant_001",
                display_name="Merchant",
                entity_type="npc",
                short_description="a friendly merchant",
            ),
        },
        items_at_location={
            "coin_001": GroundedEntity(
                key="coin_001",
                display_name="Gold Coin",
                entity_type="item",
            ),
        },
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
        action_type=ActionType.INTERACT_NPC,
        target_key="guard_001",
        input_patterns=["talk.*guard", "speak.*guard"],
        probability=0.25,
        reason=PredictionReason.ADJACENT,
        display_name="Talk to guard",
    )


@pytest.fixture
def sample_branch(sample_action):
    """Create a sample quantum branch."""
    return QuantumBranch(
        branch_key="village_square::interact_npc::guard_001::no_twist",
        action=sample_action,
        gm_decision=GMDecision(
            decision_type="no_twist",
            probability=0.7,
        ),
        variants={
            "success": OutcomeVariant(
                variant_type=VariantType.SUCCESS,
                requires_dice=False,
                narrative="You approach [guard_001:the guard] and strike up a conversation.",
                time_passed_minutes=5,
            ),
        },
        generated_at=datetime.now(),
        generation_time_ms=100.0,
    )


class TestTurnResult:
    """Tests for TurnResult dataclass."""

    def test_turn_result_defaults(self):
        """Test TurnResult default values."""
        result = TurnResult(narrative="Hello")

        assert result.narrative == "Hello"
        assert result.raw_narrative == ""
        assert result.was_cache_hit is False
        assert result.matched_action is None
        assert result.error is None
        assert result.used_fallback is False

    def test_turn_result_with_all_fields(self, sample_action):
        """Test TurnResult with all fields populated."""
        result = TurnResult(
            narrative="You talk to the guard.",
            raw_narrative="You talk to [guard_001:the guard].",
            was_cache_hit=True,
            matched_action=sample_action,
            match_confidence=0.95,
            total_time_ms=50.0,
        )

        assert result.was_cache_hit is True
        assert result.matched_action == sample_action
        assert result.match_confidence == 0.95


class TestAnticipationConfig:
    """Tests for AnticipationConfig dataclass."""

    def test_default_config(self):
        """Test default configuration."""
        config = AnticipationConfig()

        assert config.enabled is True
        assert config.max_actions_per_cycle == 5
        assert config.max_gm_decisions_per_action == 2
        assert config.cycle_delay_seconds == 0.5

    def test_custom_config(self):
        """Test custom configuration."""
        config = AnticipationConfig(
            enabled=False,
            max_actions_per_cycle=10,
            cycle_delay_seconds=1.0,
        )

        assert config.enabled is False
        assert config.max_actions_per_cycle == 10


class TestPipelineInit:
    """Tests for QuantumPipeline initialization."""

    def test_initialization(self, mock_db, mock_game_session, mock_llm_provider):
        """Test basic initialization."""
        with patch("src.world_server.quantum.pipeline.GMContextBuilder"):
            pipeline = QuantumPipeline(
                db=mock_db,
                game_session=mock_game_session,
                llm_provider=mock_llm_provider,
            )

            assert pipeline.db == mock_db
            assert pipeline.game_session == mock_game_session
            assert pipeline.metrics is not None
            assert pipeline._running is False

    def test_initialization_with_custom_metrics(
        self, mock_db, mock_game_session, mock_llm_provider
    ):
        """Test initialization with custom metrics."""
        metrics = QuantumMetrics()

        with patch("src.world_server.quantum.pipeline.GMContextBuilder"):
            pipeline = QuantumPipeline(
                db=mock_db,
                game_session=mock_game_session,
                llm_provider=mock_llm_provider,
                metrics=metrics,
            )

            assert pipeline.metrics is metrics


class TestProcessTurn:
    """Tests for process_turn method."""

    @pytest.mark.asyncio
    async def test_cache_hit_returns_quickly(
        self, mock_db, mock_game_session, mock_llm_provider, sample_manifest, sample_branch
    ):
        """Test that cache hit returns quickly."""
        with patch("src.world_server.quantum.pipeline.GMContextBuilder") as MockBuilder:
            mock_builder = MagicMock()
            mock_builder.build_grounding_manifest.return_value = sample_manifest
            MockBuilder.return_value = mock_builder

            pipeline = QuantumPipeline(
                db=mock_db,
                game_session=mock_game_session,
                llm_provider=mock_llm_provider,
            )

            # Mock the cache to return a hit
            pipeline.branch_cache.get_branch = AsyncMock(return_value=sample_branch)

            # Mock collapse
            collapse_result = CollapseResult(
                narrative="You talk to the guard.",
                raw_narrative="You talk to [guard_001:the guard].",
                state_deltas=[],
                time_passed_minutes=5,
            )
            pipeline.collapse_manager.collapse_branch = AsyncMock(
                return_value=collapse_result
            )

            result = await pipeline.process_turn(
                player_input="talk to the guard",
                location_key="village_square",
                turn_number=1,
            )

            assert result.was_cache_hit is True
            assert "guard" in result.narrative.lower()

    @pytest.mark.asyncio
    async def test_cache_miss_generates_sync(
        self, mock_db, mock_game_session, mock_llm_provider, sample_manifest
    ):
        """Test that cache miss triggers sync generation."""
        with patch("src.world_server.quantum.pipeline.GMContextBuilder") as MockBuilder:
            mock_builder = MagicMock()
            mock_builder.build_grounding_manifest.return_value = sample_manifest
            MockBuilder.return_value = mock_builder

            pipeline = QuantumPipeline(
                db=mock_db,
                game_session=mock_game_session,
                llm_provider=mock_llm_provider,
            )

            # Mock cache miss
            pipeline.branch_cache.get_branch = AsyncMock(return_value=None)

            # Mock action prediction to return something
            mock_predictions = [
                ActionPrediction(
                    action_type=ActionType.INTERACT_NPC,
                    target_key="guard_001",
                    input_patterns=["talk.*guard"],
                    probability=0.3,
                    reason=PredictionReason.ADJACENT,
                ),
            ]
            pipeline.action_predictor.predict_actions = MagicMock(
                return_value=mock_predictions
            )

            # Mock branch generation
            mock_branch = QuantumBranch(
                branch_key="test::interact_npc::guard_001::no_twist",
                action=mock_predictions[0],
                gm_decision=GMDecision("no_twist", 0.7),
                variants={
                    "success": OutcomeVariant(
                        variant_type=VariantType.SUCCESS,
                        requires_dice=False,
                        narrative="You talk to the guard.",
                    ),
                },
                generated_at=datetime.now(),
            )
            pipeline.branch_generator.generate_branch = AsyncMock(
                return_value=mock_branch
            )
            pipeline.branch_cache.put_branch = AsyncMock()

            # Mock collapse
            collapse_result = CollapseResult(
                narrative="You talk to the guard.",
                raw_narrative="You talk to the guard.",
                state_deltas=[],
                time_passed_minutes=5,
            )
            pipeline.collapse_manager.collapse_branch = AsyncMock(
                return_value=collapse_result
            )

            result = await pipeline.process_turn(
                player_input="talk to the guard",
                location_key="village_square",
                turn_number=1,
            )

            assert result.was_cache_hit is False
            assert result.generation_time_ms > 0

    @pytest.mark.asyncio
    async def test_error_handling(
        self, mock_db, mock_game_session, mock_llm_provider, sample_manifest
    ):
        """Test error handling returns fallback."""
        with patch("src.world_server.quantum.pipeline.GMContextBuilder") as MockBuilder:
            mock_builder = MagicMock()
            mock_builder.build_grounding_manifest.side_effect = Exception("Test error")
            MockBuilder.return_value = mock_builder

            pipeline = QuantumPipeline(
                db=mock_db,
                game_session=mock_game_session,
                llm_provider=mock_llm_provider,
            )

            result = await pipeline.process_turn(
                player_input="do something",
                location_key="test_location",
                turn_number=1,
            )

            assert result.error is not None
            assert result.used_fallback is True


class TestGMDecisionSelection:
    """Tests for GM decision selection."""

    def test_select_single_decision(self, mock_db, mock_game_session, mock_llm_provider):
        """Test selecting from single decision."""
        with patch("src.world_server.quantum.pipeline.GMContextBuilder"):
            pipeline = QuantumPipeline(
                db=mock_db,
                game_session=mock_game_session,
                llm_provider=mock_llm_provider,
            )

            decisions = [GMDecision("no_twist", 1.0)]
            selected = pipeline._select_gm_decision(decisions)

            assert selected.decision_type == "no_twist"

    def test_select_from_empty_returns_default(
        self, mock_db, mock_game_session, mock_llm_provider
    ):
        """Test selecting from empty list returns default."""
        with patch("src.world_server.quantum.pipeline.GMContextBuilder"):
            pipeline = QuantumPipeline(
                db=mock_db,
                game_session=mock_game_session,
                llm_provider=mock_llm_provider,
            )

            selected = pipeline._select_gm_decision([])

            assert selected.decision_type == "no_twist"
            assert selected.probability == 1.0

    def test_select_weighted_random(self, mock_db, mock_game_session, mock_llm_provider):
        """Test weighted random selection."""
        with patch("src.world_server.quantum.pipeline.GMContextBuilder"):
            pipeline = QuantumPipeline(
                db=mock_db,
                game_session=mock_game_session,
                llm_provider=mock_llm_provider,
            )

            decisions = [
                GMDecision("no_twist", 0.7),
                GMDecision("theft_accusation", 0.3),
            ]

            # Run many times and check distribution
            results = {"no_twist": 0, "theft_accusation": 0}
            for _ in range(1000):
                selected = pipeline._select_gm_decision(decisions)
                results[selected.decision_type] += 1

            # Should roughly follow probabilities (with some variance)
            assert results["no_twist"] > results["theft_accusation"]


class TestCacheManagement:
    """Tests for cache management methods."""

    @pytest.mark.asyncio
    async def test_invalidate_location(
        self, mock_db, mock_game_session, mock_llm_provider
    ):
        """Test invalidating a location."""
        with patch("src.world_server.quantum.pipeline.GMContextBuilder"):
            pipeline = QuantumPipeline(
                db=mock_db,
                game_session=mock_game_session,
                llm_provider=mock_llm_provider,
            )

            # Add some branches
            pipeline.branch_cache.put_branch = AsyncMock()
            pipeline.branch_cache.invalidate_location = AsyncMock(return_value=3)

            removed = await pipeline.invalidate_location("tavern")

            assert removed == 3
            pipeline.branch_cache.invalidate_location.assert_called_once_with("tavern")

    @pytest.mark.asyncio
    async def test_clear_cache(self, mock_db, mock_game_session, mock_llm_provider):
        """Test clearing the cache."""
        with patch("src.world_server.quantum.pipeline.GMContextBuilder"):
            pipeline = QuantumPipeline(
                db=mock_db,
                game_session=mock_game_session,
                llm_provider=mock_llm_provider,
            )

            pipeline.branch_cache.clear = AsyncMock(return_value=10)

            removed = await pipeline.clear_cache()

            assert removed == 10

    def test_get_stats(self, mock_db, mock_game_session, mock_llm_provider):
        """Test getting pipeline stats."""
        with patch("src.world_server.quantum.pipeline.GMContextBuilder"):
            pipeline = QuantumPipeline(
                db=mock_db,
                game_session=mock_game_session,
                llm_provider=mock_llm_provider,
            )

            stats = pipeline.get_stats()

            assert "cache" in stats
            assert "metrics" in stats
            assert "anticipation" in stats
            assert stats["anticipation"]["running"] is False


class TestBackgroundAnticipation:
    """Tests for background anticipation."""

    @pytest.mark.asyncio
    async def test_start_anticipation(
        self, mock_db, mock_game_session, mock_llm_provider
    ):
        """Test starting anticipation."""
        with patch("src.world_server.quantum.pipeline.GMContextBuilder"):
            pipeline = QuantumPipeline(
                db=mock_db,
                game_session=mock_game_session,
                llm_provider=mock_llm_provider,
            )

            await pipeline.start_anticipation()

            assert pipeline._running is True
            assert pipeline._anticipation_task is not None

            await pipeline.stop_anticipation()

            assert pipeline._running is False

    @pytest.mark.asyncio
    async def test_stop_anticipation(
        self, mock_db, mock_game_session, mock_llm_provider
    ):
        """Test stopping anticipation."""
        with patch("src.world_server.quantum.pipeline.GMContextBuilder"):
            pipeline = QuantumPipeline(
                db=mock_db,
                game_session=mock_game_session,
                llm_provider=mock_llm_provider,
            )

            await pipeline.start_anticipation()
            await pipeline.stop_anticipation()

            assert pipeline._running is False
            assert pipeline._anticipation_task is None

    @pytest.mark.asyncio
    async def test_disabled_anticipation(
        self, mock_db, mock_game_session, mock_llm_provider
    ):
        """Test anticipation when disabled."""
        config = AnticipationConfig(enabled=False)

        with patch("src.world_server.quantum.pipeline.GMContextBuilder"):
            pipeline = QuantumPipeline(
                db=mock_db,
                game_session=mock_game_session,
                llm_provider=mock_llm_provider,
                anticipation_config=config,
            )

            await pipeline.start_anticipation()

            # Should not start when disabled
            assert pipeline._anticipation_task is None

    @pytest.mark.asyncio
    async def test_trigger_anticipation(
        self, mock_db, mock_game_session, mock_llm_provider
    ):
        """Test triggering anticipation for new location."""
        with patch("src.world_server.quantum.pipeline.GMContextBuilder"):
            pipeline = QuantumPipeline(
                db=mock_db,
                game_session=mock_game_session,
                llm_provider=mock_llm_provider,
            )

            pipeline._trigger_anticipation("new_location")

            assert pipeline._current_location == "new_location"


class TestModifierPassing:
    """Tests for passing modifiers to skill checks."""

    @pytest.mark.asyncio
    async def test_modifiers_passed_to_collapse(
        self, mock_db, mock_game_session, mock_llm_provider, sample_manifest, sample_branch
    ):
        """Test that modifiers are passed to collapse manager."""
        with patch("src.world_server.quantum.pipeline.GMContextBuilder") as MockBuilder:
            mock_builder = MagicMock()
            mock_builder.build_grounding_manifest.return_value = sample_manifest
            MockBuilder.return_value = mock_builder

            pipeline = QuantumPipeline(
                db=mock_db,
                game_session=mock_game_session,
                llm_provider=mock_llm_provider,
            )

            # Mock cache hit
            pipeline.branch_cache.get_branch = AsyncMock(return_value=sample_branch)

            # Track collapse call
            collapse_result = CollapseResult(
                narrative="Success!",
                raw_narrative="Success!",
                state_deltas=[],
                time_passed_minutes=5,
            )
            pipeline.collapse_manager.collapse_branch = AsyncMock(
                return_value=collapse_result
            )

            await pipeline.process_turn(
                player_input="talk to guard",
                location_key="village_square",
                turn_number=1,
                attribute_modifier=3,
                skill_modifier=5,
                advantage_type=AdvantageType.ADVANTAGE,
            )

            # Verify modifiers were passed
            call_kwargs = pipeline.collapse_manager.collapse_branch.call_args.kwargs
            assert call_kwargs["attribute_modifier"] == 3
            assert call_kwargs["skill_modifier"] == 5
            assert call_kwargs["advantage_type"] == AdvantageType.ADVANTAGE


class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.asyncio
    async def test_no_predictions(
        self, mock_db, mock_game_session, mock_llm_provider, sample_manifest
    ):
        """Test handling when no predictions are made."""
        with patch("src.world_server.quantum.pipeline.GMContextBuilder") as MockBuilder:
            mock_builder = MagicMock()
            mock_builder.build_grounding_manifest.return_value = sample_manifest
            MockBuilder.return_value = mock_builder

            pipeline = QuantumPipeline(
                db=mock_db,
                game_session=mock_game_session,
                llm_provider=mock_llm_provider,
            )

            # No cache, no predictions
            pipeline.branch_cache.get_branch = AsyncMock(return_value=None)
            pipeline.action_predictor.predict_actions = MagicMock(return_value=[])

            # Mock generation to fail
            pipeline.branch_generator.generate_branch = AsyncMock(
                side_effect=Exception("No predictions")
            )

            result = await pipeline.process_turn(
                player_input="do something random",
                location_key="village_square",
                turn_number=1,
            )

            # Should return fallback
            assert result.used_fallback is True

    @pytest.mark.asyncio
    async def test_empty_player_input(
        self, mock_db, mock_game_session, mock_llm_provider, sample_manifest
    ):
        """Test handling empty player input."""
        with patch("src.world_server.quantum.pipeline.GMContextBuilder") as MockBuilder:
            mock_builder = MagicMock()
            mock_builder.build_grounding_manifest.return_value = sample_manifest
            MockBuilder.return_value = mock_builder

            pipeline = QuantumPipeline(
                db=mock_db,
                game_session=mock_game_session,
                llm_provider=mock_llm_provider,
            )

            pipeline.branch_cache.get_branch = AsyncMock(return_value=None)
            pipeline.action_predictor.predict_actions = MagicMock(return_value=[])
            pipeline.branch_generator.generate_branch = AsyncMock(
                side_effect=Exception("Empty input")
            )

            result = await pipeline.process_turn(
                player_input="",
                location_key="village_square",
                turn_number=1,
            )

            # Should handle gracefully
            assert result is not None
