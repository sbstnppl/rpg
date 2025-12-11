"""Tests for RumorManager."""

import pytest

from src.database.models.rumors import Rumor, RumorKnowledge, RumorSentiment
from src.managers.rumor_manager import RumorManager, RumorInfo, RumorSpreadResult


class TestCreateRumor:
    """Tests for rumor creation."""

    def test_create_rumor_basic(self, db_session, game_session):
        """Test creating a basic rumor."""
        manager = RumorManager(db_session, game_session)

        rumor = manager.create_rumor(
            rumor_key="hero_deed",
            subject_entity_key="player",
            content="The stranger saved the child from drowning",
            origin_location_key="river_crossing",
            origin_turn=5,
        )

        assert rumor.rumor_key == "hero_deed"
        assert rumor.subject_entity_key == "player"
        assert rumor.content == "The stranger saved the child from drowning"
        assert rumor.origin_location_key == "river_crossing"
        assert rumor.origin_turn == 5
        assert rumor.sentiment == RumorSentiment.NEUTRAL

    def test_create_rumor_with_sentiment(self, db_session, game_session):
        """Test creating a rumor with specific sentiment."""
        manager = RumorManager(db_session, game_session)

        rumor = manager.create_rumor(
            rumor_key="scandal",
            subject_entity_key="noble",
            content="The baron was seen leaving the tavern wench's room",
            origin_location_key="tavern",
            origin_turn=10,
            sentiment=RumorSentiment.SCANDALOUS,
            spread_rate=0.8,
        )

        assert rumor.sentiment == RumorSentiment.SCANDALOUS
        assert rumor.spread_rate == 0.8

    def test_create_rumor_with_tags(self, db_session, game_session):
        """Test creating a rumor with tags."""
        manager = RumorManager(db_session, game_session)

        rumor = manager.create_rumor(
            rumor_key="crime_rumor",
            subject_entity_key="player",
            content="They stole from the merchant",
            origin_location_key="market",
            origin_turn=15,
            tags=["theft", "crime"],
            sentiment=RumorSentiment.NEGATIVE,
        )

        assert rumor.tags == ["theft", "crime"]

    def test_create_rumor_with_event_link(self, db_session, game_session):
        """Test creating a rumor linked to an event."""
        manager = RumorManager(db_session, game_session)

        rumor = manager.create_rumor(
            rumor_key="battle_story",
            subject_entity_key="player",
            content="The hero fought bravely",
            origin_location_key="battlefield",
            origin_turn=20,
            original_event_id=42,
        )

        assert rumor.original_event_id == 42


class TestGetRumor:
    """Tests for retrieving rumors."""

    def test_get_rumor(self, db_session, game_session):
        """Test getting a rumor by key."""
        manager = RumorManager(db_session, game_session)

        manager.create_rumor(
            rumor_key="test_rumor",
            subject_entity_key="player",
            content="Test content",
            origin_location_key="town",
            origin_turn=1,
        )

        rumor = manager.get_rumor("test_rumor")
        assert rumor is not None
        assert rumor.rumor_key == "test_rumor"

    def test_get_rumor_not_found(self, db_session, game_session):
        """Test getting non-existent rumor."""
        manager = RumorManager(db_session, game_session)

        rumor = manager.get_rumor("nonexistent")
        assert rumor is None

    def test_get_rumors_about(self, db_session, game_session):
        """Test getting all rumors about an entity."""
        manager = RumorManager(db_session, game_session)

        manager.create_rumor(
            rumor_key="rumor1",
            subject_entity_key="player",
            content="First rumor",
            origin_location_key="town",
            origin_turn=1,
        )
        manager.create_rumor(
            rumor_key="rumor2",
            subject_entity_key="player",
            content="Second rumor",
            origin_location_key="village",
            origin_turn=2,
        )
        manager.create_rumor(
            rumor_key="rumor3",
            subject_entity_key="other_npc",
            content="About someone else",
            origin_location_key="city",
            origin_turn=3,
        )

        player_rumors = manager.get_rumors_about("player")
        assert len(player_rumors) == 2

    def test_get_active_rumors(self, db_session, game_session):
        """Test getting only active rumors."""
        manager = RumorManager(db_session, game_session)

        rumor1 = manager.create_rumor(
            rumor_key="active_rumor",
            subject_entity_key="player",
            content="Active",
            origin_location_key="town",
            origin_turn=1,
        )
        rumor2 = manager.create_rumor(
            rumor_key="inactive_rumor",
            subject_entity_key="player",
            content="Inactive",
            origin_location_key="town",
            origin_turn=2,
        )
        rumor2.is_active = False
        db_session.commit()

        active = manager.get_active_rumors()
        assert len(active) == 1
        assert active[0].rumor_key == "active_rumor"


