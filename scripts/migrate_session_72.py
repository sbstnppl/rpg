"""Migrate session 72 to new inventory system.

This script creates the necessary Location and StorageLocation records
for session 72 and fixes item ownership/placement issues.
"""

from src.database.connection import get_db_session
from src.database.models import (
    Entity,
    GameSession,
    Item,
    Location,
    StorageLocation,
)
from src.database.models.enums import StorageLocationType


SESSION_ID = 72


def create_locations(db) -> dict[str, int]:
    """Step 1: Create Location records for the world."""
    locations_data = [
        {
            "location_key": "forest",
            "display_name": "Western Forest",
            "category": "wilderness",
            "description": "A dense forest to the west of the village. The canopy filters "
            "sunlight into dappled patches on the forest floor. Birdsong echoes through the trees.",
        },
        {
            "location_key": "brook",
            "display_name": "Forest Brook",
            "category": "wilderness",
            "description": "A clear brook winds through the forest, its banks lined with "
            "watercress and smooth river stones. The water is cold and fresh.",
        },
        {
            "location_key": "crossroads",
            "display_name": "Forest Crossroads",
            "category": "wilderness",
            "description": "A four-way crossing in the forest with a weathered wooden signpost. "
            "Paths lead to the village, deeper into the forest, and to unknown destinations.",
        },
        {
            "location_key": "village",
            "display_name": "Village",
            "category": "settlement",
            "description": "A small farming village with thatched-roof cottages clustered around "
            "a central square. The smell of bread baking mingles with livestock and earth.",
        },
        {
            "location_key": "village_square",
            "display_name": "Village Square",
            "category": "public",
            "description": "The heart of the village, with a stone well at its center. "
            "Villagers gather here to draw water, trade gossip, and conduct business.",
        },
        {
            "location_key": "weary_traveler_inn",
            "display_name": "The Weary Traveler",
            "category": "establishment",
            "description": "A cozy inn at the edge of the village square, run by Marta. "
            "The sign above the door shows a tired pilgrim resting under a tree.",
        },
        {
            "location_key": "inn_common_room",
            "display_name": "Common Room",
            "category": "interior",
            "description": "The main room of The Weary Traveler inn. Wooden tables and benches "
            "fill the space, with a large fireplace providing warmth. The smell of porridge "
            "and ale fills the air.",
        },
    ]

    location_ids = {}

    for loc_data in locations_data:
        # Check if already exists
        existing = (
            db.query(Location)
            .filter(
                Location.session_id == SESSION_ID,
                Location.location_key == loc_data["location_key"],
            )
            .first()
        )
        if existing:
            print(f"  Location '{loc_data['location_key']}' already exists (id={existing.id})")
            location_ids[loc_data["location_key"]] = existing.id
            continue

        location = Location(session_id=SESSION_ID, **loc_data)
        db.add(location)
        db.flush()  # Get the ID
        location_ids[loc_data["location_key"]] = location.id
        print(f"  Created Location '{loc_data['location_key']}' (id={location.id})")

    # Set parent relationships
    # inn_common_room -> weary_traveler_inn
    # village_square -> village
    # brook -> forest
    # crossroads -> forest
    parent_mappings = [
        ("inn_common_room", "weary_traveler_inn"),
        ("village_square", "village"),
        ("brook", "forest"),
        ("crossroads", "forest"),
    ]

    for child_key, parent_key in parent_mappings:
        child = (
            db.query(Location)
            .filter(Location.session_id == SESSION_ID, Location.location_key == child_key)
            .first()
        )
        parent = (
            db.query(Location)
            .filter(Location.session_id == SESSION_ID, Location.location_key == parent_key)
            .first()
        )
        if child and parent and child.parent_location_id != parent.id:
            child.parent_location_id = parent.id
            print(f"  Set parent: {child_key} -> {parent_key}")

    return location_ids


