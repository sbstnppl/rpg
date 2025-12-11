"""Reputation manager for faction reputation tracking.

This manager handles faction creation, reputation tracking,
inter-faction relationships, and standing calculations.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import Entity, GameSession
from src.database.models.faction import (
    EntityReputation,
    Faction,
    FactionRelationship,
    ReputationChange as ReputationChangeModel,
    ReputationTier,
)
from src.managers.base import BaseManager


@dataclass
class ReputationChange:
    """Result of a reputation adjustment."""

    faction_key: str
    old_reputation: int
    new_reputation: int
    delta: int
    reason: str
    old_tier: ReputationTier
    new_tier: ReputationTier
    tier_changed: bool


@dataclass
class FactionStanding:
    """Standing with a faction."""

    faction_key: str
    faction_name: str
    reputation: int
    tier: ReputationTier
    is_ally: bool
    is_enemy: bool
    is_neutral: bool


# Tier thresholds
TIER_THRESHOLDS = [
    (-100, -75, ReputationTier.HATED),
    (-74, -50, ReputationTier.HOSTILE),
    (-49, -25, ReputationTier.UNFRIENDLY),
    (-24, 24, ReputationTier.NEUTRAL),
    (25, 49, ReputationTier.FRIENDLY),
    (50, 74, ReputationTier.HONORED),
    (75, 89, ReputationTier.REVERED),
    (90, 100, ReputationTier.EXALTED),
]

# Standing thresholds
ALLY_THRESHOLD = 50
ENEMY_THRESHOLD = -50


class ReputationManager(BaseManager):
    """Manages faction reputation for entities.

    Handles faction creation, reputation tracking, standing calculations,
    and inter-faction relationships.
    """

    def create_faction(
        self,
        faction_key: str,
        name: str,
        description: str | None = None,
        base_reputation: int = 0,
        is_hostile_by_default: bool = False,
    ) -> Faction:
        """Create a new faction.

        Args:
            faction_key: Unique key within session.
            name: Display name.
            description: Faction description.
            base_reputation: Starting reputation for new entities.
            is_hostile_by_default: Whether faction starts hostile.

        Returns:
            Created Faction.
        """
        faction = Faction(
            session_id=self.session_id,
            faction_key=faction_key,
            name=name,
            description=description,
            base_reputation=base_reputation,
            is_hostile_by_default=is_hostile_by_default,
        )
        self.db.add(faction)
        self.db.flush()
        return faction

    def get_faction(self, faction_key: str) -> Faction | None:
        """Get a faction by key.

        Args:
            faction_key: The faction key.

        Returns:
            Faction if found, None otherwise.
        """
        return self.db.execute(
            select(Faction).where(
                Faction.session_id == self.session_id,
                Faction.faction_key == faction_key,
            )
        ).scalar_one_or_none()

    def get_all_factions(self, include_inactive: bool = False) -> list[Faction]:
        """Get all factions for this session.

        Args:
            include_inactive: Whether to include inactive factions.

        Returns:
            List of factions.
        """
        query = select(Faction).where(Faction.session_id == self.session_id)
        if not include_inactive:
            query = query.where(Faction.is_active == True)  # noqa: E712
        return list(self.db.execute(query).scalars().all())

    def _get_entity(self, entity_key: str) -> Entity:
        """Get entity by key or raise error."""
        entity = self.db.execute(
            select(Entity).where(
                Entity.session_id == self.session_id,
                Entity.entity_key == entity_key,
            )
        ).scalar_one_or_none()

        if not entity:
            raise ValueError(f"Entity '{entity_key}' not found")
        return entity

    def _get_or_create_reputation(
        self, entity_id: int, faction: Faction
    ) -> EntityReputation:
        """Get or create reputation record for entity-faction pair."""
        reputation = self.db.execute(
            select(EntityReputation).where(
                EntityReputation.entity_id == entity_id,
                EntityReputation.faction_id == faction.id,
            )
        ).scalar_one_or_none()

        if not reputation:
            reputation = EntityReputation(
                entity_id=entity_id,
                faction_id=faction.id,
                reputation=faction.base_reputation,
            )
            self.db.add(reputation)
            self.db.flush()

        return reputation

    def get_reputation(self, entity_key: str, faction_key: str) -> int:
        """Get an entity's reputation with a faction.

        Args:
            entity_key: The entity.
            faction_key: The faction.

        Returns:
            Reputation value (-100 to 100).
        """
        faction = self.get_faction(faction_key)
        if not faction:
            return 0

        entity = self.db.execute(
            select(Entity).where(
                Entity.session_id == self.session_id,
                Entity.entity_key == entity_key,
            )
        ).scalar_one_or_none()

        if not entity:
            return faction.base_reputation

        reputation = self.db.execute(
            select(EntityReputation).where(
                EntityReputation.entity_id == entity.id,
                EntityReputation.faction_id == faction.id,
            )
        ).scalar_one_or_none()

        if reputation:
            return reputation.reputation
        return faction.base_reputation

    def adjust_reputation(
        self,
        entity_key: str,
        faction_key: str,
        delta: int,
        reason: str,
    ) -> ReputationChange:
        """Adjust an entity's reputation with a faction.

        Args:
            entity_key: The entity.
            faction_key: The faction.
            delta: Amount to adjust (-100 to 100).
            reason: Why this change is happening.

        Returns:
            ReputationChange result.

        Raises:
            ValueError: If entity or faction not found.
        """
        faction = self.get_faction(faction_key)
        if not faction:
            raise ValueError(f"Faction '{faction_key}' not found")

        entity = self._get_entity(entity_key)
        reputation = self._get_or_create_reputation(entity.id, faction)

        old_value = reputation.reputation
        old_tier = self._calculate_tier(old_value)

        # Apply change with clamping
        new_value = max(-100, min(100, old_value + delta))
        reputation.reputation = new_value

        new_tier = self._calculate_tier(new_value)

        # Record change in audit log
        change_record = ReputationChangeModel(
            entity_reputation_id=reputation.id,
            old_value=old_value,
            new_value=new_value,
            delta=new_value - old_value,
            reason=reason,
            turn_number=self.current_turn,
        )
        self.db.add(change_record)
        self.db.flush()

        return ReputationChange(
            faction_key=faction_key,
            old_reputation=old_value,
            new_reputation=new_value,
            delta=new_value - old_value,
            reason=reason,
            old_tier=old_tier,
            new_tier=new_tier,
            tier_changed=old_tier != new_tier,
        )

    def _calculate_tier(self, reputation: int) -> ReputationTier:
        """Calculate reputation tier from value."""
        for min_val, max_val, tier in TIER_THRESHOLDS:
            if min_val <= reputation <= max_val:
                return tier
        return ReputationTier.NEUTRAL

    def get_reputation_tier(
        self, entity_key: str, faction_key: str
    ) -> ReputationTier:
        """Get an entity's reputation tier with a faction.

        Args:
            entity_key: The entity.
            faction_key: The faction.

        Returns:
            Reputation tier.
        """
        reputation = self.get_reputation(entity_key, faction_key)
        return self._calculate_tier(reputation)

    def get_faction_standing(
        self, entity_key: str, faction_key: str
    ) -> FactionStanding:
        """Get an entity's standing with a faction.

        Args:
            entity_key: The entity.
            faction_key: The faction.

        Returns:
            FactionStanding with ally/enemy/neutral status.
        """
        faction = self.get_faction(faction_key)
        if not faction:
            raise ValueError(f"Faction '{faction_key}' not found")

        reputation = self.get_reputation(entity_key, faction_key)
        tier = self._calculate_tier(reputation)

        is_ally = reputation >= ALLY_THRESHOLD
        is_enemy = reputation <= ENEMY_THRESHOLD
        is_neutral = not is_ally and not is_enemy

        return FactionStanding(
            faction_key=faction_key,
            faction_name=faction.name,
            reputation=reputation,
            tier=tier,
            is_ally=is_ally,
            is_enemy=is_enemy,
            is_neutral=is_neutral,
        )

    def set_faction_relationship(
        self,
        faction1_key: str,
        faction2_key: str,
        relationship: str,
        mutual: bool = True,
    ) -> None:
        """Set the relationship between two factions.

        Args:
            faction1_key: First faction.
            faction2_key: Second faction.
            relationship: Type (ally, rival, vassal, enemy, etc.).
            mutual: If True, set both directions.
        """
        faction1 = self.get_faction(faction1_key)
        faction2 = self.get_faction(faction2_key)

        if not faction1 or not faction2:
            raise ValueError("One or both factions not found")

        # Set faction1 -> faction2
        self._set_faction_rel(faction1.id, faction2.id, relationship)

        if mutual:
            # Set faction2 -> faction1
            self._set_faction_rel(faction2.id, faction1.id, relationship)

        self.db.flush()

    def _set_faction_rel(
        self, from_id: int, to_id: int, relationship: str
    ) -> None:
        """Set or update a faction relationship."""
        existing = self.db.execute(
            select(FactionRelationship).where(
                FactionRelationship.from_faction_id == from_id,
                FactionRelationship.to_faction_id == to_id,
            )
        ).scalar_one_or_none()

        if existing:
            existing.relationship_type = relationship
        else:
            rel = FactionRelationship(
                from_faction_id=from_id,
                to_faction_id=to_id,
                relationship_type=relationship,
            )
            self.db.add(rel)

    def get_faction_relationship(
        self, faction1_key: str, faction2_key: str
    ) -> str | None:
        """Get the relationship from faction1 to faction2.

        Args:
            faction1_key: First faction.
            faction2_key: Second faction.

        Returns:
            Relationship type or None if not set.
        """
        faction1 = self.get_faction(faction1_key)
        faction2 = self.get_faction(faction2_key)

        if not faction1 or not faction2:
            return None

        rel = self.db.execute(
            select(FactionRelationship).where(
                FactionRelationship.from_faction_id == faction1.id,
                FactionRelationship.to_faction_id == faction2.id,
            )
        ).scalar_one_or_none()

        return rel.relationship_type if rel else None

    def get_allied_factions(self, faction_key: str) -> list[Faction]:
        """Get all factions allied with this one.

        Args:
            faction_key: The faction to check.

        Returns:
            List of allied factions.
        """
        return self._get_factions_by_relationship(faction_key, "ally")

    def get_rival_factions(self, faction_key: str) -> list[Faction]:
        """Get all factions that are rivals of this one.

        Args:
            faction_key: The faction to check.

        Returns:
            List of rival factions.
        """
        return self._get_factions_by_relationship(faction_key, "rival")

    def _get_factions_by_relationship(
        self, faction_key: str, relationship_type: str
    ) -> list[Faction]:
        """Get factions with a specific relationship to the given faction."""
        faction = self.get_faction(faction_key)
        if not faction:
            return []

        relationships = self.db.execute(
            select(FactionRelationship).where(
                FactionRelationship.from_faction_id == faction.id,
                FactionRelationship.relationship_type == relationship_type,
            )
        ).scalars().all()

        faction_ids = [r.to_faction_id for r in relationships]
        if not faction_ids:
            return []

        return list(
            self.db.execute(
                select(Faction).where(Faction.id.in_(faction_ids))
            ).scalars().all()
        )

    def get_reputation_context(self, entity_key: str) -> str:
        """Generate context string for entity's faction reputations.

        Args:
            entity_key: The entity to generate context for.

        Returns:
            Formatted context string, or empty string if no factions.
        """
        factions = self.get_all_factions()
        if not factions:
            return ""

        entity = self.db.execute(
            select(Entity).where(
                Entity.session_id == self.session_id,
                Entity.entity_key == entity_key,
            )
        ).scalar_one_or_none()

        if not entity:
            return ""

        lines = ["## Faction Reputation"]

        for faction in factions:
            reputation = self.get_reputation(entity_key, faction.faction_key)
            tier = self._calculate_tier(reputation)

            # Format tier name nicely
            tier_name = tier.value.replace("_", " ").title()
            lines.append(f"- **{faction.name}**: {tier_name} ({reputation:+d})")

        return "\n".join(lines)

    def get_reputation_history(
        self,
        entity_key: str,
        faction_key: str,
        limit: int = 20,
    ) -> list[ReputationChange]:
        """Get history of reputation changes.

        Args:
            entity_key: The entity.
            faction_key: The faction.
            limit: Maximum entries to return.

        Returns:
            List of ReputationChange objects (most recent first).
        """
        faction = self.get_faction(faction_key)
        if not faction:
            return []

        entity = self.db.execute(
            select(Entity).where(
                Entity.session_id == self.session_id,
                Entity.entity_key == entity_key,
            )
        ).scalar_one_or_none()

        if not entity:
            return []

        reputation = self.db.execute(
            select(EntityReputation).where(
                EntityReputation.entity_id == entity.id,
                EntityReputation.faction_id == faction.id,
            )
        ).scalar_one_or_none()

        if not reputation:
            return []

        changes = self.db.execute(
            select(ReputationChangeModel)
            .where(ReputationChangeModel.entity_reputation_id == reputation.id)
            .order_by(ReputationChangeModel.created_at.desc())
            .limit(limit)
        ).scalars().all()

        return [
            ReputationChange(
                faction_key=faction_key,
                old_reputation=c.old_value,
                new_reputation=c.new_value,
                delta=c.delta,
                reason=c.reason,
                old_tier=self._calculate_tier(c.old_value),
                new_tier=self._calculate_tier(c.new_value),
                tier_changed=self._calculate_tier(c.old_value)
                != self._calculate_tier(c.new_value),
            )
            for c in changes
        ]
