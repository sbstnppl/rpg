"""Tests for needs_validator_node - catches missed needs updates after GM narration."""

import pytest

from src.agents.nodes.needs_validator_node import (
    NEED_KEYWORDS,
    needs_validator_node,
)
from src.agents.state import GameState
from src.database.models.character_state import CharacterNeeds
from src.database.models.enums import EntityType
from src.managers.needs import NeedsManager
from tests.factories import create_entity


class TestNeedKeywordPatterns:
    """Test that keyword patterns match expected words."""

    def test_hygiene_keywords_match_wash_variants(self):
        """Verify hygiene patterns match wash/bathe/etc."""
        import re

        patterns = NEED_KEYWORDS["hygiene"]
        test_texts = [
            ("you wash your face", True),
            ("you washed yourself", True),
            ("you are washing", True),
            ("you bathe in the stream", True),
            ("you take a bath", True),
            ("you rinse off", True),
            ("you scrub the floor", True),  # Also matches
            ("the water is cold", False),  # water alone shouldn't match
        ]

        for text, should_match in test_texts:
            matched = any(re.search(p, text.lower()) for p in patterns)
            assert matched == should_match, f"Text '{text}' should {'match' if should_match else 'not match'}"

    def test_hunger_keywords_match_eat_variants(self):
        """Verify hunger patterns match eat/meal/etc."""
        import re

        patterns = NEED_KEYWORDS["hunger"]
        test_texts = [
            ("you eat the bread", True),
            ("you ate your fill", True),
            ("you are eating", True),
            ("you have a meal", True),
            ("breakfast is served", True),
            ("you take a bite", True),
            ("the table is set", False),
        ]

        for text, should_match in test_texts:
            matched = any(re.search(p, text.lower()) for p in patterns)
            assert matched == should_match, f"Text '{text}' should {'match' if should_match else 'not match'}"

    def test_thirst_keywords_match_drink_variants(self):
        """Verify thirst patterns match drink/sip/etc."""
        import re

        patterns = NEED_KEYWORDS["thirst"]
        test_texts = [
            ("you drink the water", True),
            ("you drank deeply", True),
            ("you sip the tea", True),
            ("you gulp down the ale", True),
            ("the well is nearby", False),
        ]

        for text, should_match in test_texts:
            matched = any(re.search(p, text.lower()) for p in patterns)
            assert matched == should_match, f"Text '{text}' should {'match' if should_match else 'not match'}"


