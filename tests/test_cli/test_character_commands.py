"""Tests for character CLI commands."""

from contextlib import contextmanager
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from typer.testing import CliRunner

from src.cli.main import app
from src.cli.commands.character import CharacterCreationState
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

    yield engine, mock_get_db_session

    engine.dispose()


@pytest.fixture
def session_with_player(temp_db):
    """Create a session with a player character."""
    engine, mock_get_db_session = temp_db

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

    return engine, mock_get_db_session, session_id, player_id


class TestCharacterStatus:
    """Tests for 'rpg character status' command."""

    def test_shows_player_name(self, session_with_player):
        """Should display player character name."""
        engine, mock_get_db_session, session_id, player_id = session_with_player

        with patch("src.cli.commands.character.get_db_session", mock_get_db_session):
            result = runner.invoke(
                app, ["character", "status", "--session", str(session_id)]
            )

        assert result.exit_code == 0
        assert "Test Hero" in result.output

    def test_requires_existing_session(self, temp_db):
        """Should error when no session exists."""
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.character.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["character", "status"])

        assert result.exit_code == 1
        assert "No active session" in result.output or "not found" in result.output.lower()

    def test_requires_existing_character(self, temp_db):
        """Should error when session has no player."""
        engine, mock_get_db_session = temp_db

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

        with patch("src.cli.commands.character.get_db_session", mock_get_db_session):
            result = runner.invoke(
                app, ["character", "status", "--session", str(session_id)]
            )

        assert result.exit_code == 1
        assert "No player" in result.output or "not found" in result.output.lower()


class TestCharacterInventory:
    """Tests for 'rpg character inventory' command."""

    def test_shows_owned_items(self, session_with_player):
        """Should display items owned by player."""
        engine, mock_get_db_session, session_id, player_id = session_with_player

        with patch("src.cli.commands.character.get_db_session", mock_get_db_session):
            result = runner.invoke(
                app, ["character", "inventory", "--session", str(session_id)]
            )

        assert result.exit_code == 0
        assert "Steel Sword" in result.output
        assert "Cloth Tunic" in result.output

    def test_shows_item_types(self, session_with_player):
        """Should show item type information."""
        engine, mock_get_db_session, session_id, player_id = session_with_player

        with patch("src.cli.commands.character.get_db_session", mock_get_db_session):
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
        engine, mock_get_db_session, session_id, player_id = session_with_player

        with patch("src.cli.commands.character.get_db_session", mock_get_db_session):
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
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.character.get_db_session", mock_get_db_session):
            result = runner.invoke(app, ["character", "create"])

        assert result.exit_code == 1
        assert "No active session" in result.output

    def test_prevents_duplicate_player(self, session_with_player):
        """Should prevent creating second player in same session."""
        engine, mock_get_db_session, session_id, player_id = session_with_player

        with patch("src.cli.commands.character.get_db_session", mock_get_db_session):
            result = runner.invoke(
                app, ["character", "create", "--session", str(session_id)]
            )

        assert result.exit_code == 1
        assert "already has" in result.output.lower() or "Test Hero" in result.output


