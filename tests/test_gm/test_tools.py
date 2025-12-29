"""Tests for the GM pipeline tools."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.entities import Entity, NPCExtension
from src.database.models.enums import EntityType
from src.database.models.session import GameSession
from src.gm.tools import GMTools
from src.gm.schemas import EntityType as GMEntityType
from src.gm.grounding import GroundingManifest, GroundedEntity
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


class TestExecuteToolFiltering:
    """Tests for execute_tool input filtering to handle LLM hallucinated params."""

    def test_take_item_ignores_hallucinated_storage_location(
        self, db_session: Session, game_session: GameSession
    ):
        """take_item ignores hallucinated storage_location parameter."""
        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        tools = GMTools(db_session, game_session, player.id)

        # Call execute_tool with hallucinated param - should not raise TypeError
        result = tools.execute_tool("take_item", {
            "item_key": "nonexistent_item",
            "storage_location": "chest"  # hallucinated param
        })

        # Should get item not found error, not TypeError
        assert "error" in result
        assert "not found" in result["error"].lower() or "item not found" in result["error"].lower()

    def test_drop_item_ignores_extra_params(
        self, db_session: Session, game_session: GameSession
    ):
        """drop_item ignores any extra hallucinated parameters."""
        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        tools = GMTools(db_session, game_session, player.id)

        # Call with hallucinated params
        result = tools.execute_tool("drop_item", {
            "item_key": "nonexistent_item",
            "target_location": "floor",  # hallucinated
            "carefully": True  # hallucinated
        })

        # Should get item not found error, not TypeError
        assert "error" in result

    def test_skill_check_ignores_extra_params(
        self, db_session: Session, game_session: GameSession
    ):
        """skill_check ignores hallucinated parameters."""
        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        tools = GMTools(db_session, game_session, player.id)

        # Call with hallucinated params - should work without TypeError
        result = tools.execute_tool("skill_check", {
            "skill": "perception",
            "dc": 10,
            "bonus_modifier": 5,  # hallucinated
            "advantage": True  # hallucinated
        })

        # Should succeed (not raise TypeError)
        assert "success" in result or "roll" in result

    def test_get_valid_params_returns_correct_set(
        self, db_session: Session, game_session: GameSession
    ):
        """_get_valid_params returns correct parameter set for tools."""
        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        tools = GMTools(db_session, game_session, player.id)

        # Check take_item
        take_params = tools._get_valid_params("take_item")
        assert take_params == {"item_key"}

        # Check skill_check
        skill_params = tools._get_valid_params("skill_check")
        assert "skill" in skill_params
        assert "dc" in skill_params

    def test_filter_tool_input_removes_invalid_params(
        self, db_session: Session, game_session: GameSession
    ):
        """_filter_tool_input removes params not in tool definition."""
        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        tools = GMTools(db_session, game_session, player.id)

        # Filter take_item input
        input_data = {
            "item_key": "sword_001",
            "storage_location": "chest",
            "quantity": 1
        }
        filtered = tools._filter_tool_input("take_item", input_data)

        assert filtered == {"item_key": "sword_001"}
        assert "storage_location" not in filtered
        assert "quantity" not in filtered


class TestSatisfyNeedMapping:
    """Tests for satisfy_need activity-to-need mapping."""

    def test_tool_description_contains_activity_mappings(
        self, db_session: Session, game_session: GameSession
    ):
        """Tool description includes explicit activity-to-need mappings."""
        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        tools = GMTools(db_session, game_session, player.id)
        tool_defs = tools.get_tool_definitions()

        # Find satisfy_need tool
        satisfy_need_tool = next(
            (t for t in tool_defs if t["name"] == "satisfy_need"), None
        )
        assert satisfy_need_tool is not None

        description = satisfy_need_tool["description"]

        # Verify key mappings are present
        assert "Drinking" in description and "thirst" in description
        assert "Eating" in description and "hunger" in description
        assert "Resting" in description and "stamina" in description
        assert "Sleeping" in description and "sleep_pressure" in description
        assert "Bathing" in description and "hygiene" in description
        assert "Talking" in description or "socializing" in description

    def test_satisfy_need_thirst_drinking(
        self, db_session: Session, game_session: GameSession
    ):
        """satisfy_need with thirst correctly updates thirst level."""
        from src.managers.needs import NeedsManager

        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        # Initialize needs
        needs_manager = NeedsManager(db_session, game_session)
        needs = needs_manager.get_or_create_needs(player.id)
        initial_thirst = needs.thirst

        tools = GMTools(db_session, game_session, player.id)
        result = tools.satisfy_need(
            need="thirst",
            amount=25,
            activity="drinking ale",
        )

        assert result["success"] is True
        assert result["need"] == "thirst"
        assert result["new_value"] > initial_thirst

    def test_satisfy_need_hunger_eating(
        self, db_session: Session, game_session: GameSession
    ):
        """satisfy_need with hunger correctly updates hunger level."""
        from src.managers.needs import NeedsManager

        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        # Initialize needs
        needs_manager = NeedsManager(db_session, game_session)
        needs = needs_manager.get_or_create_needs(player.id)
        initial_hunger = needs.hunger

        tools = GMTools(db_session, game_session, player.id)
        result = tools.satisfy_need(
            need="hunger",
            amount=40,
            activity="eating bread",
        )

        assert result["success"] is True
        assert result["need"] == "hunger"
        assert result["new_value"] > initial_hunger

    def test_satisfy_need_stamina_resting(
        self, db_session: Session, game_session: GameSession
    ):
        """satisfy_need with stamina correctly updates stamina level."""
        from src.managers.needs import NeedsManager

        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        # Initialize needs
        needs_manager = NeedsManager(db_session, game_session)
        needs = needs_manager.get_or_create_needs(player.id)
        initial_stamina = needs.stamina

        tools = GMTools(db_session, game_session, player.id)
        result = tools.satisfy_need(
            need="stamina",
            amount=25,
            activity="resting by the fire",
        )

        assert result["success"] is True
        assert result["need"] == "stamina"
        assert result["new_value"] > initial_stamina


class TestGetTimeTool:
    """Tests for the get_time tool (OOC time queries)."""

    def test_get_time_tool_defined(
        self, db_session: Session, game_session: GameSession
    ):
        """get_time tool should be in tool definitions."""
        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        tools = GMTools(db_session, game_session, player.id)
        tool_defs = tools.get_tool_definitions()

        names = [t["name"] for t in tool_defs]
        assert "get_time" in names

    def test_get_time_returns_current_time(
        self, db_session: Session, game_session: GameSession
    ):
        """get_time should return accurate time state."""
        from src.managers.time_manager import TimeManager

        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        # Set specific time
        tm = TimeManager(db_session, game_session)
        tm.set_time("10:30")

        tools = GMTools(db_session, game_session, player.id)
        result = tools.execute_tool("get_time", {})

        assert result["current_time"] == "10:30"
        assert result["current_day"] == 1
        # 10:30 - 08:00 = 150 minutes
        assert result["elapsed_minutes"] == 150

    def test_get_time_elapsed_formatting_hours(
        self, db_session: Session, game_session: GameSession
    ):
        """elapsed_today should show hours and minutes."""
        from src.managers.time_manager import TimeManager

        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        # 1 hour and 15 minutes after default start (08:00)
        tm = TimeManager(db_session, game_session)
        tm.set_time("09:15")

        tools = GMTools(db_session, game_session, player.id)
        result = tools.execute_tool("get_time", {})

        assert result["elapsed_today"] == "1 hour and 15 minutes"
        assert result["elapsed_minutes"] == 75

    def test_get_time_elapsed_formatting_minutes_only(
        self, db_session: Session, game_session: GameSession
    ):
        """elapsed_today should show just minutes for <60 min."""
        from src.managers.time_manager import TimeManager

        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        # 10 minutes after default start (08:00)
        tm = TimeManager(db_session, game_session)
        tm.set_time("08:10")

        tools = GMTools(db_session, game_session, player.id)
        result = tools.execute_tool("get_time", {})

        assert result["elapsed_today"] == "10 minutes"
        assert result["elapsed_minutes"] == 10

    def test_get_time_elapsed_singular_minute(
        self, db_session: Session, game_session: GameSession
    ):
        """elapsed_today should use singular 'minute' for 1 minute."""
        from src.managers.time_manager import TimeManager

        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        # 1 minute after default start (08:00)
        tm = TimeManager(db_session, game_session)
        tm.set_time("08:01")

        tools = GMTools(db_session, game_session, player.id)
        result = tools.execute_tool("get_time", {})

        assert result["elapsed_today"] == "1 minute"
        assert result["elapsed_minutes"] == 1

    def test_get_time_includes_day_of_week(
        self, db_session: Session, game_session: GameSession
    ):
        """get_time should return day of week."""
        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        tools = GMTools(db_session, game_session, player.id)
        result = tools.execute_tool("get_time", {})

        assert "day_of_week" in result
        assert result["day_of_week"] == "monday"

    def test_get_time_includes_period(
        self, db_session: Session, game_session: GameSession
    ):
        """get_time should return period of day."""
        from src.managers.time_manager import TimeManager

        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        # Set to afternoon
        tm = TimeManager(db_session, game_session)
        tm.set_time("14:00")

        tools = GMTools(db_session, game_session, player.id)
        result = tools.execute_tool("get_time", {})

        assert result["period"] == "afternoon"

    def test_get_time_just_started(
        self, db_session: Session, game_session: GameSession
    ):
        """get_time should say 'just started' at session start time."""
        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        # Default time is 08:00, same as session start
        tools = GMTools(db_session, game_session, player.id)
        result = tools.execute_tool("get_time", {})

        assert result["elapsed_today"] == "just started"
        assert result["elapsed_minutes"] == 0


class TestMoveTo:
    """Tests for the move_to tool."""

    def test_move_to_existing_location(
        self, db_session: Session, game_session: GameSession
    ):
        """move_to updates player location to existing location."""
        from src.managers.location_manager import LocationManager

        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        player_ext = NPCExtension(entity_id=player.id, current_location="tavern")
        db_session.add(player_ext)

        # Create current location
        loc_manager = LocationManager(db_session, game_session)
        loc_manager.create_location(
            location_key="tavern",
            display_name="The Tavern",
            description="A cozy tavern.",
        )

        # Create target location
        loc_manager.create_location(
            location_key="village_square",
            display_name="Village Square",
            description="The central square of the village.",
        )
        db_session.flush()

        tools = GMTools(db_session, game_session, player.id, location_key="tavern")
        result = tools.move_to(destination="village_square")

        assert result["success"] is True
        assert result["to_location"] == "village_square"
        assert result["display_name"] == "Village Square"
        assert result["travel_time_minutes"] >= 1

        # Verify DB updated
        db_session.refresh(player_ext)
        assert player_ext.current_location == "village_square"

    def test_move_to_fuzzy_match(
        self, db_session: Session, game_session: GameSession
    ):
        """move_to uses fuzzy matching for destination."""
        from src.managers.location_manager import LocationManager

        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        player_ext = NPCExtension(entity_id=player.id, current_location="tavern")
        db_session.add(player_ext)

        # Create current and target locations
        loc_manager = LocationManager(db_session, game_session)
        loc_manager.create_location(
            location_key="tavern",
            display_name="The Tavern",
            description="A cozy tavern.",
        )
        loc_manager.create_location(
            location_key="farmhouse_well",
            display_name="The Well",
            description="A stone well near the farmhouse.",
        )
        db_session.flush()

        tools = GMTools(db_session, game_session, player.id, location_key="tavern")

        # Use informal name - should fuzzy match to farmhouse_well
        result = tools.move_to(destination="the well")

        assert result["success"] is True
        assert result["to_location"] == "farmhouse_well"

    def test_move_to_creates_new_location(
        self, db_session: Session, game_session: GameSession
    ):
        """move_to creates new location if not found."""
        from src.managers.location_manager import LocationManager

        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        player_ext = NPCExtension(entity_id=player.id, current_location="tavern")
        db_session.add(player_ext)

        # Create current location only
        loc_manager = LocationManager(db_session, game_session)
        loc_manager.create_location(
            location_key="tavern",
            display_name="The Tavern",
            description="A cozy tavern.",
        )
        db_session.flush()

        tools = GMTools(db_session, game_session, player.id, location_key="tavern")
        result = tools.move_to(destination="the old mill")

        assert result["success"] is True
        assert "mill" in result["to_location"].lower()

        # Verify location was created
        loc = loc_manager.get_location(result["to_location"])
        assert loc is not None
        assert "mill" in loc.display_name.lower()

    def test_move_to_running_faster(
        self, db_session: Session, game_session: GameSession
    ):
        """Running reduces travel time compared to walking."""
        from src.managers.location_manager import LocationManager

        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        player_ext = NPCExtension(entity_id=player.id, current_location="tavern")
        db_session.add(player_ext)

        loc_manager = LocationManager(db_session, game_session)
        loc_manager.create_location(
            location_key="tavern",
            display_name="The Tavern",
            description="A cozy tavern.",
        )
        loc_manager.create_location(
            location_key="village_square",
            display_name="Village Square",
            description="The central square.",
        )
        db_session.flush()

        tools = GMTools(db_session, game_session, player.id, location_key="tavern")

        walk_result = tools.move_to(destination="village_square", travel_method="walk")

        # Reset location for second test
        player_ext.current_location = "tavern"
        tools.location_key = "tavern"
        db_session.flush()

        run_result = tools.move_to(destination="village_square", travel_method="run")

        # Running should be faster (or equal for very short distances)
        assert run_result["travel_time_minutes"] <= walk_result["travel_time_minutes"]

    def test_move_to_same_location_zero_time(
        self, db_session: Session, game_session: GameSession
    ):
        """Moving to current location returns zero time."""
        from src.managers.location_manager import LocationManager

        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        player_ext = NPCExtension(entity_id=player.id, current_location="tavern")
        db_session.add(player_ext)

        loc_manager = LocationManager(db_session, game_session)
        loc_manager.create_location(
            location_key="tavern",
            display_name="The Tavern",
            description="A cozy tavern.",
        )
        db_session.flush()

        tools = GMTools(db_session, game_session, player.id, location_key="tavern")
        result = tools.move_to(destination="tavern")

        assert result["success"] is True
        assert result["travel_time_minutes"] == 0

    def test_move_to_no_destination_error(
        self, db_session: Session, game_session: GameSession
    ):
        """move_to returns error when no destination provided."""
        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        tools = GMTools(db_session, game_session, player.id, location_key="tavern")
        result = tools.move_to(destination="")

        assert result["success"] is False
        assert "error" in result

    def test_move_to_sneaking_slower(
        self, db_session: Session, game_session: GameSession
    ):
        """Sneaking takes longer than walking."""
        from src.managers.location_manager import LocationManager

        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        player_ext = NPCExtension(entity_id=player.id, current_location="tavern")
        db_session.add(player_ext)

        loc_manager = LocationManager(db_session, game_session)
        loc_manager.create_location(
            location_key="tavern",
            display_name="The Tavern",
            description="A cozy tavern.",
        )
        loc_manager.create_location(
            location_key="village_square",
            display_name="Village Square",
            description="The central square.",
        )
        db_session.flush()

        tools = GMTools(db_session, game_session, player.id, location_key="tavern")

        walk_result = tools.move_to(destination="village_square", travel_method="walk")

        # Reset location
        player_ext.current_location = "tavern"
        tools.location_key = "tavern"
        db_session.flush()

        sneak_result = tools.move_to(destination="village_square", travel_method="sneak")

        # Sneaking should take longer
        assert sneak_result["travel_time_minutes"] >= walk_result["travel_time_minutes"]

    def test_move_to_updates_tools_location_key(
        self, db_session: Session, game_session: GameSession
    ):
        """move_to updates the GMTools instance location_key."""
        from src.managers.location_manager import LocationManager

        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        player_ext = NPCExtension(entity_id=player.id, current_location="tavern")
        db_session.add(player_ext)

        loc_manager = LocationManager(db_session, game_session)
        loc_manager.create_location(
            location_key="tavern",
            display_name="The Tavern",
            description="A cozy tavern.",
        )
        loc_manager.create_location(
            location_key="village_square",
            display_name="Village Square",
            description="The central square.",
        )
        db_session.flush()

        tools = GMTools(db_session, game_session, player.id, location_key="tavern")
        assert tools.location_key == "tavern"

        tools.move_to(destination="village_square")

        # Instance should be updated for subsequent tool calls
        assert tools.location_key == "village_square"

    def test_execute_tool_dispatches_move_to(
        self, db_session: Session, game_session: GameSession
    ):
        """execute_tool correctly dispatches to move_to method."""
        from src.managers.location_manager import LocationManager

        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        player_ext = NPCExtension(entity_id=player.id, current_location="tavern")
        db_session.add(player_ext)

        loc_manager = LocationManager(db_session, game_session)
        loc_manager.create_location(
            location_key="tavern",
            display_name="The Tavern",
            description="A cozy tavern.",
        )
        loc_manager.create_location(
            location_key="village_square",
            display_name="Village Square",
            description="The central square.",
        )
        db_session.flush()

        tools = GMTools(db_session, game_session, player.id, location_key="tavern")

        # Use execute_tool (the LLM-facing dispatcher) instead of direct method call
        result = tools.execute_tool("move_to", {
            "destination": "village_square",
            "travel_method": "walk"
        })

        assert result["success"] is True
        assert result["to_location"] == "village_square"
        assert "travel_time_minutes" in result

        # Verify DB updated
        db_session.refresh(player_ext)
        assert player_ext.current_location == "village_square"


class TestKeyResolver:
    """Tests for KeyResolver fuzzy entity key matching."""

    def test_key_resolver_exact_match(
        self, db_session: Session, game_session: GameSession
    ):
        """KeyResolver returns exact match without correction."""
        from src.gm.tools import KeyResolver
        from src.gm.grounding import GroundingManifest, GroundedEntity

        manifest = GroundingManifest(
            location_key="tavern",
            location_display="Tavern",
            player_key="test_hero",
            player_display="Hero",
            npcs={
                "farmer_marcus": GroundedEntity(
                    key="farmer_marcus",
                    display_name="Marcus",
                    entity_type="npc",
                ),
            },
            items_at_location={},
            inventory={},
            equipped={},
            storages={},
            exits={},
        )

        resolver = KeyResolver(manifest)
        key, was_corrected = resolver.resolve("farmer_marcus")

        assert key == "farmer_marcus"
        assert was_corrected is False

    def test_key_resolver_fuzzy_match(
        self, db_session: Session, game_session: GameSession
    ):
        """KeyResolver fuzzy matches hallucinated keys."""
        from src.gm.tools import KeyResolver
        from src.gm.grounding import GroundingManifest, GroundedEntity

        manifest = GroundingManifest(
            location_key="tavern",
            location_display="Tavern",
            player_key="test_hero",
            player_display="Hero",
            npcs={
                "farmer_marcus": GroundedEntity(
                    key="farmer_marcus",
                    display_name="Marcus",
                    entity_type="npc",
                ),
            },
            items_at_location={
                "bread_001": GroundedEntity(
                    key="bread_001",
                    display_name="Bread",
                    entity_type="item",
                ),
            },
            inventory={},
            equipped={},
            storages={},
            exits={},
        )

        resolver = KeyResolver(manifest)

        # Test NPC hallucination: farmer_001 -> farmer_marcus
        key, was_corrected = resolver.resolve("farmer_001")
        assert key == "farmer_marcus"
        assert was_corrected is True

        # Test item simplification: bread -> bread_001
        key, was_corrected = resolver.resolve("bread")
        assert key == "bread_001"
        assert was_corrected is True

    def test_key_resolver_no_match(
        self, db_session: Session, game_session: GameSession
    ):
        """KeyResolver returns original key if no close match."""
        from src.gm.tools import KeyResolver
        from src.gm.grounding import GroundingManifest, GroundedEntity

        manifest = GroundingManifest(
            location_key="tavern",
            location_display="Tavern",
            player_key="test_hero",
            player_display="Hero",
            npcs={
                "farmer_marcus": GroundedEntity(
                    key="farmer_marcus",
                    display_name="Marcus",
                    entity_type="npc",
                ),
            },
            items_at_location={},
            inventory={},
            equipped={},
            storages={},
            exits={},
        )

        resolver = KeyResolver(manifest)
        key, was_corrected = resolver.resolve("completely_different_xyz")

        assert key == "completely_different_xyz"
        assert was_corrected is False

    def test_tools_resolve_key_with_manifest(
        self, db_session: Session, game_session: GameSession
    ):
        """GMTools._resolve_key uses manifest when available."""
        from src.gm.grounding import GroundingManifest, GroundedEntity

        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        manifest = GroundingManifest(
            location_key="tavern",
            location_display="Tavern",
            player_key="player",
            player_display="Test Player",
            npcs={
                "farmer_marcus": GroundedEntity(
                    key="farmer_marcus",
                    display_name="Marcus",
                    entity_type="npc",
                ),
            },
            items_at_location={},
            inventory={},
            equipped={},
            storages={},
            exits={},
        )

        tools = GMTools(db_session, game_session, player.id, manifest=manifest)

        # Should resolve farmer_001 to farmer_marcus
        resolved = tools._resolve_key("farmer_001")
        assert resolved == "farmer_marcus"

    def test_tools_resolve_key_without_manifest(
        self, db_session: Session, game_session: GameSession
    ):
        """GMTools._resolve_key returns original key without manifest."""
        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        tools = GMTools(db_session, game_session, player.id)  # No manifest

        # Should return original key unchanged
        resolved = tools._resolve_key("farmer_001")
        assert resolved == "farmer_001"


class TestItemKeyValidation:
    """Tests for item key validation in execute_tool."""

    def test_take_item_invalid_key_returns_helpful_error(
        self, db_session: Session, game_session: GameSession
    ):
        """take_item with invalid key returns error with valid key hints."""
        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        # Create manifest with known items
        manifest = GroundingManifest(
            location_key="tavern_001",
            location_display="Tavern",
            player_key="player",
            items_at_location={
                "ale_mug_001": GroundedEntity(
                    key="ale_mug_001",
                    display_name="Ale Mug",
                    entity_type="item",
                ),
            },
            inventory={},
            equipped={},
            npcs={},
            storages={},
            exits={},
        )

        tools = GMTools(db_session, game_session, player.id, manifest=manifest)

        # Try to take with hallucinated key
        result = tools.execute_tool("take_item", {"item_key": "mug_of_ale"})

        assert "error" in result
        assert "Invalid item key" in result["error"]
        assert "hint" in result
        assert "ale_mug_001" in str(result["hint"])

    def test_drop_item_invalid_key_returns_helpful_error(
        self, db_session: Session, game_session: GameSession
    ):
        """drop_item with invalid key returns error with valid key hints."""
        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        # Create manifest with inventory items
        manifest = GroundingManifest(
            location_key="tavern_001",
            location_display="Tavern",
            player_key="player",
            items_at_location={},
            inventory={
                "gold_coins_001": GroundedEntity(
                    key="gold_coins_001",
                    display_name="Gold Coins",
                    entity_type="item",
                ),
            },
            equipped={},
            npcs={},
            storages={},
            exits={},
        )

        tools = GMTools(db_session, game_session, player.id, manifest=manifest)

        # Try to drop with hallucinated key
        result = tools.execute_tool("drop_item", {"item_key": "gold_coin_001"})

        assert "error" in result
        assert "Invalid item key" in result["error"]
        assert "hint" in result
        assert "gold_coins_001" in str(result["hint"])

    def test_give_item_invalid_key_returns_helpful_error(
        self, db_session: Session, game_session: GameSession
    ):
        """give_item with invalid key returns error with valid key hints."""
        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        # Create manifest with inventory items
        manifest = GroundingManifest(
            location_key="tavern_001",
            location_display="Tavern",
            player_key="player",
            items_at_location={},
            inventory={
                "bread_loaf_001": GroundedEntity(
                    key="bread_loaf_001",
                    display_name="Loaf of Bread",
                    entity_type="item",
                ),
            },
            equipped={},
            npcs={
                "marcus_001": GroundedEntity(
                    key="marcus_001",
                    display_name="Marcus",
                    entity_type="npc",
                ),
            },
            storages={},
            exits={},
        )

        tools = GMTools(db_session, game_session, player.id, manifest=manifest)

        # Try to give with hallucinated key
        result = tools.execute_tool("give_item", {
            "item_key": "bread",
            "recipient_key": "marcus_001",
        })

        assert "error" in result
        assert "Invalid item key" in result["error"]
        assert "hint" in result
        assert "bread_loaf_001" in str(result["hint"])

    def test_take_item_valid_key_proceeds_normally(
        self, db_session: Session, game_session: GameSession
    ):
        """take_item with valid key proceeds to actual item lookup."""
        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        # Create manifest with the key we'll use
        manifest = GroundingManifest(
            location_key="tavern_001",
            location_display="Tavern",
            player_key="player",
            items_at_location={
                "ale_mug_001": GroundedEntity(
                    key="ale_mug_001",
                    display_name="Ale Mug",
                    entity_type="item",
                ),
            },
            inventory={},
            equipped={},
            npcs={},
            storages={},
            exits={},
        )

        tools = GMTools(db_session, game_session, player.id, manifest=manifest)

        # Valid key should proceed past validation (may fail at DB lookup)
        result = tools.execute_tool("take_item", {"item_key": "ale_mug_001"})

        # Should not get "Invalid item key" - should get "Item not found" from DB
        if "error" in result:
            assert "Invalid item key" not in result["error"]
