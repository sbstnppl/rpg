"""Data models for the World Server anticipation system.

These schemas define the core data structures used for:
- Pre-generated scenes (uncommitted until observed)
- Location predictions with probabilities
- Anticipation task tracking
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class GenerationStatus(str, Enum):
    """Status of an anticipation generation task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"  # Location changed before generation completed
    CANCELLED = "cancelled"  # Manually cancelled


class PredictionReason(str, Enum):
    """Why a location was predicted as a likely destination."""

    ADJACENT = "adjacent"  # Connected via exits
    QUEST_TARGET = "quest_target"  # Active quest objective
    MENTIONED = "mentioned"  # Referenced in recent dialogue
    HOME = "home"  # Player's home location
    FREQUENT = "frequent"  # Frequently visited
    NPC_LOCATION = "npc_location"  # Location of NPC player mentioned


@dataclass
class LocationPrediction:
    """Predicted next location with probability and reasoning."""

    location_key: str
    probability: float  # 0.0 to 1.0
    reason: PredictionReason
    reason_detail: str | None = None  # e.g., "quest: Find the merchant"

    def __post_init__(self) -> None:
        """Validate probability range."""
        if not 0.0 <= self.probability <= 1.0:
            raise ValueError(f"Probability must be 0.0-1.0, got {self.probability}")


@dataclass
class PreGeneratedScene:
    """Scene generated but not yet observed by player.

    This represents uncommitted state - content that exists in memory
    but hasn't been persisted to the database yet. When the player
    observes this location, it will be "collapsed" (committed to DB).
    """

    location_key: str
    location_display_name: str

    # Scene content
    scene_manifest: dict[str, Any]  # Full SceneManifest as dict
    npcs_present: list[dict[str, Any]]  # NPC data for persistence
    items_present: list[dict[str, Any]]  # Item data for persistence
    furniture: list[dict[str, Any]]  # Furniture data
    atmosphere: dict[str, Any]  # Lighting, sounds, smells

    # Metadata
    generated_at: datetime = field(default_factory=datetime.now)
    generation_time_ms: float = 0.0  # How long generation took
    is_committed: bool = False
    expiry_seconds: int = 300  # 5 minutes default

    # Prediction info
    predicted_probability: float = 0.0
    prediction_reason: PredictionReason | None = None

    def is_stale(self) -> bool:
        """Check if pre-generated content has expired."""
        age = (datetime.now() - self.generated_at).total_seconds()
        return age > self.expiry_seconds

    def age_seconds(self) -> float:
        """Get age of this pre-generated scene in seconds."""
        return (datetime.now() - self.generated_at).total_seconds()

    def remaining_ttl_seconds(self) -> float:
        """Get remaining time-to-live in seconds."""
        return max(0.0, self.expiry_seconds - self.age_seconds())


@dataclass
class AnticipationTask:
    """Task queued for background scene generation."""

    location_key: str
    priority: float  # Higher = generate first (typically the probability)
    prediction_reason: PredictionReason

    # Status tracking
    status: GenerationStatus = GenerationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Result tracking
    error: str | None = None
    result: PreGeneratedScene | None = None

    def mark_started(self) -> None:
        """Mark task as started."""
        self.status = GenerationStatus.IN_PROGRESS
        self.started_at = datetime.now()

    def mark_completed(self, result: PreGeneratedScene) -> None:
        """Mark task as completed with result."""
        self.status = GenerationStatus.COMPLETED
        self.completed_at = datetime.now()
        self.result = result

    def mark_failed(self, error: str) -> None:
        """Mark task as failed with error."""
        self.status = GenerationStatus.FAILED
        self.completed_at = datetime.now()
        self.error = error

    def mark_expired(self) -> None:
        """Mark task as expired (location changed)."""
        self.status = GenerationStatus.EXPIRED
        self.completed_at = datetime.now()

    def duration_ms(self) -> float | None:
        """Get task duration in milliseconds, if completed."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return None


@dataclass
class AnticipationMetrics:
    """Metrics for tracking anticipation performance."""

    # Counters
    predictions_made: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    generations_started: int = 0
    generations_completed: int = 0
    generations_failed: int = 0
    generations_expired: int = 0  # Started but location changed
    generations_wasted: int = 0  # Completed but never used (expired from cache)

    # Timing (cumulative for averaging)
    total_generation_time_ms: float = 0.0
    total_cache_hit_latency_ms: float = 0.0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0

    @property
    def waste_rate(self) -> float:
        """Calculate wasted generation rate."""
        if self.generations_completed == 0:
            return 0.0
        return self.generations_wasted / self.generations_completed

    @property
    def avg_generation_time_ms(self) -> float:
        """Average generation time in milliseconds."""
        if self.generations_completed == 0:
            return 0.0
        return self.total_generation_time_ms / self.generations_completed

    @property
    def avg_cache_hit_latency_ms(self) -> float:
        """Average cache hit latency in milliseconds."""
        if self.cache_hits == 0:
            return 0.0
        return self.total_cache_hit_latency_ms / self.cache_hits

    def record_prediction(self) -> None:
        """Record a prediction was made."""
        self.predictions_made += 1

    def record_cache_hit(self, latency_ms: float) -> None:
        """Record a cache hit."""
        self.cache_hits += 1
        self.total_cache_hit_latency_ms += latency_ms

    def record_cache_miss(self) -> None:
        """Record a cache miss."""
        self.cache_misses += 1

    def record_generation_started(self) -> None:
        """Record generation started."""
        self.generations_started += 1

    def record_generation_completed(self, duration_ms: float) -> None:
        """Record generation completed."""
        self.generations_completed += 1
        self.total_generation_time_ms += duration_ms

    def record_generation_failed(self) -> None:
        """Record generation failed."""
        self.generations_failed += 1

    def record_generation_expired(self) -> None:
        """Record generation expired (location changed mid-generation)."""
        self.generations_expired += 1

    def record_generation_wasted(self) -> None:
        """Record generation wasted (completed but cache expired without use)."""
        self.generations_wasted += 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/display."""
        return {
            "predictions_made": self.predictions_made,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": f"{self.hit_rate:.1%}",
            "generations_started": self.generations_started,
            "generations_completed": self.generations_completed,
            "generations_failed": self.generations_failed,
            "generations_expired": self.generations_expired,
            "generations_wasted": self.generations_wasted,
            "waste_rate": f"{self.waste_rate:.1%}",
            "avg_generation_time_ms": f"{self.avg_generation_time_ms:.0f}",
            "avg_cache_hit_latency_ms": f"{self.avg_cache_hit_latency_ms:.1f}",
        }


@dataclass
class CollapseResult:
    """Result of collapsing (observing) a location."""

    location_key: str
    narrator_manifest: dict[str, Any]
    was_pre_generated: bool
    latency_ms: float

    # If pre-generated, info about the cache hit
    cache_age_seconds: float | None = None
    prediction_reason: PredictionReason | None = None

    # If not pre-generated, info about sync generation
    generation_time_ms: float | None = None
