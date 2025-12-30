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
from src.world_server.quantum.branch_generator import BranchContext, BranchGenerator
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

logger = logging.getLogger(__name__)


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
        self.gm_oracle = GMDecisionOracle(db, game_session)
        # BranchGenerator needs structured JSON output → use reasoning model
        self.branch_generator = BranchGenerator(db, game_session, self._reasoning_llm)
        self.branch_cache = QuantumBranchCache(metrics=self._metrics)
        self.collapse_manager = BranchCollapseManager(db, game_session, self._metrics)

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

            # 3. Try to match player input
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
                    # CACHE HIT - Collapse and return
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

        # Get GM decision
        gm_decisions = self.gm_oracle.predict_decisions(action, manifest)
        selected_decision = self._select_gm_decision(gm_decisions)

        # Build generation context with player input for topic-awareness
        context = self._build_branch_context(location_key, player_input=player_input)

        # Generate branch
        try:
            branch = await self.branch_generator.generate_branch(
                action=action,
                gm_decision=selected_decision,
                manifest=manifest,
                context=context,
            )

            generation_time_ms = (time.perf_counter() - gen_start) * 1000

            # Cache the branch for potential reuse
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
        )

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
        }
