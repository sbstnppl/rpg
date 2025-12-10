"""Tests for the EmergentItemGenerator service."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.entities import Entity
from src.database.models.enums import EntityType, ItemCondition, ItemType
from src.database.models.items import Item
from src.database.models.session import GameSession
from src.services.emergent_item_generator import (
    EmergentItemGenerator,
    ItemConstraints,
    ItemFullState,
    ITEM_TEMPLATES,
    QUALITY_MULTIPLIERS,
    CONDITION_MULTIPLIERS,
    value_to_description,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def generator(db_session: Session, game_session: GameSession) -> EmergentItemGenerator:
    """Create EmergentItemGenerator instance."""
    return EmergentItemGenerator(db_session, game_session)


@pytest.fixture
def owner_entity(db_session: Session, game_session: GameSession) -> Entity:
    """Create an owner entity for items."""
    entity = Entity(
        session_id=game_session.id,
        entity_key="shopkeeper_test",
        display_name="Test Shopkeeper",
        entity_type=EntityType.NPC,
    )
    db_session.add(entity)
    db_session.flush()
    return entity


# =============================================================================
# Basic Item Creation Tests
# =============================================================================


class TestItemCreation:
    """Tests for basic item creation."""

    def test_create_item_returns_full_state(
        self,
        generator: EmergentItemGenerator,
    ):
        """Test that create_item returns a complete ItemFullState."""
        item_state = generator.create_item(
            item_type="weapon",
            context="a sword on display",
            location_key="blacksmith_shop",
        )

        assert isinstance(item_state, ItemFullState)
        assert item_state.item_key is not None
        assert item_state.display_name is not None
        assert item_state.item_type == "weapon"
        assert item_state.description is not None
        assert item_state.quality in ["poor", "common", "good", "fine", "exceptional"]
        assert item_state.condition in ["pristine", "good", "worn", "damaged", "broken"]
        assert item_state.estimated_value >= 0
        assert item_state.value_description is not None

    def test_create_item_persists_to_database(
        self,
        generator: EmergentItemGenerator,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test that created items are persisted to the database."""
        item_state = generator.create_item(
            item_type="food",
            context="fresh bread",
            location_key="bakery",
        )

        # Query the database for the item
        db_item = (
            db_session.query(Item)
            .filter(
                Item.session_id == game_session.id,
                Item.item_key == item_state.item_key,
            )
            .first()
        )

        assert db_item is not None
        assert db_item.display_name == item_state.display_name
        assert db_item.item_type == ItemType.CONSUMABLE  # food maps to consumable

    def test_create_item_with_owner(
        self,
        generator: EmergentItemGenerator,
        db_session: Session,
        game_session: GameSession,
        owner_entity: Entity,
    ):
        """Test that items can be created with an owner."""
        item_state = generator.create_item(
            item_type="weapon",
            context="dagger in a sheath",
            location_key="blacksmith_shop",
            owner_entity_id=owner_entity.id,
        )

        db_item = (
            db_session.query(Item)
            .filter(
                Item.session_id == game_session.id,
                Item.item_key == item_state.item_key,
            )
            .first()
        )

        assert db_item is not None
        assert db_item.owner_id == owner_entity.id
        assert db_item.holder_id == owner_entity.id

    def test_create_item_generates_unique_key(
        self,
        generator: EmergentItemGenerator,
    ):
        """Test that each item gets a unique key."""
        item1 = generator.create_item(
            item_type="weapon",
            context="sword",
            location_key="shop",
        )
        item2 = generator.create_item(
            item_type="weapon",
            context="sword",
            location_key="shop",
        )

        assert item1.item_key != item2.item_key


# =============================================================================
# Item Type Tests
# =============================================================================


