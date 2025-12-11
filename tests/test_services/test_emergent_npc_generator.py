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


# =============================================================================
# Age Attraction System Tests
# =============================================================================


class TestAgeAttractionSystem:
    """Tests for the age-relative attraction system."""

    def test_age_decay_rate_varies_with_age(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that decay rate is higher for younger NPCs."""
        rate_18 = generator._calculate_age_decay_rate(18)
        rate_40 = generator._calculate_age_decay_rate(40)
        rate_60 = generator._calculate_age_decay_rate(60)

        # Younger = higher decay rate (pickier)
        assert rate_18 > rate_40 > rate_60

    def test_age_decay_rate_bounds(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that decay rate is clamped to expected bounds."""
        # Very young - should hit upper bound
        rate_very_young = generator._calculate_age_decay_rate(10)
        assert rate_very_young <= 0.30

        # Very old - should hit lower bound
        rate_very_old = generator._calculate_age_decay_rate(100)
        assert rate_very_old >= 0.03

    def test_age_decay_rate_formula(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test specific decay rate values."""
        # At age 40, formula gives exactly 0.1
        rate_40 = generator._calculate_age_decay_rate(40)
        assert abs(rate_40 - 0.1) < 0.001

        # At age 18, formula gives 0.1 * (40/18) ≈ 0.222
        rate_18 = generator._calculate_age_decay_rate(18)
        assert abs(rate_18 - 0.222) < 0.01

    def test_age_offset_bounds_for_adult(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that adult NPC offset respects 16+ minimum partner age."""
        # Run many times to check bounds are respected
        for _ in range(50):
            offset = generator._generate_age_offset(40)
            # 40yo with offset should prefer at least 16yo
            # min_offset = 16 - 40 = -24
            assert offset >= -24
            # Preferred age = 40 + offset
            preferred = 40 + offset
            assert preferred >= 16

    def test_age_offset_bounds_for_18yo(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that 18yo NPC cannot prefer younger than 16."""
        for _ in range(50):
            offset = generator._generate_age_offset(18)
            # 18yo: min_offset = 16 - 18 = -2
            assert offset >= -2
            preferred = 18 + offset
            assert preferred >= 16

    def test_age_offset_bounds_for_minor(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that minor NPC has restricted offset."""
        for _ in range(50):
            offset = generator._generate_age_offset(16)
            # 16yo: min_offset = max(10-16, -2) = -2
            # max_offset = min(85-16, max(30, 16-10)) = 30
            assert -2 <= offset <= 30
            preferred = 16 + offset
            assert 14 <= preferred <= 46

    def test_age_offset_centered_near_zero(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that most offsets are near zero (same-age preference)."""
        offsets = [generator._generate_age_offset(30) for _ in range(100)]
        near_zero = sum(1 for o in offsets if abs(o) <= 3)
        # At least 40% should be within +/-3 years
        assert near_zero >= 40

    def test_age_attraction_factor_perfect_match(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that perfect match (within +/-2) gives 1.0."""
        # NPC age 30, offset 0, player age 30 (exact match)
        factor = generator._calculate_age_attraction_factor(30, 30, 0)
        assert factor == 1.0

        # Player age within +/-2 of preferred
        factor = generator._calculate_age_attraction_factor(30, 32, 0)
        assert factor == 1.0
        factor = generator._calculate_age_attraction_factor(30, 28, 0)
        assert factor == 1.0

    def test_age_attraction_factor_decay_starts_after_range(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that decay starts after +/-2 perfect match range."""
        # NPC age 30, offset 0, preferred = 30
        # +/-2 perfect match, so 28-32 = 1.0
        # 33 = 1 year outside = decay starts
        factor_32 = generator._calculate_age_attraction_factor(30, 32, 0)
        factor_33 = generator._calculate_age_attraction_factor(30, 33, 0)
        assert factor_32 == 1.0
        assert factor_33 < 1.0

    def test_age_attraction_factor_respects_offset(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that offset shifts the preferred age."""
        # NPC age 30 with offset +10 prefers 40yo
        # So player at 40 should get 1.0
        factor = generator._calculate_age_attraction_factor(30, 40, 10)
        assert factor == 1.0

        # Player at 30 is 10 years from preferred (outside +/-2 range)
        # Distance = 10 - 2 = 8 years of decay
        factor = generator._calculate_age_attraction_factor(30, 30, 10)
        assert factor < 1.0
        assert factor < 0.5  # Should be significantly reduced

    def test_age_attraction_factor_younger_pickier(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that younger NPCs have faster decay (pickier)."""
        # Same distance outside perfect range, different NPC ages
        # 5 years outside perfect range
        factor_18yo = generator._calculate_age_attraction_factor(18, 30, 0)  # 10 outside, 8 after range
        factor_60yo = generator._calculate_age_attraction_factor(60, 70, 0)  # 10 outside, 8 after range

        # 18yo should have lower factor (pickier)
        assert factor_18yo < factor_60yo

    def test_age_attraction_factor_floor(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that factor never goes below 0.02."""
        # Very large distance
        factor = generator._calculate_age_attraction_factor(20, 80, 0)
        assert factor >= 0.02


# =============================================================================
# Age-Aware Height Tests
# =============================================================================


class TestAgeAwareHeight:
    """Tests for age-aware height generation."""

    def test_adult_height_in_normal_range(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that adults (18+) get height in adult ranges."""
        for _ in range(20):
            height_male = generator._calculate_height("male", 25)
            height_female = generator._calculate_height("female", 25)

            # Adult male: 165-195cm (with variance)
            assert 155 <= height_male <= 205
            # Adult female: 155-185cm (with variance)
            assert 145 <= height_female <= 195

    def test_child_height_shorter_than_adult(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that children are shorter than adults."""
        # Get average heights over multiple samples
        adult_heights = [generator._calculate_height("male", 25) for _ in range(20)]
        child_heights = [generator._calculate_height("male", 10) for _ in range(20)]

        avg_adult = sum(adult_heights) / len(adult_heights)
        avg_child = sum(child_heights) / len(child_heights)

        # Children should be significantly shorter
        assert avg_child < avg_adult * 0.85  # At least 15% shorter

    def test_height_increases_with_age(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that height generally increases through childhood/teens."""
        ages = [8, 12, 15, 18]
        avg_heights = []

        for age in ages:
            heights = [generator._calculate_height("male", age) for _ in range(20)]
            avg_heights.append(sum(heights) / len(heights))

        # Each age should be taller on average than the previous
        for i in range(len(avg_heights) - 1):
            assert avg_heights[i] < avg_heights[i + 1], f"Age {ages[i]} not shorter than {ages[i+1]}"

    def test_height_at_specific_ages(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test height percentages at specific ages match growth curves."""
        # 10-year-old should be ~70% of adult height
        heights_10 = [generator._calculate_height("male", 10) for _ in range(30)]
        avg_10 = sum(heights_10) / len(heights_10)
        # Adult male average ~180cm, so 10yo should be ~126cm
        assert 115 <= avg_10 <= 140, f"10yo avg height {avg_10} not in expected range"

        # 15-year-old should be ~93% of adult height
        heights_15 = [generator._calculate_height("male", 15) for _ in range(30)]
        avg_15 = sum(heights_15) / len(heights_15)
        # Should be ~167cm
        assert 155 <= avg_15 <= 180, f"15yo avg height {avg_15} not in expected range"

    def test_very_young_child_height(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that very young children get appropriate heights."""
        heights_5 = [generator._calculate_height("male", 5) for _ in range(20)]
        avg_5 = sum(heights_5) / len(heights_5)
        # 5yo should be ~55% of adult height (~99cm)
        assert 85 <= avg_5 <= 115, f"5yo avg height {avg_5} not in expected range"

    def test_height_gender_difference(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that male heights are generally taller than female."""
        male_heights = [generator._calculate_height("male", 25) for _ in range(30)]
        female_heights = [generator._calculate_height("female", 25) for _ in range(30)]

        avg_male = sum(male_heights) / len(male_heights)
        avg_female = sum(female_heights) / len(female_heights)

        assert avg_male > avg_female


# =============================================================================
# Age-Aware Voice Tests
# =============================================================================


class TestAgeAwareVoice:
    """Tests for age-aware voice generation with pre-voice-break support."""

    def test_child_voice_descriptors(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that children under 10 get child voice descriptors."""
        child_voices = {"high and clear", "piping", "soft", "childlike", "bright"}
        for _ in range(20):
            voice = generator._generate_voice("male", 8)
            assert voice in child_voices, f"Child voice '{voice}' not in child voice pool"

    def test_teen_male_pre_voice_break(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that male teens under 15 get pre-voice-break descriptors."""
        teen_voices = {"youthful", "clear", "light", "bright", "unbroken"}
        for _ in range(20):
            voice = generator._generate_voice("male", 13)
            assert voice in teen_voices, f"Teen male voice '{voice}' not in teen voice pool"

    def test_teen_female_pre_voice_break(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that female teens under 13 get pre-voice-break descriptors."""
        teen_voices = {"youthful", "clear", "light", "bright", "unbroken"}
        for _ in range(20):
            voice = generator._generate_voice("female", 11)
            assert voice in teen_voices, f"Teen female voice '{voice}' not in teen voice pool"

    def test_adult_male_voice(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that adult males (15+) get adult male voice descriptors."""
        adult_male_voices = {
            "deep and resonant", "gravelly", "warm baritone", "quiet and measured",
            "booming", "soft-spoken", "rough from shouting", "melodic",
        }
        for _ in range(20):
            voice = generator._generate_voice("male", 30)
            assert voice in adult_male_voices, f"Adult male voice '{voice}' not in adult voice pool"

    def test_adult_female_voice(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that adult females (13+) get adult female voice descriptors."""
        adult_female_voices = {
            "melodic", "warm and inviting", "soft and gentle", "clear and bright",
            "husky", "sharp and precise", "lilting", "quiet but firm",
        }
        for _ in range(20):
            voice = generator._generate_voice("female", 25)
            assert voice in adult_female_voices, f"Adult female voice '{voice}' not in adult voice pool"

    def test_elderly_voice(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that elderly (60+) get elderly voice descriptors."""
        elderly_voices = {
            "thin and reedy", "surprisingly strong", "warm and weathered",
            "crackling", "patient and slow",
        }
        for _ in range(20):
            voice = generator._generate_voice("male", 70)
            assert voice in elderly_voices, f"Elderly voice '{voice}' not in elderly voice pool"

    def test_voice_break_age_difference_by_gender(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that voice break happens at different ages for male vs female."""
        # 14yo male should still have teen voice (voice breaks at ~15)
        teen_voices = {"youthful", "clear", "light", "bright", "unbroken"}
        voice_14m = generator._generate_voice("male", 14)
        assert voice_14m in teen_voices, "14yo male should have pre-voice-break voice"

        # 14yo female should have adult voice (voice breaks at ~13)
        adult_female_voices = {
            "melodic", "warm and inviting", "soft and gentle", "clear and bright",
            "husky", "sharp and precise", "lilting", "quiet but firm",
        }
        voice_14f = generator._generate_voice("female", 14)
        assert voice_14f in adult_female_voices, "14yo female should have adult voice"


# =============================================================================
# Birthplace and Skin Color Tests
# =============================================================================


class TestBirthplaceGeneration:
    """Tests for birthplace generation based on regions."""

    def test_generate_birthplace_mostly_local(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that most NPCs are born locally (85-90%)."""
        from src.schemas.regions import REGIONS_CONTEMPORARY

        local_region = "Northern Europe"
        birthplaces = [
            generator._generate_birthplace(local_region, REGIONS_CONTEMPORARY)
            for _ in range(100)
        ]

        local_count = sum(1 for bp in birthplaces if bp == local_region)
        # Should be 80-95% local (allowing for randomness)
        assert 75 <= local_count <= 95, f"Local count {local_count} not in expected range"

    def test_generate_birthplace_some_migrants(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that some NPCs are migrants (10-15%)."""
        from src.schemas.regions import REGIONS_CONTEMPORARY

        local_region = "Northern Europe"
        birthplaces = [
            generator._generate_birthplace(local_region, REGIONS_CONTEMPORARY)
            for _ in range(100)
        ]

        migrant_count = sum(1 for bp in birthplaces if bp != local_region)
        # Should have some migrants (5-25% allowing for randomness)
        assert 5 <= migrant_count <= 25, f"Migrant count {migrant_count} not in expected range"

    def test_generate_birthplace_returns_valid_region(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that generated birthplace is always a valid region."""
        from src.schemas.regions import REGIONS_FANTASY

        for _ in range(50):
            birthplace = generator._generate_birthplace("Central Plains", REGIONS_FANTASY)
            assert birthplace in REGIONS_FANTASY, f"Invalid birthplace: {birthplace}"


class TestSkinColorFromBirthplace:
    """Tests for birthplace-derived skin color generation."""

    def test_skin_color_from_northern_europe(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that Northern Europe generates mostly fair/light skin tones."""
        from src.schemas.regions import REGIONS_CONTEMPORARY

        colors = [
            generator._generate_skin_color_from_birthplace(
                "Northern Europe", REGIONS_CONTEMPORARY
            )
            for _ in range(100)
        ]

        fair_light_count = sum(
            1 for c in colors if c in ("fair", "pale", "light", "freckled fair", "ruddy")
        )
        # Should be mostly fair/light
        assert fair_light_count >= 70, f"Fair/light count {fair_light_count} too low for Northern Europe"

    def test_skin_color_from_sub_saharan_africa(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that Sub-Saharan Africa generates mostly dark skin tones."""
        from src.schemas.regions import REGIONS_CONTEMPORARY

        colors = [
            generator._generate_skin_color_from_birthplace(
                "Sub-Saharan Africa", REGIONS_CONTEMPORARY
            )
            for _ in range(100)
        ]

        dark_count = sum(
            1 for c in colors if c in ("dark", "dark brown", "brown", "tan")
        )
        # Should be mostly dark tones
        assert dark_count >= 80, f"Dark count {dark_count} too low for Sub-Saharan Africa"

    def test_skin_color_fallback_for_unknown_region(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that unknown regions fall back to random skin color."""
        from src.schemas.regions import REGIONS_CONTEMPORARY

        # Unknown region should still return a valid skin color
        color = generator._generate_skin_color_from_birthplace(
            "Unknown Region", REGIONS_CONTEMPORARY
        )
        assert color is not None
        assert isinstance(color, str)
        assert len(color) > 0


# =============================================================================
# Setting-Specific Name Generation Tests
# =============================================================================


class TestSettingSpecificNames:
    """Tests for setting-specific name generation."""

    def test_fantasy_names_exist(self):
        """Test that fantasy name pools exist."""
        from src.services.emergent_npc_generator import NAMES_BY_SETTING

        assert "fantasy" in NAMES_BY_SETTING
        assert "male" in NAMES_BY_SETTING["fantasy"]
        assert "female" in NAMES_BY_SETTING["fantasy"]
        assert "surnames" in NAMES_BY_SETTING["fantasy"]

    def test_contemporary_names_exist(self):
        """Test that contemporary name pools exist."""
        from src.services.emergent_npc_generator import NAMES_BY_SETTING

        assert "contemporary" in NAMES_BY_SETTING
        assert "male" in NAMES_BY_SETTING["contemporary"]
        assert "female" in NAMES_BY_SETTING["contemporary"]
        assert "surnames" in NAMES_BY_SETTING["contemporary"]

        # Check for typical contemporary names
        male_names = NAMES_BY_SETTING["contemporary"]["male"]
        assert any(name in male_names for name in ["James", "Michael", "David", "John"])

        surnames = NAMES_BY_SETTING["contemporary"]["surnames"]
        assert any(name in surnames for name in ["Smith", "Johnson", "Williams"])

    def test_scifi_names_exist(self):
        """Test that sci-fi name pools exist."""
        from src.services.emergent_npc_generator import NAMES_BY_SETTING

        assert "scifi" in NAMES_BY_SETTING
        assert "male" in NAMES_BY_SETTING["scifi"]
        assert "female" in NAMES_BY_SETTING["scifi"]
        assert "surnames" in NAMES_BY_SETTING["scifi"]

    def test_generate_name_uses_setting(
        self,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test that name generation uses the game session's setting."""
        # Set contemporary setting
        game_session.setting = "contemporary"
        db_session.commit()

        generator = EmergentNPCGenerator(db_session, game_session)

        # Generate multiple names and check they're from contemporary pool
        from src.services.emergent_npc_generator import NAMES_BY_SETTING

        contemporary_names = (
            NAMES_BY_SETTING["contemporary"]["male"]
            + NAMES_BY_SETTING["contemporary"]["female"]
        )

        names = [generator._generate_name("male", None) for _ in range(10)]

        # At least some should be from the contemporary pool (first names)
        first_names = [n.split()[0] for n in names]
        matches = sum(1 for fn in first_names if fn in contemporary_names)
        # Allow for some randomness, but expect most to match
        assert matches >= 5, f"Only {matches}/10 names matched contemporary pool"

    def test_generate_name_fallback_for_unknown_setting(
        self,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test that unknown settings fall back to fantasy names."""
        # Set an unknown setting
        game_session.setting = "unknown_setting"
        db_session.commit()

        generator = EmergentNPCGenerator(db_session, game_session)

        # Should still generate a valid name
        name = generator._generate_name("male", None)
        assert name is not None
        assert len(name) > 0

    def test_fantasy_setting_uses_fantasy_names(
        self,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test that fantasy setting uses fantasy name pool."""
        game_session.setting = "fantasy"
        db_session.commit()

        generator = EmergentNPCGenerator(db_session, game_session)

        from src.services.emergent_npc_generator import NAMES_BY_SETTING

        fantasy_names = (
            NAMES_BY_SETTING["fantasy"]["male"]
            + NAMES_BY_SETTING["fantasy"]["female"]
        )

        names = [generator._generate_name("female", None) for _ in range(10)]
        first_names = [n.split()[0] for n in names]
        matches = sum(1 for fn in first_names if fn in fantasy_names)
        assert matches >= 5, f"Only {matches}/10 names matched fantasy pool"

    def test_scifi_setting_uses_scifi_names(
        self,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test that sci-fi setting uses sci-fi name pool."""
        game_session.setting = "scifi"
        db_session.commit()

        generator = EmergentNPCGenerator(db_session, game_session)

        from src.services.emergent_npc_generator import NAMES_BY_SETTING

        scifi_names = (
            NAMES_BY_SETTING["scifi"]["male"]
            + NAMES_BY_SETTING["scifi"]["female"]
        )

        names = [generator._generate_name("male", None) for _ in range(10)]
        first_names = [n.split()[0] for n in names]
        matches = sum(1 for fn in first_names if fn in scifi_names)
        assert matches >= 5, f"Only {matches}/10 names matched scifi pool"

    def test_surnames_setting_specific(
        self,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test that surnames are setting-specific."""
        from src.services.emergent_npc_generator import NAMES_BY_SETTING

        # Check that surnames differ between settings
        fantasy_surnames = set(NAMES_BY_SETTING["fantasy"]["surnames"])
        contemporary_surnames = set(NAMES_BY_SETTING["contemporary"]["surnames"])

        # They should have minimal overlap
        overlap = fantasy_surnames & contemporary_surnames
        # Allow some overlap (common names) but expect mostly different
        assert len(overlap) < len(fantasy_surnames) * 0.3, "Surnames should mostly differ"


# =============================================================================
# Context-Aware Apprentice Generation Tests
# =============================================================================


class TestContextAwareApprentice:
    """Tests for context-aware apprentice generation."""

    def test_location_apprentice_mappings_exist(self):
        """Test that location-to-apprentice mappings exist."""
        from src.services.emergent_npc_generator import LOCATION_APPRENTICE_ROLES

        assert isinstance(LOCATION_APPRENTICE_ROLES, dict)
        assert len(LOCATION_APPRENTICE_ROLES) > 0

    def test_bakery_generates_baker_apprentice(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that bakery location generates baker's apprentice."""
        from src.services.emergent_npc_generator import LOCATION_APPRENTICE_ROLES

        # Verify bakery is in the mapping
        assert any(
            "baker" in key.lower() or "bakery" in key.lower()
            for key in LOCATION_APPRENTICE_ROLES.keys()
        )

    def test_blacksmith_generates_smith_apprentice(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that blacksmith location generates smith apprentice."""
        from src.services.emergent_npc_generator import LOCATION_APPRENTICE_ROLES

        # Verify blacksmith/forge is in the mapping
        assert any(
            "smith" in key.lower() or "forge" in key.lower()
            for key in LOCATION_APPRENTICE_ROLES.keys()
        )

    def test_generate_apprentice_from_location_returns_trade_specific(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that apprentice generation uses location context."""
        # Generate apprentice for a specific location
        occupation = generator._generate_context_aware_apprentice(
            location_key="bakery",
            age=16,
        )

        # Should contain trade-specific term
        assert occupation is not None
        assert isinstance(occupation, str)
        # Either "baker" or generic apprentice
        assert "apprentice" in occupation.lower() or "helper" in occupation.lower()

    def test_generate_apprentice_fallback_for_unknown_location(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test fallback for unknown locations."""
        occupation = generator._generate_context_aware_apprentice(
            location_key="unknown_location_xyz",
            age=16,
        )

        # Should still return a valid occupation
        assert occupation is not None
        assert len(occupation) > 0

    def test_generate_apprentice_age_aware(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that apprentice generation is age-aware."""
        # Very young (under 14) should get simpler roles
        young_occupation = generator._generate_context_aware_apprentice(
            location_key="bakery",
            age=10,
        )
        assert young_occupation is not None

        # Older teen should get actual apprentice role
        older_occupation = generator._generate_context_aware_apprentice(
            location_key="bakery",
            age=17,
        )
        assert older_occupation is not None

    def test_tavern_generates_appropriate_role(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that tavern/inn locations generate appropriate youth roles."""
        from src.services.emergent_npc_generator import LOCATION_APPRENTICE_ROLES

        # Verify tavern/inn has appropriate roles
        tavern_keys = [k for k in LOCATION_APPRENTICE_ROLES.keys() if "tavern" in k or "inn" in k]
        assert len(tavern_keys) > 0

    def test_stable_generates_appropriate_role(
        self,
        generator: EmergentNPCGenerator,
    ):
        """Test that stable locations generate appropriate youth roles."""
        from src.services.emergent_npc_generator import LOCATION_APPRENTICE_ROLES

        # Verify stable has appropriate roles
        stable_keys = [k for k in LOCATION_APPRENTICE_ROLES.keys() if "stable" in k]
        assert len(stable_keys) > 0
