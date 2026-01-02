"""Semantic Reasoning Engine for the Quantum Pipeline (Phase 2).

Phase 2 of the split architecture. Uses the reasoning model (qwen3) to:
1. Determine WHAT happens (semantic outcome, not prose)
2. Identify new things created (display names only)
3. Describe changes in plain English
4. Determine skill check requirements

The key insight is that we separate reasoning (what happens logically)
from narration (how to describe it creatively). This allows:
- Deterministic delta translation from semantic changes
- Creative prose generation grounded to verified deltas
- No hallucinated entity keys (Phase 3 generates them)
"""

import logging
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from src.llm.base import LLMProvider
from src.llm.factory import get_reasoning_provider
from src.llm.message_types import Message
from src.world_server.quantum.intent import IntentClassification
from src.world_server.quantum.schemas import ActionType, VariantType

logger = logging.getLogger(__name__)


# =============================================================================
# Semantic Change Types
# =============================================================================


class SemanticChangeType:
    """Types of semantic changes that can occur.

    These are plain English descriptions of what happens,
    NOT delta types. The delta translator converts these to deltas.
    """

    GIVE_ITEM = "give_item"  # Someone gives something to someone
    TAKE_ITEM = "take_item"  # Someone takes something
    CREATE_ITEM = "create_item"  # Something new appears/is created
    DESTROY_ITEM = "destroy_item"  # Something is destroyed/consumed
    MOVE_ENTITY = "move_entity"  # Someone/something moves
    LEARN_INFO = "learn_info"  # Character learns information
    CHANGE_RELATIONSHIP = "change_relationship"  # Relationship changes
    CHANGE_STATE = "change_state"  # Entity state changes
    TRIGGER_EVENT = "trigger_event"  # Something happens in the world


# =============================================================================
# LLM Response Schemas
# =============================================================================


class SemanticChange(BaseModel):
    """A single semantic change in plain English.

    This describes WHAT happens without specifying entity keys.
    The delta translator will convert this to proper StateDelta objects.
    """

    change_type: str = Field(
        description="Type of change: give_item, take_item, create_item, destroy_item, "
        "move_entity, learn_info, change_relationship, change_state, trigger_event"
    )
    description: str = Field(
        description="Plain English description of what happens. "
        "Use display names (e.g., 'Old Tom gives the player a mug of ale')"
    )
    actor: str | None = Field(
        default=None,
        description="Who/what causes this change (display name)",
    )
    target: str | None = Field(
        default=None,
        description="Who/what is affected (display name)",
    )
    object_involved: str | None = Field(
        default=None,
        description="Item or object involved (display name)",
    )


class SemanticOutcome(BaseModel):
    """The semantic outcome of an action (Phase 2 output).

    This describes WHAT happens in plain English, without:
    - Entity keys (those are generated in Phase 3)
    - Prose/narrative (that's generated in Phase 4)

    The reasoning model focuses purely on logical consequences.
    """

    what_happens: str = Field(
        description="One sentence summary of what happens. "
        "Example: 'The bartender serves the player a mug of honeyed ale'"
    )
    outcome_type: str = Field(
        description="Type of outcome: success, failure, partial_success, "
        "critical_success, critical_failure"
    )
    new_things: list[str] = Field(
        default_factory=list,
        description="Display names of NEW things created/appearing. "
        "Example: ['a mug of honeyed ale', 'a small key']",
    )
    changes: list[SemanticChange] = Field(
        default_factory=list,
        description="List of semantic changes that occur",
    )

    # Skill check info (for variants)
    requires_skill_check: bool = Field(
        default=False,
        description="Whether this action requires a skill check",
    )
    skill_name: str | None = Field(
        default=None,
        description="Name of the skill to check (e.g., 'Persuasion', 'Athletics')",
    )
    difficulty: str | None = Field(
        default=None,
        description="Difficulty level: trivial, easy, medium, hard, very_hard, extreme",
    )

    # Time
    time_description: str = Field(
        default="a moment",
        description="How long this takes in natural language. "
        "Examples: 'a moment', 'a few minutes', 'about an hour'",
    )


