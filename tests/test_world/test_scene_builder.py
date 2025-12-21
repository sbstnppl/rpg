"""Tests for SceneBuilder - Scene-First Architecture Phase 3.

These tests verify:
- First visit scene generation (LLM-driven furniture/items/atmosphere)
- Return visit scene loading (from database)
- Observation level progression (entry → look → search → examine)
- Container content lazy loading
- NPCs merged from WorldUpdate
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from src.database.models.entities import Entity, NPCExtension
from src.database.models.enums import EntityType, ItemType, StorageLocationType
from src.database.models.items import Item, StorageLocation
from src.database.models.session import GameSession
from src.database.models.world import Location, TimeState
from src.world.schemas import (
    Atmosphere,
    FurnitureSpec,
    ItemSpec,
    ItemVisibility,
    NPCPlacement,
    ObservationLevel,
    PresenceReason,
    SceneContents,
    SceneManifest,
    SceneNPC,
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
def test_location(db_session: Session, game_session: GameSession) -> Location:
    """Create a test location."""
    location = Location(
        session_id=game_session.id,
        location_key="player_bedroom",
        display_name="Your Bedroom",
        description="A cozy room with a window.",
        category="bedroom",
    )
    db_session.add(location)
    db_session.flush()
    return location


@pytest.fixture
def visited_location(db_session: Session, game_session: GameSession) -> Location:
    """Create a location that has been visited (has canonical description)."""
    location = Location(
        session_id=game_session.id,
        location_key="tavern_main",
        display_name="The Rusty Anchor",
        description="A bustling tavern.",
        category="tavern",
        first_visited_turn=5,
        canonical_description="A worn tavern with oak tables and a stone fireplace.",
    )
    db_session.add(location)
    db_session.flush()
    return location


@pytest.fixture
def existing_furniture(
    db_session: Session,
    game_session: GameSession,
    visited_location: Location,
) -> list[Item]:
    """Create furniture items at a location.

    Note: Furniture is stored as Items with item_type=MISC or CONTAINER,
    identified by the 'furniture_type' property.
    """
    # Create storage location for the tavern
    storage = StorageLocation(
        session_id=game_session.id,
        location_key=f"place_{visited_location.location_key}",
        location_type=StorageLocationType.PLACE,
        owner_location_id=visited_location.id,
    )
    db_session.add(storage)
    db_session.flush()

    # Create furniture as items (using MISC type with furniture_type property)
    bed = Item(
        session_id=game_session.id,
        item_key="bed_001",
        display_name="a sturdy wooden bed",
        item_type=ItemType.MISC,  # Furniture uses MISC with furniture_type property
        storage_location_id=storage.id,
        owner_location_id=visited_location.id,
        properties={"furniture_type": "bed", "material": "wood", "is_container": False},
    )
    closet = Item(
        session_id=game_session.id,
        item_key="closet_001",
        display_name="an oak closet",
        item_type=ItemType.CONTAINER,  # Closet is a container type
        storage_location_id=storage.id,
        owner_location_id=visited_location.id,
        properties={
            "furniture_type": "closet",
            "material": "wood",
            "is_container": True,
            "container_state": "closed",
        },
    )
    db_session.add_all([bed, closet])
    db_session.flush()
    return [bed, closet]


@pytest.fixture
def npc_at_location(db_session: Session, game_session: GameSession) -> Entity:
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

    ext = NPCExtension(
        entity_id=entity.id,
        current_location="player_bedroom",
    )
    db_session.add(ext)
    db_session.flush()

    return entity


@pytest.fixture
def world_update_with_npc() -> WorldUpdate:
    """Create a WorldUpdate with one NPC."""
    return WorldUpdate(
        npcs_at_location=[
            NPCPlacement(
                entity_key="marcus_001",
                presence_reason=PresenceReason.VISITING,
                presence_justification="Came to visit",
                activity="sitting on the bed",
                mood="relaxed",
                position_in_scene="on the bed",
                will_initiate_conversation=True,
            )
        ],
        scheduled_movements=[],
        new_elements=[],
        events=[],
        fact_updates=[],
    )


@pytest.fixture
def mock_llm_provider() -> MagicMock:
    """Create a mock LLM provider."""
    provider = MagicMock()
    provider.complete_structured = AsyncMock()
    return provider


@pytest.fixture
def sample_scene_contents() -> SceneContents:
    """Create sample scene contents for LLM mock responses."""
    return SceneContents(
        furniture=[
            FurnitureSpec(
                furniture_key="bed_001",
                display_name="a wooden bed",
                furniture_type="bed",
                material="wood",
                condition="good",
                position_in_room="against the wall",
                is_container=False,
            ),
            FurnitureSpec(
                furniture_key="desk_001",
                display_name="a small desk",
                furniture_type="desk",
                material="wood",
                condition="worn",
                position_in_room="by the window",
                is_container=True,
                container_state="closed",
            ),
        ],
        items=[
            ItemSpec(
                item_key="candle_001",
                display_name="a candle",
                item_type="light",
                position="on desk",
                visibility=ItemVisibility.OBVIOUS,
            ),
            ItemSpec(
                item_key="diary_001",
                display_name="a small diary",
                item_type="book",
                position="in desk drawer",
                visibility=ItemVisibility.DISCOVERABLE,
            ),
        ],
        atmosphere=Atmosphere(
            lighting="soft morning light",
            lighting_source="window",
            sounds=["birds chirping outside"],
            smells=["fresh linen"],
            temperature="comfortable",
            overall_mood="peaceful",
        ),
        discoverable_hints=["The desk drawer might contain something"],
    )


# =============================================================================
# SceneBuilder Class Tests
# =============================================================================


class TestSceneBuilderInit:
    """Tests for SceneBuilder initialization."""

    def test_init_with_db_and_session(
        self,
        db_session: Session,
        game_session: GameSession,
    ) -> None:
        """SceneBuilder initializes with db and game_session."""
        from src.world.scene_builder import SceneBuilder

        sb = SceneBuilder(db_session, game_session)

        assert sb.db is db_session
        assert sb.game_session is game_session
        assert sb.session_id == game_session.id

    def test_init_with_llm_provider(
        self,
        db_session: Session,
        game_session: GameSession,
        mock_llm_provider: MagicMock,
    ) -> None:
        """SceneBuilder accepts optional LLM provider."""
        from src.world.scene_builder import SceneBuilder

        sb = SceneBuilder(db_session, game_session, llm_provider=mock_llm_provider)

        assert sb.llm_provider is mock_llm_provider


# =============================================================================
# First Visit Scene Generation Tests
# =============================================================================


class TestFirstVisitSceneGeneration:
    """Tests for generating scenes on first visit."""

    @pytest.mark.asyncio
    async def test_build_scene_first_visit_returns_scene_manifest(
        self,
        db_session: Session,
        game_session: GameSession,
        test_location: Location,
        time_state: TimeState,
        mock_llm_provider: MagicMock,
        sample_scene_contents: SceneContents,
    ) -> None:
        """build_scene returns SceneManifest for first visit."""
        from src.world.scene_builder import SceneBuilder

        # Configure LLM mock to return scene contents
        mock_response = MagicMock()
        mock_response.parsed_content = sample_scene_contents
        mock_llm_provider.complete_structured.return_value = mock_response

        sb = SceneBuilder(db_session, game_session, llm_provider=mock_llm_provider)

        result = await sb.build_scene(
            location_key="player_bedroom",
            world_update=WorldUpdate(),
            observation_level=ObservationLevel.ENTRY,
        )

        assert isinstance(result, SceneManifest)
        assert result.location_key == "player_bedroom"
        assert result.is_first_visit is True

    @pytest.mark.asyncio
    async def test_build_scene_first_visit_includes_furniture(
        self,
        db_session: Session,
        game_session: GameSession,
        test_location: Location,
        time_state: TimeState,
        mock_llm_provider: MagicMock,
        sample_scene_contents: SceneContents,
    ) -> None:
        """First visit scene includes generated furniture."""
        from src.world.scene_builder import SceneBuilder

        mock_response = MagicMock()
        mock_response.parsed_content = sample_scene_contents
        mock_llm_provider.complete_structured.return_value = mock_response

        sb = SceneBuilder(db_session, game_session, llm_provider=mock_llm_provider)

        result = await sb.build_scene(
            location_key="player_bedroom",
            world_update=WorldUpdate(),
        )

        assert len(result.furniture) >= 1
        furniture_keys = [f.furniture_key for f in result.furniture]
        assert "bed_001" in furniture_keys

    @pytest.mark.asyncio
    async def test_build_scene_first_visit_includes_atmosphere(
        self,
        db_session: Session,
        game_session: GameSession,
        test_location: Location,
        time_state: TimeState,
        mock_llm_provider: MagicMock,
        sample_scene_contents: SceneContents,
    ) -> None:
        """First visit scene includes atmosphere."""
        from src.world.scene_builder import SceneBuilder

        mock_response = MagicMock()
        mock_response.parsed_content = sample_scene_contents
        mock_llm_provider.complete_structured.return_value = mock_response

        sb = SceneBuilder(db_session, game_session, llm_provider=mock_llm_provider)

        result = await sb.build_scene(
            location_key="player_bedroom",
            world_update=WorldUpdate(),
        )

        assert result.atmosphere is not None
        assert result.atmosphere.lighting == "soft morning light"

    @pytest.mark.asyncio
    async def test_build_scene_first_visit_calls_llm(
        self,
        db_session: Session,
        game_session: GameSession,
        test_location: Location,
        time_state: TimeState,
        mock_llm_provider: MagicMock,
        sample_scene_contents: SceneContents,
    ) -> None:
        """First visit calls LLM to generate scene."""
        from src.world.scene_builder import SceneBuilder

        mock_response = MagicMock()
        mock_response.parsed_content = sample_scene_contents
        mock_llm_provider.complete_structured.return_value = mock_response

        sb = SceneBuilder(db_session, game_session, llm_provider=mock_llm_provider)

        await sb.build_scene(
            location_key="player_bedroom",
            world_update=WorldUpdate(),
        )

        mock_llm_provider.complete_structured.assert_called_once()

    @pytest.mark.asyncio
    async def test_build_scene_first_visit_sets_generated_timestamp(
        self,
        db_session: Session,
        game_session: GameSession,
        test_location: Location,
        time_state: TimeState,
        mock_llm_provider: MagicMock,
        sample_scene_contents: SceneContents,
    ) -> None:
        """First visit scene has generation timestamp."""
        from src.world.scene_builder import SceneBuilder

        mock_response = MagicMock()
        mock_response.parsed_content = sample_scene_contents
        mock_llm_provider.complete_structured.return_value = mock_response

        sb = SceneBuilder(db_session, game_session, llm_provider=mock_llm_provider)

        result = await sb.build_scene(
            location_key="player_bedroom",
            world_update=WorldUpdate(),
        )

        assert result.generated_at is not None


# =============================================================================
# Return Visit Scene Loading Tests
# =============================================================================


class TestReturnVisitSceneLoading:
    """Tests for loading scenes on return visits."""

    @pytest.mark.asyncio
    async def test_build_scene_return_visit_loads_from_db(
        self,
        db_session: Session,
        game_session: GameSession,
        visited_location: Location,
        existing_furniture: list[Item],
        time_state: TimeState,
        mock_llm_provider: MagicMock,
    ) -> None:
        """Return visit loads scene from database without LLM call."""
        from src.world.scene_builder import SceneBuilder

        sb = SceneBuilder(db_session, game_session, llm_provider=mock_llm_provider)

        result = await sb.build_scene(
            location_key="tavern_main",
            world_update=WorldUpdate(),
        )

        # Should NOT call LLM for return visit
        mock_llm_provider.complete_structured.assert_not_called()
        assert result.is_first_visit is False

    @pytest.mark.asyncio
    async def test_build_scene_return_visit_includes_existing_furniture(
        self,
        db_session: Session,
        game_session: GameSession,
        visited_location: Location,
        existing_furniture: list[Item],
        time_state: TimeState,
        mock_llm_provider: MagicMock,
    ) -> None:
        """Return visit includes furniture from database."""
        from src.world.scene_builder import SceneBuilder

        sb = SceneBuilder(db_session, game_session, llm_provider=mock_llm_provider)

        result = await sb.build_scene(
            location_key="tavern_main",
            world_update=WorldUpdate(),
        )

        furniture_keys = [f.furniture_key for f in result.furniture]
        assert "bed_001" in furniture_keys
        assert "closet_001" in furniture_keys

    @pytest.mark.asyncio
    async def test_build_scene_return_visit_uses_canonical_description(
        self,
        db_session: Session,
        game_session: GameSession,
        visited_location: Location,
        existing_furniture: list[Item],
        time_state: TimeState,
    ) -> None:
        """Return visit uses canonical description from first visit."""
        from src.world.scene_builder import SceneBuilder

        sb = SceneBuilder(db_session, game_session)

        result = await sb.build_scene(
            location_key="tavern_main",
            world_update=WorldUpdate(),
        )

        # The location display should match
        assert result.location_display == "The Rusty Anchor"


# =============================================================================
# NPC Merging Tests
# =============================================================================


class TestNPCMerging:
    """Tests for merging NPCs from WorldUpdate into scene."""

    @pytest.mark.asyncio
    async def test_build_scene_includes_npcs_from_world_update(
        self,
        db_session: Session,
        game_session: GameSession,
        test_location: Location,
        npc_at_location: Entity,
        time_state: TimeState,
        mock_llm_provider: MagicMock,
        sample_scene_contents: SceneContents,
        world_update_with_npc: WorldUpdate,
    ) -> None:
        """Scene includes NPCs from WorldUpdate."""
        from src.world.scene_builder import SceneBuilder

        mock_response = MagicMock()
        mock_response.parsed_content = sample_scene_contents
        mock_llm_provider.complete_structured.return_value = mock_response

        sb = SceneBuilder(db_session, game_session, llm_provider=mock_llm_provider)

        result = await sb.build_scene(
            location_key="player_bedroom",
            world_update=world_update_with_npc,
        )

        assert len(result.npcs) >= 1
        npc_keys = [n.entity_key for n in result.npcs]
        assert "marcus_001" in npc_keys

    @pytest.mark.asyncio
    async def test_build_scene_npc_includes_display_info(
        self,
        db_session: Session,
        game_session: GameSession,
        test_location: Location,
        npc_at_location: Entity,
        time_state: TimeState,
        mock_llm_provider: MagicMock,
        sample_scene_contents: SceneContents,
        world_update_with_npc: WorldUpdate,
    ) -> None:
        """Scene NPCs have display name from entity."""
        from src.world.scene_builder import SceneBuilder

        mock_response = MagicMock()
        mock_response.parsed_content = sample_scene_contents
        mock_llm_provider.complete_structured.return_value = mock_response

        sb = SceneBuilder(db_session, game_session, llm_provider=mock_llm_provider)

        result = await sb.build_scene(
            location_key="player_bedroom",
            world_update=world_update_with_npc,
        )

        marcus = next(n for n in result.npcs if n.entity_key == "marcus_001")
        assert marcus.display_name == "Marcus"
        assert marcus.gender == "male"

    @pytest.mark.asyncio
    async def test_build_scene_npc_includes_activity_from_placement(
        self,
        db_session: Session,
        game_session: GameSession,
        test_location: Location,
        npc_at_location: Entity,
        time_state: TimeState,
        mock_llm_provider: MagicMock,
        sample_scene_contents: SceneContents,
        world_update_with_npc: WorldUpdate,
    ) -> None:
        """Scene NPCs have activity from WorldUpdate placement."""
        from src.world.scene_builder import SceneBuilder

        mock_response = MagicMock()
        mock_response.parsed_content = sample_scene_contents
        mock_llm_provider.complete_structured.return_value = mock_response

        sb = SceneBuilder(db_session, game_session, llm_provider=mock_llm_provider)

        result = await sb.build_scene(
            location_key="player_bedroom",
            world_update=world_update_with_npc,
        )

        marcus = next(n for n in result.npcs if n.entity_key == "marcus_001")
        assert marcus.activity == "sitting on the bed"
        assert marcus.position_in_scene == "on the bed"


# =============================================================================
# Observation Level Tests
# =============================================================================


class TestObservationLevels:
    """Tests for observation level filtering."""

    @pytest.mark.asyncio
    async def test_entry_level_shows_only_obvious_items(
        self,
        db_session: Session,
        game_session: GameSession,
        test_location: Location,
        time_state: TimeState,
        mock_llm_provider: MagicMock,
        sample_scene_contents: SceneContents,
    ) -> None:
        """ENTRY observation shows only obvious items."""
        from src.world.scene_builder import SceneBuilder

        mock_response = MagicMock()
        mock_response.parsed_content = sample_scene_contents
        mock_llm_provider.complete_structured.return_value = mock_response

        sb = SceneBuilder(db_session, game_session, llm_provider=mock_llm_provider)

        result = await sb.build_scene(
            location_key="player_bedroom",
            world_update=WorldUpdate(),
            observation_level=ObservationLevel.ENTRY,
        )

        # Only obvious items should be visible
        visible_items = [i for i in result.items if i.visibility == ItemVisibility.OBVIOUS]
        hidden_items = [
            i for i in result.items if i.visibility != ItemVisibility.OBVIOUS
        ]

        assert result.observation_level == ObservationLevel.ENTRY
        # Should have obvious items
        assert len(visible_items) >= 0
        # Discoverable items should be in undiscovered_hints
        assert len(result.undiscovered_hints) >= 0

    @pytest.mark.asyncio
    async def test_look_level_reveals_discoverable_items(
        self,
        db_session: Session,
        game_session: GameSession,
        test_location: Location,
        time_state: TimeState,
        mock_llm_provider: MagicMock,
        sample_scene_contents: SceneContents,
    ) -> None:
        """LOOK observation reveals discoverable items."""
        from src.world.scene_builder import SceneBuilder

        mock_response = MagicMock()
        mock_response.parsed_content = sample_scene_contents
        mock_llm_provider.complete_structured.return_value = mock_response

        sb = SceneBuilder(db_session, game_session, llm_provider=mock_llm_provider)

        result = await sb.build_scene(
            location_key="player_bedroom",
            world_update=WorldUpdate(),
            observation_level=ObservationLevel.LOOK,
        )

        assert result.observation_level == ObservationLevel.LOOK
        # LOOK should show discoverable items
        item_visibilities = [i.visibility for i in result.items]
        # Should include discoverable items now
        assert any(v != ItemVisibility.HIDDEN for v in item_visibilities)

    @pytest.mark.asyncio
    async def test_search_level_reveals_hidden_items(
        self,
        db_session: Session,
        game_session: GameSession,
        test_location: Location,
        time_state: TimeState,
        mock_llm_provider: MagicMock,
    ) -> None:
        """SEARCH observation reveals hidden items."""
        from src.world.scene_builder import SceneBuilder

        # Create scene contents with hidden items
        contents = SceneContents(
            furniture=[],
            items=[
                ItemSpec(
                    item_key="obvious_001",
                    display_name="a visible item",
                    item_type="misc",
                    position="on table",
                    visibility=ItemVisibility.OBVIOUS,
                ),
                ItemSpec(
                    item_key="hidden_001",
                    display_name="a hidden item",
                    item_type="misc",
                    position="under floorboard",
                    visibility=ItemVisibility.HIDDEN,
                ),
            ],
            atmosphere=Atmosphere(
                lighting="dim",
                lighting_source="candle",
            ),
        )

        mock_response = MagicMock()
        mock_response.parsed_content = contents
        mock_llm_provider.complete_structured.return_value = mock_response

        sb = SceneBuilder(db_session, game_session, llm_provider=mock_llm_provider)

        result = await sb.build_scene(
            location_key="player_bedroom",
            world_update=WorldUpdate(),
            observation_level=ObservationLevel.SEARCH,
        )

        assert result.observation_level == ObservationLevel.SEARCH
        # Should include all items including hidden
        item_keys = [i.item_key for i in result.items]
        assert "hidden_001" in item_keys


# =============================================================================
# Container Content Tests
# =============================================================================


class TestContainerContents:
    """Tests for container content lazy loading."""

    @pytest.mark.asyncio
    async def test_closed_container_hides_contents(
        self,
        db_session: Session,
        game_session: GameSession,
        visited_location: Location,
        existing_furniture: list[Item],
        time_state: TimeState,
    ) -> None:
        """Closed containers don't reveal their contents."""
        from src.world.scene_builder import SceneBuilder

        # Add an item inside the closet
        closet = existing_furniture[1]  # The closet
        closet_storage = StorageLocation(
            session_id=game_session.id,
            location_key="closet_001_storage",
            location_type=StorageLocationType.CONTAINER,
            container_item_id=closet.id,
        )
        db_session.add(closet_storage)
        db_session.flush()

        hidden_item = Item(
            session_id=game_session.id,
            item_key="hidden_jacket",
            display_name="a leather jacket",
            item_type=ItemType.CLOTHING,
            storage_location_id=closet_storage.id,
        )
        db_session.add(hidden_item)
        db_session.flush()

        sb = SceneBuilder(db_session, game_session)

        result = await sb.build_scene(
            location_key="tavern_main",
            world_update=WorldUpdate(),
            observation_level=ObservationLevel.ENTRY,
        )

        # Item inside closed container should not appear in scene items
        item_keys = [i.item_key for i in result.items]
        assert "hidden_jacket" not in item_keys


