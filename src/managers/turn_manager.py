"""Turn history manager for accessing and querying turn data."""

from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.database.models.session import GameSession, Turn
from src.managers.base import BaseManager


class TurnManager(BaseManager):
    """Manager for turn history queries.

    Provides methods for accessing turn data including:
    - Recent turns for context building
    - Mentioned items for deferred spawning
    - Turn snapshots for replay/debugging
    """

    def __init__(self, db: Session, game_session: GameSession) -> None:
        """Initialize turn manager.

        Args:
            db: SQLAlchemy database session
            game_session: Current game session for scoping queries
        """
        super().__init__(db, game_session)

    def get_recent_turns(self, count: int = 10) -> list[Turn]:
        """Get the most recent turns for the session.

        Args:
            count: Number of turns to retrieve

        Returns:
            List of Turn objects, newest first
        """
        return (
            self.db.query(Turn)
            .filter(Turn.session_id == self.session_id)
            .order_by(desc(Turn.turn_number))
            .limit(count)
            .all()
        )

    def get_mentioned_items_at_location(
        self,
        location_key: str,
        lookback_turns: int = 10,
    ) -> list[dict[str, Any]]:
        """Get decorative items mentioned in recent turns at a location.

        DEPRECATED: In scene-first architecture, all items are created upfront
        in the scene manifest. Deferred item tracking is not needed. This method
        is kept for system-authority pipeline backward compatibility.

        These are items that were mentioned in narrative but deferred for
        on-demand spawning (decorative items like pebbles, dust, etc.).

        When a player references one of these items, they can be spawned
        on-demand rather than cluttering the world with decorative entities.

        Args:
            location_key: The location key to filter by
            lookback_turns: How many recent turns to search

        Returns:
            List of dicts with keys: name, context, location, turn_number
        """
        recent_turns = (
            self.db.query(Turn)
            .filter(Turn.session_id == self.session_id)
            .order_by(desc(Turn.turn_number))
            .limit(lookback_turns)
            .all()
        )

        mentioned_items: list[dict[str, Any]] = []

        for turn in recent_turns:
            # Skip turns without mentioned items
            if not turn.mentioned_items:
                continue

            # Filter for items at the specified location
            for item in turn.mentioned_items:
                item_location = item.get("location", "")
                if item_location == location_key:
                    mentioned_items.append({
                        "name": item.get("name", ""),
                        "context": item.get("context", ""),
                        "location": item_location,
                        "turn_number": turn.turn_number,
                    })

        return mentioned_items

    def get_all_mentioned_items(
        self,
        lookback_turns: int = 10,
    ) -> list[dict[str, Any]]:
        """Get all decorative items mentioned in recent turns (any location).

        DEPRECATED: In scene-first architecture, all items are created upfront
        in the scene manifest. Deferred item tracking is not needed. This method
        is kept for system-authority pipeline backward compatibility.

        This is a fallback for when location-specific lookup fails. Useful
        for INFO responses that mention items at locations the player hasn't
        visited yet (e.g., "you usually wash at the well with a bucket").

        Args:
            lookback_turns: How many recent turns to search

        Returns:
            List of dicts with keys: name, context, location, turn_number
        """
        recent_turns = (
            self.db.query(Turn)
            .filter(Turn.session_id == self.session_id)
            .order_by(desc(Turn.turn_number))
            .limit(lookback_turns)
            .all()
        )

        mentioned_items: list[dict[str, Any]] = []

        for turn in recent_turns:
            if not turn.mentioned_items:
                continue

            for item in turn.mentioned_items:
                mentioned_items.append({
                    "name": item.get("name", ""),
                    "context": item.get("context", ""),
                    "location": item.get("location", ""),
                    "turn_number": turn.turn_number,
                })

        return mentioned_items

    def get_turn_by_number(self, turn_number: int) -> Turn | None:
        """Get a specific turn by number.

        Args:
            turn_number: The turn number to retrieve

        Returns:
            Turn object or None if not found
        """
        return (
            self.db.query(Turn)
            .filter(
                Turn.session_id == self.session_id,
                Turn.turn_number == turn_number,
            )
            .first()
        )

    def get_latest_turn(self) -> Turn | None:
        """Get the most recent turn for the session.

        Returns:
            Latest Turn object or None if no turns exist
        """
        return (
            self.db.query(Turn)
            .filter(Turn.session_id == self.session_id)
            .order_by(desc(Turn.turn_number))
            .first()
        )

    def save_mentioned_items(
        self,
        turn_number: int,
        items: list[dict[str, str]],
    ) -> bool:
        """Save mentioned items to a turn.

        DEPRECATED: In scene-first architecture, all items are created upfront
        in the scene manifest. Deferred item tracking is not needed. This method
        is kept for system-authority pipeline backward compatibility.

        Used by narrative validator to persist deferred items for later
        on-demand spawning.

        Args:
            turn_number: Turn number to update
            items: List of dicts with name, context, location

        Returns:
            True if successful, False if turn not found
        """
        turn = self.get_turn_by_number(turn_number)
        if not turn:
            return False

        # Merge with existing items if any
        # Must create new list to trigger SQLAlchemy dirty detection
        existing = list(turn.mentioned_items) if turn.mentioned_items else []
        existing.extend(items)
        turn.mentioned_items = existing

        self.db.flush()
        return True
