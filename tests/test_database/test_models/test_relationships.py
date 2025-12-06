"""Tests for Relationship and RelationshipChange models."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.database.models.entities import Entity
from src.database.models.relationships import Relationship, RelationshipChange
from src.database.models.session import GameSession
from tests.factories import (
    create_entity,
    create_game_session,
    create_relationship,
    create_relationship_change,
)


class TestRelationship:
    """Tests for Relationship model."""

    def test_create_relationship_required_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify Relationship creation with required fields."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)

        rel = Relationship(
            session_id=game_session.id,
            from_entity_id=entity1.id,
            to_entity_id=entity2.id,
        )
        db_session.add(rel)
        db_session.flush()

        assert rel.id is not None
        assert rel.session_id == game_session.id
        assert rel.from_entity_id == entity1.id
        assert rel.to_entity_id == entity2.id

    def test_relationship_unique_constraint(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify unique constraint on session_id + from + to."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)

        create_relationship(db_session, game_session, entity1, entity2)

        with pytest.raises(IntegrityError):
            create_relationship(db_session, game_session, entity1, entity2)

    def test_relationship_directional(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify relationships are directional (A→B is different from B→A)."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)

        # A's attitude toward B
        rel_ab = create_relationship(
            db_session, game_session, entity1, entity2, trust=80, liking=70
        )
        # B's attitude toward A (different values)
        rel_ba = create_relationship(
            db_session, game_session, entity2, entity1, trust=30, liking=40
        )

        assert rel_ab.id != rel_ba.id
        assert rel_ab.trust == 80
        assert rel_ba.trust == 30

    def test_relationship_core_dimensions_defaults(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify default values for core dimensions."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)

        rel = Relationship(
            session_id=game_session.id,
            from_entity_id=entity1.id,
            to_entity_id=entity2.id,
        )
        db_session.add(rel)
        db_session.flush()

        # Core dimensions start at neutral (50), romantic at 0
        assert rel.trust == 50
        assert rel.liking == 50
        assert rel.respect == 50
        assert rel.romantic_interest == 0

    def test_relationship_context_dimensions_defaults(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify default values for context dimensions."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)

        rel = Relationship(
            session_id=game_session.id,
            from_entity_id=entity1.id,
            to_entity_id=entity2.id,
        )
        db_session.add(rel)
        db_session.flush()

        assert rel.familiarity == 0
        assert rel.fear == 0
        assert rel.social_debt == 0

    def test_relationship_social_debt_signed(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify social_debt can be negative (they owe you = positive)."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)

        # Entity1 owes entity2 (negative from entity1's perspective)
        rel = create_relationship(
            db_session, game_session, entity1, entity2, social_debt=-50
        )

        db_session.refresh(rel)
        assert rel.social_debt == -50

    def test_relationship_mood_modifier(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify mood modifier fields."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)

        rel = create_relationship(
            db_session,
            game_session,
            entity1,
            entity2,
            mood_modifier=15,
            mood_reason="Just received good news",
            mood_expires_turn=10,
        )

        db_session.refresh(rel)

        assert rel.mood_modifier == 15
        assert rel.mood_reason == "Just received good news"
        assert rel.mood_expires_turn == 10

    def test_relationship_knows_flag(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify knows boolean flag."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)

        # Default knows should be set by factory
        rel = create_relationship(db_session, game_session, entity1, entity2)
        assert rel.knows is True

        # Create unknown relationship
        entity3 = create_entity(db_session, game_session)
        rel_unknown = create_relationship(
            db_session, game_session, entity1, entity3, knows=False
        )
        assert rel_unknown.knows is False

    def test_relationship_type_and_status(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify relationship_type and relationship_status fields."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)

        rel = create_relationship(
            db_session,
            game_session,
            entity1,
            entity2,
            relationship_type="friend",
            relationship_status="dating",
        )

        db_session.refresh(rel)

        assert rel.relationship_type == "friend"
        assert rel.relationship_status == "dating"

    def test_relationship_history_tracking(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify history tracking fields."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)

        rel = create_relationship(
            db_session,
            game_session,
            entity1,
            entity2,
            first_met_turn=5,
            first_met_location="tavern",
            last_interaction_turn=10,
        )

        db_session.refresh(rel)

        assert rel.first_met_turn == 5
        assert rel.first_met_location == "tavern"
        assert rel.last_interaction_turn == 10

    def test_relationship_from_entity_back_reference(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify from_entity relationship."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)

        rel = create_relationship(db_session, game_session, entity1, entity2)

        assert rel.from_entity is not None
        assert rel.from_entity.id == entity1.id

    def test_relationship_to_entity_back_reference(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify to_entity relationship."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)

        rel = create_relationship(db_session, game_session, entity1, entity2)

        assert rel.to_entity is not None
        assert rel.to_entity.id == entity2.id

    def test_relationship_changes_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify changes relationship works."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)

        rel = create_relationship(db_session, game_session, entity1, entity2)
        change = create_relationship_change(db_session, rel)

        db_session.refresh(rel)

        assert len(rel.changes) == 1
        assert rel.changes[0].id == change.id

    def test_relationship_cascade_delete_from_entity(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify relationship is deleted when from_entity is deleted."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)

        rel = create_relationship(db_session, game_session, entity1, entity2)
        rel_id = rel.id

        db_session.delete(entity1)
        db_session.flush()

        # Clear session cache to verify database state
        db_session.expire_all()

        # Query directly to check if relationship exists
        result = (
            db_session.query(Relationship)
            .filter(Relationship.id == rel_id)
            .first()
        )
        assert result is None

    def test_relationship_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)

        rel = create_relationship(
            db_session,
            game_session,
            entity1,
            entity2,
            trust=70,
            liking=60,
            respect=80,
            familiarity=40,
        )

        repr_str = repr(rel)
        assert "Relationship" in repr_str
        assert "T:70" in repr_str
        assert "L:60" in repr_str
        assert "R:80" in repr_str
        assert "F:40" in repr_str

    def test_relationship_session_scoping(self, db_session: Session):
        """Verify relationships are properly scoped to sessions."""
        session1 = create_game_session(db_session)
        session2 = create_game_session(db_session)

        entity1_s1 = create_entity(db_session, session1)
        entity2_s1 = create_entity(db_session, session1)
        entity1_s2 = create_entity(db_session, session2)
        entity2_s2 = create_entity(db_session, session2)

        rel_s1 = create_relationship(db_session, session1, entity1_s1, entity2_s1)
        rel_s2 = create_relationship(db_session, session2, entity1_s2, entity2_s2)

        # Query for session1 relationships only
        result = (
            db_session.query(Relationship)
            .filter(Relationship.session_id == session1.id)
            .all()
        )

        assert len(result) == 1
        assert result[0].id == rel_s1.id


class TestRelationshipChange:
    """Tests for RelationshipChange model."""

    def test_create_relationship_change_required(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify RelationshipChange creation with required fields."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        rel = create_relationship(db_session, game_session, entity1, entity2)

        change = RelationshipChange(
            relationship_id=rel.id,
            dimension="trust",
            old_value=50,
            new_value=60,
            delta=10,
            reason="Player helped them",
            turn_number=5,
        )
        db_session.add(change)
        db_session.flush()

        assert change.id is not None
        assert change.relationship_id == rel.id
        assert change.dimension == "trust"
        assert change.old_value == 50
        assert change.new_value == 60
        assert change.delta == 10
        assert change.reason == "Player helped them"
        assert change.turn_number == 5

    def test_relationship_change_audit_log(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify multiple changes create an audit trail."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        rel = create_relationship(db_session, game_session, entity1, entity2, trust=50)

        # First change
        change1 = create_relationship_change(
            db_session,
            rel,
            dimension="trust",
            old_value=50,
            new_value=60,
            delta=10,
            reason="Helped with task",
            turn_number=1,
        )

        # Second change
        change2 = create_relationship_change(
            db_session,
            rel,
            dimension="trust",
            old_value=60,
            new_value=75,
            delta=15,
            reason="Saved their life",
            turn_number=5,
        )

        db_session.refresh(rel)

        assert len(rel.changes) == 2
        # Check audit trail
        changes = sorted(rel.changes, key=lambda c: c.turn_number)
        assert changes[0].new_value == 60
        assert changes[1].new_value == 75

    def test_relationship_change_back_reference(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify RelationshipChange has back reference to relationship."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        rel = create_relationship(db_session, game_session, entity1, entity2)
        change = create_relationship_change(db_session, rel)

        assert change.relationship is not None
        assert change.relationship.id == rel.id

    def test_relationship_change_cascade_delete(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify changes are deleted when relationship is deleted."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        rel = create_relationship(db_session, game_session, entity1, entity2)
        change = create_relationship_change(db_session, rel)
        change_id = change.id

        db_session.delete(rel)
        db_session.flush()

        assert db_session.get(RelationshipChange, change_id) is None

    def test_relationship_change_created_at(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify created_at is automatically set."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        rel = create_relationship(db_session, game_session, entity1, entity2)
        change = create_relationship_change(db_session, rel)

        assert change.created_at is not None

    def test_relationship_change_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        rel = create_relationship(db_session, game_session, entity1, entity2)
        change = create_relationship_change(
            db_session, rel, dimension="liking", old_value=40, new_value=55
        )

        repr_str = repr(change)
        assert "RelationshipChange" in repr_str
        assert "liking" in repr_str
        assert "40" in repr_str
        assert "55" in repr_str

    def test_relationship_change_negative_delta(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify negative changes are recorded correctly."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        rel = create_relationship(db_session, game_session, entity1, entity2)
        change = create_relationship_change(
            db_session,
            rel,
            dimension="trust",
            old_value=60,
            new_value=30,
            delta=-30,
            reason="Caught lying",
        )

        db_session.refresh(change)

        assert change.delta == -30
        assert change.new_value < change.old_value
