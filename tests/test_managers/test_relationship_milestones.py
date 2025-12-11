"""Tests for relationship milestone tracking and notifications."""

import pytest
from sqlalchemy.orm import Session

from src.database.models import Entity, EntityType, GameSession
from src.managers.relationship_manager import RelationshipManager
from tests.factories import create_entity


@pytest.fixture
def relationship_manager(
    db_session: Session, game_session: GameSession
) -> RelationshipManager:
    """Create a RelationshipManager instance."""
    game_session.total_turns = 1
    db_session.flush()
    return RelationshipManager(db_session, game_session)


@pytest.fixture
def player(db_session: Session, game_session: GameSession) -> Entity:
    """Create a player entity."""
    return create_entity(
        db_session,
        game_session,
        entity_key="hero",
        entity_type=EntityType.PLAYER,
    )


@pytest.fixture
def npc(db_session: Session, game_session: GameSession) -> Entity:
    """Create an NPC entity."""
    return create_entity(
        db_session,
        game_session,
        entity_key="merchant",
        entity_type=EntityType.NPC,
    )


class TestMilestoneDetection:
    """Tests for detecting milestone crossings."""

    def test_trust_milestone_earned(
        self,
        relationship_manager: RelationshipManager,
        player: Entity,
        npc: Entity,
    ):
        """Verify milestone when trust crosses 70 threshold."""
        # Need familiarity first to allow trust to grow beyond cap
        relationship_manager.update_attitude(
            npc.id, player.id, "familiarity", 60, "Time together"
        )
        # Start at 50 (neutral), increase to 75
        result = relationship_manager.update_attitude(
            from_id=npc.id,
            to_id=player.id,
            dimension="trust",
            delta=25,
            reason="Player saved NPC from bandits",
        )

        milestones = relationship_manager.get_recent_milestones(npc.id, player.id)
        trust_milestones = [m for m in milestones if m.milestone_type == "earned_trust"]

        assert len(trust_milestones) == 1
        assert trust_milestones[0].notified is False

    def test_trust_milestone_lost(
        self,
        relationship_manager: RelationshipManager,
        player: Entity,
        npc: Entity,
    ):
        """Verify milestone when trust drops below 30."""
        # Decrease trust significantly
        relationship_manager.update_attitude(
            npc.id, player.id, "trust", -25, "Player lied to NPC"
        )

        milestones = relationship_manager.get_recent_milestones(npc.id, player.id)

        assert any(m.milestone_type == "lost_trust" for m in milestones)

    def test_friendship_milestone(
        self,
        relationship_manager: RelationshipManager,
        player: Entity,
        npc: Entity,
    ):
        """Verify milestone when liking crosses 70 threshold."""
        # Need high familiarity to allow liking to grow
        relationship_manager.update_attitude(
            npc.id, player.id, "familiarity", 60, "Many conversations"
        )
        relationship_manager.update_attitude(
            npc.id, player.id, "liking", 25, "Player is kind and helpful"
        )

        milestones = relationship_manager.get_recent_milestones(npc.id, player.id)

        assert any(m.milestone_type == "became_friends" for m in milestones)

    def test_enemy_milestone(
        self,
        relationship_manager: RelationshipManager,
        player: Entity,
        npc: Entity,
    ):
        """Verify milestone when liking drops below 30."""
        relationship_manager.update_attitude(
            npc.id, player.id, "liking", -25, "Player insulted NPC's family"
        )

        milestones = relationship_manager.get_recent_milestones(npc.id, player.id)

        assert any(m.milestone_type == "made_enemy" for m in milestones)

    def test_respect_milestone_earned(
        self,
        relationship_manager: RelationshipManager,
        player: Entity,
        npc: Entity,
    ):
        """Verify milestone when respect crosses 70 threshold."""
        relationship_manager.update_attitude(
            npc.id, player.id, "familiarity", 60, "Combat together"
        )
        relationship_manager.update_attitude(
            npc.id, player.id, "respect", 25, "Demonstrated combat prowess"
        )

        milestones = relationship_manager.get_recent_milestones(npc.id, player.id)

        assert any(m.milestone_type == "earned_respect" for m in milestones)

    def test_romantic_spark_milestone(
        self,
        relationship_manager: RelationshipManager,
        player: Entity,
        npc: Entity,
    ):
        """Verify milestone when romantic interest reaches 30."""
        relationship_manager.update_attitude(
            npc.id, player.id, "romantic_interest", 30, "Charming conversation"
        )

        milestones = relationship_manager.get_recent_milestones(npc.id, player.id)

        assert any(m.milestone_type == "romantic_spark" for m in milestones)

    def test_romantic_interest_milestone(
        self,
        relationship_manager: RelationshipManager,
        player: Entity,
        npc: Entity,
    ):
        """Verify milestone when romantic interest reaches 50."""
        # Need familiarity to allow romantic_interest to grow
        relationship_manager.update_attitude(
            npc.id, player.id, "familiarity", 60, "Time together"
        )
        relationship_manager.update_attitude(
            npc.id, player.id, "romantic_interest", 50, "Romantic gesture"
        )

        milestones = relationship_manager.get_recent_milestones(npc.id, player.id)

        assert any(m.milestone_type == "romantic_interest" for m in milestones)

    def test_close_bond_milestone(
        self,
        relationship_manager: RelationshipManager,
        player: Entity,
        npc: Entity,
    ):
        """Verify milestone when familiarity reaches 70."""
        relationship_manager.update_attitude(
            npc.id, player.id, "familiarity", 70, "Spent much time together"
        )

        milestones = relationship_manager.get_recent_milestones(npc.id, player.id)

        assert any(m.milestone_type == "close_bond" for m in milestones)

    def test_fear_milestone(
        self,
        relationship_manager: RelationshipManager,
        player: Entity,
        npc: Entity,
    ):
        """Verify milestone when fear reaches 70."""
        relationship_manager.update_attitude(
            npc.id, player.id, "fear", 70, "Witnessed player's terrible power"
        )

        milestones = relationship_manager.get_recent_milestones(npc.id, player.id)

        assert any(m.milestone_type == "terrified" for m in milestones)


