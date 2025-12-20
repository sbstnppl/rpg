"""Tests for parse_intent_node and pronoun resolution context building."""

from unittest.mock import AsyncMock, MagicMock
import pytest
from sqlalchemy.orm import Session

from src.agents.nodes.parse_intent_node import _build_scene_context
from src.database.models.session import GameSession, Turn
from src.parser.intent_parser import SceneContext
from src.parser.action_types import ActionType
from src.parser.llm_classifier import (
    _build_classifier_prompt,
    classify_intent,
    ClassificationResult,
    ClassifiedAction,
)


class TestBuildClassifierPrompt:
    """Test that classifier prompt includes context for pronoun resolution."""

    def test_recent_mentions_included_in_prompt(self):
        """Recent conversation should be included when provided."""
        context = SceneContext(
            location_key="farm",
            entities_present=["ursula"],
            entity_names={"ursula": "Ursula"},
            recent_mentions="GM: Ursula waves at you from the field.",
        )
        prompt = _build_classifier_prompt("Where is she?", context)

        assert "Ursula" in prompt
        assert "Recent Conversation" in prompt
        assert "waves at you from the field" in prompt

    def test_entities_present_in_prompt(self):
        """Entities at location should be listed with their display names."""
        context = SceneContext(
            location_key="farm",
            entities_present=["ursula", "blacksmith_tom"],
            entity_names={"ursula": "Ursula", "blacksmith_tom": "Tom the Blacksmith"},
        )
        prompt = _build_classifier_prompt("Talk to her", context)

        assert "ursula (Ursula)" in prompt
        assert "blacksmith_tom (Tom the Blacksmith)" in prompt

    def test_items_present_in_prompt(self):
        """Items at location should be listed with their display names."""
        context = SceneContext(
            location_key="cellar",
            items_present=["rusty_sword", "old_shield"],
            item_names={"rusty_sword": "rusty sword", "old_shield": "battered shield"},
        )
        prompt = _build_classifier_prompt("Take it", context)

        assert "rusty_sword (rusty sword)" in prompt
        assert "old_shield (battered shield)" in prompt

    def test_empty_context_gracefully_handled(self):
        """Empty context should not crash and show 'none' for entities/items."""
        context = SceneContext(location_key="wilderness")
        prompt = _build_classifier_prompt("Look around", context)

        assert "Entities present: none" in prompt
        assert "Items visible: none" in prompt

    def test_no_recent_mentions_section_when_empty(self):
        """Recent Conversation section should not appear when empty."""
        context = SceneContext(
            location_key="farm",
            recent_mentions="",
        )
        prompt = _build_classifier_prompt("Look around", context)

        assert "Recent Conversation" not in prompt


class TestBuildSceneContext:
    """Test _build_scene_context helper populates context from database."""

    def test_returns_minimal_context_without_db(self):
        """Without DB, should return context with just location_key."""
        state = {
            "player_location": "village_square",
            "_db": None,
            "_game_session": None,
        }

        context = _build_scene_context(state)

        assert context.location_key == "village_square"
        assert context.entities_present is None
        assert context.items_present is None
        assert context.recent_mentions == ""

    def test_populates_recent_mentions_from_turns(
        self, db_session: Session, game_session: GameSession
    ):
        """Should populate recent_mentions from last 2 GM responses."""
        # Create turns with GM responses
        turn1 = Turn(
            session_id=game_session.id,
            turn_number=1,
            player_input="Hello",
            gm_response="Ursula looks up from her work and smiles at you warmly.",
        )
        turn2 = Turn(
            session_id=game_session.id,
            turn_number=2,
            player_input="How are you?",
            gm_response="She says she's been busy with the harvest lately.",
        )
        db_session.add_all([turn1, turn2])
        db_session.flush()

        state = {
            "player_location": "farm",
            "_db": db_session,
            "_game_session": game_session,
        }

        context = _build_scene_context(state)

        # Should contain both GM responses (in chronological order)
        assert "Ursula" in context.recent_mentions
        assert "harvest" in context.recent_mentions

    def test_truncates_long_gm_responses(
        self, db_session: Session, game_session: GameSession
    ):
        """Long GM responses should be truncated with ellipsis."""
        # Create turn with very long response (> 1000 chars to trigger truncation)
        long_response = "A" * 1500  # 1500 chars, above 1000 limit
        turn = Turn(
            session_id=game_session.id,
            turn_number=1,
            player_input="Describe",
            gm_response=long_response,
        )
        db_session.add(turn)
        db_session.flush()

        state = {
            "player_location": "farm",
            "_db": db_session,
            "_game_session": game_session,
        }

        context = _build_scene_context(state)

        # Should be truncated to ~1000 chars for GM + ~200 for player + prefixes + "..."
        # Total should be < 1300 chars (not the full 1500)
        assert len(context.recent_mentions) < 1300
        assert context.recent_mentions.endswith("...")

    def test_handles_empty_location(
        self, db_session: Session, game_session: GameSession
    ):
        """Should handle location with no entities or items."""
        state = {
            "player_location": "empty_room",
            "_db": db_session,
            "_game_session": game_session,
        }

        context = _build_scene_context(state)

        # Should return empty lists, not None
        assert context.entities_present == []
        assert context.items_present == []


