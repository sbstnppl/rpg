"""End-to-end tests for complete game flows."""

import os
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from typer.testing import CliRunner

from src.cli.main import app
from src.database.models.base import Base
from src.database.models.entities import Entity, EntityAttribute
from src.database.models.enums import EntityType
from src.database.models.items import Item
from src.database.models.session import GameSession
from src.database.models.world import TimeState


runner = CliRunner()


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary SQLite database for E2E tests."""
    db_path = tmp_path / "test_e2e.db"
    db_url = f"sqlite:///{db_path}"

    engine = create_engine(db_url)

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)

    yield db_url, engine

    engine.dispose()


class TestGameFlowE2E:
    """End-to-end tests for complete game flows."""

    def test_session_start_to_character_create(self, temp_db):
        """Full flow: session start → character create → verify in DB."""
        db_url, engine = temp_db

        with patch.dict(os.environ, {"DATABASE_URL": db_url}):
            # Step 1: Create a session
            result = runner.invoke(app, ["session", "start", "--name", "E2E Test"])
            assert result.exit_code == 0
            assert "Created session" in result.output

            # Step 2: Create a character (mocked interactive prompts)
            with patch("src.cli.commands.character.prompt_character_name") as mock_name:
                with patch("src.cli.commands.character.prompt_background") as mock_bg:
                    with patch("src.cli.display.Console.input") as mock_input:
                        mock_name.return_value = "E2E Hero"
                        mock_bg.return_value = "A test character"
                        mock_input.return_value = "y"

                        result = runner.invoke(app, ["character", "create", "--random"])

            assert result.exit_code == 0

        # Step 3: Verify in database
        Session = sessionmaker(bind=engine)
        with Session() as db:
            game_session = db.query(GameSession).first()
            assert game_session is not None
            assert game_session.session_name == "E2E Test"

            player = db.query(Entity).filter(
                Entity.session_id == game_session.id,
                Entity.entity_type == EntityType.PLAYER,
            ).first()
            assert player is not None
            assert player.display_name == "E2E Hero"

    def test_character_create_with_equipment(self, temp_db):
        """Verify starting equipment is created and equipped."""
        db_url, engine = temp_db

        with patch.dict(os.environ, {"DATABASE_URL": db_url}):
            # Create session and character
            runner.invoke(app, ["session", "start"])

            with patch("src.cli.commands.character.prompt_character_name") as mock_name:
                with patch("src.cli.commands.character.prompt_background") as mock_bg:
                    with patch("src.cli.display.Console.input") as mock_input:
                        mock_name.return_value = "Equipped Hero"
                        mock_bg.return_value = "Test"
                        mock_input.return_value = "y"

                        runner.invoke(app, ["character", "create", "--random"])

        # Verify equipment was created
        Session = sessionmaker(bind=engine)
        with Session() as db:
            player = db.query(Entity).filter(
                Entity.entity_type == EntityType.PLAYER
            ).first()
            assert player is not None

            # Check items were created
            items = db.query(Item).filter(
                Item.owner_id == player.id
            ).all()
            assert len(items) > 0, "Should have starting equipment"

            # Check some items are equipped
            equipped = [i for i in items if i.body_slot is not None]
            assert len(equipped) > 0, "Should have equipped items"

    def test_full_character_status_flow(self, temp_db):
        """Verify character status shows all created data."""
        db_url, engine = temp_db

        with patch.dict(os.environ, {"DATABASE_URL": db_url}):
            # Setup
            runner.invoke(app, ["session", "start"])

            with patch("src.cli.commands.character.prompt_character_name") as mock_name:
                with patch("src.cli.commands.character.prompt_background") as mock_bg:
                    with patch("src.cli.display.Console.input") as mock_input:
                        mock_name.return_value = "Status Hero"
                        mock_bg.return_value = "Test background"
                        mock_input.return_value = "y"

                        runner.invoke(app, ["character", "create", "--random"])

            # Check status
            result = runner.invoke(app, ["character", "status"])

        assert result.exit_code == 0
        assert "Status Hero" in result.output


class TestDatabaseIntegrity:
    """Tests for database integrity and constraints."""

    def test_session_delete_cascades_all_data(self, temp_db):
        """Deleting session should cascade to all related data."""
        db_url, engine = temp_db

        with patch.dict(os.environ, {"DATABASE_URL": db_url}):
            # Create session with character
            runner.invoke(app, ["session", "start"])

            with patch("src.cli.commands.character.prompt_character_name") as mock_name:
                with patch("src.cli.commands.character.prompt_background") as mock_bg:
                    with patch("src.cli.display.Console.input") as mock_input:
                        mock_name.return_value = "Delete Test"
                        mock_bg.return_value = "Test"
                        mock_input.return_value = "y"

                        runner.invoke(app, ["character", "create", "--random"])

        # Verify data exists
        Session = sessionmaker(bind=engine)
        with Session() as db:
            session = db.query(GameSession).first()
            session_id = session.id

            # Verify related data exists
            time_state = db.query(TimeState).filter(
                TimeState.session_id == session_id
            ).first()
            assert time_state is not None

            player = db.query(Entity).filter(
                Entity.session_id == session_id
            ).first()
            assert player is not None

            items = db.query(Item).filter(
                Item.session_id == session_id
            ).all()
            assert len(items) > 0

        # Delete session
        with patch.dict(os.environ, {"DATABASE_URL": db_url}):
            runner.invoke(app, ["session", "delete", str(session_id), "--force"])

        # Verify cascade
        with Session() as db:
            # Session gone
            session = db.query(GameSession).filter(
                GameSession.id == session_id
            ).first()
            assert session is None

            # TimeState gone
            time_state = db.query(TimeState).filter(
                TimeState.session_id == session_id
            ).first()
            assert time_state is None

            # Entities gone
            entities = db.query(Entity).filter(
                Entity.session_id == session_id
            ).all()
            assert len(entities) == 0

            # Items gone
            items = db.query(Item).filter(
                Item.session_id == session_id
            ).all()
            assert len(items) == 0

    def test_duplicate_entity_key_prevented(self, temp_db):
        """Should prevent duplicate entity keys in same session."""
        db_url, engine = temp_db

        Session = sessionmaker(bind=engine)
        with Session() as db:
            # Create session
            game_session = GameSession(
                session_name="Duplicate Test",
                setting="fantasy",
                status="active",
            )
            db.add(game_session)
            db.flush()

            # Create first entity
            entity1 = Entity(
                session_id=game_session.id,
                entity_key="unique_key",
                display_name="First Entity",
                entity_type=EntityType.NPC,
            )
            db.add(entity1)
            db.flush()

            # Try to create duplicate
            entity2 = Entity(
                session_id=game_session.id,
                entity_key="unique_key",  # Same key
                display_name="Second Entity",
                entity_type=EntityType.NPC,
            )
            db.add(entity2)

            # Should raise integrity error
            with pytest.raises(Exception):  # IntegrityError
                db.flush()

    def test_orphaned_records_not_created(self, temp_db):
        """Should not be able to create records without valid foreign keys."""
        db_url, engine = temp_db

        Session = sessionmaker(bind=engine)
        with Session() as db:
            # Try to create TimeState for non-existent session
            time_state = TimeState(
                session_id=99999,  # Doesn't exist
                current_day=1,
                current_time="09:00",
            )
            db.add(time_state)

            # Should fail due to FK constraint
            with pytest.raises(Exception):
                db.flush()


class TestMultiSessionIsolation:
    """Tests for session isolation."""

    def test_sessions_are_isolated(self, temp_db):
        """Entities in one session should not appear in another."""
        db_url, engine = temp_db

        with patch.dict(os.environ, {"DATABASE_URL": db_url}):
            # Create first session with character
            runner.invoke(app, ["session", "start", "--name", "Session 1"])

            with patch("src.cli.commands.character.prompt_character_name") as mock_name:
                with patch("src.cli.commands.character.prompt_background") as mock_bg:
                    with patch("src.cli.display.Console.input") as mock_input:
                        mock_name.return_value = "Hero 1"
                        mock_bg.return_value = "Test"
                        mock_input.return_value = "y"

                        runner.invoke(app, ["character", "create", "--random"])

            # Create second session
            runner.invoke(app, ["session", "start", "--name", "Session 2"])

        # Verify isolation
        Session = sessionmaker(bind=engine)
        with Session() as db:
            sessions = db.query(GameSession).order_by(GameSession.id).all()
            assert len(sessions) == 2

            session1_id = sessions[0].id
            session2_id = sessions[1].id

            # Session 1 should have a player
            player1 = db.query(Entity).filter(
                Entity.session_id == session1_id,
                Entity.entity_type == EntityType.PLAYER,
            ).first()
            assert player1 is not None
            assert player1.display_name == "Hero 1"

            # Session 2 should NOT have a player
            player2 = db.query(Entity).filter(
                Entity.session_id == session2_id,
                Entity.entity_type == EntityType.PLAYER,
            ).first()
            assert player2 is None
