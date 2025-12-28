"""Anticipation Engine for pre-generating scenes.

The engine runs in the background, predicting likely player destinations
and pre-generating scenes for them while the player reads narrative text.
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Callable

from sqlalchemy.orm import Session

from src.database.models.session import GameSession
from src.database.models.world import Location
from src.world_server.cache import PreGenerationCache
from src.world_server.predictor import LocationPredictor
from src.world_server.schemas import (
    AnticipationMetrics,
    AnticipationTask,
    GenerationStatus,
    PreGeneratedScene,
    PredictionReason,
)

logger = logging.getLogger(__name__)


class AnticipationEngine:
    """Pre-generates content for predicted player destinations.

    The engine:
    1. Predicts likely next locations based on current position
    2. Queues generation tasks for locations not in cache
    3. Runs generation in background threads
    4. Stores results in cache for instant retrieval
    """

    def __init__(
        self,
        db_session_factory: Callable[[], Session],
        game_session_id: int,
        cache: PreGenerationCache | None = None,
        max_workers: int = 2,
        check_interval: float = 1.0,
        max_predictions: int = 3,
    ):
        """Initialize the anticipation engine.

        Args:
            db_session_factory: Factory function to create new DB sessions
            game_session_id: ID of the current game session
            cache: Pre-generation cache (creates new one if None)
            max_workers: Max concurrent generation threads
            check_interval: Seconds between anticipation cycles
            max_predictions: Max locations to predict per cycle
        """
        self._db_session_factory = db_session_factory
        self._game_session_id = game_session_id
        self._cache = cache or PreGenerationCache()
        self._max_workers = max_workers
        self._check_interval = check_interval
        self._max_predictions = max_predictions

        # Thread pool for LLM generation
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

        # State
        self._running = False
        self._current_location: str | None = None
        self._generation_tasks: dict[str, AnticipationTask] = {}
        self._loop_task: asyncio.Task | None = None

        # Metrics
        self._metrics = self._cache.metrics

    @property
    def cache(self) -> PreGenerationCache:
        """Get the pre-generation cache."""
        return self._cache

    @property
    def metrics(self) -> AnticipationMetrics:
        """Get anticipation metrics."""
        return self._metrics

    @property
    def is_running(self) -> bool:
        """Check if the anticipation loop is running."""
        return self._running

    @property
    def current_location(self) -> str | None:
        """Get the current player location."""
        return self._current_location

    async def start(self, current_location: str) -> None:
        """Start the anticipation engine.

        Args:
            current_location: Current player location key
        """
        if self._running:
            logger.warning("Anticipation engine already running")
            return

        self._running = True
        self._current_location = current_location
        self._loop_task = asyncio.create_task(self._anticipation_loop())

        logger.info(
            f"Anticipation engine started at {current_location}, "
            f"max_workers={self._max_workers}, "
            f"interval={self._check_interval}s"
        )

    async def stop(self) -> None:
        """Stop the anticipation engine."""
        if not self._running:
            return

        self._running = False

        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None

        # Mark in-progress tasks as expired
        for task in self._generation_tasks.values():
            if task.status == GenerationStatus.IN_PROGRESS:
                task.mark_expired()
                self._metrics.record_generation_expired()

        logger.info("Anticipation engine stopped")

    async def on_location_change(self, new_location: str) -> None:
        """Called when player moves to a new location.

        This invalidates stale predictions and starts predicting from
        the new location.

        Args:
            new_location: New player location key
        """
        old_location = self._current_location
        self._current_location = new_location

        logger.info(f"Location changed: {old_location} -> {new_location}")

        # Check if we had a cache hit (new location was pre-generated)
        # The actual cache lookup happens in StateCollapseManager, but we can
        # track if this location was in our prediction set
        for task in self._generation_tasks.values():
            if task.location_key == new_location:
                if task.status == GenerationStatus.COMPLETED:
                    logger.info(f"Prediction hit: {new_location} was pre-generated")

        # Invalidate predictions from old location
        # Keep the new location if it was pre-generated
        await self._cache.invalidate_all_except(keep_key=new_location)

        # Mark in-progress tasks for other locations as expired
        for task in list(self._generation_tasks.values()):
            if task.location_key != new_location:
                if task.status == GenerationStatus.IN_PROGRESS:
                    task.mark_expired()
                    self._metrics.record_generation_expired()

        # Clear old task tracking
        self._generation_tasks = {
            k: v for k, v in self._generation_tasks.items()
            if k == new_location
        }

        # Trigger immediate prediction cycle for new location
        if self._running:
            asyncio.create_task(self._run_anticipation_cycle())

    async def get_pre_generated(self, location_key: str) -> PreGeneratedScene | None:
        """Get a pre-generated scene if available.

        Args:
            location_key: Location to look up

        Returns:
            PreGeneratedScene if found and fresh, None otherwise
        """
        return await self._cache.get(location_key)

    async def force_generate(self, location_key: str) -> PreGeneratedScene | None:
        """Force generation of a specific location (blocking).

        Bypasses the prediction system and generates immediately.
        Useful for testing or manual pre-generation.

        Args:
            location_key: Location to generate

        Returns:
            Generated scene or None if failed
        """
        logger.info(f"Force generating scene for {location_key}")

        # Check if already cached
        cached = await self._cache.get(location_key)
        if cached:
            return cached

        # Generate synchronously
        try:
            scene = await self._generate_scene(location_key)
            if scene:
                await self._cache.put(scene)
            return scene
        except Exception as e:
            logger.error(f"Force generation failed for {location_key}: {e}")
            return None

    async def _anticipation_loop(self) -> None:
        """Background loop that runs anticipation cycles."""
        logger.debug("Anticipation loop started")

        while self._running:
            try:
                await self._run_anticipation_cycle()
            except Exception as e:
                logger.error(f"Anticipation cycle error: {e}", exc_info=True)

            await asyncio.sleep(self._check_interval)

        logger.debug("Anticipation loop ended")

    async def _run_anticipation_cycle(self) -> None:
        """Run a single anticipation cycle."""
        if not self._current_location:
            return

        # Get predictions
        predictions = await self._get_predictions()

        if not predictions:
            return

        self._metrics.predictions_made += len(predictions)

        # Queue generation for predictions not in cache
        for pred in predictions:
            # Skip if already in cache
            if await self._cache.contains(pred.location_key):
                logger.debug(f"Skipping {pred.location_key}, already cached")
                continue

            # Skip if already being generated
            if pred.location_key in self._generation_tasks:
                task = self._generation_tasks[pred.location_key]
                if task.status in (GenerationStatus.PENDING, GenerationStatus.IN_PROGRESS):
                    logger.debug(f"Skipping {pred.location_key}, already queued")
                    continue

            # Queue for generation
            await self._queue_generation(pred.location_key, pred.probability, pred.reason)

    async def _get_predictions(self) -> list:
        """Get location predictions from the predictor."""
        # Create a new DB session for this query
        db = self._db_session_factory()
        try:
            game_session = db.query(GameSession).get(self._game_session_id)
            if not game_session:
                logger.error(f"Game session {self._game_session_id} not found")
                return []

            predictor = LocationPredictor(db, game_session)
            predictions = predictor.predict_next_locations(
                self._current_location,
                max_predictions=self._max_predictions,
            )
            return predictions
        finally:
            db.close()

    async def _queue_generation(
        self,
        location_key: str,
        priority: float,
        reason: PredictionReason,
    ) -> None:
        """Queue a location for background generation.

        Args:
            location_key: Location to generate
            priority: Generation priority (higher = sooner)
            reason: Why this location was predicted
        """
        task = AnticipationTask(
            location_key=location_key,
            priority=priority,
            prediction_reason=reason,
        )
        self._generation_tasks[location_key] = task

        logger.info(
            f"Queued generation for {location_key}, "
            f"priority={priority:.0%}, reason={reason.value}"
        )

        # Start generation in thread pool
        loop = asyncio.get_event_loop()
        loop.run_in_executor(
            self._executor,
            self._generate_scene_sync,
            location_key,
        )

    def _generate_scene_sync(self, location_key: str) -> None:
        """Generate a scene synchronously (runs in thread pool).

        This is the actual generation work that runs in a background thread.

        Args:
            location_key: Location to generate
        """
        task = self._generation_tasks.get(location_key)
        if not task:
            return

        # Check if task was cancelled/expired
        if task.status == GenerationStatus.EXPIRED:
            logger.debug(f"Task expired before starting: {location_key}")
            return

        task.mark_started()
        self._metrics.record_generation_started()
        start_time = time.perf_counter()

        logger.info(f"Starting generation for {location_key}")

        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                scene = loop.run_until_complete(self._generate_scene(location_key))
            finally:
                loop.close()

            if scene is None:
                raise ValueError(f"Scene generation returned None for {location_key}")

            # Check if still valid (location might have changed)
            if task.status == GenerationStatus.EXPIRED:
                logger.info(f"Generation completed but task expired: {location_key}")
                return

            # Store in cache
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._cache.put(scene))
            finally:
                loop.close()

            duration_ms = (time.perf_counter() - start_time) * 1000
            task.mark_completed(scene)
            self._metrics.record_generation_completed(duration_ms)

            logger.info(
                f"Generation completed for {location_key}, "
                f"duration={duration_ms:.0f}ms"
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            task.mark_failed(str(e))
            self._metrics.record_generation_failed()

            logger.error(
                f"Generation failed for {location_key} after {duration_ms:.0f}ms: {e}",
                exc_info=True,
            )

    async def _generate_scene(self, location_key: str) -> PreGeneratedScene | None:
        """Generate a scene for a location.

        This method integrates with the existing WorldMechanics and SceneBuilder.

        Args:
            location_key: Location to generate

        Returns:
            PreGeneratedScene or None if generation failed
        """
        db = self._db_session_factory()
        try:
            game_session = db.query(GameSession).get(self._game_session_id)
            if not game_session:
                logger.error(f"Game session {self._game_session_id} not found")
                return None

            # Get location
            location = (
                db.query(Location)
                .filter(
                    Location.session_id == self._game_session_id,
                    Location.location_key == location_key,
                )
                .first()
            )

            if not location:
                logger.error(f"Location not found: {location_key}")
                return None

            start_time = time.perf_counter()

            # Import here to avoid circular imports
            from src.world.world_mechanics import WorldMechanics
            from src.world.scene_builder import SceneBuilder
            from src.world.schemas import WorldUpdate, ObservationLevel

            # Get NPCs at location using WorldMechanics
            world_mechanics = WorldMechanics(db, game_session)
            npcs_at_location = world_mechanics.get_npcs_at_location(location_key)

            # Create WorldUpdate with NPCs
            world_update = WorldUpdate(npcs_at_location=npcs_at_location)

            # Build scene using SceneBuilder
            # Note: For first visits, this will use LLM to generate furniture/items
            # For return visits, it loads from DB
            scene_builder = SceneBuilder(db, game_session)
            scene_manifest = await scene_builder.build_scene(
                location_key=location_key,
                world_update=world_update,
                observation_level=ObservationLevel.ENTRY,
            )

            generation_time_ms = (time.perf_counter() - start_time) * 1000

            # Convert to PreGeneratedScene
            return PreGeneratedScene(
                location_key=location_key,
                location_display_name=location.display_name or location_key,
                scene_manifest=scene_manifest.model_dump(),
                npcs_present=[npc.model_dump() for npc in npcs_at_location],
                items_present=[
                    item.model_dump()
                    for item in scene_manifest.items
                ] if hasattr(scene_manifest, 'items') and scene_manifest.items else [],
                furniture=[
                    f.model_dump()
                    for f in scene_manifest.furniture
                ] if hasattr(scene_manifest, 'furniture') and scene_manifest.furniture else [],
                atmosphere=scene_manifest.atmosphere.model_dump() if hasattr(scene_manifest, 'atmosphere') and scene_manifest.atmosphere else {},
                generated_at=datetime.now(),
                generation_time_ms=generation_time_ms,
            )

        except Exception as e:
            logger.error(f"Scene generation error for {location_key}: {e}", exc_info=True)
            return None
        finally:
            db.close()

    async def get_status(self) -> dict:
        """Get current engine status.

        Returns:
            Dict with engine state and metrics
        """
        tasks_by_status = {}
        for task in self._generation_tasks.values():
            status = task.status.value
            tasks_by_status[status] = tasks_by_status.get(status, 0) + 1

        return {
            "running": self._running,
            "current_location": self._current_location,
            "cache_stats": await self._cache.stats(),
            "tasks": tasks_by_status,
            "metrics": self._metrics.to_dict(),
        }

    async def cleanup(self) -> None:
        """Cleanup resources."""
        await self.stop()
        self._executor.shutdown(wait=False)
        await self._cache.clear()
