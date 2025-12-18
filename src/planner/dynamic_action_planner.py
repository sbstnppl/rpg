"""Dynamic Action Planner for transforming freeform actions into structured plans.

This module provides the core planner class that takes a CUSTOM action
and produces a DynamicActionPlan that can be executed mechanically.
"""

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from src.database.models.entities import Entity
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

    async def plan(
        self,
        action: Action,
        actor: Entity,
        scene_context: str,
    ) -> DynamicActionPlan:
        """Generate execution plan for a custom action.

        Args:
            action: The CUSTOM action to plan.
            actor: Entity performing the action.
            scene_context: Scene context string for additional info.

        Returns:
            DynamicActionPlan with state changes and narrator facts.
        """
        # Get raw input from action
        raw_input = action.parameters.get("raw_input", str(action))

        # Gather current state
        current_state = self._gather_relevant_state(actor)

        # Build prompt
        prompt = PLANNER_USER_TEMPLATE.format(
            raw_input=raw_input,
            inventory=json.dumps(current_state.inventory, indent=2),
            equipped=json.dumps(current_state.equipped, indent=2),
            known_facts=json.dumps(current_state.known_facts, indent=2),
            entity_state=json.dumps(current_state.entity_state, indent=2),
            background=current_state.background or "Not specified",
            scene_context=scene_context[:500] if scene_context else "No context",
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
                plan = DynamicActionPlan(**response.parsed_content)
            else:
                plan = response.parsed_content

            logger.debug(f"Generated plan for '{raw_input}': {plan.action_type}")
            return plan

        except Exception as e:
            logger.error(f"Error generating plan for '{raw_input}': {e}")
            return self._fallback_plan(raw_input)

    def _gather_relevant_state(self, actor: Entity) -> RelevantState:
        """Query current state relevant to the action.

        Args:
            actor: Entity performing the action.

        Returns:
            RelevantState with inventory, equipped items, facts, etc.
        """
        # Get inventory
        inventory_items = self.item_manager.get_inventory(actor.id)
        inventory = [
            {
                "key": item.item_key,
                "name": item.display_name,
                "properties": item.properties or {},
            }
            for item in inventory_items
        ]

        # Get equipped items
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

        # Get facts about the actor
        facts = self._get_actor_facts(actor)
        known_facts = [
            {"predicate": f.predicate, "value": f.value}
            for f in facts
        ]

        # Get entity temporary state
        entity_state = actor.temporary_state or {}

        # Get background
        background = actor.background

        return RelevantState(
            inventory=inventory,
            equipped=equipped,
            known_facts=known_facts,
            entity_state=entity_state,
            background=background,
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
