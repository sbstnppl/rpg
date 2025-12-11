"""Tests for Combat Conditions system."""

import pytest
from sqlalchemy.orm import Session

from src.database.models import Entity, EntityType, GameSession
from src.database.models.combat_conditions import CombatCondition, EntityCondition
from src.managers.combat_condition_manager import (
    CombatConditionManager,
    ConditionEffect,
    ConditionInfo,
)
from tests.factories import create_entity


@pytest.fixture
def condition_manager(
    db_session: Session, game_session: GameSession
) -> CombatConditionManager:
    return CombatConditionManager(db_session, game_session)


@pytest.fixture
def fighter(db_session: Session, game_session: GameSession) -> Entity:
    return create_entity(
        db_session,
        game_session,
        entity_key="fighter",
        display_name="Fighter",
        entity_type=EntityType.PLAYER,
    )


@pytest.fixture
def goblin(db_session: Session, game_session: GameSession) -> Entity:
    return create_entity(
        db_session,
        game_session,
        entity_key="goblin",
        display_name="Goblin",
        entity_type=EntityType.MONSTER,
    )


class TestCombatConditionEnum:
    """Tests for CombatCondition enum."""

    def test_movement_conditions(self):
        assert CombatCondition.PRONE.value == "prone"
        assert CombatCondition.GRAPPLED.value == "grappled"
        assert CombatCondition.RESTRAINED.value == "restrained"
        assert CombatCondition.PARALYZED.value == "paralyzed"

    def test_sensory_conditions(self):
        assert CombatCondition.BLINDED.value == "blinded"
        assert CombatCondition.DEAFENED.value == "deafened"
        assert CombatCondition.INVISIBLE.value == "invisible"

    def test_impairment_conditions(self):
        assert CombatCondition.STUNNED.value == "stunned"
        assert CombatCondition.INCAPACITATED.value == "incapacitated"
        assert CombatCondition.UNCONSCIOUS.value == "unconscious"

    def test_debuff_conditions(self):
        assert CombatCondition.POISONED.value == "poisoned"
        assert CombatCondition.FRIGHTENED.value == "frightened"
        assert CombatCondition.CHARMED.value == "charmed"
        assert CombatCondition.EXHAUSTED.value == "exhausted"


class TestApplyCondition:
    """Tests for applying conditions."""

    def test_apply_condition_basic(
        self, condition_manager: CombatConditionManager, fighter: Entity
    ):
        result = condition_manager.apply_condition(
            entity_key="fighter",
            condition=CombatCondition.PRONE,
        )
        assert result is not None
        assert result.condition == CombatCondition.PRONE
        assert result.duration_rounds is None  # No duration = permanent until removed

    def test_apply_condition_with_duration(
        self, condition_manager: CombatConditionManager, fighter: Entity
    ):
        result = condition_manager.apply_condition(
            entity_key="fighter",
            condition=CombatCondition.STUNNED,
            duration_rounds=2,
        )
        assert result.duration_rounds == 2
        assert result.rounds_remaining == 2

    def test_apply_condition_with_source(
        self, condition_manager: CombatConditionManager, fighter: Entity, goblin: Entity
    ):
        result = condition_manager.apply_condition(
            entity_key="fighter",
            condition=CombatCondition.GRAPPLED,
            source_entity_key="goblin",
        )
        assert result.source_entity_key == "goblin"

    def test_apply_duplicate_condition_extends(
        self, condition_manager: CombatConditionManager, fighter: Entity
    ):
        # Apply poisoned for 3 rounds
        condition_manager.apply_condition(
            entity_key="fighter",
            condition=CombatCondition.POISONED,
            duration_rounds=3,
        )
        # Apply again for 5 rounds - should extend/replace
        result = condition_manager.apply_condition(
            entity_key="fighter",
            condition=CombatCondition.POISONED,
            duration_rounds=5,
        )
        # Should have 5 rounds, not stack
        assert result.rounds_remaining == 5

    def test_apply_exhaustion_stacks(
        self, condition_manager: CombatConditionManager, fighter: Entity
    ):
        # Exhaustion is special - it stacks up to level 6
        condition_manager.apply_condition(
            entity_key="fighter",
            condition=CombatCondition.EXHAUSTED,
            exhaustion_level=1,
        )
        result = condition_manager.apply_condition(
            entity_key="fighter",
            condition=CombatCondition.EXHAUSTED,
            exhaustion_level=1,  # Add another level
        )
        assert result.exhaustion_level == 2


