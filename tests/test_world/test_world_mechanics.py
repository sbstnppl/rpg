"""Tests for WorldMechanics - Scene-First Architecture Phase 2.

These tests verify:
- Scheduled NPC presence at locations
- Event-driven NPC placement
- Story-driven NPC placement
- Constraint enforcement (social and physical limits)
- New element introduction with validation
- LLM integration for world simulation
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.orm import Session

from src.database.models.entities import Entity, NPCExtension
from src.database.models.enums import DayOfWeek, EntityType
from src.database.models.relationships import Relationship
from src.database.models.session import GameSession
from src.database.models.world import Schedule, TimeState
from src.world.constraints import RealisticConstraintChecker
from src.world.schemas import (
    ConstraintResult,
    NPCPlacement,
    NPCSpec,
    PresenceReason,
    SocialLimits,
    WorldUpdate,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def time_state(db_session: Session, game_session: GameSession) -> TimeState:
    """Create a time state for testing."""
    time = TimeState(
        session_id=game_session.id,
        current_day=1,
        current_time="10:00",
        day_of_week="monday",
    )
    db_session.add(time)
    db_session.flush()
    return time


@pytest.fixture
def player_entity(db_session: Session, game_session: GameSession) -> Entity:
    """Create a player entity."""
    entity = Entity(
        session_id=game_session.id,
        entity_key="player",
        entity_type=EntityType.PLAYER,
        display_name="Hero",
    )
    db_session.add(entity)
    db_session.flush()
    return entity


@pytest.fixture
def npc_entity(db_session: Session, game_session: GameSession) -> Entity:
    """Create an NPC entity."""
    entity = Entity(
        session_id=game_session.id,
        entity_key="marcus_001",
        entity_type=EntityType.NPC,
        display_name="Marcus",
        gender="male",
    )
    db_session.add(entity)
    db_session.flush()

    # Add NPC extension with location info
    ext = NPCExtension(
        entity_id=entity.id,
        current_location="market",
    )
    db_session.add(ext)
    db_session.flush()

    return entity


@pytest.fixture
def scheduled_npc(
    db_session: Session,
    game_session: GameSession,
    npc_entity: Entity,
) -> Schedule:
    """Create a schedule entry for the NPC."""
    schedule = Schedule(
        entity_id=npc_entity.id,
        day_pattern=DayOfWeek.WEEKDAY,
        start_time="09:00",
        end_time="17:00",
        activity="selling goods",
        location_key="market",
        priority=0,
    )
    db_session.add(schedule)
    db_session.flush()
    return schedule


@pytest.fixture
def mock_llm_provider() -> MagicMock:
    """Create a mock LLM provider."""
    provider = MagicMock()
    provider.complete_structured = AsyncMock()
    return provider


# =============================================================================
# WorldMechanics Class Tests
# =============================================================================


class TestWorldMechanicsInit:
    """Tests for WorldMechanics initialization."""

    def test_init_with_db_and_session(
        self,
        db_session: Session,
        game_session: GameSession,
    ) -> None:
        """WorldMechanics initializes with db and game_session."""
        from src.world.world_mechanics import WorldMechanics

        wm = WorldMechanics(db_session, game_session)

        assert wm.db is db_session
        assert wm.game_session is game_session
        assert wm.session_id == game_session.id

    def test_init_with_llm_provider(
        self,
        db_session: Session,
        game_session: GameSession,
        mock_llm_provider: MagicMock,
    ) -> None:
        """WorldMechanics accepts optional LLM provider."""
        from src.world.world_mechanics import WorldMechanics

        wm = WorldMechanics(db_session, game_session, llm_provider=mock_llm_provider)

        assert wm.llm_provider is mock_llm_provider

    def test_init_creates_default_constraint_checker(
        self,
        db_session: Session,
        game_session: GameSession,
    ) -> None:
        """WorldMechanics creates a constraint checker by default."""
        from src.world.world_mechanics import WorldMechanics

        wm = WorldMechanics(db_session, game_session)

        assert wm.constraint_checker is not None
        assert isinstance(wm.constraint_checker, RealisticConstraintChecker)


# =============================================================================
# Scheduled NPC Tests
# =============================================================================


class TestScheduledNPCs:
    """Tests for NPC presence based on schedules."""

    def test_get_scheduled_npcs_returns_empty_for_no_schedules(
        self,
        db_session: Session,
        game_session: GameSession,
        time_state: TimeState,
    ) -> None:
        """Returns empty list when no NPCs are scheduled."""
        from src.world.world_mechanics import WorldMechanics

        wm = WorldMechanics(db_session, game_session)

        result = wm.get_scheduled_npcs("empty_location")

        assert result == []

    def test_get_scheduled_npcs_returns_npc_at_location(
        self,
        db_session: Session,
        game_session: GameSession,
        time_state: TimeState,
        npc_entity: Entity,
        scheduled_npc: Schedule,
    ) -> None:
        """Returns NPCs scheduled at the specified location."""
        from src.world.world_mechanics import WorldMechanics

        wm = WorldMechanics(db_session, game_session)

        result = wm.get_scheduled_npcs("market")

        assert len(result) == 1
        assert result[0].entity_key == "marcus_001"
        assert result[0].presence_reason == PresenceReason.SCHEDULE

    def test_get_scheduled_npcs_respects_time_range(
        self,
        db_session: Session,
        game_session: GameSession,
        npc_entity: Entity,
        scheduled_npc: Schedule,
    ) -> None:
        """Only returns NPCs when current time is in schedule range."""
        from src.world.world_mechanics import WorldMechanics

        # Set time outside schedule range (after 17:00)
        time = TimeState(
            session_id=game_session.id,
            current_day=1,
            current_time="20:00",
            day_of_week="monday",
        )
        db_session.add(time)
        db_session.flush()

        wm = WorldMechanics(db_session, game_session)

        result = wm.get_scheduled_npcs("market")

        assert result == []

    def test_get_scheduled_npcs_respects_day_pattern(
        self,
        db_session: Session,
        game_session: GameSession,
        npc_entity: Entity,
        scheduled_npc: Schedule,
    ) -> None:
        """Only returns NPCs when day matches schedule pattern."""
        from src.world.world_mechanics import WorldMechanics

        # Set day to weekend (schedule is WEEKDAY only)
        time = TimeState(
            session_id=game_session.id,
            current_day=1,
            current_time="10:00",
            day_of_week="saturday",
        )
        db_session.add(time)
        db_session.flush()

        wm = WorldMechanics(db_session, game_session)

        result = wm.get_scheduled_npcs("market")

        assert result == []

    def test_get_scheduled_npcs_includes_activity(
        self,
        db_session: Session,
        game_session: GameSession,
        time_state: TimeState,
        npc_entity: Entity,
        scheduled_npc: Schedule,
    ) -> None:
        """Returned placements include the scheduled activity."""
        from src.world.world_mechanics import WorldMechanics

        wm = WorldMechanics(db_session, game_session)

        result = wm.get_scheduled_npcs("market")

        assert result[0].activity == "selling goods"


# =============================================================================
# NPCs At Location Tests
# =============================================================================


class TestNPCsAtLocation:
    """Tests for determining all NPCs at a location."""

    def test_get_npcs_at_location_includes_scheduled(
        self,
        db_session: Session,
        game_session: GameSession,
        time_state: TimeState,
        npc_entity: Entity,
        scheduled_npc: Schedule,
    ) -> None:
        """NPCs at location includes those from schedules."""
        from src.world.world_mechanics import WorldMechanics

        wm = WorldMechanics(db_session, game_session)

        result = wm.get_npcs_at_location("market")

        assert len(result) == 1
        assert result[0].entity_key == "marcus_001"

    def test_get_npcs_at_location_includes_residents(
        self,
        db_session: Session,
        game_session: GameSession,
        time_state: TimeState,
    ) -> None:
        """NPCs at location includes those who live there."""
        from src.world.world_mechanics import WorldMechanics

        # Create an NPC who lives at the location
        resident = Entity(
            session_id=game_session.id,
            entity_key="innkeeper_001",
            entity_type=EntityType.NPC,
            display_name="Tom",
            gender="male",
        )
        db_session.add(resident)
        db_session.flush()

        # Add NPC extension with home location
        ext = NPCExtension(
            entity_id=resident.id,
            home_location="tavern",
            current_location="tavern",
        )
        db_session.add(ext)
        db_session.flush()

        wm = WorldMechanics(db_session, game_session)

        result = wm.get_npcs_at_location("tavern")

        assert len(result) == 1
        assert result[0].entity_key == "innkeeper_001"
        assert result[0].presence_reason == PresenceReason.LIVES_HERE


# =============================================================================
# Physical Constraint Tests
# =============================================================================


class TestPhysicalConstraints:
    """Tests for physical plausibility constraints."""

    def test_rejects_visiting_during_sleep_hours(
        self,
        db_session: Session,
        game_session: GameSession,
    ) -> None:
        """Visiting NPCs are rejected during sleep hours."""
        from src.world.world_mechanics import WorldMechanics

        # Set time to 2am (sleep hours)
        time = TimeState(
            session_id=game_session.id,
            current_day=1,
            current_time="02:00",
            day_of_week="monday",
        )
        db_session.add(time)
        db_session.flush()

        wm = WorldMechanics(db_session, game_session)

        placement = NPCPlacement(
            entity_key="visitor_001",
            presence_reason=PresenceReason.VISITING,
            presence_justification="Came to visit",
            activity="waiting",
            position_in_scene="at door",
        )

        result = wm.check_placement_constraints(
            placement,
            location_type="tavern",
        )

        assert not result.allowed
        assert "sleep" in result.reason.lower()

    def test_allows_scheduled_during_sleep_hours(
        self,
        db_session: Session,
        game_session: GameSession,
    ) -> None:
        """Scheduled NPCs are allowed during sleep hours (night shift)."""
        from src.world.world_mechanics import WorldMechanics

        # Set time to 2am
        time = TimeState(
            session_id=game_session.id,
            current_day=1,
            current_time="02:00",
            day_of_week="monday",
        )
        db_session.add(time)
        db_session.flush()

        wm = WorldMechanics(db_session, game_session)

        placement = NPCPlacement(
            entity_key="guard_001",
            presence_reason=PresenceReason.SCHEDULE,
            presence_justification="Night guard shift",
            activity="patrolling",
            position_in_scene="by the gate",
        )

        result = wm.check_placement_constraints(
            placement,
            location_type="gate",
        )

        assert result.allowed

    def test_rejects_casual_entry_to_private_location(
        self,
        db_session: Session,
        game_session: GameSession,
        time_state: TimeState,
    ) -> None:
        """NPCs cannot casually enter player's private spaces."""
        from src.world.world_mechanics import WorldMechanics

        wm = WorldMechanics(db_session, game_session)

        placement = NPCPlacement(
            entity_key="stranger_001",
            presence_reason=PresenceReason.VISITING,
            presence_justification="Came to visit",
            activity="standing",
            position_in_scene="by door",
        )

        result = wm.check_placement_constraints(
            placement,
            location_type="bedroom",
            is_player_home=True,
        )

        assert not result.allowed
        # Check that the rejection is about private location access
        assert result.violated_constraint == "private_location"


