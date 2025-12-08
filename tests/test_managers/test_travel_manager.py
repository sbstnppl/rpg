"""Tests for TravelManager - journey simulation and travel mechanics."""

import pytest

from src.database.models.enums import EncounterFrequency, TerrainType
from src.managers.travel_manager import TravelManager, JourneyState
from tests.factories import (
    create_terrain_zone,
    create_transport_mode,
    create_zone_connection,
)


class TestTravelManagerJourneyStart:
    """Tests for starting journeys."""

    def test_start_journey_creates_journey_state(self, db_session, game_session):
        """start_journey should create a JourneyState."""
        zone_a = create_terrain_zone(db_session, game_session, zone_key="zone_a")
        zone_b = create_terrain_zone(db_session, game_session, zone_key="zone_b")
        db_session.flush()
        create_zone_connection(db_session, game_session, zone_a, zone_b, direction="east")
        db_session.commit()

        manager = TravelManager(db_session, game_session)
        result = manager.start_journey("zone_a", "zone_b", "walking")

        assert result["success"] is True
        assert result["journey"] is not None
        assert result["journey"].current_zone_key == "zone_a"
        assert result["journey"].destination_zone_key == "zone_b"
        assert result["journey"].transport_mode == "walking"

    def test_start_journey_calculates_path(self, db_session, game_session):
        """start_journey should calculate and store the path."""
        zone_a = create_terrain_zone(db_session, game_session, zone_key="zone_a")
        zone_b = create_terrain_zone(db_session, game_session, zone_key="zone_b")
        zone_c = create_terrain_zone(db_session, game_session, zone_key="zone_c")
        db_session.flush()
        create_zone_connection(db_session, game_session, zone_a, zone_b, direction="east")
        create_zone_connection(db_session, game_session, zone_b, zone_c, direction="east")
        db_session.commit()

        manager = TravelManager(db_session, game_session)
        result = manager.start_journey("zone_a", "zone_c", "walking")

        assert result["success"] is True
        path_keys = [z.zone_key for z in result["journey"].path]
        assert path_keys == ["zone_a", "zone_b", "zone_c"]

    def test_start_journey_no_path_fails(self, db_session, game_session):
        """start_journey should fail if no path exists."""
        create_terrain_zone(db_session, game_session, zone_key="zone_a")
        create_terrain_zone(db_session, game_session, zone_key="zone_b")
        db_session.commit()

        manager = TravelManager(db_session, game_session)
        result = manager.start_journey("zone_a", "zone_b", "walking")

        assert result["success"] is False
        assert "no path" in result["reason"].lower()

    def test_start_journey_invalid_zones(self, db_session, game_session):
        """start_journey should handle invalid zone keys."""
        create_terrain_zone(db_session, game_session, zone_key="zone_a")
        db_session.commit()

        manager = TravelManager(db_session, game_session)
        result = manager.start_journey("zone_a", "nonexistent", "walking")

        assert result["success"] is False


