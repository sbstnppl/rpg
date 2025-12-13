"""Tests for EntityManager class."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.enums import EntityType
from src.database.models.session import GameSession
from src.database.models.entities import Entity, EntityAttribute, EntitySkill
from src.managers.entity_manager import EntityManager
from tests.factories import (
    create_entity,
    create_entity_attribute,
    create_entity_skill,
    create_npc_extension,
)


class TestEntityManagerBasics:
    """Tests for EntityManager basic operations."""

    def test_get_entity_returns_none_when_missing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_entity returns None when entity doesn't exist."""
        manager = EntityManager(db_session, game_session)

        result = manager.get_entity("nonexistent")

        assert result is None

    def test_get_entity_returns_existing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_entity returns existing entity by key."""
        entity = create_entity(
            db_session, game_session, entity_key="hero", display_name="The Hero"
        )
        manager = EntityManager(db_session, game_session)

        result = manager.get_entity("hero")

        assert result is not None
        assert result.id == entity.id
        assert result.display_name == "The Hero"

    def test_get_entity_by_id_returns_none_when_missing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_entity_by_id returns None for invalid ID."""
        manager = EntityManager(db_session, game_session)

        result = manager.get_entity_by_id(999999)

        assert result is None

    def test_get_entity_by_id_returns_existing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_entity_by_id returns entity by ID."""
        entity = create_entity(db_session, game_session)
        manager = EntityManager(db_session, game_session)

        result = manager.get_entity_by_id(entity.id)

        assert result is not None
        assert result.id == entity.id

    def test_get_entity_by_display_name_returns_none_when_missing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_entity_by_display_name returns None when not found."""
        manager = EntityManager(db_session, game_session)

        result = manager.get_entity_by_display_name("Unknown Person")

        assert result is None

    def test_get_entity_by_display_name_returns_existing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_entity_by_display_name finds entity by display name."""
        entity = create_entity(
            db_session, game_session, entity_key="bartender_bob", display_name="Bob"
        )
        manager = EntityManager(db_session, game_session)

        result = manager.get_entity_by_display_name("Bob")

        assert result is not None
        assert result.id == entity.id

    def test_get_entity_by_display_name_case_insensitive(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_entity_by_display_name is case-insensitive."""
        entity = create_entity(
            db_session, game_session, entity_key="queen_alice", display_name="Queen Alice"
        )
        manager = EntityManager(db_session, game_session)

        # Try different cases
        assert manager.get_entity_by_display_name("queen alice") is not None
        assert manager.get_entity_by_display_name("QUEEN ALICE") is not None
        assert manager.get_entity_by_display_name("Queen Alice") is not None

    def test_create_entity_basic(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify create_entity creates new entity."""
        manager = EntityManager(db_session, game_session)

        result = manager.create_entity(
            entity_key="knight",
            display_name="Sir Lancelot",
            entity_type=EntityType.NPC,
        )

        assert result is not None
        assert result.entity_key == "knight"
        assert result.display_name == "Sir Lancelot"
        assert result.entity_type == EntityType.NPC
        assert result.session_id == game_session.id
        assert result.is_alive is True
        assert result.is_active is True

    def test_create_entity_with_appearance(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify create_entity can set appearance JSON."""
        manager = EntityManager(db_session, game_session)
        appearance = {"height": "tall", "hair": "blonde", "eyes": "blue"}

        result = manager.create_entity(
            entity_key="princess",
            display_name="Princess Aurora",
            entity_type=EntityType.NPC,
            appearance=appearance,
        )

        assert result.appearance == appearance


class TestEntityManagerQueries:
    """Tests for entity query operations."""

    def test_get_player_returns_player_type(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_player returns entity with PLAYER type."""
        create_entity(db_session, game_session, entity_type=EntityType.NPC)
        player = create_entity(
            db_session, game_session,
            entity_key="player",
            entity_type=EntityType.PLAYER
        )
        manager = EntityManager(db_session, game_session)

        result = manager.get_player()

        assert result is not None
        assert result.id == player.id
        assert result.entity_type == EntityType.PLAYER

    def test_get_player_returns_none_when_no_player(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_player returns None when no player exists."""
        create_entity(db_session, game_session, entity_type=EntityType.NPC)
        manager = EntityManager(db_session, game_session)

        result = manager.get_player()

        assert result is None

    def test_get_all_npcs_filters_by_type(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_all_npcs returns only NPCs."""
        npc1 = create_entity(
            db_session, game_session,
            entity_key="npc1",
            entity_type=EntityType.NPC
        )
        npc2 = create_entity(
            db_session, game_session,
            entity_key="npc2",
            entity_type=EntityType.NPC
        )
        create_entity(
            db_session, game_session,
            entity_key="player",
            entity_type=EntityType.PLAYER
        )
        create_entity(
            db_session, game_session,
            entity_key="monster",
            entity_type=EntityType.MONSTER
        )
        manager = EntityManager(db_session, game_session)

        result = manager.get_all_npcs()

        assert len(result) == 2
        assert all(e.entity_type == EntityType.NPC for e in result)

    def test_get_all_npcs_excludes_dead_when_alive_only(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_all_npcs excludes dead NPCs by default."""
        alive_npc = create_entity(
            db_session, game_session,
            entity_key="alive",
            entity_type=EntityType.NPC,
            is_alive=True
        )
        create_entity(
            db_session, game_session,
            entity_key="dead",
            entity_type=EntityType.NPC,
            is_alive=False
        )
        manager = EntityManager(db_session, game_session)

        result = manager.get_all_npcs(alive_only=True)

        assert len(result) == 1
        assert result[0].id == alive_npc.id

    def test_get_all_npcs_includes_dead_when_requested(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_all_npcs includes dead NPCs when alive_only=False."""
        create_entity(
            db_session, game_session,
            entity_key="alive",
            entity_type=EntityType.NPC,
            is_alive=True
        )
        create_entity(
            db_session, game_session,
            entity_key="dead",
            entity_type=EntityType.NPC,
            is_alive=False
        )
        manager = EntityManager(db_session, game_session)

        result = manager.get_all_npcs(alive_only=False)

        assert len(result) == 2

    def test_get_entities_at_location(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_entities_at_location returns entities at location."""
        entity1 = create_entity(db_session, game_session, entity_key="npc1")
        create_npc_extension(db_session, entity1, current_location="tavern")

        entity2 = create_entity(db_session, game_session, entity_key="npc2")
        create_npc_extension(db_session, entity2, current_location="tavern")

        entity3 = create_entity(db_session, game_session, entity_key="npc3")
        create_npc_extension(db_session, entity3, current_location="market")

        manager = EntityManager(db_session, game_session)

        result = manager.get_entities_at_location("tavern")

        assert len(result) == 2
        keys = [e.entity_key for e in result]
        assert "npc1" in keys
        assert "npc2" in keys


class TestEntityManagerLocationUpdate:
    """Tests for updating entity locations."""

    def test_update_location_updates_npc_extension(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify update_location updates NPCExtension current_location."""
        entity = create_entity(db_session, game_session, entity_key="merchant")
        create_npc_extension(db_session, entity, current_location="market")
        manager = EntityManager(db_session, game_session)

        result = manager.update_location("merchant", "tavern")

        assert result.npc_extension.current_location == "tavern"

    def test_update_location_creates_extension_if_missing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify update_location creates NPCExtension if missing."""
        entity = create_entity(db_session, game_session, entity_key="wanderer")
        manager = EntityManager(db_session, game_session)

        result = manager.update_location("wanderer", "forest")

        assert result.npc_extension is not None
        assert result.npc_extension.current_location == "forest"

    def test_update_activity_updates_npc_extension(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify update_activity updates current_activity and mood."""
        entity = create_entity(db_session, game_session, entity_key="bard")
        create_npc_extension(db_session, entity)
        manager = EntityManager(db_session, game_session)

        result = manager.update_activity("bard", "playing lute", mood="cheerful")

        assert result.npc_extension.current_activity == "playing lute"
        assert result.npc_extension.current_mood == "cheerful"


class TestEntityManagerAttributes:
    """Tests for attribute management."""

    def test_get_attribute_returns_value_with_modifier(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_attribute returns value + temporary_modifier."""
        entity = create_entity(db_session, game_session)
        create_entity_attribute(
            db_session, entity,
            attribute_key="strength",
            value=15,
            temporary_modifier=3
        )
        manager = EntityManager(db_session, game_session)

        result = manager.get_attribute(entity.id, "strength")

        assert result == 18  # 15 + 3

    def test_get_attribute_returns_none_when_missing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_attribute returns None when attribute doesn't exist."""
        entity = create_entity(db_session, game_session)
        manager = EntityManager(db_session, game_session)

        result = manager.get_attribute(entity.id, "nonexistent")

        assert result is None

    def test_set_attribute_creates_when_missing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify set_attribute creates attribute if it doesn't exist."""
        entity = create_entity(db_session, game_session)
        manager = EntityManager(db_session, game_session)

        result = manager.set_attribute(entity.id, "charisma", 14)

        assert result.attribute_key == "charisma"
        assert result.value == 14
        assert result.entity_id == entity.id

    def test_set_attribute_updates_existing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify set_attribute updates existing attribute."""
        entity = create_entity(db_session, game_session)
        attr = create_entity_attribute(
            db_session, entity,
            attribute_key="intelligence",
            value=10
        )
        manager = EntityManager(db_session, game_session)

        result = manager.set_attribute(entity.id, "intelligence", 16)

        assert result.id == attr.id
        assert result.value == 16

    def test_set_attribute_with_max_value(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify set_attribute can set max_value."""
        entity = create_entity(db_session, game_session)
        manager = EntityManager(db_session, game_session)

        result = manager.set_attribute(entity.id, "health", 50, max_value=100)

        assert result.value == 50
        assert result.max_value == 100

    def test_modify_attribute_adds_delta(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify modify_attribute adds delta to current value."""
        entity = create_entity(db_session, game_session)
        create_entity_attribute(
            db_session, entity,
            attribute_key="mana",
            value=20
        )
        manager = EntityManager(db_session, game_session)

        result = manager.modify_attribute(entity.id, "mana", 10)

        assert result.value == 30

    def test_modify_attribute_creates_if_missing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify modify_attribute creates attribute with delta as value."""
        entity = create_entity(db_session, game_session)
        manager = EntityManager(db_session, game_session)

        result = manager.modify_attribute(entity.id, "luck", 5)

        assert result.value == 5

    def test_set_temporary_modifier(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify set_temporary_modifier updates modifier."""
        entity = create_entity(db_session, game_session)
        create_entity_attribute(
            db_session, entity,
            attribute_key="strength",
            value=15,
            temporary_modifier=0
        )
        manager = EntityManager(db_session, game_session)

        result = manager.set_temporary_modifier(entity.id, "strength", 5)

        assert result.temporary_modifier == 5


class TestEntityManagerSkills:
    """Tests for skill management."""

    def test_get_skill_returns_none_when_missing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_skill returns None when skill doesn't exist."""
        entity = create_entity(db_session, game_session)
        manager = EntityManager(db_session, game_session)

        result = manager.get_skill(entity.id, "swordfighting")

        assert result is None

    def test_get_skill_returns_existing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_skill returns existing skill."""
        entity = create_entity(db_session, game_session)
        skill = create_entity_skill(
            db_session, entity,
            skill_key="lockpicking",
            proficiency_level=3
        )
        manager = EntityManager(db_session, game_session)

        result = manager.get_skill(entity.id, "lockpicking")

        assert result is not None
        assert result.id == skill.id
        assert result.proficiency_level == 3

    def test_set_skill_creates_when_missing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify set_skill creates skill if it doesn't exist."""
        entity = create_entity(db_session, game_session)
        manager = EntityManager(db_session, game_session)

        result = manager.set_skill(entity.id, "persuasion", 5)

        assert result.skill_key == "persuasion"
        assert result.proficiency_level == 5

    def test_set_skill_updates_existing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify set_skill updates existing skill level."""
        entity = create_entity(db_session, game_session)
        skill = create_entity_skill(
            db_session, entity,
            skill_key="archery",
            proficiency_level=2
        )
        manager = EntityManager(db_session, game_session)

        result = manager.set_skill(entity.id, "archery", 4)

        assert result.id == skill.id
        assert result.proficiency_level == 4


class TestEntityManagerStatus:
    """Tests for entity status changes."""

    def test_mark_dead_sets_is_alive_false(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify mark_dead sets is_alive to False."""
        entity = create_entity(
            db_session, game_session,
            entity_key="villain",
            is_alive=True
        )
        manager = EntityManager(db_session, game_session)

        result = manager.mark_dead("villain")

        assert result.is_alive is False

    def test_mark_inactive_sets_is_active_false(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify mark_inactive sets is_active to False."""
        entity = create_entity(
            db_session, game_session,
            entity_key="traveler",
            is_active=True
        )
        manager = EntityManager(db_session, game_session)

        result = manager.mark_inactive("traveler")

        assert result.is_active is False

    def test_get_active_entities_filters_inactive(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_active_entities excludes inactive entities."""
        create_entity(
            db_session, game_session,
            entity_key="active",
            is_alive=True,
            is_active=True
        )
        create_entity(
            db_session, game_session,
            entity_key="inactive",
            is_alive=True,
            is_active=False
        )
        create_entity(
            db_session, game_session,
            entity_key="dead",
            is_alive=False,
            is_active=True
        )
        manager = EntityManager(db_session, game_session)

        result = manager.get_active_entities()

        assert len(result) == 1
        assert result[0].entity_key == "active"

    def test_get_active_entities_returns_all_types(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_active_entities returns all entity types."""
        create_entity(
            db_session, game_session,
            entity_key="player",
            entity_type=EntityType.PLAYER,
            is_alive=True,
            is_active=True
        )
        create_entity(
            db_session, game_session,
            entity_key="npc",
            entity_type=EntityType.NPC,
            is_alive=True,
            is_active=True
        )
        create_entity(
            db_session, game_session,
            entity_key="monster",
            entity_type=EntityType.MONSTER,
            is_alive=True,
            is_active=True
        )
        manager = EntityManager(db_session, game_session)

        result = manager.get_active_entities()

        assert len(result) == 3


class TestEntityManagerUpdateAttribute:
    """Tests for update_attribute method."""

    def test_update_attribute_creates_new(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify update_attribute creates attribute if missing."""
        entity = create_entity(db_session, game_session)
        manager = EntityManager(db_session, game_session)

        result = manager.update_attribute(entity.id, "strength", 16)

        assert result is not None
        assert result.attribute_key == "strength"
        assert result.value == 16
        assert result.entity_id == entity.id

    def test_update_attribute_updates_existing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify update_attribute updates existing attribute."""
        entity = create_entity(db_session, game_session)
        attr = create_entity_attribute(
            db_session, entity,
            attribute_key="strength",
            value=10
        )
        manager = EntityManager(db_session, game_session)

        result = manager.update_attribute(entity.id, "strength", 18)

        assert result.id == attr.id
        assert result.value == 18
