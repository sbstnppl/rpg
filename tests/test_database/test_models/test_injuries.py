"""Tests for BodyInjury and ActivityRestriction models."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.enums import BodyPart, InjurySeverity, InjuryType
from src.database.models.injuries import ActivityRestriction, BodyInjury
from src.database.models.session import GameSession
from tests.factories import (
    create_activity_restriction,
    create_body_injury,
    create_entity,
    create_game_session,
)


class TestBodyInjury:
    """Tests for BodyInjury model."""

    def test_create_injury_required_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify BodyInjury creation with required fields."""
        entity = create_entity(db_session, game_session)
        injury = BodyInjury(
            entity_id=entity.id,
            session_id=game_session.id,
            body_part=BodyPart.LEFT_ARM,
            injury_type=InjuryType.BRUISE,
            severity=InjurySeverity.MINOR,
            caused_by="Fell down stairs",
            occurred_turn=5,
            base_recovery_days=3,
            adjusted_recovery_days=3,
        )
        db_session.add(injury)
        db_session.flush()

        assert injury.id is not None
        assert injury.body_part == BodyPart.LEFT_ARM
        assert injury.injury_type == InjuryType.BRUISE

    def test_injury_body_part_enum(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify BodyPart enum storage."""
        entity = create_entity(db_session, game_session)
        for body_part in [BodyPart.HEAD, BodyPart.TORSO, BodyPart.LEFT_LEG]:
            injury = create_body_injury(db_session, game_session, entity, body_part=body_part)
            db_session.refresh(injury)
            assert injury.body_part == body_part

    def test_injury_type_enum(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify InjuryType enum storage."""
        entity = create_entity(db_session, game_session)
        for injury_type in [InjuryType.CUT, InjuryType.FRACTURE, InjuryType.SPRAIN]:
            injury = create_body_injury(db_session, game_session, entity, injury_type=injury_type)
            db_session.refresh(injury)
            assert injury.injury_type == injury_type

    def test_injury_severity_enum(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify InjurySeverity enum storage."""
        entity = create_entity(db_session, game_session)
        for severity in InjurySeverity:
            injury = create_body_injury(db_session, game_session, entity, severity=severity)
            db_session.refresh(injury)
            assert injury.severity == severity

    def test_injury_medical_care(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify medical care fields."""
        entity = create_entity(db_session, game_session)
        injury = create_body_injury(
            db_session,
            game_session,
            entity,
            received_medical_care=True,
            medical_care_quality=80,
            medical_care_turn=10,
        )

        db_session.refresh(injury)

        assert injury.received_medical_care is True
        assert injury.medical_care_quality == 80
        assert injury.medical_care_turn == 10

    def test_injury_recovery_tracking(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify recovery progress fields."""
        entity = create_entity(db_session, game_session)
        injury = create_body_injury(
            db_session,
            game_session,
            entity,
            base_recovery_days=7,
            adjusted_recovery_days=5.0,  # Reduced by medical care
            recovery_progress_days=2.5,
        )

        db_session.refresh(injury)

        assert injury.base_recovery_days == 7
        assert injury.adjusted_recovery_days == 5.0
        assert injury.recovery_progress_days == 2.5

    def test_injury_healed_state(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify healed injury state."""
        entity = create_entity(db_session, game_session)
        injury = create_body_injury(db_session, game_session, entity)

        assert injury.is_healed is False

        # Mark as healed
        injury.is_healed = True
        injury.healed_turn = 20
        db_session.flush()
        db_session.refresh(injury)

        assert injury.is_healed is True
        assert injury.healed_turn == 20

    def test_injury_complications(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify complication flags."""
        entity = create_entity(db_session, game_session)
        injury = create_body_injury(
            db_session,
            game_session,
            entity,
            is_infected=True,
            is_reinjured=True,
        )

        db_session.refresh(injury)

        assert injury.is_infected is True
        assert injury.is_reinjured is True

    def test_injury_permanent_damage(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify permanent damage fields."""
        entity = create_entity(db_session, game_session)
        injury = create_body_injury(
            db_session,
            game_session,
            entity,
            has_permanent_damage=True,
            permanent_damage_description="Chronic pain in cold weather",
        )

        db_session.refresh(injury)

        assert injury.has_permanent_damage is True
        assert "Chronic pain" in injury.permanent_damage_description

    def test_injury_pain_level(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify current_pain_level field."""
        entity = create_entity(db_session, game_session)
        injury = create_body_injury(
            db_session, game_session, entity, current_pain_level=45
        )

        db_session.refresh(injury)
        assert injury.current_pain_level == 45

    def test_injury_activity_restrictions_json(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify activity_restrictions cached JSON field."""
        entity = create_entity(db_session, game_session)
        restrictions = {
            "walking": {"impact": "painful", "penalty": 10},
            "running": {"impact": "impossible"},
            "writing": {"impact": "unaffected"},
        }
        injury = create_body_injury(
            db_session, game_session, entity, activity_restrictions=restrictions
        )

        db_session.refresh(injury)

        assert injury.activity_restrictions == restrictions
        assert injury.activity_restrictions["running"]["impact"] == "impossible"

    def test_injury_entity_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify injury has back reference to entity."""
        entity = create_entity(db_session, game_session)
        injury = create_body_injury(db_session, game_session, entity)

        assert injury.entity is not None
        assert injury.entity.id == entity.id

    def test_injury_cascade_delete(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify injury deleted when entity is deleted."""
        entity = create_entity(db_session, game_session)
        injury = create_body_injury(db_session, game_session, entity)
        injury_id = injury.id

        db_session.delete(entity)
        db_session.flush()
        db_session.expire_all()

        result = db_session.query(BodyInjury).filter(BodyInjury.id == injury_id).first()
        assert result is None

    def test_injury_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        entity = create_entity(db_session, game_session)
        injury = create_body_injury(
            db_session,
            game_session,
            entity,
            body_part=BodyPart.RIGHT_LEG,
            injury_type=InjuryType.FRACTURE,
            severity=InjurySeverity.SEVERE,
        )

        repr_str = repr(injury)
        assert "BodyInjury" in repr_str
        assert "right_leg" in repr_str
        assert "fracture" in repr_str
        assert "severe" in repr_str

    def test_injury_repr_healed(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify repr includes HEALED marker."""
        entity = create_entity(db_session, game_session)
        injury = create_body_injury(db_session, game_session, entity, is_healed=True)

        repr_str = repr(injury)
        assert "HEALED" in repr_str

    def test_multiple_injuries_per_entity(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify entity can have multiple injuries."""
        entity = create_entity(db_session, game_session)

        injury1 = create_body_injury(
            db_session, game_session, entity, body_part=BodyPart.LEFT_ARM
        )
        injury2 = create_body_injury(
            db_session, game_session, entity, body_part=BodyPart.RIGHT_LEG
        )
        injury3 = create_body_injury(
            db_session, game_session, entity, body_part=BodyPart.HEAD
        )

        injuries = (
            db_session.query(BodyInjury)
            .filter(BodyInjury.entity_id == entity.id)
            .all()
        )
        assert len(injuries) == 3


class TestActivityRestriction:
    """Tests for ActivityRestriction model."""

    def test_create_activity_restriction(self, db_session: Session):
        """Verify ActivityRestriction creation."""
        restriction = ActivityRestriction(
            body_part=BodyPart.LEFT_LEG,
            injury_type=InjuryType.FRACTURE,
            severity=InjurySeverity.SEVERE,
            activity_name="running",
            impact_type="impossible",
        )
        db_session.add(restriction)
        db_session.flush()

        assert restriction.id is not None
        assert restriction.activity_name == "running"
        assert restriction.impact_type == "impossible"

    def test_activity_restriction_impact_types(self, db_session: Session):
        """Verify different impact types."""
        # Unaffected
        r1 = create_activity_restriction(
            db_session,
            activity_name="talking",
            impact_type="unaffected",
        )
        assert r1.impact_type == "unaffected"

        # Painful
        r2 = create_activity_restriction(
            db_session,
            activity_name="walking",
            impact_type="painful",
            impact_value=20,
        )
        assert r2.impact_type == "painful"
        assert r2.impact_value == 20

        # Penalty
        r3 = create_activity_restriction(
            db_session,
            activity_name="running",
            impact_type="penalty",
            impact_value=50,
        )
        assert r3.impact_type == "penalty"
        assert r3.impact_value == 50

        # Impossible
        r4 = create_activity_restriction(
            db_session,
            activity_name="jumping",
            impact_type="impossible",
        )
        assert r4.impact_type == "impossible"

    def test_activity_restriction_requirement(self, db_session: Session):
        """Verify requirement field for impossible_without type."""
        restriction = create_activity_restriction(
            db_session,
            body_part=BodyPart.LEFT_LEG,
            injury_type=InjuryType.FRACTURE,
            severity=InjurySeverity.SEVERE,
            activity_name="walking",
            impact_type="impossible_without",
            requirement="crutches",
        )

        db_session.refresh(restriction)

        assert restriction.requirement == "crutches"

    def test_activity_restriction_repr(self, db_session: Session):
        """Verify string representation."""
        restriction = create_activity_restriction(
            db_session,
            body_part=BodyPart.HEAD,
            injury_type=InjuryType.CONCUSSION,
            activity_name="reading",
            impact_type="painful",
        )

        repr_str = repr(restriction)
        assert "ActivityRestriction" in repr_str
        assert "head" in repr_str
        assert "concussion" in repr_str
        assert "reading" in repr_str
        assert "painful" in repr_str
