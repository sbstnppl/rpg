"""Tests for MysteryManager - mystery, clue, and revelation tracking."""

import pytest
from sqlalchemy.orm import Session

from src.database.models import (
    ArcType,
    GameSession,
    Mystery,
    StoryArc,
)
from src.managers.mystery_manager import MysteryManager, MysteryStatus
from src.managers.story_arc_manager import StoryArcManager


@pytest.fixture
def mystery_manager(db_session: Session, game_session: GameSession) -> MysteryManager:
    """Create a MysteryManager instance."""
    return MysteryManager(db_session, game_session)


@pytest.fixture
def arc_manager(db_session: Session, game_session: GameSession) -> StoryArcManager:
    """Create a StoryArcManager instance."""
    return StoryArcManager(db_session, game_session)


class TestMysteryCreation:
    """Tests for creating mysteries."""

    def test_create_mystery_basic(self, mystery_manager: MysteryManager):
        """Verify basic mystery creation."""
        mystery = mystery_manager.create_mystery(
            mystery_key="who_killed_mayor",
            title="Who Killed the Mayor?",
            truth="The butler did it with poison.",
        )

        assert mystery.mystery_key == "who_killed_mayor"
        assert mystery.title == "Who Killed the Mayor?"
        assert mystery.truth == "The butler did it with poison."
        assert mystery.is_solved is False

    def test_create_mystery_with_clues(self, mystery_manager: MysteryManager):
        """Verify mystery with clues."""
        clues = [
            {"clue_id": "poison_vial", "description": "Empty poison vial", "location": "kitchen"},
            {"clue_id": "torn_letter", "description": "A torn letter", "location": "study"},
        ]
        mystery = mystery_manager.create_mystery(
            mystery_key="murder",
            title="Murder Mystery",
            truth="The truth",
            clues=clues,
        )

        assert mystery.total_clues == 2
        assert mystery.clues_discovered == 0
        assert len(mystery.clues) == 2

    def test_create_mystery_with_red_herrings(self, mystery_manager: MysteryManager):
        """Verify mystery with red herrings."""
        red_herrings = [
            {"suspect": "gardener", "evidence": "had a grudge"},
            {"suspect": "maid", "evidence": "was seen arguing"},
        ]
        mystery = mystery_manager.create_mystery(
            mystery_key="whodunit",
            title="Whodunit",
            truth="The truth",
            red_herrings=red_herrings,
        )

        assert len(mystery.red_herrings) == 2

    def test_create_mystery_duplicate_key_raises(self, mystery_manager: MysteryManager):
        """Verify duplicate key raises error."""
        mystery_manager.create_mystery(
            mystery_key="unique",
            title="First",
            truth="Truth",
        )

        with pytest.raises(ValueError, match="already exists"):
            mystery_manager.create_mystery(
                mystery_key="unique",
                title="Second",
                truth="Truth 2",
            )

    def test_create_mystery_with_story_arc(
        self,
        mystery_manager: MysteryManager,
        arc_manager: StoryArcManager,
    ):
        """Verify mystery can be linked to story arc on creation."""
        arc = arc_manager.create_arc(
            arc_key="mystery_arc",
            title="Mystery Arc",
            arc_type=ArcType.MYSTERY,
        )

        mystery = mystery_manager.create_mystery(
            mystery_key="linked",
            title="Linked Mystery",
            truth="The truth",
            story_arc_id=arc.id,
        )

        assert mystery.story_arc_id == arc.id


class TestMysteryRetrieval:
    """Tests for retrieving mysteries."""

    def test_get_mystery(self, mystery_manager: MysteryManager):
        """Verify mystery retrieval by key."""
        mystery_manager.create_mystery(
            mystery_key="test",
            title="Test",
            truth="Truth",
        )

        mystery = mystery_manager.get_mystery("test")
        assert mystery is not None
        assert mystery.mystery_key == "test"

    def test_get_mystery_not_found(self, mystery_manager: MysteryManager):
        """Verify None returned for non-existent mystery."""
        mystery = mystery_manager.get_mystery("nonexistent")
        assert mystery is None

    def test_get_unsolved_mysteries(self, mystery_manager: MysteryManager):
        """Verify unsolved mysteries retrieval."""
        mystery_manager.create_mystery(
            mystery_key="unsolved1",
            title="Unsolved 1",
            truth="Truth 1",
        )
        mystery_manager.create_mystery(
            mystery_key="unsolved2",
            title="Unsolved 2",
            truth="Truth 2",
        )
        mystery_manager.create_mystery(
            mystery_key="solved",
            title="Solved",
            truth="Truth 3",
        )
        mystery_manager.solve_mystery("solved")

        unsolved = mystery_manager.get_unsolved_mysteries()

        assert len(unsolved) == 2
        assert all(not m.is_solved for m in unsolved)

    def test_get_mysteries_by_arc(
        self,
        mystery_manager: MysteryManager,
        arc_manager: StoryArcManager,
    ):
        """Verify mysteries retrieval by arc."""
        arc = arc_manager.create_arc(
            arc_key="arc",
            title="Arc",
            arc_type=ArcType.MYSTERY,
        )

        mystery_manager.create_mystery(
            mystery_key="linked1",
            title="Linked 1",
            truth="Truth",
            story_arc_id=arc.id,
        )
        mystery_manager.create_mystery(
            mystery_key="linked2",
            title="Linked 2",
            truth="Truth",
            story_arc_id=arc.id,
        )
        mystery_manager.create_mystery(
            mystery_key="unlinked",
            title="Unlinked",
            truth="Truth",
        )

        arc_mysteries = mystery_manager.get_mysteries_by_arc(arc.id)

        assert len(arc_mysteries) == 2


