"""Integration tests for the Millbrook world data."""

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from src.database.models.entities import Entity, NPCExtension
from src.database.models.enums import DayOfWeek, EntityType
from src.database.models.items import Item
from src.database.models.navigation import TerrainZone, LocationZonePlacement
from src.database.models.session import GameSession
from src.database.models.world import Fact, Location, Schedule
from src.services.world_loader_extended import load_complete_world


# Path to the world data files
WORLD_DIR = Path(__file__).parent.parent.parent / "data" / "worlds"
WORLD_NAME = "millbrook"


class TestMillbrookWorldLoading:
    """Integration tests for loading the Millbrook world."""

    @pytest.fixture(autouse=True)
    def load_world(self, db_session: Session, game_session: GameSession):
        """Load the Millbrook world before each test."""
        self.results = load_complete_world(
            db_session, game_session, WORLD_DIR, WORLD_NAME
        )
        self.db = db_session
        self.session = game_session
        db_session.flush()

    def test_world_loads_without_errors(self):
        """Millbrook world should load without critical errors."""
        # Check world component
        assert self.results["world"].get("zones", 0) >= 8, "Should have at least 8 zones"
        assert self.results["world"].get("locations", 0) >= 12, "Should have at least 12 locations"

        # Check no critical errors in world loading
        world_errors = self.results["world"].get("errors", [])
        assert len(world_errors) == 0, f"World errors: {world_errors}"

    def test_npcs_load_correctly(self):
        """All 7 NPCs should load with their data."""
        npc_count = self.results["npcs"]["count"]
        assert npc_count >= 7, f"Expected 7+ NPCs, got {npc_count}"

        # Check no NPC loading errors
        npc_errors = self.results["npcs"].get("errors", [])
        assert len(npc_errors) == 0, f"NPC errors: {npc_errors}"

    def test_schedules_load_correctly(self):
        """NPC schedules should load correctly."""
        schedule_count = self.results["schedules"]["count"]
        assert schedule_count > 0, "Should have schedule entries"

        # Check no schedule loading errors
        sched_errors = self.results["schedules"].get("errors", [])
        assert len(sched_errors) == 0, f"Schedule errors: {sched_errors}"

    def test_items_load_correctly(self):
        """Starbound artifacts should load correctly."""
        item_count = self.results["items"]["count"]
        assert item_count >= 4, f"Expected 4+ items (artifacts), got {item_count}"

        # Check no item loading errors
        item_errors = self.results["items"].get("errors", [])
        assert len(item_errors) == 0, f"Item errors: {item_errors}"

    def test_facts_load_correctly(self):
        """World facts should load correctly."""
        fact_count = self.results["facts"]["count"]
        assert fact_count >= 10, f"Expected 10+ facts, got {fact_count}"

        # Check no fact loading errors
        fact_errors = self.results["facts"].get("errors", [])
        assert len(fact_errors) == 0, f"Fact errors: {fact_errors}"


class TestMillbrookZones:
    """Tests for Millbrook zone structure."""

    @pytest.fixture(autouse=True)
    def load_world(self, db_session: Session, game_session: GameSession):
        """Load the Millbrook world before each test."""
        load_complete_world(db_session, game_session, WORLD_DIR, WORLD_NAME)
        self.db = db_session
        self.session = game_session
        db_session.flush()

    def test_village_zone_exists(self):
        """Millbrook village zone should exist."""
        zone = (
            self.db.query(TerrainZone)
            .filter(
                TerrainZone.session_id == self.session.id,
                TerrainZone.zone_key == "millbrook_village",
            )
            .first()
        )
        assert zone is not None
        assert zone.display_name == "Millbrook Village"

    def test_forest_zone_exists(self):
        """Greywood Forest zone should exist."""
        zone = (
            self.db.query(TerrainZone)
            .filter(
                TerrainZone.session_id == self.session.id,
                TerrainZone.zone_key == "greywood_forest",
            )
            .first()
        )
        assert zone is not None
        assert zone.display_name == "Greywood Forest"

    def test_zone_hierarchy(self):
        """Zones should have proper parent relationships."""
        village = (
            self.db.query(TerrainZone)
            .filter(
                TerrainZone.session_id == self.session.id,
                TerrainZone.zone_key == "millbrook_village",
            )
            .first()
        )
        region = (
            self.db.query(TerrainZone)
            .filter(
                TerrainZone.session_id == self.session.id,
                TerrainZone.zone_key == "millbrook_region",
            )
            .first()
        )

        assert village is not None
        assert region is not None
        assert village.parent_zone_id == region.id


