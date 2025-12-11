"""Tests for EquipmentManager."""

import pytest
from sqlalchemy.orm import Session

from src.database.models import GameSession
from src.database.models.equipment import (
    ArmorCategory,
    ArmorDefinition,
    DamageType,
    WeaponCategory,
    WeaponDefinition,
    WeaponRange,
)
from src.managers.equipment_manager import (
    ArmorStats,
    EquipmentManager,
    WeaponStats,
)
from tests.factories import create_game_session


@pytest.fixture
def equipment_manager(db_session: Session, game_session: GameSession) -> EquipmentManager:
    return EquipmentManager(db_session, game_session)


class TestCreateWeapon:
    """Tests for weapon creation."""

    def test_create_weapon(self, equipment_manager: EquipmentManager):
        weapon = equipment_manager.create_weapon(
            weapon_key="longsword",
            name="Longsword",
            category=WeaponCategory.MARTIAL_MELEE,
            damage_dice="1d8",
            damage_type=DamageType.SLASHING,
        )
        assert weapon.id is not None
        assert weapon.weapon_key == "longsword"
        assert weapon.name == "Longsword"
        assert weapon.damage_dice == "1d8"

    def test_create_weapon_with_properties(self, equipment_manager: EquipmentManager):
        weapon = equipment_manager.create_weapon(
            weapon_key="rapier",
            name="Rapier",
            category=WeaponCategory.MARTIAL_MELEE,
            damage_dice="1d8",
            damage_type=DamageType.PIERCING,
            properties=["finesse"],
        )
        assert "finesse" in weapon.properties

    def test_create_ranged_weapon(self, equipment_manager: EquipmentManager):
        weapon = equipment_manager.create_weapon(
            weapon_key="longbow",
            name="Longbow",
            category=WeaponCategory.MARTIAL_RANGED,
            damage_dice="1d8",
            damage_type=DamageType.PIERCING,
            range_type=WeaponRange.RANGED,
            range_normal=150,
            range_long=600,
        )
        assert weapon.range_type == WeaponRange.RANGED
        assert weapon.range_normal == 150
        assert weapon.range_long == 600

    def test_create_versatile_weapon(self, equipment_manager: EquipmentManager):
        weapon = equipment_manager.create_weapon(
            weapon_key="quarterstaff",
            name="Quarterstaff",
            category=WeaponCategory.SIMPLE_MELEE,
            damage_dice="1d6",
            damage_type=DamageType.BLUDGEONING,
            properties=["versatile"],
            versatile_dice="1d8",
        )
        assert weapon.versatile_dice == "1d8"

    def test_get_weapon(self, equipment_manager: EquipmentManager):
        equipment_manager.create_weapon(
            weapon_key="dagger",
            name="Dagger",
            category=WeaponCategory.SIMPLE_MELEE,
            damage_dice="1d4",
            damage_type=DamageType.PIERCING,
        )
        weapon = equipment_manager.get_weapon("dagger")
        assert weapon is not None
        assert weapon.name == "Dagger"

    def test_get_weapon_not_found(self, equipment_manager: EquipmentManager):
        weapon = equipment_manager.get_weapon("nonexistent")
        assert weapon is None


