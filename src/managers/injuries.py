"""Injury management (activity impact, healing progression)."""

from dataclasses import dataclass, field
from datetime import datetime
from random import random
from typing import Literal

from sqlalchemy.orm import Session

from src.database.models.character_state import CharacterNeeds
from src.database.models.enums import BodyPart, InjurySeverity, InjuryType
from src.database.models.injuries import ActivityRestriction, BodyInjury
from src.database.models.session import GameSession
from src.managers.base import BaseManager


@dataclass
class InjuryRecoveryTime:
    """Base recovery time range for an injury type."""

    min_days: int
    max_days: int

    @property
    def average_days(self) -> int:
        return (self.min_days + self.max_days) // 2


# Base recovery times by injury type
RECOVERY_TIMES: dict[InjuryType, InjuryRecoveryTime] = {
    InjuryType.BRUISE: InjuryRecoveryTime(2, 5),
    InjuryType.CUT: InjuryRecoveryTime(5, 10),
    InjuryType.LACERATION: InjuryRecoveryTime(10, 20),
    InjuryType.BURN: InjuryRecoveryTime(7, 21),
    InjuryType.SPRAIN: InjuryRecoveryTime(7, 21),
    InjuryType.STRAIN: InjuryRecoveryTime(3, 10),
    InjuryType.FRACTURE: InjuryRecoveryTime(42, 84),  # 6-12 weeks
    InjuryType.DISLOCATION: InjuryRecoveryTime(14, 28),
    InjuryType.MUSCLE_SORE: InjuryRecoveryTime(1, 3),
    InjuryType.MUSCLE_TEAR: InjuryRecoveryTime(21, 42),
    InjuryType.MUSCLE_RUPTURE: InjuryRecoveryTime(90, 180),
    InjuryType.CONCUSSION: InjuryRecoveryTime(7, 28),
    InjuryType.INTERNAL_BLEEDING: InjuryRecoveryTime(14, 60),
    InjuryType.NERVE_DAMAGE: InjuryRecoveryTime(60, 180),
}

# Severity multipliers for recovery time
SEVERITY_MULTIPLIERS: dict[InjurySeverity, float] = {
    InjurySeverity.MINOR: 0.5,
    InjurySeverity.MODERATE: 1.0,
    InjurySeverity.SEVERE: 1.5,
    InjurySeverity.CRITICAL: 2.0,
}

# Pain levels by severity (0-100)
SEVERITY_PAIN: dict[InjurySeverity, int] = {
    InjurySeverity.MINOR: 15,
    InjurySeverity.MODERATE: 35,
    InjurySeverity.SEVERE: 60,
    InjurySeverity.CRITICAL: 85,
}

# Chance of permanent damage by severity
PERMANENT_DAMAGE_CHANCE: dict[InjurySeverity, float] = {
    InjurySeverity.MINOR: 0.0,
    InjurySeverity.MODERATE: 0.05,
    InjurySeverity.SEVERE: 0.15,
    InjurySeverity.CRITICAL: 0.30,
}


@dataclass
class ActivityImpact:
    """Impact of injuries on a specific activity."""

    impact_type: Literal["unaffected", "painful", "penalty", "impossible", "impossible_without"]
    value: int = 0  # Percentage for painful/penalty
    requirement: str | None = None  # For impossible_without
    injuries: list[BodyInjury] = field(default_factory=list)

    @property
    def can_perform(self) -> bool:
        return self.impact_type not in ("impossible",)

    @property
    def effectiveness(self) -> float:
        """Returns effectiveness multiplier (0.0 - 1.0)."""
        if self.impact_type == "penalty":
            return 1.0 - (self.value / 100)
        if self.impact_type == "impossible":
            return 0.0
        return 1.0


