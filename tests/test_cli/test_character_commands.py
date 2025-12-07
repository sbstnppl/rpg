"""Tests for character CLI commands."""

import os
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from typer.testing import CliRunner

from src.cli.main import app
from src.database.models.base import Base
from src.database.models.entities import Entity, EntityAttribute
from src.database.models.enums import EntityType, ItemType
from src.database.models.items import Item
from src.database.models.session import GameSession
from src.database.models.world import TimeState


runner = CliRunner()


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary SQLite database for CLI tests."""
    db_path = tmp_path / "test_cli.db"
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


@pytest.fixture
def session_with_player(temp_db):
    """Create a session with a player character."""
    db_url, engine = temp_db

    Session = sessionmaker(bind=engine)
    with Session() as db:
        # Create session
        game_session = GameSession(
            session_name="Test Session",
            setting="fantasy",
            status="active",
            total_turns=0,
        )
        db.add(game_session)
        db.flush()

        # Create time state
        time_state = TimeState(
            session_id=game_session.id,
            current_day=1,
            current_time="09:00",
        )
        db.add(time_state)

        # Create player
        player = Entity(
            session_id=game_session.id,
            entity_key="test_player",
            display_name="Test Hero",
            entity_type=EntityType.PLAYER,
            is_alive=True,
            is_active=True,
        )
        db.add(player)
        db.flush()

        # Create some attributes
        for attr_key, value in [
            ("strength", 15),
            ("dexterity", 14),
            ("constitution", 13),
        ]:
            attr = EntityAttribute(
                entity_id=player.id,
                attribute_key=attr_key,
                value=value,
            )
            db.add(attr)

        # Create some items
        sword = Item(
            session_id=game_session.id,
            item_key="test_sword",
            display_name="Steel Sword",
            item_type=ItemType.WEAPON,
            owner_id=player.id,
            holder_id=player.id,
            body_slot="right_hand",
        )
        db.add(sword)

        tunic = Item(
            session_id=game_session.id,
            item_key="test_tunic",
            display_name="Cloth Tunic",
            item_type=ItemType.CLOTHING,
            owner_id=player.id,
            holder_id=player.id,
            body_slot="torso",
        )
        db.add(tunic)

        db.commit()

        session_id = game_session.id
        player_id = player.id

    return db_url, engine, session_id, player_id


class TestCharacterStatus:
    """Tests for 'rpg character status' command."""

    def test_shows_player_name(self, session_with_player):
        """Should display player character name."""
        db_url, engine, session_id, player_id = session_with_player

        with patch.dict(os.environ, {"DATABASE_URL": db_url}):
            result = runner.invoke(
                app, ["character", "status", "--session", str(session_id)]
            )

        assert result.exit_code == 0
        assert "Test Hero" in result.output

    def test_requires_existing_session(self, temp_db):
        """Should error when no session exists."""
        db_url, engine = temp_db

        with patch.dict(os.environ, {"DATABASE_URL": db_url}):
            result = runner.invoke(app, ["character", "status"])

        assert result.exit_code == 1
        assert "No active session" in result.output or "not found" in result.output.lower()

    def test_requires_existing_character(self, temp_db):
        """Should error when session has no player."""
        db_url, engine = temp_db

        # Create session without player
        Session = sessionmaker(bind=engine)
        with Session() as db:
            game_session = GameSession(
                session_name="Empty Session",
                setting="fantasy",
                status="active",
            )
            db.add(game_session)
            db.commit()
            session_id = game_session.id

        with patch.dict(os.environ, {"DATABASE_URL": db_url}):
            result = runner.invoke(
                app, ["character", "status", "--session", str(session_id)]
            )

        assert result.exit_code == 1
        assert "No player" in result.output or "not found" in result.output.lower()


class TestCharacterInventory:
    """Tests for 'rpg character inventory' command."""

    def test_shows_owned_items(self, session_with_player):
        """Should display items owned by player."""
        db_url, engine, session_id, player_id = session_with_player

        with patch.dict(os.environ, {"DATABASE_URL": db_url}):
            result = runner.invoke(
                app, ["character", "inventory", "--session", str(session_id)]
            )

        assert result.exit_code == 0
        assert "Steel Sword" in result.output
        assert "Cloth Tunic" in result.output

    def test_shows_item_types(self, session_with_player):
        """Should show item type information."""
        db_url, engine, session_id, player_id = session_with_player

        with patch.dict(os.environ, {"DATABASE_URL": db_url}):
            result = runner.invoke(
                app, ["character", "inventory", "--session", str(session_id)]
            )

        assert result.exit_code == 0
        # Should show item types in output
        assert "weapon" in result.output.lower() or "clothing" in result.output.lower()


class TestCharacterEquipment:
    """Tests for 'rpg character equipment' command."""

    def test_shows_equipped_items(self, session_with_player):
        """Should display equipped items with slots."""
        db_url, engine, session_id, player_id = session_with_player

        with patch.dict(os.environ, {"DATABASE_URL": db_url}):
            result = runner.invoke(
                app, ["character", "equipment", "--session", str(session_id)]
            )

        assert result.exit_code == 0
        assert "Steel Sword" in result.output
        assert "Cloth Tunic" in result.output


class TestCharacterCreate:
    """Tests for 'rpg character create' command."""

    def test_requires_active_session(self, temp_db):
        """Should require an active session to create character."""
        db_url, engine = temp_db

        with patch.dict(os.environ, {"DATABASE_URL": db_url}):
            result = runner.invoke(app, ["character", "create"])

        assert result.exit_code == 1
        assert "No active session" in result.output

    def test_prevents_duplicate_player(self, session_with_player):
        """Should prevent creating second player in same session."""
        db_url, engine, session_id, player_id = session_with_player

        with patch.dict(os.environ, {"DATABASE_URL": db_url}):
            result = runner.invoke(
                app, ["character", "create", "--session", str(session_id)]
            )

        assert result.exit_code == 1
        assert "already has" in result.output.lower() or "Test Hero" in result.output


class TestCharacterCreateRandom:
    """Tests for 'rpg character create --random' command."""

    def test_random_creates_player(self, temp_db):
        """Random creation should create a player entity."""
        db_url, engine = temp_db

        # First create a session
        with patch.dict(os.environ, {"DATABASE_URL": db_url}):
            runner.invoke(app, ["session", "start"])

        # Now create character with random stats
        # We need to mock the interactive input
        with patch.dict(os.environ, {"DATABASE_URL": db_url}):
            # Mock the prompts
            with patch("src.cli.commands.character.prompt_character_name") as mock_name:
                with patch("src.cli.commands.character.prompt_background") as mock_bg:
                    with patch("src.cli.display.Console.input") as mock_input:
                        mock_name.return_value = "Random Hero"
                        mock_bg.return_value = "A randomly rolled adventurer"
                        mock_input.return_value = "y"  # Accept the stats

                        result = runner.invoke(
                            app, ["character", "create", "--random"]
                        )

        # Should succeed
        assert result.exit_code == 0
        assert "Random Hero" in result.output or "created" in result.output.lower()

        # Verify in database
        Session = sessionmaker(bind=engine)
        with Session() as db:
            player = db.query(Entity).filter(
                Entity.entity_type == EntityType.PLAYER
            ).first()
            assert player is not None
            assert player.display_name == "Random Hero"


class TestCharacterCreateAI:
    """Tests for 'rpg character create --ai' command."""

    def test_ai_flag_triggers_async_creation(self, temp_db):
        """--ai flag should call the async AI creation function."""
        db_url, engine = temp_db

        # Create a session first
        with patch.dict(os.environ, {"DATABASE_URL": db_url}):
            runner.invoke(app, ["session", "start"])

        # Mock the AI creation function and world extraction
        with patch.dict(os.environ, {"DATABASE_URL": db_url}):
            with patch(
                "src.cli.commands.character._ai_character_creation"
            ) as mock_ai:
                with patch(
                    "src.cli.commands.character._extract_world_data"
                ) as mock_extract:
                    mock_ai.return_value = (
                        "AI Hero",
                        {"strength": 15, "dexterity": 14, "constitution": 13,
                         "intelligence": 12, "wisdom": 10, "charisma": 8},
                        "Created by AI",
                        "AI: Hello! User: Create me a character",
                    )
                    # Return None to skip world extraction
                    mock_extract.return_value = None

                    result = runner.invoke(app, ["character", "create", "--ai"])

        # Should call the AI function
        mock_ai.assert_called_once()

        # Should succeed
        assert result.exit_code == 0
        assert "AI Hero" in result.output or "created" in result.output.lower()

    def test_ai_creation_handles_llm_error(self, temp_db):
        """Should handle LLM errors gracefully."""
        db_url, engine = temp_db

        with patch.dict(os.environ, {"DATABASE_URL": db_url}):
            runner.invoke(app, ["session", "start"])

        with patch.dict(os.environ, {"DATABASE_URL": db_url}):
            with patch(
                "src.cli.commands.character._ai_character_creation"
            ) as mock_ai:
                # Simulate LLM error by raising SystemExit (from typer.Exit)
                import typer
                mock_ai.side_effect = typer.Exit(1)

                result = runner.invoke(app, ["character", "create", "--ai"])

        # Should exit with error
        assert result.exit_code == 1
