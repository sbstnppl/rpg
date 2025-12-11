"""Tests for StoryArcManager - narrative structure and pacing."""

import pytest
from sqlalchemy.orm import Session

from src.database.models import (
    ArcPhase,
    ArcStatus,
    ArcType,
    GameSession,
    StoryArc,
)
from src.managers.story_arc_manager import (
    PacingHint,
    StoryArcManager,
)
from tests.factories import create_entity


@pytest.fixture
def arc_manager(db_session: Session, game_session: GameSession) -> StoryArcManager:
    """Create a StoryArcManager instance."""
    return StoryArcManager(db_session, game_session)


class TestStoryArcCreation:
    """Tests for creating story arcs."""

    def test_create_arc_basic(
        self, arc_manager: StoryArcManager, game_session: GameSession
    ):
        """Verify basic arc creation."""
        arc = arc_manager.create_arc(
            arc_key="main_quest",
            title="The Dragon's Lair",
            arc_type=ArcType.MAIN_QUEST,
        )

        assert arc.arc_key == "main_quest"
        assert arc.title == "The Dragon's Lair"
        assert arc.arc_type == ArcType.MAIN_QUEST
        assert arc.status == ArcStatus.DORMANT
        assert arc.current_phase == ArcPhase.SETUP

    def test_create_arc_with_description(self, arc_manager: StoryArcManager):
        """Verify arc with description and stakes."""
        arc = arc_manager.create_arc(
            arc_key="revenge_arc",
            title="Vengeance for Father",
            arc_type=ArcType.REVENGE,
            description="Seeking justice for murder",
            stakes="Family honor",
        )

        assert arc.description == "Seeking justice for murder"
        assert arc.stakes == "Family honor"

    def test_create_arc_with_entities(
        self,
        arc_manager: StoryArcManager,
        db_session: Session,
        game_session: GameSession,
    ):
        """Verify arc with protagonist and antagonist."""
        hero = create_entity(db_session, game_session, entity_key="hero")
        villain = create_entity(db_session, game_session, entity_key="villain")

        arc = arc_manager.create_arc(
            arc_key="hero_journey",
            title="The Hero's Journey",
            arc_type=ArcType.MAIN_QUEST,
            protagonist_id=hero.id,
            antagonist_id=villain.id,
        )

        assert arc.protagonist_id == hero.id
        assert arc.antagonist_id == villain.id

    def test_create_arc_activated(self, arc_manager: StoryArcManager):
        """Verify arc can be created in active state."""
        arc = arc_manager.create_arc(
            arc_key="active_arc",
            title="Active Arc",
            arc_type=ArcType.SIDE_QUEST,
            activate=True,
        )

        assert arc.status == ArcStatus.ACTIVE
        assert arc.started_turn == arc_manager.current_turn

    def test_create_arc_duplicate_key_raises(self, arc_manager: StoryArcManager):
        """Verify duplicate arc_key raises error."""
        arc_manager.create_arc(
            arc_key="unique_key",
            title="First Arc",
            arc_type=ArcType.SIDE_QUEST,
        )

        with pytest.raises(ValueError, match="already exists"):
            arc_manager.create_arc(
                arc_key="unique_key",
                title="Duplicate Arc",
                arc_type=ArcType.SIDE_QUEST,
            )

    def test_create_arc_priority_clamped(self, arc_manager: StoryArcManager):
        """Verify priority is clamped to 1-10."""
        arc_low = arc_manager.create_arc(
            arc_key="low_priority",
            title="Low",
            arc_type=ArcType.SIDE_QUEST,
            priority=-5,
        )
        arc_high = arc_manager.create_arc(
            arc_key="high_priority",
            title="High",
            arc_type=ArcType.MAIN_QUEST,
            priority=15,
        )

        assert arc_low.priority == 1
        assert arc_high.priority == 10


