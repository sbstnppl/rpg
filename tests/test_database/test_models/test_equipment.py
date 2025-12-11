"""Tests for weapon and armor equipment models."""

import pytest
from sqlalchemy.orm import Session

from src.database.models import GameSession
from src.database.models.equipment import (
    ArmorCategory,
    ArmorDefinition,
    DamageType,
    WeaponCategory,
    WeaponDefinition,
    WeaponProperty,
    WeaponRange,
)
from tests.factories import create_game_session


class TestDamageType:
    """Tests for DamageType enum."""

    def test_physical_damage_types(self):
        assert DamageType.SLASHING.value == "slashing"
        assert DamageType.PIERCING.value == "piercing"
        assert DamageType.BLUDGEONING.value == "bludgeoning"

    def test_elemental_damage_types(self):
        assert DamageType.FIRE.value == "fire"
        assert DamageType.COLD.value == "cold"
        assert DamageType.LIGHTNING.value == "lightning"
        assert DamageType.ACID.value == "acid"
        assert DamageType.POISON.value == "poison"

    def test_special_damage_types(self):
        assert DamageType.PSYCHIC.value == "psychic"
        assert DamageType.RADIANT.value == "radiant"
        assert DamageType.NECROTIC.value == "necrotic"
        assert DamageType.FORCE.value == "force"


class TestWeaponProperty:
    """Tests for WeaponProperty enum."""

    def test_melee_properties(self):
        assert WeaponProperty.FINESSE.value == "finesse"
        assert WeaponProperty.HEAVY.value == "heavy"
        assert WeaponProperty.LIGHT.value == "light"
        assert WeaponProperty.REACH.value == "reach"
        assert WeaponProperty.TWO_HANDED.value == "two_handed"
        assert WeaponProperty.VERSATILE.value == "versatile"

    def test_ranged_properties(self):
        assert WeaponProperty.AMMUNITION.value == "ammunition"
        assert WeaponProperty.LOADING.value == "loading"
        assert WeaponProperty.THROWN.value == "thrown"


class TestWeaponCategory:
    """Tests for WeaponCategory enum."""

    def test_categories(self):
        assert WeaponCategory.SIMPLE_MELEE.value == "simple_melee"
        assert WeaponCategory.SIMPLE_RANGED.value == "simple_ranged"
        assert WeaponCategory.MARTIAL_MELEE.value == "martial_melee"
        assert WeaponCategory.MARTIAL_RANGED.value == "martial_ranged"
        assert WeaponCategory.EXOTIC.value == "exotic"
        assert WeaponCategory.IMPROVISED.value == "improvised"


class TestArmorCategory:
    """Tests for ArmorCategory enum."""

    def test_categories(self):
        assert ArmorCategory.LIGHT.value == "light"
        assert ArmorCategory.MEDIUM.value == "medium"
        assert ArmorCategory.HEAVY.value == "heavy"
        assert ArmorCategory.SHIELD.value == "shield"


class TestWeaponDefinition:
    """Tests for WeaponDefinition model."""

    def test_create_simple_weapon(self, db_session: Session, game_session: GameSession):
        weapon = WeaponDefinition(
            session_id=game_session.id,
            weapon_key="shortsword",
            name="Shortsword",
            category=WeaponCategory.MARTIAL_MELEE,
            damage_dice="1d6",
            damage_type=DamageType.PIERCING,
            properties=[WeaponProperty.FINESSE.value, WeaponProperty.LIGHT.value],
            range_type=WeaponRange.MELEE,
            weight=2.0,
        )
        db_session.add(weapon)
        db_session.commit()

        assert weapon.id is not None
        assert weapon.weapon_key == "shortsword"
        assert weapon.damage_dice == "1d6"
        assert weapon.damage_type == DamageType.PIERCING
        assert "finesse" in weapon.properties
        assert weapon.range_type == WeaponRange.MELEE

    def test_create_ranged_weapon(self, db_session: Session, game_session: GameSession):
        weapon = WeaponDefinition(
            session_id=game_session.id,
            weapon_key="longbow",
            name="Longbow",
            category=WeaponCategory.MARTIAL_RANGED,
            damage_dice="1d8",
            damage_type=DamageType.PIERCING,
            properties=["ammunition", "heavy", "two_handed"],
            range_type=WeaponRange.RANGED,
            range_normal=150,
            range_long=600,
            weight=2.0,
        )
        db_session.add(weapon)
        db_session.commit()

        assert weapon.range_type == WeaponRange.RANGED
        assert weapon.range_normal == 150
        assert weapon.range_long == 600

    def test_create_thrown_weapon(self, db_session: Session, game_session: GameSession):
        weapon = WeaponDefinition(
            session_id=game_session.id,
            weapon_key="javelin",
            name="Javelin",
            category=WeaponCategory.SIMPLE_MELEE,
            damage_dice="1d6",
            damage_type=DamageType.PIERCING,
            properties=["thrown"],
            range_type=WeaponRange.THROWN,
            range_normal=30,
            range_long=120,
            weight=2.0,
        )
        db_session.add(weapon)
        db_session.commit()

        assert weapon.range_type == WeaponRange.THROWN
        assert "thrown" in weapon.properties

    def test_weapon_with_versatile_damage(self, db_session: Session, game_session: GameSession):
        weapon = WeaponDefinition(
            session_id=game_session.id,
            weapon_key="longsword",
            name="Longsword",
            category=WeaponCategory.MARTIAL_MELEE,
            damage_dice="1d8",
            damage_type=DamageType.SLASHING,
            properties=["versatile"],
            versatile_dice="1d10",
            range_type=WeaponRange.MELEE,
            weight=3.0,
        )
        db_session.add(weapon)
        db_session.commit()

        assert weapon.damage_dice == "1d8"
        assert weapon.versatile_dice == "1d10"

    def test_weapon_unique_key_per_session(
        self, db_session: Session, game_session: GameSession
    ):
        weapon1 = WeaponDefinition(
            session_id=game_session.id,
            weapon_key="dagger",
            name="Dagger",
            category=WeaponCategory.SIMPLE_MELEE,
            damage_dice="1d4",
            damage_type=DamageType.PIERCING,
            range_type=WeaponRange.MELEE,
        )
        db_session.add(weapon1)
        db_session.commit()

        weapon2 = WeaponDefinition(
            session_id=game_session.id,
            weapon_key="dagger",
            name="Dagger Duplicate",
            category=WeaponCategory.SIMPLE_MELEE,
            damage_dice="1d4",
            damage_type=DamageType.PIERCING,
            range_type=WeaponRange.MELEE,
        )
        db_session.add(weapon2)
        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()

    def test_weapon_repr(self, db_session: Session, game_session: GameSession):
        weapon = WeaponDefinition(
            session_id=game_session.id,
            weapon_key="greatsword",
            name="Greatsword",
            category=WeaponCategory.MARTIAL_MELEE,
            damage_dice="2d6",
            damage_type=DamageType.SLASHING,
            range_type=WeaponRange.MELEE,
        )
        db_session.add(weapon)
        db_session.commit()

        assert "greatsword" in repr(weapon)
        assert "Greatsword" in repr(weapon)