class TestItemTypes:
    """Tests for different item types."""

    @pytest.mark.parametrize("item_type,expected_db_type", [
        ("weapon", ItemType.WEAPON),
        ("armor", ItemType.ARMOR),
        ("clothing", ItemType.CLOTHING),
        ("food", ItemType.CONSUMABLE),
        ("drink", ItemType.CONSUMABLE),
        ("tool", ItemType.MISC),
        ("container", ItemType.CONTAINER),
        ("misc", ItemType.MISC),
    ])
    def test_item_type_mapping(
        self,
        generator: EmergentItemGenerator,
        db_session: Session,
        game_session: GameSession,
        item_type: str,
        expected_db_type: ItemType,
    ):
        """Test that item types map correctly to database enums."""
        item_state = generator.create_item(
            item_type=item_type,
            context=f"a {item_type} item",
            location_key="shop",
        )

        db_item = (
            db_session.query(Item)
            .filter(Item.item_key == item_state.item_key)
            .first()
        )

        assert db_item.item_type == expected_db_type

    def test_weapon_has_damage_property(
        self,
        generator: EmergentItemGenerator,
    ):
        """Test that weapons have damage properties."""
        item_state = generator.create_item(
            item_type="weapon",
            context="a sharp dagger",
            location_key="shop",
        )

        assert "damage" in item_state.properties

    def test_food_triggers_hunger(
        self,
        generator: EmergentItemGenerator,
    ):
        """Test that food items trigger hunger need."""
        item_state = generator.create_item(
            item_type="food",
            context="fresh bread",
            location_key="bakery",
        )

        assert "hunger" in item_state.need_triggers

    def test_drink_triggers_thirst(
        self,
        generator: EmergentItemGenerator,
    ):
        """Test that drink items trigger thirst need."""
        item_state = generator.create_item(
            item_type="drink",
            context="cold water",
            location_key="tavern",
        )

        assert "thirst" in item_state.need_triggers


# =============================================================================
# Constraint Tests
# =============================================================================


class TestItemConstraints:
    """Tests for item constraints."""

    def test_constraint_name(
        self,
        generator: EmergentItemGenerator,
    ):
        """Test that name constraint is respected."""
        constraints = ItemConstraints(name="Excalibur")

        item_state = generator.create_item(
            item_type="weapon",
            context="legendary sword",
            location_key="castle",
            constraints=constraints,
        )

        assert item_state.display_name == "Excalibur"

    def test_constraint_quality(
        self,
        generator: EmergentItemGenerator,
    ):
        """Test that quality constraint is respected."""
        constraints = ItemConstraints(quality="exceptional")

        item_state = generator.create_item(
            item_type="weapon",
            context="ordinary sword",
            location_key="shop",
            constraints=constraints,
        )

        assert item_state.quality == "exceptional"

    def test_constraint_condition(
        self,
        generator: EmergentItemGenerator,
    ):
        """Test that condition constraint is respected."""
        constraints = ItemConstraints(condition="broken")

        item_state = generator.create_item(
            item_type="weapon",
            context="new sword",
            location_key="shop",
            constraints=constraints,
        )

        assert item_state.condition == "broken"

    def test_constraint_has_history(
        self,
        generator: EmergentItemGenerator,
    ):
        """Test that has_history constraint is respected."""
        constraints = ItemConstraints(has_history=True)

        item_state = generator.create_item(
            item_type="misc",
            context="old book",
            location_key="library",
            constraints=constraints,
        )

        # Should have provenance when history is forced
        assert item_state.provenance is not None

    def test_constraint_no_history(
        self,
        generator: EmergentItemGenerator,
    ):
        """Test that has_history=False suppresses provenance."""
        constraints = ItemConstraints(has_history=False)

        # Create multiple items to ensure none have history
        for _ in range(5):
            item_state = generator.create_item(
                item_type="misc",
                context="book",
                location_key="library",
                constraints=constraints,
            )
            assert item_state.provenance is None


# =============================================================================
# Context Inference Tests
# =============================================================================


