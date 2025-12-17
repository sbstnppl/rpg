"""Complication Oracle for injecting narrative complications.

The oracle determines when and what complications occur during gameplay.
It uses:
- Probability calculation based on context
- LLM generation for creative complication details
- Story arc awareness for narrative coherence
- Cooldown tracking to prevent complication spam
"""

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from src.database.models.narrative import ArcStatus, StoryArc
from src.database.models.session import GameSession
from src.llm.base import LLMProvider
from src.llm.message_types import Message
from src.managers.fact_manager import FactManager
from src.managers.story_arc_manager import StoryArcManager
from src.oracle.complication_types import Complication, ComplicationType, Effect
from src.oracle.probability import (
    ComplicationProbability,
    ProbabilityCalculator,
    should_trigger_complication,
)


@dataclass
class OracleContext:
    """Context for the oracle to make decisions."""

    actions_summary: str  # What the player is doing
    scene_context: str  # Current scene description
    risk_tags: list[str]  # Tags from validation
    active_arc: StoryArc | None  # Current story arc
    relevant_facts: list[str]  # World facts
    turns_since_complication: int | None  # Cooldown tracking


@dataclass
class OracleResult:
    """Result of oracle consultation."""

    complication: Complication | None
    probability: ComplicationProbability
    triggered: bool
    reason: str  # Why or why not


# Default prompt template
COMPLICATION_PROMPT_TEMPLATE = """You are the Complication Oracle for a fantasy RPG.

The player is about to successfully complete these actions:
{actions_summary}

SCENE: {scene_context}
{arc_context}
ESTABLISHED FACTS:
{facts}

Generate ONE complication that:
1. Does NOT prevent any action from succeeding
2. ADDS something interesting (discovery, interruption, cost, or twist)
3. Fits the established world and current story arc
4. Creates a hook for future player choices

COMPLICATION TYPES:
- discovery: Learn something new (a secret, a clue, an opportunity)
- interruption: Situation changes (NPC arrives, weather shifts, timer starts)
- cost: Success with a price (resource consumed, attention drawn)
- twist: Story revelation (foreshadowing pays off, hidden truth revealed)

CONSTRAINTS:
- The player WILL complete their actions successfully
- You can add consequences, discoveries, or interruptions
- You CANNOT contradict established facts
- Keep mechanical effects minor (small HP loss, new information, etc.)
- Do NOT make up dramatic deaths or major plot events

Respond ONLY with valid JSON:
{{
  "type": "discovery|interruption|cost|twist",
  "description": "What happens (2-3 sentences, vivid description)",
  "mechanical_effects": [
    {{"type": "hp_loss|resource_loss|status_add|reveal_fact|spawn_entity", "target": "entity_key", "value": 2}}
  ],
  "new_facts": ["Fact 1 to remember", "Fact 2"],
  "interrupts_action": false,
  "foreshadowing": "Optional hint about future consequences"
}}

If no effects are needed, use: "mechanical_effects": []
If no facts are needed, use: "new_facts": []
"""


