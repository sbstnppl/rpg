"""Tests for GameSession and Turn models."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.database.models.session import GameSession, SessionStatus, Turn
from tests.factories import create_game_session, create_turn, create_entity


class TestGameSession:
    """Tests for GameSession model."""

    def test_create_game_session_defaults(self, db_session: Session):
        """Verify GameSession creation with defaults."""
        session = GameSession()
        db_session.add(session)
        db_session.flush()

        assert session.id is not None
        assert session.setting == "fantasy"
        assert session.status == SessionStatus.ACTIVE
        assert session.total_turns == 0
        assert session.llm_provider == "anthropic"

    def test_create_game_session_with_name(self, db_session: Session):
        """Verify GameSession creation with custom name."""
        session = create_game_session(db_session, session_name="My Adventure")

        assert session.session_name == "My Adventure"

    def test_game_session_setting_options(self, db_session: Session):
        """Verify different setting options work."""
        for setting in ["fantasy", "contemporary", "scifi", "custom"]:
            session = create_game_session(db_session, setting=setting)
            assert session.setting == setting

    def test_game_session_status_values(self, db_session: Session):
        """Verify different status values work."""
        for status in [SessionStatus.ACTIVE, SessionStatus.PAUSED, SessionStatus.COMPLETED]:
            session = create_game_session(db_session, status=status)
            assert session.status == status

    def test_game_session_json_fields(self, db_session: Session):
        """Verify JSON fields work correctly."""
        attribute_schema = {"strength": {"min": 1, "max": 20}}
        equipment_slots = ["head", "chest", "hands"]
        session_context = {"current_scene": "tavern"}

        session = create_game_session(
            db_session,
            attribute_schema=attribute_schema,
            equipment_slots=equipment_slots,
            session_context=session_context,
        )

        db_session.refresh(session)

        assert session.attribute_schema == attribute_schema
        assert session.equipment_slots == equipment_slots
        assert session.session_context == session_context

    def test_game_session_turns_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify turns relationship works."""
        turn = create_turn(db_session, game_session)

        db_session.refresh(game_session)

        assert len(game_session.turns) == 1
        assert game_session.turns[0].id == turn.id

    def test_game_session_entities_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify entities relationship works."""
        entity = create_entity(db_session, game_session)

        db_session.refresh(game_session)

        assert len(game_session.entities) == 1
        assert game_session.entities[0].id == entity.id

    def test_game_session_player_entity_reference(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify player_entity_id foreign key works."""
        from src.database.models.enums import EntityType

        player = create_entity(
            db_session, game_session, entity_type=EntityType.PLAYER, entity_key="hero"
        )

        game_session.player_entity_id = player.id
        db_session.flush()
        db_session.refresh(game_session)

        assert game_session.player_entity_id == player.id

    def test_game_session_repr(self, db_session: Session):
        """Verify string representation."""
        session = create_game_session(db_session, session_name="Test Adventure")

        repr_str = repr(session)
        assert "GameSession" in repr_str
        assert "Test Adventure" in repr_str
        assert "fantasy" in repr_str

    def test_game_session_repr_unnamed(self, db_session: Session):
        """Verify repr handles unnamed sessions."""
        session = create_game_session(db_session, session_name=None)

        repr_str = repr(session)
        assert "Unnamed" in repr_str

    def test_game_session_timestamps(self, db_session: Session):
        """Verify timestamp mixin fields."""
        session = create_game_session(db_session)

        assert session.created_at is not None
        assert session.updated_at is not None
        assert session.last_activity is not None


