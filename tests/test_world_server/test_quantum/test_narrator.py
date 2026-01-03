"""Tests for the Narrator Engine (Phase 4 of split architecture)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.world_server.quantum.narrator import (
    NarratorEngine,
    NarrationContext,
    NarrationResponse,
    build_narration_context,
    narrate_question_response,
    narrate_ooc_response,
)
from src.world_server.quantum.reasoning import SemanticOutcome
from src.world_server.quantum.delta_translator import TranslationResult


class TestNarrationResponse:
    """Tests for NarrationResponse schema."""

    def test_basic_creation(self):
        response = NarrationResponse(
            narrative="[npc_tom:Old Tom] slides [item_ale:a mug of ale] across the bar."
        )
        assert "[npc_tom:Old Tom]" in response.narrative
        assert "[item_ale:a mug of ale]" in response.narrative

    def test_with_inner_thoughts(self):
        response = NarrationResponse(
            narrative="The door opens.",
            inner_thoughts="You feel a chill run down your spine.",
        )
        assert response.inner_thoughts is not None
        assert "chill" in response.inner_thoughts

    def test_with_ambient_details(self):
        response = NarrationResponse(
            narrative="The tavern is quiet.",
            ambient_details="A log crackles in the fireplace.",
        )
        assert response.ambient_details is not None
        assert "fireplace" in response.ambient_details


class TestNarrationContext:
    """Tests for NarrationContext dataclass."""

    def test_basic_creation(self):
        context = NarrationContext(
            what_happens="Tom gives the player a mug of ale",
            outcome_type="success",
            key_mapping={"a mug of ale": "item_ale_001"},
            player_key="hero_001",
        )
        assert context.what_happens == "Tom gives the player a mug of ale"
        assert context.outcome_type == "success"
        assert "a mug of ale" in context.key_mapping

    def test_full_key_mapping(self):
        """Test that full_key_mapping combines all sources."""
        context = NarrationContext(
            what_happens="...",
            outcome_type="success",
            key_mapping={"new item": "item_001"},
            player_key="hero_001",
            location_display="The Tavern",
            location_key="loc_tavern",
            npcs_in_scene={"Old Tom": "npc_tom"},
            items_in_scene={"Ale Mug": "item_ale"},
        )

        full = context.full_key_mapping

        # Should contain all sources
        assert "new item" in full
        assert "Old Tom" in full
        assert "Ale Mug" in full
        assert "The Tavern" in full


class TestBuildNarrationContext:
    """Tests for build_narration_context helper."""

    def test_builds_correct_structure(self):
        context = build_narration_context(
            what_happens="Player picks up sword",
            outcome_type="success",
            key_mapping={"rusty sword": "item_sword_001"},
            player_key="hero_001",
            location_display="Armory",
            location_key="loc_armory",
            npcs_in_scene={"Guard": "npc_guard"},
            items_in_scene={"Shield": "item_shield"},
            tone_hints=["tense", "dramatic"],
        )

        assert context.what_happens == "Player picks up sword"
        assert context.outcome_type == "success"
        assert context.player_key == "hero_001"
        assert context.location_display == "Armory"
        assert "tense" in context.tone_hints

    def test_defaults_for_optional_params(self):
        context = build_narration_context(
            what_happens="Something happens",
            outcome_type="success",
            key_mapping={},
            player_key="hero",
        )

        assert context.location_display == ""
        assert context.npcs_in_scene == {}
        assert context.items_in_scene == {}
        assert context.tone_hints == []


class TestNarrationHelpers:
    """Tests for narration helper functions."""

    def test_narrate_question_response(self):
        response = narrate_question_response(
            question="Could I talk to Tom?",
            answer="Yes, Old Tom is at the bar and seems open to conversation.",
            player_key="hero_001",
        )

        assert "[hero_001:You]" in response
        assert "consider" in response
        assert "Old Tom" in response

    def test_narrate_ooc_response(self):
        response = narrate_ooc_response(
            request="what time is it?",
            response="It is currently 3:00 PM game time.",
        )

        assert "[OOC]" in response
        assert "3:00 PM" in response


class TestNarratorEngine:
    """Tests for NarratorEngine class."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM provider."""
        llm = MagicMock()
        llm.complete_structured = AsyncMock()
        return llm

    @pytest.fixture
    def narrator(self, mock_llm):
        """Create narrator with mock LLM."""
        return NarratorEngine(llm=mock_llm)

    @pytest.fixture
    def sample_context(self):
        """Create sample narration context."""
        return NarrationContext(
            what_happens="Old Tom gives the player a mug of honeyed ale",
            outcome_type="success",
            key_mapping={"a mug of honeyed ale": "item_ale_001"},
            player_key="hero_001",
            location_display="The Rusty Tankard",
            location_key="loc_tavern",
            npcs_in_scene={"Old Tom": "npc_tom_001"},
            items_in_scene={},
        )

    @pytest.mark.asyncio
    async def test_narrate_success(self, narrator, mock_llm, sample_context):
        """Test successful narration."""
        mock_response = MagicMock()
        mock_response.parsed_content = NarrationResponse(
            narrative="[npc_tom_001:Old Tom] slides [item_ale_001:a mug of honeyed ale] "
            "across the worn bar toward [hero_001:you] with a warm smile."
        )
        mock_llm.complete_structured.return_value = mock_response

        result = await narrator.narrate(sample_context)

        assert "[npc_tom_001:Old Tom]" in result.narrative
        assert "[item_ale_001:a mug of honeyed ale]" in result.narrative
        assert "[hero_001:you]" in result.narrative

    @pytest.mark.asyncio
    async def test_narrate_failure_outcome(self, narrator, mock_llm):
        """Test narration for failure outcomes."""
        context = NarrationContext(
            what_happens="The player fails to pick the lock",
            outcome_type="failure",
            key_mapping={},
            player_key="hero_001",
            items_in_scene={"the chest": "item_chest_001"},
        )

        mock_response = MagicMock()
        mock_response.parsed_content = NarrationResponse(
            narrative="[hero_001:You] fumble with [item_chest_001:the chest]'s lock, "
            "but the tumblers refuse to give."
        )
        mock_llm.complete_structured.return_value = mock_response

        result = await narrator.narrate(context)

        assert "[hero_001:You]" in result.narrative
        assert "chest" in result.narrative.lower()

    @pytest.mark.asyncio
    async def test_fallback_on_error(self, narrator, mock_llm, sample_context):
        """Test fallback narration when LLM fails."""
        mock_llm.complete_structured.side_effect = Exception("LLM error")

        result = await narrator.narrate(sample_context)

        assert result is not None
        assert result.narrative != ""
        # Fallback should include the what_happens
        assert "ale" in result.narrative.lower() or "tom" in result.narrative.lower()

    @pytest.mark.asyncio
    async def test_fallback_on_no_content(self, narrator, mock_llm, sample_context):
        """Test fallback narration when LLM returns no content."""
        mock_response = MagicMock()
        mock_response.parsed_content = None
        mock_llm.complete_structured.return_value = mock_response

        result = await narrator.narrate(sample_context)

        assert result is not None
        assert result.narrative != ""

    @pytest.mark.asyncio
    async def test_narrate_from_outcome(self, narrator, mock_llm):
        """Test convenience method for narrating from outcome."""
        outcome = SemanticOutcome(
            what_happens="Tom gives the player ale",
            outcome_type="success",
            new_things=["a mug of ale"],
        )
        translation = TranslationResult(
            deltas=[],
            key_mapping={"a mug of ale": "item_ale_001"},
            time_minutes=5,
        )

        mock_response = MagicMock()
        mock_response.parsed_content = NarrationResponse(
            narrative="[npc_tom:Tom] hands [hero_001:you] [item_ale_001:a mug of ale]."
        )
        mock_llm.complete_structured.return_value = mock_response

        result = await narrator.narrate_from_outcome(
            outcome=outcome,
            translation=translation,
            player_key="hero_001",
            location_display="Tavern",
            location_key="loc_tavern",
            npcs_in_scene={"Tom": "npc_tom"},
        )

        assert result.narrative != ""

    def test_build_prompt_includes_key_mapping(self, narrator, sample_context):
        """Test that prompt includes all key mappings."""
        prompt = narrator._build_prompt(sample_context)

        # Should include player key instruction
        assert "hero_001" in prompt
        assert "you" in prompt.lower()

        # Should include NPC key
        assert "npc_tom_001" in prompt
        assert "Old Tom" in prompt

        # Should include new item key
        assert "item_ale_001" in prompt

    def test_build_prompt_includes_location(self, narrator, sample_context):
        """Test that prompt includes location info."""
        prompt = narrator._build_prompt(sample_context)

        assert "The Rusty Tankard" in prompt
        assert "loc_tavern" in prompt

    def test_build_prompt_includes_tone_hints(self, narrator):
        """Test that tone hints are included."""
        context = NarrationContext(
            what_happens="Something tense happens",
            outcome_type="success",
            key_mapping={},
            player_key="hero",
            tone_hints=["tense", "dramatic", "suspenseful"],
        )

        prompt = narrator._build_prompt(context)

        assert "tense" in prompt
        assert "dramatic" in prompt

    def test_fallback_replaces_player_references(self, narrator):
        """Test that fallback replaces 'the player' with key format."""
        context = NarrationContext(
            what_happens="The player picks up the sword",
            outcome_type="success",
            key_mapping={},
            player_key="hero_001",
        )

        result = narrator._fallback_narration(context)

        assert "[hero_001:you]" in result.narrative or "[hero_001:You]" in result.narrative