class TestStoryArcRetrieval:
    """Tests for retrieving story arcs."""

    def test_get_arc(self, arc_manager: StoryArcManager):
        """Verify arc retrieval by key."""
        arc_manager.create_arc(
            arc_key="test_arc",
            title="Test",
            arc_type=ArcType.SIDE_QUEST,
        )

        arc = arc_manager.get_arc("test_arc")
        assert arc is not None
        assert arc.arc_key == "test_arc"

    def test_get_arc_not_found(self, arc_manager: StoryArcManager):
        """Verify None returned for non-existent arc."""
        arc = arc_manager.get_arc("nonexistent")
        assert arc is None

    def test_get_active_arcs(self, arc_manager: StoryArcManager):
        """Verify active arcs retrieval."""
        arc_manager.create_arc(
            arc_key="dormant",
            title="Dormant",
            arc_type=ArcType.SIDE_QUEST,
        )
        arc_manager.create_arc(
            arc_key="active1",
            title="Active 1",
            arc_type=ArcType.MAIN_QUEST,
            activate=True,
            priority=8,
        )
        arc_manager.create_arc(
            arc_key="active2",
            title="Active 2",
            arc_type=ArcType.ROMANCE,
            activate=True,
            priority=5,
        )

        active = arc_manager.get_active_arcs()

        assert len(active) == 2
        assert active[0].arc_key == "active1"  # Higher priority first
        assert active[1].arc_key == "active2"

    def test_get_arcs_by_type(self, arc_manager: StoryArcManager):
        """Verify arcs retrieval by type."""
        arc_manager.create_arc(
            arc_key="romance1",
            title="Romance 1",
            arc_type=ArcType.ROMANCE,
        )
        arc_manager.create_arc(
            arc_key="romance2",
            title="Romance 2",
            arc_type=ArcType.ROMANCE,
        )
        arc_manager.create_arc(
            arc_key="revenge",
            title="Revenge",
            arc_type=ArcType.REVENGE,
        )

        romance_arcs = arc_manager.get_arcs_by_type(ArcType.ROMANCE)

        assert len(romance_arcs) == 2
        assert all(a.arc_type == ArcType.ROMANCE for a in romance_arcs)


class TestStoryArcStatusChanges:
    """Tests for arc status management."""

    def test_activate_dormant_arc(self, arc_manager: StoryArcManager):
        """Verify dormant arc can be activated."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.SIDE_QUEST,
        )

        arc = arc_manager.activate_arc("test")

        assert arc.status == ArcStatus.ACTIVE
        assert arc.started_turn is not None

    def test_activate_paused_arc(self, arc_manager: StoryArcManager):
        """Verify paused arc can be reactivated."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.SIDE_QUEST,
            activate=True,
        )
        arc_manager.pause_arc("test")

        arc = arc_manager.activate_arc("test")

        assert arc.status == ArcStatus.ACTIVE

    def test_activate_completed_arc_raises(self, arc_manager: StoryArcManager):
        """Verify completed arc cannot be activated."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.SIDE_QUEST,
            activate=True,
        )
        arc_manager.complete_arc("test")

        with pytest.raises(ValueError, match="Cannot activate"):
            arc_manager.activate_arc("test")

    def test_pause_active_arc(self, arc_manager: StoryArcManager):
        """Verify active arc can be paused."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.SIDE_QUEST,
            activate=True,
        )

        arc = arc_manager.pause_arc("test")

        assert arc.status == ArcStatus.PAUSED

    def test_pause_dormant_arc_raises(self, arc_manager: StoryArcManager):
        """Verify dormant arc cannot be paused."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.SIDE_QUEST,
        )

        with pytest.raises(ValueError, match="only pause active"):
            arc_manager.pause_arc("test")

    def test_complete_arc_success(self, arc_manager: StoryArcManager):
        """Verify arc can be completed successfully."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.SIDE_QUEST,
            activate=True,
        )

        arc = arc_manager.complete_arc("test", outcome="Victory!", success=True)

        assert arc.status == ArcStatus.COMPLETED
        assert arc.outcome == "Victory!"
        assert arc.completed_turn is not None

    def test_complete_arc_failure(self, arc_manager: StoryArcManager):
        """Verify arc can be marked as failed."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.SIDE_QUEST,
            activate=True,
        )

        arc = arc_manager.complete_arc("test", outcome="Defeat", success=False)

        assert arc.status == ArcStatus.FAILED
        assert arc.outcome == "Defeat"

    def test_abandon_arc(self, arc_manager: StoryArcManager):
        """Verify arc can be abandoned."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.SIDE_QUEST,
            activate=True,
        )

        arc = arc_manager.abandon_arc("test", reason="Lost interest")

        assert arc.status == ArcStatus.ABANDONED
        assert arc.outcome == "Lost interest"


