"""Tests for RelationshipArcManager."""

import pytest

from src.database.models.relationship_arcs import (
    RelationshipArc,
    RelationshipArcPhase,
    RelationshipArcType,
)
from src.managers.relationship_arc_manager import (
    ArcBeatSuggestion,
    ArcInfo,
    RelationshipArcManager,
)


class TestCreateArc:
    """Tests for arc creation."""

    def test_create_arc_basic(self, db_session, game_session):
        """Test creating a basic arc."""
        manager = RelationshipArcManager(db_session, game_session)

        arc = manager.create_arc(
            arc_key="player_elara",
            arc_type=RelationshipArcType.ENEMIES_TO_LOVERS,
            entity1_key="player",
            entity2_key="elara",
            started_turn=10,
        )

        assert arc.arc_key == "player_elara"
        assert arc.arc_type == RelationshipArcType.ENEMIES_TO_LOVERS
        assert arc.entity1_key == "player"
        assert arc.entity2_key == "elara"
        assert arc.current_phase == RelationshipArcPhase.INTRODUCTION

    def test_create_arc_with_tension(self, db_session, game_session):
        """Test creating an arc with initial tension."""
        manager = RelationshipArcManager(db_session, game_session)

        arc = manager.create_arc(
            arc_key="player_rival",
            arc_type=RelationshipArcType.RIVALRY,
            entity1_key="player",
            entity2_key="rival_knight",
            started_turn=5,
            initial_tension=40,
        )

        assert arc.arc_tension == 40


class TestGetArc:
    """Tests for retrieving arcs."""

    def test_get_arc(self, db_session, game_session):
        """Test getting an arc by key."""
        manager = RelationshipArcManager(db_session, game_session)

        manager.create_arc(
            arc_key="test_arc",
            arc_type=RelationshipArcType.BETRAYAL,
            entity1_key="player",
            entity2_key="traitor",
            started_turn=1,
        )

        arc = manager.get_arc("test_arc")
        assert arc is not None
        assert arc.arc_key == "test_arc"

    def test_get_arc_not_found(self, db_session, game_session):
        """Test getting non-existent arc."""
        manager = RelationshipArcManager(db_session, game_session)

        arc = manager.get_arc("nonexistent")
        assert arc is None

    def test_get_active_arcs(self, db_session, game_session):
        """Test getting all active arcs."""
        manager = RelationshipArcManager(db_session, game_session)

        manager.create_arc(
            arc_key="active_1",
            arc_type=RelationshipArcType.REDEMPTION,
            entity1_key="player",
            entity2_key="fallen_hero",
            started_turn=1,
        )
        arc2 = manager.create_arc(
            arc_key="inactive",
            arc_type=RelationshipArcType.FOUND_FAMILY,
            entity1_key="player",
            entity2_key="orphan",
            started_turn=2,
        )
        arc2.is_active = False
        db_session.commit()

        active = manager.get_active_arcs()
        assert len(active) == 1
        assert active[0].arc_key == "active_1"

    def test_get_arcs_for_entity(self, db_session, game_session):
        """Test getting arcs involving an entity."""
        manager = RelationshipArcManager(db_session, game_session)

        manager.create_arc(
            arc_key="arc_1",
            arc_type=RelationshipArcType.ENEMIES_TO_LOVERS,
            entity1_key="player",
            entity2_key="elara",
            started_turn=1,
        )
        manager.create_arc(
            arc_key="arc_2",
            arc_type=RelationshipArcType.MENTORS_FALL,
            entity1_key="player",
            entity2_key="sage",
            started_turn=2,
        )
        manager.create_arc(
            arc_key="arc_3",
            arc_type=RelationshipArcType.RIVALRY,
            entity1_key="npc_1",
            entity2_key="npc_2",
            started_turn=3,
        )

        player_arcs = manager.get_arcs_for_entity("player")
        assert len(player_arcs) == 2

        elara_arcs = manager.get_arcs_for_entity("elara")
        assert len(elara_arcs) == 1