class TestTravelManagerAdvance:
    """Tests for advancing through a journey."""

    def test_advance_travel_moves_to_next_zone(self, db_session, game_session):
        """advance_travel should move to the next zone in path."""
        zone_a = create_terrain_zone(
            db_session, game_session, zone_key="zone_a", base_travel_cost=10
        )
        zone_b = create_terrain_zone(
            db_session, game_session, zone_key="zone_b", base_travel_cost=10
        )
        zone_c = create_terrain_zone(
            db_session, game_session, zone_key="zone_c", base_travel_cost=10
        )
        db_session.flush()
        create_zone_connection(db_session, game_session, zone_a, zone_b, direction="east")
        create_zone_connection(db_session, game_session, zone_b, zone_c, direction="east")
        db_session.commit()

        manager = TravelManager(db_session, game_session)
        start_result = manager.start_journey("zone_a", "zone_c", "walking")
        journey = start_result["journey"]

        # Advance to next zone
        advance_result = manager.advance_travel(journey)

        assert advance_result["success"] is True
        assert journey.current_zone_key == "zone_b"
        assert journey.path_index == 1

    def test_advance_travel_tracks_elapsed_time(self, db_session, game_session):
        """advance_travel should accumulate elapsed time."""
        zone_a = create_terrain_zone(
            db_session, game_session, zone_key="zone_a", base_travel_cost=15
        )
        zone_b = create_terrain_zone(
            db_session, game_session, zone_key="zone_b", base_travel_cost=20
        )
        db_session.flush()
        create_zone_connection(
            db_session, game_session, zone_a, zone_b, direction="east", crossing_minutes=5
        )
        db_session.commit()

        manager = TravelManager(db_session, game_session)
        start_result = manager.start_journey("zone_a", "zone_b", "walking")
        journey = start_result["journey"]

        advance_result = manager.advance_travel(journey)

        assert journey.elapsed_minutes > 0
        # Time should include zone cost + crossing cost
        assert journey.elapsed_minutes == 20 + 5  # zone_b cost + crossing

    def test_advance_travel_detects_arrival(self, db_session, game_session):
        """advance_travel should detect when destination is reached."""
        zone_a = create_terrain_zone(db_session, game_session, zone_key="zone_a")
        zone_b = create_terrain_zone(db_session, game_session, zone_key="zone_b")
        db_session.flush()
        create_zone_connection(db_session, game_session, zone_a, zone_b, direction="east")
        db_session.commit()

        manager = TravelManager(db_session, game_session)
        start_result = manager.start_journey("zone_a", "zone_b", "walking")
        journey = start_result["journey"]

        advance_result = manager.advance_travel(journey)

        assert advance_result["success"] is True
        assert advance_result["arrived"] is True
        assert journey.is_complete is True

    def test_advance_travel_returns_zone_description(self, db_session, game_session):
        """advance_travel should return info about the entered zone."""
        zone_a = create_terrain_zone(db_session, game_session, zone_key="zone_a")
        zone_b = create_terrain_zone(
            db_session,
            game_session,
            zone_key="zone_b",
            display_name="Dark Forest",
            description="A dense, shadowy forest.",
            atmosphere="The trees creak ominously.",
        )
        db_session.flush()
        create_zone_connection(db_session, game_session, zone_a, zone_b, direction="east")
        db_session.commit()

        manager = TravelManager(db_session, game_session)
        start_result = manager.start_journey("zone_a", "zone_b", "walking")
        journey = start_result["journey"]

        advance_result = manager.advance_travel(journey)

        assert "zone_info" in advance_result
        assert advance_result["zone_info"]["display_name"] == "Dark Forest"
        assert advance_result["zone_info"]["description"] == "A dense, shadowy forest."


class TestTravelManagerEncounters:
    """Tests for encounter rolling during travel."""

    def test_advance_travel_rolls_encounters(self, db_session, game_session):
        """advance_travel should roll for random encounters."""
        zone_a = create_terrain_zone(db_session, game_session, zone_key="zone_a")
        zone_b = create_terrain_zone(
            db_session,
            game_session,
            zone_key="zone_b",
            encounter_frequency=EncounterFrequency.HIGH,
        )
        db_session.flush()
        create_zone_connection(db_session, game_session, zone_a, zone_b, direction="east")
        db_session.commit()

        manager = TravelManager(db_session, game_session)
        start_result = manager.start_journey("zone_a", "zone_b", "walking")
        journey = start_result["journey"]

        advance_result = manager.advance_travel(journey)

        # encounter_check should always be present
        assert "encounter_check" in advance_result
        assert "rolled" in advance_result["encounter_check"]
        assert "threshold" in advance_result["encounter_check"]

    def test_encounter_frequency_affects_threshold(self, db_session, game_session):
        """Higher encounter frequency should have lower threshold."""
        zone_a = create_terrain_zone(db_session, game_session, zone_key="zone_a")
        zone_low = create_terrain_zone(
            db_session,
            game_session,
            zone_key="zone_low",
            encounter_frequency=EncounterFrequency.LOW,
        )
        zone_high = create_terrain_zone(
            db_session,
            game_session,
            zone_key="zone_high",
            encounter_frequency=EncounterFrequency.HIGH,
        )
        db_session.flush()
        create_zone_connection(db_session, game_session, zone_a, zone_low, direction="north")
        create_zone_connection(db_session, game_session, zone_a, zone_high, direction="south")
        db_session.commit()

        manager = TravelManager(db_session, game_session)

        # Check threshold for low frequency zone
        low_result = manager.start_journey("zone_a", "zone_low", "walking")
        low_advance = manager.advance_travel(low_result["journey"])

        # Check threshold for high frequency zone
        high_result = manager.start_journey("zone_a", "zone_high", "walking")
        high_advance = manager.advance_travel(high_result["journey"])

        # High frequency should have LOWER threshold (easier to trigger since roll >= threshold)
        assert high_advance["encounter_check"]["threshold"] < low_advance["encounter_check"]["threshold"]


