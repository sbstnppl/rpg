"""Action types and dataclasses for the intent parser.

This module defines the core action types that the game recognizes
and the data structures for representing parsed player intents.
"""

from dataclasses import dataclass, field
from enum import Enum


class ActionType(str, Enum):
    """Types of mechanical actions a player can perform.

    These actions map to game state changes that can be validated
    and executed by the system. Each action type has corresponding
    validators and executors.
    """

    # Movement
    MOVE = "move"  # Go to a location/zone
    ENTER = "enter"  # Enter a building/room
    EXIT = "exit"  # Leave current location

    # Item Interaction
    TAKE = "take"  # Pick up an item
    DROP = "drop"  # Put down an item
    GIVE = "give"  # Give item to someone
    USE = "use"  # Use an item (general)
    EQUIP = "equip"  # Wear/wield an item
    UNEQUIP = "unequip"  # Remove worn/wielded item
    EXAMINE = "examine"  # Look at item/entity closely
    OPEN = "open"  # Open container/door
    CLOSE = "close"  # Close container/door

    # Combat
    ATTACK = "attack"  # Attack a target
    DEFEND = "defend"  # Take defensive stance
    FLEE = "flee"  # Attempt to escape combat

    # Social Interaction
    TALK = "talk"  # Initiate conversation with NPC
    ASK = "ask"  # Ask NPC about something
    TELL = "tell"  # Tell NPC something
    TRADE = "trade"  # Initiate trading with NPC
    PERSUADE = "persuade"  # Attempt to convince NPC
    INTIMIDATE = "intimidate"  # Attempt to frighten NPC

    # World Interaction
    SEARCH = "search"  # Search area for hidden things
    REST = "rest"  # Rest to recover stamina
    WAIT = "wait"  # Wait/pass time
    SLEEP = "sleep"  # Sleep (longer rest)

    # Consumption
    EAT = "eat"  # Eat food item
    DRINK = "drink"  # Drink beverage

    # Skills
    CRAFT = "craft"  # Create an item
    LOCKPICK = "lockpick"  # Attempt to pick a lock
    SNEAK = "sneak"  # Move stealthily
    CLIMB = "climb"  # Climb surface
    SWIM = "swim"  # Swim through water

    # Meta/Special
    LOOK = "look"  # Look around (scene description)
    INVENTORY = "inventory"  # Check inventory
    STATUS = "status"  # Check character status

    # Custom/Freeform
    CUSTOM = "custom"  # Unrecognized action requiring LLM interpretation


class ActionCategory(str, Enum):
    """High-level categories for grouping action types."""

    MOVEMENT = "movement"
    ITEM = "item"
    COMBAT = "combat"
    SOCIAL = "social"
    WORLD = "world"
    CONSUMPTION = "consumption"
    SKILL = "skill"
    META = "meta"


# Mapping of action types to categories
ACTION_CATEGORIES: dict[ActionType, ActionCategory] = {
    # Movement
    ActionType.MOVE: ActionCategory.MOVEMENT,
    ActionType.ENTER: ActionCategory.MOVEMENT,
    ActionType.EXIT: ActionCategory.MOVEMENT,
    # Item
    ActionType.TAKE: ActionCategory.ITEM,
    ActionType.DROP: ActionCategory.ITEM,
    ActionType.GIVE: ActionCategory.ITEM,
    ActionType.USE: ActionCategory.ITEM,
    ActionType.EQUIP: ActionCategory.ITEM,
    ActionType.UNEQUIP: ActionCategory.ITEM,
    ActionType.EXAMINE: ActionCategory.ITEM,
    ActionType.OPEN: ActionCategory.ITEM,
    ActionType.CLOSE: ActionCategory.ITEM,
    # Combat
    ActionType.ATTACK: ActionCategory.COMBAT,
    ActionType.DEFEND: ActionCategory.COMBAT,
    ActionType.FLEE: ActionCategory.COMBAT,
    # Social
    ActionType.TALK: ActionCategory.SOCIAL,
    ActionType.ASK: ActionCategory.SOCIAL,
    ActionType.TELL: ActionCategory.SOCIAL,
    ActionType.TRADE: ActionCategory.SOCIAL,
    ActionType.PERSUADE: ActionCategory.SOCIAL,
    ActionType.INTIMIDATE: ActionCategory.SOCIAL,
    # World
    ActionType.SEARCH: ActionCategory.WORLD,
    ActionType.REST: ActionCategory.WORLD,
    ActionType.WAIT: ActionCategory.WORLD,
    ActionType.SLEEP: ActionCategory.WORLD,
    # Consumption
    ActionType.EAT: ActionCategory.CONSUMPTION,
    ActionType.DRINK: ActionCategory.CONSUMPTION,
    # Skill
    ActionType.CRAFT: ActionCategory.SKILL,
    ActionType.LOCKPICK: ActionCategory.SKILL,
    ActionType.SNEAK: ActionCategory.SKILL,
    ActionType.CLIMB: ActionCategory.SKILL,
    ActionType.SWIM: ActionCategory.SKILL,
    # Meta
    ActionType.LOOK: ActionCategory.META,
    ActionType.INVENTORY: ActionCategory.META,
    ActionType.STATUS: ActionCategory.META,
    ActionType.CUSTOM: ActionCategory.META,
}


