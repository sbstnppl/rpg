"""Tests for Entity and extension models."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.database.models.entities import (
    Entity,
    EntityAttribute,
    EntitySkill,
    MonsterExtension,
    NPCExtension,
)
from src.database.models.enums import EntityType
from src.database.models.session import GameSession
from tests.factories import (
    create_entity,
    create_entity_attribute,
    create_entity_skill,
    create_game_session,
    create_monster_extension,
    create_npc_extension,
)


class TestEntity:
    """Tests for Entity model."""

    def test_create_entity_required_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify Entity creation with required fields."""
        entity = Entity(
            session_id=game_session.id,
            entity_key="test_npc",
            display_name="Test NPC",
            entity_type=EntityType.NPC,
        )
        db_session.add(entity)
        db_session.flush()

        assert entity.id is not None
        assert entity.session_id == game_session.id
        assert entity.entity_key == "test_npc"
        assert entity.display_name == "Test NPC"
        assert entity.entity_type == EntityType.NPC

    def test_entity_default_values(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify Entity default values."""
        entity = create_entity(db_session, game_session)

        assert entity.is_alive is True
        assert entity.is_active is True
        assert entity.appearance is None
        assert entity.background is None
        assert entity.personality_notes is None
        assert entity.first_appeared_turn is None

    def test_entity_unique_constraint_session_key(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify unique constraint on session_id + entity_key."""
        create_entity(db_session, game_session, entity_key="duplicate_key")

        with pytest.raises(IntegrityError):
            create_entity(db_session, game_session, entity_key="duplicate_key")

    def test_entity_same_key_different_sessions(self, db_session: Session):
        """Verify same entity_key allowed in different sessions."""
        session1 = create_game_session(db_session)
        session2 = create_game_session(db_session)

        entity1 = create_entity(db_session, session1, entity_key="hero")
        entity2 = create_entity(db_session, session2, entity_key="hero")

        assert entity1.id != entity2.id
        assert entity1.entity_key == entity2.entity_key

    def test_entity_type_enum_storage(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify EntityType enum is stored and retrieved correctly."""
        for entity_type in EntityType:
            entity = create_entity(
                db_session,
                game_session,
                entity_type=entity_type,
            )
            db_session.refresh(entity)
            assert entity.entity_type == entity_type

    def test_entity_appearance_json(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify appearance JSON field."""
        appearance = {
            "height": "tall",
            "build": "muscular",
            "hair": "brown",
            "eyes": "blue",
            "distinguishing_features": ["scar on cheek"],
        }
        entity = create_entity(db_session, game_session, appearance=appearance)

        db_session.refresh(entity)

        assert entity.appearance == appearance
        assert entity.appearance["hair"] == "brown"

    def test_entity_text_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify text fields (background, personality_notes)."""
        entity = create_entity(
            db_session,
            game_session,
            background="A mysterious stranger from the north.",
            personality_notes="Quiet and observant. Trusts few people.",
        )

        db_session.refresh(entity)

        assert "mysterious stranger" in entity.background
        assert "Quiet and observant" in entity.personality_notes

    def test_entity_session_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify entity has back reference to session."""
        entity = create_entity(db_session, game_session)

        assert entity.session is not None
        assert entity.session.id == game_session.id

    def test_entity_attributes_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify entity has attributes relationship."""
        entity = create_entity(db_session, game_session)
        attr = create_entity_attribute(db_session, entity, attribute_key="strength", value=15)

        db_session.refresh(entity)

        assert len(entity.attributes) == 1
        assert entity.attributes[0].attribute_key == "strength"

    def test_entity_skills_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify entity has skills relationship."""
        entity = create_entity(db_session, game_session)
        skill = create_entity_skill(db_session, entity, skill_key="swordfighting")

        db_session.refresh(entity)

        assert len(entity.skills) == 1
        assert entity.skills[0].skill_key == "swordfighting"

    def test_entity_cascade_delete(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify entity deletion cascades to attributes and skills."""
        entity = create_entity(db_session, game_session)
        attr = create_entity_attribute(db_session, entity)
        skill = create_entity_skill(db_session, entity)
        attr_id = attr.id
        skill_id = skill.id

        db_session.delete(entity)
        db_session.flush()

        assert db_session.get(EntityAttribute, attr_id) is None
        assert db_session.get(EntitySkill, skill_id) is None

    def test_entity_repr(self, db_session: Session, game_session: GameSession):
        """Verify string representation."""
        entity = create_entity(
            db_session,
            game_session,
            entity_key="hero",
            entity_type=EntityType.PLAYER,
        )

        repr_str = repr(entity)
        assert "Entity" in repr_str
        assert "hero" in repr_str
        assert "player" in repr_str

    def test_entity_session_scoping(self, db_session: Session):
        """Verify entities are properly scoped to sessions."""
        session1 = create_game_session(db_session)
        session2 = create_game_session(db_session)

        entity1 = create_entity(db_session, session1)
        entity2 = create_entity(db_session, session2)

        # Query for session1 entities only
        result = (
            db_session.query(Entity)
            .filter(Entity.session_id == session1.id)
            .all()
        )

        assert len(result) == 1
        assert result[0].id == entity1.id


class TestEntityAttribute:
    """Tests for EntityAttribute model."""

    def test_create_attribute_required_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify EntityAttribute creation."""
        entity = create_entity(db_session, game_session)
        attr = EntityAttribute(
            entity_id=entity.id,
            attribute_key="strength",
            value=15,
        )
        db_session.add(attr)
        db_session.flush()

        assert attr.id is not None
        assert attr.attribute_key == "strength"
        assert attr.value == 15

    def test_attribute_unique_per_entity(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify unique constraint on entity_id + attribute_key."""
        entity = create_entity(db_session, game_session)
        create_entity_attribute(db_session, entity, attribute_key="strength")

        with pytest.raises(IntegrityError):
            create_entity_attribute(db_session, entity, attribute_key="strength")

    def test_attribute_same_key_different_entities(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify same attribute_key allowed for different entities."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)

        attr1 = create_entity_attribute(db_session, entity1, attribute_key="strength", value=10)
        attr2 = create_entity_attribute(db_session, entity2, attribute_key="strength", value=18)

        assert attr1.id != attr2.id
        assert attr1.value == 10
        assert attr2.value == 18

    def test_attribute_temporary_modifier_default(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify temporary_modifier defaults to 0."""
        entity = create_entity(db_session, game_session)
        attr = create_entity_attribute(db_session, entity)

        assert attr.temporary_modifier == 0

    def test_attribute_max_value_optional(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify max_value is optional."""
        entity = create_entity(db_session, game_session)
        attr = create_entity_attribute(db_session, entity, max_value=20)

        db_session.refresh(attr)
        assert attr.max_value == 20

    def test_attribute_entity_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify attribute has back reference to entity."""
        entity = create_entity(db_session, game_session)
        attr = create_entity_attribute(db_session, entity)

        assert attr.entity is not None
        assert attr.entity.id == entity.id

    def test_attribute_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        entity = create_entity(db_session, game_session)
        attr = create_entity_attribute(
            db_session, entity, attribute_key="charisma", value=18
        )

        repr_str = repr(attr)
        assert "charisma" in repr_str
        assert "18" in repr_str


class TestEntitySkill:
    """Tests for EntitySkill model."""

    def test_create_skill_required_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify EntitySkill creation."""
        entity = create_entity(db_session, game_session)
        skill = EntitySkill(
            entity_id=entity.id,
            skill_key="persuasion",
        )
        db_session.add(skill)
        db_session.flush()

        assert skill.id is not None
        assert skill.skill_key == "persuasion"

    def test_skill_unique_per_entity(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify unique constraint on entity_id + skill_key."""
        entity = create_entity(db_session, game_session)
        create_entity_skill(db_session, entity, skill_key="lockpicking")

        with pytest.raises(IntegrityError):
            create_entity_skill(db_session, entity, skill_key="lockpicking")

    def test_skill_proficiency_default(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify proficiency_level defaults to 1."""
        entity = create_entity(db_session, game_session)
        skill = create_entity_skill(db_session, entity)

        assert skill.proficiency_level == 1

    def test_skill_experience_tracking(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify experience_points field."""
        entity = create_entity(db_session, game_session)
        skill = create_entity_skill(db_session, entity, experience_points=150)

        db_session.refresh(skill)
        assert skill.experience_points == 150

    def test_skill_entity_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify skill has back reference to entity."""
        entity = create_entity(db_session, game_session)
        skill = create_entity_skill(db_session, entity)

        assert skill.entity is not None
        assert skill.entity.id == entity.id

    def test_skill_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        entity = create_entity(db_session, game_session)
        skill = create_entity_skill(
            db_session, entity, skill_key="swordfighting", proficiency_level=5
        )

        repr_str = repr(skill)
        assert "swordfighting" in repr_str
        assert "5" in repr_str


class TestNPCExtension:
    """Tests for NPCExtension model."""

    def test_npc_extension_one_to_one(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify NPCExtension has unique entity_id constraint."""
        entity = create_entity(db_session, game_session, entity_type=EntityType.NPC)
        create_npc_extension(db_session, entity)

        with pytest.raises(IntegrityError):
            create_npc_extension(db_session, entity)

    def test_npc_extension_work_life_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify work/life fields."""
        entity = create_entity(db_session, game_session, entity_type=EntityType.NPC)
        ext = create_npc_extension(
            db_session,
            entity,
            job="Blacksmith",
            workplace="The Forge",
            home_location="Artisan Quarter",
            hobbies=["fishing", "whittling"],
        )

        db_session.refresh(ext)

        assert ext.job == "Blacksmith"
        assert ext.workplace == "The Forge"
        assert ext.home_location == "Artisan Quarter"
        assert ext.hobbies == ["fishing", "whittling"]

    def test_npc_extension_current_state(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify current state fields."""
        entity = create_entity(db_session, game_session, entity_type=EntityType.NPC)
        ext = create_npc_extension(
            db_session,
            entity,
            current_activity="sweeping the floor",
            current_location="tavern",
            current_mood="content",
        )

        db_session.refresh(ext)

        assert ext.current_activity == "sweeping the floor"
        assert ext.current_location == "tavern"
        assert ext.current_mood == "content"

    def test_npc_extension_personality_traits_json(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify personality_traits JSON field."""
        entity = create_entity(db_session, game_session, entity_type=EntityType.NPC)
        traits = {
            "suspicious": 0.7,
            "generous": 0.3,
            "shy": 0.5,
        }
        ext = create_npc_extension(db_session, entity, personality_traits=traits)

        db_session.refresh(ext)

        assert ext.personality_traits == traits
        assert ext.personality_traits["suspicious"] == 0.7

    def test_npc_extension_entity_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify NPCExtension has back reference to entity."""
        entity = create_entity(db_session, game_session, entity_type=EntityType.NPC)
        ext = create_npc_extension(db_session, entity)

        assert ext.entity is not None
        assert ext.entity.id == entity.id

    def test_entity_npc_extension_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify Entity has npc_extension relationship."""
        entity = create_entity(db_session, game_session, entity_type=EntityType.NPC)
        ext = create_npc_extension(db_session, entity)

        db_session.refresh(entity)

        assert entity.npc_extension is not None
        assert entity.npc_extension.id == ext.id

    def test_npc_extension_cascade_delete(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify NPCExtension is deleted when entity is deleted."""
        entity = create_entity(db_session, game_session, entity_type=EntityType.NPC)
        ext = create_npc_extension(db_session, entity)
        ext_id = ext.id

        db_session.delete(entity)
        db_session.flush()

        assert db_session.get(NPCExtension, ext_id) is None

    def test_npc_extension_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        entity = create_entity(db_session, game_session, entity_type=EntityType.NPC)
        ext = create_npc_extension(db_session, entity)

        repr_str = repr(ext)
        assert "NPCExtension" in repr_str
        assert str(entity.id) in repr_str


class TestMonsterExtension:
    """Tests for MonsterExtension model."""

    def test_monster_extension_one_to_one(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify MonsterExtension has unique entity_id constraint."""
        entity = create_entity(db_session, game_session, entity_type=EntityType.MONSTER)
        create_monster_extension(db_session, entity)

        with pytest.raises(IntegrityError):
            create_monster_extension(db_session, entity)

    def test_monster_combat_stats(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify combat stat fields."""
        entity = create_entity(db_session, game_session, entity_type=EntityType.MONSTER)
        ext = create_monster_extension(
            db_session,
            entity,
            hit_points=45,
            max_hit_points=50,
            armor_class=15,
            challenge_rating=3,
        )

        db_session.refresh(ext)

        assert ext.hit_points == 45
        assert ext.max_hit_points == 50
        assert ext.armor_class == 15
        assert ext.challenge_rating == 3

    def test_monster_hostility_default(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify is_hostile defaults to True."""
        entity = create_entity(db_session, game_session, entity_type=EntityType.MONSTER)
        ext = create_monster_extension(db_session, entity)

        assert ext.is_hostile is True

    def test_monster_non_hostile(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify monster can be non-hostile."""
        entity = create_entity(db_session, game_session, entity_type=EntityType.ANIMAL)
        ext = create_monster_extension(db_session, entity, is_hostile=False)

        db_session.refresh(ext)
        assert ext.is_hostile is False

    def test_monster_loot_table_json(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify loot_table JSON field."""
        entity = create_entity(db_session, game_session, entity_type=EntityType.MONSTER)
        loot = [
            {"item": "gold_coins", "chance": 0.8, "amount": "2d10"},
            {"item": "goblin_ear", "chance": 0.5, "amount": "1"},
        ]
        ext = create_monster_extension(db_session, entity, loot_table=loot)

        db_session.refresh(ext)

        assert ext.loot_table == loot
        assert len(ext.loot_table) == 2

    def test_monster_behavior_pattern(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify behavior_pattern text field."""
        entity = create_entity(db_session, game_session, entity_type=EntityType.MONSTER)
        behavior = "Attacks weakest target. Flees below 20% HP."
        ext = create_monster_extension(db_session, entity, behavior_pattern=behavior)

        db_session.refresh(ext)
        assert ext.behavior_pattern == behavior

    def test_monster_extension_entity_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify MonsterExtension has back reference to entity."""
        entity = create_entity(db_session, game_session, entity_type=EntityType.MONSTER)
        ext = create_monster_extension(db_session, entity)

        assert ext.entity is not None
        assert ext.entity.id == entity.id

    def test_entity_monster_extension_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify Entity has monster_extension relationship."""
        entity = create_entity(db_session, game_session, entity_type=EntityType.MONSTER)
        ext = create_monster_extension(db_session, entity)

        db_session.refresh(entity)

        assert entity.monster_extension is not None
        assert entity.monster_extension.id == ext.id

    def test_monster_extension_cascade_delete(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify MonsterExtension is deleted when entity is deleted."""
        entity = create_entity(db_session, game_session, entity_type=EntityType.MONSTER)
        ext = create_monster_extension(db_session, entity)
        ext_id = ext.id

        db_session.delete(entity)
        db_session.flush()

        assert db_session.get(MonsterExtension, ext_id) is None

    def test_monster_extension_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        entity = create_entity(db_session, game_session, entity_type=EntityType.MONSTER)
        ext = create_monster_extension(db_session, entity, hit_points=30, max_hit_points=50)

        repr_str = repr(ext)
        assert "MonsterExtension" in repr_str
        assert "30" in repr_str
        assert "50" in repr_str
