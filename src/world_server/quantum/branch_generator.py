"""Branch Generator for Quantum Branching.

Generates full narrative outcome branches for predicted actions.
Each branch contains multiple variants (success, failure, critical)
with pre-generated prose and state deltas.

The generator:
1. Takes an action prediction and GM decision
2. Builds a prompt with scene context
3. Calls the LLM to generate all variants in one call
4. Parses the response into OutcomeVariant objects
5. Returns a QuantumBranch ready for caching
"""

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database.models.session import GameSession
from src.gm.grounding import GroundingManifest
from src.llm.base import LLMProvider
from src.llm.message_types import Message
from src.world_server.quantum.schemas import (
    ActionPrediction,
    ActionType,
    DeltaType,
    GMDecision,
    OutcomeVariant,
    QuantumBranch,
    StateDelta,
    VariantType,
)

logger = logging.getLogger(__name__)


# Pydantic models for structured LLM output
class GeneratedStateDelta(BaseModel):
    """State change from LLM output."""

    delta_type: str = Field(description="Type: create_entity, update_entity, transfer_item, record_fact, advance_time")
    target_key: str = Field(description="Entity or location key affected")
    changes: dict[str, Any] = Field(description="The changes to apply")


class GeneratedVariant(BaseModel):
    """Outcome variant from LLM output."""

    variant_type: str = Field(description="success, failure, critical_success, or critical_failure")
    narrative: str = Field(description="Full narrative prose with [entity_key:display_name] format")
    state_deltas: list[GeneratedStateDelta] = Field(default_factory=list)
    time_passed_minutes: int = Field(default=1, description="Game time that passes")
    requires_skill_check: bool = Field(default=False)
    skill: str | None = Field(default=None, description="Skill for check if required")
    dc: int | None = Field(default=None, description="Difficulty class if skill check required")


class BranchGenerationResponse(BaseModel):
    """Full response from branch generation LLM call."""

    variants: list[GeneratedVariant] = Field(description="All outcome variants")
    action_summary: str = Field(description="Brief summary of the action being resolved")


@dataclass
class BranchContext:
    """Context for branch generation."""

    location_key: str
    location_display: str
    player_key: str
    game_time: str  # e.g., "14:30"
    game_day: int
    recent_events: list[str]  # Recent narrative summaries


