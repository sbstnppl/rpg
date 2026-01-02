"""Quantum Branching World Server - Pre-generates action outcome branches.

This module provides a unified pipeline that:
- Predicts likely player actions based on scene manifest
- Pre-generates multiple outcome branches (success/failure/critical)
- Rolls dice at RUNTIME to select the appropriate branch
- Collapses uncommitted state when player observes

Key Components:
- ActionPredictor: Predicts likely actions from scene context
- ActionMatcher: Fuzzy matches player input to predictions
- GMDecisionOracle: Predicts whether GM would add a twist
- BranchGenerator: Generates narrative variants for each branch
- QuantumBranchCache: LRU cache for pre-generated branches
- BranchCollapseManager: Rolls dice and commits selected branch
- QuantumPipeline: Main entry point for turn processing

The key insight is that dice rolls happen LIVE at runtime - we prepare
all possible outcomes in advance, then select based on the roll result.
Like a tabletop GM who thinks ahead about what might happen.
"""

from src.world_server.quantum.schemas import (
    ActionType,
    VariantType,
    ActionPrediction,
    OutcomeVariant,
    GMDecision,
    QuantumBranch,
    StateDelta,
    DeltaType,
    QuantumMetrics,
)
from src.world_server.quantum.action_predictor import ActionPredictor
from src.world_server.quantum.action_matcher import ActionMatcher, MatchResult
from src.world_server.quantum.intent import (
    IntentType,
    IntentClassification,
    IntentClassifierInput,
    CachedBranchSummary,
)
from src.world_server.quantum.intent_classifier import IntentClassifier
from src.world_server.quantum.gm_oracle import GMDecisionOracle, TwistDefinition
from src.world_server.quantum.branch_generator import (
    BranchGenerator,
    BranchContext,
    BranchGenerationResponse,
)
from src.world_server.quantum.reasoning import (
    ReasoningEngine,
    ReasoningContext,
    ReasoningResponse,
    SemanticOutcome,
    SemanticChange,
    build_reasoning_context,
    difficulty_to_dc,
    time_description_to_minutes,
    # Ref-based architecture
    RefBasedChange,
    RefBasedOutcome,
    RefReasoningResponse,
    RefReasoningContext,
    reason_with_refs,
)
from src.world_server.quantum.ref_manifest import (
    RefEntry,
    RefManifest,
)
from src.world_server.quantum.delta_translator import (
    DeltaTranslator,
    TranslationResult,
    ManifestContext,
    EntityKeyGenerator,
    create_manifest_context,
    # Ref-based architecture
    RefDeltaTranslator,
)
from src.world_server.quantum.narrator import (
    NarratorEngine,
    NarrationContext,
    NarrationResponse,
    build_narration_context,
    narrate_question_response,
    narrate_ooc_response,
)
from src.world_server.quantum.cleanup import (
    CleanupResult,
    strip_entity_refs,
    normalize_whitespace,
    fix_capitalization,
    fix_pronouns,
    cleanup_narrative,
    extract_entity_keys,
    validate_entity_refs,
    replace_entity_key,
    add_entity_ref,
)
from src.world_server.quantum.cache import (
    QuantumBranchCache,
    CacheEntry,
)
from src.world_server.quantum.collapse import (
    BranchCollapseManager,
    CollapseResult,
    StaleStateError,
    strip_entity_references,
    extract_entity_references,
)
from src.world_server.quantum.pipeline import (
    QuantumPipeline,
    TurnResult,
    AnticipationConfig,
)
from src.world_server.quantum.validation import (
    IssueSeverity,
    ValidationIssue,
    ValidationResult,
    NarrativeConsistencyValidator,
    DeltaValidator,
    BranchValidator,
)

__all__ = [
    # Enums
    "ActionType",
    "VariantType",
    "DeltaType",
    # Schemas
    "ActionPrediction",
    "OutcomeVariant",
    "GMDecision",
    "QuantumBranch",
    "StateDelta",
    "QuantumMetrics",
    # Action Prediction
    "ActionPredictor",
    "ActionMatcher",
    "MatchResult",
    # Intent Classification (Phase 1)
    "IntentType",
    "IntentClassification",
    "IntentClassifierInput",
    "CachedBranchSummary",
    "IntentClassifier",
    # GM Oracle
    "GMDecisionOracle",
    "TwistDefinition",
    # Branch Generation
    "BranchGenerator",
    "BranchContext",
    "BranchGenerationResponse",
    # Reasoning (Phase 2)
    "ReasoningEngine",
    "ReasoningContext",
    "ReasoningResponse",
    "SemanticOutcome",
    "SemanticChange",
    "build_reasoning_context",
    "difficulty_to_dc",
    "time_description_to_minutes",
    # Ref-based Reasoning
    "RefBasedChange",
    "RefBasedOutcome",
    "RefReasoningResponse",
    "RefReasoningContext",
    "reason_with_refs",
    # Ref Manifest
    "RefEntry",
    "RefManifest",
    # Delta Translation (Phase 3)
    "DeltaTranslator",
    "TranslationResult",
    "ManifestContext",
    "EntityKeyGenerator",
    "create_manifest_context",
    # Ref-based Delta Translation
    "RefDeltaTranslator",
    # Narration (Phase 4)
    "NarratorEngine",
    "NarrationContext",
    "NarrationResponse",
    "build_narration_context",
    "narrate_question_response",
    "narrate_ooc_response",
    # Cleanup (Phase 5)
    "CleanupResult",
    "strip_entity_refs",
    "normalize_whitespace",
    "fix_capitalization",
    "fix_pronouns",
    "cleanup_narrative",
    "extract_entity_keys",
    "validate_entity_refs",
    "replace_entity_key",
    "add_entity_ref",
    # Cache
    "QuantumBranchCache",
    "CacheEntry",
    # Collapse
    "BranchCollapseManager",
    "CollapseResult",
    "StaleStateError",
    "strip_entity_references",
    "extract_entity_references",
    # Pipeline
    "QuantumPipeline",
    "TurnResult",
    "AnticipationConfig",
    # Validation
    "IssueSeverity",
    "ValidationIssue",
    "ValidationResult",
    "NarrativeConsistencyValidator",
    "DeltaValidator",
    "BranchValidator",
]