class TestMilestoneNotifications:
    """Tests for milestone notification tracking."""

    def test_get_pending_notifications(
        self,
        relationship_manager: RelationshipManager,
        player: Entity,
        npc: Entity,
    ):
        """Verify getting unnotified milestones."""
        # Create a milestone
        relationship_manager.update_attitude(
            npc.id, player.id, "familiarity", 60, "Time together"
        )
        relationship_manager.update_attitude(
            npc.id, player.id, "trust", 25, "Earned trust"
        )

        pending = relationship_manager.get_pending_milestone_notifications(player.id)

        assert len(pending) >= 1
        assert all(m.notified is False for m in pending)

    def test_mark_milestone_notified(
        self,
        relationship_manager: RelationshipManager,
        player: Entity,
        npc: Entity,
    ):
        """Verify marking milestones as notified."""
        relationship_manager.update_attitude(
            npc.id, player.id, "familiarity", 60, "Time together"
        )
        relationship_manager.update_attitude(
            npc.id, player.id, "trust", 25, "Trust earned"
        )

        # Get pending and mark them notified
        pending = relationship_manager.get_pending_milestone_notifications(player.id)
        for m in pending:
            relationship_manager.mark_milestone_notified(m.id)

        # Should be no pending now
        pending_after = relationship_manager.get_pending_milestone_notifications(
            player.id
        )
        assert len(pending_after) == 0

    def test_milestone_includes_entity_names(
        self,
        relationship_manager: RelationshipManager,
        player: Entity,
        npc: Entity,
    ):
        """Verify milestones include entity names for display."""
        relationship_manager.update_attitude(
            npc.id, player.id, "familiarity", 60, "Time together"
        )
        relationship_manager.update_attitude(
            npc.id, player.id, "trust", 25, "Trust earned"
        )

        milestones = relationship_manager.get_recent_milestones(npc.id, player.id)

        assert milestones[0].from_entity_name is not None
        assert milestones[0].to_entity_name is not None


class TestNoDuplicateMilestones:
    """Tests for preventing duplicate milestones."""

    def test_no_duplicate_on_repeated_threshold_crossing(
        self,
        relationship_manager: RelationshipManager,
        player: Entity,
        npc: Entity,
    ):
        """Verify same milestone isn't recorded twice."""
        # Cross trust threshold
        relationship_manager.update_attitude(
            npc.id, player.id, "familiarity", 60, "Time"
        )
        relationship_manager.update_attitude(
            npc.id, player.id, "trust", 25, "First trust boost"
        )

        # Trust is now 75, increase more - shouldn't create another milestone
        relationship_manager.update_attitude(
            npc.id, player.id, "trust", 10, "Another trust boost"
        )

        milestones = relationship_manager.get_recent_milestones(npc.id, player.id)
        trust_milestones = [m for m in milestones if m.milestone_type == "earned_trust"]

        assert len(trust_milestones) == 1

    def test_milestone_resets_after_losing_and_regaining(
        self,
        relationship_manager: RelationshipManager,
        player: Entity,
        npc: Entity,
    ):
        """Verify milestone can be earned again after losing it."""
        relationship_manager.update_attitude(
            npc.id, player.id, "familiarity", 60, "Time"
        )
        # Earn trust
        relationship_manager.update_attitude(
            npc.id, player.id, "trust", 25, "First trust"
        )

        # Lose trust
        relationship_manager.update_attitude(
            npc.id, player.id, "trust", -50, "Betrayal"
        )

        # Clear notifications
        for m in relationship_manager.get_pending_milestone_notifications(player.id):
            relationship_manager.mark_milestone_notified(m.id)

        # Regain trust
        relationship_manager.update_attitude(
            npc.id, player.id, "trust", 50, "Redemption"
        )

        # Should have new earned_trust milestone
        milestones = relationship_manager.get_recent_milestones(npc.id, player.id)
        trust_milestones = [m for m in milestones if m.milestone_type == "earned_trust"]

        # Should have 2 - original and new one
        assert len(trust_milestones) == 2


