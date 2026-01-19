"""Tests for the OOC (Out-of-Character) Handler."""

import pytest
from unittest.mock import AsyncMock

from sqlalchemy.orm import Session

from src.database.models.session import GameSession
from src.llm.response_types import LLMResponse, UsageStats
from src.world_server.quantum.ooc_handler import (
    OOCHandler,
    OOCContext,
    OOCQueryType,
)
from tests.factories import create_location


class TestOOCQueryClassification:
    """Tests for query classification logic."""

    @pytest.fixture
    def handler(self):
        return OOCHandler()

    def test_classify_exits_direct(self, handler):
        """Direct 'exits' query is classified correctly."""
        assert handler._classify_query("exits") == OOCQueryType.EXITS

    def test_classify_exits_with_question(self, handler):
        """Question about exits is classified correctly."""
        assert handler._classify_query("what exits are available?") == OOCQueryType.EXITS

    def test_classify_exits_where_can_go(self, handler):
        """'Where can I go' is classified as exits query."""
        assert handler._classify_query("where can i go") == OOCQueryType.EXITS

    def test_classify_exits_directions(self, handler):
        """'Directions' is classified as exits query."""
        assert handler._classify_query("directions") == OOCQueryType.EXITS

    def test_classify_exits_leave(self, handler):
        """'How do I leave' is classified as exits query."""
        assert handler._classify_query("how do i leave") == OOCQueryType.EXITS

    def test_classify_time(self, handler):
        """Time queries are classified correctly."""
        assert handler._classify_query("what time is it") == OOCQueryType.TIME
        assert handler._classify_query("time") == OOCQueryType.TIME

    def test_classify_inventory(self, handler):
        """Inventory queries are classified correctly."""
        assert handler._classify_query("inventory") == OOCQueryType.INVENTORY
        assert handler._classify_query("what do i have") == OOCQueryType.INVENTORY

    def test_classify_location(self, handler):
        """Location queries are classified correctly."""
        assert handler._classify_query("where am i") == OOCQueryType.LOCATION

    def test_classify_npcs(self, handler):
        """NPC queries are classified correctly."""
        assert handler._classify_query("who is here") == OOCQueryType.NPCS
        assert handler._classify_query("who's here") == OOCQueryType.NPCS

    def test_classify_stats(self, handler):
        """Stats queries are classified correctly."""
        assert handler._classify_query("stats") == OOCQueryType.STATS
        assert handler._classify_query("health") == OOCQueryType.STATS

    def test_classify_help(self, handler):
        """Help queries are classified correctly."""
        assert handler._classify_query("help") == OOCQueryType.HELP
        assert handler._classify_query("what can i ask") == OOCQueryType.HELP

    def test_classify_unknown(self, handler):
        """Unrecognized queries are classified as unknown."""
        assert handler._classify_query("how far is the dragon") == OOCQueryType.UNKNOWN
        assert handler._classify_query("can I retcon my last action") == OOCQueryType.UNKNOWN

    def test_classify_strips_ooc_prefix(self, handler):
        """OOC prefix is stripped before classification."""
        assert handler._classify_query("ooc: exits") == OOCQueryType.EXITS
        assert handler._classify_query("ooc: what time is it") == OOCQueryType.TIME

    def test_classify_case_insensitive(self, handler):
        """Classification is case-insensitive."""
        assert handler._classify_query("EXITS") == OOCQueryType.EXITS
        assert handler._classify_query("What EXITS are AVAILABLE?") == OOCQueryType.EXITS


class TestOOCExitsHandler:
    """Tests for exits query handling."""

    @pytest.fixture
    def handler(self):
        return OOCHandler()

    def test_handle_exits_with_multiple_exits(
        self, handler, db_session: Session, game_session: GameSession
    ):
        """Returns formatted list of exits when multiple exist."""
        # Create current location with exits defined
        current_loc = create_location(
            db_session,
            game_session,
            location_key="town_square",
            display_name="Town Square",
            spatial_layout={"exits": ["market", "tavern", "blacksmith"]},
        )

        # Create exit locations
        market = create_location(
            db_session,
            game_session,
            location_key="market",
            display_name="Market District",
        )
        tavern = create_location(
            db_session,
            game_session,
            location_key="tavern",
            display_name="The Rusty Tankard",
        )
        blacksmith = create_location(
            db_session,
            game_session,
            location_key="blacksmith",
            display_name="Blacksmith's Forge",
        )

        context = OOCContext(
            db=db_session,
            game_session=game_session,
            location_key="town_square",
        )

        result = handler._handle_exits(context)

        assert "[OOC]" in result
        assert "exits" in result.lower() or "Exits" in result
        assert "Market District" in result
        assert "The Rusty Tankard" in result
        assert "Blacksmith's Forge" in result

    def test_handle_exits_no_exits_available(
        self, handler, db_session: Session, game_session: GameSession
    ):
        """Returns 'no exits' message when location has no exits."""
        # Create location with no exits defined
        loc = create_location(
            db_session,
            game_session,
            location_key="prison_cell",
            display_name="Prison Cell",
            spatial_layout={"exits": []},
        )

        context = OOCContext(
            db=db_session,
            game_session=game_session,
            location_key="prison_cell",
        )

        result = handler._handle_exits(context)

        assert "[OOC]" in result
        assert "no" in result.lower()
        assert "exit" in result.lower()

    def test_handle_exits_no_spatial_layout(
        self, handler, db_session: Session, game_session: GameSession
    ):
        """Returns 'no exits' message when spatial_layout is None."""
        loc = create_location(
            db_session,
            game_session,
            location_key="void",
            display_name="The Void",
            spatial_layout=None,
        )

        context = OOCContext(
            db=db_session,
            game_session=game_session,
            location_key="void",
        )

        result = handler._handle_exits(context)

        assert "[OOC]" in result
        assert "no" in result.lower()

    def test_handle_exits_filters_inaccessible(
        self, handler, db_session: Session, game_session: GameSession
    ):
        """Filters out inaccessible locations from exits list."""
        current_loc = create_location(
            db_session,
            game_session,
            location_key="hallway",
            display_name="Hallway",
            spatial_layout={"exits": ["open_room", "locked_room"]},
        )

        open_room = create_location(
            db_session,
            game_session,
            location_key="open_room",
            display_name="Open Room",
            is_accessible=True,
        )
        locked_room = create_location(
            db_session,
            game_session,
            location_key="locked_room",
            display_name="Locked Room",
            is_accessible=False,  # Not accessible
        )

        context = OOCContext(
            db=db_session,
            game_session=game_session,
            location_key="hallway",
        )

        result = handler._handle_exits(context)

        assert "Open Room" in result
        assert "Locked Room" not in result


