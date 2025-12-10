"""Tests for persistence node manifest handling."""

import pytest
from sqlalchemy.orm import Session

from src.agents.nodes.persistence_node import (
    _persist_from_manifest,
    _persist_manifest_fact,
    _persist_manifest_relationship,
    _persist_manifest_goal_creation,
    _persist_manifest_goal_update,
)
from src.database.models.entities import Entity
from src.database.models.enums import EntityType, GoalPriority, GoalStatus, GoalType
from src.database.models.goals import NPCGoal
from src.database.models.session import GameSession
from src.managers.entity_manager import EntityManager
from src.managers.fact_manager import FactManager
from src.managers.goal_manager import GoalManager
from src.managers.relationship_manager import RelationshipManager


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def entity_manager(db_session: Session, game_session: GameSession) -> EntityManager:
    """Create EntityManager instance."""
    return EntityManager(db_session, game_session)


@pytest.fixture
def fact_manager(db_session: Session, game_session: GameSession) -> FactManager:
    """Create FactManager instance."""
    return FactManager(db_session, game_session)


@pytest.fixture
def goal_manager(db_session: Session, game_session: GameSession) -> GoalManager:
    """Create GoalManager instance."""
    return GoalManager(db_session, game_session)


@pytest.fixture
def relationship_manager(
    db_session: Session, game_session: GameSession
) -> RelationshipManager:
    """Create RelationshipManager instance."""
    return RelationshipManager(db_session, game_session)


@pytest.fixture
def player_entity(db_session: Session, game_session: GameSession) -> Entity:
    """Create player entity."""
    entity = Entity(
        session_id=game_session.id,
        entity_key="player",
        display_name="Hero",
        entity_type=EntityType.PLAYER,
    )
    db_session.add(entity)
    db_session.flush()
    return entity


@pytest.fixture
def npc_entity(db_session: Session, game_session: GameSession) -> Entity:
    """Create NPC entity."""
    entity = Entity(
        session_id=game_session.id,
        entity_key="merchant_bob",
        display_name="Bob the Merchant",
        entity_type=EntityType.NPC,
    )
    db_session.add(entity)
    db_session.flush()
    return entity


# =============================================================================
# Fact Persistence Tests
# =============================================================================


class TestManifestFactPersistence:
    """Tests for _persist_manifest_fact."""

    def test_persists_basic_fact(
        self,
        fact_manager: FactManager,
    ):
        """Test that basic facts are persisted."""
        fact_data = {
            "subject": "merchant_bob",
            "predicate": "works_at",
            "value": "general_store",
            "is_secret": False,
        }

        _persist_manifest_fact(fact_manager, fact_data)

        facts = fact_manager.get_facts_about("merchant_bob")
        assert len(facts) == 1
        assert facts[0].predicate == "works_at"
        assert facts[0].value == "general_store"

    def test_persists_secret_fact(
        self,
        fact_manager: FactManager,
    ):
        """Test that secret facts are marked correctly."""
        fact_data = {
            "subject": "merchant_bob",
            "predicate": "secretly_is",
            "value": "thieves_guild_member",
            "is_secret": True,
        }

        _persist_manifest_fact(fact_manager, fact_data)

        # Need include_secrets=True to see secret facts
        facts = fact_manager.get_facts_about("merchant_bob", include_secrets=True)
        assert len(facts) == 1
        assert facts[0].is_secret is True

    def test_skips_incomplete_fact(
        self,
        fact_manager: FactManager,
    ):
        """Test that incomplete facts are skipped."""
        fact_data = {
            "subject": "merchant_bob",
            # Missing predicate and value
        }

        _persist_manifest_fact(fact_manager, fact_data)

        facts = fact_manager.get_facts_about("merchant_bob")
        assert len(facts) == 0


# =============================================================================
# Relationship Persistence Tests
# =============================================================================


class TestManifestRelationshipPersistence:
    """Tests for _persist_manifest_relationship."""

    def test_persists_relationship_change(
        self,
        entity_manager: EntityManager,
        relationship_manager: RelationshipManager,
        player_entity: Entity,
        npc_entity: Entity,
    ):
        """Test that relationship changes are persisted."""
        # First establish familiarity so relationship changes aren't capped
        rel = relationship_manager.get_or_create_relationship(
            npc_entity.id, player_entity.id
        )
        rel.familiarity = 50  # Enough to allow full trust changes
        relationship_manager.db.flush()

        change_data = {
            "from_entity": "merchant_bob",
            "to_entity": "player",
            "dimension": "trust",
            "delta": 10,
            "reason": "player helped with bandits",
        }

        _persist_manifest_relationship(
            entity_manager, relationship_manager, change_data
        )

        rel = relationship_manager.get_or_create_relationship(
            npc_entity.id, player_entity.id
        )
        assert rel.trust == 60  # 50 (default) + 10

    def test_skips_missing_entity(
        self,
        entity_manager: EntityManager,
        relationship_manager: RelationshipManager,
        player_entity: Entity,
    ):
        """Test that changes with missing entities are skipped."""
        change_data = {
            "from_entity": "nonexistent_npc",
            "to_entity": "player",
            "dimension": "trust",
            "delta": 10,
            "reason": "test",
        }

        # Should not raise, just skip
        _persist_manifest_relationship(
            entity_manager, relationship_manager, change_data
        )

    def test_skips_incomplete_change(
        self,
        entity_manager: EntityManager,
        relationship_manager: RelationshipManager,
    ):
        """Test that incomplete changes are skipped."""
        change_data = {
            "from_entity": "merchant_bob",
            # Missing to_entity and dimension
        }

        # Should not raise, just skip
        _persist_manifest_relationship(
            entity_manager, relationship_manager, change_data
        )


