"""Tests for the NeedsCommunicationManager."""

from datetime import datetime, timedelta

import pytest

from src.database.models.character_state import CharacterNeeds, NeedsCommunicationLog
from src.managers.needs_communication_manager import (
    NeedAlert,
    NeedsCommunicationManager,
    NEED_STATE_THRESHOLDS,
    REMINDER_INTERVAL_HOURS,
)
from tests.factories import create_entity


class TestGetStateLabel:
    """Tests for get_state_label method."""

    def test_hunger_hungry_state(self, db_session, game_session):
        """Test hunger value below threshold returns hungry."""
        manager = NeedsCommunicationManager(db_session, game_session)
        label, is_negative = manager.get_state_label("hunger", 25)
        assert label == "hungry"
        assert is_negative is True

    def test_hunger_starving_state(self, db_session, game_session):
        """Test hunger value far below threshold returns starving."""
        manager = NeedsCommunicationManager(db_session, game_session)
        label, is_negative = manager.get_state_label("hunger", 10)
        assert label == "starving"
        assert is_negative is True

    def test_hunger_well_fed_state(self, db_session, game_session):
        """Test hunger value above positive threshold returns well-fed."""
        manager = NeedsCommunicationManager(db_session, game_session)
        label, is_negative = manager.get_state_label("hunger", 90)
        assert label == "well-fed"
        assert is_negative is False

    def test_hunger_normal_state(self, db_session, game_session):
        """Test hunger in middle range returns normal."""
        manager = NeedsCommunicationManager(db_session, game_session)
        label, is_negative = manager.get_state_label("hunger", 50)
        assert label == "normal"
        assert is_negative is False

    def test_energy_exhausted_state(self, db_session, game_session):
        """Test energy value below threshold returns exhausted."""
        manager = NeedsCommunicationManager(db_session, game_session)
        label, is_negative = manager.get_state_label("energy", 15)
        assert label == "exhausted"
        assert is_negative is True

    def test_unknown_need_returns_normal(self, db_session, game_session):
        """Test unknown need name returns normal state."""
        manager = NeedsCommunicationManager(db_session, game_session)
        label, is_negative = manager.get_state_label("unknown_need", 50)
        assert label == "normal"
        assert is_negative is False


class TestRecordCommunication:
    """Tests for record_communication method."""

    def test_create_new_communication_record(self, db_session, game_session):
        """Test creating a new communication record."""
        entity = create_entity(db_session, game_session)
        manager = NeedsCommunicationManager(db_session, game_session)

        game_time = datetime(2000, 1, 5, 14, 30)
        log = manager.record_communication(
            entity_id=entity.id,
            need_name="hunger",
            value=25,
            state_label="hungry",
            game_time=game_time,
            turn=5,
        )

        assert log.entity_id == entity.id
        assert log.need_name == "hunger"
        assert log.communicated_value == 25
        assert log.communicated_state == "hungry"
        assert log.communicated_turn == 5
        assert log.communicated_game_time == game_time

    def test_update_existing_communication_record(self, db_session, game_session):
        """Test updating an existing communication record."""
        entity = create_entity(db_session, game_session)
        manager = NeedsCommunicationManager(db_session, game_session)

        # Create initial record
        game_time1 = datetime(2000, 1, 5, 14, 30)
        manager.record_communication(
            entity_id=entity.id,
            need_name="hunger",
            value=25,
            state_label="hungry",
            game_time=game_time1,
            turn=5,
        )

        # Update with new values
        game_time2 = datetime(2000, 1, 5, 17, 0)
        log = manager.record_communication(
            entity_id=entity.id,
            need_name="hunger",
            value=10,
            state_label="starving",
            game_time=game_time2,
            turn=8,
        )

        # Should have updated, not created new
        count = db_session.query(NeedsCommunicationLog).filter(
            NeedsCommunicationLog.entity_id == entity.id,
            NeedsCommunicationLog.need_name == "hunger",
        ).count()
        assert count == 1
        assert log.communicated_value == 10
        assert log.communicated_state == "starving"
        assert log.communicated_turn == 8


