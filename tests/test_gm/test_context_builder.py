"""Tests for the GMContextBuilder, focusing on familiarity and OOC detection."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.enums import EntityType
from src.database.models.session import GameSession
from src.gm.context_builder import GMContextBuilder
from src.llm.message_types import MessageRole
from tests.factories import (
    create_entity,
    create_fact,
    create_location,
    create_turn,
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


class TestSelectTurnsForContext:
    """Tests for _select_turns_for_context day-aware turn selection."""

    def test_returns_turns_from_day_start_when_10_back_spans_days(
        self, db_session: Session, game_session: GameSession
    ):
        """When 10 turns back lands on a different day, extend to that day's start."""
        # Create turns across multiple days:
        # Day 1: Turns 1-5
        # Day 2: Turns 6-15
        # Day 3: Turns 16-20 (current = 20)
        for i in range(1, 6):
            create_turn(
                db_session,
                game_session,
                turn_number=i,
                game_day_at_turn=1,
                game_time_at_turn="10:00",
                player_input=f"Day 1 turn {i}",
                gm_response=f"Response {i}",
            )
        for i in range(6, 16):
            create_turn(
                db_session,
                game_session,
                turn_number=i,
                game_day_at_turn=2,
                game_time_at_turn="10:00",
                player_input=f"Day 2 turn {i}",
                gm_response=f"Response {i}",
            )
        for i in range(16, 21):
            create_turn(
                db_session,
                game_session,
                turn_number=i,
                game_day_at_turn=3,
                game_time_at_turn="10:00",
                player_input=f"Day 3 turn {i}",
                gm_response=f"Response {i}",
            )

        builder = GMContextBuilder(db_session, game_session)
        turns = builder._select_turns_for_context(current_turn_number=20)

        # 10 back from 20 = turn 10 (Day 2)
        # First turn of Day 2 = turn 6
        # So we should get turns 6-19 (excluding current)
        assert len(turns) == 14
        assert turns[0].turn_number == 6
        assert turns[-1].turn_number == 19

    def test_returns_all_turns_when_less_than_10_exist(
        self, db_session: Session, game_session: GameSession
    ):
        """When fewer than 10 turns exist, return all of them."""
        for i in range(1, 6):
            create_turn(
                db_session,
                game_session,
                turn_number=i,
                game_day_at_turn=1,
                game_time_at_turn="10:00",
                player_input=f"Turn {i}",
                gm_response=f"Response {i}",
            )

        builder = GMContextBuilder(db_session, game_session)
        turns = builder._select_turns_for_context(current_turn_number=5)

        # Should return turns 1-4 (all previous turns)
        assert len(turns) == 4
        assert turns[0].turn_number == 1
        assert turns[-1].turn_number == 4

    def test_single_day_returns_all_day_turns(
        self, db_session: Session, game_session: GameSession
    ):
        """When all 10+ turns are same day, return all from that day."""
        for i in range(1, 16):
            create_turn(
                db_session,
                game_session,
                turn_number=i,
                game_day_at_turn=1,
                game_time_at_turn="10:00",
                player_input=f"Turn {i}",
                gm_response=f"Response {i}",
            )

        builder = GMContextBuilder(db_session, game_session)
        turns = builder._select_turns_for_context(current_turn_number=15)

        # 10 back from 15 = turn 5, which is Day 1
        # First turn of Day 1 = turn 1
        # So we get turns 1-14
        assert len(turns) == 14
        assert turns[0].turn_number == 1
        assert turns[-1].turn_number == 14

    def test_returns_empty_for_first_turn(
        self, db_session: Session, game_session: GameSession
    ):
        """First turn has no history to return."""
        builder = GMContextBuilder(db_session, game_session)
        turns = builder._select_turns_for_context(current_turn_number=1)

        assert len(turns) == 0


