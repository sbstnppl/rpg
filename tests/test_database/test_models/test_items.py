"""Tests for Item and StorageLocation models."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.database.models.enums import ItemCondition, ItemType, StorageLocationType
from src.database.models.items import Item, StorageLocation
from src.database.models.session import GameSession
from tests.factories import (
    create_entity,
    create_game_session,
    create_item,
    create_location,
    create_storage_location,
)


class TestStorageLocation:
    """Tests for StorageLocation model."""

    def test_create_storage_location_required_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify StorageLocation creation with required fields."""
        loc = StorageLocation(
            session_id=game_session.id,
            location_key="player_body",
            location_type=StorageLocationType.ON_PERSON,
        )
        db_session.add(loc)
        db_session.flush()

        assert loc.id is not None
        assert loc.session_id == game_session.id
        assert loc.location_key == "player_body"

    def test_storage_location_types(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify all storage location types."""
        for loc_type in StorageLocationType:
            storage = create_storage_location(
                db_session,
                game_session,
                location_type=loc_type,
            )
            db_session.refresh(storage)
            assert storage.location_type == loc_type

    def test_storage_location_unique_constraint(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify unique constraint on session_id + location_key."""
        create_storage_location(db_session, game_session, location_key="chest_01")

        with pytest.raises(IntegrityError):
            create_storage_location(db_session, game_session, location_key="chest_01")

    def test_storage_location_hierarchy(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify parent_location_id self-reference."""
        backpack = create_storage_location(
            db_session,
            game_session,
            location_key="backpack",
            location_type=StorageLocationType.CONTAINER,
        )
        inner_pouch = create_storage_location(
            db_session,
            game_session,
            location_key="inner_pouch",
            location_type=StorageLocationType.CONTAINER,
            parent_location_id=backpack.id,
        )

        db_session.refresh(inner_pouch)

        assert inner_pouch.parent_location_id == backpack.id
        assert inner_pouch.parent_location.location_key == "backpack"

    def test_storage_location_owner_entity(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify owner_entity_id foreign key."""
        entity = create_entity(db_session, game_session)
        storage = create_storage_location(
            db_session,
            game_session,
            owner_entity_id=entity.id,
        )

        db_session.refresh(storage)

        assert storage.owner_entity_id == entity.id
        assert storage.owner_entity.id == entity.id

    def test_storage_location_world_location(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify world_location_id for PLACE type."""
        world_loc = create_location(db_session, game_session)
        storage = create_storage_location(
            db_session,
            game_session,
            location_type=StorageLocationType.PLACE,
            world_location_id=world_loc.id,
        )

        db_session.refresh(storage)

        assert storage.world_location_id == world_loc.id
        assert storage.world_location.id == world_loc.id

    def test_storage_location_capacity(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify capacity field for containers."""
        storage = create_storage_location(
            db_session,
            game_session,
            location_type=StorageLocationType.CONTAINER,
            container_type="chest",
            capacity=20,
        )

        db_session.refresh(storage)

        assert storage.container_type == "chest"
        assert storage.capacity == 20

    def test_storage_location_temporary(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify is_temporary flag."""
        storage = create_storage_location(
            db_session,
            game_session,
            is_temporary=True,
        )

        db_session.refresh(storage)
        assert storage.is_temporary is True

    def test_storage_location_stored_items_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify stored_items relationship."""
        storage = create_storage_location(db_session, game_session)
        item = create_item(db_session, game_session, storage_location_id=storage.id)

        db_session.refresh(storage)

        assert len(storage.stored_items) == 1
        assert storage.stored_items[0].id == item.id

    def test_storage_location_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        storage = create_storage_location(
            db_session,
            game_session,
            location_key="backpack",
            location_type=StorageLocationType.CONTAINER,
        )

        repr_str = repr(storage)
        assert "StorageLocation" in repr_str
        assert "backpack" in repr_str
        assert "container" in repr_str


class TestItem:
    """Tests for Item model."""

    def test_create_item_required_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify Item creation with required fields."""
        item = Item(
            session_id=game_session.id,
            item_key="sword_01",
            display_name="Iron Sword",
        )
        db_session.add(item)
        db_session.flush()

        assert item.id is not None
        assert item.item_key == "sword_01"
        assert item.display_name == "Iron Sword"

    def test_item_unique_constraint(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify unique constraint on session_id + item_key."""
        create_item(db_session, game_session, item_key="sword")

        with pytest.raises(IntegrityError):
            create_item(db_session, game_session, item_key="sword")

    def test_item_owner_vs_holder(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify separate owner_id and holder_id fields."""
        owner = create_entity(db_session, game_session, entity_key="owner")
        holder = create_entity(db_session, game_session, entity_key="holder")

        item = create_item(
            db_session,
            game_session,
            owner_id=owner.id,
            holder_id=holder.id,
        )

        db_session.refresh(item)

        assert item.owner_id == owner.id
        assert item.holder_id == holder.id
        assert item.owner_id != item.holder_id
        assert item.owner.entity_key == "owner"
        assert item.holder.entity_key == "holder"

    def test_item_body_slot_and_layer(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify body_slot, body_layer, is_visible fields."""
        shirt = create_item(
            db_session,
            game_session,
            item_key="shirt",
            item_type=ItemType.CLOTHING,
            body_slot="upper_body",
            body_layer=0,
            is_visible=False,  # Covered by outer layer
        )
        jacket = create_item(
            db_session,
            game_session,
            item_key="jacket",
            item_type=ItemType.CLOTHING,
            body_slot="upper_body",
            body_layer=1,
            is_visible=True,
        )

        db_session.refresh(shirt)
        db_session.refresh(jacket)

        assert shirt.body_slot == "upper_body"
        assert shirt.body_layer == 0
        assert shirt.is_visible is False

        assert jacket.body_layer == 1
        assert jacket.is_visible is True

    def test_item_provides_slots_json(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify provides_slots JSON field."""
        pants = create_item(
            db_session,
            game_session,
            item_type=ItemType.CLOTHING,
            provides_slots=["pocket_left", "pocket_right"],
        )

        db_session.refresh(pants)

        assert pants.provides_slots == ["pocket_left", "pocket_right"]

    def test_item_type_enum(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify ItemType enum storage."""
        for item_type in ItemType:
            item = create_item(db_session, game_session, item_type=item_type)
            db_session.refresh(item)
            assert item.item_type == item_type

    def test_item_condition_enum(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify ItemCondition enum storage."""
        for condition in ItemCondition:
            item = create_item(db_session, game_session, condition=condition)
            db_session.refresh(item)
            assert item.condition == condition

    def test_item_stacking(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify quantity and is_stackable fields."""
        potion = create_item(
            db_session,
            game_session,
            item_type=ItemType.CONSUMABLE,
            is_stackable=True,
            quantity=5,
        )

        db_session.refresh(potion)

        assert potion.is_stackable is True
        assert potion.quantity == 5

    def test_item_properties_json(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify properties JSON field."""
        sword = create_item(
            db_session,
            game_session,
            item_type=ItemType.WEAPON,
            properties={
                "damage": "2d6",
                "damage_type": "slashing",
                "weight": 3,
            },
        )

        db_session.refresh(sword)

        assert sword.properties["damage"] == "2d6"
        assert sword.properties["damage_type"] == "slashing"

    def test_item_storage_location_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify storage_location_id FK and relationship."""
        storage = create_storage_location(db_session, game_session)
        item = create_item(db_session, game_session, storage_location_id=storage.id)

        db_session.refresh(item)

        assert item.storage_location_id == storage.id
        assert item.storage_location.id == storage.id

    def test_item_durability(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify durability field."""
        item = create_item(db_session, game_session, durability=75)

        db_session.refresh(item)
        assert item.durability == 75

    def test_item_acquired_turn(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify acquired_turn tracking."""
        item = create_item(db_session, game_session, acquired_turn=10)

        db_session.refresh(item)
        assert item.acquired_turn == 10

    def test_item_repr_basic(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify basic string representation."""
        item = create_item(
            db_session,
            game_session,
            display_name="Iron Sword",
        )

        repr_str = repr(item)
        assert "Item" in repr_str
        assert "Iron Sword" in repr_str

    def test_item_repr_with_quantity(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify repr with quantity."""
        item = create_item(
            db_session,
            game_session,
            display_name="Gold Coin",
            quantity=100,
        )

        repr_str = repr(item)
        assert "x100" in repr_str

    def test_item_repr_with_slot(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify repr with body slot."""
        item = create_item(
            db_session,
            game_session,
            display_name="Helmet",
            body_slot="head",
            body_layer=0,
        )

        repr_str = repr(item)
        assert "head" in repr_str
        assert "L0" in repr_str

    def test_item_session_scoping(self, db_session: Session):
        """Verify items are properly scoped to sessions."""
        session1 = create_game_session(db_session)
        session2 = create_game_session(db_session)

        item1 = create_item(db_session, session1)
        item2 = create_item(db_session, session2)

        result = (
            db_session.query(Item)
            .filter(Item.session_id == session1.id)
            .all()
        )

        assert len(result) == 1
        assert result[0].id == item1.id