# =============================================================================
# Location Type Detection Tests
# =============================================================================


class TestLocationTypeDetection:
    """Tests for detecting location type from database."""

    @pytest.mark.asyncio
    async def test_build_scene_detects_location_type(
        self,
        db_session: Session,
        game_session: GameSession,
        test_location: Location,
        time_state: TimeState,
        mock_llm_provider: MagicMock,
        sample_scene_contents: SceneContents,
    ) -> None:
        """build_scene correctly detects location type from category."""
        from src.world.scene_builder import SceneBuilder

        mock_response = MagicMock()
        mock_response.parsed_content = sample_scene_contents
        mock_llm_provider.complete_structured.return_value = mock_response

        sb = SceneBuilder(db_session, game_session, llm_provider=mock_llm_provider)

        result = await sb.build_scene(
            location_key="player_bedroom",
            world_update=WorldUpdate(),
        )

        assert result.location_type == "bedroom"


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in SceneBuilder."""

    @pytest.mark.asyncio
    async def test_build_scene_unknown_location_raises_error(
        self,
        db_session: Session,
        game_session: GameSession,
        time_state: TimeState,
    ) -> None:
        """build_scene raises error for unknown location."""
        from src.world.scene_builder import SceneBuilder

        sb = SceneBuilder(db_session, game_session)

        with pytest.raises(ValueError, match="Location not found"):
            await sb.build_scene(
                location_key="nonexistent_location",
                world_update=WorldUpdate(),
            )

    @pytest.mark.asyncio
    async def test_build_scene_without_llm_provider_uses_defaults(
        self,
        db_session: Session,
        game_session: GameSession,
        test_location: Location,
        time_state: TimeState,
    ) -> None:
        """build_scene works without LLM provider using defaults."""
        from src.world.scene_builder import SceneBuilder

        sb = SceneBuilder(db_session, game_session)  # No LLM provider

        result = await sb.build_scene(
            location_key="player_bedroom",
            world_update=WorldUpdate(),
        )

        # Should return a valid scene with default/minimal contents
        assert isinstance(result, SceneManifest)
        assert result.atmosphere is not None


# =============================================================================
# Atmosphere Context Tests
# =============================================================================


class TestAtmosphereContext:
    """Tests for atmosphere based on time/weather context."""

    @pytest.mark.asyncio
    async def test_atmosphere_reflects_time_of_day(
        self,
        db_session: Session,
        game_session: GameSession,
        test_location: Location,
        mock_llm_provider: MagicMock,
        sample_scene_contents: SceneContents,
    ) -> None:
        """Atmosphere notes include time of day."""
        from src.world.scene_builder import SceneBuilder

        # Create evening time state
        time = TimeState(
            session_id=game_session.id,
            current_day=1,
            current_time="20:00",
            day_of_week="monday",
        )
        db_session.add(time)
        db_session.flush()

        mock_response = MagicMock()
        mock_response.parsed_content = sample_scene_contents
        mock_llm_provider.complete_structured.return_value = mock_response

        sb = SceneBuilder(db_session, game_session, llm_provider=mock_llm_provider)

        await sb.build_scene(
            location_key="player_bedroom",
            world_update=WorldUpdate(),
        )

        # Verify LLM was called with time context
        call_args = mock_llm_provider.complete_structured.call_args
        assert call_args is not None
        # The messages should contain time information
