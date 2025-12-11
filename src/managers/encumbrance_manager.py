"""EncumbranceManager for tracking carrying capacity and weight penalties."""

from dataclasses import dataclass
from enum import Enum

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from src.database.models.entities import Entity, EntityAttribute
from src.database.models.items import Item
from src.database.models.session import GameSession
from src.managers.base import BaseManager


class EncumbranceLevel(str, Enum):
    """Encumbrance level based on carried weight vs capacity."""

    LIGHT = "light"  # 0-33% capacity - no penalty
    MEDIUM = "medium"  # 34-66% capacity - -10 speed
    HEAVY = "heavy"  # 67-100% capacity - -20 speed, disadvantage on physical
    OVER = "over"  # >100% capacity - immobile, disadvantage on all


@dataclass
class EncumbranceStatus:
    """Current encumbrance status for an entity.

    Attributes:
        carried_weight: Total weight of all carried items in pounds.
        capacity: Maximum carrying capacity in pounds.
        level: Current encumbrance level.
        speed_penalty: Movement speed reduction (0, 10, 20, or -1 for immobile).
        combat_penalty: Combat disadvantage type if any.
        percentage: Carried weight as percentage of capacity.
    """

    carried_weight: float
    capacity: float
    level: EncumbranceLevel
    speed_penalty: int
    combat_penalty: str | None
    percentage: float


# Encumbrance thresholds as percentage of capacity
LIGHT_THRESHOLD = 0.33
MEDIUM_THRESHOLD = 0.66
HEAVY_THRESHOLD = 1.0

# Penalties by level
ENCUMBRANCE_PENALTIES = {
    EncumbranceLevel.LIGHT: {"speed": 0, "combat": None},
    EncumbranceLevel.MEDIUM: {"speed": 10, "combat": None},
    EncumbranceLevel.HEAVY: {"speed": 20, "combat": "disadvantage_physical"},
    EncumbranceLevel.OVER: {"speed": -1, "combat": "disadvantage_all"},  # -1 = immobile
}

# Default strength if entity has no strength attribute
DEFAULT_STRENGTH = 10

# Pounds carried per point of strength
CAPACITY_PER_STRENGTH = 15.0


