"""State change applier for the Simplified GM Pipeline.

Applies validated state changes from GM responses to the database.
"""

import logging
from typing import Any

from sqlalchemy.orm import Session

from src.database.models.entities import Entity
from src.database.models.enums import EntityType
from src.database.models.session import GameSession, Turn
from src.database.models.world import Fact
from src.gm.schemas import GMResponse, StateChange, StateChangeType, NewEntity
from src.managers.entity_manager import EntityManager
from src.managers.item_manager import ItemManager
from src.managers.needs import NeedsManager
from src.managers.relationship_manager import RelationshipManager
from src.managers.time_manager import TimeManager

logger = logging.getLogger(__name__)


class StateApplier:
    """Applies state changes from GM responses to the database.

    Handles:
    - Creating new entities
    - Moving player
    - Taking/dropping items
    - Updating relationships
    - Advancing time
    - Persisting turns
    """

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        player_id: int,
        location_key: str,
    ) -> None:
        """Initialize applier.

        Args:
            db: Database session.
            game_session: Current game session.
            player_id: Player entity ID.
            location_key: Current location key.
        """
        self.db = db
        self.game_session = game_session
        self.session_id = game_session.id
        self.player_id = player_id
        self.location_key = location_key

        # Lazy-loaded managers
        self._entity_manager: EntityManager | None = None
        self._item_manager: ItemManager | None = None
        self._needs_manager: NeedsManager | None = None
        self._relationship_manager: RelationshipManager | None = None
        self._time_manager: TimeManager | None = None

    @property
    def entity_manager(self) -> EntityManager:
        if self._entity_manager is None:
            self._entity_manager = EntityManager(self.db, self.game_session)
        return self._entity_manager

    @property
    def item_manager(self) -> ItemManager:
        if self._item_manager is None:
            self._item_manager = ItemManager(self.db, self.game_session)
        return self._item_manager

    @property
    def needs_manager(self) -> NeedsManager:
        if self._needs_manager is None:
            self._needs_manager = NeedsManager(self.db, self.game_session)
        return self._needs_manager

    @property
    def relationship_manager(self) -> RelationshipManager:
        if self._relationship_manager is None:
            self._relationship_manager = RelationshipManager(self.db, self.game_session)
        return self._relationship_manager

    @property
    def time_manager(self) -> TimeManager:
        if self._time_manager is None:
            self._time_manager = TimeManager(self.db, self.game_session)
        return self._time_manager

    def apply(
        self,
        response: GMResponse,
        player_input: str,
        turn_number: int,
    ) -> str:
        """Apply all state changes from a GM response.

        Args:
            response: The validated GM response.
            player_input: Original player input.
            turn_number: Current turn number.

        Returns:
            New location key (if changed).
        """
        new_location = self.location_key

        # For OOC responses, skip state changes and time advancement
        # (facts recorded by tools are already persisted during tool execution)
        if not response.is_ooc:
            # Apply state changes
            for change in response.state_changes:
                result = self._apply_change(change)
                if change.change_type == StateChangeType.MOVE and result:
                    new_location = result

            # Advance time based on time_passed
            if response.time_passed_minutes > 0:
                self._advance_time(response.time_passed_minutes)

        # Persist the turn (always, including OOC)
        self._persist_turn(response, player_input, turn_number)

        self.db.commit()
        return new_location

    def _apply_change(self, change: StateChange) -> str | None:
        """Apply a single state change.

        Args:
            change: The state change to apply.

        Returns:
            New location key if this was a move, otherwise None.
        """
        logger.debug(f"Applying state change: {change.change_type} -> {change.target}")

        if change.change_type == StateChangeType.MOVE:
            return self._apply_move(change)

        elif change.change_type == StateChangeType.TAKE:
            self._apply_take(change)

        elif change.change_type == StateChangeType.DROP:
            self._apply_drop(change)

        elif change.change_type == StateChangeType.GIVE:
            self._apply_give(change)

        elif change.change_type == StateChangeType.EQUIP:
            self._apply_equip(change)

        elif change.change_type == StateChangeType.UNEQUIP:
            self._apply_unequip(change)

        elif change.change_type == StateChangeType.SATISFY_NEED:
            self._apply_satisfy_need(change)

        elif change.change_type == StateChangeType.RELATIONSHIP:
            self._apply_relationship(change)

        elif change.change_type == StateChangeType.FACT:
            self._apply_fact(change)

        elif change.change_type == StateChangeType.TIME_SKIP:
            self._apply_time_skip(change)

        return None

    def _apply_move(self, change: StateChange) -> str | None:
        """Apply a move state change for player or NPC.

        Args:
            change: The move change.

        Returns:
            New location key if player moved, None for NPC moves.
        """
        target_key = change.target
        destination = change.details.get("to", target_key)

        if target_key == "player":
            # Player movement
            player = self.entity_manager.get_player()
            if player and player.npc_extension:
                player.npc_extension.current_location = destination
                self.db.add(player)

            logger.info(f"Player moved to {destination}")
            return destination
        else:
            # NPC movement
            npc = self.entity_manager.get_entity(target_key)
            if npc and npc.npc_extension:
                npc.npc_extension.current_location = destination
                self.db.flush()
                logger.info(f"NPC {target_key} moved to {destination}")
            return None

    def _apply_take(self, change: StateChange) -> None:
        """Apply a take item state change."""
        item_key = change.target

        # Get the item
        item = self.item_manager.get_item(item_key)
        if item:
            # Transfer ownership to player
            self.item_manager.transfer_to_inventory(item.id, self.player_id)
            logger.info(f"Player took item: {item_key}")

    def _apply_drop(self, change: StateChange) -> None:
        """Apply a drop item state change."""
        item_key = change.target

        item = self.item_manager.get_item(item_key)
        if item:
            # Drop at current location
            self.item_manager.drop_at_location(item.id, self.location_key)
            logger.info(f"Player dropped item: {item_key}")

    def _apply_give(self, change: StateChange) -> None:
        """Apply a give item state change."""
        item_key = change.target
        recipient_key = change.details.get("to")

        if not recipient_key:
            return

        item = self.item_manager.get_item(item_key)
        recipient = self.entity_manager.get_entity(recipient_key)

        if item and recipient:
            self.item_manager.transfer_to_inventory(item.id, recipient.id)
            logger.info(f"Player gave {item_key} to {recipient_key}")

    def _apply_equip(self, change: StateChange) -> None:
        """Apply an equip item state change."""
        item_key = change.target
        slot = change.details.get("slot")

        item = self.item_manager.get_item(item_key)
        if item:
            self.item_manager.equip_item(item.id, self.player_id, slot)
            logger.info(f"Player equipped: {item_key}")

    def _apply_unequip(self, change: StateChange) -> None:
        """Apply an unequip item state change."""
        item_key = change.target

        item = self.item_manager.get_item(item_key)
        if item:
            self.item_manager.unequip_item(item.id)
            logger.info(f"Player unequipped: {item_key}")

    def _apply_satisfy_need(self, change: StateChange) -> None:
        """Apply a need satisfaction state change.

        Handles both:
        - Item consumption (eating bread, drinking ale) - deletes item
        - Activity satisfaction (sleeping, bathing) - no item deletion
        """
        target_key = change.target
        details = change.details or {}

        # Check if this is an activity-based satisfaction (has 'activity' key)
        if "activity" in details:
            # Activity-based need satisfaction (sleeping, bathing, conversations)
            entity = self.entity_manager.get_entity(target_key)
            if not entity:
                logger.warning(f"Entity not found for need satisfaction: {target_key}")
                return

            need_name = details.get("need")
            amount = details.get("amount", 0)
            activity = details.get("activity", "unknown")

            if need_name and amount:
                self.needs_manager.satisfy_need(
                    entity.id,
                    need_name,
                    amount,
                    turn=self.game_session.total_turns,
                )
                logger.info(f"{target_key} satisfied {need_name} by {amount} via {activity}")
        else:
            # Item consumption - get the item and apply effects
            item = self.item_manager.get_item(target_key)
            if not item:
                logger.warning(f"Item not found for consumption: {target_key}")
                return

            # Apply hunger/thirst restoration using satisfy_need
            hunger_restore = details.get("hunger", 0)
            thirst_restore = details.get("thirst", 0)

            if hunger_restore:
                self.needs_manager.satisfy_need(
                    self.player_id, "hunger", hunger_restore,
                    turn=self.game_session.total_turns
                )
            if thirst_restore:
                self.needs_manager.satisfy_need(
                    self.player_id, "thirst", thirst_restore,
                    turn=self.game_session.total_turns
                )

            # Delete item unless explicitly told not to
            if details.get("destroys_item", True):
                self.item_manager.delete_item(target_key)
                logger.info(f"Player consumed item: {target_key}")
            else:
                logger.info(f"Player used item (not consumed): {target_key}")

    def _apply_relationship(self, change: StateChange) -> None:
        """Apply a relationship change."""
        from src.database.models.enums import RelationshipDimension

        npc_key = change.target
        adjustments = change.details

        npc = self.entity_manager.get_entity(npc_key)
        if not npc:
            return

        # Map string dimension names to enum values
        dimension_map = {
            "trust": RelationshipDimension.TRUST,
            "liking": RelationshipDimension.LIKING,
            "respect": RelationshipDimension.RESPECT,
            "fear": RelationshipDimension.FEAR,
            "romantic_interest": RelationshipDimension.ROMANTIC_INTEREST,
            "familiarity": RelationshipDimension.FAMILIARITY,
        }

        # Apply each adjustment
        for dimension_str, delta in adjustments.items():
            if dimension_str in dimension_map:
                self.relationship_manager.update_attitude(
                    from_id=npc.id,
                    to_id=self.player_id,
                    dimension=dimension_map[dimension_str],
                    delta=delta,
                    reason="GM state change",
                )
                logger.info(f"Adjusted {npc_key}'s {dimension_str} by {delta}")

    def _apply_fact(self, change: StateChange) -> None:
        """Apply a new fact."""
        subject = change.target
        predicate = change.details.get("predicate", "")
        value = change.details.get("value", "")

        if predicate and value:
            fact = Fact(
                session_id=self.session_id,
                subject_key=subject,
                predicate=predicate,
                value=str(value),
                is_secret=change.details.get("is_secret", False),
            )
            self.db.add(fact)
            logger.info(f"Added fact: {subject}.{predicate} = {value}")

    def _apply_time_skip(self, change: StateChange) -> None:
        """Apply a time skip."""
        minutes = change.details.get("minutes", 0)
        if minutes:
            self._advance_time(minutes)

    def _advance_time(self, minutes: int) -> None:
        """Advance game time and update needs.

        Args:
            minutes: Minutes to advance.
        """
        if minutes <= 0:
            return

        # Advance time
        self.time_manager.advance_time(minutes)

        # Decay needs based on time (convert minutes to hours)
        hours = minutes / 60.0
        self.needs_manager.apply_time_decay(self.player_id, hours)

        logger.debug(f"Advanced time by {minutes} minutes")

    def _persist_turn(
        self,
        response: GMResponse,
        player_input: str,
        turn_number: int,
    ) -> None:
        """Persist the turn to the database.

        Args:
            response: The GM response.
            player_input: Original player input.
            turn_number: Turn number.
        """
        turn = Turn(
            session_id=self.session_id,
            turn_number=turn_number,
            player_input=player_input,
            gm_response=response.narrative,
            is_ooc=response.is_ooc,
        )
        self.db.add(turn)
        logger.debug(f"Persisted turn {turn_number} (OOC: {response.is_ooc})")


def apply_response(
    response: GMResponse,
    db: Session,
    game_session: GameSession,
    player_id: int,
    location_key: str,
    player_input: str,
    turn_number: int,
) -> str:
    """Convenience function to apply a GM response.

    Args:
        response: The validated GMResponse.
        db: Database session.
        game_session: Current game session.
        player_id: Player entity ID.
        location_key: Current location key.
        player_input: Original player input.
        turn_number: Current turn number.

    Returns:
        New location key (may be same as current if no move).
    """
    applier = StateApplier(db, game_session, player_id, location_key)
    return applier.apply(response, player_input, turn_number)
