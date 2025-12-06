"""Tests for BaseManager class."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.session import GameSession
from src.managers.base import BaseManager


class TestBaseManager:
    """Tests for BaseManager class."""

    def test_init_stores_db_and_session(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify BaseManager stores db session and game session."""
        manager = BaseManager(db_session, game_session)

        assert manager.db is db_session
        assert manager.game_session is game_session

    def test_session_id_property(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify session_id property returns game session ID."""
        manager = BaseManager(db_session, game_session)

        assert manager.session_id == game_session.id

    def test_current_turn_property(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify current_turn property returns total_turns from session."""
        game_session.total_turns = 42
        db_session.flush()

        manager = BaseManager(db_session, game_session)

        assert manager.current_turn == 42

    def test_clamp_within_range(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify _clamp returns value when within bounds."""
        manager = BaseManager(db_session, game_session)

        assert manager._clamp(50) == 50
        assert manager._clamp(0) == 0
        assert manager._clamp(100) == 100

    def test_clamp_below_minimum(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify _clamp clamps to minimum."""
        manager = BaseManager(db_session, game_session)

        assert manager._clamp(-10) == 0
        assert manager._clamp(-100) == 0

    def test_clamp_above_maximum(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify _clamp clamps to maximum."""
        manager = BaseManager(db_session, game_session)

        assert manager._clamp(110) == 100
        assert manager._clamp(200) == 100

    def test_clamp_custom_range(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify _clamp with custom min and max values."""
        manager = BaseManager(db_session, game_session)

        assert manager._clamp(50, min_val=10, max_val=90) == 50
        assert manager._clamp(5, min_val=10, max_val=90) == 10
        assert manager._clamp(95, min_val=10, max_val=90) == 90

    def test_clamp_float_conversion(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify _clamp converts float to int."""
        manager = BaseManager(db_session, game_session)

        assert manager._clamp(50.7) == 50
        assert manager._clamp(50.2) == 50
        assert isinstance(manager._clamp(50.5), int)