class TestRemoveCondition:
    """Tests for removing conditions."""

    def test_remove_condition(
        self, condition_manager: CombatConditionManager, fighter: Entity
    ):
        condition_manager.apply_condition(
            entity_key="fighter",
            condition=CombatCondition.BLINDED,
        )
        removed = condition_manager.remove_condition("fighter", CombatCondition.BLINDED)
        assert removed is True

        # Should no longer have condition
        conditions = condition_manager.get_active_conditions("fighter")
        assert CombatCondition.BLINDED not in [c.condition for c in conditions]

    def test_remove_nonexistent_condition(
        self, condition_manager: CombatConditionManager, fighter: Entity
    ):
        removed = condition_manager.remove_condition("fighter", CombatCondition.STUNNED)
        assert removed is False

    def test_remove_all_conditions(
        self, condition_manager: CombatConditionManager, fighter: Entity
    ):
        condition_manager.apply_condition("fighter", CombatCondition.PRONE)
        condition_manager.apply_condition("fighter", CombatCondition.POISONED)
        condition_manager.apply_condition("fighter", CombatCondition.BLINDED)

        count = condition_manager.remove_all_conditions("fighter")
        assert count == 3

        conditions = condition_manager.get_active_conditions("fighter")
        assert len(conditions) == 0


class TestConditionDuration:
    """Tests for condition duration management."""

    def test_tick_conditions(
        self, condition_manager: CombatConditionManager, fighter: Entity
    ):
        condition_manager.apply_condition(
            entity_key="fighter",
            condition=CombatCondition.STUNNED,
            duration_rounds=3,
        )

        # Tick one round
        expired = condition_manager.tick_conditions("fighter")
        assert len(expired) == 0  # Still 2 rounds left

        # Check remaining
        info = condition_manager.get_condition_info("fighter", CombatCondition.STUNNED)
        assert info.rounds_remaining == 2

    def test_tick_conditions_expires(
        self, condition_manager: CombatConditionManager, fighter: Entity
    ):
        condition_manager.apply_condition(
            entity_key="fighter",
            condition=CombatCondition.STUNNED,
            duration_rounds=1,
        )

        expired = condition_manager.tick_conditions("fighter")
        assert CombatCondition.STUNNED in expired

    def test_tick_permanent_condition(
        self, condition_manager: CombatConditionManager, fighter: Entity
    ):
        # Permanent conditions (no duration) don't expire from ticking
        condition_manager.apply_condition(
            entity_key="fighter",
            condition=CombatCondition.PRONE,
        )

        expired = condition_manager.tick_conditions("fighter")
        assert len(expired) == 0

        # Still has condition
        assert condition_manager.has_condition("fighter", CombatCondition.PRONE)


class TestQueryConditions:
    """Tests for querying conditions."""

    def test_get_active_conditions(
        self, condition_manager: CombatConditionManager, fighter: Entity
    ):
        condition_manager.apply_condition("fighter", CombatCondition.PRONE)
        condition_manager.apply_condition("fighter", CombatCondition.POISONED)

        conditions = condition_manager.get_active_conditions("fighter")
        assert len(conditions) == 2

    def test_has_condition(
        self, condition_manager: CombatConditionManager, fighter: Entity
    ):
        condition_manager.apply_condition("fighter", CombatCondition.BLINDED)

        assert condition_manager.has_condition("fighter", CombatCondition.BLINDED)
        assert not condition_manager.has_condition("fighter", CombatCondition.DEAFENED)

    def test_get_condition_info(
        self, condition_manager: CombatConditionManager, fighter: Entity, goblin: Entity
    ):
        condition_manager.apply_condition(
            entity_key="fighter",
            condition=CombatCondition.RESTRAINED,
            duration_rounds=5,
            source_entity_key="goblin",
        )

        info = condition_manager.get_condition_info("fighter", CombatCondition.RESTRAINED)
        assert info is not None
        assert info.condition == CombatCondition.RESTRAINED
        assert info.rounds_remaining == 5
        assert info.source_entity_key == "goblin"


