"""Tests for ConflictManager - conflict tracking and escalation."""

import pytest
from sqlalchemy.orm import Session

from src.database.models import (
    ArcType,
    Conflict,
    ConflictLevel,
    GameSession,
)
from src.managers.conflict_manager import ConflictManager, ConflictStatus
from src.managers.story_arc_manager import StoryArcManager


@pytest.fixture
def conflict_manager(
    db_session: Session, game_session: GameSession
) -> ConflictManager:
    """Create a ConflictManager instance."""
    return ConflictManager(db_session, game_session)


@pytest.fixture
def arc_manager(db_session: Session, game_session: GameSession) -> StoryArcManager:
    """Create a StoryArcManager instance."""
    return StoryArcManager(db_session, game_session)


class TestConflictCreation:
    """Tests for creating conflicts."""

    def test_create_conflict_basic(self, conflict_manager: ConflictManager):
        """Verify basic conflict creation."""
        conflict = conflict_manager.create_conflict(
            conflict_key="guild_war",
            title="The Guild War",
        )

        assert conflict.conflict_key == "guild_war"
        assert conflict.title == "The Guild War"
        assert conflict.current_level == ConflictLevel.TENSION
        assert conflict.level_numeric == 1
        assert conflict.is_active is True
        assert conflict.is_resolved is False

    def test_create_conflict_with_parties(self, conflict_manager: ConflictManager):
        """Verify conflict with parties."""
        conflict = conflict_manager.create_conflict(
            conflict_key="faction_war",
            title="Faction War",
            party_a_key="merchants_guild",
            party_b_key="thieves_guild",
        )

        assert conflict.party_a_key == "merchants_guild"
        assert conflict.party_b_key == "thieves_guild"

    def test_create_conflict_with_triggers(self, conflict_manager: ConflictManager):
        """Verify conflict with escalation/de-escalation triggers."""
        conflict = conflict_manager.create_conflict(
            conflict_key="feud",
            title="Family Feud",
            escalation_triggers=["insult", "violence"],
            de_escalation_triggers=["apology", "mediation"],
        )

        assert len(conflict.escalation_triggers) == 2
        assert len(conflict.de_escalation_triggers) == 2

    def test_create_conflict_with_initial_level(
        self, conflict_manager: ConflictManager
    ):
        """Verify conflict with custom initial level."""
        conflict = conflict_manager.create_conflict(
            conflict_key="war",
            title="Already at War",
            initial_level=ConflictLevel.HOSTILITY,
        )

        assert conflict.current_level == ConflictLevel.HOSTILITY
        assert conflict.level_numeric == 4

    def test_create_conflict_duplicate_key_raises(
        self, conflict_manager: ConflictManager
    ):
        """Verify duplicate key raises error."""
        conflict_manager.create_conflict(
            conflict_key="unique",
            title="First",
        )

        with pytest.raises(ValueError, match="already exists"):
            conflict_manager.create_conflict(
                conflict_key="unique",
                title="Second",
            )

    def test_create_conflict_with_level_descriptions(
        self, conflict_manager: ConflictManager
    ):
        """Verify conflict with custom level descriptions."""
        descriptions = {
            "tension": "Merchants glare at thieves.",
            "dispute": "Accusations of theft.",
        }
        conflict = conflict_manager.create_conflict(
            conflict_key="custom",
            title="Custom",
            level_descriptions=descriptions,
        )

        assert "Merchants glare" in conflict.level_descriptions["tension"]


