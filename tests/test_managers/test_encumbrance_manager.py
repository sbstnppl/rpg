"""Tests for EncumbranceManager."""

import pytest

from src.database.models.entities import Entity, EntityAttribute
from src.database.models.enums import EntityType
from src.database.models.items import Item, StorageLocation
from src.database.models.enums import StorageLocationType, ItemType
from src.managers.encumbrance_manager import (
    EncumbranceManager,
    EncumbranceStatus,
    EncumbranceLevel,
)


# Helper to create entity with strength
def create_entity_with_strength(
    db_session, game_session, entity_key: str, strength: int
) -> Entity:
    """Create an entity with a strength attribute."""
    entity = Entity(
        session_id=game_session.id,
        entity_key=entity_key,
        display_name=entity_key.replace("_", " ").title(),
        entity_type=EntityType.NPC,
    )
    db_session.add(entity)
    db_session.flush()

    # Add strength attribute (EntityAttribute doesn't have session_id - scoped via entity)
    strength_attr = EntityAttribute(
        entity_id=entity.id,
        attribute_key="strength",
        value=strength,
    )
    db_session.add(strength_attr)
    db_session.flush()

    return entity


def create_item_with_weight(
    db_session, game_session, item_key: str, weight: float, holder_id: int | None = None
) -> Item:
    """Create an item with a specific weight."""
    item = Item(
        session_id=game_session.id,
        item_key=item_key,
        display_name=item_key.replace("_", " ").title(),
        item_type=ItemType.MISC,
        weight=weight,
        holder_id=holder_id,
    )
    db_session.add(item)
    db_session.flush()
    return item


class TestCapacityCalculation:
    """Tests for carrying capacity calculation."""

    def test_capacity_from_strength_10(self, db_session, game_session):
        """Test capacity calculation for strength 10."""
        manager = EncumbranceManager(db_session, game_session)

        # Capacity = strength * 15
        capacity = manager.get_carry_capacity(10)
        assert capacity == 150.0

    def test_capacity_from_strength_18(self, db_session, game_session):
        """Test capacity calculation for high strength."""
        manager = EncumbranceManager(db_session, game_session)

        capacity = manager.get_carry_capacity(18)
        assert capacity == 270.0

    def test_capacity_from_strength_8(self, db_session, game_session):
        """Test capacity calculation for low strength."""
        manager = EncumbranceManager(db_session, game_session)

        capacity = manager.get_carry_capacity(8)
        assert capacity == 120.0

    def test_get_entity_capacity(self, db_session, game_session):
        """Test getting capacity for an entity by key."""
        entity = create_entity_with_strength(db_session, game_session, "strong_warrior", 16)
        manager = EncumbranceManager(db_session, game_session)

        capacity = manager.get_entity_capacity(entity.entity_key)
        assert capacity == 240.0  # 16 * 15

    def test_get_entity_capacity_no_strength(self, db_session, game_session):
        """Test capacity defaults to 10 strength if no attribute."""
        entity = Entity(
            session_id=game_session.id,
            entity_key="no_str_entity",
            display_name="No Strength Entity",
            entity_type=EntityType.NPC,
        )
        db_session.add(entity)
        db_session.flush()

        manager = EncumbranceManager(db_session, game_session)
        capacity = manager.get_entity_capacity("no_str_entity")
        assert capacity == 150.0  # Default 10 * 15