class TestBuildSystemPrompt:
    """Tests for build_system_prompt method."""

    def test_includes_gm_instructions(
        self, db_session: Session, game_session: GameSession
    ):
        """System prompt should include GM instructions."""
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
        result = builder.build_system_prompt(
            player_id=player.id,
            location_key=location.location_key,
        )

        # Should include key GM instruction sections
        assert "MANDATORY TOOL CALLS" in result
        assert "Game Master" in result

    def test_includes_world_state(
        self, db_session: Session, game_session: GameSession
    ):
        """System prompt should include current world state."""
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
        result = builder.build_system_prompt(
            player_id=player.id,
            location_key=location.location_key,
        )

        # Should include location info
        assert "The Rusty Tankard" in result or "tavern" in result

    def test_includes_summaries(
        self, db_session: Session, game_session: GameSession
    ):
        """System prompt should include story context section for summaries."""
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
        result = builder.build_system_prompt(
            player_id=player.id,
            location_key=location.location_key,
        )

        # Should have story context section
        assert "STORY CONTEXT" in result or "Story" in result


class TestBuildConversationMessages:
    """Tests for build_conversation_messages method."""

    def test_returns_message_pairs_for_history(
        self, db_session: Session, game_session: GameSession
    ):
        """Should return USER/ASSISTANT pairs for past turns."""
        player = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.PLAYER,
            entity_key="player_001",
            display_name="Finn",
        )
        # Create some turn history
        for i in range(1, 4):
            create_turn(
                db_session,
                game_session,
                turn_number=i,
                game_day_at_turn=1,
                game_time_at_turn="10:00",
                player_input=f"Player action {i}",
                gm_response=f"GM response {i}",
            )

        builder = GMContextBuilder(db_session, game_session)
        messages = builder.build_conversation_messages(
            player_id=player.id,
            player_input="Current action",
            turn_number=4,
        )

        # Should have: 3 history turns (6 messages) + 1 current (1 message) = 7
        assert len(messages) == 7
        # Check alternating pattern
        assert messages[0].role == MessageRole.USER
        assert messages[1].role == MessageRole.ASSISTANT
        assert messages[2].role == MessageRole.USER
        # Last message is current input
        assert messages[-1].role == MessageRole.USER
        assert "Current action" in messages[-1].content

    def test_current_input_is_last_message(
        self, db_session: Session, game_session: GameSession
    ):
        """Current player input should be the final message."""
        player = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.PLAYER,
            entity_key="player_001",
            display_name="Finn",
        )
        create_turn(
            db_session,
            game_session,
            turn_number=1,
            game_day_at_turn=1,
            player_input="Previous action",
            gm_response="Previous response",
        )

        builder = GMContextBuilder(db_session, game_session)
        messages = builder.build_conversation_messages(
            player_id=player.id,
            player_input="I look around",
            turn_number=2,
        )

        assert messages[-1].role == MessageRole.USER
        assert "I look around" in messages[-1].content

    def test_ooc_hint_prepended_to_current_input(
        self, db_session: Session, game_session: GameSession
    ):
        """When OOC hint detected, it should be prepended to current input."""
        player = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.PLAYER,
            entity_key="player_001",
            display_name="Finn",
        )

        builder = GMContextBuilder(db_session, game_session)
        messages = builder.build_conversation_messages(
            player_id=player.id,
            player_input="Where do I usually sleep?",
            turn_number=1,
            is_ooc_hint=True,
        )

        # The last message should contain OOC indicator
        assert messages[-1].role == MessageRole.USER
        assert "[EXPLICIT OOC" in messages[-1].content or "[POSSIBLE OOC" in messages[-1].content

    def test_empty_history_returns_only_current_input(
        self, db_session: Session, game_session: GameSession
    ):
        """First turn should only have current input message."""
        player = create_entity(
            db_session,
            game_session,
            entity_type=EntityType.PLAYER,
            entity_key="player_001",
            display_name="Finn",
        )

        builder = GMContextBuilder(db_session, game_session)
        messages = builder.build_conversation_messages(
            player_id=player.id,
            player_input="Hello world",
            turn_number=1,
        )

        assert len(messages) == 1
        assert messages[0].role == MessageRole.USER
        assert "Hello world" in messages[0].content