class TestOOCHandleQuery:
    """Tests for the main handle_query entry point."""

    @pytest.fixture
    def handler(self):
        return OOCHandler()

    def test_handle_query_exits(
        self, handler, db_session: Session, game_session: GameSession
    ):
        """handle_query routes exits queries correctly."""
        loc = create_location(
            db_session,
            game_session,
            location_key="test_loc",
            display_name="Test Location",
            spatial_layout={"exits": []},
        )

        context = OOCContext(
            db=db_session,
            game_session=game_session,
            location_key="test_loc",
        )

        result = handler.handle_query("what exits are available?", context)

        assert "[OOC]" in result

    def test_handle_query_help(
        self, handler, db_session: Session, game_session: GameSession
    ):
        """handle_query returns help message for help queries."""
        loc = create_location(
            db_session,
            game_session,
            location_key="test_loc",
            display_name="Test Location",
        )

        context = OOCContext(
            db=db_session,
            game_session=game_session,
            location_key="test_loc",
        )

        result = handler.handle_query("help", context)

        assert "[OOC]" in result
        assert "exit" in result.lower()  # Should mention exits as a command


class TestOOCUnknownQueryLLMFallback:
    """Tests for LLM fallback on unknown queries."""

    @pytest.fixture
    def handler(self):
        return OOCHandler()

    @pytest.mark.asyncio
    async def test_unknown_query_calls_llm(
        self, handler, db_session: Session, game_session: GameSession
    ):
        """Unknown queries fall back to LLM."""
        loc = create_location(
            db_session,
            game_session,
            location_key="test_loc",
            display_name="Test Location",
        )

        context = OOCContext(
            db=db_session,
            game_session=game_session,
            location_key="test_loc",
        )

        mock_llm = AsyncMock()
        mock_response = LLMResponse(
            content="[OOC] The dragon is about 2 days journey to the north.",
            tool_calls=(),
            parsed_content=None,
            finish_reason="stop",
            model="test-model",
            usage=UsageStats(
                prompt_tokens=100,
                completion_tokens=20,
                total_tokens=120,
            ),
        )
        mock_llm.complete.return_value = mock_response

        result = await handler.handle_query_async(
            "how far is the dragon",
            context,
            llm_provider=mock_llm,
        )

        mock_llm.complete.assert_called_once()
        assert "[OOC]" in result
        assert "dragon" in result.lower()

    @pytest.mark.asyncio
    async def test_llm_fallback_includes_context(
        self, handler, db_session: Session, game_session: GameSession
    ):
        """LLM fallback prompt includes game state context."""
        loc = create_location(
            db_session,
            game_session,
            location_key="village_square",
            display_name="Village Square",
        )

        context = OOCContext(
            db=db_session,
            game_session=game_session,
            location_key="village_square",
        )

        mock_llm = AsyncMock()
        mock_response = LLMResponse(
            content="[OOC] Answer here.",
            tool_calls=(),
            parsed_content=None,
            finish_reason="stop",
            model="test-model",
            usage=UsageStats(
                prompt_tokens=100,
                completion_tokens=20,
                total_tokens=120,
            ),
        )
        mock_llm.complete.return_value = mock_response

        await handler.handle_query_async(
            "can I retcon my last action",
            context,
            llm_provider=mock_llm,
        )

        # Check that the prompt passed to LLM contains location info
        call_args = mock_llm.complete.call_args
        # The messages kwarg contains a list of Message objects
        messages = call_args[1].get("messages", [])
        # Extract content from the first user message
        prompt = messages[0].content if messages else ""
        assert "Village Square" in prompt

    @pytest.mark.asyncio
    async def test_llm_fallback_without_provider_returns_generic(
        self, handler, db_session: Session, game_session: GameSession
    ):
        """Without LLM provider, returns generic response."""
        loc = create_location(
            db_session,
            game_session,
            location_key="test_loc",
            display_name="Test Location",
        )

        context = OOCContext(
            db=db_session,
            game_session=game_session,
            location_key="test_loc",
        )

        result = await handler.handle_query_async(
            "how far is the dragon",
            context,
            llm_provider=None,
        )

        assert "[OOC]" in result
        # Should indicate it doesn't know, not crash
        assert "don't" in result.lower() or "cannot" in result.lower() or "unable" in result.lower()


class TestOOCContext:
    """Tests for OOCContext dataclass."""

    def test_context_creation(self, db_session: Session, game_session: GameSession):
        """OOCContext can be created with required fields."""
        loc = create_location(
            db_session,
            game_session,
            location_key="test_loc",
            display_name="Test Location",
        )

        context = OOCContext(
            db=db_session,
            game_session=game_session,
            location_key="test_loc",
        )

        assert context.db == db_session
        assert context.game_session == game_session
        assert context.location_key == "test_loc"
