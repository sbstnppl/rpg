"""Quantum Pipeline - Main entry point for turn processing.

This module provides the unified pipeline that replaces all existing
pipelines. The core insight is that dice rolls happen LIVE at runtime -
we prepare all possible outcomes in advance, then select based on
the actual roll result.

The pipeline:
1. Predicts likely player actions from scene context
2. Pre-generates multiple outcome branches (success/failure/critical)
3. Matches player input to predicted actions
4. Rolls dice at runtime to select the appropriate branch
5. Collapses the branch and applies state changes

Background anticipation runs continuously, pre-generating branches
for likely actions so most turns get instant cache hits.
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from src.database.models.session import GameSession, Turn
from src.database.models.world import TimeState
from src.dice.types import AdvantageType
from src.gm.context_builder import GMContextBuilder
from src.gm.grounding import GroundingManifest
from src.llm.base import LLMProvider
from src.llm.factory import get_narrator_provider, get_reasoning_provider
from src.world_server.quantum.action_matcher import ActionMatcher, MatchResult
from src.world_server.quantum.action_predictor import ActionPredictor
from src.world_server.quantum.intent import IntentType
from src.world_server.quantum.intent_classifier import (
    IntentClassifier,
    IntentClassifierInput,
    CachedBranchSummary,
)
from src.world_server.quantum.branch_generator import BranchContext, BranchGenerator

# Split architecture imports (Phases 2-5)
from src.world_server.quantum.reasoning import (
    ReasoningEngine,
    ReasoningContext,
    ReasoningResponse,
    SemanticOutcome,
    difficulty_to_dc,
    time_description_to_minutes,
    # Ref-based architecture
    RefReasoningContext,
    RefReasoningResponse,
    RefBasedOutcome,
    reason_with_refs,
)
from src.world_server.quantum.delta_translator import (
    DeltaTranslator,
    ManifestContext,
    TranslationResult,
    # Ref-based architecture
    RefDeltaTranslator,
)
from src.world_server.quantum.ref_manifest import RefManifest
from src.world_server.quantum.narrator import (
    NarratorEngine,
    NarrationContext,
)
from src.world_server.quantum.cleanup import cleanup_narrative
from src.world_server.quantum.cache import QuantumBranchCache
from src.world_server.quantum.collapse import (
    BranchCollapseManager,
    CollapseResult,
    StaleStateError,
)
from src.world_server.quantum.gm_oracle import GMDecisionOracle
from src.world_server.quantum.schemas import (
    ActionPrediction,
    GMDecision,
    QuantumBranch,
    QuantumMetrics,
)
from src.world_server.quantum.validation import BranchValidator, IssueSeverity

logger = logging.getLogger(__name__)


def _has_blocking_grounding_errors(validation_result) -> tuple[bool, str]:
    """Check if validation result has errors that should block display.

    Args:
        validation_result: ValidationResult from BranchValidator

    Returns:
        Tuple of (should_block, fallback_narrative)
    """
    if not validation_result.errors:
        return False, ""

    # Check error categories
    has_npc_hallucination = any(
        "npc_hallucination" in i.category for i in validation_result.errors
    )
    has_grounding_error = any(
        "grounding" in i.category for i in validation_result.errors
    )
    has_delta_error = any(
        i.category == "delta" and i.severity == IssueSeverity.ERROR
        for i in validation_result.errors
    )

    if has_npc_hallucination:
        return True, "You look around but don't see anyone to talk to here."

    if has_grounding_error:
        return True, "You try, but something doesn't seem quite right..."

    if has_delta_error:
        return True, "You try to go that way, but something stops you..."

    return False, ""


@dataclass
class TurnResult:
    """Result of processing a player turn.

    Contains the narrative to display, metadata about how it was
    generated, and state changes that were applied.
    """

    # Narrative content
    narrative: str
    raw_narrative: str = ""  # With [key:text] format preserved

    # Source info
    was_cache_hit: bool = False
    matched_action: ActionPrediction | None = None
    match_confidence: float = 0.0

    # GM decision
    gm_decision: GMDecision | None = None
    had_twist: bool = False

    # Collapse info
    collapse_result: CollapseResult | None = None

    # Performance
    total_time_ms: float = 0.0
    cache_lookup_time_ms: float = 0.0
    generation_time_ms: float = 0.0

    # Error handling
    error: str | None = None
    used_fallback: bool = False

    @property
    def skill_check_result(self):
        """Convenience accessor for skill check result from collapse."""
        if self.collapse_result:
            return self.collapse_result.skill_check_result
        return None

    @property
    def errors(self) -> list[str]:
        """Convenience accessor for errors as a list (CLI compatibility)."""
        if self.error:
            return [self.error]
        return []


@dataclass
class AnticipationConfig:
    """Configuration for background anticipation.

    Note: Anticipation is disabled by default due to the topic-awareness problem.
    Pre-generated branches can't know what the player wants to discuss with NPCs.
    See docs/quantum-branching/anticipation-caching-issue.md for details.
    """

    enabled: bool = False
    max_actions_per_cycle: int = 5  # Top N actions to pre-generate
    max_gm_decisions_per_action: int = 2  # Top N GM decisions per action
    cycle_delay_seconds: float = 0.5  # Delay between anticipation cycles
    error_delay_seconds: float = 2.0  # Delay after errors


class QuantumPipeline:
    """Unified pipeline for processing player turns.

    This pipeline replaces all existing pipelines with a quantum
    branching approach. The key insight is that dice rolls happen
    at RUNTIME - we prepare all possible outcomes in advance.

    Usage:
        pipeline = QuantumPipeline(db, game_session)
        await pipeline.start_anticipation()

        result = await pipeline.process_turn(
            player_input="talk to the guard",
            location_key="village_square",
            turn_number=1,
        )

        await pipeline.stop_anticipation()
    """

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        llm_provider: LLMProvider | None = None,
        metrics: QuantumMetrics | None = None,
        anticipation_config: AnticipationConfig | None = None,
    ):
        """Initialize the pipeline.

        Args:
            db: Database session
            game_session: Current game session
            llm_provider: LLM provider for branch generation (default: narrator)
            metrics: Optional shared metrics tracker
            anticipation_config: Configuration for background anticipation
        """
        self.db = db
        self.game_session = game_session
        self._metrics = metrics or QuantumMetrics()

        # Dual-model separation:
        # - Reasoning (qwen3): Logic, predictions, tool decisions
        # - Narrator (magmell): Prose generation, narrative output
        self._reasoning_llm = get_reasoning_provider()
        self._narrator_llm = llm_provider or get_narrator_provider()

        # Initialize components
        self.action_predictor = ActionPredictor(db, game_session)
        self.action_matcher = ActionMatcher()
        self.intent_classifier = IntentClassifier()  # Phase 1: LLM-based intent classification
        self.gm_oracle = GMDecisionOracle(db, game_session)
        # BranchGenerator needs structured JSON output → use reasoning model
        self.branch_generator = BranchGenerator(db, game_session, self._reasoning_llm)
        self.branch_cache = QuantumBranchCache(metrics=self._metrics)
        self.collapse_manager = BranchCollapseManager(db, game_session, self._metrics)

        # Split architecture components (Phases 2-5)
        self.reasoning_engine = ReasoningEngine(self._reasoning_llm)  # Phase 2
        self.delta_translator = DeltaTranslator()  # Phase 3
        self.ref_delta_translator = RefDeltaTranslator()  # Phase 3 (ref-based)
        self.narrator_engine = NarratorEngine(self._narrator_llm)  # Phase 4
        # Phase 5 (cleanup) is a function, not a class

        # Configuration for split architecture (disabled by default for comparison)
        self._use_split_architecture = False
        # Ref-based architecture: uses A/B/C refs instead of display names
        self._use_ref_based = False

        # Context builder for manifests
        self._context_builder = GMContextBuilder(db, game_session)

        # Anticipation state
        self._anticipation_config = anticipation_config or AnticipationConfig()
        self._anticipation_task: asyncio.Task | None = None
        self._current_location: str | None = None
        self._running = False

    @property
    def metrics(self) -> QuantumMetrics:
        """Get the metrics tracker."""
        return self._metrics

    async def process_turn(
        self,
        player_input: str,
        location_key: str,
        turn_number: int,
        player_id: int | None = None,
        attribute_modifier: int = 0,
        skill_modifier: int = 0,
        advantage_type: AdvantageType = AdvantageType.NORMAL,
    ) -> TurnResult:
        """Process a player turn.

        This is the main entry point. It tries to:
        1. Match player input to a cached branch (fast path)
        2. If no cache hit, generate synchronously (slow path)
        3. Trigger background anticipation for new state

        Args:
            player_input: The player's input text
            location_key: Current location key
            turn_number: Current turn number
            player_id: Optional player entity ID
            attribute_modifier: Player's attribute modifier for skill checks
            skill_modifier: Player's skill modifier for skill checks
            advantage_type: Whether player has advantage/disadvantage

        Returns:
            TurnResult with narrative and metadata
        """
        start_time = time.perf_counter()
        self._current_location = location_key

        try:
            # 1. Build manifest for current scene
            manifest = await self._build_manifest(player_id, location_key)

            # 2. Get predictions
            predictions = self.action_predictor.predict_actions(
                location_key=location_key,
                manifest=manifest,
            )
            self._metrics.predictions_made += 1
            self._metrics.actions_predicted += len(predictions)

            # 3. Classify player intent (Phase 1 of split architecture)
            intent_result = await self._classify_intent(
                player_input=player_input,
                manifest=manifest,
                location_key=location_key,
            )

            # Handle informational intents (questions/hypotheticals) - no state change
            if intent_result and intent_result.is_informational:
                return await self._handle_informational_intent(
                    intent_result=intent_result,
                    manifest=manifest,
                    location_key=location_key,
                    start_time=start_time,
                )

            # 4. Match player input (fallback to old matcher if intent classifier uncertain)
            if intent_result and intent_result.confidence >= 0.7:
                # Use intent classifier result for matching
                match_result = self._intent_to_match_result(intent_result, predictions)
            else:
                # Fall back to fuzzy matcher
                match_result = self.action_matcher.match(
                    player_input=player_input,
                    predictions=predictions,
                    manifest=manifest,
                )

            if match_result:
                action = match_result.prediction
                confidence = match_result.confidence

                # 4. Get GM decisions
                gm_decisions = self.gm_oracle.predict_decisions(action, manifest)
                selected_decision = self._select_gm_decision(gm_decisions)

                # 5. Check cache for this branch
                cache_start = time.perf_counter()
                branch = await self.branch_cache.get_branch(
                    location_key=location_key,
                    action=action,
                    gm_decision_type=selected_decision.decision_type,
                )
                cache_lookup_time_ms = (time.perf_counter() - cache_start) * 1000

                if branch:
                    # CACHE HIT - Validate before collapse
                    validator = BranchValidator(manifest, self.db, self.game_session)
                    validation_result = validator.validate(branch)

                    # Check for blocking grounding errors (stale/hallucinated entities)
                    should_block, fallback_narrative = _has_blocking_grounding_errors(
                        validation_result
                    )
                    if should_block:
                        logger.warning(
                            f"Blocking grounding errors in cached branch: "
                            f"{[e.message for e in validation_result.errors]}"
                        )
                        total_time_ms = (time.perf_counter() - start_time) * 1000
                        return TurnResult(
                            narrative=fallback_narrative,
                            was_cache_hit=True,
                            matched_action=action,
                            match_confidence=confidence,
                            total_time_ms=total_time_ms,
                            cache_lookup_time_ms=cache_lookup_time_ms,
                            used_fallback=True,
                            error=f"Validation errors: {', '.join(e.message for e in validation_result.errors)}",
                        )

                    try:
                        collapse_result = await self.collapse_manager.collapse_branch(
                            branch=branch,
                            player_input=player_input,
                            turn_number=turn_number,
                            attribute_modifier=attribute_modifier,
                            skill_modifier=skill_modifier,
                            advantage_type=advantage_type,
                        )

                        total_time_ms = (time.perf_counter() - start_time) * 1000

                        # Trigger anticipation for new state
                        self._trigger_anticipation(location_key)

                        return TurnResult(
                            narrative=collapse_result.narrative,
                            raw_narrative=collapse_result.raw_narrative,
                            was_cache_hit=True,
                            matched_action=action,
                            match_confidence=confidence,
                            gm_decision=selected_decision,
                            had_twist=collapse_result.had_twist,
                            collapse_result=collapse_result,
                            total_time_ms=total_time_ms,
                            cache_lookup_time_ms=cache_lookup_time_ms,
                        )

                    except StaleStateError as e:
                        logger.warning(f"Stale branch, generating sync: {e}")
                        # Fall through to sync generation

            # 6. CACHE MISS - Generate synchronously
            result = await self._generate_sync(
                player_input=player_input,
                location_key=location_key,
                turn_number=turn_number,
                manifest=manifest,
                predictions=predictions,
                match_result=match_result,
                attribute_modifier=attribute_modifier,
                skill_modifier=skill_modifier,
                advantage_type=advantage_type,
                intent_result=intent_result,
            )

            result.total_time_ms = (time.perf_counter() - start_time) * 1000

            # Trigger anticipation
            self._trigger_anticipation(location_key)

            return result

        except Exception as e:
            logger.error(f"Turn processing failed: {e}")
            total_time_ms = (time.perf_counter() - start_time) * 1000

            return TurnResult(
                narrative=f"Something unexpected happened. ({str(e)[:50]})",
                was_cache_hit=False,
                total_time_ms=total_time_ms,
                error=str(e),
                used_fallback=True,
            )

    async def _build_manifest(
        self,
        player_id: int | None,
        location_key: str,
    ) -> GroundingManifest:
        """Build grounding manifest for current scene.

        Args:
            player_id: Optional player entity ID
            location_key: Current location key

        Returns:
            GroundingManifest with all scene entities
        """
        if player_id is None:
            # Try to get player ID from session
            player_id = self._get_player_id()

        return self._context_builder.build_grounding_manifest(
            player_id=player_id,
            location_key=location_key,
        )

    def _get_player_entity(self):
        """Get player entity from session."""
        from src.database.models.entities import Entity
        from src.database.models.enums import EntityType

        return (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.game_session.id,
                Entity.entity_type == EntityType.PLAYER,
            )
            .first()
        )

    def _get_player_id(self) -> int:
        """Get player entity ID from session."""
        player = self._get_player_entity()
        return player.id if player else 0

    def _select_gm_decision(self, decisions: list[GMDecision]) -> GMDecision:
        """Select a GM decision based on probabilities.

        Uses weighted random selection based on decision probabilities.

        Args:
            decisions: List of possible GM decisions

        Returns:
            Selected GMDecision
        """
        if not decisions:
            return GMDecision(decision_type="no_twist", probability=1.0)

        if len(decisions) == 1:
            return decisions[0]

        # Weighted random selection
        total_prob = sum(d.probability for d in decisions)
        if total_prob <= 0:
            return decisions[0]

        r = random.random() * total_prob
        cumulative = 0.0

        for decision in decisions:
            cumulative += decision.probability
            if r <= cumulative:
                return decision

        return decisions[-1]

    # =========================================================================
    # Intent Classification (Phase 1 of split architecture)
    # =========================================================================

    async def _classify_intent(
        self,
        player_input: str,
        manifest: GroundingManifest,
        location_key: str,
    ):
        """Classify player intent using LLM.

        This is Phase 1 of the split architecture. The intent classifier
        determines whether the input is an action, question, hypothetical,
        or OOC request, and extracts relevant details.

        Args:
            player_input: The player's input text
            manifest: Current scene manifest
            location_key: Current location key

        Returns:
            IntentClassification or None if classification fails
        """
        from src.world_server.quantum.intent import IntentClassification

        try:
            # Get location display name
            location_display = manifest.location_display or location_key

            # Extract available targets from manifest (npcs/items/exits are dicts)
            npcs = [npc.display_name for npc in manifest.npcs.values()] if manifest.npcs else []
            # items_at_location = things player can pick up
            items = [item.display_name for item in manifest.items_at_location.values()] if manifest.items_at_location else []
            exits = [exit.display_name for exit in manifest.exits.values()] if manifest.exits else []

            # Build classifier input
            classifier_input = IntentClassifierInput(
                player_input=player_input,
                location_display=location_display,
                location_key=location_key,
                npcs_present=npcs,
                items_available=items,
                exits_available=exits,
                cached_branches=[],  # TODO: Add cached branch summaries for matching
            )

            # Run classification
            result = await self.intent_classifier.classify(classifier_input)
            logger.debug(
                f"Intent classification: type={result.intent_type.value}, "
                f"confidence={result.confidence:.2f}, action={result.action_type}"
            )
            return result

        except Exception as e:
            logger.warning(f"Intent classification failed, falling back: {e}")
            return None

    async def _handle_informational_intent(
        self,
        intent_result,
        manifest: GroundingManifest,
        location_key: str,
        start_time: float,
    ) -> TurnResult:
        """Handle informational intents (questions, hypotheticals).

        These don't change game state - they just describe possibilities.

        Args:
            intent_result: The classified intent
            manifest: Current scene manifest
            location_key: Current location key
            start_time: Turn start time for timing

        Returns:
            TurnResult with descriptive narrative (no state changes)
        """
        # Generate a descriptive response without executing anything
        # For now, use a simple template - future: use narrator model

        narrative = self._generate_informational_response(intent_result, manifest)

        total_time_ms = (time.perf_counter() - start_time) * 1000

        return TurnResult(
            narrative=narrative,
            was_cache_hit=False,
            total_time_ms=total_time_ms,
            used_fallback=False,
        )

    def _generate_informational_response(self, intent_result, manifest: GroundingManifest) -> str:
        """Generate a response for informational intents.

        Args:
            intent_result: The classified intent
            manifest: Current scene manifest

        Returns:
            Descriptive narrative answering the question
        """
        from src.world_server.quantum.intent import IntentType

        if intent_result.intent_type == IntentType.QUESTION:
            # Answer questions about possibilities
            if intent_result.target_display:
                # Check if target exists in scene
                target = intent_result.target_display.lower()

                # Check NPCs (manifest.npcs is a dict)
                for npc in (manifest.npcs or {}).values():
                    if target in npc.display_name.lower():
                        desc = npc.short_description or "available"
                        return f"Yes, {npc.display_name} is here. They appear to be {desc}."

                # Check items at location (manifest.items_at_location is a dict)
                for item in (manifest.items_at_location or {}).values():
                    if target in item.display_name.lower():
                        return f"Yes, you can see {item.display_name} nearby."

                # Check exits (manifest.exits is a dict)
                for exit in (manifest.exits or {}).values():
                    if target in exit.display_name.lower():
                        return f"Yes, you could go to {exit.display_name} from here."

                return f"You don't see '{intent_result.target_display}' here."
            else:
                return "What would you like to know about?"

        elif intent_result.intent_type == IntentType.HYPOTHETICAL:
            if intent_result.target_display:
                return f"If you tried that with {intent_result.target_display}, various outcomes could unfold depending on the circumstances."
            return "That's an interesting thought. What specifically are you considering?"

        elif intent_result.intent_type == IntentType.OUT_OF_CHARACTER:
            return "That's an out-of-character request. What would you like to know?"

        return "I'm not sure what you're asking. Could you be more specific?"

    def _intent_to_match_result(
        self,
        intent_result,
        predictions: list[ActionPrediction],
    ) -> MatchResult | None:
        """Convert intent classification to MatchResult.

        Finds the best matching prediction based on the classified intent.

        Args:
            intent_result: The classified intent
            predictions: Available action predictions

        Returns:
            MatchResult if a good match is found, None otherwise
        """
        if not intent_result.action_type:
            return None

        # Find prediction matching the intent
        for prediction in predictions:
            # Match by action type
            if prediction.action_type.value != intent_result.action_type.value:
                continue

            # Match by target if specified
            if intent_result.target_display:
                target_lower = intent_result.target_display.lower()

                # Check if prediction has a matching target
                if prediction.display_name:
                    if target_lower not in prediction.display_name.lower():
                        continue
                elif prediction.target_key:
                    if target_lower not in prediction.target_key.lower():
                        continue

            # Found a match
            return MatchResult(
                prediction=prediction,
                confidence=intent_result.confidence,
                match_reason="intent_classifier",
            )

        return None

    async def _generate_sync(
        self,
        player_input: str,
        location_key: str,
        turn_number: int,
        manifest: GroundingManifest,
        predictions: list[ActionPrediction],
        match_result: MatchResult | None,
        attribute_modifier: int,
        skill_modifier: int,
        advantage_type: AdvantageType,
        intent_result=None,
    ) -> TurnResult:
        """Generate a branch synchronously on cache miss.

        Args:
            player_input: Player's input
            location_key: Current location
            turn_number: Current turn
            manifest: Scene manifest
            predictions: Action predictions
            match_result: Match result (if any)
            attribute_modifier: Player's attribute modifier
            skill_modifier: Player's skill modifier
            advantage_type: Advantage state
            intent_result: Optional intent classification from Phase 1

        Returns:
            TurnResult from synchronous generation
        """
        gen_start = time.perf_counter()

        # Get action and decision
        if match_result:
            action = match_result.prediction
            confidence = match_result.confidence
        else:
            # No match - use first prediction or create generic
            if predictions:
                action = predictions[0]
                confidence = 0.3
            else:
                # Create a generic action
                from src.world_server.quantum.schemas import ActionType
                from src.world_server.schemas import PredictionReason

                action = ActionPrediction(
                    action_type=ActionType.CUSTOM,
                    target_key=None,
                    input_patterns=[],
                    probability=0.1,
                    reason=PredictionReason.DEFAULT,
                    context={"original_input": player_input},
                )
                confidence = 0.1

        # Use ref-based architecture if enabled (highest priority)
        if self._use_ref_based:
            logger.info("Using ref-based architecture")
            return await self._generate_ref_based(
                player_input=player_input,
                location_key=location_key,
                turn_number=turn_number,
                manifest=manifest,
                action=action,
                intent_result=intent_result,
                attribute_modifier=attribute_modifier,
                skill_modifier=skill_modifier,
                advantage_type=advantage_type,
            )

        # Use split architecture if enabled
        if self._use_split_architecture:
            logger.info("Using split architecture (Phases 2-5)")
            return await self._generate_split_architecture(
                player_input=player_input,
                location_key=location_key,
                turn_number=turn_number,
                manifest=manifest,
                action=action,
                intent_result=intent_result,
                attribute_modifier=attribute_modifier,
                skill_modifier=skill_modifier,
                advantage_type=advantage_type,
            )

        # Get GM decision
        gm_decisions = self.gm_oracle.predict_decisions(action, manifest)
        selected_decision = self._select_gm_decision(gm_decisions)

        # Build generation context with player input for topic-awareness
        # For MOVE actions, use destination location for accurate arrival narrative
        from src.world_server.quantum.schemas import ActionType

        generation_manifest = manifest
        generation_location = location_key

        if action.action_type == ActionType.MOVE and action.target_key:
            # Build manifest for destination so narrative describes where player arrives
            try:
                generation_manifest = await self._build_manifest(
                    self._get_player_id(), action.target_key
                )
                generation_location = action.target_key
                logger.debug(f"Using destination manifest for MOVE to {action.target_key}")
            except Exception as e:
                logger.warning(f"Failed to build destination manifest: {e}, using current")

        context = self._build_branch_context(generation_location, player_input=player_input)

        # Generate branch
        try:
            branch = await self.branch_generator.generate_branch(
                action=action,
                gm_decision=selected_decision,
                manifest=generation_manifest,
                context=context,
            )

            generation_time_ms = (time.perf_counter() - gen_start) * 1000

            # Validate the branch for grounding/hallucination issues
            # Use the same manifest that was used for generation (destination for MOVE)
            validator = BranchValidator(generation_manifest, self.db, self.game_session)
            validation_result = validator.validate(branch)

            if not validation_result.valid:
                # Log validation errors
                for issue in validation_result.errors:
                    logger.warning(f"Branch validation: {issue.category} - {issue.message}")

                # Check for blocking grounding errors (stale/hallucinated entities)
                should_block, fallback_narrative = _has_blocking_grounding_errors(
                    validation_result
                )
                if should_block:
                    logger.warning(
                        f"Blocking grounding errors: {[e.message for e in validation_result.errors]}"
                    )
                    return TurnResult(
                        narrative=fallback_narrative,
                        was_cache_hit=False,
                        matched_action=action,
                        match_confidence=confidence,
                        generation_time_ms=generation_time_ms,
                        used_fallback=True,
                        error=f"Validation errors: {', '.join(e.message for e in validation_result.errors)}",
                    )

            # Cache the branch for potential reuse (only if valid)
            if validation_result.valid:
                await self.branch_cache.put_branch(branch)

            # Collapse immediately
            collapse_result = await self.collapse_manager.collapse_branch(
                branch=branch,
                player_input=player_input,
                turn_number=turn_number,
                attribute_modifier=attribute_modifier,
                skill_modifier=skill_modifier,
                advantage_type=advantage_type,
            )

            return TurnResult(
                narrative=collapse_result.narrative,
                raw_narrative=collapse_result.raw_narrative,
                was_cache_hit=False,
                matched_action=action,
                match_confidence=confidence,
                gm_decision=selected_decision,
                had_twist=collapse_result.had_twist,
                collapse_result=collapse_result,
                generation_time_ms=generation_time_ms,
            )

        except Exception as e:
            logger.error(f"Branch generation failed: {e}")
            generation_time_ms = (time.perf_counter() - gen_start) * 1000

            # Return fallback narrative
            return TurnResult(
                narrative=f"You attempt to {player_input.lower()[:50]}...",
                was_cache_hit=False,
                matched_action=action,
                match_confidence=confidence,
                generation_time_ms=generation_time_ms,
                error=str(e),
                used_fallback=True,
            )

    def _build_branch_context(
        self, location_key: str, player_input: str | None = None
    ) -> BranchContext:
        """Build context for branch generation.

        Args:
            location_key: Current location
            player_input: Optional player input for topic-awareness

        Returns:
            BranchContext with scene info
        """
        # Get time state
        time_state = (
            self.db.query(TimeState)
            .filter(TimeState.session_id == self.game_session.id)
            .first()
        )

        game_time = time_state.current_time if time_state else "12:00"
        game_day = time_state.current_day if time_state else 1

        # Calculate period of day from time
        try:
            hours = int(str(game_time).split(":")[0])
            if hours < 6:
                game_period = "night"
            elif hours < 7:
                game_period = "dawn"
            elif hours < 12:
                game_period = "morning"
            elif hours < 18:
                game_period = "afternoon"
            elif hours < 21:
                game_period = "evening"
            else:
                game_period = "night"
        except (ValueError, IndexError):
            game_period = "afternoon"  # Default fallback

        # Get location display name
        from src.database.models.world import Location

        location = (
            self.db.query(Location)
            .filter(
                Location.session_id == self.game_session.id,
                Location.location_key == location_key,
            )
            .first()
        )
        location_display = location.display_name if location else location_key

        # Get recent events (last 3 turns)
        recent_turns = (
            self.db.query(Turn)
            .filter(Turn.session_id == self.game_session.id)
            .order_by(Turn.turn_number.desc())
            .limit(3)
            .all()
        )
        recent_events = [t.gm_response[:100] for t in recent_turns if t.gm_response]

        # Get actual player entity key (not hardcoded "player")
        player = self._get_player_entity()
        player_key = player.entity_key if player else "player"

        return BranchContext(
            location_key=location_key,
            location_display=location_display,
            player_key=player_key,
            game_time=game_time,
            game_day=game_day,
            recent_events=recent_events,
            player_input=player_input,
            game_period=game_period,
        )

    # =========================================================================
    # Split Architecture Generation (Phases 2-5)
    # =========================================================================

    async def _generate_split_architecture(
        self,
        player_input: str,
        location_key: str,
        turn_number: int,
        manifest: GroundingManifest,
        action: ActionPrediction,
        intent_result,
        attribute_modifier: int = 0,
        skill_modifier: int = 0,
        advantage_type: AdvantageType = AdvantageType.NORMAL,
    ) -> TurnResult:
        """Generate using the split 5-phase architecture.

        This is the new pipeline that separates concerns:
        - Phase 2: Reasoning (what happens logically)
        - Phase 3: Delta Translation (generate entity keys)
        - Phase 4: Narration (creative prose)
        - Phase 5: Cleanup (strip entity refs)

        Args:
            player_input: Player's input
            location_key: Current location
            turn_number: Current turn
            manifest: Scene manifest
            action: Matched action prediction
            intent_result: Classification from Phase 1
            attribute_modifier: Player's attribute modifier
            skill_modifier: Player's skill modifier
            advantage_type: Advantage state

        Returns:
            TurnResult from split architecture
        """
        import time as time_module
        gen_start = time_module.perf_counter()
        player = self._get_player_entity()
        player_key = player.entity_key if player else "player"

        try:
            # ===== PHASE 2: Reasoning =====
            # Build reasoning context from manifest and intent
            reasoning_context = self._build_reasoning_context(
                action=action,
                intent_result=intent_result,
                manifest=manifest,
                location_key=location_key,
            )

            reasoning_response = await self.reasoning_engine.reason(
                context=reasoning_context,
                intent=intent_result,
            )

            logger.debug(
                f"Reasoning: requires_check={reasoning_response.requires_skill_check}, "
                f"skill={reasoning_response.skill_name}"
            )

            # Select outcome based on skill check (if needed)
            outcome = await self._select_outcome_from_reasoning(
                reasoning_response=reasoning_response,
                attribute_modifier=attribute_modifier,
                skill_modifier=skill_modifier,
                advantage_type=advantage_type,
            )

            # ===== PHASE 3: Delta Translation =====
            manifest_context = self._build_manifest_context(manifest, location_key, player_key)
            translation = self.delta_translator.translate(outcome, manifest_context)

            if translation.has_errors:
                logger.warning(f"Delta translation errors: {translation.errors}")

            logger.debug(
                f"Deltas: {len(translation.deltas)}, "
                f"new_keys: {list(translation.key_mapping.values())}"
            )

            # ===== PHASE 4: Narration =====
            # Build narration context with full key mapping
            narration_context = NarrationContext(
                what_happens=outcome.what_happens,
                outcome_type=outcome.outcome_type,
                key_mapping=translation.key_mapping,
                player_key=player_key,
                location_display=manifest.location_display or location_key,
                location_key=location_key,
                npcs_in_scene={
                    npc.display_name: npc.key
                    for npc in (manifest.npcs or {}).values()
                },
                items_in_scene={
                    item.display_name: item.key
                    for item in (manifest.items_at_location or {}).values()
                },
            )

            narration_response = await self.narrator_engine.narrate(narration_context)
            raw_narrative = narration_response.narrative

            logger.debug(f"Raw narrative: {raw_narrative[:100]}...")

            # ===== PHASE 5: Cleanup =====
            cleanup_result = cleanup_narrative(raw_narrative, player_key=player_key)
            final_narrative = cleanup_result.text

            logger.debug(f"Final narrative: {final_narrative[:100]}...")

            generation_time_ms = (time_module.perf_counter() - gen_start) * 1000

            # Apply state deltas (using collapse manager for consistency)
            # For now, we build a temporary branch for the collapse manager
            from src.world_server.quantum.schemas import QuantumBranch, OutcomeVariant, VariantType

            # Create a single-variant branch for collapse
            from src.world_server.quantum.schemas import GMDecision

            variant_type = self.reasoning_engine.outcome_to_variant_type(outcome)
            variant = OutcomeVariant(
                variant_type=variant_type,
                narrative=raw_narrative,
                state_deltas=translation.deltas,
                requires_dice=reasoning_response.requires_skill_check,
                dc=difficulty_to_dc(reasoning_response.difficulty) if reasoning_response.requires_skill_check else None,
                skill=reasoning_response.skill_name,
                time_passed_minutes=translation.time_minutes,
            )

            branch = QuantumBranch(
                branch_key=f"split_{turn_number}_{int(time_module.time())}",
                action=action,
                gm_decision=GMDecision(decision_type="no_twist", probability=1.0),
                variants={variant_type.value: variant},
            )

            collapse_result = await self.collapse_manager.collapse_branch(
                branch=branch,
                player_input=player_input,
                turn_number=turn_number,
                attribute_modifier=attribute_modifier,
                skill_modifier=skill_modifier,
                advantage_type=advantage_type,
            )

            return TurnResult(
                narrative=final_narrative,
                raw_narrative=raw_narrative,
                was_cache_hit=False,
                matched_action=action,
                match_confidence=0.9,  # High confidence for split architecture
                collapse_result=collapse_result,
                generation_time_ms=generation_time_ms,
            )

        except Exception as e:
            logger.error(f"Split architecture generation failed: {e}", exc_info=True)
            import time as time_module
            generation_time_ms = (time_module.perf_counter() - gen_start) * 1000

            return TurnResult(
                narrative=f"You attempt to {player_input.lower()[:50]}...",
                was_cache_hit=False,
                matched_action=action,
                match_confidence=0.5,
                generation_time_ms=generation_time_ms,
                error=str(e),
                used_fallback=True,
            )

    def _build_reasoning_context(
        self,
        action: ActionPrediction,
        intent_result,
        manifest: GroundingManifest,
        location_key: str,
    ) -> ReasoningContext:
        """Build context for the reasoning engine.

        Args:
            action: The action being performed
            intent_result: Classification from Phase 1
            manifest: Scene manifest
            location_key: Current location

        Returns:
            ReasoningContext for Phase 2
        """
        # Get location description
        from src.database.models.world import Location
        location = (
            self.db.query(Location)
            .filter(
                Location.session_id == self.game_session.id,
                Location.location_key == location_key,
            )
            .first()
        )

        location_description = ""
        if location and location.description:
            location_description = location.description

        # Build action summary
        action_summary = f"{action.action_type.value}"
        if action.display_name:
            action_summary = f"{action.action_type.value}: {action.display_name}"
        if intent_result and intent_result.topic:
            action_summary += f" (about {intent_result.topic})"

        # Extract NPC/item/exit display names
        npcs = [npc.display_name for npc in (manifest.npcs or {}).values()]
        items = [item.display_name for item in (manifest.items_at_location or {}).values()]
        exits = [exit.display_name for exit in (manifest.exits or {}).values()]

        # Get recent events
        recent_turns = (
            self.db.query(Turn)
            .filter(Turn.session_id == self.game_session.id)
            .order_by(Turn.turn_number.desc())
            .limit(3)
            .all()
        )
        recent_events = [t.gm_response[:100] for t in recent_turns if t.gm_response]

        return ReasoningContext(
            action_type=action.action_type,
            action_summary=action_summary,
            topic=intent_result.topic if intent_result else None,
            location_display=manifest.location_display or location_key,
            location_description=location_description,
            npcs_present=npcs,
            items_available=items,
            exits_available=exits,
            recent_events=recent_events,
        )

    def _build_manifest_context(
        self,
        manifest: GroundingManifest,
        location_key: str,
        player_key: str,
    ) -> ManifestContext:
        """Build ManifestContext for delta translation.

        Args:
            manifest: Scene manifest
            location_key: Current location
            player_key: Player entity key

        Returns:
            ManifestContext for Phase 3
        """
        # Build display_name -> entity_key mappings
        npcs_map = {
            npc.display_name.lower(): npc.key
            for npc in (manifest.npcs or {}).values()
        }
        items_map = {
            item.display_name.lower(): item.key
            for item in (manifest.items_at_location or {}).values()
        }
        # Player inventory items
        for item in (manifest.inventory or {}).values():
            items_map[item.display_name.lower()] = item.key

        locations_map = {
            exit.display_name.lower(): exit.key
            for exit in (manifest.exits or {}).values()
        }

        return ManifestContext(
            npcs=npcs_map,
            items=items_map,
            locations=locations_map,
            current_location_key=location_key,
            player_key=player_key,
        )

    async def _select_outcome_from_reasoning(
        self,
        reasoning_response: ReasoningResponse,
        attribute_modifier: int,
        skill_modifier: int,
        advantage_type: AdvantageType,
    ) -> SemanticOutcome:
        """Select the appropriate outcome based on skill check.

        If the action requires a skill check, roll dice and select
        the appropriate outcome. Otherwise, return success.

        Args:
            reasoning_response: Response from Phase 2
            attribute_modifier: Player's attribute modifier
            skill_modifier: Player's skill modifier
            advantage_type: Advantage state

        Returns:
            Selected SemanticOutcome
        """
        if not reasoning_response.requires_skill_check:
            return reasoning_response.success

        # Roll skill check
        from src.dice.roller import DiceRoller

        dc = difficulty_to_dc(reasoning_response.difficulty)
        roller = DiceRoller()

        result = roller.skill_check(
            dc=dc,
            modifier=attribute_modifier + skill_modifier,
            advantage_type=advantage_type,
        )

        logger.info(
            f"Skill check: {reasoning_response.skill_name} DC {dc}, "
            f"rolled {result.total} ({'success' if result.success else 'failure'})"
        )

        # Select outcome based on roll
        if result.is_critical_success and reasoning_response.critical_success:
            return reasoning_response.critical_success
        elif result.is_critical_failure and reasoning_response.critical_failure:
            return reasoning_response.critical_failure
        elif result.success:
            return reasoning_response.success
        elif reasoning_response.failure:
            return reasoning_response.failure
        else:
            # Fallback to success if no failure variant
            return reasoning_response.success

    # =========================================================================
    # Ref-Based Architecture Generation
    # =========================================================================

    async def _generate_ref_based(
        self,
        player_input: str,
        location_key: str,
        turn_number: int,
        manifest: GroundingManifest,
        action: ActionPrediction,
        intent_result,
        attribute_modifier: int = 0,
        skill_modifier: int = 0,
        advantage_type: AdvantageType = AdvantageType.NORMAL,
    ) -> TurnResult:
        """Generate using the ref-based architecture.

        This architecture uses single-letter refs (A, B, C) instead of
        display names to eliminate fuzzy matching entirely. Invalid refs
        produce clear errors instead of being guessed.

        Flow:
        1. Build RefManifest from GroundingManifest
        2. Call reason_with_refs() with entity refs
        3. Use RefDeltaTranslator to resolve refs to keys
        4. Pass resolved entities to narrator
        5. Cleanup and collapse

        Args:
            player_input: Player's input
            location_key: Current location
            turn_number: Current turn
            manifest: Scene manifest
            action: Matched action prediction
            intent_result: Classification from Phase 1
            attribute_modifier: Player's attribute modifier
            skill_modifier: Player's skill modifier
            advantage_type: Advantage state

        Returns:
            TurnResult from ref-based architecture
        """
        import time as time_module
        from src.llm.audit_logger import set_audit_context

        gen_start = time_module.perf_counter()
        player = self._get_player_entity()
        player_key = player.entity_key if player else "player"

        # Set audit context for LLM logging
        set_audit_context(
            session_id=self.game_session.id,
            turn_number=turn_number,
            call_type="ref_based_turn",
        )

        try:
            # ===== BUILD REF MANIFEST =====
            ref_manifest = RefManifest.from_grounding_manifest(manifest, player_key)
            entities_prompt = ref_manifest.format_for_reasoning_prompt()

            logger.debug(f"Ref manifest: {len(ref_manifest.entries)} entities")

            # ===== PHASE 2: Reasoning with Refs =====
            # Build context with entities in ref format
            from src.database.models.world import Location
            location = (
                self.db.query(Location)
                .filter(
                    Location.session_id == self.game_session.id,
                    Location.location_key == location_key,
                )
                .first()
            )
            location_description = location.description if location else ""

            # Build action summary
            action_summary = f"{action.action_type.value}"
            if action.display_name:
                action_summary = f"{action.action_type.value}: {action.display_name}"
            if intent_result and intent_result.topic:
                action_summary += f" (about {intent_result.topic})"

            # Get recent events for context
            recent_turns = (
                self.db.query(Turn)
                .filter(Turn.session_id == self.game_session.id)
                .order_by(Turn.turn_number.desc())
                .limit(3)
                .all()
            )
            recent_events = [t.gm_response[:100] for t in recent_turns if t.gm_response]

            # Build ref-based reasoning context
            ref_context = RefReasoningContext(
                action_type=action.action_type,
                action_summary=action_summary,
                topic=intent_result.topic if intent_result else None,
                location_display=manifest.location_display or location_key,
                location_description=location_description,
                entities_prompt=entities_prompt,
                recent_events=recent_events,
            )

            reasoning_response = await reason_with_refs(ref_context, self._reasoning_llm)

            logger.debug(
                f"Ref reasoning: requires_check={reasoning_response.requires_skill_check}, "
                f"skill={reasoning_response.skill_name}"
            )

            # Select outcome based on skill check (if needed)
            outcome = await self._select_ref_outcome(
                reasoning_response=reasoning_response,
                attribute_modifier=attribute_modifier,
                skill_modifier=skill_modifier,
                advantage_type=advantage_type,
            )

            # ===== PHASE 3: Delta Translation with Refs =====
            translation = self.ref_delta_translator.translate(outcome, ref_manifest)

            if translation.has_errors:
                logger.warning(f"Ref delta translation errors: {translation.errors}")
                # Continue anyway - some errors are recoverable

            logger.debug(
                f"Ref deltas: {len(translation.deltas)}, "
                f"key_mapping: {translation.key_mapping}"
            )

            # ===== PHASE 4: Narration =====
            # Build narration context with resolved entity keys
            narration_context = NarrationContext(
                what_happens=outcome.what_happens,
                outcome_type=outcome.outcome_type,
                key_mapping=translation.key_mapping,
                player_key=player_key,
                location_display=manifest.location_display or location_key,
                location_key=location_key,
                npcs_in_scene={
                    npc.display_name: npc.key
                    for npc in (manifest.npcs or {}).values()
                },
                items_in_scene={
                    item.display_name: item.key
                    for item in (manifest.items_at_location or {}).values()
                },
            )

            narration_response = await self.narrator_engine.narrate(narration_context)
            raw_narrative = narration_response.narrative

            logger.debug(f"Raw narrative: {raw_narrative[:100]}...")

            # ===== PHASE 5: Cleanup =====
            cleanup_result = cleanup_narrative(raw_narrative, player_key=player_key)
            final_narrative = cleanup_result.text

            logger.debug(f"Final narrative: {final_narrative[:100]}...")

            generation_time_ms = (time_module.perf_counter() - gen_start) * 1000

            # ===== Apply state deltas via collapse manager =====
            from src.world_server.quantum.schemas import QuantumBranch, OutcomeVariant, VariantType, GMDecision

            # Map outcome_type to variant_type
            variant_type_map = {
                "success": VariantType.SUCCESS,
                "failure": VariantType.FAILURE,
                "critical_success": VariantType.CRITICAL_SUCCESS,
                "critical_failure": VariantType.CRITICAL_FAILURE,
            }
            variant_type = variant_type_map.get(outcome.outcome_type, VariantType.SUCCESS)

            variant = OutcomeVariant(
                variant_type=variant_type,
                narrative=raw_narrative,
                state_deltas=translation.deltas,
                requires_dice=reasoning_response.requires_skill_check,
                dc=difficulty_to_dc(reasoning_response.difficulty) if reasoning_response.requires_skill_check else None,
                skill=reasoning_response.skill_name,
                time_passed_minutes=translation.time_minutes,
            )

            branch = QuantumBranch(
                branch_key=f"ref_{turn_number}_{int(time_module.time())}",
                action=action,
                gm_decision=GMDecision(decision_type="no_twist", probability=1.0),
                variants={variant_type.value: variant},
            )

            collapse_result = await self.collapse_manager.collapse_branch(
                branch=branch,
                player_input=player_input,
                turn_number=turn_number,
                attribute_modifier=attribute_modifier,
                skill_modifier=skill_modifier,
                advantage_type=advantage_type,
            )

            return TurnResult(
                narrative=final_narrative,
                raw_narrative=raw_narrative,
                was_cache_hit=False,
                matched_action=action,
                match_confidence=0.95,  # High confidence for ref-based (deterministic)
                collapse_result=collapse_result,
                generation_time_ms=generation_time_ms,
            )

        except Exception as e:
            logger.error(f"Ref-based generation failed: {e}", exc_info=True)
            import time as time_module
            generation_time_ms = (time_module.perf_counter() - gen_start) * 1000

            return TurnResult(
                narrative=f"You attempt to {player_input.lower()[:50]}...",
                was_cache_hit=False,
                matched_action=action,
                match_confidence=0.5,
                generation_time_ms=generation_time_ms,
                error=str(e),
                used_fallback=True,
            )

    async def _select_ref_outcome(
        self,
        reasoning_response: RefReasoningResponse,
        attribute_modifier: int,
        skill_modifier: int,
        advantage_type: AdvantageType,
    ) -> RefBasedOutcome:
        """Select the appropriate ref-based outcome based on skill check.

        Args:
            reasoning_response: Response from ref-based reasoning
            attribute_modifier: Player's attribute modifier
            skill_modifier: Player's skill modifier
            advantage_type: Advantage state

        Returns:
            Selected RefBasedOutcome
        """
        if not reasoning_response.requires_skill_check:
            return reasoning_response.success

        # Roll skill check
        from src.dice.roller import DiceRoller

        dc = difficulty_to_dc(reasoning_response.difficulty)
        roller = DiceRoller()

        result = roller.skill_check(
            dc=dc,
            modifier=attribute_modifier + skill_modifier,
            advantage_type=advantage_type,
        )

        logger.info(
            f"Ref skill check: {reasoning_response.skill_name} DC {dc}, "
            f"rolled {result.total} ({'success' if result.success else 'failure'})"
        )

        # Select outcome based on roll
        if result.is_critical_success and reasoning_response.critical_success:
            return reasoning_response.critical_success
        elif result.is_critical_failure and reasoning_response.critical_failure:
            return reasoning_response.critical_failure
        elif result.success:
            return reasoning_response.success
        elif reasoning_response.failure:
            return reasoning_response.failure
        else:
            # Fallback to success if no failure variant
            return reasoning_response.success

    # =========================================================================
    # Background Anticipation
    # =========================================================================

    async def start_anticipation(self) -> None:
        """Start background anticipation loop."""
        if self._anticipation_task is not None:
            return

        if not self._anticipation_config.enabled:
            logger.info("Anticipation disabled by config")
            return

        self._running = True
        self._anticipation_task = asyncio.create_task(self._anticipation_loop())
        logger.info("Started background anticipation")

    async def stop_anticipation(self) -> None:
        """Stop background anticipation loop."""
        self._running = False

        if self._anticipation_task is not None:
            self._anticipation_task.cancel()
            try:
                await self._anticipation_task
            except asyncio.CancelledError:
                pass
            self._anticipation_task = None

        logger.info("Stopped background anticipation")

    def _trigger_anticipation(self, location_key: str) -> None:
        """Trigger anticipation for a new location.

        Args:
            location_key: Location to anticipate for
        """
        self._current_location = location_key
        # Anticipation loop will pick this up on next cycle

    async def _anticipation_loop(self) -> None:
        """Background loop that pre-generates branches.

        Runs continuously, predicting actions and generating branches
        for the current location. Uses exponential backoff on errors.
        """
        config = self._anticipation_config

        while self._running:
            try:
                location_key = self._current_location
                if not location_key:
                    await asyncio.sleep(config.cycle_delay_seconds)
                    continue

                # Build manifest
                player_id = self._get_player_id()
                manifest = await self._build_manifest(player_id, location_key)

                # Predict actions
                predictions = self.action_predictor.predict_actions(
                    location_key=location_key,
                    manifest=manifest,
                )

                # Generate branches for top N predictions
                branches_generated = 0
                for action in predictions[: config.max_actions_per_cycle]:
                    # Check if action already cached
                    cached_branches = await self.branch_cache.get_branches_for_action(
                        location_key=location_key,
                        action=action,
                    )
                    if len(cached_branches) >= config.max_gm_decisions_per_action:
                        continue

                    # Get GM decisions
                    gm_decisions = self.gm_oracle.predict_decisions(action, manifest)

                    # Generate branches for top GM decisions
                    context = self._build_branch_context(location_key)
                    for decision in gm_decisions[: config.max_gm_decisions_per_action]:
                        # Check if this specific branch is cached
                        existing = await self.branch_cache.get_branch(
                            location_key=location_key,
                            action=action,
                            gm_decision_type=decision.decision_type,
                        )
                        if existing:
                            continue

                        # Generate and cache
                        try:
                            branch = await self.branch_generator.generate_branch(
                                action=action,
                                gm_decision=decision,
                                manifest=manifest,
                                context=context,
                            )
                            await self.branch_cache.put_branch(branch)
                            branches_generated += 1

                        except Exception as e:
                            logger.warning(f"Anticipation generation failed: {e}")

                if branches_generated > 0:
                    logger.debug(f"Anticipation generated {branches_generated} branches")

                await asyncio.sleep(config.cycle_delay_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Anticipation error: {e}")
                await asyncio.sleep(config.error_delay_seconds)

    # =========================================================================
    # Cache Management
    # =========================================================================

    async def invalidate_location(self, location_key: str) -> int:
        """Invalidate all cached branches for a location.

        Call this when world state changes at a location.

        Args:
            location_key: Location to invalidate

        Returns:
            Number of branches invalidated
        """
        return await self.branch_cache.invalidate_location(location_key)

    async def clear_cache(self) -> int:
        """Clear all cached branches.

        Returns:
            Number of branches cleared
        """
        return await self.branch_cache.clear()

    def enable_split_architecture(self, enabled: bool = True) -> None:
        """Enable or disable the split architecture (Phases 2-5).

        When enabled, the pipeline uses:
        - Phase 2: ReasoningEngine (semantic outcomes)
        - Phase 3: DeltaTranslator (generate entity keys)
        - Phase 4: NarratorEngine (creative prose)
        - Phase 5: cleanup_narrative (final processing)

        When disabled (default), uses the old BranchGenerator.

        Args:
            enabled: Whether to enable split architecture
        """
        self._use_split_architecture = enabled
        logger.info(f"Split architecture {'enabled' if enabled else 'disabled'}")

    def enable_ref_based(self, enabled: bool = True) -> None:
        """Enable or disable the ref-based architecture.

        When enabled, the pipeline uses single-letter refs (A, B, C) instead
        of display names to eliminate fuzzy matching entirely. This provides:
        - Deterministic entity resolution (no guessing)
        - Clear errors for invalid refs
        - Simpler disambiguation for duplicate display names

        Takes priority over split architecture when both are enabled.

        Args:
            enabled: Whether to enable ref-based architecture
        """
        self._use_ref_based = enabled
        logger.info(f"Ref-based architecture {'enabled' if enabled else 'disabled'}")

    def get_stats(self) -> dict[str, Any]:
        """Get pipeline statistics.

        Returns:
            Dictionary with cache and metrics stats
        """
        return {
            "cache": self.branch_cache.get_stats(),
            "metrics": self._metrics.to_dict(),
            "anticipation": {
                "enabled": self._anticipation_config.enabled,
                "running": self._running,
                "current_location": self._current_location,
            },
            "split_architecture": {
                "enabled": self._use_split_architecture,
            },
            "ref_based": {
                "enabled": self._use_ref_based,
            },
        }