class TestClueManagement:
    """Tests for clue operations."""

    def test_add_clue(self, mystery_manager: MysteryManager):
        """Verify clue can be added."""
        mystery_manager.create_mystery(
            mystery_key="test",
            title="Test",
            truth="Truth",
        )

        mystery = mystery_manager.add_clue(
            "test",
            clue_id="new_clue",
            description="A new clue",
            location="garden",
            importance="high",
        )

        assert mystery.total_clues == 1
        assert mystery.clues[0]["clue_id"] == "new_clue"
        assert mystery.clues[0]["importance"] == "high"

    def test_add_clue_duplicate_raises(self, mystery_manager: MysteryManager):
        """Verify duplicate clue_id raises error."""
        mystery_manager.create_mystery(
            mystery_key="test",
            title="Test",
            truth="Truth",
        )
        mystery_manager.add_clue("test", clue_id="clue1", description="First")

        with pytest.raises(ValueError, match="already exists"):
            mystery_manager.add_clue("test", clue_id="clue1", description="Duplicate")

    def test_discover_clue(self, mystery_manager: MysteryManager):
        """Verify clue can be discovered."""
        mystery_manager.create_mystery(
            mystery_key="test",
            title="Test",
            truth="Truth",
            clues=[{"clue_id": "clue1", "description": "A clue"}],
        )

        mystery, clue = mystery_manager.discover_clue("test", "clue1")

        assert mystery.clues_discovered == 1
        assert clue["discovered"] is True
        assert clue["discovered_turn"] is not None

    def test_discover_clue_already_discovered_raises(
        self, mystery_manager: MysteryManager
    ):
        """Verify discovering already discovered clue raises error."""
        mystery_manager.create_mystery(
            mystery_key="test",
            title="Test",
            truth="Truth",
            clues=[{"clue_id": "clue1", "description": "A clue"}],
        )
        mystery_manager.discover_clue("test", "clue1")

        with pytest.raises(ValueError, match="already discovered"):
            mystery_manager.discover_clue("test", "clue1")

    def test_discover_clue_not_found_raises(self, mystery_manager: MysteryManager):
        """Verify discovering non-existent clue raises error."""
        mystery_manager.create_mystery(
            mystery_key="test",
            title="Test",
            truth="Truth",
        )

        with pytest.raises(ValueError, match="not found"):
            mystery_manager.discover_clue("test", "nonexistent")

    def test_get_discovered_clues(self, mystery_manager: MysteryManager):
        """Verify discovered clues retrieval."""
        mystery_manager.create_mystery(
            mystery_key="test",
            title="Test",
            truth="Truth",
            clues=[
                {"clue_id": "clue1", "description": "First"},
                {"clue_id": "clue2", "description": "Second"},
                {"clue_id": "clue3", "description": "Third"},
            ],
        )
        mystery_manager.discover_clue("test", "clue1")
        mystery_manager.discover_clue("test", "clue3")

        discovered = mystery_manager.get_discovered_clues("test")

        assert len(discovered) == 2
        assert all(c["discovered"] for c in discovered)

    def test_get_undiscovered_clues(self, mystery_manager: MysteryManager):
        """Verify undiscovered clues retrieval."""
        mystery_manager.create_mystery(
            mystery_key="test",
            title="Test",
            truth="Truth",
            clues=[
                {"clue_id": "clue1", "description": "First"},
                {"clue_id": "clue2", "description": "Second"},
            ],
        )
        mystery_manager.discover_clue("test", "clue1")

        undiscovered = mystery_manager.get_undiscovered_clues("test")

        assert len(undiscovered) == 1
        assert undiscovered[0]["clue_id"] == "clue2"

    def test_get_clue_at_location(self, mystery_manager: MysteryManager):
        """Verify clues retrieval by location."""
        mystery_manager.create_mystery(
            mystery_key="test",
            title="Test",
            truth="Truth",
            clues=[
                {"clue_id": "clue1", "description": "First", "location": "kitchen"},
                {"clue_id": "clue2", "description": "Second", "location": "garden"},
                {"clue_id": "clue3", "description": "Third", "location": "kitchen"},
            ],
        )

        kitchen_clues = mystery_manager.get_clue_at_location("test", "kitchen")

        assert len(kitchen_clues) == 2

    def test_get_all_clues_at_location(self, mystery_manager: MysteryManager):
        """Verify clues retrieval across all mysteries."""
        mystery_manager.create_mystery(
            mystery_key="mystery1",
            title="Mystery 1",
            truth="Truth",
            clues=[{"clue_id": "clue1", "description": "First", "location": "tavern"}],
        )
        mystery_manager.create_mystery(
            mystery_key="mystery2",
            title="Mystery 2",
            truth="Truth",
            clues=[{"clue_id": "clue2", "description": "Second", "location": "tavern"}],
        )

        tavern_clues = mystery_manager.get_all_clues_at_location("tavern")

        assert len(tavern_clues) == 2
        assert tavern_clues[0][0] in ("mystery1", "mystery2")


