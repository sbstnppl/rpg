"""Integration tests for manager interactions - verify managers work together correctly."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.enums import (
    BodyPart,
    GriefStage,
    InjurySeverity,
    InjuryType,
    RelationshipDimension,
    VitalStatus,
)
from src.database.models.session import GameSession
from src.managers.death import DeathManager
from src.managers.grief import GriefManager
from src.managers.injuries import InjuryManager
from src.managers.needs import NeedsManager
from src.managers.relationship_manager import RelationshipManager
from tests.factories import (
    create_entity,
    create_relationship,
)


class TestNeedsAndInjuryInteraction:
    """Tests for needs and injury manager interaction."""

    def test_injured_entity_has_needs(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify injured entities can still have needs tracked."""
        entity = create_entity(db_session, game_session)

        injury_mgr = InjuryManager(db_session, game_session)
        needs_mgr = NeedsManager(db_session, game_session)

        # Add injury
        injury_mgr.add_injury(
            entity.id, BodyPart.LEFT_ARM, InjuryType.CUT,
            InjurySeverity.MODERATE, "Combat", turn=1
        )

        # Create needs
        needs = needs_mgr.get_or_create_needs(entity.id)
        needs.hunger = 40
        needs.thirst = 60
        db_session.flush()

        # Both should be queryable
        retrieved_injury = injury_mgr.get_injuries(entity.id)
        retrieved_needs = needs_mgr.get_needs(entity.id)

        assert len(retrieved_injury) == 1
        assert retrieved_needs.hunger == 40
        assert retrieved_needs.thirst == 60


