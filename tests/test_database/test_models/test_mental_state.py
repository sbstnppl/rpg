"""Tests for MentalCondition and GriefCondition models."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.database.models.enums import GriefStage, MentalConditionType
from src.database.models.mental_state import GriefCondition, MentalCondition
from src.database.models.session import GameSession
from tests.factories import (
    create_entity,
    create_game_session,
    create_grief_condition,
    create_mental_condition,
)


class TestMentalCondition:
    """Tests for MentalCondition model."""

    def test_create_mental_condition_required_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify MentalCondition creation with required fields."""
        entity = create_entity(db_session, game_session)
        condition = MentalCondition(
            entity_id=entity.id,
            session_id=game_session.id,
            condition_type=MentalConditionType.ANXIETY,
            acquired_turn=5,
            acquired_reason="Witnessed a traumatic event",
        )
        db_session.add(condition)
        db_session.flush()

        assert condition.id is not None
        assert condition.entity_id == entity.id
        assert condition.condition_type == MentalConditionType.ANXIETY

    def test_mental_condition_type_enum(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify MentalConditionType enum storage."""
        entity = create_entity(db_session, game_session)
        for condition_type in MentalConditionType:
            condition = create_mental_condition(
                db_session, game_session, entity, condition_type=condition_type
            )
            db_session.refresh(condition)
            assert condition.condition_type == condition_type

    def test_mental_condition_severity(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify severity 0-100 scale."""
        entity = create_entity(db_session, game_session)
        condition = create_mental_condition(
            db_session, game_session, entity, severity=75
        )

        db_session.refresh(condition)
        assert condition.severity == 75

    def test_mental_condition_permanence(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify is_permanent and is_active flags."""
        entity = create_entity(db_session, game_session)
        condition = create_mental_condition(
            db_session,
            game_session,
            entity,
            is_permanent=True,
            is_active=True,
        )

        db_session.refresh(condition)

        assert condition.is_permanent is True
        assert condition.is_active is True

    def test_mental_condition_triggers_json(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify trigger_description and triggers JSON field."""
        entity = create_entity(db_session, game_session)
        triggers = {
            "keywords": ["spider", "arachnid"],
            "locations": ["dark_cellar", "cave"],
            "situations": ["being alone", "cramped spaces"],
        }
        condition = create_mental_condition(
            db_session,
            game_session,
            entity,
            condition_type=MentalConditionType.PHOBIA,
            trigger_description="Fear of spiders",
            triggers=triggers,
        )

        db_session.refresh(condition)

        assert condition.trigger_description == "Fear of spiders"
        assert condition.triggers == triggers
        assert "spider" in condition.triggers["keywords"]

    def test_mental_condition_effects_json(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify stat_penalties and behavioral_effects JSON fields."""
        entity = create_entity(db_session, game_session)
        penalties = {"morale": -20, "WIS": -2, "all_checks": -3}
        behaviors = {"flee_impulse": 0.7, "panic_chance": 0.3}
        condition = create_mental_condition(
            db_session,
            game_session,
            entity,
            stat_penalties=penalties,
            behavioral_effects=behaviors,
        )

        db_session.refresh(condition)

        assert condition.stat_penalties == penalties
        assert condition.stat_penalties["morale"] == -20
        assert condition.behavioral_effects["panic_chance"] == 0.3

    def test_mental_condition_treatment(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify treatment fields."""
        entity = create_entity(db_session, game_session)
        condition = create_mental_condition(
            db_session,
            game_session,
            entity,
            can_be_treated=True,
            treatment_progress=60,
            treatment_notes="Regular therapy sessions showing progress",
        )

        db_session.refresh(condition)

        assert condition.can_be_treated is True
        assert condition.treatment_progress == 60
        assert "therapy" in condition.treatment_notes

    def test_mental_condition_resolution(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify resolved_turn and resolved_at fields."""
        entity = create_entity(db_session, game_session)
        condition = create_mental_condition(
            db_session, game_session, entity, is_active=False
        )

        condition.resolved_turn = 50
        db_session.flush()
        db_session.refresh(condition)

        assert condition.resolved_turn == 50

    def test_mental_condition_entity_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify condition has back reference to entity."""
        entity = create_entity(db_session, game_session)
        condition = create_mental_condition(db_session, game_session, entity)

        assert condition.entity is not None
        assert condition.entity.id == entity.id

    def test_mental_condition_cascade_delete(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify condition deleted when entity is deleted."""
        entity = create_entity(db_session, game_session)
        condition = create_mental_condition(db_session, game_session, entity)
        condition_id = condition.id

        db_session.delete(entity)
        db_session.flush()
        db_session.expire_all()

        result = db_session.query(MentalCondition).filter(
            MentalCondition.id == condition_id
        ).first()
        assert result is None

    def test_mental_condition_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        entity = create_entity(db_session, game_session)
        condition = create_mental_condition(
            db_session,
            game_session,
            entity,
            condition_type=MentalConditionType.PTSD_COMBAT,
            severity=70,
        )

        repr_str = repr(condition)
        assert "MentalCondition" in repr_str
        assert "ptsd_combat" in repr_str
        assert "70" in repr_str

    def test_mental_condition_repr_permanent(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify repr includes PERMANENT marker."""
        entity = create_entity(db_session, game_session)
        condition = create_mental_condition(
            db_session, game_session, entity, is_permanent=True
        )

        repr_str = repr(condition)
        assert "PERMANENT" in repr_str

    def test_mental_condition_repr_inactive(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify repr includes INACTIVE marker."""
        entity = create_entity(db_session, game_session)
        condition = create_mental_condition(
            db_session, game_session, entity, is_active=False
        )

        repr_str = repr(condition)
        assert "INACTIVE" in repr_str

    def test_multiple_conditions_per_entity(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify entity can have multiple conditions."""
        entity = create_entity(db_session, game_session)

        create_mental_condition(
            db_session, game_session, entity, condition_type=MentalConditionType.ANXIETY
        )
        create_mental_condition(
            db_session, game_session, entity, condition_type=MentalConditionType.DEPRESSION
        )
        create_mental_condition(
            db_session, game_session, entity, condition_type=MentalConditionType.PHOBIA
        )

        conditions = (
            db_session.query(MentalCondition)
            .filter(MentalCondition.entity_id == entity.id)
            .all()
        )
        assert len(conditions) == 3


class TestGriefCondition:
    """Tests for GriefCondition model."""

    def test_create_grief_condition_required_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify GriefCondition creation with required fields."""
        grieving = create_entity(db_session, game_session, entity_key="griever")
        deceased = create_entity(db_session, game_session, entity_key="deceased")

        condition = GriefCondition(
            entity_id=grieving.id,
            deceased_entity_id=deceased.id,
            session_id=game_session.id,
            started_turn=10,
            current_stage_started_turn=10,
            expected_duration_days=30,
        )
        db_session.add(condition)
        db_session.flush()

        assert condition.id is not None
        assert condition.entity_id == grieving.id
        assert condition.deceased_entity_id == deceased.id

    def test_grief_stage_enum(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify GriefStage enum storage."""
        grieving = create_entity(db_session, game_session)
        for stage in GriefStage:
            deceased = create_entity(db_session, game_session)
            condition = create_grief_condition(
                db_session, game_session, grieving, deceased, grief_stage=stage
            )
            db_session.refresh(condition)
            assert condition.grief_stage == stage

    def test_grief_intensity(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify intensity 0-100 based on relationship."""
        grieving = create_entity(db_session, game_session)
        deceased = create_entity(db_session, game_session)

        # High intensity grief (close relationship)
        condition = create_grief_condition(
            db_session, game_session, grieving, deceased, intensity=90
        )

        db_session.refresh(condition)
        assert condition.intensity == 90

    def test_grief_morale_modifier(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify morale_modifier field."""
        grieving = create_entity(db_session, game_session)
        deceased = create_entity(db_session, game_session)

        condition = create_grief_condition(
            db_session, game_session, grieving, deceased, morale_modifier=-30
        )

        db_session.refresh(condition)
        assert condition.morale_modifier == -30

    def test_grief_behavioral_changes_json(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify behavioral_changes JSON field."""
        grieving = create_entity(db_session, game_session)
        deceased = create_entity(db_session, game_session)

        behaviors = {
            "social_withdrawal": 0.7,
            "crying_probability": 0.5,
            "productivity_penalty": 0.4,
        }
        condition = create_grief_condition(
            db_session, game_session, grieving, deceased, behavioral_changes=behaviors
        )

        db_session.refresh(condition)

        assert condition.behavioral_changes == behaviors
        assert condition.behavioral_changes["social_withdrawal"] == 0.7

    def test_grief_blame(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify blames_someone and blamed_entity_key fields."""
        grieving = create_entity(db_session, game_session)
        deceased = create_entity(db_session, game_session)

        condition = create_grief_condition(
            db_session,
            game_session,
            grieving,
            deceased,
            blames_someone=True,
            blamed_entity_key="evil_wizard",
        )

        db_session.refresh(condition)

        assert condition.blames_someone is True
        assert condition.blamed_entity_key == "evil_wizard"

    def test_grief_resolution(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify is_resolved and resolved_turn fields."""
        grieving = create_entity(db_session, game_session)
        deceased = create_entity(db_session, game_session)

        condition = create_grief_condition(
            db_session, game_session, grieving, deceased, is_resolved=False
        )
        assert condition.is_resolved is False

        # Mark as resolved
        condition.is_resolved = True
        condition.resolved_turn = 100
        db_session.flush()
        db_session.refresh(condition)

        assert condition.is_resolved is True
        assert condition.resolved_turn == 100

    def test_grief_dual_entity_references(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify entity_id and deceased_entity_id FKs."""
        grieving = create_entity(db_session, game_session, display_name="Grieving Person")
        deceased = create_entity(db_session, game_session, display_name="Deceased Person")

        condition = create_grief_condition(db_session, game_session, grieving, deceased)

        db_session.refresh(condition)

        assert condition.entity is not None
        assert condition.entity.display_name == "Grieving Person"
        assert condition.deceased_entity is not None
        assert condition.deceased_entity.display_name == "Deceased Person"

    def test_grief_timeline(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify timeline tracking fields."""
        grieving = create_entity(db_session, game_session)
        deceased = create_entity(db_session, game_session)

        condition = create_grief_condition(
            db_session,
            game_session,
            grieving,
            deceased,
            started_turn=5,
            current_stage_started_turn=10,
            expected_duration_days=45,
        )

        db_session.refresh(condition)

        assert condition.started_turn == 5
        assert condition.current_stage_started_turn == 10
        assert condition.expected_duration_days == 45

    def test_grief_cascade_delete_grieving_entity(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify grief deleted when grieving entity is deleted."""
        grieving = create_entity(db_session, game_session)
        deceased = create_entity(db_session, game_session)

        condition = create_grief_condition(db_session, game_session, grieving, deceased)
        condition_id = condition.id

        db_session.delete(grieving)
        db_session.flush()
        db_session.expire_all()

        result = db_session.query(GriefCondition).filter(
            GriefCondition.id == condition_id
        ).first()
        assert result is None

    def test_grief_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        grieving = create_entity(db_session, game_session)
        deceased = create_entity(db_session, game_session)

        condition = create_grief_condition(
            db_session,
            game_session,
            grieving,
            deceased,
            grief_stage=GriefStage.ANGER,
        )

        repr_str = repr(condition)
        assert "GriefCondition" in repr_str
        assert "anger" in repr_str
        assert str(grieving.id) in repr_str
        assert str(deceased.id) in repr_str

    def test_grief_repr_resolved(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify repr includes RESOLVED marker."""
        grieving = create_entity(db_session, game_session)
        deceased = create_entity(db_session, game_session)

        condition = create_grief_condition(
            db_session, game_session, grieving, deceased, is_resolved=True
        )

        repr_str = repr(condition)
        assert "RESOLVED" in repr_str