@dataclass
class Action:
    """A single mechanical action parsed from player input.

    Represents one atomic action that can be validated and executed
    by the game system.

    Attributes:
        type: The type of action (TAKE, MOVE, ATTACK, etc.)
        target: Primary target of the action (item key, location key, entity key)
        indirect_target: Secondary target for two-target actions ("give X to Y")
        manner: How the action is performed ("carefully", "quickly", "stealthily")
        parameters: Additional action-specific parameters
    """

    type: ActionType
    target: str | None = None
    indirect_target: str | None = None
    manner: str | None = None
    parameters: dict[str, str] = field(default_factory=dict)

    @property
    def category(self) -> ActionCategory:
        """Get the category of this action."""
        return ACTION_CATEGORIES.get(self.type, ActionCategory.META)

    @property
    def requires_target(self) -> bool:
        """Whether this action type requires a target."""
        return self.type not in {
            ActionType.LOOK,
            ActionType.INVENTORY,
            ActionType.STATUS,
            ActionType.REST,
            ActionType.WAIT,
            ActionType.SLEEP,
            ActionType.DEFEND,
            ActionType.FLEE,
        }

    @property
    def requires_indirect_target(self) -> bool:
        """Whether this action type requires an indirect target."""
        return self.type in {ActionType.GIVE, ActionType.ASK, ActionType.TELL}

    def __str__(self) -> str:
        """Human-readable representation of the action."""
        parts = [self.type.value]
        if self.target:
            parts.append(self.target)
        if self.indirect_target:
            parts.append(f"to {self.indirect_target}")
        if self.manner:
            parts.append(f"({self.manner})")
        return " ".join(parts)


@dataclass
class ParsedIntent:
    """The result of parsing player input.

    Contains all actions extracted from the input, plus any ambient
    flavor text that doesn't map to mechanical actions.

    Attributes:
        actions: List of mechanical actions to validate and execute
        ambient_flavor: Non-mechanical descriptive text ("nervously", "with a smile")
        raw_input: The original player input string
        needs_clarification: Whether the parser needs more information
        clarification_prompt: Question to ask player if clarification needed
    """

    actions: list[Action] = field(default_factory=list)
    ambient_flavor: str | None = None
    raw_input: str = ""
    needs_clarification: bool = False
    clarification_prompt: str | None = None

    @property
    def is_empty(self) -> bool:
        """Whether no actions were parsed."""
        return len(self.actions) == 0 and not self.needs_clarification

    @property
    def has_combat_action(self) -> bool:
        """Whether any action is combat-related."""
        return any(a.category == ActionCategory.COMBAT for a in self.actions)

    @property
    def has_movement_action(self) -> bool:
        """Whether any action is movement-related."""
        return any(a.category == ActionCategory.MOVEMENT for a in self.actions)

    def __str__(self) -> str:
        """Human-readable representation."""
        if self.needs_clarification:
            return f"[Needs clarification: {self.clarification_prompt}]"
        action_strs = [str(a) for a in self.actions]
        result = " + ".join(action_strs) if action_strs else "[No actions]"
        if self.ambient_flavor:
            result += f" [{self.ambient_flavor}]"
        return result