class EncumbranceManager(BaseManager):
    """Manager for encumbrance and carrying capacity.

    Handles:
    - Calculating carrying capacity from strength
    - Summing carried item weight
    - Determining encumbrance level and penalties
    - Checking if entity can pick up additional items
    """

    def get_carry_capacity(self, strength: int) -> float:
        """Calculate carrying capacity from strength.

        Args:
            strength: The entity's strength value.

        Returns:
            Maximum carrying capacity in pounds.
        """
        return strength * CAPACITY_PER_STRENGTH

    def get_entity_capacity(self, entity_key: str) -> float:
        """Get carrying capacity for an entity.

        Args:
            entity_key: The entity's unique key.

        Returns:
            Maximum carrying capacity in pounds.
        """
        # Get entity
        entity = (
            self.db.query(Entity)
            .filter(
                and_(
                    Entity.session_id == self.session_id,
                    Entity.entity_key == entity_key,
                )
            )
            .first()
        )

        if not entity:
            return self.get_carry_capacity(DEFAULT_STRENGTH)

        # Get strength attribute (EntityAttribute is scoped via entity_id, not session_id)
        strength_attr = (
            self.db.query(EntityAttribute)
            .filter(
                and_(
                    EntityAttribute.entity_id == entity.id,
                    EntityAttribute.attribute_key == "strength",
                )
            )
            .first()
        )

        strength = strength_attr.value if strength_attr else DEFAULT_STRENGTH
        return self.get_carry_capacity(strength)

    def get_carried_weight(self, entity_key: str) -> float:
        """Calculate total weight of items carried by an entity.

        Args:
            entity_key: The entity's unique key.

        Returns:
            Total weight in pounds (items with no weight are ignored).
        """
        # Get entity
        entity = (
            self.db.query(Entity)
            .filter(
                and_(
                    Entity.session_id == self.session_id,
                    Entity.entity_key == entity_key,
                )
            )
            .first()
        )

        if not entity:
            return 0.0

        # Sum weight of all items held by this entity
        # Weight is multiplied by quantity for stacked items
        result = (
            self.db.query(func.sum(Item.weight * Item.quantity))
            .filter(
                and_(
                    Item.session_id == self.session_id,
                    Item.holder_id == entity.id,
                    Item.weight.isnot(None),
                )
            )
            .scalar()
        )

        return float(result) if result else 0.0

    def _calculate_encumbrance_level(
        self, carried_weight: float, capacity: float
    ) -> EncumbranceLevel:
        """Determine encumbrance level from weight and capacity.

        Args:
            carried_weight: Current carried weight in pounds.
            capacity: Maximum capacity in pounds.

        Returns:
            The encumbrance level.
        """
        if capacity <= 0:
            return EncumbranceLevel.OVER

        ratio = carried_weight / capacity

        if ratio <= LIGHT_THRESHOLD:
            return EncumbranceLevel.LIGHT
        elif ratio <= MEDIUM_THRESHOLD:
            return EncumbranceLevel.MEDIUM
        elif ratio <= HEAVY_THRESHOLD:
            return EncumbranceLevel.HEAVY
        else:
            return EncumbranceLevel.OVER

    def get_encumbrance_status(self, entity_key: str) -> EncumbranceStatus | None:
        """Get full encumbrance status for an entity.

        Args:
            entity_key: The entity's unique key.

        Returns:
            EncumbranceStatus with all details, or None if entity not found.
        """
        # Check entity exists
        entity = (
            self.db.query(Entity)
            .filter(
                and_(
                    Entity.session_id == self.session_id,
                    Entity.entity_key == entity_key,
                )
            )
            .first()
        )

        if not entity:
            return None

        carried_weight = self.get_carried_weight(entity_key)
        capacity = self.get_entity_capacity(entity_key)
        level = self._calculate_encumbrance_level(carried_weight, capacity)
        penalties = ENCUMBRANCE_PENALTIES[level]

        percentage = (carried_weight / capacity * 100) if capacity > 0 else 100.0

        return EncumbranceStatus(
            carried_weight=carried_weight,
            capacity=capacity,
            level=level,
            speed_penalty=penalties["speed"],
            combat_penalty=penalties["combat"],
            percentage=round(percentage, 1),
        )

    def can_pick_up(
        self, entity_key: str, item_key: str
    ) -> tuple[bool, str | None]:
        """Check if an entity can pick up an item without exceeding capacity.

        Args:
            entity_key: The entity's unique key.
            item_key: The item's unique key.

        Returns:
            Tuple of (can_pick_up, reason_if_not).
        """
        # Get item
        item = (
            self.db.query(Item)
            .filter(
                and_(
                    Item.session_id == self.session_id,
                    Item.item_key == item_key,
                )
            )
            .first()
        )

        if not item:
            return False, "Item not found"

        # Weightless items can always be picked up
        if item.weight is None:
            return True, None

        # Get current weight and capacity
        current_weight = self.get_carried_weight(entity_key)
        capacity = self.get_entity_capacity(entity_key)

        # Calculate new weight (including quantity for stacked items)
        item_weight = item.weight * item.quantity
        new_weight = current_weight + item_weight

        if new_weight > capacity:
            return (
                False,
                f"Would exceed carrying capacity ({new_weight:.1f}/{capacity:.1f} lbs)",
            )

        return True, None

    def get_encumbrance_context(self, entity_key: str) -> str:
        """Format encumbrance status for GM prompt context.

        Args:
            entity_key: The entity's unique key.

        Returns:
            Formatted string describing encumbrance status.
        """
        status = self.get_encumbrance_status(entity_key)

        if not status:
            return ""

        lines = [
            f"Carrying: {status.carried_weight:.1f}/{status.capacity:.1f} lbs "
            f"({status.percentage:.0f}%)",
            f"Encumbrance: {status.level.value}",
        ]

        if status.level == EncumbranceLevel.MEDIUM:
            lines.append("Speed: -10 ft")
        elif status.level == EncumbranceLevel.HEAVY:
            lines.append("Speed: -20 ft")
            lines.append("Penalty: Disadvantage on physical checks")
        elif status.level == EncumbranceLevel.OVER:
            lines.append("Movement: IMMOBILE (over-encumbered)")
            lines.append("Penalty: Disadvantage on ALL checks")

        return "\n".join(lines)
