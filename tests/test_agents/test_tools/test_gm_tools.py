"""Tests for GM tools - LLM function calling tools."""

import pytest
from unittest.mock import patch, MagicMock

from sqlalchemy.orm import Session

from src.database.models.session import GameSession
from src.database.models.entities import Entity
from src.database.models.enums import EntityType
from tests.factories import create_entity, create_relationship, create_item


class TestToolDefinitions:
    """Test tool definition schemas."""

    def test_skill_check_tool_defined(self):
        """skill_check tool should be properly defined."""
        from src.agents.tools.gm_tools import SKILL_CHECK_TOOL

        assert SKILL_CHECK_TOOL.name == "skill_check"
        assert "dc" in [p.name for p in SKILL_CHECK_TOOL.parameters]
        assert "skill_name" in [p.name for p in SKILL_CHECK_TOOL.parameters]

    def test_attack_roll_tool_defined(self):
        """attack_roll tool should be properly defined."""
        from src.agents.tools.gm_tools import ATTACK_ROLL_TOOL

        assert ATTACK_ROLL_TOOL.name == "attack_roll"
        assert "target_ac" in [p.name for p in ATTACK_ROLL_TOOL.parameters]

    def test_roll_damage_tool_defined(self):
        """roll_damage tool should be properly defined."""
        from src.agents.tools.gm_tools import ROLL_DAMAGE_TOOL

        assert ROLL_DAMAGE_TOOL.name == "roll_damage"
        assert "damage_dice" in [p.name for p in ROLL_DAMAGE_TOOL.parameters]

    def test_get_npc_attitude_tool_defined(self):
        """get_npc_attitude tool should be properly defined."""
        from src.agents.tools.gm_tools import GET_NPC_ATTITUDE_TOOL

        assert GET_NPC_ATTITUDE_TOOL.name == "get_npc_attitude"
        assert "from_entity" in [p.name for p in GET_NPC_ATTITUDE_TOOL.parameters]

    def test_update_npc_attitude_tool_defined(self):
        """update_npc_attitude tool should be properly defined."""
        from src.agents.tools.gm_tools import UPDATE_NPC_ATTITUDE_TOOL

        assert UPDATE_NPC_ATTITUDE_TOOL.name == "update_npc_attitude"
        assert "delta" in [p.name for p in UPDATE_NPC_ATTITUDE_TOOL.parameters]

    def test_gm_tools_list(self):
        """GM_TOOLS should contain all tools."""
        from src.agents.tools.gm_tools import GM_TOOLS

        assert len(GM_TOOLS) >= 5
        names = [t.name for t in GM_TOOLS]
        assert "skill_check" in names
        assert "attack_roll" in names
        assert "roll_damage" in names
        assert "get_npc_attitude" in names
        assert "update_npc_attitude" in names

    def test_acquire_item_tool_defined(self):
        """acquire_item tool should be properly defined."""
        from src.agents.tools.gm_tools import ACQUIRE_ITEM_TOOL

        assert ACQUIRE_ITEM_TOOL.name == "acquire_item"
        param_names = [p.name for p in ACQUIRE_ITEM_TOOL.parameters]
        assert "entity_key" in param_names
        assert "display_name" in param_names
        assert "item_type" in param_names

    def test_drop_item_tool_defined(self):
        """drop_item tool should be properly defined."""
        from src.agents.tools.gm_tools import DROP_ITEM_TOOL

        assert DROP_ITEM_TOOL.name == "drop_item"
        param_names = [p.name for p in DROP_ITEM_TOOL.parameters]
        assert "entity_key" in param_names
        assert "item_key" in param_names

    def test_advance_time_tool_defined(self):
        """advance_time tool should be properly defined."""
        from src.agents.tools.gm_tools import ADVANCE_TIME_TOOL

        assert ADVANCE_TIME_TOOL.name == "advance_time"
        param_names = [p.name for p in ADVANCE_TIME_TOOL.parameters]
        assert "minutes" in param_names
        assert "reason" in param_names

    def test_entity_move_tool_defined(self):
        """entity_move tool should be properly defined."""
        from src.agents.tools.gm_tools import ENTITY_MOVE_TOOL

        assert ENTITY_MOVE_TOOL.name == "entity_move"
        param_names = [p.name for p in ENTITY_MOVE_TOOL.parameters]
        assert "entity_key" in param_names
        assert "location_key" in param_names
        assert "create_if_missing" in param_names

    def test_start_combat_tool_defined(self):
        """start_combat tool should be properly defined."""
        from src.agents.tools.gm_tools import START_COMBAT_TOOL

        assert START_COMBAT_TOOL.name == "start_combat"
        param_names = [p.name for p in START_COMBAT_TOOL.parameters]
        assert "enemy_keys" in param_names
        assert "surprise" in param_names
        assert "reason" in param_names

    def test_end_combat_tool_defined(self):
        """end_combat tool should be properly defined."""
        from src.agents.tools.gm_tools import END_COMBAT_TOOL

        assert END_COMBAT_TOOL.name == "end_combat"
        param_names = [p.name for p in END_COMBAT_TOOL.parameters]
        assert "outcome" in param_names

    def test_state_management_tools_in_list(self):
        """State management tools should be in GM_TOOLS list."""
        from src.agents.tools.gm_tools import GM_TOOLS

        names = [t.name for t in GM_TOOLS]
        assert "advance_time" in names
        assert "entity_move" in names
        assert "start_combat" in names
        assert "end_combat" in names