class TestNeedsValidatorNode:
    """Test the needs_validator_node function."""

    @pytest.fixture
    def game_state_with_wash_response(self, db_session, game_session):
        """Create game state with a GM response mentioning washing."""
        player = create_entity(
            db_session, game_session,
            entity_type=EntityType.PLAYER,
            entity_key="player",
        )

        # Create needs with low hygiene
        needs = CharacterNeeds(
            entity_id=player.id,
            session_id=game_session.id,
            hygiene=40,
            last_bath_turn=None,  # Not updated this turn
        )
        db_session.add(needs)
        db_session.commit()

        return GameState(
            session_id=game_session.id,
            player_id=player.id,
            player_location="cottage_interior",
            player_input="I wash myself",
            gm_response="You splash cool water on your face and wash off the dust from the road.",
            turn_number=5,
            _db=db_session,
            _game_session=game_session,
        )

    @pytest.fixture
    def game_state_with_wash_already_applied(self, db_session, game_session):
        """Create game state where GM already called satisfy_need."""
        player = create_entity(
            db_session, game_session,
            entity_type=EntityType.PLAYER,
            entity_key="player",
        )

        # Create needs where last_bath_turn = current turn (already updated)
        needs = CharacterNeeds(
            entity_id=player.id,
            session_id=game_session.id,
            hygiene=70,
            last_bath_turn=5,  # Already updated this turn
        )
        db_session.add(needs)
        db_session.commit()

        return GameState(
            session_id=game_session.id,
            player_id=player.id,
            player_location="cottage_interior",
            player_input="I wash myself",
            gm_response="You wash your hands in the basin.",
            turn_number=5,
            _db=db_session,
            _game_session=game_session,
        )

    @pytest.mark.asyncio
    async def test_validator_applies_hygiene_when_gm_forgets(
        self, game_state_with_wash_response, db_session, game_session
    ):
        """Verify validator auto-applies hygiene update when GM didn't call tool."""
        state = game_state_with_wash_response
        player_id = state["player_id"]

        # Get initial hygiene
        needs_before = db_session.query(CharacterNeeds).filter(
            CharacterNeeds.entity_id == player_id
        ).first()
        assert needs_before.hygiene == 40

        # Run validator
        result = await needs_validator_node(state)

        # Check that hygiene was auto-applied (may also detect "water" for thirst)
        assert "needs_auto_applied" in result
        needs_applied = [n["need"] for n in result["needs_auto_applied"]]
        assert "hygiene" in needs_applied

        # Verify DB was updated
        db_session.refresh(needs_before)
        assert needs_before.hygiene > 40

    @pytest.mark.asyncio
    async def test_validator_skips_when_gm_already_called_tool(
        self, game_state_with_wash_already_applied, db_session, game_session
    ):
        """Verify validator doesn't duplicate when GM already called satisfy_need."""
        state = game_state_with_wash_already_applied
        player_id = state["player_id"]

        # Get initial hygiene
        needs_before = db_session.query(CharacterNeeds).filter(
            CharacterNeeds.entity_id == player_id
        ).first()
        initial_hygiene = needs_before.hygiene

        # Run validator
        result = await needs_validator_node(state)

        # Should NOT have auto-applied anything (GM already did)
        assert result.get("needs_auto_applied") is None or len(result.get("needs_auto_applied", [])) == 0

        # Hygiene should be unchanged
        db_session.refresh(needs_before)
        assert needs_before.hygiene == initial_hygiene

    @pytest.mark.asyncio
    async def test_validator_handles_multiple_needs_in_response(
        self, db_session, game_session
    ):
        """Verify validator can detect eating AND washing in same response."""
        player = create_entity(
            db_session, game_session,
            entity_type=EntityType.PLAYER,
            entity_key="player",
        )

        # Create needs with low values
        needs = CharacterNeeds(
            entity_id=player.id,
            session_id=game_session.id,
            hygiene=30,
            hunger=30,
            last_bath_turn=None,
            last_meal_turn=None,
        )
        db_session.add(needs)
        db_session.commit()

        state = GameState(
            session_id=game_session.id,
            player_id=player.id,
            player_location="cottage_interior",
            player_input="I eat breakfast and wash up",
            gm_response="You eat a hearty breakfast of eggs and bread, then wash your face in the basin.",
            turn_number=5,
            _db=db_session,
            _game_session=game_session,
        )

        result = await needs_validator_node(state)

        # Should have auto-applied both hygiene and hunger
        assert "needs_auto_applied" in result
        needs_names = [n["need"] for n in result["needs_auto_applied"]]
        assert "hygiene" in needs_names
        assert "hunger" in needs_names

    @pytest.mark.asyncio
    async def test_validator_returns_empty_for_no_keywords(
        self, db_session, game_session
    ):
        """Verify validator returns empty dict when no need keywords found."""
        player = create_entity(
            db_session, game_session,
            entity_type=EntityType.PLAYER,
            entity_key="player",
        )

        state = GameState(
            session_id=game_session.id,
            player_id=player.id,
            player_location="cottage_interior",
            player_input="I look around",
            gm_response="The cottage is small but cozy. Sunlight streams through the window.",
            turn_number=5,
            _db=db_session,
            _game_session=game_session,
        )

        result = await needs_validator_node(state)

        # No needs should be auto-applied
        assert result.get("needs_auto_applied") is None or len(result.get("needs_auto_applied", [])) == 0

    @pytest.mark.asyncio
    async def test_validator_handles_missing_db_gracefully(self):
        """Verify validator returns empty dict when DB context missing."""
        state = GameState(
            session_id=1,
            player_id=1,
            player_location="test",
            player_input="test",
            gm_response="You wash yourself.",
            turn_number=1,
        )

        # No _db or _game_session
        result = await needs_validator_node(state)
        assert result == {}
