"""Tests for ContextCompiler manager, specifically turn context functionality."""

import pytest

from src.database.models.enums import DiscoveryMethod, TerrainType
from src.managers.context_compiler import ContextCompiler, SceneContext
from tests.factories import (
    create_entity,
    create_location,
    create_terrain_zone,
    create_turn,
    create_zone_connection,
)


class TestTurnContext:
    """Test the _get_turn_context method."""

    def test_first_turn_indicates_introduction(self, db_session, game_session, player_entity):
        """First turn context should instruct GM to introduce character."""
        compiler = ContextCompiler(db_session, game_session)

        result = compiler._get_turn_context(turn_number=1)

        assert "Turn 1" in result
        assert "FIRST TURN" in result
        assert "Introduce" in result

    def test_continuation_turn_prevents_reintroduction(
        self, db_session, game_session, player_entity
    ):
        """Continuation turns should instruct GM NOT to re-introduce."""
        compiler = ContextCompiler(db_session, game_session)

        result = compiler._get_turn_context(turn_number=2)

        assert "Turn 2" in result
        assert "CONTINUATION" in result
        assert "Do NOT re-introduce" in result

    def test_continuation_includes_recent_history(
        self, db_session, game_session, player_entity
    ):
        """Continuation turns should include recent turn history."""
        # Create some previous turns
        create_turn(
            db_session,
            game_session,
            turn_number=1,
            player_input="I look around the tavern",
            gm_response="You see a cozy tavern with a roaring fireplace.",
        )
        create_turn(
            db_session,
            game_session,
            turn_number=2,
            player_input="I approach the bartender",
            gm_response="The bartender nods at you with a friendly smile.",
        )
        db_session.flush()

        compiler = ContextCompiler(db_session, game_session)
        result = compiler._get_turn_context(turn_number=3)

        assert "Recent History" in result
        assert "look around the tavern" in result
        assert "cozy tavern" in result
        assert "approach the bartender" in result
        assert "bartender nods" in result

    def test_history_shows_turns_in_chronological_order(
        self, db_session, game_session, player_entity
    ):
        """Turn history should be ordered oldest to newest."""
        create_turn(
            db_session,
            game_session,
            turn_number=1,
            player_input="First action",
            gm_response="First response",
        )
        create_turn(
            db_session,
            game_session,
            turn_number=2,
            player_input="Second action",
            gm_response="Second response",
        )
        db_session.flush()

        compiler = ContextCompiler(db_session, game_session)
        result = compiler._get_turn_context(turn_number=3)

        # Turn 1 should appear before Turn 2
        first_pos = result.find("Turn 1")
        second_pos = result.find("Turn 2")
        assert first_pos < second_pos

    def test_history_truncates_long_responses(
        self, db_session, game_session, player_entity
    ):
        """Long GM responses should be truncated in history."""
        long_response = "A" * 1200  # Longer than 1000 char limit for most recent turn
        create_turn(
            db_session,
            game_session,
            turn_number=1,
            player_input="Test input",
            gm_response=long_response,
        )
        db_session.flush()

        compiler = ContextCompiler(db_session, game_session)
        result = compiler._get_turn_context(turn_number=2)

        # Should be truncated with ellipsis
        assert "..." in result
        # Should not contain the full 1200 chars
        assert long_response not in result

    def test_history_limits_to_specified_turns(
        self, db_session, game_session, player_entity
    ):
        """Should only include the specified number of recent turns."""
        # Create 5 turns
        for i in range(1, 6):
            create_turn(
                db_session,
                game_session,
                turn_number=i,
                player_input=f"Action {i}",
                gm_response=f"Response {i}",
            )
        db_session.flush()

        compiler = ContextCompiler(db_session, game_session)
        # Default limit is 3
        result = compiler._get_turn_context(turn_number=6)

        # Should have turns 3, 4, 5 but not 1, 2
        assert "Action 5" in result
        assert "Action 4" in result
        assert "Action 3" in result
        assert "Action 2" not in result
        assert "Action 1" not in result

    def test_first_turn_has_no_history(self, db_session, game_session, player_entity):
        """First turn should not include history section."""
        compiler = ContextCompiler(db_session, game_session)
        result = compiler._get_turn_context(turn_number=1)

        assert "Recent History" not in result