class TestToolExecutor:
    """Test GMToolExecutor execution."""

    def test_execute_skill_check(self, db_session: Session, game_session: GameSession):
        """Execute skill_check tool with entity lookup."""
        from src.agents.tools.executor import GMToolExecutor
        from src.database.models.entities import EntityAttribute, EntitySkill

        # Create a player entity with attributes and skills
        player = create_entity(
            db_session,
            game_session,
            entity_key="player",
            entity_type=EntityType.PLAYER,
        )

        # Add a dexterity attribute (stealth uses dexterity)
        attr = EntityAttribute(
            entity_id=player.id,
            attribute_key="dexterity",
            value=14,
        )
        db_session.add(attr)

        # Add stealth skill
        skill = EntitySkill(
            entity_id=player.id,
            skill_key="stealth",
            proficiency_level=40,  # Competent (+2)
        )
        db_session.add(skill)
        db_session.flush()

        executor = GMToolExecutor(db_session, game_session)

        from src.dice.types import OutcomeTier

        with patch('src.agents.tools.executor.make_skill_check') as mock_check:
            mock_check.return_value = MagicMock(
                success=True,
                roll_result=MagicMock(total=18, individual_rolls=(8, 6)),  # 2d10
                margin=3,
                is_critical_success=False,
                is_critical_failure=False,
                is_auto_success=False,
                outcome_tier=OutcomeTier.NARROW_SUCCESS,
            )

            result = executor.execute("skill_check", {
                "entity_key": "player",
                "dc": 15,
                "skill_name": "stealth",
            })

        assert result["success"] is True
        assert result["roll"] == 18
        assert result["dice_rolls"] == [8, 6]  # 2d10 individual dice
        assert result["skill_name"] == "stealth"
        assert result["is_auto_success"] is False
        assert result["outcome_tier"] == "narrow_success"
        # Check modifiers were looked up
        assert result["attribute_modifier"] == 2  # (14-10)//2 = 2
        assert result["skill_modifier"] == 2  # 40//20 = 2
        assert result["skill_tier"] == "Competent"

    def test_execute_attack_roll_hit(self, db_session: Session, game_session: GameSession):
        """Execute attack_roll tool that hits."""
        from src.agents.tools.executor import GMToolExecutor

        executor = GMToolExecutor(db_session, game_session)

        with patch('src.agents.tools.executor.make_attack_roll') as mock_attack:
            mock_attack.return_value = MagicMock(
                hit=True,
                is_critical_hit=False,
                roll_result=MagicMock(total=18, individual_rolls=(15,)),
            )

            result = executor.execute("attack_roll", {
                "target_ac": 15,
                "attack_bonus": 3,
            })

        assert result["hit"] is True
        assert result["roll"] == 18

    def test_execute_attack_roll_miss(self, db_session: Session, game_session: GameSession):
        """Execute attack_roll tool that misses."""
        from src.agents.tools.executor import GMToolExecutor

        executor = GMToolExecutor(db_session, game_session)

        with patch('src.agents.tools.executor.make_attack_roll') as mock_attack:
            mock_attack.return_value = MagicMock(
                hit=False,
                is_critical_hit=False,
                roll_result=MagicMock(total=10, individual_rolls=(7,)),
            )

            result = executor.execute("attack_roll", {
                "target_ac": 15,
                "attack_bonus": 3,
            })

        assert result["hit"] is False

    def test_execute_roll_damage(self, db_session: Session, game_session: GameSession):
        """Execute roll_damage tool."""
        from src.agents.tools.executor import GMToolExecutor

        executor = GMToolExecutor(db_session, game_session)

        with patch('src.agents.tools.executor.roll_damage') as mock_damage:
            mock_damage.return_value = MagicMock(
                roll_result=MagicMock(total=8, individual_rolls=(5, 3)),
                damage_type="slashing",
                is_critical=False,
            )

            result = executor.execute("roll_damage", {
                "damage_dice": "2d6",
                "damage_type": "slashing",
                "bonus": 2,
            })

        assert result["total"] == 8
        assert result["damage_type"] == "slashing"

    def test_execute_get_npc_attitude(self, db_session: Session, game_session: GameSession):
        """Execute get_npc_attitude tool."""
        from src.agents.tools.executor import GMToolExecutor

        npc = create_entity(db_session, game_session, entity_type=EntityType.NPC,
                           entity_key="bartender")
        player = create_entity(db_session, game_session, entity_type=EntityType.PLAYER,
                              entity_key="hero")
        create_relationship(db_session, game_session, npc, player,
                          trust=60, liking=70, respect=50)

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("get_npc_attitude", {
            "from_entity": "bartender",
            "to_entity": "hero",
        })

        assert result["trust"] == 60
        assert result["liking"] == 70
        assert result["respect"] == 50

    def test_execute_update_npc_attitude(self, db_session: Session, game_session: GameSession):
        """Execute update_npc_attitude tool."""
        from src.agents.tools.executor import GMToolExecutor

        npc = create_entity(db_session, game_session, entity_type=EntityType.NPC,
                           entity_key="bartender")
        player = create_entity(db_session, game_session, entity_type=EntityType.PLAYER,
                              entity_key="hero")
        rel = create_relationship(db_session, game_session, npc, player,
                                 trust=50, liking=50, familiarity=50)

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("update_npc_attitude", {
            "from_entity": "bartender",
            "to_entity": "hero",
            "dimension": "trust",
            "delta": 10,
            "reason": "Player helped fix the bar",
        })

        assert result["new_value"] == 60
        assert result["delta"] == 10

    def test_execute_unknown_tool_raises(self, db_session: Session, game_session: GameSession):
        """Unknown tool should raise ValueError."""
        from src.agents.tools.executor import GMToolExecutor

        executor = GMToolExecutor(db_session, game_session)

        with pytest.raises(ValueError, match="Unknown tool"):
            executor.execute("unknown_tool", {})

    def test_execute_view_map(self, db_session: Session, game_session: GameSession):
        """Execute view_map tool."""
        from src.agents.tools.executor import GMToolExecutor
        from src.database.models.enums import MapType
        from tests.factories import (
            create_item,
            create_map_item,
            create_terrain_zone,
        )

        # Create viewer entity
        player = create_entity(db_session, game_session, entity_type=EntityType.PLAYER,
                              entity_key="player")

        # Create zones and a map
        zone1 = create_terrain_zone(db_session, game_session, zone_key="forest")
        zone2 = create_terrain_zone(db_session, game_session, zone_key="mountain")
        db_session.flush()

        item = create_item(db_session, game_session, item_key="old_map")
        create_map_item(
            db_session,
            game_session,
            item=item,
            map_type=MapType.REGIONAL,
            revealed_zone_ids=[zone1.id, zone2.id],
        )
        db_session.commit()

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("view_map", {
            "item_key": "old_map",
            "viewer_entity_key": "player",
        })

        assert result["success"] is True
        assert result["item_key"] == "old_map"
        assert len(result["zones_discovered"]) == 2
        assert "forest" in result["zones_discovered"]
        assert "mountain" in result["zones_discovered"]

    def test_execute_acquire_item_success(self, db_session: Session, game_session: GameSession):
        """Execute acquire_item tool successfully creates and assigns item."""
        from src.agents.tools.executor import GMToolExecutor

        player = create_entity(
            db_session, game_session,
            entity_key="player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("acquire_item", {
            "entity_key": "player",
            "display_name": "Iron Sword",
            "item_type": "weapon",
            "item_size": "medium",
        })

        assert result["success"] is True
        assert result["display_name"] == "Iron Sword"
        assert result["assigned_slot"] == "main_hand"
        assert "item_key" in result

    def test_execute_acquire_item_auto_assigns_slot(self, db_session: Session, game_session: GameSession):
        """acquire_item auto-assigns slot based on item type."""
        from src.agents.tools.executor import GMToolExecutor

        player = create_entity(
            db_session, game_session,
            entity_key="player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        executor = GMToolExecutor(db_session, game_session)

        # First weapon goes to main_hand
        result1 = executor.execute("acquire_item", {
            "entity_key": "player",
            "display_name": "Sword",
            "item_type": "weapon",
        })
        assert result1["success"] is True
        assert result1["assigned_slot"] == "main_hand"

        # Second weapon goes to off_hand
        result2 = executor.execute("acquire_item", {
            "entity_key": "player",
            "display_name": "Dagger",
            "item_type": "weapon",
        })
        assert result2["success"] is True
        assert result2["assigned_slot"] == "off_hand"

    def test_execute_acquire_item_fails_when_slots_full(self, db_session: Session, game_session: GameSession):
        """acquire_item fails gracefully when no slots available."""
        from src.agents.tools.executor import GMToolExecutor

        player = create_entity(
            db_session, game_session,
            entity_key="player",
            entity_type=EntityType.PLAYER,
        )
        # Fill all weapon slots
        create_item(db_session, game_session, item_key="sword",
                   holder_id=player.id, body_slot="main_hand")
        create_item(db_session, game_session, item_key="shield",
                   holder_id=player.id, body_slot="off_hand")
        create_item(db_session, game_session, item_key="bow",
                   holder_id=player.id, body_slot="back")
        db_session.flush()

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("acquire_item", {
            "entity_key": "player",
            "display_name": "Spear",
            "item_type": "weapon",
        })

        assert result["success"] is False
        assert "reason" in result
        assert "suggestion" in result

    def test_execute_acquire_item_fails_when_slot_occupied(self, db_session: Session, game_session: GameSession):
        """acquire_item fails when specific slot is occupied."""
        from src.agents.tools.executor import GMToolExecutor

        player = create_entity(
            db_session, game_session,
            entity_key="player",
            entity_type=EntityType.PLAYER,
        )
        create_item(db_session, game_session, item_key="torch",
                   holder_id=player.id, body_slot="main_hand",
                   display_name="Lit Torch")
        db_session.flush()

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("acquire_item", {
            "entity_key": "player",
            "display_name": "Sword",
            "item_type": "weapon",
            "slot": "main_hand",  # Specifically request main_hand
        })

        assert result["success"] is False
        assert "occupied" in result["reason"].lower()
        assert "Lit Torch" in result.get("occupied_by", "")

    def test_execute_acquire_item_weight_validation(self, db_session: Session, game_session: GameSession):
        """acquire_item validates weight limits."""
        from src.agents.tools.executor import GMToolExecutor

        player = create_entity(
            db_session, game_session,
            entity_key="player",
            entity_type=EntityType.PLAYER,
        )
        # Add heavy existing items
        create_item(db_session, game_session, item_key="armor",
                   holder_id=player.id, weight=45.0)
        db_session.flush()

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("acquire_item", {
            "entity_key": "player",
            "display_name": "Heavy Chest",
            "item_type": "misc",
            "item_size": "large",
            "weight": 20.0,
        })

        assert result["success"] is False
        assert "heavy" in result["reason"].lower() or "weight" in result["reason"].lower()

    def test_execute_acquire_item_with_quantity(self, db_session: Session, game_session: GameSession):
        """acquire_item handles quantity parameter."""
        from src.agents.tools.executor import GMToolExecutor
        from src.managers.item_manager import ItemManager

        player = create_entity(
            db_session, game_session,
            entity_key="player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("acquire_item", {
            "entity_key": "player",
            "display_name": "Gold Coins",
            "item_type": "misc",
            "quantity": 10,
        })

        assert result["success"] is True

        # Verify quantity was set
        item_mgr = ItemManager(db_session, game_session)
        item = item_mgr.get_item(result["item_key"])
        assert item.quantity == 10

    def test_execute_drop_item_success(self, db_session: Session, game_session: GameSession):
        """Execute drop_item tool successfully removes item from holder."""
        from src.agents.tools.executor import GMToolExecutor
        from src.managers.item_manager import ItemManager

        player = create_entity(
            db_session, game_session,
            entity_key="player",
            entity_type=EntityType.PLAYER,
        )
        item = create_item(db_session, game_session, item_key="torch",
                          holder_id=player.id, body_slot="off_hand",
                          display_name="Torch")
        db_session.flush()

        executor = GMToolExecutor(db_session, game_session, current_zone_key="town_square")
        result = executor.execute("drop_item", {
            "entity_key": "player",
            "item_key": "torch",
        })
        assert result["success"] is True
        assert result["item_key"] == "torch"
        assert result["dropped"] is True

        # Verify item no longer held
        item_mgr = ItemManager(db_session, game_session)
        db_session.refresh(item)
        assert item.holder_id is None
        assert item.body_slot is None

    def test_execute_drop_item_transfer_to_other(self, db_session: Session, game_session: GameSession):
        """Execute drop_item with transfer_to gives item to another entity."""
        from src.agents.tools.executor import GMToolExecutor
        from src.managers.item_manager import ItemManager

        player = create_entity(
            db_session, game_session,
            entity_key="player",
            entity_type=EntityType.PLAYER,
        )
        npc = create_entity(
            db_session, game_session,
            entity_key="merchant",
            entity_type=EntityType.NPC,
        )
        item = create_item(db_session, game_session, item_key="gold",
                          holder_id=player.id, body_slot="belt_pouch_1",
                          display_name="Gold Pouch")
        db_session.flush()

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("drop_item", {
            "entity_key": "player",
            "item_key": "gold",
            "transfer_to": "merchant",
        })

        assert result["success"] is True
        assert result["to_entity"] == "merchant"

        # Verify item transferred
        item_mgr = ItemManager(db_session, game_session)
        db_session.refresh(item)
        assert item.holder_id == npc.id

    def test_execute_drop_item_not_found(self, db_session: Session, game_session: GameSession):
        """drop_item fails gracefully when item not found."""
        from src.agents.tools.executor import GMToolExecutor

        player = create_entity(
            db_session, game_session,
            entity_key="player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("drop_item", {
            "entity_key": "player",
            "item_key": "nonexistent",
        })

        assert result["success"] is False
        assert "error" in result

    def test_execute_drop_item_not_held_by_entity(self, db_session: Session, game_session: GameSession):
        """drop_item fails when item not held by specified entity."""
        from src.agents.tools.executor import GMToolExecutor

        player = create_entity(
            db_session, game_session,
            entity_key="player",
            entity_type=EntityType.PLAYER,
        )
        npc = create_entity(
            db_session, game_session,
            entity_key="thief",
            entity_type=EntityType.NPC,
        )
        # Item held by NPC, not player
        item = create_item(db_session, game_session, item_key="stolen_gem",
                          holder_id=npc.id, display_name="Stolen Gem")
        db_session.flush()

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("drop_item", {
            "entity_key": "player",
            "item_key": "stolen_gem",
        })

        assert result["success"] is False
        assert "not holding" in result["error"].lower() or "not held" in result["error"].lower()

    # =========================================================================
    # State Management Tool Tests
    # =========================================================================

    def test_execute_advance_time(self, db_session: Session, game_session: GameSession):
        """Execute advance_time tool updates time state and pending_state_updates."""
        from src.agents.tools.executor import GMToolExecutor
        from src.database.models.world import TimeState

        # Create time state
        time_state = TimeState(
            session_id=game_session.id,
            current_day=1,
            current_time="10:00",
        )
        db_session.add(time_state)
        db_session.flush()

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("advance_time", {
            "minutes": 30,
            "reason": "walking to the forge",
        })

        assert result["success"] is True
        assert result["minutes_advanced"] == 30
        assert result["old_time"] == "10:00"
        assert result["new_time"] == "10:30"

        # Check pending state updates
        assert executor.pending_state_updates["time_advance_minutes"] == 30

    def test_execute_advance_time_day_rollover(self, db_session: Session, game_session: GameSession):
        """advance_time handles day rollover correctly."""
        from src.agents.tools.executor import GMToolExecutor
        from src.database.models.world import TimeState

        time_state = TimeState(
            session_id=game_session.id,
            current_day=1,
            current_time="23:30",
        )
        db_session.add(time_state)
        db_session.flush()

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("advance_time", {
            "minutes": 60,
        })

        assert result["success"] is True
        assert result["new_time"] == "00:30"
        assert result["new_day"] == 2
        assert result["days_passed"] == 1

    def test_execute_entity_move_player(self, db_session: Session, game_session: GameSession):
        """entity_move for player updates pending_state_updates."""
        from src.agents.tools.executor import GMToolExecutor
        from src.database.models.world import Location

        player = create_entity(
            db_session, game_session,
            entity_key="player",
            entity_type=EntityType.PLAYER,
        )
        location = Location(
            session_id=game_session.id,
            location_key="village_square",
            display_name="Village Square",
            description="The central square of the village.",
        )
        db_session.add(location)
        db_session.flush()

        executor = GMToolExecutor(db_session, game_session, current_zone_key="inn_common_room")
        result = executor.execute("entity_move", {
            "entity_key": "player",
            "location_key": "village_square",
        })

        assert result["success"] is True
        assert result["new_location"] == "village_square"
        assert result["location_name"] == "Village Square"

        # Check pending state updates for player
        assert executor.pending_state_updates["location_changed"] is True
        assert executor.pending_state_updates["player_location"] == "village_square"

    def test_execute_entity_move_npc(self, db_session: Session, game_session: GameSession):
        """entity_move for NPC updates NPCExtension, not pending_state_updates."""
        from src.agents.tools.executor import GMToolExecutor
        from src.database.models.world import Location
        from src.database.models.entities import NPCExtension

        npc = create_entity(
            db_session, game_session,
            entity_key="npc_blacksmith",
            entity_type=EntityType.NPC,
            display_name="Blacksmith",
        )
        # Create NPC extension
        npc_ext = NPCExtension(
            entity_id=npc.id,
            current_location="forge",
        )
        db_session.add(npc_ext)

        location = Location(
            session_id=game_session.id,
            location_key="tavern",
            display_name="Tavern",
            description="A cozy tavern.",
        )
        db_session.add(location)
        db_session.flush()

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("entity_move", {
            "entity_key": "npc_blacksmith",
            "location_key": "tavern",
        })

        assert result["success"] is True
        assert result["entity_key"] == "npc_blacksmith"
        assert result["new_location"] == "tavern"

        # NPC movement shouldn't set player location updates
        assert "location_changed" not in executor.pending_state_updates
        assert "player_location" not in executor.pending_state_updates

        # But NPC's location should be updated in DB
        db_session.refresh(npc_ext)
        assert npc_ext.current_location == "tavern"

    def test_execute_entity_move_creates_location(self, db_session: Session, game_session: GameSession):
        """entity_move creates location if create_if_missing is true."""
        from src.agents.tools.executor import GMToolExecutor
        from src.database.models.world import Location

        player = create_entity(
            db_session, game_session,
            entity_key="player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("entity_move", {
            "entity_key": "player",
            "location_key": "new_forest_clearing",
            "create_if_missing": True,
        })

        assert result["success"] is True

        # Verify location was created
        location = db_session.query(Location).filter(
            Location.session_id == game_session.id,
            Location.location_key == "new_forest_clearing",
        ).first()
        assert location is not None
        assert location.display_name == "New Forest Clearing"

    def test_execute_entity_move_fails_without_create(self, db_session: Session, game_session: GameSession):
        """entity_move fails if location missing and create_if_missing=False."""
        from src.agents.tools.executor import GMToolExecutor

        player = create_entity(
            db_session, game_session,
            entity_key="player",
            entity_type=EntityType.PLAYER,
        )
        db_session.flush()

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("entity_move", {
            "entity_key": "player",
            "location_key": "nonexistent_place",
            "create_if_missing": False,
        })

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_execute_start_combat(self, db_session: Session, game_session: GameSession):
        """start_combat sets combat state in pending_state_updates."""
        from src.agents.tools.executor import GMToolExecutor

        player = create_entity(
            db_session, game_session,
            entity_key="player",
            entity_type=EntityType.PLAYER,
        )
        bandit = create_entity(
            db_session, game_session,
            entity_key="npc_bandit",
            entity_type=EntityType.NPC,
            display_name="Bandit",
        )
        db_session.flush()

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("start_combat", {
            "enemy_keys": ["npc_bandit"],
            "surprise": "enemies",
            "reason": "ambush",
        })

        assert result["success"] is True
        assert result["combat_started"] is True
        assert len(result["enemies"]) == 1
        assert result["enemies"][0]["entity_key"] == "npc_bandit"
        assert result["surprise"] == "enemies"

        # Check pending state updates
        assert executor.pending_state_updates["combat_active"] is True
        assert executor.pending_state_updates["combat_state"]["enemies"][0]["entity_key"] == "npc_bandit"

    def test_execute_start_combat_missing_enemies(self, db_session: Session, game_session: GameSession):
        """start_combat fails if enemies not found."""
        from src.agents.tools.executor import GMToolExecutor

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("start_combat", {
            "enemy_keys": ["nonexistent_enemy"],
            "reason": "attack",
        })

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_execute_end_combat(self, db_session: Session, game_session: GameSession):
        """end_combat clears combat state in pending_state_updates."""
        from src.agents.tools.executor import GMToolExecutor

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("end_combat", {
            "outcome": "victory",
            "summary": "The bandit was defeated.",
        })

        assert result["success"] is True
        assert result["combat_ended"] is True
        assert result["outcome"] == "victory"

        # Check pending state updates
        assert executor.pending_state_updates["combat_active"] is False
        assert executor.pending_state_updates["combat_state"] is None

    def test_pending_state_updates_initialized(self, db_session: Session, game_session: GameSession):
        """pending_state_updates should be an empty dict on init."""
        from src.agents.tools.executor import GMToolExecutor

        executor = GMToolExecutor(db_session, game_session)
        assert executor.pending_state_updates == {}