class ReasoningResponse(BaseModel):
    """Full response from the reasoning LLM call.

    When an action requires a skill check, we generate multiple variants.
    Otherwise, just the success outcome.
    """

    requires_skill_check: bool = Field(
        default=False,
        description="Whether this action requires a skill check",
    )
    skill_name: str | None = Field(
        default=None,
        description="Name of the skill to check",
    )
    difficulty: str | None = Field(
        default=None,
        description="Difficulty: trivial, easy, medium, hard, very_hard, extreme",
    )

    # Outcomes - success always present, others conditional
    success: SemanticOutcome = Field(
        description="What happens on success (or if no skill check needed)"
    )
    failure: SemanticOutcome | None = Field(
        default=None,
        description="What happens on failure (only if skill check required)",
    )
    critical_success: SemanticOutcome | None = Field(
        default=None,
        description="What happens on critical success (nat 20, etc.)",
    )
    critical_failure: SemanticOutcome | None = Field(
        default=None,
        description="What happens on critical failure (nat 1, etc.)",
    )


# =============================================================================
# System Prompt
# =============================================================================

REASONING_SYSTEM_PROMPT = """You are a game master reasoning about the logical consequences of player actions in a fantasy RPG.

Your job is to determine WHAT HAPPENS, not how to describe it. Focus on:
1. What is the logical outcome of this action?
2. Does it require a skill check? If so, what skill and difficulty?
3. What new things are created (items, NPCs)?
4. What changes occur in the world?

## Rules

1. **Use display names, NOT entity keys**
   - Good: "Old Tom", "a mug of ale", "the village square"
   - Bad: "innkeeper_tom", "ale_001", "loc_village_square"

2. **Be specific about new things**
   - If an item is given, describe what it looks like
   - Example: "a mug of honeyed ale" not just "ale"

3. **Skill checks**
   - Only require skill checks for non-trivial actions
   - Talking to a friendly NPC: no check
   - Persuading a suspicious guard: check (Persuasion)
   - Picking a simple lock: check (Lockpicking)
   - Walking to another location: no check
   - Climbing a slippery wall: check (Athletics)

4. **Difficulty levels**
   - trivial: Anyone could do it (DC 5)
   - easy: Most people could do it (DC 10)
   - medium: Requires some skill (DC 15)
   - hard: Challenging even for skilled (DC 20)
   - very_hard: Expert level (DC 25)
   - extreme: Near impossible (DC 30)

5. **Time estimates**
   Use natural language:
   - "a moment" (instant, <1 min)
   - "a few seconds" (1-10 seconds)
   - "a minute or two" (1-5 min)
   - "several minutes" (5-15 min)
   - "about half an hour" (15-45 min)
   - "about an hour" (45-90 min)
   - "a few hours" (2-4 hours)

6. **Failure outcomes**
   - Failures should be interesting, not just "nothing happens"
   - Could reveal information, create complications, or partial success
   - Critical failures should have consequences but not be unfair

7. **Critical outcomes**
   - Critical success: Exceptional result, bonus effects
   - Critical failure: Complication or setback, but survivable
"""


# =============================================================================
# Reasoning Engine
# =============================================================================


@dataclass
class ReasoningContext:
    """Context provided to the reasoning engine."""

    # Action being performed
    action_type: ActionType
    action_summary: str  # "talk to Old Tom about ale"
    topic: str | None = None

    # Location context
    location_display: str = ""
    location_description: str = ""

    # Available entities (display names)
    npcs_present: list[str] = field(default_factory=list)
    items_available: list[str] = field(default_factory=list)
    exits_available: list[str] = field(default_factory=list)

    # Recent history for context
    recent_events: list[str] = field(default_factory=list)

    # Player info
    player_name: str = "the player"


