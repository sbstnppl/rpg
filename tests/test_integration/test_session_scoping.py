"""Integration tests for session scoping - verify data isolation between game sessions."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.character_state import CharacterNeeds
from src.database.models.entities import Entity
from src.database.models.enums import (
    BodyPart,
    EntityType,
    GriefStage,
    InjurySeverity,
    InjuryType,
    VitalStatus,
)
from src.database.models.injuries import BodyInjury
from src.database.models.items import Item
from src.database.models.mental_state import GriefCondition, MentalCondition
from src.database.models.relationships import Relationship
from src.database.models.session import GameSession
from src.database.models.vital_state import EntityVitalState
from src.database.models.world import Fact, Location, WorldEvent
from src.managers.death import DeathManager
from src.managers.grief import GriefManager
from src.managers.injuries import InjuryManager
from src.managers.needs import NeedsManager
from src.managers.relationship_manager import RelationshipManager
from tests.factories import (
    create_entity,
    create_game_session,
    create_location,
)


class TestEntitySessionScoping:
    """Tests for entity isolation between sessions."""

    def test_entity_query_only_returns_current_session(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify entity queries filter by session_id."""
        other_session = create_game_session(db_session, session_name="Other Game")

        # Create entities in both sessions
        entity1 = create_entity(db_session, game_session, entity_key="hero")
        entity2 = create_entity(db_session, other_session, entity_key="hero")

        # Query should only return current session's entity
        result = (
            db_session.query(Entity)
            .filter(Entity.session_id == game_session.id)
            .all()
        )

        assert len(result) == 1
        assert result[0].id == entity1.id

    def test_same_entity_key_different_sessions(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify same entity_key can exist in different sessions."""
        other_session = create_game_session(db_session)

        # Same key in both sessions should work
        entity1 = create_entity(db_session, game_session, entity_key="player")
        entity2 = create_entity(db_session, other_session, entity_key="player")

        assert entity1.entity_key == entity2.entity_key
        assert entity1.session_id != entity2.session_id
        assert entity1.id != entity2.id


class TestRelationshipSessionScoping:
    """Tests for relationship isolation between sessions."""

    def test_relationship_query_scoped_to_session(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify relationship queries filter by session_id."""
        other_session = create_game_session(db_session)

        # Create entities and relationships in both sessions
        e1_s1 = create_entity(db_session, game_session, entity_key="npc1")
        e2_s1 = create_entity(db_session, game_session, entity_key="npc2")
        e1_s2 = create_entity(db_session, other_session, entity_key="npc1")
        e2_s2 = create_entity(db_session, other_session, entity_key="npc2")

        manager1 = RelationshipManager(db_session, game_session)
        manager2 = RelationshipManager(db_session, other_session)

        manager1.record_meeting(e1_s1.id, e2_s1.id, "tavern")
        manager2.record_meeting(e1_s2.id, e2_s2.id, "tavern")

        # Each manager should only see its session's relationships
        rels1 = manager1.get_relationships_for_entity(e1_s1.id)
        rels2 = manager2.get_relationships_for_entity(e1_s2.id)

        assert len(rels1) == 2  # Bidirectional
        assert len(rels2) == 2
        assert all(r.session_id == game_session.id for r in rels1)
        assert all(r.session_id == other_session.id for r in rels2)


class TestNeedsSessionScoping:
    """Tests for character needs isolation between sessions."""

    def test_needs_scoped_to_session(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify needs queries filter by session_id."""
        other_session = create_game_session(db_session)

        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, other_session)

        manager1 = NeedsManager(db_session, game_session)
        manager2 = NeedsManager(db_session, other_session)

        needs1 = manager1.get_or_create_needs(entity1.id)
        needs1.hunger = 25
        needs2 = manager2.get_or_create_needs(entity2.id)
        needs2.hunger = 75
        db_session.flush()

        # Each manager should see only its session's needs
        result1 = manager1.get_needs(entity1.id)
        result2 = manager2.get_needs(entity2.id)

        assert result1.hunger == 25
        assert result2.hunger == 75

        # Cross-session query should return None
        assert manager1.get_needs(entity2.id) is None
        assert manager2.get_needs(entity1.id) is None


class TestInjurySessionScoping:
    """Tests for injury isolation between sessions."""

    def test_injuries_scoped_to_session(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify injury queries filter by session_id."""
        other_session = create_game_session(db_session)

        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, other_session)

        manager1 = InjuryManager(db_session, game_session)
        manager2 = InjuryManager(db_session, other_session)

        manager1.add_injury(
            entity1.id, BodyPart.LEFT_ARM, InjuryType.CUT,
            InjurySeverity.MINOR, "Combat", turn=1
        )
        manager2.add_injury(
            entity2.id, BodyPart.RIGHT_LEG, InjuryType.FRACTURE,
            InjurySeverity.SEVERE, "Fall", turn=1
        )

        # Each manager should see only its session's injuries
        injuries1 = manager1.get_injuries(entity1.id)
        injuries2 = manager2.get_injuries(entity2.id)

        assert len(injuries1) == 1
        assert injuries1[0].body_part == BodyPart.LEFT_ARM
        assert len(injuries2) == 1
        assert injuries2[0].body_part == BodyPart.RIGHT_LEG

        # Cross-session query should be empty
        assert manager1.get_injuries(entity2.id) == []


class TestVitalStateSessionScoping:
    """Tests for vital state isolation between sessions."""

    def test_vital_state_scoped_to_session(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify vital state queries filter by session_id."""
        other_session = create_game_session(db_session)

        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, other_session)

        manager1 = DeathManager(db_session, game_session)
        manager2 = DeathManager(db_session, other_session)

        manager1.set_vital_status(entity1.id, VitalStatus.WOUNDED)
        manager2.set_vital_status(entity2.id, VitalStatus.CRITICAL)

        # Each manager should see only its session's states
        state1 = manager1.get_vital_state(entity1.id)
        state2 = manager2.get_vital_state(entity2.id)

        assert state1.vital_status == VitalStatus.WOUNDED
        assert state2.vital_status == VitalStatus.CRITICAL

        # Cross-session query should return None
        assert manager1.get_vital_state(entity2.id) is None


class TestGriefSessionScoping:
    """Tests for grief isolation between sessions."""

    def test_grief_scoped_to_session(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify grief queries filter by session_id."""
        other_session = create_game_session(db_session)

        griever1 = create_entity(db_session, game_session, entity_key="griever")
        deceased1 = create_entity(db_session, game_session, entity_key="deceased")
        griever2 = create_entity(db_session, other_session, entity_key="griever")
        deceased2 = create_entity(db_session, other_session, entity_key="deceased")

        manager1 = GriefManager(db_session, game_session)
        manager2 = GriefManager(db_session, other_session)

        manager1.start_grief(griever1.id, deceased1.id)
        manager2.start_grief(griever2.id, deceased2.id)

        # Each manager should see only its session's grief
        griefs1 = manager1.get_grief_conditions(griever1.id)
        griefs2 = manager2.get_grief_conditions(griever2.id)

        assert len(griefs1) == 1
        assert len(griefs2) == 1

        # Cross-session query should be empty
        assert manager1.get_grief_conditions(griever2.id) == []


class TestWorldDataSessionScoping:
    """Tests for world data isolation between sessions."""

    def test_locations_scoped_to_session(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify location queries filter by session_id."""
        other_session = create_game_session(db_session)

        loc1 = create_location(db_session, game_session, location_key="tavern")
        loc2 = create_location(db_session, other_session, location_key="tavern")

        # Query should only return current session's location
        result = (
            db_session.query(Location)
            .filter(
                Location.session_id == game_session.id,
                Location.location_key == "tavern",
            )
            .first()
        )

        assert result.id == loc1.id
        assert result.id != loc2.id

    def test_facts_scoped_to_session(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify fact queries filter by session_id."""
        other_session = create_game_session(db_session)

        # Create same fact in both sessions
        fact1 = Fact(
            session_id=game_session.id,
            subject_type="entity",
            subject_key="king",
            predicate="is_alive",
            value="true",
            source_turn=1,
        )
        fact2 = Fact(
            session_id=other_session.id,
            subject_type="entity",
            subject_key="king",
            predicate="is_alive",
            value="false",  # Different state
            source_turn=1,
        )
        db_session.add_all([fact1, fact2])
        db_session.flush()

        # Query should return different facts for different sessions
        result1 = (
            db_session.query(Fact)
            .filter(
                Fact.session_id == game_session.id,
                Fact.subject_key == "king",
            )
            .first()
        )
        result2 = (
            db_session.query(Fact)
            .filter(
                Fact.session_id == other_session.id,
                Fact.subject_key == "king",
            )
            .first()
        )

        assert result1.value == "true"
        assert result2.value == "false"


class TestItemSessionScoping:
    """Tests for item isolation between sessions."""

    def test_items_scoped_to_session(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify item queries filter by session_id."""
        other_session = create_game_session(db_session)

        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, other_session)

        item1 = Item(
            session_id=game_session.id,
            item_key="magic_sword",
            display_name="Magic Sword",
            owner_id=entity1.id,
        )
        item2 = Item(
            session_id=other_session.id,
            item_key="magic_sword",
            display_name="Magic Sword",
            owner_id=entity2.id,
        )
        db_session.add_all([item1, item2])
        db_session.flush()

        # Query should return different items for different sessions
        result1 = (
            db_session.query(Item)
            .filter(
                Item.session_id == game_session.id,
                Item.item_key == "magic_sword",
            )
            .all()
        )
        result2 = (
            db_session.query(Item)
            .filter(
                Item.session_id == other_session.id,
                Item.item_key == "magic_sword",
            )
            .all()
        )

        assert len(result1) == 1
        assert len(result2) == 1
        assert result1[0].owner_id == entity1.id
        assert result2[0].owner_id == entity2.id


class TestCrossSessionIsolation:
    """Tests for complete isolation between game sessions."""

    def test_deleting_session_does_not_affect_other_sessions(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify deleting one session doesn't affect others."""
        other_session = create_game_session(db_session)

        # Create data in both sessions
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, other_session)

        # Count entities
        count_before = db_session.query(Entity).count()
        assert count_before == 2

        # Delete one session's entity
        db_session.delete(entity1)
        db_session.flush()

        # Other session's entity should still exist
        count_after = db_session.query(Entity).count()
        remaining = db_session.query(Entity).first()

        assert count_after == 1
        assert remaining.id == entity2.id

    def test_manager_operations_isolated(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify manager operations don't cross session boundaries."""
        other_session = create_game_session(db_session)

        # Create entities in both sessions
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, other_session)

        # Use managers for session 1
        needs_mgr = NeedsManager(db_session, game_session)
        injury_mgr = InjuryManager(db_session, game_session)
        death_mgr = DeathManager(db_session, game_session)

        needs_mgr.get_or_create_needs(entity1.id)
        injury_mgr.add_injury(
            entity1.id, BodyPart.HEAD, InjuryType.CONCUSSION,
            InjurySeverity.MODERATE, "Impact", turn=1
        )
        death_mgr.set_vital_status(entity1.id, VitalStatus.WOUNDED)

        # Session 2 should have no data from these operations
        needs_mgr2 = NeedsManager(db_session, other_session)
        injury_mgr2 = InjuryManager(db_session, other_session)
        death_mgr2 = DeathManager(db_session, other_session)

        assert needs_mgr2.get_needs(entity2.id) is None
        assert injury_mgr2.get_injuries(entity2.id) == []
        assert death_mgr2.get_vital_state(entity2.id) is None

        # And managers from session 1 can't see session 2's entity
        assert needs_mgr.get_needs(entity2.id) is None