class InjuryManager(BaseManager):
    """Manages injuries: creation, healing, and activity impact."""

    def get_injuries(self, entity_id: int, active_only: bool = True) -> list[BodyInjury]:
        """Get all injuries for an entity.

        Args:
            entity_id: Entity to query
            active_only: If True, only return unhealed injuries

        Returns:
            List of BodyInjury objects
        """
        query = self.db.query(BodyInjury).filter(
            BodyInjury.entity_id == entity_id,
            BodyInjury.session_id == self.session_id,
        )
        if active_only:
            query = query.filter(BodyInjury.is_healed == False)
        return query.all()

    def get_injury_by_part(
        self,
        entity_id: int,
        body_part: BodyPart,
        active_only: bool = True,
    ) -> list[BodyInjury]:
        """Get injuries to a specific body part."""
        query = self.db.query(BodyInjury).filter(
            BodyInjury.entity_id == entity_id,
            BodyInjury.session_id == self.session_id,
            BodyInjury.body_part == body_part,
        )
        if active_only:
            query = query.filter(BodyInjury.is_healed == False)
        return query.all()

    def add_injury(
        self,
        entity_id: int,
        body_part: BodyPart,
        injury_type: InjuryType,
        severity: InjurySeverity,
        caused_by: str,
        turn: int,
        check_reinjury: bool = True,
    ) -> BodyInjury:
        """Create a new injury for an entity.

        Args:
            entity_id: Entity to injure
            body_part: Body part affected
            injury_type: Type of injury
            severity: How severe
            caused_by: What caused it
            turn: Current game turn
            check_reinjury: Check for existing injuries on same part

        Returns:
            Created BodyInjury
        """
        # Check for reinjury
        is_reinjury = False
        if check_reinjury:
            existing = self.get_injury_by_part(entity_id, body_part)
            if existing:
                is_reinjury = True

        # Calculate base recovery time
        base_time = RECOVERY_TIMES.get(
            injury_type,
            InjuryRecoveryTime(7, 14),
        )
        base_days = base_time.average_days

        # Apply severity multiplier
        severity_mult = SEVERITY_MULTIPLIERS.get(severity, 1.0)
        adjusted_days = base_days * severity_mult

        # Reinjury adds 50%
        if is_reinjury:
            adjusted_days *= 1.5

        # Initial pain level
        pain_level = SEVERITY_PAIN.get(severity, 30)

        # Calculate activity restrictions
        restrictions = self._calculate_restrictions(body_part, injury_type, severity)

        injury = BodyInjury(
            entity_id=entity_id,
            session_id=self.session_id,
            body_part=body_part,
            injury_type=injury_type,
            severity=severity,
            caused_by=caused_by,
            occurred_turn=turn,
            occurred_at=datetime.utcnow(),
            base_recovery_days=base_days,
            adjusted_recovery_days=adjusted_days,
            is_reinjured=is_reinjury,
            current_pain_level=pain_level,
            activity_restrictions=restrictions,
        )

        self.db.add(injury)
        self.db.flush()

        return injury

    def _calculate_restrictions(
        self,
        body_part: BodyPart,
        injury_type: InjuryType,
        severity: InjurySeverity,
    ) -> dict:
        """Calculate activity restrictions for this injury."""
        # Try to find pre-computed restrictions
        stored = (
            self.db.query(ActivityRestriction)
            .filter(
                ActivityRestriction.body_part == body_part,
                ActivityRestriction.injury_type == injury_type,
                ActivityRestriction.severity == severity,
            )
            .all()
        )

        if stored:
            return {
                r.activity_name: {
                    "type": r.impact_type,
                    "value": r.impact_value,
                    "requirement": r.requirement,
                }
                for r in stored
            }

        # Generate default restrictions based on body part and severity
        restrictions = {}
        severity_penalty = {
            InjurySeverity.MINOR: 15,
            InjurySeverity.MODERATE: 35,
            InjurySeverity.SEVERE: 60,
            InjurySeverity.CRITICAL: 100,
        }
        penalty = severity_penalty.get(severity, 30)

        # Leg injuries affect movement
        if body_part in (
            BodyPart.LEFT_LEG,
            BodyPart.RIGHT_LEG,
            BodyPart.LEFT_FOOT,
            BodyPart.RIGHT_FOOT,
            BodyPart.LEFT_HIP,
            BodyPart.RIGHT_HIP,
        ):
            restrictions["walking"] = {
                "type": "painful" if severity == InjurySeverity.MINOR else "penalty",
                "value": penalty,
            }
            restrictions["running"] = {
                "type": "penalty" if severity != InjurySeverity.CRITICAL else "impossible",
                "value": min(penalty * 1.5, 100),
            }
            restrictions["climbing"] = {
                "type": "penalty" if severity != InjurySeverity.CRITICAL else "impossible",
                "value": min(penalty * 1.5, 100),
            }

        # Arm/hand injuries affect manipulation
        if body_part in (
            BodyPart.LEFT_ARM,
            BodyPart.RIGHT_ARM,
            BodyPart.LEFT_HAND,
            BodyPart.RIGHT_HAND,
            BodyPart.LEFT_SHOULDER,
            BodyPart.RIGHT_SHOULDER,
        ):
            restrictions["lifting"] = {
                "type": "penalty" if severity != InjurySeverity.CRITICAL else "impossible",
                "value": penalty,
            }
            restrictions["fine_manipulation"] = {
                "type": "penalty",
                "value": penalty,
            }
            if "hand" in body_part.value.lower():
                restrictions["writing"] = {
                    "type": "impossible" if severity == InjurySeverity.CRITICAL else "penalty",
                    "value": penalty,
                }

        # Head injuries affect cognition
        if body_part == BodyPart.HEAD:
            restrictions["concentration"] = {
                "type": "penalty",
                "value": penalty,
            }
            if injury_type == InjuryType.CONCUSSION:
                restrictions["bright_lights"] = {
                    "type": "painful",
                    "value": penalty,
                }
                restrictions["loud_noises"] = {
                    "type": "painful",
                    "value": penalty,
                }

        # Torso/back injuries affect exertion
        if body_part in (BodyPart.TORSO, BodyPart.BACK):
            restrictions["heavy_lifting"] = {
                "type": "penalty" if severity != InjurySeverity.CRITICAL else "impossible",
                "value": penalty,
            }
            restrictions["bending"] = {
                "type": "painful",
                "value": penalty,
            }

        return restrictions

    def apply_healing(
        self,
        entity_id: int,
        days_passed: float,
        medical_care_quality: int | None = None,
        is_hardy: bool = False,
        age: int | None = None,
    ) -> list[BodyInjury]:
        """Apply healing progress to all injuries.

        Args:
            entity_id: Entity to heal
            days_passed: In-game days that passed
            medical_care_quality: 0-100 quality of care received
            is_hardy: Character has hardy constitution
            age: Character's age (affects healing)

        Returns:
            List of injuries that fully healed this update
        """
        injuries = self.get_injuries(entity_id, active_only=True)
        healed_injuries: list[BodyInjury] = []

        for injury in injuries:
            # Calculate healing rate modifier
            healing_modifier = 1.0

            # Medical care reduces time by up to 30%
            if medical_care_quality is not None:
                if not injury.received_medical_care:
                    injury.received_medical_care = True
                    injury.medical_care_quality = medical_care_quality
                    injury.medical_care_turn = self.current_turn
                    # Reduce remaining time
                    care_reduction = 0.30 * (medical_care_quality / 100)
                    injury.adjusted_recovery_days *= (1 - care_reduction)

            # Hardy constitution
            if is_hardy:
                healing_modifier *= 1.2  # 20% faster healing

            # Age modifier
            if age is not None and age > 50:
                healing_modifier *= 0.77  # 30% slower (1/1.3)

            # Apply healing
            effective_days = days_passed * healing_modifier
            injury.recovery_progress_days += effective_days

            # Update pain level (decreases as healing progresses)
            progress_pct = injury.recovery_progress_days / injury.adjusted_recovery_days
            base_pain = SEVERITY_PAIN.get(injury.severity, 30)
            injury.current_pain_level = int(base_pain * (1 - progress_pct))

            # Check if healed
            if injury.recovery_progress_days >= injury.adjusted_recovery_days:
                injury.is_healed = True
                injury.healed_at = datetime.utcnow()
                injury.healed_turn = self.current_turn
                injury.current_pain_level = 0

                # Check for permanent damage
                if injury.severity in (InjurySeverity.SEVERE, InjurySeverity.CRITICAL):
                    damage_chance = PERMANENT_DAMAGE_CHANCE.get(injury.severity, 0)
                    if random() < damage_chance:
                        injury.has_permanent_damage = True
                        injury.permanent_damage_description = self._generate_permanent_damage(
                            injury.body_part,
                            injury.injury_type,
                        )

                healed_injuries.append(injury)

        self.db.flush()
        return healed_injuries

    def _generate_permanent_damage(
        self,
        body_part: BodyPart,
        injury_type: InjuryType,
    ) -> str:
        """Generate a description of permanent damage."""
        damages = {
            BodyPart.HEAD: [
                "occasional headaches",
                "minor memory issues",
                "sensitivity to bright lights",
            ],
            BodyPart.TORSO: [
                "chronic back pain",
                "reduced lung capacity",
                "visible scarring",
            ],
            BodyPart.BACK: [
                "chronic pain when bending",
                "stiffness in cold weather",
                "reduced flexibility",
            ],
        }

        # Limb damages
        limb_damages = [
            "chronic pain",
            "reduced range of motion",
            "weakness",
            "stiffness in cold weather",
            "visible scarring",
        ]

        if body_part in damages:
            options = damages[body_part]
        else:
            options = limb_damages

        # Pick based on injury type
        if injury_type in (InjuryType.CUT, InjuryType.LACERATION, InjuryType.BURN):
            return "visible scarring"
        elif injury_type == InjuryType.FRACTURE:
            return "chronic pain and stiffness in cold weather"
        elif injury_type == InjuryType.NERVE_DAMAGE:
            return "numbness and reduced sensitivity"
        else:
            return options[0] if options else "chronic discomfort"

    def get_activity_impact(self, entity_id: int, activity: str) -> ActivityImpact:
        """Calculate combined impact of all injuries on an activity.

        Args:
            entity_id: Entity to check
            activity: Activity name (walking, running, lifting, etc.)

        Returns:
            ActivityImpact with combined effects
        """
        injuries = self.get_injuries(entity_id, active_only=True)

        if not injuries:
            return ActivityImpact(impact_type="unaffected")

        # Gather all impacts for this activity
        impacts: list[dict] = []
        affecting_injuries: list[BodyInjury] = []

        for injury in injuries:
            if injury.activity_restrictions and activity in injury.activity_restrictions:
                impacts.append(injury.activity_restrictions[activity])
                affecting_injuries.append(injury)

        if not impacts:
            return ActivityImpact(impact_type="unaffected")

        # Check for impossible
        for impact in impacts:
            if impact.get("type") == "impossible":
                return ActivityImpact(
                    impact_type="impossible",
                    injuries=affecting_injuries,
                )

        # Check for impossible_without
        requirements = []
        for impact in impacts:
            if impact.get("type") == "impossible_without":
                if impact.get("requirement"):
                    requirements.append(impact["requirement"])

        if requirements:
            return ActivityImpact(
                impact_type="impossible_without",
                requirement=", ".join(set(requirements)),
                injuries=affecting_injuries,
            )

        # Combine penalties (multiply effectiveness)
        total_effectiveness = 1.0
        max_pain = 0

        for impact in impacts:
            if impact.get("type") == "penalty":
                penalty_pct = impact.get("value", 0) / 100
                total_effectiveness *= (1 - penalty_pct)
            elif impact.get("type") == "painful":
                pain_value = impact.get("value", 0)
                max_pain = max(max_pain, pain_value)

        # Convert back to penalty percentage
        total_penalty = int((1 - total_effectiveness) * 100)

        if total_penalty >= 100:
            return ActivityImpact(
                impact_type="impossible",
                injuries=affecting_injuries,
            )
        elif max_pain > 0 and total_penalty == 0:
            return ActivityImpact(
                impact_type="painful",
                value=max_pain,
                injuries=affecting_injuries,
            )
        elif total_penalty > 0:
            return ActivityImpact(
                impact_type="penalty",
                value=total_penalty,
                injuries=affecting_injuries,
            )
        else:
            return ActivityImpact(impact_type="unaffected")

    def get_total_pain(self, entity_id: int) -> int:
        """Calculate total pain level from all injuries (0-100)."""
        injuries = self.get_injuries(entity_id, active_only=True)
        if not injuries:
            return 0

        # Pain doesn't simply add up - it's more like taking the max with some addition
        pain_levels = [i.current_pain_level for i in injuries]
        if not pain_levels:
            return 0

        max_pain = max(pain_levels)
        additional_pain = sum(p for p in pain_levels if p != max_pain) * 0.3

        return min(100, int(max_pain + additional_pain))

    def sync_pain_to_needs(self, entity_id: int, needs_manager: "NeedsManager") -> None:
        """Sync injury pain to character needs wellness value.

        Wellness is inverted from pain: 0 = agony, 100 = pain-free.
        """
        total_pain = self.get_total_pain(entity_id)
        needs = needs_manager.get_or_create_needs(entity_id)
        needs.wellness = 100 - total_pain
        self.db.flush()

    def get_injuries_summary(self, entity_id: int) -> dict:
        """Get summary of all injuries for context/display."""
        injuries = self.get_injuries(entity_id, active_only=True)

        if not injuries:
            return {"has_injuries": False, "injuries": [], "total_pain": 0}

        return {
            "has_injuries": True,
            "injuries": [
                {
                    "body_part": i.body_part.value,
                    "type": i.injury_type.value,
                    "severity": i.severity.value,
                    "pain": i.current_pain_level,
                    "healing_progress": round(
                        i.recovery_progress_days / i.adjusted_recovery_days * 100, 1
                    ),
                    "days_remaining": max(
                        0, round(i.adjusted_recovery_days - i.recovery_progress_days, 1)
                    ),
                    "is_infected": i.is_infected,
                    "has_permanent_damage": i.has_permanent_damage,
                }
                for i in injuries
            ],
            "total_pain": self.get_total_pain(entity_id),
            "permanent_conditions": [
                {
                    "body_part": i.body_part.value,
                    "description": i.permanent_damage_description,
                }
                for i in self.get_injuries(entity_id, active_only=False)
                if i.has_permanent_damage
            ],
        }