class TestToolSchemas:
    """Test tool JSON schema generation."""

    def test_skill_check_to_json_schema(self):
        """Tool should generate valid JSON schema."""
        from src.agents.tools.gm_tools import SKILL_CHECK_TOOL

        schema = SKILL_CHECK_TOOL.to_json_schema()

        assert "properties" in schema
        assert "dc" in schema["properties"]
        assert schema["properties"]["dc"]["type"] == "integer"

    def test_attack_roll_to_anthropic_format(self):
        """Tool should convert to Anthropic format."""
        from src.agents.tools.gm_tools import ATTACK_ROLL_TOOL

        anthropic_tool = ATTACK_ROLL_TOOL.to_anthropic_format()

        assert anthropic_tool["name"] == "attack_roll"
        assert "input_schema" in anthropic_tool


class TestPhase2ToolDefinitions:
    """Test Phase 2 tool definitions."""

    def test_quest_tools_defined(self):
        """Quest management tools should be defined."""
        from src.agents.tools.gm_tools import (
            ASSIGN_QUEST_TOOL,
            UPDATE_QUEST_TOOL,
            COMPLETE_QUEST_TOOL,
            GM_TOOLS,
        )

        assert ASSIGN_QUEST_TOOL.name == "assign_quest"
        assert UPDATE_QUEST_TOOL.name == "update_quest"
        assert COMPLETE_QUEST_TOOL.name == "complete_quest"

        # All should be in GM_TOOLS
        tool_names = [t.name for t in GM_TOOLS]
        assert "assign_quest" in tool_names
        assert "update_quest" in tool_names
        assert "complete_quest" in tool_names

    def test_record_fact_tool_defined(self):
        """Record fact tool should be defined."""
        from src.agents.tools.gm_tools import RECORD_FACT_TOOL, GM_TOOLS

        assert RECORD_FACT_TOOL.name == "record_fact"
        assert "record_fact" in [t.name for t in GM_TOOLS]

    def test_npc_scene_tools_defined(self):
        """NPC scene management tools should be defined."""
        from src.agents.tools.gm_tools import (
            INTRODUCE_NPC_TOOL,
            NPC_LEAVES_TOOL,
            GM_TOOLS,
        )

        assert INTRODUCE_NPC_TOOL.name == "introduce_npc"
        assert NPC_LEAVES_TOOL.name == "npc_leaves"

        tool_names = [t.name for t in GM_TOOLS]
        assert "introduce_npc" in tool_names
        assert "npc_leaves" in tool_names


