"""Action executor for the System-Authority architecture.

Executes validated actions and produces structured results for narration.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from src.parser.action_types import Action, ActionType
from src.validators.action_validator import ValidationResult

if TYPE_CHECKING:
    from src.database.models.session import GameSession
    from src.database.models.entities import Entity


@dataclass
class ExecutionResult:
    """Result of executing a single action.

    Attributes:
        action: The action that was executed
        success: Whether execution succeeded
        outcome: Brief factual description for narration
        state_changes: List of state changes made
        metadata: Additional execution data
    """

    action: Action
    success: bool
    outcome: str
    state_changes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        status = "OK" if self.success else "FAIL"
        return f"[{status}] {self.outcome}"


@dataclass
class TurnResult:
    """Combined result of all actions in a turn.

    Attributes:
        executions: Results of all executed actions
        failed_validations: Actions that failed validation
        new_facts: New facts to persist (from executions)
    """

    executions: list[ExecutionResult] = field(default_factory=list)
    failed_validations: list[ValidationResult] = field(default_factory=list)
    new_facts: list[str] = field(default_factory=list)

    @property
    def all_successful(self) -> bool:
        """Whether all actions executed successfully."""
        return all(e.success for e in self.executions)

    @property
    def has_failures(self) -> bool:
        """Whether any actions failed (validation or execution)."""
        return bool(self.failed_validations) or any(not e.success for e in self.executions)


class ActionExecutor:
    """Executes validated actions and produces results.

    The executor takes validated actions and performs the actual
    game state changes, returning structured results for narration.

    Example:
        executor = ActionExecutor(db, game_session)
        result = await executor.execute_turn(
            valid_actions=[validation_result],
            failed_actions=[failed_validation],
            actor=player_entity
        )
    """

    def __init__(self, db: Session, game_session: "GameSession"):
        """Initialize executor.

        Args:
            db: SQLAlchemy database session.
            game_session: Current game session.
        """
        self.db = db
        self.game_session = game_session
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
    def time_manager(self):
        """Lazy-load TimeManager."""
        if "time" not in self._managers_cache:
            from src.managers.time_manager import TimeManager

            self._managers_cache["time"] = TimeManager(self.db, self.game_session)
        return self._managers_cache["time"]

    @property
    def needs_manager(self):
        """Lazy-load NeedsManager."""
        if "needs" not in self._managers_cache:
            from src.managers.needs import NeedsManager

            self._managers_cache["needs"] = NeedsManager(self.db, self.game_session)
        return self._managers_cache["needs"]

    @property
    def death_manager(self):
        """Lazy-load DeathManager."""
        if "death" not in self._managers_cache:
            from src.managers.death import DeathManager

            self._managers_cache["death"] = DeathManager(self.db, self.game_session)
        return self._managers_cache["death"]

    @property
    def relationship_manager(self):
        """Lazy-load RelationshipManager."""
        if "relationship" not in self._managers_cache:
            from src.managers.relationship_manager import RelationshipManager

            self._managers_cache["relationship"] = RelationshipManager(
                self.db, self.game_session
            )
        return self._managers_cache["relationship"]

    def _get_actor_location(self, actor: "Entity") -> str:
        """Get the actor's current location.

        Uses the stored actor_location if set (for players), otherwise
        tries to get it from the actor's NPCExtension.

        Args:
            actor: The entity to get location for.

        Returns:
            Location key string, or empty string if unknown.
        """
        if hasattr(self, "_actor_location") and self._actor_location:
            return self._actor_location
        # Try NPCExtension for NPCs
        if hasattr(actor, "npc_extension") and actor.npc_extension:
            return actor.npc_extension.current_location or ""
        return ""

    async def execute_turn(
        self,
        valid_actions: list[ValidationResult],
        failed_actions: list[ValidationResult],
        actor: "Entity",
        actor_location: str | None = None,
        dynamic_plans: dict[str, Any] | None = None,
    ) -> TurnResult:
        """Execute all valid actions for a turn.

        Args:
            valid_actions: List of validated actions to execute.
            failed_actions: List of actions that failed validation.
            actor: The entity performing the actions.
            actor_location: Override location for actor (for players without NPCExtension).
            dynamic_plans: Plans for CUSTOM actions from dynamic_planner_node.

        Returns:
            TurnResult with all execution results.
        """
        # Store actor_location for use in execution methods
        self._actor_location = actor_location
        # Store dynamic plans for CUSTOM action execution
        self._dynamic_plans = dynamic_plans or {}

        result = TurnResult(failed_validations=failed_actions)

        for validation in valid_actions:
            execution = await self._execute_action(validation, actor)
            result.executions.append(execution)

            # Collect new facts
            if execution.metadata.get("new_facts"):
                result.new_facts.extend(execution.metadata["new_facts"])

        # Commit all changes
        self.db.commit()

        return result

    async def _execute_action(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute a single validated action.

        Args:
            validation: The validation result containing the action.
            actor: Entity performing the action.

        Returns:
            ExecutionResult with outcome.
        """
        action = validation.action

        # Handle deferred item spawning (items mentioned in narrative but not yet real)
        # This spawns the item BEFORE execution so the action handler can find it
        if validation.metadata.get("spawn_on_demand"):
            spawned = self._spawn_deferred_item(validation, actor)
            if spawned:
                # Update metadata with the spawned item info
                validation.metadata["item_id"] = spawned.get("item_id")
                validation.metadata["spawned_on_demand"] = True

        # Dispatch based on action type
        match action.type:
            # Item actions
            case ActionType.TAKE:
                return await self._execute_take(validation, actor)
            case ActionType.DROP:
                return await self._execute_drop(validation, actor)
            case ActionType.GIVE:
                return await self._execute_give(validation, actor)
            case ActionType.USE:
                return await self._execute_use(validation, actor)
            case ActionType.EQUIP:
                return await self._execute_equip(validation, actor)
            case ActionType.UNEQUIP:
                return await self._execute_unequip(validation, actor)
            case ActionType.EXAMINE:
                return await self._execute_examine(validation, actor)
            case ActionType.OPEN | ActionType.CLOSE:
                return await self._execute_open_close(validation, actor)

            # Movement actions
            case ActionType.MOVE | ActionType.ENTER | ActionType.EXIT:
                return await self._execute_move(validation, actor)

            # Combat actions
            case ActionType.ATTACK:
                return await self._execute_attack(validation, actor)
            case ActionType.DEFEND:
                return await self._execute_defend(validation, actor)
            case ActionType.FLEE:
                return await self._execute_flee(validation, actor)

            # Social actions
            case ActionType.TALK | ActionType.ASK | ActionType.TELL:
                return await self._execute_talk(validation, actor)
            case ActionType.TRADE:
                return await self._execute_trade(validation, actor)
            case ActionType.PERSUADE | ActionType.INTIMIDATE:
                return await self._execute_social_skill(validation, actor)

            # World actions
            case ActionType.SEARCH:
                return await self._execute_search(validation, actor)
            case ActionType.REST:
                return await self._execute_rest(validation, actor)
            case ActionType.WAIT:
                return await self._execute_wait(validation, actor)
            case ActionType.SLEEP:
                return await self._execute_sleep(validation, actor)

            # Consumption
            case ActionType.EAT | ActionType.DRINK:
                return await self._execute_consume(validation, actor)

            # Skills
            case ActionType.CRAFT:
                return await self._execute_craft(validation, actor)
            case ActionType.LOCKPICK:
                return await self._execute_lockpick(validation, actor)
            case ActionType.SNEAK:
                return await self._execute_sneak(validation, actor)
            case ActionType.CLIMB | ActionType.SWIM:
                return await self._execute_physical_skill(validation, actor)

            # Meta actions
            case ActionType.LOOK:
                return await self._execute_look(validation, actor)
            case ActionType.INVENTORY:
                return await self._execute_inventory(validation, actor)
            case ActionType.STATUS:
                return await self._execute_status(validation, actor)

            # Custom actions
            case ActionType.CUSTOM:
                return await self._execute_custom(validation, actor)

            case _:
                return ExecutionResult(
                    action=action,
                    success=False,
                    outcome=f"Unknown action type: {action.type}",
                )

    # =========================================================================
    # Deferred Item Spawning
    # =========================================================================

    def _spawn_deferred_item(
        self, validation: ValidationResult, actor: "Entity"
    ) -> dict[str, Any] | None:
        """Spawn a deferred item that was mentioned in narrative but not yet real.

        Deferred items are decorative/environmental items mentioned in previous
        narrative but not spawned until the player actually references them.
        This enables consistent world-building while avoiding item bloat.

        Args:
            validation: ValidationResult with deferred_item in metadata.
            actor: Entity performing the action (for location context).

        Returns:
            Dict with spawned item info (item_key, item_id, display_name) or None.
        """
        from src.narrator.hallucination_handler import spawn_hallucinated_items

        deferred = validation.metadata.get("deferred_item")
        if not deferred:
            return None

        item_name = deferred.get("name", validation.resolved_target)
        # Use the item's stored location, falling back to actor location
        location_key = deferred.get("location") or self._get_actor_location(actor)
        context = deferred.get("context", "")

        # Spawn the item
        spawned_items = spawn_hallucinated_items(
            db=self.db,
            game_session=self.game_session,
            items=[item_name],
            location_key=location_key,
            context=context,
        )

        if spawned_items:
            spawned = spawned_items[0]
            # Flush to ensure item is visible to subsequent queries
            self.db.flush()
            return {
                "item_key": spawned.get("item_key"),
                "item_id": spawned.get("item_id"),
                "display_name": spawned.get("display_name"),
            }

        return None

    # =========================================================================
    # Item Execution
    # =========================================================================

    async def _execute_take(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute taking an item."""
        action = validation.action
        item_key = validation.resolved_target
        item_id = validation.metadata.get("item_id")

        # Get item using manager
        item = None
        if item_key:
            item = self.item_manager.get_item(item_key)
        elif item_id:
            item = self.item_manager.get_item_by_id(item_id)

        if not item:
            return ExecutionResult(
                action=action,
                success=False,
                outcome=f"Item not found: {action.target}",
            )

        # Transfer item to actor using manager
        try:
            self.item_manager.transfer_item(item.item_key, to_entity_id=actor.id)
        except ValueError as e:
            return ExecutionResult(
                action=action,
                success=False,
                outcome=str(e),
            )

        return ExecutionResult(
            action=action,
            success=True,
            outcome=f"Picked up {item.display_name}",
            state_changes=[f"Added {item.item_key} to inventory"],
            metadata={"item_key": item.item_key, "item_name": item.display_name},
        )

    async def _execute_drop(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute dropping an item."""
        action = validation.action
        item_key = validation.resolved_target
        item_id = validation.metadata.get("item_id")

        # Get item using manager
        item = None
        if item_key:
            item = self.item_manager.get_item(item_key)
        elif item_id:
            item = self.item_manager.get_item_by_id(item_id)

        if not item:
            return ExecutionResult(
                action=action,
                success=False,
                outcome=f"Item not found: {action.target}",
            )

        location = self._get_actor_location(actor) or "unknown"

        # Drop item at current location using manager
        try:
            self.item_manager.drop_item(item.item_key, location)
        except ValueError as e:
            return ExecutionResult(
                action=action,
                success=False,
                outcome=str(e),
            )

        return ExecutionResult(
            action=action,
            success=True,
            outcome=f"Dropped {item.display_name}",
            state_changes=[f"Removed {item.item_key} from inventory"],
            metadata={"item_key": item.item_key, "item_name": item.display_name},
        )

    async def _execute_give(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute giving an item to someone."""
        action = validation.action
        item_key = validation.resolved_target
        item_id = validation.metadata.get("item_id")
        recipient_id = validation.metadata.get("recipient_id")
        recipient_key = validation.resolved_indirect

        # Get item using manager
        item = None
        if item_key:
            item = self.item_manager.get_item(item_key)
        elif item_id:
            item = self.item_manager.get_item_by_id(item_id)

        if not item:
            return ExecutionResult(
                action=action,
                success=False,
                outcome="Item not found",
            )

        # Get recipient using manager
        recipient = None
        if recipient_key:
            recipient = self.entity_manager.get_entity(recipient_key)
        elif recipient_id:
            recipient = self.entity_manager.get_entity_by_id(recipient_id)

        if not recipient:
            return ExecutionResult(
                action=action,
                success=False,
                outcome="Recipient not found",
            )

        # Transfer item to recipient
        try:
            self.item_manager.transfer_item(item.item_key, to_entity_id=recipient.id)
        except ValueError as e:
            return ExecutionResult(
                action=action,
                success=False,
                outcome=str(e),
            )

        return ExecutionResult(
            action=action,
            success=True,
            outcome=f"Gave {item.display_name} to {recipient.display_name}",
            state_changes=[
                f"Transferred {item.item_key} to {recipient.entity_key}"
            ],
            metadata={
                "item_key": item.item_key,
                "item_name": item.display_name,
                "recipient_key": recipient.entity_key,
                "recipient_name": recipient.display_name,
            },
        )

    async def _execute_use(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute using an item."""
        action = validation.action
        item_key = validation.resolved_target
        item_id = validation.metadata.get("item_id")

        # Get item using manager
        item = None
        if item_key:
            item = self.item_manager.get_item(item_key)
        elif item_id:
            item = self.item_manager.get_item_by_id(item_id)

        item_name = item.display_name if item else action.target

        target_desc = ""
        if validation.resolved_indirect:
            target_desc = f" on {validation.resolved_indirect}"

        return ExecutionResult(
            action=action,
            success=True,
            outcome=f"Used {item_name}{target_desc}",
            metadata={
                "item_key": item.item_key if item else None,
                "item_name": item_name,
                "use_target": validation.resolved_indirect,
            },
        )

    async def _execute_equip(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute equipping an item."""
        action = validation.action
        item_key = validation.resolved_target
        item_id = validation.metadata.get("item_id")
        body_slot = validation.metadata.get("body_slot", "right_hand")

        # Get item using manager
        item = None
        if item_key:
            item = self.item_manager.get_item(item_key)
        elif item_id:
            item = self.item_manager.get_item_by_id(item_id)

        if not item:
            return ExecutionResult(
                action=action,
                success=False,
                outcome=f"Item not found: {action.target}",
            )

        # Equip item to body slot using manager
        try:
            self.item_manager.equip_item(item.item_key, actor.id, body_slot)
        except ValueError as e:
            return ExecutionResult(
                action=action,
                success=False,
                outcome=str(e),
            )

        return ExecutionResult(
            action=action,
            success=True,
            outcome=f"Equipped {item.display_name}",
            state_changes=[f"Equipped {item.item_key} to {body_slot}"],
            metadata={
                "item_key": item.item_key,
                "item_name": item.display_name,
                "body_slot": body_slot,
            },
        )

    async def _execute_unequip(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute unequipping an item."""
        action = validation.action
        item_key = validation.resolved_target
        item_id = validation.metadata.get("item_id")

        # Get item using manager
        item = None
        if item_key:
            item = self.item_manager.get_item(item_key)
        elif item_id:
            item = self.item_manager.get_item_by_id(item_id)

        if not item:
            return ExecutionResult(
                action=action,
                success=False,
                outcome=f"Item not found: {action.target}",
            )

        old_slot = item.body_slot

        # Unequip item using manager
        try:
            self.item_manager.unequip_item(item.item_key)
        except ValueError as e:
            return ExecutionResult(
                action=action,
                success=False,
                outcome=str(e),
            )

        return ExecutionResult(
            action=action,
            success=True,
            outcome=f"Removed {item.display_name}",
            state_changes=[f"Unequipped {item.item_key} from {old_slot}"],
            metadata={
                "item_key": item.item_key,
                "item_name": item.display_name,
                "old_slot": old_slot,
            },
        )

    async def _execute_examine(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute examining something."""
        action = validation.action
        examine_type = validation.metadata.get("type", "unknown")
        target_key = validation.resolved_target

        if examine_type == "item":
            item_id = validation.metadata.get("item_id")
            item = None
            if target_key:
                item = self.item_manager.get_item(target_key)
            elif item_id:
                item = self.item_manager.get_item_by_id(item_id)

            if item:
                description = item.description or f"A {item.display_name}."
                return ExecutionResult(
                    action=action,
                    success=True,
                    outcome=f"Examined {item.display_name}: {description}",
                    metadata={
                        "target_type": "item",
                        "target_key": item.item_key,
                        "target_name": item.display_name,
                        "description": description,
                    },
                )

        elif examine_type == "entity":
            entity_id = validation.metadata.get("entity_id")
            entity = None
            if target_key:
                entity = self.entity_manager.get_entity(target_key)
            elif entity_id:
                entity = self.entity_manager.get_entity_by_id(entity_id)

            if entity:
                description = entity.description or f"{entity.display_name}."
                return ExecutionResult(
                    action=action,
                    success=True,
                    outcome=f"Examined {entity.display_name}: {description}",
                    metadata={
                        "target_type": "entity",
                        "target_key": entity.entity_key,
                        "target_name": entity.display_name,
                        "description": description,
                    },
                )

        return ExecutionResult(
            action=action,
            success=True,
            outcome=f"Examined {validation.resolved_target or action.target}",
            metadata={"target": validation.resolved_target or action.target},
        )

    async def _execute_open_close(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute opening or closing something."""
        action = validation.action
        verb = "opened" if action.type == ActionType.OPEN else "closed"
        target = validation.resolved_target or action.target

        return ExecutionResult(
            action=action,
            success=True,
            outcome=f"{verb.capitalize()} {target}",
            metadata={"target": target, "action": verb},
        )

    # =========================================================================
    # Movement Execution
    # =========================================================================

    async def _execute_move(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute moving to a location."""
        action = validation.action
        destination = validation.resolved_target or action.target
        is_new = validation.metadata.get("new_location", False)

        old_location = self._get_actor_location(actor)
        # Update stored location (for players, this is tracked in state)
        self._actor_location = destination

        outcome_parts = [f"Moved to {destination}"]
        if is_new:
            outcome_parts.append("(new location)")

        return ExecutionResult(
            action=action,
            success=True,
            outcome=" ".join(outcome_parts),
            state_changes=[f"Location: {old_location} -> {destination}"],
            metadata={
                "from_location": old_location,
                "to_location": destination,
                "is_new_location": is_new,
            },
        )

    # =========================================================================
    # Combat Execution
    # =========================================================================

    async def _execute_attack(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute an attack."""
        action = validation.action
        target_key = validation.resolved_target
        target_id = validation.metadata.get("target_id")

        # Get target using manager
        target = None
        if target_key:
            target = self.entity_manager.get_entity(target_key)
        elif target_id:
            target = self.entity_manager.get_entity_by_id(target_id)

        if not target:
            return ExecutionResult(
                action=action,
                success=False,
                outcome="Target not found",
            )

        # Execute attack roll
        from src.dice.combat import make_attack_roll, roll_damage

        # Get actor's attack bonus from STR attribute
        attack_bonus = 0
        str_attr = self.entity_manager.get_attribute(actor.id, "strength")
        if str_attr:
            attack_bonus = (str_attr.value - 10) // 2

        # Get target AC (base 10 + DEX modifier)
        target_ac = 10
        dex_attr = self.entity_manager.get_attribute(target.id, "dexterity")
        if dex_attr:
            target_ac = 10 + (dex_attr.value - 10) // 2

        attack_result = make_attack_roll(
            target_ac=target_ac,
            attack_bonus=attack_bonus,
        )

        state_changes = [f"Attack against {target.entity_key}"]
        vital_status = None
        new_hp = None

        if attack_result.hit:
            damage_result = roll_damage(
                damage_dice="1d6",  # TODO: Get from weapon
                bonus=attack_bonus,
                is_critical=attack_result.is_critical_hit,
            )
            damage = damage_result.roll_result.total

            outcome = f"Hit {target.display_name} for {damage} damage"
            if attack_result.is_critical_hit:
                outcome = f"Critical hit! " + outcome

            # Apply damage via DeathManager
            current_hp = self.entity_manager.get_attribute(target.id, "current_hp")
            max_hp = self.entity_manager.get_attribute(target.id, "max_hp")

            if current_hp is not None and max_hp is not None:
                vital_status, new_hp, injury = self.death_manager.take_damage(
                    entity_id=target.id,
                    damage=damage,
                    current_hp=current_hp,
                    max_hp=max_hp,
                    damage_type="physical",
                    create_injury=False,  # Simple combat doesn't create injuries
                )

                # Update HP attribute
                self.entity_manager.set_attribute(target.id, "current_hp", new_hp)
                state_changes.append(f"HP: {current_hp} -> {new_hp}")

                if vital_status:
                    outcome += f" ({vital_status.value})"
                    if vital_status.value == "dead":
                        outcome = f"{target.display_name} has been slain!"
        else:
            damage = 0
            outcome = f"Missed {target.display_name}"
            if attack_result.is_critical_miss:
                outcome = "Critical miss! Attack went wide"

        return ExecutionResult(
            action=action,
            success=True,  # Execution succeeded even if attack missed
            outcome=outcome,
            state_changes=state_changes,
            metadata={
                "target_key": target.entity_key,
                "target_name": target.display_name,
                "hit": attack_result.hit,
                "damage": damage,
                "is_critical_hit": attack_result.is_critical_hit,
                "is_critical_miss": attack_result.is_critical_miss,
                "roll": attack_result.roll_result.total,
                "vital_status": vital_status.value if vital_status else None,
                "new_hp": new_hp,
            },
        )

    async def _execute_defend(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute taking a defensive stance."""
        action = validation.action

        return ExecutionResult(
            action=action,
            success=True,
            outcome="Took a defensive stance",
            state_changes=["Defending"],
            metadata={"stance": "defensive"},
        )

    async def _execute_flee(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute fleeing from combat."""
        action = validation.action

        # TODO: Roll flee check
        return ExecutionResult(
            action=action,
            success=True,
            outcome="Fled from combat",
            state_changes=["Left combat"],
            metadata={"fled": True},
        )

    # =========================================================================
    # Social Execution
    # =========================================================================

    async def _execute_talk(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute talking to someone."""
        action = validation.action
        target_key = validation.resolved_target
        target_id = validation.metadata.get("target_id")

        # Get target using manager
        target = None
        if target_key:
            target = self.entity_manager.get_entity(target_key)
        elif target_id:
            target = self.entity_manager.get_entity_by_id(target_id)

        target_name = target.display_name if target else validation.resolved_target

        verb = action.type.value  # talk, ask, or tell
        outcome = f"Started {verb}ing to {target_name}"

        if action.type == ActionType.ASK and action.indirect_target:
            outcome = f"Asked {target_name} about {action.indirect_target}"
        elif action.type == ActionType.TELL and action.indirect_target:
            outcome = f"Told {target_name} about {action.indirect_target}"

        return ExecutionResult(
            action=action,
            success=True,
            outcome=outcome,
            metadata={
                "target_key": target.entity_key if target else None,
                "target_name": target_name,
                "topic": action.indirect_target,
            },
        )

    async def _execute_trade(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute initiating trade."""
        action = validation.action
        target_key = validation.resolved_target
        target_id = validation.metadata.get("target_id")

        # Get target using manager
        target = None
        if target_key:
            target = self.entity_manager.get_entity(target_key)
        elif target_id:
            target = self.entity_manager.get_entity_by_id(target_id)

        target_name = target.display_name if target else validation.resolved_target

        return ExecutionResult(
            action=action,
            success=True,
            outcome=f"Initiated trade with {target_name}",
            metadata={
                "target_key": target.entity_key if target else None,
                "target_name": target_name,
            },
        )

    async def _execute_social_skill(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute persuade/intimidate."""
        from src.dice.checks import make_skill_check

        action = validation.action
        target_key = validation.resolved_target
        target_id = validation.metadata.get("target_id")

        # Get target using manager
        target = None
        if target_key:
            target = self.entity_manager.get_entity(target_key)
        elif target_id:
            target = self.entity_manager.get_entity_by_id(target_id)

        target_name = target.display_name if target else validation.resolved_target

        is_persuade = action.type == ActionType.PERSUADE
        skill_name = "persuasion" if is_persuade else "intimidation"
        verb = "persuade" if is_persuade else "intimidate"

        # Get actor's charisma modifier for skill check
        cha_modifier = 0
        cha_attr = self.entity_manager.get_attribute(actor.id, "charisma")
        if cha_attr:
            cha_modifier = (cha_attr - 10) // 2

        # Roll skill check (DC based on target's willpower/wisdom)
        dc = 12  # Base DC
        if target:
            wis_attr = self.entity_manager.get_attribute(target.id, "wisdom")
            if wis_attr:
                dc = 10 + (wis_attr - 10) // 2

        skill_result = make_skill_check(
            dc=dc,
            attribute_modifier=cha_modifier,
        )

        state_changes = []

        if skill_result.success and target:
            # Update relationship based on skill type
            if is_persuade:
                # Successful persuasion increases liking
                self.relationship_manager.update_attitude(
                    from_id=target.id,
                    to_id=actor.id,
                    dimension="liking",
                    delta=5,
                    reason=f"Persuaded by {actor.display_name}",
                )
                outcome = f"Successfully persuaded {target_name}"
                state_changes.append(f"liking +5")
            else:
                # Successful intimidation increases fear
                self.relationship_manager.update_attitude(
                    from_id=target.id,
                    to_id=actor.id,
                    dimension="fear",
                    delta=10,
                    reason=f"Intimidated by {actor.display_name}",
                )
                # But decreases liking
                self.relationship_manager.update_attitude(
                    from_id=target.id,
                    to_id=actor.id,
                    dimension="liking",
                    delta=-5,
                    reason=f"Intimidated by {actor.display_name}",
                )
                outcome = f"Successfully intimidated {target_name}"
                state_changes.append(f"fear +10, liking -5")
        else:
            outcome = f"Failed to {verb} {target_name}"
            if target and not is_persuade:
                # Failed intimidation can reduce respect
                self.relationship_manager.update_attitude(
                    from_id=target.id,
                    to_id=actor.id,
                    dimension="respect",
                    delta=-5,
                    reason=f"Failed intimidation attempt by {actor.display_name}",
                )
                state_changes.append(f"respect -5")

        roll_total = skill_result.roll_result.total if skill_result.roll_result else None

        return ExecutionResult(
            action=action,
            success=skill_result.success,
            outcome=outcome,
            state_changes=state_changes,
            metadata={
                "target_key": target.entity_key if target else None,
                "target_name": target_name,
                "skill": skill_name,
                "roll_total": roll_total,
                "dc": dc,
                "margin": skill_result.margin,
                "success": skill_result.success,
                "outcome_tier": skill_result.outcome_tier.value if skill_result.outcome_tier else None,
            },
        )

    # =========================================================================
    # World Execution
    # =========================================================================

    async def _execute_search(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute searching an area."""
        action = validation.action
        target = validation.resolved_target or "the area"

        # TODO: Roll perception check
        return ExecutionResult(
            action=action,
            success=True,
            outcome=f"Searched {target}",
            metadata={
                "target": target,
                "skill_check_required": True,
            },
        )

    async def _execute_rest(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute resting."""
        action = validation.action
        rest_minutes = 30  # Short rest is 30 minutes

        # Advance time
        time_state = self.time_manager.advance_time(rest_minutes)

        return ExecutionResult(
            action=action,
            success=True,
            outcome=f"Rested for {rest_minutes} minutes",
            state_changes=[
                f"Time advanced: {rest_minutes} minutes",
                f"Current time: {time_state.current_time}",
            ],
            metadata={
                "rest_type": "short",
                "minutes": rest_minutes,
                "new_time": time_state.current_time,
            },
        )

    async def _execute_wait(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute waiting."""
        action = validation.action
        minutes = int(action.target) if action.target and action.target.isdigit() else 10

        # Advance time
        time_state = self.time_manager.advance_time(minutes)

        return ExecutionResult(
            action=action,
            success=True,
            outcome=f"Waited for {minutes} minutes",
            state_changes=[
                f"Time advanced: {minutes} minutes",
                f"Current time: {time_state.current_time}",
            ],
            metadata={
                "minutes": minutes,
                "new_time": time_state.current_time,
            },
        )

    async def _execute_sleep(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute sleeping."""
        action = validation.action
        sleep_hours = 8  # Default sleep is 8 hours

        # Advance time (convert hours to minutes)
        time_state = self.time_manager.advance_time(sleep_hours * 60)

        state_changes = [
            f"Time advanced: {sleep_hours} hours",
            f"Current time: {time_state.current_time}",
            f"Day: {time_state.current_day}",
        ]

        # Restore energy via NeedsManager (sleep fully restores energy)
        energy_restored = 0
        try:
            needs = self.needs_manager.satisfy_need(
                entity_id=actor.id,
                need_name="energy",
                amount=100,  # Full restoration
            )
            energy_restored = needs.energy
            state_changes.append(f"Energy fully restored: {energy_restored}")
        except ValueError:
            # Entity might not have needs tracking
            pass

        return ExecutionResult(
            action=action,
            success=True,
            outcome=f"Slept for {sleep_hours} hours and feel refreshed",
            state_changes=state_changes,
            metadata={
                "rest_type": "sleep",
                "hours": sleep_hours,
                "new_time": time_state.current_time,
                "new_day": time_state.current_day,
                "energy_restored": energy_restored,
            },
        )

    # =========================================================================
    # Consumption Execution
    # =========================================================================

    async def _execute_consume(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute eating or drinking."""
        action = validation.action
        item_key = validation.resolved_target
        item_id = validation.metadata.get("item_id")

        # Get item using manager
        item = None
        if item_key:
            item = self.item_manager.get_item(item_key)
        elif item_id:
            item = self.item_manager.get_item_by_id(item_id)

        if not item:
            return ExecutionResult(
                action=action,
                success=False,
                outcome=f"Item not found: {action.target}",
            )

        is_eating = action.type == ActionType.EAT
        verb = "Ate" if is_eating else "Drank"
        item_name = item.display_name
        item_key_value = item.item_key

        # Determine satisfaction amount from item properties
        # Default satisfaction: food=25, drink=30
        satisfaction_amount = 25 if is_eating else 30
        if item.properties and "satisfaction" in item.properties:
            satisfaction_amount = item.properties["satisfaction"]

        # Remove consumable using manager
        self.item_manager.delete_item(item.item_key)

        # Update needs via NeedsManager
        need_name = "hunger" if is_eating else "thirst"
        state_changes = [f"Consumed {item_key_value}"]

        try:
            needs = self.needs_manager.satisfy_need(
                entity_id=actor.id,
                need_name=need_name,
                amount=satisfaction_amount,
            )
            new_value = getattr(needs, need_name, None)
            state_changes.append(f"{need_name}: +{satisfaction_amount} -> {new_value}")
        except ValueError:
            # Entity might not have needs tracking (e.g., monsters)
            pass

        return ExecutionResult(
            action=action,
            success=True,
            outcome=f"{verb} {item_name}",
            state_changes=state_changes,
            metadata={
                "item_key": item_key_value,
                "item_name": item_name,
                "consumed": True,
                "need_satisfied": need_name,
                "satisfaction_amount": satisfaction_amount,
            },
        )

    # =========================================================================
    # Skill Execution
    # =========================================================================

    async def _execute_craft(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute crafting."""
        action = validation.action

        return ExecutionResult(
            action=action,
            success=True,
            outcome=f"Attempted to craft {action.target}",
            metadata={
                "target": action.target,
                "skill_check_required": True,
            },
        )

    async def _execute_lockpick(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute lockpicking."""
        action = validation.action

        # TODO: Roll lockpicking check
        return ExecutionResult(
            action=action,
            success=True,
            outcome=f"Attempted to pick the lock on {action.target}",
            metadata={
                "target": action.target,
                "skill_check_required": True,
            },
        )

    async def _execute_sneak(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute sneaking."""
        action = validation.action

        # TODO: Roll stealth check
        return ExecutionResult(
            action=action,
            success=True,
            outcome="Started moving stealthily",
            metadata={
                "skill": "stealth",
                "skill_check_required": True,
            },
        )

    async def _execute_physical_skill(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute climbing or swimming."""
        action = validation.action
        skill = "climbing" if action.type == ActionType.CLIMB else "swimming"
        verb = "Climbed" if action.type == ActionType.CLIMB else "Swam"

        target = action.target or "forward"

        return ExecutionResult(
            action=action,
            success=True,
            outcome=f"{verb} {target}",
            metadata={
                "skill": skill,
                "target": target,
                "skill_check_required": True,
            },
        )

    # =========================================================================
    # Meta Execution
    # =========================================================================

    async def _execute_look(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute looking around."""
        action = validation.action
        location = self._get_actor_location(actor) or "unknown"

        return ExecutionResult(
            action=action,
            success=True,
            outcome=f"Looked around at {location}",
            metadata={"location": location},
        )

    async def _execute_inventory(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute checking inventory."""
        action = validation.action

        inventory = self.item_manager.get_inventory(actor.id)
        item_names = [item.display_name for item in inventory]

        return ExecutionResult(
            action=action,
            success=True,
            outcome=f"Inventory: {', '.join(item_names) if item_names else 'empty'}",
            metadata={
                "items": [item.item_key for item in inventory],
                "item_count": len(inventory),
            },
        )

    async def _execute_status(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute checking status."""
        action = validation.action

        return ExecutionResult(
            action=action,
            success=True,
            outcome=f"Checked status",
            metadata={
                "entity_key": actor.entity_key,
                "entity_name": actor.display_name,
            },
        )

    async def _execute_custom(
        self, validation: ValidationResult, actor: "Entity"
    ) -> ExecutionResult:
        """Execute a custom action using dynamic plan if available.

        If a dynamic plan exists for this action, applies state changes
        and returns narrator facts. Otherwise falls back to simple pass-through.

        Args:
            validation: The validation result containing the action.
            actor: Entity performing the action.

        Returns:
            ExecutionResult with outcome and narrator facts.
        """
        action = validation.action
        raw_input = action.parameters.get("raw_input", str(action))

        # Look up dynamic plan
        plan_dict = self._dynamic_plans.get(raw_input)
        if not plan_dict:
            # No plan - fall back to simple pass-through
            return ExecutionResult(
                action=action,
                success=True,
                outcome=f"Attempted: {raw_input}",
                metadata={"custom": True},
            )

        # We have a dynamic plan - execute it
        from src.planner.schemas import DynamicActionPlan, DynamicActionType

        # Parse plan (it's stored as dict)
        plan = DynamicActionPlan(**plan_dict)

        # Handle already_true case (action is redundant)
        if plan.already_true:
            return ExecutionResult(
                action=action,
                success=True,
                outcome=plan.already_true_message or "Already in that state",
                state_changes=[],
                metadata={
                    "custom": True,
                    "plan_type": plan.action_type,
                    "narrator_facts": plan.narrator_facts,
                    "already_true": True,
                },
            )

        # Apply state changes for STATE_CHANGE type
        state_changes = []
        spawned_items = []
        if plan.action_type == DynamicActionType.STATE_CHANGE:
            for change in plan.state_changes:
                try:
                    result = self._apply_state_change(change, actor)
                    # Track spawned items
                    if result is not None:
                        spawned_items.append(result)
                        state_changes.append(
                            f"Spawned: {result.get('display_name', 'item')}"
                        )
                    else:
                        state_changes.append(
                            f"{change.target_key}.{change.property_name}: "
                            f"{change.old_value} -> {change.new_value}"
                        )
                except Exception as e:
                    # Log but continue with other changes
                    state_changes.append(f"Failed: {change.target_key}.{change.property_name}: {e}")

        # Build outcome from first narrator fact or action type
        outcome = plan.narrator_facts[0] if plan.narrator_facts else f"Completed: {raw_input}"

        return ExecutionResult(
            action=action,
            success=True,
            outcome=outcome,
            state_changes=state_changes,
            metadata={
                "custom": True,
                "plan_type": plan.action_type,
                "narrator_facts": plan.narrator_facts,
                "requires_roll": plan.requires_roll,
                "roll_type": plan.roll_type,
                "roll_dc": plan.roll_dc,
                "spawned_items": spawned_items,
            },
        )

    def _apply_state_change(self, change: Any, actor: "Entity") -> dict[str, Any] | None:
        """Apply a single state change from a dynamic plan.

        Args:
            change: StateChange object with change details.
            actor: Entity performing the action (for context).

        Returns:
            For SPAWN_ITEM: dict with spawned item info. Otherwise None.

        Raises:
            ValueError: If change cannot be applied.
        """
        from src.planner.schemas import StateChangeType, SpawnItemSpec

        if change.change_type == StateChangeType.ITEM_PROPERTY:
            # Update item property via ItemManager
            self.item_manager.update_item_property(
                item_key=change.target_key,
                property_name=change.property_name,
                value=change.new_value,
            )
            return None

        elif change.change_type == StateChangeType.ENTITY_STATE:
            # Update entity temporary state via EntityManager
            self.entity_manager.update_temporary_state(
                entity_key=change.target_key,
                property_name=change.property_name,
                value=change.new_value,
            )
            return None

        elif change.change_type == StateChangeType.FACT:
            # Record a new fact via FactManager
            from src.managers.fact_manager import FactManager
            fact_manager = FactManager(self.db, self.game_session)
            fact_manager.record_fact(
                subject_type=change.target_type,  # "location", "world", "entity", etc.
                subject_key=change.target_key,
                predicate=change.property_name,
                value=str(change.new_value),
            )
            return None

        elif change.change_type == StateChangeType.KNOWLEDGE_QUERY:
            # Knowledge queries don't modify state
            return None

        elif change.change_type == StateChangeType.SPAWN_ITEM:
            # Create emergent item at current location
            return self._apply_spawn_item(change, actor)

        else:
            raise ValueError(f"Unknown change type: {change.change_type}")

    def _apply_spawn_item(self, change: Any, actor: "Entity") -> dict[str, Any]:
        """Apply a SPAWN_ITEM state change to create an emergent item.

        Args:
            change: StateChange with spawn_spec.
            actor: Entity performing the action (for location context).

        Returns:
            Dict with spawned item info (item_key, display_name, item_type).

        Raises:
            ValueError: If spawn_spec is missing or invalid.
        """
        from src.planner.schemas import SpawnItemSpec
        from src.services.emergent_item_generator import (
            EmergentItemGenerator,
            ItemConstraints,
        )

        # Parse spawn_spec
        spec = change.spawn_spec
        if spec is None:
            raise ValueError("SPAWN_ITEM requires spawn_spec")

        if isinstance(spec, dict):
            spec = SpawnItemSpec(**spec)

        # Get current location
        location_key = self._get_actor_location(actor)
        if not location_key:
            location_key = "unknown"

        # Build constraints from spec if any are specified
        constraints = None
        if spec.display_name or spec.quality or spec.condition:
            constraints = ItemConstraints(
                name=spec.display_name,
                quality=spec.quality,
                condition=spec.condition,
            )

        # Create the item using EmergentItemGenerator
        generator = EmergentItemGenerator(self.db, self.game_session)
        item_state = generator.create_item(
            item_type=spec.item_type,
            context=spec.context,
            location_key=location_key,
            owner_entity_id=None,  # Unowned environmental item
            constraints=constraints,
        )

        return {
            "item_key": item_state.item_key,
            "display_name": item_state.display_name,
            "item_type": item_state.item_type,
        }