class TestPhaseProgression:
    """Tests for narrative phase management."""

    def test_advance_phase(self, arc_manager: StoryArcManager):
        """Verify phase advances correctly."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.SIDE_QUEST,
            activate=True,
        )

        arc = arc_manager.advance_phase("test")

        assert arc.current_phase == ArcPhase.RISING_ACTION
        assert arc.turns_in_phase == 0

    def test_advance_phase_full_progression(self, arc_manager: StoryArcManager):
        """Verify full phase progression."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.SIDE_QUEST,
            activate=True,
        )

        expected_phases = [
            ArcPhase.RISING_ACTION,
            ArcPhase.MIDPOINT,
            ArcPhase.ESCALATION,
            ArcPhase.CLIMAX,
            ArcPhase.FALLING_ACTION,
            ArcPhase.RESOLUTION,
            ArcPhase.AFTERMATH,
        ]

        for expected in expected_phases:
            arc = arc_manager.advance_phase("test")
            assert arc.current_phase == expected

    def test_advance_phase_at_end_raises(self, arc_manager: StoryArcManager):
        """Verify cannot advance past final phase."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.SIDE_QUEST,
            activate=True,
        )

        # Advance to aftermath
        for _ in range(7):
            arc_manager.advance_phase("test")

        with pytest.raises(ValueError, match="final phase"):
            arc_manager.advance_phase("test")

    def test_set_phase(self, arc_manager: StoryArcManager):
        """Verify phase can be set directly."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.SIDE_QUEST,
            activate=True,
        )

        arc = arc_manager.set_phase("test", ArcPhase.CLIMAX)

        assert arc.current_phase == ArcPhase.CLIMAX
        assert arc.turns_in_phase == 0

    def test_set_phase_inactive_arc_raises(self, arc_manager: StoryArcManager):
        """Verify cannot set phase on inactive arc."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.SIDE_QUEST,
        )

        with pytest.raises(ValueError, match="only set phase on active"):
            arc_manager.set_phase("test", ArcPhase.CLIMAX)


class TestTensionManagement:
    """Tests for tension level management."""

    def test_update_tension_positive(self, arc_manager: StoryArcManager):
        """Verify tension increases correctly."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.SIDE_QUEST,
        )

        arc = arc_manager.update_tension("test", delta=20)

        assert arc.tension_level == 30  # Default 10 + 20

    def test_update_tension_negative(self, arc_manager: StoryArcManager):
        """Verify tension decreases correctly."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.SIDE_QUEST,
        )

        arc = arc_manager.update_tension("test", delta=-5)

        assert arc.tension_level == 5  # Default 10 - 5

    def test_update_tension_clamped_max(self, arc_manager: StoryArcManager):
        """Verify tension clamped at 100."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.SIDE_QUEST,
        )

        arc = arc_manager.update_tension("test", delta=200)

        assert arc.tension_level == 100

    def test_update_tension_clamped_min(self, arc_manager: StoryArcManager):
        """Verify tension clamped at 0."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.SIDE_QUEST,
        )

        arc = arc_manager.update_tension("test", delta=-50)

        assert arc.tension_level == 0

    def test_set_tension(self, arc_manager: StoryArcManager):
        """Verify tension can be set directly."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.SIDE_QUEST,
        )

        arc = arc_manager.set_tension("test", level=75)

        assert arc.tension_level == 75


