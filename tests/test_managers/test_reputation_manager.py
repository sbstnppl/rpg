"""Tests for ReputationManager - faction reputation tracking."""

import pytest
from sqlalchemy.orm import Session

from src.database.models import Entity, EntityType, GameSession
from src.database.models.faction import Faction, ReputationTier
from src.managers.reputation_manager import (
    ReputationManager,
    ReputationChange,
    FactionStanding,
)
from tests.factories import create_entity


@pytest.fixture
def reputation_manager(
    db_session: Session, game_session: GameSession
) -> ReputationManager:
    """Create a ReputationManager instance."""
    return ReputationManager(db_session, game_session)


@pytest.fixture
def player(db_session: Session, game_session: GameSession) -> Entity:
    """Create a player entity."""
    return create_entity(
        db_session,
        game_session,
        entity_key="hero",
        entity_type=EntityType.PLAYER,
    )


class TestCreateFaction:
    """Tests for faction creation."""

    def test_create_faction(
        self,
        reputation_manager: ReputationManager,
        db_session: Session,
    ):
        """Verify faction creation."""
        faction = reputation_manager.create_faction(
            faction_key="thieves_guild",
            name="Thieves Guild",
            description="A secretive organization of rogues",
        )

        assert faction.faction_key == "thieves_guild"
        assert faction.name == "Thieves Guild"
        assert faction.description == "A secretive organization of rogues"

    def test_create_faction_with_base_reputation(
        self,
        reputation_manager: ReputationManager,
    ):
        """Verify faction creation with custom base reputation."""
        faction = reputation_manager.create_faction(
            faction_key="royal_guard",
            name="Royal Guard",
            description="Elite protectors of the crown",
            base_reputation=25,  # Slightly positive by default
        )

        assert faction.base_reputation == 25

    def test_create_faction_with_hostility(
        self,
        reputation_manager: ReputationManager,
    ):
        """Verify faction creation with hostile default."""
        faction = reputation_manager.create_faction(
            faction_key="bandits",
            name="Bandit Clan",
            description="Outlaws who prey on travelers",
            base_reputation=-50,
            is_hostile_by_default=True,
        )

        assert faction.base_reputation == -50
        assert faction.is_hostile_by_default is True

    def test_get_faction(
        self,
        reputation_manager: ReputationManager,
    ):
        """Verify faction retrieval."""
        reputation_manager.create_faction(
            faction_key="merchants",
            name="Merchant League",
            description="Guild of traders",
        )

        faction = reputation_manager.get_faction("merchants")

        assert faction is not None
        assert faction.name == "Merchant League"

    def test_get_faction_not_found(
        self,
        reputation_manager: ReputationManager,
    ):
        """Verify None returned for non-existent faction."""
        faction = reputation_manager.get_faction("nonexistent")
        assert faction is None

    def test_get_all_factions(
        self,
        reputation_manager: ReputationManager,
    ):
        """Verify getting all factions."""
        reputation_manager.create_faction("faction1", "Faction 1", "Desc 1")
        reputation_manager.create_faction("faction2", "Faction 2", "Desc 2")
        reputation_manager.create_faction("faction3", "Faction 3", "Desc 3")

        factions = reputation_manager.get_all_factions()

        assert len(factions) == 3