class TestCarriedWeight:
    """Tests for calculating carried weight."""

    def test_carried_weight_no_items(self, db_session, game_session):
        """Test carried weight when entity has no items."""
        entity = create_entity_with_strength(db_session, game_session, "empty_hands", 10)
        manager = EncumbranceManager(db_session, game_session)

        weight = manager.get_carried_weight(entity.entity_key)
        assert weight == 0.0

    def test_carried_weight_single_item(self, db_session, game_session):
        """Test carried weight with a single item."""
        entity = create_entity_with_strength(db_session, game_session, "carrier", 10)
        create_item_with_weight(db_session, game_session, "sword", 5.0, entity.id)

        manager = EncumbranceManager(db_session, game_session)
        weight = manager.get_carried_weight(entity.entity_key)
        assert weight == 5.0

    def test_carried_weight_multiple_items(self, db_session, game_session):
        """Test carried weight with multiple items."""
        entity = create_entity_with_strength(db_session, game_session, "pack_mule", 10)
        create_item_with_weight(db_session, game_session, "sword", 5.0, entity.id)
        create_item_with_weight(db_session, game_session, "shield", 8.0, entity.id)
        create_item_with_weight(db_session, game_session, "armor", 40.0, entity.id)

        manager = EncumbranceManager(db_session, game_session)
        weight = manager.get_carried_weight(entity.entity_key)
        assert weight == 53.0

    def test_carried_weight_ignores_null_weight(self, db_session, game_session):
        """Test that items with no weight (None) are ignored."""
        entity = create_entity_with_strength(db_session, game_session, "mixed_carrier", 10)
        create_item_with_weight(db_session, game_session, "sword", 5.0, entity.id)

        # Item with no weight
        weightless_item = Item(
            session_id=game_session.id,
            item_key="magic_feather",
            display_name="Magic Feather",
            item_type=ItemType.MISC,
            weight=None,
            holder_id=entity.id,
        )
        db_session.add(weightless_item)
        db_session.flush()

        manager = EncumbranceManager(db_session, game_session)
        weight = manager.get_carried_weight(entity.entity_key)
        assert weight == 5.0

    def test_carried_weight_stacked_items(self, db_session, game_session):
        """Test carried weight accounts for item quantity."""
        entity = create_entity_with_strength(db_session, game_session, "potion_hoarder", 10)

        # Stack of 5 potions, each weighing 0.5 lbs
        potions = Item(
            session_id=game_session.id,
            item_key="healing_potions",
            display_name="Healing Potions",
            item_type=ItemType.CONSUMABLE,
            weight=0.5,
            quantity=5,
            is_stackable=True,
            holder_id=entity.id,
        )
        db_session.add(potions)
        db_session.flush()

        manager = EncumbranceManager(db_session, game_session)
        weight = manager.get_carried_weight(entity.entity_key)
        assert weight == 2.5  # 0.5 * 5

    def test_carried_weight_session_isolation(self, db_session, game_session, game_session_2):
        """Test that items from different sessions are not counted."""
        entity = create_entity_with_strength(db_session, game_session, "isolated", 10)
        create_item_with_weight(db_session, game_session, "my_sword", 5.0, entity.id)

        # Item in different session (shouldn't count)
        other_item = Item(
            session_id=game_session_2.id,
            item_key="other_sword",
            display_name="Other Sword",
            item_type=ItemType.MISC,
            weight=10.0,
            holder_id=entity.id,  # Same holder_id but different session
        )
        db_session.add(other_item)
        db_session.flush()

        manager = EncumbranceManager(db_session, game_session)
        weight = manager.get_carried_weight("isolated")
        assert weight == 5.0  # Only counts items from same session