@dataclass
class ReasoningEngine:
    """LLM-based reasoning engine for determining action outcomes.

    Uses the reasoning model (qwen3) to determine what happens,
    generating semantic outcomes that can be translated to deltas.
    """

    llm: LLMProvider | None = None

    def __post_init__(self) -> None:
        """Initialize with default provider if not provided."""
        if self.llm is None:
            self.llm = get_reasoning_provider()

    async def reason(
        self,
        context: ReasoningContext,
        intent: IntentClassification | None = None,
    ) -> ReasoningResponse:
        """Determine the semantic outcome of an action.

        Args:
            context: Context about the action and scene.
            intent: Optional intent classification for additional context.

        Returns:
            ReasoningResponse with outcomes for each variant.
        """
        prompt = self._build_prompt(context, intent)

        try:
            response = await self.llm.complete_structured(
                messages=[Message.user(prompt)],
                response_schema=ReasoningResponse,
                system_prompt=REASONING_SYSTEM_PROMPT,
                temperature=0.3,  # Some creativity for outcomes
                max_tokens=1024,
            )

            if response.parsed_content is None:
                logger.warning("Reasoning engine returned no parsed content")
                return self._fallback_response(context)

            # Handle dict response (some providers return dict instead of Pydantic model)
            result = response.parsed_content
            if isinstance(result, dict):
                result = ReasoningResponse(**result)

            return result

        except Exception as e:
            logger.error(f"Reasoning engine failed: {e}")
            return self._fallback_response(context)

    def _build_prompt(
        self,
        context: ReasoningContext,
        intent: IntentClassification | None,
    ) -> str:
        """Build the reasoning prompt."""
        lines = [
            "## Action",
            f"**{context.action_summary}**",
            "",
        ]

        if context.topic:
            lines.append(f"Topic: {context.topic}")
            lines.append("")

        lines.extend(
            [
                f"## Location: {context.location_display}",
                "",
            ]
        )

        if context.location_description:
            lines.append(context.location_description)
            lines.append("")

        # Scene context
        if context.npcs_present:
            lines.append(f"**NPCs present:** {', '.join(context.npcs_present)}")
        if context.items_available:
            lines.append(f"**Items available:** {', '.join(context.items_available)}")
        if context.exits_available:
            lines.append(f"**Exits:** {', '.join(context.exits_available)}")

        if context.recent_events:
            lines.extend(["", "## Recent Events"])
            for event in context.recent_events[-3:]:
                lines.append(f"- {event}")

        lines.extend(
            [
                "",
                "## Task",
                "Determine what happens when the player performs this action.",
                "If a skill check is needed, provide outcomes for success, failure, "
                "and critical results.",
                "If no skill check is needed, just provide the success outcome.",
            ]
        )

        return "\n".join(lines)

    def _fallback_response(self, context: ReasoningContext) -> ReasoningResponse:
        """Create a fallback response when LLM fails."""
        return ReasoningResponse(
            requires_skill_check=False,
            success=SemanticOutcome(
                what_happens=f"The player attempts to {context.action_summary}",
                outcome_type="success",
                new_things=[],
                changes=[],
                time_description="a moment",
            ),
        )

    def outcome_to_variant_type(self, outcome: SemanticOutcome) -> VariantType:
        """Convert outcome_type string to VariantType enum."""
        mapping = {
            "success": VariantType.SUCCESS,
            "failure": VariantType.FAILURE,
            "partial_success": VariantType.PARTIAL_SUCCESS,
            "critical_success": VariantType.CRITICAL_SUCCESS,
            "critical_failure": VariantType.CRITICAL_FAILURE,
        }
        return mapping.get(outcome.outcome_type, VariantType.SUCCESS)


# =============================================================================
# Helper Functions
# =============================================================================


