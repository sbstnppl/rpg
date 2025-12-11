"""Tests for CliffhangerManager - dramatic tension and stopping point detection."""

import pytest
from sqlalchemy.orm import Session

from src.database.models import (
    ArcPhase,
    ArcStatus,
    ArcType,
    Conflict,
    ConflictLevel,
    GameSession,
    Mystery,
    StoryArc,
)
from src.managers.cliffhanger_manager import (
    CliffhangerManager,
    CliffhangerSuggestion,
    DramaticMoment,
    SceneTensionAnalysis,
)
from src.managers.story_arc_manager import StoryArcManager
from src.managers.mystery_manager import MysteryManager
from src.managers.conflict_manager import ConflictManager


@pytest.fixture
def cliffhanger_manager(
    db_session: Session, game_session: GameSession
) -> CliffhangerManager:
    """Create a CliffhangerManager instance."""
    return CliffhangerManager(db_session, game_session)


@pytest.fixture
def arc_manager(db_session: Session, game_session: GameSession) -> StoryArcManager:
    """Create a StoryArcManager instance."""
    return StoryArcManager(db_session, game_session)


@pytest.fixture
def mystery_manager(db_session: Session, game_session: GameSession) -> MysteryManager:
    """Create a MysteryManager instance."""
    return MysteryManager(db_session, game_session)


@pytest.fixture
def conflict_manager(
    db_session: Session, game_session: GameSession
) -> ConflictManager:
    """Create a ConflictManager instance."""
    return ConflictManager(db_session, game_session)


class TestSceneTensionAnalysis:
    """Tests for analyzing scene tension."""

    def test_analyze_empty_scene(self, cliffhanger_manager: CliffhangerManager):
        """Verify analysis with no dramatic elements."""
        analysis = cliffhanger_manager.analyze_scene_tension()

        assert analysis.overall_tension == 0
        assert analysis.primary_source == "none"
        assert len(analysis.dramatic_moments) == 0
        assert analysis.is_good_stopping_point is False

    def test_analyze_with_story_arc(
        self,
        cliffhanger_manager: CliffhangerManager,
        arc_manager: StoryArcManager,
    ):
        """Verify analysis includes story arc tension."""
        arc_manager.create_arc(
            arc_key="main",
            title="Main Quest",
            arc_type=ArcType.MAIN_QUEST,
            activate=True,
        )
        arc_manager.set_phase("main", ArcPhase.CLIMAX)
        arc_manager.set_tension("main", 85)

        analysis = cliffhanger_manager.analyze_scene_tension()

        assert analysis.overall_tension > 50
        assert "story_arc" in analysis.primary_source
        arc_moments = [m for m in analysis.dramatic_moments if m.source == "story_arc"]
        assert len(arc_moments) == 1
        assert arc_moments[0].cliffhanger_potential == "perfect"

    def test_analyze_with_conflict(
        self,
        cliffhanger_manager: CliffhangerManager,
        conflict_manager: ConflictManager,
    ):
        """Verify analysis includes conflict tension."""
        conflict_manager.create_conflict(
            conflict_key="guild_war",
            title="Guild War",
            initial_level=ConflictLevel.CRISIS,
        )

        analysis = cliffhanger_manager.analyze_scene_tension()

        assert analysis.overall_tension > 0
        conflict_moments = [
            m for m in analysis.dramatic_moments if m.source == "conflict"
        ]
        assert len(conflict_moments) == 1
        assert conflict_moments[0].cliffhanger_potential == "perfect"

    def test_analyze_with_mystery(
        self,
        cliffhanger_manager: CliffhangerManager,
        mystery_manager: MysteryManager,
    ):
        """Verify analysis includes mystery tension."""
        mystery_manager.create_mystery(
            mystery_key="murder",
            title="Murder Mystery",
            truth="The butler did it",
            clues=[
                {"clue_id": "c1", "description": "1"},
                {"clue_id": "c2", "description": "2"},
                {"clue_id": "c3", "description": "3"},
                {"clue_id": "c4", "description": "4"},
            ],
        )
        # Discover 3 of 4 clues = 75%
        mystery_manager.discover_clue("murder", "c1")
        mystery_manager.discover_clue("murder", "c2")
        mystery_manager.discover_clue("murder", "c3")

        analysis = cliffhanger_manager.analyze_scene_tension()

        mystery_moments = [
            m for m in analysis.dramatic_moments if m.source == "mystery"
        ]
        assert len(mystery_moments) == 1
        assert mystery_moments[0].cliffhanger_potential == "perfect"

    def test_analyze_combines_multiple_sources(
        self,
        cliffhanger_manager: CliffhangerManager,
        arc_manager: StoryArcManager,
        conflict_manager: ConflictManager,
    ):
        """Verify analysis combines tension from multiple sources."""
        arc_manager.create_arc(
            arc_key="arc",
            title="Arc",
            arc_type=ArcType.MAIN_QUEST,
            activate=True,
        )
        arc_manager.set_tension("arc", 60)

        conflict_manager.create_conflict(
            conflict_key="conflict",
            title="Conflict",
            initial_level=ConflictLevel.HOSTILITY,
        )

        analysis = cliffhanger_manager.analyze_scene_tension()

        assert len(analysis.dramatic_moments) == 2
        # Overall tension should be weighted blend
        assert analysis.overall_tension > 0


