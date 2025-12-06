"""Tests for RelationshipManager class."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.entities import NPCExtension
from src.database.models.relationships import Relationship, RelationshipChange
from src.database.models.session import GameSession
from src.managers.relationship_manager import RelationshipManager, PERSONALITY_EFFECTS
from tests.factories import (
    create_entity,
    create_npc_extension,
    create_relationship,
)


class TestRelationshipManagerBasics:
    """Tests for RelationshipManager basic operations."""

    def test_get_relationship_returns_none_when_missing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_relationship returns None when not exists."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        manager = RelationshipManager(db_session, game_session)

        result = manager.get_relationship(entity1.id, entity2.id)

        assert result is None

    def test_get_relationship_returns_existing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_relationship returns existing relationship."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        rel = create_relationship(
            db_session, game_session, entity1, entity2, trust=75
        )
        manager = RelationshipManager(db_session, game_session)

        result = manager.get_relationship(entity1.id, entity2.id)

        assert result is not None
        assert result.id == rel.id
        assert result.trust == 75

    def test_get_or_create_relationship_creates_when_missing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_or_create creates new relationship."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        manager = RelationshipManager(db_session, game_session)

        result = manager.get_or_create_relationship(entity1.id, entity2.id)

        assert result is not None
        assert result.from_entity_id == entity1.id
        assert result.to_entity_id == entity2.id
        assert result.knows is False

    def test_get_or_create_relationship_returns_existing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_or_create returns existing relationship."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        rel = create_relationship(
            db_session, game_session, entity1, entity2, trust=60
        )
        manager = RelationshipManager(db_session, game_session)

        result = manager.get_or_create_relationship(entity1.id, entity2.id)

        assert result.id == rel.id
        assert result.trust == 60


class TestGetAttitude:
    """Tests for getting attitude information."""

    def test_get_attitude_unknown_entity(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify default attitude for unknown entity."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        manager = RelationshipManager(db_session, game_session)

        attitude = manager.get_attitude(entity1.id, entity2.id)

        assert attitude["knows"] is False
        assert attitude["trust"] == 50
        assert attitude["liking"] == 50
        assert attitude["effective_liking"] == 50

    def test_get_attitude_known_entity(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify attitude for known entity."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        create_relationship(
            db_session, game_session, entity1, entity2,
            knows=True,
            trust=80,
            liking=70,
            respect=60,
        )
        manager = RelationshipManager(db_session, game_session)

        attitude = manager.get_attitude(entity1.id, entity2.id)

        assert attitude["knows"] is True
        assert attitude["trust"] == 80
        assert attitude["liking"] == 70
        assert attitude["respect"] == 60

    def test_get_attitude_includes_mood_modifier(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify mood modifier affects effective liking."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        create_relationship(
            db_session, game_session, entity1, entity2,
            liking=60,
            mood_modifier=10,
        )
        manager = RelationshipManager(db_session, game_session)

        attitude = manager.get_attitude(entity1.id, entity2.id)

        assert attitude["liking"] == 60
        assert attitude["effective_liking"] == 70


class TestRecordMeeting:
    """Tests for recording first meetings."""

    def test_record_meeting_creates_bidirectional(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify record_meeting creates relationships in both directions."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        manager = RelationshipManager(db_session, game_session)

        rel1, rel2 = manager.record_meeting(entity1.id, entity2.id, "tavern")

        assert rel1.from_entity_id == entity1.id
        assert rel1.to_entity_id == entity2.id
        assert rel2.from_entity_id == entity2.id
        assert rel2.to_entity_id == entity1.id

    def test_record_meeting_sets_knows(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify meeting sets knows flag."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        manager = RelationshipManager(db_session, game_session)

        rel1, rel2 = manager.record_meeting(entity1.id, entity2.id, "market")

        assert rel1.knows is True
        assert rel2.knows is True

    def test_record_meeting_sets_location(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify meeting records first met location."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        manager = RelationshipManager(db_session, game_session)

        rel1, rel2 = manager.record_meeting(entity1.id, entity2.id, "castle_gate")

        assert rel1.first_met_location == "castle_gate"
        assert rel2.first_met_location == "castle_gate"

    def test_record_meeting_initial_familiarity(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify meeting gives initial familiarity."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        manager = RelationshipManager(db_session, game_session)

        rel1, rel2 = manager.record_meeting(entity1.id, entity2.id, "tavern")

        assert rel1.familiarity >= 5
        assert rel2.familiarity >= 5


class TestUpdateAttitude:
    """Tests for attitude updates."""

    def test_update_attitude_positive_delta(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify positive attitude update."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        create_relationship(
            db_session, game_session, entity1, entity2,
            trust=50, familiarity=60  # High familiarity to avoid cap
        )
        manager = RelationshipManager(db_session, game_session)

        result = manager.update_attitude(
            entity1.id, entity2.id, "trust", 10, "Helped in danger"
        )

        assert result.trust == 60

    def test_update_attitude_negative_delta(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify negative attitude update."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        create_relationship(
            db_session, game_session, entity1, entity2, liking=60
        )
        manager = RelationshipManager(db_session, game_session)

        result = manager.update_attitude(
            entity1.id, entity2.id, "liking", -20, "Insulted them"
        )

        assert result.liking == 40

    def test_update_attitude_clamps_to_100(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify attitude clamped at 100."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        create_relationship(
            db_session, game_session, entity1, entity2,
            trust=90, familiarity=60
        )
        manager = RelationshipManager(db_session, game_session)

        result = manager.update_attitude(
            entity1.id, entity2.id, "trust", 50, "Saved their life"
        )

        assert result.trust == 100

    def test_update_attitude_clamps_to_zero(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify attitude clamped at 0."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        create_relationship(
            db_session, game_session, entity1, entity2, trust=10
        )
        manager = RelationshipManager(db_session, game_session)

        result = manager.update_attitude(
            entity1.id, entity2.id, "trust", -50, "Betrayed them"
        )

        assert result.trust == 0

    def test_update_attitude_social_debt_signed(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify social_debt can be negative."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        create_relationship(
            db_session, game_session, entity1, entity2, social_debt=0
        )
        manager = RelationshipManager(db_session, game_session)

        result = manager.update_attitude(
            entity1.id, entity2.id, "social_debt", -30, "They owe me"
        )

        assert result.social_debt == -30

    def test_update_attitude_records_change(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify attitude change is recorded in audit log."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        rel = create_relationship(
            db_session, game_session, entity1, entity2,
            trust=50, familiarity=60  # High familiarity to avoid cap
        )
        manager = RelationshipManager(db_session, game_session)

        manager.update_attitude(
            entity1.id, entity2.id, "trust", 15, "Completed favor"
        )

        changes = db_session.query(RelationshipChange).filter(
            RelationshipChange.relationship_id == rel.id
        ).all()
        assert len(changes) == 1
        assert changes[0].dimension == "trust"
        assert changes[0].old_value == 50
        assert changes[0].new_value == 65


class TestPersonalityModifiers:
    """Tests for personality trait modifiers."""

    def test_get_personality_modifiers_no_traits(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify default modifiers when no personality traits."""
        entity = create_entity(db_session, game_session)
        manager = RelationshipManager(db_session, game_session)

        mods = manager.get_personality_modifiers(entity.id)

        assert mods.trust_gain_mult == 1.0
        assert mods.trust_loss_mult == 1.0
        assert mods.liking_gain_mult == 1.0

    def test_get_personality_modifiers_suspicious(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify suspicious trait reduces trust gain."""
        entity = create_entity(db_session, game_session)
        create_npc_extension(
            db_session, entity,
            personality_traits={"suspicious": True}
        )
        manager = RelationshipManager(db_session, game_session)

        mods = manager.get_personality_modifiers(entity.id)

        assert mods.trust_gain_mult == 0.5
        assert mods.trust_loss_mult == 2.0

    def test_get_personality_modifiers_trusting(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify trusting trait increases trust gain."""
        entity = create_entity(db_session, game_session)
        create_npc_extension(
            db_session, entity,
            personality_traits={"trusting": True}
        )
        manager = RelationshipManager(db_session, game_session)

        mods = manager.get_personality_modifiers(entity.id)

        assert mods.trust_gain_mult == 1.5
        assert mods.trust_loss_mult == 0.7

    def test_update_attitude_applies_personality(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify personality modifiers are applied to updates."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        create_npc_extension(
            db_session, entity1,
            personality_traits={"suspicious": True}
        )
        create_relationship(
            db_session, game_session, entity1, entity2,
            trust=50, familiarity=60  # High familiarity to avoid cap
        )
        manager = RelationshipManager(db_session, game_session)

        # +20 trust with suspicious (0.5x) = +10
        result = manager.update_attitude(
            entity1.id, entity2.id, "trust", 20, "Helped them"
        )

        assert result.trust == 60  # 50 + 10


class TestFamiliarityCap:
    """Tests for familiarity-based relationship caps."""

    def test_familiarity_cap_strangers(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify strangers can't reach high trust quickly."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        create_relationship(
            db_session, game_session, entity1, entity2,
            trust=30, familiarity=10  # Strangers
        )
        manager = RelationshipManager(db_session, game_session)

        # Try to add +50 trust
        result = manager.update_attitude(
            entity1.id, entity2.id, "trust", 50, "First impression",
            apply_personality=False
        )

        # Should be capped at 40 for familiarity < 15
        assert result.trust == 40

    def test_familiarity_cap_acquaintance(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify casual acquaintances capped at 60."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        create_relationship(
            db_session, game_session, entity1, entity2,
            trust=50, familiarity=20  # Casual acquaintance
        )
        manager = RelationshipManager(db_session, game_session)

        result = manager.update_attitude(
            entity1.id, entity2.id, "trust", 50, "Good deed",
            apply_personality=False
        )

        # Capped at 60 for familiarity 15-30
        assert result.trust == 60

    def test_familiarity_cap_high_familiarity_no_cap(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify high familiarity allows full relationship growth."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        create_relationship(
            db_session, game_session, entity1, entity2,
            trust=80, familiarity=60  # Good friends
        )
        manager = RelationshipManager(db_session, game_session)

        result = manager.update_attitude(
            entity1.id, entity2.id, "trust", 30, "Trusted with secret",
            apply_personality=False
        )

        # No cap with familiarity >= 50
        assert result.trust == 100


class TestMoodModifiers:
    """Tests for temporary mood modifiers."""

    def test_set_mood_modifier(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify set_mood_modifier sets values."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        create_relationship(db_session, game_session, entity1, entity2)
        manager = RelationshipManager(db_session, game_session)

        result = manager.set_mood_modifier(
            entity1.id, entity2.id, 15, "Pleased by gift", duration_turns=5
        )

        assert result.mood_modifier == 15
        assert result.mood_reason == "Pleased by gift"
        assert result.mood_expires_turn == game_session.total_turns + 5

    def test_set_mood_modifier_clamps_range(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify mood modifier clamped to -20 to +20."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        create_relationship(db_session, game_session, entity1, entity2)
        manager = RelationshipManager(db_session, game_session)

        result_high = manager.set_mood_modifier(entity1.id, entity2.id, 50, "Very happy")
        assert result_high.mood_modifier == 20

        result_low = manager.set_mood_modifier(entity1.id, entity2.id, -50, "Very upset")
        assert result_low.mood_modifier == -20

    def test_expire_mood_modifiers(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify expire_mood_modifiers clears expired moods."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        rel = create_relationship(
            db_session, game_session, entity1, entity2,
            mood_modifier=10,
            mood_expires_turn=5,
        )
        game_session.total_turns = 10  # Past expiry
        manager = RelationshipManager(db_session, game_session)

        count = manager.expire_mood_modifiers()

        assert count == 1
        db_session.refresh(rel)
        assert rel.mood_modifier == 0


class TestRelationshipHistory:
    """Tests for relationship change history."""

    def test_get_relationship_history_no_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify empty history when no relationship."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        manager = RelationshipManager(db_session, game_session)

        history = manager.get_relationship_history(entity1.id, entity2.id)

        assert history == []

    def test_get_relationship_history_with_changes(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify history returns relationship changes."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        rel = create_relationship(
            db_session, game_session, entity1, entity2,
            trust=50, liking=50, familiarity=60  # High familiarity to allow changes
        )
        manager = RelationshipManager(db_session, game_session)

        # Make some changes
        manager.update_attitude(entity1.id, entity2.id, "trust", 10, "First change")
        manager.update_attitude(entity1.id, entity2.id, "liking", 5, "Second change")

        history = manager.get_relationship_history(entity1.id, entity2.id)

        assert len(history) == 2


class TestSocialCheckModifier:
    """Tests for social check modifier calculation."""

    def test_calculate_social_check_modifier_neutral(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify neutral relationships give no modifier."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        create_relationship(
            db_session, game_session, entity2, entity1,  # Target's attitude
            trust=50, liking=50, respect=50
        )
        manager = RelationshipManager(db_session, game_session)

        modifier = manager.calculate_social_check_modifier(entity1.id, entity2.id)

        assert modifier == 0

    def test_calculate_social_check_modifier_friendly(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify friendly relationships give positive modifier."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        create_relationship(
            db_session, game_session, entity2, entity1,
            trust=80, liking=75, respect=70
        )
        manager = RelationshipManager(db_session, game_session)

        modifier = manager.calculate_social_check_modifier(entity1.id, entity2.id)

        # +2 (liking 70+) + 1 (trust 70+) + 1 (respect 70+) = +4
        assert modifier == 4

    def test_calculate_social_check_modifier_hostile(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify hostile relationships give negative modifier."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        create_relationship(
            db_session, game_session, entity2, entity1,
            trust=20, liking=20, respect=20
        )
        manager = RelationshipManager(db_session, game_session)

        modifier = manager.calculate_social_check_modifier(entity1.id, entity2.id)

        # -2 (liking <30) + -1 (trust <30) + -1 (respect <30) = -4
        assert modifier == -4


class TestAttitudeDescription:
    """Tests for human-readable attitude descriptions."""

    def test_get_attitude_description_stranger(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify stranger description."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        create_relationship(
            db_session, game_session, entity1, entity2, knows=False
        )
        manager = RelationshipManager(db_session, game_session)

        desc = manager.get_attitude_description(entity1.id, entity2.id)

        assert desc == "stranger"

    def test_get_attitude_description_friendly_trusting(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify friendly trusting description."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        create_relationship(
            db_session, game_session, entity1, entity2,
            knows=True, liking=80, trust=75
        )
        manager = RelationshipManager(db_session, game_session)

        desc = manager.get_attitude_description(entity1.id, entity2.id)

        assert "friendly" in desc
        assert "trusting" in desc

    def test_get_attitude_description_hostile(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify hostile description."""
        entity1 = create_entity(db_session, game_session)
        entity2 = create_entity(db_session, game_session)
        create_relationship(
            db_session, game_session, entity1, entity2,
            knows=True, liking=20
        )
        manager = RelationshipManager(db_session, game_session)

        desc = manager.get_attitude_description(entity1.id, entity2.id)

        assert desc == "hostile"