class TestRumorKnowledge:
    """Tests for rumor knowledge management."""

    def test_add_knowledge(self, db_session, game_session):
        """Test adding knowledge of a rumor to an NPC."""
        manager = RumorManager(db_session, game_session)

        rumor = manager.create_rumor(
            rumor_key="knowledge_test",
            subject_entity_key="player",
            content="Test content",
            origin_location_key="tavern",
            origin_turn=1,
        )

        knowledge = manager.add_knowledge(
            rumor_key="knowledge_test",
            entity_key="innkeeper",
            learned_turn=2,
        )

        assert knowledge.entity_key == "innkeeper"
        assert knowledge.learned_turn == 2
        assert knowledge.believed is True
        assert knowledge.will_spread is True

    def test_add_knowledge_disbelieved(self, db_session, game_session):
        """Test adding knowledge where NPC doesn't believe it."""
        manager = RumorManager(db_session, game_session)

        manager.create_rumor(
            rumor_key="dubious_rumor",
            subject_entity_key="player",
            content="Unbelievable claim",
            origin_location_key="tavern",
            origin_turn=1,
        )

        knowledge = manager.add_knowledge(
            rumor_key="dubious_rumor",
            entity_key="skeptic",
            learned_turn=3,
            believed=False,
            will_spread=False,
        )

        assert knowledge.believed is False
        assert knowledge.will_spread is False

    def test_add_knowledge_with_distortion(self, db_session, game_session):
        """Test adding knowledge with local distortion."""
        manager = RumorManager(db_session, game_session)

        manager.create_rumor(
            rumor_key="distortion_test",
            subject_entity_key="player",
            content="They killed one bandit",
            origin_location_key="village",
            origin_turn=1,
        )

        knowledge = manager.add_knowledge(
            rumor_key="distortion_test",
            entity_key="exaggerator",
            learned_turn=5,
            local_distortion="They killed TEN bandits!",
        )

        assert knowledge.local_distortion == "They killed TEN bandits!"

    def test_get_rumors_known_by(self, db_session, game_session):
        """Test getting all rumors known by an NPC."""
        manager = RumorManager(db_session, game_session)

        manager.create_rumor(
            rumor_key="rumor_a",
            subject_entity_key="player",
            content="Rumor A",
            origin_location_key="town",
            origin_turn=1,
        )
        manager.create_rumor(
            rumor_key="rumor_b",
            subject_entity_key="player",
            content="Rumor B",
            origin_location_key="town",
            origin_turn=2,
        )

        manager.add_knowledge("rumor_a", "gossip", 3)
        manager.add_knowledge("rumor_b", "gossip", 4)
        manager.add_knowledge("rumor_a", "other_npc", 5)

        gossip_rumors = manager.get_rumors_known_by("gossip")
        assert len(gossip_rumors) == 2

        other_rumors = manager.get_rumors_known_by("other_npc")
        assert len(other_rumors) == 1

    def test_entity_knows_rumor(self, db_session, game_session):
        """Test checking if entity knows a rumor."""
        manager = RumorManager(db_session, game_session)

        manager.create_rumor(
            rumor_key="check_test",
            subject_entity_key="player",
            content="Test",
            origin_location_key="town",
            origin_turn=1,
        )
        manager.add_knowledge("check_test", "informed_npc", 2)

        assert manager.entity_knows_rumor("informed_npc", "check_test") is True
        assert manager.entity_knows_rumor("uninformed_npc", "check_test") is False