class TestTurn:
    """Tests for Turn model."""

    def test_create_turn_required_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify Turn creation with required fields."""
        turn = Turn(
            session_id=game_session.id,
            turn_number=1,
            player_input="Hello",
            gm_response="Greetings, adventurer!",
        )
        db_session.add(turn)
        db_session.flush()

        assert turn.id is not None
        assert turn.session_id == game_session.id
        assert turn.turn_number == 1
        assert turn.player_input == "Hello"
        assert turn.gm_response == "Greetings, adventurer!"

    def test_turn_session_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify turn has back reference to session."""
        turn = create_turn(db_session, game_session)

        assert turn.session is not None
        assert turn.session.id == game_session.id

    def test_turn_requires_session_id(self, db_session: Session):
        """Verify turn requires valid session_id."""
        turn = Turn(
            session_id=99999,  # Non-existent
            turn_number=1,
            player_input="Test",
            gm_response="Response",
        )
        db_session.add(turn)

        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_turn_npc_dialogues_json(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify npc_dialogues JSON field works."""
        dialogues = [
            {"npc": "Joe", "dialogue": "Welcome!", "emotion": "friendly"},
            {"npc": "Guard", "dialogue": "Halt!", "emotion": "stern"},
        ]
        turn = create_turn(db_session, game_session, npc_dialogues=dialogues)

        db_session.refresh(turn)

        assert turn.npc_dialogues == dialogues
        assert len(turn.npc_dialogues) == 2

    def test_turn_context_snapshot_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify context snapshot fields."""
        turn = create_turn(
            db_session,
            game_session,
            location_at_turn="tavern",
            npcs_present_at_turn=["bartender_joe", "patron_1"],
            game_day_at_turn=1,
            game_time_at_turn="14:30",
        )

        db_session.refresh(turn)

        assert turn.location_at_turn == "tavern"
        assert turn.npcs_present_at_turn == ["bartender_joe", "patron_1"]
        assert turn.game_day_at_turn == 1
        assert turn.game_time_at_turn == "14:30"

    def test_turn_entities_extracted_json(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify entities_extracted JSON field."""
        extracted = {
            "new_npcs": ["mysterious_stranger"],
            "items_mentioned": ["ancient_sword"],
        }
        turn = create_turn(db_session, game_session, entities_extracted=extracted)

        db_session.refresh(turn)

        assert turn.entities_extracted == extracted

    def test_turn_world_events_json(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify world_events_generated JSON field."""
        events = [{"type": "npc_arrival", "details": {"npc": "merchant"}}]
        turn = create_turn(db_session, game_session, world_events_generated=events)

        db_session.refresh(turn)

        assert turn.world_events_generated == events

    def test_turn_created_at_immutable(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify turn has created_at but no updated_at (immutable)."""
        turn = create_turn(db_session, game_session)

        assert turn.created_at is not None
        # Turn should not have updated_at as it's immutable
        assert not hasattr(turn, "updated_at") or turn.updated_at is None

    def test_turn_repr(self, db_session: Session, game_session: GameSession):
        """Verify string representation."""
        turn = create_turn(db_session, game_session, turn_number=5)

        repr_str = repr(turn)
        assert "Turn" in repr_str
        assert str(game_session.id) in repr_str
        assert "5" in repr_str

    def test_turn_cascade_delete_with_session(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify turns are deleted when session is deleted."""
        turn = create_turn(db_session, game_session)
        turn_id = turn.id

        db_session.delete(game_session)
        db_session.flush()

        # Turn should no longer exist
        result = db_session.get(Turn, turn_id)
        assert result is None


class TestSessionTurnInteraction:
    """Tests for GameSession and Turn interaction."""

    def test_multiple_turns_per_session(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify multiple turns can exist per session."""
        turns = []
        for i in range(5):
            turn = create_turn(
                db_session,
                game_session,
                turn_number=i + 1,
                player_input=f"Action {i}",
                gm_response=f"Response {i}",
            )
            turns.append(turn)

        db_session.refresh(game_session)

        assert len(game_session.turns) == 5
        assert all(t.session_id == game_session.id for t in game_session.turns)

    def test_turns_ordered_by_turn_number(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify turns can be queried by turn_number."""
        # Create turns out of order
        create_turn(db_session, game_session, turn_number=3)
        create_turn(db_session, game_session, turn_number=1)
        create_turn(db_session, game_session, turn_number=2)

        # Query in order
        turns = (
            db_session.query(Turn)
            .filter(Turn.session_id == game_session.id)
            .order_by(Turn.turn_number)
            .all()
        )

        assert [t.turn_number for t in turns] == [1, 2, 3]
