"""Progression Manager for skill advancement through usage.

This manager handles character progression by tracking skill usage
and advancing proficiency based on successful use. Uses diminishing
returns to model realistic skill development.

Advancement Formula:
- Uses 1-10: No advancement (learning basics)
- Uses 11-25: +3 proficiency per 5 successful uses (fast early learning)
- Uses 26-50: +2 proficiency per 5 successful uses (steady growth)
- Uses 51-100: +1 proficiency per 5 successful uses (mastery)
- Uses 100+: +1 proficiency per 10 successful uses (refinement)
"""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import Session

from src.database.models.entities import Entity, EntitySkill
from src.database.models.session import GameSession
from src.dice.checks import get_proficiency_tier_name, proficiency_to_modifier
from src.managers.base import BaseManager


# Advancement milestones: (min_uses, max_uses, uses_per_milestone, proficiency_gain)
ADVANCEMENT_TIERS = [
    (1, 10, None, 0),      # No advancement in first 10 uses
    (11, 25, 5, 3),        # Fast early learning: +3 per 5 uses
    (26, 50, 5, 2),        # Steady growth: +2 per 5 uses
    (51, 100, 5, 1),       # Mastery: +1 per 5 uses
    (101, float('inf'), 10, 1),  # Refinement: +1 per 10 uses
]

# Maximum proficiency level
MAX_PROFICIENCY = 100


@dataclass
class AdvancementResult:
    """Result of recording a skill use."""

    skill_key: str
    usage_count: int
    successful_uses: int
    advanced: bool = False
    proficiency_gained: int = 0
    new_proficiency: int = 0
    tier_changed: bool = False
    old_tier: str | None = None
    new_tier: str | None = None


@dataclass
class SkillProgress:
    """Progress information for a skill."""

    skill_key: str
    proficiency_level: int
    tier_name: str
    usage_count: int
    successful_uses: int
    uses_to_next_milestone: int
    next_milestone_gain: int