class TestContextInference:
    """Tests for context-based property inference."""

    def test_context_infers_subtype_sword(
        self,
        generator: EmergentItemGenerator,
    ):
        """Test that context mentioning 'sword' infers sword subtype."""
        item_state = generator.create_item(
            item_type="weapon",
            context="a fine steel sword",
            location_key="blacksmith",
        )

        # Should use sword properties (1d8 damage)
        assert item_state.properties.get("damage") == "1d8"

    def test_context_infers_subtype_dagger(
        self,
        generator: EmergentItemGenerator,
    ):
        """Test that context mentioning 'dagger' infers dagger subtype."""
        item_state = generator.create_item(
            item_type="weapon",
            context="a small dagger",
            location_key="shop",
        )

        # Should use dagger properties (1d4 damage)
        assert item_state.properties.get("damage") == "1d4"

    def test_context_infers_pristine_condition(
        self,
        generator: EmergentItemGenerator,
    ):
        """Test that 'new' context suggests pristine condition."""
        # Run multiple times to increase confidence
        pristine_count = 0
        for _ in range(10):
            item_state = generator.create_item(
                item_type="weapon",
                context="brand new pristine sword",
                location_key="shop",
            )
            if item_state.condition == "pristine":
                pristine_count += 1

        # Should usually be pristine
        assert pristine_count >= 7

    def test_context_infers_worn_condition(
        self,
        generator: EmergentItemGenerator,
    ):
        """Test that 'worn' context suggests worn condition."""
        worn_count = 0
        for _ in range(10):
            item_state = generator.create_item(
                item_type="weapon",
                context="old worn sword",
                location_key="shop",
            )
            if item_state.condition == "worn":
                worn_count += 1

        # Should usually be worn
        assert worn_count >= 7

    def test_context_infers_fine_quality(
        self,
        generator: EmergentItemGenerator,
    ):
        """Test that 'fine' context suggests higher quality."""
        fine_count = 0
        for _ in range(10):
            item_state = generator.create_item(
                item_type="weapon",
                context="exquisite masterwork blade",
                location_key="shop",
            )
            if item_state.quality in ["fine", "exceptional"]:
                fine_count += 1

        # Should usually be fine or exceptional
        assert fine_count >= 7


# =============================================================================
# Value Calculation Tests
# =============================================================================


class TestValueCalculation:
    """Tests for item value calculation."""

    def test_quality_affects_value(
        self,
        generator: EmergentItemGenerator,
    ):
        """Test that higher quality increases value."""
        poor_item = generator.create_item(
            item_type="weapon",
            context="sword",
            location_key="shop",
            constraints=ItemConstraints(quality="poor", condition="good"),
        )
        exceptional_item = generator.create_item(
            item_type="weapon",
            context="sword",
            location_key="shop",
            constraints=ItemConstraints(quality="exceptional", condition="good"),
        )

        assert exceptional_item.estimated_value > poor_item.estimated_value

    def test_condition_affects_value(
        self,
        generator: EmergentItemGenerator,
    ):
        """Test that better condition increases value."""
        broken_item = generator.create_item(
            item_type="weapon",
            context="sword",
            location_key="shop",
            constraints=ItemConstraints(quality="common", condition="broken"),
        )
        pristine_item = generator.create_item(
            item_type="weapon",
            context="sword",
            location_key="shop",
            constraints=ItemConstraints(quality="common", condition="pristine"),
        )

        assert pristine_item.estimated_value > broken_item.estimated_value


class TestValueDescriptions:
    """Tests for value_to_description function."""

    def test_worthless_value(self):
        """Test description for nearly worthless items."""
        assert value_to_description(5) == "nearly worthless"

    def test_copper_value(self):
        """Test description for copper-range items."""
        assert "copper" in value_to_description(30)
        assert "copper" in value_to_description(75)

    def test_silver_value(self):
        """Test description for silver-range items."""
        assert "silver" in value_to_description(300)
        assert "silver" in value_to_description(800)

    def test_gold_value(self):
        """Test description for gold-range items."""
        assert "gold" in value_to_description(2000)
        assert "gold" in value_to_description(8000)

    def test_valuable_items(self):
        """Test description for very valuable items."""
        assert "valuable" in value_to_description(30000)
        assert "valuable" in value_to_description(100000)


# =============================================================================
# Get Item State Tests
# =============================================================================


class TestGetItemState:
    """Tests for get_item_state method."""

    def test_get_item_state_returns_existing_item(
        self,
        generator: EmergentItemGenerator,
    ):
        """Test that get_item_state returns correct data for existing item."""
        created_item = generator.create_item(
            item_type="weapon",
            context="sword",
            location_key="shop",
        )

        retrieved_item = generator.get_item_state(created_item.item_key)

        assert retrieved_item is not None
        assert retrieved_item.item_key == created_item.item_key
        assert retrieved_item.display_name == created_item.display_name

    def test_get_item_state_returns_none_for_missing_item(
        self,
        generator: EmergentItemGenerator,
    ):
        """Test that get_item_state returns None for non-existent item."""
        result = generator.get_item_state("nonexistent_item")
        assert result is None


