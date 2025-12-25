"""Integration tests for GM pipeline with storage observation tracking.

These tests verify the end-to-end behavior of:
- First-time vs revisit context generation
- Observation recording when items are created in storage
- Context ordering (conversation-first)
"""

import pytest
from sqlalchemy.orm import Session

from src.database.models.enums import EntityType, StorageLocationType
from src.database.models.items import Item, StorageLocation
from src.database.models.session import GameSession
from src.database.models.world import StorageObservation
from src.gm.context_builder import GMContextBuilder
from src.managers.storage_observation_manager import StorageObservationManager
from tests.factories import (
    create_entity,
    create_location,
    create_storage_location,
)


class TestStorageContextGeneration:
    """Tests for storage context with [FIRST TIME] and [REVISIT] tags."""

    def test_unobserved_storage_shows_first_time(
        self, db_session: Session, game_session: GameSession
    ):
        """An unobserved storage should show [FIRST TIME] tag in context."""
        player = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.PLAYER,
            entity_key="player_001",
            display_name="Finn",
        )
        location = create_location(
            db_session,
            game_session,
            location_key="bedroom",
            display_name="Bedroom",
        )
        storage = create_storage_location(
            db_session,
            game_session,
            location_key="clothes_chest",
            location_type=StorageLocationType.PLACE,
            world_location_id=location.id,
        )

        builder = GMContextBuilder(db_session, game_session)
        context = builder.build(
            player_id=player.id,
            location_key=location.location_key,
            player_input="I look in the chest",
            turn_number=1,
        )

        assert "[FIRST TIME]" in context
        assert "clothes_chest" in context
        assert "invent" in context.lower() or "first time" in context.lower()

    def test_observed_storage_shows_revisit(
        self, db_session: Session, game_session: GameSession
    ):
        """An already-observed storage should show [REVISIT] tag in context."""
        player = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.PLAYER,
            entity_key="player_001",
            display_name="Finn",
        )
        location = create_location(
            db_session,
            game_session,
            location_key="bedroom",
            display_name="Bedroom",
        )
        storage = create_storage_location(
            db_session,
            game_session,
            location_key="clothes_chest",
            location_type=StorageLocationType.PLACE,
            world_location_id=location.id,
        )

        # Record a previous observation
        obs_manager = StorageObservationManager(db_session, game_session)
        obs_manager.record_observation(
            observer_id=player.id,
            storage_location_id=storage.id,
            contents=["shirt_001", "pants_001"],
            turn=1,
            game_day=1,
            game_time="08:00",
        )

        builder = GMContextBuilder(db_session, game_session)
        context = builder.build(
            player_id=player.id,
            location_key=location.location_key,
            player_input="What else is in the chest?",
            turn_number=5,
        )

        assert "[REVISIT]" in context
        assert "clothes_chest" in context
        # Should mention established contents
        assert "shirt_001" in context or "pants_001" in context


class TestContextOrdering:
    """Tests for conversation-first context ordering."""

    def test_recent_conversation_comes_first(
        self, db_session: Session, game_session: GameSession
    ):
        """RECENT CONVERSATION section should appear before CURRENT SCENE."""
        player = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.PLAYER,
            entity_key="player_001",
            display_name="Finn",
        )
        location = create_location(
            db_session,
            game_session,
            location_key="tavern",
            display_name="The Rusty Tankard",
        )

        builder = GMContextBuilder(db_session, game_session)
        context = builder.build(
            player_id=player.id,
            location_key=location.location_key,
            player_input="Hello",
            turn_number=1,
        )

        # Check that RECENT CONVERSATION comes before CURRENT SCENE
        conv_pos = context.find("## RECENT CONVERSATION")
        scene_pos = context.find("## CURRENT SCENE")

        assert conv_pos != -1, "RECENT CONVERSATION section not found"
        assert scene_pos != -1, "CURRENT SCENE section not found"
        assert conv_pos < scene_pos, "RECENT CONVERSATION should come before CURRENT SCENE"

    def test_system_notes_come_last(
        self, db_session: Session, game_session: GameSession
    ):
        """SYSTEM NOTES section should come after PLAYER STATE."""
        player = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.PLAYER,
            entity_key="player_001",
            display_name="Finn",
        )
        location = create_location(
            db_session,
            game_session,
            location_key="tavern",
            display_name="The Rusty Tankard",
        )

        builder = GMContextBuilder(db_session, game_session)
        context = builder.build(
            player_id=player.id,
            location_key=location.location_key,
            player_input="Hello",
            turn_number=1,
        )

        # Check ordering
        player_state_pos = context.find("## PLAYER STATE")
        system_notes_pos = context.find("## SYSTEM NOTES")
        player_input_pos = context.find("**PLAYER INPUT**")

        assert system_notes_pos > player_state_pos, "SYSTEM NOTES should come after PLAYER STATE"
        assert player_input_pos > system_notes_pos, "PLAYER INPUT should come after SYSTEM NOTES"


