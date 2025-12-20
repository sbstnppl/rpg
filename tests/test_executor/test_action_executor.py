"""Tests for ActionExecutor class."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.enums import EntityType, ItemType
from src.database.models.items import Item
from src.database.models.session import GameSession
from src.parser.action_types import Action, ActionType
from src.validators.action_validator import ValidationResult
from src.executor.action_executor import ActionExecutor
from tests.factories import (
    create_entity,
    create_item,
    create_location,
    create_entity_attribute,
    create_time_state,
    create_character_needs,
)


class TestActionExecutorBasics:
    """Tests for ActionExecutor basic operations."""

    def test_executor_creation(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify ActionExecutor can be instantiated."""
        executor = ActionExecutor(db_session, game_session)

        assert executor is not None
        assert executor.db == db_session
        assert executor.game_session == game_session

    def test_executor_lazy_loads_managers(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify managers are lazy-loaded on first access."""
        executor = ActionExecutor(db_session, game_session)

        # Managers should not be loaded yet
        assert len(executor._managers_cache) == 0

        # Access a manager
        _ = executor.item_manager

        # Now it should be cached
        assert "item" in executor._managers_cache


class TestTakeExecution:
    """Tests for TAKE action execution."""

    @pytest.mark.asyncio
    async def test_take_transfers_item_to_actor(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify TAKE transfers item to actor's inventory."""
        entity = create_entity(db_session, game_session, entity_key="player")
        item = create_item(
            db_session, game_session,
            item_key="gold_coin",
            display_name="Gold Coin",
            holder_id=None  # Not held by anyone
        )

        executor = ActionExecutor(db_session, game_session)
        action = Action(type=ActionType.TAKE, target="gold_coin")
        validation = ValidationResult(
            action=action,
            valid=True,
            resolved_target="gold_coin",
            metadata={"item_id": item.id}
        )

        result = await executor._execute_take(validation, entity)

        assert result.success is True
        assert "picked up" in result.outcome.lower() or "gold coin" in result.outcome.lower()

        # Verify item is now held by entity
        db_session.refresh(item)
        assert item.holder_id == entity.id


class TestDropExecution:
    """Tests for DROP action execution."""

    @pytest.mark.asyncio
    async def test_drop_removes_item_from_holder(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify DROP removes item from actor's inventory."""
        location = create_location(db_session, game_session, location_key="tavern")
        entity = create_entity(
            db_session, game_session,
            entity_key="player",
            current_location="tavern"
        )
        item = create_item(
            db_session, game_session,
            item_key="sword",
            holder_id=entity.id
        )

        executor = ActionExecutor(db_session, game_session)
        action = Action(type=ActionType.DROP, target="sword")
        validation = ValidationResult(
            action=action,
            valid=True,
            resolved_target="sword",
            metadata={"item_id": item.id}
        )

        result = await executor._execute_drop(validation, entity)

        assert result.success is True

        # Verify item is no longer held
        db_session.refresh(item)
        assert item.holder_id is None


class TestEquipExecution:
    """Tests for EQUIP action execution."""

    @pytest.mark.asyncio
    async def test_equip_sets_body_slot(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify EQUIP sets the item's body_slot."""
        entity = create_entity(db_session, game_session)
        item = create_item(
            db_session, game_session,
            item_key="sword",
            item_type=ItemType.WEAPON,
            holder_id=entity.id,
            body_slot=None
        )

        executor = ActionExecutor(db_session, game_session)
        action = Action(type=ActionType.EQUIP, target="sword")
        validation = ValidationResult(
            action=action,
            valid=True,
            resolved_target="sword",
            metadata={"item_id": item.id, "body_slot": "right_hand"}
        )

        result = await executor._execute_equip(validation, entity)

        assert result.success is True

        # Verify item has body_slot set
        db_session.refresh(item)
        assert item.body_slot is not None


class TestUnequipExecution:
    """Tests for UNEQUIP action execution."""

    @pytest.mark.asyncio
    async def test_unequip_clears_body_slot(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify UNEQUIP clears the item's body_slot."""
        entity = create_entity(db_session, game_session)
        item = create_item(
            db_session, game_session,
            item_key="helmet",
            item_type=ItemType.ARMOR,
            holder_id=entity.id,
            body_slot="head"
        )

        executor = ActionExecutor(db_session, game_session)
        action = Action(type=ActionType.UNEQUIP, target="helmet")
        validation = ValidationResult(
            action=action,
            valid=True,
            resolved_target="helmet",
            metadata={"item_id": item.id}
        )

        result = await executor._execute_unequip(validation, entity)

        assert result.success is True

        # Verify body_slot is cleared
        db_session.refresh(item)
        assert item.body_slot is None


class TestAttackExecution:
    """Tests for ATTACK action execution."""

    @pytest.mark.asyncio
    async def test_attack_returns_result_with_damage_info(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify ATTACK returns result with hit/damage information."""
        entity = create_entity(db_session, game_session, entity_key="player")
        enemy = create_entity(
            db_session, game_session,
            entity_key="goblin",
            entity_type=EntityType.MONSTER
        )

        # Add attributes for combat calculations
        create_entity_attribute(db_session, entity, attribute_key="strength", value=14)
        create_entity_attribute(db_session, enemy, attribute_key="dexterity", value=10)
        create_entity_attribute(db_session, enemy, attribute_key="current_hp", value=10)
        create_entity_attribute(db_session, enemy, attribute_key="max_hp", value=10)

        executor = ActionExecutor(db_session, game_session)
        action = Action(type=ActionType.ATTACK, target="goblin")
        validation = ValidationResult(
            action=action,
            valid=True,
            resolved_target="goblin",
            metadata={"target_id": enemy.id}
        )

        result = await executor._execute_attack(validation, entity)

        # Execution should always succeed (hit or miss)
        assert result.success is True
        assert "hit" in result.metadata or "damage" in result.metadata


class TestRestExecution:
    """Tests for REST action execution."""

    @pytest.mark.asyncio
    async def test_rest_advances_time(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify REST advances game time."""
        entity = create_entity(db_session, game_session)
        time_state = create_time_state(
            db_session, game_session,
            current_time="12:00"
        )

        executor = ActionExecutor(db_session, game_session)
        action = Action(type=ActionType.REST, target=None)
        validation = ValidationResult(action=action, valid=True)

        result = await executor._execute_rest(validation, entity)

        assert result.success is True
        assert "new_time" in result.metadata
        assert result.metadata["new_time"] != "12:00"  # Time should have changed


class TestWaitExecution:
    """Tests for WAIT action execution."""

    @pytest.mark.asyncio
    async def test_wait_advances_time_by_minutes(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify WAIT advances time by specified minutes."""
        entity = create_entity(db_session, game_session)
        time_state = create_time_state(
            db_session, game_session,
            current_time="10:00"
        )

        executor = ActionExecutor(db_session, game_session)
        action = Action(type=ActionType.WAIT, target="30")
        validation = ValidationResult(action=action, valid=True)

        result = await executor._execute_wait(validation, entity)

        assert result.success is True
        assert result.metadata["minutes"] == 30
        assert result.metadata["new_time"] == "10:30"


class TestSleepExecution:
    """Tests for SLEEP action execution."""

    @pytest.mark.asyncio
    async def test_sleep_restores_energy(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify SLEEP restores energy via NeedsManager."""
        entity = create_entity(db_session, game_session)
        time_state = create_time_state(
            db_session, game_session,
            current_time="22:00"
        )
        needs = create_character_needs(
            db_session, game_session, entity,
            stamina=30  # Low energy
        )

        executor = ActionExecutor(db_session, game_session)
        action = Action(type=ActionType.SLEEP, target=None)
        validation = ValidationResult(action=action, valid=True)

        result = await executor._execute_sleep(validation, entity)

        assert result.success is True
        assert "refreshed" in result.outcome.lower()

        # Verify energy was restored
        db_session.refresh(needs)
        assert needs.energy > 30  # Energy should have increased


class TestConsumeExecution:
    """Tests for EAT and DRINK action execution."""

    @pytest.mark.asyncio
    async def test_eat_satisfies_hunger(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify EAT satisfies hunger need and consumes item."""
        entity = create_entity(db_session, game_session)
        item = create_item(
            db_session, game_session,
            item_key="bread",
            item_type=ItemType.CONSUMABLE,
            holder_id=entity.id
        )
        needs = create_character_needs(
            db_session, game_session, entity,
            hunger=50  # Moderate hunger
        )

        executor = ActionExecutor(db_session, game_session)
        action = Action(type=ActionType.EAT, target="bread")
        validation = ValidationResult(
            action=action,
            valid=True,
            resolved_target="bread",
            metadata={"item_id": item.id}
        )

        result = await executor._execute_consume(validation, entity)

        assert result.success is True
        assert result.metadata["consumed"] is True
        assert result.metadata["need_satisfied"] == "hunger"

        # Verify hunger increased
        db_session.refresh(needs)
        assert needs.hunger > 50

        # Verify item was deleted
        deleted_item = db_session.query(Item).filter_by(id=item.id).first()
        assert deleted_item is None

    @pytest.mark.asyncio
    async def test_drink_satisfies_thirst(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify DRINK satisfies thirst need and consumes item."""
        entity = create_entity(db_session, game_session)
        item = create_item(
            db_session, game_session,
            item_key="water",
            item_type=ItemType.CONSUMABLE,
            holder_id=entity.id
        )
        needs = create_character_needs(
            db_session, game_session, entity,
            thirst=50
        )

        executor = ActionExecutor(db_session, game_session)
        action = Action(type=ActionType.DRINK, target="water")
        validation = ValidationResult(
            action=action,
            valid=True,
            resolved_target="water",
            metadata={"item_id": item.id}
        )

        result = await executor._execute_consume(validation, entity)

        assert result.success is True
        assert result.metadata["need_satisfied"] == "thirst"

        # Verify thirst increased
        db_session.refresh(needs)
        assert needs.thirst > 50


class TestSocialSkillExecution:
    """Tests for PERSUADE and INTIMIDATE action execution."""

    @pytest.mark.asyncio
    async def test_persuade_rolls_skill_check(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify PERSUADE performs skill check."""
        entity = create_entity(db_session, game_session, entity_key="player")
        npc = create_entity(
            db_session, game_session,
            entity_key="merchant",
            entity_type=EntityType.NPC
        )
        create_entity_attribute(db_session, entity, attribute_key="charisma", value=14)
        create_entity_attribute(db_session, npc, attribute_key="wisdom", value=10)

        executor = ActionExecutor(db_session, game_session)
        action = Action(type=ActionType.PERSUADE, target="merchant")
        validation = ValidationResult(
            action=action,
            valid=True,
            resolved_target="merchant",
            metadata={"target_id": npc.id}
        )

        result = await executor._execute_social_skill(validation, entity)

        assert result.metadata["skill"] == "persuasion"
        assert "dc" in result.metadata
        assert "success" in result.metadata

    @pytest.mark.asyncio
    async def test_intimidate_rolls_skill_check(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify INTIMIDATE performs skill check."""
        entity = create_entity(db_session, game_session, entity_key="player")
        npc = create_entity(
            db_session, game_session,
            entity_key="guard",
            entity_type=EntityType.NPC
        )
        create_entity_attribute(db_session, entity, attribute_key="charisma", value=12)
        create_entity_attribute(db_session, npc, attribute_key="wisdom", value=12)

        executor = ActionExecutor(db_session, game_session)
        action = Action(type=ActionType.INTIMIDATE, target="guard")
        validation = ValidationResult(
            action=action,
            valid=True,
            resolved_target="guard",
            metadata={"target_id": npc.id}
        )

        result = await executor._execute_social_skill(validation, entity)

        assert result.metadata["skill"] == "intimidation"
        assert "dc" in result.metadata
