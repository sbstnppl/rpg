"""Equipment manager for weapon and armor definitions.

This manager handles creation, retrieval, and stat calculation
for weapons and armor.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models.equipment import (
    ArmorCategory,
    ArmorDefinition,
    DamageType,
    WeaponCategory,
    WeaponDefinition,
    WeaponRange,
)
from src.managers.base import BaseManager


@dataclass
class WeaponStats:
    """Calculated weapon statistics for combat."""

    weapon_key: str
    name: str
    attack_bonus: int
    damage_dice: str
    damage_bonus: int
    damage_type: str
    properties: list[str]
    range_normal: int | None = None
    range_long: int | None = None


@dataclass
class ArmorStats:
    """Calculated armor statistics."""

    armor_key: str
    name: str
    category: str
    total_ac: int
    base_ac: int
    dex_bonus_applied: int
    stealth_disadvantage: bool
    strength_required: int | None = None


class EquipmentManager(BaseManager):
    """Manages weapon and armor definitions.

    Handles creation, retrieval, and stat calculation for equipment.
    """

    # --- Weapon Methods ---

    def create_weapon(
        self,
        weapon_key: str,
        name: str,
        category: WeaponCategory,
        damage_dice: str,
        damage_type: DamageType,
        description: str | None = None,
        properties: list[str] | None = None,
        range_type: WeaponRange = WeaponRange.MELEE,
        range_normal: int | None = None,
        range_long: int | None = None,
        versatile_dice: str | None = None,
        weight: float | None = None,
    ) -> WeaponDefinition:
        """Create a new weapon definition.

        Args:
            weapon_key: Unique key within session.
            name: Display name.
            category: Weapon category (simple/martial, melee/ranged).
            damage_dice: Damage dice notation (e.g., "1d8").
            damage_type: Type of damage dealt.
            description: Optional description.
            properties: List of property values (e.g., ["finesse", "light"]).
            range_type: Range type (melee, reach, ranged, thrown).
            range_normal: Normal range in feet.
            range_long: Long range in feet.
            versatile_dice: Damage dice for two-handed use.
            weight: Weight in pounds.

        Returns:
            Created WeaponDefinition.
        """
        weapon = WeaponDefinition(
            session_id=self.session_id,
            weapon_key=weapon_key,
            name=name,
            description=description,
            category=category,
            damage_dice=damage_dice,
            damage_type=damage_type,
            properties=properties,
            range_type=range_type,
            range_normal=range_normal,
            range_long=range_long,
            versatile_dice=versatile_dice,
            weight=weight,
        )
        self.db.add(weapon)
        self.db.flush()
        return weapon

    def get_weapon(self, weapon_key: str) -> WeaponDefinition | None:
        """Get a weapon definition by key.

        Args:
            weapon_key: The weapon key.

        Returns:
            WeaponDefinition if found, None otherwise.
        """
        return self.db.execute(
            select(WeaponDefinition).where(
                WeaponDefinition.session_id == self.session_id,
                WeaponDefinition.weapon_key == weapon_key,
            )
        ).scalar_one_or_none()

    def get_all_weapons(self) -> list[WeaponDefinition]:
        """Get all weapon definitions for this session.

        Returns:
            List of all weapons.
        """
        return list(
            self.db.execute(
                select(WeaponDefinition).where(
                    WeaponDefinition.session_id == self.session_id
                )
            ).scalars().all()
        )

    def get_weapons_by_category(
        self, category: WeaponCategory
    ) -> list[WeaponDefinition]:
        """Get weapons of a specific category.

        Args:
            category: The weapon category to filter by.

        Returns:
            List of weapons in that category.
        """
        return list(
            self.db.execute(
                select(WeaponDefinition).where(
                    WeaponDefinition.session_id == self.session_id,
                    WeaponDefinition.category == category,
                )
            ).scalars().all()
        )

    def get_weapon_stats(
        self,
        weapon_key: str,
        strength_mod: int = 0,
        dexterity_mod: int = 0,
        proficiency_bonus: int = 0,
        two_handed: bool = False,
    ) -> WeaponStats | None:
        """Calculate weapon stats for an attacker.

        Determines attack bonus and damage based on weapon properties
        and attacker's ability modifiers.

        Args:
            weapon_key: The weapon to calculate stats for.
            strength_mod: Attacker's strength modifier.
            dexterity_mod: Attacker's dexterity modifier.
            proficiency_bonus: Proficiency bonus if proficient.
            two_handed: Whether using weapon two-handed (for versatile).

        Returns:
            WeaponStats or None if weapon not found.
        """
        weapon = self.get_weapon(weapon_key)
        if not weapon:
            return None

        properties = weapon.properties or []

        # Determine which ability modifier to use
        is_finesse = "finesse" in properties
        is_ranged = weapon.range_type == WeaponRange.RANGED

        if is_ranged:
            # Ranged weapons use DEX
            ability_mod = dexterity_mod
        elif is_finesse:
            # Finesse weapons use higher of STR or DEX
            ability_mod = max(strength_mod, dexterity_mod)
        else:
            # Melee weapons use STR
            ability_mod = strength_mod

        # Calculate attack bonus
        attack_bonus = ability_mod + proficiency_bonus

        # Determine damage dice (versatile if two-handed)
        is_versatile = "versatile" in properties
        if is_versatile and two_handed and weapon.versatile_dice:
            damage_dice = weapon.versatile_dice
        else:
            damage_dice = weapon.damage_dice

        return WeaponStats(
            weapon_key=weapon.weapon_key,
            name=weapon.name,
            attack_bonus=attack_bonus,
            damage_dice=damage_dice,
            damage_bonus=ability_mod,
            damage_type=weapon.damage_type.value,
            properties=properties,
            range_normal=weapon.range_normal,
            range_long=weapon.range_long,
        )

    # --- Armor Methods ---

    def create_armor(
        self,
        armor_key: str,
        name: str,
        category: ArmorCategory,
        base_ac: int,
        description: str | None = None,
        max_dex_bonus: int | None = None,
        strength_required: int | None = None,
        stealth_disadvantage: bool = False,
        weight: float | None = None,
    ) -> ArmorDefinition:
        """Create a new armor definition.

        Args:
            armor_key: Unique key within session.
            name: Display name.
            category: Armor category (light/medium/heavy/shield).
            base_ac: Base AC value (or bonus for shields).
            description: Optional description.
            max_dex_bonus: Maximum DEX bonus to AC (None = unlimited).
            strength_required: Minimum STR to avoid speed penalty.
            stealth_disadvantage: Whether wearing gives stealth disadvantage.
            weight: Weight in pounds.

        Returns:
            Created ArmorDefinition.
        """
        armor = ArmorDefinition(
            session_id=self.session_id,
            armor_key=armor_key,
            name=name,
            description=description,
            category=category,
            base_ac=base_ac,
            max_dex_bonus=max_dex_bonus,
            strength_required=strength_required,
            stealth_disadvantage=stealth_disadvantage,
            weight=weight,
        )
        self.db.add(armor)
        self.db.flush()
        return armor

    def get_armor(self, armor_key: str) -> ArmorDefinition | None:
        """Get an armor definition by key.

        Args:
            armor_key: The armor key.

        Returns:
            ArmorDefinition if found, None otherwise.
        """
        return self.db.execute(
            select(ArmorDefinition).where(
                ArmorDefinition.session_id == self.session_id,
                ArmorDefinition.armor_key == armor_key,
            )
        ).scalar_one_or_none()

    def get_all_armors(self) -> list[ArmorDefinition]:
        """Get all armor definitions for this session.

        Returns:
            List of all armors.
        """
        return list(
            self.db.execute(
                select(ArmorDefinition).where(
                    ArmorDefinition.session_id == self.session_id
                )
            ).scalars().all()
        )

    def get_armors_by_category(
        self, category: ArmorCategory
    ) -> list[ArmorDefinition]:
        """Get armors of a specific category.

        Args:
            category: The armor category to filter by.

        Returns:
            List of armors in that category.
        """
        return list(
            self.db.execute(
                select(ArmorDefinition).where(
                    ArmorDefinition.session_id == self.session_id,
                    ArmorDefinition.category == category,
                )
            ).scalars().all()
        )

    def get_armor_stats(
        self,
        armor_key: str,
        dexterity_mod: int = 0,
    ) -> ArmorStats | None:
        """Calculate armor stats.

        Args:
            armor_key: The armor to calculate stats for.
            dexterity_mod: Wearer's dexterity modifier.

        Returns:
            ArmorStats or None if armor not found.
        """
        armor = self.get_armor(armor_key)
        if not armor:
            return None

        # Calculate DEX bonus based on armor category
        if armor.category == ArmorCategory.SHIELD:
            # Shields just provide flat AC bonus
            dex_bonus = 0
            total_ac = armor.base_ac
        elif armor.max_dex_bonus is not None:
            # Cap DEX bonus
            dex_bonus = min(dexterity_mod, armor.max_dex_bonus)
            total_ac = armor.base_ac + dex_bonus
        else:
            # Full DEX bonus (light armor)
            dex_bonus = dexterity_mod
            total_ac = armor.base_ac + dex_bonus

        return ArmorStats(
            armor_key=armor.armor_key,
            name=armor.name,
            category=armor.category.value,
            total_ac=total_ac,
            base_ac=armor.base_ac,
            dex_bonus_applied=dex_bonus,
            stealth_disadvantage=armor.stealth_disadvantage,
            strength_required=armor.strength_required,
        )

    def calculate_total_ac(
        self,
        armor_key: str | None = None,
        shield_key: str | None = None,
        dexterity_mod: int = 0,
    ) -> int:
        """Calculate total AC with armor and optional shield.

        Args:
            armor_key: Armor being worn (None for unarmored).
            shield_key: Shield being held (None for no shield).
            dexterity_mod: Wearer's dexterity modifier.

        Returns:
            Total Armor Class.
        """
        # Base AC calculation
        if armor_key:
            armor_stats = self.get_armor_stats(armor_key, dexterity_mod)
            if armor_stats:
                base_ac = armor_stats.total_ac
            else:
                # Armor not found, use unarmored
                base_ac = 10 + dexterity_mod
        else:
            # Unarmored: 10 + DEX
            base_ac = 10 + dexterity_mod

        # Add shield bonus
        shield_bonus = 0
        if shield_key:
            shield = self.get_armor(shield_key)
            if shield and shield.category == ArmorCategory.SHIELD:
                shield_bonus = shield.base_ac

        return base_ac + shield_bonus
