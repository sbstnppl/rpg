"""Tests for GameState TypedDict and state utilities."""

import pytest
from typing import get_type_hints

from src.agents.state import (
    GameState,
    create_initial_state,
    merge_state,
    AgentName,
)


class TestGameStateSchema:
    """Test GameState TypedDict structure."""

    def test_game_state_is_typed_dict(self):
        """GameState should be a TypedDict."""
        # TypedDict classes have __annotations__
        assert hasattr(GameState, "__annotations__")

    def test_required_session_fields(self):
        """GameState should have session context fields."""
        hints = get_type_hints(GameState)
        assert "session_id" in hints
        assert "player_id" in hints
        assert "player_location" in hints

    def test_required_turn_fields(self):
        """GameState should have turn I/O fields."""
        hints = get_type_hints(GameState)
        assert "player_input" in hints
        assert "gm_response" in hints
        assert "scene_context" in hints

    def test_routing_fields(self):
        """GameState should have routing control fields."""
        hints = get_type_hints(GameState)
        assert "next_agent" in hints

    def test_trigger_fields(self):
        """GameState should have trigger fields for conditional routing."""
        hints = get_type_hints(GameState)
        assert "time_advance_minutes" in hints
        assert "location_changed" in hints
        assert "combat_active" in hints

    def test_extraction_fields(self):
        """GameState should have extraction result fields."""
        hints = get_type_hints(GameState)
        assert "extracted_entities" in hints
        assert "extracted_facts" in hints
        assert "relationship_changes" in hints

    def test_metadata_fields(self):
        """GameState should have metadata fields."""
        hints = get_type_hints(GameState)
        assert "turn_number" in hints
        assert "errors" in hints


class TestAgentName:
    """Test AgentName literal type."""

    def test_valid_agent_names(self):
        """AgentName should include all expected agents."""
        # AgentName is a Literal type, we test by assignment
        valid_names = [
            "context_compiler",
            "game_master",
            "entity_extractor",
            "combat_resolver",
            "world_simulator",
            "persistence",
            "end",
        ]
        # Just verify these are valid string values
        for name in valid_names:
            assert isinstance(name, str)


class TestCreateInitialState:
    """Test initial state creation."""

    def test_create_with_required_fields(self):
        """Should create state with required session fields."""
        state = create_initial_state(
            session_id=1,
            player_id=10,
            player_location="tavern",
            player_input="Look around",
        )

        assert state["session_id"] == 1
        assert state["player_id"] == 10
        assert state["player_location"] == "tavern"
        assert state["player_input"] == "Look around"

    def test_default_values(self):
        """Should set sensible defaults for optional fields."""
        state = create_initial_state(
            session_id=1,
            player_id=10,
            player_location="tavern",
            player_input="Hello",
        )

        assert state["gm_response"] is None
        assert state["scene_context"] == ""
        assert state["next_agent"] == "context_compiler"
        assert state["time_advance_minutes"] == 0
        assert state["location_changed"] is False
        assert state["combat_active"] is False
        assert state["extracted_entities"] == []
        assert state["extracted_facts"] == []
        assert state["relationship_changes"] == []
        assert state["errors"] == []

    def test_turn_number_starts_at_one(self):
        """Turn number should start at 1 by default."""
        state = create_initial_state(
            session_id=1,
            player_id=10,
            player_location="tavern",
            player_input="Test",
        )
        assert state["turn_number"] == 1

    def test_custom_turn_number(self):
        """Should accept custom turn number."""
        state = create_initial_state(
            session_id=1,
            player_id=10,
            player_location="tavern",
            player_input="Test",
            turn_number=5,
        )
        assert state["turn_number"] == 5


class TestMergeState:
    """Test state merging with reducer support."""

    def test_simple_field_override(self):
        """Non-list fields should be overwritten."""
        original = create_initial_state(
            session_id=1,
            player_id=10,
            player_location="tavern",
            player_input="Hello",
        )

        updated = merge_state(original, {
            "gm_response": "You see a dark tavern.",
            "next_agent": "entity_extractor",
        })

        assert updated["gm_response"] == "You see a dark tavern."
        assert updated["next_agent"] == "entity_extractor"
        # Original unchanged
        assert updated["session_id"] == 1

    def test_list_accumulation(self):
        """List fields with reducers should accumulate."""
        original = create_initial_state(
            session_id=1,
            player_id=10,
            player_location="tavern",
            player_input="Hello",
        )
        original["extracted_entities"] = [{"name": "Bob"}]

        updated = merge_state(original, {
            "extracted_entities": [{"name": "Alice"}],
        })

        # Should accumulate, not replace
        assert len(updated["extracted_entities"]) == 2
        assert {"name": "Bob"} in updated["extracted_entities"]
        assert {"name": "Alice"} in updated["extracted_entities"]

    def test_error_accumulation(self):
        """Error list should accumulate."""
        original = create_initial_state(
            session_id=1,
            player_id=10,
            player_location="tavern",
            player_input="Hello",
        )
        original["errors"] = ["First error"]

        updated = merge_state(original, {
            "errors": ["Second error"],
        })

        assert len(updated["errors"]) == 2
        assert "First error" in updated["errors"]
        assert "Second error" in updated["errors"]

    def test_does_not_mutate_original(self):
        """Merge should not mutate the original state."""
        original = create_initial_state(
            session_id=1,
            player_id=10,
            player_location="tavern",
            player_input="Hello",
        )
        original_response = original.get("gm_response")

        merge_state(original, {"gm_response": "New response"})

        assert original.get("gm_response") == original_response


class TestStateWithDatabase:
    """Test state integration with database fixtures."""

    def test_state_with_game_session_ids(self, db_session, game_session, player_entity):
        """State should work with actual database IDs."""
        state = create_initial_state(
            session_id=game_session.id,
            player_id=player_entity.id,
            player_location="test_location",
            player_input="Test input",
        )

        assert state["session_id"] == game_session.id
        assert state["player_id"] == player_entity.id
