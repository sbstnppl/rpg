"""Integration layer for World Server with game loop.

Provides a simple API for the CLI to interact with the anticipation system.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from sqlalchemy.orm import Session

from src.database.models.session import GameSession
from src.world_server.anticipation import AnticipationEngine
from src.world_server.cache import PreGenerationCache
from src.world_server.collapse import StateCollapseManager
from src.world_server.predictor import LocationPredictor
from src.world_server.schemas import AnticipationMetrics, CollapseResult

logger = logging.getLogger(__name__)


class WorldServerManager:
    """Manages the World Server anticipation system.

    This is the main entry point for CLI integration. It handles:
    - Starting/stopping the anticipation engine
    - Triggering anticipation after player actions
    - Checking for pre-generated content before scene generation
    """

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        max_cache_size: int = 5,
        enabled: bool = True,
    ):
        """Initialize the World Server manager.

        Args:
            db: Database session
            game_session: Current game session
            max_cache_size: Maximum number of pre-generated scenes to cache
            enabled: Whether anticipation is enabled
        """
        self.db = db
        self.game_session = game_session
        self.enabled = enabled

        # Shared metrics
        self._metrics = AnticipationMetrics()

        # Cache for pre-generated scenes
        self._cache = PreGenerationCache(
            max_size=max_cache_size,
            metrics=self._metrics,
        )

        # Predictor for location prediction
        self._predictor = LocationPredictor(db, game_session)

        # Collapse manager for committing pre-generated scenes
        self._collapse_manager = StateCollapseManager(
            db, game_session, self._cache, self._metrics
        )

        # Background executor for anticipation
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="anticipation")

        # Anticipation engine (created lazily)
        self._engine: AnticipationEngine | None = None

        # Track if we have pending anticipation work
        self._pending_future = None

        logger.info(
            f"WorldServerManager initialized for session {game_session.id}, "
            f"enabled={enabled}, cache_size={max_cache_size}"
        )

    async def trigger_anticipation(
        self,
        current_location: str,
        recent_actions: list[str] | None = None,
        scene_generator: Callable | None = None,
    ) -> None:
        """Trigger background anticipation for likely next locations.

        This should be called after displaying narrative to the player,
        while they're reading. The anticipation runs in the background.

        Args:
            current_location: Current player location key
            recent_actions: Recent player actions for context
            scene_generator: Async function to generate a scene
        """
        if not self.enabled:
            return

        # Don't start new anticipation if previous is still running
        if self._pending_future and not self._pending_future.done():
            logger.debug("Skipping anticipation - previous still running")
            return

        # Predict likely next locations
        predictions = self._predictor.predict_next_locations(
            current_location,
            recent_actions=recent_actions,
            max_predictions=3,
        )

        if not predictions:
            logger.debug(f"No predictions for {current_location}")
            return

        logger.info(
            f"Starting anticipation from {current_location}: "
            f"{[p.location_key for p in predictions]}"
        )

        # Run anticipation in background
        async def run_anticipation():
            for prediction in predictions:
                # Skip if already cached
                if await self._cache.contains(prediction.location_key):
                    logger.debug(f"Skipping {prediction.location_key} - already cached")
                    continue

                # Generate scene if generator provided
                if scene_generator:
                    try:
                        scene = await scene_generator(prediction.location_key)
                        if scene:
                            scene.prediction_reason = prediction.reason
                            await self._cache.put(scene)
                            logger.info(f"Pre-generated {prediction.location_key}")
                    except Exception as e:
                        logger.error(f"Failed to pre-generate {prediction.location_key}: {e}")

        # Schedule in background
        loop = asyncio.get_event_loop()
        self._pending_future = loop.create_task(run_anticipation())

    async def check_pre_generated(
        self,
        location_key: str,
        turn_number: int,
    ) -> CollapseResult | None:
        """Check if we have pre-generated content for a location.

        If pre-generated content exists and is valid, returns it immediately.
        Otherwise returns None, indicating normal generation should proceed.

        Args:
            location_key: Location to check
            turn_number: Current turn number

        Returns:
            CollapseResult if pre-generated content was used, None otherwise
        """
        if not self.enabled:
            return None

        # Check cache
        pre_gen = await self._cache.get(location_key)
        if pre_gen and not pre_gen.is_stale():
            logger.info(f"Cache HIT for {location_key}")
            return await self._collapse_manager.collapse_location(
                location_key, turn_number
            )

        logger.debug(f"Cache MISS for {location_key}")
        return None

    def get_stats(self) -> dict:
        """Get current anticipation statistics.

        Returns:
            Dict with cache and prediction statistics
        """
        return {
            "enabled": self.enabled,
            "metrics": self._metrics.to_dict(),
            "predictor_stats": self._predictor.get_prediction_stats(),
        }

    async def invalidate_cache(self, location_key: str | None = None) -> int:
        """Invalidate cached content.

        Args:
            location_key: Specific location to invalidate, or None for all

        Returns:
            Number of entries invalidated
        """
        if location_key:
            result = await self._cache.invalidate(location_key)
            return 1 if result else 0
        else:
            return await self._cache.clear()

    async def shutdown(self) -> None:
        """Shutdown the World Server manager.

        Cancels pending anticipation and cleans up resources.
        """
        # Cancel pending anticipation
        if self._pending_future and not self._pending_future.done():
            self._pending_future.cancel()

        # Shutdown executor
        self._executor.shutdown(wait=False)

        # Clear cache
        await self._cache.clear()

        logger.info("WorldServerManager shutdown complete")


# Singleton instance for CLI
_manager: WorldServerManager | None = None


def get_world_server_manager(
    db: Session,
    game_session: GameSession,
    enabled: bool = True,
) -> WorldServerManager:
    """Get or create the World Server manager.

    Args:
        db: Database session
        game_session: Current game session
        enabled: Whether anticipation is enabled

    Returns:
        WorldServerManager instance
    """
    global _manager

    # Create new manager if needed
    if _manager is None or _manager.game_session.id != game_session.id:
        if _manager:
            # Cleanup old manager (fire and forget)
            asyncio.create_task(_manager.shutdown())

        _manager = WorldServerManager(
            db=db,
            game_session=game_session,
            enabled=enabled,
        )

    return _manager


async def shutdown_world_server() -> None:
    """Shutdown the World Server manager."""
    global _manager
    if _manager:
        await _manager.shutdown()
        _manager = None