def build_reasoning_context(
    action_type: ActionType,
    action_summary: str,
    location_display: str,
    location_description: str = "",
    npcs: list[str] | None = None,
    items: list[str] | None = None,
    exits: list[str] | None = None,
    topic: str | None = None,
    recent_events: list[str] | None = None,
) -> ReasoningContext:
    """Build ReasoningContext from components.

    Convenience function for creating reasoning context from
    individual components rather than constructing the dataclass directly.
    """
    return ReasoningContext(
        action_type=action_type,
        action_summary=action_summary,
        topic=topic,
        location_display=location_display,
        location_description=location_description,
        npcs_present=npcs or [],
        items_available=items or [],
        exits_available=exits or [],
        recent_events=recent_events or [],
    )


def difficulty_to_dc(difficulty: str | None) -> int:
    """Convert difficulty string to numeric DC."""
    mapping = {
        "trivial": 5,
        "easy": 10,
        "medium": 15,
        "hard": 20,
        "very_hard": 25,
        "extreme": 30,
    }
    return mapping.get(difficulty or "medium", 15)


def time_description_to_minutes(description: str) -> int:
    """Convert natural language time to minutes.

    This is an approximate conversion for game mechanics.
    """
    description = description.lower()

    if "moment" in description or "instant" in description:
        return 1
    if "second" in description:
        return 1
    if "minute or two" in description:
        return 2
    if "few minutes" in description or "several minutes" in description:
        return 10
    if "half hour" in description or "half an hour" in description:
        return 30
    if "hour" in description and "few" in description:
        return 180
    if "hour" in description:
        return 60
    if "day" in description:
        return 1440

    # Default to a few minutes
    return 5


# =============================================================================
# Ref-Based Schemas (New Architecture)
# =============================================================================


class RefBasedChange(BaseModel):
    """A semantic change using single-letter refs for entity identification.

    Entity-based changes use refs (A, B, C) for unambiguous resolution.
    Non-entity changes use direct values (destination, duration, etc.).

    Entity-based change types:
    - take_item: Player takes an item (entity ref)
    - give_item: Transfer item from one entity to another
    - destroy_item: Item is consumed/destroyed
    - change_state: Entity state changes (e.g., door locked -> unlocked)
    - change_relationship: Relationship with NPC changes

    Non-entity change types:
    - advance_time: Time passes (duration)
    - move_to: Player moves to location (destination)
    - learn_info: Player learns information (fact)
    - update_need: Player need changes (need, change)
    - create_entity: New entity appears (description, entity_type)
    """

    change_type: str = Field(
        description="Type: take_item, give_item, destroy_item, change_state, "
        "change_relationship, advance_time, move_to, learn_info, update_need, create_entity"
    )

    # Entity-based (use refs like "A", "B", "C")
    entity: str | None = Field(
        default=None,
        description="Ref of the entity involved (e.g., 'A' for [A] rusty sword)",
    )
    from_entity: str | None = Field(
        default=None,
        description="Ref of source entity for transfers",
    )
    to_entity: str | None = Field(
        default=None,
        description="Ref of target entity for transfers, or 'player'",
    )
    npc: str | None = Field(
        default=None,
        description="Ref of NPC for relationship changes",
    )

    # Non-entity (direct values)
    destination: str | None = Field(
        default=None,
        description="Location key for move_to (e.g., 'village_square')",
    )
    duration: str | None = Field(
        default=None,
        description="Natural language duration for advance_time (e.g., '6 hours')",
    )
    fact: str | None = Field(
        default=None,
        description="Information learned for learn_info",
    )
    need: str | None = Field(
        default=None,
        description="Need name for update_need (e.g., 'fatigue', 'hunger')",
    )
    need_change: str | None = Field(
        default=None,
        description="How the need changes (e.g., 'rested', 'satisfied', 'increases')",
    )
    description: str | None = Field(
        default=None,
        description="Description for create_entity (e.g., 'small campfire')",
    )
    entity_type: str | None = Field(
        default=None,
        description="Type for create_entity: 'item', 'npc', 'object'",
    )
    new_state: str | None = Field(
        default=None,
        description="New state for change_state (e.g., 'broken', 'open', 'lit')",
    )
    delta: str | None = Field(
        default=None,
        description="Relationship delta for change_relationship (e.g., '+trust', '-respect')",
    )