class TestTravelManagerHazards:
    """Tests for hazardous terrain handling."""

    def test_advance_travel_detects_skill_requirement(self, db_session, game_session):
        """advance_travel should detect when a skill check is required."""
        zone_a = create_terrain_zone(db_session, game_session, zone_key="zone_a")
        zone_lake = create_terrain_zone(
            db_session,
            game_session,
            zone_key="lake",
            terrain_type=TerrainType.LAKE,
            requires_skill="swimming",
            skill_difficulty=12,
            failure_consequence="drowning",
        )
        db_session.flush()
        create_zone_connection(db_session, game_session, zone_a, zone_lake, direction="north")
        db_session.commit()

        manager = TravelManager(db_session, game_session)
        start_result = manager.start_journey("zone_a", "lake", "walking")
        journey = start_result["journey"]

        advance_result = manager.advance_travel(journey)

        assert "skill_check" in advance_result
        assert advance_result["skill_check"]["required"] is True
        assert advance_result["skill_check"]["skill"] == "swimming"
        assert advance_result["skill_check"]["difficulty"] == 12

    def test_blocked_zone_stops_travel(self, db_session, game_session):
        """advance_travel should stop if next zone is blocked."""
        zone_a = create_terrain_zone(db_session, game_session, zone_key="zone_a")
        zone_b = create_terrain_zone(db_session, game_session, zone_key="zone_b")
        zone_b.is_accessible = False
        zone_b.blocked_reason = "Landslide blocking the path"
        db_session.flush()
        create_zone_connection(db_session, game_session, zone_a, zone_b, direction="east")
        db_session.commit()

        manager = TravelManager(db_session, game_session)
        start_result = manager.start_journey("zone_a", "zone_b", "walking")

        # Should fail because the zone is blocked
        assert start_result["success"] is False or (
            start_result["success"] and "blocked" in str(start_result.get("warning", "")).lower()
        )


class TestTravelManagerInterrupt:
    """Tests for interrupting travel."""

    def test_interrupt_travel_stops_journey(self, db_session, game_session):
        """interrupt_travel should stop the journey at current location."""
        zone_a = create_terrain_zone(db_session, game_session, zone_key="zone_a")
        zone_b = create_terrain_zone(db_session, game_session, zone_key="zone_b")
        zone_c = create_terrain_zone(db_session, game_session, zone_key="zone_c")
        db_session.flush()
        create_zone_connection(db_session, game_session, zone_a, zone_b, direction="east")
        create_zone_connection(db_session, game_session, zone_b, zone_c, direction="east")
        db_session.commit()

        manager = TravelManager(db_session, game_session)
        start_result = manager.start_journey("zone_a", "zone_c", "walking")
        journey = start_result["journey"]

        # Advance once
        manager.advance_travel(journey)
        assert journey.current_zone_key == "zone_b"

        # Interrupt
        interrupt_result = manager.interrupt_travel(journey, "explore")

        assert interrupt_result["success"] is True
        assert journey.is_interrupted is True
        assert journey.current_zone_key == "zone_b"

    def test_interrupt_travel_returns_current_zone_info(self, db_session, game_session):
        """interrupt_travel should return info about current zone."""
        zone_a = create_terrain_zone(db_session, game_session, zone_key="zone_a")
        zone_b = create_terrain_zone(
            db_session,
            game_session,
            zone_key="zone_b",
            display_name="Crossroads",
        )
        zone_c = create_terrain_zone(db_session, game_session, zone_key="zone_c")
        db_session.flush()
        create_zone_connection(db_session, game_session, zone_a, zone_b, direction="east")
        create_zone_connection(db_session, game_session, zone_b, zone_c, direction="east")
        db_session.commit()

        manager = TravelManager(db_session, game_session)
        start_result = manager.start_journey("zone_a", "zone_c", "walking")
        journey = start_result["journey"]

        manager.advance_travel(journey)
        interrupt_result = manager.interrupt_travel(journey, "explore")

        assert "current_zone" in interrupt_result
        assert interrupt_result["current_zone"]["display_name"] == "Crossroads"


