"""Tests for session CLI commands."""

from contextlib import contextmanager
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from typer.testing import CliRunner

from src.cli.main import app
from src.database.models.base import Base
from src.database.models.session import GameSession
from src.database.models.world import TimeState


runner = CliRunner()


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary SQLite database for CLI tests."""
    db_path = tmp_path / "test_cli.db"
    db_url = f"sqlite:///{db_path}"

    engine = create_engine(db_url)

    # Enable foreign keys for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)

    # Create a session factory for this test database
    TestSessionLocal = sessionmaker(bind=engine)

    @contextmanager
    def mock_get_db_session():
        """Mock get_db_session that uses the test database."""
        session = TestSessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    yield engine, mock_get_db_session

    engine.dispose()


class TestSessionStart:
    """Tests for 'rpg session start' command."""

    def test_creates_session_with_defaults(self, temp_db):
        """Should create session with default name and setting."""
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.session.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["session", "start"])

        assert result.exit_code == 0
        assert "Created session" in result.output
        assert "New Adventure" in result.output

        # Verify in database
        Session = sessionmaker(bind=engine)
        with Session() as db:
            session = db.query(GameSession).first()
            assert session is not None
            assert session.session_name == "New Adventure"
            assert session.setting == "fantasy"
            assert session.status == "active"

    def test_creates_session_with_custom_name(self, temp_db):
        """Should create session with custom name."""
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.session.get_db_session", mock_get_db_session):
            result = runner.invoke(
                app, ["session", "start", "--name", "My Epic Quest"]
            )

        assert result.exit_code == 0
        assert "My Epic Quest" in result.output

        Session = sessionmaker(bind=engine)
        with Session() as db:
            session = db.query(GameSession).first()
            assert session.session_name == "My Epic Quest"

    def test_creates_session_with_custom_setting(self, temp_db):
        """Should create session with custom setting."""
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.session.get_db_session", mock_get_db_session):
            result = runner.invoke(
                app, ["session", "start", "--setting", "scifi"]
            )

        assert result.exit_code == 0
        assert "scifi" in result.output

        Session = sessionmaker(bind=engine)
        with Session() as db:
            session = db.query(GameSession).first()
            assert session.setting == "scifi"

    def test_creates_time_state_for_session(self, temp_db):
        """Should create TimeState record for new session."""
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.session.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["session", "start"])

        assert result.exit_code == 0

        Session = sessionmaker(bind=engine)
        with Session() as db:
            session = db.query(GameSession).first()
            time_state = (
                db.query(TimeState)
                .filter(TimeState.session_id == session.id)
                .first()
            )
            assert time_state is not None
            assert time_state.current_day == 1
            assert time_state.current_time == "09:00"

    def test_foreign_keys_enforced(self, temp_db):
        """Should enforce foreign key constraints in SQLite."""
        engine, mock_get_db_session = temp_db

        # Try to insert orphan time_state - should fail
        Session = sessionmaker(bind=engine)
        with Session() as db:
            # Enable FK pragma to verify it's working
            result = db.execute(text("PRAGMA foreign_keys"))
            fk_enabled = result.scalar()
            assert fk_enabled == 1, "Foreign keys should be enabled"


class TestSessionList:
    """Tests for 'rpg session list' command."""

    def test_lists_all_sessions(self, temp_db):
        """Should list all sessions."""
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.session.get_db_session", mock_get_db_session):
            # Create some sessions
            runner.invoke(app, ["session", "start", "--name", "Session 1"])
            runner.invoke(app, ["session", "start", "--name", "Session 2"])

            result = runner.invoke(app, ["session", "list"])

        assert result.exit_code == 0
        assert "Session 1" in result.output
        assert "Session 2" in result.output

    def test_shows_empty_message_when_no_sessions(self, temp_db):
        """Should handle empty session list gracefully."""
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.session.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["session", "list"])

        assert result.exit_code == 0


class TestSessionDelete:
    """Tests for 'rpg session delete' command."""

    def test_deletes_session(self, temp_db):
        """Should delete session by ID."""
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.session.get_db_session", mock_get_db_session):
            # Create a session
            runner.invoke(app, ["session", "start", "--name", "To Delete"])

            # Get the session ID
            Session = sessionmaker(bind=engine)
            with Session() as db:
                session = db.query(GameSession).first()
                session_id = session.id

            # Delete with force flag (skip confirmation)
            result = runner.invoke(
                app, ["session", "delete", str(session_id), "--force"]
            )

        assert result.exit_code == 0
        assert "Deleted" in result.output

        # Verify deleted
        with Session() as db:
            session = db.query(GameSession).filter(
                GameSession.id == session_id
            ).first()
            assert session is None

    def test_cascades_to_time_states(self, temp_db):
        """Deleting session should cascade to time_states."""
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.session.get_db_session", mock_get_db_session):
            # Create a session (which creates time_state)
            runner.invoke(app, ["session", "start"])

            Session = sessionmaker(bind=engine)
            with Session() as db:
                session = db.query(GameSession).first()
                session_id = session.id

                # Verify time_state exists
                time_state = db.query(TimeState).filter(
                    TimeState.session_id == session_id
                ).first()
                assert time_state is not None

            # Delete session
            runner.invoke(
                app, ["session", "delete", str(session_id), "--force"]
            )

            # Verify time_state also deleted (cascade)
            with Session() as db:
                time_state = db.query(TimeState).filter(
                    TimeState.session_id == session_id
                ).first()
                assert time_state is None

    def test_handles_nonexistent_session(self, temp_db):
        """Should handle attempt to delete non-existent session."""
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.session.get_db_session", mock_get_db_session):
            result = runner.invoke(
                app, ["session", "delete", "9999", "--force"]
            )

        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestSessionLoad:
    """Tests for 'rpg session load' command."""

    def test_loads_session_info(self, temp_db):
        """Should display session information."""
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.session.get_db_session", mock_get_db_session):
            runner.invoke(app, ["session", "start", "--name", "Test Session"])

            Session = sessionmaker(bind=engine)
            with Session() as db:
                session = db.query(GameSession).first()
                session_id = session.id

            result = runner.invoke(app, ["session", "load", str(session_id)])

        assert result.exit_code == 0
        assert "Test Session" in result.output

    def test_handles_nonexistent_session(self, temp_db):
        """Should handle loading non-existent session."""
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.session.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["session", "load", "9999"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()
