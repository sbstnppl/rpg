"""Dynamic Action Planner for transforming freeform actions into structured plans.

This module provides the core planner class that takes a CUSTOM action
and produces a DynamicActionPlan that can be executed mechanically.
It also handles player queries by gathering comprehensive state information.
"""

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from src.database.models.entities import Entity
from src.database.models.enums import BodyPart, InjuryType
from src.database.models.session import GameSession
from src.database.models.world import Fact
from src.llm.base import LLMProvider
from src.llm.message_types import Message
from src.managers.entity_manager import EntityManager
from src.managers.fact_manager import FactManager
from src.managers.item_manager import ItemManager
from src.parser.action_types import Action
from src.planner.prompts import PLANNER_SYSTEM_PROMPT, PLANNER_USER_TEMPLATE
from src.planner.schemas import DynamicActionPlan, DynamicActionType, RelevantState

logger = logging.getLogger(__name__)

# Body parts that are typically visible (not covered by clothing)
VISIBLE_BODY_PARTS = {
    BodyPart.HEAD, BodyPart.LEFT_ARM, BodyPart.RIGHT_ARM,
    BodyPart.LEFT_HAND, BodyPart.RIGHT_HAND, BodyPart.LEFT_LEG,
    BodyPart.RIGHT_LEG, BodyPart.LEFT_FOOT, BodyPart.RIGHT_FOOT,
}

# Injury types that are visually observable
VISIBLE_INJURY_TYPES = {
    InjuryType.CUT, InjuryType.LACERATION, InjuryType.BURN,
    InjuryType.BRUISE, InjuryType.FRACTURE, InjuryType.DISLOCATION,
}