# =============================================================================
# Social Constraint Tests
# =============================================================================


class TestSocialConstraints:
    """Tests for social relationship constraints."""

    def test_rejects_new_npc_when_at_weekly_limit(
        self,
        db_session: Session,
        game_session: GameSession,
        time_state: TimeState,
    ) -> None:
        """New NPCs are rejected when weekly introduction limit reached."""
        from src.world.world_mechanics import WorldMechanics

        wm = WorldMechanics(
            db_session,
            game_session,
            social_limits=SocialLimits(max_new_relationships_per_week=0),
        )

        placement = NPCPlacement(
            new_npc=NPCSpec(
                display_name="New Friend",
                gender="female",
            ),
            presence_reason=PresenceReason.STORY,
            presence_justification="Here to meet the player",
            activity="waiting",
            position_in_scene="center of room",
        )

        result = wm.check_placement_constraints(
            placement,
            location_type="tavern",
        )

        assert not result.allowed
        assert "relationship" in result.reason.lower() or "week" in result.reason.lower()

    def test_allows_existing_npc_regardless_of_limits(
        self,
        db_session: Session,
        game_session: GameSession,
        time_state: TimeState,
        npc_entity: Entity,
    ) -> None:
        """Existing NPCs are allowed even when at social limits."""
        from src.world.world_mechanics import WorldMechanics

        wm = WorldMechanics(
            db_session,
            game_session,
            social_limits=SocialLimits(max_new_relationships_per_week=0),
        )

        placement = NPCPlacement(
            entity_key="marcus_001",
            presence_reason=PresenceReason.VISITING,
            presence_justification="Visiting the player",
            activity="talking",
            position_in_scene="by the fire",
        )

        result = wm.check_placement_constraints(
            placement,
            location_type="tavern",
        )

        assert result.allowed