class TestConflictRetrieval:
    """Tests for retrieving conflicts."""

    def test_get_conflict(self, conflict_manager: ConflictManager):
        """Verify conflict retrieval by key."""
        conflict_manager.create_conflict(
            conflict_key="test",
            title="Test",
        )

        conflict = conflict_manager.get_conflict("test")
        assert conflict is not None
        assert conflict.conflict_key == "test"

    def test_get_conflict_not_found(self, conflict_manager: ConflictManager):
        """Verify None returned for non-existent conflict."""
        conflict = conflict_manager.get_conflict("nonexistent")
        assert conflict is None

    def test_get_active_conflicts(self, conflict_manager: ConflictManager):
        """Verify active conflicts retrieval."""
        conflict_manager.create_conflict(
            conflict_key="active1",
            title="Active 1",
            initial_level=ConflictLevel.CRISIS,
        )
        conflict_manager.create_conflict(
            conflict_key="active2",
            title="Active 2",
            initial_level=ConflictLevel.TENSION,
        )
        conflict_manager.create_conflict(
            conflict_key="resolved",
            title="Resolved",
        )
        conflict_manager.resolve_conflict("resolved", "Peace achieved")

        active = conflict_manager.get_active_conflicts()

        assert len(active) == 2
        # Should be ordered by level_numeric desc
        assert active[0].conflict_key == "active1"

    def test_get_conflicts_by_party(self, conflict_manager: ConflictManager):
        """Verify conflicts retrieval by party."""
        conflict_manager.create_conflict(
            conflict_key="war1",
            title="War 1",
            party_a_key="guild_a",
            party_b_key="guild_b",
        )
        conflict_manager.create_conflict(
            conflict_key="war2",
            title="War 2",
            party_a_key="guild_c",
            party_b_key="guild_a",
        )
        conflict_manager.create_conflict(
            conflict_key="war3",
            title="War 3",
            party_a_key="guild_c",
            party_b_key="guild_d",
        )

        guild_a_conflicts = conflict_manager.get_conflicts_by_party("guild_a")

        assert len(guild_a_conflicts) == 2

    def test_get_conflicts_at_level(self, conflict_manager: ConflictManager):
        """Verify conflicts retrieval at specific level."""
        conflict_manager.create_conflict(
            conflict_key="tension",
            title="Tension",
            initial_level=ConflictLevel.TENSION,
        )
        conflict_manager.create_conflict(
            conflict_key="crisis",
            title="Crisis",
            initial_level=ConflictLevel.CRISIS,
        )

        tension_conflicts = conflict_manager.get_conflicts_at_level(
            ConflictLevel.TENSION
        )

        assert len(tension_conflicts) == 1
        assert tension_conflicts[0].conflict_key == "tension"


class TestEscalation:
    """Tests for escalation mechanics."""

    def test_escalate(self, conflict_manager: ConflictManager):
        """Verify conflict escalates to next level."""
        conflict_manager.create_conflict(
            conflict_key="test",
            title="Test",
        )

        conflict, event = conflict_manager.escalate("test", trigger="Player insult")

        assert conflict.current_level == ConflictLevel.DISPUTE
        assert conflict.level_numeric == 2
        assert event.from_level == "tension"
        assert event.to_level == "dispute"
        assert event.trigger == "Player insult"

    def test_escalate_full_progression(self, conflict_manager: ConflictManager):
        """Verify escalation through all levels."""
        conflict_manager.create_conflict(
            conflict_key="test",
            title="Test",
        )

        expected_levels = [
            ConflictLevel.DISPUTE,
            ConflictLevel.CONFRONTATION,
            ConflictLevel.HOSTILITY,
            ConflictLevel.CRISIS,
            ConflictLevel.WAR,
        ]

        for expected in expected_levels:
            conflict, event = conflict_manager.escalate("test")
            assert conflict.current_level == expected

    def test_escalate_at_max_returns_none(self, conflict_manager: ConflictManager):
        """Verify escalation at max level returns None event."""
        conflict_manager.create_conflict(
            conflict_key="test",
            title="Test",
            initial_level=ConflictLevel.WAR,
        )

        conflict, event = conflict_manager.escalate("test")

        assert event is None
        assert conflict.current_level == ConflictLevel.WAR

    def test_escalate_inactive_raises(self, conflict_manager: ConflictManager):
        """Verify escalating inactive conflict raises error."""
        conflict_manager.create_conflict(
            conflict_key="test",
            title="Test",
        )
        conflict_manager.pause_conflict("test")

        with pytest.raises(ValueError, match="not active"):
            conflict_manager.escalate("test")

    def test_de_escalate(self, conflict_manager: ConflictManager):
        """Verify conflict de-escalates to lower level."""
        conflict_manager.create_conflict(
            conflict_key="test",
            title="Test",
            initial_level=ConflictLevel.CRISIS,
        )

        conflict, event = conflict_manager.de_escalate("test", trigger="Peace talks")

        assert conflict.current_level == ConflictLevel.HOSTILITY
        assert conflict.level_numeric == 4
        assert event.from_level == "crisis"
        assert event.to_level == "hostility"

    def test_de_escalate_at_min_returns_none(self, conflict_manager: ConflictManager):
        """Verify de-escalation at min level returns None event."""
        conflict_manager.create_conflict(
            conflict_key="test",
            title="Test",
        )

        conflict, event = conflict_manager.de_escalate("test")

        assert event is None
        assert conflict.current_level == ConflictLevel.TENSION

    def test_set_level(self, conflict_manager: ConflictManager):
        """Verify level can be set directly."""
        conflict_manager.create_conflict(
            conflict_key="test",
            title="Test",
        )

        conflict = conflict_manager.set_level("test", ConflictLevel.CRISIS)

        assert conflict.current_level == ConflictLevel.CRISIS
        assert conflict.level_numeric == 5