class TestCharacterCreateRandom:
    """Tests for 'rpg character create --random' command."""

    def test_random_creates_player(self, temp_db):
        """Random creation should create a player entity."""
        engine, mock_get_db_session = temp_db

        # First create a session
        with patch("src.cli.commands.session.get_db_session", mock_get_db_session):
            runner.invoke(app, ["session", "start"])

        # Now create character with random stats
        # We need to mock the interactive input
        with patch("src.cli.commands.character.get_db_session", mock_get_db_session):
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
        engine, mock_get_db_session = temp_db

        # Create a session first
        with patch("src.cli.commands.session.get_db_session", mock_get_db_session):
            runner.invoke(app, ["session", "start"])

        # Mock the AI creation function and world extraction
        with patch("src.cli.commands.character.get_db_session", mock_get_db_session):
            with patch(
                "src.cli.commands.character._ai_character_creation"
            ) as mock_ai:
                with patch(
                    "src.cli.commands.character._extract_world_data"
                ) as mock_extract:
                    # Return a CharacterCreationState object
                    mock_ai.return_value = CharacterCreationState(
                        name="AI Hero",
                        attributes={"strength": 15, "dexterity": 14, "constitution": 13,
                                   "intelligence": 12, "wisdom": 10, "charisma": 8},
                        background="Created by AI",
                        age=25,
                        gender="male",
                        build="athletic",
                        hair_color="brown",
                        eye_color="blue",
                        personality_notes="Brave and kind",
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
        engine, mock_get_db_session = temp_db

        with patch("src.cli.commands.session.get_db_session", mock_get_db_session):
            runner.invoke(app, ["session", "start"])

        with patch("src.cli.commands.character.get_db_session", mock_get_db_session):
            with patch(
                "src.cli.commands.character._ai_character_creation"
            ) as mock_ai:
                # Simulate LLM error by raising SystemExit (from typer.Exit)
                import typer
                mock_ai.side_effect = typer.Exit(1)

                result = runner.invoke(app, ["character", "create", "--ai"])

        # Should exit with error
        assert result.exit_code == 1


class TestParseReadyToPlay:
    """Tests for _parse_ready_to_play function."""

    def test_detects_ready_in_code_block(self):
        """Should detect ready_to_play in markdown code block."""
        from src.cli.commands.character import _parse_ready_to_play

        response = '''Great! Let's begin!

```json
{"ready_to_play": true}
```'''
        assert _parse_ready_to_play(response) is True

    def test_detects_ready_inline(self):
        """Should detect inline ready_to_play JSON."""
        from src.cli.commands.character import _parse_ready_to_play

        response = 'Finn is ready for adventure! {"ready_to_play": true}'
        assert _parse_ready_to_play(response) is True

    def test_returns_false_when_not_present(self):
        """Should return False when no ready_to_play."""
        from src.cli.commands.character import _parse_ready_to_play

        response = '''Here are your attributes:

```json
{"field_updates": {"name": "Finn"}}
```'''
        assert _parse_ready_to_play(response) is False

    def test_returns_false_when_false_value(self):
        """Should return False when ready_to_play is false."""
        from src.cli.commands.character import _parse_ready_to_play

        response = '{"ready_to_play": false}'
        assert _parse_ready_to_play(response) is False

    def test_handles_mixed_case(self):
        """Should handle case-insensitive boolean."""
        from src.cli.commands.character import _parse_ready_to_play

        response = '{"ready_to_play": True}'
        # JSON booleans are lowercase, but regex handles True
        assert _parse_ready_to_play(response) is True


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

    def test_strips_player_input_section(self):
        """Should remove ## Player Input section echoed by LLM."""
        from src.cli.commands.character import _strip_json_blocks

        text = '''Great choice! Roran is a strong name.

How old would you like Roran to be?

## Player Input
25'''

        result = _strip_json_blocks(text)

        assert "## Player Input" not in result
        assert "How old would you like Roran to be?" in result
        # The "25" after Player Input header should be stripped
        assert result.strip().endswith("?")

    def test_strips_player_echo_at_end(self):
        """Should remove Player: format echoed at end of response."""
        from src.cli.commands.character import _strip_json_blocks

        text = '''How old would you like Roran to be?

Player: 25'''

        result = _strip_json_blocks(text)

        assert "Player: 25" not in result
        assert "How old would you like Roran to be?" in result

    def test_strips_conversation_history_section(self):
        """Should remove ## Conversation History section."""
        from src.cli.commands.character import _strip_json_blocks

        text = '''Great choice!

## Conversation History
Player: Male
Assistant: A human male...

What's next?'''

        result = _strip_json_blocks(text)

        assert "## Conversation History" not in result
        assert "Great choice!" in result

    def test_strips_multiple_template_sections(self):
        """Should handle multiple template sections in one response."""
        from src.cli.commands.character import _strip_json_blocks

        text = '''Here's my response.

## Required Fields
- name
- age

## Player Input
test

More content.'''

        result = _strip_json_blocks(text)

        assert "## Required Fields" not in result
        assert "## Player Input" not in result
        assert "Here's my response." in result
        assert "More content." in result

    def test_preserves_normal_markdown_headers(self):
        """Should not strip legitimate markdown headers in AI response."""
        from src.cli.commands.character import _strip_json_blocks

        # Normal headers that are part of AI's response should be kept
        text = '''## Character Options

Here are some names:
- Finn
- Roran'''

        result = _strip_json_blocks(text)

        assert "## Character Options" in result
        assert "Finn" in result


class TestStripJsonComments:
    """Tests for _strip_json_comments function."""

    def test_strips_single_line_comments(self):
        """Should strip // comments from JSON."""
        from src.cli.commands.character import _strip_json_comments

        json_with_comments = '''{
            "strength": 10,  // Typical for age
            "dexterity": 14  // Quick and nimble
        }'''

        result = _strip_json_comments(json_with_comments)
        assert "//" not in result
        assert "Typical" not in result
        assert '"strength": 10' in result
        assert '"dexterity": 14' in result

    def test_preserves_urls_with_slashes(self):
        """Should not strip // in URLs."""
        from src.cli.commands.character import _strip_json_comments

        json_with_url = '{"url": "https://example.com/path"}'
        result = _strip_json_comments(json_with_url)

        assert "https://example.com/path" in result

    def test_handles_multiline_json(self):
        """Should handle multiline JSON with comments on each line."""
        from src.cli.commands.character import _strip_json_comments

        json_str = '''{"attributes": {
            "strength": 8,     // young
            "dexterity": 14,   // nimble
            "constitution": 12 // healthy
        }}'''

        result = _strip_json_comments(json_str)
        # Should be valid JSON now
        import json
        data = json.loads(result)
        assert data["attributes"]["strength"] == 8
        assert data["attributes"]["dexterity"] == 14


class TestParseFieldUpdatesWithComments:
    """Tests for _parse_field_updates handling of JSON with comments."""

    def test_parses_json_with_inline_comments(self):
        """Should parse field_updates with // comments."""
        from src.cli.commands.character import _parse_field_updates

        response = '''I'll set Finn's attributes:

```json
{"field_updates": {"attributes": {
    "strength": 8,     // Typical for his young age
    "dexterity": 14,   // Nimble and quick
    "constitution": 12, // Healthy and resilient
    "intelligence": 13, // Curious and bright
    "wisdom": 11,       // Learning about the world
    "charisma": 8       // Still developing social skills
}}}
```'''

        updates = _parse_field_updates(response)
        assert updates is not None
        assert "attributes" in updates
        assert updates["attributes"]["strength"] == 8
        assert updates["attributes"]["dexterity"] == 14

    def test_parses_multiline_inline_json(self):
        """Should parse inline JSON spread across multiple lines."""
        from src.cli.commands.character import _parse_field_updates

        response = '''Setting values: {"field_updates": {
            "name": "Finn",
            "age": 12,
            "gender": "male"
        }} Done!'''

        updates = _parse_field_updates(response)
        assert updates is not None
        assert updates["name"] == "Finn"
        assert updates["age"] == 12

    def test_parses_json_with_newlines_in_strings(self):
        """Should parse JSON where string values contain literal newlines."""
        from src.cli.commands.character import _parse_field_updates

        # Simulating AI output with newlines inside the background string
        response = '''```json
{"field_updates": {"background": "Finn grew up in a village.
He lost his parents at age 8.
Now he helps the local herbalist."}}
```'''

        updates = _parse_field_updates(response)
        assert updates is not None
        assert "background" in updates
        assert "village" in updates["background"]


class TestSanitizeJsonString:
    """Tests for _sanitize_json_string function."""

    def test_escapes_newlines_in_string_values(self):
        """Should escape newlines inside JSON string values."""
        from src.cli.commands.character import _sanitize_json_string

        json_str = '{"text": "line one\nline two"}'
        result = _sanitize_json_string(json_str)

        assert "\\n" in result
        import json
        data = json.loads(result)
        assert data["text"] == "line one\nline two"

    def test_preserves_structural_newlines(self):
        """Should not escape newlines between JSON elements."""
        from src.cli.commands.character import _sanitize_json_string

        json_str = '{\n  "name": "Finn",\n  "age": 12\n}'
        result = _sanitize_json_string(json_str)

        import json
        data = json.loads(result)
        assert data["name"] == "Finn"
        assert data["age"] == 12


class TestExtractNameFromInput:
    """Tests for _extract_name_from_input function."""

    def test_extracts_capitalized_single_word(self):
        """Should extract a capitalized single word as name."""
        from src.cli.commands.character import _extract_name_from_input

        assert _extract_name_from_input("Finn") == "Finn"
        assert _extract_name_from_input("Elena") == "Elena"
        assert _extract_name_from_input("Marcus") == "Marcus"

    def test_ignores_common_words(self):
        """Should not extract common words as names."""
        from src.cli.commands.character import _extract_name_from_input

        assert _extract_name_from_input("Yes") is None
        assert _extract_name_from_input("Done") is None
        assert _extract_name_from_input("Ready") is None
        assert _extract_name_from_input("Male") is None

    def test_extracts_from_name_phrases(self):
        """Should extract name from 'My name is X' patterns."""
        from src.cli.commands.character import _extract_name_from_input

        assert _extract_name_from_input("My name is Finn") == "Finn"
        assert _extract_name_from_input("Call me Elena") == "Elena"

    def test_returns_none_for_sentences(self):
        """Should return None for longer sentences."""
        from src.cli.commands.character import _extract_name_from_input

        assert _extract_name_from_input("I want to play a warrior") is None
        assert _extract_name_from_input("Make him strong") is None