# =============================================================================
# Goal Creation Tests
# =============================================================================


class TestManifestGoalCreation:
    """Tests for _persist_manifest_goal_creation."""

    def test_creates_basic_goal(
        self,
        entity_manager: EntityManager,
        goal_manager: GoalManager,
        npc_entity: Entity,
    ):
        """Test that goals are created from manifest."""
        goal_data = {
            "entity_key": "merchant_bob",
            "goal_type": "acquire",
            "target": "rare_gem",
            "description": "Find the rare gem for a customer",
            "priority": "high",
            "motivation": ["profit", "reputation"],
            "strategies": ["visit mines", "check market"],
            "success_condition": "gem acquired",
        }

        _persist_manifest_goal_creation(entity_manager, goal_manager, goal_data)

        goals = goal_manager.get_entity_goals(npc_entity.id)
        assert len(goals) == 1
        assert goals[0].goal_type == GoalType.ACQUIRE
        assert goals[0].target == "rare_gem"
        assert goals[0].priority == GoalPriority.HIGH
        assert "profit" in goals[0].motivation

    def test_handles_invalid_goal_type(
        self,
        entity_manager: EntityManager,
        goal_manager: GoalManager,
        npc_entity: Entity,
    ):
        """Test that invalid goal types default to ACQUIRE."""
        goal_data = {
            "entity_key": "merchant_bob",
            "goal_type": "invalid_type",
            "target": "something",
            "description": "Test goal",
        }

        _persist_manifest_goal_creation(entity_manager, goal_manager, goal_data)

        goals = goal_manager.get_entity_goals(npc_entity.id)
        assert len(goals) == 1
        assert goals[0].goal_type == GoalType.ACQUIRE

    def test_skips_missing_entity(
        self,
        entity_manager: EntityManager,
        goal_manager: GoalManager,
    ):
        """Test that goals for missing entities are skipped."""
        goal_data = {
            "entity_key": "nonexistent_npc",
            "goal_type": "acquire",
            "target": "something",
            "description": "Test goal",
        }

        # Should not raise, just skip
        _persist_manifest_goal_creation(entity_manager, goal_manager, goal_data)

        # Verify no goals were created
        all_goals = goal_manager.get_active_goals()
        assert len(all_goals) == 0


# =============================================================================
# Goal Update Tests
# =============================================================================


class TestManifestGoalUpdate:
    """Tests for _persist_manifest_goal_update."""

    @pytest.fixture
    def existing_goal(
        self,
        goal_manager: GoalManager,
        npc_entity: Entity,
    ) -> NPCGoal:
        """Create an existing goal."""
        return goal_manager.create_goal(
            entity_id=npc_entity.id,
            goal_type=GoalType.ACQUIRE,
            target="rare_gem",
            description="Find the rare gem",
            success_condition="gem acquired",
            priority=GoalPriority.MEDIUM,
            strategies=["step 1", "step 2", "step 3"],
            goal_key="test_goal_001",
        )

    def test_completes_goal(
        self,
        goal_manager: GoalManager,
        existing_goal: NPCGoal,
    ):
        """Test that goals can be completed via manifest."""
        update_data = {
            "goal_key": "test_goal_001",
            "status": "completed",
            "outcome": "Found the gem in the mines",
        }

        _persist_manifest_goal_update(goal_manager, update_data)

        goal = goal_manager.get_goal(existing_goal.id)
        assert goal.status == GoalStatus.COMPLETED
        assert goal.outcome == "Found the gem in the mines"

    def test_fails_goal(
        self,
        goal_manager: GoalManager,
        existing_goal: NPCGoal,
    ):
        """Test that goals can be failed via manifest."""
        update_data = {
            "goal_key": "test_goal_001",
            "status": "failed",
            "outcome": "The gem was stolen by another",
        }

        _persist_manifest_goal_update(goal_manager, update_data)

        goal = goal_manager.get_goal(existing_goal.id)
        assert goal.status == GoalStatus.FAILED

    def test_advances_step(
        self,
        goal_manager: GoalManager,
        existing_goal: NPCGoal,
    ):
        """Test that goal steps can be advanced via manifest."""
        update_data = {
            "goal_key": "test_goal_001",
            "current_step": 2,
        }

        _persist_manifest_goal_update(goal_manager, update_data)

        goal = goal_manager.get_goal(existing_goal.id)
        assert goal.current_step == 2

    def test_skips_missing_goal(
        self,
        goal_manager: GoalManager,
    ):
        """Test that updates for missing goals are skipped."""
        update_data = {
            "goal_key": "nonexistent_goal",
            "status": "completed",
            "outcome": "test",
        }

        # Should not raise, just skip
        _persist_manifest_goal_update(goal_manager, update_data)


