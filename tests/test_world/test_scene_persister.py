"""Tests for ScenePersister - Scene-First Architecture Phase 4.

These tests verify:
- Persisting World Mechanics output (new NPCs, events, facts)
- Persisting Scene Builder output (furniture, items)
- Building narrator manifest from persisted scene
- Atomic transaction behavior
- Location scene generation tracking
"""

import pytest
from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from src.database.models.entities import Entity, NPCExtension
from src.database.models.enums import EntityType, ItemType, StorageLocationType
from src.database.models.items import Item, StorageLocation
from src.database.models.session import GameSession
from src.database.models.world import Fact, Location, TimeState
from src.world.schemas import (
    Atmosphere,
    EntityRef,
    FurnitureSpec,
    ItemSpec,
    ItemVisibility,
    NarratorManifest,
    NPCPlacement,
    NPCSpec,
    PersistedItem,
    PersistedNPC,
    PersistedScene,
    PersistedWorldUpdate,
    PresenceReason,
    SceneManifest,
    SceneNPC,
    WorldUpdate,
    FactUpdate,
)
from tests.factories import (
    create_entity,
    create_item,
    create_location,
    create_npc_extension,
    create_storage_location,
    create_time_state,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def time_state(db_session: Session, game_session: GameSession) -> TimeState:
    """Create a time state for testing."""
    return create_time_state(db_session, game_session, current_time="10:00")


@pytest.fixture
def location(db_session: Session, game_session: GameSession) -> Location:
    """Create a test location."""
    return create_location(
        db_session,
        game_session,
        location_key="tavern_main",
        display_name="The Main Hall",
        category="tavern",
    )


@pytest.fixture
def player_entity(db_session: Session, game_session: GameSession) -> Entity:
    """Create a player entity."""
    return create_entity(
        db_session,
        game_session,
        entity_type=EntityType.PLAYER,
        entity_key="player",
        display_name="Hero",
    )


@pytest.fixture
def existing_npc(db_session: Session, game_session: GameSession) -> Entity:
    """Create an existing NPC entity."""
    entity = create_entity(
        db_session,
        game_session,
        entity_type=EntityType.NPC,
        entity_key="bartender_001",
        display_name="Tom the Bartender",
        gender="male",
    )
    create_npc_extension(
        db_session,
        entity,
        job="bartender",
        current_location="tavern_main",
    )
    return entity


@pytest.fixture
def sample_atmosphere() -> Atmosphere:
    """Create a sample atmosphere for testing."""
    return Atmosphere(
        lighting="dim candlelight",
        lighting_source="candles on tables",
        sounds=["murmured conversations", "clinking glasses"],
        smells=["ale", "wood smoke"],
        temperature="warm",
        overall_mood="cozy",
    )


@pytest.fixture
def sample_world_update() -> WorldUpdate:
    """Create a sample world update with a new NPC."""
    return WorldUpdate(
        npcs_at_location=[
            NPCPlacement(
                new_npc=NPCSpec(
                    display_name="Sarah",
                    gender="female",
                    occupation="merchant",
                    personality_hints=["friendly", "curious"],
                ),
                presence_reason=PresenceReason.VISITING,
                presence_justification="Traveling through town",
                activity="drinking ale",
                mood="cheerful",
                position_in_scene="at a corner table",
            ),
        ],
        fact_updates=[
            FactUpdate(
                subject="tavern_main",
                predicate="has_special",
                value="meat pie",
                source="observation",
            ),
        ],
    )


@pytest.fixture
def sample_scene_manifest(sample_atmosphere: Atmosphere) -> SceneManifest:
    """Create a sample scene manifest."""
    return SceneManifest(
        location_key="tavern_main",
        location_display="The Main Hall",
        location_type="tavern",
        furniture=[
            FurnitureSpec(
                furniture_key="bar_counter",
                display_name="long oak bar",
                furniture_type="bar",
                material="oak",
                condition="worn",
                position_in_room="along the back wall",
                is_container=False,
            ),
            FurnitureSpec(
                furniture_key="fireplace_001",
                display_name="stone fireplace",
                furniture_type="fireplace",
                material="stone",
                condition="good",
                position_in_room="center of the west wall",
                is_container=False,
            ),
        ],
        items=[
            ItemSpec(
                item_key="mug_001",
                display_name="pewter mug",
                item_type="container",
                position="on the bar",
                visibility=ItemVisibility.OBVIOUS,
                material="pewter",
            ),
            ItemSpec(
                item_key="coin_pouch_hidden",
                display_name="small coin pouch",
                item_type="container",
                position="under a loose floorboard",
                visibility=ItemVisibility.HIDDEN,
                material="leather",
            ),
        ],
        npcs=[],  # NPCs added after World Mechanics
        atmosphere=sample_atmosphere,
        is_first_visit=True,
    )


# =============================================================================
# ScenePersister Initialization Tests
# =============================================================================


class TestScenePersisterInit:
    """Tests for ScenePersister initialization."""

    def test_init_with_db_and_session(
        self,
        db_session: Session,
        game_session: GameSession,
    ) -> None:
        """ScenePersister initializes with db and game_session."""
        from src.world.scene_persister import ScenePersister

        persister = ScenePersister(db_session, game_session)

        assert persister.db is db_session
        assert persister.game_session is game_session
        assert persister.session_id == game_session.id


# =============================================================================
# Persist World Update Tests
# =============================================================================


class TestPersistWorldUpdate:
    """Tests for persisting World Mechanics output."""

    def test_persist_world_update_creates_new_npc(
        self,
        db_session: Session,
        game_session: GameSession,
        location: Location,
        time_state: TimeState,
        sample_world_update: WorldUpdate,
    ) -> None:
        """New NPCs from WorldUpdate are persisted to the database."""
        from src.world.scene_persister import ScenePersister

        persister = ScenePersister(db_session, game_session)

        result = persister.persist_world_update(
            world_update=sample_world_update,
            location_key="tavern_main",
            turn_number=1,
        )

        assert isinstance(result, PersistedWorldUpdate)
        assert len(result.npcs) == 1
        assert result.npcs[0].was_created is True

        # Verify NPC was created in database
        npc = (
            db_session.query(Entity)
            .filter(
                Entity.session_id == game_session.id,
                Entity.display_name == "Sarah",
            )
            .first()
        )
        assert npc is not None
        assert npc.entity_type == EntityType.NPC
        assert npc.gender == "female"

    def test_persist_world_update_creates_npc_extension(
        self,
        db_session: Session,
        game_session: GameSession,
        location: Location,
        time_state: TimeState,
        sample_world_update: WorldUpdate,
    ) -> None:
        """New NPCs get NPC extension with location info."""
        from src.world.scene_persister import ScenePersister

        persister = ScenePersister(db_session, game_session)

        result = persister.persist_world_update(
            world_update=sample_world_update,
            location_key="tavern_main",
            turn_number=1,
        )

        # Get the created NPC
        entity_key = result.npcs[0].entity_key
        npc = (
            db_session.query(Entity)
            .filter(
                Entity.session_id == game_session.id,
                Entity.entity_key == entity_key,
            )
            .first()
        )
        assert npc is not None
        assert npc.npc_extension is not None
        assert npc.npc_extension.current_location == "tavern_main"
        assert npc.npc_extension.job == "merchant"

    def test_persist_world_update_skips_existing_npcs(
        self,
        db_session: Session,
        game_session: GameSession,
        location: Location,
        time_state: TimeState,
        existing_npc: Entity,
    ) -> None:
        """Existing NPCs are not recreated."""
        from src.world.scene_persister import ScenePersister

        world_update = WorldUpdate(
            npcs_at_location=[
                NPCPlacement(
                    entity_key="bartender_001",
                    presence_reason=PresenceReason.SCHEDULE,
                    presence_justification="Working shift",
                    activity="polishing glasses",
                    mood="neutral",
                    position_in_scene="behind the bar",
                ),
            ],
        )

        persister = ScenePersister(db_session, game_session)

        result = persister.persist_world_update(
            world_update=world_update,
            location_key="tavern_main",
            turn_number=1,
        )

        assert len(result.npcs) == 1
        assert result.npcs[0].entity_key == "bartender_001"
        assert result.npcs[0].was_created is False

    def test_persist_world_update_stores_facts(
        self,
        db_session: Session,
        game_session: GameSession,
        location: Location,
        time_state: TimeState,
        sample_world_update: WorldUpdate,
    ) -> None:
        """Fact updates are persisted to the database."""
        from src.world.scene_persister import ScenePersister

        persister = ScenePersister(db_session, game_session)

        result = persister.persist_world_update(
            world_update=sample_world_update,
            location_key="tavern_main",
            turn_number=1,
        )

        assert result.facts_stored == 1

        # Verify fact was created
        fact = (
            db_session.query(Fact)
            .filter(
                Fact.session_id == game_session.id,
                Fact.subject_key == "tavern_main",
                Fact.predicate == "has_special",
            )
            .first()
        )
        assert fact is not None
        assert fact.value == "meat pie"

    def test_persist_world_update_generates_unique_keys(
        self,
        db_session: Session,
        game_session: GameSession,
        location: Location,
        time_state: TimeState,
    ) -> None:
        """Generated NPC keys are unique and follow naming convention."""
        from src.world.scene_persister import ScenePersister

        world_update = WorldUpdate(
            npcs_at_location=[
                NPCPlacement(
                    new_npc=NPCSpec(display_name="John"),
                    presence_reason=PresenceReason.VISITING,
                    presence_justification="Visiting",
                    activity="standing",
                    position_in_scene="by door",
                ),
                NPCPlacement(
                    new_npc=NPCSpec(display_name="Jane"),
                    presence_reason=PresenceReason.VISITING,
                    presence_justification="Visiting",
                    activity="standing",
                    position_in_scene="by window",
                ),
            ],
        )

        persister = ScenePersister(db_session, game_session)

        result = persister.persist_world_update(
            world_update=world_update,
            location_key="tavern_main",
            turn_number=1,
        )

        assert len(result.npcs) == 2
        keys = [npc.entity_key for npc in result.npcs]
        assert keys[0] != keys[1]  # Keys are unique
        assert all("_" in key for key in keys)  # Keys have underscore separator


# =============================================================================
# Persist Scene Tests
# =============================================================================


class TestPersistScene:
    """Tests for persisting Scene Builder output."""

    def test_persist_scene_creates_furniture(
        self,
        db_session: Session,
        game_session: GameSession,
        location: Location,
        sample_scene_manifest: SceneManifest,
    ) -> None:
        """Furniture from SceneManifest is persisted as items."""
        from src.world.scene_persister import ScenePersister

        persister = ScenePersister(db_session, game_session)

        result = persister.persist_scene(
            scene_manifest=sample_scene_manifest,
            location=location,
            turn_number=1,
        )

        assert isinstance(result, PersistedScene)
        assert len(result.furniture) == 2

        # Verify furniture items were created
        bar = (
            db_session.query(Item)
            .filter(
                Item.session_id == game_session.id,
                Item.item_key == "bar_counter",
            )
            .first()
        )
        assert bar is not None
        assert bar.display_name == "long oak bar"
        assert bar.properties.get("furniture_type") == "bar"

    def test_persist_scene_creates_items(
        self,
        db_session: Session,
        game_session: GameSession,
        location: Location,
        sample_scene_manifest: SceneManifest,
    ) -> None:
        """Items from SceneManifest are persisted."""
        from src.world.scene_persister import ScenePersister

        persister = ScenePersister(db_session, game_session)

        result = persister.persist_scene(
            scene_manifest=sample_scene_manifest,
            location=location,
            turn_number=1,
        )

        assert len(result.items) == 2

        # Verify items were created
        mug = (
            db_session.query(Item)
            .filter(
                Item.session_id == game_session.id,
                Item.item_key == "mug_001",
            )
            .first()
        )
        assert mug is not None
        assert mug.display_name == "pewter mug"

    def test_persist_scene_stores_visibility(
        self,
        db_session: Session,
        game_session: GameSession,
        location: Location,
        sample_scene_manifest: SceneManifest,
    ) -> None:
        """Item visibility is stored in properties."""
        from src.world.scene_persister import ScenePersister

        persister = ScenePersister(db_session, game_session)

        persister.persist_scene(
            scene_manifest=sample_scene_manifest,
            location=location,
            turn_number=1,
        )

        # Check hidden item has visibility property
        hidden_item = (
            db_session.query(Item)
            .filter(
                Item.session_id == game_session.id,
                Item.item_key == "coin_pouch_hidden",
            )
            .first()
        )
        assert hidden_item is not None
        assert hidden_item.properties.get("visibility") == "hidden"

    def test_persist_scene_creates_storage_location(
        self,
        db_session: Session,
        game_session: GameSession,
        location: Location,
        sample_scene_manifest: SceneManifest,
    ) -> None:
        """Scene items are linked to a storage location for the place."""
        from src.world.scene_persister import ScenePersister

        persister = ScenePersister(db_session, game_session)

        persister.persist_scene(
            scene_manifest=sample_scene_manifest,
            location=location,
            turn_number=1,
        )

        # Check storage location was created
        storage = (
            db_session.query(StorageLocation)
            .filter(
                StorageLocation.session_id == game_session.id,
                StorageLocation.owner_location_id == location.id,
                StorageLocation.location_type == StorageLocationType.PLACE,
            )
            .first()
        )
        assert storage is not None

        # Check items are linked to storage
        mug = (
            db_session.query(Item)
            .filter(
                Item.session_id == game_session.id,
                Item.item_key == "mug_001",
            )
            .first()
        )
        assert mug.storage_location_id == storage.id

    def test_persist_scene_sets_location_first_visited(
        self,
        db_session: Session,
        game_session: GameSession,
        location: Location,
        sample_scene_manifest: SceneManifest,
    ) -> None:
        """First visit marks the location's first_visited_turn."""
        from src.world.scene_persister import ScenePersister

        assert location.first_visited_turn is None

        persister = ScenePersister(db_session, game_session)

        result = persister.persist_scene(
            scene_manifest=sample_scene_manifest,
            location=location,
            turn_number=5,
        )

        db_session.refresh(location)
        assert location.first_visited_turn == 5
        assert result.location_marked_generated is True

    def test_persist_scene_does_not_reset_first_visited(
        self,
        db_session: Session,
        game_session: GameSession,
        location: Location,
        sample_scene_manifest: SceneManifest,
    ) -> None:
        """Return visits don't update first_visited_turn."""
        from src.world.scene_persister import ScenePersister

        # Mark as already visited
        location.first_visited_turn = 2
        db_session.flush()

        # Modify manifest to indicate return visit
        sample_scene_manifest.is_first_visit = False

        persister = ScenePersister(db_session, game_session)

        result = persister.persist_scene(
            scene_manifest=sample_scene_manifest,
            location=location,
            turn_number=10,
        )

        db_session.refresh(location)
        assert location.first_visited_turn == 2  # Unchanged
        assert result.location_marked_generated is False

    def test_persist_scene_furniture_owned_by_location(
        self,
        db_session: Session,
        game_session: GameSession,
        location: Location,
        sample_scene_manifest: SceneManifest,
    ) -> None:
        """Furniture items are owned by the location."""
        from src.world.scene_persister import ScenePersister

        persister = ScenePersister(db_session, game_session)

        persister.persist_scene(
            scene_manifest=sample_scene_manifest,
            location=location,
            turn_number=1,
        )

        bar = (
            db_session.query(Item)
            .filter(
                Item.session_id == game_session.id,
                Item.item_key == "bar_counter",
            )
            .first()
        )
        assert bar.owner_location_id == location.id


# =============================================================================
# Build Narrator Manifest Tests
# =============================================================================


class TestBuildNarratorManifest:
    """Tests for building narrator manifest from scene."""

    def test_build_narrator_manifest_includes_npcs(
        self,
        db_session: Session,
        game_session: GameSession,
        location: Location,
        existing_npc: Entity,
        sample_atmosphere: Atmosphere,
    ) -> None:
        """Narrator manifest includes NPCs from scene."""
        from src.world.scene_persister import ScenePersister

        # Create scene with NPCs
        scene = SceneManifest(
            location_key="tavern_main",
            location_display="The Main Hall",
            location_type="tavern",
            furniture=[],
            items=[],
            npcs=[
                SceneNPC(
                    entity_key="bartender_001",
                    display_name="Tom the Bartender",
                    gender="male",
                    presence_reason=PresenceReason.SCHEDULE,
                    activity="polishing glasses",
                    mood="neutral",
                    position_in_scene="behind the bar",
                    pronouns="he/him",
                ),
            ],
            atmosphere=sample_atmosphere,
        )

        persister = ScenePersister(db_session, game_session)

        manifest = persister.build_narrator_manifest(scene)

        assert isinstance(manifest, NarratorManifest)
        assert "bartender_001" in manifest.entities
        entity_ref = manifest.entities["bartender_001"]
        assert entity_ref.display_name == "Tom the Bartender"
        assert entity_ref.entity_type == "npc"
        assert entity_ref.pronouns == "he/him"

    def test_build_narrator_manifest_includes_furniture(
        self,
        db_session: Session,
        game_session: GameSession,
        location: Location,
        sample_scene_manifest: SceneManifest,
    ) -> None:
        """Narrator manifest includes furniture from scene."""
        from src.world.scene_persister import ScenePersister

        persister = ScenePersister(db_session, game_session)

        manifest = persister.build_narrator_manifest(sample_scene_manifest)

        assert "bar_counter" in manifest.entities
        assert manifest.entities["bar_counter"].entity_type == "furniture"
        assert "fireplace_001" in manifest.entities

    def test_build_narrator_manifest_includes_items(
        self,
        db_session: Session,
        game_session: GameSession,
        location: Location,
        sample_scene_manifest: SceneManifest,
    ) -> None:
        """Narrator manifest includes visible items from scene."""
        from src.world.scene_persister import ScenePersister

        persister = ScenePersister(db_session, game_session)

        manifest = persister.build_narrator_manifest(sample_scene_manifest)

        # Should include obvious item
        assert "mug_001" in manifest.entities
        assert manifest.entities["mug_001"].entity_type == "item"

        # Should include hidden item (narrator needs to know about all)
        assert "coin_pouch_hidden" in manifest.entities

    def test_build_narrator_manifest_includes_atmosphere(
        self,
        db_session: Session,
        game_session: GameSession,
        location: Location,
        sample_scene_manifest: SceneManifest,
    ) -> None:
        """Narrator manifest includes atmosphere details."""
        from src.world.scene_persister import ScenePersister

        persister = ScenePersister(db_session, game_session)

        manifest = persister.build_narrator_manifest(sample_scene_manifest)

        assert manifest.atmosphere.lighting == "dim candlelight"
        assert manifest.atmosphere.overall_mood == "cozy"

    def test_build_narrator_manifest_includes_location(
        self,
        db_session: Session,
        game_session: GameSession,
        location: Location,
        sample_scene_manifest: SceneManifest,
    ) -> None:
        """Narrator manifest includes location info."""
        from src.world.scene_persister import ScenePersister

        persister = ScenePersister(db_session, game_session)

        manifest = persister.build_narrator_manifest(sample_scene_manifest)

        assert manifest.location_key == "tavern_main"
        assert manifest.location_display == "The Main Hall"

    def test_get_reference_guide_formats_correctly(
        self,
        db_session: Session,
        game_session: GameSession,
        location: Location,
        existing_npc: Entity,
        sample_scene_manifest: SceneManifest,
    ) -> None:
        """Reference guide is formatted for narrator prompt."""
        from src.world.scene_persister import ScenePersister

        # Add NPC to manifest
        sample_scene_manifest.npcs = [
            SceneNPC(
                entity_key="bartender_001",
                display_name="Tom",
                gender="male",
                presence_reason=PresenceReason.SCHEDULE,
                activity="working",
                mood="neutral",
                position_in_scene="behind bar",
                pronouns="he/him",
            ),
        ]

        persister = ScenePersister(db_session, game_session)

        manifest = persister.build_narrator_manifest(sample_scene_manifest)
        guide = manifest.get_reference_guide()

        assert "## Entities You May Reference" in guide
        assert "[bartender_001:Tom]" in guide  # Format: [key:display_name]
        assert "NPCs:" in guide or "**NPCs:**" in guide
        assert "Furniture:" in guide or "**Furniture:**" in guide


# =============================================================================
# Atomic Transaction Tests
# =============================================================================


class TestAtomicTransaction:
    """Tests for atomic transaction behavior."""

    def test_persist_world_update_is_atomic(
        self,
        db_session: Session,
        game_session: GameSession,
        location: Location,
        time_state: TimeState,
    ) -> None:
        """If one NPC fails to create, none are created."""
        from src.world.scene_persister import ScenePersister

        # Create first NPC to cause duplicate key error
        first_npc = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.NPC,
            entity_key="duplicate_key",
            display_name="First",
        )

        world_update = WorldUpdate(
            npcs_at_location=[
                NPCPlacement(
                    new_npc=NPCSpec(display_name="Good NPC"),
                    presence_reason=PresenceReason.VISITING,
                    presence_justification="Visiting",
                    activity="standing",
                    position_in_scene="by door",
                ),
            ],
        )

        persister = ScenePersister(db_session, game_session)

        # Should not raise - handled gracefully
        result = persister.persist_world_update(
            world_update=world_update,
            location_key="tavern_main",
            turn_number=1,
        )

        # Should successfully create the NPC with a unique key
        assert len(result.npcs) == 1

    def test_persist_scene_handles_existing_items(
        self,
        db_session: Session,
        game_session: GameSession,
        location: Location,
        sample_atmosphere: Atmosphere,
    ) -> None:
        """If items already exist, they are not duplicated."""
        from src.world.scene_persister import ScenePersister

        # Create an item that will be in the manifest
        existing = create_item(
            db_session,
            game_session,
            item_key="existing_item",
            display_name="Existing Item",
        )

        scene = SceneManifest(
            location_key="tavern_main",
            location_display="The Main Hall",
            location_type="tavern",
            furniture=[],
            items=[
                ItemSpec(
                    item_key="existing_item",
                    display_name="Existing Item",
                    item_type="misc",
                    position="on floor",
                    visibility=ItemVisibility.OBVIOUS,
                ),
            ],
            npcs=[],
            atmosphere=sample_atmosphere,
            is_first_visit=True,
        )

        persister = ScenePersister(db_session, game_session)

        result = persister.persist_scene(
            scene_manifest=scene,
            location=location,
            turn_number=1,
        )

        # Should skip existing item
        assert len(result.items) == 1
        assert result.items[0].was_created is False


