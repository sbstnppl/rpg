"""Tests for rumor system models."""

import pytest
from sqlalchemy.exc import IntegrityError

from src.database.models.rumors import (
    Rumor,
    RumorKnowledge,
    RumorSentiment,
)


class TestRumorSentiment:
    """Tests for RumorSentiment enum."""

    def test_sentiment_values(self):
        assert RumorSentiment.POSITIVE.value == "positive"
        assert RumorSentiment.NEGATIVE.value == "negative"
        assert RumorSentiment.NEUTRAL.value == "neutral"
        assert RumorSentiment.SCANDALOUS.value == "scandalous"
        assert RumorSentiment.HEROIC.value == "heroic"


class TestRumorModel:
    """Tests for Rumor model."""

    def test_create_rumor(self, db_session, game_session):
        """Test creating a basic rumor."""
        rumor = Rumor(
            session_id=game_session.id,
            rumor_key="hero_slays_bandit",
            subject_entity_key="player",
            content="A stranger slew the bandit chief with a single blow",
            truth_value=0.9,
            origin_location_key="village_square",
            origin_turn=5,
            spread_rate=0.5,
            decay_rate=0.05,
            intensity=1.0,
            sentiment=RumorSentiment.HEROIC,
        )
        db_session.add(rumor)
        db_session.commit()

        assert rumor.id is not None
        assert rumor.rumor_key == "hero_slays_bandit"
        assert rumor.subject_entity_key == "player"
        assert rumor.truth_value == 0.9
        assert rumor.intensity == 1.0
        assert rumor.sentiment == RumorSentiment.HEROIC
        assert rumor.is_active is True

    def test_rumor_with_tags(self, db_session, game_session):
        """Test rumor with categorization tags."""
        rumor = Rumor(
            session_id=game_session.id,
            rumor_key="theft_rumor",
            subject_entity_key="player",
            content="They say that stranger stole from the merchant",
            truth_value=0.3,
            origin_location_key="tavern",
            origin_turn=10,
            spread_rate=0.7,
            decay_rate=0.03,
            intensity=0.8,
            sentiment=RumorSentiment.NEGATIVE,
            tags=["theft", "crime", "merchant"],
        )
        db_session.add(rumor)
        db_session.commit()

        assert rumor.tags == ["theft", "crime", "merchant"]

    def test_rumor_with_event_link(self, db_session, game_session):
        """Test rumor linked to a world event."""
        rumor = Rumor(
            session_id=game_session.id,
            rumor_key="battle_rumor",
            subject_entity_key="player",
            content="The hero fought off ten bandits",
            truth_value=0.6,
            original_event_id=42,
            origin_location_key="road",
            origin_turn=15,
            spread_rate=0.4,
            decay_rate=0.02,
            intensity=0.9,
            sentiment=RumorSentiment.HEROIC,
        )
        db_session.add(rumor)
        db_session.commit()

        assert rumor.original_event_id == 42

    def test_rumor_unique_key_per_session(self, db_session, game_session):
        """Test that rumor_key must be unique within session."""
        rumor1 = Rumor(
            session_id=game_session.id,
            rumor_key="unique_rumor",
            subject_entity_key="player",
            content="First version",
            truth_value=1.0,
            origin_location_key="town",
            origin_turn=1,
            spread_rate=0.5,
            decay_rate=0.05,
            intensity=1.0,
            sentiment=RumorSentiment.NEUTRAL,
        )
        db_session.add(rumor1)
        db_session.commit()

        rumor2 = Rumor(
            session_id=game_session.id,
            rumor_key="unique_rumor",
            subject_entity_key="npc",
            content="Second version",
            truth_value=0.5,
            origin_location_key="city",
            origin_turn=2,
            spread_rate=0.5,
            decay_rate=0.05,
            intensity=1.0,
            sentiment=RumorSentiment.NEUTRAL,
        )
        db_session.add(rumor2)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_rumor_defaults(self, db_session, game_session):
        """Test default values for rumor."""
        rumor = Rumor(
            session_id=game_session.id,
            rumor_key="simple_rumor",
            subject_entity_key="npc_1",
            content="Something happened",
            origin_location_key="somewhere",
            origin_turn=1,
        )
        db_session.add(rumor)
        db_session.commit()

        assert rumor.truth_value == 1.0
        assert rumor.spread_rate == 0.5
        assert rumor.decay_rate == 0.05
        assert rumor.intensity == 1.0
        assert rumor.sentiment == RumorSentiment.NEUTRAL
        assert rumor.is_active is True
        assert rumor.tags == []