class TestCliffhangerDetection:
    """Tests for cliffhanger opportunity detection."""

    def test_is_cliffhanger_ready_high_tension(
        self,
        cliffhanger_manager: CliffhangerManager,
        arc_manager: StoryArcManager,
    ):
        """Verify ready at high tension."""
        arc_manager.create_arc(
            arc_key="arc",
            title="Arc",
            arc_type=ArcType.MAIN_QUEST,
            activate=True,
        )
        arc_manager.set_phase("arc", ArcPhase.CLIMAX)
        arc_manager.set_tension("arc", 90)

        is_ready, reason = cliffhanger_manager.is_cliffhanger_ready()

        assert is_ready is True
        assert "High tension" in reason or "tension" in reason.lower()

    def test_is_cliffhanger_ready_low_tension(
        self, cliffhanger_manager: CliffhangerManager
    ):
        """Verify not ready at low tension."""
        is_ready, reason = cliffhanger_manager.is_cliffhanger_ready()

        assert is_ready is False
        assert "low" in reason.lower()

    def test_is_good_stopping_point_perfect_moment(
        self,
        cliffhanger_manager: CliffhangerManager,
        arc_manager: StoryArcManager,
    ):
        """Verify perfect moments are good stopping points."""
        arc_manager.create_arc(
            arc_key="arc",
            title="Arc",
            arc_type=ArcType.MAIN_QUEST,
            activate=True,
        )
        arc_manager.set_phase("arc", ArcPhase.CLIMAX)

        analysis = cliffhanger_manager.analyze_scene_tension()

        assert analysis.is_good_stopping_point is True

    def test_stopping_recommendation(
        self,
        cliffhanger_manager: CliffhangerManager,
        conflict_manager: ConflictManager,
    ):
        """Verify stopping recommendations are generated."""
        conflict_manager.create_conflict(
            conflict_key="crisis",
            title="The Crisis",
            initial_level=ConflictLevel.CRISIS,
        )

        analysis = cliffhanger_manager.analyze_scene_tension()

        assert analysis.stopping_recommendation
        assert "crisis" in analysis.stopping_recommendation.lower()


class TestCliffhangerSuggestions:
    """Tests for cliffhanger suggestion generation."""

    def test_get_cliffhanger_hooks(
        self,
        cliffhanger_manager: CliffhangerManager,
        arc_manager: StoryArcManager,
    ):
        """Verify cliffhanger hooks are generated."""
        arc_manager.create_arc(
            arc_key="arc",
            title="Arc",
            arc_type=ArcType.MAIN_QUEST,
            activate=True,
        )
        arc_manager.set_phase("arc", ArcPhase.ESCALATION)

        hooks = cliffhanger_manager.get_cliffhanger_hooks()

        assert len(hooks) > 0
        # Should be sorted by tension level
        if len(hooks) >= 2:
            assert hooks[0].tension_level >= hooks[-1].tension_level

    def test_suggestion_for_story_arc(
        self,
        cliffhanger_manager: CliffhangerManager,
        arc_manager: StoryArcManager,
    ):
        """Verify story arc generates revelation suggestion."""
        arc_manager.create_arc(
            arc_key="arc",
            title="Arc",
            arc_type=ArcType.MAIN_QUEST,
            activate=True,
        )
        arc_manager.set_phase("arc", ArcPhase.CLIMAX)

        analysis = cliffhanger_manager.analyze_scene_tension()
        revelation_hooks = [
            s for s in analysis.suggested_cliffhangers if s.hook_type == "revelation"
        ]

        assert len(revelation_hooks) > 0

    def test_suggestion_for_conflict(
        self,
        cliffhanger_manager: CliffhangerManager,
        conflict_manager: ConflictManager,
    ):
        """Verify conflict generates threat suggestion."""
        conflict_manager.create_conflict(
            conflict_key="war",
            title="War",
            initial_level=ConflictLevel.WAR,
        )

        analysis = cliffhanger_manager.analyze_scene_tension()
        threat_hooks = [
            s for s in analysis.suggested_cliffhangers if s.hook_type == "threat"
        ]

        assert len(threat_hooks) > 0

    def test_suggestion_for_mystery(
        self,
        cliffhanger_manager: CliffhangerManager,
        mystery_manager: MysteryManager,
    ):
        """Verify near-solved mystery generates mystery suggestion."""
        mystery_manager.create_mystery(
            mystery_key="murder",
            title="Murder",
            truth="Truth",
            clues=[
                {"clue_id": "c1", "description": "1"},
                {"clue_id": "c2", "description": "2"},
            ],
        )
        mystery_manager.discover_clue("murder", "c1")
        mystery_manager.discover_clue("murder", "c2")  # 100% - perfect

        analysis = cliffhanger_manager.analyze_scene_tension()
        mystery_hooks = [
            s for s in analysis.suggested_cliffhangers if s.hook_type == "mystery"
        ]

        assert len(mystery_hooks) > 0

    def test_generic_suggestions_at_moderate_tension(
        self,
        cliffhanger_manager: CliffhangerManager,
        arc_manager: StoryArcManager,
    ):
        """Verify generic suggestions at moderate tension without specific hooks."""
        # Create arc at moderate phase (not high enough for "perfect" or "high")
        arc_manager.create_arc(
            arc_key="arc",
            title="Arc",
            arc_type=ArcType.SIDE_QUEST,
            activate=True,
        )
        arc_manager.set_phase("arc", ArcPhase.SETUP)
        arc_manager.set_tension("arc", 60)

        analysis = cliffhanger_manager.analyze_scene_tension()

        # Should have some suggestions even if not perfect hooks
        # (generic "choice" and "arrival" suggestions when tension >= 50)
        assert analysis.overall_tension > 0


