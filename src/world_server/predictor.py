"""Location prediction for anticipatory generation.

Predicts which locations the player is most likely to visit next,
allowing the anticipation engine to pre-generate those scenes.
"""

import logging
import re
from sqlalchemy.orm import Session

from src.database.models.session import GameSession
from src.database.models.world import Location
from src.database.models.tasks import Task
from src.database.models.enums import EntityType
from src.world_server.schemas import LocationPrediction, PredictionReason

logger = logging.getLogger(__name__)


class LocationPredictor:
    """Predicts likely next player destinations.

    Uses multiple signals to predict where the player will go:
    1. Adjacent locations (from spatial_layout exits)
    2. Quest/task target locations
    3. Locations mentioned in recent dialogue
    4. Player's home location
    5. Frequently visited locations
    """

    # Base probabilities for different prediction reasons
    BASE_PROBABILITIES = {
        PredictionReason.ADJACENT: 0.7,
        PredictionReason.QUEST_TARGET: 0.5,
        PredictionReason.MENTIONED: 0.3,
        PredictionReason.HOME: 0.2,
        PredictionReason.FREQUENT: 0.2,
        PredictionReason.NPC_LOCATION: 0.3,
    }

    # Boost when multiple reasons apply
    PROBABILITY_BOOST = 0.15

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
    ):
        """Initialize the predictor.

        Args:
            db: Database session
            game_session: Current game session
        """
        self.db = db
        self.game_session = game_session
        self.session_id = game_session.id

    def predict_next_locations(
        self,
        current_location: str,
        recent_actions: list[str] | None = None,
        max_predictions: int = 3,
    ) -> list[LocationPrediction]:
        """Predict most likely next locations.

        Args:
            current_location: Current player location key
            recent_actions: Recent player input/dialogue for context
            max_predictions: Maximum number of predictions to return

        Returns:
            List of LocationPrediction sorted by probability (descending)
        """
        predictions: dict[str, LocationPrediction] = {}

        # 1. Adjacent locations (highest base probability)
        adjacent = self._get_adjacent_locations(current_location)
        for loc_key in adjacent:
            self._add_or_boost_prediction(
                predictions,
                loc_key,
                PredictionReason.ADJACENT,
                f"exit from {current_location}",
            )

        # 2. Quest/task target locations
        quest_locations = self._get_quest_target_locations()
        for loc_key, task_title in quest_locations:
            self._add_or_boost_prediction(
                predictions,
                loc_key,
                PredictionReason.QUEST_TARGET,
                f"quest: {task_title}",
            )

        # 3. Mentioned locations from recent actions
        if recent_actions:
            mentioned = self._extract_mentioned_locations(recent_actions)
            for loc_key in mentioned:
                self._add_or_boost_prediction(
                    predictions,
                    loc_key,
                    PredictionReason.MENTIONED,
                    "mentioned in dialogue",
                )

        # 4. Player home location
        home_key = self._get_player_home_location()
        if home_key and home_key != current_location:
            self._add_or_boost_prediction(
                predictions,
                home_key,
                PredictionReason.HOME,
                "player home",
            )

        # Sort by probability descending
        sorted_predictions = sorted(
            predictions.values(),
            key=lambda p: p.probability,
            reverse=True,
        )

        result = sorted_predictions[:max_predictions]

        logger.info(
            f"Predicted {len(result)} locations from {current_location}: "
            f"{[(p.location_key, f'{p.probability:.0%}') for p in result]}"
        )

        return result

    def _add_or_boost_prediction(
        self,
        predictions: dict[str, LocationPrediction],
        location_key: str,
        reason: PredictionReason,
        detail: str,
    ) -> None:
        """Add a prediction or boost existing one.

        Args:
            predictions: Dict of predictions by location key
            location_key: Location to add/boost
            reason: Reason for prediction
            detail: Detail string for logging
        """
        if location_key in predictions:
            # Boost existing prediction
            existing = predictions[location_key]
            new_prob = min(1.0, existing.probability + self.PROBABILITY_BOOST)
            predictions[location_key] = LocationPrediction(
                location_key=location_key,
                probability=new_prob,
                reason=existing.reason,  # Keep original reason
                reason_detail=f"{existing.reason_detail}; {detail}",
            )
        else:
            # Add new prediction
            base_prob = self.BASE_PROBABILITIES.get(reason, 0.3)
            predictions[location_key] = LocationPrediction(
                location_key=location_key,
                probability=base_prob,
                reason=reason,
                reason_detail=detail,
            )

    def _get_adjacent_locations(self, location_key: str) -> list[str]:
        """Get locations connected via spatial_layout exits.

        Args:
            location_key: Current location key

        Returns:
            List of adjacent location keys
        """
        location = (
            self.db.query(Location)
            .filter(
                Location.session_id == self.session_id,
                Location.location_key == location_key,
            )
            .first()
        )

        if location is None or location.spatial_layout is None:
            return []

        exits = location.spatial_layout.get("exits", [])

        # exits can be a list of keys or a dict mapping direction to key
        if isinstance(exits, dict):
            return list(exits.values())
        elif isinstance(exits, list):
            return exits
        else:
            return []

    def _get_quest_target_locations(self) -> list[tuple[str, str]]:
        """Get locations from active quest/task objectives.

        Returns:
            List of (location_key, task_title) tuples
        """
        active_tasks = (
            self.db.query(Task)
            .filter(
                Task.session_id == self.session_id,
                Task.completed == False,
                Task.location != None,
            )
            .all()
        )

        result = []
        for task in active_tasks:
            if task.location:
                result.append((task.location, task.description or "Unknown task"))

        return result

    def _extract_mentioned_locations(
        self,
        recent_actions: list[str],
    ) -> list[str]:
        """Extract location mentions from recent player actions.

        Simple keyword matching against known location names.

        Args:
            recent_actions: Recent player input strings

        Returns:
            List of mentioned location keys
        """
        # Get all known locations
        all_locations = (
            self.db.query(Location)
            .filter(Location.session_id == self.session_id)
            .all()
        )

        # Build lookup from display name to key
        location_names: dict[str, str] = {}
        for loc in all_locations:
            if loc.display_name:
                location_names[loc.display_name.lower()] = loc.location_key
            # Also add the key itself (might be mentioned directly)
            location_names[loc.location_key.lower()] = loc.location_key

        # Combine recent actions into searchable text
        text = " ".join(recent_actions).lower()

        # Find mentions
        mentioned = []
        for name, key in location_names.items():
            # Use word boundary matching to avoid partial matches
            pattern = r'\b' + re.escape(name) + r'\b'
            if re.search(pattern, text):
                if key not in mentioned:
                    mentioned.append(key)

        return mentioned

    def _get_player_home_location(self) -> str | None:
        """Get the player's home location if set.

        Returns:
            Home location key or None
        """
        # Check if player entity has a home_location
        from src.database.models.entities import Entity, NPCExtension

        player = (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.session_id,
                Entity.entity_type == EntityType.PLAYER,
            )
            .first()
        )

        if player is None:
            return None

        # Check NPCExtension for home_location
        extension = (
            self.db.query(NPCExtension)
            .filter(NPCExtension.entity_id == player.id)
            .first()
        )

        if extension and extension.home_location:
            return extension.home_location

        return None

    def get_prediction_stats(self) -> dict:
        """Get statistics about prediction capability.

        Returns:
            Dict with stats about available prediction signals
        """
        active_tasks_with_location = (
            self.db.query(Task)
            .filter(
                Task.session_id == self.session_id,
                Task.completed == False,
                Task.location != None,
            )
            .count()
        )

        total_locations = (
            self.db.query(Location)
            .filter(Location.session_id == self.session_id)
            .count()
        )

        return {
            "active_tasks_with_location": active_tasks_with_location,
            "total_locations": total_locations,
            "has_player_home": self._get_player_home_location() is not None,
        }