class TestReputationTracking:
    """Tests for reputation tracking."""

    def test_get_reputation_default(
        self,
        reputation_manager: ReputationManager,
        player: Entity,
    ):
        """Verify default reputation for new entity-faction pair."""
        reputation_manager.create_faction(
            "guild", "Guild", "A guild", base_reputation=0
        )

        rep = reputation_manager.get_reputation("hero", "guild")

        assert rep == 0  # Default neutral

    def test_get_reputation_with_base(
        self,
        reputation_manager: ReputationManager,
        player: Entity,
    ):
        """Verify reputation uses faction's base reputation."""
        reputation_manager.create_faction(
            "friendly_faction", "Friendly Faction", "They like everyone",
            base_reputation=25,
        )

        rep = reputation_manager.get_reputation("hero", "friendly_faction")

        assert rep == 25

    def test_adjust_reputation_positive(
        self,
        reputation_manager: ReputationManager,
        player: Entity,
    ):
        """Verify positive reputation adjustment."""
        reputation_manager.create_faction("guild", "Guild", "A guild")

        result = reputation_manager.adjust_reputation(
            entity_key="hero",
            faction_key="guild",
            delta=20,
            reason="Helped guild member",
        )

        assert result.new_reputation == 20
        assert result.delta == 20
        assert result.reason == "Helped guild member"

    def test_adjust_reputation_negative(
        self,
        reputation_manager: ReputationManager,
        player: Entity,
    ):
        """Verify negative reputation adjustment."""
        reputation_manager.create_faction("guild", "Guild", "A guild")

        result = reputation_manager.adjust_reputation(
            entity_key="hero",
            faction_key="guild",
            delta=-30,
            reason="Stole from guild vault",
        )

        assert result.new_reputation == -30
        assert result.delta == -30

    def test_reputation_clamped_to_100(
        self,
        reputation_manager: ReputationManager,
        player: Entity,
    ):
        """Verify reputation capped at 100."""
        reputation_manager.create_faction("guild", "Guild", "A guild")
        reputation_manager.adjust_reputation("hero", "guild", 80, "Good deeds")

        result = reputation_manager.adjust_reputation(
            "hero", "guild", 50, "More good deeds"
        )

        assert result.new_reputation == 100

    def test_reputation_clamped_to_negative_100(
        self,
        reputation_manager: ReputationManager,
        player: Entity,
    ):
        """Verify reputation floor at -100."""
        reputation_manager.create_faction("guild", "Guild", "A guild")
        reputation_manager.adjust_reputation("hero", "guild", -80, "Bad deeds")

        result = reputation_manager.adjust_reputation(
            "hero", "guild", -50, "More bad deeds"
        )

        assert result.new_reputation == -100

    def test_adjust_reputation_nonexistent_faction(
        self,
        reputation_manager: ReputationManager,
        player: Entity,
    ):
        """Verify error when faction not found."""
        with pytest.raises(ValueError, match="Faction.*not found"):
            reputation_manager.adjust_reputation("hero", "nonexistent", 10, "Test")

    def test_adjust_reputation_nonexistent_entity(
        self,
        reputation_manager: ReputationManager,
    ):
        """Verify error when entity not found."""
        reputation_manager.create_faction("guild", "Guild", "A guild")

        with pytest.raises(ValueError, match="Entity.*not found"):
            reputation_manager.adjust_reputation("nonexistent", "guild", 10, "Test")


class TestReputationTiers:
    """Tests for reputation tier calculations."""

    def test_tier_hated(
        self,
        reputation_manager: ReputationManager,
        player: Entity,
    ):
        """Verify Hated tier at very low reputation."""
        reputation_manager.create_faction("guild", "Guild", "A guild")
        reputation_manager.adjust_reputation("hero", "guild", -80, "War")

        tier = reputation_manager.get_reputation_tier("hero", "guild")

        assert tier == ReputationTier.HATED

    def test_tier_hostile(
        self,
        reputation_manager: ReputationManager,
        player: Entity,
    ):
        """Verify Hostile tier."""
        reputation_manager.create_faction("guild", "Guild", "A guild")
        reputation_manager.adjust_reputation("hero", "guild", -50, "Conflict")

        tier = reputation_manager.get_reputation_tier("hero", "guild")

        assert tier == ReputationTier.HOSTILE

    def test_tier_unfriendly(
        self,
        reputation_manager: ReputationManager,
        player: Entity,
    ):
        """Verify Unfriendly tier."""
        reputation_manager.create_faction("guild", "Guild", "A guild")
        reputation_manager.adjust_reputation("hero", "guild", -25, "Tensions")

        tier = reputation_manager.get_reputation_tier("hero", "guild")

        assert tier == ReputationTier.UNFRIENDLY

    def test_tier_neutral(
        self,
        reputation_manager: ReputationManager,
        player: Entity,
    ):
        """Verify Neutral tier at 0 reputation."""
        reputation_manager.create_faction("guild", "Guild", "A guild")

        tier = reputation_manager.get_reputation_tier("hero", "guild")

        assert tier == ReputationTier.NEUTRAL

    def test_tier_friendly(
        self,
        reputation_manager: ReputationManager,
        player: Entity,
    ):
        """Verify Friendly tier."""
        reputation_manager.create_faction("guild", "Guild", "A guild")
        reputation_manager.adjust_reputation("hero", "guild", 25, "Helped")

        tier = reputation_manager.get_reputation_tier("hero", "guild")

        assert tier == ReputationTier.FRIENDLY

    def test_tier_honored(
        self,
        reputation_manager: ReputationManager,
        player: Entity,
    ):
        """Verify Honored tier."""
        reputation_manager.create_faction("guild", "Guild", "A guild")
        reputation_manager.adjust_reputation("hero", "guild", 50, "Great deeds")

        tier = reputation_manager.get_reputation_tier("hero", "guild")

        assert tier == ReputationTier.HONORED

    def test_tier_revered(
        self,
        reputation_manager: ReputationManager,
        player: Entity,
    ):
        """Verify Revered tier."""
        reputation_manager.create_faction("guild", "Guild", "A guild")
        reputation_manager.adjust_reputation("hero", "guild", 75, "Legendary")

        tier = reputation_manager.get_reputation_tier("hero", "guild")

        assert tier == ReputationTier.REVERED

    def test_tier_exalted(
        self,
        reputation_manager: ReputationManager,
        player: Entity,
    ):
        """Verify Exalted tier at max reputation."""
        reputation_manager.create_faction("guild", "Guild", "A guild")
        reputation_manager.adjust_reputation("hero", "guild", 100, "Savior")

        tier = reputation_manager.get_reputation_tier("hero", "guild")

        assert tier == ReputationTier.EXALTED