class TestMillbrookLocations:
    """Tests for Millbrook locations."""

    @pytest.fixture(autouse=True)
    def load_world(self, db_session: Session, game_session: GameSession):
        """Load the Millbrook world before each test."""
        load_complete_world(db_session, game_session, WORLD_DIR, WORLD_NAME)
        self.db = db_session
        self.session = game_session
        db_session.flush()

    def test_market_square_exists(self):
        """Market Square should exist with proper data."""
        location = (
            self.db.query(Location)
            .filter(
                Location.session_id == self.session.id,
                Location.location_key == "market_square",
            )
            .first()
        )
        assert location is not None
        assert location.display_name == "Market Square"
        assert "well" in location.description.lower()

    def test_dusty_flagon_exists(self):
        """Dusty Flagon tavern should exist."""
        location = (
            self.db.query(Location)
            .filter(
                Location.session_id == self.session.id,
                Location.location_key == "dusty_flagon",
            )
            .first()
        )
        assert location is not None
        assert location.display_name == "The Dusty Flagon"

    def test_chapel_exists(self):
        """Chapel of Light should exist."""
        location = (
            self.db.query(Location)
            .filter(
                Location.session_id == self.session.id,
                Location.location_key == "chapel_of_light",
            )
            .first()
        )
        assert location is not None

    def test_hidden_locations_exist(self):
        """Hidden locations should exist."""
        sealed_shrine = (
            self.db.query(Location)
            .filter(
                Location.session_id == self.session.id,
                Location.location_key == "sealed_shrine",
            )
            .first()
        )
        assert sealed_shrine is not None

        temple = (
            self.db.query(Location)
            .filter(
                Location.session_id == self.session.id,
                Location.location_key == "temple_dawn_star",
            )
            .first()
        )
        assert temple is not None


class TestMillbrookNPCs:
    """Tests for Millbrook NPCs."""

    @pytest.fixture(autouse=True)
    def load_world(self, db_session: Session, game_session: GameSession):
        """Load the Millbrook world before each test."""
        load_complete_world(db_session, game_session, WORLD_DIR, WORLD_NAME)
        self.db = db_session
        self.session = game_session
        db_session.flush()

    def test_old_aldric_exists(self):
        """Old Aldric the storyteller should exist with full data."""
        aldric = (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.session.id,
                Entity.entity_key == "old_aldric",
            )
            .first()
        )
        assert aldric is not None
        assert aldric.display_name == "Old Aldric"
        assert aldric.age == 78
        assert aldric.occupation == "village storyteller"

    def test_sister_maren_exists(self):
        """Sister Maren should exist."""
        maren = (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.session.id,
                Entity.entity_key == "sister_maren",
            )
            .first()
        )
        assert maren is not None
        assert maren.display_name == "Sister Maren"

    def test_hermit_exists(self):
        """The Hermit should exist with secret backstory."""
        hermit = (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.session.id,
                Entity.entity_key == "the_hermit",
            )
            .first()
        )
        assert hermit is not None
        assert hermit.display_name == "The Hermit"
        assert hermit.age == 94
        assert hermit.hidden_backstory is not None
        assert "Starfell" in hermit.hidden_backstory

    def test_npc_extensions_exist(self):
        """NPCs should have extension data."""
        tom = (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.session.id,
                Entity.entity_key == "tom_barkeep",
            )
            .first()
        )
        assert tom is not None

        ext = (
            self.db.query(NPCExtension)
            .filter(NPCExtension.entity_id == tom.id)
            .first()
        )
        assert ext is not None
        assert ext.job == "barkeep"
        assert ext.workplace == "flagon_common_room"

    def test_knowledge_areas_loaded(self):
        """NPCs with knowledge areas should have them in appearance JSON."""
        aldric = (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.session.id,
                Entity.entity_key == "old_aldric",
            )
            .first()
        )
        assert aldric is not None
        assert aldric.appearance is not None
        assert "knowledge_areas" in aldric.appearance
        assert "starbound_ballads" in aldric.appearance["knowledge_areas"]