class TestPhase2ToolExecutors:
    """Test Phase 2 tool execution handlers."""

    def test_execute_assign_quest(self, db_session: Session, game_session: GameSession):
        """assign_quest creates a new quest record."""
        from src.agents.tools.executor import GMToolExecutor
        from src.database.models.tasks import Quest
        from src.database.models.enums import QuestStatus

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("assign_quest", {
            "quest_key": "find_lost_ring",
            "title": "The Lost Ring",
            "description": "Find the ring that was lost in the forest.",
            "rewards": "50 gold coins",
        })

        assert result["success"] is True
        assert result["quest_key"] == "find_lost_ring"

        # Verify quest was created
        quest = db_session.query(Quest).filter(
            Quest.session_id == game_session.id,
            Quest.quest_key == "find_lost_ring",
        ).first()
        assert quest is not None
        assert quest.name == "The Lost Ring"
        assert quest.status == QuestStatus.ACTIVE

    def test_execute_assign_quest_duplicate_fails(self, db_session: Session, game_session: GameSession):
        """assign_quest fails if quest already exists."""
        from src.agents.tools.executor import GMToolExecutor
        from src.database.models.tasks import Quest
        from src.database.models.enums import QuestStatus

        # Create existing quest
        quest = Quest(
            session_id=game_session.id,
            quest_key="existing_quest",
            name="Existing Quest",
            description="Already exists",
            status=QuestStatus.ACTIVE,
        )
        db_session.add(quest)
        db_session.flush()

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("assign_quest", {
            "quest_key": "existing_quest",
            "title": "New Title",
            "description": "New description",
        })

        assert result["success"] is False
        assert "already exists" in result["reason"]

    def test_execute_update_quest(self, db_session: Session, game_session: GameSession):
        """update_quest advances quest stage."""
        from src.agents.tools.executor import GMToolExecutor
        from src.database.models.tasks import Quest
        from src.database.models.enums import QuestStatus

        # Create quest
        quest = Quest(
            session_id=game_session.id,
            quest_key="test_quest",
            name="Test Quest",
            description="For testing",
            status=QuestStatus.ACTIVE,
            current_stage=0,
        )
        db_session.add(quest)
        db_session.flush()

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("update_quest", {
            "quest_key": "test_quest",
            "new_stage": 1,
            "stage_name": "Find the witness",
            "stage_description": "Locate the witness in the tavern",
        })

        assert result["success"] is True
        assert result["current_stage"] == 1

        # Verify quest was updated
        db_session.refresh(quest)
        assert quest.current_stage == 1

    def test_execute_complete_quest(self, db_session: Session, game_session: GameSession):
        """complete_quest marks quest as completed."""
        from src.agents.tools.executor import GMToolExecutor
        from src.database.models.tasks import Quest
        from src.database.models.enums import QuestStatus

        # Create quest
        quest = Quest(
            session_id=game_session.id,
            quest_key="completable_quest",
            name="Completable Quest",
            description="Can be completed",
            status=QuestStatus.ACTIVE,
        )
        db_session.add(quest)
        db_session.flush()

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("complete_quest", {
            "quest_key": "completable_quest",
            "outcome": "completed",
        })

        assert result["success"] is True
        assert result["outcome"] == "completed"

        # Verify quest was updated
        db_session.refresh(quest)
        assert quest.status == QuestStatus.COMPLETED

    def test_execute_record_fact_create(self, db_session: Session, game_session: GameSession):
        """record_fact creates a new fact record."""
        from src.agents.tools.executor import GMToolExecutor
        from src.database.models.world import Fact

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("record_fact", {
            "subject_type": "entity",
            "subject_key": "npc_marta",
            "predicate": "has_job",
            "value": "innkeeper",
        })

        assert result["success"] is True
        assert result["created"] is True

        # Verify fact was created
        fact = db_session.query(Fact).filter(
            Fact.session_id == game_session.id,
            Fact.subject_key == "npc_marta",
            Fact.predicate == "has_job",
        ).first()
        assert fact is not None
        assert fact.value == "innkeeper"

    def test_execute_record_fact_update_existing(self, db_session: Session, game_session: GameSession):
        """record_fact updates existing fact with same subject+predicate."""
        from src.agents.tools.executor import GMToolExecutor
        from src.database.models.world import Fact
        from src.database.models.enums import FactCategory

        # Create existing fact
        fact = Fact(
            session_id=game_session.id,
            subject_type="entity",
            subject_key="npc_tom",
            predicate="mood",
            value="happy",
            category=FactCategory.PERSONAL,
            source_turn=1,
        )
        db_session.add(fact)
        db_session.flush()

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("record_fact", {
            "subject_type": "entity",
            "subject_key": "npc_tom",
            "predicate": "mood",
            "value": "angry",
        })

        assert result["success"] is True
        assert result["updated"] is True

        # Verify fact was updated (not duplicated)
        db_session.refresh(fact)
        assert fact.value == "angry"
        count = db_session.query(Fact).filter(
            Fact.session_id == game_session.id,
            Fact.subject_key == "npc_tom",
            Fact.predicate == "mood",
        ).count()
        assert count == 1

    def test_execute_introduce_npc_create(self, db_session: Session, game_session: GameSession):
        """introduce_npc creates new NPC with extension."""
        from src.agents.tools.executor import GMToolExecutor
        from src.database.models.entities import Entity, NPCExtension
        from src.database.models.enums import EntityType

        # Create player for relationship
        player = Entity(
            session_id=game_session.id,
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
            is_alive=True,
            is_active=True,
        )
        db_session.add(player)
        db_session.flush()

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("introduce_npc", {
            "entity_key": "npc_blacksmith",
            "display_name": "Tom the Blacksmith",
            "description": "A burly man with soot-stained hands.",
            "location_key": "forge",
            "occupation": "blacksmith",
            "initial_attitude": "friendly",
        })

        assert result["success"] is True
        assert result["created"] is True

        # Verify NPC was created
        npc = db_session.query(Entity).filter(
            Entity.session_id == game_session.id,
            Entity.entity_key == "npc_blacksmith",
        ).first()
        assert npc is not None
        assert npc.display_name == "Tom the Blacksmith"

        # Verify NPC extension
        npc_ext = db_session.query(NPCExtension).filter(
            NPCExtension.entity_id == npc.id,
        ).first()
        assert npc_ext is not None
        assert npc_ext.current_location == "forge"
        assert npc_ext.job == "blacksmith"

    def test_execute_introduce_npc_existing(self, db_session: Session, game_session: GameSession):
        """introduce_npc updates location for existing NPC."""
        from src.agents.tools.executor import GMToolExecutor
        from src.database.models.entities import Entity, NPCExtension
        from src.database.models.enums import EntityType

        # Create existing NPC
        npc = Entity(
            session_id=game_session.id,
            entity_key="npc_existing",
            display_name="Existing NPC",
            entity_type=EntityType.NPC,
            is_alive=True,
            is_active=True,
        )
        db_session.add(npc)
        db_session.flush()

        npc_ext = NPCExtension(
            entity_id=npc.id,
            current_location="old_location",
        )
        db_session.add(npc_ext)
        db_session.flush()

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("introduce_npc", {
            "entity_key": "npc_existing",
            "display_name": "Existing NPC",
            "description": "An existing NPC",
            "location_key": "new_location",
        })

        assert result["success"] is True
        assert result["created"] is False  # Not newly created

        # Verify location updated
        db_session.refresh(npc_ext)
        assert npc_ext.current_location == "new_location"

    def test_execute_npc_leaves(self, db_session: Session, game_session: GameSession):
        """npc_leaves updates NPC location."""
        from src.agents.tools.executor import GMToolExecutor
        from src.database.models.entities import Entity, NPCExtension
        from src.database.models.enums import EntityType

        # Create NPC
        npc = Entity(
            session_id=game_session.id,
            entity_key="npc_leaving",
            display_name="Leaving NPC",
            entity_type=EntityType.NPC,
            is_alive=True,
            is_active=True,
        )
        db_session.add(npc)
        db_session.flush()

        npc_ext = NPCExtension(
            entity_id=npc.id,
            current_location="tavern",
        )
        db_session.add(npc_ext)
        db_session.flush()

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("npc_leaves", {
            "entity_key": "npc_leaving",
            "destination": "home",
            "reason": "The day is done",
        })

        assert result["success"] is True
        assert result["destination"] == "home"

        # Verify location updated
        db_session.refresh(npc_ext)
        assert npc_ext.current_location == "home"

    def test_execute_npc_leaves_not_found(self, db_session: Session, game_session: GameSession):
        """npc_leaves fails if NPC not found."""
        from src.agents.tools.executor import GMToolExecutor

        executor = GMToolExecutor(db_session, game_session)
        result = executor.execute("npc_leaves", {
            "entity_key": "nonexistent_npc",
            "destination": "somewhere",
        })

        assert result["success"] is False
        assert "not found" in result["reason"]


