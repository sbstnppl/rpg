"""Probability calculation for the Complication Oracle.

The oracle uses multiple factors to determine complication chance:
1. Base chance (low by default)
2. Story arc phase modifiers (higher during dramatic moments)
3. Action risk tags (dangerous/mysterious/etc. actions are riskier)
4. Cooldown (prevent complication spam)
5. Hard cap (never exceed max probability)
"""

from dataclasses import dataclass

from src.oracle.complication_types import (
    ARC_PHASE_MODIFIERS,
    LOCATION_DANGER_MODIFIERS,
    RISK_TAG_MODIFIERS,
    SUBTURN_MODIFIERS,
)


@dataclass
class ComplicationProbability:
    """Result of probability calculation with breakdown."""

    base_chance: float
    arc_modifier: float
    risk_modifier: float
    cooldown_multiplier: float
    final_chance: float
    breakdown: dict[str, float]  # Detailed breakdown for debugging
    subturn_modifier: float = 0.0  # Modifier based on subturn index in chain
    location_modifier: float = 0.0  # Modifier based on location danger


class ProbabilityCalculator:
    """Calculates complication probability from context.

    Design principles:
    - Low base chance (players shouldn't expect complications)
    - Story-aware (arc phases affect drama)
    - Risk-aware (dangerous actions invite complications)
    - Cooldown-aware (no complication spam)
    - Hard-capped (never too likely)
    """

    def __init__(
        self,
        base_chance: float = 0.05,
        max_chance: float = 0.35,
        cooldown_turns: int = 3,
        cooldown_recovery_turns: int = 6,
    ):
        """Initialize the probability calculator.

        Args:
            base_chance: Starting probability (default 5%)
            max_chance: Maximum probability cap (default 35%)
            cooldown_turns: Full cooldown period after complication
            cooldown_recovery_turns: Turns until cooldown fully recovers
        """
        self.base_chance = base_chance
        self.max_chance = max_chance
        self.cooldown_turns = cooldown_turns
        self.cooldown_recovery_turns = cooldown_recovery_turns

    def calculate(
        self,
        risk_tags: list[str],
        arc_phase: str | None = None,
        arc_tension: int | None = None,
        turns_since_complication: int | None = None,
        subturn_index: int = 0,
        location_danger: str = "neutral",
    ) -> ComplicationProbability:
        """Calculate complication probability.

        Args:
            risk_tags: Tags from validation results (e.g., ["dangerous", "mysterious"])
            arc_phase: Current story arc phase (e.g., "climax")
            arc_tension: Current tension level (0-100)
            turns_since_complication: Turns since last complication
            subturn_index: 0-indexed position in multi-action chain
            location_danger: Danger level of current location

        Returns:
            ComplicationProbability with calculated chance and breakdown.
        """
        breakdown: dict[str, float] = {}

        # 1. Base chance
        chance = self.base_chance
        breakdown["base"] = self.base_chance

        # 2. Arc phase modifier
        arc_modifier = 0.0
        if arc_phase:
            arc_modifier = ARC_PHASE_MODIFIERS.get(arc_phase.lower(), 0.0)
        breakdown["arc_phase"] = arc_modifier

        # 3. Arc tension modifier (higher tension = slightly higher chance)
        tension_modifier = 0.0
        if arc_tension is not None and arc_tension > 50:
            # Add up to 5% at tension 100
            tension_modifier = (arc_tension - 50) / 50 * 0.05
        breakdown["arc_tension"] = tension_modifier

        # 4. Risk tag modifiers
        risk_modifier = 0.0
        for tag in risk_tags:
            tag_mod = RISK_TAG_MODIFIERS.get(tag.lower(), 0.0)
            risk_modifier += tag_mod
            breakdown[f"risk_{tag}"] = tag_mod

        # 5. Subturn index modifier (later actions in chain have higher chance)
        subturn_modifier = SUBTURN_MODIFIERS.get(
            min(subturn_index, 4), SUBTURN_MODIFIERS[4]
        )
        breakdown["subturn_index"] = subturn_modifier

        # 6. Location danger modifier
        location_modifier = LOCATION_DANGER_MODIFIERS.get(
            location_danger.lower(), 0.0
        )
        breakdown["location_danger"] = location_modifier

        # Sum modifiers
        chance += (
            arc_modifier
            + tension_modifier
            + risk_modifier
            + subturn_modifier
            + location_modifier
        )

        # 7. Cooldown multiplier
        cooldown_multiplier = 1.0
        if turns_since_complication is not None:
            if turns_since_complication < self.cooldown_turns:
                # Full cooldown - very unlikely
                cooldown_multiplier = 0.2
            elif turns_since_complication < self.cooldown_recovery_turns:
                # Partial recovery
                recovery_progress = (
                    turns_since_complication - self.cooldown_turns
                ) / (self.cooldown_recovery_turns - self.cooldown_turns)
                cooldown_multiplier = 0.2 + (0.8 * recovery_progress)

        breakdown["cooldown_multiplier"] = cooldown_multiplier

        # Apply cooldown
        chance *= cooldown_multiplier

        # 8. Hard cap
        final_chance = min(chance, self.max_chance)
        breakdown["capped"] = self.max_chance if chance > self.max_chance else 0.0

        return ComplicationProbability(
            base_chance=self.base_chance,
            arc_modifier=arc_modifier + tension_modifier,
            risk_modifier=risk_modifier,
            subturn_modifier=subturn_modifier,
            location_modifier=location_modifier,
            cooldown_multiplier=cooldown_multiplier,
            final_chance=final_chance,
            breakdown=breakdown,
        )


def should_trigger_complication(probability: ComplicationProbability) -> bool:
    """Determine if a complication should trigger.

    Args:
        probability: Calculated probability result.

    Returns:
        True if complication should occur.
    """
    import random

    return random.random() < probability.final_chance