class TestArcPhases:
    """Tests for arc phase management."""

    def test_advance_phase(self, db_session, game_session):
        """Test advancing to next phase."""
        manager = RelationshipArcManager(db_session, game_session)

        arc = manager.create_arc(
            arc_key="advance_test",
            arc_type=RelationshipArcType.ENEMIES_TO_LOVERS,
            entity1_key="player",
            entity2_key="rival",
            started_turn=1,
        )

        manager.advance_phase("advance_test")

        db_session.refresh(arc)
        assert arc.current_phase == RelationshipArcPhase.DEVELOPMENT
        assert arc.phase_progress == 0

    def test_advance_phase_sequence(self, db_session, game_session):
        """Test advancing through all phases."""
        manager = RelationshipArcManager(db_session, game_session)

        arc = manager.create_arc(
            arc_key="sequence_test",
            arc_type=RelationshipArcType.BETRAYAL,
            entity1_key="player",
            entity2_key="friend",
            started_turn=1,
        )

        phases = [
            RelationshipArcPhase.INTRODUCTION,
            RelationshipArcPhase.DEVELOPMENT,
            RelationshipArcPhase.CRISIS,
            RelationshipArcPhase.CLIMAX,
            RelationshipArcPhase.RESOLUTION,
        ]

        for i, expected_phase in enumerate(phases):
            db_session.refresh(arc)
            assert arc.current_phase == expected_phase
            if i < len(phases) - 1:
                manager.advance_phase("sequence_test")

    def test_update_phase_progress(self, db_session, game_session):
        """Test updating progress within a phase."""
        manager = RelationshipArcManager(db_session, game_session)

        arc = manager.create_arc(
            arc_key="progress_test",
            arc_type=RelationshipArcType.REDEMPTION,
            entity1_key="player",
            entity2_key="villain",
            started_turn=1,
        )

        manager.update_phase_progress("progress_test", 50)

        db_session.refresh(arc)
        assert arc.phase_progress == 50

    def test_update_tension(self, db_session, game_session):
        """Test updating arc tension."""
        manager = RelationshipArcManager(db_session, game_session)

        arc = manager.create_arc(
            arc_key="tension_test",
            arc_type=RelationshipArcType.CORRUPTION,
            entity1_key="player",
            entity2_key="innocent",
            started_turn=1,
        )

        manager.update_tension("tension_test", 75)

        db_session.refresh(arc)
        assert arc.arc_tension == 75


class TestMilestones:
    """Tests for milestone tracking."""

    def test_hit_milestone(self, db_session, game_session):
        """Test recording a hit milestone."""
        manager = RelationshipArcManager(db_session, game_session)

        arc = manager.create_arc(
            arc_key="milestone_test",
            arc_type=RelationshipArcType.ENEMIES_TO_LOVERS,
            entity1_key="player",
            entity2_key="rival",
            started_turn=1,
        )

        manager.hit_milestone("milestone_test", "first_conflict")

        db_session.refresh(arc)
        assert "first_conflict" in arc.milestones_hit

    def test_hit_multiple_milestones(self, db_session, game_session):
        """Test recording multiple milestones."""
        manager = RelationshipArcManager(db_session, game_session)

        arc = manager.create_arc(
            arc_key="multi_milestone",
            arc_type=RelationshipArcType.MENTORS_FALL,
            entity1_key="player",
            entity2_key="mentor",
            started_turn=1,
        )

        manager.hit_milestone("multi_milestone", "first_lesson")
        manager.hit_milestone("multi_milestone", "trust_established")
        manager.hit_milestone("multi_milestone", "secret_shared")

        db_session.refresh(arc)
        assert len(arc.milestones_hit) == 3
        assert "first_lesson" in arc.milestones_hit
        assert "trust_established" in arc.milestones_hit

    def test_has_milestone(self, db_session, game_session):
        """Test checking if milestone was hit."""
        manager = RelationshipArcManager(db_session, game_session)

        arc = manager.create_arc(
            arc_key="check_milestone",
            arc_type=RelationshipArcType.RIVALRY,
            entity1_key="player",
            entity2_key="competitor",
            started_turn=1,
        )

        manager.hit_milestone("check_milestone", "first_competition")

        assert manager.has_milestone("check_milestone", "first_competition") is True
        assert manager.has_milestone("check_milestone", "final_showdown") is False


class TestCompleteArc:
    """Tests for arc completion."""

    def test_complete_arc(self, db_session, game_session):
        """Test completing an arc."""
        manager = RelationshipArcManager(db_session, game_session)

        arc = manager.create_arc(
            arc_key="complete_test",
            arc_type=RelationshipArcType.ENEMIES_TO_LOVERS,
            entity1_key="player",
            entity2_key="love_interest",
            started_turn=1,
        )

        manager.complete_arc("complete_test", completed_turn=100)

        db_session.refresh(arc)
        assert arc.is_active is False
        assert arc.completed_turn == 100
        assert arc.current_phase == RelationshipArcPhase.RESOLUTION

    def test_abandon_arc(self, db_session, game_session):
        """Test abandoning an arc without completing it."""
        manager = RelationshipArcManager(db_session, game_session)

        arc = manager.create_arc(
            arc_key="abandon_test",
            arc_type=RelationshipArcType.BETRAYAL,
            entity1_key="player",
            entity2_key="spy",
            started_turn=1,
        )

        manager.abandon_arc("abandon_test")

        db_session.refresh(arc)
        assert arc.is_active is False
        # Phase should NOT be set to resolution for abandoned arcs
        assert arc.current_phase != RelationshipArcPhase.RESOLUTION or arc.completed_turn is None


