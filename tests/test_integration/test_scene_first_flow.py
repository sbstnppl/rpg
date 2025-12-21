"""Integration tests for Scene-First Architecture flow.

Tests the complete scene-first pipeline:
- World Mechanics → Scene Builder → Persist → Resolve → Narrate

These tests verify the graph nodes work together correctly.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.orm import Session

from src.agents.graph import build_scene_first_graph, SCENE_FIRST_NODES
from src.agents.state import create_initial_state, GameState
from src.database.models.enums import EntityType, DayOfWeek
from src.database.models.session import GameSession
from src.database.models.world import Location, TimeState
from src.database.models.entities import Entity, NPCExtension
from src.llm.response_types import LLMResponse, UsageStats
from src.world.schemas import (
    Atmosphere,
    FurnitureSpec,
    ItemSpec,
    ItemVisibility,
    SceneContents,
)
from tests.factories import create_entity, create_location


# Fixtures


@pytest.fixture
def tavern_location(db_session: Session, game_session: GameSession):
    """Create a tavern location for testing."""
    location = Location(
        session_id=game_session.id,
        location_key="tavern",
        display_name="The Rusty Mug Tavern",
        category="tavern",
        description="A cozy tavern with a warm fireplace",
        atmosphere="Warm and inviting",
    )
    db_session.add(location)
    db_session.flush()
    return location


@pytest.fixture
def time_state(db_session: Session, game_session: GameSession):
    """Create time state for testing."""
    ts = TimeState(
        session_id=game_session.id,
        current_day=1,
        current_time="14:00",
        day_of_week="monday",
        weather="clear",
    )
    db_session.add(ts)
    db_session.flush()
    return ts


@pytest.fixture
def bartender_npc(db_session: Session, game_session: GameSession, tavern_location):
    """Create a bartender NPC at the tavern."""
    entity = Entity(
        session_id=game_session.id,
        entity_key="bartender_001",
        display_name="Old Tom",
        entity_type=EntityType.NPC,
        gender="male",
        occupation="bartender",
        is_alive=True,
        is_active=True,
    )
    db_session.add(entity)
    db_session.flush()

    npc_ext = NPCExtension(
        entity_id=entity.id,
        job="bartender",
        home_location="tavern",
        current_location="tavern",
        current_activity="polishing mugs",
        current_mood="friendly",
    )
    db_session.add(npc_ext)
    db_session.flush()

    return entity


@pytest.fixture
def mock_scene_contents():
    """Mock LLM response for scene generation."""
    return SceneContents(
        furniture=[
            FurnitureSpec(
                furniture_key="bar_counter_001",
                display_name="Bar Counter",
                furniture_type="counter",
                material="oak",
                condition="worn",
                position_in_room="along the north wall",
                is_container=False,
            ),
            FurnitureSpec(
                furniture_key="fireplace_001",
                display_name="Stone Fireplace",
                furniture_type="fireplace",
                material="stone",
                condition="good",
                position_in_room="on the east wall",
                is_container=False,
            ),
        ],
        items=[
            ItemSpec(
                item_key="mug_001",
                display_name="Wooden Mug",
                item_type="misc",
                position="on the bar counter",
                visibility=ItemVisibility.OBVIOUS,
            ),
        ],
        atmosphere=Atmosphere(
            lighting="warm firelight",
            lighting_source="fireplace",
            sounds=["crackling fire", "murmured conversations"],
            smells=["woodsmoke", "ale"],
            temperature="warm",
            overall_mood="cozy",
        ),
        discoverable_hints=[],
    )


# Test Classes


class TestSceneFirstGraph:
    """Test that the scene-first graph can be built and compiled."""

    def test_graph_builds_successfully(self):
        """Graph should build without errors."""
        graph = build_scene_first_graph()
        assert graph is not None

    def test_graph_has_all_nodes(self):
        """Graph should contain all expected nodes."""
        graph = build_scene_first_graph()
        expected_nodes = [
            "context_compiler",
            "parse_intent",
            "world_mechanics",
            "scene_builder",
            "persist_scene",
            "resolve_references",
            "subturn_processor",
            "state_validator",
            "constrained_narrator",
            "validate_narrator",
            "persistence",
        ]
        for node in expected_nodes:
            assert node in graph.nodes, f"Missing node: {node}"

    def test_graph_compiles(self):
        """Graph should compile to runnable."""
        graph = build_scene_first_graph()
        compiled = graph.compile()
        assert compiled is not None


class TestWorldMechanicsNode:
    """Test the world mechanics node in isolation."""

    @pytest.mark.asyncio
    async def test_world_mechanics_returns_update(
        self,
        db_session: Session,
        game_session: GameSession,
        player_entity,
        tavern_location,
        time_state,
        bartender_npc,
    ):
        """World mechanics should return NPCs at location."""
        from src.agents.nodes.world_mechanics_node import world_mechanics_node

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="look around",
        )
        state["_db"] = db_session
        state["_game_session"] = game_session
        state["location_changed"] = True

        result = await world_mechanics_node(state)

        assert "world_update" in result
        assert result["world_update"] is not None
        assert "npcs_at_location" in result["world_update"]
        assert result.get("just_entered_location") is True

    @pytest.mark.asyncio
    async def test_world_mechanics_handles_missing_location(
        self,
        db_session: Session,
        game_session: GameSession,
        player_entity,
    ):
        """World mechanics should handle missing location gracefully."""
        from src.agents.nodes.world_mechanics_node import world_mechanics_node

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="nonexistent",
            player_input="look around",
        )
        state["_db"] = db_session
        state["_game_session"] = game_session

        result = await world_mechanics_node(state)

        # Should still return world_update (may be empty)
        assert "world_update" in result


class TestSceneBuilderNode:
    """Test the scene builder node in isolation."""

    @pytest.mark.asyncio
    async def test_scene_builder_first_visit(
        self,
        db_session: Session,
        game_session: GameSession,
        player_entity,
        tavern_location,
        time_state,
        mock_scene_contents,
    ):
        """Scene builder should generate scene on first visit."""
        from src.agents.nodes.scene_builder_node import scene_builder_node
        from src.world.schemas import WorldUpdate

        # Create world update
        world_update = WorldUpdate(
            npcs_at_location=[],
            scheduled_movements=[],
            new_elements=[],
            events=[],
            fact_updates=[],
        )

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="look around",
        )
        state["_db"] = db_session
        state["_game_session"] = game_session
        state["world_update"] = world_update.model_dump()
        state["just_entered_location"] = True

        # Mock LLM provider (mock at source module since imports are lazy)
        with patch("src.llm.factory.get_extraction_provider") as mock_provider:
            mock_llm = AsyncMock()
            mock_llm.complete_structured = AsyncMock(
                return_value=MagicMock(parsed_content=mock_scene_contents)
            )
            mock_provider.return_value = mock_llm

            result = await scene_builder_node(state)

        assert "scene_manifest" in result
        assert result["scene_manifest"] is not None
        assert result["scene_manifest"]["is_first_visit"] is True


class TestResolveReferencesNode:
    """Test the reference resolution node."""

    @pytest.mark.asyncio
    async def test_resolve_exact_key(
        self,
        db_session: Session,
        game_session: GameSession,
        player_entity,
    ):
        """Should resolve exact key matches."""
        from src.agents.nodes.resolve_references_node import resolve_references_node
        from src.world.schemas import NarratorManifest, EntityRef, Atmosphere

        # Create manifest with bartender
        manifest = NarratorManifest(
            location_key="tavern",
            location_display="The Rusty Mug Tavern",
            entities={
                "bartender_001": EntityRef(
                    key="bartender_001",
                    display_name="Old Tom",
                    entity_type="npc",
                    short_description="friendly bartender",
                    pronouns="he/him",
                ),
            },
            atmosphere=Atmosphere(
                lighting="warm",
                lighting_source="fireplace",
                sounds=[],
                smells=[],
                temperature="comfortable",
                overall_mood="cozy",
            ),
        )

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="talk to Old Tom",
        )
        state["narrator_manifest"] = manifest.model_dump()
        state["parsed_actions"] = [
            {"type": "TALK", "target": "Old Tom", "parameters": {}}
        ]

        result = await resolve_references_node(state)

        assert "resolved_actions" in result
        assert len(result["resolved_actions"]) == 1
        assert result["resolved_actions"][0].get("resolved_target_key") == "bartender_001"
        assert result["needs_clarification"] is False

    @pytest.mark.asyncio
    async def test_resolve_ambiguous_pronoun(
        self,
        db_session: Session,
        game_session: GameSession,
        player_entity,
    ):
        """Should detect ambiguous pronoun references."""
        from src.agents.nodes.resolve_references_node import resolve_references_node
        from src.world.schemas import NarratorManifest, EntityRef, Atmosphere

        # Create manifest with two male NPCs
        manifest = NarratorManifest(
            location_key="tavern",
            location_display="The Rusty Mug Tavern",
            entities={
                "bartender_001": EntityRef(
                    key="bartender_001",
                    display_name="Old Tom",
                    entity_type="npc",
                    short_description="friendly bartender",
                    pronouns="he/him",
                ),
                "patron_001": EntityRef(
                    key="patron_001",
                    display_name="Marcus",
                    entity_type="npc",
                    short_description="regular patron",
                    pronouns="he/him",
                ),
            },
            atmosphere=Atmosphere(
                lighting="warm",
                lighting_source="fireplace",
                sounds=[],
                smells=[],
                temperature="comfortable",
                overall_mood="cozy",
            ),
        )

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="talk to him",
        )
        state["narrator_manifest"] = manifest.model_dump()
        state["parsed_actions"] = [
            {"type": "TALK", "target": "him", "parameters": {}}
        ]

        result = await resolve_references_node(state)

        assert result["needs_clarification"] is True
        assert result["clarification_prompt"] is not None
        assert len(result["clarification_candidates"]) == 2


class TestConstrainedNarratorNode:
    """Test the constrained narrator node."""

    @pytest.mark.asyncio
    async def test_narrator_scene_entry(
        self,
        db_session: Session,
        game_session: GameSession,
        player_entity,
    ):
        """Should generate scene entry narration."""
        from src.agents.nodes.constrained_narrator_node import constrained_narrator_node
        from src.world.schemas import NarratorManifest, EntityRef, Atmosphere

        manifest = NarratorManifest(
            location_key="tavern",
            location_display="The Rusty Mug Tavern",
            entities={
                "bartender_001": EntityRef(
                    key="bartender_001",
                    display_name="Old Tom",
                    entity_type="npc",
                    short_description="friendly bartender",
                    pronouns="he/him",
                ),
            },
            atmosphere=Atmosphere(
                lighting="warm firelight",
                lighting_source="fireplace",
                sounds=["crackling fire"],
                smells=["woodsmoke"],
                temperature="warm",
                overall_mood="cozy",
            ),
        )

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="[FIRST TURN]",
        )
        state["narrator_manifest"] = manifest.model_dump()
        state["just_entered_location"] = True
        state["is_scene_request"] = True

        # Mock LLM to return structured output (mock at source module since imports are lazy)
        with patch("src.llm.factory.get_extraction_provider") as mock_provider:
            mock_llm = AsyncMock()
            mock_llm.complete = AsyncMock(
                return_value=MagicMock(
                    content="You step into The Rusty Mug Tavern. Warm firelight bathes the room as [bartender_001] polishes a mug behind the counter."
                )
            )
            mock_provider.return_value = mock_llm

            result = await constrained_narrator_node(state)

        assert "gm_response" in result
        assert result["gm_response"] is not None
        # Key should be stripped in display
        assert "Old Tom" in result["gm_response"]


class TestRouting:
    """Test graph routing functions."""

    def test_route_after_parse_location_change(self):
        """Should route to world_mechanics on location change."""
        from src.agents.graph import route_after_parse_scene_first

        state = GameState(
            session_id=1,
            player_id=1,
            player_location="tavern",
            player_input="go to tavern",
            location_changed=True,
            errors=[],
        )

        result = route_after_parse_scene_first(state)
        assert result == "world_mechanics"

    def test_route_after_parse_with_actions(self):
        """Should route to resolve_references with parsed actions."""
        from src.agents.graph import route_after_parse_scene_first

        state = GameState(
            session_id=1,
            player_id=1,
            player_location="tavern",
            player_input="talk to bartender",
            location_changed=False,
            just_entered_location=False,
            parsed_actions=[{"type": "TALK", "target": "bartender"}],
            errors=[],
        )

        result = route_after_parse_scene_first(state)
        assert result == "resolve_references"

    def test_route_after_resolve_clarification(self):
        """Should route to narrator when clarification needed."""
        from src.agents.graph import route_after_resolve

        state = GameState(
            session_id=1,
            player_id=1,
            player_location="tavern",
            player_input="talk to him",
            needs_clarification=True,
            clarification_prompt="Which person?",
            errors=[],
        )

        result = route_after_resolve(state)
        assert result == "constrained_narrator"

    def test_route_after_resolve_with_actions(self):
        """Should route to subturn_processor with resolved actions."""
        from src.agents.graph import route_after_resolve

        state = GameState(
            session_id=1,
            player_id=1,
            player_location="tavern",
            player_input="talk to bartender",
            needs_clarification=False,
            resolved_actions=[{"type": "TALK", "resolved_target_key": "bartender_001"}],
            errors=[],
        )

        result = route_after_resolve(state)
        assert result == "subturn_processor"


class TestEndToEndFlow:
    """Test complete end-to-end flows."""

    @pytest.mark.asyncio
    async def test_enter_location_flow(
        self,
        db_session: Session,
        game_session: GameSession,
        player_entity,
        tavern_location,
        time_state,
        bartender_npc,
        mock_scene_contents,
    ):
        """Test complete flow: enter location → see scene."""
        from src.agents.nodes.world_mechanics_node import world_mechanics_node
        from src.agents.nodes.scene_builder_node import scene_builder_node
        from src.agents.nodes.persist_scene_node import persist_scene_node
        from src.agents.nodes.resolve_references_node import resolve_references_node
        from src.agents.nodes.constrained_narrator_node import constrained_narrator_node

        # Step 1: Create initial state for entering location
        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="tavern",
            player_input="[FIRST TURN]",
        )
        state["_db"] = db_session
        state["_game_session"] = game_session
        state["location_changed"] = True
        state["is_scene_request"] = True

        # Step 2: World Mechanics
        result1 = await world_mechanics_node(state)
        state.update(result1)

        assert result1["world_update"] is not None

        # Step 3: Scene Builder (with mocked LLM)
        with patch("src.llm.factory.get_extraction_provider") as mock_provider:
            mock_llm = AsyncMock()
            mock_llm.complete_structured = AsyncMock(
                return_value=MagicMock(parsed_content=mock_scene_contents)
            )
            mock_provider.return_value = mock_llm

            result2 = await scene_builder_node(state)
            state.update(result2)

        assert result2["scene_manifest"] is not None
        assert result2["scene_manifest"]["is_first_visit"] is True

        # Step 4: Persist Scene
        result3 = await persist_scene_node(state)
        state.update(result3)

        assert result3["narrator_manifest"] is not None

        # Step 5: Resolve References (no actions for scene entry)
        result4 = await resolve_references_node(state)
        state.update(result4)

        assert result4["needs_clarification"] is False

        # Step 6: Constrained Narrator
        with patch("src.llm.factory.get_extraction_provider") as mock_provider:
            mock_llm = AsyncMock()
            mock_llm.complete = AsyncMock(
                return_value=MagicMock(
                    content="You enter The Rusty Mug Tavern. [bartender_001] stands behind the [bar_counter_001], polishing a [mug_001]."
                )
            )
            mock_provider.return_value = mock_llm

            result5 = await constrained_narrator_node(state)

        assert result5["gm_response"] is not None
        # Keys should be replaced with display names
        assert "Old Tom" in result5["gm_response"]
        assert "Bar Counter" in result5["gm_response"]
