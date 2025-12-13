"""Tests for NPC Generator Service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.orm import Session

from src.agents.schemas.npc_generation import (
    NPCAppearance,
    NPCBackground,
    NPCGenerationResult,
    NPCInitialNeeds,
    NPCInventoryItem,
    NPCPreferences,
    NPCSkill,
)
from src.database.models.character_preferences import CharacterPreferences
from src.database.models.character_state import CharacterNeeds
from src.database.models.entities import Entity, EntitySkill, NPCExtension
from src.database.models.enums import EntityType, ItemType, SocialTendency, DriveLevel
from src.database.models.items import Item
from src.database.models.session import GameSession
from src.services.npc_generator import (
    NPCGeneratorService,
    infer_npc_initial_needs,
    OCCUPATION_SKILLS,
    OCCUPATION_INVENTORY,
)
from tests.factories import (
    create_entity,
    create_game_session,
    create_location,
    create_time_state,
)


class TestNPCGeneratorService:
    """Test NPC Generator Service methods."""

    def test_create_entity_with_appearance(
        self, db_session: Session, game_session: GameSession
    ):
        """Test entity creation with all appearance fields."""
        service = NPCGeneratorService(db_session, game_session)

        appearance = NPCAppearance(
            age=35,
            age_apparent="mid-thirties",
            gender="male",
            height="5'10\"",
            build="stocky",
            hair_color="brown",
            hair_style="short and messy",
            eye_color="green",
            skin_tone="fair",
            species="human",
            distinguishing_features="scar on left cheek",
            voice_description="deep and gravelly",
        )

        entity = service._create_entity_with_appearance(
            entity_key="test_npc",
            display_name="Test NPC",
            entity_type=EntityType.NPC,
            appearance=appearance,
            description="A stocky man with a scar",
        )

        assert entity.entity_key == "test_npc"
        assert entity.display_name == "Test NPC"
        assert entity.entity_type == EntityType.NPC
        assert entity.age == 35
        assert entity.age_apparent == "mid-thirties"
        assert entity.gender == "male"
        assert entity.height == "5'10\""
        assert entity.build == "stocky"
        assert entity.hair_color == "brown"
        assert entity.hair_style == "short and messy"
        assert entity.eye_color == "green"
        assert entity.skin_tone == "fair"
        assert entity.species == "human"
        assert entity.distinguishing_features == "scar on left cheek"
        assert entity.voice_description == "deep and gravelly"

    def test_create_npc_extension(
        self, db_session: Session, game_session: GameSession
    ):
        """Test NPCExtension creation with job and location."""
        service = NPCGeneratorService(db_session, game_session)

        entity = create_entity(
            db_session, game_session,
            entity_key="bartender_joe",
            display_name="Joe",
        )

        background = NPCBackground(
            backstory="Joe has worked at the tavern for 10 years.",
            occupation="bartender",
            occupation_years=10,
            personality_notes="Friendly but no-nonsense",
        )

        service._create_npc_extension(
            entity=entity,
            background=background,
            current_activity="Cleaning glasses",
            current_location="tavern",
            personality_traits=["friendly", "observant"],
        )

        db_session.flush()
        db_session.refresh(entity)

        assert entity.npc_extension is not None
        assert entity.npc_extension.job == "bartender"
        assert entity.npc_extension.current_activity == "Cleaning glasses"
        assert entity.npc_extension.current_location == "tavern"
        assert entity.npc_extension.current_mood == "neutral"
        assert entity.occupation == "bartender"
        assert entity.occupation_years == 10
        assert entity.background == "Joe has worked at the tavern for 10 years."
        assert entity.personality_notes == "Friendly but no-nonsense"

    def test_create_npc_skills(
        self, db_session: Session, game_session: GameSession
    ):
        """Test skill creation for NPC."""
        service = NPCGeneratorService(db_session, game_session)

        entity = create_entity(
            db_session, game_session,
            entity_key="skilled_npc",
        )

        skills = [
            NPCSkill(skill_key="swordfighting", proficiency_level=75),
            NPCSkill(skill_key="intimidation", proficiency_level=50),
            NPCSkill(skill_key="perception", proficiency_level=60),
        ]

        service._create_npc_skills(entity.id, skills)
        db_session.flush()

        entity_skills = (
            db_session.query(EntitySkill)
            .filter(EntitySkill.entity_id == entity.id)
            .all()
        )

        assert len(entity_skills) == 3
        skill_map = {s.skill_key: s.proficiency_level for s in entity_skills}
        assert skill_map["swordfighting"] == 75
        assert skill_map["intimidation"] == 50
        assert skill_map["perception"] == 60

    def test_create_npc_inventory(
        self, db_session: Session, game_session: GameSession
    ):
        """Test inventory creation for NPC."""
        service = NPCGeneratorService(db_session, game_session)

        entity = create_entity(
            db_session, game_session,
            entity_key="merchant_npc",
        )

        items = [
            NPCInventoryItem(
                item_key="coin_purse",
                display_name="Leather Coin Purse",
                item_type="container",
                description="A worn leather purse",
                is_equipped=True,
                body_slot="waist",
            ),
            NPCInventoryItem(
                item_key="merchant_clothes",
                display_name="Merchant's Clothes",
                item_type="clothing",
                body_slot="torso",
                body_layer=2,
                is_equipped=True,
            ),
            NPCInventoryItem(
                item_key="ledger",
                display_name="Account Ledger",
                item_type="misc",
                description="A leather-bound ledger",
            ),
        ]

        service._create_npc_inventory(entity, items)
        db_session.flush()

        inventory = (
            db_session.query(Item)
            .filter(Item.owner_id == entity.id)
            .all()
        )

        assert len(inventory) == 3

        # Items are prefixed with entity_key
        item_map = {i.item_key.replace(f"{entity.entity_key}_", ""): i for i in inventory}

        assert item_map["coin_purse"].display_name == "Leather Coin Purse"
        assert item_map["coin_purse"].item_type == ItemType.CONTAINER
        assert item_map["coin_purse"].body_slot == "waist"

        assert item_map["merchant_clothes"].body_slot == "torso"
        assert item_map["merchant_clothes"].body_layer == 2

        assert item_map["ledger"].item_type == ItemType.MISC

    def test_create_npc_preferences(
        self, db_session: Session, game_session: GameSession
    ):
        """Test preferences creation for NPC."""
        service = NPCGeneratorService(db_session, game_session)

        entity = create_entity(
            db_session, game_session,
            entity_key="preference_npc",
        )

        preferences = NPCPreferences(
            social_tendency="extrovert",
            preferred_group_size=5,
            drive_level="moderate",
            intimacy_style="emotional",
            alcohol_tolerance="high",
            favorite_foods=["roasted meat", "fresh bread"],
            disliked_foods=["fish"],
            is_social_butterfly=True,
        )

        service._create_npc_preferences(entity.id, preferences)
        db_session.flush()

        prefs = (
            db_session.query(CharacterPreferences)
            .filter(CharacterPreferences.entity_id == entity.id)
            .first()
        )

        assert prefs is not None
        assert prefs.social_tendency == SocialTendency.EXTROVERT
        assert prefs.preferred_group_size == 5
        assert prefs.drive_level == DriveLevel.MODERATE
        assert prefs.is_social_butterfly is True
        assert prefs.favorite_foods == ["roasted meat", "fresh bread"]
        assert prefs.disliked_foods == ["fish"]

    def test_create_npc_needs(
        self, db_session: Session, game_session: GameSession
    ):
        """Test needs creation for NPC."""
        service = NPCGeneratorService(db_session, game_session)

        entity = create_entity(
            db_session, game_session,
            entity_key="needs_npc",
        )

        initial_needs = NPCInitialNeeds(
            hunger=60,
            thirst=70,
            energy=50,
            hygiene=80,
            comfort=70,
            wellness=100,
            social_connection=65,
            morale=70,
            sense_of_purpose=60,
            intimacy=75,
        )

        service._create_npc_needs(entity.id, initial_needs)
        db_session.flush()

        needs = (
            db_session.query(CharacterNeeds)
            .filter(CharacterNeeds.entity_id == entity.id)
            .first()
        )

        assert needs is not None
        assert needs.hunger == 60
        assert needs.thirst == 70
        assert needs.energy == 50
        assert needs.hygiene == 80
        assert needs.comfort == 70
        assert needs.wellness == 100
        assert needs.social_connection == 65
        assert needs.morale == 70
        assert needs.sense_of_purpose == 60
        assert needs.intimacy == 75


class TestNPCInitialNeedsInference:
    """Test time-based and occupation-based needs inference."""

    def test_morning_needs(self):
        """Morning NPCs should have breakfast-appropriate hunger."""
        needs = infer_npc_initial_needs(
            occupation="farmer",
            game_time="07:00",
            game_day=1,
        )

        # Morning: lower hunger (needs breakfast), higher energy (just woke)
        assert needs["hunger"] <= 65  # Needs breakfast
        assert needs["energy"] >= 60  # Just woke up

    def test_midday_needs(self):
        """Midday NPCs should have lunch-appropriate hunger."""
        needs = infer_npc_initial_needs(
            occupation="merchant",
            game_time="12:30",
            game_day=1,
        )

        # Midday: lower hunger (needs lunch)
        assert needs["hunger"] <= 65

    def test_evening_needs(self):
        """Evening NPCs should have lower energy."""
        needs = infer_npc_initial_needs(
            occupation="guard",
            game_time="20:00",
            game_day=1,
        )

        # Evening: lower energy (tired after day)
        assert needs["energy"] <= 60

    def test_night_needs(self):
        """Night NPCs should be very tired."""
        needs = infer_npc_initial_needs(
            occupation="innkeeper",
            game_time="23:00",
            game_day=1,
        )

        # Night: very low energy
        assert needs["energy"] <= 45

    def test_occupation_affects_needs(self):
        """Occupation should influence starting needs."""
        # Innkeeper has access to food/drink
        innkeeper = infer_npc_initial_needs(
            occupation="innkeeper",
            game_time="14:00",
            game_day=1,
        )

        # Farmer does physical labor
        farmer = infer_npc_initial_needs(
            occupation="farmer",
            game_time="14:00",
            game_day=1,
        )

        # Scholar is more sedentary
        scholar = infer_npc_initial_needs(
            occupation="scholar",
            game_time="14:00",
            game_day=1,
        )

        # Innkeeper should have better food access
        assert innkeeper["hunger"] >= farmer["hunger"]

        # Farmer should have lower energy from labor
        assert farmer["energy"] <= scholar["energy"]


class TestOccupationTemplates:
    """Test occupation-based skill and inventory templates."""

    def test_occupation_skills_defined(self):
        """Common occupations should have skill templates."""
        assert "merchant" in OCCUPATION_SKILLS
        assert "guard" in OCCUPATION_SKILLS
        assert "innkeeper" in OCCUPATION_SKILLS
        assert "blacksmith" in OCCUPATION_SKILLS
        assert "farmer" in OCCUPATION_SKILLS

    def test_occupation_inventory_defined(self):
        """Common occupations should have inventory templates."""
        assert "merchant" in OCCUPATION_INVENTORY
        assert "guard" in OCCUPATION_INVENTORY
        assert "innkeeper" in OCCUPATION_INVENTORY

    def test_merchant_has_trade_skills(self):
        """Merchants should have trading-related skills."""
        skills = OCCUPATION_SKILLS.get("merchant", [])
        assert any("haggl" in s.lower() for s in skills)
        assert any("apprais" in s.lower() for s in skills) or any(
            "persuas" in s.lower() for s in skills
        )

    def test_guard_has_combat_skills(self):
        """Guards should have combat-related skills."""
        skills = OCCUPATION_SKILLS.get("guard", [])
        # Should have at least one combat skill
        combat_keywords = ["sword", "fight", "combat", "weapon", "intim"]
        assert any(
            any(kw in s.lower() for kw in combat_keywords)
            for s in skills
        )


class TestNPCGeneratorServiceIntegration:
    """Integration tests for full NPC generation."""

    @pytest.mark.asyncio
    async def test_generate_npc_creates_all_records(
        self, db_session: Session, game_session: GameSession
    ):
        """Test that generate_npc creates entity, skills, inventory, preferences, needs."""
        # Create time state for the session
        create_time_state(db_session, game_session, current_time="14:00")

        service = NPCGeneratorService(db_session, game_session)

        # Mock the LLM call
        mock_result = NPCGenerationResult(
            entity_key="test_merchant",
            appearance=NPCAppearance(
                age=45,
                gender="male",
                height="5'8\"",
                build="portly",
                hair_color="gray",
                species="human",
            ),
            background=NPCBackground(
                backstory="A merchant who traveled the trade routes for 20 years.",
                occupation="merchant",
                occupation_years=20,
                personality_notes="Shrewd but fair",
            ),
            skills=[
                NPCSkill(skill_key="haggling", proficiency_level=80),
                NPCSkill(skill_key="appraisal", proficiency_level=70),
            ],
            inventory=[
                NPCInventoryItem(
                    item_key="coin_purse",
                    display_name="Heavy Coin Purse",
                    item_type="container",
                ),
                NPCInventoryItem(
                    item_key="fine_clothes",
                    display_name="Fine Merchant Clothes",
                    item_type="clothing",
                    body_slot="torso",
                    is_equipped=True,
                ),
            ],
            preferences=NPCPreferences(
                social_tendency="extrovert",
                drive_level="low",
            ),
            initial_needs=NPCInitialNeeds(
                hunger=70,
                thirst=75,
                energy=65,
            ),
        )

        with patch.object(
            service, "_call_llm_for_generation", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = mock_result

            entity = await service.generate_npc(
                entity_key="test_merchant",
                display_name="Marcus the Merchant",
                entity_type=EntityType.NPC,
                description="A portly merchant",
                personality_traits=["shrewd", "fair"],
                current_activity="Examining wares",
                current_location="marketplace",
            )

        db_session.flush()

        # Verify entity
        assert entity.entity_key == "test_merchant"
        assert entity.display_name == "Marcus the Merchant"
        assert entity.age == 45
        assert entity.occupation == "merchant"

        # Verify NPC extension
        assert entity.npc_extension is not None
        assert entity.npc_extension.job == "merchant"
        assert entity.npc_extension.current_location == "marketplace"

        # Verify skills
        skills = (
            db_session.query(EntitySkill)
            .filter(EntitySkill.entity_id == entity.id)
            .all()
        )
        assert len(skills) == 2

        # Verify inventory
        items = (
            db_session.query(Item)
            .filter(Item.owner_id == entity.id)
            .all()
        )
        assert len(items) == 2

        # Verify preferences (now formula-generated, not LLM-generated)
        prefs = (
            db_session.query(CharacterPreferences)
            .filter(CharacterPreferences.entity_id == entity.id)
            .first()
        )
        assert prefs is not None
        # Preferences are now randomly generated by formula, so just check valid values
        assert prefs.social_tendency in (
            SocialTendency.INTROVERT, SocialTendency.AMBIVERT, SocialTendency.EXTROVERT
        )
        assert prefs.drive_level is not None

        # Verify needs
        needs = (
            db_session.query(CharacterNeeds)
            .filter(CharacterNeeds.entity_id == entity.id)
            .first()
        )
        assert needs is not None
        assert needs.hunger == 70

    @pytest.mark.asyncio
    async def test_generate_npc_fallback_on_error(
        self, db_session: Session, game_session: GameSession
    ):
        """Test that NPC generation falls back to minimal entity on LLM error."""
        create_time_state(db_session, game_session, current_time="14:00")

        service = NPCGeneratorService(db_session, game_session)

        with patch.object(
            service, "_call_llm_for_generation", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.side_effect = Exception("LLM error")

            entity = await service.generate_npc(
                entity_key="fallback_npc",
                display_name="Fallback NPC",
                entity_type=EntityType.NPC,
                description="A person",
                personality_traits=[],
                current_activity=None,
                current_location=None,
            )

        # Should still create minimal entity
        assert entity is not None
        assert entity.entity_key == "fallback_npc"
        assert entity.display_name == "Fallback NPC"

    @pytest.mark.asyncio
    async def test_existing_entity_not_regenerated(
        self, db_session: Session, game_session: GameSession
    ):
        """Test that existing entities are not regenerated."""
        # Create an existing entity
        existing = create_entity(
            db_session, game_session,
            entity_key="existing_npc",
            display_name="Existing NPC",
        )

        service = NPCGeneratorService(db_session, game_session)

        # Try to generate same entity
        result = await service.generate_npc(
            entity_key="existing_npc",
            display_name="Should Not Override",
            entity_type=EntityType.NPC,
            description="New description",
            personality_traits=[],
            current_activity=None,
            current_location=None,
        )

        # Should return existing entity unchanged
        assert result.id == existing.id
        assert result.display_name == "Existing NPC"