# =============================================================================
# Item Properties Tests
# =============================================================================


class TestItemProperties:
    """Tests for special item properties."""

    def test_food_has_nutrition(
        self,
        generator: EmergentItemGenerator,
    ):
        """Test that food items have nutrition property."""
        item_state = generator.create_item(
            item_type="food",
            context="bread",
            location_key="bakery",
        )

        assert "nutrition" in item_state.properties

    def test_drink_has_hydration(
        self,
        generator: EmergentItemGenerator,
    ):
        """Test that drink items have hydration property."""
        item_state = generator.create_item(
            item_type="drink",
            context="water",
            location_key="tavern",
        )

        assert "hydration" in item_state.properties

    def test_armor_has_ac_bonus(
        self,
        generator: EmergentItemGenerator,
    ):
        """Test that armor items have AC bonus property."""
        item_state = generator.create_item(
            item_type="armor",
            context="leather armor",
            location_key="shop",
        )

        assert "ac_bonus" in item_state.properties

    def test_container_has_capacity(
        self,
        generator: EmergentItemGenerator,
    ):
        """Test that container items have capacity property."""
        item_state = generator.create_item(
            item_type="container",
            context="backpack",
            location_key="shop",
        )

        assert "capacity" in item_state.properties


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_unknown_item_type_defaults_to_misc(
        self,
        generator: EmergentItemGenerator,
        db_session: Session,
    ):
        """Test that unknown item type defaults to misc template."""
        item_state = generator.create_item(
            item_type="unknown_type",
            context="mysterious object",
            location_key="shop",
        )

        # Should still create successfully
        assert item_state is not None
        assert item_state.item_key is not None

    def test_empty_context(
        self,
        generator: EmergentItemGenerator,
    ):
        """Test that empty context doesn't break creation."""
        item_state = generator.create_item(
            item_type="weapon",
            context="",
            location_key="shop",
        )

        assert item_state is not None
        assert item_state.item_key is not None

    def test_narrative_hooks_can_be_generated(
        self,
        generator: EmergentItemGenerator,
    ):
        """Test that items can have narrative hooks."""
        # Create many items with history to increase chance of getting hooks
        hook_found = False
        for _ in range(20):
            item_state = generator.create_item(
                item_type="misc",
                context="ancient artifact",
                location_key="ruins",
                constraints=ItemConstraints(has_history=True),
            )
            if item_state.narrative_hooks:
                hook_found = True
                break

        # Should find at least one item with hooks in 20 tries
        # (20% chance per item with history)
        assert hook_found


# =============================================================================
# Database Persistence Tests
# =============================================================================


class TestDatabasePersistence:
    """Tests for database persistence details."""

    def test_properties_stored_in_json(
        self,
        generator: EmergentItemGenerator,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test that item properties are stored in JSON column."""
        item_state = generator.create_item(
            item_type="weapon",
            context="sword",
            location_key="shop",
            constraints=ItemConstraints(quality="fine", has_history=True),
        )

        db_item = (
            db_session.query(Item)
            .filter(Item.item_key == item_state.item_key)
            .first()
        )

        assert db_item.properties is not None
        assert "quality" in db_item.properties
        assert db_item.properties["quality"] == "fine"
        assert "estimated_value" in db_item.properties

    def test_condition_mapped_to_enum(
        self,
        generator: EmergentItemGenerator,
        db_session: Session,
    ):
        """Test that conditions are properly mapped to database enums."""
        constraints = ItemConstraints(condition="worn")
        item_state = generator.create_item(
            item_type="weapon",
            context="sword",
            location_key="shop",
            constraints=constraints,
        )

        db_item = (
            db_session.query(Item)
            .filter(Item.item_key == item_state.item_key)
            .first()
        )

        assert db_item.condition == ItemCondition.WORN