class TestMillbrookSchedules:
    """Tests for Millbrook NPC schedules."""

    @pytest.fixture(autouse=True)
    def load_world(self, db_session: Session, game_session: GameSession):
        """Load the Millbrook world before each test."""
        load_complete_world(db_session, game_session, WORLD_DIR, WORLD_NAME)
        self.db = db_session
        self.session = game_session
        db_session.flush()

    def test_aldric_has_schedule(self):
        """Old Aldric should have schedules."""
        aldric = (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.session.id,
                Entity.entity_key == "old_aldric",
            )
            .first()
        )
        assert aldric is not None

        schedules = (
            self.db.query(Schedule)
            .filter(Schedule.entity_id == aldric.id)
            .all()
        )
        assert len(schedules) >= 2, "Aldric should have multiple schedule entries"

        # Check tavern schedule
        tavern_schedule = next(
            (s for s in schedules if s.location_key == "flagon_common_room"),
            None,
        )
        assert tavern_schedule is not None

    def test_tom_has_schedule(self):
        """Tom should have barkeep schedules."""
        tom = (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.session.id,
                Entity.entity_key == "tom_barkeep",
            )
            .first()
        )
        assert tom is not None

        schedules = (
            self.db.query(Schedule)
            .filter(Schedule.entity_id == tom.id)
            .all()
        )
        assert len(schedules) >= 1

        # Check he works at the flagon
        working_schedule = next(
            (s for s in schedules if "working" in s.activity.lower()),
            None,
        )
        assert working_schedule is not None
        assert working_schedule.location_key == "flagon_common_room"


class TestMillbrookItems:
    """Tests for Millbrook items (Starbound artifacts)."""

    @pytest.fixture(autouse=True)
    def load_world(self, db_session: Session, game_session: GameSession):
        """Load the Millbrook world before each test."""
        load_complete_world(db_session, game_session, WORLD_DIR, WORLD_NAME)
        self.db = db_session
        self.session = game_session
        db_session.flush()

    def test_mothers_pendant_exists(self):
        """Mother's Pendant should exist with magical properties."""
        pendant = (
            self.db.query(Item)
            .filter(
                Item.session_id == self.session.id,
                Item.item_key == "mothers_pendant",
            )
            .first()
        )
        assert pendant is not None
        assert pendant.display_name == "Mother's Pendant"
        assert pendant.properties is not None
        assert pendant.properties.get("is_magical") is True
        assert pendant.properties.get("is_starbound_artifact") is True

    def test_dawn_star_medallion_exists(self):
        """Dawn Star Medallion should exist."""
        medallion = (
            self.db.query(Item)
            .filter(
                Item.session_id == self.session.id,
                Item.item_key == "dawn_star_medallion",
            )
            .first()
        )
        assert medallion is not None
        assert medallion.properties is not None

    def test_watchers_spyglass_exists(self):
        """Watcher's Spyglass should exist."""
        spyglass = (
            self.db.query(Item)
            .filter(
                Item.session_id == self.session.id,
                Item.item_key == "watchers_spyglass",
            )
            .first()
        )
        assert spyglass is not None


class TestMillbrookFacts:
    """Tests for Millbrook world facts."""

    @pytest.fixture(autouse=True)
    def load_world(self, db_session: Session, game_session: GameSession):
        """Load the Millbrook world before each test."""
        load_complete_world(db_session, game_session, WORLD_DIR, WORLD_NAME)
        self.db = db_session
        self.session = game_session
        db_session.flush()

    def test_starbound_legends_exist(self):
        """Public legends about Starbound Order should exist."""
        legend = (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.session.id,
                Fact.subject_key == "starbound_order",
                Fact.predicate == "public_legend",
            )
            .first()
        )
        assert legend is not None
        assert legend.is_secret is False

    def test_secret_facts_exist(self):
        """Secret facts should be marked as secret."""
        secret = (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.session.id,
                Fact.subject_key == "starbound_order",
                Fact.predicate == "true_history",
            )
            .first()
        )
        assert secret is not None
        assert secret.is_secret is True

    def test_omens_exist(self):
        """Omen facts should exist with foreshadowing."""
        omen = (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.session.id,
                Fact.subject_key == "omens",
            )
            .first()
        )
        assert omen is not None
        assert omen.is_foreshadowing is True

    def test_npc_knowledge_facts_exist(self):
        """NPC-specific knowledge facts should exist."""
        elena_fact = (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.session.id,
                Fact.subject_key == "elena_finn_mother",
            )
            .first()
        )
        assert elena_fact is not None