class TestMilestoneContext:
    """Tests for milestone context generation."""

    def test_get_milestone_context(
        self,
        relationship_manager: RelationshipManager,
        player: Entity,
        npc: Entity,
    ):
        """Verify milestone context generation."""
        relationship_manager.update_attitude(
            npc.id, player.id, "familiarity", 60, "Time together"
        )
        relationship_manager.update_attitude(
            npc.id, player.id, "trust", 25, "Trust earned"
        )

        context = relationship_manager.get_milestone_context(player.id)

        assert "milestone" in context.lower() or "trust" in context.lower()

    def test_milestone_context_empty_when_all_notified(
        self,
        relationship_manager: RelationshipManager,
        player: Entity,
        npc: Entity,
    ):
        """Verify empty context when no pending milestones."""
        context = relationship_manager.get_milestone_context(player.id)
        assert context == ""


class TestMilestoneMessages:
    """Tests for milestone message generation."""

    def test_earned_trust_message(
        self,
        relationship_manager: RelationshipManager,
        player: Entity,
        npc: Entity,
    ):
        """Verify earned trust generates appropriate message."""
        relationship_manager.update_attitude(
            npc.id, player.id, "familiarity", 60, "Time"
        )
        relationship_manager.update_attitude(
            npc.id, player.id, "trust", 25, "Trust earned"
        )

        milestones = relationship_manager.get_recent_milestones(npc.id, player.id)
        trust_milestone = next(
            m for m in milestones if m.milestone_type == "earned_trust"
        )

        assert trust_milestone.message is not None
        assert "trust" in trust_milestone.message.lower()

    def test_became_friends_message(
        self,
        relationship_manager: RelationshipManager,
        player: Entity,
        npc: Entity,
    ):
        """Verify friendship milestone generates appropriate message."""
        relationship_manager.update_attitude(
            npc.id, player.id, "familiarity", 60, "Time"
        )
        relationship_manager.update_attitude(
            npc.id, player.id, "liking", 25, "Bonding"
        )

        milestones = relationship_manager.get_recent_milestones(npc.id, player.id)
        friend_milestones = [m for m in milestones if m.milestone_type == "became_friends"]

        if friend_milestones:
            assert "friend" in friend_milestones[0].message.lower()


class TestBidirectionalMilestones:
    """Tests for milestones involving both parties."""

    def test_milestone_for_npc_toward_player(
        self,
        relationship_manager: RelationshipManager,
        player: Entity,
        npc: Entity,
    ):
        """Verify milestones track NPC's feelings toward player."""
        # NPC trusts player
        relationship_manager.update_attitude(
            npc.id, player.id, "familiarity", 60, "Time"
        )
        relationship_manager.update_attitude(
            npc.id, player.id, "trust", 25, "Player helped"
        )

        milestones = relationship_manager.get_recent_milestones(npc.id, player.id)

        assert len(milestones) >= 1
        # Milestone is from NPC's perspective
        milestone = milestones[0]
        assert milestone.from_entity_id == npc.id
        assert milestone.to_entity_id == player.id

    def test_mutual_milestones_tracked_separately(
        self,
        relationship_manager: RelationshipManager,
        player: Entity,
        npc: Entity,
    ):
        """Verify each direction tracks milestones independently."""
        # NPC trusts player
        relationship_manager.update_attitude(
            npc.id, player.id, "familiarity", 60, "Time"
        )
        relationship_manager.update_attitude(
            npc.id, player.id, "trust", 25, "NPC trusts player"
        )

        # Player trusts NPC
        relationship_manager.update_attitude(
            player.id, npc.id, "familiarity", 60, "Time"
        )
        relationship_manager.update_attitude(
            player.id, npc.id, "trust", 25, "Player trusts NPC"
        )

        npc_milestones = relationship_manager.get_recent_milestones(npc.id, player.id)
        player_milestones = relationship_manager.get_recent_milestones(
            player.id, npc.id
        )

        assert len(npc_milestones) >= 1
        assert len(player_milestones) >= 1