# =============================================================================
# Advance World Tests
# =============================================================================


class TestAdvanceWorld:
    """Tests for the main advance_world method."""

    def test_advance_world_returns_world_update(
        self,
        db_session: Session,
        game_session: GameSession,
        time_state: TimeState,
    ) -> None:
        """advance_world returns a WorldUpdate object."""
        from src.world.world_mechanics import WorldMechanics

        wm = WorldMechanics(db_session, game_session)

        result = wm.advance_world("market")

        assert isinstance(result, WorldUpdate)

    def test_advance_world_includes_scheduled_npcs(
        self,
        db_session: Session,
        game_session: GameSession,
        time_state: TimeState,
        npc_entity: Entity,
        scheduled_npc: Schedule,
    ) -> None:
        """advance_world includes scheduled NPCs at the location."""
        from src.world.world_mechanics import WorldMechanics

        wm = WorldMechanics(db_session, game_session)

        result = wm.advance_world("market")

        assert len(result.npcs_at_location) >= 1
        npc_keys = [p.entity_key for p in result.npcs_at_location]
        assert "marcus_001" in npc_keys

    def test_advance_world_filters_invalid_placements(
        self,
        db_session: Session,
        game_session: GameSession,
    ) -> None:
        """advance_world filters out placements that fail constraints."""
        from src.world.world_mechanics import WorldMechanics

        # Set time to sleep hours
        time = TimeState(
            session_id=game_session.id,
            current_day=1,
            current_time="02:00",
            day_of_week="monday",
        )
        db_session.add(time)
        db_session.flush()

        # Create NPC with schedule for daytime only
        npc = Entity(
            session_id=game_session.id,
            entity_key="day_worker",
            entity_type=EntityType.NPC,
            display_name="Day Worker",
        )
        db_session.add(npc)
        db_session.flush()

        # Add NPC extension
        ext = NPCExtension(
            entity_id=npc.id,
            current_location="shop",
        )
        db_session.add(ext)
        db_session.flush()

        # Schedule only during day
        schedule = Schedule(
            entity_id=npc.id,
            day_pattern=DayOfWeek.DAILY,
            start_time="09:00",
            end_time="17:00",
            activity="working",
            location_key="shop",
        )
        db_session.add(schedule)
        db_session.flush()

        wm = WorldMechanics(db_session, game_session)

        # At 2am, day worker shouldn't be there
        result = wm.advance_world("shop")

        npc_keys = [p.entity_key for p in result.npcs_at_location]
        assert "day_worker" not in npc_keys


