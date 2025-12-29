"""Data models for the Quantum Branching system.

These schemas define the core data structures used for:
- Action predictions (what the player might do)
- Outcome variants (success/failure branches)
- GM decisions (twists grounded in world state)
- Quantum branches (uncommitted narrative states)
- State deltas (changes to apply on collapse)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from src.world_server.schemas import PredictionReason


class ActionType(str, Enum):
    """Type of player action predicted or matched."""

    INTERACT_NPC = "interact_npc"  # Talk to, attack, trade with NPC
    MANIPULATE_ITEM = "manipulate_item"  # Take, drop, use, examine item
    MOVE = "move"  # Travel to another location
    OBSERVE = "observe"  # Look around, examine environment
    DIALOGUE = "dialogue"  # Specific dialogue choice
    SKILL_USE = "skill_use"  # Use a specific skill (lockpick, climb, etc.)
    COMBAT = "combat"  # Attack, defend, flee
    WAIT = "wait"  # Wait or rest
    CUSTOM = "custom"  # Unmatched but parseable action


class VariantType(str, Enum):
    """Type of outcome variant."""

    SUCCESS = "success"
    FAILURE = "failure"
    CRITICAL_SUCCESS = "critical_success"
    CRITICAL_FAILURE = "critical_failure"
    PARTIAL_SUCCESS = "partial_success"  # Success with complication


class DeltaType(str, Enum):
    """Type of state change to apply on branch collapse."""

    CREATE_ENTITY = "create_entity"
    DELETE_ENTITY = "delete_entity"
    UPDATE_ENTITY = "update_entity"
    TRANSFER_ITEM = "transfer_item"
    UPDATE_NEED = "update_need"
    UPDATE_RELATIONSHIP = "update_relationship"
    RECORD_FACT = "record_fact"
    UPDATE_LOCATION = "update_location"
    ADVANCE_TIME = "advance_time"


@dataclass
class StateDelta:
    """A single state change to apply when a branch is collapsed.

    State deltas are uncommitted until the player observes the outcome.
    They form an atomic transaction - all deltas for a branch are applied
    together or none are.
    """

    delta_type: DeltaType
    target_key: str  # Entity key or location key
    changes: dict[str, Any]  # Type-specific change data

    # Validation data (to detect stale branches)
    expected_state: dict[str, Any] | None = None

    def validate(self, current_state: dict[str, Any]) -> bool:
        """Check if the delta is still valid against current state."""
        if self.expected_state is None:
            return True

        for key, expected_value in self.expected_state.items():
            if current_state.get(key) != expected_value:
                return False
        return True


@dataclass
class ActionPrediction:
    """Predicted player action with input patterns for matching."""

    action_type: ActionType
    target_key: str | None  # Entity or location key, None for observe/wait
    input_patterns: list[str]  # Regex patterns to match player input
    probability: float  # 0.0 to 1.0
    reason: PredictionReason

    # Context for generation
    context: dict[str, Any] = field(default_factory=dict)

    # For display/debugging
    display_name: str | None = None

    def __post_init__(self) -> None:
        """Validate probability range."""
        if not 0.0 <= self.probability <= 1.0:
            raise ValueError(f"Probability must be 0.0-1.0, got {self.probability}")


@dataclass
class OutcomeVariant:
    """A single outcome variant with full narrative and state changes.

    Each variant represents one possible outcome of an action, complete
    with pre-generated narrative prose and state deltas to apply.
    """

    variant_type: VariantType

    # Dice roll requirements
    requires_dice: bool
    skill: str | None = None
    dc: int | None = None  # Difficulty class if requires_dice
    modifier_reason: str | None = None  # e.g., "darkness: -2"

    # Pre-generated content
    narrative: str = ""  # Full prose with [entity_key:display_name] format
    state_deltas: list[StateDelta] = field(default_factory=list)
    time_passed_minutes: int = 1

    # Metadata
    generated_at: datetime = field(default_factory=datetime.now)


@dataclass
class GMDecision:
    """A GM decision about whether to add a twist.

    Twists must be grounded in world state - the grounding_facts list
    documents WHY this twist is possible (e.g., recent theft + stranger
    status justifies a mistaken identity accusation).
    """

    decision_type: str  # "no_twist", "theft_accusation", "monster_warning", etc.
    probability: float  # 0.0 to 1.0, likelihood GM chooses this
    grounding_facts: list[str] = field(default_factory=list)

    # Context for narrative generation
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate probability range."""
        if not 0.0 <= self.probability <= 1.0:
            raise ValueError(f"Probability must be 0.0-1.0, got {self.probability}")