class TestGetCommunicationLog:
    """Tests for get_communication_log method."""

    def test_get_empty_log(self, db_session, game_session):
        """Test getting log for entity with no records."""
        entity = create_entity(db_session, game_session)
        manager = NeedsCommunicationManager(db_session, game_session)

        log = manager.get_communication_log(entity.id)
        assert log == {}

    def test_get_existing_logs(self, db_session, game_session):
        """Test getting existing communication logs."""
        entity = create_entity(db_session, game_session)
        manager = NeedsCommunicationManager(db_session, game_session)

        game_time = datetime(2000, 1, 5, 14, 30)
        manager.record_communication(
            entity_id=entity.id,
            need_name="hunger",
            value=25,
            state_label="hungry",
            game_time=game_time,
            turn=5,
        )
        manager.record_communication(
            entity_id=entity.id,
            need_name="energy",
            value=35,
            state_label="tired",
            game_time=game_time,
            turn=5,
        )

        log = manager.get_communication_log(entity.id)
        assert "hunger" in log
        assert "energy" in log
        assert log["hunger"].communicated_state == "hungry"
        assert log["energy"].communicated_state == "tired"


class TestGetNeedsAlerts:
    """Tests for get_needs_alerts method."""

    def test_state_change_alert(self, db_session, game_session):
        """Test alert generated when state changes."""
        entity = create_entity(db_session, game_session)
        manager = NeedsCommunicationManager(db_session, game_session)

        # Create needs record
        needs = CharacterNeeds(
            entity_id=entity.id,
            session_id=game_session.id,
            hunger=25,  # hungry state
            stamina=80,
        )
        db_session.add(needs)
        db_session.flush()

        # Record previous communication as satisfied
        game_time = datetime(2000, 1, 5, 10, 0)
        manager.record_communication(
            entity_id=entity.id,
            need_name="hunger",
            value=60,
            state_label="normal",
            game_time=game_time,
            turn=1,
        )

        # Get alerts at later time
        current_time = datetime(2000, 1, 5, 12, 0)
        alerts = manager.get_needs_alerts(
            entity_id=entity.id,
            needs=needs,
            current_game_time=current_time,
            current_turn=3,
        )

        # Should have a state change alert for hunger
        hunger_alerts = [a for a in alerts if a.need_name == "hunger"]
        assert len(hunger_alerts) == 1
        assert hunger_alerts[0].alert_type == "state_change"
        assert hunger_alerts[0].current_state == "hungry"
        assert hunger_alerts[0].previous_state == "normal"

    def test_reminder_alert_after_time_elapsed(self, db_session, game_session):
        """Test reminder generated when time has elapsed."""
        entity = create_entity(db_session, game_session)
        manager = NeedsCommunicationManager(db_session, game_session)

        # Create needs record
        needs = CharacterNeeds(
            entity_id=entity.id,
            session_id=game_session.id,
            hunger=25,  # hungry state
        )
        db_session.add(needs)
        db_session.flush()

        # Record communication 3 hours ago (same state)
        old_time = datetime(2000, 1, 5, 10, 0)
        manager.record_communication(
            entity_id=entity.id,
            need_name="hunger",
            value=28,
            state_label="hungry",
            game_time=old_time,
            turn=1,
        )

        # Get alerts 3 hours later (exceeds REMINDER_INTERVAL_HOURS)
        current_time = datetime(2000, 1, 5, 13, 0)
        alerts = manager.get_needs_alerts(
            entity_id=entity.id,
            needs=needs,
            current_game_time=current_time,
            current_turn=10,
        )

        # Should have a reminder for hunger
        hunger_alerts = [a for a in alerts if a.need_name == "hunger"]
        assert len(hunger_alerts) == 1
        assert hunger_alerts[0].alert_type == "reminder"
        assert hunger_alerts[0].hours_since_mentioned == 3.0

    def test_no_reminder_if_time_not_elapsed(self, db_session, game_session):
        """Test no reminder if within time threshold."""
        entity = create_entity(db_session, game_session)
        manager = NeedsCommunicationManager(db_session, game_session)

        # Create needs record
        needs = CharacterNeeds(
            entity_id=entity.id,
            session_id=game_session.id,
            hunger=25,  # hungry state
        )
        db_session.add(needs)
        db_session.flush()

        # Record communication 30 minutes ago
        old_time = datetime(2000, 1, 5, 10, 0)
        manager.record_communication(
            entity_id=entity.id,
            need_name="hunger",
            value=28,
            state_label="hungry",
            game_time=old_time,
            turn=1,
        )

        # Get alerts 30 minutes later
        current_time = datetime(2000, 1, 5, 10, 30)
        alerts = manager.get_needs_alerts(
            entity_id=entity.id,
            needs=needs,
            current_game_time=current_time,
            current_turn=2,
        )

        # Should NOT have any alert for hunger (still in same state, not enough time)
        hunger_alerts = [a for a in alerts if a.need_name == "hunger"]
        assert len(hunger_alerts) == 0

    def test_new_negative_state_generates_alert(self, db_session, game_session):
        """Test new negative state without prior communication generates alert."""
        entity = create_entity(db_session, game_session)
        manager = NeedsCommunicationManager(db_session, game_session)

        # Create needs record with negative states
        needs = CharacterNeeds(
            entity_id=entity.id,
            session_id=game_session.id,
            hunger=10,  # starving
            stamina=15,  # exhausted
        )
        db_session.add(needs)
        db_session.flush()

        # No prior communication - get alerts
        current_time = datetime(2000, 1, 5, 12, 0)
        alerts = manager.get_needs_alerts(
            entity_id=entity.id,
            needs=needs,
            current_game_time=current_time,
            current_turn=1,
        )

        # Should have state_change alerts for both negative needs
        alert_types = {a.need_name: a.alert_type for a in alerts if a.alert_type == "state_change"}
        assert "hunger" in alert_types
        assert "energy" in alert_types