class TestNarrationContextTimeFields:
    """Tests for time context fields in NarrationContext."""

    def test_time_fields_defaults(self):
        """Test that time fields have sensible defaults."""
        context = NarrationContext(
            what_happens="Something happens",
            outcome_type="success",
            key_mapping={},
            player_key="hero",
        )

        assert context.game_time == ""
        assert context.game_period == ""
        assert context.game_day == 1

    def test_time_fields_can_be_set(self):
        """Test that time fields can be explicitly set."""
        context = NarrationContext(
            what_happens="Something happens",
            outcome_type="success",
            key_mapping={},
            player_key="hero",
            game_time="15:30",
            game_period="afternoon",
            game_day=3,
        )

        assert context.game_time == "15:30"
        assert context.game_period == "afternoon"
        assert context.game_day == 3

    def test_build_narration_context_with_time(self):
        """Test that helper function accepts time params."""
        context = build_narration_context(
            what_happens="Player looks around",
            outcome_type="success",
            key_mapping={},
            player_key="hero_001",
            game_time="08:00",
            game_period="morning",
            game_day=2,
        )

        assert context.game_time == "08:00"
        assert context.game_period == "morning"
        assert context.game_day == 2


class TestNarratorEngineTimeContext:
    """Tests for time context in narrator engine."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM provider."""
        llm = MagicMock()
        llm.complete_structured = AsyncMock()
        return llm

    @pytest.fixture
    def narrator(self, mock_llm):
        """Create narrator with mock LLM."""
        return NarratorEngine(llm=mock_llm)

    def test_build_prompt_includes_time_when_provided(self, narrator):
        """Test that prompt includes time context when provided."""
        context = NarrationContext(
            what_happens="Player looks around",
            outcome_type="success",
            key_mapping={},
            player_key="hero",
            location_display="The Tavern",
            location_key="loc_tavern",
            game_time="15:30",
            game_period="afternoon",
            game_day=2,
        )

        prompt = narrator._build_prompt(context)

        assert "Day 2" in prompt
        assert "15:30" in prompt
        assert "afternoon" in prompt
        assert "Time:" in prompt

    def test_build_prompt_no_time_section_when_empty(self, narrator):
        """Test that time section is omitted when game_period is empty."""
        context = NarrationContext(
            what_happens="Player looks around",
            outcome_type="success",
            key_mapping={},
            player_key="hero",
            game_time="",
            game_period="",
        )

        prompt = narrator._build_prompt(context)

        # Time section should not appear
        assert "## Time:" not in prompt

    def test_prompt_includes_time_match_instruction(self, narrator):
        """Test that prompt includes instruction to match time period."""
        context = NarrationContext(
            what_happens="Player enters the tavern",
            outcome_type="success",
            key_mapping={},
            player_key="hero",
            game_time="21:00",
            game_period="evening",
            game_day=1,
        )

        prompt = narrator._build_prompt(context)

        assert "Match your descriptions to this time period" in prompt
