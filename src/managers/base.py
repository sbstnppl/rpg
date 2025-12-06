"""Base manager class with common patterns."""

from typing import TypeVar

from sqlalchemy.orm import Session

from src.database.models.session import GameSession

T = TypeVar("T")


class BaseManager:
    """Base class for all game managers.

    Provides common patterns:
    - Database session access
    - Game session scoping (all queries filter by session_id)
    - Current turn tracking
    """

    def __init__(self, db: Session, game_session: GameSession) -> None:
        """Initialize manager with database session and game session.

        Args:
            db: SQLAlchemy database session
            game_session: Current game session for scoping queries
        """
        self.db = db
        self.game_session = game_session

    @property
    def session_id(self) -> int:
        """Get current session ID for query scoping."""
        return self.game_session.id

    @property
    def current_turn(self) -> int:
        """Get current turn number."""
        return self.game_session.total_turns

    def _clamp(self, value: int | float, min_val: int = 0, max_val: int = 100) -> int:
        """Clamp a value between min and max bounds."""
        return int(max(min_val, min(max_val, value)))
