"""Tests for narrative system models (StoryArc, Mystery, Conflict)."""

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
from tests.factories import create_entity


class TestStoryArcModel:
    """Tests for StoryArc model."""

    def test_create_story_arc(self, db_session: Session, game_session: GameSession):
        """Verify StoryArc can be created with required fields."""
        arc = StoryArc(
            session_id=game_session.id,
            arc_key="main_quest",
            title="The Dragon's Lair",
            arc_type=ArcType.MAIN_QUEST,
        )
        db_session.add(arc)
        db_session.commit()

        assert arc.id is not None
        assert arc.arc_key == "main_quest"
        assert arc.title == "The Dragon's Lair"
        assert arc.arc_type == ArcType.MAIN_QUEST

    def test_story_arc_defaults(self, db_session: Session, game_session: GameSession):
        """Verify StoryArc has correct default values."""
        arc = StoryArc(
            session_id=game_session.id,
            arc_key="side_quest",
            title="Lost Artifact",
            arc_type=ArcType.SIDE_QUEST,
        )
        db_session.add(arc)
        db_session.commit()

        assert arc.status == ArcStatus.DORMANT
        assert arc.current_phase == ArcPhase.SETUP
        assert arc.tension_level == 10
        assert arc.turns_in_phase == 0
        assert arc.priority == 5

    def test_story_arc_with_description(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify StoryArc can have description and stakes."""
        arc = StoryArc(
            session_id=game_session.id,
            arc_key="revenge_arc",
            title="Vengeance for Father",
            arc_type=ArcType.REVENGE,
            description="The hero seeks to avenge their father's murder.",
            stakes="Family honor and personal closure",
        )
        db_session.add(arc)
        db_session.commit()

        assert arc.description == "The hero seeks to avenge their father's murder."
        assert arc.stakes == "Family honor and personal closure"

    def test_story_arc_with_planted_elements(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify StoryArc can track Chekhov's guns."""
        arc = StoryArc(
            session_id=game_session.id,
            arc_key="mystery_arc",
            title="Who Killed the Mayor?",
            arc_type=ArcType.MYSTERY,
            planted_elements=[
                {"element": "bloody knife", "planted_turn": 5, "resolved": False},
                {"element": "torn letter", "planted_turn": 7, "resolved": False},
            ],
        )
        db_session.add(arc)
        db_session.commit()

        db_session.refresh(arc)
        assert len(arc.planted_elements) == 2
        assert arc.planted_elements[0]["element"] == "bloody knife"

    def test_story_arc_with_protagonist_antagonist(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify StoryArc can link to protagonist and antagonist entities."""
        hero = create_entity(db_session, game_session, entity_key="hero")
        villain = create_entity(db_session, game_session, entity_key="dark_lord")

        arc = StoryArc(
            session_id=game_session.id,
            arc_key="main_quest",
            title="Defeat the Dark Lord",
            arc_type=ArcType.MAIN_QUEST,
            protagonist_id=hero.id,
            antagonist_id=villain.id,
        )
        db_session.add(arc)
        db_session.commit()
        db_session.refresh(arc)

        assert arc.protagonist.entity_key == "hero"
        assert arc.antagonist.entity_key == "dark_lord"

    def test_story_arc_phase_progression(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify all arc phases can be used."""
        phases = [
            ArcPhase.SETUP,
            ArcPhase.RISING_ACTION,
            ArcPhase.MIDPOINT,
            ArcPhase.ESCALATION,
            ArcPhase.CLIMAX,
            ArcPhase.FALLING_ACTION,
            ArcPhase.RESOLUTION,
            ArcPhase.AFTERMATH,
        ]

        for i, phase in enumerate(phases):
            arc = StoryArc(
                session_id=game_session.id,
                arc_key=f"test_arc_{i}",
                title=f"Test Arc {i}",
                arc_type=ArcType.SIDE_QUEST,
                current_phase=phase,
            )
            db_session.add(arc)

        db_session.commit()

        arcs = (
            db_session.query(StoryArc)
            .filter(StoryArc.session_id == game_session.id)
            .all()
        )
        assert len(arcs) == 8

    def test_story_arc_all_types(self, db_session: Session, game_session: GameSession):
        """Verify all arc types can be used."""
        arc_types = [
            ArcType.MAIN_QUEST,
            ArcType.SIDE_QUEST,
            ArcType.ROMANCE,
            ArcType.REVENGE,
            ArcType.REDEMPTION,
            ArcType.MYSTERY,
            ArcType.RIVALRY,
            ArcType.MENTORSHIP,
            ArcType.BETRAYAL,
            ArcType.SURVIVAL,
            ArcType.DISCOVERY,
            ArcType.POLITICAL,
        ]

        for i, arc_type in enumerate(arc_types):
            arc = StoryArc(
                session_id=game_session.id,
                arc_key=f"type_arc_{i}",
                title=f"Type Arc {i}",
                arc_type=arc_type,
            )
            db_session.add(arc)

        db_session.commit()
        assert db_session.query(StoryArc).count() == 12

    def test_story_arc_repr(self, db_session: Session, game_session: GameSession):
        """Verify StoryArc repr is meaningful."""
        arc = StoryArc(
            session_id=game_session.id,
            arc_key="test_repr",
            title="Test",
            arc_type=ArcType.ROMANCE,
            status=ArcStatus.ACTIVE,
            current_phase=ArcPhase.RISING_ACTION,
            tension_level=45,
        )
        db_session.add(arc)
        db_session.commit()

        repr_str = repr(arc)
        assert "test_repr" in repr_str
        assert "active" in repr_str
        assert "rising_action" in repr_str
        assert "45" in repr_str

    def test_story_arc_session_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify StoryArc has proper session relationship."""
        arc = StoryArc(
            session_id=game_session.id,
            arc_key="rel_test",
            title="Relationship Test",
            arc_type=ArcType.SIDE_QUEST,
        )
        db_session.add(arc)
        db_session.commit()
        db_session.refresh(game_session)

        assert arc in game_session.story_arcs
        assert arc.session == game_session


class TestMysteryModel:
    """Tests for Mystery model."""

    def test_create_mystery(self, db_session: Session, game_session: GameSession):
        """Verify Mystery can be created with required fields."""
        mystery = Mystery(
            session_id=game_session.id,
            mystery_key="who_killed_mayor",
            title="Who Killed the Mayor?",
            truth="The butler did it with poison.",
            created_turn=1,
        )
        db_session.add(mystery)
        db_session.commit()

        assert mystery.id is not None
        assert mystery.mystery_key == "who_killed_mayor"
        assert mystery.truth == "The butler did it with poison."

    def test_mystery_defaults(self, db_session: Session, game_session: GameSession):
        """Verify Mystery has correct default values."""
        mystery = Mystery(
            session_id=game_session.id,
            mystery_key="default_test",
            title="Test Mystery",
            truth="Secret truth",
            created_turn=1,
        )
        db_session.add(mystery)
        db_session.commit()

        assert mystery.is_solved is False
        assert mystery.clues_discovered == 0
        assert mystery.total_clues == 0
        assert mystery.solved_turn is None

    def test_mystery_with_clues(self, db_session: Session, game_session: GameSession):
        """Verify Mystery can track clues."""
        mystery = Mystery(
            session_id=game_session.id,
            mystery_key="clue_test",
            title="The Missing Heir",
            truth="The heir was kidnapped by rivals.",
            clues=[
                {"clue": "A torn noble crest", "discovered": False, "location": "garden"},
                {"clue": "Footprints leading east", "discovered": True, "location": "gate"},
                {"clue": "Ransom note draft", "discovered": False, "location": "study"},
            ],
            clues_discovered=1,
            total_clues=3,
            created_turn=1,
        )
        db_session.add(mystery)
        db_session.commit()
        db_session.refresh(mystery)

        assert len(mystery.clues) == 3
        assert mystery.clues_discovered == 1
        assert mystery.total_clues == 3

    def test_mystery_with_red_herrings(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify Mystery can have red herrings."""
        mystery = Mystery(
            session_id=game_session.id,
            mystery_key="herring_test",
            title="The Stolen Artifact",
            truth="It was an inside job by the curator.",
            red_herrings=[
                {"suspect": "visiting merchant", "evidence": "was seen near vault"},
                {"suspect": "disgruntled guard", "evidence": "had motive"},
            ],
            created_turn=1,
        )
        db_session.add(mystery)
        db_session.commit()
        db_session.refresh(mystery)

        assert len(mystery.red_herrings) == 2

    def test_mystery_with_player_theory(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify Mystery can track player's theory."""
        mystery = Mystery(
            session_id=game_session.id,
            mystery_key="theory_test",
            title="The Cursed Village",
            truth="A necromancer in the catacombs.",
            player_theory="The villagers suspect the old hermit on the hill.",
            created_turn=1,
        )
        db_session.add(mystery)
        db_session.commit()

        assert mystery.player_theory == "The villagers suspect the old hermit on the hill."

    def test_mystery_linked_to_story_arc(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify Mystery can be linked to a StoryArc."""
        arc = StoryArc(
            session_id=game_session.id,
            arc_key="mystery_main",
            title="The Grand Mystery",
            arc_type=ArcType.MYSTERY,
        )
        db_session.add(arc)
        db_session.commit()

        mystery = Mystery(
            session_id=game_session.id,
            mystery_key="linked_mystery",
            title="Part of the Grand Mystery",
            truth="A piece of the puzzle.",
            story_arc_id=arc.id,
            created_turn=1,
        )
        db_session.add(mystery)
        db_session.commit()
        db_session.refresh(mystery)

        assert mystery.story_arc == arc

    def test_mystery_solved(self, db_session: Session, game_session: GameSession):
        """Verify Mystery can be marked as solved."""
        mystery = Mystery(
            session_id=game_session.id,
            mystery_key="solved_test",
            title="The Easy Mystery",
            truth="It was obvious.",
            is_solved=True,
            solved_turn=15,
            created_turn=1,
        )
        db_session.add(mystery)
        db_session.commit()

        assert mystery.is_solved is True
        assert mystery.solved_turn == 15

    def test_mystery_repr(self, db_session: Session, game_session: GameSession):
        """Verify Mystery repr is meaningful."""
        mystery = Mystery(
            session_id=game_session.id,
            mystery_key="repr_test",
            title="Repr Test",
            truth="Test",
            clues_discovered=2,
            total_clues=5,
            created_turn=1,
        )
        db_session.add(mystery)
        db_session.commit()

        repr_str = repr(mystery)
        assert "repr_test" in repr_str
        assert "2/5" in repr_str

        # Test solved repr
        mystery.is_solved = True
        repr_str = repr(mystery)
        assert "SOLVED" in repr_str

    def test_mystery_session_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify Mystery has proper session relationship."""
        mystery = Mystery(
            session_id=game_session.id,
            mystery_key="rel_test",
            title="Relationship Test",
            truth="Test",
            created_turn=1,
        )
        db_session.add(mystery)
        db_session.commit()
        db_session.refresh(game_session)

        assert mystery in game_session.mysteries
        assert mystery.session == game_session


class TestConflictModel:
    """Tests for Conflict model."""

    def test_create_conflict(self, db_session: Session, game_session: GameSession):
        """Verify Conflict can be created with required fields."""
        conflict = Conflict(
            session_id=game_session.id,
            conflict_key="guild_war",
            title="The Guild War",
            started_turn=1,
        )
        db_session.add(conflict)
        db_session.commit()

        assert conflict.id is not None
        assert conflict.conflict_key == "guild_war"
        assert conflict.title == "The Guild War"

    def test_conflict_defaults(self, db_session: Session, game_session: GameSession):
        """Verify Conflict has correct default values."""
        conflict = Conflict(
            session_id=game_session.id,
            conflict_key="default_test",
            title="Test Conflict",
            started_turn=1,
        )
        db_session.add(conflict)
        db_session.commit()

        assert conflict.current_level == ConflictLevel.TENSION
        assert conflict.level_numeric == 1
        assert conflict.is_active is True
        assert conflict.is_resolved is False

    def test_conflict_all_levels(self, db_session: Session, game_session: GameSession):
        """Verify all conflict levels can be used."""
        levels = [
            (ConflictLevel.TENSION, 1),
            (ConflictLevel.DISPUTE, 2),
            (ConflictLevel.CONFRONTATION, 3),
            (ConflictLevel.HOSTILITY, 4),
            (ConflictLevel.CRISIS, 5),
            (ConflictLevel.WAR, 6),
        ]

        for i, (level, numeric) in enumerate(levels):
            conflict = Conflict(
                session_id=game_session.id,
                conflict_key=f"level_test_{i}",
                title=f"Level {level.value}",
                current_level=level,
                level_numeric=numeric,
                started_turn=1,
            )
            db_session.add(conflict)

        db_session.commit()
        assert db_session.query(Conflict).count() == 6

    def test_conflict_with_parties(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify Conflict can track involved parties."""
        conflict = Conflict(
            session_id=game_session.id,
            conflict_key="faction_war",
            title="The Faction War",
            party_a_key="merchant_guild",
            party_b_key="thieves_guild",
            description="A brewing conflict between the guilds over territory.",
            started_turn=1,
        )
        db_session.add(conflict)
        db_session.commit()

        assert conflict.party_a_key == "merchant_guild"
        assert conflict.party_b_key == "thieves_guild"

    def test_conflict_with_triggers(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify Conflict can track escalation/de-escalation triggers."""
        conflict = Conflict(
            session_id=game_session.id,
            conflict_key="trigger_test",
            title="Trigger Test",
            escalation_triggers=[
                "Player sides with one faction",
                "Time passes without resolution",
                "Another theft occurs",
            ],
            de_escalation_triggers=[
                "Player mediates successfully",
                "Common enemy appears",
                "Trade agreement signed",
            ],
            started_turn=1,
        )
        db_session.add(conflict)
        db_session.commit()
        db_session.refresh(conflict)

        assert len(conflict.escalation_triggers) == 3
        assert len(conflict.de_escalation_triggers) == 3

    def test_conflict_with_level_descriptions(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify Conflict can have level-specific descriptions."""
        conflict = Conflict(
            session_id=game_session.id,
            conflict_key="desc_test",
            title="Description Test",
            level_descriptions={
                "tension": "Merchants are whispering about thieves in the market.",
                "dispute": "Accusations are flying between guild masters.",
                "confrontation": "Guild members refuse to do business together.",
                "hostility": "Beatings have occurred in dark alleys.",
                "crisis": "A guild hall has been set ablaze.",
                "war": "Open warfare in the streets.",
            },
            started_turn=1,
        )
        db_session.add(conflict)
        db_session.commit()
        db_session.refresh(conflict)

        assert len(conflict.level_descriptions) == 6
        assert "whispering" in conflict.level_descriptions["tension"]

    def test_conflict_resolved(self, db_session: Session, game_session: GameSession):
        """Verify Conflict can be marked as resolved."""
        conflict = Conflict(
            session_id=game_session.id,
            conflict_key="resolved_test",
            title="Resolved Conflict",
            is_active=False,
            is_resolved=True,
            resolution="The player brokered a peace treaty.",
            resolved_turn=25,
            started_turn=1,
        )
        db_session.add(conflict)
        db_session.commit()

        assert conflict.is_resolved is True
        assert conflict.resolved_turn == 25

    def test_conflict_linked_to_story_arc(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify Conflict can be linked to a StoryArc."""
        arc = StoryArc(
            session_id=game_session.id,
            arc_key="political_arc",
            title="Political Intrigue",
            arc_type=ArcType.POLITICAL,
        )
        db_session.add(arc)
        db_session.commit()

        conflict = Conflict(
            session_id=game_session.id,
            conflict_key="linked_conflict",
            title="Noble House Rivalry",
            story_arc_id=arc.id,
            started_turn=1,
        )
        db_session.add(conflict)
        db_session.commit()
        db_session.refresh(conflict)

        assert conflict.story_arc == arc

    def test_conflict_repr(self, db_session: Session, game_session: GameSession):
        """Verify Conflict repr is meaningful."""
        conflict = Conflict(
            session_id=game_session.id,
            conflict_key="repr_test",
            title="Repr Test",
            current_level=ConflictLevel.HOSTILITY,
            started_turn=1,
        )
        db_session.add(conflict)
        db_session.commit()

        repr_str = repr(conflict)
        assert "repr_test" in repr_str
        assert "hostility" in repr_str

        # Test resolved repr
        conflict.is_resolved = True
        repr_str = repr(conflict)
        assert "resolved" in repr_str

    def test_conflict_session_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify Conflict has proper session relationship."""
        conflict = Conflict(
            session_id=game_session.id,
            conflict_key="rel_test",
            title="Relationship Test",
            started_turn=1,
        )
        db_session.add(conflict)
        db_session.commit()
        db_session.refresh(game_session)

        assert conflict in game_session.conflicts
        assert conflict.session == game_session


class TestNarrativeCascadeDelete:
    """Tests for cascade delete behavior."""

    def test_story_arc_deleted_with_session(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify StoryArcs are deleted when session is deleted."""
        arc = StoryArc(
            session_id=game_session.id,
            arc_key="cascade_test",
            title="Cascade Test",
            arc_type=ArcType.SIDE_QUEST,
        )
        db_session.add(arc)
        db_session.commit()
        arc_id = arc.id

        db_session.delete(game_session)
        db_session.commit()

        assert db_session.get(StoryArc, arc_id) is None

    def test_mystery_deleted_with_session(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify Mysteries are deleted when session is deleted."""
        mystery = Mystery(
            session_id=game_session.id,
            mystery_key="cascade_test",
            title="Cascade Test",
            truth="Test",
            created_turn=1,
        )
        db_session.add(mystery)
        db_session.commit()
        mystery_id = mystery.id

        db_session.delete(game_session)
        db_session.commit()

        assert db_session.get(Mystery, mystery_id) is None

    def test_conflict_deleted_with_session(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify Conflicts are deleted when session is deleted."""
        conflict = Conflict(
            session_id=game_session.id,
            conflict_key="cascade_test",
            title="Cascade Test",
            started_turn=1,
        )
        db_session.add(conflict)
        db_session.commit()
        conflict_id = conflict.id

        db_session.delete(game_session)
        db_session.commit()

        assert db_session.get(Conflict, conflict_id) is None