class TestDeathAndGriefInteraction:
    """Tests for death and grief manager interaction."""

    def test_death_triggers_grief_scenario(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify death can trigger grief in related entities."""
        deceased = create_entity(db_session, game_session, entity_key="victim")
        mourner = create_entity(db_session, game_session, entity_key="mourner")

        # Create relationship between mourner and victim
        create_relationship(
            db_session, game_session, mourner, deceased,
            trust=80, liking=90, familiarity=70
        )

        death_mgr = DeathManager(db_session, game_session)
        grief_mgr = GriefManager(db_session, game_session)

        # Mark deceased as dead
        death_mgr.set_vital_status(deceased.id, VitalStatus.DEAD)

        # Start grief for mourner
        grief = grief_mgr.start_grief(mourner.id, deceased.id)

        # Verify state
        vital_state = death_mgr.get_vital_state(deceased.id)
        grief_conditions = grief_mgr.get_grief_conditions(mourner.id)

        assert vital_state.vital_status == VitalStatus.DEAD
        assert len(grief_conditions) == 1
        assert grief_conditions[0].deceased_entity_id == deceased.id
        assert grief_conditions[0].intensity > 50  # High intensity due to relationship

    def test_grief_intensity_scales_with_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify grief intensity depends on relationship strength."""
        deceased = create_entity(db_session, game_session, entity_key="deceased")
        close_friend = create_entity(db_session, game_session, entity_key="close_friend")
        acquaintance = create_entity(db_session, game_session, entity_key="acquaintance")

        # Close relationship
        create_relationship(
            db_session, game_session, close_friend, deceased,
            trust=90, liking=95, familiarity=80
        )
        # Weak relationship
        create_relationship(
            db_session, game_session, acquaintance, deceased,
            trust=20, liking=30, familiarity=15
        )

        grief_mgr = GriefManager(db_session, game_session)

        grief_close = grief_mgr.start_grief(close_friend.id, deceased.id)
        grief_weak = grief_mgr.start_grief(acquaintance.id, deceased.id)

        # Close friend should have much higher grief intensity
        assert grief_close.intensity > grief_weak.intensity
        assert grief_close.intensity > 70  # Very intense grief
        assert grief_weak.intensity < 40  # Mild grief


class TestInjuryAndDeathInteraction:
    """Tests for injury and death manager interaction."""

    def test_severe_injury_and_vital_state(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify severe injuries can be tracked alongside vital state."""
        entity = create_entity(db_session, game_session)

        injury_mgr = InjuryManager(db_session, game_session)
        death_mgr = DeathManager(db_session, game_session)

        # Add severe injury
        injury_mgr.add_injury(
            entity.id, BodyPart.TORSO, InjuryType.LACERATION,
            InjurySeverity.CRITICAL, "Ambush", turn=1
        )

        # Set critical vital state
        death_mgr.set_vital_status(entity.id, VitalStatus.CRITICAL)

        # Both states should be queryable
        injuries = injury_mgr.get_injuries(entity.id)
        vital_state = death_mgr.get_vital_state(entity.id)

        assert len(injuries) == 1
        assert injuries[0].severity == InjurySeverity.CRITICAL
        assert vital_state.vital_status == VitalStatus.CRITICAL

    def test_multiple_injuries_accumulate(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify multiple injuries can be tracked simultaneously."""
        entity = create_entity(db_session, game_session)

        injury_mgr = InjuryManager(db_session, game_session)

        # Add multiple injuries from combat
        injury_mgr.add_injury(
            entity.id, BodyPart.LEFT_ARM, InjuryType.CUT,
            InjurySeverity.MINOR, "Sword slash", turn=1
        )
        injury_mgr.add_injury(
            entity.id, BodyPart.RIGHT_LEG, InjuryType.BRUISE,
            InjurySeverity.MODERATE, "Shield bash", turn=2
        )
        injury_mgr.add_injury(
            entity.id, BodyPart.TORSO, InjuryType.LACERATION,
            InjurySeverity.SEVERE, "Dagger thrust", turn=3
        )

        injuries = injury_mgr.get_injuries(entity.id)
        total_pain = injury_mgr.get_total_pain(entity.id)
        # Check activity impact for walking (uses legs and torso)
        activity_impact = injury_mgr.get_activity_impact(entity.id, "walking")

        assert len(injuries) == 3
        assert total_pain > 0  # Should have accumulated pain
        # Activity impact should exist (has injured leg and torso)
        assert activity_impact is not None


class TestRelationshipAndGriefInteraction:
    """Tests for relationship and grief interaction."""

    def test_grief_with_blame_tracks_entity(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify grief can track who is blamed for death."""
        deceased = create_entity(db_session, game_session, entity_key="victim")
        mourner = create_entity(db_session, game_session, entity_key="mourner")
        killer = create_entity(db_session, game_session, entity_key="killer")

        # Create relationships
        create_relationship(
            db_session, game_session, mourner, deceased,
            trust=80, liking=85, familiarity=70
        )
        create_relationship(
            db_session, game_session, mourner, killer,
            trust=50, liking=40, familiarity=30
        )

        grief_mgr = GriefManager(db_session, game_session)

        # Start grief with blame
        grief = grief_mgr.start_grief(
            mourner.id, deceased.id, blamed_entity_key=killer.entity_key
        )

        assert grief.blames_someone is True
        assert grief.blamed_entity_key == killer.entity_key

    def test_multiple_grieving_for_same_deceased(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify multiple entities can grieve for the same deceased."""
        deceased = create_entity(db_session, game_session, entity_key="beloved")
        mourner1 = create_entity(db_session, game_session, entity_key="friend")
        mourner2 = create_entity(db_session, game_session, entity_key="family")
        mourner3 = create_entity(db_session, game_session, entity_key="lover")

        # Create relationships
        for mourner in [mourner1, mourner2, mourner3]:
            create_relationship(
                db_session, game_session, mourner, deceased,
                trust=70, liking=80, familiarity=60
            )

        grief_mgr = GriefManager(db_session, game_session)

        # All mourners start grief
        grief_mgr.start_grief(mourner1.id, deceased.id)
        grief_mgr.start_grief(mourner2.id, deceased.id)
        grief_mgr.start_grief(mourner3.id, deceased.id)

        # Find all NPCs grieving for deceased
        grieving_ids = grief_mgr.find_npcs_grieving_for(deceased.id)

        assert len(grieving_ids) == 3
        assert mourner1.id in grieving_ids
        assert mourner2.id in grieving_ids
        assert mourner3.id in grieving_ids


class TestCompleteEntityLifecycle:
    """Tests for complete entity lifecycle scenarios."""

    def test_entity_full_lifecycle(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify complete entity lifecycle from creation to death."""
        # Create entity
        entity = create_entity(db_session, game_session, entity_key="adventurer")
        friend = create_entity(db_session, game_session, entity_key="companion")

        needs_mgr = NeedsManager(db_session, game_session)
        injury_mgr = InjuryManager(db_session, game_session)
        death_mgr = DeathManager(db_session, game_session)
        grief_mgr = GriefManager(db_session, game_session)
        rel_mgr = RelationshipManager(db_session, game_session)

        # 1. Establish relationship
        rel_mgr.record_meeting(entity.id, friend.id, "tavern")
        rel_mgr.update_attitude(
            entity.id, friend.id, RelationshipDimension.TRUST, 30, "shared_quest"
        )

        # 2. Track needs
        needs = needs_mgr.get_or_create_needs(entity.id)
        needs.hunger = 60
        needs.thirst = 50

        # 3. Sustain injury
        injury_mgr.add_injury(
            entity.id, BodyPart.RIGHT_ARM, InjuryType.CUT,
            InjurySeverity.MODERATE, "Monster attack", turn=5
        )

        # 4. Condition worsens
        death_mgr.set_vital_status(entity.id, VitalStatus.WOUNDED)
        db_session.flush()

        # 5. Death occurs
        death_mgr.set_vital_status(entity.id, VitalStatus.DEAD)

        # 6. Friend grieves
        grief_mgr.start_grief(friend.id, entity.id)

        # Verify final state
        assert death_mgr.get_vital_state(entity.id).vital_status == VitalStatus.DEAD
        assert len(injury_mgr.get_injuries(entity.id)) == 1
        assert len(grief_mgr.get_grief_conditions(friend.id)) == 1

    def test_multiple_entities_interacting(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify multiple entities can interact through managers."""
        hero = create_entity(db_session, game_session, entity_key="hero")
        sidekick = create_entity(db_session, game_session, entity_key="sidekick")
        villain = create_entity(db_session, game_session, entity_key="villain")

        rel_mgr = RelationshipManager(db_session, game_session)
        needs_mgr = NeedsManager(db_session, game_session)
        injury_mgr = InjuryManager(db_session, game_session)

        # Hero meets sidekick (friendly) - increase familiarity first to avoid cap
        rel_mgr.record_meeting(hero.id, sidekick.id, "village")
        rel_mgr.update_attitude(hero.id, sidekick.id, RelationshipDimension.FAMILIARITY, 55, "adventures")
        rel_mgr.update_attitude(hero.id, sidekick.id, RelationshipDimension.TRUST, 40, "saved_life")
        rel_mgr.update_attitude(hero.id, sidekick.id, RelationshipDimension.LIKING, 30, "humor")

        # Hero meets villain (hostile) - increase familiarity first to avoid cap
        rel_mgr.record_meeting(hero.id, villain.id, "dungeon")
        rel_mgr.update_attitude(hero.id, villain.id, RelationshipDimension.FAMILIARITY, 55, "confrontations")
        rel_mgr.update_attitude(hero.id, villain.id, RelationshipDimension.TRUST, -30, "betrayal")
        rel_mgr.update_attitude(hero.id, villain.id, RelationshipDimension.LIKING, -40, "cruelty")

        # All have needs
        for entity in [hero, sidekick, villain]:
            needs_mgr.get_or_create_needs(entity.id)

        # Combat results in injuries
        injury_mgr.add_injury(
            hero.id, BodyPart.LEFT_ARM, InjuryType.BURN,
            InjurySeverity.MODERATE, "Fire spell", turn=10
        )
        injury_mgr.add_injury(
            villain.id, BodyPart.TORSO, InjuryType.LACERATION,
            InjurySeverity.SEVERE, "Hero's sword", turn=10
        )

        # Verify relationships
        hero_to_sidekick = rel_mgr.get_relationship(hero.id, sidekick.id)
        hero_to_villain = rel_mgr.get_relationship(hero.id, villain.id)

        assert hero_to_sidekick.trust > 50  # Positive
        assert hero_to_villain.trust < 50  # Negative (default is 50)

        # Verify injuries
        assert len(injury_mgr.get_injuries(hero.id)) == 1
        assert len(injury_mgr.get_injuries(villain.id)) == 1
        assert len(injury_mgr.get_injuries(sidekick.id)) == 0


class TestManagerConsistency:
    """Tests for data consistency across managers."""

    def test_entity_data_consistent_across_managers(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify entity data stays consistent when accessed by different managers."""
        entity = create_entity(db_session, game_session)

        # Create managers
        needs_mgr = NeedsManager(db_session, game_session)
        injury_mgr = InjuryManager(db_session, game_session)
        death_mgr = DeathManager(db_session, game_session)

        # Add data through each manager
        needs = needs_mgr.get_or_create_needs(entity.id)
        needs.hunger = 75
        injury_mgr.add_injury(
            entity.id, BodyPart.HEAD, InjuryType.BRUISE,
            InjurySeverity.MINOR, "Bump", turn=1
        )
        death_mgr.set_vital_status(entity.id, VitalStatus.HEALTHY)
        db_session.flush()

        # Create fresh managers (simulate different request)
        needs_mgr2 = NeedsManager(db_session, game_session)
        injury_mgr2 = InjuryManager(db_session, game_session)
        death_mgr2 = DeathManager(db_session, game_session)

        # Verify data is consistent
        assert needs_mgr2.get_needs(entity.id).hunger == 75
        assert len(injury_mgr2.get_injuries(entity.id)) == 1
        assert death_mgr2.get_vital_state(entity.id).vital_status == VitalStatus.HEALTHY

    def test_session_id_always_applied(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify all manager operations apply session_id correctly."""
        from tests.factories import create_game_session

        other_session = create_game_session(db_session, session_name="Other Game")

        entity1 = create_entity(db_session, game_session, entity_key="npc")
        entity2 = create_entity(db_session, other_session, entity_key="npc")

        # Managers for session 1
        needs_mgr1 = NeedsManager(db_session, game_session)
        injury_mgr1 = InjuryManager(db_session, game_session)

        # Managers for session 2
        needs_mgr2 = NeedsManager(db_session, other_session)
        injury_mgr2 = InjuryManager(db_session, other_session)

        # Add data to session 1
        needs_mgr1.get_or_create_needs(entity1.id)
        injury_mgr1.add_injury(
            entity1.id, BodyPart.LEFT_LEG, InjuryType.FRACTURE,
            InjurySeverity.MODERATE, "Fall", turn=1
        )

        # Session 2 managers should not see session 1 data
        assert needs_mgr2.get_needs(entity1.id) is None
        assert injury_mgr2.get_injuries(entity1.id) == []

        # Session 1 managers should not see session 2 entities
        assert needs_mgr1.get_needs(entity2.id) is None
        assert injury_mgr1.get_injuries(entity2.id) == []
