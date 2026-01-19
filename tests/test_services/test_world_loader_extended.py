"""Tests for world_loader_extended service."""

import json
import tempfile
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from src.database.models.entities import Entity, NPCExtension
from src.database.models.enums import DayOfWeek, EntityType, FactCategory, ItemType
from src.database.models.items import Item
from src.database.models.session import GameSession
from src.database.models.world import Fact, Schedule
from src.services.world_loader_extended import (
    load_complete_world,
    load_facts_from_file,
    load_items_from_file,
    load_npcs_from_file,
    load_schedules_from_file,
)


class TestLoadNPCs:
    """Tests for load_npcs_from_file function."""

    def test_load_basic_npc(self, db_session: Session, game_session: GameSession):
        """Should load a basic NPC from JSON file."""
        npc_data = {
            "npcs": [
                {
                    "entity_key": "test_npc",
                    "display_name": "Test NPC",
                    "entity_type": "npc",
                    "age": 30,
                    "gender": "male",
                    "occupation": "blacksmith",
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(npc_data, f)
            file_path = Path(f.name)

        try:
            results = load_npcs_from_file(db_session, game_session, file_path)

            assert results["count"] == 1
            assert "test_npc" in results["entity_keys"]
            assert len(results["errors"]) == 0

            # Verify entity exists
            entity = (
                db_session.query(Entity)
                .filter(
                    Entity.session_id == game_session.id,
                    Entity.entity_key == "test_npc",
                )
                .first()
            )
            assert entity is not None
            assert entity.display_name == "Test NPC"
            assert entity.age == 30
            assert entity.gender == "male"
            assert entity.occupation == "blacksmith"
        finally:
            file_path.unlink()

    def test_load_npc_with_extension(self, db_session: Session, game_session: GameSession):
        """Should load NPC with extension data."""
        npc_data = {
            "npcs": [
                {
                    "entity_key": "extended_npc",
                    "display_name": "Extended NPC",
                    "entity_type": "npc",
                    "npc_extension": {
                        "job": "tavern keeper",
                        "workplace": "dusty_flagon",
                        "home_location": "flagon_upstairs",
                        "hobbies": ["cooking", "gossip"],
                        "speech_pattern": "Friendly and warm",
                        "dark_secret": "Smuggles goods",
                        "hidden_goal": "Make enough to retire",
                    },
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(npc_data, f)
            file_path = Path(f.name)

        try:
            results = load_npcs_from_file(db_session, game_session, file_path)

            assert results["count"] == 1

            # Verify entity and extension
            entity = (
                db_session.query(Entity)
                .filter(
                    Entity.session_id == game_session.id,
                    Entity.entity_key == "extended_npc",
                )
                .first()
            )
            assert entity is not None

            ext = (
                db_session.query(NPCExtension)
                .filter(NPCExtension.entity_id == entity.id)
                .first()
            )
            assert ext is not None
            assert ext.job == "tavern keeper"
            assert ext.workplace == "dusty_flagon"
            assert ext.hobbies == ["cooking", "gossip"]
            assert ext.dark_secret == "Smuggles goods"
        finally:
            file_path.unlink()

    def test_load_npc_with_knowledge_areas(
        self, db_session: Session, game_session: GameSession
    ):
        """Should load NPC with knowledge areas stored in appearance JSON."""
        npc_data = {
            "npcs": [
                {
                    "entity_key": "knowledgeable_npc",
                    "display_name": "Knowledgeable NPC",
                    "entity_type": "npc",
                    "knowledge_areas": {
                        "village_history": {
                            "description": "History of the village",
                            "disclosure_threshold": 20,
                            "sample_content": "The village was founded...",
                        },
                        "secret_knowledge": {
                            "description": "Hidden truths",
                            "disclosure_threshold": 80,
                            "sample_content": "Only the worthy know...",
                        },
                    },
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(npc_data, f)
            file_path = Path(f.name)

        try:
            results = load_npcs_from_file(db_session, game_session, file_path)

            assert results["count"] == 1

            entity = (
                db_session.query(Entity)
                .filter(
                    Entity.session_id == game_session.id,
                    Entity.entity_key == "knowledgeable_npc",
                )
                .first()
            )
            assert entity is not None
            assert entity.appearance is not None
            assert "knowledge_areas" in entity.appearance
            assert "village_history" in entity.appearance["knowledge_areas"]
            assert (
                entity.appearance["knowledge_areas"]["village_history"]["disclosure_threshold"]
                == 20
            )
        finally:
            file_path.unlink()

    def test_load_npcs_file_not_found(
        self, db_session: Session, game_session: GameSession
    ):
        """Should record error for missing file."""
        results = load_npcs_from_file(
            db_session, game_session, Path("/nonexistent/file.json")
        )

        assert results["count"] == 0
        assert len(results["errors"]) == 1
        assert "File not found" in results["errors"][0]


class TestLoadSchedules:
    """Tests for load_schedules_from_file function."""

    def test_load_schedule(self, db_session: Session, game_session: GameSession):
        """Should load NPC schedule from JSON file."""
        # First create an NPC
        entity = Entity(
            session_id=game_session.id,
            entity_key="scheduled_npc",
            display_name="Scheduled NPC",
            entity_type=EntityType.NPC,
        )
        db_session.add(entity)
        db_session.flush()

        schedule_data = {
            "schedules": [
                {
                    "entity_key": "scheduled_npc",
                    "entries": [
                        {
                            "day_pattern": "daily",
                            "start_time": "08:00",
                            "end_time": "18:00",
                            "activity": "working at forge",
                            "location_key": "blacksmith_forge",
                            "priority": 1,
                        },
                        {
                            "day_pattern": "sunday",
                            "start_time": "09:00",
                            "end_time": "11:00",
                            "activity": "chapel service",
                            "location_key": "chapel",
                            "priority": 2,
                        },
                    ],
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(schedule_data, f)
            file_path = Path(f.name)

        try:
            results = load_schedules_from_file(db_session, game_session, file_path)

            assert results["count"] == 2
            assert len(results["errors"]) == 0

            # Verify schedules
            schedules = (
                db_session.query(Schedule)
                .filter(Schedule.entity_id == entity.id)
                .all()
            )
            assert len(schedules) == 2

            # Check day patterns
            daily_sched = next(s for s in schedules if s.day_pattern == DayOfWeek.DAILY)
            assert daily_sched.activity == "working at forge"
            assert daily_sched.location_key == "blacksmith_forge"

            sunday_sched = next(s for s in schedules if s.day_pattern == DayOfWeek.SUNDAY)
            assert sunday_sched.priority == 2
        finally:
            file_path.unlink()

    def test_load_schedule_nonexistent_entity(
        self, db_session: Session, game_session: GameSession
    ):
        """Should record error for nonexistent entity."""
        schedule_data = {
            "schedules": [
                {
                    "entity_key": "nonexistent_npc",
                    "entries": [
                        {
                            "day_pattern": "daily",
                            "start_time": "08:00",
                            "end_time": "18:00",
                            "activity": "working",
                        }
                    ],
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(schedule_data, f)
            file_path = Path(f.name)

        try:
            results = load_schedules_from_file(db_session, game_session, file_path)

            assert results["count"] == 0
            assert len(results["errors"]) == 1
            assert "Entity not found" in results["errors"][0]
        finally:
            file_path.unlink()


class TestLoadItems:
    """Tests for load_items_from_file function."""

    def test_load_basic_item(self, db_session: Session, game_session: GameSession):
        """Should load a basic item from JSON file."""
        item_data = {
            "items": [
                {
                    "item_key": "test_sword",
                    "display_name": "Test Sword",
                    "item_type": "weapon",
                    "description": "A simple sword",
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(item_data, f)
            file_path = Path(f.name)

        try:
            results = load_items_from_file(db_session, game_session, file_path)

            assert results["count"] == 1
            assert "test_sword" in results["item_keys"]
            assert len(results["errors"]) == 0

            # Verify item exists
            item = (
                db_session.query(Item)
                .filter(
                    Item.session_id == game_session.id,
                    Item.item_key == "test_sword",
                )
                .first()
            )
            assert item is not None
            assert item.display_name == "Test Sword"
            assert item.item_type == ItemType.WEAPON
        finally:
            file_path.unlink()

    def test_load_item_with_properties(
        self, db_session: Session, game_session: GameSession
    ):
        """Should load item with magical properties."""
        item_data = {
            "items": [
                {
                    "item_key": "magic_pendant",
                    "display_name": "Magic Pendant",
                    "item_type": "accessory",
                    "body_slot": "neck",
                    "body_layer": 0,
                    "properties": {
                        "is_magical": True,
                        "functions": [
                            {"name": "Glow", "activation": "passive"},
                        ],
                    },
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(item_data, f)
            file_path = Path(f.name)

        try:
            results = load_items_from_file(db_session, game_session, file_path)

            assert results["count"] == 1

            item = (
                db_session.query(Item)
                .filter(
                    Item.session_id == game_session.id,
                    Item.item_key == "magic_pendant",
                )
                .first()
            )
            assert item is not None
            assert item.body_slot == "neck"
            assert item.properties is not None
            assert item.properties["is_magical"] is True
        finally:
            file_path.unlink()

    def test_load_item_with_owner(
        self, db_session: Session, game_session: GameSession
    ):
        """Should load item with owner reference."""
        # Create owner entity first
        owner = Entity(
            session_id=game_session.id,
            entity_key="item_owner",
            display_name="Item Owner",
            entity_type=EntityType.NPC,
        )
        db_session.add(owner)
        db_session.flush()

        item_data = {
            "items": [
                {
                    "item_key": "owned_item",
                    "display_name": "Owned Item",
                    "item_type": "misc",
                    "owner_entity_key": "item_owner",
                    "holder_entity_key": "item_owner",
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(item_data, f)
            file_path = Path(f.name)

        try:
            results = load_items_from_file(db_session, game_session, file_path)

            assert results["count"] == 1

            item = (
                db_session.query(Item)
                .filter(
                    Item.session_id == game_session.id,
                    Item.item_key == "owned_item",
                )
                .first()
            )
            assert item is not None
            assert item.owner_id == owner.id
            assert item.holder_id == owner.id
        finally:
            file_path.unlink()


class TestLoadFacts:
    """Tests for load_facts_from_file function."""

    def test_load_basic_fact(self, db_session: Session, game_session: GameSession):
        """Should load a basic fact from JSON file."""
        fact_data = {
            "facts": [
                {
                    "subject_type": "world",
                    "subject_key": "test_world",
                    "predicate": "climate",
                    "value": "temperate",
                    "category": "world",
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(fact_data, f)
            file_path = Path(f.name)

        try:
            results = load_facts_from_file(db_session, game_session, file_path)

            assert results["count"] == 1
            assert len(results["errors"]) == 0

            # Verify fact exists
            fact = (
                db_session.query(Fact)
                .filter(
                    Fact.session_id == game_session.id,
                    Fact.subject_key == "test_world",
                    Fact.predicate == "climate",
                )
                .first()
            )
            assert fact is not None
            assert fact.value == "temperate"
            assert fact.category == FactCategory.WORLD
        finally:
            file_path.unlink()

    def test_load_secret_fact(self, db_session: Session, game_session: GameSession):
        """Should load secret facts correctly."""
        fact_data = {
            "facts": [
                {
                    "subject_type": "entity",
                    "subject_key": "villain",
                    "predicate": "true_identity",
                    "value": "The lost prince",
                    "category": "secret",
                    "is_secret": True,
                    "player_believes": "Just a merchant",
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(fact_data, f)
            file_path = Path(f.name)

        try:
            results = load_facts_from_file(db_session, game_session, file_path)

            assert results["count"] == 1

            fact = (
                db_session.query(Fact)
                .filter(
                    Fact.session_id == game_session.id,
                    Fact.subject_key == "villain",
                )
                .first()
            )
            assert fact is not None
            assert fact.is_secret is True
            assert fact.player_believes == "Just a merchant"
        finally:
            file_path.unlink()

    def test_load_foreshadowing_fact(
        self, db_session: Session, game_session: GameSession
    ):
        """Should load foreshadowing facts correctly."""
        fact_data = {
            "facts": [
                {
                    "subject_type": "world",
                    "subject_key": "omens",
                    "predicate": "strange_weather",
                    "value": "Unseasonable cold from the mountains",
                    "category": "world",
                    "is_foreshadowing": True,
                    "foreshadow_target": "ancient_evil_awakening",
                    "times_mentioned": 1,
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(fact_data, f)
            file_path = Path(f.name)

        try:
            results = load_facts_from_file(db_session, game_session, file_path)

            assert results["count"] == 1

            fact = (
                db_session.query(Fact)
                .filter(
                    Fact.session_id == game_session.id,
                    Fact.predicate == "strange_weather",
                )
                .first()
            )
            assert fact is not None
            assert fact.is_foreshadowing is True
            assert fact.foreshadow_target == "ancient_evil_awakening"
        finally:
            file_path.unlink()


class TestLoadCompleteWorld:
    """Tests for load_complete_world function."""

    def test_load_complete_world(self, db_session: Session, game_session: GameSession):
        """Should load all world files from directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            world_dir = Path(tmpdir)
            world_name = "test_world"

            # Create world YAML (using JSON for simplicity)
            world_data = {
                "name": "Test Complete World",
                "zones": [{"zone_key": "village", "display_name": "Village"}],
                "locations": [
                    {
                        "location_key": "tavern",
                        "display_name": "Tavern",
                        "zone_key": "village",
                    }
                ],
            }
            with open(world_dir / f"{world_name}.json", "w") as f:
                json.dump(world_data, f)

            # Create NPCs JSON
            npc_data = {
                "npcs": [
                    {"entity_key": "barkeep", "display_name": "Tom the Barkeep"}
                ]
            }
            with open(world_dir / f"{world_name}_npcs.json", "w") as f:
                json.dump(npc_data, f)

            # Create schedules JSON
            schedule_data = {
                "schedules": [
                    {
                        "entity_key": "barkeep",
                        "entries": [
                            {
                                "day_pattern": "daily",
                                "start_time": "10:00",
                                "end_time": "22:00",
                                "activity": "working",
                                "location_key": "tavern",
                            }
                        ],
                    }
                ]
            }
            with open(world_dir / f"{world_name}_schedules.json", "w") as f:
                json.dump(schedule_data, f)

            # Create items JSON
            item_data = {
                "items": [
                    {"item_key": "ale_mug", "display_name": "Mug of Ale"}
                ]
            }
            with open(world_dir / f"{world_name}_items.json", "w") as f:
                json.dump(item_data, f)

            # Create facts JSON
            fact_data = {
                "facts": [
                    {
                        "subject_type": "location",
                        "subject_key": "tavern",
                        "predicate": "specialty",
                        "value": "ale",
                    }
                ]
            }
            with open(world_dir / f"{world_name}_facts.json", "w") as f:
                json.dump(fact_data, f)

            # Load complete world
            results = load_complete_world(db_session, game_session, world_dir, world_name)

            # Check all components loaded
            assert results["world"]["zones"] == 1
            assert results["world"]["locations"] == 1
            assert results["npcs"]["count"] == 1
            assert results["schedules"]["count"] == 1
            assert results["items"]["count"] == 1
            assert results["facts"]["count"] == 1

    def test_load_complete_world_missing_files(
        self, db_session: Session, game_session: GameSession
    ):
        """Should handle missing optional files gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            world_dir = Path(tmpdir)
            world_name = "partial_world"

            # Create only world YAML
            world_data = {
                "name": "Partial World",
                "zones": [{"zone_key": "zone_a", "display_name": "Zone A"}],
            }
            with open(world_dir / f"{world_name}.json", "w") as f:
                json.dump(world_data, f)

            results = load_complete_world(db_session, game_session, world_dir, world_name)

            # World should load
            assert results["world"]["zones"] == 1
            # Other components should be empty (not error)
            assert results["npcs"]["count"] == 0
            assert results["schedules"]["count"] == 0
            assert results["items"]["count"] == 0
            assert results["facts"]["count"] == 0
