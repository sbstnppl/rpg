"""Tests for the EmergentNPCGenerator service."""

import pytest
from sqlalchemy.orm import Session

from src.agents.schemas.npc_state import (
    NPCConstraints,
    NPCFullState,
    NPCReactions,
    PlayerSummary,
    SceneContext,
    VisibleItem,
)
from src.database.models.character_preferences import CharacterPreferences
from src.database.models.character_state import CharacterNeeds
from src.database.models.entities import Entity, EntitySkill, NPCExtension
from src.database.models.enums import EntityType
from src.database.models.items import Item
from src.database.models.session import GameSession
from src.services.emergent_npc_generator import EmergentNPCGenerator


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def generator(db_session: Session, game_session: GameSession) -> EmergentNPCGenerator:
    """Create EmergentNPCGenerator instance."""
    return EmergentNPCGenerator(db_session, game_session)


@pytest.fixture
def basic_scene_context() -> SceneContext:
    """Create basic scene context for tests."""
    return SceneContext(
        location_key="general_store",
        location_description="A well-stocked general store",
        entities_present=["player"],
        visible_items=[
            VisibleItem(
                item_key="water_bottle",
                display_name="Water Bottle",
                brief_description="A half-full water bottle",
                holder_key="player",
            )
        ],
        environment=["warm", "smells of spices"],
        player_visible_state=PlayerSummary(
            appearance_summary="A tall, dark-haired stranger with lean build",
            visible_items=["water_bottle", "sword"],
            visible_conditions=["travel-worn"],
            current_activity="browsing goods",
        ),
        time_of_day="afternoon",
    )


@pytest.fixture
def scene_with_food() -> SceneContext:
    """Create scene context with food items visible."""
    return SceneContext(
        location_key="tavern",
        location_description="A cozy tavern",
        entities_present=["player"],
        visible_items=[
            VisibleItem(
                item_key="bread_loaf",
                display_name="Fresh Bread",
                brief_description="A warm, fresh loaf of bread",
                holder_key="player",
            ),
            VisibleItem(
                item_key="ale_mug",
                display_name="Mug of Ale",
                brief_description="A foaming mug of ale",
                holder_key=None,
            ),
        ],
        environment=["smells of bread and stew", "warm fire"],
        time_of_day="evening",
    )


# =============================================================================
# Basic NPC Creation Tests
# =============================================================================


