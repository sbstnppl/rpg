"""Relationship management with personality trait modifiers."""

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models.entities import Entity, NPCExtension
from src.database.models.relationships import (
    Relationship,
    RelationshipChange,
    RelationshipMilestone,
)
from src.database.models.session import GameSession
from src.managers.base import BaseManager


# Relationship dimensions
RelationshipDimension = Literal[
    "trust", "liking", "respect", "romantic_interest",
    "familiarity", "fear", "social_debt"
]

# Which dimensions are core (0-100) vs context (-100 to 100 for social_debt)
CORE_DIMENSIONS = {"trust", "liking", "respect", "romantic_interest", "familiarity", "fear"}
SIGNED_DIMENSIONS = {"social_debt"}


@dataclass
class PersonalityModifiers:
    """Modifiers derived from personality traits."""

    trust_gain_mult: float = 1.0
    trust_loss_mult: float = 1.0
    liking_gain_mult: float = 1.0
    liking_loss_mult: float = 1.0
    respect_gain_mult: float = 1.0
    respect_loss_mult: float = 1.0
    familiarity_gain_mult: float = 1.0
    romantic_gain_mult: float = 1.0
    fear_decay_mult: float = 1.0
    max_liking_while_unfamiliar: int = 100  # Cap when familiarity < 30
    respect_importance_mult: float = 1.0  # How much respect affects other dimensions


# Personality trait effects
PERSONALITY_EFFECTS: dict[str, dict] = {
    "suspicious": {
        "trust_gain_mult": 0.5,
        "trust_loss_mult": 2.0,
    },
    "trusting": {
        "trust_gain_mult": 1.5,
        "trust_loss_mult": 0.7,
    },
    "forgiving": {
        "trust_loss_mult": 0.5,
        "liking_loss_mult": 0.5,
    },
    "grudge_holder": {
        "trust_loss_mult": 1.5,
        "liking_loss_mult": 1.5,
    },
    "shy": {
        "familiarity_gain_mult": 0.6,
        "max_liking_while_unfamiliar": 40,
    },
    "outgoing": {
        "familiarity_gain_mult": 1.5,
    },
    "prideful": {
        "respect_importance_mult": 2.0,
    },
    "humble": {
        "respect_importance_mult": 0.5,
    },
    "romantic": {
        "romantic_gain_mult": 1.5,
    },
    "reserved": {
        "romantic_gain_mult": 0.5,
    },
    "fearless": {
        "fear_decay_mult": 2.0,  # Fear fades faster
    },
    "anxious": {
        "fear_decay_mult": 0.5,  # Fear persists longer
    },
}


# Milestone thresholds configuration
# Format: (dimension, milestone_type, threshold, direction, message_template)
MILESTONE_THRESHOLDS: list[tuple[str, str, int, str, str]] = [
    ("trust", "earned_trust", 70, "up", "{from_name} has earned {to_name}'s trust!"),
    ("trust", "lost_trust", 30, "down", "{from_name} has lost {to_name}'s trust."),
    ("liking", "became_friends", 70, "up", "{from_name} has become friends with {to_name}!"),
    ("liking", "made_enemy", 30, "down", "{from_name} has made an enemy of {to_name}."),
    ("respect", "earned_respect", 70, "up", "{from_name} has earned {to_name}'s respect!"),
    ("respect", "lost_respect", 30, "down", "{from_name} has lost {to_name}'s respect."),
    ("romantic_interest", "romantic_spark", 30, "up", "{to_name} has caught {from_name}'s eye!"),
    ("romantic_interest", "romantic_interest", 50, "up", "{to_name} has captured {from_name}'s heart!"),
    ("familiarity", "close_bond", 70, "up", "{from_name} and {to_name} have formed a close bond!"),
    ("fear", "terrified", 70, "up", "{from_name} is terrified of {to_name}!"),
]


@dataclass
class MilestoneInfo:
    """Information about a relationship milestone."""

    id: int
    milestone_type: str
    dimension: str
    threshold_value: int
    direction: str
    message: str
    notified: bool
    turn_number: int
    from_entity_id: int
    to_entity_id: int
    from_entity_name: str | None = None
    to_entity_name: str | None = None


