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
from src.database.models.character_state import CharacterNeeds
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
    # Thirst: 0=dehydrated, 100=well-hydrated. Decays faster than hunger (vital).
    "thirst": NeedDecayRates(active=-10, resting=-5, sleeping=-2, combat=-15),
    # Stamina: 0=collapsed, 100=fresh. Physical capacity.
    # Decreases with activity, recovers with rest.
    "stamina": NeedDecayRates(active=-8, resting=15, sleeping=50, combat=-25),
    # Sleep Pressure: 0=well-rested, 100=desperately sleepy.
    # ALWAYS INCREASES while awake (positive rates), only clears during sleep (negative).
    # Note: This is inverted from other needs - higher = worse
    "sleep_pressure": NeedDecayRates(active=4.5, resting=4.5, sleeping=-12, combat=6),
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
    "thirst": {
        "sip": 8, "small_drink": 8, "taste": 5,
        "drink": 25, "water": 25, "ale": 25, "tea": 25, "juice": 25,
        "large_drink": 45, "gulp": 45, "chug": 45,
        "drink_deeply": 70, "quench": 70, "drain": 70,
        # Negative actions (dehydration)
        "salty_food": -10, "spicy_food": -15,
        "vomit": -25, "diarrhea": -30,
        "sweating": -15, "heavy_exertion": -20,
    },
    "stamina": {
        "quick_rest": 10, "catch_breath": 10, "pause": 8,
        "short_rest": 20, "rest": 20, "break": 15,
        "long_rest": 40, "extended_rest": 40, "relax": 35,
        "full_rest": 60, "recuperate": 60,
        # Sleep also restores stamina fully
        "sleep": 100, "full_sleep": 100, "night_sleep": 100,
    },
    "hygiene": {
        "quick_wash": 15, "rinse": 15, "wipe": 10,
        "partial_bath": 30, "wash": 30, "sponge_bath": 30,
        "full_bath": 65, "bath": 65, "shower": 65,
        "luxury_bath": 85, "spa": 85, "hot_spring": 85,
        # Negative actions (getting dirty)
        "sweat": -10, "exertion": -10,
        "get_dirty": -15, "dust": -15, "grime": -15,
        "mud": -25, "splash": -20, "fall": -25,
        "blood": -20, "gore": -30,
        "filth": -35, "sewer": -40, "garbage": -35,
    },
    "social_connection": {
        "chat": 10, "small_talk": 10, "greeting": 5,
        "conversation": 22, "talk": 22, "discussion": 22,
        "group_activity": 30, "gathering": 30, "party": 35,
        "bonding": 45, "intimate_talk": 45, "deep_conversation": 45,
        "romantic": 60,
        # Negative actions (social setbacks)
        "snub": -10, "ignored": -10, "dismissed": -10,
        "argument": -15, "disagreement": -15, "conflict": -15,
        "rejection": -25, "excluded": -25, "ostracized": -30,
        "betrayal": -40, "abandoned": -40,
        "isolation": -20, "alone": -15,
    },
    "comfort": {
        "change_clothes": 20, "dry_off": 15,
        "warm_up": 20, "cool_down": 20,
        "shelter": 30, "find_shelter": 30,
        "luxury": 65, "comfortable_bed": 50,
        # Negative actions (discomfort)
        "cramped": -10, "awkward_position": -10,
        "uncomfortable": -15, "hard_surface": -15,
        "get_wet": -20, "soaked": -25, "drenched": -30,
        "get_cold": -20, "freezing": -30, "chilled": -15,
        "overheated": -20, "sweltering": -25,
        "pain": -25, "injury_aggravation": -30,
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
        # Negative actions (romantic setbacks)
        "rebuff": -10, "cold_shoulder": -10,
        "romantic_rejection": -20, "turned_down": -20,
        "heartbreak": -40, "breakup": -45,
        "loneliness": -15, "yearning": -10,
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

    # === STAMINA MODIFIERS ===
    elif need_name == "stamina":
        # Stamina traits affect recovery
        if prefs.has_high_stamina:
            multiplier *= 1.2
        elif prefs.has_low_stamina:
            multiplier *= 0.8

        # Rest-specific modifiers (sleep also restores stamina)
        if "sleep" in action_lower or "rest" in action_lower:
            if prefs.is_heavy_sleeper:
                multiplier *= 1.3  # Recovers well from sleep
            if prefs.is_insomniac:
                multiplier *= 0.6  # Poor quality rest/sleep

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

    def get_preferences(self, entity_id: int) -> CharacterPreferences | None:
        """Get character preferences for an entity.

        Args:
            entity_id: Entity to get preferences for.

        Returns:
            CharacterPreferences or None if not found.
        """
        return (
            self.db.query(CharacterPreferences)
            .filter(
                CharacterPreferences.entity_id == entity_id,
                CharacterPreferences.session_id == self.session_id,
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
        prefs = self.get_preferences(entity_id)
        if prefs:
            daily_rate = INTIMACY_DAILY_DECAY.get(prefs.drive_level, 5)
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

        # Thirst effects on morale (vital - affects morale significantly)
        if needs.thirst < 5:
            morale_modifier -= 25
        elif needs.thirst < 15:
            morale_modifier -= 15
        elif needs.thirst < 30:
            morale_modifier -= 5

        # Stamina effects on morale (low stamina = physically exhausted)
        if needs.stamina < 20:
            morale_modifier -= 10
        elif needs.stamina < 40:
            morale_modifier -= 5

        # Sleep pressure effects on morale (high pressure = desperately tired)
        if needs.sleep_pressure > 80:
            morale_modifier -= 15
        elif needs.sleep_pressure > 60:
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
        resting increases stamina, healing increases wellness).

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
            "thirst": "last_drink_turn",
            "stamina": "last_sleep_turn",  # Track when last rested/slept
            "hygiene": "last_bath_turn",
            "social_connection": "last_social_turn",
            "intimacy": "last_intimate_turn",
        }
        if need_name in turn_tracking and turn is not None:
            setattr(needs, turn_tracking[need_name], turn)

        # Reset craving when need is satisfied
        # Note: stamina and sleep_pressure don't have cravings
        craving_map = {
            "hunger": "hunger_craving",
            "thirst": "thirst_craving",
            "social_connection": "social_craving",
            "intimacy": "intimacy_craving",
        }
        if need_name in craving_map:
            setattr(needs, craving_map[need_name], 0)

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

        # Thirst effects (vital - more severe than hunger)
        if needs.thirst < 5:
            effects.append(
                NeedEffect(
                    need_name="thirst",
                    threshold_name="severely_dehydrated",
                    description="Severely dehydrated - death imminent",
                    stat_penalties={"CON": -4, "WIS": -4, "STR": -2},
                    morale_modifier=-25,
                    special_effects={"death_save_required": 1.0, "movement_penalty": 0.5},
                )
            )
        elif needs.thirst < 15:
            effects.append(
                NeedEffect(
                    need_name="thirst",
                    threshold_name="dehydrated",
                    description="Dehydrated - lightheaded and weak",
                    stat_penalties={"CON": -2, "WIS": -2},
                    morale_modifier=-15,
                    special_effects={"movement_penalty": 0.25},
                )
            )
        elif needs.thirst < 30:
            effects.append(
                NeedEffect(
                    need_name="thirst",
                    threshold_name="thirsty",
                    description="Thirsty - distracted by need for water",
                    stat_penalties={"WIS": -1},
                    morale_modifier=-5,
                )
            )

        # Stamina effects (low stamina = physically exhausted)
        if needs.stamina < 10:
            effects.append(
                NeedEffect(
                    need_name="stamina",
                    threshold_name="collapsed",
                    description="Physically collapsed - cannot take physical actions",
                    stat_penalties={"STR": -4, "DEX": -4, "CON": -2},
                    morale_modifier=-10,
                    special_effects={"cannot_run": 1.0, "movement_halved": 1.0},
                )
            )
        elif needs.stamina < 30:
            effects.append(
                NeedEffect(
                    need_name="stamina",
                    threshold_name="exhausted",
                    description="Physically exhausted - movement halved",
                    stat_penalties={"STR": -3, "DEX": -3, "CON": -1},
                    special_effects={"cannot_run": 1.0},
                )
            )
        elif needs.stamina < 50:
            effects.append(
                NeedEffect(
                    need_name="stamina",
                    threshold_name="winded",
                    description="Winded - cannot run or sprint",
                    stat_penalties={"STR": -2, "DEX": -2},
                    special_effects={"cannot_run": 1.0},
                )
            )
        elif needs.stamina < 70:
            effects.append(
                NeedEffect(
                    need_name="stamina",
                    threshold_name="fatigued",
                    description="Physically fatigued",
                    stat_penalties={"DEX": -1},
                )
            )

        # Sleep pressure effects (high pressure = desperately sleepy)
        if needs.sleep_pressure >= 96:
            effects.append(
                NeedEffect(
                    need_name="sleep_pressure",
                    threshold_name="collapse_imminent",
                    description="About to collapse from exhaustion - forced sleep saves required",
                    stat_penalties={"INT": -4, "WIS": -4, "CHA": -3},
                    morale_modifier=-20,
                    special_effects={"forced_sleep_save": 1.0, "hallucination_chance": 0.20},
                )
            )
        elif needs.sleep_pressure > 80:
            effects.append(
                NeedEffect(
                    need_name="sleep_pressure",
                    threshold_name="delirious",
                    description="Delirious from lack of sleep - hallucination risk",
                    stat_penalties={"INT": -3, "WIS": -3, "CHA": -2},
                    morale_modifier=-15,
                    special_effects={"hallucination_chance": 0.10, "microsleep_risk": 0.15},
                )
            )
        elif needs.sleep_pressure > 60:
            effects.append(
                NeedEffect(
                    need_name="sleep_pressure",
                    threshold_name="sleep_exhausted",
                    description="Exhausted from lack of sleep - struggling to concentrate",
                    stat_penalties={"INT": -2, "WIS": -2, "CHA": -1},
                    special_effects={"microsleep_risk": 0.05},
                )
            )
        elif needs.sleep_pressure > 40:
            effects.append(
                NeedEffect(
                    need_name="sleep_pressure",
                    threshold_name="tired",
                    description="Tired - mental focus reduced",
                    stat_penalties={"INT": -1, "WIS": -1},
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
            "thirst": needs.thirst,
            "stamina": needs.stamina,
            "sleep_pressure": needs.sleep_pressure,
            "hygiene": needs.hygiene,
            "comfort": needs.comfort,
            "wellness": needs.wellness,
            "social_connection": needs.social_connection,
            "morale": needs.morale,
            "sense_of_purpose": needs.sense_of_purpose,
            "intimacy": needs.intimacy,
            # Include effective needs (accounting for cravings)
            "effective_hunger": needs.get_effective_need("hunger"),
            "effective_thirst": needs.get_effective_need("thirst"),
            # Note: stamina and sleep_pressure don't have cravings
            "critical_states": [e.threshold_name for e in effects],
            "stat_modifiers": self.calculate_stat_modifiers(entity_id),
            "check_penalty": self.calculate_check_penalty(entity_id),
        }

    def get_npc_urgency(self, entity_id: int) -> tuple[str | None, int]:
        """Get the most urgent need for NPC behavior decisions.

        Returns (need_name, urgency_level) where urgency > 70 overrides schedule.
        Most needs: 0 = bad, 100 = good. Urgency = 100 - value.
        Exception: sleep_pressure: 0 = good, 100 = bad. Urgency = value directly.
        """
        needs = self.get_needs(entity_id)
        if needs is None:
            return None, 0

        # Calculate urgency for each need (0-100)
        # Use effective needs (accounting for cravings) for urgency calculation
        urgencies: dict[str, int] = {
            "hunger": max(0, 100 - needs.get_effective_need("hunger")),
            "thirst": max(0, 100 - needs.get_effective_need("thirst")),
            "stamina": max(0, 100 - needs.stamina),  # Low stamina = high urgency
            "sleep_pressure": needs.sleep_pressure,  # High pressure = high urgency (inverted)
            "social_connection": max(0, 100 - needs.get_effective_need("social_connection")),
            "intimacy": max(0, 100 - needs.get_effective_need("intimacy")),
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

    # =========================================================================
    # Vital Need Death Checks
    # =========================================================================

    def check_vital_needs(
        self,
        entity_id: int,
        minutes_passed: float,
    ) -> list[dict]:
        """Check if vital needs are critically low and require death saves.

        Vital needs: thirst, hunger, stamina (in priority order)
        Scaling frequency:
        - Need < 5: check every hour
        - Need < 3: check every 30 minutes
        - Need = 0: check every turn (5 minutes)

        Args:
            entity_id: Entity to check.
            minutes_passed: Minutes since last check.

        Returns:
            List of death save requirements with need name and DC.
        """
        needs = self.get_needs(entity_id)
        if needs is None:
            return []

        death_saves_required: list[dict] = []

        # Check in priority order: thirst (fastest killer), hunger, stamina
        vital_needs = [
            ("thirst", needs.thirst, "dehydration"),
            ("hunger", needs.hunger, "starvation"),
            ("stamina", needs.stamina, "physical_exhaustion"),
        ]

        for need_name, value, cause in vital_needs:
            if value >= 5:
                continue  # Not critical

            # Determine check frequency based on severity
            if value == 0:
                check_interval = 5  # Every turn
                dc = 18  # Very hard
            elif value < 3:
                check_interval = 30  # Every 30 minutes
                dc = 15  # Hard
            else:  # value < 5
                check_interval = 60  # Every hour
                dc = 12  # Medium

            # Check if enough time has passed for this check
            if minutes_passed >= check_interval:
                death_saves_required.append({
                    "need_name": need_name,
                    "value": value,
                    "cause": cause,
                    "dc": dc,
                    "description": f"Death save required due to {cause} ({need_name}={value})",
                })

        return death_saves_required

    # =========================================================================
    # Craving/Stimulus Methods
    # =========================================================================

    def apply_craving(
        self,
        entity_id: int,
        need_name: str,
        relevance: float,
        attention: float = 0.6,
    ) -> int:
        """Apply a craving boost to a need based on stimulus.

        Cravings intensify the perceived urgency of a need without changing
        the actual physiological value. Higher craving = feels more urgent.

        Formula: boost = relevance × attention × base_craving × 0.6
        where base_craving = 100 - current_need

        Args:
            entity_id: Entity to apply craving to.
            need_name: Name of need (hunger, thirst, social_connection, intimacy).
            relevance: How relevant the stimulus is to preferences (0.0-1.0).
            attention: How prominent the stimulus is (0.3=background, 0.6=described, 1.0=offered).

        Returns:
            Amount of craving boost applied.
        """
        needs = self.get_or_create_needs(entity_id)

        # Map need names to craving fields
        # Note: stamina and sleep_pressure don't have cravings - they're physical states
        craving_map = {
            "hunger": "hunger_craving",
            "thirst": "thirst_craving",
            "social_connection": "social_craving",
            "intimacy": "intimacy_craving",
        }

        if need_name not in craving_map:
            return 0

        current_need = getattr(needs, need_name)
        base_craving = 100 - current_need  # Lower need = higher susceptibility

        # Calculate boost (capped at 50 to prevent overwhelming)
        boost = int(relevance * attention * base_craving * 0.6)
        boost = min(boost, 50)

        # Apply boost to craving field
        craving_field = craving_map[need_name]
        current_craving = getattr(needs, craving_field)
        new_craving = min(100, current_craving + boost)
        setattr(needs, craving_field, new_craving)

        self.db.flush()
        return boost

    def decay_cravings(
        self,
        entity_id: int,
        minutes_passed: float,
    ) -> None:
        """Decay all cravings over time when stimuli are removed.

        Rate: -20 per 30 minutes.

        Args:
            entity_id: Entity to decay cravings for.
            minutes_passed: Minutes since last decay.
        """
        needs = self.get_needs(entity_id)
        if needs is None:
            return

        # Calculate decay amount: -20 per 30 minutes
        decay_amount = int((minutes_passed / 30) * 20)

        # Note: stamina and sleep_pressure don't have cravings
        craving_fields = [
            "hunger_craving",
            "thirst_craving",
            "social_craving",
            "intimacy_craving",
        ]

        for field in craving_fields:
            current = getattr(needs, field)
            if current > 0:
                new_value = max(0, current - decay_amount)
                setattr(needs, field, new_value)

        self.db.flush()

    # =========================================================================
    # Sleep Pressure Methods
    # =========================================================================

    def can_sleep(self, entity_id: int) -> tuple[bool, str]:
        """Check if entity has enough sleep pressure to fall asleep.

        Requires sleep_pressure >= 30 to sleep. Below that, the character
        is too alert to fall asleep.

        Args:
            entity_id: Entity to check.

        Returns:
            Tuple of (can_sleep, reason). If can_sleep is False, reason explains why.
        """
        needs = self.get_needs(entity_id)
        if needs is None:
            return True, ""  # No needs tracked, allow sleep

        if needs.sleep_pressure < 30:
            return False, "You're not tired enough to sleep."

        return True, ""

    def get_sleep_duration(self, entity_id: int) -> float:
        """Calculate natural sleep duration based on sleep pressure.

        Higher sleep pressure results in longer sleep:
        - 30-40 pressure: 1-2 hours (power nap)
        - 41-55 pressure: 2-4 hours (short sleep)
        - 56-70 pressure: 4-6 hours (normal sleep)
        - 71-85 pressure: 6-8 hours (good sleep)
        - 86-100 pressure: 8-10 hours (recovery sleep)

        Formula: hours = clamp((pressure - 30) / 10 + 1, 1, 10)

        Args:
            entity_id: Entity to calculate duration for.

        Returns:
            Sleep duration in hours (1.0 to 10.0).
        """
        needs = self.get_needs(entity_id)
        if needs is None:
            return 6.0  # Default reasonable sleep

        pressure = needs.sleep_pressure

        # Can't sleep with low pressure (but if called, return minimum)
        if pressure < 30:
            return 0.0

        # Calculate hours based on pressure
        hours = (pressure - 30) / 10 + 1
        return max(1.0, min(10.0, hours))

    def reduce_sleep_pressure(self, entity_id: int, hours_slept: float) -> int:
        """Reduce sleep pressure after sleeping.

        Sleep clears pressure at a rate of 12 points per hour slept.
        Also fully restores stamina.

        Args:
            entity_id: Entity that slept.
            hours_slept: Number of hours slept.

        Returns:
            New sleep pressure value after reduction.
        """
        needs = self.get_or_create_needs(entity_id)

        # Clear sleep pressure: 12 points per hour
        pressure_cleared = int(hours_slept * 12)
        new_pressure = max(0, needs.sleep_pressure - pressure_cleared)
        needs.sleep_pressure = new_pressure

        # Full stamina recovery from sleep
        needs.stamina = 100

        # Track last sleep turn
        if self.current_turn is not None:
            needs.last_sleep_turn = self.current_turn

        self.db.flush()
        return new_pressure

    def check_forced_sleep(self, entity_id: int) -> tuple[bool, int]:
        """Check if sleep pressure is so high it requires a forced sleep save.

        At pressure >= 96, the character must make a CON save or collapse.

        Args:
            entity_id: Entity to check.

        Returns:
            Tuple of (save_required, dc). If save_required is False, dc is 0.
        """
        needs = self.get_needs(entity_id)
        if needs is None:
            return False, 0

        if needs.sleep_pressure >= 96:
            return True, 15  # DC 15 CON save to stay awake

        return False, 0

    # =========================================================================
    # Accumulation Methods (Non-Vital Needs)
    # =========================================================================

    def check_accumulation_effects(
        self,
        entity_id: int,
    ) -> list[dict]:
        """Check for probability-based effects from prolonged low non-vital needs.

        Formula: daily_chance = (100 - need_value) / 4
        Should be called once per in-game day.

        Non-vital needs checked:
        - hygiene < 30: illness/disease chance
        - social_connection < 25: depression chance
        - comfort < 20: morale penalty
        - sense_of_purpose < 20: motivation loss

        Args:
            entity_id: Entity to check.

        Returns:
            List of triggered effects with descriptions.
        """
        import random

        needs = self.get_needs(entity_id)
        if needs is None:
            return []

        triggered_effects: list[dict] = []

        # Hygiene → illness
        if needs.hygiene < 30:
            chance = (100 - needs.hygiene) / 4 / 100  # Convert to 0-1
            if random.random() < chance:
                triggered_effects.append({
                    "type": "illness",
                    "need": "hygiene",
                    "value": needs.hygiene,
                    "chance": chance * 100,
                    "description": "Poor hygiene has led to illness",
                    "effect": "wellness_penalty",
                    "severity": -20 if needs.hygiene < 15 else -10,
                })

        # Social connection → depression
        if needs.social_connection < 25:
            chance = (100 - needs.social_connection) / 4 / 100
            if random.random() < chance:
                triggered_effects.append({
                    "type": "depression",
                    "need": "social_connection",
                    "value": needs.social_connection,
                    "chance": chance * 100,
                    "description": "Prolonged isolation has deepened depression",
                    "effect": "morale_penalty",
                    "severity": -15 if needs.social_connection < 15 else -8,
                })

        # Comfort → stress accumulation
        if needs.comfort < 20:
            chance = (100 - needs.comfort) / 4 / 100
            if random.random() < chance:
                triggered_effects.append({
                    "type": "stress",
                    "need": "comfort",
                    "value": needs.comfort,
                    "chance": chance * 100,
                    "description": "Miserable conditions have taken their toll",
                    "effect": "stamina_penalty",
                    "severity": -10,
                })

        # Sense of purpose → motivation loss
        if needs.sense_of_purpose < 20:
            chance = (100 - needs.sense_of_purpose) / 4 / 100
            if random.random() < chance:
                triggered_effects.append({
                    "type": "apathy",
                    "need": "sense_of_purpose",
                    "value": needs.sense_of_purpose,
                    "chance": chance * 100,
                    "description": "Lack of purpose has led to growing apathy",
                    "effect": "initiative_penalty",
                    "severity": -2,
                })

        return triggered_effects

    def apply_companion_time_decay(
        self,
        hours: float,
        activity: ActivityType = ActivityType.ACTIVE,
    ) -> dict[str, CharacterNeeds | None]:
        """Apply time-based need decay to all companion NPCs.

        This method should be called during time progression (e.g., world simulation)
        to update the needs of all NPCs traveling with the player.

        Args:
            hours: In-game hours that passed.
            activity: Type of activity during this time.

        Returns:
            Dict mapping entity_key to updated CharacterNeeds (or None if no needs record).
        """
        from src.managers.entity_manager import EntityManager

        entity_manager = EntityManager(self.db, self.game_session)
        companions = entity_manager.get_companions()

        results: dict[str, CharacterNeeds | None] = {}

        for companion in companions:
            # Check if companion has needs record
            needs = self.get_needs(companion.id)
            if needs:
                updated = self.apply_time_decay(
                    entity_id=companion.id,
                    hours=hours,
                    activity=activity,
                    is_alone=False,  # Companions are with player
                )
                results[companion.entity_key] = updated
            else:
                results[companion.entity_key] = None

        return results