class TestSpawnToolDefinitions:
    """Test spawn tool definition schemas."""

    def test_spawn_storage_tool_defined(self):
        """spawn_storage tool should be properly defined."""
        from src.agents.tools.gm_tools import SPAWN_STORAGE_TOOL

        assert SPAWN_STORAGE_TOOL.name == "spawn_storage"
        param_names = [p.name for p in SPAWN_STORAGE_TOOL.parameters]
        assert "container_type" in param_names
        assert "description" in param_names
        assert "is_fixed" in param_names
        assert "capacity" in param_names

    def test_spawn_item_tool_defined(self):
        """spawn_item tool should be properly defined."""
        from src.agents.tools.gm_tools import SPAWN_ITEM_TOOL

        assert SPAWN_ITEM_TOOL.name == "spawn_item"
        param_names = [p.name for p in SPAWN_ITEM_TOOL.parameters]
        assert "display_name" in param_names
        assert "description" in param_names
        assert "item_type" in param_names
        assert "surface" in param_names

    def test_spawn_tools_in_list(self):
        """Spawn tools should be in GM_TOOLS list."""
        from src.agents.tools.gm_tools import GM_TOOLS

        names = [t.name for t in GM_TOOLS]
        assert "spawn_storage" in names
        assert "spawn_item" in names