class TestTriggerManagement:
    """Tests for trigger management."""

    def test_add_escalation_trigger(self, conflict_manager: ConflictManager):
        """Verify escalation trigger can be added."""
        conflict_manager.create_conflict(
            conflict_key="test",
            title="Test",
        )

        conflict = conflict_manager.add_escalation_trigger("test", "Player attacks")

        assert "Player attacks" in conflict.escalation_triggers

    def test_add_de_escalation_trigger(self, conflict_manager: ConflictManager):
        """Verify de-escalation trigger can be added."""
        conflict_manager.create_conflict(
            conflict_key="test",
            title="Test",
        )

        conflict = conflict_manager.add_de_escalation_trigger("test", "Player mediates")

        assert "Player mediates" in conflict.de_escalation_triggers

    def test_set_level_description(self, conflict_manager: ConflictManager):
        """Verify level description can be set."""
        conflict_manager.create_conflict(
            conflict_key="test",
            title="Test",
        )

        conflict = conflict_manager.set_level_description(
            "test",
            ConflictLevel.CRISIS,
            "Everything is on fire!",
        )

        assert conflict.level_descriptions["crisis"] == "Everything is on fire!"


class TestConflictResolution:
    """Tests for conflict resolution."""

    def test_resolve_conflict(self, conflict_manager: ConflictManager):
        """Verify conflict can be resolved."""
        conflict_manager.create_conflict(
            conflict_key="test",
            title="Test",
        )

        conflict = conflict_manager.resolve_conflict("test", "Peace treaty signed")

        assert conflict.is_active is False
        assert conflict.is_resolved is True
        assert conflict.resolution == "Peace treaty signed"
        assert conflict.resolved_turn is not None

    def test_resolve_already_resolved_raises(self, conflict_manager: ConflictManager):
        """Verify resolving already resolved conflict raises error."""
        conflict_manager.create_conflict(
            conflict_key="test",
            title="Test",
        )
        conflict_manager.resolve_conflict("test", "Done")

        with pytest.raises(ValueError, match="already resolved"):
            conflict_manager.resolve_conflict("test", "Again")

    def test_pause_conflict(self, conflict_manager: ConflictManager):
        """Verify conflict can be paused."""
        conflict_manager.create_conflict(
            conflict_key="test",
            title="Test",
        )

        conflict = conflict_manager.pause_conflict("test")

        assert conflict.is_active is False
        assert conflict.is_resolved is False  # Not resolved, just paused

    def test_reactivate_conflict(self, conflict_manager: ConflictManager):
        """Verify paused conflict can be reactivated."""
        conflict_manager.create_conflict(
            conflict_key="test",
            title="Test",
        )
        conflict_manager.pause_conflict("test")

        conflict = conflict_manager.reactivate_conflict("test")

        assert conflict.is_active is True

    def test_reactivate_resolved_raises(self, conflict_manager: ConflictManager):
        """Verify reactivating resolved conflict raises error."""
        conflict_manager.create_conflict(
            conflict_key="test",
            title="Test",
        )
        conflict_manager.resolve_conflict("test", "Done")

        with pytest.raises(ValueError, match="Cannot reactivate resolved"):
            conflict_manager.reactivate_conflict("test")