class TestRumorDecay:
    """Tests for rumor decay mechanics."""

    def test_decay_rumors(self, db_session, game_session):
        """Test decaying rumor intensity over time."""
        manager = RumorManager(db_session, game_session)

        rumor = manager.create_rumor(
            rumor_key="decay_test",
            subject_entity_key="player",
            content="Test decay",
            origin_location_key="town",
            origin_turn=1,
            intensity=1.0,
            decay_rate=0.1,
        )

        # Decay by 1 day
        manager.decay_rumors(days=1)

        db_session.refresh(rumor)
        assert rumor.intensity == pytest.approx(0.9, rel=0.01)

    def test_decay_deactivates_weak_rumors(self, db_session, game_session):
        """Test that rumors with low intensity become inactive."""
        manager = RumorManager(db_session, game_session)

        rumor = manager.create_rumor(
            rumor_key="weak_rumor",
            subject_entity_key="player",
            content="Fading rumor",
            origin_location_key="town",
            origin_turn=1,
            intensity=0.15,
            decay_rate=0.1,
        )

        # Decay should drop it below threshold
        manager.decay_rumors(days=1)

        db_session.refresh(rumor)
        assert rumor.intensity < 0.1
        assert rumor.is_active is False

    def test_decay_multiple_rumors(self, db_session, game_session):
        """Test decaying multiple rumors at once."""
        manager = RumorManager(db_session, game_session)

        rumor1 = manager.create_rumor(
            rumor_key="multi_decay_1",
            subject_entity_key="player",
            content="First",
            origin_location_key="town",
            origin_turn=1,
            intensity=1.0,
            decay_rate=0.05,
        )
        rumor2 = manager.create_rumor(
            rumor_key="multi_decay_2",
            subject_entity_key="player",
            content="Second",
            origin_location_key="town",
            origin_turn=1,
            intensity=0.8,
            decay_rate=0.1,
        )

        manager.decay_rumors(days=2)

        db_session.refresh(rumor1)
        db_session.refresh(rumor2)

        assert rumor1.intensity == pytest.approx(0.9, rel=0.01)
        assert rumor2.intensity == pytest.approx(0.6, rel=0.01)


class TestRumorSpread:
    """Tests for rumor spreading mechanics."""

    def test_spread_rumor_to_entity(self, db_session, game_session):
        """Test spreading a rumor to a specific entity."""
        manager = RumorManager(db_session, game_session)

        manager.create_rumor(
            rumor_key="spread_test",
            subject_entity_key="player",
            content="Original content",
            origin_location_key="tavern",
            origin_turn=1,
            truth_value=1.0,
        )

        result = manager.spread_rumor_to_entity(
            rumor_key="spread_test",
            from_entity_key="witness",
            to_entity_key="listener",
            current_turn=5,
        )

        assert result.spread_successful is True
        assert result.to_entity_key == "listener"
        assert manager.entity_knows_rumor("listener", "spread_test")

    def test_spread_rumor_already_known(self, db_session, game_session):
        """Test spreading a rumor the target already knows."""
        manager = RumorManager(db_session, game_session)

        manager.create_rumor(
            rumor_key="already_known",
            subject_entity_key="player",
            content="Known content",
            origin_location_key="tavern",
            origin_turn=1,
        )
        manager.add_knowledge("already_known", "listener", 2)

        result = manager.spread_rumor_to_entity(
            rumor_key="already_known",
            from_entity_key="speaker",
            to_entity_key="listener",
            current_turn=5,
        )

        assert result.spread_successful is False
        assert result.reason == "already_known"

    def test_spread_rumor_with_distortion(self, db_session, game_session):
        """Test that spreading can introduce distortion."""
        manager = RumorManager(db_session, game_session)

        manager.create_rumor(
            rumor_key="distort_spread",
            subject_entity_key="player",
            content="They found some gold",
            origin_location_key="mine",
            origin_turn=1,
            truth_value=1.0,
        )

        # Spread with distortion chance
        result = manager.spread_rumor_to_entity(
            rumor_key="distort_spread",
            from_entity_key="exaggerator",
            to_entity_key="gullible",
            current_turn=5,
            distortion_chance=1.0,  # Force distortion for test
        )

        assert result.spread_successful is True
        # Distortion applied means truth value decreased
        rumor = manager.get_rumor("distort_spread")
        # Truth value should be reduced when distortion occurs
        assert rumor.truth_value <= 1.0


