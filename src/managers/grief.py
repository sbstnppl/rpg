"""Grief management for NPCs who lost someone they cared about."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from src.database.models.enums import GriefStage
from src.database.models.mental_state import GriefCondition
from src.database.models.relationships import Relationship
from src.database.models.session import GameSession
from src.managers.base import BaseManager


@dataclass
class GriefStageInfo:
    """Information about a grief stage."""

    stage: GriefStage
    min_duration_days: int
    max_duration_days: int
    morale_modifier: int
    behavioral_changes: dict


# Grief stage definitions
GRIEF_STAGES: dict[GriefStage, GriefStageInfo] = {
    GriefStage.SHOCK: GriefStageInfo(
        stage=GriefStage.SHOCK,
        min_duration_days=1,
        max_duration_days=3,
        morale_modifier=-20,
        behavioral_changes={
            "focus_penalty": -3,
            "emotional_numbness": True,
            "social_withdrawal": 0.3,
        },
    ),
    GriefStage.DENIAL: GriefStageInfo(
        stage=GriefStage.DENIAL,
        min_duration_days=3,
        max_duration_days=7,
        morale_modifier=-15,
        behavioral_changes={
            "mentions_deceased_present_tense": True,
            "avoids_death_topic": True,
        },
    ),
    GriefStage.ANGER: GriefStageInfo(
        stage=GriefStage.ANGER,
        min_duration_days=7,
        max_duration_days=14,
        morale_modifier=-15,
        behavioral_changes={
            "irritability": 0.5,
            "aggression_bonus": 10,
            "blame_seeking": True,
        },
    ),
    GriefStage.BARGAINING: GriefStageInfo(
        stage=GriefStage.BARGAINING,
        min_duration_days=3,
        max_duration_days=7,
        morale_modifier=-20,
        behavioral_changes={
            "magical_thinking": True,
            "seeking_meaning": True,
            "what_if_thoughts": True,
        },
    ),
    GriefStage.DEPRESSION: GriefStageInfo(
        stage=GriefStage.DEPRESSION,
        min_duration_days=14,
        max_duration_days=28,
        morale_modifier=-25,
        behavioral_changes={
            "energy_penalty": -30,
            "social_withdrawal": 0.6,
            "crying_spells": 0.3,
            "appetite_loss": True,
            "sleep_disruption": True,
        },
    ),
    GriefStage.ACCEPTANCE: GriefStageInfo(
        stage=GriefStage.ACCEPTANCE,
        min_duration_days=7,
        max_duration_days=21,
        morale_modifier=-5,
        behavioral_changes={
            "can_discuss_deceased": True,
            "gradual_recovery": True,
            "new_normal": True,
        },
    ),
}

# Stage progression order
STAGE_ORDER = [
    GriefStage.SHOCK,
    GriefStage.DENIAL,
    GriefStage.ANGER,
    GriefStage.BARGAINING,
    GriefStage.DEPRESSION,
    GriefStage.ACCEPTANCE,
]


class GriefManager(BaseManager):
    """Manages grief conditions and stage progression."""

    def get_grief_conditions(
        self,
        entity_id: int,
        active_only: bool = True,
    ) -> list[GriefCondition]:
        """Get all grief conditions for an entity.

        Args:
            entity_id: Entity to query
            active_only: If True, only return unresolved grief

        Returns:
            List of GriefCondition objects
        """
        query = self.db.query(GriefCondition).filter(
            GriefCondition.entity_id == entity_id,
            GriefCondition.session_id == self.session_id,
        )
        if active_only:
            query = query.filter(GriefCondition.is_resolved == False)
        return query.all()

    def get_grief_for_deceased(
        self,
        entity_id: int,
        deceased_id: int,
    ) -> GriefCondition | None:
        """Get grief condition for a specific deceased entity."""
        return (
            self.db.query(GriefCondition)
            .filter(
                GriefCondition.entity_id == entity_id,
                GriefCondition.deceased_entity_id == deceased_id,
                GriefCondition.session_id == self.session_id,
                GriefCondition.is_resolved == False,
            )
            .first()
        )

    def start_grief(
        self,
        entity_id: int,
        deceased_id: int,
        blamed_entity_key: str | None = None,
    ) -> GriefCondition:
        """Start grief process when someone dies.

        Args:
            entity_id: The grieving entity
            deceased_id: The entity who died
            blamed_entity_key: Optional key of who they blame

        Returns:
            Created GriefCondition
        """
        # Check if already grieving this person
        existing = self.get_grief_for_deceased(entity_id, deceased_id)
        if existing:
            return existing

        # Calculate intensity based on relationship
        intensity = self._calculate_grief_intensity(entity_id, deceased_id)

        # Calculate expected duration based on intensity
        # More intense grief = longer duration
        base_duration = 30  # Base 30 days
        intensity_multiplier = intensity / 50  # 50 intensity = 1x duration
        expected_duration = int(base_duration * intensity_multiplier)
        expected_duration = max(14, min(90, expected_duration))  # 2 weeks to 3 months

        stage_info = GRIEF_STAGES[GriefStage.SHOCK]

        grief = GriefCondition(
            entity_id=entity_id,
            deceased_entity_id=deceased_id,
            session_id=self.session_id,
            grief_stage=GriefStage.SHOCK,
            intensity=intensity,
            started_turn=self.current_turn,
            started_at=datetime.utcnow(),
            current_stage_started_turn=self.current_turn,
            expected_duration_days=expected_duration,
            morale_modifier=stage_info.morale_modifier,
            behavioral_changes=stage_info.behavioral_changes,
            blames_someone=blamed_entity_key is not None,
            blamed_entity_key=blamed_entity_key,
        )

        self.db.add(grief)
        self.db.flush()
        return grief

    def _calculate_grief_intensity(self, entity_id: int, deceased_id: int) -> int:
        """Calculate grief intensity based on relationship strength.

        Returns 0-100 intensity based on:
        - Trust level
        - Liking level
        - Familiarity level

        Returns:
            Intensity 0-100
        """
        relationship = (
            self.db.query(Relationship)
            .filter(
                Relationship.source_entity_id == entity_id,
                Relationship.target_entity_id == deceased_id,
                Relationship.session_id == self.session_id,
            )
            .first()
        )

        if relationship is None:
            return 20  # Minimal grief for strangers

        # Weight the components
        trust_weight = 0.35
        liking_weight = 0.40
        familiarity_weight = 0.25

        intensity = (
            relationship.trust * trust_weight
            + relationship.liking * liking_weight
            + relationship.familiarity * familiarity_weight
        )

        # Romantic relationships intensify grief
        if relationship.romantic_interest > 50:
            intensity *= 1.3

        return self._clamp(int(intensity))

    def progress_grief(
        self,
        entity_id: int,
        days_passed: float,
        had_support: bool = False,
        had_therapy: bool = False,
    ) -> list[tuple[GriefCondition, GriefStage | None]]:
        """Progress all active grief conditions.

        Args:
            entity_id: Entity to update
            days_passed: In-game days that passed
            had_support: Entity had social support
            had_therapy: Entity received counseling

        Returns:
            List of (grief_condition, new_stage_or_none) tuples
        """
        griefs = self.get_grief_conditions(entity_id, active_only=True)
        results: list[tuple[GriefCondition, GriefStage | None]] = []

        for grief in griefs:
            new_stage = self._progress_single_grief(grief, days_passed, had_support, had_therapy)
            results.append((grief, new_stage))

        self.db.flush()
        return results

    def _progress_single_grief(
        self,
        grief: GriefCondition,
        days_passed: float,
        had_support: bool,
        had_therapy: bool,
    ) -> GriefStage | None:
        """Progress a single grief condition.

        Returns new stage if stage changed, None otherwise.
        """
        if grief.is_resolved:
            return None

        # Calculate how many turns in current stage
        turns_in_stage = self.current_turn - grief.current_stage_started_turn

        # Assume ~3 turns per day (8 hours each)
        days_in_stage = turns_in_stage / 3

        # Get current stage info
        current_idx = STAGE_ORDER.index(grief.grief_stage)
        stage_info = GRIEF_STAGES[grief.grief_stage]

        # Calculate stage duration based on intensity
        intensity_multiplier = grief.intensity / 50
        min_days = stage_info.min_duration_days * intensity_multiplier
        max_days = stage_info.max_duration_days * intensity_multiplier

        # Support and therapy reduce duration
        if had_support:
            max_days *= 0.8
        if had_therapy:
            max_days *= 0.7

        # Check if ready to progress
        if days_in_stage >= min_days:
            # Calculate chance of progression
            # Increases as we approach max_days
            progress_chance = (days_in_stage - min_days) / (max_days - min_days + 1)
            progress_chance = min(1.0, progress_chance)

            # Random progression based on days
            import random

            if random.random() < progress_chance or days_in_stage >= max_days:
                # Move to next stage
                if current_idx + 1 < len(STAGE_ORDER):
                    new_stage = STAGE_ORDER[current_idx + 1]
                    grief.grief_stage = new_stage
                    grief.current_stage_started_turn = self.current_turn

                    # Update modifiers for new stage
                    new_stage_info = GRIEF_STAGES[new_stage]
                    grief.morale_modifier = new_stage_info.morale_modifier
                    grief.behavioral_changes = new_stage_info.behavioral_changes

                    # Check if accepted = resolved
                    if new_stage == GriefStage.ACCEPTANCE:
                        # Will resolve after acceptance duration
                        pass

                    return new_stage
                else:
                    # Past acceptance - resolve grief
                    grief.is_resolved = True
                    grief.resolved_turn = self.current_turn
                    return None

        return None

    def get_total_morale_modifier(self, entity_id: int) -> int:
        """Get total morale modifier from all active grief conditions."""
        griefs = self.get_grief_conditions(entity_id, active_only=True)
        if not griefs:
            return 0

        # Take the worst modifier (most negative)
        return min(g.morale_modifier for g in griefs)

    def get_behavioral_effects(self, entity_id: int) -> dict:
        """Get combined behavioral effects from all active grief.

        Returns merged dict of all behavioral changes.
        """
        griefs = self.get_grief_conditions(entity_id, active_only=True)
        if not griefs:
            return {}

        combined: dict = {}
        for grief in griefs:
            if grief.behavioral_changes:
                for key, value in grief.behavioral_changes.items():
                    if key in combined:
                        # For numeric values, take the more severe
                        if isinstance(value, (int, float)) and isinstance(combined[key], (int, float)):
                            if value < 0:
                                combined[key] = min(combined[key], value)
                            else:
                                combined[key] = max(combined[key], value)
                        # For booleans, OR them
                        elif isinstance(value, bool):
                            combined[key] = combined[key] or value
                    else:
                        combined[key] = value

        return combined

    def trigger_grief_event(
        self,
        entity_id: int,
        event_type: str,
    ) -> dict | None:
        """Trigger a grief-related event based on current stage.

        Args:
            entity_id: Grieving entity
            event_type: Type of trigger (mention_deceased, anniversary, etc.)

        Returns:
            Event details if triggered, None otherwise
        """
        griefs = self.get_grief_conditions(entity_id, active_only=True)
        if not griefs:
            return None

        # Get most intense grief
        primary_grief = max(griefs, key=lambda g: g.intensity)
        behaviors = primary_grief.behavioral_changes or {}

        if event_type == "mention_deceased":
            if primary_grief.grief_stage == GriefStage.DENIAL:
                return {
                    "reaction": "avoidance",
                    "description": "changes the subject, pretends not to hear",
                }
            elif primary_grief.grief_stage == GriefStage.ANGER:
                return {
                    "reaction": "anger",
                    "description": "becomes visibly upset, may lash out",
                }
            elif primary_grief.grief_stage == GriefStage.DEPRESSION:
                return {
                    "reaction": "tears",
                    "description": "eyes well up, voice breaks",
                }
            elif primary_grief.grief_stage == GriefStage.ACCEPTANCE:
                return {
                    "reaction": "bittersweet",
                    "description": "smiles sadly, shares a memory",
                }

        if event_type == "anniversary" or event_type == "reminder":
            import random

            if random.random() < 0.5:
                return {
                    "reaction": "grief_wave",
                    "description": "hit by a wave of grief, needs a moment",
                    "morale_penalty": -10,
                }

        return None

    def find_npcs_grieving_for(self, deceased_id: int) -> list[int]:
        """Find all NPCs who are grieving for a specific deceased entity.

        Returns:
            List of entity IDs who are grieving
        """
        griefs = (
            self.db.query(GriefCondition)
            .filter(
                GriefCondition.deceased_entity_id == deceased_id,
                GriefCondition.session_id == self.session_id,
                GriefCondition.is_resolved == False,
            )
            .all()
        )
        return [g.entity_id for g in griefs]

    def get_grief_summary(self, entity_id: int) -> dict:
        """Get summary of grief state for context/display."""
        griefs = self.get_grief_conditions(entity_id, active_only=True)

        if not griefs:
            return {"is_grieving": False}

        return {
            "is_grieving": True,
            "grief_count": len(griefs),
            "griefs": [
                {
                    "deceased_entity_id": g.deceased_entity_id,
                    "stage": g.grief_stage.value,
                    "intensity": g.intensity,
                    "morale_modifier": g.morale_modifier,
                    "blames": g.blamed_entity_key,
                }
                for g in griefs
            ],
            "total_morale_modifier": self.get_total_morale_modifier(entity_id),
            "behavioral_effects": self.get_behavioral_effects(entity_id),
        }