class ProgressionManager(BaseManager):
    """Manages character skill progression through usage.

    Tracks skill usage and advances proficiency based on successful
    use with diminishing returns at higher levels.
    """

    def record_skill_use(
        self,
        entity_key: str,
        skill_key: str,
        success: bool,
    ) -> AdvancementResult:
        """Record a skill use and check for advancement.

        Args:
            entity_key: Entity key of the character.
            skill_key: Key of the skill being used.
            success: Whether the skill check was successful.

        Returns:
            AdvancementResult with usage counts and any advancement.

        Raises:
            ValueError: If entity not found.
        """
        entity = self._get_entity(entity_key)
        if not entity:
            raise ValueError(f"Entity '{entity_key}' not found")

        # Get or create skill
        skill = self._get_or_create_skill(entity.id, skill_key)

        # Record usage
        skill.usage_count += 1
        if success:
            skill.successful_uses += 1

        # Check for advancement (only on successful use)
        old_proficiency = skill.proficiency_level
        old_tier = get_proficiency_tier_name(old_proficiency)

        advanced = False
        proficiency_gained = 0

        if success:
            proficiency_gained = self._calculate_advancement(skill.successful_uses)
            if proficiency_gained > 0:
                skill.proficiency_level = min(
                    MAX_PROFICIENCY,
                    skill.proficiency_level + proficiency_gained
                )
                advanced = True

        new_tier = get_proficiency_tier_name(skill.proficiency_level)
        tier_changed = advanced and old_tier != new_tier

        self.db.commit()
        self.db.refresh(skill)

        return AdvancementResult(
            skill_key=skill_key,
            usage_count=skill.usage_count,
            successful_uses=skill.successful_uses,
            advanced=advanced,
            proficiency_gained=proficiency_gained,
            new_proficiency=skill.proficiency_level,
            tier_changed=tier_changed,
            old_tier=old_tier if tier_changed else None,
            new_tier=new_tier if tier_changed else None,
        )

    def advance_skill(
        self,
        entity_key: str,
        skill_key: str,
        amount: int,
        reason: str | None = None,
    ) -> AdvancementResult:
        """Manually advance a skill (training, learning from master, etc.).

        Args:
            entity_key: Entity key of the character.
            skill_key: Key of the skill to advance.
            amount: Amount of proficiency to gain.
            reason: Optional reason for advancement.

        Returns:
            AdvancementResult with the advancement details.

        Raises:
            ValueError: If entity not found.
        """
        entity = self._get_entity(entity_key)
        if not entity:
            raise ValueError(f"Entity '{entity_key}' not found")

        skill = self._get_or_create_skill(entity.id, skill_key)

        old_proficiency = skill.proficiency_level
        old_tier = get_proficiency_tier_name(old_proficiency)

        # Calculate actual gain (respecting cap)
        actual_gain = min(amount, MAX_PROFICIENCY - skill.proficiency_level)
        skill.proficiency_level += actual_gain

        new_tier = get_proficiency_tier_name(skill.proficiency_level)
        tier_changed = old_tier != new_tier

        self.db.commit()
        self.db.refresh(skill)

        return AdvancementResult(
            skill_key=skill_key,
            usage_count=skill.usage_count,
            successful_uses=skill.successful_uses,
            advanced=actual_gain > 0,
            proficiency_gained=actual_gain,
            new_proficiency=skill.proficiency_level,
            tier_changed=tier_changed,
            old_tier=old_tier if tier_changed else None,
            new_tier=new_tier if tier_changed else None,
        )

    def get_skill_progress(
        self,
        entity_key: str,
        skill_key: str,
    ) -> SkillProgress | None:
        """Get progress information for a specific skill.

        Args:
            entity_key: Entity key of the character.
            skill_key: Key of the skill.

        Returns:
            SkillProgress if skill exists, None otherwise.
        """
        entity = self._get_entity(entity_key)
        if not entity:
            return None

        skill = (
            self.db.query(EntitySkill)
            .filter(
                and_(
                    EntitySkill.entity_id == entity.id,
                    EntitySkill.skill_key == skill_key,
                )
            )
            .first()
        )

        if not skill:
            return None

        uses_to_next, next_gain = self._get_next_milestone_info(skill.successful_uses)

        return SkillProgress(
            skill_key=skill.skill_key,
            proficiency_level=skill.proficiency_level,
            tier_name=get_proficiency_tier_name(skill.proficiency_level),
            usage_count=skill.usage_count,
            successful_uses=skill.successful_uses,
            uses_to_next_milestone=uses_to_next,
            next_milestone_gain=next_gain,
        )

    def get_all_skill_progress(
        self,
        entity_key: str,
    ) -> list[SkillProgress]:
        """Get progress information for all skills.

        Args:
            entity_key: Entity key of the character.

        Returns:
            List of SkillProgress for all skills.
        """
        entity = self._get_entity(entity_key)
        if not entity:
            return []

        skills = (
            self.db.query(EntitySkill)
            .filter(EntitySkill.entity_id == entity.id)
            .all()
        )

        result = []
        for skill in skills:
            uses_to_next, next_gain = self._get_next_milestone_info(skill.successful_uses)
            result.append(SkillProgress(
                skill_key=skill.skill_key,
                proficiency_level=skill.proficiency_level,
                tier_name=get_proficiency_tier_name(skill.proficiency_level),
                usage_count=skill.usage_count,
                successful_uses=skill.successful_uses,
                uses_to_next_milestone=uses_to_next,
                next_milestone_gain=next_gain,
            ))

        return result

    def get_progression_context(self, entity_key: str) -> str:
        """Generate context string for skill progression.

        Args:
            entity_key: Entity key of the character.

        Returns:
            Formatted string with skill progress information.
        """
        all_progress = self.get_all_skill_progress(entity_key)
        if not all_progress:
            return ""

        lines = ["## Skill Progress"]
        for progress in sorted(all_progress, key=lambda p: -p.proficiency_level):
            lines.append(
                f"- {progress.skill_key}: {progress.tier_name} "
                f"({progress.proficiency_level}/100) - "
                f"{progress.successful_uses} successful uses"
            )

        return "\n".join(lines)

    def _get_entity(self, entity_key: str) -> Entity | None:
        """Get entity by key within session scope."""
        return (
            self.db.query(Entity)
            .filter(
                and_(
                    Entity.session_id == self.session_id,
                    Entity.entity_key == entity_key,
                )
            )
            .first()
        )

    def _get_or_create_skill(
        self,
        entity_id: int,
        skill_key: str,
    ) -> EntitySkill:
        """Get or create a skill for an entity."""
        skill = (
            self.db.query(EntitySkill)
            .filter(
                and_(
                    EntitySkill.entity_id == entity_id,
                    EntitySkill.skill_key == skill_key,
                )
            )
            .first()
        )

        if not skill:
            skill = EntitySkill(
                entity_id=entity_id,
                skill_key=skill_key,
                proficiency_level=1,
                usage_count=0,
                successful_uses=0,
            )
            self.db.add(skill)
            self.db.flush()

        return skill

    def _calculate_advancement(self, successful_uses: int) -> int:
        """Calculate proficiency gain based on successful uses.

        Uses milestone system - advancement happens when crossing
        milestone boundaries within each tier.

        Args:
            successful_uses: Total successful uses (including current).

        Returns:
            Proficiency points gained (0 if no milestone crossed).
        """
        for min_uses, max_uses, uses_per_milestone, gain in ADVANCEMENT_TIERS:
            if min_uses <= successful_uses <= max_uses:
                if uses_per_milestone is None:
                    return 0  # No advancement in this tier

                # Check if we crossed a milestone
                # Milestone at: min_uses + uses_per_milestone, min_uses + 2*uses_per_milestone, etc.
                uses_in_tier = successful_uses - min_uses + 1
                if uses_in_tier % uses_per_milestone == 0:
                    return gain

                return 0

        return 0

    def _get_next_milestone_info(
        self,
        successful_uses: int,
    ) -> tuple[int, int]:
        """Get info about the next milestone.

        Args:
            successful_uses: Current successful uses.

        Returns:
            Tuple of (uses_to_next_milestone, proficiency_gain_at_milestone).
        """
        for min_uses, max_uses, uses_per_milestone, gain in ADVANCEMENT_TIERS:
            if min_uses <= successful_uses <= max_uses:
                if uses_per_milestone is None:
                    # In no-advancement tier, calculate to next tier
                    return max_uses - successful_uses + 1, 3  # Next tier gives +3

                uses_in_tier = successful_uses - min_uses + 1
                uses_to_next = uses_per_milestone - (uses_in_tier % uses_per_milestone)
                if uses_to_next == uses_per_milestone:
                    uses_to_next = 0  # At a milestone right now
                return uses_to_next, gain

            elif successful_uses < min_uses:
                # Haven't reached this tier yet
                return min_uses - successful_uses, gain if gain > 0 else 3

        # Past all tiers (in refinement)
        return 10 - (successful_uses % 10), 1