class TestConditionEffects:
    """Tests for condition effects on combat."""

    def test_get_attack_modifiers_blinded(
        self, condition_manager: CombatConditionManager, fighter: Entity
    ):
        condition_manager.apply_condition("fighter", CombatCondition.BLINDED)

        effects = condition_manager.get_condition_effects("fighter")
        assert effects.attack_disadvantage is True
        assert effects.attack_advantage is False  # Not both

    def test_get_attack_modifiers_invisible_attacker(
        self, condition_manager: CombatConditionManager, fighter: Entity
    ):
        condition_manager.apply_condition("fighter", CombatCondition.INVISIBLE)

        effects = condition_manager.get_condition_effects("fighter")
        assert effects.attack_advantage is True

    def test_get_defense_modifiers_prone(
        self, condition_manager: CombatConditionManager, fighter: Entity
    ):
        condition_manager.apply_condition("fighter", CombatCondition.PRONE)

        effects = condition_manager.get_condition_effects("fighter")
        # Prone: melee attacks against have advantage, ranged have disadvantage
        assert effects.melee_attacks_against_advantage is True
        assert effects.ranged_attacks_against_disadvantage is True

    def test_get_defense_modifiers_stunned(
        self, condition_manager: CombatConditionManager, fighter: Entity
    ):
        condition_manager.apply_condition("fighter", CombatCondition.STUNNED)

        effects = condition_manager.get_condition_effects("fighter")
        assert effects.auto_fail_str_saves is True
        assert effects.auto_fail_dex_saves is True
        assert effects.attacks_against_advantage is True

    def test_movement_speed_modifiers(
        self, condition_manager: CombatConditionManager, fighter: Entity
    ):
        condition_manager.apply_condition("fighter", CombatCondition.GRAPPLED)

        effects = condition_manager.get_condition_effects("fighter")
        assert effects.speed_zero is True

    def test_exhaustion_effects(
        self, condition_manager: CombatConditionManager, fighter: Entity
    ):
        condition_manager.apply_condition(
            "fighter", CombatCondition.EXHAUSTED, exhaustion_level=2
        )

        effects = condition_manager.get_condition_effects("fighter")
        # Level 1: Disadvantage on ability checks
        assert effects.ability_check_disadvantage is True
        # Level 2: Speed halved
        assert effects.speed_halved is True

    def test_multiple_conditions_combine(
        self, condition_manager: CombatConditionManager, fighter: Entity
    ):
        condition_manager.apply_condition("fighter", CombatCondition.BLINDED)
        condition_manager.apply_condition("fighter", CombatCondition.PRONE)

        effects = condition_manager.get_condition_effects("fighter")
        # From blinded
        assert effects.attack_disadvantage is True
        # From prone
        assert effects.melee_attacks_against_advantage is True


class TestConditionContext:
    """Tests for condition context generation."""

    def test_get_condition_context(
        self, condition_manager: CombatConditionManager, fighter: Entity
    ):
        condition_manager.apply_condition("fighter", CombatCondition.POISONED)
        condition_manager.apply_condition(
            "fighter", CombatCondition.STUNNED, duration_rounds=2
        )

        context = condition_manager.get_condition_context("fighter")
        assert "Poisoned" in context
        assert "Stunned" in context
        assert "2 rounds" in context

    def test_get_condition_context_empty(
        self, condition_manager: CombatConditionManager, fighter: Entity
    ):
        context = condition_manager.get_condition_context("fighter")
        assert context == ""  # No conditions = empty context
