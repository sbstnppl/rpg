"""Tests for DeathManager class."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.enums import VitalStatus
from src.database.models.mental_state import MentalCondition
from src.database.models.session import GameSession
from src.database.models.vital_state import EntityVitalState
from src.managers.death import DeathManager
from tests.factories import (
    create_entity,
    create_entity_vital_state,
)


class TestDeathManagerBasics:
    """Tests for DeathManager basic operations."""

    def test_get_vital_state_returns_none_when_missing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_vital_state returns None when not exists."""
        entity = create_entity(db_session, game_session)
        manager = DeathManager(db_session, game_session)

        result = manager.get_vital_state(entity.id)

        assert result is None

    def test_get_vital_state_returns_existing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_vital_state returns existing state."""
        entity = create_entity(db_session, game_session)
        state = create_entity_vital_state(
            db_session, game_session, entity,
            vital_status=VitalStatus.WOUNDED,
        )
        manager = DeathManager(db_session, game_session)

        result = manager.get_vital_state(entity.id)

        assert result is not None
        assert result.vital_status == VitalStatus.WOUNDED

    def test_get_or_create_vital_state_creates_when_missing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_or_create creates new state."""
        entity = create_entity(db_session, game_session)
        manager = DeathManager(db_session, game_session)

        result = manager.get_or_create_vital_state(entity.id)

        assert result is not None
        assert result.entity_id == entity.id
        assert result.vital_status == VitalStatus.HEALTHY

    def test_get_or_create_vital_state_returns_existing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_or_create returns existing state."""
        entity = create_entity(db_session, game_session)
        state = create_entity_vital_state(
            db_session, game_session, entity,
            vital_status=VitalStatus.CRITICAL,
        )
        manager = DeathManager(db_session, game_session)

        result = manager.get_or_create_vital_state(entity.id)

        assert result.id == state.id
        assert result.vital_status == VitalStatus.CRITICAL


class TestSetVitalStatus:
    """Tests for setting vital status."""

    def test_set_vital_status_updates_status(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify set_vital_status updates the status."""
        entity = create_entity(db_session, game_session)
        create_entity_vital_state(db_session, game_session, entity)
        manager = DeathManager(db_session, game_session)

        result = manager.set_vital_status(entity.id, VitalStatus.WOUNDED)

        assert result.vital_status == VitalStatus.WOUNDED

    def test_set_vital_status_dead_marks_death(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify setting DEAD status records death info."""
        entity = create_entity(db_session, game_session)
        create_entity_vital_state(db_session, game_session, entity)
        manager = DeathManager(db_session, game_session)

        result = manager.set_vital_status(
            entity.id, VitalStatus.DEAD, cause="Combat"
        )

        assert result.is_dead is True
        assert result.death_cause == "Combat"
        assert result.death_turn is not None
        assert result.death_timestamp is not None

    def test_set_vital_status_dead_updates_entity(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify setting DEAD updates entity.is_alive."""
        entity = create_entity(db_session, game_session)
        create_entity_vital_state(db_session, game_session, entity)
        manager = DeathManager(db_session, game_session)

        manager.set_vital_status(entity.id, VitalStatus.DEAD)

        db_session.refresh(entity)
        assert entity.is_alive is False

    def test_set_vital_status_dying_resets_death_saves(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify setting DYING resets death saves."""
        entity = create_entity(db_session, game_session)
        state = create_entity_vital_state(
            db_session, game_session, entity,
            death_saves_remaining=1,
            death_saves_failed=2,
        )
        manager = DeathManager(db_session, game_session)

        result = manager.set_vital_status(entity.id, VitalStatus.DYING)

        assert result.death_saves_remaining == 3
        assert result.death_saves_failed == 0


class TestTakeDamage:
    """Tests for damage processing."""

    def test_take_damage_massive_instant_death(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify massive damage causes instant death."""
        entity = create_entity(db_session, game_session)
        create_entity_vital_state(db_session, game_session, entity)
        manager = DeathManager(db_session, game_session)

        status, hp, injury = manager.take_damage(
            entity.id,
            damage=150,
            current_hp=50,
            max_hp=50,
            create_injury=False,
        )

        # Damage > 2x max HP = instant death
        assert status == VitalStatus.DEAD
        assert hp == 0

    def test_take_damage_zero_hp_dying(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify dropping to 0 HP causes dying status."""
        entity = create_entity(db_session, game_session)
        create_entity_vital_state(db_session, game_session, entity)
        manager = DeathManager(db_session, game_session)

        status, hp, _ = manager.take_damage(
            entity.id,
            damage=50,
            current_hp=50,
            max_hp=100,
            create_injury=False,
        )

        assert status == VitalStatus.DYING
        assert hp == 0

    def test_take_damage_critical_threshold(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify critical status when HP < 25%."""
        entity = create_entity(db_session, game_session)
        create_entity_vital_state(db_session, game_session, entity)
        manager = DeathManager(db_session, game_session)

        status, hp, _ = manager.take_damage(
            entity.id,
            damage=60,
            current_hp=80,
            max_hp=100,
            create_injury=False,
        )

        # 20 HP remaining = 20% = critical
        assert status == VitalStatus.CRITICAL
        assert hp == 20

    def test_take_damage_wounded_threshold(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify wounded status when HP 25-50%."""
        entity = create_entity(db_session, game_session)
        create_entity_vital_state(db_session, game_session, entity)
        manager = DeathManager(db_session, game_session)

        status, hp, _ = manager.take_damage(
            entity.id,
            damage=60,
            current_hp=100,
            max_hp=100,
            create_injury=False,
        )

        # 40 HP remaining = 40% = wounded
        assert status == VitalStatus.WOUNDED
        assert hp == 40

    def test_take_damage_stays_healthy_above_50(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify stays healthy when HP > 50%."""
        entity = create_entity(db_session, game_session)
        create_entity_vital_state(db_session, game_session, entity)
        manager = DeathManager(db_session, game_session)

        status, hp, _ = manager.take_damage(
            entity.id,
            damage=40,
            current_hp=100,
            max_hp=100,
            create_injury=False,
        )

        # 60 HP remaining = 60% = healthy
        assert status == VitalStatus.HEALTHY
        assert hp == 60


class TestDeathSaves:
    """Tests for death saving throws."""

    def test_make_death_save_success(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify successful death save."""
        entity = create_entity(db_session, game_session)
        create_entity_vital_state(
            db_session, game_session, entity,
            vital_status=VitalStatus.DYING,
        )
        manager = DeathManager(db_session, game_session)

        result = manager.make_death_save(entity.id, roll=15, dc=10)

        assert result.success is True
        assert result.saves_remaining == 2  # Used one success

    def test_make_death_save_failure(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify failed death save."""
        entity = create_entity(db_session, game_session)
        create_entity_vital_state(
            db_session, game_session, entity,
            vital_status=VitalStatus.DYING,
        )
        manager = DeathManager(db_session, game_session)

        result = manager.make_death_save(entity.id, roll=5, dc=10)

        assert result.success is False
        assert result.saves_failed == 1

    def test_make_death_save_natural_20_stabilizes(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify natural 20 immediately stabilizes."""
        entity = create_entity(db_session, game_session)
        create_entity_vital_state(
            db_session, game_session, entity,
            vital_status=VitalStatus.DYING,
        )
        manager = DeathManager(db_session, game_session)

        result = manager.make_death_save(entity.id, roll=20, dc=10)

        assert result.stabilized is True
        assert result.died is False

    def test_make_death_save_natural_1_double_failure(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify natural 1 counts as 2 failures."""
        entity = create_entity(db_session, game_session)
        create_entity_vital_state(
            db_session, game_session, entity,
            vital_status=VitalStatus.DYING,
        )
        manager = DeathManager(db_session, game_session)

        result = manager.make_death_save(entity.id, roll=1, dc=10)

        assert result.saves_failed == 2

    def test_make_death_save_three_failures_death(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify 3 failures causes death."""
        entity = create_entity(db_session, game_session)
        create_entity_vital_state(
            db_session, game_session, entity,
            vital_status=VitalStatus.DYING,
            death_saves_failed=2,
        )
        manager = DeathManager(db_session, game_session)

        result = manager.make_death_save(entity.id, roll=5, dc=10)

        assert result.died is True
        assert result.saves_failed == 3

    def test_make_death_save_three_successes_stabilize(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify 3 successes stabilizes."""
        entity = create_entity(db_session, game_session)
        create_entity_vital_state(
            db_session, game_session, entity,
            vital_status=VitalStatus.DYING,
            death_saves_remaining=1,
        )
        manager = DeathManager(db_session, game_session)

        result = manager.make_death_save(entity.id, roll=15, dc=10)

        assert result.stabilized is True
        assert result.saves_remaining == 0


class TestStabilize:
    """Tests for stabilization."""

    def test_stabilize_dying_entity(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify stabilize works on dying entity."""
        entity = create_entity(db_session, game_session)
        create_entity_vital_state(
            db_session, game_session, entity,
            vital_status=VitalStatus.DYING,
        )
        manager = DeathManager(db_session, game_session)

        result = manager.stabilize(entity.id)

        assert result is True
        state = manager.get_vital_state(entity.id)
        assert state.vital_status == VitalStatus.CRITICAL

    def test_stabilize_non_dying_fails(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify stabilize fails if not dying."""
        entity = create_entity(db_session, game_session)
        create_entity_vital_state(
            db_session, game_session, entity,
            vital_status=VitalStatus.WOUNDED,
        )
        manager = DeathManager(db_session, game_session)

        result = manager.stabilize(entity.id)

        assert result is False


class TestRevival:
    """Tests for revival mechanics."""

    def test_attempt_revival_not_dead_fails(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify revival fails if target not dead."""
        entity = create_entity(db_session, game_session)
        create_entity_vital_state(
            db_session, game_session, entity,
            vital_status=VitalStatus.CRITICAL,
        )
        manager = DeathManager(db_session, game_session, setting="fantasy")

        result = manager.attempt_revival(entity.id, "raise_dead")

        assert result.success is False
        assert "not dead" in result.consequences[0].lower()

    def test_attempt_revival_permanently_dead_fails(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify revival fails on permanently dead."""
        entity = create_entity(db_session, game_session)
        create_entity_vital_state(
            db_session, game_session, entity,
            vital_status=VitalStatus.PERMANENTLY_DEAD,
            is_dead=True,
        )
        manager = DeathManager(db_session, game_session, setting="fantasy")

        result = manager.attempt_revival(entity.id, "true_resurrection")

        assert result.success is False

    def test_attempt_revival_fantasy_success(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify fantasy revival succeeds."""
        entity = create_entity(db_session, game_session)
        create_entity_vital_state(
            db_session, game_session, entity,
            vital_status=VitalStatus.DEAD,
            is_dead=True,
        )
        manager = DeathManager(db_session, game_session, setting="fantasy")

        result = manager.attempt_revival(
            entity.id, "resurrection", materials_available=True
        )

        assert result.success is True
        assert result.new_status == VitalStatus.CRITICAL
        # Check entity is now alive
        db_session.refresh(entity)
        assert entity.is_alive is True

    def test_attempt_revival_adds_trauma(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify revival adds PTSD condition."""
        entity = create_entity(db_session, game_session)
        create_entity_vital_state(
            db_session, game_session, entity,
            vital_status=VitalStatus.DEAD,
            is_dead=True,
        )
        manager = DeathManager(db_session, game_session, setting="fantasy")

        manager.attempt_revival(entity.id, "resurrection", materials_available=True)

        # Check PTSD was added
        ptsd = (
            db_session.query(MentalCondition)
            .filter(MentalCondition.entity_id == entity.id)
            .first()
        )
        assert ptsd is not None

    def test_attempt_revival_scifi_no_backup_fails(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify sci-fi revival fails without backup."""
        entity = create_entity(db_session, game_session)
        create_entity_vital_state(
            db_session, game_session, entity,
            vital_status=VitalStatus.DEAD,
            is_dead=True,
            has_consciousness_backup=False,
        )
        manager = DeathManager(db_session, game_session, setting="scifi")

        result = manager.attempt_revival(entity.id, "clone_restore")

        assert result.success is False

    def test_attempt_revival_scifi_with_backup_success(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify sci-fi revival succeeds with backup."""
        entity = create_entity(db_session, game_session)
        create_entity_vital_state(
            db_session, game_session, entity,
            vital_status=VitalStatus.DEAD,
            is_dead=True,
            has_consciousness_backup=True,
            last_backup_turn=5,
        )
        game_session.total_turns = 10
        manager = DeathManager(db_session, game_session, setting="scifi")

        result = manager.attempt_revival(entity.id, "clone_restore")

        assert result.success is True
        assert result.new_status == VitalStatus.HEALTHY
        # Should have memory loss consequence
        assert any("memories" in c.lower() for c in result.consequences)


class TestConsciousnessBackup:
    """Tests for sci-fi consciousness backup."""

    def test_create_backup_scifi_setting(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify backup creation in sci-fi setting."""
        entity = create_entity(db_session, game_session)
        create_entity_vital_state(db_session, game_session, entity)
        manager = DeathManager(db_session, game_session, setting="scifi")

        result = manager.create_backup(entity.id, "orbital_station")

        assert result is True
        state = manager.get_vital_state(entity.id)
        assert state.has_consciousness_backup is True
        assert state.backup_location == "orbital_station"

    def test_create_backup_non_scifi_fails(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify backup fails in non-sci-fi settings."""
        entity = create_entity(db_session, game_session)
        create_entity_vital_state(db_session, game_session, entity)
        manager = DeathManager(db_session, game_session, setting="fantasy")

        result = manager.create_backup(entity.id, "temple")

        assert result is False


class TestVitalSummary:
    """Tests for vital state summary."""

    def test_get_vital_summary_no_state(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify summary when no state exists."""
        entity = create_entity(db_session, game_session)
        manager = DeathManager(db_session, game_session)

        summary = manager.get_vital_summary(entity.id)

        assert summary["has_vital_state"] is False
        assert summary["status"] == "healthy"

    def test_get_vital_summary_with_state(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify complete vital summary."""
        entity = create_entity(db_session, game_session)
        create_entity_vital_state(
            db_session, game_session, entity,
            vital_status=VitalStatus.DYING,
            death_saves_remaining=2,
            death_saves_failed=1,
        )
        manager = DeathManager(db_session, game_session)

        summary = manager.get_vital_summary(entity.id)

        assert summary["has_vital_state"] is True
        assert summary["status"] == "dying"
        assert summary["death_saves_remaining"] == 2
        assert summary["death_saves_failed"] == 1