class TestConflictStatus:
    """Tests for conflict status reporting."""

    def test_get_conflict_status(self, conflict_manager: ConflictManager):
        """Verify status generation."""
        conflict_manager.create_conflict(
            conflict_key="test",
            title="Test Conflict",
            party_a_key="guild_a",
            party_b_key="guild_b",
            escalation_triggers=["attack"],
            de_escalation_triggers=["peace"],
            level_descriptions={"tension": "Staring contest"},
        )

        status = conflict_manager.get_conflict_status("test")

        assert status.conflict_key == "test"
        assert status.title == "Test Conflict"
        assert status.level == "tension"
        assert status.level_numeric == 1
        assert status.is_active is True
        assert status.party_a == "guild_a"
        assert status.party_b == "guild_b"
        assert status.current_description == "Staring contest"
        assert "attack" in status.escalation_risk
        assert "peace" in status.de_escalation_opportunity

    def test_get_conflict_status_not_found(self, conflict_manager: ConflictManager):
        """Verify None returned for non-existent conflict."""
        status = conflict_manager.get_conflict_status("nonexistent")
        assert status is None

    def test_get_high_tension_conflicts(self, conflict_manager: ConflictManager):
        """Verify high tension conflicts retrieval."""
        conflict_manager.create_conflict(
            conflict_key="low",
            title="Low",
            initial_level=ConflictLevel.TENSION,
        )
        conflict_manager.create_conflict(
            conflict_key="crisis",
            title="Crisis",
            initial_level=ConflictLevel.CRISIS,
        )
        conflict_manager.create_conflict(
            conflict_key="war",
            title="War",
            initial_level=ConflictLevel.WAR,
        )

        high_tension = conflict_manager.get_high_tension_conflicts()

        assert len(high_tension) == 2
        assert all(c.level_numeric >= 5 for c in high_tension)

    def test_get_conflicts_context(self, conflict_manager: ConflictManager):
        """Verify context string generation."""
        conflict_manager.create_conflict(
            conflict_key="war",
            title="Guild War",
            party_a_key="merchants",
            party_b_key="thieves",
            initial_level=ConflictLevel.CRISIS,
        )

        context = conflict_manager.get_conflicts_context()

        assert "Active Conflicts" in context
        assert "Guild War" in context
        assert "merchants vs thieves" in context
        assert "CRISIS" in context
        assert "5/6" in context
        assert "CRITICAL" in context

    def test_get_conflicts_context_empty(self, conflict_manager: ConflictManager):
        """Verify empty context when no active conflicts."""
        context = conflict_manager.get_conflicts_context()
        assert context == ""


class TestStoryArcLinking:
    """Tests for story arc linking."""

    def test_link_to_story_arc(
        self,
        conflict_manager: ConflictManager,
        arc_manager: StoryArcManager,
    ):
        """Verify conflict can be linked to arc."""
        arc = arc_manager.create_arc(
            arc_key="arc",
            title="Arc",
            arc_type=ArcType.POLITICAL,
        )
        conflict_manager.create_conflict(
            conflict_key="test",
            title="Test",
        )

        conflict = conflict_manager.link_to_story_arc("test", arc.id)

        assert conflict.story_arc_id == arc.id

    def test_link_not_found_raises(self, conflict_manager: ConflictManager):
        """Verify linking non-existent conflict raises error."""
        with pytest.raises(ValueError, match="not found"):
            conflict_manager.link_to_story_arc("nonexistent", 1)
