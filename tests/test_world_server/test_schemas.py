"""Tests for World Server schemas."""

import pytest
from datetime import datetime, timedelta

from src.world_server.schemas import (
    AnticipationMetrics,
    AnticipationTask,
    CollapseResult,
    GenerationStatus,
    LocationPrediction,
    PreGeneratedScene,
    PredictionReason,
)


class TestLocationPrediction:
    """Tests for LocationPrediction dataclass."""

    def test_create_valid_prediction(self):
        """Test creating a valid prediction."""
        pred = LocationPrediction(
            location_key="tavern",
            probability=0.7,
            reason=PredictionReason.ADJACENT,
        )
        assert pred.location_key == "tavern"
        assert pred.probability == 0.7
        assert pred.reason == PredictionReason.ADJACENT

    def test_prediction_with_detail(self):
        """Test prediction with reason detail."""
        pred = LocationPrediction(
            location_key="market",
            probability=0.5,
            reason=PredictionReason.QUEST_TARGET,
            reason_detail="quest: Find the merchant",
        )
        assert pred.reason_detail == "quest: Find the merchant"

    def test_probability_validation_too_high(self):
        """Test that probability > 1.0 raises error."""
        with pytest.raises(ValueError, match="Probability must be"):
            LocationPrediction(
                location_key="test",
                probability=1.5,
                reason=PredictionReason.ADJACENT,
            )

    def test_probability_validation_negative(self):
        """Test that negative probability raises error."""
        with pytest.raises(ValueError, match="Probability must be"):
            LocationPrediction(
                location_key="test",
                probability=-0.1,
                reason=PredictionReason.ADJACENT,
            )

    def test_probability_boundary_values(self):
        """Test boundary probability values (0.0 and 1.0)."""
        pred_zero = LocationPrediction(
            location_key="test",
            probability=0.0,
            reason=PredictionReason.MENTIONED,
        )
        assert pred_zero.probability == 0.0

        pred_one = LocationPrediction(
            location_key="test",
            probability=1.0,
            reason=PredictionReason.ADJACENT,
        )
        assert pred_one.probability == 1.0


class TestPreGeneratedScene:
    """Tests for PreGeneratedScene dataclass."""

    def test_create_scene(self):
        """Test creating a pre-generated scene."""
        scene = PreGeneratedScene(
            location_key="tavern",
            location_display_name="The Rusty Anchor",
            scene_manifest={"test": "data"},
            npcs_present=[{"name": "Bartender"}],
            items_present=[{"name": "Mug"}],
            furniture=[{"type": "bar"}],
            atmosphere={"lighting": "dim"},
        )
        assert scene.location_key == "tavern"
        assert scene.is_committed is False
        assert scene.expiry_seconds == 300

    def test_is_stale_fresh(self):
        """Test is_stale returns False for fresh scene."""
        scene = PreGeneratedScene(
            location_key="test",
            location_display_name="Test",
            scene_manifest={},
            npcs_present=[],
            items_present=[],
            furniture=[],
            atmosphere={},
            generated_at=datetime.now(),
        )
        assert scene.is_stale() is False

    def test_is_stale_expired(self):
        """Test is_stale returns True for expired scene."""
        scene = PreGeneratedScene(
            location_key="test",
            location_display_name="Test",
            scene_manifest={},
            npcs_present=[],
            items_present=[],
            furniture=[],
            atmosphere={},
            generated_at=datetime.now() - timedelta(seconds=400),
            expiry_seconds=300,
        )
        assert scene.is_stale() is True

    def test_age_seconds(self):
        """Test age_seconds calculation."""
        past_time = datetime.now() - timedelta(seconds=60)
        scene = PreGeneratedScene(
            location_key="test",
            location_display_name="Test",
            scene_manifest={},
            npcs_present=[],
            items_present=[],
            furniture=[],
            atmosphere={},
            generated_at=past_time,
        )
        assert 59 <= scene.age_seconds() <= 61

    def test_remaining_ttl(self):
        """Test remaining_ttl_seconds calculation."""
        scene = PreGeneratedScene(
            location_key="test",
            location_display_name="Test",
            scene_manifest={},
            npcs_present=[],
            items_present=[],
            furniture=[],
            atmosphere={},
            generated_at=datetime.now() - timedelta(seconds=100),
            expiry_seconds=300,
        )
        ttl = scene.remaining_ttl_seconds()
        assert 199 <= ttl <= 201

    def test_remaining_ttl_expired(self):
        """Test remaining_ttl returns 0 for expired scene."""
        scene = PreGeneratedScene(
            location_key="test",
            location_display_name="Test",
            scene_manifest={},
            npcs_present=[],
            items_present=[],
            furniture=[],
            atmosphere={},
            generated_at=datetime.now() - timedelta(seconds=400),
            expiry_seconds=300,
        )
        assert scene.remaining_ttl_seconds() == 0.0