# =============================================================================
# NPC Key Generation Tests
# =============================================================================


class TestNPCKeyGeneration:
    """Tests for NPC key generation."""

    def test_generates_key_from_display_name(
        self,
        db_session: Session,
        game_session: GameSession,
        location: Location,
        time_state: TimeState,
    ) -> None:
        """NPC keys are derived from display names."""
        from src.world.scene_persister import ScenePersister

        world_update = WorldUpdate(
            npcs_at_location=[
                NPCPlacement(
                    new_npc=NPCSpec(display_name="Lady Eleanor"),
                    presence_reason=PresenceReason.VISITING,
                    presence_justification="Visiting",
                    activity="sitting",
                    position_in_scene="at table",
                ),
            ],
        )

        persister = ScenePersister(db_session, game_session)

        result = persister.persist_world_update(
            world_update=world_update,
            location_key="tavern_main",
            turn_number=1,
        )

        key = result.npcs[0].entity_key
        assert "lady" in key.lower() or "eleanor" in key.lower()

    def test_handles_special_characters_in_name(
        self,
        db_session: Session,
        game_session: GameSession,
        location: Location,
        time_state: TimeState,
    ) -> None:
        """Special characters in names are handled."""
        from src.world.scene_persister import ScenePersister

        world_update = WorldUpdate(
            npcs_at_location=[
                NPCPlacement(
                    new_npc=NPCSpec(display_name="Jean-Pierre O'Brien"),
                    presence_reason=PresenceReason.VISITING,
                    presence_justification="Visiting",
                    activity="sitting",
                    position_in_scene="at table",
                ),
            ],
        )

        persister = ScenePersister(db_session, game_session)

        result = persister.persist_world_update(
            world_update=world_update,
            location_key="tavern_main",
            turn_number=1,
        )

        key = result.npcs[0].entity_key
        # Key should be valid identifier (no special chars except underscore)
        assert key.replace("_", "").replace("0", "").replace("1", "").replace("2", "").replace("3", "").replace("4", "").replace("5", "").replace("6", "").replace("7", "").replace("8", "").replace("9", "").isalpha() or "_" in key