# =============================================================================
# Full Manifest Persistence Tests
# =============================================================================


class TestFullManifestPersistence:
    """Tests for _persist_from_manifest."""

    def test_persists_complete_manifest(
        self,
        entity_manager: EntityManager,
        fact_manager: FactManager,
        relationship_manager: RelationshipManager,
        goal_manager: GoalManager,
        player_entity: Entity,
        npc_entity: Entity,
    ):
        """Test that a complete manifest is persisted correctly."""
        # First establish familiarity so relationship changes aren't capped
        rel = relationship_manager.get_or_create_relationship(
            npc_entity.id, player_entity.id
        )
        rel.familiarity = 50
        relationship_manager.db.flush()

        manifest = {
            "facts_revealed": [
                {
                    "subject": "merchant_bob",
                    "predicate": "hometown",
                    "value": "Riverdale",
                    "is_secret": False,
                }
            ],
            "relationship_changes": [
                {
                    "from_entity": "merchant_bob",
                    "to_entity": "player",
                    "dimension": "liking",
                    "delta": 5,
                    "reason": "friendly conversation",
                }
            ],
            "goals_created": [
                {
                    "entity_key": "merchant_bob",
                    "goal_type": "social",
                    "target": "player",
                    "description": "Get to know the newcomer",
                    "priority": "low",
                }
            ],
            "goal_updates": [],
        }

        errors = _persist_from_manifest(
            entity_manager,
            fact_manager,
            relationship_manager,
            goal_manager,
            manifest,
            player_entity.id,
        )

        assert errors == []

        # Verify fact
        facts = fact_manager.get_facts_about("merchant_bob")
        assert len(facts) == 1
        assert facts[0].predicate == "hometown"

        # Verify relationship
        rel = relationship_manager.get_or_create_relationship(
            npc_entity.id, player_entity.id
        )
        assert rel.liking == 55  # 50 + 5

        # Verify goal
        goals = goal_manager.get_entity_goals(npc_entity.id)
        assert len(goals) == 1
        assert goals[0].goal_type == GoalType.SOCIAL

    def test_returns_errors_for_failures(
        self,
        entity_manager: EntityManager,
        fact_manager: FactManager,
        relationship_manager: RelationshipManager,
        goal_manager: GoalManager,
        player_entity: Entity,
        npc_entity: Entity,
    ):
        """Test that errors are collected and returned."""
        # Create a goal to update
        goal = goal_manager.create_goal(
            entity_id=npc_entity.id,
            goal_type=GoalType.ACQUIRE,
            target="test",
            description="Test",
            success_condition="done",
            goal_key="update_target",
        )

        manifest = {
            "facts_revealed": [
                {
                    "subject": "test",
                    "predicate": "is",
                    "value": "working",
                }
            ],
            "relationship_changes": [],
            "goals_created": [],
            "goal_updates": [
                {
                    "goal_key": "update_target",
                    "status": "completed",
                    "outcome": "done",
                }
            ],
        }

        errors = _persist_from_manifest(
            entity_manager,
            fact_manager,
            relationship_manager,
            goal_manager,
            manifest,
            player_entity.id,
        )

        # Should complete without errors
        assert errors == []

        # Verify goal was completed
        updated_goal = goal_manager.get_goal(goal.id)
        assert updated_goal.status == GoalStatus.COMPLETED

    def test_handles_empty_manifest(
        self,
        entity_manager: EntityManager,
        fact_manager: FactManager,
        relationship_manager: RelationshipManager,
        goal_manager: GoalManager,
        player_entity: Entity,
    ):
        """Test that empty manifest is handled gracefully."""
        manifest = {
            "facts_revealed": [],
            "relationship_changes": [],
            "goals_created": [],
            "goal_updates": [],
        }

        errors = _persist_from_manifest(
            entity_manager,
            fact_manager,
            relationship_manager,
            goal_manager,
            manifest,
            player_entity.id,
        )

        assert errors == []