def create_body_storages(db, entities: list[Entity]) -> dict[int, int]:
    """Step 2: Create ON_PERSON StorageLocations for each entity."""
    entity_to_storage = {}

    for entity in entities:
        storage_key = f"{entity.entity_key}_body"

        # Check if already exists
        existing = (
            db.query(StorageLocation)
            .filter(
                StorageLocation.session_id == SESSION_ID,
                StorageLocation.location_key == storage_key,
            )
            .first()
        )
        if existing:
            print(f"  Storage '{storage_key}' already exists (id={existing.id})")
            entity_to_storage[entity.id] = existing.id
            continue

        storage = StorageLocation(
            session_id=SESSION_ID,
            location_key=storage_key,
            location_type=StorageLocationType.ON_PERSON,
            owner_entity_id=entity.id,
            container_type="body",
        )
        db.add(storage)
        db.flush()
        entity_to_storage[entity.id] = storage.id
        print(f"  Created ON_PERSON storage for {entity.entity_key} (id={storage.id})")

    return entity_to_storage


def create_container_storages(db, containers: list[Item]) -> dict[int, int]:
    """Step 3: Create StorageLocations linked to container Items."""
    item_to_storage = {}

    container_configs = {
        "durgan_stonehammer_belt_pouch": {"type": "pouch", "capacity": 10, "weight_capacity": 5.0},
        "village_woman_elara_small_coin_purse": {"type": "purse", "capacity": 50, "weight_capacity": 2.0},
        "marta_herb_pouch": {"type": "pouch", "capacity": 20, "weight_capacity": 3.0},
        "marta_coin_purse": {"type": "purse", "capacity": 100, "weight_capacity": 5.0},
        "elara_wicker_basket": {"type": "basket", "capacity": 15, "weight_capacity": 10.0},
        "elara_small_coin_purse": {"type": "purse", "capacity": 50, "weight_capacity": 2.0},
        "old_henrik_herb_pouch": {"type": "pouch", "capacity": 20, "weight_capacity": 3.0},
        "henrik_coin_pouch": {"type": "purse", "capacity": 50, "weight_capacity": 3.0},
    }

    for item in containers:
        storage_key = f"{item.item_key}_storage"
        config = container_configs.get(item.item_key, {"type": "container", "capacity": 10})

        # Check if already exists
        existing = (
            db.query(StorageLocation)
            .filter(
                StorageLocation.session_id == SESSION_ID,
                StorageLocation.location_key == storage_key,
            )
            .first()
        )
        if existing:
            print(f"  Storage '{storage_key}' already exists (id={existing.id})")
            item_to_storage[item.id] = existing.id
            continue

        storage = StorageLocation(
            session_id=SESSION_ID,
            location_key=storage_key,
            location_type=StorageLocationType.CONTAINER,
            owner_entity_id=item.owner_id,
            container_item_id=item.id,
            container_type=config["type"],
            capacity=config.get("capacity"),
            weight_capacity=config.get("weight_capacity"),
        )
        db.add(storage)
        db.flush()
        item_to_storage[item.id] = storage.id
        print(f"  Created CONTAINER storage for {item.item_key} (id={storage.id})")

    return item_to_storage


def create_inn_storage(db, inn_location_id: int) -> int:
    """Step 4: Create inn kitchen storage for inn-owned items."""
    storage_key = "inn_kitchen_storage"

    # Check if already exists
    existing = (
        db.query(StorageLocation)
        .filter(
            StorageLocation.session_id == SESSION_ID,
            StorageLocation.location_key == storage_key,
        )
        .first()
    )
    if existing:
        print(f"  Storage '{storage_key}' already exists (id={existing.id})")
        return existing.id

    storage = StorageLocation(
        session_id=SESSION_ID,
        location_key=storage_key,
        location_type=StorageLocationType.PLACE,
        owner_location_id=inn_location_id,
        container_type="kitchen",
        capacity=100,
        is_fixed=True,
    )
    db.add(storage)
    db.flush()
    print(f"  Created inn_kitchen_storage (id={storage.id})")
    return storage.id


def fix_bowl_spoon_ownership(db, inn_location_id: int) -> None:
    """Step 5: Fix bowl/spoon to be inn-owned, held by player."""
    items_to_fix = ["porridge_bowl", "wooden_spoon"]

    for item_key in items_to_fix:
        item = (
            db.query(Item)
            .filter(Item.session_id == SESSION_ID, Item.item_key == item_key)
            .first()
        )
        if item:
            old_owner = item.owner_id
            item.owner_id = None  # No entity owner
            item.owner_location_id = inn_location_id  # Inn owns it
            # holder_id stays as player (they're using it)
            print(f"  Fixed {item_key}: owner_id {old_owner} -> owner_location_id {inn_location_id}")


