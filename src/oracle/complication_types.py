"""Complication types and dataclasses for the oracle system.

Complications add narrative interest without breaking mechanics:
- DISCOVERY: Learn something new (a secret, a clue, an opportunity)
- INTERRUPTION: Situation changes (NPC arrives, weather shifts, timer starts)
- COST: Success with a price (resource consumed, attention drawn)
- TWIST: Story revelation (foreshadowing pays off, hidden truth revealed)

Item spawn decisions:
- SPAWN: Create item normally in game state
- PLOT_HOOK_MISSING: Don't spawn, item is mysteriously absent (creates intrigue)
- PLOT_HOOK_RELOCATED: Spawn elsewhere (e.g., bandit camp) (creates quest hook)
- DEFER: Track but don't spawn yet (decorative items, spawn on-demand later)

NPC spawn decisions:
- SPAWN: Create NPC with full generation (CRITICAL + named SUPPORTING NPCs)
- DEFER: Track in mentioned_npcs, don't spawn (BACKGROUND NPCs)
- PLOT_HOOK_ABSENT: NPC is mysteriously absent (triggers re-narration)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.narrator.item_extractor import ExtractedItem
    from src.narrator.npc_extractor import ExtractedNPC


class ItemSpawnDecision(str, Enum):
    """Decisions oracle can make about item spawning.

    When the narrator mentions an item that doesn't exist in game state,
    the oracle decides what to do with it.
    """

    SPAWN = "spawn"  # Create item normally
    PLOT_HOOK_MISSING = "plot_hook_missing"  # Don't spawn, create mystery (item is absent)
    PLOT_HOOK_RELOCATED = "plot_hook_relocated"  # Spawn elsewhere (creates quest hook)
    DEFER = "defer"  # Track but don't spawn yet (for decorative items)


@dataclass
class ItemSpawnResult:
    """Result of oracle evaluating an item spawn decision.

    Attributes:
        item_name: Name of the item being evaluated.
        decision: The oracle's spawn decision.
        reasoning: Explanation of why this decision was made.
        spawn_location: For RELOCATED, where the item should be spawned.
        plot_hook_description: For PLOT_HOOK variants, description of the hook.
        new_facts: Facts to record about this decision (e.g., "bucket was stolen").
    """

    item_name: str
    decision: ItemSpawnDecision
    reasoning: str
    spawn_location: str | None = None
    plot_hook_description: str | None = None
    new_facts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "item_name": self.item_name,
            "decision": self.decision.value,
            "reasoning": self.reasoning,
            "spawn_location": self.spawn_location,
            "plot_hook_description": self.plot_hook_description,
            "new_facts": self.new_facts,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ItemSpawnResult":
        """Create from dictionary."""
        return cls(
            item_name=data["item_name"],
            decision=ItemSpawnDecision(data["decision"]),
            reasoning=data["reasoning"],
            spawn_location=data.get("spawn_location"),
            plot_hook_description=data.get("plot_hook_description"),
            new_facts=data.get("new_facts", []),
        )


class NPCSpawnDecision(str, Enum):
    """Decisions oracle can make about NPC spawning.

    When the narrator mentions an NPC that doesn't exist in game state,
    the oracle decides what to do with them.
    """

    SPAWN = "spawn"  # Create NPC with full generation (CRITICAL + named SUPPORTING)
    DEFER = "defer"  # Track in mentioned_npcs, don't spawn (BACKGROUND)
    PLOT_HOOK_ABSENT = "plot_hook_absent"  # NPC is mysteriously absent (re-narrate)


@dataclass
class NPCSpawnResult:
    """Result of oracle evaluating an NPC spawn decision.

    Attributes:
        npc_name: Name of the NPC being evaluated.
        decision: The oracle's spawn decision.
        reasoning: Explanation of why this decision was made.
        plot_hook_description: For PLOT_HOOK_ABSENT, description of the absence.
        new_facts: Facts to record about this decision.
    """

    npc_name: str
    decision: NPCSpawnDecision
    reasoning: str
    plot_hook_description: str | None = None
    new_facts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "npc_name": self.npc_name,
            "decision": self.decision.value,
            "reasoning": self.reasoning,
            "plot_hook_description": self.plot_hook_description,
            "new_facts": self.new_facts,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NPCSpawnResult":
        """Create from dictionary."""
        return cls(
            npc_name=data["npc_name"],
            decision=NPCSpawnDecision(data["decision"]),
            reasoning=data["reasoning"],
            plot_hook_description=data.get("plot_hook_description"),
            new_facts=data.get("new_facts", []),
        )


class ComplicationType(str, Enum):
    """Types of complications the oracle can introduce."""

    DISCOVERY = "discovery"  # Learn something new
    INTERRUPTION = "interruption"  # Situation changes
    COST = "cost"  # Success with price
    TWIST = "twist"  # Story revelation


class EffectType(str, Enum):
    """Types of mechanical effects a complication can have."""

    HP_LOSS = "hp_loss"  # Minor damage
    HP_GAIN = "hp_gain"  # Minor healing
    RESOURCE_LOSS = "resource_loss"  # Lose gold, item, etc.
    RESOURCE_GAIN = "resource_gain"  # Gain item, gold
    STATUS_ADD = "status_add"  # Gain a status condition
    STATUS_REMOVE = "status_remove"  # Lose a status condition
    RELATIONSHIP_CHANGE = "relationship_change"  # Attitude shift
    TIME_ADVANCE = "time_advance"  # Time passes
    SPAWN_ENTITY = "spawn_entity"  # New NPC/creature appears
    REVEAL_FACT = "reveal_fact"  # World fact becomes known
    TENSION_CHANGE = "tension_change"  # Story arc tension shifts


@dataclass
class Effect:
    """A mechanical effect from a complication.

    Effects are small, contained changes that don't fundamentally
    alter the game state but add consequence to the narrative.
    """

    type: EffectType
    target: str | None = None  # Entity key, item key, etc.
    value: int | str | None = None  # Amount or value
    metadata: dict = field(default_factory=dict)  # Additional data

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "type": self.type.value,
            "target": self.target,
            "value": self.value,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Effect":
        """Create from dictionary."""
        return cls(
            type=EffectType(data["type"]),
            target=data.get("target"),
            value=data.get("value"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Complication:
    """A narrative complication introduced by the oracle.

    Complications ADD to the narrative without preventing player actions.
    They create hooks for future player choices and add dramatic interest.

    Key constraints:
    - Player actions ALWAYS succeed (if validated)
    - Complications happen AFTER or ALONGSIDE success
    - Effects are minor (no instant death, no critical resource loss)
    - Must fit established world facts
    """

    type: ComplicationType
    description: str  # What happens (for narrative)
    mechanical_effects: list[Effect] = field(default_factory=list)
    new_facts: list[str] = field(default_factory=list)  # Facts to persist
    interrupts_action: bool = False  # If True, happens BEFORE action completes
    source_arc_key: str | None = None  # Related story arc
    foreshadowing: str | None = None  # Hint about future consequences

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "type": self.type.value,
            "description": self.description,
            "mechanical_effects": [e.to_dict() for e in self.mechanical_effects],
            "new_facts": self.new_facts,
            "interrupts_action": self.interrupts_action,
            "source_arc_key": self.source_arc_key,
            "foreshadowing": self.foreshadowing,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Complication":
        """Create from dictionary."""
        return cls(
            type=ComplicationType(data["type"]),
            description=data["description"],
            mechanical_effects=[
                Effect.from_dict(e) for e in data.get("mechanical_effects", [])
            ],
            new_facts=data.get("new_facts", []),
            interrupts_action=data.get("interrupts_action", False),
            source_arc_key=data.get("source_arc_key"),
            foreshadowing=data.get("foreshadowing"),
        )


# Risk tags that increase complication chance
RISK_TAG_MODIFIERS: dict[str, float] = {
    "dangerous": 0.10,  # High-risk action
    "mysterious": 0.08,  # Unknown territory
    "valuable": 0.06,  # High-value target
    "forbidden": 0.12,  # Breaking rules/laws
    "magical": 0.07,  # Magic is unpredictable
    "social": 0.05,  # Social interaction has nuances
    "stealthy": 0.08,  # Stealth can go wrong
    "aggressive": 0.09,  # Violence has consequences
    "sacred": 0.10,  # Divine attention
    "cursed": 0.15,  # Already under bad fortune
}

# Arc phase modifiers - more complications during dramatic phases
ARC_PHASE_MODIFIERS: dict[str, float] = {
    "setup": 0.02,  # Few complications early
    "rising_action": 0.05,  # Building tension
    "midpoint": 0.08,  # Major turning point
    "escalation": 0.10,  # Stakes are high
    "climax": 0.15,  # Maximum drama
    "falling_action": 0.05,  # Wrapping up
    "resolution": 0.02,  # Few surprises
    "aftermath": 0.03,  # Mild complications for hooks
}

# Subturn modifiers - later actions in a chain have higher interrupt chance
# This creates natural "things can go wrong during longer journeys" feel
SUBTURN_MODIFIERS: dict[int, float] = {
    0: 0.0,    # First action - no modifier
    1: 0.02,   # Second action - slight increase
    2: 0.05,   # Third action - moderate increase
    3: 0.08,   # Fourth action - notable increase
    4: 0.12,   # Fifth+ action - maximum modifier
}

# Location danger modifiers - some places are inherently riskier
LOCATION_DANGER_MODIFIERS: dict[str, float] = {
    "safe": -0.05,      # Home, temple, church - actually reduces chance
    "neutral": 0.0,     # Town square, market, tavern
    "risky": 0.08,      # Forest, road at night, wilderness
    "dangerous": 0.15,  # Dungeon, cave, crypt, monster lair
    "hostile": 0.25,    # Enemy territory, active combat zone
}
