"""Tests for character CLI commands."""

from contextlib import contextmanager
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

    yield db_url, engine, mock_get_db_session

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


class TestDetectGameStartIntent:
    """Tests for _detect_game_start_intent function."""

    def test_detects_start_playing(self):
        """Should detect 'start playing' phrases."""
        from src.cli.commands.character import _detect_game_start_intent

        assert _detect_game_start_intent("Let's start playing now")
        assert _detect_game_start_intent("I want to start playing")
        assert _detect_game_start_intent("start playing please")

    def test_detects_lets_phrases(self):
        """Should detect 'let's go/play/start/begin' phrases."""
        from src.cli.commands.character import _detect_game_start_intent

        assert _detect_game_start_intent("let's go")
        assert _detect_game_start_intent("Let's play!")
        assert _detect_game_start_intent("let's start")
        assert _detect_game_start_intent("let's begin")

    def test_detects_ready_phrases(self):
        """Should detect 'ready' phrases."""
        from src.cli.commands.character import _detect_game_start_intent

        assert _detect_game_start_intent("I'm ready to play")
        assert _detect_game_start_intent("im ready")
        assert _detect_game_start_intent("ready to start")
        assert _detect_game_start_intent("good to go")

    def test_detects_done_phrases(self):
        """Should detect 'done' phrases."""
        from src.cli.commands.character import _detect_game_start_intent

        assert _detect_game_start_intent("done")
        assert _detect_game_start_intent("I'm done")
        assert _detect_game_start_intent("im done")
        assert _detect_game_start_intent("all done")
        assert _detect_game_start_intent("that's it")
        assert _detect_game_start_intent("thats all")

    def test_does_not_detect_regular_conversation(self):
        """Should not detect regular conversation."""
        from src.cli.commands.character import _detect_game_start_intent

        assert not _detect_game_start_intent("Tell me more about attributes")
        assert not _detect_game_start_intent("What's my character's name again?")
        assert not _detect_game_start_intent("Can you make him taller?")
        assert not _detect_game_start_intent("I want high strength")
        assert not _detect_game_start_intent("Give me more options")


class TestExtractNameFromHistory:
    """Tests for _extract_name_from_history function."""

    def test_extracts_name_from_ai_description(self):
        """Should extract name when AI describes character."""
        from src.cli.commands.character import _extract_name_from_history

        history = [
            "Player: Create a 12-year-old boy",
            "Assistant: Finn is a 12-year-old boy with tousled dark hair.",
        ]
        assert _extract_name_from_history(history) == "Finn"

    def test_extracts_name_from_possessive(self):
        """Should extract name from possessive patterns."""
        from src.cli.commands.character import _extract_name_from_history

        history = [
            "Assistant: Here are Finn's attributes:",
        ]
        assert _extract_name_from_history(history) == "Finn"

    def test_extracts_name_from_explicit_naming(self):
        """Should extract name from 'name is X' patterns."""
        from src.cli.commands.character import _extract_name_from_history

        history = [
            "Assistant: The character's name is Elena.",
        ]
        assert _extract_name_from_history(history) == "Elena"

    def test_returns_none_for_no_name(self):
        """Should return None when no name found."""
        from src.cli.commands.character import _extract_name_from_history

        history = [
            "Player: Create a warrior",
            "Assistant: What would you like to name your character?",
        ]
        assert _extract_name_from_history(history) is None

    def test_filters_false_positives(self):
        """Should not extract common words as names."""
        from src.cli.commands.character import _extract_name_from_history

        history = [
            "Assistant: The character is a young adventurer.",
        ]
        # "The" should not be extracted as a name
        assert _extract_name_from_history(history) is None


class TestCharacterCreationState:
    """Tests for CharacterCreationState dataclass."""

    def test_missing_groups_all_empty(self):
        """Should report all groups as missing when state is empty."""
        from src.cli.commands.character import CharacterCreationState

        state = CharacterCreationState()
        missing = state.get_missing_groups()

        assert "name" in missing
        assert "attributes" in missing
        assert "appearance" in missing
        assert "background" in missing
        assert "personality" in missing
        assert len(missing) == 5

    def test_missing_groups_partially_filled(self):
        """Should only report unfilled groups."""
        from src.cli.commands.character import CharacterCreationState

        state = CharacterCreationState(
            name="Finn",
            attributes={"strength": 10, "dexterity": 14},
            background="A village boy",
        )
        missing = state.get_missing_groups()

        assert "name" not in missing
        assert "attributes" not in missing
        assert "background" not in missing
        assert "appearance" in missing
        assert "personality" in missing

    def test_is_complete_when_all_required_filled(self):
        """Should return True when all required fields are filled."""
        from src.cli.commands.character import CharacterCreationState

        state = CharacterCreationState(
            name="Finn",
            attributes={"strength": 10, "dexterity": 14, "constitution": 12,
                        "intelligence": 13, "wisdom": 11, "charisma": 8},
            age=12,
            gender="male",
            build="lean",
            hair_color="dark brown",
            eye_color="hazel",
            background="A village boy who helps the herbalist",
            personality_notes="Curious, quiet, observant",
        )

        assert state.is_complete()
        assert len(state.get_missing_groups()) == 0

    def test_appearance_requires_all_core_fields(self):
        """Appearance is incomplete without age, gender, build, hair_color, eye_color."""
        from src.cli.commands.character import CharacterCreationState

        # Missing eye_color
        state = CharacterCreationState(
            age=12,
            gender="male",
            build="lean",
            hair_color="brown",
        )
        assert "appearance" in state.get_missing_groups()

        # Add eye_color
        state.eye_color = "blue"
        assert "appearance" not in state.get_missing_groups()

    def test_get_current_state_summary(self):
        """Should generate a readable summary."""
        from src.cli.commands.character import CharacterCreationState

        state = CharacterCreationState(
            name="Finn",
            age=12,
            gender="male",
        )
        summary = state.get_current_state_summary()

        assert "Finn" in summary
        assert "age=12" in summary
        assert "gender=male" in summary
        assert "Still needed:" in summary