class TestPronounResolutionPassthrough:
    """Test that resolved pronouns are passed through to planner."""

    @pytest.mark.asyncio
    async def test_resolved_target_passed_for_custom_query(self):
        """When classifier resolves pronoun for CUSTOM query, resolved_target should be in params."""
        # Mock the LLM provider
        mock_provider = MagicMock()
        mock_response = MagicMock()
        mock_response.parsed_content = ClassificationResult(
            actions=[
                ClassifiedAction(
                    action_type="custom",
                    target="ursula",  # Classifier resolved "she" to "ursula"
                )
            ]
        )
        mock_provider.complete_structured = AsyncMock(return_value=mock_response)

        # Create context with Ursula mentioned in recent conversation
        context = SceneContext(
            location_key="farm",
            entities_present=["ursula"],
            entity_names={"ursula": "Ursula"},
            recent_mentions="GM: Ursula waves at you from the field.",
        )

        # Classify the query
        result = await classify_intent(
            text="Where is she?",
            context=context,
            provider=mock_provider,
        )

        # Verify resolved_target is passed through
        assert len(result.actions) == 1
        action = result.actions[0]
        assert action.type == ActionType.CUSTOM
        assert action.target == "ursula"
        assert action.parameters.get("resolved_target") == "ursula"
        assert "Where is she?" in action.parameters.get("raw_input", "")

    @pytest.mark.asyncio
    async def test_no_resolved_target_when_no_pronoun(self):
        """When classifier has no pronoun to resolve, resolved_target should not be set."""
        mock_provider = MagicMock()
        mock_response = MagicMock()
        mock_response.parsed_content = ClassificationResult(
            actions=[
                ClassifiedAction(
                    action_type="custom",
                    target=None,  # No pronoun to resolve
                )
            ]
        )
        mock_provider.complete_structured = AsyncMock(return_value=mock_response)

        context = SceneContext(location_key="farm")

        result = await classify_intent(
            text="Am I hungry?",
            context=context,
            provider=mock_provider,
        )

        assert len(result.actions) == 1
        action = result.actions[0]
        assert action.type == ActionType.CUSTOM
        # resolved_target should NOT be set
        assert "resolved_target" not in action.parameters
        assert action.parameters.get("raw_input") == "Am I hungry?"

    @pytest.mark.asyncio
    async def test_resolved_target_for_action_with_pronoun(self):
        """For regular actions (not CUSTOM), resolved pronoun should be in target."""
        mock_provider = MagicMock()
        mock_response = MagicMock()
        mock_response.parsed_content = ClassificationResult(
            actions=[
                ClassifiedAction(
                    action_type="talk",
                    target="ursula",  # Resolved from "her"
                )
            ]
        )
        mock_provider.complete_structured = AsyncMock(return_value=mock_response)

        context = SceneContext(
            location_key="farm",
            entities_present=["ursula"],
            entity_names={"ursula": "Ursula"},
            recent_mentions="GM: Ursula is standing nearby.",
        )

        result = await classify_intent(
            text="Talk to her",
            context=context,
            provider=mock_provider,
        )

        assert len(result.actions) == 1
        action = result.actions[0]
        assert action.type == ActionType.TALK
        assert action.target == "ursula"
        # For non-CUSTOM actions, resolved_target is not separately tracked
        # (the target field already contains the resolved value)