class TestPlantedElements:
    """Tests for Chekhov's gun management."""

    def test_plant_element(self, arc_manager: StoryArcManager):
        """Verify element can be planted."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.MYSTERY,
        )

        arc = arc_manager.plant_element(
            "test",
            element="bloody_knife",
            description="A knife found at the crime scene",
        )

        assert len(arc.planted_elements) == 1
        assert arc.planted_elements[0]["element"] == "bloody_knife"
        assert arc.planted_elements[0]["resolved"] is False

    def test_plant_multiple_elements(self, arc_manager: StoryArcManager):
        """Verify multiple elements can be planted."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.MYSTERY,
        )

        arc_manager.plant_element("test", "knife")
        arc_manager.plant_element("test", "letter")
        arc = arc_manager.plant_element("test", "witness")

        assert len(arc.planted_elements) == 3

    def test_resolve_element(self, arc_manager: StoryArcManager):
        """Verify element can be resolved."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.MYSTERY,
        )
        arc_manager.plant_element("test", "knife")

        arc = arc_manager.resolve_element(
            "test",
            element="knife",
            resolution="Used to identify the killer",
        )

        # Check planted element marked resolved
        planted = [e for e in arc.planted_elements if e["element"] == "knife"][0]
        assert planted["resolved"] is True

        # Check resolved_elements list
        assert len(arc.resolved_elements) == 1
        assert arc.resolved_elements[0]["resolution"] == "Used to identify the killer"

    def test_resolve_nonexistent_element_raises(self, arc_manager: StoryArcManager):
        """Verify resolving non-existent element raises error."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.MYSTERY,
        )

        with pytest.raises(ValueError, match="not found"):
            arc_manager.resolve_element("test", "nonexistent")

    def test_get_unresolved_elements(self, arc_manager: StoryArcManager):
        """Verify unresolved elements retrieval."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.MYSTERY,
        )
        arc_manager.plant_element("test", "knife")
        arc_manager.plant_element("test", "letter")
        arc_manager.plant_element("test", "witness")
        arc_manager.resolve_element("test", "knife")

        unresolved = arc_manager.get_unresolved_elements("test")

        assert len(unresolved) == 2
        assert "letter" in [e["element"] for e in unresolved]
        assert "witness" in [e["element"] for e in unresolved]


class TestTurnTracking:
    """Tests for turn count tracking."""

    def test_increment_turn_count_single_arc(self, arc_manager: StoryArcManager):
        """Verify turn count increments for specific arc."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.SIDE_QUEST,
            activate=True,
        )

        arc_manager.increment_turn_count("test")
        arc = arc_manager.get_arc("test")

        assert arc.turns_in_phase == 1

    def test_increment_turn_count_all_active(self, arc_manager: StoryArcManager):
        """Verify turn count increments for all active arcs."""
        arc_manager.create_arc(
            arc_key="active1",
            title="Active 1",
            arc_type=ArcType.SIDE_QUEST,
            activate=True,
        )
        arc_manager.create_arc(
            arc_key="active2",
            title="Active 2",
            arc_type=ArcType.ROMANCE,
            activate=True,
        )
        arc_manager.create_arc(
            arc_key="dormant",
            title="Dormant",
            arc_type=ArcType.MYSTERY,
        )

        arc_manager.increment_turn_count()

        assert arc_manager.get_arc("active1").turns_in_phase == 1
        assert arc_manager.get_arc("active2").turns_in_phase == 1
        assert arc_manager.get_arc("dormant").turns_in_phase == 0

    def test_increment_turn_count_dormant_arc_ignored(
        self, arc_manager: StoryArcManager
    ):
        """Verify dormant arc is not incremented."""
        arc_manager.create_arc(
            arc_key="dormant",
            title="Dormant",
            arc_type=ArcType.SIDE_QUEST,
        )

        arc_manager.increment_turn_count("dormant")
        arc = arc_manager.get_arc("dormant")

        assert arc.turns_in_phase == 0