class TestSpawnToolExecutor:
    """Test spawn tool execution."""

    def test_execute_spawn_storage(self, db_session: Session, game_session: GameSession):
        """spawn_storage creates storage at current location."""
        from src.agents.tools.executor import GMToolExecutor
        from src.database.models.world import Location
        from src.database.models.items import StorageLocation

        # Create a location
        location = Location(
            session_id=game_session.id,
            location_key="test_cottage",
            display_name="Test Cottage",
            description="A small cottage",
        )
        db_session.add(location)
        db_session.flush()

        executor = GMToolExecutor(
            db_session, game_session, current_zone_key="test_cottage"
        )

        result = executor.execute("spawn_storage", {
            "container_type": "table",
            "description": "A sturdy oak table",
        })

        assert result["success"] is True
        assert result["container_type"] == "table"
        assert "table" in result["storage_key"]

        # Verify storage was created
        storage = db_session.query(StorageLocation).filter(
            StorageLocation.location_key == result["storage_key"]
        ).first()
        assert storage is not None
        assert storage.container_type == "table"
        assert storage.world_location_id == location.id

    def test_execute_spawn_storage_creates_location(self, db_session: Session, game_session: GameSession):
        """spawn_storage creates location record if it doesn't exist."""
        from src.agents.tools.executor import GMToolExecutor
        from src.database.models.world import Location

        executor = GMToolExecutor(
            db_session, game_session, current_zone_key="new_location"
        )

        result = executor.execute("spawn_storage", {
            "container_type": "shelf",
            "description": "A wooden shelf",
        })

        assert result["success"] is True

        # Verify location was created
        location = db_session.query(Location).filter(
            Location.location_key == "new_location"
        ).first()
        assert location is not None

    def test_execute_spawn_storage_no_location(self, db_session: Session, game_session: GameSession):
        """spawn_storage fails if no current location set."""
        from src.agents.tools.executor import GMToolExecutor

        executor = GMToolExecutor(
            db_session, game_session, current_zone_key=None
        )

        result = executor.execute("spawn_storage", {
            "container_type": "table",
        })

        assert result["success"] is False
        assert "unknown" in result["error"].lower()

    def test_execute_spawn_item(self, db_session: Session, game_session: GameSession):
        """spawn_item creates item at storage location."""
        from src.agents.tools.executor import GMToolExecutor
        from src.database.models.world import Location
        from src.database.models.items import StorageLocation, Item

        # Create location and storage
        location = Location(
            session_id=game_session.id,
            location_key="test_room",
            display_name="Test Room",
            description="A test room",
        )
        db_session.add(location)
        db_session.flush()

        from src.managers.item_manager import ItemManager
        from src.database.models.enums import StorageLocationType
        item_mgr = ItemManager(db_session, game_session)
        storage = item_mgr.create_storage(
            location_key="test_room_table_1",
            location_type=StorageLocationType.PLACE,
            container_type="table",
            world_location_id=location.id,
        )

        executor = GMToolExecutor(
            db_session, game_session, current_zone_key="test_room"
        )

        result = executor.execute("spawn_item", {
            "display_name": "Half-loaf of Bread",
            "description": "A half-eaten loaf of brown bread",
            "item_type": "consumable",
            "surface": "table",
        })

        assert result["success"] is True
        assert "bread" in result["item_key"].lower()
        assert result["surface"] == "table"

        # Verify item was created
        item = db_session.query(Item).filter(
            Item.item_key == result["item_key"]
        ).first()
        assert item is not None
        assert item.display_name == "Half-loaf of Bread"
        assert item.storage_location_id == storage.id

    def test_execute_spawn_item_no_storage(self, db_session: Session, game_session: GameSession):
        """spawn_item fails if storage surface doesn't exist."""
        from src.agents.tools.executor import GMToolExecutor
        from src.database.models.world import Location

        # Create location but no storage
        location = Location(
            session_id=game_session.id,
            location_key="empty_room",
            display_name="Empty Room",
            description="A room with nothing in it",
        )
        db_session.add(location)
        db_session.flush()

        executor = GMToolExecutor(
            db_session, game_session, current_zone_key="empty_room"
        )

        result = executor.execute("spawn_item", {
            "display_name": "Sword",
            "description": "A sword",
            "item_type": "weapon",
            "surface": "table",
        })

        assert result["success"] is False
        assert "spawn_storage" in result["suggestion"]

    def test_execute_spawn_item_no_location(self, db_session: Session, game_session: GameSession):
        """spawn_item fails if location doesn't exist."""
        from src.agents.tools.executor import GMToolExecutor

        executor = GMToolExecutor(
            db_session, game_session, current_zone_key="nonexistent"
        )

        result = executor.execute("spawn_item", {
            "display_name": "Sword",
            "description": "A sword",
            "item_type": "weapon",
        })

        assert result["success"] is False

    def test_spawn_workflow(self, db_session: Session, game_session: GameSession):
        """Full workflow: spawn storage, then spawn items on it."""
        from src.agents.tools.executor import GMToolExecutor
        from src.database.models.world import Location
        from src.database.models.items import Item

        # Create location
        location = Location(
            session_id=game_session.id,
            location_key="cottage",
            display_name="Cottage",
            description="A cozy cottage",
        )
        db_session.add(location)
        db_session.flush()

        executor = GMToolExecutor(
            db_session, game_session, current_zone_key="cottage"
        )

        # First spawn storage
        storage_result = executor.execute("spawn_storage", {
            "container_type": "table",
            "description": "A wooden table",
        })
        assert storage_result["success"] is True

        # Then spawn items on it
        item_result = executor.execute("spawn_item", {
            "display_name": "Clay Bowl",
            "description": "A simple clay bowl",
            "item_type": "misc",
            "surface": "table",
        })
        assert item_result["success"] is True

        # Verify item is on the table
        item = db_session.query(Item).filter(
            Item.item_key == item_result["item_key"]
        ).first()
        assert item is not None
        assert item.storage_location_id is not None