class TestArcTemplates:
    """Tests for arc template suggestions."""

    def test_get_arc_beat_suggestion(self, db_session, game_session):
        """Test getting suggested next beat for an arc."""
        manager = RelationshipArcManager(db_session, game_session)

        manager.create_arc(
            arc_key="suggestion_test",
            arc_type=RelationshipArcType.ENEMIES_TO_LOVERS,
            entity1_key="player",
            entity2_key="rival",
            started_turn=1,
        )

        suggestion = manager.get_arc_beat_suggestion("suggestion_test")

        assert suggestion is not None
        assert isinstance(suggestion, ArcBeatSuggestion)
        assert suggestion.arc_type == RelationshipArcType.ENEMIES_TO_LOVERS.value
        assert suggestion.current_phase == RelationshipArcPhase.INTRODUCTION.value
        assert len(suggestion.suggested_scenes) > 0

    def test_set_suggested_beat(self, db_session, game_session):
        """Test setting a custom suggested beat."""
        manager = RelationshipArcManager(db_session, game_session)

        arc = manager.create_arc(
            arc_key="custom_beat",
            arc_type=RelationshipArcType.REDEMPTION,
            entity1_key="player",
            entity2_key="fallen",
            started_turn=1,
        )

        manager.set_suggested_beat("custom_beat", "The fallen warrior must face their former comrades")

        db_session.refresh(arc)
        assert arc.suggested_next_beat == "The fallen warrior must face their former comrades"


class TestArcInfo:
    """Tests for arc info retrieval."""

    def test_get_arc_info(self, db_session, game_session):
        """Test getting detailed arc info."""
        manager = RelationshipArcManager(db_session, game_session)

        arc = manager.create_arc(
            arc_key="info_test",
            arc_type=RelationshipArcType.FOUND_FAMILY,
            entity1_key="player",
            entity2_key="orphan",
            started_turn=5,
            initial_tension=20,
        )
        manager.hit_milestone("info_test", "shared_meal")
        manager.update_phase_progress("info_test", 30)

        info = manager.get_arc_info("info_test")

        assert info is not None
        assert info.arc_key == "info_test"
        assert info.arc_type == RelationshipArcType.FOUND_FAMILY.value
        assert info.entity1_key == "player"
        assert info.entity2_key == "orphan"
        assert info.current_phase == RelationshipArcPhase.INTRODUCTION.value
        assert info.phase_progress == 30
        assert info.arc_tension == 20
        assert "shared_meal" in info.milestones_hit


class TestArcContext:
    """Tests for arc context generation."""

    def test_get_arc_context(self, db_session, game_session):
        """Test generating arc context for GM."""
        manager = RelationshipArcManager(db_session, game_session)

        manager.create_arc(
            arc_key="context_arc",
            arc_type=RelationshipArcType.ENEMIES_TO_LOVERS,
            entity1_key="player",
            entity2_key="elara",
            started_turn=1,
        )
        manager.update_tension("context_arc", 50)

        context = manager.get_arc_context()

        assert "elara" in context.lower()
        assert "enemies" in context.lower() or "lovers" in context.lower()

    def test_get_arc_context_empty(self, db_session, game_session):
        """Test context when no arcs exist."""
        manager = RelationshipArcManager(db_session, game_session)

        context = manager.get_arc_context()

        assert context == "" or "no active" in context.lower()

    def test_get_arc_context_for_entity(self, db_session, game_session):
        """Test getting arc context for a specific entity."""
        manager = RelationshipArcManager(db_session, game_session)

        manager.create_arc(
            arc_key="entity_context_1",
            arc_type=RelationshipArcType.RIVALRY,
            entity1_key="player",
            entity2_key="rival",
            started_turn=1,
        )
        manager.create_arc(
            arc_key="entity_context_2",
            arc_type=RelationshipArcType.MENTORS_FALL,
            entity1_key="mentor",
            entity2_key="student",
            started_turn=2,
        )

        player_context = manager.get_arc_context_for_entity("player")
        mentor_context = manager.get_arc_context_for_entity("mentor")

        assert "rival" in player_context.lower()
        assert "student" in mentor_context.lower()