class TestArmorDefinition:
    """Tests for ArmorDefinition model."""

    def test_create_light_armor(self, db_session: Session, game_session: GameSession):
        armor = ArmorDefinition(
            session_id=game_session.id,
            armor_key="leather",
            name="Leather Armor",
            category=ArmorCategory.LIGHT,
            base_ac=11,
            max_dex_bonus=None,  # Unlimited
            weight=10.0,
        )
        db_session.add(armor)
        db_session.commit()

        assert armor.id is not None
        assert armor.armor_key == "leather"
        assert armor.base_ac == 11
        assert armor.max_dex_bonus is None
        assert armor.stealth_disadvantage is False

    def test_create_medium_armor(self, db_session: Session, game_session: GameSession):
        armor = ArmorDefinition(
            session_id=game_session.id,
            armor_key="chain_shirt",
            name="Chain Shirt",
            category=ArmorCategory.MEDIUM,
            base_ac=13,
            max_dex_bonus=2,
            weight=20.0,
        )
        db_session.add(armor)
        db_session.commit()

        assert armor.category == ArmorCategory.MEDIUM
        assert armor.max_dex_bonus == 2

    def test_create_heavy_armor(self, db_session: Session, game_session: GameSession):
        armor = ArmorDefinition(
            session_id=game_session.id,
            armor_key="plate",
            name="Plate Armor",
            category=ArmorCategory.HEAVY,
            base_ac=18,
            max_dex_bonus=0,  # No DEX bonus
            strength_required=15,
            stealth_disadvantage=True,
            weight=65.0,
        )
        db_session.add(armor)
        db_session.commit()

        assert armor.category == ArmorCategory.HEAVY
        assert armor.max_dex_bonus == 0
        assert armor.strength_required == 15
        assert armor.stealth_disadvantage is True

    def test_create_shield(self, db_session: Session, game_session: GameSession):
        shield = ArmorDefinition(
            session_id=game_session.id,
            armor_key="shield",
            name="Shield",
            category=ArmorCategory.SHIELD,
            base_ac=2,  # AC bonus
            weight=6.0,
        )
        db_session.add(shield)
        db_session.commit()

        assert shield.category == ArmorCategory.SHIELD
        assert shield.base_ac == 2

    def test_armor_unique_key_per_session(
        self, db_session: Session, game_session: GameSession
    ):
        armor1 = ArmorDefinition(
            session_id=game_session.id,
            armor_key="chainmail",
            name="Chainmail",
            category=ArmorCategory.HEAVY,
            base_ac=16,
        )
        db_session.add(armor1)
        db_session.commit()

        armor2 = ArmorDefinition(
            session_id=game_session.id,
            armor_key="chainmail",
            name="Chainmail Duplicate",
            category=ArmorCategory.HEAVY,
            base_ac=16,
        )
        db_session.add(armor2)
        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()

    def test_armor_repr(self, db_session: Session, game_session: GameSession):
        armor = ArmorDefinition(
            session_id=game_session.id,
            armor_key="studded_leather",
            name="Studded Leather",
            category=ArmorCategory.LIGHT,
            base_ac=12,
        )
        db_session.add(armor)
        db_session.commit()

        assert "studded_leather" in repr(armor)
        assert "Studded Leather" in repr(armor)
