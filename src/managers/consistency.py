"""World consistency validation (possession, spatial, temporal, behavioral)."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from sqlalchemy.orm import Session

from src.database.models.entities import Entity, NPCExtension
from src.database.models.enums import StorageLocationType
from src.database.models.items import Item, StorageLocation
from src.database.models.relationships import Relationship
from src.database.models.session import GameSession
from src.database.models.world import Fact, Location
from src.managers.base import BaseManager


@dataclass
class ConsistencyIssue:
    """A detected consistency problem."""

    category: Literal["possession", "spatial", "temporal", "behavioral", "item_persistence"]
    severity: Literal["warning", "error", "critical"]
    description: str
    entity_key: str | None = None
    location_key: str | None = None
    item_id: int | None = None
    suggested_fix: str | None = None


@dataclass
class TemporalEffects:
    """Effects that should occur due to time passage."""

    npc_movements: list[dict] = field(default_factory=list)
    lighting_change: str | None = None
    crowd_change: str | None = None
    items_spoiled: list[int] = field(default_factory=list)
    items_cleaned: list[int] = field(default_factory=list)
    bodies_removed: list[int] = field(default_factory=list)


# Role-appropriate possessions (what NPCs of this role should typically own)
ROLE_POSSESSIONS: dict[str, list[str]] = {
    "blacksmith": ["hammer", "anvil", "forge", "tongs", "apron"],
    "innkeeper": ["keys", "ledger", "cleaning supplies"],
    "guard": ["weapon", "armor", "badge", "handcuffs"],
    "merchant": ["scales", "ledger", "coin pouch"],
    "farmer": ["tools", "seeds", "cart"],
    "noble": ["fine clothes", "jewelry", "signet ring"],
    "scholar": ["books", "quill", "ink", "parchment"],
    "healer": ["herbs", "bandages", "medicine", "mortar"],
    "thief": ["lockpicks", "dark clothes", "rope"],
}

# Items inappropriate for certain categories
INAPPROPRIATE_ITEMS: dict[str, list[str]] = {
    "child": ["weapon", "alcohol", "gambling"],
    "peasant": ["expensive", "luxury", "noble"],
    "pacifist": ["weapon", "armor"],
}

# Wealth level expectations (rough item value limits)
WEALTH_LIMITS: dict[str, int] = {
    "destitute": 10,
    "poor": 50,
    "modest": 200,
    "comfortable": 1000,
    "wealthy": 10000,
    "rich": 100000,
}


class ConsistencyValidator(BaseManager):
    """Validates world consistency across multiple dimensions."""

    def validate_all(self, entity_id: int | None = None) -> list[ConsistencyIssue]:
        """Run all consistency checks.

        Args:
            entity_id: If provided, only check this entity. Otherwise check all.

        Returns:
            List of detected consistency issues
        """
        issues: list[ConsistencyIssue] = []

        if entity_id:
            issues.extend(self.validate_possession(entity_id))
            issues.extend(self.validate_behavioral(entity_id))
        else:
            # Check all entities
            entities = (
                self.db.query(Entity)
                .filter(Entity.session_id == self.session_id)
                .all()
            )
            for entity in entities:
                issues.extend(self.validate_possession(entity.id))
                issues.extend(self.validate_behavioral(entity.id))

        # Always check spatial and item persistence
        issues.extend(self.validate_spatial())
        issues.extend(self.validate_item_persistence())

        return issues

    def validate_possession(self, entity_id: int) -> list[ConsistencyIssue]:
        """Validate that entity possessions match their role and wealth.

        Checks:
        - Role-appropriate items (blacksmith should have tools)
        - Inappropriate items (child shouldn't have weapons)
        - Wealth-appropriate values

        Returns:
            List of possession-related issues
        """
        issues: list[ConsistencyIssue] = []

        entity = (
            self.db.query(Entity)
            .filter(Entity.id == entity_id)
            .first()
        )
        if not entity:
            return issues

        # Get NPC extension for job info
        npc_ext = (
            self.db.query(NPCExtension)
            .filter(NPCExtension.entity_id == entity_id)
            .first()
        )

        # Get entity's items
        items = (
            self.db.query(Item)
            .filter(
                Item.owner_id == entity_id,
                Item.session_id == self.session_id,
            )
            .all()
        )

        if not items:
            return issues

        # Check role-appropriate possessions
        if npc_ext and npc_ext.job:
            job_lower = npc_ext.job.lower()
            for role, expected_items in ROLE_POSSESSIONS.items():
                if role in job_lower:
                    # Check if they have role-appropriate items
                    item_names = [i.display_name.lower() for i in items]
                    has_role_item = any(
                        any(exp in name for exp in expected_items)
                        for name in item_names
                    )
                    if not has_role_item:
                        issues.append(
                            ConsistencyIssue(
                                category="possession",
                                severity="warning",
                                description=f"{entity.display_name} is a {npc_ext.job} but lacks typical tools of the trade",
                                entity_key=entity.entity_key,
                                suggested_fix=f"Consider adding items like: {', '.join(expected_items[:3])}",
                            )
                        )

        # Check for inappropriate items based on entity characteristics
        personality = entity.personality_notes or ""
        for category, forbidden in INAPPROPRIATE_ITEMS.items():
            is_category = category.lower() in personality.lower()

            # Special check for children based on age in facts
            if category == "child":
                age_fact = (
                    self.db.query(Fact)
                    .filter(
                        Fact.subject_key == entity.entity_key,
                        Fact.predicate == "age",
                        Fact.session_id == self.session_id,
                    )
                    .first()
                )
                if age_fact:
                    try:
                        age = int(age_fact.value)
                        is_category = age < 16
                    except ValueError:
                        pass

            if is_category:
                for item in items:
                    item_lower = item.display_name.lower()
                    if any(f in item_lower for f in forbidden):
                        issues.append(
                            ConsistencyIssue(
                                category="possession",
                                severity="warning",
                                description=f"{entity.display_name} ({category}) owns inappropriate item: {item.display_name}",
                                entity_key=entity.entity_key,
                                item_id=item.id,
                                suggested_fix="Remove item or explain how they obtained it",
                            )
                        )

        # Check wealth consistency
        wealth_fact = (
            self.db.query(Fact)
            .filter(
                Fact.subject_key == entity.entity_key,
                Fact.predicate.in_(["wealth", "wealth_level", "economic_status"]),
                Fact.session_id == self.session_id,
            )
            .first()
        )

        if wealth_fact:
            wealth_level = wealth_fact.value.lower()
            max_value = WEALTH_LIMITS.get(wealth_level, 1000)

            total_value = sum(getattr(i, "value", 0) or 0 for i in items)
            if total_value > max_value * 2:
                issues.append(
                    ConsistencyIssue(
                        category="possession",
                        severity="warning",
                        description=f"{entity.display_name} ({wealth_level}) owns items worth {total_value}, exceeding expected wealth",
                        entity_key=entity.entity_key,
                        suggested_fix="Reduce item values or explain wealth source",
                    )
                )

        return issues

    def validate_spatial(self) -> list[ConsistencyIssue]:
        """Validate spatial consistency of locations.

        Checks:
        - Locations have canonical descriptions set on first visit
        - Layout consistency (no sudden changes)
        - State history tracking

        Returns:
            List of spatial consistency issues
        """
        issues: list[ConsistencyIssue] = []

        locations = (
            self.db.query(Location)
            .filter(Location.session_id == self.session_id)
            .all()
        )

        for location in locations:
            is_visited = location.last_visited_turn is not None

            # Check if canonical description is set
            if is_visited and not location.canonical_description:
                issues.append(
                    ConsistencyIssue(
                        category="spatial",
                        severity="warning",
                        description=f"Location '{location.display_name}' was visited but has no canonical description",
                        location_key=location.location_key,
                        suggested_fix="Set canonical_description on first visit",
                    )
                )

            # Check state history is being tracked
            if is_visited and location.state_history is None:
                issues.append(
                    ConsistencyIssue(
                        category="spatial",
                        severity="warning",
                        description=f"Location '{location.display_name}' has no state history tracking",
                        location_key=location.location_key,
                        suggested_fix="Initialize state_history to track changes",
                    )
                )

        return issues

    def validate_item_persistence(self) -> list[ConsistencyIssue]:
        """Validate that dropped/placed items persist appropriately.

        Checks:
        - Items dropped recently should still be there
        - Items removed should have explanation

        Returns:
            List of item persistence issues
        """
        issues: list[ConsistencyIssue] = []

        # Find items that were dropped/placed but no longer have a holder
        # This is a simplified check - full implementation would track item movement history

        orphaned_items = (
            self.db.query(Item)
            .filter(
                Item.session_id == self.session_id,
                Item.holder_id.is_(None),
                Item.owner_id.isnot(None),
            )
            .all()
        )

        for item in orphaned_items:
            # Check if this was a recent drop (within last 10 turns)
            # Would need turn tracking on item - for now just flag
            if not item.storage_location_id:
                issues.append(
                    ConsistencyIssue(
                        category="item_persistence",
                        severity="warning",
                        description=f"Item '{item.display_name}' has no holder and no location - may be lost",
                        item_id=item.id,
                        suggested_fix="Set storage_location or explain item removal",
                    )
                )

        return issues

    def validate_behavioral(self, entity_id: int) -> list[ConsistencyIssue]:
        """Validate NPC behavioral consistency.

        Checks:
        - Trust-based behavior expectations
        - Relationship-appropriate reactions
        - Job-appropriate knowledge

        Returns:
            List of behavioral issues
        """
        issues: list[ConsistencyIssue] = []

        entity = (
            self.db.query(Entity)
            .filter(Entity.id == entity_id)
            .first()
        )
        if not entity:
            return issues

        # Get relationships where this entity is the source
        relationships = (
            self.db.query(Relationship)
            .filter(
                Relationship.from_entity_id == entity_id,
                Relationship.session_id == self.session_id,
            )
            .all()
        )

        for rel in relationships:
            # Check for inconsistent relationship values
            if rel.trust > 80 and rel.fear > 60:
                issues.append(
                    ConsistencyIssue(
                        category="behavioral",
                        severity="warning",
                        description=f"High trust ({rel.trust}) with high fear ({rel.fear}) is unusual",
                        entity_key=entity.entity_key,
                        suggested_fix="Consider if this is intentional (abusive relationship) or an error",
                    )
                )

            if rel.liking > 70 and rel.trust < 20:
                issues.append(
                    ConsistencyIssue(
                        category="behavioral",
                        severity="warning",
                        description=f"High liking ({rel.liking}) with very low trust ({rel.trust}) needs explanation",
                        entity_key=entity.entity_key,
                        suggested_fix="Add backstory explaining why they like but don't trust this person",
                    )
                )

        return issues

    def calculate_temporal_effects(
        self,
        hours_passed: float,
        current_location: str | None = None,
    ) -> TemporalEffects:
        """Calculate what effects should occur due to time passage.

        Args:
            hours_passed: In-game hours that passed
            current_location: Player's current location

        Returns:
            TemporalEffects describing what should change
        """
        effects = TemporalEffects()

        if hours_passed >= 0.5:  # 30 minutes
            # NPCs should move according to schedules
            effects.npc_movements = self._get_scheduled_movements(hours_passed)

        if hours_passed >= 2:
            # Lighting and crowds shift
            effects.lighting_change = self._calculate_lighting_change(hours_passed)
            effects.crowd_change = self._calculate_crowd_change(hours_passed)

        if hours_passed >= 12:
            # Major time passage effects
            effects.items_spoiled = self._get_spoiled_items(hours_passed)

        if hours_passed >= 48:  # 2+ days
            # Bodies removed, rooms cleaned
            effects.bodies_removed = self._get_removable_bodies()
            effects.items_cleaned = self._get_cleanable_items(current_location)

        return effects

    def _get_scheduled_movements(self, hours: float) -> list[dict]:
        """Get NPC movements based on schedules."""
        # This would query Schedule table and calculate movements
        # Simplified for now
        return []

    def _calculate_lighting_change(self, hours: float) -> str | None:
        """Calculate lighting change description."""
        # Would use TimeState to determine
        return None

    def _calculate_crowd_change(self, hours: float) -> str | None:
        """Calculate crowd level change."""
        # Would depend on time of day and location type
        return None

    def _get_spoiled_items(self, hours: float) -> list[int]:
        """Get IDs of items that should spoil."""
        days = hours / 24

        # Find perishable items
        perishables = (
            self.db.query(Item)
            .filter(
                Item.session_id == self.session_id,
            )
            .all()
        )

        spoiled = []
        for item in perishables:
            # Check if item type is perishable
            item_lower = item.display_name.lower()
            if any(food in item_lower for food in ["food", "meat", "fish", "bread", "fruit", "vegetable"]):
                # Items spoil after ~2 days without preservation
                if days >= 2:
                    spoiled.append(item.id)

        return spoiled

    def _get_removable_bodies(self) -> list[int]:
        """Get IDs of bodies that should be removed after 2+ days."""
        # Find dead entities that haven't been marked as removed
        dead_entities = (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.session_id,
                Entity.is_alive == False,
            )
            .all()
        )

        # Would check death timestamp vs current time
        return [e.id for e in dead_entities]

    def _get_cleanable_items(self, location: str | None) -> list[int]:
        """Get IDs of items that would be cleaned up in a location.

        Note: This requires integration with the StorageLocation system
        to properly track items at world locations.
        """
        if not location:
            return []

        # Find items dropped in this location via StorageLocation
        # StorageLocation of type PLACE links to world Location
        storage_locs = (
            self.db.query(StorageLocation)
            .filter(
                StorageLocation.session_id == self.session_id,
                StorageLocation.location_type == StorageLocationType.PLACE,
            )
            .all()
        )

        # Find storage locations that match this world location
        matching_storage_ids = []
        for storage in storage_locs:
            if storage.world_location and storage.world_location.location_key == location:
                matching_storage_ids.append(storage.id)

        if not matching_storage_ids:
            return []

        # Find items in these storage locations without a holder
        dropped = (
            self.db.query(Item)
            .filter(
                Item.session_id == self.session_id,
                Item.holder_id.is_(None),
                Item.storage_location_id.in_(matching_storage_ids),
            )
            .all()
        )

        # Low-value items get cleaned up (items without properties are low-value)
        return [i.id for i in dropped if not i.properties or i.properties.get("value", 0) < 10]

    def get_behavior_expectations(
        self,
        from_entity_id: int,
        to_entity_id: int,
    ) -> dict:
        """Get behavioral expectations based on relationship.

        Returns dict describing how from_entity should behave toward to_entity.
        """
        relationship = (
            self.db.query(Relationship)
            .filter(
                Relationship.from_entity_id == from_entity_id,
                Relationship.to_entity_id == to_entity_id,
                Relationship.session_id == self.session_id,
            )
            .first()
        )

        if not relationship:
            return {
                "disposition": "neutral",
                "trust_behavior": "cautious",
                "will_help": False,
                "will_share_secrets": False,
            }

        trust = relationship.trust
        liking = relationship.liking
        fear = relationship.fear

        # Trust-based behaviors
        if trust < 30:
            trust_behavior = "suspicious"
            will_share = False
        elif trust < 60:
            trust_behavior = "cautious"
            will_share = False
        else:
            trust_behavior = "open"
            will_share = True

        # Liking-based help
        will_help = liking > 40

        # Fear effects
        if fear > 60:
            disposition = "intimidated"
            will_help = True  # Compliance from fear
        elif liking > 60:
            disposition = "friendly"
        elif liking < 30:
            disposition = "unfriendly"
        else:
            disposition = "neutral"

        return {
            "disposition": disposition,
            "trust_behavior": trust_behavior,
            "will_help": will_help,
            "will_share_secrets": will_share,
            "is_intimidated": fear > 60,
            "gives_benefit_of_doubt": trust > 60,
        }

    def ensure_location_canonical(
        self,
        location_key: str,
        description: str,
    ) -> Location | None:
        """Ensure a location has a canonical description set.

        Only sets if not already set (first visit).

        Returns:
            The Location object, or None if not found
        """
        location = (
            self.db.query(Location)
            .filter(
                Location.location_key == location_key,
                Location.session_id == self.session_id,
            )
            .first()
        )

        if location and not location.canonical_description:
            location.canonical_description = description
            if location.first_visited_turn is None:
                location.first_visited_turn = self.current_turn
            if location.last_visited_turn is None:
                location.last_visited_turn = self.current_turn
            if location.state_history is None:
                location.state_history = []
            self.db.flush()

        return location

    def record_location_change(
        self,
        location_key: str,
        change_description: str,
        turn: int,
    ) -> None:
        """Record a change to a location's state.

        Args:
            location_key: Location that changed
            change_description: What changed
            turn: Turn when change occurred
        """
        location = (
            self.db.query(Location)
            .filter(
                Location.location_key == location_key,
                Location.session_id == self.session_id,
            )
            .first()
        )

        if location:
            if location.state_history is None:
                location.state_history = []

            location.state_history.append({
                "turn": turn,
                "change": change_description,
                "timestamp": datetime.utcnow().isoformat(),
            })
            self.db.flush()