class TestRedHerringManagement:
    """Tests for red herring operations."""

    def test_add_red_herring(self, mystery_manager: MysteryManager):
        """Verify red herring can be added."""
        mystery_manager.create_mystery(
            mystery_key="test",
            title="Test",
            truth="Truth",
        )

        mystery = mystery_manager.add_red_herring(
            "test",
            suspect="gardener",
            evidence="was seen near the scene",
        )

        assert len(mystery.red_herrings) == 1
        assert mystery.red_herrings[0]["suspect"] == "gardener"

    def test_reveal_red_herring(self, mystery_manager: MysteryManager):
        """Verify red herring can be revealed as false."""
        mystery_manager.create_mystery(
            mystery_key="test",
            title="Test",
            truth="Truth",
            red_herrings=[{"suspect": "gardener", "evidence": "evidence"}],
        )

        mystery = mystery_manager.reveal_red_herring("test", "gardener")

        assert mystery.red_herrings[0]["revealed_as_false"] is True

    def test_reveal_red_herring_not_found_raises(
        self, mystery_manager: MysteryManager
    ):
        """Verify revealing non-existent red herring raises error."""
        mystery_manager.create_mystery(
            mystery_key="test",
            title="Test",
            truth="Truth",
        )

        with pytest.raises(ValueError, match="not found"):
            mystery_manager.reveal_red_herring("test", "nonexistent")


class TestPlayerTheory:
    """Tests for player theory tracking."""

    def test_set_player_theory(self, mystery_manager: MysteryManager):
        """Verify player theory can be set."""
        mystery_manager.create_mystery(
            mystery_key="test",
            title="Test",
            truth="Truth",
        )

        mystery = mystery_manager.set_player_theory(
            "test",
            theory="I think the butler did it",
        )

        assert mystery.player_theory == "I think the butler did it"

    def test_set_player_theory_updates(self, mystery_manager: MysteryManager):
        """Verify player theory can be updated."""
        mystery_manager.create_mystery(
            mystery_key="test",
            title="Test",
            truth="Truth",
        )
        mystery_manager.set_player_theory("test", "First theory")
        mystery = mystery_manager.set_player_theory("test", "Revised theory")

        assert mystery.player_theory == "Revised theory"