class TestFormatAlertsForGm:
    """Tests for format_alerts_for_gm method."""

    def test_format_with_alerts_and_reminders(self, db_session, game_session):
        """Test formatting with mixed alert types."""
        manager = NeedsCommunicationManager(db_session, game_session)

        alerts = [
            NeedAlert(
                need_name="hunger",
                current_state="hungry",
                current_value=25,
                previous_state="normal",
                alert_type="state_change",
                is_improvement=False,
            ),
            NeedAlert(
                need_name="energy",
                current_state="tired",
                current_value=35,
                previous_state="tired",
                alert_type="reminder",
                hours_since_mentioned=3.0,
            ),
            NeedAlert(
                need_name="hygiene",
                current_state="clean",
                current_value=85,
                previous_state=None,
                alert_type="status",
            ),
        ]

        output = manager.format_alerts_for_gm(alerts, "Hero")

        assert "## Needs Alerts" in output
        assert "hunger dropped to 'hungry'" in output
        assert "## Needs Reminders" in output
        assert "energy: still tired" in output
        assert "3h since mentioned" in output
        assert "## Needs Status" in output
        assert "hygiene: clean" in output

    def test_format_empty_alerts(self, db_session, game_session):
        """Test formatting with no alerts."""
        manager = NeedsCommunicationManager(db_session, game_session)
        output = manager.format_alerts_for_gm([], "Hero")
        assert output == ""

    def test_format_improvement_alert(self, db_session, game_session):
        """Test formatting improvement alerts."""
        manager = NeedsCommunicationManager(db_session, game_session)

        alerts = [
            NeedAlert(
                need_name="hunger",
                current_state="well-fed",
                current_value=90,
                previous_state="hungry",
                alert_type="state_change",
                is_improvement=True,
            ),
        ]

        output = manager.format_alerts_for_gm(alerts, "Hero")

        assert "hunger improved to 'well-fed'" in output
