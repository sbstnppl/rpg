"""Tests for world_loader service."""

import json
import tempfile
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from src.database.models.navigation import TerrainZone, ZoneConnection
from src.database.models.session import GameSession
from src.database.models.world import Location
from src.services.world_loader import WorldLoadError, load_world_from_file


class TestWorldLoader:
    """Tests for load_world_from_file function."""

    def test_load_json_world(self, db_session: Session, game_session: GameSession):
        """Should load world from JSON file."""
        world_data = {
            "name": "Test World",
            "zones": [
                {"zone_key": "zone_a", "display_name": "Zone A", "terrain_type": "forest"},
                {"zone_key": "zone_b", "display_name": "Zone B", "terrain_type": "grassland"},
            ],
            "connections": [
                {"from_zone": "zone_a", "to_zone": "zone_b", "direction": "east"},
            ],
            "locations": [
                {
                    "location_key": "tavern",
                    "display_name": "The Tavern",
                    "zone_key": "zone_a",
                    "category": "tavern",
                },
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(world_data, f)
            file_path = Path(f.name)

        try:
            results = load_world_from_file(db_session, game_session, file_path)

            assert results["zones"] == 2
            # 1 bidirectional = 2 connections
            assert results["connections"] == 2
            assert results["locations"] == 1

            # Verify zones exist
            zones = db_session.query(TerrainZone).filter(
                TerrainZone.session_id == game_session.id
            ).all()
            assert len(zones) == 2

            # Verify location exists
            locations = db_session.query(Location).filter(
                Location.session_id == game_session.id
            ).all()
            assert len(locations) == 1
            assert locations[0].display_name == "The Tavern"
        finally:
            file_path.unlink()

    def test_load_yaml_world(self, db_session: Session, game_session: GameSession):
        """Should load world from YAML file."""
        yaml_content = """
name: YAML Test World
zones:
  - zone_key: forest
    display_name: Dark Forest
    terrain_type: dense_forest
    base_travel_cost: 30
locations:
  - location_key: cabin
    display_name: Abandoned Cabin
    zone_key: forest
    category: building
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            file_path = Path(f.name)

        try:
            results = load_world_from_file(db_session, game_session, file_path)

            assert results["zones"] == 1
            assert results["locations"] == 1

            # Verify zone
            zone = db_session.query(TerrainZone).filter(
                TerrainZone.session_id == game_session.id,
                TerrainZone.zone_key == "forest",
            ).first()
            assert zone is not None
            assert zone.display_name == "Dark Forest"
            assert zone.base_travel_cost == 30
        finally:
            file_path.unlink()

    def test_load_world_with_parent_zones(
        self, db_session: Session, game_session: GameSession
    ):
        """Should correctly set parent zone relationships."""
        world_data = {
            "name": "Hierarchical World",
            "zones": [
                {"zone_key": "region", "display_name": "Northern Region"},
                {"zone_key": "subregion", "display_name": "Highlands", "parent_zone_key": "region"},
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(world_data, f)
            file_path = Path(f.name)

        try:
            results = load_world_from_file(db_session, game_session, file_path)

            assert results["zones"] == 2

            # Verify parent relationship
            subregion = db_session.query(TerrainZone).filter(
                TerrainZone.session_id == game_session.id,
                TerrainZone.zone_key == "subregion",
            ).first()
            assert subregion is not None
            assert subregion.parent_zone_id is not None

            region = db_session.query(TerrainZone).filter(
                TerrainZone.session_id == game_session.id,
                TerrainZone.zone_key == "region",
            ).first()
            assert subregion.parent_zone_id == region.id
        finally:
            file_path.unlink()

    def test_load_world_file_not_found(
        self, db_session: Session, game_session: GameSession
    ):
        """Should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            load_world_from_file(
                db_session, game_session, Path("/nonexistent/file.json")
            )

    def test_load_world_invalid_format(
        self, db_session: Session, game_session: GameSession
    ):
        """Should raise WorldLoadError for unsupported format."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"invalid content")
            file_path = Path(f.name)

        try:
            with pytest.raises(WorldLoadError, match="Unsupported file format"):
                load_world_from_file(db_session, game_session, file_path)
        finally:
            file_path.unlink()

    def test_load_world_invalid_json(
        self, db_session: Session, game_session: GameSession
    ):
        """Should raise WorldLoadError for invalid JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ invalid json }")
            file_path = Path(f.name)

        try:
            with pytest.raises(WorldLoadError, match="Failed to parse"):
                load_world_from_file(db_session, game_session, file_path)
        finally:
            file_path.unlink()

    def test_load_world_invalid_schema(
        self, db_session: Session, game_session: GameSession
    ):
        """Should raise WorldLoadError for invalid template schema."""
        # Missing required 'name' field
        world_data = {
            "zones": [{"zone_key": "test"}],  # Missing display_name
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(world_data, f)
            file_path = Path(f.name)

        try:
            with pytest.raises(WorldLoadError, match="Invalid world template"):
                load_world_from_file(db_session, game_session, file_path)
        finally:
            file_path.unlink()

    def test_load_world_records_errors_for_invalid_refs(
        self, db_session: Session, game_session: GameSession
    ):
        """Should record errors for invalid zone references but continue loading."""
        world_data = {
            "name": "Test World",
            "zones": [
                {"zone_key": "zone_a", "display_name": "Zone A"},
            ],
            "connections": [
                # Invalid: nonexistent_zone doesn't exist
                {"from_zone": "zone_a", "to_zone": "nonexistent_zone"},
            ],
            "locations": [
                # Invalid: bad_zone doesn't exist
                {"location_key": "loc", "display_name": "Location", "zone_key": "bad_zone"},
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(world_data, f)
            file_path = Path(f.name)

        try:
            results = load_world_from_file(db_session, game_session, file_path)

            # Zones should load successfully
            assert results["zones"] == 1
            # Connections and locations should fail
            assert results["connections"] == 0
            assert results["locations"] == 0
            # Errors should be recorded
            assert len(results["errors"]) == 2
        finally:
            file_path.unlink()