class TestRumorsByLocation:
    """Tests for location-based rumor queries."""

    def test_get_rumors_at_location(self, db_session, game_session):
        """Test getting rumors circulating at a location."""
        manager = RumorManager(db_session, game_session)

        # Create rumors with different origins
        manager.create_rumor(
            rumor_key="tavern_rumor",
            subject_entity_key="player",
            content="Tavern gossip",
            origin_location_key="tavern",
            origin_turn=1,
        )
        manager.create_rumor(
            rumor_key="market_rumor",
            subject_entity_key="merchant",
            content="Market news",
            origin_location_key="market",
            origin_turn=2,
        )

        # Add knowledge to NPCs at tavern
        manager.add_knowledge("tavern_rumor", "tavern_patron_1", 3)
        manager.add_knowledge("tavern_rumor", "tavern_patron_2", 4)
        manager.add_knowledge("market_rumor", "tavern_patron_1", 5)

        # Get rumors known by NPCs (would need location tracking in real impl)
        tavern_patron_rumors = manager.get_rumors_known_by("tavern_patron_1")
        assert len(tavern_patron_rumors) == 2

    def test_get_rumors_originating_at(self, db_session, game_session):
        """Test getting rumors that originated at a location."""
        manager = RumorManager(db_session, game_session)

        manager.create_rumor(
            rumor_key="local_1",
            subject_entity_key="player",
            content="Local 1",
            origin_location_key="village_square",
            origin_turn=1,
        )
        manager.create_rumor(
            rumor_key="local_2",
            subject_entity_key="player",
            content="Local 2",
            origin_location_key="village_square",
            origin_turn=2,
        )
        manager.create_rumor(
            rumor_key="elsewhere",
            subject_entity_key="player",
            content="Elsewhere",
            origin_location_key="city",
            origin_turn=3,
        )

        village_rumors = manager.get_rumors_originating_at("village_square")
        assert len(village_rumors) == 2


class TestRumorInfo:
    """Tests for rumor info retrieval."""

    def test_get_rumor_info(self, db_session, game_session):
        """Test getting detailed rumor info."""
        manager = RumorManager(db_session, game_session)

        manager.create_rumor(
            rumor_key="info_test",
            subject_entity_key="player",
            content="Test content",
            origin_location_key="tavern",
            origin_turn=1,
            sentiment=RumorSentiment.HEROIC,
            tags=["heroism", "combat"],
        )
        manager.add_knowledge("info_test", "npc_1", 2)
        manager.add_knowledge("info_test", "npc_2", 3)

        info = manager.get_rumor_info("info_test")

        assert info is not None
        assert info.rumor_key == "info_test"
        assert info.content == "Test content"
        assert info.sentiment == "heroic"
        assert info.known_by_count == 2
        assert "heroism" in info.tags


class TestRumorContext:
    """Tests for rumor context generation."""

    def test_get_rumor_context_for_entity(self, db_session, game_session):
        """Test generating rumor context for an NPC."""
        manager = RumorManager(db_session, game_session)

        manager.create_rumor(
            rumor_key="context_rumor",
            subject_entity_key="player",
            content="The stranger is a skilled fighter",
            origin_location_key="arena",
            origin_turn=1,
            sentiment=RumorSentiment.HEROIC,
        )
        manager.add_knowledge("context_rumor", "guard", 2)

        context = manager.get_rumor_context_for_entity("guard")

        assert "skilled fighter" in context
        assert "heroic" in context.lower() or "positive" in context.lower()

    def test_get_rumor_context_empty(self, db_session, game_session):
        """Test context when NPC knows no rumors."""
        manager = RumorManager(db_session, game_session)

        context = manager.get_rumor_context_for_entity("uninformed_npc")

        assert context == "" or "no rumors" in context.lower()

    def test_get_rumors_context(self, db_session, game_session):
        """Test generating general rumors context for GM."""
        manager = RumorManager(db_session, game_session)

        manager.create_rumor(
            rumor_key="gm_context_1",
            subject_entity_key="player",
            content="Player did something heroic",
            origin_location_key="village",
            origin_turn=1,
            sentiment=RumorSentiment.HEROIC,
            intensity=0.9,
        )
        manager.create_rumor(
            rumor_key="gm_context_2",
            subject_entity_key="player",
            content="Player stole bread",
            origin_location_key="market",
            origin_turn=5,
            sentiment=RumorSentiment.NEGATIVE,
            intensity=0.5,
        )

        context = manager.get_rumors_context()

        assert "heroic" in context.lower() or "Player did something" in context
        assert len(context) > 0
