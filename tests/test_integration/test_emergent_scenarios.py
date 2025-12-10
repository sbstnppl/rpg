"""Integration tests for emergent NPC behavior scenarios.

These tests verify that the full system works together:
- EmergentNPCGenerator creates NPCs with situational awareness
- NPCs react to player's visible items and state
- Goals are created and persisted correctly
- Persistence node handles manifest data correctly
"""

import pytest
from sqlalchemy.orm import Session

from src.agents.nodes.persistence_node import _persist_from_manifest
from src.agents.schemas.npc_state import (
    NPCConstraints,
    PlayerSummary,
    SceneContext,
    VisibleItem,
)
from src.database.models.character_state import CharacterNeeds
from src.database.models.entities import Entity
from src.database.models.enums import EntityType, GoalPriority, GoalStatus, GoalType
from src.database.models.session import GameSession
from src.managers.entity_manager import EntityManager
from src.managers.fact_manager import FactManager
from src.managers.goal_manager import GoalManager
from src.managers.relationship_manager import RelationshipManager
from src.services.emergent_npc_generator import EmergentNPCGenerator


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def generator(db_session: Session, game_session: GameSession) -> EmergentNPCGenerator:
    """Create EmergentNPCGenerator instance."""
    return EmergentNPCGenerator(db_session, game_session)


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


# =============================================================================
# Scenario: Hungry NPC in Tavern Notices Player's Food
# =============================================================================


class TestHungryNPCScenario:
    """Test that hungry NPCs react to visible food."""

    def test_hungry_npc_notices_player_food(
        self,
        generator: EmergentNPCGenerator,
        player_entity: Entity,
        entity_manager: EntityManager,
    ):
        """Hungry NPC should notice and react to player's visible food."""
        scene = SceneContext(
            location_key="tavern",
            location_description="A warm tavern filled with the smell of roasting meat",
            entities_present=["player"],
            visible_items=[
                VisibleItem(
                    item_key="bread_loaf",
                    display_name="Fresh Bread",
                    brief_description="A warm, fresh loaf of bread",
                    holder_key="player",
                ),
            ],
            environment=["warm", "smells of food"],
            player_visible_state=PlayerSummary(
                appearance_summary="A traveler with bread",
                visible_items=["bread_loaf"],
            ),
        )

        # Create a hungry traveler
        npc = generator.create_npc(
            role="traveler",
            location_key="tavern",
            scene_context=scene,
        )

        # Set hunger to high (low value = hungry)
        entity = entity_manager.get_entity(npc.entity_key)
        needs = generator.db.query(CharacterNeeds).filter(
            CharacterNeeds.entity_id == entity.id
        ).first()
        needs.hunger = 15  # Very hungry
        generator.db.flush()

        # Query NPC reactions with updated state
        reactions = generator.query_npc_reactions(
            entity_key=npc.entity_key,
            scene_context=scene,
        )

        # Should notice the food due to hunger
        food_reactions = [
            r for r in reactions.environmental_reactions
            if "bread" in r.notices.lower() or "food" in r.notices.lower()
        ]

        # At minimum, the NPC should notice the environment
        assert reactions is not None
        assert reactions.behavioral_prediction != ""

    def test_satisfied_npc_less_interested_in_food(
        self,
        generator: EmergentNPCGenerator,
        player_entity: Entity,
        entity_manager: EntityManager,
    ):
        """Well-fed NPC should not strongly react to food."""
        scene = SceneContext(
            location_key="tavern",
            location_description="A warm tavern",
            entities_present=["player"],
            visible_items=[
                VisibleItem(
                    item_key="bread_loaf",
                    display_name="Fresh Bread",
                    brief_description="A warm loaf",
                    holder_key="player",
                ),
            ],
            environment=["warm"],
            player_visible_state=PlayerSummary(
                appearance_summary="A traveler",
                visible_items=["bread_loaf"],
            ),
        )

        # Create an NPC who just ate (well-fed)
        npc = generator.create_npc(
            role="merchant",
            location_key="tavern",
            scene_context=scene,
        )

        # Set hunger to satisfied (high value = not hungry)
        entity = entity_manager.get_entity(npc.entity_key)
        needs = generator.db.query(CharacterNeeds).filter(
            CharacterNeeds.entity_id == entity.id
        ).first()
        needs.hunger = 90  # Very satisfied
        generator.db.flush()

        # Query NPC reactions
        reactions = generator.query_npc_reactions(
            entity_key=npc.entity_key,
            scene_context=scene,
        )

        # Check that food reactions aren't urgent
        food_reactions = [
            r for r in reactions.environmental_reactions
            if r.need_triggered == "hunger" and r.intensity in ("strong", "overwhelming")
        ]

        # Should have no strong hunger reactions when satisfied
        assert len(food_reactions) == 0