class TestPacingHints:
    """Tests for pacing guidance."""

    def test_hint_low_tension(self, arc_manager: StoryArcManager):
        """Verify hint generated for low tension."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.SIDE_QUEST,
            activate=True,
        )
        arc_manager.set_phase("test", ArcPhase.ESCALATION)
        arc_manager.set_tension("test", 30)  # Too low for escalation

        hints = arc_manager.get_pacing_hints()

        tension_hints = [h for h in hints if "low" in h.message.lower()]
        assert len(tension_hints) > 0

    def test_hint_high_tension(self, arc_manager: StoryArcManager):
        """Verify hint generated for high tension."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.SIDE_QUEST,
            activate=True,
        )
        # Setup phase with very high tension
        arc_manager.set_tension("test", 95)

        hints = arc_manager.get_pacing_hints()

        tension_hints = [h for h in hints if "high" in h.message.lower()]
        assert len(tension_hints) > 0

    def test_hint_phase_too_long(self, arc_manager: StoryArcManager):
        """Verify hint generated for lingering phase."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.SIDE_QUEST,
            activate=True,
        )
        # Simulate many turns in phase
        for _ in range(10):
            arc_manager.increment_turn_count("test")

        hints = arc_manager.get_pacing_hints()

        duration_hints = [h for h in hints if "turns" in h.message.lower()]
        assert len(duration_hints) > 0

    def test_hint_unresolved_elements_late_phase(self, arc_manager: StoryArcManager):
        """Verify hint for unresolved elements in late phases."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.MYSTERY,
            activate=True,
        )
        arc_manager.plant_element("test", "knife")
        arc_manager.set_phase("test", ArcPhase.RESOLUTION)

        hints = arc_manager.get_pacing_hints()

        unresolved_hints = [h for h in hints if "unresolved" in h.message.lower()]
        assert len(unresolved_hints) > 0
        assert unresolved_hints[0].urgency == "high"

    def test_hint_climax_ready(self, arc_manager: StoryArcManager):
        """Verify hint when arc is ready for climax."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.SIDE_QUEST,
            activate=True,
        )
        arc_manager.set_phase("test", ArcPhase.ESCALATION)
        arc_manager.set_tension("test", 80)

        hints = arc_manager.get_pacing_hints()

        climax_hints = [h for h in hints if "climax" in h.message.lower()]
        assert len(climax_hints) > 0


class TestArcSummary:
    """Tests for arc summary generation."""

    def test_get_arc_summary(self, arc_manager: StoryArcManager):
        """Verify arc summary generation."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test Arc",
            arc_type=ArcType.MYSTERY,
            stakes="Life or death",
            activate=True,
        )
        arc_manager.set_tension("test", 50)
        arc_manager.plant_element("test", "knife")
        arc_manager.set_next_beat_hint("test", "Introduce suspect")

        summary = arc_manager.get_arc_summary("test")

        assert summary.arc_key == "test"
        assert summary.title == "Test Arc"
        assert summary.arc_type == "mystery"
        assert summary.status == "active"
        assert summary.phase == "setup"
        assert summary.tension == 50
        assert summary.stakes == "Life or death"
        assert "knife" in summary.unresolved_elements
        assert summary.next_beat_hint == "Introduce suspect"

    def test_get_arc_summary_not_found(self, arc_manager: StoryArcManager):
        """Verify None returned for non-existent arc."""
        summary = arc_manager.get_arc_summary("nonexistent")
        assert summary is None

    def test_get_active_arcs_context(self, arc_manager: StoryArcManager):
        """Verify context string generation."""
        arc_manager.create_arc(
            arc_key="main",
            title="Main Quest",
            arc_type=ArcType.MAIN_QUEST,
            stakes="Save the kingdom",
            activate=True,
        )
        arc_manager.set_tension("main", 70)

        context = arc_manager.get_active_arcs_context()

        assert "Active Story Arcs" in context
        assert "Main Quest" in context
        assert "main_quest" in context
        assert "70/100" in context
        assert "Save the kingdom" in context

    def test_get_active_arcs_context_empty(self, arc_manager: StoryArcManager):
        """Verify empty context when no active arcs."""
        context = arc_manager.get_active_arcs_context()
        assert context == ""


class TestNextBeatHint:
    """Tests for next beat hint management."""

    def test_set_next_beat_hint(self, arc_manager: StoryArcManager):
        """Verify next beat hint can be set."""
        arc_manager.create_arc(
            arc_key="test",
            title="Test",
            arc_type=ArcType.SIDE_QUEST,
        )

        arc = arc_manager.set_next_beat_hint("test", "Introduce the villain")

        assert arc.next_beat_hint == "Introduce the villain"

    def test_set_next_beat_hint_not_found_raises(self, arc_manager: StoryArcManager):
        """Verify error when arc not found."""
        with pytest.raises(ValueError, match="not found"):
            arc_manager.set_next_beat_hint("nonexistent", "hint")
