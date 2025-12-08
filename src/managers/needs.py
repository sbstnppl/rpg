"""Character needs management (hunger, fatigue, hygiene, morale, etc.)."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from sqlalchemy.orm import Session

from src.database.models.character_preferences import (
    CharacterPreferences,
    NeedAdaptation,
    NeedModifier,
)
from src.database.models.character_state import CharacterNeeds, IntimacyProfile
from src.database.models.entities import Entity
from src.database.models.enums import DriveLevel, IntimacyStyle, ModifierSource, SocialTendency
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


# Decay rates per in-game hour (negative = need decreases toward 0)
# All needs now follow: 0 = bad (action required), 100 = good (no action needed)
DECAY_RATES: dict[str, NeedDecayRates] = {
    # Hunger: 0=starving, 100=stuffed. Decreases over time.
    "hunger": NeedDecayRates(active=-6, resting=-3, sleeping=-1, combat=-6),
    # Energy: 0=exhausted, 100=energized. Decreases with activity.
    "energy": NeedDecayRates(active=-12, resting=5, sleeping=15, combat=-20),
    # Hygiene: 0=filthy, 100=clean. Decreases over time.
    "hygiene": NeedDecayRates(active=-3, resting=-1, sleeping=0, combat=-8),
    # Comfort: 0=miserable, 100=luxurious. Environmental, doesn't decay automatically.
    "comfort": NeedDecayRates(active=0, resting=0, sleeping=0, combat=-10),
    # Wellness: 0=agony, 100=pain-free. Recovers with rest (managed by InjuryManager).
    "wellness": NeedDecayRates(active=0, resting=1, sleeping=2, combat=0),
    # Social: 0=lonely, 100=fulfilled. Decreases when alone.
    "social_connection": NeedDecayRates(active=-2, resting=-2, sleeping=0, combat=0),
    # Morale: 0=depressed, 100=elated. Affected by other needs.
    "morale": NeedDecayRates(active=0, resting=0, sleeping=0, combat=0),
    # Purpose: 0=aimless, 100=driven. Slow decay.
    "sense_of_purpose": NeedDecayRates(active=-0.5, resting=-0.5, sleeping=0, combat=0),
    # Intimacy: 0=desperate, 100=content. Decreases based on drive level.
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

# Action catalog with midpoint satisfaction values for each need
# These represent typical satisfaction amounts before quality/preference modifiers
# All needs: higher value = better, so satisfaction increases the need value
ACTION_SATISFACTION_CATALOG: dict[str, dict[str, int]] = {
    "hunger": {
        "snack": 10, "nibble": 10, "bite": 10,
        "light_meal": 22, "soup": 22, "half_portion": 22,
        "full_meal": 40, "meal": 40, "dinner": 40,
        "feast": 65, "gorge": 65, "banquet": 65,
        "ration": 15, "trail_ration": 15,
    },
    "energy": {
        "quick_nap": 15, "nap": 15, "doze": 15,
        "short_rest": 28, "rest": 28, "break": 20,
        "full_sleep": 75, "sleep": 75, "night_sleep": 75,
        "long_sleep": 90, "extended_rest": 90,
    },
    "hygiene": {
        "quick_wash": 15, "rinse": 15, "wipe": 10,
        "partial_bath": 30, "wash": 30, "sponge_bath": 30,
        "full_bath": 65, "bath": 65, "shower": 65,
        "luxury_bath": 85, "spa": 85, "hot_spring": 85,
    },
    "social_connection": {
        "chat": 10, "small_talk": 10, "greeting": 5,
        "conversation": 22, "talk": 22, "discussion": 22,
        "group_activity": 30, "gathering": 30, "party": 35,
        "bonding": 45, "intimate_talk": 45, "deep_conversation": 45,
        "romantic": 60,
    },
    "comfort": {
        "change_clothes": 20, "dry_off": 15,
        "warm_up": 20, "cool_down": 20,
        "shelter": 30, "find_shelter": 30,
        "luxury": 65, "comfortable_bed": 50,
    },
    "wellness": {
        "minor_remedy": 10, "bandage": 10, "ice": 10,
        "medicine": 30, "painkiller": 30, "potion": 30,
        "treatment": 45, "healing": 45, "medical_care": 45,
        "full_healing": 100, "magical_restoration": 100,
    },
    "morale": {
        "minor_victory": 10, "compliment": 10, "small_success": 10,
        "achievement": 22, "victory": 22, "accomplishment": 22,
        "major_success": 45, "triumph": 45, "great_victory": 45,
        "setback": -20, "failure": -20, "embarrassment": -15,
        "tragedy": -60, "devastation": -60, "major_loss": -50,
    },
    "sense_of_purpose": {
        "accept_quest": 17, "new_goal": 17, "mission": 17,
        "progress": 10, "step_forward": 10, "advancement": 10,
        "complete_quest": 35, "goal_achieved": 35, "mission_complete": 35,
        "find_calling": 60, "life_purpose": 60,
        "lose_purpose": -45, "goal_failed": -30,
    },
    "intimacy": {
        "flirtation": 10, "flirt": 10,
        "affection": 22, "kissing": 22, "cuddle": 20,
        "intimate_encounter": 60, "intimacy": 60,
        "emotional_intimacy": 30, "vulnerability": 30,
    },
}

# Quality multipliers for satisfaction amounts
QUALITY_MULTIPLIERS: dict[str, float] = {
    "poor": 0.6,
    "basic": 1.0,
    "good": 1.3,
    "excellent": 1.6,
    "exceptional": 2.0,
}


def estimate_base_satisfaction(
    need_name: str,
    action_type: str,
    quality: str = "basic",
) -> int:
    """Estimate base satisfaction amount from action type and quality.

    Uses the action catalog to look up midpoint values and applies
    quality multipliers.

    Args:
        need_name: Name of the need being satisfied.
        action_type: Type of action performed (e.g., 'full_meal', 'quick_nap').
        quality: Quality level ('poor', 'basic', 'good', 'excellent', 'exceptional').

    Returns:
        Estimated base satisfaction amount (before preference modifiers).
    """
    catalog = ACTION_SATISFACTION_CATALOG.get(need_name, {})
    base = catalog.get(action_type.lower(), 20)  # Default to 20 if not found

    quality_mult = QUALITY_MULTIPLIERS.get(quality.lower(), 1.0)

    return int(base * quality_mult)


def get_preference_multiplier(
    prefs: CharacterPreferences | None,
    need_name: str,
    action_type: str,
    quality: str = "basic",
) -> float:
    """Calculate preference-based multiplier for need satisfaction.

    Uses CharacterPreferences traits to adjust satisfaction amounts.
    For example, a greedy eater gets +30% hunger satisfaction.

    Args:
        prefs: CharacterPreferences for the entity (or None).
        need_name: Name of the need being satisfied.
        action_type: Type of action performed.
        quality: Quality level of the action.

    Returns:
        Multiplier to apply to base satisfaction (0.0 to 2.0+).
    """
    if prefs is None:
        return 1.0

    multiplier = 1.0
    action_lower = action_type.lower()

    # === HUNGER MODIFIERS ===
    if need_name == "hunger":
        # Greedy eater gets more satisfaction from eating
        if prefs.is_greedy_eater:
            multiplier *= 1.3

        # Picky eater: quality affects satisfaction more
        if prefs.is_picky_eater:
            if quality in ("excellent", "exceptional"):
                multiplier *= 1.3  # Loves high-quality food
            elif quality == "poor":
                multiplier *= 0.5  # Barely tolerates low-quality

    # === ENERGY MODIFIERS ===
    elif need_name == "energy":
        # Stamina traits affect recovery
        if prefs.has_high_stamina:
            multiplier *= 1.2
        elif prefs.has_low_stamina:
            multiplier *= 0.8

        # Sleep-specific modifiers
        if "sleep" in action_lower or "rest" in action_lower:
            if prefs.is_insomniac:
                multiplier *= 0.6  # Struggles to recover from sleep
            elif prefs.is_heavy_sleeper:
                multiplier *= 1.3  # Recovers well from sleep

    # === SOCIAL CONNECTION MODIFIERS ===
    elif need_name == "social_connection":
        # Social personality traits
        if prefs.is_social_butterfly:
            multiplier *= 1.3
        elif prefs.is_loner:
            multiplier *= 0.5

        # Social tendency affects group vs individual interactions
        if prefs.social_tendency == SocialTendency.EXTROVERT:
            if "group" in action_lower or "party" in action_lower or "gathering" in action_lower:
                multiplier *= 1.2
        elif prefs.social_tendency == SocialTendency.INTROVERT:
            if "group" in action_lower or "party" in action_lower or "gathering" in action_lower:
                multiplier *= 0.8
            elif "conversation" in action_lower or "talk" in action_lower or "chat" in action_lower:
                multiplier *= 1.2  # Prefers one-on-one

    # === INTIMACY MODIFIERS ===
    elif need_name == "intimacy":
        # Drive level affects satisfaction
        drive_multipliers = {
            DriveLevel.ASEXUAL: 0.0,
            DriveLevel.VERY_LOW: 0.5,
            DriveLevel.LOW: 0.8,
            DriveLevel.MODERATE: 1.0,
            DriveLevel.HIGH: 1.2,
            DriveLevel.VERY_HIGH: 1.5,
        }
        multiplier *= drive_multipliers.get(prefs.drive_level, 1.0)

        # Intimacy style modifiers
        if prefs.intimacy_style == IntimacyStyle.CASUAL:
            if "encounter" in action_lower or "physical" in action_lower:
                multiplier *= 1.3
        elif prefs.intimacy_style == IntimacyStyle.EMOTIONAL:
            if "emotional" in action_lower or "vulnerability" in action_lower:
                multiplier *= 1.5
            elif "encounter" in action_lower:
                multiplier *= 0.8  # Physical without emotional connection less satisfying

    return multiplier


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

            # Apply decay rate multiplier from modifiers
            decay_multiplier = self.get_decay_multiplier(entity_id, need_name)
            rate = rate * decay_multiplier

            current_value = getattr(needs, need_name)
            new_value = current_value + (rate * hours)

            # Get max intensity cap and clamp
            max_intensity = self.get_max_intensity(entity_id, need_name)
            setattr(needs, need_name, self._clamp(new_value, max_val=max_intensity))

        # Handle intimacy separately (daily decay based on drive)
        # Intimacy decreases over time (0 = desperate, 100 = content)
        profile = self.get_intimacy_profile(entity_id)
        if profile:
            daily_rate = INTIMACY_DAILY_DECAY.get(profile.drive_level, 5)
            # Apply decay multiplier for intimacy too
            decay_multiplier = self.get_decay_multiplier(entity_id, "intimacy")
            hourly_rate = (daily_rate / 24) * decay_multiplier
            # Intimacy decreases (negative rate) based on drive level
            needs.intimacy = self._clamp(
                needs.intimacy - (hourly_rate * hours)
            )

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

        # Energy effects on morale (low energy = exhausted)
        if needs.energy < 20:
            morale_modifier -= 15
        elif needs.energy < 40:
            morale_modifier -= 8

        # Wellness effects on morale (low wellness = pain)
        if needs.wellness < 40:
            morale_modifier -= 25
        elif needs.wellness < 60:
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

        Applies satisfaction_multiplier from any active NeedModifier records.

        All needs follow the same semantics: higher value = better state.
        Satisfying a need increases its value (e.g., eating increases hunger,
        resting increases energy, healing increases wellness).

        Args:
            entity_id: Entity to update
            need_name: Name of need to satisfy
            amount: How much to increase (positive = satisfy, before multipliers)
            turn: Current turn for tracking last satisfaction

        Returns:
            Updated CharacterNeeds
        """
        needs = self.get_or_create_needs(entity_id)

        if not hasattr(needs, need_name):
            raise ValueError(f"Unknown need: {need_name}")

        # Apply satisfaction multiplier from NeedModifier
        satisfaction_mult = self.get_satisfaction_multiplier(entity_id, need_name)
        modified_amount = int(amount * satisfaction_mult)

        current = getattr(needs, need_name)

        # All needs: higher is better, so satisfaction increases the value
        new_value = current + modified_amount

        setattr(needs, need_name, self._clamp(new_value))

        # Track last satisfaction turn
        turn_tracking = {
            "hunger": "last_meal_turn",
            "energy": "last_sleep_turn",
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

        # Energy effects (low energy = exhausted)
        if needs.energy < 20:
            effects.append(
                NeedEffect(
                    need_name="energy",
                    threshold_name="exhausted",
                    description="Exhausted - barely able to stand",
                    stat_penalties={"STR": -3, "DEX": -3, "INT": -3, "WIS": -3},
                    morale_modifier=-15,
                    special_effects={"hallucination_chance": 0.20},
                )
            )
        elif needs.energy < 40:
            effects.append(
                NeedEffect(
                    need_name="energy",
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

        # Wellness effects (low wellness = pain)
        if needs.wellness < 40:
            effects.append(
                NeedEffect(
                    need_name="wellness",
                    threshold_name="severe",
                    description="Severe pain - hard to concentrate",
                    morale_modifier=-25,
                    check_penalty=-4,
                )
            )
        elif needs.wellness < 60:
            effects.append(
                NeedEffect(
                    need_name="wellness",
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

        # Intimacy effects (low intimacy = desperate)
        if needs.intimacy < 20:
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
            "energy": needs.energy,
            "hygiene": needs.hygiene,
            "comfort": needs.comfort,
            "wellness": needs.wellness,
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
        All needs now follow the same pattern: 0 = bad, 100 = good.
        Urgency is calculated as 100 - value (lower value = higher urgency).
        """
        needs = self.get_needs(entity_id)
        if needs is None:
            return None, 0

        # Calculate urgency for each need (0-100)
        # All needs: 0 = bad state, so urgency = 100 - value
        urgencies: dict[str, int] = {
            "hunger": max(0, 100 - needs.hunger),
            "energy": max(0, 100 - needs.energy),
            "social_connection": max(0, 100 - needs.social_connection),
            "intimacy": max(0, 100 - needs.intimacy),
        }

        # Find most urgent
        if not urgencies:
            return None, 0

        most_urgent = max(urgencies.items(), key=lambda x: x[1])
        return most_urgent[0], most_urgent[1]

    # =========================================================================
    # Modifier Methods
    # =========================================================================

    def get_decay_multiplier(self, entity_id: int, need_name: str) -> float:
        """Get combined decay rate multiplier for a need.

        Multiplies all active modifiers for this need.

        Args:
            entity_id: Entity to get multiplier for.
            need_name: Name of the need.

        Returns:
            Combined multiplier (1.0 if no modifiers).
        """
        modifiers = (
            self.db.query(NeedModifier)
            .filter(
                NeedModifier.entity_id == entity_id,
                NeedModifier.session_id == self.session_id,
                NeedModifier.need_name == need_name,
                NeedModifier.is_active == True,
            )
            .all()
        )

        result = 1.0
        for mod in modifiers:
            result *= mod.decay_rate_multiplier
        return result

    def get_satisfaction_multiplier(self, entity_id: int, need_name: str) -> float:
        """Get combined satisfaction multiplier for a need.

        Multiplies all active modifiers for this need.

        Args:
            entity_id: Entity to get multiplier for.
            need_name: Name of the need.

        Returns:
            Combined multiplier (1.0 if no modifiers).
        """
        modifiers = (
            self.db.query(NeedModifier)
            .filter(
                NeedModifier.entity_id == entity_id,
                NeedModifier.session_id == self.session_id,
                NeedModifier.need_name == need_name,
                NeedModifier.is_active == True,
            )
            .all()
        )

        result = 1.0
        for mod in modifiers:
            result *= mod.satisfaction_multiplier
        return result

    def get_max_intensity(self, entity_id: int, need_name: str) -> int:
        """Get maximum intensity cap for a need.

        Returns the lowest cap from all active modifiers.

        Args:
            entity_id: Entity to get cap for.
            need_name: Name of the need.

        Returns:
            Lowest cap value, or 100 if no caps exist.
        """
        modifiers = (
            self.db.query(NeedModifier)
            .filter(
                NeedModifier.entity_id == entity_id,
                NeedModifier.session_id == self.session_id,
                NeedModifier.need_name == need_name,
                NeedModifier.is_active == True,
                NeedModifier.max_intensity_cap.isnot(None),
            )
            .all()
        )

        if not modifiers:
            return 100

        return min(mod.max_intensity_cap for mod in modifiers)

    # =========================================================================
    # Adaptation Methods
    # =========================================================================

    def get_total_adaptation(self, entity_id: int, need_name: str) -> int:
        """Get total adaptation delta for a need.

        Sums all adaptation deltas for this need.

        Args:
            entity_id: Entity to get adaptation for.
            need_name: Name of the need.

        Returns:
            Sum of all adaptation deltas (0 if none).
        """
        from sqlalchemy import func

        result = (
            self.db.query(func.sum(NeedAdaptation.adaptation_delta))
            .filter(
                NeedAdaptation.entity_id == entity_id,
                NeedAdaptation.session_id == self.session_id,
                NeedAdaptation.need_name == need_name,
            )
            .scalar()
        )

        return result or 0

    def create_adaptation(
        self,
        entity_id: int,
        need_name: str,
        delta: int,
        reason: str,
        trigger_event: str | None = None,
        started_turn: int | None = None,
        is_gradual: bool = False,
        duration_days: int | None = None,
        is_reversible: bool = False,
        reversal_trigger: str | None = None,
    ) -> NeedAdaptation:
        """Create a need adaptation record.

        Args:
            entity_id: Entity to create adaptation for.
            need_name: Name of the need being adapted.
            delta: Change to baseline (positive or negative).
            reason: Why this adaptation occurred.
            trigger_event: Optional event that triggered this.
            started_turn: Turn when adaptation started (defaults to current turn).
            is_gradual: Whether this adaptation happens gradually.
            duration_days: Days for gradual adaptation.
            is_reversible: Whether this can be reversed.
            reversal_trigger: What would reverse this adaptation.

        Returns:
            Created NeedAdaptation record.
        """
        if started_turn is None:
            started_turn = self.current_turn

        adaptation = NeedAdaptation(
            entity_id=entity_id,
            session_id=self.session_id,
            need_name=need_name,
            adaptation_delta=delta,
            reason=reason,
            trigger_event=trigger_event,
            started_turn=started_turn,
            is_gradual=is_gradual,
            duration_days=duration_days,
            is_reversible=is_reversible,
            reversal_trigger=reversal_trigger,
        )
        self.db.add(adaptation)
        self.db.flush()
        return adaptation