@dataclass
class QuantumBranch:
    """A pre-generated branch representing one action + GM decision combo.

    The branch contains multiple variants (success, failure, etc.) that
    will be selected at runtime based on dice rolls. This is the core
    of the quantum branching system - uncommitted state that collapses
    when the player observes it.
    """

    branch_key: str  # "location::action_type::target::gm_decision"
    action: ActionPrediction
    gm_decision: GMDecision
    variants: dict[str, OutcomeVariant]  # variant_type -> OutcomeVariant

    # Metadata
    generated_at: datetime = field(default_factory=datetime.now)
    generation_time_ms: float = 0.0
    expiry_seconds: int = 180  # 3 minutes default

    # Tracking
    is_collapsed: bool = False
    collapsed_variant: str | None = None

    def is_stale(self) -> bool:
        """Check if this branch has expired."""
        age = (datetime.now() - self.generated_at).total_seconds()
        return age > self.expiry_seconds

    def age_seconds(self) -> float:
        """Get age of this branch in seconds."""
        return (datetime.now() - self.generated_at).total_seconds()

    def remaining_ttl_seconds(self) -> float:
        """Get remaining time-to-live in seconds."""
        return max(0.0, self.expiry_seconds - self.age_seconds())

    def get_variant(self, variant_type: VariantType) -> OutcomeVariant | None:
        """Get a specific variant by type."""
        return self.variants.get(variant_type.value)

    @classmethod
    def create_key(
        cls,
        location_key: str,
        action_type: ActionType,
        target_key: str | None,
        gm_decision_type: str,
    ) -> str:
        """Create a branch key from components."""
        target = target_key or "none"
        return f"{location_key}::{action_type.value}::{target}::{gm_decision_type}"


@dataclass
class QuantumMetrics:
    """Metrics for tracking quantum branching performance.

    Extends the anticipation metrics with branch-specific tracking.
    """

    # Prediction counters
    predictions_made: int = 0
    actions_predicted: int = 0

    # Cache counters
    cache_hits: int = 0
    cache_misses: int = 0

    # Branch generation
    branches_generated: int = 0
    branches_collapsed: int = 0
    branches_expired: int = 0
    branches_invalidated: int = 0  # Stale state detected

    # Variant selection
    successes: int = 0
    failures: int = 0
    critical_successes: int = 0
    critical_failures: int = 0

    # Timing (cumulative)
    total_generation_time_ms: float = 0.0
    total_collapse_time_ms: float = 0.0
    total_cache_hit_latency_ms: float = 0.0

    # GM decisions
    twists_applied: int = 0
    no_twists: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0

    @property
    def avg_generation_time_ms(self) -> float:
        """Average branch generation time in milliseconds."""
        if self.branches_generated == 0:
            return 0.0
        return self.total_generation_time_ms / self.branches_generated

    @property
    def avg_cache_hit_latency_ms(self) -> float:
        """Average cache hit latency in milliseconds."""
        if self.cache_hits == 0:
            return 0.0
        return self.total_cache_hit_latency_ms / self.cache_hits

    @property
    def success_rate(self) -> float:
        """Player success rate on skill checks."""
        total = self.successes + self.failures + self.critical_successes + self.critical_failures
        if total == 0:
            return 0.0
        return (self.successes + self.critical_successes) / total

    def record_cache_hit(self, latency_ms: float) -> None:
        """Record a cache hit with latency."""
        self.cache_hits += 1
        self.total_cache_hit_latency_ms += latency_ms

    def record_cache_miss(self) -> None:
        """Record a cache miss."""
        self.cache_misses += 1

    def record_branch_generated(self, generation_time_ms: float) -> None:
        """Record a branch was generated."""
        self.branches_generated += 1
        self.total_generation_time_ms += generation_time_ms

    def record_branch_collapsed(
        self,
        variant_type: VariantType,
        had_twist: bool,
        collapse_time_ms: float,
    ) -> None:
        """Record a branch was collapsed (observed)."""
        self.branches_collapsed += 1
        self.total_collapse_time_ms += collapse_time_ms

        # Track variant outcomes
        if variant_type == VariantType.SUCCESS:
            self.successes += 1
        elif variant_type == VariantType.FAILURE:
            self.failures += 1
        elif variant_type == VariantType.CRITICAL_SUCCESS:
            self.critical_successes += 1
        elif variant_type == VariantType.CRITICAL_FAILURE:
            self.critical_failures += 1

        # Track GM decisions
        if had_twist:
            self.twists_applied += 1
        else:
            self.no_twists += 1

    def record_branch_expired(self) -> None:
        """Record a branch expired without being used."""
        self.branches_expired += 1

    def record_branch_invalidated(self) -> None:
        """Record a branch was invalidated due to stale state."""
        self.branches_invalidated += 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/display."""
        return {
            "predictions_made": self.predictions_made,
            "actions_predicted": self.actions_predicted,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": f"{self.hit_rate:.1%}",
            "branches_generated": self.branches_generated,
            "branches_collapsed": self.branches_collapsed,
            "branches_expired": self.branches_expired,
            "branches_invalidated": self.branches_invalidated,
            "avg_generation_time_ms": f"{self.avg_generation_time_ms:.0f}",
            "avg_cache_hit_latency_ms": f"{self.avg_cache_hit_latency_ms:.1f}",
            "success_rate": f"{self.success_rate:.1%}",
            "twists_applied": self.twists_applied,
            "no_twists": self.no_twists,
        }
