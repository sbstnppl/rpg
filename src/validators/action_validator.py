"""Main action validator that dispatches to type-specific validators.

This module provides the central validation logic for the System-Authority
architecture. It validates all parsed actions before execution.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from src.parser.action_types import Action, ActionType, ActionCategory

if TYPE_CHECKING:
    from src.database.models.session import GameSession
    from src.database.models.entities import Entity


class RiskTag(str, Enum):
    """Tags indicating risk level for complication probability."""

    DANGEROUS = "dangerous"  # Location/entity is dangerous
    MYSTERIOUS = "mysterious"  # Unknown/magical element
    VALUABLE = "valuable"  # High-value item involved
    DARK = "dark"  # Low visibility
    HOSTILE = "hostile"  # Hostile entities present
    SACRED = "sacred"  # Religious/sacred space
    CURSED = "cursed"  # Known curse
    HIDDEN = "hidden"  # Secret/hidden element
    FIRST_TIME = "first_time"  # First interaction


@dataclass
class ValidationResult:
    """Result of validating a single action.

    Attributes:
        action: The action that was validated
        valid: Whether the action is mechanically possible
        reason: If invalid, why the action failed
        warnings: Non-blocking warnings (e.g., "entering darkness without light")
        risk_tags: Tags for complication probability calculation
        resolved_target: Resolved entity/item key if different from original
        resolved_indirect: Resolved indirect target if applicable
        metadata: Additional validation metadata for execution
    """

    action: Action
    valid: bool
    reason: str | None = None
    warnings: list[str] = field(default_factory=list)
    risk_tags: list[RiskTag] = field(default_factory=list)
    resolved_target: str | None = None
    resolved_indirect: str | None = None
    metadata: dict = field(default_factory=dict)

    def __str__(self) -> str:
        if self.valid:
            return f"[OK] {self.action}"
        return f"[FAIL] {self.action}: {self.reason}"


class ActionValidator:
    """Central validator for all action types.

    Dispatches validation to type-specific methods based on action category.
    Uses game managers to check mechanical constraints.

    Example:
        validator = ActionValidator(db, game_session)
        result = validator.validate(action, player)

        if result.valid:
            # Proceed with execution
        else:
            # Return error to player
    """

    def __init__(
        self,
        db: Session,
        game_session: "GameSession",
        combat_active: bool = False,
    ):
        """Initialize validator with database session.

        Args:
            db: SQLAlchemy database session.
            game_session: Current game session.
            combat_active: Whether combat is currently active.
        """
        self.db = db
        self.game_session = game_session
        self._combat_active = combat_active
        self._managers_cache: dict = {}

    @property
    def item_manager(self):
        """Lazy-load ItemManager."""
        if "item" not in self._managers_cache:
            from src.managers.item_manager import ItemManager

            self._managers_cache["item"] = ItemManager(self.db, self.game_session)
        return self._managers_cache["item"]

    @property
    def entity_manager(self):
        """Lazy-load EntityManager."""
        if "entity" not in self._managers_cache:
            from src.managers.entity_manager import EntityManager

            self._managers_cache["entity"] = EntityManager(self.db, self.game_session)
        return self._managers_cache["entity"]

    @property
    def location_manager(self):
        """Lazy-load LocationManager."""
        if "location" not in self._managers_cache:
            from src.managers.location_manager import LocationManager

            self._managers_cache["location"] = LocationManager(self.db, self.game_session)
        return self._managers_cache["location"]

    @property
    def combat_manager(self):
        """Lazy-load CombatManager."""
        if "combat" not in self._managers_cache:
            from src.managers.combat_manager import CombatManager

            self._managers_cache["combat"] = CombatManager(self.db, self.game_session)
        return self._managers_cache["combat"]

    @property
    def turn_manager(self):
        """Lazy-load TurnManager."""
        if "turn" not in self._managers_cache:
            from src.managers.turn_manager import TurnManager

            self._managers_cache["turn"] = TurnManager(self.db, self.game_session)
        return self._managers_cache["turn"]

    def _get_actor_location(self, actor: "Entity") -> str:
        """Get the actor's current location.

        Uses the stored actor_location if set (for players), otherwise
        tries to get it from the actor's NPCExtension.

        Args:
            actor: The entity to get location for.

        Returns:
            Location key string, or empty string if unknown.
        """
        if self._actor_location:
            return self._actor_location
        # Try NPCExtension for NPCs
        if hasattr(actor, "npc_extension") and actor.npc_extension:
            return actor.npc_extension.current_location or ""
        return ""

    def validate(
        self, action: Action, actor: "Entity", actor_location: str | None = None
    ) -> ValidationResult:
        """Validate a single action for an actor.

        Args:
            action: The action to validate.
            actor: The entity performing the action.
            actor_location: Override location for actor (for players without NPCExtension).

        Returns:
            ValidationResult indicating if action is valid.
        """
        # Store actor_location for use in validation methods
        self._actor_location = actor_location
        # Dispatch based on action type
        match action.type:
            # Item actions
            case ActionType.TAKE:
                return self._validate_take(action, actor)
            case ActionType.DROP:
                return self._validate_drop(action, actor)
            case ActionType.GIVE:
                return self._validate_give(action, actor)
            case ActionType.USE:
                return self._validate_use(action, actor)
            case ActionType.EQUIP:
                return self._validate_equip(action, actor)
            case ActionType.UNEQUIP:
                return self._validate_unequip(action, actor)
            case ActionType.EXAMINE:
                return self._validate_examine(action, actor)
            case ActionType.OPEN | ActionType.CLOSE:
                return self._validate_open_close(action, actor)

            # Movement actions
            case ActionType.MOVE | ActionType.ENTER | ActionType.EXIT:
                return self._validate_move(action, actor)

            # Combat actions
            case ActionType.ATTACK:
                return self._validate_attack(action, actor)
            case ActionType.DEFEND | ActionType.FLEE:
                return self._validate_combat_stance(action, actor)

            # Social actions
            case ActionType.TALK:
                return self._validate_talk(action, actor)
            case ActionType.ASK:
                return self._validate_ask(action, actor)
            case ActionType.TELL:
                return self._validate_tell(action, actor)
            case ActionType.TRADE:
                return self._validate_trade(action, actor)
            case ActionType.PERSUADE | ActionType.INTIMIDATE:
                return self._validate_social_skill(action, actor)

            # World actions
            case ActionType.SEARCH:
                return self._validate_search(action, actor)
            case ActionType.REST | ActionType.WAIT | ActionType.SLEEP:
                return self._validate_rest(action, actor)

            # Consumption
            case ActionType.EAT | ActionType.DRINK:
                return self._validate_consume(action, actor)

            # Skills
            case ActionType.CRAFT:
                return self._validate_craft(action, actor)
            case ActionType.LOCKPICK:
                return self._validate_lockpick(action, actor)
            case ActionType.SNEAK:
                return self._validate_sneak(action, actor)
            case ActionType.CLIMB | ActionType.SWIM:
                return self._validate_physical_skill(action, actor)

            # Meta actions - always valid
            case ActionType.LOOK | ActionType.INVENTORY | ActionType.STATUS:
                return ValidationResult(action=action, valid=True)

            # Custom actions need special handling
            case ActionType.CUSTOM:
                return self._validate_custom(action, actor)

            case _:
                return ValidationResult(
                    action=action,
                    valid=False,
                    reason=f"Unknown action type: {action.type}",
                )

    def validate_all(
        self, actions: list[Action], actor: "Entity"
    ) -> list[ValidationResult]:
        """Validate multiple actions.

        Args:
            actions: List of actions to validate.
            actor: The entity performing the actions.

        Returns:
            List of ValidationResults in same order as input.
        """
        return [self.validate(action, actor) for action in actions]

    # =========================================================================
    # Item Validators
    # =========================================================================

    def _validate_take(self, action: Action, actor: "Entity") -> ValidationResult:
        """Validate taking an item.

        Also checks for deferred items (decorative items mentioned in narrative
        but not yet spawned). If found, marks for on-demand spawning.
        """
        if not action.target:
            return ValidationResult(
                action=action, valid=False, reason="Take what? Specify an item."
            )

        # Find the item at current location
        location_key = self._get_actor_location(actor)
        items_here = self.item_manager.get_items_at_location(location_key)

        # Try to match the target
        target_lower = action.target.lower()
        matching_items = [
            item
            for item in items_here
            if target_lower in item.display_name.lower()
            or target_lower == item.item_key.lower()
        ]

        if not matching_items:
            # Check for deferred items (mentioned in narrative but not spawned)
            deferred = self._find_deferred_item(target_lower, location_key)
            if deferred:
                # For TAKE, verify the deferred item is at the current location
                item_location = deferred.get("location")
                if item_location and item_location != location_key:
                    return ValidationResult(
                        action=action,
                        valid=False,
                        reason=f"There's no '{action.target}' here to take.",
                    )
                # Valid - will be spawned on-demand during execution
                return ValidationResult(
                    action=action,
                    valid=True,
                    resolved_target=deferred["name"],
                    metadata={
                        "spawn_on_demand": True,
                        "deferred_item": deferred,
                    },
                )
            return ValidationResult(
                action=action,
                valid=False,
                reason=f"There's no '{action.target}' here to take.",
            )

        item = matching_items[0]
        risk_tags = self._assess_item_risk(item)

        # Check weight capacity
        item_weight = item.properties.get("weight", 1.0) if item.properties else 1.0
        if not self.item_manager.can_carry_weight(actor.id, item_weight):
            return ValidationResult(
                action=action,
                valid=False,
                reason=f"The {item.display_name} is too heavy. Drop something first.",
                risk_tags=risk_tags,
            )

        # Check available slots
        item_type = item.item_type.value if item.item_type else "misc"
        item_size = item.properties.get("size", "medium") if item.properties else "medium"
        available_slot = self.item_manager.find_available_slot(actor.id, item_type, item_size)

        if available_slot is None:
            return ValidationResult(
                action=action,
                valid=False,
                reason="Your hands and pockets are full. Drop or stow something first.",
                risk_tags=risk_tags,
            )

        return ValidationResult(
            action=action,
            valid=True,
            risk_tags=risk_tags,
            resolved_target=item.item_key,
            metadata={"item_id": item.id, "slot": available_slot},
        )

    def _validate_drop(self, action: Action, actor: "Entity") -> ValidationResult:
        """Validate dropping an item."""
        if not action.target:
            return ValidationResult(
                action=action, valid=False, reason="Drop what? Specify an item."
            )

        # Check if player has the item
        inventory = self.item_manager.get_inventory(actor.id)
        target_lower = action.target.lower()

        matching_items = [
            item
            for item in inventory
            if target_lower in item.display_name.lower()
            or target_lower == item.item_key.lower()
        ]

        if not matching_items:
            return ValidationResult(
                action=action,
                valid=False,
                reason=f"You don't have '{action.target}' to drop.",
            )

        item = matching_items[0]

        return ValidationResult(
            action=action,
            valid=True,
            resolved_target=item.item_key,
            metadata={"item_id": item.id},
        )

    def _validate_give(self, action: Action, actor: "Entity") -> ValidationResult:
        """Validate giving an item to someone."""
        if not action.target:
            return ValidationResult(
                action=action, valid=False, reason="Give what? Specify an item."
            )
        if not action.indirect_target:
            return ValidationResult(
                action=action, valid=False, reason="Give to whom? Specify a recipient."
            )

        # Check if player has the item
        inventory = self.item_manager.get_inventory(actor.id)
        target_lower = action.target.lower()

        matching_items = [
            item
            for item in inventory
            if target_lower in item.display_name.lower()
            or target_lower == item.item_key.lower()
        ]

        if not matching_items:
            return ValidationResult(
                action=action,
                valid=False,
                reason=f"You don't have '{action.target}' to give.",
            )

        item = matching_items[0]

        # Check if recipient exists and is here
        recipient = self._find_entity_at_location(
            action.indirect_target, self._get_actor_location(actor)
        )

        if not recipient:
            return ValidationResult(
                action=action,
                valid=False,
                reason=f"'{action.indirect_target}' is not here.",
            )

        return ValidationResult(
            action=action,
            valid=True,
            resolved_target=item.item_key,
            resolved_indirect=recipient.entity_key,
            metadata={"item_id": item.id, "recipient_id": recipient.id},
        )

    def _validate_use(self, action: Action, actor: "Entity") -> ValidationResult:
        """Validate using an item."""
        if not action.target:
            return ValidationResult(
                action=action, valid=False, reason="Use what? Specify an item."
            )

        # Check if player has the item
        inventory = self.item_manager.get_inventory(actor.id)
        target_lower = action.target.lower()

        matching_items = [
            item
            for item in inventory
            if target_lower in item.display_name.lower()
            or target_lower == item.item_key.lower()
        ]

        if not matching_items:
            return ValidationResult(
                action=action,
                valid=False,
                reason=f"You don't have '{action.target}' to use.",
            )

        item = matching_items[0]
        risk_tags = self._assess_item_risk(item)

        # If there's an indirect target, validate it exists
        resolved_indirect = None
        if action.indirect_target:
            # Could be an item or entity
            target = self._find_use_target(action.indirect_target, actor)
            if not target:
                return ValidationResult(
                    action=action,
                    valid=False,
                    reason=f"'{action.indirect_target}' is not here.",
                    risk_tags=risk_tags,
                )
            resolved_indirect = target

        return ValidationResult(
            action=action,
            valid=True,
            risk_tags=risk_tags,
            resolved_target=item.item_key,
            resolved_indirect=resolved_indirect,
            metadata={"item_id": item.id},
        )

    def _validate_equip(self, action: Action, actor: "Entity") -> ValidationResult:
        """Validate equipping an item."""
        if not action.target:
            return ValidationResult(
                action=action, valid=False, reason="Equip what? Specify an item."
            )

        inventory = self.item_manager.get_inventory(actor.id)
        target_lower = action.target.lower()

        matching_items = [
            item
            for item in inventory
            if target_lower in item.display_name.lower()
            or target_lower == item.item_key.lower()
        ]

        if not matching_items:
            return ValidationResult(
                action=action,
                valid=False,
                reason=f"You don't have '{action.target}' to equip.",
            )

        item = matching_items[0]

        # Check if item is equippable
        from src.database.models.enums import ItemType

        equippable_types = {ItemType.CLOTHING, ItemType.ACCESSORY, ItemType.WEAPON, ItemType.ARMOR}
        if item.item_type not in equippable_types:
            return ValidationResult(
                action=action,
                valid=False,
                reason=f"You can't equip {item.display_name}.",
            )

        return ValidationResult(
            action=action,
            valid=True,
            resolved_target=item.item_key,
            metadata={"item_id": item.id},
        )

    def _validate_unequip(self, action: Action, actor: "Entity") -> ValidationResult:
        """Validate unequipping an item."""
        if not action.target:
            return ValidationResult(
                action=action, valid=False, reason="Unequip what? Specify an item."
            )

        # Check equipped items (items with body_slot set)
        equipped_items = self.item_manager.get_equipped_items(actor.id)
        target_lower = action.target.lower()

        matching_items = [
            item
            for item in equipped_items
            if target_lower in item.display_name.lower()
            or target_lower == item.item_key.lower()
        ]

        if not matching_items:
            return ValidationResult(
                action=action,
                valid=False,
                reason=f"You're not wearing '{action.target}'.",
            )

        item = matching_items[0]

        return ValidationResult(
            action=action,
            valid=True,
            resolved_target=item.item_key,
            metadata={"item_id": item.id},
        )

    def _validate_examine(self, action: Action, actor: "Entity") -> ValidationResult:
        """Validate examining something."""
        if not action.target:
            return ValidationResult(
                action=action, valid=False, reason="Examine what?"
            )

        # Can examine items in inventory, in scene, or entities in scene
        risk_tags = []

        # Check inventory
        inventory = self.item_manager.get_inventory(actor.id)
        target_lower = action.target.lower()

        for item in inventory:
            if target_lower in item.display_name.lower() or target_lower == item.item_key.lower():
                return ValidationResult(
                    action=action,
                    valid=True,
                    resolved_target=item.item_key,
                    metadata={"type": "item", "item_id": item.id},
                )

        # Check items at location
        items_here = self.item_manager.get_items_at_location(self._get_actor_location(actor))
        for item in items_here:
            if target_lower in item.display_name.lower() or target_lower == item.item_key.lower():
                risk_tags = self._assess_item_risk(item)
                return ValidationResult(
                    action=action,
                    valid=True,
                    risk_tags=risk_tags,
                    resolved_target=item.item_key,
                    metadata={"type": "item", "item_id": item.id},
                )

        # Check entities at location
        entity = self._find_entity_at_location(action.target, self._get_actor_location(actor))
        if entity:
            return ValidationResult(
                action=action,
                valid=True,
                resolved_target=entity.entity_key,
                metadata={"type": "entity", "entity_id": entity.id},
            )

        # Check for deferred items (mentioned in narrative but not spawned)
        deferred = self._find_deferred_item(target_lower, self._get_actor_location(actor))
        if deferred:
            return ValidationResult(
                action=action,
                valid=True,
                resolved_target=deferred["name"],
                metadata={
                    "type": "deferred_item",
                    "deferred_item": deferred,
                },
            )

        return ValidationResult(
            action=action,
            valid=False,
            reason=f"You don't see '{action.target}' here.",
        )

    def _validate_open_close(self, action: Action, actor: "Entity") -> ValidationResult:
        """Validate opening or closing something."""
        if not action.target:
            verb = "open" if action.type == ActionType.OPEN else "close"
            return ValidationResult(
                action=action, valid=False, reason=f"{verb.capitalize()} what?"
            )

        # For now, always allow - executor will handle specifics
        return ValidationResult(
            action=action,
            valid=True,
            resolved_target=action.target,
        )

    # =========================================================================
    # Movement Validators
    # =========================================================================

    def _validate_move(self, action: Action, actor: "Entity") -> ValidationResult:
        """Validate movement to a location."""
        if not action.target and action.type != ActionType.EXIT:
            return ValidationResult(
                action=action, valid=False, reason="Go where? Specify a destination."
            )

        # Check if in combat
        if self._is_in_combat(actor):
            return ValidationResult(
                action=action,
                valid=False,
                reason="You can't leave while in combat. Flee first.",
                risk_tags=[RiskTag.HOSTILE],
            )

        risk_tags = []

        # If we have a target, try to validate the path
        if action.target:
            # Check if location exists (use fuzzy matching to resolve "well" -> "family_farm_well")
            location = self.location_manager.fuzzy_match_location(action.target)
            if location:
                # Check if there's a valid path
                # For now, allow if location exists
                # Location model doesn't have properties - skip this check for now
                # if location.properties and location.properties.get("dangerous"):
                #     risk_tags.append(RiskTag.DANGEROUS)
                return ValidationResult(
                    action=action,
                    valid=True,
                    risk_tags=risk_tags,
                    resolved_target=location.location_key,
                    metadata={"location_id": location.id},
                )

            # Location doesn't exist yet - GM will create it
            # This is valid for the new architecture
            return ValidationResult(
                action=action,
                valid=True,
                risk_tags=[RiskTag.FIRST_TIME],
                metadata={"new_location": True},
            )

        # EXIT without target
        return ValidationResult(
            action=action,
            valid=True,
        )

    # =========================================================================
    # Combat Validators
    # =========================================================================

    def _validate_attack(self, action: Action, actor: "Entity") -> ValidationResult:
        """Validate attacking a target."""
        if not action.target:
            return ValidationResult(
                action=action, valid=False, reason="Attack whom?"
            )

        # Find target at location
        target = self._find_entity_at_location(action.target, self._get_actor_location(actor))

        if not target:
            return ValidationResult(
                action=action,
                valid=False,
                reason=f"'{action.target}' is not here.",
            )

        # Can't attack yourself
        if target.id == actor.id:
            return ValidationResult(
                action=action,
                valid=False,
                reason="You can't attack yourself.",
            )

        # Check if target is alive
        if not target.is_alive:
            return ValidationResult(
                action=action,
                valid=False,
                reason=f"{target.display_name} is already dead.",
            )

        risk_tags = [RiskTag.DANGEROUS, RiskTag.HOSTILE]

        return ValidationResult(
            action=action,
            valid=True,
            risk_tags=risk_tags,
            resolved_target=target.entity_key,
            metadata={"target_id": target.id},
        )

    def _validate_combat_stance(self, action: Action, actor: "Entity") -> ValidationResult:
        """Validate defend or flee actions."""
        # These are always valid if in combat
        if not self._is_in_combat(actor):
            if action.type == ActionType.DEFEND:
                return ValidationResult(
                    action=action,
                    valid=False,
                    reason="You're not in combat.",
                )
            # Flee when not in combat is just moving away
            return ValidationResult(action=action, valid=True)

        return ValidationResult(
            action=action,
            valid=True,
            risk_tags=[RiskTag.HOSTILE],
        )

    # =========================================================================
    # Social Validators
    # =========================================================================

    def _validate_talk(self, action: Action, actor: "Entity") -> ValidationResult:
        """Validate talking to someone."""
        if not action.target:
            return ValidationResult(
                action=action, valid=False, reason="Talk to whom?"
            )

        target = self._find_entity_at_location(action.target, self._get_actor_location(actor))

        if not target:
            return ValidationResult(
                action=action,
                valid=False,
                reason=f"'{action.target}' is not here.",
            )

        if not target.is_alive:
            return ValidationResult(
                action=action,
                valid=False,
                reason=f"{target.display_name} can't talk anymore.",
            )

        return ValidationResult(
            action=action,
            valid=True,
            resolved_target=target.entity_key,
            metadata={"target_id": target.id},
        )

    def _validate_ask(self, action: Action, actor: "Entity") -> ValidationResult:
        """Validate asking someone about something.

        ASK requires both a target (who) and indirect_target (what about).
        """
        if not action.target:
            return ValidationResult(
                action=action, valid=False, reason="Ask whom?"
            )

        if not action.indirect_target:
            return ValidationResult(
                action=action,
                valid=False,
                reason=f"Ask {action.target} about what?",
            )

        target = self._find_entity_at_location(action.target, self._get_actor_location(actor))

        if not target:
            return ValidationResult(
                action=action,
                valid=False,
                reason=f"'{action.target}' is not here.",
            )

        if not target.is_alive:
            return ValidationResult(
                action=action,
                valid=False,
                reason=f"{target.display_name} can't answer anymore.",
            )

        return ValidationResult(
            action=action,
            valid=True,
            resolved_target=target.entity_key,
            resolved_indirect=action.indirect_target,
            metadata={"target_id": target.id, "topic": action.indirect_target},
        )

    def _validate_tell(self, action: Action, actor: "Entity") -> ValidationResult:
        """Validate telling someone something.

        TELL requires both a target (who) and indirect_target (what to tell).
        """
        if not action.target:
            return ValidationResult(
                action=action, valid=False, reason="Tell whom?"
            )

        if not action.indirect_target:
            return ValidationResult(
                action=action,
                valid=False,
                reason=f"Tell {action.target} what?",
            )

        target = self._find_entity_at_location(action.target, self._get_actor_location(actor))

        if not target:
            return ValidationResult(
                action=action,
                valid=False,
                reason=f"'{action.target}' is not here.",
            )

        if not target.is_alive:
            return ValidationResult(
                action=action,
                valid=False,
                reason=f"{target.display_name} can't hear you anymore.",
            )

        return ValidationResult(
            action=action,
            valid=True,
            resolved_target=target.entity_key,
            resolved_indirect=action.indirect_target,
            metadata={"target_id": target.id, "message": action.indirect_target},
        )

    def _validate_trade(self, action: Action, actor: "Entity") -> ValidationResult:
        """Validate trading with someone."""
        if not action.target:
            return ValidationResult(
                action=action, valid=False, reason="Trade with whom?"
            )

        target = self._find_entity_at_location(action.target, self._get_actor_location(actor))

        if not target:
            return ValidationResult(
                action=action,
                valid=False,
                reason=f"'{action.target}' is not here.",
            )

        return ValidationResult(
            action=action,
            valid=True,
            resolved_target=target.entity_key,
            metadata={"target_id": target.id},
        )

    def _validate_social_skill(self, action: Action, actor: "Entity") -> ValidationResult:
        """Validate persuade/intimidate actions."""
        if not action.target:
            verb = action.type.value
            return ValidationResult(
                action=action, valid=False, reason=f"{verb.capitalize()} whom?"
            )

        target = self._find_entity_at_location(action.target, self._get_actor_location(actor))

        if not target:
            return ValidationResult(
                action=action,
                valid=False,
                reason=f"'{action.target}' is not here.",
            )

        return ValidationResult(
            action=action,
            valid=True,
            resolved_target=target.entity_key,
            metadata={"target_id": target.id, "skill_check_required": True},
        )

    # =========================================================================
    # World Validators
    # =========================================================================

    def _validate_search(self, action: Action, actor: "Entity") -> ValidationResult:
        """Validate searching an area."""
        risk_tags = []

        # Check if location has hidden elements
        # Note: Location model doesn't have properties column yet
        location = self.location_manager.get_location(self._get_actor_location(actor) or "")
        if location and hasattr(location, 'properties') and location.properties:
            if location.properties.get("hidden_elements"):
                risk_tags.append(RiskTag.HIDDEN)
            if location.properties.get("dangerous"):
                risk_tags.append(RiskTag.DANGEROUS)

        return ValidationResult(
            action=action,
            valid=True,
            risk_tags=risk_tags,
            resolved_target=action.target,  # Optional specific area to search
            metadata={"skill_check_required": True},
        )

    def _validate_rest(self, action: Action, actor: "Entity") -> ValidationResult:
        """Validate resting/waiting/sleeping."""
        # Can't rest in combat
        if self._is_in_combat(actor):
            return ValidationResult(
                action=action,
                valid=False,
                reason="You can't rest while in combat.",
                risk_tags=[RiskTag.HOSTILE],
            )

        risk_tags = []

        # Check if location is safe
        # Note: Location model doesn't have properties column yet
        location = self.location_manager.get_location(self._get_actor_location(actor) or "")
        if location and hasattr(location, 'properties') and location.properties:
            if location.properties.get("dangerous"):
                risk_tags.append(RiskTag.DANGEROUS)

        return ValidationResult(
            action=action,
            valid=True,
            risk_tags=risk_tags,
        )

    # =========================================================================
    # Consumption Validators
    # =========================================================================

    def _validate_consume(self, action: Action, actor: "Entity") -> ValidationResult:
        """Validate eating/drinking something."""
        if not action.target:
            verb = "eat" if action.type == ActionType.EAT else "drink"
            return ValidationResult(
                action=action, valid=False, reason=f"{verb.capitalize()} what?"
            )

        # Check inventory for consumable
        inventory = self.item_manager.get_inventory(actor.id)
        target_lower = action.target.lower()

        matching_items = [
            item
            for item in inventory
            if target_lower in item.display_name.lower()
            or target_lower == item.item_key.lower()
        ]

        if not matching_items:
            return ValidationResult(
                action=action,
                valid=False,
                reason=f"You don't have '{action.target}'.",
            )

        item = matching_items[0]

        # Check if consumable
        from src.database.models.enums import ItemType

        if item.item_type != ItemType.CONSUMABLE:
            verb = "eat" if action.type == ActionType.EAT else "drink"
            return ValidationResult(
                action=action,
                valid=False,
                reason=f"You can't {verb} {item.display_name}.",
            )

        return ValidationResult(
            action=action,
            valid=True,
            resolved_target=item.item_key,
            metadata={"item_id": item.id},
        )

    # =========================================================================
    # Skill Validators
    # =========================================================================

    def _validate_craft(self, action: Action, actor: "Entity") -> ValidationResult:
        """Validate crafting something."""
        if not action.target:
            return ValidationResult(
                action=action, valid=False, reason="Craft what?"
            )

        return ValidationResult(
            action=action,
            valid=True,
            metadata={"skill_check_required": True},
        )

    def _validate_lockpick(self, action: Action, actor: "Entity") -> ValidationResult:
        """Validate lockpicking something."""
        if not action.target:
            return ValidationResult(
                action=action, valid=False, reason="Pick the lock on what?"
            )

        return ValidationResult(
            action=action,
            valid=True,
            risk_tags=[RiskTag.HIDDEN],
            metadata={"skill_check_required": True},
        )

    def _validate_sneak(self, action: Action, actor: "Entity") -> ValidationResult:
        """Validate sneaking."""
        return ValidationResult(
            action=action,
            valid=True,
            metadata={"skill_check_required": True},
        )

    def _validate_physical_skill(self, action: Action, actor: "Entity") -> ValidationResult:
        """Validate climbing/swimming."""
        return ValidationResult(
            action=action,
            valid=True,
            risk_tags=[RiskTag.DANGEROUS],
            metadata={"skill_check_required": True},
        )

    def _validate_custom(self, action: Action, actor: "Entity") -> ValidationResult:
        """Validate custom/freeform action."""
        # Custom actions are passed through to narrator for creative handling
        return ValidationResult(
            action=action,
            valid=True,
            risk_tags=[RiskTag.FIRST_TIME],  # Unknown action = potential complication
            metadata={"custom": True},
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _find_entity_at_location(
        self, name: str, location_key: str | None
    ) -> "Entity | None":
        """Find an entity by name at a location."""
        if not location_key:
            return None

        from src.database.models.entities import Entity, NPCExtension
        from src.database.models.enums import EntityType

        # Query entities via NPCExtension to filter by location
        entities = (
            self.db.query(Entity)
            .join(NPCExtension, Entity.id == NPCExtension.entity_id)
            .filter(
                Entity.session_id == self.game_session.id,
                NPCExtension.current_location == location_key,
                Entity.entity_type.in_([EntityType.NPC, EntityType.MONSTER, EntityType.ANIMAL]),
            )
            .all()
        )

        name_lower = name.lower()
        for entity in entities:
            if (
                name_lower in entity.display_name.lower()
                or name_lower == entity.entity_key.lower()
            ):
                return entity

        return None

    def _find_use_target(
        self, name: str, actor: "Entity"
    ) -> str | None:
        """Find a target for 'use X on Y'."""
        name_lower = name.lower()

        # Check items at location
        items_here = self.item_manager.get_items_at_location(self._get_actor_location(actor))
        for item in items_here:
            if name_lower in item.display_name.lower() or name_lower == item.item_key.lower():
                return item.item_key

        # Check entities at location
        entity = self._find_entity_at_location(name, self._get_actor_location(actor))
        if entity:
            return entity.entity_key

        return None

    def _is_in_combat(self, actor: "Entity") -> bool:
        """Check if actor is in active combat.

        Args:
            actor: The entity to check.

        Returns:
            True if combat is active for this session.
        """
        return self._combat_active

    def _assess_item_risk(self, item) -> list[RiskTag]:
        """Assess risk tags for an item."""
        risk_tags = []

        if item.properties:
            if item.properties.get("magical"):
                risk_tags.append(RiskTag.MYSTERIOUS)
            if item.properties.get("cursed"):
                risk_tags.append(RiskTag.CURSED)
            if item.properties.get("valuable"):
                risk_tags.append(RiskTag.VALUABLE)
            if item.properties.get("sacred"):
                risk_tags.append(RiskTag.SACRED)

        return risk_tags

    def _find_deferred_item(
        self, target_lower: str, location_key: str
    ) -> dict | None:
        """Find a deferred item mentioned in recent narrative.

        Deferred items are decorative items mentioned in narrative
        but not yet spawned. They can be spawned on-demand when
        the player references them.

        First checks items at the current location, then falls back to
        checking ALL deferred items (for INFO responses that mention
        items at other locations, like "the bucket at the well").

        Args:
            target_lower: Lowercase item name to search for.
            location_key: Current location to filter by.

        Returns:
            Deferred item dict if found, None otherwise.
        """
        # First try location-specific lookup
        if location_key:
            mentioned_items = self.turn_manager.get_mentioned_items_at_location(
                location_key, lookback_turns=10
            )

            for item in mentioned_items:
                item_name_lower = item.get("name", "").lower()
                if target_lower in item_name_lower or item_name_lower in target_lower:
                    return item

        # Fallback: check ALL deferred items regardless of location
        # This handles INFO responses that mention items at other locations
        # (e.g., "you wash at the well with a bucket" while player is in kitchen)
        all_items = self.turn_manager.get_all_mentioned_items(lookback_turns=10)

        for item in all_items:
            item_name_lower = item.get("name", "").lower()
            if target_lower in item_name_lower or item_name_lower in target_lower:
                return item

        return None