class TestStorageContainerSection:
    """Tests for the Storage Containers section in scene context."""

    def test_storage_section_included_in_scene(
        self, db_session: Session, game_session: GameSession
    ):
        """Storage containers should be listed in the scene context."""
        player = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.PLAYER,
            entity_key="player_001",
            display_name="Finn",
        )
        location = create_location(
            db_session,
            game_session,
            location_key="bedroom",
            display_name="Bedroom",
        )
        chest = create_storage_location(
            db_session,
            game_session,
            location_key="clothes_chest",
            location_type=StorageLocationType.PLACE,
            world_location_id=location.id,
        )
        wardrobe = create_storage_location(
            db_session,
            game_session,
            location_key="wardrobe",
            location_type=StorageLocationType.PLACE,
            world_location_id=location.id,
        )

        builder = GMContextBuilder(db_session, game_session)
        context = builder.build(
            player_id=player.id,
            location_key=location.location_key,
            player_input="I look around",
            turn_number=1,
        )

        assert "### Storage Containers" in context
        assert "clothes_chest" in context
        assert "wardrobe" in context

    def test_empty_location_shows_no_storage_containers(
        self, db_session: Session, game_session: GameSession
    ):
        """A location with no storage shows appropriate message."""
        player = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.PLAYER,
            entity_key="player_001",
            display_name="Finn",
        )
        location = create_location(
            db_session,
            game_session,
            location_key="empty_room",
            display_name="Empty Room",
        )

        builder = GMContextBuilder(db_session, game_session)
        context = builder.build(
            player_id=player.id,
            location_key=location.location_key,
            player_input="I look around",
            turn_number=1,
        )

        # Should still have the section but indicate no storages
        assert "### Storage Containers" in context
        # The content after the section should indicate none
        storage_pos = context.find("### Storage Containers")
        section_end = context.find("---", storage_pos)
        section_content = context[storage_pos:section_end]
        assert "None" in section_content or len(section_content.strip().split("\n")) <= 2


class TestObservationRecordingIntegration:
    """Tests for observation recording after item creation."""

    def test_observation_recorded_after_item_creation(
        self, db_session: Session, game_session: GameSession
    ):
        """When items are created in storage, observation should be recorded."""
        player = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.PLAYER,
            entity_key="player_001",
            display_name="Finn",
        )
        location = create_location(
            db_session,
            game_session,
            location_key="bedroom",
            display_name="Bedroom",
        )
        storage = create_storage_location(
            db_session,
            game_session,
            location_key="clothes_chest",
            location_type=StorageLocationType.PLACE,
            world_location_id=location.id,
        )

        # Verify no observation exists yet
        obs_manager = StorageObservationManager(db_session, game_session)
        assert not obs_manager.has_observed(player.id, storage.id)

        # Simulate what gm_node does when recording observations
        # Create an item in the storage
        item = Item(
            session_id=game_session.id,
            item_key="shirt_001",
            display_name="Linen Shirt",
            storage_location_id=storage.id,
        )
        db_session.add(item)
        db_session.flush()

        # Record the observation (as gm_node would do)
        items = db_session.query(Item).filter(
            Item.session_id == game_session.id,
            Item.storage_location_id == storage.id,
        ).all()
        contents = [i.item_key for i in items]

        obs_manager.record_observation(
            observer_id=player.id,
            storage_location_id=storage.id,
            contents=contents,
            turn=1,
            game_day=1,
            game_time="08:00",
        )

        # Verify observation was recorded
        assert obs_manager.has_observed(player.id, storage.id)
        observation = obs_manager.get_observation(player.id, storage.id)
        assert observation is not None
        assert "shirt_001" in observation.contents_snapshot


class TestGMPromptStructure:
    """Tests for GM prompt structure improvements."""

    def test_system_prompt_includes_intent_analysis(
        self, db_session: Session, game_session: GameSession
    ):
        """GM system prompt should include INTENT ANALYSIS section."""
        from src.gm.prompts import GM_SYSTEM_PROMPT

        assert "## INTENT ANALYSIS" in GM_SYSTEM_PROMPT
        assert "QUESTION" in GM_SYSTEM_PROMPT
        assert "ACTION" in GM_SYSTEM_PROMPT
        assert "DIALOGUE" in GM_SYSTEM_PROMPT

    def test_system_prompt_includes_first_time_revisit(
        self, db_session: Session, game_session: GameSession
    ):
        """GM system prompt should include FIRST-TIME vs REVISIT section."""
        from src.gm.prompts import GM_SYSTEM_PROMPT

        assert "FIRST-TIME vs REVISIT" in GM_SYSTEM_PROMPT or "[FIRST TIME]" in GM_SYSTEM_PROMPT
        assert "[REVISIT]" in GM_SYSTEM_PROMPT

    def test_system_prompt_tool_rules(
        self, db_session: Session, game_session: GameSession
    ):
        """GM system prompt should have clear tool usage rules."""
        from src.gm.prompts import GM_SYSTEM_PROMPT

        # Should mention not creating entities for questions
        assert "create_entity" in GM_SYSTEM_PROMPT.lower()
        # Should mention grounding rules
        assert "## GROUNDING" in GM_SYSTEM_PROMPT or "grounding" in GM_SYSTEM_PROMPT.lower()
