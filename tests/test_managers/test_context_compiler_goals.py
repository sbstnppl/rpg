"""Tests for ContextCompiler goal and motivation features."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.character_state import CharacterNeeds
from src.database.models.entities import Entity, NPCExtension
from src.database.models.enums import EntityType, GoalPriority, GoalStatus, GoalType
from src.database.models.goals import NPCGoal
from src.database.models.session import GameSession
from src.database.models.world import Location, TimeState
from src.managers.context_compiler import ContextCompiler, SceneContext


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def compiler(db_session: Session, game_session: GameSession) -> ContextCompiler:
    """Create ContextCompiler instance."""
    return ContextCompiler(db_session, game_session)


@pytest.fixture
def time_state(db_session: Session, game_session: GameSession) -> TimeState:
    """Create TimeState for the session."""
    time = TimeState(
        session_id=game_session.id,
        current_day=1,
        current_time="12:00",
        day_of_week="monday",
        weather="clear",
    )
    db_session.add(time)
    db_session.flush()
    return time


@pytest.fixture
def location(db_session: Session, game_session: GameSession) -> Location:
    """Create a test location."""
    loc = Location(
        session_id=game_session.id,
        location_key="tavern",
        display_name="The Rusty Tankard",
        description="A cozy tavern",
    )
    db_session.add(loc)
    db_session.flush()
    return loc


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
def npc_with_goal(
    db_session: Session,
    game_session: GameSession,
    location: Location,
) -> tuple[Entity, NPCGoal]:
    """Create NPC with an active goal at the test location."""
    entity = Entity(
        session_id=game_session.id,
        entity_key="merchant_bob",
        display_name="Bob the Merchant",
        entity_type=EntityType.NPC,
        is_alive=True,
        is_active=True,
    )
    db_session.add(entity)
    db_session.flush()

    extension = NPCExtension(
        entity_id=entity.id,
        job="merchant",
        current_activity="manning the stall",
        current_location=location.location_key,
    )
    db_session.add(extension)

    needs = CharacterNeeds(
        session_id=game_session.id,
        entity_id=entity.id,
        hunger=50,
        thirst=50,
        stamina=50,
        social_connection=50,
        intimacy=50,
        morale=50,
    )
    db_session.add(needs)

    goal = NPCGoal(
        session_id=game_session.id,
        entity_id=entity.id,
        goal_key="bob_find_supplies",
        goal_type=GoalType.ACQUIRE,
        target="trade_goods",
        description="Restock the shop with trade goods",
        motivation=["business_need", "duty"],
        priority=GoalPriority.HIGH,
        strategies=["visit market", "negotiate prices", "transport goods"],
        current_step=0,
        success_condition="shop restocked",
        status=GoalStatus.ACTIVE,
        created_at_turn=1,
    )
    db_session.add(goal)
    db_session.flush()
    return entity, goal


@pytest.fixture
def npc_with_urgent_need(
    db_session: Session,
    game_session: GameSession,
    location: Location,
) -> Entity:
    """Create NPC with urgent hunger need at the test location."""
    entity = Entity(
        session_id=game_session.id,
        entity_key="hungry_guard",
        display_name="Hungry Guard",
        entity_type=EntityType.NPC,
        is_alive=True,
        is_active=True,
    )
    db_session.add(entity)
    db_session.flush()

    extension = NPCExtension(
        entity_id=entity.id,
        job="guard",
        current_location=location.location_key,
    )
    db_session.add(extension)

    # Low hunger value = urgent hunger (urgency = 100 - value)
    needs = CharacterNeeds(
        session_id=game_session.id,
        entity_id=entity.id,
        hunger=20,  # 80% urgency
        thirst=50,
        stamina=50,
        social_connection=50,
        intimacy=50,
        morale=50,
    )
    db_session.add(needs)
    db_session.flush()
    return entity


# =============================================================================
# NPC Location Reason Tests
# =============================================================================


class TestNPCLocationReason:
    """Tests for _get_npc_location_reason method."""

    def test_shows_goal_pursuit_for_high_priority_goal(
        self,
        compiler: ContextCompiler,
        npc_with_goal: tuple[Entity, NPCGoal],
    ):
        """Test that high priority goals show as location reason."""
        npc, goal = npc_with_goal
        reason = compiler._get_npc_location_reason(npc)

        assert "Goal pursuit" in reason
        assert goal.description in reason

    def test_shows_scheduled_for_npc_with_job(
        self,
        compiler: ContextCompiler,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test that NPCs without goals show schedule/job."""
        entity = Entity(
            session_id=game_session.id,
            entity_key="baker_jane",
            display_name="Jane the Baker",
            entity_type=EntityType.NPC,
            is_alive=True,
            is_active=True,
        )
        db_session.add(entity)
        db_session.flush()

        extension = NPCExtension(
            entity_id=entity.id,
            job="baker",
        )
        db_session.add(extension)
        db_session.flush()

        reason = compiler._get_npc_location_reason(entity)

        assert "Scheduled" in reason
        assert "baker" in reason


# =============================================================================
# NPC Active Goals Tests
# =============================================================================