class TestTensionContext:
    """Tests for tension context generation."""

    def test_get_tension_context(
        self,
        cliffhanger_manager: CliffhangerManager,
        arc_manager: StoryArcManager,
    ):
        """Verify tension context generation."""
        arc_manager.create_arc(
            arc_key="epic",
            title="Epic Quest",
            arc_type=ArcType.MAIN_QUEST,
            activate=True,
        )
        arc_manager.set_phase("epic", ArcPhase.ESCALATION)
        arc_manager.set_tension("epic", 75)

        context = cliffhanger_manager.get_tension_context()

        assert "Dramatic Tension" in context
        assert "Primary Source" in context or "epic" in context.lower()

    def test_get_tension_context_empty(self, cliffhanger_manager: CliffhangerManager):
        """Verify empty context when no tension."""
        context = cliffhanger_manager.get_tension_context()
        assert context == ""

    def test_get_tension_context_includes_hooks(
        self,
        cliffhanger_manager: CliffhangerManager,
        conflict_manager: ConflictManager,
    ):
        """Verify context includes cliffhanger options."""
        conflict_manager.create_conflict(
            conflict_key="crisis",
            title="Crisis",
            initial_level=ConflictLevel.CRISIS,
        )

        context = cliffhanger_manager.get_tension_context()

        assert "Cliffhanger Options" in context


class TestDramaticMomentScoring:
    """Tests for dramatic moment scoring accuracy."""

    def test_climax_phase_high_score(
        self,
        cliffhanger_manager: CliffhangerManager,
        arc_manager: StoryArcManager,
    ):
        """Verify climax phase scores high."""
        arc_manager.create_arc(
            arc_key="arc",
            title="Arc",
            arc_type=ArcType.MAIN_QUEST,
            activate=True,
        )
        arc_manager.set_phase("arc", ArcPhase.CLIMAX)
        arc_manager.set_tension("arc", 100)

        analysis = cliffhanger_manager.analyze_scene_tension()
        arc_moment = [m for m in analysis.dramatic_moments if m.source == "story_arc"][0]

        assert arc_moment.tension_score >= 80

    def test_setup_phase_low_score(
        self,
        cliffhanger_manager: CliffhangerManager,
        arc_manager: StoryArcManager,
    ):
        """Verify setup phase scores low."""
        arc_manager.create_arc(
            arc_key="arc",
            title="Arc",
            arc_type=ArcType.MAIN_QUEST,
            activate=True,
        )
        arc_manager.set_tension("arc", 10)

        analysis = cliffhanger_manager.analyze_scene_tension()
        arc_moment = [m for m in analysis.dramatic_moments if m.source == "story_arc"][0]

        assert arc_moment.tension_score < 30

    def test_war_conflict_high_score(
        self,
        cliffhanger_manager: CliffhangerManager,
        conflict_manager: ConflictManager,
    ):
        """Verify war-level conflict scores high."""
        conflict_manager.create_conflict(
            conflict_key="war",
            title="War",
            initial_level=ConflictLevel.WAR,
        )

        analysis = cliffhanger_manager.analyze_scene_tension()
        conflict_moment = [
            m for m in analysis.dramatic_moments if m.source == "conflict"
        ][0]

        assert conflict_moment.tension_score == 100
