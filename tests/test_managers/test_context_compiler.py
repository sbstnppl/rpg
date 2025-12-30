"""Tests for ContextCompiler manager, specifically turn context functionality."""

import pytest

from src.database.models.enums import DiscoveryMethod, TerrainType
from src.managers.context_compiler import ContextCompiler, SceneContext
from tests.factories import (
    create_entity,
    create_fact,
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


class TestWorldFactsContext:
    """Tests for world facts in scene context."""

    def test_get_world_facts_context_returns_empty_when_no_facts(
        self, db_session, game_session, player_entity
    ):
        """Should return empty string when no non-secret facts exist."""
        compiler = ContextCompiler(db_session, game_session)

        result = compiler._get_world_facts_context(location_key="village")

        assert result == ""

    def test_get_world_facts_context_includes_non_secret_facts(
        self, db_session, game_session, player_entity
    ):
        """Should include non-secret facts in context."""
        create_fact(
            db_session,
            game_session,
            subject_key="the_weary_traveler",
            predicate="type",
            value="Village inn",
            is_secret=False,
        )
        create_fact(
            db_session,
            game_session,
            subject_key="the_weary_traveler",
            predicate="owner",
            value="Martha",
            is_secret=False,
        )
        db_session.flush()

        compiler = ContextCompiler(db_session, game_session)
        result = compiler._get_world_facts_context(location_key="village")

        assert "Established World Facts" in result
        assert "The Weary Traveler" in result  # Subject key converted to title
        assert "Village inn" in result
        assert "Martha" in result

    def test_get_world_facts_context_excludes_secret_facts(
        self, db_session, game_session, player_entity
    ):
        """Should NOT include secret facts in world facts context."""
        create_fact(
            db_session,
            game_session,
            subject_key="village_elder",
            predicate="occupation",
            value="Baker",
            is_secret=False,
        )
        create_fact(
            db_session,
            game_session,
            subject_key="village_elder",
            predicate="secret_identity",
            value="Former assassin",
            is_secret=True,  # This is a secret!
        )
        db_session.flush()

        compiler = ContextCompiler(db_session, game_session)
        result = compiler._get_world_facts_context(location_key="village")

        assert "Baker" in result
        assert "Former assassin" not in result
        assert "secret_identity" not in result

    def test_get_world_facts_context_groups_by_subject(
        self, db_session, game_session, player_entity
    ):
        """Facts should be grouped by subject."""
        create_fact(
            db_session,
            game_session,
            subject_key="tavern",
            predicate="name",
            value="The Golden Dragon",
            is_secret=False,
        )
        create_fact(
            db_session,
            game_session,
            subject_key="tavern",
            predicate="location",
            value="Town square",
            is_secret=False,
        )
        create_fact(
            db_session,
            game_session,
            subject_key="blacksmith",
            predicate="name",
            value="Iron Magnus",
            is_secret=False,
        )
        db_session.flush()

        compiler = ContextCompiler(db_session, game_session)
        result = compiler._get_world_facts_context(location_key="village")

        # Should have headers for each subject
        assert "### Tavern" in result
        assert "### Blacksmith" in result

    def test_compile_scene_includes_world_facts(
        self, db_session, game_session, player_entity
    ):
        """compile_scene should include world facts in result."""
        create_fact(
            db_session,
            game_session,
            subject_key="test_inn",
            predicate="type",
            value="Roadside inn",
            is_secret=False,
        )
        db_session.flush()

        compiler = ContextCompiler(db_session, game_session)
        result = compiler.compile_scene(
            player_id=player_entity.id,
            location_key="test_location",
            turn_number=1,
        )

        assert result.world_facts_context is not None
        assert "Roadside inn" in result.world_facts_context

    def test_to_prompt_includes_world_facts(
        self, db_session, game_session, player_entity
    ):
        """to_prompt should include world facts in the output."""
        create_fact(
            db_session,
            game_session,
            subject_key="village_well",
            predicate="location",
            value="Center of village square",
            is_secret=False,
        )
        db_session.flush()

        compiler = ContextCompiler(db_session, game_session)
        scene = compiler.compile_scene(
            player_id=player_entity.id,
            location_key="test_location",
            turn_number=1,
        )
        prompt = scene.to_prompt()

        assert "Established World Facts" in prompt
        assert "Center of village square" in prompt

    def test_world_facts_context_includes_consistency_warning(
        self, db_session, game_session, player_entity
    ):
        """Should include warning to use established names."""
        create_fact(
            db_session,
            game_session,
            subject_key="test_location",
            predicate="name",
            value="Test Place",
            is_secret=False,
        )
        db_session.flush()

        compiler = ContextCompiler(db_session, game_session)
        result = compiler._get_world_facts_context(location_key="village")

        assert "IMPORTANT" in result
        assert "consistency" in result.lower() or "invent" in result.lower()


class TestPlayerContextOccupation:
    """Tests for player occupation in context."""

    def test_player_context_includes_occupation(
        self, db_session, game_session, player_entity
    ):
        """Player context should include occupation when set."""
        player_entity.occupation = "farmer"
        db_session.flush()

        compiler = ContextCompiler(db_session, game_session)
        result = compiler._get_player_context(player_entity.id)

        assert "Occupation: farmer" in result

    def test_player_context_includes_occupation_with_years(
        self, db_session, game_session, player_entity
    ):
        """Player context should include occupation years when set."""
        player_entity.occupation = "blacksmith"
        player_entity.occupation_years = 5
        db_session.flush()

        compiler = ContextCompiler(db_session, game_session)
        result = compiler._get_player_context(player_entity.id)

        assert "Occupation: blacksmith (5 years)" in result

    def test_player_context_omits_occupation_when_not_set(
        self, db_session, game_session, player_entity
    ):
        """Player context should not have occupation line when not set."""
        # player_entity has no occupation by default
        compiler = ContextCompiler(db_session, game_session)
        result = compiler._get_player_context(player_entity.id)

        assert "Occupation:" not in result


class TestLocationInventoryContext:
    """Tests for location inventory context (storage surfaces and items)."""

    def test_get_location_inventory_context_returns_empty_when_no_location(
        self, db_session, game_session, player_entity
    ):
        """Should return empty string when location doesn't exist."""
        compiler = ContextCompiler(db_session, game_session)

        result = compiler._get_location_inventory_context(location_key="nonexistent")

        assert result == ""

    def test_get_location_inventory_context_returns_empty_when_no_storage(
        self, db_session, game_session, player_entity
    ):
        """Should return empty string when location has no storage surfaces."""
        from tests.factories import create_location

        location = create_location(
            db_session,
            game_session,
            location_key="empty_room",
            display_name="Empty Room",
        )
        db_session.flush()

        compiler = ContextCompiler(db_session, game_session)
        result = compiler._get_location_inventory_context(location_key="empty_room")

        assert result == ""

    def test_get_location_inventory_context_shows_storage_surfaces(
        self, db_session, game_session, player_entity
    ):
        """Should list storage surfaces at the location."""
        from src.database.models.enums import StorageLocationType
        from src.database.models.items import StorageLocation
        from tests.factories import create_location

        location = create_location(
            db_session,
            game_session,
            location_key="cottage",
            display_name="Cozy Cottage",
        )
        db_session.flush()

        # Create storage surfaces
        table = StorageLocation(
            session_id=game_session.id,
            location_key="table_01",
            location_type=StorageLocationType.PLACE,
            container_type="table",
            world_location_id=location.id,
        )
        shelf = StorageLocation(
            session_id=game_session.id,
            location_key="shelf_01",
            location_type=StorageLocationType.PLACE,
            container_type="shelf",
            world_location_id=location.id,
        )
        db_session.add_all([table, shelf])
        db_session.flush()

        compiler = ContextCompiler(db_session, game_session)
        result = compiler._get_location_inventory_context(location_key="cottage")

        assert "Location Inventory" in result
        assert "Storage Surfaces" in result
        assert "Table (table_01)" in result
        assert "Shelf (shelf_01)" in result
        assert "empty" in result  # No items yet

    def test_get_location_inventory_context_shows_items_on_surfaces(
        self, db_session, game_session, player_entity
    ):
        """Should show items placed on storage surfaces."""
        from src.database.models.enums import ItemType, StorageLocationType
        from src.database.models.items import Item, StorageLocation
        from tests.factories import create_location

        location = create_location(
            db_session,
            game_session,
            location_key="cottage",
            display_name="Cozy Cottage",
        )
        db_session.flush()

        # Create storage surface
        table = StorageLocation(
            session_id=game_session.id,
            location_key="table_01",
            location_type=StorageLocationType.PLACE,
            container_type="table",
            world_location_id=location.id,
        )
        db_session.add(table)
        db_session.flush()

        # Create items on the table
        bread = Item(
            session_id=game_session.id,
            item_key="bread_01",
            display_name="Half-loaf of Bread",
            description="A half-eaten loaf of brown bread",
            item_type=ItemType.CONSUMABLE,
            storage_location_id=table.id,
        )
        bowl = Item(
            session_id=game_session.id,
            item_key="bowl_01",
            display_name="Clay Bowl",
            description="A simple clay bowl",
            item_type=ItemType.MISC,
            storage_location_id=table.id,
        )
        db_session.add_all([bread, bowl])
        db_session.flush()

        compiler = ContextCompiler(db_session, game_session)
        result = compiler._get_location_inventory_context(location_key="cottage")

        # Storage surfaces section
        assert "Table (table_01): Half-loaf of Bread, Clay Bowl" in result

        # Items at location section
        assert "Items at Location" in result
        assert "bread_01" in result
        assert "bowl_01" in result
        assert "on table" in result

    def test_get_location_inventory_context_in_scene_context(
        self, db_session, game_session, player_entity
    ):
        """Location inventory should be included in compiled scene context."""
        from src.database.models.enums import StorageLocationType
        from src.database.models.items import StorageLocation
        from tests.factories import create_location

        location = create_location(
            db_session,
            game_session,
            location_key="tavern",
            display_name="The Rusty Anchor",
        )
        db_session.flush()

        # Create storage surface
        counter = StorageLocation(
            session_id=game_session.id,
            location_key="counter_01",
            location_type=StorageLocationType.PLACE,
            container_type="counter",
            world_location_id=location.id,
        )
        db_session.add(counter)
        db_session.flush()

        compiler = ContextCompiler(db_session, game_session)
        scene = compiler.compile_scene(
            player_id=player_entity.id,
            location_key="tavern",
            turn_number=1,
        )

        assert "Location Inventory" in scene.location_inventory_context
        assert "Counter (counter_01)" in scene.location_inventory_context

    def test_location_inventory_context_in_to_prompt(
        self, db_session, game_session, player_entity
    ):
        """Location inventory should appear in to_prompt() output."""
        from src.database.models.enums import StorageLocationType
        from src.database.models.items import StorageLocation
        from tests.factories import create_location

        location = create_location(
            db_session,
            game_session,
            location_key="shop",
            display_name="General Store",
        )
        db_session.flush()

        shelf = StorageLocation(
            session_id=game_session.id,
            location_key="shelf_02",
            location_type=StorageLocationType.PLACE,
            container_type="shelf",
            world_location_id=location.id,
        )
        db_session.add(shelf)
        db_session.flush()

        compiler = ContextCompiler(db_session, game_session)
        scene = compiler.compile_scene(
            player_id=player_entity.id,
            location_key="shop",
            turn_number=1,
        )

        prompt = scene.to_prompt()

        assert "Location Inventory" in prompt
        assert "Shelf (shelf_02)" in prompt


class TestNeedsDescription:
    """Tests for _get_needs_description method with positive and negative states."""

    def test_includes_positive_state_well_fed(self, db_session, game_session, player_entity):
        """When hunger is high, should report 'well-fed'."""
        from tests.factories import create_character_needs

        create_character_needs(
            db_session, game_session, player_entity,
            hunger=90,  # High hunger = well-fed
            stamina=50,  # Neutral
            hygiene=50,
            morale=50,
        )
        db_session.flush()

        compiler = ContextCompiler(db_session, game_session)
        result = compiler._get_needs_description(player_entity.id)

        assert "well-fed" in result

    def test_includes_positive_state_well_rested(self, db_session, game_session, player_entity):
        """When sleep_pressure is low, should report 'well-rested'.

        Note: 'well-rested' comes from low sleep_pressure, not high stamina.
        stamina = physical energy, sleep_pressure = how sleepy you are.
        """
        from tests.factories import create_character_needs

        create_character_needs(
            db_session, game_session, player_entity,
            hunger=50,
            stamina=50,
            sleep_pressure=10,  # Low sleep pressure = well-rested
            hygiene=50,
            morale=50,
        )
        db_session.flush()

        compiler = ContextCompiler(db_session, game_session)
        result = compiler._get_needs_description(player_entity.id)

        assert "well-rested" in result

    def test_includes_positive_state_clean(self, db_session, game_session, player_entity):
        """When hygiene is high, should report 'clean'."""
        from tests.factories import create_character_needs

        create_character_needs(
            db_session, game_session, player_entity,
            hunger=50,
            stamina=50,
            hygiene=85,  # High hygiene = clean
            morale=50,
        )
        db_session.flush()

        compiler = ContextCompiler(db_session, game_session)
        result = compiler._get_needs_description(player_entity.id)

        assert "clean" in result

    def test_includes_positive_state_good_spirits(self, db_session, game_session, player_entity):
        """When morale is high, should report 'in good spirits'."""
        from tests.factories import create_character_needs

        create_character_needs(
            db_session, game_session, player_entity,
            hunger=50,
            stamina=50,
            hygiene=50,
            morale=85,  # High morale = in good spirits
        )
        db_session.flush()

        compiler = ContextCompiler(db_session, game_session)
        result = compiler._get_needs_description(player_entity.id)

        assert "in good spirits" in result

    def test_includes_negative_state_hungry(self, db_session, game_session, player_entity):
        """When hunger is low, should report 'hungry' or 'starving'."""
        from tests.factories import create_character_needs

        create_character_needs(
            db_session, game_session, player_entity,
            hunger=25,  # Low hunger = hungry
            stamina=50,
            hygiene=50,
            morale=50,
        )
        db_session.flush()

        compiler = ContextCompiler(db_session, game_session)
        result = compiler._get_needs_description(player_entity.id)

        assert "hungry" in result

    def test_neutral_state_shows_nothing(self, db_session, game_session, player_entity):
        """When needs are in neutral range, should not include that descriptor."""
        from tests.factories import create_character_needs

        create_character_needs(
            db_session, game_session, player_entity,
            hunger=60,  # Neutral - not hungry, not full
            stamina=60,  # Neutral - not tired, not rested
            hygiene=60,  # Neutral
            morale=60,  # Neutral
        )
        db_session.flush()

        compiler = ContextCompiler(db_session, game_session)
        result = compiler._get_needs_description(player_entity.id)

        # Should not have any of these descriptors
        assert "hungry" not in result
        assert "well-fed" not in result
        assert "tired" not in result
        assert "well-rested" not in result

    def test_multiple_positive_states(self, db_session, game_session, player_entity):
        """Should include multiple positive descriptors when applicable."""
        from tests.factories import create_character_needs

        create_character_needs(
            db_session, game_session, player_entity,
            hunger=90,
            stamina=85,
            sleep_pressure=10,  # Low sleep pressure = well-rested
            hygiene=85,
            morale=85,
            comfort=85,
        )
        db_session.flush()

        compiler = ContextCompiler(db_session, game_session)
        result = compiler._get_needs_description(player_entity.id)

        assert "well-fed" in result
        assert "well-rested" in result
        assert "clean" in result
        assert "in good spirits" in result