class TestFactionStanding:
    """Tests for faction standing (ally/neutral/enemy)."""

    def test_standing_ally(
        self,
        reputation_manager: ReputationManager,
        player: Entity,
    ):
        """Verify ally standing at high reputation."""
        reputation_manager.create_faction("guild", "Guild", "A guild")
        reputation_manager.adjust_reputation("hero", "guild", 50, "Allied")

        standing = reputation_manager.get_faction_standing("hero", "guild")

        assert standing.is_ally is True
        assert standing.is_enemy is False
        assert standing.is_neutral is False

    def test_standing_enemy(
        self,
        reputation_manager: ReputationManager,
        player: Entity,
    ):
        """Verify enemy standing at low reputation."""
        reputation_manager.create_faction("guild", "Guild", "A guild")
        reputation_manager.adjust_reputation("hero", "guild", -50, "War")

        standing = reputation_manager.get_faction_standing("hero", "guild")

        assert standing.is_ally is False
        assert standing.is_enemy is True
        assert standing.is_neutral is False

    def test_standing_neutral(
        self,
        reputation_manager: ReputationManager,
        player: Entity,
    ):
        """Verify neutral standing at 0 reputation."""
        reputation_manager.create_faction("guild", "Guild", "A guild")

        standing = reputation_manager.get_faction_standing("hero", "guild")

        assert standing.is_ally is False
        assert standing.is_enemy is False
        assert standing.is_neutral is True

    def test_standing_hostile_by_default(
        self,
        reputation_manager: ReputationManager,
        player: Entity,
    ):
        """Verify hostile factions start as enemies."""
        reputation_manager.create_faction(
            "bandits", "Bandits", "Outlaws",
            base_reputation=-50,
            is_hostile_by_default=True,
        )

        standing = reputation_manager.get_faction_standing("hero", "bandits")

        assert standing.is_enemy is True


