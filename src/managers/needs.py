"""Character needs management (hunger, fatigue, hygiene, morale, etc.)."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from sqlalchemy.orm import Session

from src.database.models.character_state import CharacterNeeds, IntimacyProfile
from src.database.models.entities import Entity
from src.database.models.enums import DriveLevel
from src.database.models.session import GameSession
from src.managers.base import BaseManager


class ActivityType(str, Enum):
    """Activity types affecting need decay rates."""

    ACTIVE = "active"  # Normal activity
    RESTING = "resting"  # Sitting, relaxing
    SLEEPING = "sleeping"  # Asleep
    COMBAT = "combat"  # Fighting
    SOCIALIZING = "socializing"  # With others


@dataclass
class NeedEffect:
    """Effect from an unmet need."""

    need_name: str
    threshold_name: str
    description: str
    stat_penalties: dict[str, int] = field(default_factory=dict)
    morale_modifier: int = 0
    special_effects: dict[str, float] = field(default_factory=dict)
    check_penalty: int = 0


@dataclass
class NeedDecayRates:
    """Decay rates per in-game hour for each activity type."""

    active: float
    resting: float
    sleeping: float
    combat: float


# Decay rates per in-game hour (positive = need increases/worsens)
DECAY_RATES: dict[str, NeedDecayRates] = {
    # Hunger: 0=starving, 100=stuffed. Decreases over time.
    "hunger": NeedDecayRates(active=-6, resting=-3, sleeping=-1, combat=-6),
    # Fatigue: 0=rested, 100=exhausted. Increases with activity.
    "fatigue": NeedDecayRates(active=12, resting=-5, sleeping=-15, combat=20),
    # Hygiene: 100=clean, decreases over time
    "hygiene": NeedDecayRates(active=-3, resting=-1, sleeping=0, combat=-8),
    # Comfort: environmental, doesn't decay automatically
    "comfort": NeedDecayRates(active=0, resting=0, sleeping=0, combat=-10),
    # Pain: from injuries, doesn't decay (managed by InjuryManager)
    "pain": NeedDecayRates(active=0, resting=-1, sleeping=-2, combat=0),
    # Social: 100=fulfilled, decreases when alone
    "social_connection": NeedDecayRates(active=-2, resting=-2, sleeping=0, combat=0),
    # Morale: 100=elated, affected by other needs
    "morale": NeedDecayRates(active=0, resting=0, sleeping=0, combat=0),
    # Purpose: 100=driven, slow decay
    "sense_of_purpose": NeedDecayRates(active=-0.5, resting=-0.5, sleeping=0, combat=0),
    # Intimacy: 0=satisfied, 100=desperate. Increases based on drive level.
    "intimacy": NeedDecayRates(active=0, resting=0, sleeping=0, combat=0),
}

# Intimacy decay per in-game day based on drive level
INTIMACY_DAILY_DECAY: dict[DriveLevel, float] = {
    DriveLevel.ASEXUAL: 0,
    DriveLevel.VERY_LOW: 1,
    DriveLevel.LOW: 3,
    DriveLevel.MODERATE: 5,
    DriveLevel.HIGH: 7,
    DriveLevel.VERY_HIGH: 10,
}


class NeedsManager(BaseManager):
    """Manages character needs: decay, effects, and satisfaction."""

    def get_needs(self, entity_id: int) -> CharacterNeeds | None:
        """Get character needs for an entity."""
        return (
            self.db.query(CharacterNeeds)
            .filter(
                CharacterNeeds.entity_id == entity_id,
                CharacterNeeds.session_id == self.session_id,
            )
            .first()
        )

    def get_or_create_needs(self, entity_id: int) -> CharacterNeeds:
        """Get or create character needs for an entity."""
        needs = self.get_needs(entity_id)
        if needs is None:
            needs = CharacterNeeds(
                entity_id=entity_id,
                session_id=self.session_id,
            )
            self.db.add(needs)
            self.db.flush()
        return needs

    def get_intimacy_profile(self, entity_id: int) -> IntimacyProfile | None:
        """Get intimacy profile for an entity."""
        return (
            self.db.query(IntimacyProfile)
            .filter(
                IntimacyProfile.entity_id == entity_id,
                IntimacyProfile.session_id == self.session_id,
            )
            .first()
        )

    def apply_time_decay(
        self,
        entity_id: int,
        hours: float,
        activity: ActivityType = ActivityType.ACTIVE,
        is_alone: bool = True,
    ) -> CharacterNeeds:
        """Apply time-based decay to all needs.

        Args:
            entity_id: Entity to update
            hours: In-game hours that passed
            activity: Type of activity during this time
            is_alone: Whether entity was alone (affects social need)

        Returns:
            Updated CharacterNeeds
        """
        needs = self.get_or_create_needs(entity_id)

        # Get decay rates for this activity
        activity_key = activity.value

        for need_name, rates in DECAY_RATES.items():
            if not hasattr(needs, need_name):
                continue

            # Get rate for this activity type
            rate = getattr(rates, activity_key, rates.active)

            # Special handling for social connection
            if need_name == "social_connection":
                if not is_alone:
                    rate = 5  # Increases when socializing
                elif activity == ActivityType.SOCIALIZING:
                    rate = 5

            current_value = getattr(needs, need_name)
            new_value = current_value + (rate * hours)

            # Clamp to 0-100
            setattr(needs, need_name, self._clamp(new_value))

        # Handle intimacy separately (daily decay based on drive)
        profile = self.get_intimacy_profile(entity_id)
        if profile:
            daily_rate = INTIMACY_DAILY_DECAY.get(profile.drive_level, 5)
            hourly_rate = daily_rate / 24
            needs.intimacy = self._clamp(needs.intimacy + (hourly_rate * hours))

        # Update morale based on other needs
        self._update_morale(needs)

        self.db.flush()
        return needs

    def _update_morale(self, needs: CharacterNeeds) -> None:
        """Update morale based on other need states."""
        morale_modifier = 0

        # Hunger effects on morale
        if needs.hunger < 15:
            morale_modifier -= 20
        elif needs.hunger < 30:
            morale_modifier -= 10

        # Fatigue effects on morale
        if needs.fatigue > 80:
            morale_modifier -= 15
        elif needs.fatigue > 60:
            morale_modifier -= 8

        # Pain effects on morale
        if needs.pain > 60:
            morale_modifier -= 25
        elif needs.pain > 40:
            morale_modifier -= 15

        # Social isolation effects
        if needs.social_connection < 20:
            morale_modifier -= 25
        elif needs.social_connection < 40:
            morale_modifier -= 10

        # Comfort effects
        if needs.comfort < 20:
            morale_modifier -= 10

        # Apply gradual morale adjustment toward baseline + modifiers
        baseline = 50 + morale_modifier
        current = needs.morale

        # Morale drifts toward baseline at 5 points per update
        if current < baseline:
            needs.morale = min(current + 5, baseline)
        elif current > baseline:
            needs.morale = max(current - 5, baseline)

        needs.morale = self._clamp(needs.morale)

    def satisfy_need(
        self,
        entity_id: int,
        need_name: str,
        amount: int,
        turn: int | None = None,
    ) -> CharacterNeeds:
        """Satisfy a need by the given amount.

        For hunger: increases (eating fills you up)
        For fatigue: decreases (resting reduces fatigue)
        For hygiene: increases (bathing cleans you)
        For social: increases (socializing fulfills need)
        For intimacy: decreases (satisfied = 0)

        Args:
            entity_id: Entity to update
            need_name: Name of need to satisfy
            amount: How much to change (positive = satisfy)
            turn: Current turn for tracking last satisfaction

        Returns:
            Updated CharacterNeeds
        """
        needs = self.get_or_create_needs(entity_id)

        if not hasattr(needs, need_name):
            raise ValueError(f"Unknown need: {need_name}")

        current = getattr(needs, need_name)

        # Different needs work differently
        if need_name in ("fatigue", "pain", "intimacy"):
            # Lower is better for these
            new_value = current - amount
        else:
            # Higher is better
            new_value = current + amount

        setattr(needs, need_name, self._clamp(new_value))

        # Track last satisfaction turn
        turn_tracking = {
            "hunger": "last_meal_turn",
            "fatigue": "last_sleep_turn",
            "hygiene": "last_bath_turn",
            "social_connection": "last_social_turn",
            "intimacy": "last_intimate_turn",
        }
        if need_name in turn_tracking and turn is not None:
            setattr(needs, turn_tracking[need_name], turn)

        self.db.flush()
        return needs

    def get_active_effects(self, entity_id: int) -> list[NeedEffect]:
        """Get all active effects from unmet needs.

        Returns list of NeedEffect objects describing current penalties.
        """
        needs = self.get_needs(entity_id)
        if needs is None:
            return []

        effects: list[NeedEffect] = []

        # Hunger effects
        if needs.hunger < 15:
            effects.append(
                NeedEffect(
                    need_name="hunger",
                    threshold_name="starving",
                    description="Starving - can barely function",
                    stat_penalties={"STR": -3, "DEX": -2, "CON": -2},
                    morale_modifier=-20,
                )
            )
        elif needs.hunger < 30:
            effects.append(
                NeedEffect(
                    need_name="hunger",
                    threshold_name="very_hungry",
                    description="Very hungry - weakened",
                    stat_penalties={"STR": -1, "DEX": -1},
                    morale_modifier=-10,
                )
            )

        # Fatigue effects
        if needs.fatigue > 80:
            effects.append(
                NeedEffect(
                    need_name="fatigue",
                    threshold_name="exhausted",
                    description="Exhausted - barely able to stand",
                    stat_penalties={"STR": -3, "DEX": -3, "INT": -3, "WIS": -3},
                    morale_modifier=-15,
                    special_effects={"hallucination_chance": 0.20},
                )
            )
        elif needs.fatigue > 60:
            effects.append(
                NeedEffect(
                    need_name="fatigue",
                    threshold_name="very_tired",
                    description="Very tired - struggling to focus",
                    stat_penalties={"INT": -2, "WIS": -2, "DEX": -1},
                )
            )

        # Hygiene effects
        if needs.hygiene < 20:
            effects.append(
                NeedEffect(
                    need_name="hygiene",
                    threshold_name="filthy",
                    description="Filthy - people avoid you",
                    stat_penalties={"CHA": -4},
                    special_effects={"disease_chance": 0.15},
                    check_penalty=-3,  # Social interaction penalty
                )
            )

        # Pain effects
        if needs.pain > 60:
            effects.append(
                NeedEffect(
                    need_name="pain",
                    threshold_name="severe",
                    description="Severe pain - hard to concentrate",
                    morale_modifier=-25,
                    check_penalty=-4,
                )
            )
        elif needs.pain > 40:
            effects.append(
                NeedEffect(
                    need_name="pain",
                    threshold_name="moderate",
                    description="Moderate pain - distracting",
                    morale_modifier=-15,
                    check_penalty=-2,
                )
            )

        # Morale effects
        if needs.morale < 20:
            effects.append(
                NeedEffect(
                    need_name="morale",
                    threshold_name="depressed",
                    description="Depressed - struggling to see the point",
                    check_penalty=-3,
                    special_effects={"give_up_chance": 0.30},
                )
            )

        # Social connection effects
        if needs.social_connection < 20:
            effects.append(
                NeedEffect(
                    need_name="social_connection",
                    threshold_name="lonely",
                    description="Lonely - isolated and withdrawn",
                    stat_penalties={"INT": -1},
                    morale_modifier=-25,
                )
            )

        # Intimacy effects
        if needs.intimacy > 80:
            effects.append(
                NeedEffect(
                    need_name="intimacy",
                    threshold_name="desperate",
                    description="Desperate for intimacy - distracted by need",
                    special_effects={"priority_override": 1.0},
                )
            )

        return effects

    def calculate_stat_modifiers(self, entity_id: int) -> dict[str, int]:
        """Calculate total stat modifiers from all need effects.

        Returns dict of {stat_name: total_modifier}.
        """
        effects = self.get_active_effects(entity_id)
        modifiers: dict[str, int] = {}

        for effect in effects:
            for stat, penalty in effect.stat_penalties.items():
                modifiers[stat] = modifiers.get(stat, 0) + penalty

        return modifiers

    def calculate_check_penalty(self, entity_id: int) -> int:
        """Calculate total penalty to all checks from needs."""
        effects = self.get_active_effects(entity_id)
        return sum(e.check_penalty for e in effects)

    def get_needs_summary(self, entity_id: int) -> dict:
        """Get a summary of needs for context/display.

        Returns dict with current values and any critical states.
        """
        needs = self.get_needs(entity_id)
        if needs is None:
            return {"has_needs": False}

        effects = self.get_active_effects(entity_id)

        return {
            "has_needs": True,
            "hunger": needs.hunger,
            "fatigue": needs.fatigue,
            "hygiene": needs.hygiene,
            "comfort": needs.comfort,
            "pain": needs.pain,
            "social_connection": needs.social_connection,
            "morale": needs.morale,
            "sense_of_purpose": needs.sense_of_purpose,
            "intimacy": needs.intimacy,
            "critical_states": [e.threshold_name for e in effects],
            "stat_modifiers": self.calculate_stat_modifiers(entity_id),
            "check_penalty": self.calculate_check_penalty(entity_id),
        }

    def get_npc_urgency(self, entity_id: int) -> tuple[str | None, int]:
        """Get the most urgent need for NPC behavior decisions.

        Returns (need_name, urgency_level) where urgency > 70 overrides schedule.
        """
        needs = self.get_needs(entity_id)
        if needs is None:
            return None, 0

        # Calculate urgency for each need (0-100)
        urgencies: dict[str, int] = {
            "hunger": max(0, 100 - needs.hunger),  # Lower hunger = more urgent
            "fatigue": needs.fatigue,  # Higher fatigue = more urgent
            "social_connection": max(0, 100 - needs.social_connection),
            "intimacy": needs.intimacy,  # Higher = more urgent
        }

        # Find most urgent
        if not urgencies:
            return None, 0

        most_urgent = max(urgencies.items(), key=lambda x: x[1])
        return most_urgent[0], most_urgent[1]
