"""State Collapse Manager for committing pre-generated scenes.

When a player observes a location (enters it, looks around), the "wave function
collapses" - pre-generated content becomes committed to the database.
"""

import logging
import time
from datetime import datetime

from sqlalchemy.orm import Session

from src.database.models.session import GameSession
from src.database.models.world import Location
from src.world_server.cache import PreGenerationCache
from src.world_server.schemas import (
    AnticipationMetrics,
    CollapseResult,
    PreGeneratedScene,
)

logger = logging.getLogger(__name__)


class StateCollapseManager:
    """Commits pre-generated state when player observes a location.

    This handles the "wave function collapse" - when the player enters a location,
    we check if it was pre-generated. If so, we commit that state to the database.
    If not, we fall back to synchronous generation.
    """

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        cache: PreGenerationCache,
        metrics: AnticipationMetrics | None = None,
    ):
        """Initialize the collapse manager.

        Args:
            db: Database session
            game_session: Current game session
            cache: Pre-generation cache to check for pre-generated scenes
            metrics: Shared metrics object
        """
        self.db = db
        self.game_session = game_session
        self.session_id = game_session.id
        self._cache = cache
        self._metrics = metrics or cache.metrics

    async def collapse_location(
        self,
        location_key: str,
        turn_number: int,
    ) -> CollapseResult:
        """Collapse state for a location when player observes it.

        This is the main entry point called when the player enters a location.
        It checks for pre-generated content and either:
        1. Uses pre-generated content (instant)
        2. Falls back to synchronous generation (slow)

        Args:
            location_key: Location the player is observing
            turn_number: Current turn number (for tracking)

        Returns:
            CollapseResult with narrator manifest and timing info
        """
        start_time = time.perf_counter()

        # Check cache for pre-generated scene
        pre_gen = await self._cache.get(location_key)

        if pre_gen and not pre_gen.is_stale():
            # Cache hit - use pre-generated content
            result = await self._commit_pre_generated(pre_gen, turn_number)
            latency_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                f"Collapse cache HIT for {location_key}, "
                f"age={pre_gen.age_seconds():.1f}s, "
                f"latency={latency_ms:.1f}ms"
            )

            return CollapseResult(
                location_key=location_key,
                narrator_manifest=result,
                was_pre_generated=True,
                latency_ms=latency_ms,
                cache_age_seconds=pre_gen.age_seconds(),
                prediction_reason=pre_gen.prediction_reason,
            )
        else:
            # Cache miss - fall back to synchronous generation
            self._metrics.record_cache_miss()

            logger.info(f"Collapse cache MISS for {location_key}, generating sync")

            gen_start = time.perf_counter()
            result = await self._generate_synchronous(location_key, turn_number)
            gen_time_ms = (time.perf_counter() - gen_start) * 1000
            latency_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                f"Collapse sync generation for {location_key}, "
                f"gen_time={gen_time_ms:.0f}ms, "
                f"total_latency={latency_ms:.0f}ms"
            )

            return CollapseResult(
                location_key=location_key,
                narrator_manifest=result,
                was_pre_generated=False,
                latency_ms=latency_ms,
                generation_time_ms=gen_time_ms,
            )

    async def _commit_pre_generated(
        self,
        pre_gen: PreGeneratedScene,
        turn_number: int,
    ) -> dict:
        """Commit pre-generated scene to database.

        This persists the pre-generated entities (NPCs, items, furniture)
        to the database, marking the scene as observed.

        Args:
            pre_gen: Pre-generated scene to commit
            turn_number: Current turn number

        Returns:
            NarratorManifest dict for the narrator
        """
        # Mark as committed to prevent re-use
        pre_gen.is_committed = True

        # Update location visit tracking
        location = (
            self.db.query(Location)
            .filter(
                Location.session_id == self.session_id,
                Location.location_key == pre_gen.location_key,
            )
            .first()
        )

        if location:
            if location.first_visited_turn is None:
                location.first_visited_turn = turn_number
            location.last_visited_turn = turn_number
            self.db.flush()

        # Build NarratorManifest from pre-generated data
        # The scene_manifest already contains the full SceneManifest
        narrator_manifest = self._build_narrator_manifest(pre_gen)

        # Invalidate this entry from cache (it's been used)
        await self._cache.invalidate(pre_gen.location_key)

        return narrator_manifest

    async def _generate_synchronous(
        self,
        location_key: str,
        turn_number: int,
    ) -> dict:
        """Generate scene synchronously (fallback when cache miss).

        This is the slow path - called when the player goes somewhere
        we didn't predict.

        Args:
            location_key: Location to generate
            turn_number: Current turn number

        Returns:
            NarratorManifest dict for the narrator
        """
        from src.world.world_mechanics import WorldMechanics
        from src.world.scene_builder import SceneBuilder
        from src.world.schemas import WorldUpdate, ObservationLevel

        # Get NPCs at location
        world_mechanics = WorldMechanics(self.db, self.game_session)
        npcs_at_location = world_mechanics.get_npcs_at_location(location_key)

        # Create WorldUpdate
        world_update = WorldUpdate(npcs_at_location=npcs_at_location)

        # Build scene
        scene_builder = SceneBuilder(self.db, self.game_session)
        scene_manifest = await scene_builder.build_scene(
            location_key=location_key,
            world_update=world_update,
            observation_level=ObservationLevel.ENTRY,
        )

        # Update location visit tracking
        location = (
            self.db.query(Location)
            .filter(
                Location.session_id == self.session_id,
                Location.location_key == location_key,
            )
            .first()
        )

        if location:
            if location.first_visited_turn is None:
                location.first_visited_turn = turn_number
            location.last_visited_turn = turn_number
            self.db.flush()

        # Build NarratorManifest
        return self._scene_manifest_to_narrator_manifest(scene_manifest, location_key)

    def _build_narrator_manifest(self, pre_gen: PreGeneratedScene) -> dict:
        """Build NarratorManifest from pre-generated scene.

        The NarratorManifest tells the narrator what entities it can
        reference in its prose.

        Args:
            pre_gen: Pre-generated scene

        Returns:
            NarratorManifest dict
        """
        return {
            "location_key": pre_gen.location_key,
            "location_display_name": pre_gen.location_display_name,
            "npcs": pre_gen.npcs_present,
            "items": pre_gen.items_present,
            "furniture": pre_gen.furniture,
            "atmosphere": pre_gen.atmosphere,
            "scene_manifest": pre_gen.scene_manifest,
            "was_pre_generated": True,
            "pre_generation_age_seconds": pre_gen.age_seconds(),
        }

    def _scene_manifest_to_narrator_manifest(
        self,
        scene_manifest,
        location_key: str,
    ) -> dict:
        """Convert SceneManifest to NarratorManifest dict.

        Args:
            scene_manifest: SceneManifest from SceneBuilder
            location_key: Location key

        Returns:
            NarratorManifest dict
        """
        # Get location for display name
        location = (
            self.db.query(Location)
            .filter(
                Location.session_id == self.session_id,
                Location.location_key == location_key,
            )
            .first()
        )

        display_name = location.display_name if location else location_key

        # Extract NPCs
        npcs = []
        if hasattr(scene_manifest, 'npcs') and scene_manifest.npcs:
            npcs = [npc.model_dump() for npc in scene_manifest.npcs]

        # Extract items
        items = []
        if hasattr(scene_manifest, 'items') and scene_manifest.items:
            items = [item.model_dump() for item in scene_manifest.items]

        # Extract furniture
        furniture = []
        if hasattr(scene_manifest, 'furniture') and scene_manifest.furniture:
            furniture = [f.model_dump() for f in scene_manifest.furniture]

        # Extract atmosphere
        atmosphere = {}
        if hasattr(scene_manifest, 'atmosphere') and scene_manifest.atmosphere:
            atmosphere = scene_manifest.atmosphere.model_dump()

        return {
            "location_key": location_key,
            "location_display_name": display_name,
            "npcs": npcs,
            "items": items,
            "furniture": furniture,
            "atmosphere": atmosphere,
            "scene_manifest": scene_manifest.model_dump(),
            "was_pre_generated": False,
        }

    async def check_and_collapse(
        self,
        location_key: str,
        turn_number: int,
    ) -> tuple[dict, bool]:
        """Check for pre-generated scene and collapse if available.

        Convenience method that returns both the manifest and whether
        it was pre-generated.

        Args:
            location_key: Location to check/collapse
            turn_number: Current turn number

        Returns:
            Tuple of (narrator_manifest, was_pre_generated)
        """
        result = await self.collapse_location(location_key, turn_number)
        return result.narrator_manifest, result.was_pre_generated

    def get_cache_status(self, location_key: str) -> dict:
        """Get cache status for a location (synchronous check).

        Args:
            location_key: Location to check

        Returns:
            Dict with cache status info
        """
        # Note: This is a sync method for quick checks
        # For full async check, use cache.contains() or cache.get()
        return {
            "location_key": location_key,
            "cache_max_size": self._cache.max_size,
            "metrics": self._metrics.to_dict(),
        }
