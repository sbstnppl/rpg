"""Tests for the GMContextBuilder, focusing on familiarity and OOC detection."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.enums import EntityType
from src.database.models.session import GameSession
from src.gm.context_builder import GMContextBuilder
from tests.factories import (
    create_entity,
    create_fact,
    create_location,
)


class TestFamiliarityContext:
    """Tests for _get_familiarity_context method."""

    def test_unfamiliar_location_returns_unfamiliar_message(
        self, db_session: Session, game_session: GameSession
    ):
        """When player has no connection to location, should show unfamiliar."""
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
        result = builder._get_familiarity_context(player.id, location.location_key)

        assert "Unfamiliar with current location" in result
        assert "doesn't know details" in result

    def test_home_location_shows_familiar(
        self, db_session: Session, game_session: GameSession
    ):
        """When player lives_at location, should show as home."""
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
            location_key="brennan_farm",
            display_name="Brennan Farm",
        )
        create_fact(
            db_session,
            game_session,
            subject_type="entity",
            subject_key="player_001",
            predicate="lives_at",
            value="brennan_farm",
        )

        builder = GMContextBuilder(db_session, game_session)
        result = builder._get_familiarity_context(player.id, location.location_key)

        assert "This is Finn's home" in result
        assert "knows all routines" in result
        assert "Questions about familiar things = OOC" in result

    def test_home_sublocation_shows_familiar(
        self, db_session: Session, game_session: GameSession
    ):
        """When player is in sublocation of home, should still show familiar."""
        player = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.PLAYER,
            entity_key="player_001",
            display_name="Finn",
        )
        # Player lives at brennan_farm
        create_fact(
            db_session,
            game_session,
            subject_type="entity",
            subject_key="player_001",
            predicate="lives_at",
            value="brennan_farm",
        )
        # Currently in a sublocation
        sublocation = create_location(
            db_session,
            game_session,
            location_key="brennan_farm.bedroom",
            display_name="Finn's Bedroom",
        )

        builder = GMContextBuilder(db_session, game_session)
        result = builder._get_familiarity_context(player.id, sublocation.location_key)

        assert "This is Finn's home" in result

    @pytest.mark.skip(reason="Item-location relationship requires StorageLocation setup")
    def test_owned_items_at_location_shows_familiarity(
        self, db_session: Session, game_session: GameSession
    ):
        """When player owns items at location, should show them.

        Note: This test is skipped because items are associated with locations
        through StorageLocation, which requires more complex setup.
        """
        pass

    def test_location_facts_show_familiarity(
        self, db_session: Session, game_session: GameSession
    ):
        """When there are non-secret facts about location, should mention them."""
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
        # Add some facts about the tavern
        create_fact(
            db_session,
            game_session,
            subject_key="tavern",
            predicate="serves",
            value="ale",
        )
        create_fact(
            db_session,
            game_session,
            subject_key="tavern",
            predicate="owner",
            value="Barkeep Tom",
        )

        builder = GMContextBuilder(db_session, game_session)
        result = builder._get_familiarity_context(player.id, location.location_key)

        assert "2 known facts" in result


class TestOOCHintDetection:
    """Tests for _get_ooc_hint method - implicit OOC signal detection."""

    def test_explicit_ooc_returns_explicit_message(
        self, db_session: Session, game_session: GameSession
    ):
        """When explicit OOC prefix used, should return explicit OOC message."""
        builder = GMContextBuilder(db_session, game_session)
        result = builder._get_ooc_hint(is_explicit_ooc=True, player_input="What time is it?")

        assert "[EXPLICIT OOC REQUEST]" in result

    def test_where_do_i_usually_triggers_ooc_hint(
        self, db_session: Session, game_session: GameSession
    ):
        """'Where do I usually wash myself?' should trigger OOC hint."""
        builder = GMContextBuilder(db_session, game_session)
        result = builder._get_ooc_hint(
            is_explicit_ooc=False,
            player_input="Where do I usually wash myself?",
        )

        assert "[POSSIBLE OOC]" in result

    def test_how_do_i_usually_triggers_ooc_hint(
        self, db_session: Session, game_session: GameSession
    ):
        """'How do I usually get to work?' should trigger OOC hint."""
        builder = GMContextBuilder(db_session, game_session)
        result = builder._get_ooc_hint(
            is_explicit_ooc=False,
            player_input="How do I usually get to work?",
        )

        assert "[POSSIBLE OOC]" in result

    def test_where_do_i_sleep_triggers_ooc_hint(
        self, db_session: Session, game_session: GameSession
    ):
        """'Where do I sleep?' should trigger OOC hint."""
        builder = GMContextBuilder(db_session, game_session)
        result = builder._get_ooc_hint(
            is_explicit_ooc=False,
            player_input="Where do I sleep?",
        )

        assert "[POSSIBLE OOC]" in result

    def test_regular_action_no_ooc_hint(
        self, db_session: Session, game_session: GameSession
    ):
        """'I walk to the tavern' should not trigger OOC hint."""
        builder = GMContextBuilder(db_session, game_session)
        result = builder._get_ooc_hint(
            is_explicit_ooc=False,
            player_input="I walk to the tavern",
        )

        assert "[POSSIBLE OOC]" not in result
        assert "[EXPLICIT OOC]" not in result


class TestContextBuildIntegration:
    """Integration tests for the full context build."""

    def test_build_includes_familiarity_section(
        self, db_session: Session, game_session: GameSession
    ):
        """Built context should include familiarity section."""
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
        result = builder.build(
            player_id=player.id,
            location_key=location.location_key,
            player_input="Hello",
            turn_number=1,
        )

        # Familiarity info is now in SYSTEM NOTES section (no separate header)
        assert "## SYSTEM NOTES" in result
        # Check for familiarity content (unfamiliar in this case)
        assert "Unfamiliar with current location" in result or "Familiar with current location" in result