class TestTravelManagerJourneyState:
    """Tests for journey state tracking."""

    def test_get_journey_state_returns_progress(self, db_session, game_session):
        """get_journey_state should return current journey progress."""
        zone_a = create_terrain_zone(db_session, game_session, zone_key="zone_a")
        zone_b = create_terrain_zone(db_session, game_session, zone_key="zone_b")
        zone_c = create_terrain_zone(db_session, game_session, zone_key="zone_c")
        zone_d = create_terrain_zone(db_session, game_session, zone_key="zone_d")
        db_session.flush()
        create_zone_connection(db_session, game_session, zone_a, zone_b, direction="east")
        create_zone_connection(db_session, game_session, zone_b, zone_c, direction="east")
        create_zone_connection(db_session, game_session, zone_c, zone_d, direction="east")
        db_session.commit()

        manager = TravelManager(db_session, game_session)
        start_result = manager.start_journey("zone_a", "zone_d", "walking")
        journey = start_result["journey"]

        manager.advance_travel(journey)  # Move to zone_b

        state = manager.get_journey_state(journey)

        assert state["current_zone"] == "zone_b"
        assert state["destination"] == "zone_d"
        assert state["progress_percent"] > 0
        assert state["progress_percent"] < 100
        assert state["zones_remaining"] == 2  # zone_c and zone_d

    def test_journey_tracks_visited_zones(self, db_session, game_session):
        """Journey should track all visited zones."""
        zone_a = create_terrain_zone(db_session, game_session, zone_key="zone_a")
        zone_b = create_terrain_zone(db_session, game_session, zone_key="zone_b")
        zone_c = create_terrain_zone(db_session, game_session, zone_key="zone_c")
        db_session.flush()
        create_zone_connection(db_session, game_session, zone_a, zone_b, direction="east")
        create_zone_connection(db_session, game_session, zone_b, zone_c, direction="east")
        db_session.commit()

        manager = TravelManager(db_session, game_session)
        start_result = manager.start_journey("zone_a", "zone_c", "walking")
        journey = start_result["journey"]

        manager.advance_travel(journey)  # Move to zone_b
        manager.advance_travel(journey)  # Move to zone_c

        assert "zone_a" in journey.visited_zones
        assert "zone_b" in journey.visited_zones
        assert "zone_c" in journey.visited_zones


class TestTravelManagerResumeJourney:
    """Tests for resuming interrupted journeys."""

    def test_resume_journey_continues_from_current(self, db_session, game_session):
        """resume_journey should continue from current position."""
        zone_a = create_terrain_zone(db_session, game_session, zone_key="zone_a")
        zone_b = create_terrain_zone(db_session, game_session, zone_key="zone_b")
        zone_c = create_terrain_zone(db_session, game_session, zone_key="zone_c")
        db_session.flush()
        create_zone_connection(db_session, game_session, zone_a, zone_b, direction="east")
        create_zone_connection(db_session, game_session, zone_b, zone_c, direction="east")
        db_session.commit()

        manager = TravelManager(db_session, game_session)
        start_result = manager.start_journey("zone_a", "zone_c", "walking")
        journey = start_result["journey"]

        manager.advance_travel(journey)  # At zone_b
        manager.interrupt_travel(journey, "rest")

        # Resume
        resume_result = manager.resume_journey(journey)

        assert resume_result["success"] is True
        assert journey.is_interrupted is False

        # Should be able to continue
        advance_result = manager.advance_travel(journey)
        assert journey.current_zone_key == "zone_c"


class TestTravelManagerAdjacentExploration:
    """Tests for leaving the path to explore adjacent zones."""

    def test_detour_to_adjacent_zone(self, db_session, game_session):
        """Should be able to detour to an adjacent zone not on the path."""
        zone_a = create_terrain_zone(db_session, game_session, zone_key="zone_a")
        zone_b = create_terrain_zone(db_session, game_session, zone_key="zone_b")
        zone_c = create_terrain_zone(db_session, game_session, zone_key="zone_c")
        zone_forest = create_terrain_zone(
            db_session, game_session, zone_key="forest", display_name="Side Forest"
        )
        db_session.flush()
        create_zone_connection(db_session, game_session, zone_a, zone_b, direction="east")
        create_zone_connection(db_session, game_session, zone_b, zone_c, direction="east")
        create_zone_connection(db_session, game_session, zone_b, zone_forest, direction="north")
        db_session.commit()

        manager = TravelManager(db_session, game_session)
        start_result = manager.start_journey("zone_a", "zone_c", "walking")
        journey = start_result["journey"]

        manager.advance_travel(journey)  # At zone_b

        # Detour to forest
        detour_result = manager.detour_to_zone(journey, "forest")

        assert detour_result["success"] is True
        assert journey.current_zone_key == "forest"
        assert journey.is_interrupted is True

    def test_detour_fails_for_non_adjacent_zone(self, db_session, game_session):
        """detour_to_zone should fail for non-adjacent zones."""
        zone_a = create_terrain_zone(db_session, game_session, zone_key="zone_a")
        zone_b = create_terrain_zone(db_session, game_session, zone_key="zone_b")
        zone_far = create_terrain_zone(db_session, game_session, zone_key="far_zone")
        db_session.flush()
        create_zone_connection(db_session, game_session, zone_a, zone_b, direction="east")
        # far_zone is not connected
        db_session.commit()

        manager = TravelManager(db_session, game_session)
        start_result = manager.start_journey("zone_a", "zone_b", "walking")
        journey = start_result["journey"]

        detour_result = manager.detour_to_zone(journey, "far_zone")

        assert detour_result["success"] is False
        assert "not adjacent" in detour_result["reason"].lower()