def move_items_to_storage(db, belt_pouch_storage_id: int) -> None:
    """Step 6: Move gold and stones to belt pouch storage."""
    items_to_move = [
        "durgan_stonehammer_starting_gold",
        "smooth_river_stones",
    ]

    for item_key in items_to_move:
        item = (
            db.query(Item)
            .filter(Item.session_id == SESSION_ID, Item.item_key == item_key)
            .first()
        )
        if item:
            item.storage_location_id = belt_pouch_storage_id
            item.holder_id = None  # In storage, not directly held
            item.body_slot = None  # Not on body
            print(f"  Moved {item_key} to belt pouch storage")


def update_body_slots(db) -> None:
    """Step 7: Update body slots for items that need them."""
    # Items currently with slot="-" that need proper slots
    slot_updates = [
        ("sturdy_branches", "off_hand"),
        ("porridge_bowl", "main_hand"),
        # wooden_spoon is narratively in the bowl, not held separately
    ]

    for item_key, slot in slot_updates:
        item = (
            db.query(Item)
            .filter(Item.session_id == SESSION_ID, Item.item_key == item_key)
            .first()
        )
        if item:
            old_slot = item.body_slot
            item.body_slot = slot
            print(f"  Updated {item_key}: body_slot '{old_slot}' -> '{slot}'")


def main():
    """Run the full migration."""
    print("=" * 60)
    print("Session 72 Migration to New Inventory System")
    print("=" * 60)

    with get_db_session() as db:
        # Verify session exists
        session = db.query(GameSession).filter(GameSession.id == SESSION_ID).first()
        if not session:
            print(f"ERROR: Session {SESSION_ID} not found!")
            return

        print(f"\nSession: {session.id} ({session.setting})")

        # Get entities
        entities = db.query(Entity).filter(Entity.session_id == SESSION_ID).all()
        print(f"Entities: {len(entities)}")

        # Get container items
        containers = (
            db.query(Item)
            .filter(
                Item.session_id == SESSION_ID,
                Item.item_key.like("%pouch%")
                | Item.item_key.like("%basket%")
                | Item.item_key.like("%purse%"),
            )
            .all()
        )
        print(f"Container items: {len(containers)}")

        # Step 1: Create Locations
        print("\n--- Step 1: Create Location Records ---")
        location_ids = create_locations(db)

        # Step 2: Create ON_PERSON storages
        print("\n--- Step 2: Create ON_PERSON StorageLocations ---")
        entity_storage_map = create_body_storages(db, entities)

        # Step 3: Create CONTAINER storages linked to items
        print("\n--- Step 3: Create Container StorageLocations ---")
        container_storage_map = create_container_storages(db, containers)

        # Step 4: Create inn kitchen storage
        print("\n--- Step 4: Create Inn Storage ---")
        inn_id = location_ids.get("weary_traveler_inn")
        if inn_id:
            inn_storage_id = create_inn_storage(db, inn_id)
        else:
            print("  ERROR: Inn location not found!")
            return

        # Step 5: Fix bowl/spoon ownership
        print("\n--- Step 5: Fix Bowl/Spoon Ownership ---")
        fix_bowl_spoon_ownership(db, inn_id)

        # Step 6: Move items to storage
        print("\n--- Step 6: Move Items to Storage ---")
        belt_pouch_storage_id = None
        for item in containers:
            if item.item_key == "durgan_stonehammer_belt_pouch":
                belt_pouch_storage_id = container_storage_map.get(item.id)
                break

        if belt_pouch_storage_id:
            move_items_to_storage(db, belt_pouch_storage_id)
        else:
            print("  ERROR: Belt pouch storage not found!")

        # Step 7: Update body slots
        print("\n--- Step 7: Update Body Slots ---")
        update_body_slots(db)

        # Commit is automatic via context manager
        print("\n" + "=" * 60)
        print("Migration complete!")
        print("=" * 60)

        # Summary
        locs = db.query(Location).filter(Location.session_id == SESSION_ID).count()
        storages = db.query(StorageLocation).filter(StorageLocation.session_id == SESSION_ID).count()
        print(f"\nFinal state:")
        print(f"  Locations: {locs}")
        print(f"  StorageLocations: {storages}")


if __name__ == "__main__":
    main()