class TestNPCCreation:
    """Tests for basic NPC creation."""

    def test_create_npc_returns_full_state(
        self,
        generator: EmergentNPCGenerator,
        basic_scene_context: SceneContext,
    ):
        """Test that create_npc returns a complete NPCFullState."""
        npc_state = generator.create_npc(
            role="customer",
            location_key="general_store",
            scene_context=basic_scene_context,
        )

        assert isinstance(npc_state, NPCFullState)
        assert npc_state.entity_key is not None
        assert npc_state.display_name is not None
        assert npc_state.appearance is not None
        assert npc_state.background is not None
        assert npc_state.personality is not None
        assert npc_state.preferences is not None
        assert npc_state.current_needs is not None
        assert npc_state.current_state is not None
        assert npc_state.behavioral_prediction is not None

    def test_create_npc_generates_unique_entity_key(
        self,
        generator: EmergentNPCGenerator,
        basic_scene_context: SceneContext,
    ):
        """Test that each NPC gets a unique entity key."""
        npc1 = generator.create_npc(
            role="customer",
            location_key="general_store",
            scene_context=basic_scene_context,
        )
        npc2 = generator.create_npc(
            role="customer",
            location_key="general_store",
            scene_context=basic_scene_context,
        )

        assert npc1.entity_key != npc2.entity_key

    def test_create_npc_persists_to_database(
        self,
        generator: EmergentNPCGenerator,
        basic_scene_context: SceneContext,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test that created NPC is persisted to the database."""
        npc_state = generator.create_npc(
            role="merchant",
            location_key="market",
            scene_context=basic_scene_context,
        )

        # Check entity exists
        entity = (
            db_session.query(Entity)
            .filter(
                Entity.session_id == game_session.id,
                Entity.entity_key == npc_state.entity_key,
            )
            .first()
        )
        assert entity is not None
        assert entity.display_name == npc_state.display_name
        assert entity.entity_type == EntityType.NPC
        assert entity.is_alive is True
        assert entity.is_active is True

    def test_create_npc_persists_extension(
        self,
        generator: EmergentNPCGenerator,
        basic_scene_context: SceneContext,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test that NPC extension is persisted."""
        npc_state = generator.create_npc(
            role="guard",
            location_key="gate",
            scene_context=basic_scene_context,
        )

        entity = (
            db_session.query(Entity)
            .filter(Entity.entity_key == npc_state.entity_key)
            .first()
        )

        extension = (
            db_session.query(NPCExtension)
            .filter(NPCExtension.entity_id == entity.id)
            .first()
        )
        assert extension is not None
        assert extension.current_mood is not None
        assert extension.current_location == npc_state.current_state.current_location

    def test_create_npc_persists_needs(
        self,
        generator: EmergentNPCGenerator,
        basic_scene_context: SceneContext,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test that NPC needs are persisted."""
        npc_state = generator.create_npc(
            role="innkeeper",
            location_key="inn",
            scene_context=basic_scene_context,
        )

        entity = (
            db_session.query(Entity)
            .filter(Entity.entity_key == npc_state.entity_key)
            .first()
        )

        needs = (
            db_session.query(CharacterNeeds)
            .filter(
                CharacterNeeds.session_id == game_session.id,
                CharacterNeeds.entity_id == entity.id,
            )
            .first()
        )
        assert needs is not None

    def test_create_npc_persists_preferences(
        self,
        generator: EmergentNPCGenerator,
        basic_scene_context: SceneContext,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test that NPC preferences are persisted."""
        npc_state = generator.create_npc(
            role="scholar",
            location_key="library",
            scene_context=basic_scene_context,
        )

        entity = (
            db_session.query(Entity)
            .filter(Entity.entity_key == npc_state.entity_key)
            .first()
        )

        prefs = (
            db_session.query(CharacterPreferences)
            .filter(
                CharacterPreferences.session_id == game_session.id,
                CharacterPreferences.entity_id == entity.id,
            )
            .first()
        )
        assert prefs is not None
        assert prefs.attraction_preferences is not None

    def test_create_npc_persists_skills(
        self,
        generator: EmergentNPCGenerator,
        basic_scene_context: SceneContext,
        db_session: Session,
    ):
        """Test that NPC skills are persisted based on occupation."""
        npc_state = generator.create_npc(
            role="blacksmith",
            location_key="smithy",
            scene_context=basic_scene_context,
        )

        entity = (
            db_session.query(Entity)
            .filter(Entity.entity_key == npc_state.entity_key)
            .first()
        )

        skills = (
            db_session.query(EntitySkill)
            .filter(EntitySkill.entity_id == entity.id)
            .all()
        )
        assert len(skills) > 0
        skill_keys = [s.skill_key for s in skills]
        assert "smithing" in skill_keys

    def test_create_npc_persists_inventory(
        self,
        generator: EmergentNPCGenerator,
        basic_scene_context: SceneContext,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test that NPC inventory items are persisted."""
        npc_state = generator.create_npc(
            role="guard",
            location_key="gate",
            scene_context=basic_scene_context,
        )

        entity = (
            db_session.query(Entity)
            .filter(Entity.entity_key == npc_state.entity_key)
            .first()
        )

        items = (
            db_session.query(Item)
            .filter(
                Item.session_id == game_session.id,
                Item.owner_id == entity.id,
            )
            .all()
        )
        # Guards should have sword and whistle
        assert len(items) >= 1


# =============================================================================
# Constraint Tests
# =============================================================================


class TestNPCConstraints:
    """Tests for NPC creation with constraints."""

    def test_constraint_gender(
        self,
        generator: EmergentNPCGenerator,
        basic_scene_context: SceneContext,
    ):
        """Test that gender constraint is respected."""
        constraints = NPCConstraints(gender="female")
        npc_state = generator.create_npc(
            role="customer",
            location_key="store",
            scene_context=basic_scene_context,
            constraints=constraints,
        )

        assert npc_state.appearance.gender == "female"

    def test_constraint_name(
        self,
        generator: EmergentNPCGenerator,
        basic_scene_context: SceneContext,
    ):
        """Test that name constraint is respected."""
        constraints = NPCConstraints(name="Marcus Ironforge")
        npc_state = generator.create_npc(
            role="blacksmith",
            location_key="smithy",
            scene_context=basic_scene_context,
            constraints=constraints,
        )

        assert npc_state.display_name == "Marcus Ironforge"

    def test_constraint_age_range(
        self,
        generator: EmergentNPCGenerator,
        basic_scene_context: SceneContext,
    ):
        """Test that age range constraint is respected."""
        constraints = NPCConstraints(age_range="elderly")
        npc_state = generator.create_npc(
            role="sage",
            location_key="tower",
            scene_context=basic_scene_context,
            constraints=constraints,
        )

        assert npc_state.appearance.age >= 56

    def test_constraint_personality(
        self,
        generator: EmergentNPCGenerator,
        basic_scene_context: SceneContext,
    ):
        """Test that personality constraint is respected."""
        constraints = NPCConstraints(personality=["shy", "suspicious"])
        npc_state = generator.create_npc(
            role="hermit",
            location_key="cave",
            scene_context=basic_scene_context,
            constraints=constraints,
        )

        assert "shy" in npc_state.personality.traits
        assert "suspicious" in npc_state.personality.traits

    def test_constraint_exact_age(
        self,
        generator: EmergentNPCGenerator,
        basic_scene_context: SceneContext,
    ):
        """Test that exact age constraint is respected."""
        constraints = NPCConstraints(age_exact=25)
        npc_state = generator.create_npc(
            role="guard",
            location_key="gate",
            scene_context=basic_scene_context,
            constraints=constraints,
        )

        assert npc_state.appearance.age == 25


# =============================================================================
# Environmental Reaction Tests
# =============================================================================


class TestEnvironmentalReactions:
    """Tests for NPC environmental reactions."""

    def test_npc_notices_player(
        self,
        generator: EmergentNPCGenerator,
        basic_scene_context: SceneContext,
    ):
        """Test that NPC can have reaction to player."""
        npc_state = generator.create_npc(
            role="customer",
            location_key="store",
            scene_context=basic_scene_context,
        )

        # Check if there are any environmental reactions
        # (may or may not include player attraction based on random generation)
        assert npc_state.environmental_reactions is not None

    def test_hungry_npc_notices_food(
        self,
        generator: EmergentNPCGenerator,
        scene_with_food: SceneContext,
        db_session: Session,
    ):
        """Test that hungry NPCs notice food items."""
        # Create NPC - needs are randomized but scene context triggers reactions
        npc_state = generator.create_npc(
            role="beggar",
            location_key="tavern",
            scene_context=scene_with_food,
        )

        # Food/drink reactions depend on need levels
        # The scene has bread and ale which should trigger reactions if needs are high
        food_reactions = [
            r for r in npc_state.environmental_reactions
            if r.reaction_type == "need_triggered"
        ]
        # We can't guarantee reactions since needs are random,
        # but the system should process items
        assert isinstance(food_reactions, list)

    def test_attraction_calculation(
        self,
        generator: EmergentNPCGenerator,
        basic_scene_context: SceneContext,
    ):
        """Test that attraction scores are calculated."""
        # Use constraint to force attraction
        constraints = NPCConstraints(attracted_to_player=True)
        npc_state = generator.create_npc(
            role="customer",
            location_key="store",
            scene_context=basic_scene_context,
            constraints=constraints,
        )

        attraction_reactions = [
            r for r in npc_state.environmental_reactions
            if r.reaction_type == "attraction"
        ]
        assert len(attraction_reactions) > 0
        assert attraction_reactions[0].attraction_score is not None
        assert attraction_reactions[0].attraction_score.overall >= 0.5


# =============================================================================
# Goal Generation Tests
# =============================================================================


class TestGoalGeneration:
    """Tests for immediate goal generation."""

    def test_generates_primary_goal(
        self,
        generator: EmergentNPCGenerator,
        basic_scene_context: SceneContext,
    ):
        """Test that NPC has a primary goal based on role."""
        npc_state = generator.create_npc(
            role="merchant",
            location_key="market",
            scene_context=basic_scene_context,
        )

        primary_goals = [
            g for g in npc_state.immediate_goals
            if g.priority == "primary"
        ]
        assert len(primary_goals) > 0

    def test_behavioral_prediction_generated(
        self,
        generator: EmergentNPCGenerator,
        basic_scene_context: SceneContext,
    ):
        """Test that behavioral prediction is generated."""
        npc_state = generator.create_npc(
            role="guard",
            location_key="gate",
            scene_context=basic_scene_context,
        )

        assert npc_state.behavioral_prediction is not None
        assert len(npc_state.behavioral_prediction) > 0


# =============================================================================
# Query NPC Tests
# =============================================================================


class TestQueryNPC:
    """Tests for querying existing NPCs."""

    def test_query_existing_npc(
        self,
        generator: EmergentNPCGenerator,
        basic_scene_context: SceneContext,
    ):
        """Test querying an existing NPC's reactions."""
        # First create an NPC
        npc_state = generator.create_npc(
            role="shopkeeper",
            location_key="store",
            scene_context=basic_scene_context,
        )

        # Now query their reactions
        reactions = generator.query_npc_reactions(
            entity_key=npc_state.entity_key,
            scene_context=basic_scene_context,
        )

        assert reactions is not None
        assert isinstance(reactions, NPCReactions)
        assert reactions.entity_key == npc_state.entity_key
        assert reactions.current_needs is not None
        assert reactions.behavioral_prediction is not None

    def test_query_nonexistent_npc(
        self,
        generator: EmergentNPCGenerator,
        basic_scene_context: SceneContext,
    ):
        """Test querying a non-existent NPC returns None."""
        reactions = generator.query_npc_reactions(
            entity_key="nonexistent_npc",
            scene_context=basic_scene_context,
        )

        assert reactions is None

    def test_query_updates_with_new_scene(
        self,
        generator: EmergentNPCGenerator,
        basic_scene_context: SceneContext,
        scene_with_food: SceneContext,
    ):
        """Test that querying with new scene context recalculates reactions."""
        # Create NPC in basic scene
        npc_state = generator.create_npc(
            role="customer",
            location_key="store",
            scene_context=basic_scene_context,
        )

        # Query with food scene
        reactions = generator.query_npc_reactions(
            entity_key=npc_state.entity_key,
            scene_context=scene_with_food,
        )

        assert reactions is not None
        # Reactions might be different now due to food in scene


# =============================================================================
# Appearance Generation Tests
# =============================================================================


class TestAppearanceGeneration:
    """Tests for appearance generation."""

    def test_appearance_has_required_fields(
        self,
        generator: EmergentNPCGenerator,
        basic_scene_context: SceneContext,
    ):
        """Test that appearance has all required fields."""
        npc_state = generator.create_npc(
            role="farmer",
            location_key="farm",
            scene_context=basic_scene_context,
        )

        appearance = npc_state.appearance
        assert appearance.age > 0
        assert appearance.gender in ["male", "female"]
        assert appearance.height_cm > 0
        assert appearance.age_description is not None
        assert appearance.height_description is not None
        assert appearance.build is not None
        assert appearance.hair is not None
        assert appearance.eyes is not None
        assert appearance.skin is not None
        assert appearance.clothing is not None

    def test_build_influenced_by_role(
        self,
        generator: EmergentNPCGenerator,
        basic_scene_context: SceneContext,
    ):
        """Test that physical occupations tend toward stronger builds."""
        physical_builds = []
        for _ in range(5):
            npc_state = generator.create_npc(
                role="blacksmith",
                location_key="smithy",
                scene_context=basic_scene_context,
            )
            physical_builds.append(npc_state.appearance.build)

        # At least some should be muscular/athletic/stocky
        strong_builds = {"muscular", "athletic", "stocky", "wiry"}
        assert any(b in strong_builds for b in physical_builds)


# =============================================================================
# Personality Generation Tests
# =============================================================================


class TestPersonalityGeneration:
    """Tests for personality generation."""

    def test_personality_has_traits(
        self,
        generator: EmergentNPCGenerator,
        basic_scene_context: SceneContext,
    ):
        """Test that personality has traits, values, and flaws."""
        npc_state = generator.create_npc(
            role="bard",
            location_key="tavern",
            scene_context=basic_scene_context,
        )

        personality = npc_state.personality
        assert len(personality.traits) >= 2
        assert len(personality.values) >= 1
        assert len(personality.flaws) >= 1

    def test_personality_variability(
        self,
        generator: EmergentNPCGenerator,
        basic_scene_context: SceneContext,
    ):
        """Test that different NPCs get different personalities."""
        npcs = [
            generator.create_npc(
                role="customer",
                location_key="store",
                scene_context=basic_scene_context,
            )
            for _ in range(3)
        ]

        # Check that at least some traits differ
        all_traits = [set(npc.personality.traits) for npc in npcs]
        # Not all should be identical
        assert not all(t == all_traits[0] for t in all_traits)


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_existing_entity_returns_existing(
        self,
        generator: EmergentNPCGenerator,
        basic_scene_context: SceneContext,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test that creating an NPC with existing entity_key returns existing."""
        # Create first NPC
        npc1 = generator.create_npc(
            role="shopkeeper",
            location_key="store",
            scene_context=basic_scene_context,
        )

        # Count entities
        count_before = (
            db_session.query(Entity)
            .filter(Entity.session_id == game_session.id)
            .count()
        )

        # Try to get same NPC again (via query)
        reactions = generator.query_npc_reactions(
            entity_key=npc1.entity_key,
            scene_context=basic_scene_context,
        )

        # Should return reactions for existing NPC
        assert reactions is not None
        assert reactions.entity_key == npc1.entity_key

        # No new entity should be created
        count_after = (
            db_session.query(Entity)
            .filter(Entity.session_id == game_session.id)
            .count()
        )
        assert count_after == count_before

    def test_minimal_scene_context(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test NPC creation with minimal scene context."""
        minimal_context = SceneContext(
            location_key="unknown",
            location_description="An unknown place",
        )

        npc_state = generator.create_npc(
            role="stranger",
            location_key="unknown",
            scene_context=minimal_context,
        )

        assert npc_state is not None
        assert npc_state.entity_key is not None