class DynamicActionPlanner:
    """Plans execution of freeform/CUSTOM actions.

    The planner:
    1. Gathers current state relevant to the action
    2. Calls LLM with structured output to generate a plan
    3. Returns DynamicActionPlan for mechanical execution

    Example:
        planner = DynamicActionPlanner(db, game_session, llm_provider)
        plan = await planner.plan(action, actor, scene_context)
        # plan.state_changes contains mechanical changes to apply
        # plan.narrator_facts contains facts for narrator
    """

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        llm_provider: LLMProvider,
    ):
        """Initialize planner.

        Args:
            db: Database session.
            game_session: Current game session.
            llm_provider: LLM provider for structured output.
        """
        self.db = db
        self.game_session = game_session
        self.llm_provider = llm_provider

        # Lazy-load managers
        self._item_manager: ItemManager | None = None
        self._entity_manager: EntityManager | None = None
        self._fact_manager: FactManager | None = None
        self._needs_manager: Any | None = None
        self._injury_manager: Any | None = None
        self._memory_manager: Any | None = None
        self._discovery_manager: Any | None = None
        self._relationship_manager: Any | None = None
        self._location_manager: Any | None = None

    @property
    def item_manager(self) -> ItemManager:
        if self._item_manager is None:
            self._item_manager = ItemManager(self.db, self.game_session)
        return self._item_manager

    @property
    def entity_manager(self) -> EntityManager:
        if self._entity_manager is None:
            self._entity_manager = EntityManager(self.db, self.game_session)
        return self._entity_manager

    @property
    def fact_manager(self) -> FactManager:
        if self._fact_manager is None:
            self._fact_manager = FactManager(self.db, self.game_session)
        return self._fact_manager

    @property
    def needs_manager(self) -> Any:
        if self._needs_manager is None:
            from src.managers.needs import NeedsManager
            self._needs_manager = NeedsManager(self.db, self.game_session)
        return self._needs_manager

    @property
    def injury_manager(self) -> Any:
        if self._injury_manager is None:
            from src.managers.injuries import InjuryManager
            self._injury_manager = InjuryManager(self.db, self.game_session)
        return self._injury_manager

    @property
    def memory_manager(self) -> Any:
        if self._memory_manager is None:
            from src.managers.memory_manager import MemoryManager
            self._memory_manager = MemoryManager(self.db, self.game_session)
        return self._memory_manager

    @property
    def discovery_manager(self) -> Any:
        if self._discovery_manager is None:
            from src.managers.discovery_manager import DiscoveryManager
            self._discovery_manager = DiscoveryManager(self.db, self.game_session)
        return self._discovery_manager

    @property
    def relationship_manager(self) -> Any:
        if self._relationship_manager is None:
            from src.managers.relationship_manager import RelationshipManager
            self._relationship_manager = RelationshipManager(self.db, self.game_session)
        return self._relationship_manager

    @property
    def location_manager(self) -> Any:
        if self._location_manager is None:
            from src.managers.location_manager import LocationManager
            self._location_manager = LocationManager(self.db, self.game_session)
        return self._location_manager

    async def plan(
        self,
        action: Action,
        actor: Entity,
        scene_context: str,
        actor_location: str | int | None = None,
    ) -> DynamicActionPlan:
        """Generate execution plan for a custom action or answer a player query.

        Args:
            action: The CUSTOM action to plan.
            actor: Entity performing the action.
            scene_context: Scene context string for additional info.
            actor_location: Current location key of the actor.

        Returns:
            DynamicActionPlan with state changes and narrator facts.
        """
        # Get raw input from action
        raw_input = action.parameters.get("raw_input", str(action))

        # Gather current state (comprehensive, with visibility filtering)
        current_state = self._gather_relevant_state(actor, actor_location)

        # Build prompt with all state fields
        prompt = PLANNER_USER_TEMPLATE.format(
            raw_input=raw_input,
            # Existing fields
            inventory=json.dumps(current_state.inventory, indent=2),
            equipped=json.dumps(current_state.equipped, indent=2),
            known_facts=json.dumps(current_state.known_facts, indent=2),
            entity_state=json.dumps(current_state.entity_state, indent=2),
            background=current_state.background or "Not specified",
            # New character state fields
            character_needs=json.dumps(current_state.character_needs, indent=2),
            visible_injuries=json.dumps(current_state.visible_injuries, indent=2),
            character_memories=json.dumps(current_state.character_memories, indent=2),
            # New environment perception fields
            npcs_present=json.dumps(current_state.npcs_present, indent=2),
            items_at_location=json.dumps(current_state.items_at_location, indent=2),
            available_exits=json.dumps(current_state.available_exits, indent=2),
            # New knowledge fields
            discovered_locations=json.dumps(current_state.discovered_locations, indent=2),
            relationships=json.dumps(current_state.relationships, indent=2),
            # NEW: Enrichment context fields
            location_details=json.dumps(current_state.location_details, indent=2),
            world_facts=json.dumps(current_state.world_facts, indent=2),
            recent_actions=json.dumps(current_state.recent_actions, indent=2),
            # Scene context (not truncated anymore - let LLM handle it)
            scene_context=scene_context or "No context",
        )

        # Call LLM with structured output
        try:
            messages = [Message.user(prompt)]

            response = await self.llm_provider.complete_structured(
                messages=messages,
                response_schema=DynamicActionPlan,
                temperature=0.0,  # Deterministic
                max_tokens=1000,
                system_prompt=PLANNER_SYSTEM_PROMPT,
            )

            # Parse response
            if response.parsed_content is None:
                logger.warning(f"LLM returned no structured content for: {raw_input}")
                return self._fallback_plan(raw_input)

            # Handle both dict and Pydantic model
            if isinstance(response.parsed_content, dict):
                content = response.parsed_content
                # Handle case where LLM wraps response in 'input' key
                if "input" in content and isinstance(content["input"], dict):
                    content = content["input"]
                plan = DynamicActionPlan(**content)
            else:
                plan = response.parsed_content

            logger.debug(f"Generated plan for '{raw_input}': {plan.action_type}")
            return plan

        except Exception as e:
            logger.error(f"Error generating plan for '{raw_input}': {e}")
            return self._fallback_plan(raw_input)

    def _gather_relevant_state(
        self, actor: Entity, actor_location: str | int | None = None
    ) -> RelevantState:
        """Query current state relevant to the action or query.

        Gathers comprehensive state with proper visibility filtering to support
        player queries about their character and environment.

        Args:
            actor: Entity performing the action.
            actor_location: Current location key of the actor.

        Returns:
            RelevantState with all queryable fields (visibility-filtered).
        """
        # Ensure clean transaction state before gathering
        try:
            # Test connection with a simple query
            from sqlalchemy import text
            self.db.execute(text("SELECT 1"))
        except Exception:
            # Transaction may be in failed state, rollback to recover
            logger.warning("Rolling back failed transaction before gathering state")
            self.db.rollback()

        # ===========================================
        # EXISTING: Player's own inventory/equipment
        # ===========================================
        inventory_items = self.item_manager.get_inventory(actor.id)
        inventory = [
            {
                "key": item.item_key,
                "name": item.display_name,
                "properties": item.properties or {},
            }
            for item in inventory_items
        ]

        equipped_items = self.item_manager.get_equipped_items(actor.id)
        equipped = [
            {
                "key": item.item_key,
                "name": item.display_name,
                "slot": item.body_slot,
                "properties": item.properties or {},
            }
            for item in equipped_items
        ]

        # Get facts about the actor (non-secret only)
        facts = self._get_actor_facts(actor)
        known_facts = [
            {"predicate": f.predicate, "value": f.value}
            for f in facts
        ]

        entity_state = actor.temporary_state or {}
        background = actor.background

        # ===========================================
        # NEW: Character needs
        # ===========================================
        character_needs = self._get_character_needs(actor)

        # ===========================================
        # NEW: Visible injuries
        # ===========================================
        visible_injuries = self._get_visible_injuries(actor)

        # ===========================================
        # NEW: Character memories
        # ===========================================
        character_memories = self._get_character_memories(actor)

        # ===========================================
        # NEW: Environment perception (visibility-filtered)
        # ===========================================
        npcs_present = self._get_visible_npcs(actor, actor_location)
        items_at_location = self._get_visible_location_items(actor_location)
        available_exits = self._get_available_exits(actor_location)

        # ===========================================
        # NEW: Knowledge (what player has discovered)
        # ===========================================
        discovered_locations = self._get_discovered_locations()
        relationships = self._get_known_relationships(actor)

        # ===========================================
        # NEW: Enrichment context (already-established details)
        # ===========================================
        location_details = self._get_location_details(actor_location)
        world_facts = self._get_world_facts()
        recent_actions = self._search_recent_actions()  # Get general recent history

        return RelevantState(
            inventory=inventory,
            equipped=equipped,
            known_facts=known_facts,
            entity_state=entity_state,
            background=background,
            character_needs=character_needs,
            visible_injuries=visible_injuries,
            character_memories=character_memories,
            npcs_present=npcs_present,
            items_at_location=items_at_location,
            available_exits=available_exits,
            discovered_locations=discovered_locations,
            relationships=relationships,
            # NEW enrichment context
            location_details=location_details,
            world_facts=world_facts,
            recent_actions=recent_actions,
        )

    def _get_actor_facts(self, actor: Entity) -> list[Fact]:
        """Get facts known to/about the actor.

        Args:
            actor: Entity to get facts for.

        Returns:
            List of relevant facts.
        """
        # Get facts where actor is the subject
        facts = (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.game_session.id,
                Fact.subject_key == actor.entity_key,
                Fact.is_secret == False,  # Only non-secret facts
            )
            .limit(20)
            .all()
        )
        return facts

    def _fallback_plan(self, raw_input: str) -> DynamicActionPlan:
        """Generate fallback plan when LLM fails.

        Args:
            raw_input: Original player input.

        Returns:
            Simple narrative-only plan.
        """
        return DynamicActionPlan(
            action_type=DynamicActionType.NARRATIVE_ONLY,
            narrator_facts=[f"Attempted: {raw_input}"],
        )

    # ===========================================
    # NEW: Helper methods for comprehensive state
    # ===========================================

    def _get_character_needs(self, actor: Entity) -> dict[str, int]:
        """Get character needs (hunger, thirst, energy, etc.).

        Args:
            actor: Entity to get needs for.

        Returns:
            Dict with need values (0=critical, 100=satisfied).
        """
        try:
            needs = self.needs_manager.get_needs(actor.id)
            if needs:
                return {
                    "hunger": needs.hunger,
                    "thirst": needs.thirst,
                    "energy": needs.energy,
                    "wellness": needs.wellness,
                    "hygiene": needs.hygiene,
                    "comfort": needs.comfort,
                    "morale": needs.morale,
                }
        except Exception as e:
            logger.warning(f"Could not get character needs: {e}")
            self.db.rollback()
        return {}

    def _get_visible_injuries(self, actor: Entity) -> list[dict[str, Any]]:
        """Get injuries on visible body parts only.

        Args:
            actor: Entity to get injuries for.

        Returns:
            List of visible injuries with body_part, type, severity.
        """
        try:
            injuries = self.injury_manager.get_injuries(actor.id, active_only=True)
            visible = []
            for injury in injuries:
                # Only include injuries on visible body parts
                if injury.body_part in VISIBLE_BODY_PARTS:
                    # Only include visually observable injury types
                    if injury.injury_type in VISIBLE_INJURY_TYPES:
                        visible.append({
                            "body_part": injury.body_part.value if hasattr(injury.body_part, 'value') else str(injury.body_part),
                            "type": injury.injury_type.value if hasattr(injury.injury_type, 'value') else str(injury.injury_type),
                            "severity": injury.severity,
                        })
            return visible
        except Exception as e:
            logger.warning(f"Could not get injuries: {e}")
            self.db.rollback()
        return []

    def _get_character_memories(self, actor: Entity) -> list[dict[str, Any]]:
        """Get character's emotional memories.

        Args:
            actor: Entity to get memories for.

        Returns:
            List of memories with subject, emotion, context.
        """
        try:
            memories = self.memory_manager.get_memories_for_entity(actor.id)
            return [
                {
                    "subject": m.subject,
                    "emotion": m.emotion.value if hasattr(m.emotion, 'value') else str(m.emotion) if m.emotion else None,
                    "context": m.context,
                }
                for m in memories[:10]  # Limit to 10 memories
            ]
        except Exception as e:
            logger.warning(f"Could not get memories: {e}")
            self.db.rollback()
        return []

    def _get_visible_npcs(
        self, actor: Entity, actor_location: str | int | None
    ) -> list[dict[str, Any]]:
        """Get NPCs at current location with VISIBLE info only.

        Args:
            actor: The player entity (excluded from results).
            actor_location: Current location key (string) or ID (int).

        Returns:
            List of NPCs with visible info (appearance, mood, visible equipment).
            EXCLUDES: hidden_backstory, dark_secret, hidden_goal, items under clothing.
        """
        if not actor_location:
            return []

        try:
            # Handle both location key (string) and location ID (int or numeric string)
            from src.database.models.world import Location

            # Check if it's an integer or a numeric string (location ID)
            is_location_id = isinstance(actor_location, int)
            if not is_location_id and isinstance(actor_location, str) and actor_location.isdigit():
                is_location_id = True
                actor_location = int(actor_location)

            location_key = actor_location
            if is_location_id:
                location = (
                    self.db.query(Location)
                    .filter(
                        Location.session_id == self.game_session.id,
                        Location.id == actor_location,
                    )
                    .first()
                )
                location_key = location.location_key if location else None

            if not location_key:
                return []

            # Get NPCs at this location
            npcs = self.entity_manager.get_entities_at_location(str(location_key))
            visible_npcs = []

            for npc in npcs:
                # Skip the player
                if npc.id == actor.id:
                    continue

                # Get NPC extension for mood/activity
                npc_ext = getattr(npc, 'npc_extension', None)

                # Get visible equipment (outermost layer only)
                visible_equipment = self._get_visible_equipment(npc.id)

                visible_npcs.append({
                    "key": npc.entity_key,
                    "name": npc.display_name,
                    "appearance": npc.appearance or {},
                    "mood": npc_ext.current_mood if npc_ext else None,
                    "activity": npc_ext.current_activity if npc_ext else None,
                    "visible_equipment": visible_equipment,
                    # NEVER include: hidden_backstory, dark_secret, hidden_goal
                })

            return visible_npcs
        except Exception as e:
            logger.warning(f"Could not get NPCs: {e}")
            self.db.rollback()
        return []

    def _get_visible_equipment(self, entity_id: int) -> list[dict[str, str]]:
        """Get visible equipment for an entity (outermost layer only).

        Args:
            entity_id: Entity to get equipment for.

        Returns:
            List of visible items with name and slot.
        """
        try:
            equipped = self.item_manager.get_equipped_items(entity_id)
            return [
                {"name": item.display_name, "slot": item.body_slot}
                for item in equipped
                if item.is_visible  # Only outermost layer
            ]
        except Exception as e:
            logger.warning(f"Could not get visible equipment: {e}")
            self.db.rollback()
        return []

    def _get_visible_location_items(
        self, actor_location: str | int | None
    ) -> list[dict[str, Any]]:
        """Get items visible at current location.

        Args:
            actor_location: Current location key (string) or ID (int).

        Returns:
            List of items on location surfaces (not in closed containers).
        """
        if not actor_location:
            return []

        try:
            # Handle both location key (string) and location ID (int or numeric string)
            from src.database.models.world import Location

            # Check if it's an integer or a numeric string (location ID)
            is_location_id = isinstance(actor_location, int)
            if not is_location_id and isinstance(actor_location, str) and actor_location.isdigit():
                is_location_id = True
                actor_location = int(actor_location)

            if is_location_id:
                location = (
                    self.db.query(Location)
                    .filter(
                        Location.session_id == self.game_session.id,
                        Location.id == actor_location,
                    )
                    .first()
                )
            else:
                location = self.location_manager.get_location(str(actor_location))
            if not location:
                return []

            # Get items at this location that are on surfaces (visible)
            # Note: get_items_at_location expects location_key (string), not location.id
            items = self.item_manager.get_items_at_location(location.location_key)
            return [
                {
                    "key": item.item_key,
                    "name": item.display_name,
                    "description": item.description[:100] if item.description else None,
                }
                for item in items
                if item.is_visible  # Only visible items
            ]
        except Exception as e:
            logger.warning(f"Could not get location items: {e}")
            self.db.rollback()
        return []

    def _get_available_exits(
        self, actor_location: str | int | None
    ) -> list[dict[str, Any]]:
        """Get available exits with accessibility info.

        Args:
            actor_location: Current location key (string) or ID (int).

        Returns:
            List of exits with name, is_accessible, blocked_reason.
            EXCLUDES: secret passages (is_visible=False).
        """
        if not actor_location:
            return []

        try:
            # Handle both location key (string) and location ID (int or numeric string)
            from src.database.models.world import Location

            # Check if it's an integer or a numeric string (location ID)
            is_location_id = isinstance(actor_location, int)
            if not is_location_id and isinstance(actor_location, str) and actor_location.isdigit():
                is_location_id = True
                actor_location = int(actor_location)

            location_key = actor_location
            if is_location_id:
                location = (
                    self.db.query(Location)
                    .filter(
                        Location.session_id == self.game_session.id,
                        Location.id == actor_location,
                    )
                    .first()
                )
                location_key = location.location_key if location else None

            if not location_key:
                return []

            exits = self.location_manager.get_accessible_locations(str(location_key))
            return [
                {
                    "key": loc.location_key,
                    "name": loc.display_name,
                    "is_accessible": loc.is_accessible,
                    "access_requirements": loc.access_requirements,
                }
                for loc in exits
                # Only include exits that aren't secret
            ]
        except Exception as e:
            logger.warning(f"Could not get exits: {e}")
            self.db.rollback()
        return []

    def _get_discovered_locations(self) -> list[str]:
        """Get location keys player has discovered.

        Returns:
            List of discovered location keys.
        """
        try:
            locations = self.discovery_manager.get_known_locations()
            return [loc.location_key for loc in locations]
        except Exception as e:
            logger.warning(f"Could not get discovered locations: {e}")
            self.db.rollback()
        return []

    def _get_known_relationships(self, actor: Entity) -> list[dict[str, Any]]:
        """Get relationships for NPCs player has met.

        Args:
            actor: The player entity.

        Returns:
            List of relationship data for NPCs player knows.
            EXCLUDES: NPCs not yet met (knows=False).
        """
        try:
            relationships = self.relationship_manager.get_relationships_for_entity(
                actor.id, direction="from"
            )
            return [
                {
                    "npc_key": rel.to_entity.entity_key if rel.to_entity else None,
                    "npc_name": rel.to_entity.display_name if rel.to_entity else None,
                    "trust": rel.trust,
                    "liking": rel.liking,
                    "respect": rel.respect,
                    "familiarity": rel.familiarity,
                }
                for rel in relationships
                if rel.knows and rel.to_entity  # Only include NPCs player has met
            ]
        except Exception as e:
            logger.warning(f"Could not get relationships: {e}")
            self.db.rollback()
        return []

    # ===========================================
    # NEW: Enrichment context gathering methods
    # ===========================================

    def _get_location_details(self, actor_location: str | int | None) -> dict[str, str]:
        """Get already-established facts about the current location.

        These are details that have been enriched/generated previously
        (floor_type, lighting, ambient_smell, etc.)

        Args:
            actor_location: Current location key (string) or ID (int).

        Returns:
            Dict mapping predicate to value for location facts.
        """
        if not actor_location:
            return {}

        try:
            from src.database.models.world import Location

            # Resolve location key
            location_key = actor_location
            if isinstance(actor_location, int) or (
                isinstance(actor_location, str) and actor_location.isdigit()
            ):
                loc_id = int(actor_location) if isinstance(actor_location, str) else actor_location
                location = (
                    self.db.query(Location)
                    .filter(
                        Location.session_id == self.game_session.id,
                        Location.id == loc_id,
                    )
                    .first()
                )
                location_key = location.location_key if location else None

            if not location_key:
                return {}

            # Get facts about this location
            facts = self.fact_manager.get_facts_about(str(location_key), include_secrets=False)
            return {f.predicate: f.value for f in facts}

        except Exception as e:
            logger.warning(f"Could not get location details: {e}")
            self.db.rollback()
        return {}

    def _get_world_facts(self) -> dict[str, str]:
        """Get world-level facts (weather, currency, customs, etc.).

        These are session-wide facts that apply globally.

        Returns:
            Dict mapping predicate to value for world facts.
        """
        try:
            # Query world-level facts
            facts = (
                self.db.query(Fact)
                .filter(
                    Fact.session_id == self.game_session.id,
                    Fact.subject_type == "world",
                    Fact.is_secret == False,
                )
                .limit(50)
                .all()
            )
            return {f.predicate: f.value for f in facts}
        except Exception as e:
            logger.warning(f"Could not get world facts: {e}")
            self.db.rollback()
        return {}

    def _search_recent_actions(
        self,
        action_types: list[str] | None = None,
        keywords: list[str] | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search recent turn history for matching actions.

        Used for memory queries like "What did I eat?" or "Did I lock the door?"

        Args:
            action_types: Optional list of action types to filter (e.g., ["eat", "drink"]).
            keywords: Optional keywords to search in turn data.
            limit: Maximum number of turns to search.

        Returns:
            List of matching actions with turn_number, action_type, target, outcome.
        """
        try:
            from src.database.models.session import Turn

            recent_turns = (
                self.db.query(Turn)
                .filter(Turn.session_id == self.game_session.id)
                .order_by(Turn.turn_number.desc())
                .limit(limit)
                .all()
            )

            matches = []
            for turn in recent_turns:
                player_input = turn.player_input or ""
                gm_response = turn.gm_response or ""

                # Search in player input and GM response
                search_text = f"{player_input} {gm_response}".lower()

                # Check action type filter (look for action words in text)
                if action_types:
                    found_type = False
                    for at in action_types:
                        if at.lower() in search_text:
                            found_type = True
                            break
                    if not found_type:
                        continue

                # Check keyword filter
                if keywords:
                    if not any(kw.lower() in search_text for kw in keywords):
                        continue

                matches.append({
                    "turn_number": turn.turn_number,
                    "player_input": player_input[:100],
                    "outcome": gm_response[:200] if gm_response else None,
                })

            return matches[:10]  # Return at most 10 matches
        except Exception as e:
            logger.warning(f"Could not search recent actions: {e}")
            self.db.rollback()
        return []
