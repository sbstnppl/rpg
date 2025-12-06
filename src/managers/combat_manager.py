"""Combat management for resolving combat encounters."""

from dataclasses import replace
from typing import Any

from sqlalchemy.orm import Session

from src.agents.schemas.combat import CombatState, Combatant
from src.database.models.entities import Entity, EntityAttribute, MonsterExtension
from src.database.models.enums import EntityType
from src.database.models.session import GameSession
from src.dice.combat import make_attack_roll, roll_damage, roll_initiative
from src.managers.base import BaseManager


class CombatManager(BaseManager):
    """Manages combat encounters and resolution."""

    def initialize_combat(
        self,
        player_id: int,
        enemy_ids: list[int],
    ) -> CombatState:
        """Initialize a combat encounter.

        Args:
            player_id: Player entity ID.
            enemy_ids: List of enemy entity IDs.

        Returns:
            Initialized CombatState with all combatants.
        """
        combatants = []

        # Add player
        player = self._load_combatant(player_id, is_player=True)
        if player:
            combatants.append(player)

        # Add enemies
        for enemy_id in enemy_ids:
            enemy = self._load_combatant(enemy_id, is_player=False)
            if enemy:
                combatants.append(enemy)

        state = CombatState(combatants=combatants)

        # Roll initiative for all
        state = self.roll_all_initiatives(state)

        return state

    def _load_combatant(self, entity_id: int, is_player: bool) -> Combatant | None:
        """Load an entity as a combatant.

        Args:
            entity_id: Entity ID.
            is_player: Whether this is the player.

        Returns:
            Combatant or None if entity not found.
        """
        entity = (
            self.db.query(Entity)
            .filter(Entity.id == entity_id, Entity.session_id == self.game_session.id)
            .first()
        )
        if not entity:
            return None

        # Default stats
        hit_points = 30 if is_player else 10
        max_hit_points = hit_points
        armor_class = 10
        attack_bonus = 0
        damage_dice = "1d4"
        dex_mod = 0

        # Get DEX modifier for initiative
        dex_attr = (
            self.db.query(EntityAttribute)
            .filter(
                EntityAttribute.entity_id == entity_id,
                EntityAttribute.attribute_key == "dexterity",
            )
            .first()
        )
        if dex_attr:
            dex_mod = (dex_attr.value - 10) // 2

        # Get monster stats if applicable
        if entity.entity_type == EntityType.MONSTER:
            monster_ext = (
                self.db.query(MonsterExtension)
                .filter(MonsterExtension.entity_id == entity_id)
                .first()
            )
            if monster_ext:
                hit_points = monster_ext.hit_points
                max_hit_points = monster_ext.max_hit_points
                armor_class = monster_ext.armor_class

        # Calculate attack bonus from STR
        str_attr = (
            self.db.query(EntityAttribute)
            .filter(
                EntityAttribute.entity_id == entity_id,
                EntityAttribute.attribute_key == "strength",
            )
            .first()
        )
        if str_attr:
            attack_bonus = (str_attr.value - 10) // 2

        return Combatant(
            entity_id=entity.id,
            entity_key=entity.entity_key,
            display_name=entity.display_name,
            hit_points=hit_points,
            max_hit_points=max_hit_points,
            armor_class=armor_class,
            attack_bonus=attack_bonus,
            damage_dice=damage_dice,
            is_player=is_player,
        )

    def roll_all_initiatives(self, state: CombatState) -> CombatState:
        """Roll initiative for all combatants and sort.

        Args:
            state: Current combat state.

        Returns:
            Updated state with initiatives and sorted order.
        """
        # Roll for each combatant
        initiatives: list[tuple[int, int]] = []  # (entity_id, initiative)

        for combatant in state.combatants:
            # Get DEX modifier (would need to look up, using 0 for simplicity)
            dex_mod = 0
            roll_result = roll_initiative(dex_mod)
            combatant.initiative = roll_result.total
            initiatives.append((combatant.entity_id, roll_result.total))

        # Sort by initiative (highest first)
        initiatives.sort(key=lambda x: x[1], reverse=True)

        # Update initiative order
        state.initiative_order = [entity_id for entity_id, _ in initiatives]

        return state

    def resolve_attack(
        self,
        attacker: Combatant,
        defender: Combatant,
    ) -> tuple[bool, int, str]:
        """Resolve an attack from attacker to defender.

        Args:
            attacker: The attacking combatant.
            defender: The defending combatant.

        Returns:
            Tuple of (hit, damage, narrative).
        """
        # Make attack roll
        attack_result = make_attack_roll(
            target_ac=defender.armor_class,
            attack_bonus=attacker.attack_bonus,
        )

        if not attack_result.hit:
            narrative = f"{attacker.display_name} attacks {defender.display_name} but misses!"
            return False, 0, narrative

        # Roll damage
        damage_result = roll_damage(
            damage_dice=attacker.damage_dice,
            damage_type=attacker.damage_type,
            bonus=attacker.attack_bonus,
            is_critical=attack_result.is_critical_hit,
        )

        damage = damage_result.roll_result.total

        if attack_result.is_critical_hit:
            narrative = f"{attacker.display_name} lands a CRITICAL HIT on {defender.display_name} for {damage} damage!"
        else:
            narrative = f"{attacker.display_name} hits {defender.display_name} for {damage} damage!"

        return True, damage, narrative

    def apply_damage(
        self,
        combatant: Combatant,
        damage: int,
        damage_type: str,
    ) -> tuple[Combatant, str]:
        """Apply damage to a combatant.

        Args:
            combatant: The combatant taking damage.
            damage: Amount of damage.
            damage_type: Type of damage.

        Returns:
            Tuple of (updated_combatant, narrative).
        """
        new_hp = max(0, combatant.hit_points - damage)
        is_dead = new_hp <= 0

        updated = replace(
            combatant,
            hit_points=new_hp,
            is_dead=is_dead,
        )

        if is_dead:
            narrative = f"{combatant.display_name} falls to the ground, defeated!"
        else:
            narrative = f"{combatant.display_name} has {new_hp}/{combatant.max_hit_points} HP remaining."

        return updated, narrative

    def advance_turn(self, state: CombatState) -> CombatState:
        """Advance to the next combatant's turn.

        Args:
            state: Current combat state.

        Returns:
            Updated state with next turn.
        """
        # Skip dead combatants
        next_index = state.current_turn_index + 1
        wrapped = False

        while True:
            # Wrap around to new round
            if next_index >= len(state.initiative_order):
                next_index = 0
                wrapped = True

            # Get combatant at this index
            entity_id = state.initiative_order[next_index]
            combatant = state.get_combatant(entity_id)

            # If alive, this is the next turn
            if combatant and not combatant.is_dead:
                break

            next_index += 1

            # Safety: if we've gone through everyone
            if next_index >= len(state.initiative_order) * 2:
                break

        new_round = state.round_number + 1 if wrapped else state.round_number

        return replace(
            state,
            current_turn_index=next_index,
            round_number=new_round,
        )

    def get_living_enemies(self, state: CombatState) -> list[Combatant]:
        """Get all living enemy combatants.

        Args:
            state: Current combat state.

        Returns:
            List of living enemy combatants.
        """
        return [c for c in state.combatants if not c.is_player and not c.is_dead]

    def get_player(self, state: CombatState) -> Combatant | None:
        """Get the player combatant.

        Args:
            state: Current combat state.

        Returns:
            Player combatant or None.
        """
        for c in state.combatants:
            if c.is_player:
                return c
        return None
