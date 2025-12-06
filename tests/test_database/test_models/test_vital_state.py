"""Tests for EntityVitalState model."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.database.models.enums import VitalStatus
from src.database.models.session import GameSession
from src.database.models.vital_state import EntityVitalState
from tests.factories import (
    create_entity,
    create_entity_vital_state,
    create_game_session,
)


class TestEntityVitalState:
    """Tests for EntityVitalState model."""

    def test_create_vital_state_required_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify EntityVitalState creation with required fields."""
        entity = create_entity(db_session, game_session)
        state = EntityVitalState(
            entity_id=entity.id,
            session_id=game_session.id,
        )
        db_session.add(state)
        db_session.flush()

        assert state.id is not None
        assert state.entity_id == entity.id
        assert state.session_id == game_session.id

    def test_vital_state_one_to_one(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify unique entity_id constraint."""
        entity = create_entity(db_session, game_session)
        create_entity_vital_state(db_session, game_session, entity)

        with pytest.raises(IntegrityError):
            create_entity_vital_state(db_session, game_session, entity)

    def test_vital_status_enum(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify VitalStatus enum storage."""
        for status in VitalStatus:
            entity = create_entity(db_session, game_session)
            state = create_entity_vital_state(
                db_session, game_session, entity, vital_status=status
            )
            db_session.refresh(state)
            assert state.vital_status == status

    def test_vital_status_default(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify default vital status is HEALTHY."""
        entity = create_entity(db_session, game_session)
        state = EntityVitalState(
            entity_id=entity.id,
            session_id=game_session.id,
        )
        db_session.add(state)
        db_session.flush()

        assert state.vital_status == VitalStatus.HEALTHY

    def test_death_saves_defaults(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify death saves default values."""
        entity = create_entity(db_session, game_session)
        state = create_entity_vital_state(db_session, game_session, entity)

        assert state.death_saves_remaining == 3
        assert state.death_saves_failed == 0

    def test_death_saves_tracking(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify death saves can be tracked."""
        entity = create_entity(db_session, game_session)
        state = create_entity_vital_state(
            db_session,
            game_session,
            entity,
            vital_status=VitalStatus.DYING,
            death_saves_remaining=1,
            death_saves_failed=2,
        )

        db_session.refresh(state)

        assert state.death_saves_remaining == 1
        assert state.death_saves_failed == 2

    def test_stabilization(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify stabilization fields."""
        entity = create_entity(db_session, game_session)
        state = create_entity_vital_state(
            db_session,
            game_session,
            entity,
            vital_status=VitalStatus.CRITICAL,
            stabilized_turn=15,
        )

        db_session.refresh(state)

        assert state.stabilized_turn == 15

    def test_death_record(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify death record fields."""
        entity = create_entity(db_session, game_session)
        state = create_entity_vital_state(
            db_session,
            game_session,
            entity,
            vital_status=VitalStatus.DEAD,
            is_dead=True,
            death_turn=25,
            death_cause="combat",
            death_description="Slain by the dragon's fire breath.",
            death_location="dragon_lair",
        )

        db_session.refresh(state)

        assert state.is_dead is True
        assert state.death_turn == 25
        assert state.death_cause == "combat"
        assert "dragon" in state.death_description
        assert state.death_location == "dragon_lair"

    def test_revival_record(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify revival record fields."""
        entity = create_entity(db_session, game_session)
        state = create_entity_vital_state(
            db_session,
            game_session,
            entity,
            vital_status=VitalStatus.WOUNDED,
            has_been_revived=True,
            revival_count=2,
            last_revival_turn=30,
            revival_method="resurrection_spell",
            revival_cost="500 gold and diamond dust",
        )

        db_session.refresh(state)

        assert state.has_been_revived is True
        assert state.revival_count == 2
        assert state.last_revival_turn == 30
        assert state.revival_method == "resurrection_spell"
        assert "diamond dust" in state.revival_cost

    def test_scifi_backup(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify sci-fi consciousness backup fields."""
        entity = create_entity(db_session, game_session)
        state = create_entity_vital_state(
            db_session,
            game_session,
            entity,
            has_consciousness_backup=True,
            last_backup_turn=20,
            backup_location="orbital_station_alpha",
        )

        db_session.refresh(state)

        assert state.has_consciousness_backup is True
        assert state.last_backup_turn == 20
        assert state.backup_location == "orbital_station_alpha"

    def test_vital_state_entity_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify vital state has back reference to entity."""
        entity = create_entity(db_session, game_session)
        state = create_entity_vital_state(db_session, game_session, entity)

        assert state.entity is not None
        assert state.entity.id == entity.id

    def test_vital_state_cascade_delete(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify vital state deleted when entity is deleted."""
        entity = create_entity(db_session, game_session)
        state = create_entity_vital_state(db_session, game_session, entity)
        state_id = state.id

        db_session.delete(entity)
        db_session.flush()
        db_session.expire_all()

        result = db_session.query(EntityVitalState).filter(
            EntityVitalState.id == state_id
        ).first()
        assert result is None

    def test_vital_state_repr_healthy(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation for healthy entity."""
        entity = create_entity(db_session, game_session)
        state = create_entity_vital_state(
            db_session, game_session, entity, vital_status=VitalStatus.HEALTHY
        )

        repr_str = repr(state)
        assert "EntityVitalState" in repr_str
        assert "healthy" in repr_str

    def test_vital_state_repr_dead(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation for dead entity."""
        entity = create_entity(db_session, game_session)
        state = create_entity_vital_state(
            db_session, game_session, entity, vital_status=VitalStatus.DEAD, is_dead=True
        )

        repr_str = repr(state)
        assert "DEAD" in repr_str

    def test_vital_state_repr_revived(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation includes revival count."""
        entity = create_entity(db_session, game_session)
        state = create_entity_vital_state(
            db_session,
            game_session,
            entity,
            vital_status=VitalStatus.DEAD,
            is_dead=True,
            has_been_revived=True,
            revival_count=3,
        )

        repr_str = repr(state)
        assert "revived 3x" in repr_str