class TestFactionRelationships:
    """Tests for inter-faction relationships."""

    def test_set_faction_relationship(
        self,
        reputation_manager: ReputationManager,
    ):
        """Verify setting relationship between factions."""
        reputation_manager.create_faction("guild1", "Guild 1", "First guild")
        reputation_manager.create_faction("guild2", "Guild 2", "Second guild")

        reputation_manager.set_faction_relationship(
            faction1_key="guild1",
            faction2_key="guild2",
            relationship="rival",
            mutual=True,
        )

        rel = reputation_manager.get_faction_relationship("guild1", "guild2")
        assert rel == "rival"

    def test_faction_relationship_mutual(
        self,
        reputation_manager: ReputationManager,
    ):
        """Verify mutual faction relationships."""
        reputation_manager.create_faction("guild1", "Guild 1", "First")
        reputation_manager.create_faction("guild2", "Guild 2", "Second")

        reputation_manager.set_faction_relationship(
            "guild1", "guild2", "ally", mutual=True
        )

        # Both directions should be set
        assert reputation_manager.get_faction_relationship("guild1", "guild2") == "ally"
        assert reputation_manager.get_faction_relationship("guild2", "guild1") == "ally"

    def test_faction_relationship_one_way(
        self,
        reputation_manager: ReputationManager,
    ):
        """Verify one-way faction relationships."""
        reputation_manager.create_faction("guild1", "Guild 1", "First")
        reputation_manager.create_faction("guild2", "Guild 2", "Second")

        reputation_manager.set_faction_relationship(
            "guild1", "guild2", "vassal", mutual=False
        )

        assert reputation_manager.get_faction_relationship("guild1", "guild2") == "vassal"
        assert reputation_manager.get_faction_relationship("guild2", "guild1") is None

    def test_get_allied_factions(
        self,
        reputation_manager: ReputationManager,
    ):
        """Verify getting allied factions."""
        reputation_manager.create_faction("main", "Main Guild", "Main")
        reputation_manager.create_faction("ally1", "Ally 1", "First ally")
        reputation_manager.create_faction("ally2", "Ally 2", "Second ally")
        reputation_manager.create_faction("rival", "Rival", "A rival")

        reputation_manager.set_faction_relationship("main", "ally1", "ally", mutual=True)
        reputation_manager.set_faction_relationship("main", "ally2", "ally", mutual=True)
        reputation_manager.set_faction_relationship("main", "rival", "rival", mutual=True)

        allies = reputation_manager.get_allied_factions("main")

        assert len(allies) == 2
        ally_keys = [f.faction_key for f in allies]
        assert "ally1" in ally_keys
        assert "ally2" in ally_keys

    def test_get_rival_factions(
        self,
        reputation_manager: ReputationManager,
    ):
        """Verify getting rival factions."""
        reputation_manager.create_faction("main", "Main Guild", "Main")
        reputation_manager.create_faction("rival1", "Rival 1", "First rival")
        reputation_manager.create_faction("ally", "Ally", "An ally")

        reputation_manager.set_faction_relationship("main", "rival1", "rival", mutual=True)
        reputation_manager.set_faction_relationship("main", "ally", "ally", mutual=True)

        rivals = reputation_manager.get_rival_factions("main")

        assert len(rivals) == 1
        assert rivals[0].faction_key == "rival1"


class TestReputationContext:
    """Tests for reputation context generation."""

    def test_get_reputation_context(
        self,
        reputation_manager: ReputationManager,
        player: Entity,
    ):
        """Verify reputation context generation."""
        reputation_manager.create_faction("guild", "Thieves Guild", "Rogues")
        reputation_manager.adjust_reputation("hero", "guild", 50, "Joined")

        context = reputation_manager.get_reputation_context("hero")

        assert "Thieves Guild" in context
        assert "Honored" in context

    def test_reputation_context_empty(
        self,
        reputation_manager: ReputationManager,
        player: Entity,
    ):
        """Verify empty context when no factions."""
        context = reputation_manager.get_reputation_context("hero")
        assert context == ""

    def test_reputation_context_multiple_factions(
        self,
        reputation_manager: ReputationManager,
        player: Entity,
    ):
        """Verify context with multiple factions."""
        reputation_manager.create_faction("guild1", "Guild 1", "First")
        reputation_manager.create_faction("guild2", "Guild 2", "Second")
        reputation_manager.adjust_reputation("hero", "guild1", 50, "Good")
        reputation_manager.adjust_reputation("hero", "guild2", -50, "Bad")

        context = reputation_manager.get_reputation_context("hero")

        assert "Guild 1" in context
        assert "Guild 2" in context
        assert "Honored" in context
        assert "Hostile" in context


class TestReputationHistory:
    """Tests for reputation change history."""

    def test_get_reputation_history(
        self,
        reputation_manager: ReputationManager,
        player: Entity,
    ):
        """Verify reputation history retrieval."""
        reputation_manager.create_faction("guild", "Guild", "A guild")
        reputation_manager.adjust_reputation("hero", "guild", 20, "First deed")
        reputation_manager.adjust_reputation("hero", "guild", 10, "Second deed")
        reputation_manager.adjust_reputation("hero", "guild", -5, "Minor offense")

        history = reputation_manager.get_reputation_history("hero", "guild")

        assert len(history) == 3
        # Most recent first
        assert history[0].delta == -5
        assert history[1].delta == 10
        assert history[2].delta == 20

    def test_reputation_history_limit(
        self,
        reputation_manager: ReputationManager,
        player: Entity,
    ):
        """Verify reputation history limit."""
        reputation_manager.create_faction("guild", "Guild", "A guild")
        for i in range(10):
            reputation_manager.adjust_reputation("hero", "guild", 5, f"Deed {i}")

        history = reputation_manager.get_reputation_history("hero", "guild", limit=5)

        assert len(history) == 5
