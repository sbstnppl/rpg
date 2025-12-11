"""Tests for relationship arc models."""

import pytest
from sqlalchemy.exc import IntegrityError

from src.database.models.relationship_arcs import (
    RelationshipArc,
    RelationshipArcPhase,
    RelationshipArcType,
)


class TestRelationshipArcType:
    """Tests for RelationshipArcType enum."""

    def test_arc_types(self):
        assert RelationshipArcType.ENEMIES_TO_LOVERS.value == "enemies_to_lovers"
        assert RelationshipArcType.MENTORS_FALL.value == "mentors_fall"
        assert RelationshipArcType.BETRAYAL.value == "betrayal"
        assert RelationshipArcType.REDEMPTION.value == "redemption"
        assert RelationshipArcType.RIVALRY.value == "rivalry"
        assert RelationshipArcType.FOUND_FAMILY.value == "found_family"
        assert RelationshipArcType.LOST_LOVE_REKINDLED.value == "lost_love_rekindled"
        assert RelationshipArcType.CORRUPTION.value == "corruption"


class TestRelationshipArcPhase:
    """Tests for RelationshipArcPhase enum."""

    def test_arc_phases(self):
        assert RelationshipArcPhase.INTRODUCTION.value == "introduction"
        assert RelationshipArcPhase.DEVELOPMENT.value == "development"
        assert RelationshipArcPhase.CRISIS.value == "crisis"
        assert RelationshipArcPhase.CLIMAX.value == "climax"
        assert RelationshipArcPhase.RESOLUTION.value == "resolution"


class TestRelationshipArcModel:
    """Tests for RelationshipArc model."""

    def test_create_relationship_arc(self, db_session, game_session):
        """Test creating a basic relationship arc."""
        arc = RelationshipArc(
            session_id=game_session.id,
            arc_key="player_elara_romance",
            arc_type=RelationshipArcType.ENEMIES_TO_LOVERS,
            entity1_key="player",
            entity2_key="elara",
            current_phase=RelationshipArcPhase.INTRODUCTION,
            phase_progress=0,
            arc_tension=20,
            started_turn=10,
        )
        db_session.add(arc)
        db_session.commit()

        assert arc.id is not None
        assert arc.arc_key == "player_elara_romance"
        assert arc.arc_type == RelationshipArcType.ENEMIES_TO_LOVERS
        assert arc.entity1_key == "player"
        assert arc.entity2_key == "elara"
        assert arc.current_phase == RelationshipArcPhase.INTRODUCTION
        assert arc.is_active is True

    def test_arc_with_milestones(self, db_session, game_session):
        """Test arc with milestone tracking."""
        arc = RelationshipArc(
            session_id=game_session.id,
            arc_key="player_mentor",
            arc_type=RelationshipArcType.MENTORS_FALL,
            entity1_key="player",
            entity2_key="wise_sage",
            current_phase=RelationshipArcPhase.DEVELOPMENT,
            phase_progress=50,
            milestones_hit=["first_lesson", "trust_established", "secret_revealed"],
            arc_tension=45,
            started_turn=5,
        )
        db_session.add(arc)
        db_session.commit()

        assert arc.milestones_hit == ["first_lesson", "trust_established", "secret_revealed"]

    def test_arc_with_suggested_beat(self, db_session, game_session):
        """Test arc with suggested next beat."""
        arc = RelationshipArc(
            session_id=game_session.id,
            arc_key="player_villain",
            arc_type=RelationshipArcType.REDEMPTION,
            entity1_key="player",
            entity2_key="fallen_knight",
            current_phase=RelationshipArcPhase.CRISIS,
            phase_progress=75,
            arc_tension=85,
            started_turn=1,
            suggested_next_beat="The fallen knight must choose between old loyalties and new bonds",
        )
        db_session.add(arc)
        db_session.commit()

        assert arc.suggested_next_beat is not None
        assert "choose" in arc.suggested_next_beat

    def test_arc_unique_key_per_session(self, db_session, game_session):
        """Test that arc_key must be unique within session."""
        arc1 = RelationshipArc(
            session_id=game_session.id,
            arc_key="unique_arc",
            arc_type=RelationshipArcType.RIVALRY,
            entity1_key="player",
            entity2_key="npc_1",
            current_phase=RelationshipArcPhase.INTRODUCTION,
            started_turn=1,
        )
        db_session.add(arc1)
        db_session.commit()

        arc2 = RelationshipArc(
            session_id=game_session.id,
            arc_key="unique_arc",
            arc_type=RelationshipArcType.BETRAYAL,
            entity1_key="player",
            entity2_key="npc_2",
            current_phase=RelationshipArcPhase.INTRODUCTION,
            started_turn=2,
        )
        db_session.add(arc2)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_arc_defaults(self, db_session, game_session):
        """Test default values for arc."""
        arc = RelationshipArc(
            session_id=game_session.id,
            arc_key="default_arc",
            arc_type=RelationshipArcType.FOUND_FAMILY,
            entity1_key="player",
            entity2_key="orphan",
            started_turn=1,
        )
        db_session.add(arc)
        db_session.commit()

        assert arc.current_phase == RelationshipArcPhase.INTRODUCTION
        assert arc.phase_progress == 0
        assert arc.arc_tension == 0
        assert arc.milestones_hit == []
        assert arc.is_active is True
        assert arc.completed_turn is None

    def test_completed_arc(self, db_session, game_session):
        """Test marking an arc as completed."""
        arc = RelationshipArc(
            session_id=game_session.id,
            arc_key="completed_arc",
            arc_type=RelationshipArcType.ENEMIES_TO_LOVERS,
            entity1_key="player",
            entity2_key="rival",
            current_phase=RelationshipArcPhase.RESOLUTION,
            phase_progress=100,
            arc_tension=10,
            started_turn=1,
            completed_turn=50,
            is_active=False,
        )
        db_session.add(arc)
        db_session.commit()

        assert arc.is_active is False
        assert arc.completed_turn == 50
        assert arc.current_phase == RelationshipArcPhase.RESOLUTION
