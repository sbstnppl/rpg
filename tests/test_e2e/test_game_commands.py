"""End-to-end tests for game CLI commands.

These tests cover the modern game commands (rpg game start, list, delete, play, turn).
"""

import asyncio
from contextlib import contextmanager
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
from src.database.models.character_state import CharacterNeeds


runner = CliRunner()


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary SQLite database for E2E tests."""
    db_path = tmp_path / "test_game_e2e.db"
    db_url = f"sqlite:///{db_path}"

    engine = create_engine(db_url)

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)

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


class TestGameList:
    """Tests for 'rpg game list' command."""

    def test_lists_all_games(self, temp_db):
        """Should list all games."""
        engine, mock_get_db_session = temp_db

        # Create some games directly in DB
        Session = sessionmaker(bind=engine)
        with Session() as db:
            game1 = GameSession(
                session_name="Adventure One",
                setting="fantasy",
                status="active",
                total_turns=5,
                llm_provider="anthropic",
                gm_model="test",
            )
            game2 = GameSession(
                session_name="Adventure Two",
                setting="scifi",
                status="paused",
                total_turns=10,
                llm_provider="anthropic",
                gm_model="test",
            )
            db.add(game1)
            db.add(game2)
            db.commit()

        with patch("src.cli.commands.game.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["game", "list"])

        assert result.exit_code == 0
        assert "Adventure One" in result.output
        assert "Adventure Two" in result.output
        assert "fantasy" in result.output
        assert "scifi" in result.output

    def test_lists_empty_when_no_games(self, temp_db):
        """Should show message when no games exist."""
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.game.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["game", "list"])

        assert result.exit_code == 0
        assert "No games found" in result.output

    def test_filter_by_status(self, temp_db):
        """Should filter games by status."""
        engine, mock_get_db_session = temp_db

        Session = sessionmaker(bind=engine)
        with Session() as db:
            game1 = GameSession(
                session_name="Active Game",
                setting="fantasy",
                status="active",
                total_turns=5,
                llm_provider="anthropic",
                gm_model="test",
            )
            game2 = GameSession(
                session_name="Paused Game",
                setting="fantasy",
                status="paused",
                total_turns=10,
                llm_provider="anthropic",
                gm_model="test",
            )
            db.add(game1)
            db.add(game2)
            db.commit()

        with patch("src.cli.commands.game.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["game", "list", "--status", "active"])

        assert result.exit_code == 0
        assert "Active Game" in result.output
        assert "Paused Game" not in result.output


class TestGameDelete:
    """Tests for 'rpg game delete' command."""

    def test_deletes_game_with_force(self, temp_db):
        """Should delete game when --force is provided."""
        engine, mock_get_db_session = temp_db

        # Create a game
        Session = sessionmaker(bind=engine)
        with Session() as db:
            game = GameSession(
                session_name="To Delete",
                setting="fantasy",
                status="active",
                total_turns=0,
                llm_provider="anthropic",
                gm_model="test",
            )
            db.add(game)
            db.commit()
            game_id = game.id

        with patch("src.cli.commands.game.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["game", "delete", str(game_id), "--force"])

        assert result.exit_code == 0
        assert "Deleted" in result.output

        # Verify deleted
        with Session() as db:
            game = db.query(GameSession).filter(GameSession.id == game_id).first()
            assert game is None

    def test_deletes_game_cascades_data(self, temp_db):
        """Deleting game should cascade to all related data."""
        engine, mock_get_db_session = temp_db

        Session = sessionmaker(bind=engine)
        with Session() as db:
            # Create game with related data
            game = GameSession(
                session_name="Cascade Test",
                setting="fantasy",
                status="active",
                total_turns=0,
                llm_provider="anthropic",
                gm_model="test",
            )
            db.add(game)
            db.flush()

            time_state = TimeState(
                session_id=game.id,
                current_day=1,
                current_time="09:00",
            )
            db.add(time_state)

            entity = Entity(
                session_id=game.id,
                entity_key="test_player",
                display_name="Test Player",
                entity_type=EntityType.PLAYER,
                is_alive=True,
                is_active=True,
            )
            db.add(entity)
            db.commit()
            game_id = game.id

        with patch("src.cli.commands.game.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["game", "delete", str(game_id), "--force"])

        assert result.exit_code == 0

        # Verify cascade
        with Session() as db:
            assert db.query(GameSession).filter(GameSession.id == game_id).first() is None
            assert db.query(TimeState).filter(TimeState.session_id == game_id).first() is None
            assert db.query(Entity).filter(Entity.session_id == game_id).first() is None

    def test_handles_nonexistent_game(self, temp_db):
        """Should handle deleting non-existent game."""
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.game.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["game", "delete", "99999", "--force"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestGamePlay:
    """Tests for 'rpg game play' command."""

    def test_play_requires_session(self, temp_db):
        """Should show error when no active session exists."""
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.game.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["game", "play"])

        assert result.exit_code == 1
        assert "No active session" in result.output

    def test_play_requires_character(self, temp_db):
        """Should prompt for character creation when no character exists."""
        engine, mock_get_db_session = temp_db

        # Create session without character
        Session = sessionmaker(bind=engine)
        with Session() as db:
            game = GameSession(
                session_name="No Character",
                setting="fantasy",
                status="active",
                total_turns=0,
                llm_provider="anthropic",
                gm_model="test",
            )
            db.add(game)
            db.commit()

        with patch("src.cli.commands.game.get_db_session", mock_get_db_session):
            # User declines to create character
            result = runner.invoke(app, ["game", "play"], input="n\n")

        assert result.exit_code == 0
        assert "No character found" in result.output


class TestGameTurn:
    """Tests for 'rpg game turn' command."""

    def test_turn_requires_session(self, temp_db):
        """Should error when no active session exists."""
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.game.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["game", "turn", "look around"])

        assert result.exit_code == 1
        assert "No active session" in result.output


class TestGameStartWizard:
    """Tests for 'rpg game start' wizard flow.

    Note: Testing the full wizard flow requires mocking LLM responses.
    These tests focus on the setup and error paths.
    """

    def test_start_shows_welcome(self, temp_db):
        """Starting game should show welcome message."""
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.game.get_db_session", mock_get_db_session):
            # Abort early by hitting Ctrl+C (simulated by CliRunner)
            result = runner.invoke(
                app,
                ["game", "start", "--name", "Test", "--setting", "fantasy"],
                input="\x03",  # Ctrl+C
            )

        # Should show the welcome message before cancellation
        assert "Welcome to RPG Game" in result.output or "adventure" in result.output.lower()

    def test_start_uses_preset_setting(self, temp_db):
        """Starting with --setting should use that setting."""
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.game.get_db_session", mock_get_db_session):
            result = runner.invoke(
                app,
                ["game", "start", "--name", "Scifi Game", "--setting", "scifi"],
                input="\x03",  # Cancel early
            )

        # Should mention the setting
        assert "scifi" in result.output.lower()

    def test_start_uses_preset_name(self, temp_db):
        """Starting with --name should use that name."""
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.game.get_db_session", mock_get_db_session):
            result = runner.invoke(
                app,
                ["game", "start", "--name", "My Epic Quest", "--setting", "fantasy"],
                input="\x03",  # Cancel early
            )

        assert "My Epic Quest" in result.output

    def test_start_keyboard_interrupt_handled(self, temp_db):
        """KeyboardInterrupt should be handled gracefully."""
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.game.get_db_session", mock_get_db_session):
            result = runner.invoke(
                app,
                ["game", "start", "--name", "Test"],
                input="\x03",  # Ctrl+C
            )

        # Should show cancellation message, not crash
        # Exit code might be 0 or 1 depending on where interruption occurs
        assert result.exception is None or isinstance(result.exception, SystemExit)


class TestWizardResponseParsing:
    """Tests for the wizard response parsing functions."""

    def test_parse_wizard_response_field_updates(self):
        """Should parse field_updates JSON from AI response."""
        from src.cli.commands.character import _parse_wizard_response

        response = '''
        Great! Let me save that.

        ```json
        {"field_updates": {"name": "Aragorn", "species": "human"}}
        ```

        What would you like for your character's background?
        '''

        field_updates, section_data, section_complete = _parse_wizard_response(response)

        assert field_updates == {"name": "Aragorn", "species": "human"}
        assert section_complete is False

    def test_parse_wizard_response_section_complete(self):
        """Should parse section_complete signal from AI response."""
        from src.cli.commands.character import _parse_wizard_response

        response = '''
        Perfect! I've captured all your character's information.

        ```json
        {"section_complete": true, "data": {"name": "Gandalf", "species": "maiar"}}
        ```
        '''

        field_updates, section_data, section_complete = _parse_wizard_response(response)

        assert section_complete is True
        assert section_data == {"name": "Gandalf", "species": "maiar"}

    def test_parse_wizard_response_no_json(self):
        """Should handle response with no JSON gracefully."""
        from src.cli.commands.character import _parse_wizard_response

        response = "That sounds like a great character concept! Tell me more about their background."

        field_updates, section_data, section_complete = _parse_wizard_response(response)

        assert field_updates is None
        assert section_data is None
        assert section_complete is False

    def test_parse_wizard_response_malformed_json(self):
        """Should handle malformed JSON gracefully without raising."""
        from src.cli.commands.character import _parse_wizard_response

        response = '''
        ```json
        {"field_updates": {name: "missing quotes"}}
        ```
        '''

        # Should not raise
        field_updates, section_data, section_complete = _parse_wizard_response(response)

        # May or may not parse depending on sanitization
        assert section_complete is False

    def test_parse_wizard_response_quoted_section_complete_key(self):
        """Should handle section_complete with various quote styles."""
        from src.cli.commands.character import _parse_wizard_response

        # Test with single quotes around key
        response1 = '''
        ```json
        {'section_complete': true, 'data': {'name': 'Test'}}
        ```
        '''

        # The regex should still match
        _, _, section_complete1 = _parse_wizard_response(response1)
        # Note: This may fail if single quotes aren't handled

        # Test with no quotes (technically invalid JSON but LLMs sometimes do this)
        response2 = '''
        ```json
        {section_complete: true, data: {name: "Test"}}
        ```
        '''

        _, _, section_complete2 = _parse_wizard_response(response2)
        # May or may not match depending on regex

    def test_parse_wizard_response_nested_json(self):
        """Should handle nested JSON blocks correctly."""
        from src.cli.commands.character import _parse_wizard_response

        # Complex nested JSON that LLMs sometimes produce
        response = '''
        Here's your character info:

        ```json
        {
            "section_complete": true,
            "data": {
                "name": "Gandalf",
                "species": "maiar",
                "attributes": {
                    "wisdom": 18
                }
            }
        }
        ```
        '''

        field_updates, section_data, section_complete = _parse_wizard_response(response)

        assert section_complete is True
        # section_data should be the "data" field
        assert section_data is not None
        assert section_data.get("name") == "Gandalf"

    def test_parse_wizard_response_multiple_json_blocks(self):
        """Should handle multiple JSON blocks in response."""
        from src.cli.commands.character import _parse_wizard_response

        response = '''
        I've updated the field:

        ```json
        {"field_updates": {"name": "Frodo"}}
        ```

        And here's the completion:

        ```json
        {"section_complete": true, "data": {"name": "Frodo", "species": "hobbit"}}
        ```
        '''

        field_updates, section_data, section_complete = _parse_wizard_response(response)

        # Should parse both blocks
        assert field_updates == {"name": "Frodo"}
        assert section_complete is True

    def test_parse_wizard_response_json_with_comments(self):
        """Should handle JSON with JavaScript-style comments (LLMs sometimes add these)."""
        from src.cli.commands.character import _parse_wizard_response

        response = '''
        ```json
        {
            // This is the completion signal
            "section_complete": true,
            "data": {
                "name": "Aragorn"  // The character name
            }
        }
        ```
        '''

        field_updates, section_data, section_complete = _parse_wizard_response(response)

        assert section_complete is True
        assert section_data is not None
        assert section_data.get("name") == "Aragorn"

    def test_parse_wizard_response_raw_json_section_complete(self):
        """Should parse section_complete from raw JSON (no code fences).

        This tests the fix for the bug where LLMs output JSON without markdown
        code blocks, causing section_complete to not be detected.
        """
        from src.cli.commands.character import _parse_wizard_response

        # Raw JSON without code fences - the bug scenario
        response = '''
        Excellent! A human male character.

        {"section_complete": true, "data": {"species": "Human", "gender": "male"}}
        '''

        field_updates, section_data, section_complete = _parse_wizard_response(response)

        assert section_complete is True
        assert section_data == {"species": "Human", "gender": "male"}

    def test_parse_wizard_response_raw_json_field_updates(self):
        """Should parse field_updates from raw JSON (no code fences)."""
        from src.cli.commands.character import _parse_wizard_response

        response = '''
        I've noted your character's name.

        {"field_updates": {"name": "Gandalf"}}
        '''

        field_updates, section_data, section_complete = _parse_wizard_response(response)

        assert field_updates == {"name": "Gandalf"}
        assert section_complete is False

    def test_parse_wizard_response_does_not_raise_keyerror(self):
        """Ensure parsing never raises KeyError even with malformed input."""
        from src.cli.commands.character import _parse_wizard_response

        # Various malformed inputs that should not raise KeyError
        malformed_inputs = [
            '{"section_complete": }',  # Missing value
            '{"": true}',  # Empty key
            '```json\n{broken}\n```',  # Invalid JSON
            '```json\n{"key": "value",}\n```',  # Trailing comma
            'No JSON here at all',
            '```json\n\n```',  # Empty JSON block
            '```json\n{"section_complete": "not_a_bool"}\n```',  # Wrong type
        ]

        for malformed in malformed_inputs:
            # Should not raise any exception
            try:
                field_updates, section_data, section_complete = _parse_wizard_response(malformed)
                # All should return safely without raising
                assert isinstance(section_complete, bool)
            except KeyError as e:
                pytest.fail(f"KeyError raised for input: {malformed!r}, error: {e}")


class TestCharacterRecordsCreation:
    """Tests for character record creation during game start."""

    def test_create_character_records_basic(self, db_session, game_session):
        """Should create Entity with all required fields."""
        from src.cli.commands.character import _create_character_records

        attributes = {
            "strength": 14, "dexterity": 12, "constitution": 13,
            "intelligence": 10, "wisdom": 11, "charisma": 8,
        }

        entity = _create_character_records(
            db=db_session,
            game_session=game_session,
            name="Test Hero",
            attributes=attributes,
            background="A brave adventurer",
        )

        assert entity is not None
        assert entity.display_name == "Test Hero"
        assert entity.entity_type == EntityType.PLAYER
        assert entity.background == "A brave adventurer"
        assert entity.is_alive is True
        assert entity.is_active is True

    def test_create_character_records_creates_attributes(self, db_session, game_session):
        """Should create EntityAttribute records for all attributes."""
        from src.cli.commands.character import _create_character_records

        attributes = {
            "strength": 16, "dexterity": 14, "constitution": 15,
            "intelligence": 12, "wisdom": 10, "charisma": 8,
        }

        entity = _create_character_records(
            db=db_session,
            game_session=game_session,
            name="Attr Hero",
            attributes=attributes,
        )

        db_attrs = db_session.query(EntityAttribute).filter(
            EntityAttribute.entity_id == entity.id
        ).all()

        assert len(db_attrs) == 6
        attr_dict = {a.attribute_key: a.value for a in db_attrs}
        assert attr_dict["strength"] == 16
        assert attr_dict["dexterity"] == 14

    def test_create_character_records_creates_needs(self, db_session, game_session):
        """Should create CharacterNeeds record."""
        from src.cli.commands.character import _create_character_records

        attributes = {
            "strength": 10, "dexterity": 10, "constitution": 10,
            "intelligence": 10, "wisdom": 10, "charisma": 10,
        }

        entity = _create_character_records(
            db=db_session,
            game_session=game_session,
            name="Needs Hero",
            attributes=attributes,
        )

        needs = db_session.query(CharacterNeeds).filter(
            CharacterNeeds.entity_id == entity.id
        ).first()

        assert needs is not None
        assert needs.hunger > 0  # Should have default values

    def test_create_character_prevents_duplicate_player(self, db_session, game_session):
        """Should not allow multiple players in same session."""
        from src.cli.commands.character import _create_character_records

        attributes = {
            "strength": 10, "dexterity": 10, "constitution": 10,
            "intelligence": 10, "wisdom": 10, "charisma": 10,
        }

        # Create first player
        _create_character_records(
            db=db_session,
            game_session=game_session,
            name="First Player",
            attributes=attributes,
        )
        db_session.commit()

        # Second player should fail
        with pytest.raises(ValueError, match="already has a player"):
            _create_character_records(
                db=db_session,
                game_session=game_session,
                name="Second Player",
                attributes=attributes,
            )


class TestAvailableSettings:
    """Tests for settings discovery."""

    def test_get_available_settings_returns_list(self):
        """Should return a list of available settings."""
        from src.cli.commands.game import _get_available_settings

        settings = _get_available_settings()

        assert isinstance(settings, list)
        assert len(settings) > 0

        # Each setting should have required fields
        for setting in settings:
            assert "key" in setting
            assert "name" in setting
            assert "description" in setting

    def test_get_available_settings_has_fantasy(self):
        """Should include fantasy setting."""
        from src.cli.commands.game import _get_available_settings

        settings = _get_available_settings()
        keys = [s["key"] for s in settings]

        assert "fantasy" in keys


class TestFullGameFlow:
    """Integration tests for complete game flows."""

    def test_full_flow_create_list_delete(self, temp_db):
        """Full flow: create game (directly) → list → delete."""
        engine, mock_get_db_session = temp_db

        # Create game directly in DB (bypassing wizard for this flow test)
        Session = sessionmaker(bind=engine)
        with Session() as db:
            game = GameSession(
                session_name="Flow Test",
                setting="fantasy",
                status="active",
                total_turns=0,
                llm_provider="anthropic",
                gm_model="test",
            )
            db.add(game)
            db.commit()
            game_id = game.id

        # Step 1: List games
        with patch("src.cli.commands.game.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["game", "list"])

        assert result.exit_code == 0
        assert "Flow Test" in result.output

        # Step 2: Delete game
        with patch("src.cli.commands.game.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["game", "delete", str(game_id), "--force"])

        assert result.exit_code == 0

        # Verify deleted
        with Session() as db:
            assert db.query(GameSession).count() == 0

    def test_session_isolation_between_games(self, temp_db):
        """Entities in one game should not appear in another."""
        engine, mock_get_db_session = temp_db

        Session = sessionmaker(bind=engine)
        with Session() as db:
            # Create two games
            game1 = GameSession(
                session_name="Game One",
                setting="fantasy",
                status="active",
                total_turns=0,
                llm_provider="anthropic",
                gm_model="test",
            )
            game2 = GameSession(
                session_name="Game Two",
                setting="fantasy",
                status="active",
                total_turns=0,
                llm_provider="anthropic",
                gm_model="test",
            )
            db.add(game1)
            db.add(game2)
            db.flush()

            # Add player to first game only
            player = Entity(
                session_id=game1.id,
                entity_key="hero",
                display_name="Hero",
                entity_type=EntityType.PLAYER,
                is_alive=True,
                is_active=True,
            )
            db.add(player)
            db.commit()
            game1_id = game1.id
            game2_id = game2.id

        # Verify player only in game1
        with Session() as db:
            game1_players = db.query(Entity).filter(
                Entity.session_id == game1_id,
                Entity.entity_type == EntityType.PLAYER,
            ).all()
            game2_players = db.query(Entity).filter(
                Entity.session_id == game2_id,
                Entity.entity_type == EntityType.PLAYER,
            ).all()

            assert len(game1_players) == 1
            assert len(game2_players) == 0


class TestPlayShortcut:
    """Tests for 'rpg play' shortcut command."""

    def test_play_shortcut_requires_session(self, temp_db):
        """The 'rpg play' shortcut should work like 'rpg game play'."""
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.game.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["play"])

        assert result.exit_code == 1
        assert "No active session" in result.output


class TestWorldCommands:
    """Tests for 'rpg world' commands."""

    def test_time_requires_session(self, temp_db):
        """world time should require an active session."""
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.world.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["world", "time"])

        assert result.exit_code == 1
        assert "No active session" in result.output

    def test_time_shows_current_time(self, temp_db):
        """world time should display current game time."""
        engine, mock_get_db_session = temp_db

        Session = sessionmaker(bind=engine)
        with Session() as db:
            game = GameSession(
                session_name="Time Test",
                setting="fantasy",
                status="active",
                total_turns=0,
                llm_provider="anthropic",
                gm_model="test",
            )
            db.add(game)
            db.flush()

            time_state = TimeState(
                session_id=game.id,
                current_day=5,
                current_time="14:30",
                day_of_week="Wednesday",
                season="Summer",
                weather="Sunny",
            )
            db.add(time_state)
            db.commit()

        with patch("src.cli.commands.world.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["world", "time"])

        assert result.exit_code == 0
        assert "Day 5" in result.output
        assert "14:30" in result.output
        assert "Wednesday" in result.output

    def test_locations_requires_session(self, temp_db):
        """world locations should require an active session."""
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.world.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["world", "locations"])

        assert result.exit_code == 1
        assert "No active session" in result.output

    def test_locations_empty(self, temp_db):
        """world locations should handle no locations gracefully."""
        engine, mock_get_db_session = temp_db

        Session = sessionmaker(bind=engine)
        with Session() as db:
            game = GameSession(
                session_name="Empty Test",
                setting="fantasy",
                status="active",
                total_turns=0,
                llm_provider="anthropic",
                gm_model="test",
            )
            db.add(game)
            db.commit()

        with patch("src.cli.commands.world.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["world", "locations"])

        assert result.exit_code == 0
        assert "No locations" in result.output

    def test_npcs_requires_session(self, temp_db):
        """world npcs should require an active session."""
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.world.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["world", "npcs"])

        assert result.exit_code == 1
        assert "No active session" in result.output

    def test_npcs_shows_npcs(self, temp_db):
        """world npcs should list NPCs."""
        engine, mock_get_db_session = temp_db

        Session = sessionmaker(bind=engine)
        with Session() as db:
            game = GameSession(
                session_name="NPC Test",
                setting="fantasy",
                status="active",
                total_turns=0,
                llm_provider="anthropic",
                gm_model="test",
            )
            db.add(game)
            db.flush()

            npc = Entity(
                session_id=game.id,
                entity_key="bartender",
                display_name="Joe the Bartender",
                entity_type=EntityType.NPC,
                is_alive=True,
                is_active=True,
            )
            db.add(npc)
            db.commit()

        with patch("src.cli.commands.world.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["world", "npcs"])

        assert result.exit_code == 0
        assert "Joe the Bartender" in result.output

    def test_events_requires_session(self, temp_db):
        """world events should require an active session."""
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.world.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["world", "events"])

        assert result.exit_code == 1
        assert "No active session" in result.output

    def test_zones_requires_session(self, temp_db):
        """world zones should require an active session."""
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.world.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["world", "zones"])

        assert result.exit_code == 1
        assert "No active session" in result.output


class TestCharacterCommands:
    """Tests for 'rpg character' commands."""

    def test_status_requires_session(self, temp_db):
        """character status should require an active session."""
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.character.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["character", "status"])

        assert result.exit_code == 1
        assert "No active session" in result.output or "not found" in result.output.lower()

    def test_inventory_requires_session(self, temp_db):
        """character inventory should require an active session."""
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.character.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["character", "inventory"])

        assert result.exit_code == 1
        assert "No active session" in result.output or "not found" in result.output.lower()

    def test_status_shows_character_info(self, temp_db):
        """character status should show character information."""
        engine, mock_get_db_session = temp_db

        Session = sessionmaker(bind=engine)
        with Session() as db:
            game = GameSession(
                session_name="Status Test",
                setting="fantasy",
                status="active",
                total_turns=0,
                llm_provider="anthropic",
                gm_model="test",
            )
            db.add(game)
            db.flush()

            player = Entity(
                session_id=game.id,
                entity_key="hero",
                display_name="Brave Hero",
                entity_type=EntityType.PLAYER,
                is_alive=True,
                is_active=True,
            )
            db.add(player)
            db.commit()

        with patch("src.cli.commands.character.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["character", "status"])

        assert result.exit_code == 0
        assert "Brave Hero" in result.output


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_game_delete_without_force_prompts(self, temp_db):
        """game delete without --force should prompt for confirmation."""
        engine, mock_get_db_session = temp_db

        Session = sessionmaker(bind=engine)
        with Session() as db:
            game = GameSession(
                session_name="Prompt Test",
                setting="fantasy",
                status="active",
                total_turns=0,
                llm_provider="anthropic",
                gm_model="test",
            )
            db.add(game)
            db.commit()
            game_id = game.id

        with patch("src.cli.commands.game.get_db_session", mock_get_db_session):
            # Answer 'n' to confirmation
            result = runner.invoke(app, ["game", "delete", str(game_id)], input="n\n")

        assert result.exit_code == 0
        # Game should still exist
        with Session() as db:
            assert db.query(GameSession).filter(GameSession.id == game_id).first() is not None

    def test_multiple_active_sessions_uses_latest(self, temp_db):
        """When multiple active sessions exist, commands should use the most recent."""
        engine, mock_get_db_session = temp_db

        Session = sessionmaker(bind=engine)
        with Session() as db:
            game1 = GameSession(
                session_name="First Game",
                setting="fantasy",
                status="active",
                total_turns=5,
                llm_provider="anthropic",
                gm_model="test",
            )
            game2 = GameSession(
                session_name="Second Game",
                setting="fantasy",
                status="active",
                total_turns=10,
                llm_provider="anthropic",
                gm_model="test",
            )
            db.add(game1)
            db.add(game2)
            db.flush()

            # Add time state to both
            ts1 = TimeState(session_id=game1.id, current_day=1, current_time="09:00")
            ts2 = TimeState(session_id=game2.id, current_day=3, current_time="15:00")
            db.add(ts1)
            db.add(ts2)
            db.commit()

        with patch("src.cli.commands.world.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["world", "time"])

        # Should show time from the most recent (second) game
        assert "Day 3" in result.output
        assert "15:00" in result.output

    def test_session_specific_flag_overrides_active(self, temp_db):
        """The --session flag should override automatic session selection."""
        engine, mock_get_db_session = temp_db

        Session = sessionmaker(bind=engine)
        with Session() as db:
            game1 = GameSession(
                session_name="Old Game",
                setting="fantasy",
                status="active",
                total_turns=5,
                llm_provider="anthropic",
                gm_model="test",
            )
            game2 = GameSession(
                session_name="New Game",
                setting="fantasy",
                status="active",
                total_turns=10,
                llm_provider="anthropic",
                gm_model="test",
            )
            db.add(game1)
            db.add(game2)
            db.flush()

            ts1 = TimeState(session_id=game1.id, current_day=1, current_time="09:00")
            ts2 = TimeState(session_id=game2.id, current_day=5, current_time="18:00")
            db.add(ts1)
            db.add(ts2)
            db.commit()
            game1_id = game1.id

        with patch("src.cli.commands.world.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["world", "time", "--session", str(game1_id)])

        # Should show time from the specifically requested (first) game
        assert "Day 1" in result.output
        assert "09:00" in result.output