class TestCreateArmor:
    """Tests for armor creation."""

    def test_create_light_armor(self, equipment_manager: EquipmentManager):
        armor = equipment_manager.create_armor(
            armor_key="leather",
            name="Leather Armor",
            category=ArmorCategory.LIGHT,
            base_ac=11,
        )
        assert armor.id is not None
        assert armor.armor_key == "leather"
        assert armor.base_ac == 11

    def test_create_medium_armor(self, equipment_manager: EquipmentManager):
        armor = equipment_manager.create_armor(
            armor_key="chain_shirt",
            name="Chain Shirt",
            category=ArmorCategory.MEDIUM,
            base_ac=13,
            max_dex_bonus=2,
        )
        assert armor.max_dex_bonus == 2

    def test_create_heavy_armor(self, equipment_manager: EquipmentManager):
        armor = equipment_manager.create_armor(
            armor_key="plate",
            name="Plate Armor",
            category=ArmorCategory.HEAVY,
            base_ac=18,
            max_dex_bonus=0,
            strength_required=15,
            stealth_disadvantage=True,
        )
        assert armor.strength_required == 15
        assert armor.stealth_disadvantage is True

    def test_create_shield(self, equipment_manager: EquipmentManager):
        armor = equipment_manager.create_armor(
            armor_key="shield",
            name="Shield",
            category=ArmorCategory.SHIELD,
            base_ac=2,
        )
        assert armor.category == ArmorCategory.SHIELD

    def test_get_armor(self, equipment_manager: EquipmentManager):
        equipment_manager.create_armor(
            armor_key="studded_leather",
            name="Studded Leather",
            category=ArmorCategory.LIGHT,
            base_ac=12,
        )
        armor = equipment_manager.get_armor("studded_leather")
        assert armor is not None
        assert armor.name == "Studded Leather"

    def test_get_armor_not_found(self, equipment_manager: EquipmentManager):
        armor = equipment_manager.get_armor("nonexistent")
        assert armor is None


class TestWeaponStats:
    """Tests for calculating weapon stats."""

    def test_get_weapon_stats_simple(self, equipment_manager: EquipmentManager):
        equipment_manager.create_weapon(
            weapon_key="mace",
            name="Mace",
            category=WeaponCategory.SIMPLE_MELEE,
            damage_dice="1d6",
            damage_type=DamageType.BLUDGEONING,
        )
        stats = equipment_manager.get_weapon_stats("mace", strength_mod=3)
        assert stats.attack_bonus == 3
        assert stats.damage_dice == "1d6"
        assert stats.damage_bonus == 3
        assert stats.damage_type == "bludgeoning"

    def test_get_weapon_stats_finesse_dex(self, equipment_manager: EquipmentManager):
        equipment_manager.create_weapon(
            weapon_key="rapier",
            name="Rapier",
            category=WeaponCategory.MARTIAL_MELEE,
            damage_dice="1d8",
            damage_type=DamageType.PIERCING,
            properties=["finesse"],
        )
        # With finesse, should use higher of STR or DEX
        stats = equipment_manager.get_weapon_stats(
            "rapier", strength_mod=1, dexterity_mod=4
        )
        assert stats.attack_bonus == 4
        assert stats.damage_bonus == 4

    def test_get_weapon_stats_finesse_str(self, equipment_manager: EquipmentManager):
        equipment_manager.create_weapon(
            weapon_key="shortsword",
            name="Shortsword",
            category=WeaponCategory.MARTIAL_MELEE,
            damage_dice="1d6",
            damage_type=DamageType.PIERCING,
            properties=["finesse", "light"],
        )
        # With finesse but higher STR, should use STR
        stats = equipment_manager.get_weapon_stats(
            "shortsword", strength_mod=5, dexterity_mod=2
        )
        assert stats.attack_bonus == 5

    def test_get_weapon_stats_ranged(self, equipment_manager: EquipmentManager):
        equipment_manager.create_weapon(
            weapon_key="shortbow",
            name="Shortbow",
            category=WeaponCategory.SIMPLE_RANGED,
            damage_dice="1d6",
            damage_type=DamageType.PIERCING,
            range_type=WeaponRange.RANGED,
            range_normal=80,
            range_long=320,
        )
        # Ranged weapons use DEX
        stats = equipment_manager.get_weapon_stats(
            "shortbow", strength_mod=2, dexterity_mod=3
        )
        assert stats.attack_bonus == 3
        assert stats.range_normal == 80
        assert stats.range_long == 320

    def test_get_weapon_stats_with_proficiency(self, equipment_manager: EquipmentManager):
        equipment_manager.create_weapon(
            weapon_key="greatsword",
            name="Greatsword",
            category=WeaponCategory.MARTIAL_MELEE,
            damage_dice="2d6",
            damage_type=DamageType.SLASHING,
            properties=["heavy", "two_handed"],
        )
        stats = equipment_manager.get_weapon_stats(
            "greatsword", strength_mod=4, proficiency_bonus=3
        )
        assert stats.attack_bonus == 7  # STR + proficiency

    def test_get_weapon_stats_versatile(self, equipment_manager: EquipmentManager):
        equipment_manager.create_weapon(
            weapon_key="battleaxe",
            name="Battleaxe",
            category=WeaponCategory.MARTIAL_MELEE,
            damage_dice="1d8",
            damage_type=DamageType.SLASHING,
            properties=["versatile"],
            versatile_dice="1d10",
        )
        # Two-handed
        stats = equipment_manager.get_weapon_stats(
            "battleaxe", strength_mod=3, two_handed=True
        )
        assert stats.damage_dice == "1d10"

        # One-handed
        stats = equipment_manager.get_weapon_stats(
            "battleaxe", strength_mod=3, two_handed=False
        )
        assert stats.damage_dice == "1d8"

    def test_get_weapon_stats_not_found(self, equipment_manager: EquipmentManager):
        stats = equipment_manager.get_weapon_stats("nonexistent")
        assert stats is None