class RefBasedOutcome(BaseModel):
    """Semantic outcome using ref-based entity identification.

    This replaces SemanticOutcome for the ref-based architecture.
    Changes reference entities by their single-letter refs (A, B, C).
    """

    what_happens: str = Field(
        description="One sentence summary of what happens. "
        "Example: 'Player takes the sword from the table'"
    )
    outcome_type: str = Field(
        default="success",
        description="Type: success, failure, partial_success, critical_success, critical_failure",
    )
    changes: list[RefBasedChange] = Field(
        default_factory=list,
        description="List of changes using refs for entity identification",
    )

    # Skill check info
    requires_skill_check: bool = Field(
        default=False,
        description="Whether this action requires a skill check",
    )
    skill_name: str | None = Field(
        default=None,
        description="Skill name if check required (e.g., 'Athletics', 'Persuasion')",
    )
    difficulty: str | None = Field(
        default=None,
        description="Difficulty: trivial, easy, medium, hard, very_hard, extreme",
    )

    # Time
    time_description: str = Field(
        default="a moment",
        description="How long this takes (e.g., 'a moment', '6 hours')",
    )


class RefReasoningResponse(BaseModel):
    """Full response from ref-based reasoning.

    Contains outcomes for success, failure, and critical results.
    """

    requires_skill_check: bool = Field(
        default=False,
        description="Whether this action requires a skill check",
    )
    skill_name: str | None = Field(
        default=None,
        description="Skill name if check required",
    )
    difficulty: str | None = Field(
        default=None,
        description="Difficulty level",
    )

    # Outcomes
    success: RefBasedOutcome = Field(
        description="What happens on success (or if no skill check needed)"
    )
    failure: RefBasedOutcome | None = Field(
        default=None,
        description="What happens on failure",
    )
    critical_success: RefBasedOutcome | None = Field(
        default=None,
        description="What happens on critical success",
    )
    critical_failure: RefBasedOutcome | None = Field(
        default=None,
        description="What happens on critical failure",
    )


# =============================================================================
# Ref-Based System Prompt
# =============================================================================

REF_REASONING_SYSTEM_PROMPT = """You are a game master reasoning about player actions in a fantasy RPG.

Your job is to determine WHAT HAPPENS logically. You will be given a list of entities with single-letter refs.

## Entity References

Entities are identified by refs like [A], [B], [C]:

CHARACTERS:
[A] Greta (the bartender) - behind the bar
[B] Old Tom (a farmer) - sitting by the fire

ITEMS:
[C] rusty sword - on the wooden table
[D] rusty sword - hanging on the wall
[E] mug of ale - on the bar counter

EXITS:
-> village_square (north)
-> back_alley (south)

## Change Types

### Entity-based changes (use refs):

```json
{"change_type": "take_item", "entity": "C"}
{"change_type": "give_item", "entity": "E", "from_entity": "A", "to_entity": "player"}
{"change_type": "destroy_item", "entity": "E"}
{"change_type": "change_state", "entity": "C", "new_state": "broken"}
{"change_type": "change_relationship", "npc": "A", "delta": "+trust"}
```

### Non-entity changes (direct values):

```json
{"change_type": "advance_time", "duration": "6 hours"}
{"change_type": "move_to", "destination": "village_square"}
{"change_type": "learn_info", "fact": "The secret passage is behind the fireplace"}
{"change_type": "update_need", "need": "fatigue", "need_change": "rested"}
{"change_type": "create_entity", "description": "small campfire", "entity_type": "object"}
```

## Rules

1. **Use EXACT refs from the entity list** - "A", "B", "C", NOT "Greta" or "the bartender"
2. **Invalid refs cause errors** - do not invent refs not in the list
3. **Exits use location keys directly** - "village_square", NOT a ref
4. **Empty changes[] is valid** - pure roleplay with no state change is OK
5. **Player is always "player"** - not a ref

## Skill Checks

Only require skill checks for non-trivial actions:
- Talking to friendly NPC: no check
- Persuading suspicious guard: check (Persuasion, medium)
- Picking a lock: check (Lockpicking, varies)
- Climbing slippery wall: check (Athletics, hard)

Difficulties: trivial (DC 5), easy (DC 10), medium (DC 15), hard (DC 20), very_hard (DC 25), extreme (DC 30)

## Time Estimates

Use natural language: "a moment", "a few minutes", "about an hour", "6 hours", etc.

## Failure Outcomes

Failures should be interesting:
- Reveal partial information
- Create complications
- Allow partial success
- Critical failures have consequences but are survivable
"""