class TestRumorKnowledgeModel:
    """Tests for RumorKnowledge model."""

    def test_create_rumor_knowledge(self, db_session, game_session):
        """Test creating rumor knowledge record."""
        # Create a rumor first
        rumor = Rumor(
            session_id=game_session.id,
            rumor_key="test_rumor",
            subject_entity_key="player",
            content="Test rumor content",
            origin_location_key="tavern",
            origin_turn=1,
        )
        db_session.add(rumor)
        db_session.commit()

        # Create knowledge record
        knowledge = RumorKnowledge(
            session_id=game_session.id,
            rumor_id=rumor.id,
            entity_key="innkeeper",
            learned_turn=2,
            believed=True,
            will_spread=True,
        )
        db_session.add(knowledge)
        db_session.commit()

        assert knowledge.id is not None
        assert knowledge.rumor_id == rumor.id
        assert knowledge.entity_key == "innkeeper"
        assert knowledge.believed is True
        assert knowledge.will_spread is True
        assert knowledge.local_distortion is None

    def test_rumor_knowledge_with_distortion(self, db_session, game_session):
        """Test rumor knowledge with local distortion."""
        rumor = Rumor(
            session_id=game_session.id,
            rumor_key="distorted_rumor",
            subject_entity_key="player",
            content="They killed one bandit",
            origin_location_key="village",
            origin_turn=1,
        )
        db_session.add(rumor)
        db_session.commit()

        knowledge = RumorKnowledge(
            session_id=game_session.id,
            rumor_id=rumor.id,
            entity_key="gossip_npc",
            learned_turn=5,
            believed=True,
            will_spread=True,
            local_distortion="They killed TEN bandits with their bare hands!",
        )
        db_session.add(knowledge)
        db_session.commit()

        assert knowledge.local_distortion == "They killed TEN bandits with their bare hands!"

    def test_rumor_knowledge_defaults(self, db_session, game_session):
        """Test default values for rumor knowledge."""
        rumor = Rumor(
            session_id=game_session.id,
            rumor_key="default_test",
            subject_entity_key="someone",
            content="Something",
            origin_location_key="somewhere",
            origin_turn=1,
        )
        db_session.add(rumor)
        db_session.commit()

        knowledge = RumorKnowledge(
            session_id=game_session.id,
            rumor_id=rumor.id,
            entity_key="listener",
            learned_turn=2,
        )
        db_session.add(knowledge)
        db_session.commit()

        assert knowledge.believed is True
        assert knowledge.will_spread is True

    def test_rumor_knowledge_unique_per_entity(self, db_session, game_session):
        """Test that each entity can only know a rumor once."""
        rumor = Rumor(
            session_id=game_session.id,
            rumor_key="unique_knowledge_test",
            subject_entity_key="player",
            content="Test",
            origin_location_key="town",
            origin_turn=1,
        )
        db_session.add(rumor)
        db_session.commit()

        knowledge1 = RumorKnowledge(
            session_id=game_session.id,
            rumor_id=rumor.id,
            entity_key="npc_1",
            learned_turn=2,
        )
        db_session.add(knowledge1)
        db_session.commit()

        knowledge2 = RumorKnowledge(
            session_id=game_session.id,
            rumor_id=rumor.id,
            entity_key="npc_1",
            learned_turn=3,
        )
        db_session.add(knowledge2)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_rumor_relationship(self, db_session, game_session):
        """Test relationship between Rumor and RumorKnowledge."""
        rumor = Rumor(
            session_id=game_session.id,
            rumor_key="relationship_test",
            subject_entity_key="player",
            content="Test relationship",
            origin_location_key="town",
            origin_turn=1,
        )
        db_session.add(rumor)
        db_session.commit()

        knowledge1 = RumorKnowledge(
            session_id=game_session.id,
            rumor_id=rumor.id,
            entity_key="npc_1",
            learned_turn=2,
        )
        knowledge2 = RumorKnowledge(
            session_id=game_session.id,
            rumor_id=rumor.id,
            entity_key="npc_2",
            learned_turn=3,
        )
        db_session.add_all([knowledge1, knowledge2])
        db_session.commit()

        # Refresh to get relationship
        db_session.refresh(rumor)
        assert len(rumor.known_by) == 2