class TestArmorStats:
    """Tests for calculating armor stats."""

    def test_get_armor_stats_light(self, equipment_manager: EquipmentManager):
        equipment_manager.create_armor(
            armor_key="leather",
            name="Leather Armor",
            category=ArmorCategory.LIGHT,
            base_ac=11,
        )
        stats = equipment_manager.get_armor_stats("leather", dexterity_mod=3)
        assert stats.total_ac == 14  # 11 + 3 DEX
        assert stats.stealth_disadvantage is False

    def test_get_armor_stats_medium(self, equipment_manager: EquipmentManager):
        equipment_manager.create_armor(
            armor_key="scale_mail",
            name="Scale Mail",
            category=ArmorCategory.MEDIUM,
            base_ac=14,
            max_dex_bonus=2,
            stealth_disadvantage=True,
        )
        # DEX capped at +2
        stats = equipment_manager.get_armor_stats("scale_mail", dexterity_mod=4)
        assert stats.total_ac == 16  # 14 + 2 (capped)
        assert stats.stealth_disadvantage is True

    def test_get_armor_stats_heavy(self, equipment_manager: EquipmentManager):
        equipment_manager.create_armor(
            armor_key="splint",
            name="Splint Armor",
            category=ArmorCategory.HEAVY,
            base_ac=17,
            max_dex_bonus=0,
            strength_required=15,
            stealth_disadvantage=True,
        )
        # No DEX bonus
        stats = equipment_manager.get_armor_stats("splint", dexterity_mod=5)
        assert stats.total_ac == 17  # No DEX added
        assert stats.strength_required == 15

    def test_get_armor_stats_shield(self, equipment_manager: EquipmentManager):
        equipment_manager.create_armor(
            armor_key="shield",
            name="Shield",
            category=ArmorCategory.SHIELD,
            base_ac=2,
        )
        stats = equipment_manager.get_armor_stats("shield")
        assert stats.total_ac == 2  # Just the bonus

    def test_get_armor_stats_not_found(self, equipment_manager: EquipmentManager):
        stats = equipment_manager.get_armor_stats("nonexistent")
        assert stats is None