# =============================================================================
# New Element Introduction Tests
# =============================================================================


class TestNewElementIntroduction:
    """Tests for introducing new world elements."""

    def test_maybe_introduce_element_checks_constraints(
        self,
        db_session: Session,
        game_session: GameSession,
        time_state: TimeState,
    ) -> None:
        """maybe_introduce_element validates against constraints."""
        from src.world.world_mechanics import WorldMechanics
        from src.world.schemas import NewElement

        wm = WorldMechanics(
            db_session,
            game_session,
            social_limits=SocialLimits(max_new_relationships_per_week=0),
        )

        element = NewElement(
            element_type="npc",
            specification={
                "display_name": "Mystery Person",
                "gender": "female",
            },
            justification="Story needs a new character",
            narrative_purpose="To advance the plot",
        )

        result = wm.maybe_introduce_element(element)

        assert not result.allowed

    def test_maybe_introduce_element_allows_valid_npc(
        self,
        db_session: Session,
        game_session: GameSession,
        time_state: TimeState,
    ) -> None:
        """maybe_introduce_element allows NPCs within constraints."""
        from src.world.world_mechanics import WorldMechanics
        from src.world.schemas import NewElement

        wm = WorldMechanics(
            db_session,
            game_session,
            social_limits=SocialLimits(max_new_relationships_per_week=5),
        )

        element = NewElement(
            element_type="npc",
            specification={
                "display_name": "New Friend",
                "gender": "male",
                "relationship_type": "acquaintance",
            },
            justification="Story needs a new character",
            narrative_purpose="To advance the plot",
        )

        result = wm.maybe_introduce_element(element)

        assert result.allowed

    def test_maybe_introduce_element_allows_facts(
        self,
        db_session: Session,
        game_session: GameSession,
        time_state: TimeState,
    ) -> None:
        """maybe_introduce_element allows fact elements."""
        from src.world.world_mechanics import WorldMechanics
        from src.world.schemas import NewElement

        wm = WorldMechanics(db_session, game_session)

        element = NewElement(
            element_type="fact",
            specification={
                "subject": "market",
                "predicate": "has_event",
                "value": "festival",
            },
            justification="Seasonal event",
            narrative_purpose="Add atmosphere",
        )

        result = wm.maybe_introduce_element(element)

        assert result.allowed


