"""Combat condition manager for tracking entity conditions.

Handles applying, removing, and querying combat conditions like
prone, stunned, grappled, etc.
"""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import Entity
from src.database.models.combat_conditions import CombatCondition, EntityCondition
from src.managers.base import BaseManager


@dataclass
class ConditionInfo:
    """Information about an active condition."""

    condition: CombatCondition
    duration_rounds: int | None
    rounds_remaining: int | None
    source_entity_key: str | None
    source_description: str | None
    exhaustion_level: int | None = None


@dataclass
class ConditionEffect:
    """Combat effects from conditions."""

    # Attack modifiers
    attack_disadvantage: bool = False
    attack_advantage: bool = False

    # Defense modifiers
    attacks_against_advantage: bool = False
    attacks_against_disadvantage: bool = False
    melee_attacks_against_advantage: bool = False
    ranged_attacks_against_disadvantage: bool = False

    # Save modifiers
    auto_fail_str_saves: bool = False
    auto_fail_dex_saves: bool = False
    save_disadvantage: bool = False

    # Ability check modifiers
    ability_check_disadvantage: bool = False

    # Movement
    speed_zero: bool = False
    speed_halved: bool = False
    cant_move: bool = False

    # Actions
    incapacitated: bool = False
    cant_take_actions: bool = False
    cant_take_reactions: bool = False

    # Other
    conditions: list[CombatCondition] = field(default_factory=list)


# Condition effect definitions
CONDITION_EFFECTS = {
    CombatCondition.PRONE: {
        "attack_disadvantage": True,
        "melee_attacks_against_advantage": True,
        "ranged_attacks_against_disadvantage": True,
    },
    CombatCondition.GRAPPLED: {
        "speed_zero": True,
    },
    CombatCondition.RESTRAINED: {
        "speed_zero": True,
        "attack_disadvantage": True,
        "attacks_against_advantage": True,
        "save_disadvantage": True,  # DEX saves
    },
    CombatCondition.PARALYZED: {
        "incapacitated": True,
        "cant_move": True,
        "auto_fail_str_saves": True,
        "auto_fail_dex_saves": True,
        "attacks_against_advantage": True,
    },
    CombatCondition.BLINDED: {
        "attack_disadvantage": True,
        "attacks_against_advantage": True,
    },
    CombatCondition.DEAFENED: {
        # Mainly RP and hearing-based checks
    },
    CombatCondition.INVISIBLE: {
        "attack_advantage": True,
        "attacks_against_disadvantage": True,
    },
    CombatCondition.STUNNED: {
        "incapacitated": True,
        "cant_move": True,
        "auto_fail_str_saves": True,
        "auto_fail_dex_saves": True,
        "attacks_against_advantage": True,
    },
    CombatCondition.INCAPACITATED: {
        "cant_take_actions": True,
        "cant_take_reactions": True,
    },
    CombatCondition.UNCONSCIOUS: {
        "incapacitated": True,
        "cant_move": True,
        "auto_fail_str_saves": True,
        "auto_fail_dex_saves": True,
        "attacks_against_advantage": True,
    },
    CombatCondition.POISONED: {
        "attack_disadvantage": True,
        "ability_check_disadvantage": True,
    },
    CombatCondition.FRIGHTENED: {
        "attack_disadvantage": True,
        "ability_check_disadvantage": True,
    },
    CombatCondition.CHARMED: {
        # Can't attack charmer, mainly RP
    },
    CombatCondition.EXHAUSTED: {
        # Effects depend on level, handled specially
    },
    CombatCondition.PETRIFIED: {
        "incapacitated": True,
        "cant_move": True,
        "auto_fail_str_saves": True,
        "auto_fail_dex_saves": True,
    },
    CombatCondition.HIDDEN: {
        "attack_advantage": True,
    },
    CombatCondition.CONCENTRATING: {
        # Just tracking, no direct combat effects
    },
}

# Exhaustion level effects
EXHAUSTION_EFFECTS = {
    1: {"ability_check_disadvantage": True},
    2: {"speed_halved": True},
    3: {"attack_disadvantage": True, "save_disadvantage": True},
    4: {},  # HP max halved - tracked elsewhere
    5: {"speed_zero": True},
    6: {},  # Death - tracked elsewhere
}