class TestParseFieldUpdates:
    """Tests for _parse_field_updates function."""

    def test_parses_json_code_block(self):
        """Should parse field_updates from markdown code block."""
        from src.cli.commands.character import _parse_field_updates

        response = '''Here's the character:

```json
{"field_updates": {"name": "Finn", "age": 12, "gender": "male"}}
```

I've set the name to Finn.'''

        updates = _parse_field_updates(response)
        assert updates is not None
        assert updates["name"] == "Finn"
        assert updates["age"] == 12
        assert updates["gender"] == "male"

    def test_parses_inline_json(self):
        """Should parse inline field_updates JSON."""
        from src.cli.commands.character import _parse_field_updates

        response = 'Setting your character: {"field_updates": {"name": "Elena", "build": "athletic"}}'

        updates = _parse_field_updates(response)
        assert updates is not None
        assert updates["name"] == "Elena"
        assert updates["build"] == "athletic"

    def test_returns_none_for_no_json(self):
        """Should return None when no field_updates found."""
        from src.cli.commands.character import _parse_field_updates

        response = "What would you like your character's name to be?"
        assert _parse_field_updates(response) is None


class TestParseHiddenContent:
    """Tests for _parse_hidden_content function."""

    def test_parses_hidden_backstory(self):
        """Should parse hidden_content from response."""
        from src.cli.commands.character import _parse_hidden_content

        response = '''```json
{"hidden_content": {"backstory": "Unknown to Finn, his mother was a powerful mage."}}
```'''

        hidden = _parse_hidden_content(response)
        assert hidden is not None
        assert "backstory" in hidden
        assert "powerful mage" in hidden["backstory"]

    def test_returns_none_when_not_present(self):
        """Should return None when no hidden_content."""
        from src.cli.commands.character import _parse_hidden_content

        response = "Your character is ready!"
        assert _parse_hidden_content(response) is None


class TestApplyFieldUpdates:
    """Tests for _apply_field_updates function."""

    def test_applies_name(self):
        """Should apply name field."""
        from src.cli.commands.character import CharacterCreationState, _apply_field_updates

        state = CharacterCreationState()
        _apply_field_updates(state, {"name": "Finn"})

        assert state.name == "Finn"

    def test_applies_display_name_as_name(self):
        """Should map display_name to name."""
        from src.cli.commands.character import CharacterCreationState, _apply_field_updates

        state = CharacterCreationState()
        _apply_field_updates(state, {"display_name": "Elena"})

        assert state.name == "Elena"

    def test_applies_attributes(self):
        """Should apply attributes dict."""
        from src.cli.commands.character import CharacterCreationState, _apply_field_updates

        state = CharacterCreationState()
        attrs = {"strength": 10, "dexterity": 14}
        _apply_field_updates(state, {"attributes": attrs})

        assert state.attributes == attrs

    def test_applies_appearance_fields(self):
        """Should apply all appearance fields."""
        from src.cli.commands.character import CharacterCreationState, _apply_field_updates

        state = CharacterCreationState()
        _apply_field_updates(state, {
            "age": 12,
            "gender": "male",
            "build": "lean",
            "hair_color": "brown",
            "eye_color": "blue",
            "species": "human",
        })

        assert state.age == 12
        assert state.gender == "male"
        assert state.build == "lean"
        assert state.hair_color == "brown"
        assert state.eye_color == "blue"
        assert state.species == "human"

    def test_applies_personality_alias(self):
        """Should map personality to personality_notes."""
        from src.cli.commands.character import CharacterCreationState, _apply_field_updates

        state = CharacterCreationState()
        _apply_field_updates(state, {"personality": "Curious and quiet"})

        assert state.personality_notes == "Curious and quiet"

    def test_ignores_unknown_fields(self):
        """Should ignore fields not in mapping."""
        from src.cli.commands.character import CharacterCreationState, _apply_field_updates

        state = CharacterCreationState()
        _apply_field_updates(state, {"unknown_field": "value", "name": "Finn"})

        # Should apply name but not crash on unknown
        assert state.name == "Finn"


class TestStripJsonBlocks:
    """Tests for _strip_json_blocks function."""

    def test_strips_markdown_json_blocks(self):
        """Should remove ```json``` blocks."""
        from src.cli.commands.character import _strip_json_blocks

        text = '''Hello!

```json
{"field_updates": {"name": "Finn"}}
```

Nice to meet you!'''

        result = _strip_json_blocks(text)
        assert "```json" not in result
        assert "field_updates" not in result
        assert "Hello!" in result
        assert "Nice to meet you!" in result

    def test_strips_inline_field_updates(self):
        """Should remove inline field_updates JSON."""
        from src.cli.commands.character import _strip_json_blocks

        text = 'Setting name {"field_updates": {"name": "Finn"}} done!'
        result = _strip_json_blocks(text)

        assert "field_updates" not in result
        assert "Setting name" in result
        assert "done!" in result