class ComplicationOracle:
    """Oracle for determining and generating complications.

    The oracle has two modes:
    1. With LLM: Generates creative, context-aware complications
    2. Without LLM: Uses fallback generation (less creative but functional)
    """

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        llm_provider: LLMProvider | None = None,
        probability_calculator: ProbabilityCalculator | None = None,
    ):
        """Initialize the oracle.

        Args:
            db: Database session.
            game_session: Current game session.
            llm_provider: Optional LLM for creative generation.
            probability_calculator: Custom probability settings.
        """
        self.db = db
        self.game_session = game_session
        self.llm_provider = llm_provider
        self.probability = probability_calculator or ProbabilityCalculator()

        # Managers
        self._fact_manager: FactManager | None = None
        self._arc_manager: StoryArcManager | None = None

    @property
    def fact_manager(self) -> FactManager:
        """Lazy-load fact manager."""
        if self._fact_manager is None:
            self._fact_manager = FactManager(self.db, self.game_session)
        return self._fact_manager

    @property
    def arc_manager(self) -> StoryArcManager:
        """Lazy-load arc manager."""
        if self._arc_manager is None:
            self._arc_manager = StoryArcManager(self.db, self.game_session)
        return self._arc_manager

    async def check(
        self,
        actions_summary: str,
        scene_context: str,
        risk_tags: list[str],
        turns_since_complication: int | None = None,
    ) -> OracleResult:
        """Check if a complication should occur and generate it if so.

        Args:
            actions_summary: Description of actions being taken.
            scene_context: Current scene context.
            risk_tags: Risk tags from action validation.
            turns_since_complication: Turns since last complication.

        Returns:
            OracleResult with complication (if any) and probability info.
        """
        # Get active story arc for context
        active_arc = self._get_active_arc()

        # Calculate probability
        arc_phase = active_arc.current_phase.value if active_arc else None
        arc_tension = active_arc.tension_level if active_arc else None

        prob = self.probability.calculate(
            risk_tags=risk_tags,
            arc_phase=arc_phase,
            arc_tension=arc_tension,
            turns_since_complication=turns_since_complication,
        )

        # Check if complication triggers
        if not should_trigger_complication(prob):
            return OracleResult(
                complication=None,
                probability=prob,
                triggered=False,
                reason=f"Probability {prob.final_chance:.1%} did not trigger",
            )

        # Build context for generation
        relevant_facts = self._get_relevant_facts()
        context = OracleContext(
            actions_summary=actions_summary,
            scene_context=scene_context,
            risk_tags=risk_tags,
            active_arc=active_arc,
            relevant_facts=relevant_facts,
            turns_since_complication=turns_since_complication,
        )

        # Generate complication
        complication = await self._generate_complication(context)

        return OracleResult(
            complication=complication,
            probability=prob,
            triggered=True,
            reason=f"Probability {prob.final_chance:.1%} triggered complication",
        )

    def _get_active_arc(self) -> StoryArc | None:
        """Get the most relevant active story arc."""
        # Find active arcs ordered by priority
        active_arcs = (
            self.db.query(StoryArc)
            .filter(
                StoryArc.session_id == self.game_session.id,
                StoryArc.status == ArcStatus.ACTIVE,
            )
            .order_by(StoryArc.priority.desc())
            .all()
        )

        return active_arcs[0] if active_arcs else None

    def _get_relevant_facts(self, limit: int = 10) -> list[str]:
        """Get recent relevant facts for context."""
        facts = self.fact_manager.list_facts(limit=limit)
        return [f"{f.subject} {f.predicate} {f.value}" for f in facts]

    async def _generate_complication(
        self,
        context: OracleContext,
    ) -> Complication:
        """Generate a complication using LLM or fallback.

        Args:
            context: Oracle context for generation.

        Returns:
            Generated Complication.
        """
        if self.llm_provider is not None:
            return await self._generate_with_llm(context)
        else:
            return self._generate_fallback(context)

    async def _generate_with_llm(
        self,
        context: OracleContext,
    ) -> Complication:
        """Generate complication using LLM.

        Args:
            context: Oracle context.

        Returns:
            Generated Complication.
        """
        # Build arc context string
        arc_context = ""
        if context.active_arc:
            arc = context.active_arc
            arc_context = f"""STORY ARC: {arc.title}
Phase: {arc.current_phase.value}
Tension: {arc.tension_level}/100
Stakes: {arc.stakes or 'Unknown'}"""

        # Build facts string
        facts_str = "\n".join(f"- {f}" for f in context.relevant_facts) or "- None established"

        # Build prompt
        prompt = COMPLICATION_PROMPT_TEMPLATE.format(
            actions_summary=context.actions_summary,
            scene_context=context.scene_context,
            arc_context=arc_context,
            facts=facts_str,
        )

        # Call LLM
        response = await self.llm_provider.complete(
            messages=[Message.user(prompt)],
            temperature=0.8,
            max_tokens=500,
        )

        # Parse response
        try:
            content = response.text if hasattr(response, "text") else str(response)
            # Try to extract JSON from response
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                data = json.loads(json_str)
                return self._parse_complication_response(data, context)
        except (json.JSONDecodeError, KeyError, ValueError):
            pass

        # Fallback if parsing fails
        return self._generate_fallback(context)

    def _parse_complication_response(
        self,
        data: dict[str, Any],
        context: OracleContext,
    ) -> Complication:
        """Parse LLM response into Complication.

        Args:
            data: Parsed JSON response.
            context: Oracle context for additional data.

        Returns:
            Complication instance.
        """
        # Parse effects
        effects = []
        for effect_data in data.get("mechanical_effects", []):
            if isinstance(effect_data, dict) and "type" in effect_data:
                try:
                    effect = Effect.from_dict(effect_data)
                    effects.append(effect)
                except (KeyError, ValueError):
                    continue

        return Complication(
            type=ComplicationType(data.get("type", "discovery")),
            description=data.get("description", "Something unexpected happens."),
            mechanical_effects=effects,
            new_facts=data.get("new_facts", []),
            interrupts_action=data.get("interrupts_action", False),
            source_arc_key=context.active_arc.arc_key if context.active_arc else None,
            foreshadowing=data.get("foreshadowing"),
        )

    def _generate_fallback(self, context: OracleContext) -> Complication:
        """Generate a simple complication without LLM.

        Args:
            context: Oracle context.

        Returns:
            Simple Complication.
        """
        # Pick type based on risk tags
        if "mysterious" in context.risk_tags or "magical" in context.risk_tags:
            comp_type = ComplicationType.DISCOVERY
            descriptions = [
                "You notice something glinting in the shadows nearby.",
                "A faint magical aura lingers in the air around you.",
                "You catch a glimpse of movement at the edge of your vision.",
            ]
        elif "dangerous" in context.risk_tags or "aggressive" in context.risk_tags:
            comp_type = ComplicationType.COST
            descriptions = [
                "The effort leaves you slightly winded.",
                "You feel a twinge of strain from the exertion.",
                "Something scrapes against you, leaving a minor scratch.",
            ]
        elif "social" in context.risk_tags:
            comp_type = ComplicationType.INTERRUPTION
            descriptions = [
                "Someone nearby takes notice of your actions.",
                "You hear footsteps approaching.",
                "A murmur of conversation reaches your ears.",
            ]
        else:
            comp_type = ComplicationType.DISCOVERY
            descriptions = [
                "You notice something unusual about your surroundings.",
                "A detail catches your attention that you hadn't noticed before.",
                "Something here seems different than expected.",
            ]

        description = random.choice(descriptions)

        return Complication(
            type=comp_type,
            description=description,
            mechanical_effects=[],
            new_facts=[],
            interrupts_action=False,
            source_arc_key=context.active_arc.arc_key if context.active_arc else None,
        )

    def get_turns_since_complication(self) -> int | None:
        """Get the number of turns since the last complication.

        Returns:
            Turns since last complication, or None if no complications yet.
        """
        from src.database.models.narrative import (
            ComplicationHistory,
            ComplicationType as DBComplicationType,
        )

        # Get the most recent complication
        latest = (
            self.db.query(ComplicationHistory)
            .filter(ComplicationHistory.session_id == self.game_session.id)
            .order_by(ComplicationHistory.turn_number.desc())
            .first()
        )

        if latest is None:
            return None

        current_turn = self.game_session.total_turns
        return current_turn - latest.turn_number

    async def record_complication(
        self,
        complication: Complication,
        turn_number: int,
        probability: float | None = None,
        risk_tags: list[str] | None = None,
    ) -> None:
        """Record a complication in history for cooldown tracking.

        Args:
            complication: The complication that occurred.
            turn_number: Current turn number.
            probability: The probability that triggered this complication.
            risk_tags: Risk tags that contributed to the probability.
        """
        from src.database.models.narrative import (
            ComplicationHistory,
            ComplicationType as DBComplicationType,
        )

        # Find related story arc
        story_arc_id = None
        if complication.source_arc_key:
            arc = (
                self.db.query(StoryArc)
                .filter(
                    StoryArc.session_id == self.game_session.id,
                    StoryArc.arc_key == complication.source_arc_key,
                )
                .first()
            )
            if arc:
                story_arc_id = arc.id

        # Create history record
        history = ComplicationHistory(
            session_id=self.game_session.id,
            turn_number=turn_number,
            complication_type=DBComplicationType(complication.type.value),
            description=complication.description,
            mechanical_effects=(
                [e.to_dict() for e in complication.mechanical_effects]
                if complication.mechanical_effects
                else None
            ),
            new_facts=complication.new_facts if complication.new_facts else None,
            trigger_probability=probability,
            risk_tags=risk_tags,
            story_arc_id=story_arc_id,
        )
        self.db.add(history)

        # Record new facts
        for fact_text in complication.new_facts:
            # Parse simple "Subject predicate value" format
            parts = fact_text.split(" ", 2)
            if len(parts) >= 3:
                self.fact_manager.record_fact(
                    subject=parts[0],
                    predicate=parts[1],
                    value=parts[2],
                    category="complication",
                )
            else:
                # Record as a simple observation
                self.fact_manager.record_fact(
                    subject="world",
                    predicate="observed",
                    value=fact_text,
                    category="complication",
                )

        self.db.flush()
