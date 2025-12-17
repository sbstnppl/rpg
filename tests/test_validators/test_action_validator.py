"""Tests for ActionValidator class."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.enums import EntityType, ItemType
from src.database.models.session import GameSession
from src.parser.action_types import Action, ActionType
from src.validators.action_validator import ActionValidator, ValidationResult
from tests.factories import create_entity, create_item, create_location


class TestActionValidatorBasics:
    """Tests for ActionValidator basic operations."""

    def test_validator_creation(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify ActionValidator can be instantiated."""
        validator = ActionValidator(db_session, game_session)

        assert validator is not None
        assert validator.db == db_session
        assert validator.game_session == game_session

    def test_validator_with_combat_active(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify ActionValidator accepts combat_active parameter."""
        validator = ActionValidator(db_session, game_session, combat_active=True)

        assert validator._combat_active is True

    def test_is_in_combat_returns_combat_active_state(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify _is_in_combat returns the combat_active state."""
        entity = create_entity(db_session, game_session)

        validator_no_combat = ActionValidator(db_session, game_session, combat_active=False)
        validator_combat = ActionValidator(db_session, game_session, combat_active=True)

        assert validator_no_combat._is_in_combat(entity) is False
        assert validator_combat._is_in_combat(entity) is True


class TestTakeValidation:
    """Tests for TAKE action validation."""

    def test_take_item_in_location_succeeds(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify TAKE succeeds when item is in same location as actor."""
        location = create_location(db_session, game_session, location_key="tavern")
        entity = create_entity(
            db_session, game_session,
            entity_key="player",
            current_location="tavern"
        )
        item = create_item(
            db_session, game_session,
            item_key="gold_coin",
            display_name="Gold Coin"
        )

        validator = ActionValidator(db_session, game_session)
        action = Action(type=ActionType.TAKE, target="gold_coin")

        result = validator.validate(action, entity)

        assert result.valid is True
        assert result.resolved_target == "gold_coin"

    def test_take_nonexistent_item_fails(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify TAKE fails when item doesn't exist."""
        entity = create_entity(db_session, game_session)

        validator = ActionValidator(db_session, game_session)
        action = Action(type=ActionType.TAKE, target="nonexistent")

        result = validator.validate(action, entity)

        assert result.valid is False
        assert "not found" in result.reason.lower() or "no" in result.reason.lower()


class TestDropValidation:
    """Tests for DROP action validation."""

    def test_drop_held_item_succeeds(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify DROP succeeds when actor is holding the item."""
        entity = create_entity(db_session, game_session)
        item = create_item(
            db_session, game_session,
            item_key="sword",
            holder_id=entity.id
        )

        validator = ActionValidator(db_session, game_session)
        action = Action(type=ActionType.DROP, target="sword")

        result = validator.validate(action, entity)

        assert result.valid is True

    def test_drop_item_not_held_fails(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify DROP fails when actor isn't holding the item."""
        entity = create_entity(db_session, game_session)
        other_entity = create_entity(db_session, game_session)
        item = create_item(
            db_session, game_session,
            item_key="sword",
            holder_id=other_entity.id  # Held by someone else
        )

        validator = ActionValidator(db_session, game_session)
        action = Action(type=ActionType.DROP, target="sword")

        result = validator.validate(action, entity)

        assert result.valid is False


class TestEquipUnequipValidation:
    """Tests for EQUIP and UNEQUIP action validation."""

    def test_equip_held_item_succeeds(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify EQUIP succeeds when actor holds the item."""
        entity = create_entity(db_session, game_session)
        item = create_item(
            db_session, game_session,
            item_key="sword",
            item_type=ItemType.WEAPON,
            holder_id=entity.id
        )

        validator = ActionValidator(db_session, game_session)
        action = Action(type=ActionType.EQUIP, target="sword")

        result = validator.validate(action, entity)

        assert result.valid is True

    def test_unequip_equipped_item_succeeds(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify UNEQUIP succeeds when item is equipped (has body_slot)."""
        entity = create_entity(db_session, game_session)
        item = create_item(
            db_session, game_session,
            item_key="helmet",
            item_type=ItemType.ARMOR,
            holder_id=entity.id,
            body_slot="head"  # Item is equipped
        )

        validator = ActionValidator(db_session, game_session)
        action = Action(type=ActionType.UNEQUIP, target="helmet")

        result = validator.validate(action, entity)

        assert result.valid is True

    def test_unequip_not_equipped_item_fails(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify UNEQUIP fails when item is held but not equipped."""
        entity = create_entity(db_session, game_session)
        item = create_item(
            db_session, game_session,
            item_key="sword",
            holder_id=entity.id,
            body_slot=None  # Not equipped, just held
        )

        validator = ActionValidator(db_session, game_session)
        action = Action(type=ActionType.UNEQUIP, target="sword")

        result = validator.validate(action, entity)

        assert result.valid is False


class TestAskTellValidation:
    """Tests for ASK and TELL action validation."""

    def test_ask_requires_indirect_target(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify ASK fails without indirect_target (topic)."""
        entity = create_entity(db_session, game_session)
        npc = create_entity(
            db_session, game_session,
            entity_key="bartender",
            entity_type=EntityType.NPC
        )

        validator = ActionValidator(db_session, game_session)
        action = Action(type=ActionType.ASK, target="bartender", indirect_target=None)

        result = validator.validate(action, entity)

        assert result.valid is False
        assert "about what" in result.reason.lower()

    def test_ask_with_topic_succeeds(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify ASK succeeds with target and indirect_target (topic)."""
        entity = create_entity(db_session, game_session)
        npc = create_entity(
            db_session, game_session,
            entity_key="bartender",
            entity_type=EntityType.NPC
        )

        validator = ActionValidator(db_session, game_session)
        action = Action(
            type=ActionType.ASK,
            target="bartender",
            indirect_target="rumors"
        )

        result = validator.validate(action, entity)

        assert result.valid is True

    def test_tell_requires_indirect_target(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify TELL fails without indirect_target (message)."""
        entity = create_entity(db_session, game_session)
        npc = create_entity(
            db_session, game_session,
            entity_key="guard",
            entity_type=EntityType.NPC
        )

        validator = ActionValidator(db_session, game_session)
        action = Action(type=ActionType.TELL, target="guard", indirect_target=None)

        result = validator.validate(action, entity)

        assert result.valid is False
        assert "what" in result.reason.lower()

    def test_tell_with_message_succeeds(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify TELL succeeds with target and indirect_target (message)."""
        entity = create_entity(db_session, game_session)
        npc = create_entity(
            db_session, game_session,
            entity_key="guard",
            entity_type=EntityType.NPC
        )

        validator = ActionValidator(db_session, game_session)
        action = Action(
            type=ActionType.TELL,
            target="guard",
            indirect_target="about the dragon"
        )

        result = validator.validate(action, entity)

        assert result.valid is True


class TestCombatValidation:
    """Tests for combat action validation."""

    def test_attack_valid_target(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify ATTACK succeeds with valid target."""
        entity = create_entity(db_session, game_session)
        enemy = create_entity(
            db_session, game_session,
            entity_key="goblin",
            entity_type=EntityType.MONSTER
        )

        validator = ActionValidator(db_session, game_session)
        action = Action(type=ActionType.ATTACK, target="goblin")

        result = validator.validate(action, entity)

        assert result.valid is True

    def test_defend_always_valid(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify DEFEND is always valid."""
        entity = create_entity(db_session, game_session)

        validator = ActionValidator(db_session, game_session)
        action = Action(type=ActionType.DEFEND, target=None)

        result = validator.validate(action, entity)

        assert result.valid is True

    def test_flee_valid_in_combat(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify FLEE is valid during combat."""
        entity = create_entity(db_session, game_session)

        validator = ActionValidator(db_session, game_session, combat_active=True)
        action = Action(type=ActionType.FLEE, target=None)

        result = validator.validate(action, entity)

        assert result.valid is True


class TestConsumeValidation:
    """Tests for EAT and DRINK validation."""

    def test_eat_consumable_succeeds(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify EAT succeeds with consumable item."""
        entity = create_entity(db_session, game_session)
        item = create_item(
            db_session, game_session,
            item_key="bread",
            item_type=ItemType.CONSUMABLE,
            holder_id=entity.id
        )

        validator = ActionValidator(db_session, game_session)
        action = Action(type=ActionType.EAT, target="bread")

        result = validator.validate(action, entity)

        assert result.valid is True

    def test_drink_consumable_succeeds(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify DRINK succeeds with consumable item."""
        entity = create_entity(db_session, game_session)
        item = create_item(
            db_session, game_session,
            item_key="ale",
            item_type=ItemType.CONSUMABLE,
            holder_id=entity.id
        )

        validator = ActionValidator(db_session, game_session)
        action = Action(type=ActionType.DRINK, target="ale")

        result = validator.validate(action, entity)

        assert result.valid is True