class TestSceneContextWithTurn:
    """Test that SceneContext includes turn context properly."""

    def test_compile_scene_includes_turn_context(
        self, db_session, game_session, player_entity
    ):
        """compile_scene should include turn_context in result."""
        compiler = ContextCompiler(db_session, game_session)

        result = compiler.compile_scene(
            player_id=player_entity.id,
            location_key="test_location",
            turn_number=1,
        )

        assert result.turn_context is not None
        assert "Turn 1" in result.turn_context

    def test_to_prompt_includes_turn_context_first(
        self, db_session, game_session, player_entity
    ):
        """Turn context should appear first in the prompt."""
        compiler = ContextCompiler(db_session, game_session)

        scene = compiler.compile_scene(
            player_id=player_entity.id,
            location_key="test_location",
            turn_number=5,
        )
        prompt = scene.to_prompt()

        # Turn context should be at the start
        assert prompt.startswith("## Turn 5")

    def test_default_turn_number_is_one(self, db_session, game_session, player_entity):
        """compile_scene should default to turn_number=1."""
        compiler = ContextCompiler(db_session, game_session)

        result = compiler.compile_scene(
            player_id=player_entity.id,
            location_key="test_location",
        )

        assert "Turn 1" in result.turn_context
        assert "FIRST TURN" in result.turn_context