class TestAnticipationTask:
    """Tests for AnticipationTask dataclass."""

    def test_create_task(self):
        """Test creating a task."""
        task = AnticipationTask(
            location_key="tavern",
            priority=0.7,
            prediction_reason=PredictionReason.ADJACENT,
        )
        assert task.status == GenerationStatus.PENDING
        assert task.started_at is None
        assert task.completed_at is None

    def test_mark_started(self):
        """Test marking task as started."""
        task = AnticipationTask(
            location_key="test",
            priority=0.5,
            prediction_reason=PredictionReason.MENTIONED,
        )
        task.mark_started()
        assert task.status == GenerationStatus.IN_PROGRESS
        assert task.started_at is not None

    def test_mark_completed(self):
        """Test marking task as completed."""
        task = AnticipationTask(
            location_key="test",
            priority=0.5,
            prediction_reason=PredictionReason.ADJACENT,
        )
        task.mark_started()

        scene = PreGeneratedScene(
            location_key="test",
            location_display_name="Test",
            scene_manifest={},
            npcs_present=[],
            items_present=[],
            furniture=[],
            atmosphere={},
        )
        task.mark_completed(scene)

        assert task.status == GenerationStatus.COMPLETED
        assert task.completed_at is not None
        assert task.result == scene

    def test_mark_failed(self):
        """Test marking task as failed."""
        task = AnticipationTask(
            location_key="test",
            priority=0.5,
            prediction_reason=PredictionReason.QUEST_TARGET,
        )
        task.mark_started()
        task.mark_failed("Connection error")

        assert task.status == GenerationStatus.FAILED
        assert task.error == "Connection error"

    def test_mark_expired(self):
        """Test marking task as expired."""
        task = AnticipationTask(
            location_key="test",
            priority=0.5,
            prediction_reason=PredictionReason.ADJACENT,
        )
        task.mark_expired()
        assert task.status == GenerationStatus.EXPIRED

    def test_duration_ms(self):
        """Test duration calculation."""
        task = AnticipationTask(
            location_key="test",
            priority=0.5,
            prediction_reason=PredictionReason.ADJACENT,
        )

        # No duration before completion
        assert task.duration_ms() is None

        task.mark_started()
        task.completed_at = task.started_at + timedelta(milliseconds=500)

        duration = task.duration_ms()
        assert 499 <= duration <= 501


class TestAnticipationMetrics:
    """Tests for AnticipationMetrics dataclass."""

    def test_initial_state(self):
        """Test initial metrics state."""
        metrics = AnticipationMetrics()
        assert metrics.predictions_made == 0
        assert metrics.cache_hits == 0
        assert metrics.cache_misses == 0
        assert metrics.hit_rate == 0.0
        assert metrics.waste_rate == 0.0

    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        metrics = AnticipationMetrics()
        metrics.cache_hits = 7
        metrics.cache_misses = 3
        assert metrics.hit_rate == 0.7

    def test_waste_rate_calculation(self):
        """Test waste rate calculation."""
        metrics = AnticipationMetrics()
        metrics.generations_completed = 10
        metrics.generations_wasted = 3
        assert metrics.waste_rate == 0.3

    def test_avg_generation_time(self):
        """Test average generation time calculation."""
        metrics = AnticipationMetrics()
        metrics.generations_completed = 5
        metrics.total_generation_time_ms = 50000
        assert metrics.avg_generation_time_ms == 10000

    def test_record_methods(self):
        """Test all record methods."""
        metrics = AnticipationMetrics()

        metrics.record_prediction()
        assert metrics.predictions_made == 1

        metrics.record_cache_hit(10.5)
        assert metrics.cache_hits == 1
        assert metrics.total_cache_hit_latency_ms == 10.5

        metrics.record_cache_miss()
        assert metrics.cache_misses == 1

        metrics.record_generation_started()
        assert metrics.generations_started == 1

        metrics.record_generation_completed(5000)
        assert metrics.generations_completed == 1
        assert metrics.total_generation_time_ms == 5000

        metrics.record_generation_failed()
        assert metrics.generations_failed == 1

        metrics.record_generation_expired()
        assert metrics.generations_expired == 1

        metrics.record_generation_wasted()
        assert metrics.generations_wasted == 1

    def test_to_dict(self):
        """Test conversion to dict."""
        metrics = AnticipationMetrics()
        metrics.cache_hits = 7
        metrics.cache_misses = 3
        metrics.generations_completed = 10
        metrics.total_generation_time_ms = 50000

        result = metrics.to_dict()

        assert result["cache_hits"] == 7
        assert result["cache_misses"] == 3
        assert result["hit_rate"] == "70.0%"
        assert result["avg_generation_time_ms"] == "5000"


class TestCollapseResult:
    """Tests for CollapseResult dataclass."""

    def test_create_cache_hit_result(self):
        """Test creating result for cache hit."""
        result = CollapseResult(
            location_key="tavern",
            narrator_manifest={"npcs": []},
            was_pre_generated=True,
            latency_ms=50.5,
            cache_age_seconds=30.0,
            prediction_reason=PredictionReason.ADJACENT,
        )
        assert result.was_pre_generated is True
        assert result.generation_time_ms is None

    def test_create_cache_miss_result(self):
        """Test creating result for cache miss."""
        result = CollapseResult(
            location_key="ruins",
            narrator_manifest={"npcs": []},
            was_pre_generated=False,
            latency_ms=65000,
            generation_time_ms=64500,
        )
        assert result.was_pre_generated is False
        assert result.cache_age_seconds is None