class RelationshipManager(BaseManager):
    """Manages relationships between entities with personality modifiers."""

    def get_relationship(
        self, from_id: int, to_id: int
    ) -> Relationship | None:
        """Get existing relationship from one entity to another."""
        return (
            self.db.query(Relationship)
            .filter(
                Relationship.session_id == self.session_id,
                Relationship.from_entity_id == from_id,
                Relationship.to_entity_id == to_id,
            )
            .first()
        )

    def get_or_create_relationship(
        self, from_id: int, to_id: int
    ) -> Relationship:
        """Get or create relationship from one entity to another."""
        rel = self.get_relationship(from_id, to_id)
        if rel is None:
            rel = Relationship(
                session_id=self.session_id,
                from_entity_id=from_id,
                to_entity_id=to_id,
                knows=False,
            )
            self.db.add(rel)
            self.db.flush()
        return rel

    def get_attitude(self, from_id: int, to_id: int) -> dict:
        """Get attitude summary from one entity toward another.

        Returns dict with all relationship dimensions and derived info.
        """
        rel = self.get_relationship(from_id, to_id)
        if rel is None:
            return {
                "knows": False,
                "trust": 50,
                "liking": 50,
                "respect": 50,
                "romantic_interest": 0,
                "familiarity": 0,
                "fear": 0,
                "social_debt": 0,
                "mood_modifier": 0,
                "effective_liking": 50,  # Includes mood
            }

        # Calculate effective values with mood modifier
        effective_liking = self._clamp(rel.liking + rel.mood_modifier)

        return {
            "knows": rel.knows,
            "trust": rel.trust,
            "liking": rel.liking,
            "respect": rel.respect,
            "romantic_interest": rel.romantic_interest,
            "familiarity": rel.familiarity,
            "fear": rel.fear,
            "social_debt": rel.social_debt,
            "mood_modifier": rel.mood_modifier,
            "mood_reason": rel.mood_reason,
            "effective_liking": effective_liking,
            "relationship_type": rel.relationship_type,
            "relationship_status": rel.relationship_status,
        }

    def record_meeting(
        self,
        entity1_id: int,
        entity2_id: int,
        location: str,
    ) -> tuple[Relationship, Relationship]:
        """Record that two entities have met for the first time.

        Creates bidirectional relationships if needed.

        Returns:
            Tuple of (entity1's relationship to entity2, entity2's relationship to entity1)
        """
        rel1 = self.get_or_create_relationship(entity1_id, entity2_id)
        rel2 = self.get_or_create_relationship(entity2_id, entity1_id)

        # Mark as having met
        for rel in [rel1, rel2]:
            if not rel.knows:
                rel.knows = True
                rel.first_met_turn = self.current_turn
                rel.first_met_location = location
                rel.last_interaction_turn = self.current_turn

                # Initial familiarity bump from meeting
                rel.familiarity = max(rel.familiarity, 5)

        self.db.flush()
        return rel1, rel2

    def update_attitude(
        self,
        from_id: int,
        to_id: int,
        dimension: RelationshipDimension,
        delta: int,
        reason: str,
        apply_personality: bool = True,
    ) -> Relationship:
        """Update a relationship dimension with personality modifiers.

        Args:
            from_id: Entity whose attitude is changing
            to_id: Entity they have attitude toward
            dimension: Which dimension to change
            delta: Base amount to change (positive or negative)
            reason: Why this change is happening
            apply_personality: Whether to apply personality trait modifiers

        Returns:
            Updated Relationship
        """
        rel = self.get_or_create_relationship(from_id, to_id)
        rel.last_interaction_turn = self.current_turn

        # Get current value
        old_value = getattr(rel, dimension)

        # Apply personality modifiers if entity is NPC with traits
        if apply_personality:
            delta = self._apply_personality_modifiers(from_id, dimension, delta)

        # Apply familiarity cap for strangers
        if dimension in ("trust", "liking", "respect", "romantic_interest"):
            delta = self._apply_familiarity_cap(rel.familiarity, dimension, old_value, delta)

        # Calculate new value
        if dimension in SIGNED_DIMENSIONS:
            new_value = max(-100, min(100, old_value + delta))
        else:
            new_value = self._clamp(old_value + delta)

        # Update
        setattr(rel, dimension, new_value)

        # Record change in audit log
        if delta != 0:
            change = RelationshipChange(
                relationship_id=rel.id,
                dimension=dimension,
                old_value=old_value,
                new_value=new_value,
                delta=new_value - old_value,
                reason=reason,
                turn_number=self.current_turn,
            )
            self.db.add(change)

        # Check for milestone crossings
        self._check_milestones(rel, dimension, old_value, new_value)

        self.db.flush()
        return rel

    def _get_personality_traits(self, entity_id: int) -> dict | None:
        """Get personality traits for an entity."""
        npc_ext = (
            self.db.query(NPCExtension)
            .filter(NPCExtension.entity_id == entity_id)
            .first()
        )
        if npc_ext and npc_ext.personality_traits:
            return npc_ext.personality_traits
        return None

    def get_personality_modifiers(self, entity_id: int) -> PersonalityModifiers:
        """Calculate personality modifiers for an entity.

        Combines all active traits into a single modifier set.
        """
        traits = self._get_personality_traits(entity_id)
        mods = PersonalityModifiers()

        if not traits:
            return mods

        # Apply each trait that's True
        for trait_name, is_active in traits.items():
            if not is_active:
                continue
            if trait_name not in PERSONALITY_EFFECTS:
                continue

            effects = PERSONALITY_EFFECTS[trait_name]
            for attr, value in effects.items():
                if hasattr(mods, attr):
                    # Multiply multiplicative modifiers
                    if attr.endswith("_mult"):
                        current = getattr(mods, attr)
                        setattr(mods, attr, current * value)
                    else:
                        # Take minimum for caps
                        current = getattr(mods, attr)
                        setattr(mods, attr, min(current, value))

        return mods

    def _apply_personality_modifiers(
        self,
        entity_id: int,
        dimension: str,
        delta: int,
    ) -> int:
        """Apply personality modifiers to a relationship delta.

        Returns modified delta.
        """
        mods = self.get_personality_modifiers(entity_id)
        is_positive = delta > 0

        if dimension == "trust":
            mult = mods.trust_gain_mult if is_positive else mods.trust_loss_mult
        elif dimension == "liking":
            mult = mods.liking_gain_mult if is_positive else mods.liking_loss_mult
        elif dimension == "respect":
            mult = mods.respect_gain_mult if is_positive else mods.respect_loss_mult
        elif dimension == "familiarity":
            mult = mods.familiarity_gain_mult if is_positive else 1.0
        elif dimension == "romantic_interest":
            mult = mods.romantic_gain_mult if is_positive else 1.0
        elif dimension == "fear":
            # Fear decay is affected by personality
            mult = mods.fear_decay_mult if delta < 0 else 1.0
        else:
            mult = 1.0

        return int(delta * mult)

    def _apply_familiarity_cap(
        self,
        familiarity: int,
        dimension: str,
        current_value: int,
        delta: int,
    ) -> int:
        """Cap relationship growth based on familiarity level.

        Strangers (familiarity < 30) can't reach high trust/liking quickly.
        """
        if delta <= 0:
            return delta  # Only cap positive changes

        # Familiarity thresholds
        if familiarity >= 50:
            max_value = 100  # Full relationship potential
        elif familiarity >= 30:
            max_value = 80  # Good acquaintance
        elif familiarity >= 15:
            max_value = 60  # Casual acquaintance
        else:
            max_value = 40  # Stranger

        # Cap the resulting value
        target_value = current_value + delta
        if target_value > max_value:
            # Only allow growth up to the cap
            return max(0, max_value - current_value)

        return delta

    def set_mood_modifier(
        self,
        from_id: int,
        to_id: int,
        modifier: int,
        reason: str,
        duration_turns: int = 10,
    ) -> Relationship:
        """Set a temporary mood modifier on a relationship.

        Args:
            from_id: Entity whose mood is affected
            to_id: Entity they're having mood about
            modifier: -20 to +20 modifier
            reason: Why this mood exists
            duration_turns: How many turns until it expires

        Returns:
            Updated Relationship
        """
        rel = self.get_or_create_relationship(from_id, to_id)

        rel.mood_modifier = max(-20, min(20, modifier))
        rel.mood_reason = reason
        rel.mood_expires_turn = self.current_turn + duration_turns

        self.db.flush()
        return rel

    def expire_mood_modifiers(self) -> int:
        """Expire all mood modifiers that have passed their turn limit.

        Returns:
            Number of modifiers expired
        """
        expired = (
            self.db.query(Relationship)
            .filter(
                Relationship.session_id == self.session_id,
                Relationship.mood_expires_turn <= self.current_turn,
                Relationship.mood_modifier != 0,
            )
            .all()
        )

        count = 0
        for rel in expired:
            rel.mood_modifier = 0
            rel.mood_reason = None
            rel.mood_expires_turn = None
            count += 1

        if count > 0:
            self.db.flush()

        return count

    def get_relationship_history(
        self,
        from_id: int,
        to_id: int,
        limit: int = 20,
    ) -> list[RelationshipChange]:
        """Get history of changes to a relationship.

        Returns most recent changes first.
        """
        rel = self.get_relationship(from_id, to_id)
        if rel is None:
            return []

        return (
            self.db.query(RelationshipChange)
            .filter(RelationshipChange.relationship_id == rel.id)
            .order_by(RelationshipChange.turn_number.desc())
            .limit(limit)
            .all()
        )

    def get_relationships_for_entity(
        self,
        entity_id: int,
        direction: Literal["from", "to", "both"] = "both",
    ) -> list[Relationship]:
        """Get all relationships involving an entity.

        Args:
            entity_id: Entity to get relationships for
            direction: "from" = entity's attitudes, "to" = others' attitudes toward entity

        Returns:
            List of relationships
        """
        query = self.db.query(Relationship).filter(
            Relationship.session_id == self.session_id
        )

        if direction == "from":
            query = query.filter(Relationship.from_entity_id == entity_id)
        elif direction == "to":
            query = query.filter(Relationship.to_entity_id == entity_id)
        else:
            query = query.filter(
                (Relationship.from_entity_id == entity_id)
                | (Relationship.to_entity_id == entity_id)
            )

        return query.all()

    def calculate_social_check_modifier(
        self,
        actor_id: int,
        target_id: int,
    ) -> int:
        """Calculate modifier for social checks based on relationship.

        Returns modifier from -5 to +5.
        """
        attitude = self.get_attitude(target_id, actor_id)

        # Use effective liking (includes mood)
        liking = attitude["effective_liking"]
        trust = attitude["trust"]
        respect = attitude["respect"]
        fear = attitude["fear"]

        # Calculate base modifier from attitudes
        modifier = 0

        # Liking affects willingness to help
        if liking >= 70:
            modifier += 2
        elif liking >= 55:
            modifier += 1
        elif liking < 30:
            modifier -= 2
        elif liking < 45:
            modifier -= 1

        # Trust affects believability
        if trust >= 70:
            modifier += 1
        elif trust < 30:
            modifier -= 1

        # Respect affects authority
        if respect >= 70:
            modifier += 1
        elif respect < 30:
            modifier -= 1

        # Fear affects compliance (but not persuasion)
        if fear >= 50:
            modifier += 1  # More likely to comply out of fear

        return max(-5, min(5, modifier))

    def get_attitude_description(
        self,
        from_id: int,
        to_id: int,
    ) -> str:
        """Get a human-readable description of attitude.

        For use in GM context.
        """
        attitude = self.get_attitude(from_id, to_id)

        if not attitude["knows"]:
            return "stranger"

        # Determine overall disposition
        liking = attitude["effective_liking"]
        trust = attitude["trust"]

        if liking >= 70 and trust >= 70:
            base = "friendly, trusting"
        elif liking >= 70:
            base = "friendly but cautious"
        elif liking >= 55:
            base = "warm"
        elif liking >= 45:
            base = "neutral"
        elif liking >= 30:
            base = "cool"
        else:
            base = "hostile"

        # Add modifiers
        extras = []
        if attitude["respect"] >= 70:
            extras.append("respectful")
        elif attitude["respect"] < 30:
            extras.append("dismissive")

        if attitude["fear"] >= 50:
            extras.append("fearful")

        if attitude["romantic_interest"] >= 50:
            extras.append("attracted")
        elif attitude["romantic_interest"] >= 30:
            extras.append("intrigued")

        if attitude["social_debt"] >= 30:
            extras.append("in their debt")
        elif attitude["social_debt"] <= -30:
            extras.append("owed favors")

        if extras:
            return f"{base} ({', '.join(extras)})"
        return base

    # ==================== Milestone Methods ====================

    def _check_milestones(
        self,
        rel: Relationship,
        dimension: str,
        old_value: int,
        new_value: int,
    ) -> None:
        """Check if any milestones were crossed and record them.

        Args:
            rel: The relationship being updated.
            dimension: Which dimension changed.
            old_value: Value before change.
            new_value: Value after change.
        """
        for dim, milestone_type, threshold, direction, msg_template in MILESTONE_THRESHOLDS:
            if dim != dimension:
                continue

            crossed = False
            if direction == "up":
                # Crossing threshold going up
                crossed = old_value < threshold <= new_value
            elif direction == "down":
                # Crossing threshold going down
                crossed = old_value >= threshold > new_value

            if not crossed:
                continue

            # Check if this exact milestone was already recorded (dedup)
            # For "up" milestones, only record if we don't already have one at this threshold
            # that hasn't been "reset" by going below threshold
            if direction == "up":
                # Check for existing milestone at this threshold that's still valid
                existing = self._get_active_milestone(rel.id, milestone_type, dimension)
                if existing:
                    continue  # Already have this milestone

            # Get entity names for the message
            from_entity = self.db.execute(
                select(Entity).where(Entity.id == rel.from_entity_id)
            ).scalar_one_or_none()
            to_entity = self.db.execute(
                select(Entity).where(Entity.id == rel.to_entity_id)
            ).scalar_one_or_none()

            from_name = from_entity.display_name if from_entity else "Unknown"
            to_name = to_entity.display_name if to_entity else "Unknown"

            message = msg_template.format(from_name=from_name, to_name=to_name)

            milestone = RelationshipMilestone(
                relationship_id=rel.id,
                milestone_type=milestone_type,
                dimension=dimension,
                threshold_value=threshold,
                direction=direction,
                message=message,
                notified=False,
                turn_number=self.current_turn,
            )
            self.db.add(milestone)

    def _get_active_milestone(
        self, relationship_id: int, milestone_type: str, dimension: str
    ) -> RelationshipMilestone | None:
        """Get an active (non-reset) milestone of the given type.

        An "up" milestone becomes inactive when the value drops back below threshold.
        This is detected by checking for a "down" milestone on the same dimension
        that occurred after the "up" milestone.
        """
        # Get the most recent milestone of this type
        milestone = self.db.execute(
            select(RelationshipMilestone)
            .where(
                RelationshipMilestone.relationship_id == relationship_id,
                RelationshipMilestone.milestone_type == milestone_type,
            )
            .order_by(RelationshipMilestone.turn_number.desc())
        ).scalar_one_or_none()

        if not milestone:
            return None

        # Check if there's a "down" milestone on the same dimension after this one
        # If so, the milestone was "reset" and can be earned again
        # We check both turn_number and id for proper ordering within the same turn
        from sqlalchemy import or_
        down_milestone = self.db.execute(
            select(RelationshipMilestone)
            .where(
                RelationshipMilestone.relationship_id == relationship_id,
                RelationshipMilestone.dimension == dimension,
                RelationshipMilestone.direction == "down",
                or_(
                    RelationshipMilestone.turn_number > milestone.turn_number,
                    # Same turn but later ID (operations within same turn)
                    (RelationshipMilestone.turn_number == milestone.turn_number)
                    & (RelationshipMilestone.id > milestone.id),
                ),
            )
        ).scalar_one_or_none()

        if down_milestone:
            # The milestone was reset by a "down" crossing
            return None

        return milestone

    def get_recent_milestones(
        self, from_id: int, to_id: int, limit: int = 20
    ) -> list[MilestoneInfo]:
        """Get recent milestones for a relationship.

        Args:
            from_id: Entity whose attitude changed.
            to_id: Entity they have attitude toward.
            limit: Maximum milestones to return.

        Returns:
            List of MilestoneInfo objects.
        """
        rel = self.get_relationship(from_id, to_id)
        if not rel:
            return []

        milestones = self.db.execute(
            select(RelationshipMilestone)
            .where(RelationshipMilestone.relationship_id == rel.id)
            .order_by(RelationshipMilestone.turn_number.desc())
            .limit(limit)
        ).scalars().all()

        # Get entity names
        from_entity = self.db.execute(
            select(Entity).where(Entity.id == from_id)
        ).scalar_one_or_none()
        to_entity = self.db.execute(
            select(Entity).where(Entity.id == to_id)
        ).scalar_one_or_none()

        from_name = from_entity.display_name if from_entity else None
        to_name = to_entity.display_name if to_entity else None

        return [
            MilestoneInfo(
                id=m.id,
                milestone_type=m.milestone_type,
                dimension=m.dimension,
                threshold_value=m.threshold_value,
                direction=m.direction,
                message=m.message,
                notified=m.notified,
                turn_number=m.turn_number,
                from_entity_id=from_id,
                to_entity_id=to_id,
                from_entity_name=from_name,
                to_entity_name=to_name,
            )
            for m in milestones
        ]

    def get_pending_milestone_notifications(
        self, target_entity_id: int
    ) -> list[MilestoneInfo]:
        """Get unnotified milestones where the entity is the target.

        This is useful for showing the player notifications about NPCs
        whose attitudes toward them have changed significantly.

        Args:
            target_entity_id: The entity that milestones are "about" (usually player).

        Returns:
            List of unnotified MilestoneInfo objects.
        """
        # Find relationships where this entity is the target
        relationships = self.db.execute(
            select(Relationship).where(
                Relationship.session_id == self.session_id,
                Relationship.to_entity_id == target_entity_id,
            )
        ).scalars().all()

        if not relationships:
            return []

        rel_ids = [r.id for r in relationships]

        milestones = self.db.execute(
            select(RelationshipMilestone)
            .where(
                RelationshipMilestone.relationship_id.in_(rel_ids),
                RelationshipMilestone.notified == False,  # noqa: E712
            )
            .order_by(RelationshipMilestone.turn_number.desc())
        ).scalars().all()

        result = []
        for m in milestones:
            # Get relationship and entity info
            rel = next(r for r in relationships if r.id == m.relationship_id)
            from_entity = self.db.execute(
                select(Entity).where(Entity.id == rel.from_entity_id)
            ).scalar_one_or_none()

            from_name = from_entity.display_name if from_entity else None
            to_entity = self.db.execute(
                select(Entity).where(Entity.id == target_entity_id)
            ).scalar_one_or_none()
            to_name = to_entity.display_name if to_entity else None

            result.append(
                MilestoneInfo(
                    id=m.id,
                    milestone_type=m.milestone_type,
                    dimension=m.dimension,
                    threshold_value=m.threshold_value,
                    direction=m.direction,
                    message=m.message,
                    notified=m.notified,
                    turn_number=m.turn_number,
                    from_entity_id=rel.from_entity_id,
                    to_entity_id=target_entity_id,
                    from_entity_name=from_name,
                    to_entity_name=to_name,
                )
            )

        return result

    def mark_milestone_notified(self, milestone_id: int) -> bool:
        """Mark a milestone as notified.

        Args:
            milestone_id: ID of the milestone to mark.

        Returns:
            True if found and marked, False otherwise.
        """
        milestone = self.db.execute(
            select(RelationshipMilestone)
            .where(RelationshipMilestone.id == milestone_id)
        ).scalar_one_or_none()

        if not milestone:
            return False

        milestone.notified = True
        self.db.flush()
        return True

    def get_milestone_context(self, entity_id: int) -> str:
        """Generate context string for pending milestones.

        Args:
            entity_id: Entity to get context for (usually player).

        Returns:
            Formatted context string, or empty string if no pending milestones.
        """
        pending = self.get_pending_milestone_notifications(entity_id)
        if not pending:
            return ""

        lines = ["## Relationship Updates"]
        for m in pending:
            lines.append(f"- {m.message}")

        return "\n".join(lines)