class TestEncumbranceLevels:
    """Tests for encumbrance level calculation."""

    def test_light_encumbrance(self, db_session, game_session):
        """Test light encumbrance (0-33% capacity)."""
        entity = create_entity_with_strength(db_session, game_session, "light_load", 10)
        # Capacity = 150, light threshold = 50 (33%)
        create_item_with_weight(db_session, game_session, "dagger", 30.0, entity.id)

        manager = EncumbranceManager(db_session, game_session)
        status = manager.get_encumbrance_status(entity.entity_key)

        assert status.level == EncumbranceLevel.LIGHT
        assert status.speed_penalty == 0
        assert status.combat_penalty is None

    def test_medium_encumbrance(self, db_session, game_session):
        """Test medium encumbrance (34-66% capacity)."""
        entity = create_entity_with_strength(db_session, game_session, "medium_load", 10)
        # Capacity = 150, medium is 50-100 lbs
        create_item_with_weight(db_session, game_session, "gear", 75.0, entity.id)

        manager = EncumbranceManager(db_session, game_session)
        status = manager.get_encumbrance_status(entity.entity_key)

        assert status.level == EncumbranceLevel.MEDIUM
        assert status.speed_penalty == 10
        assert status.combat_penalty is None

    def test_heavy_encumbrance(self, db_session, game_session):
        """Test heavy encumbrance (67-100% capacity)."""
        entity = create_entity_with_strength(db_session, game_session, "heavy_load", 10)
        # Capacity = 150, heavy is 100-150 lbs
        create_item_with_weight(db_session, game_session, "full_gear", 120.0, entity.id)

        manager = EncumbranceManager(db_session, game_session)
        status = manager.get_encumbrance_status(entity.entity_key)

        assert status.level == EncumbranceLevel.HEAVY
        assert status.speed_penalty == 20
        assert status.combat_penalty == "disadvantage_physical"

    def test_over_encumbered(self, db_session, game_session):
        """Test over-encumbered (>100% capacity)."""
        entity = create_entity_with_strength(db_session, game_session, "overloaded", 10)
        # Capacity = 150, over = 151+
        create_item_with_weight(db_session, game_session, "way_too_much", 200.0, entity.id)

        manager = EncumbranceManager(db_session, game_session)
        status = manager.get_encumbrance_status(entity.entity_key)

        assert status.level == EncumbranceLevel.OVER
        assert status.speed_penalty == -1  # -1 indicates immobile
        assert status.combat_penalty == "disadvantage_all"

    def test_encumbrance_at_exact_thresholds(self, db_session, game_session):
        """Test encumbrance at exact threshold boundaries."""
        manager = EncumbranceManager(db_session, game_session)

        # At exactly 33% - should still be light
        entity1 = create_entity_with_strength(db_session, game_session, "at_light", 10)
        create_item_with_weight(db_session, game_session, "item1", 49.5, entity1.id)
        status1 = manager.get_encumbrance_status("at_light")
        assert status1.level == EncumbranceLevel.LIGHT

        # At exactly 66% - should still be medium
        entity2 = create_entity_with_strength(db_session, game_session, "at_medium", 10)
        create_item_with_weight(db_session, game_session, "item2", 99.0, entity2.id)
        status2 = manager.get_encumbrance_status("at_medium")
        assert status2.level == EncumbranceLevel.MEDIUM

        # At exactly 100% - should still be heavy
        entity3 = create_entity_with_strength(db_session, game_session, "at_heavy", 10)
        create_item_with_weight(db_session, game_session, "item3", 150.0, entity3.id)
        status3 = manager.get_encumbrance_status("at_heavy")
        assert status3.level == EncumbranceLevel.HEAVY