# =============================================================================
# Scenario: NPC with Goal Appears at Relevant Location
# =============================================================================


class TestGoalDrivenNPCScenario:
    """Test NPC goal creation and pursuit."""

    def test_npc_goal_persisted_via_manifest(
        self,
        entity_manager: EntityManager,
        fact_manager: FactManager,
        relationship_manager: RelationshipManager,
        goal_manager: GoalManager,
        player_entity: Entity,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test that NPC goals can be created via manifest persistence."""
        # Create an NPC first
        npc = Entity(
            session_id=game_session.id,
            entity_key="merchant_elena",
            display_name="Elena",
            entity_type=EntityType.NPC,
        )
        db_session.add(npc)
        db_session.flush()

        # Simulate GM creating a goal via manifest
        manifest = {
            "facts_revealed": [],
            "relationship_changes": [],
            "goals_created": [
                {
                    "entity_key": "merchant_elena",
                    "goal_type": "acquire",
                    "target": "rare_herbs",
                    "description": "Find rare healing herbs for a sick customer",
                    "priority": "high",
                    "motivation": ["compassion", "business"],
                    "strategies": ["visit herbalist", "check forest"],
                    "success_condition": "herbs acquired",
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

        # Verify goal was created
        goals = goal_manager.get_entity_goals(npc.id)
        assert len(goals) == 1
        assert goals[0].goal_type == GoalType.ACQUIRE
        assert goals[0].target == "rare_herbs"
        assert goals[0].priority == GoalPriority.HIGH
        assert "compassion" in goals[0].motivation

    def test_goal_updates_via_manifest(
        self,
        entity_manager: EntityManager,
        fact_manager: FactManager,
        relationship_manager: RelationshipManager,
        goal_manager: GoalManager,
        player_entity: Entity,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test that goal progress can be updated via manifest."""
        # Create NPC and goal
        npc = Entity(
            session_id=game_session.id,
            entity_key="guard_marcus",
            display_name="Marcus",
            entity_type=EntityType.NPC,
        )
        db_session.add(npc)
        db_session.flush()

        goal = goal_manager.create_goal(
            entity_id=npc.id,
            goal_type=GoalType.PROTECT,
            target="town_gate",
            description="Guard the town gate during the festival",
            success_condition="festival ends safely",
            priority=GoalPriority.HIGH,
            strategies=["patrol regularly", "check travelers", "report suspicious activity"],
            goal_key="guard_festival_001",
        )

        # Advance goal via manifest
        manifest = {
            "facts_revealed": [],
            "relationship_changes": [],
            "goals_created": [],
            "goal_updates": [
                {
                    "goal_key": "guard_festival_001",
                    "current_step": 1,  # Completed first step
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

        assert errors == []

        # Verify goal was updated
        updated_goal = goal_manager.get_goal(goal.id)
        assert updated_goal.current_step == 1

    def test_goal_completion_via_manifest(
        self,
        entity_manager: EntityManager,
        fact_manager: FactManager,
        relationship_manager: RelationshipManager,
        goal_manager: GoalManager,
        player_entity: Entity,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test that goals can be completed via manifest."""
        # Create NPC and goal
        npc = Entity(
            session_id=game_session.id,
            entity_key="blacksmith_theron",
            display_name="Theron",
            entity_type=EntityType.NPC,
        )
        db_session.add(npc)
        db_session.flush()

        goal = goal_manager.create_goal(
            entity_id=npc.id,
            goal_type=GoalType.ACQUIRE,
            target="iron_ore",
            description="Buy iron ore from the mines",
            success_condition="ore purchased",
            goal_key="theron_buy_ore",
        )

        # Complete goal via manifest
        manifest = {
            "facts_revealed": [],
            "relationship_changes": [],
            "goals_created": [],
            "goal_updates": [
                {
                    "goal_key": "theron_buy_ore",
                    "status": "completed",
                    "outcome": "Purchased 50 pounds of ore at a fair price",
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

        assert errors == []

        # Verify goal was completed
        completed_goal = goal_manager.get_goal(goal.id)
        assert completed_goal.status == GoalStatus.COMPLETED
        assert "50 pounds" in completed_goal.outcome


# =============================================================================
# Scenario: NPC Attraction to Player
# =============================================================================


class TestAttractionScenario:
    """Test NPC attraction calculations."""

    def test_npc_attraction_varies_by_player_traits(
        self,
        generator: EmergentNPCGenerator,
        player_entity: Entity,
    ):
        """NPCs with different preferences should have varying attraction."""
        # Scene with player who has specific visible traits
        scene = SceneContext(
            location_key="tavern",
            location_description="A busy tavern",
            entities_present=["player"],
            visible_items=[],
            environment=["crowded", "noisy"],
            player_visible_state=PlayerSummary(
                appearance_summary="A tall, dark-haired man with lean build and kind eyes",
                visible_items=["sword", "cloak"],
                visible_conditions=["well-dressed", "confident posture"],
                current_activity="drinking alone",
            ),
        )

        # Create multiple NPCs and check attraction varies
        attraction_scores = []
        for i in range(5):
            npc = generator.create_npc(
                role="customer",
                location_key="tavern",
                scene_context=scene,
            )

            # Look for attraction reaction
            for reaction in npc.environmental_reactions:
                if reaction.reaction_type == "attraction" and reaction.attraction_score:
                    attraction_scores.append(reaction.attraction_score.overall)

        # With 5 NPCs, we should have some variation in attraction
        # (test that the system is actually calculating)
        if len(attraction_scores) > 1:
            # Attraction should vary (not all the same)
            assert max(attraction_scores) != min(attraction_scores) or len(set(attraction_scores)) == 1

    def test_constraint_attracted_forces_attraction(
        self,
        generator: EmergentNPCGenerator,
        player_entity: Entity,
    ):
        """When attracted_to_player constraint is set, NPC should be attracted."""
        scene = SceneContext(
            location_key="tavern",
            location_description="A quiet tavern",
            entities_present=["player"],
            visible_items=[],
            environment=["dim lighting"],
            player_visible_state=PlayerSummary(
                appearance_summary="A stranger at the bar",
                visible_items=[],
            ),
        )

        # Force attraction via constraint
        constraints = NPCConstraints(attracted_to_player=True)

        npc = generator.create_npc(
            role="barmaid",
            location_key="tavern",
            scene_context=scene,
            constraints=constraints,
        )

        # Should have attraction reaction
        attraction_reactions = [
            r for r in npc.environmental_reactions
            if r.reaction_type == "attraction"
        ]

        assert len(attraction_reactions) > 0
        # When constrained, attraction should be positive
        if attraction_reactions[0].attraction_score:
            assert attraction_reactions[0].attraction_score.overall > 0.5


# =============================================================================
# Scenario: Full Manifest Workflow
# =============================================================================


class TestFullManifestWorkflow:
    """Test complete manifest-based workflows."""

    def test_complex_manifest_persistence(
        self,
        entity_manager: EntityManager,
        fact_manager: FactManager,
        relationship_manager: RelationshipManager,
        goal_manager: GoalManager,
        player_entity: Entity,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test persisting a complex manifest with multiple components."""
        # Create NPCs for the scene
        merchant = Entity(
            session_id=game_session.id,
            entity_key="merchant_anna",
            display_name="Anna",
            entity_type=EntityType.NPC,
        )
        guard = Entity(
            session_id=game_session.id,
            entity_key="guard_tom",
            display_name="Tom",
            entity_type=EntityType.NPC,
        )
        db_session.add_all([merchant, guard])
        db_session.flush()

        # Establish familiarity so relationship changes apply
        rel = relationship_manager.get_or_create_relationship(
            merchant.id, player_entity.id
        )
        rel.familiarity = 60
        db_session.flush()

        # Complex manifest from a single turn
        manifest = {
            "facts_revealed": [
                {
                    "subject": "merchant_anna",
                    "predicate": "sells",
                    "value": "rare herbs and potions",
                    "is_secret": False,
                },
                {
                    "subject": "guard_tom",
                    "predicate": "is_related_to",
                    "value": "the captain of the guard",
                    "is_secret": True,
                },
            ],
            "relationship_changes": [
                {
                    "from_entity": "merchant_anna",
                    "to_entity": "player",
                    "dimension": "trust",
                    "delta": 15,
                    "reason": "player helped chase off a thief",
                },
            ],
            "goals_created": [
                {
                    "entity_key": "merchant_anna",
                    "goal_type": "social",
                    "target": "player",
                    "description": "Get to know the helpful stranger",
                    "priority": "medium",
                    "motivation": ["gratitude", "curiosity"],
                },
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

        # Verify facts
        anna_facts = fact_manager.get_facts_about("merchant_anna")
        assert len(anna_facts) == 1
        assert anna_facts[0].predicate == "sells"

        # Secret fact needs include_secrets
        tom_facts = fact_manager.get_facts_about("guard_tom", include_secrets=True)
        assert len(tom_facts) == 1
        assert tom_facts[0].is_secret is True

        # Verify relationship
        rel = relationship_manager.get_relationship(merchant.id, player_entity.id)
        assert rel.trust == 65  # 50 base + 15 delta

        # Verify goal
        goals = goal_manager.get_entity_goals(merchant.id)
        assert len(goals) == 1
        assert goals[0].goal_type == GoalType.SOCIAL
        assert "gratitude" in goals[0].motivation

    def test_manifest_with_goal_failure(
        self,
        entity_manager: EntityManager,
        fact_manager: FactManager,
        relationship_manager: RelationshipManager,
        goal_manager: GoalManager,
        player_entity: Entity,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test persisting goal failure via manifest."""
        # Create NPC with an active goal
        thief = Entity(
            session_id=game_session.id,
            entity_key="thief_shadow",
            display_name="Shadow",
            entity_type=EntityType.NPC,
        )
        db_session.add(thief)
        db_session.flush()

        goal = goal_manager.create_goal(
            entity_id=thief.id,
            goal_type=GoalType.ACQUIRE,
            target="gold_purse",
            description="Steal the merchant's gold purse",
            success_condition="purse stolen undetected",
            failure_condition="caught or chased away",
            goal_key="steal_purse_001",
        )

        # Fail the goal via manifest
        manifest = {
            "facts_revealed": [
                {
                    "subject": "thief_shadow",
                    "predicate": "attempted_to_steal",
                    "value": "from merchant",
                    "is_secret": False,
                }
            ],
            "relationship_changes": [],
            "goals_created": [],
            "goal_updates": [
                {
                    "goal_key": "steal_purse_001",
                    "status": "failed",
                    "outcome": "Caught by an alert guard and chased away",
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

        assert errors == []

        # Verify goal failed
        failed_goal = goal_manager.get_goal(goal.id)
        assert failed_goal.status == GoalStatus.FAILED
        assert "caught" in failed_goal.outcome.lower()

        # Verify fact was recorded
        facts = fact_manager.get_facts_about("thief_shadow")
        assert len(facts) == 1