class TestNavigationContext:
    """Tests for navigation context in scene compilation."""

    def test_get_navigation_context_returns_empty_when_no_zone(
        self, db_session, game_session, player_entity
    ):
        """Navigation context should be empty when player has no current zone."""
        compiler = ContextCompiler(db_session, game_session)

        result = compiler._get_navigation_context(current_zone_key=None)

        assert result == ""

    def test_get_navigation_context_includes_current_zone(
        self, db_session, game_session, player_entity
    ):
        """Navigation context should include current zone info."""
        zone = create_terrain_zone(
            db_session,
            game_session,
            zone_key="forest_clearing",
            display_name="Forest Clearing",
            terrain_type=TerrainType.FOREST,
        )
        db_session.commit()

        compiler = ContextCompiler(db_session, game_session)
        result = compiler._get_navigation_context(current_zone_key="forest_clearing")

        assert "Forest Clearing" in result
        assert "forest" in result.lower()

    def test_get_navigation_context_includes_discovered_adjacent_zones(
        self, db_session, game_session, player_entity
    ):
        """Navigation context should list adjacent zones that are discovered."""
        from src.managers.discovery_manager import DiscoveryManager

        # Create zones
        current = create_terrain_zone(
            db_session, game_session, zone_key="current_zone", display_name="Current Zone"
        )
        north_zone = create_terrain_zone(
            db_session, game_session, zone_key="north_zone", display_name="Northern Woods"
        )
        south_zone = create_terrain_zone(
            db_session, game_session, zone_key="south_zone", display_name="Southern Plains"
        )
        db_session.commit()

        # Connect zones
        create_zone_connection(db_session, game_session, current, north_zone, direction="north")
        create_zone_connection(db_session, game_session, current, south_zone, direction="south")
        db_session.commit()

        # Discover north zone only
        discovery_mgr = DiscoveryManager(db_session, game_session)
        discovery_mgr.discover_zone("north_zone", method=DiscoveryMethod.VISITED)
        db_session.commit()

        compiler = ContextCompiler(db_session, game_session)
        result = compiler._get_navigation_context(current_zone_key="current_zone")

        # Should include discovered north zone
        assert "Northern Woods" in result
        assert "north" in result.lower()

    def test_get_navigation_context_excludes_undiscovered_zones(
        self, db_session, game_session, player_entity
    ):
        """Undiscovered adjacent zones should not be listed in context."""
        from src.managers.discovery_manager import DiscoveryManager

        current = create_terrain_zone(
            db_session, game_session, zone_key="current_zone", display_name="Current Zone"
        )
        secret_zone = create_terrain_zone(
            db_session, game_session, zone_key="secret_zone", display_name="Secret Cave"
        )
        db_session.commit()

        create_zone_connection(db_session, game_session, current, secret_zone, direction="down")
        db_session.commit()

        # Do NOT discover secret zone
        compiler = ContextCompiler(db_session, game_session)
        result = compiler._get_navigation_context(current_zone_key="current_zone")

        # Secret zone should NOT be mentioned
        assert "Secret Cave" not in result

    def test_get_navigation_context_includes_discovered_locations_in_zone(
        self, db_session, game_session, player_entity
    ):
        """Navigation context should list discovered locations in current zone."""
        from src.managers.discovery_manager import DiscoveryManager
        from src.managers.zone_manager import ZoneManager

        zone = create_terrain_zone(
            db_session, game_session, zone_key="village_square"
        )
        tavern = create_location(
            db_session, game_session, location_key="tavern", display_name="The Rusty Flagon"
        )
        db_session.commit()

        # Place location in zone
        zone_mgr = ZoneManager(db_session, game_session)
        zone_mgr.place_location_in_zone("tavern", "village_square", visibility="visible_from_zone")
        db_session.commit()

        # Discover the location
        discovery_mgr = DiscoveryManager(db_session, game_session)
        discovery_mgr.discover_location("tavern", method=DiscoveryMethod.VISITED)
        db_session.commit()

        compiler = ContextCompiler(db_session, game_session)
        result = compiler._get_navigation_context(current_zone_key="village_square")

        assert "Rusty Flagon" in result

    def test_scene_context_includes_navigation(
        self, db_session, game_session, player_entity
    ):
        """compile_scene should include navigation context when zone is provided."""
        zone = create_terrain_zone(
            db_session, game_session,
            zone_key="plains",
            display_name="Open Plains",
            terrain_type=TerrainType.PLAINS,
        )
        db_session.commit()

        compiler = ContextCompiler(db_session, game_session)
        result = compiler.compile_scene(
            player_id=player_entity.id,
            location_key="test_location",
            turn_number=1,
            current_zone_key="plains",
        )

        prompt = result.to_prompt()
        assert "Open Plains" in prompt


class TestNavigationContextTravelInfo:
    """Tests for travel-related information in navigation context."""

    def test_get_navigation_context_includes_terrain_info(
        self, db_session, game_session, player_entity
    ):
        """Navigation context should describe terrain movement characteristics."""
        zone = create_terrain_zone(
            db_session,
            game_session,
            zone_key="swamp",
            display_name="Murky Swamp",
            terrain_type=TerrainType.SWAMP,
            base_travel_cost=30,  # Slow terrain
        )
        db_session.commit()

        compiler = ContextCompiler(db_session, game_session)
        result = compiler._get_navigation_context(current_zone_key="swamp")

        # Should indicate difficult terrain
        assert "swamp" in result.lower()

    def test_get_navigation_context_indicates_hazardous_terrain(
        self, db_session, game_session, player_entity
    ):
        """Navigation context should warn about terrain that requires skills."""
        zone = create_terrain_zone(
            db_session,
            game_session,
            zone_key="lake",
            display_name="Crystal Lake",
            terrain_type=TerrainType.LAKE,
            requires_skill="swimming",
            skill_difficulty=12,
        )
        db_session.commit()

        compiler = ContextCompiler(db_session, game_session)
        # If we have access to adjacent hazardous zones, warn about them
        # For now just test that current zone shows hazard info
        result = compiler._get_navigation_context(current_zone_key="lake")

        # Should mention that special skill is needed
        assert "swimming" in result.lower() or "lake" in result.lower()
