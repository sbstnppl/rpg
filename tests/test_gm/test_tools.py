"""Tests for the GM pipeline tools."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.entities import Entity, NPCExtension
from src.database.models.enums import EntityType
from src.database.models.session import GameSession
from src.gm.tools import GMTools
from src.gm.schemas import EntityType as GMEntityType
from src.managers.entity_manager import EntityManager
from src.managers.relationship_manager import RelationshipManager
from src.managers.task_manager import TaskManager


class TestGetNpcAttitude:
    """Tests for the get_npc_attitude tool."""

    def test_returns_attitude_dimensions(
        self, db_session: Session, game_session: GameSession
    ):
        """Tool returns all attitude dimensions."""
        entity_manager = EntityManager(db_session, game_session)

        # Create player
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        player_ext = NPCExtension(entity_id=player.id, current_location="tavern")
        db_session.add(player_ext)

        # Create NPC
        merchant = entity_manager.create_entity(
            entity_key="merchant_anna",
            display_name="Anna",
            entity_type=EntityType.NPC,
        )
        db_session.flush()

        # Create relationship via get_or_create
        rel_manager = RelationshipManager(db_session, game_session)
        rel_manager.get_or_create_relationship(merchant.id, player.id)

        # Use the tool
        tools = GMTools(db_session, game_session, player.id)
        result = tools.get_npc_attitude(
            from_entity="merchant_anna", to_entity="player"
        )

        # Verify all dimensions are present
        assert "error" not in result
        assert result["from_entity"] == "merchant_anna"
        assert result["to_entity"] == "player"
        assert "trust" in result
        assert "liking" in result
        assert "respect" in result
        assert "fear" in result
        assert "romantic_interest" in result
        assert "familiarity" in result

    def test_error_on_missing_entity(
        self, db_session: Session, game_session: GameSession
    ):
        """Tool returns error when entity not found."""
        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        tools = GMTools(db_session, game_session, player.id)
        result = tools.get_npc_attitude(
            from_entity="nonexistent_npc", to_entity="player"
        )

        assert "error" in result
        assert "not found" in result["error"]


class TestQuestTools:
    """Tests for quest management tools."""

    def test_assign_quest(self, db_session: Session, game_session: GameSession):
        """assign_quest creates and starts a new quest."""
        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        tools = GMTools(db_session, game_session, player.id)
        result = tools.assign_quest(
            quest_key="find_lost_ring",
            title="The Lost Ring",
            description="Find the merchant's lost ring in the well.",
            giver_entity_key=None,
            rewards="10 gold coins",
        )

        assert result["success"] is True
        assert result["quest_key"] == "find_lost_ring"
        assert "assigned" in result["message"].lower()

        # Verify quest exists
        task_manager = TaskManager(db_session, game_session)
        quest = task_manager.get_quest("find_lost_ring")
        assert quest is not None
        assert quest.name == "The Lost Ring"

    def test_update_quest(self, db_session: Session, game_session: GameSession):
        """update_quest advances quest to next stage."""
        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        # Create and start quest
        task_manager = TaskManager(db_session, game_session)
        quest = task_manager.create_quest(
            quest_key="rescue_cat",
            name="Rescue the Cat",
            description="Get the cat down from the tree.",
        )
        task_manager.start_quest("rescue_cat")

        tools = GMTools(db_session, game_session, player.id)
        result = tools.update_quest(quest_key="rescue_cat")

        assert result["success"] is True
        assert result["quest_key"] == "rescue_cat"

    def test_complete_quest(self, db_session: Session, game_session: GameSession):
        """complete_quest marks quest as done."""
        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        # Create and start quest
        task_manager = TaskManager(db_session, game_session)
        quest = task_manager.create_quest(
            quest_key="deliver_letter",
            name="Deliver Letter",
            description="Deliver the letter to the mayor.",
        )
        task_manager.start_quest("deliver_letter")

        tools = GMTools(db_session, game_session, player.id)
        result = tools.complete_quest(
            quest_key="deliver_letter", outcome="completed"
        )

        assert result["success"] is True
        assert result["status"] == "completed"


class TestTaskTools:
    """Tests for task management tools."""

    def test_create_task(self, db_session: Session, game_session: GameSession):
        """create_task adds a new task."""
        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        tools = GMTools(db_session, game_session, player.id)
        result = tools.create_task(
            description="Buy supplies from the market",
            category="goal",
            priority=2,
        )

        assert result["success"] is True
        assert result["task_id"] is not None
        assert "created" in result["message"].lower()

    def test_complete_task(self, db_session: Session, game_session: GameSession):
        """complete_task marks task as done."""
        from src.database.models.enums import TaskCategory

        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        # Create task
        task_manager = TaskManager(db_session, game_session)
        task = task_manager.create_task(
            description="Visit the blacksmith",
            category=TaskCategory.GOAL,
        )

        tools = GMTools(db_session, game_session, player.id)
        result = tools.complete_task(task_id=task.id)

        assert result["success"] is True
        assert result["task_id"] == task.id


class TestAppointmentTools:
    """Tests for appointment management tools."""

    def test_create_appointment(
        self, db_session: Session, game_session: GameSession
    ):
        """create_appointment schedules a new meeting."""
        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        tools = GMTools(db_session, game_session, player.id)
        result = tools.create_appointment(
            description="Meet with the guild master",
            game_day=2,
            participants="Guild Master Rodrik",
            game_time="3pm",
            location_name="Guild Hall",
        )

        assert result["success"] is True
        assert result["appointment_id"] is not None
        assert result["game_day"] == 2


class TestCreateEntityWithStorage:
    """Tests for creating storage via create_entity."""

    def test_create_storage_container(
        self, db_session: Session, game_session: GameSession
    ):
        """create_entity can create a storage container."""
        from src.database.models.items import StorageLocation

        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        tools = GMTools(db_session, game_session, player.id, location_key="tavern")
        result = tools.create_entity(
            entity_type="storage",
            name="Wooden Chest",
            description="A sturdy wooden chest.",
            container_type="container",
            capacity=20,
        )

        assert result.success is True
        assert result.entity_type == GMEntityType.STORAGE
        assert "wooden_chest" in result.entity_key

        # Verify storage was created
        storage = (
            db_session.query(StorageLocation)
            .filter(StorageLocation.location_key == result.entity_key)
            .first()
        )
        assert storage is not None
        assert storage.capacity == 20

    def test_create_storage_place(
        self, db_session: Session, game_session: GameSession
    ):
        """create_entity can create a storage place (table, shelf)."""
        from src.database.models.items import StorageLocation
        from src.database.models.enums import StorageLocationType

        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        tools = GMTools(db_session, game_session, player.id, location_key="tavern")
        result = tools.create_entity(
            entity_type="storage",
            name="Oak Table",
            description="A large oak table in the corner.",
            container_type="place",
        )

        assert result.success is True
        assert result.entity_type == GMEntityType.STORAGE

        # Verify storage was created with PLACE type
        storage = (
            db_session.query(StorageLocation)
            .filter(StorageLocation.location_key == result.entity_key)
            .first()
        )
        assert storage is not None
        assert storage.location_type == StorageLocationType.PLACE


class TestTier3NeedsTools:
    """Tests for Tier 3 needs tools."""

    def test_apply_stimulus(self, db_session: Session, game_session: GameSession):
        """apply_stimulus creates a craving."""
        from src.managers.needs import NeedsManager

        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        # Create needs record so apply_craving works
        needs_manager = NeedsManager(db_session, game_session)
        needs_manager.get_or_create_needs(player.id)

        tools = GMTools(db_session, game_session, player.id)
        result = tools.apply_stimulus(
            entity_key="player",
            stimulus_type="food_sight",
            stimulus_description="The aroma of fresh bread wafts from the bakery.",
            intensity="strong",
        )

        assert result["success"] is True
        assert result["need"] == "hunger"
        # Strong intensity gives a craving boost (actual amount depends on current need)
        assert "craving_boost" in result

    def test_mark_need_communicated(
        self, db_session: Session, game_session: GameSession
    ):
        """mark_need_communicated returns success (stub implementation)."""
        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        tools = GMTools(db_session, game_session, player.id)
        result = tools.mark_need_communicated(
            entity_key="player", need_name="hunger"
        )

        assert result["success"] is True
        assert result["need_name"] == "hunger"