# =============================================================================
# Ref-Based Reasoning Context and Engine Methods
# =============================================================================


@dataclass
class RefReasoningContext:
    """Context for ref-based reasoning, including the RefManifest prompt section."""

    action_summary: str  # "take the rusty sword from the table"
    action_type: ActionType

    # Ref manifest formatted for prompt
    entities_prompt: str  # Formatted ENTITIES/EXITS section

    # Location info
    location_display: str = ""
    location_key: str = ""
    location_description: str = ""  # Description of the current location

    # Optional context
    topic: str | None = None
    recent_events: list[str] = field(default_factory=list)
    player_name: str = "the player"


async def reason_with_refs(
    context: RefReasoningContext,
    llm: LLMProvider | None = None,
) -> RefReasoningResponse:
    """Perform ref-based reasoning for an action.

    Args:
        context: RefReasoningContext with entities prompt.
        llm: LLM provider to use (defaults to reasoning provider).

    Returns:
        RefReasoningResponse with outcomes using refs.
    """
    if llm is None:
        llm = get_reasoning_provider()

    prompt = _build_ref_reasoning_prompt(context)

    try:
        response = await llm.complete_structured(
            messages=[Message.user(prompt)],
            response_schema=RefReasoningResponse,
            system_prompt=REF_REASONING_SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=1024,
        )

        if response.parsed_content is None:
            logger.warning("Ref reasoning returned no parsed content")
            return _fallback_ref_response(context)

        result = response.parsed_content
        if isinstance(result, dict):
            result = RefReasoningResponse(**result)

        return result

    except Exception as e:
        logger.error(f"Ref reasoning failed: {e}")
        return _fallback_ref_response(context)


def _build_ref_reasoning_prompt(context: RefReasoningContext) -> str:
    """Build the prompt for ref-based reasoning."""
    lines = [
        "## Action",
        f"**{context.action_summary}**",
        "",
    ]

    if context.topic:
        lines.append(f"Topic: {context.topic}")
        lines.append("")

    lines.extend([
        f"## Location: {context.location_display}",
        "",
        "## Available Entities",
        "",
        context.entities_prompt,
        "",
        "## Task",
        "Determine what happens when the player performs this action.",
        "Use the refs (A, B, C) to identify entities in your changes.",
        "If a skill check is needed, provide outcomes for success, failure, and critical results.",
        "If no skill check is needed, just provide the success outcome.",
    ])

    if context.recent_events:
        lines.insert(-4, "")
        lines.insert(-4, "## Recent Events")
        for event in context.recent_events[-3:]:
            lines.insert(-4, f"- {event}")

    return "\n".join(lines)


def _fallback_ref_response(context: RefReasoningContext) -> RefReasoningResponse:
    """Create a fallback response when LLM fails."""
    return RefReasoningResponse(
        requires_skill_check=False,
        success=RefBasedOutcome(
            what_happens=f"The player attempts to {context.action_summary}",
            outcome_type="success",
            changes=[],
            time_description="a moment",
        ),
    )