class CombatConditionManager(BaseManager):
    """Manages combat conditions on entities.

    Handles applying, removing, duration tracking, and effect calculation.
    """

    def _get_entity(self, entity_key: str) -> Entity | None:
        """Get entity by key."""
        return self.db.execute(
            select(Entity).where(
                Entity.session_id == self.session_id,
                Entity.entity_key == entity_key,
            )
        ).scalar_one_or_none()

    def apply_condition(
        self,
        entity_key: str,
        condition: CombatCondition,
        duration_rounds: int | None = None,
        source_entity_key: str | None = None,
        source_description: str | None = None,
        exhaustion_level: int | None = None,
    ) -> ConditionInfo | None:
        """Apply a condition to an entity.

        If the entity already has this condition, the duration is updated
        (not stacked). Exhaustion is special and stacks levels.

        Args:
            entity_key: Entity to apply condition to.
            condition: The condition to apply.
            duration_rounds: Duration in rounds (None = permanent).
            source_entity_key: Entity that caused this condition.
            source_description: Description of source.
            exhaustion_level: For exhaustion, the level to add.

        Returns:
            ConditionInfo for the applied condition, or None if entity not found.
        """
        entity = self._get_entity(entity_key)
        if not entity:
            return None

        source_entity = None
        if source_entity_key:
            source_entity = self._get_entity(source_entity_key)

        # Check for existing condition
        existing = self.db.execute(
            select(EntityCondition).where(
                EntityCondition.entity_id == entity.id,
                EntityCondition.condition == condition,
            )
        ).scalar_one_or_none()

        if existing:
            # Update existing condition
            if condition == CombatCondition.EXHAUSTED:
                # Exhaustion stacks levels
                current_level = existing.exhaustion_level or 0
                new_level = min(6, current_level + (exhaustion_level or 1))
                existing.exhaustion_level = new_level
            else:
                # Other conditions: update duration if longer
                if duration_rounds is not None:
                    if existing.rounds_remaining is None or duration_rounds > existing.rounds_remaining:
                        existing.duration_rounds = duration_rounds
                        existing.rounds_remaining = duration_rounds

            if source_entity:
                existing.source_entity_id = source_entity.id
            if source_description:
                existing.source_description = source_description

            self.db.flush()
            entity_cond = existing
        else:
            # Create new condition
            entity_cond = EntityCondition(
                session_id=self.session_id,
                entity_id=entity.id,
                condition=condition,
                duration_rounds=duration_rounds,
                rounds_remaining=duration_rounds,
                source_entity_id=source_entity.id if source_entity else None,
                source_description=source_description,
                exhaustion_level=exhaustion_level if condition == CombatCondition.EXHAUSTED else None,
                applied_turn=self.current_turn,
            )
            self.db.add(entity_cond)
            self.db.flush()

        return ConditionInfo(
            condition=entity_cond.condition,
            duration_rounds=entity_cond.duration_rounds,
            rounds_remaining=entity_cond.rounds_remaining,
            source_entity_key=source_entity_key,
            source_description=entity_cond.source_description,
            exhaustion_level=entity_cond.exhaustion_level,
        )

    def remove_condition(
        self, entity_key: str, condition: CombatCondition
    ) -> bool:
        """Remove a condition from an entity.

        Args:
            entity_key: Entity to remove condition from.
            condition: The condition to remove.

        Returns:
            True if removed, False if not found.
        """
        entity = self._get_entity(entity_key)
        if not entity:
            return False

        existing = self.db.execute(
            select(EntityCondition).where(
                EntityCondition.entity_id == entity.id,
                EntityCondition.condition == condition,
            )
        ).scalar_one_or_none()

        if existing:
            self.db.delete(existing)
            self.db.flush()
            return True
        return False

    def remove_all_conditions(self, entity_key: str) -> int:
        """Remove all conditions from an entity.

        Args:
            entity_key: Entity to clear conditions from.

        Returns:
            Number of conditions removed.
        """
        entity = self._get_entity(entity_key)
        if not entity:
            return 0

        conditions = self.db.execute(
            select(EntityCondition).where(EntityCondition.entity_id == entity.id)
        ).scalars().all()

        count = len(conditions)
        for cond in conditions:
            self.db.delete(cond)
        self.db.flush()
        return count

    def tick_conditions(self, entity_key: str) -> list[CombatCondition]:
        """Advance one round for all conditions on an entity.

        Decrements duration and removes expired conditions.

        Args:
            entity_key: Entity to tick conditions for.

        Returns:
            List of conditions that expired this tick.
        """
        entity = self._get_entity(entity_key)
        if not entity:
            return []

        conditions = self.db.execute(
            select(EntityCondition).where(EntityCondition.entity_id == entity.id)
        ).scalars().all()

        expired = []
        for cond in conditions:
            if cond.rounds_remaining is not None:
                cond.rounds_remaining -= 1
                if cond.rounds_remaining <= 0:
                    expired.append(cond.condition)
                    self.db.delete(cond)

        self.db.flush()
        return expired

    def has_condition(
        self, entity_key: str, condition: CombatCondition
    ) -> bool:
        """Check if entity has a specific condition.

        Args:
            entity_key: Entity to check.
            condition: Condition to check for.

        Returns:
            True if entity has the condition.
        """
        entity = self._get_entity(entity_key)
        if not entity:
            return False

        existing = self.db.execute(
            select(EntityCondition).where(
                EntityCondition.entity_id == entity.id,
                EntityCondition.condition == condition,
            )
        ).scalar_one_or_none()

        return existing is not None

    def get_active_conditions(self, entity_key: str) -> list[ConditionInfo]:
        """Get all active conditions on an entity.

        Args:
            entity_key: Entity to get conditions for.

        Returns:
            List of ConditionInfo objects.
        """
        entity = self._get_entity(entity_key)
        if not entity:
            return []

        conditions = self.db.execute(
            select(EntityCondition).where(EntityCondition.entity_id == entity.id)
        ).scalars().all()

        result = []
        for cond in conditions:
            source_key = None
            if cond.source_entity_id:
                source = self.db.execute(
                    select(Entity).where(Entity.id == cond.source_entity_id)
                ).scalar_one_or_none()
                if source:
                    source_key = source.entity_key

            result.append(ConditionInfo(
                condition=cond.condition,
                duration_rounds=cond.duration_rounds,
                rounds_remaining=cond.rounds_remaining,
                source_entity_key=source_key,
                source_description=cond.source_description,
                exhaustion_level=cond.exhaustion_level,
            ))

        return result

    def get_condition_info(
        self, entity_key: str, condition: CombatCondition
    ) -> ConditionInfo | None:
        """Get info about a specific condition on an entity.

        Args:
            entity_key: Entity to check.
            condition: Condition to get info for.

        Returns:
            ConditionInfo or None if not found.
        """
        entity = self._get_entity(entity_key)
        if not entity:
            return None

        cond = self.db.execute(
            select(EntityCondition).where(
                EntityCondition.entity_id == entity.id,
                EntityCondition.condition == condition,
            )
        ).scalar_one_or_none()

        if not cond:
            return None

        source_key = None
        if cond.source_entity_id:
            source = self.db.execute(
                select(Entity).where(Entity.id == cond.source_entity_id)
            ).scalar_one_or_none()
            if source:
                source_key = source.entity_key

        return ConditionInfo(
            condition=cond.condition,
            duration_rounds=cond.duration_rounds,
            rounds_remaining=cond.rounds_remaining,
            source_entity_key=source_key,
            source_description=cond.source_description,
            exhaustion_level=cond.exhaustion_level,
        )

    def get_condition_effects(self, entity_key: str) -> ConditionEffect:
        """Calculate combined effects of all conditions on an entity.

        Args:
            entity_key: Entity to calculate effects for.

        Returns:
            ConditionEffect with combined effects.
        """
        conditions = self.get_active_conditions(entity_key)
        effects = ConditionEffect()

        for cond_info in conditions:
            effects.conditions.append(cond_info.condition)

            # Get base effects for this condition
            base_effects = CONDITION_EFFECTS.get(cond_info.condition, {})
            for effect_name, value in base_effects.items():
                if value:
                    setattr(effects, effect_name, True)

            # Handle exhaustion specially
            if cond_info.condition == CombatCondition.EXHAUSTED and cond_info.exhaustion_level:
                for level in range(1, cond_info.exhaustion_level + 1):
                    level_effects = EXHAUSTION_EFFECTS.get(level, {})
                    for effect_name, value in level_effects.items():
                        if value:
                            setattr(effects, effect_name, True)

        return effects

    def get_condition_context(self, entity_key: str) -> str:
        """Generate context string for entity's conditions.

        Args:
            entity_key: Entity to generate context for.

        Returns:
            Formatted context string, or empty if no conditions.
        """
        conditions = self.get_active_conditions(entity_key)
        if not conditions:
            return ""

        lines = []
        for cond in conditions:
            name = cond.condition.value.replace("_", " ").title()
            parts = [name]

            if cond.exhaustion_level:
                parts[0] = f"{name} (Level {cond.exhaustion_level})"

            if cond.rounds_remaining:
                parts.append(f"{cond.rounds_remaining} rounds remaining")

            if cond.source_description:
                parts.append(f"from {cond.source_description}")
            elif cond.source_entity_key:
                parts.append(f"from {cond.source_entity_key}")

            lines.append("- " + ", ".join(parts))

        return "## Active Conditions\n" + "\n".join(lines)