class TestListEquipment:
    """Tests for listing equipment."""

    def test_get_all_weapons(self, equipment_manager: EquipmentManager):
        equipment_manager.create_weapon(
            weapon_key="sword",
            name="Sword",
            category=WeaponCategory.MARTIAL_MELEE,
            damage_dice="1d8",
            damage_type=DamageType.SLASHING,
        )
        equipment_manager.create_weapon(
            weapon_key="bow",
            name="Bow",
            category=WeaponCategory.MARTIAL_RANGED,
            damage_dice="1d8",
            damage_type=DamageType.PIERCING,
            range_type=WeaponRange.RANGED,
        )
        weapons = equipment_manager.get_all_weapons()
        assert len(weapons) == 2

    def test_get_weapons_by_category(self, equipment_manager: EquipmentManager):
        equipment_manager.create_weapon(
            weapon_key="club",
            name="Club",
            category=WeaponCategory.SIMPLE_MELEE,
            damage_dice="1d4",
            damage_type=DamageType.BLUDGEONING,
        )
        equipment_manager.create_weapon(
            weapon_key="greataxe",
            name="Greataxe",
            category=WeaponCategory.MARTIAL_MELEE,
            damage_dice="1d12",
            damage_type=DamageType.SLASHING,
        )
        simple_weapons = equipment_manager.get_weapons_by_category(WeaponCategory.SIMPLE_MELEE)
        assert len(simple_weapons) == 1
        assert simple_weapons[0].weapon_key == "club"

    def test_get_all_armors(self, equipment_manager: EquipmentManager):
        equipment_manager.create_armor(
            armor_key="hide",
            name="Hide Armor",
            category=ArmorCategory.MEDIUM,
            base_ac=12,
        )
        equipment_manager.create_armor(
            armor_key="chain",
            name="Chain Mail",
            category=ArmorCategory.HEAVY,
            base_ac=16,
        )
        armors = equipment_manager.get_all_armors()
        assert len(armors) == 2

    def test_get_armors_by_category(self, equipment_manager: EquipmentManager):
        equipment_manager.create_armor(
            armor_key="padded",
            name="Padded Armor",
            category=ArmorCategory.LIGHT,
            base_ac=11,
            stealth_disadvantage=True,
        )
        equipment_manager.create_armor(
            armor_key="half_plate",
            name="Half Plate",
            category=ArmorCategory.MEDIUM,
            base_ac=15,
        )
        light_armors = equipment_manager.get_armors_by_category(ArmorCategory.LIGHT)
        assert len(light_armors) == 1
        assert light_armors[0].armor_key == "padded"


class TestCalculateAC:
    """Tests for AC calculation with armor and shield."""

    def test_calculate_ac_with_armor_only(self, equipment_manager: EquipmentManager):
        equipment_manager.create_armor(
            armor_key="breastplate",
            name="Breastplate",
            category=ArmorCategory.MEDIUM,
            base_ac=14,
            max_dex_bonus=2,
        )
        ac = equipment_manager.calculate_total_ac(
            armor_key="breastplate",
            dexterity_mod=3,
        )
        assert ac == 16  # 14 + 2 (capped)

    def test_calculate_ac_with_shield(self, equipment_manager: EquipmentManager):
        equipment_manager.create_armor(
            armor_key="chainmail",
            name="Chain Mail",
            category=ArmorCategory.HEAVY,
            base_ac=16,
            max_dex_bonus=0,
        )
        equipment_manager.create_armor(
            armor_key="shield",
            name="Shield",
            category=ArmorCategory.SHIELD,
            base_ac=2,
        )
        ac = equipment_manager.calculate_total_ac(
            armor_key="chainmail",
            shield_key="shield",
            dexterity_mod=2,
        )
        assert ac == 18  # 16 + 0 DEX + 2 shield

    def test_calculate_ac_unarmored(self, equipment_manager: EquipmentManager):
        ac = equipment_manager.calculate_total_ac(dexterity_mod=3)
        assert ac == 13  # 10 + 3 DEX (unarmored)

    def test_calculate_ac_shield_only(self, equipment_manager: EquipmentManager):
        equipment_manager.create_armor(
            armor_key="shield",
            name="Shield",
            category=ArmorCategory.SHIELD,
            base_ac=2,
        )
        ac = equipment_manager.calculate_total_ac(
            shield_key="shield",
            dexterity_mod=4,
        )
        assert ac == 16  # 10 + 4 DEX + 2 shield