class TestNPCActiveGoals:
    """Tests for _get_npc_active_goals method."""

    def test_returns_active_goals(
        self,
        compiler: ContextCompiler,
        npc_with_goal: tuple[Entity, NPCGoal],
    ):
        """Test that active goals are returned."""
        npc, goal = npc_with_goal
        goals = compiler._get_npc_active_goals(npc.id)

        assert len(goals) == 1
        assert goal.description in goals[0]
        assert "[high]" in goals[0]

    def test_returns_empty_for_no_goals(
        self,
        compiler: ContextCompiler,
        player_entity: Entity,
    ):
        """Test that empty list returned for entity without goals."""
        goals = compiler._get_npc_active_goals(player_entity.id)
        assert goals == []

    def test_includes_motivation(
        self,
        compiler: ContextCompiler,
        npc_with_goal: tuple[Entity, NPCGoal],
    ):
        """Test that motivation is included in goal description."""
        npc, goal = npc_with_goal
        goals = compiler._get_npc_active_goals(npc.id)

        assert "motivated by" in goals[0]
        assert "business_need" in goals[0]


# =============================================================================
# Urgent Needs Tests
# =============================================================================


class TestUrgentNeeds:
    """Tests for _get_urgent_needs method."""

    def test_returns_urgent_needs(
        self,
        compiler: ContextCompiler,
        npc_with_urgent_need: Entity,
    ):
        """Test that urgent needs are returned."""
        urgent = compiler._get_urgent_needs(npc_with_urgent_need.id)

        assert "hunger" in urgent
        assert "80%" in urgent

    def test_returns_empty_for_satisfied_needs(
        self,
        compiler: ContextCompiler,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test that empty string returned when needs are satisfied."""
        entity = Entity(
            session_id=game_session.id,
            entity_key="satisfied_npc",
            display_name="Happy NPC",
            entity_type=EntityType.NPC,
        )
        db_session.add(entity)
        db_session.flush()

        needs = CharacterNeeds(
            session_id=game_session.id,
            entity_id=entity.id,
            hunger=80,  # Only 20% urgency
            thirst=80,
            stamina=80,
            social_connection=80,
            intimacy=80,
            morale=80,
        )
        db_session.add(needs)
        db_session.flush()

        urgent = compiler._get_urgent_needs(entity.id)
        assert urgent == ""


# =============================================================================
# Entity Registry Tests
# =============================================================================


class TestEntityRegistry:
    """Tests for _get_entity_registry_context method."""

    def test_includes_player(
        self,
        compiler: ContextCompiler,
        player_entity: Entity,
        location: Location,
    ):
        """Test that player is included in registry."""
        registry = compiler._get_entity_registry_context(location.location_key, player_entity.id)

        assert "Player" in registry
        assert player_entity.entity_key in registry
        assert player_entity.display_name in registry

    def test_includes_npcs_with_goal_hints(
        self,
        compiler: ContextCompiler,
        player_entity: Entity,
        npc_with_goal: tuple[Entity, NPCGoal],
        location: Location,
    ):
        """Test that NPCs are included with goal hints."""
        npc, goal = npc_with_goal
        registry = compiler._get_entity_registry_context(location.location_key, player_entity.id)

        assert "NPCs at Location" in registry
        assert npc.entity_key in registry
        assert "HERE FOR:" in registry
        assert goal.description in registry


# =============================================================================
# Full Context Integration Tests
# =============================================================================


class TestFullContextWithGoals:
    """Integration tests for full context with goals."""

    def test_compile_scene_includes_entity_registry(
        self,
        compiler: ContextCompiler,
        player_entity: Entity,
        location: Location,
        time_state: TimeState,
    ):
        """Test that compile_scene includes entity registry."""
        context = compiler.compile_scene(
            player_id=player_entity.id,
            location_key=location.location_key,
        )

        assert context.entity_registry_context != ""
        assert "Entity Registry" in context.entity_registry_context

    def test_npc_context_includes_goals(
        self,
        compiler: ContextCompiler,
        player_entity: Entity,
        npc_with_goal: tuple[Entity, NPCGoal],
        location: Location,
        time_state: TimeState,
    ):
        """Test that NPC context includes goal information."""
        npc, goal = npc_with_goal
        context = compiler.compile_scene(
            player_id=player_entity.id,
            location_key=location.location_key,
        )

        # Check NPC section includes goals
        assert "Active Goals" in context.npcs_context
        assert goal.description in context.npcs_context

    def test_npc_context_includes_location_reason(
        self,
        compiler: ContextCompiler,
        player_entity: Entity,
        npc_with_goal: tuple[Entity, NPCGoal],
        location: Location,
        time_state: TimeState,
    ):
        """Test that NPC context includes location reason."""
        context = compiler.compile_scene(
            player_id=player_entity.id,
            location_key=location.location_key,
        )

        assert "Location reason" in context.npcs_context

    def test_to_prompt_includes_entity_registry(
        self,
        compiler: ContextCompiler,
        player_entity: Entity,
        location: Location,
        time_state: TimeState,
    ):
        """Test that to_prompt includes entity registry."""
        context = compiler.compile_scene(
            player_id=player_entity.id,
            location_key=location.location_key,
        )

        prompt = context.to_prompt()
        assert "Entity Registry" in prompt

    def test_npc_context_includes_urgent_needs(
        self,
        compiler: ContextCompiler,
        player_entity: Entity,
        npc_with_urgent_need: Entity,
        location: Location,
        time_state: TimeState,
    ):
        """Test that NPC context includes urgent needs."""
        context = compiler.compile_scene(
            player_id=player_entity.id,
            location_key=location.location_key,
        )

        assert "Urgent needs" in context.npcs_context
        assert "hunger" in context.npcs_context