class BranchGenerator:
    """Generates narrative branches for predicted actions.

    Uses LLM to generate multiple outcome variants with full prose
    and state changes, ready for caching and later collapse.
    """

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        llm_provider: LLMProvider,
    ):
        """Initialize the generator.

        Args:
            db: Database session
            game_session: Current game session
            llm_provider: LLM provider for generation
        """
        self.db = db
        self.game_session = game_session
        self.llm = llm_provider

    async def generate_branch(
        self,
        action: ActionPrediction,
        gm_decision: GMDecision,
        manifest: GroundingManifest,
        context: BranchContext,
    ) -> QuantumBranch:
        """Generate a complete branch for an action + GM decision.

        Args:
            action: The predicted action
            gm_decision: The GM's decision (twist or no_twist)
            manifest: Grounding manifest for the scene
            context: Additional context for generation

        Returns:
            QuantumBranch with all variants
        """
        start_time = time.perf_counter()

        # Build prompt
        prompt = self._build_generation_prompt(action, gm_decision, manifest, context)

        # Generate variants
        try:
            response = await self.llm.complete_structured(
                messages=[Message.user(prompt)],
                response_schema=BranchGenerationResponse,
                system_prompt=self._get_system_prompt(),
                temperature=0.7,
                max_tokens=4096,
            )

            if response.parsed_content:
                # parsed_content may be a dict or Pydantic model depending on provider
                parsed = response.parsed_content
                if isinstance(parsed, dict):
                    parsed = BranchGenerationResponse.model_validate(parsed)
                variants = self._parse_variants(parsed)
            else:
                # Fallback: try to parse from raw content
                variants = self._generate_fallback_variants(action, gm_decision)
                logger.warning("Using fallback variants - structured output failed")

        except Exception as e:
            logger.error(f"Branch generation failed: {e}")
            variants = self._generate_fallback_variants(action, gm_decision)

        generation_time_ms = (time.perf_counter() - start_time) * 1000

        # Create branch
        branch_key = QuantumBranch.create_key(
            location_key=context.location_key,
            action_type=action.action_type,
            target_key=action.target_key,
            gm_decision_type=gm_decision.decision_type,
        )

        branch = QuantumBranch(
            branch_key=branch_key,
            action=action,
            gm_decision=gm_decision,
            variants=variants,
            generated_at=datetime.now(),
            generation_time_ms=generation_time_ms,
        )

        logger.info(
            f"Generated branch {branch_key} with {len(variants)} variants "
            f"in {generation_time_ms:.0f}ms"
        )

        return branch

    async def generate_branches(
        self,
        action: ActionPrediction,
        gm_decisions: list[GMDecision],
        manifest: GroundingManifest,
        context: BranchContext,
    ) -> list[QuantumBranch]:
        """Generate branches for multiple GM decisions.

        Args:
            action: The predicted action
            gm_decisions: List of possible GM decisions
            manifest: Grounding manifest
            context: Generation context

        Returns:
            List of QuantumBranch objects
        """
        branches = []

        for decision in gm_decisions:
            try:
                branch = await self.generate_branch(
                    action, decision, manifest, context
                )
                branches.append(branch)
            except Exception as e:
                logger.error(f"Failed to generate branch for {decision.decision_type}: {e}")

        return branches

    def _get_system_prompt(self) -> str:
        """Get the system prompt for branch generation."""
        return """You are a Game Master generating narrative outcomes for a fantasy RPG.

Your task is to generate multiple outcome variants for a player action. Each variant should:
1. Be written in second person ("You...", "Your...")
2. Use [entity_key:display_name] format for ALL entity references
3. Be immersive and atmospheric
4. Include sensory details (sight, sound, smell)
5. Avoid meta-commentary or questions to the player
6. Be 2-4 sentences for most outcomes

For skill checks, generate both success and failure variants. The dice roll happens at runtime.

State deltas should capture meaningful changes:
- create_entity: New items or NPCs introduced
- update_entity: Changes to existing entities (health, state)
- transfer_item: Items changing hands
- record_fact: New information learned
- advance_time: How much time passed

CRITICAL: All entity references MUST use [key:text] format. Never mention an entity without this format."""

    def _build_generation_prompt(
        self,
        action: ActionPrediction,
        gm_decision: GMDecision,
        manifest: GroundingManifest,
        context: BranchContext,
    ) -> str:
        """Build the prompt for variant generation.

        Args:
            action: The predicted action
            gm_decision: GM's decision
            manifest: Scene manifest
            context: Generation context

        Returns:
            Prompt string
        """
        # Build entity reference list
        entities_list = self._format_entities(manifest)

        # Build action description
        action_desc = self._describe_action(action, manifest)

        # Build twist context if applicable
        twist_context = ""
        if gm_decision.decision_type != "no_twist":
            twist_context = f"""
GM TWIST: {gm_decision.decision_type}
Description: {gm_decision.context.get('description', 'A complication occurs')}
Grounding Facts: {', '.join(gm_decision.grounding_facts) if gm_decision.grounding_facts else 'None'}

The twist should naturally emerge from the grounding facts. Do not force it - let it flow from the narrative."""

        prompt = f"""Generate narrative variants for this player action.

SCENE: {context.location_display}
TIME: Day {context.game_day}, {context.game_time}
{entities_list}

PLAYER ACTION: {action_desc}
{twist_context}

Generate outcome variants as JSON. Include:
- "success": The action succeeds as intended
- "failure": The action fails (if a skill check is reasonable)
- "critical_success": Exceptional success with bonus (if dice are involved)
- "critical_failure": Bad failure with complication (if dice are involved)

For each variant provide:
1. narrative: Full prose (use [entity_key:display_name] for ALL entities)
2. state_deltas: Array of state changes
3. time_passed_minutes: How long this takes (1-60 minutes)
4. requires_skill_check: true/false
5. skill: Which skill (if check required)
6. dc: Difficulty class (if check required)

Example narrative format:
"You approach [innkeeper_tom:Old Tom] and ask about rooms. He sets down [ale_mug_001:the mug] and smiles warmly."

Generate the JSON response now."""

        return prompt

    def _format_entities(self, manifest: GroundingManifest) -> str:
        """Format entities for the prompt.

        Args:
            manifest: Grounding manifest

        Returns:
            Formatted entity string
        """
        lines = ["AVAILABLE ENTITIES (use [key:name] format):"]

        if manifest.npcs:
            lines.append("NPCs:")
            for key, entity in manifest.npcs.items():
                lines.append(f"  - [{key}:{entity.display_name}] - {entity.short_description}")

        if manifest.items_at_location:
            lines.append("Items at location:")
            for key, entity in manifest.items_at_location.items():
                lines.append(f"  - [{key}:{entity.display_name}]")

        if manifest.inventory:
            lines.append("Player inventory:")
            for key, entity in manifest.inventory.items():
                lines.append(f"  - [{key}:{entity.display_name}]")

        if manifest.exits:
            lines.append("Exits:")
            for key, entity in manifest.exits.items():
                lines.append(f"  - [{key}:{entity.display_name}]")

        return "\n".join(lines)

    def _describe_action(
        self, action: ActionPrediction, manifest: GroundingManifest
    ) -> str:
        """Describe the action in natural language.

        Args:
            action: The action prediction
            manifest: Scene manifest

        Returns:
            Action description string
        """
        action_type = action.action_type
        target_key = action.target_key

        if action_type == ActionType.INTERACT_NPC:
            target = manifest.npcs.get(target_key) if target_key else None
            target_name = f"[{target_key}:{target.display_name}]" if target else "an NPC"
            return f"Talk to/interact with {target_name}"

        elif action_type == ActionType.MANIPULATE_ITEM:
            target = manifest.items_at_location.get(target_key) or manifest.inventory.get(target_key)
            if target:
                target_name = f"[{target_key}:{target.display_name}]"
            else:
                target_name = "an item"
            item_action = action.context.get("action", "interact with")
            return f"{item_action.capitalize()} {target_name}"

        elif action_type == ActionType.MOVE:
            target = manifest.exits.get(target_key) if target_key else None
            target_name = f"[{target_key}:{target.display_name}]" if target else "another location"
            return f"Travel to {target_name}"

        elif action_type == ActionType.OBSERVE:
            return "Look around and observe the surroundings"

        elif action_type == ActionType.SKILL_USE:
            skill = action.context.get("skill", "a skill")
            return f"Use {skill}"

        elif action_type == ActionType.COMBAT:
            return "Engage in combat"

        elif action_type == ActionType.WAIT:
            return "Wait and pass time"

        else:
            return f"Perform {action_type.value}"

    def _parse_variants(
        self, response: BranchGenerationResponse
    ) -> dict[str, OutcomeVariant]:
        """Parse LLM response into OutcomeVariant objects.

        Args:
            response: Structured response from LLM

        Returns:
            Dict mapping variant_type to OutcomeVariant
        """
        variants = {}

        for gen_variant in response.variants:
            try:
                variant_type = VariantType(gen_variant.variant_type)
            except ValueError:
                logger.warning(f"Unknown variant type: {gen_variant.variant_type}")
                continue

            # Parse state deltas
            state_deltas = []
            for gen_delta in gen_variant.state_deltas:
                try:
                    delta_type = DeltaType(gen_delta.delta_type)
                    state_deltas.append(StateDelta(
                        delta_type=delta_type,
                        target_key=gen_delta.target_key,
                        changes=gen_delta.changes,
                    ))
                except ValueError:
                    logger.warning(f"Unknown delta type: {gen_delta.delta_type}")

            variant = OutcomeVariant(
                variant_type=variant_type,
                requires_dice=gen_variant.requires_skill_check,
                skill=gen_variant.skill,
                dc=gen_variant.dc,
                narrative=gen_variant.narrative,
                state_deltas=state_deltas,
                time_passed_minutes=gen_variant.time_passed_minutes,
            )

            variants[variant_type.value] = variant

        return variants

    def _generate_fallback_variants(
        self,
        action: ActionPrediction,
        gm_decision: GMDecision,
    ) -> dict[str, OutcomeVariant]:
        """Generate minimal fallback variants when LLM fails.

        Args:
            action: The predicted action
            gm_decision: GM's decision

        Returns:
            Dict with basic success/failure variants
        """
        # Basic success variant
        success_narrative = f"You successfully {action.action_type.value.replace('_', ' ')}."
        if action.target_key:
            success_narrative = f"You successfully interact with {action.target_key}."

        variants = {
            "success": OutcomeVariant(
                variant_type=VariantType.SUCCESS,
                requires_dice=False,
                narrative=success_narrative,
                state_deltas=[],
                time_passed_minutes=1,
            ),
        }

        # Add failure variant for actions that might need skill checks
        if action.action_type in [ActionType.SKILL_USE, ActionType.COMBAT, ActionType.MANIPULATE_ITEM]:
            failure_narrative = f"You attempt to {action.action_type.value.replace('_', ' ')} but fail."
            variants["failure"] = OutcomeVariant(
                variant_type=VariantType.FAILURE,
                requires_dice=True,
                skill="general",
                dc=12,
                narrative=failure_narrative,
                state_deltas=[],
                time_passed_minutes=1,
            )

        return variants