class TestMysterySolving:
    """Tests for solving mysteries."""

    def test_solve_mystery(self, mystery_manager: MysteryManager):
        """Verify mystery can be solved."""
        mystery_manager.create_mystery(
            mystery_key="test",
            title="Test",
            truth="Truth",
        )

        mystery = mystery_manager.solve_mystery("test")

        assert mystery.is_solved is True
        assert mystery.solved_turn is not None

    def test_solve_mystery_already_solved_raises(
        self, mystery_manager: MysteryManager
    ):
        """Verify solving already solved mystery raises error."""
        mystery_manager.create_mystery(
            mystery_key="test",
            title="Test",
            truth="Truth",
        )
        mystery_manager.solve_mystery("test")

        with pytest.raises(ValueError, match="already solved"):
            mystery_manager.solve_mystery("test")

    def test_check_revelation_ready_no_clues(self, mystery_manager: MysteryManager):
        """Verify mystery with no clues is always ready."""
        mystery_manager.create_mystery(
            mystery_key="test",
            title="Test",
            truth="Truth",
        )

        assert mystery_manager.check_revelation_ready("test") is True

    def test_check_revelation_ready_critical_clues(
        self, mystery_manager: MysteryManager
    ):
        """Verify ready when all critical clues discovered."""
        mystery_manager.create_mystery(
            mystery_key="test",
            title="Test",
            truth="Truth",
            clues=[
                {"clue_id": "critical1", "description": "Critical", "importance": "critical"},
                {"clue_id": "normal", "description": "Normal", "importance": "medium"},
            ],
        )
        mystery_manager.discover_clue("test", "critical1")

        assert mystery_manager.check_revelation_ready("test") is True

    def test_check_revelation_ready_percentage(self, mystery_manager: MysteryManager):
        """Verify ready when >= 75% clues discovered."""
        mystery_manager.create_mystery(
            mystery_key="test",
            title="Test",
            truth="Truth",
            clues=[
                {"clue_id": "clue1", "description": "1"},
                {"clue_id": "clue2", "description": "2"},
                {"clue_id": "clue3", "description": "3"},
                {"clue_id": "clue4", "description": "4"},
            ],
        )
        # Discover 3 of 4 = 75%
        mystery_manager.discover_clue("test", "clue1")
        mystery_manager.discover_clue("test", "clue2")
        mystery_manager.discover_clue("test", "clue3")

        assert mystery_manager.check_revelation_ready("test") is True

    def test_check_revelation_not_ready(self, mystery_manager: MysteryManager):
        """Verify not ready when too few clues discovered."""
        mystery_manager.create_mystery(
            mystery_key="test",
            title="Test",
            truth="Truth",
            clues=[
                {"clue_id": "clue1", "description": "1"},
                {"clue_id": "clue2", "description": "2"},
                {"clue_id": "clue3", "description": "3"},
                {"clue_id": "clue4", "description": "4"},
            ],
        )
        # Discover 1 of 4 = 25%
        mystery_manager.discover_clue("test", "clue1")

        assert mystery_manager.check_revelation_ready("test") is False


class TestMysteryStatus:
    """Tests for mystery status reporting."""

    def test_get_mystery_status(self, mystery_manager: MysteryManager):
        """Verify status generation."""
        mystery_manager.create_mystery(
            mystery_key="test",
            title="Test Mystery",
            truth="Truth",
            clues=[
                {"clue_id": "clue1", "description": "1"},
                {"clue_id": "clue2", "description": "2"},
            ],
        )
        mystery_manager.discover_clue("test", "clue1")
        mystery_manager.set_player_theory("test", "My theory")

        status = mystery_manager.get_mystery_status("test")

        assert status.mystery_key == "test"
        assert status.title == "Test Mystery"
        assert status.clues_discovered == 1
        assert status.total_clues == 2
        assert status.progress_percentage == 50.0
        assert status.is_solved is False
        assert status.player_theory == "My theory"
        assert "clue2" in status.unresolved_clues

    def test_get_mystery_status_not_found(self, mystery_manager: MysteryManager):
        """Verify None returned for non-existent mystery."""
        status = mystery_manager.get_mystery_status("nonexistent")
        assert status is None

    def test_get_mysteries_context(self, mystery_manager: MysteryManager):
        """Verify context string generation."""
        mystery_manager.create_mystery(
            mystery_key="murder",
            title="Murder at the Manor",
            truth="Truth",
            clues=[
                {"clue_id": "clue1", "description": "1"},
                {"clue_id": "clue2", "description": "2"},
            ],
        )
        mystery_manager.discover_clue("murder", "clue1")

        context = mystery_manager.get_mysteries_context()

        assert "Active Mysteries" in context
        assert "Murder at the Manor" in context
        assert "1/2" in context
        assert "50" in context  # percentage

    def test_get_mysteries_context_empty(self, mystery_manager: MysteryManager):
        """Verify empty context when no unsolved mysteries."""
        context = mystery_manager.get_mysteries_context()
        assert context == ""

    def test_get_mysteries_context_with_theory(self, mystery_manager: MysteryManager):
        """Verify context includes player theory."""
        mystery_manager.create_mystery(
            mystery_key="test",
            title="Test",
            truth="Truth",
        )
        mystery_manager.set_player_theory("test", "Butler did it")

        context = mystery_manager.get_mysteries_context()

        assert "Butler did it" in context


class TestStoryArcLinking:
    """Tests for story arc linking."""

    def test_link_to_story_arc(
        self,
        mystery_manager: MysteryManager,
        arc_manager: StoryArcManager,
    ):
        """Verify mystery can be linked to arc."""
        arc = arc_manager.create_arc(
            arc_key="arc",
            title="Arc",
            arc_type=ArcType.MYSTERY,
        )
        mystery_manager.create_mystery(
            mystery_key="test",
            title="Test",
            truth="Truth",
        )

        mystery = mystery_manager.link_to_story_arc("test", arc.id)

        assert mystery.story_arc_id == arc.id

    def test_link_to_story_arc_not_found_raises(
        self, mystery_manager: MysteryManager
    ):
        """Verify linking non-existent mystery raises error."""
        with pytest.raises(ValueError, match="not found"):
            mystery_manager.link_to_story_arc("nonexistent", 1)
