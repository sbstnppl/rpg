"""GM Tool Executor for processing LLM tool calls.

Executes tools and returns structured results for the LLM to incorporate
into its narrative.
"""

from typing import Any

from sqlalchemy.orm import Session

from src.database.models.entities import Entity
from src.database.models.session import GameSession
from src.dice.checks import make_skill_check
from src.dice.combat import make_attack_roll, roll_damage
from src.dice.types import AdvantageType
from src.managers.relationship_manager import RelationshipManager


class GMToolExecutor:
    """Executes GM tools and returns structured results."""

    def __init__(self, db: Session, game_session: GameSession):
        """Initialize executor with database context.

        Args:
            db: Database session.
            game_session: Current game session.
        """
        self.db = db
        self.game_session = game_session
        self.relationship_manager = RelationshipManager(db, game_session)

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool and return structured result.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Tool arguments from LLM.

        Returns:
            Structured result dict for LLM to use.

        Raises:
            ValueError: If tool_name is unknown.
        """
        handlers = {
            "skill_check": self._execute_skill_check,
            "attack_roll": self._execute_attack_roll,
            "roll_damage": self._execute_roll_damage,
            "get_npc_attitude": self._execute_get_npc_attitude,
            "update_npc_attitude": self._execute_update_npc_attitude,
        }

        handler = handlers.get(tool_name)
        if handler is None:
            raise ValueError(f"Unknown tool: {tool_name}")

        return handler(arguments)

    def _execute_skill_check(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute a skill check.

        Args:
            args: Tool arguments with dc, skill_name, attribute_modifier, advantage.

        Returns:
            Result with success, roll, margin, and description.
        """
        dc = args["dc"]
        skill_name = args["skill_name"]
        attribute_modifier = args.get("attribute_modifier", 0)
        advantage_str = args.get("advantage", "normal")

        advantage_type = self._parse_advantage(advantage_str)

        result = make_skill_check(
            dc=dc,
            attribute_modifier=attribute_modifier,
            skill_modifier=0,
            advantage_type=advantage_type,
        )

        # Build description
        if result.is_critical_success:
            outcome = "Critical Success!"
        elif result.is_critical_failure:
            outcome = "Critical Failure!"
        elif result.success:
            outcome = "Success"
        else:
            outcome = "Failure"

        description = f"{skill_name.title()} check (DC {dc}): {outcome}"

        return {
            "success": result.success,
            "roll": result.roll_result.total,
            "natural_roll": result.roll_result.individual_rolls[0],
            "margin": result.margin,
            "is_critical_success": result.is_critical_success,
            "is_critical_failure": result.is_critical_failure,
            "description": description,
        }

    def _execute_attack_roll(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute an attack roll.

        Args:
            args: Tool arguments with target_ac, attack_bonus, advantage.

        Returns:
            Result with hit, roll, and critical status.
        """
        target_ac = args["target_ac"]
        attack_bonus = args.get("attack_bonus", 0)
        advantage_str = args.get("advantage", "normal")

        advantage_type = self._parse_advantage(advantage_str)

        result = make_attack_roll(
            target_ac=target_ac,
            attack_bonus=attack_bonus,
            advantage_type=advantage_type,
        )

        return {
            "hit": result.hit,
            "roll": result.roll_result.total,
            "natural_roll": result.roll_result.individual_rolls[0],
            "is_critical_hit": result.is_critical_hit,
            "is_critical_miss": result.is_critical_miss,
            "target_ac": target_ac,
        }

    def _execute_roll_damage(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute a damage roll.

        Args:
            args: Tool arguments with damage_dice, damage_type, bonus, is_critical.

        Returns:
            Result with total, dice breakdown, and damage type.
        """
        damage_dice = args["damage_dice"]
        damage_type = args.get("damage_type", "untyped")
        bonus = args.get("bonus", 0)
        is_critical = args.get("is_critical", False)

        result = roll_damage(
            damage_dice=damage_dice,
            damage_type=damage_type,
            bonus=bonus,
            is_critical=is_critical,
        )

        return {
            "total": result.roll_result.total,
            "dice_rolls": list(result.roll_result.individual_rolls),
            "damage_type": result.damage_type,
            "is_critical": result.is_critical,
        }

    def _execute_get_npc_attitude(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get NPC attitude toward another entity.

        Args:
            args: Tool arguments with from_entity, to_entity (entity keys).

        Returns:
            Attitude dimensions or error.
        """
        from_key = args["from_entity"]
        to_key = args["to_entity"]

        # Look up entities by key
        from_entity = self._get_entity_by_key(from_key)
        to_entity = self._get_entity_by_key(to_key)

        if from_entity is None:
            return {"error": f"Entity '{from_key}' not found"}
        if to_entity is None:
            return {"error": f"Entity '{to_key}' not found"}

        attitude = self.relationship_manager.get_attitude(from_entity.id, to_entity.id)

        return {
            "from_entity": from_key,
            "to_entity": to_key,
            "trust": attitude["trust"],
            "liking": attitude["liking"],
            "respect": attitude["respect"],
            "romantic_interest": attitude["romantic_interest"],
            "familiarity": attitude["familiarity"],
            "fear": attitude["fear"],
            "knows": attitude["knows"],
        }

    def _execute_update_npc_attitude(self, args: dict[str, Any]) -> dict[str, Any]:
        """Update NPC attitude toward another entity.

        Args:
            args: Tool arguments with from_entity, to_entity, dimension, delta, reason.

        Returns:
            New value and delta applied.
        """
        from_key = args["from_entity"]
        to_key = args["to_entity"]
        dimension = args["dimension"]
        delta = args["delta"]
        reason = args["reason"]

        # Look up entities by key
        from_entity = self._get_entity_by_key(from_key)
        to_entity = self._get_entity_by_key(to_key)

        if from_entity is None:
            return {"error": f"Entity '{from_key}' not found"}
        if to_entity is None:
            return {"error": f"Entity '{to_key}' not found"}

        # Get old value for delta calculation
        old_attitude = self.relationship_manager.get_attitude(from_entity.id, to_entity.id)
        old_value = old_attitude.get(dimension, 50)

        # Update attitude
        self.relationship_manager.update_attitude(
            from_id=from_entity.id,
            to_id=to_entity.id,
            dimension=dimension,
            delta=delta,
            reason=reason,
        )

        # Get new value
        new_attitude = self.relationship_manager.get_attitude(from_entity.id, to_entity.id)
        new_value = new_attitude.get(dimension, 50)

        return {
            "from_entity": from_key,
            "to_entity": to_key,
            "dimension": dimension,
            "old_value": old_value,
            "new_value": new_value,
            "delta": new_value - old_value,
            "reason": reason,
        }

    def _get_entity_by_key(self, entity_key: str) -> Entity | None:
        """Look up an entity by its entity_key.

        Args:
            entity_key: The entity's unique key.

        Returns:
            Entity or None if not found.
        """
        return (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.game_session.id,
                Entity.entity_key == entity_key,
            )
            .first()
        )

    def _parse_advantage(self, advantage_str: str) -> AdvantageType:
        """Parse advantage string to enum.

        Args:
            advantage_str: One of "normal", "advantage", "disadvantage".

        Returns:
            AdvantageType enum value.
        """
        mapping = {
            "normal": AdvantageType.NORMAL,
            "advantage": AdvantageType.ADVANTAGE,
            "disadvantage": AdvantageType.DISADVANTAGE,
        }
        return mapping.get(advantage_str, AdvantageType.NORMAL)
