"""Combat state schemas for the combat resolver.

These dataclasses track combat encounter state as it flows through the graph.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Combatant:
    """Represents a participant in combat."""

    entity_id: int
    entity_key: str
    display_name: str
    hit_points: int = 0
    max_hit_points: int = 0
    armor_class: int = 10
    attack_bonus: int = 0
    damage_dice: str = "1d4"
    damage_type: str = "bludgeoning"
    initiative: int = 0
    is_player: bool = False
    is_dead: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "entity_id": self.entity_id,
            "entity_key": self.entity_key,
            "display_name": self.display_name,
            "hit_points": self.hit_points,
            "max_hit_points": self.max_hit_points,
            "armor_class": self.armor_class,
            "attack_bonus": self.attack_bonus,
            "damage_dice": self.damage_dice,
            "damage_type": self.damage_type,
            "initiative": self.initiative,
            "is_player": self.is_player,
            "is_dead": self.is_dead,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Combatant":
        """Create from dictionary."""
        return cls(
            entity_id=data["entity_id"],
            entity_key=data["entity_key"],
            display_name=data["display_name"],
            hit_points=data.get("hit_points", 0),
            max_hit_points=data.get("max_hit_points", 0),
            armor_class=data.get("armor_class", 10),
            attack_bonus=data.get("attack_bonus", 0),
            damage_dice=data.get("damage_dice", "1d4"),
            damage_type=data.get("damage_type", "bludgeoning"),
            initiative=data.get("initiative", 0),
            is_player=data.get("is_player", False),
            is_dead=data.get("is_dead", False),
        )


@dataclass
class CombatState:
    """State for tracking a combat encounter."""

    combatants: list[Combatant] = field(default_factory=list)
    initiative_order: list[int] = field(default_factory=list)
    round_number: int = 1
    current_turn_index: int = 0
    combat_log: list[str] = field(default_factory=list)

    @property
    def current_combatant(self) -> Combatant | None:
        """Get the combatant whose turn it is."""
        if not self.initiative_order:
            return None
        if self.current_turn_index >= len(self.initiative_order):
            return None

        current_id = self.initiative_order[self.current_turn_index]
        for c in self.combatants:
            if c.entity_id == current_id:
                return c
        return None

    @property
    def is_combat_over(self) -> bool:
        """Check if combat has ended."""
        alive_enemies = [c for c in self.combatants if not c.is_player and not c.is_dead]
        alive_players = [c for c in self.combatants if c.is_player and not c.is_dead]
        return len(alive_enemies) == 0 or len(alive_players) == 0

    @property
    def player_victory(self) -> bool:
        """Check if player won (all enemies dead, player alive)."""
        if not self.is_combat_over:
            return False
        alive_players = [c for c in self.combatants if c.is_player and not c.is_dead]
        return len(alive_players) > 0

    def get_combatant(self, entity_id: int) -> Combatant | None:
        """Get a combatant by entity ID."""
        for c in self.combatants:
            if c.entity_id == entity_id:
                return c
        return None

    def update_combatant(self, updated: Combatant) -> None:
        """Update a combatant in the list."""
        for i, c in enumerate(self.combatants):
            if c.entity_id == updated.entity_id:
                self.combatants[i] = updated
                return

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "combatants": [c.to_dict() for c in self.combatants],
            "initiative_order": self.initiative_order,
            "round_number": self.round_number,
            "current_turn_index": self.current_turn_index,
            "combat_log": self.combat_log,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CombatState":
        """Create from dictionary."""
        return cls(
            combatants=[Combatant.from_dict(c) for c in data.get("combatants", [])],
            initiative_order=data.get("initiative_order", []),
            round_number=data.get("round_number", 1),
            current_turn_index=data.get("current_turn_index", 0),
            combat_log=data.get("combat_log", []),
        )