class TestCanPickUp:
    """Tests for checking if entity can pick up an item."""

    def test_can_pick_up_under_capacity(self, db_session, game_session):
        """Test can pick up when under capacity."""
        entity = create_entity_with_strength(db_session, game_session, "picker", 10)
        create_item_with_weight(db_session, game_session, "existing", 50.0, entity.id)
        new_item = create_item_with_weight(db_session, game_session, "new_item", 20.0)

        manager = EncumbranceManager(db_session, game_session)
        can_pick, reason = manager.can_pick_up(entity.entity_key, new_item.item_key)

        assert can_pick is True
        assert reason is None

    def test_cannot_pick_up_over_capacity(self, db_session, game_session):
        """Test cannot pick up when would exceed capacity."""
        entity = create_entity_with_strength(db_session, game_session, "full_hands", 10)
        create_item_with_weight(db_session, game_session, "existing", 140.0, entity.id)
        new_item = create_item_with_weight(db_session, game_session, "heavy_item", 20.0)

        manager = EncumbranceManager(db_session, game_session)
        can_pick, reason = manager.can_pick_up(entity.entity_key, new_item.item_key)

        assert can_pick is False
        assert "exceed" in reason.lower() or "capacity" in reason.lower()

    def test_can_pick_up_weightless_item(self, db_session, game_session):
        """Test can always pick up items with no weight."""
        entity = create_entity_with_strength(db_session, game_session, "collector", 10)
        create_item_with_weight(db_session, game_session, "heavy_stuff", 150.0, entity.id)

        # Weightless item
        weightless = Item(
            session_id=game_session.id,
            item_key="feather",
            display_name="Feather",
            item_type=ItemType.MISC,
            weight=None,
        )
        db_session.add(weightless)
        db_session.flush()

        manager = EncumbranceManager(db_session, game_session)
        can_pick, reason = manager.can_pick_up(entity.entity_key, "feather")

        assert can_pick is True

    def test_can_pick_up_at_exact_limit(self, db_session, game_session):
        """Test can pick up item that brings to exactly capacity."""
        entity = create_entity_with_strength(db_session, game_session, "precise", 10)
        create_item_with_weight(db_session, game_session, "existing", 140.0, entity.id)
        new_item = create_item_with_weight(db_session, game_session, "last_item", 10.0)

        manager = EncumbranceManager(db_session, game_session)
        can_pick, reason = manager.can_pick_up(entity.entity_key, new_item.item_key)

        # At exactly capacity (150) should still be allowed
        assert can_pick is True


class TestEncumbranceContext:
    """Tests for context generation."""

    def test_context_light_load(self, db_session, game_session):
        """Test context for light encumbrance."""
        entity = create_entity_with_strength(db_session, game_session, "light_traveler", 10)
        create_item_with_weight(db_session, game_session, "pack", 30.0, entity.id)

        manager = EncumbranceManager(db_session, game_session)
        context = manager.get_encumbrance_context(entity.entity_key)

        assert "30" in context  # Current weight
        assert "150" in context  # Capacity
        assert "light" in context.lower()

    def test_context_heavy_load(self, db_session, game_session):
        """Test context for heavy encumbrance includes penalties."""
        entity = create_entity_with_strength(db_session, game_session, "heavy_traveler", 10)
        create_item_with_weight(db_session, game_session, "armor", 120.0, entity.id)

        manager = EncumbranceManager(db_session, game_session)
        context = manager.get_encumbrance_context(entity.entity_key)

        assert "heavy" in context.lower()
        assert "speed" in context.lower() or "penalty" in context.lower()

    def test_context_over_encumbered(self, db_session, game_session):
        """Test context for over-encumbered shows immobile."""
        entity = create_entity_with_strength(db_session, game_session, "stuck", 10)
        create_item_with_weight(db_session, game_session, "too_much", 200.0, entity.id)

        manager = EncumbranceManager(db_session, game_session)
        context = manager.get_encumbrance_context(entity.entity_key)

        assert "over" in context.lower() or "immobile" in context.lower()


class TestEncumbranceStatus:
    """Tests for EncumbranceStatus dataclass."""

    def test_status_fields(self, db_session, game_session):
        """Test all fields in EncumbranceStatus."""
        entity = create_entity_with_strength(db_session, game_session, "status_test", 10)
        create_item_with_weight(db_session, game_session, "stuff", 75.0, entity.id)

        manager = EncumbranceManager(db_session, game_session)
        status = manager.get_encumbrance_status(entity.entity_key)

        assert isinstance(status, EncumbranceStatus)
        assert status.carried_weight == 75.0
        assert status.capacity == 150.0
        assert status.level == EncumbranceLevel.MEDIUM
        assert isinstance(status.speed_penalty, int)
        assert status.percentage == 50.0  # 75/150 * 100

    def test_status_entity_not_found(self, db_session, game_session):
        """Test status for non-existent entity returns None."""
        manager = EncumbranceManager(db_session, game_session)
        status = manager.get_encumbrance_status("nonexistent_entity")
        assert status is None