# =============================================================================
# Relationship Counting Tests
# =============================================================================


class TestRelationshipCounting:
    """Tests for counting player relationships."""

    def test_count_relationships_empty_for_new_game(
        self,
        db_session: Session,
        game_session: GameSession,
        player_entity: Entity,
    ) -> None:
        """New game has zero relationships."""
        from src.world.world_mechanics import WorldMechanics

        wm = WorldMechanics(db_session, game_session)

        counts = wm.get_relationship_counts(player_entity.id)

        assert counts["close_friends"] == 0
        assert counts["casual_friends"] == 0
        assert counts["acquaintances"] == 0

    def test_count_relationships_categorizes_correctly(
        self,
        db_session: Session,
        game_session: GameSession,
        player_entity: Entity,
        npc_entity: Entity,
    ) -> None:
        """Relationships are categorized by closeness level."""
        from src.world.world_mechanics import WorldMechanics

        # Create a close friend relationship (high liking + trust)
        rel = Relationship(
            session_id=game_session.id,
            from_entity_id=player_entity.id,
            to_entity_id=npc_entity.id,
            knows=True,
            liking=85,
            trust=80,
            familiarity=70,
        )
        db_session.add(rel)
        db_session.flush()

        wm = WorldMechanics(db_session, game_session)

        counts = wm.get_relationship_counts(player_entity.id)

        assert counts["close_friends"] == 1


# =============================================================================
# Time Context Tests
# =============================================================================


class TestTimeContext:
    """Tests for time-aware world mechanics."""

    def test_gets_current_time_from_database(
        self,
        db_session: Session,
        game_session: GameSession,
        time_state: TimeState,
    ) -> None:
        """WorldMechanics reads current time from TimeState."""
        from src.world.world_mechanics import WorldMechanics

        wm = WorldMechanics(db_session, game_session)

        current_hour = wm.get_current_hour()

        assert current_hour == 10  # From time_state fixture

    def test_creates_time_state_if_missing(
        self,
        db_session: Session,
        game_session: GameSession,
    ) -> None:
        """WorldMechanics creates default time state if none exists."""
        from src.world.world_mechanics import WorldMechanics

        wm = WorldMechanics(db_session, game_session)

        # Should not raise, uses defaults
        current_hour = wm.get_current_hour()

        assert 0 <= current_hour <= 23
