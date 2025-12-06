"""Tests for FactManager class."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.enums import FactCategory
from src.database.models.session import GameSession
from src.database.models.world import Fact
from src.managers.fact_manager import FactManager
from tests.factories import create_fact


class TestFactManagerBasics:
    """Tests for FactManager basic operations."""

    def test_record_fact_creates_new(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify record_fact creates a new fact."""
        manager = FactManager(db_session, game_session)

        result = manager.record_fact(
            subject_type="entity",
            subject_key="hero",
            predicate="hometown",
            value="Rivervale",
        )

        assert result is not None
        assert result.subject_type == "entity"
        assert result.subject_key == "hero"
        assert result.predicate == "hometown"
        assert result.value == "Rivervale"
        assert result.session_id == game_session.id

    def test_record_fact_updates_existing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify record_fact updates value if fact exists."""
        create_fact(
            db_session, game_session,
            subject_type="entity",
            subject_key="merchant",
            predicate="mood",
            value="happy"
        )
        manager = FactManager(db_session, game_session)

        result = manager.record_fact(
            subject_type="entity",
            subject_key="merchant",
            predicate="mood",
            value="angry",
        )

        # Should be the same fact with updated value
        facts = db_session.query(Fact).filter(
            Fact.subject_key == "merchant",
            Fact.predicate == "mood"
        ).all()
        assert len(facts) == 1
        assert facts[0].value == "angry"

    def test_record_fact_with_category_and_secret(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify record_fact can set category and is_secret."""
        manager = FactManager(db_session, game_session)

        result = manager.record_fact(
            subject_type="entity",
            subject_key="spy",
            predicate="true_identity",
            value="Secret Agent",
            category=FactCategory.SECRET,
            is_secret=True,
        )

        assert result.category == FactCategory.SECRET
        assert result.is_secret is True


class TestFactManagerQueries:
    """Tests for fact query operations."""

    def test_get_fact_returns_none_when_missing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_fact returns None when fact doesn't exist."""
        manager = FactManager(db_session, game_session)

        result = manager.get_fact("unknown", "unknown")

        assert result is None

    def test_get_fact_returns_existing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_fact returns existing fact."""
        fact = create_fact(
            db_session, game_session,
            subject_key="knight",
            predicate="allegiance",
            value="The Crown"
        )
        manager = FactManager(db_session, game_session)

        result = manager.get_fact("knight", "allegiance")

        assert result is not None
        assert result.id == fact.id
        assert result.value == "The Crown"

    def test_get_facts_about_returns_all(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_facts_about returns all facts about a subject."""
        create_fact(
            db_session, game_session,
            subject_key="wizard",
            predicate="name",
            value="Gandalf"
        )
        create_fact(
            db_session, game_session,
            subject_key="wizard",
            predicate="specialty",
            value="Fire magic"
        )
        # Different subject
        create_fact(
            db_session, game_session,
            subject_key="warrior",
            predicate="name",
            value="Aragorn"
        )
        manager = FactManager(db_session, game_session)

        result = manager.get_facts_about("wizard")

        assert len(result) == 2
        predicates = [f.predicate for f in result]
        assert "name" in predicates
        assert "specialty" in predicates

    def test_get_facts_about_excludes_secrets_by_default(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_facts_about excludes secrets by default."""
        create_fact(
            db_session, game_session,
            subject_key="noble",
            predicate="title",
            value="Duke",
            is_secret=False
        )
        create_fact(
            db_session, game_session,
            subject_key="noble",
            predicate="secret_lover",
            value="The Maid",
            is_secret=True
        )
        manager = FactManager(db_session, game_session)

        result = manager.get_facts_about("noble", include_secrets=False)

        assert len(result) == 1
        assert result[0].predicate == "title"

    def test_get_facts_about_includes_secrets_when_requested(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_facts_about includes secrets when include_secrets=True."""
        create_fact(
            db_session, game_session,
            subject_key="noble",
            predicate="title",
            value="Duke"
        )
        create_fact(
            db_session, game_session,
            subject_key="noble",
            predicate="secret_lover",
            value="The Maid",
            is_secret=True
        )
        manager = FactManager(db_session, game_session)

        result = manager.get_facts_about("noble", include_secrets=True)

        assert len(result) == 2

    def test_get_facts_by_predicate(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_facts_by_predicate returns facts with predicate."""
        create_fact(
            db_session, game_session,
            subject_key="hero",
            predicate="allergic_to",
            value="pollen"
        )
        create_fact(
            db_session, game_session,
            subject_key="villain",
            predicate="allergic_to",
            value="sunlight"
        )
        create_fact(
            db_session, game_session,
            subject_key="hero",
            predicate="likes",
            value="adventure"
        )
        manager = FactManager(db_session, game_session)

        result = manager.get_facts_by_predicate("allergic_to")

        assert len(result) == 2
        values = [f.value for f in result]
        assert "pollen" in values
        assert "sunlight" in values

    def test_get_facts_by_category(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_facts_by_category returns facts in category."""
        create_fact(
            db_session, game_session,
            subject_key="world",
            predicate="capital",
            value="Metropolis",
            category=FactCategory.WORLD
        )
        create_fact(
            db_session, game_session,
            subject_key="hero",
            predicate="favorite_food",
            value="Pizza",
            category=FactCategory.PERSONAL
        )
        manager = FactManager(db_session, game_session)

        result = manager.get_facts_by_category(FactCategory.WORLD)

        assert len(result) == 1
        assert result[0].predicate == "capital"


class TestFactManagerSecrets:
    """Tests for secret management."""

    def test_get_secrets_returns_only_secrets(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_secrets returns only secret facts."""
        create_fact(
            db_session, game_session,
            subject_key="person",
            predicate="public_info",
            value="Known",
            is_secret=False
        )
        secret = create_fact(
            db_session, game_session,
            subject_key="person",
            predicate="hidden_info",
            value="Secret",
            is_secret=True
        )
        manager = FactManager(db_session, game_session)

        result = manager.get_secrets()

        assert len(result) == 1
        assert result[0].id == secret.id

    def test_reveal_secret_sets_is_secret_false(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify reveal_secret marks fact as no longer secret."""
        fact = create_fact(
            db_session, game_session,
            subject_key="traitor",
            predicate="identity",
            value="The Butler",
            is_secret=True
        )
        manager = FactManager(db_session, game_session)

        result = manager.reveal_secret(fact.id)

        assert result.is_secret is False

    def test_set_player_belief(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify set_player_belief sets player_believes field."""
        fact = create_fact(
            db_session, game_session,
            subject_key="artifact",
            predicate="power",
            value="Infinite"
        )
        manager = FactManager(db_session, game_session)

        result = manager.set_player_belief(fact.id, "Limited")

        assert result.value == "Infinite"  # Actual unchanged
        assert result.player_believes == "Limited"


class TestFactManagerForeshadowing:
    """Tests for foreshadowing mechanics."""

    def test_record_foreshadowing_sets_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify record_foreshadowing sets is_foreshadowing and target."""
        manager = FactManager(db_session, game_session)

        result = manager.record_foreshadowing(
            subject_key="dream",
            predicate="vision",
            value="A dark figure approaches",
            foreshadow_target="villain_reveal"
        )

        assert result.is_foreshadowing is True
        assert result.foreshadow_target == "villain_reveal"
        assert result.times_mentioned == 1

    def test_increment_mention(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify increment_mention increases times_mentioned."""
        fact = create_fact(
            db_session, game_session,
            subject_key="hint",
            predicate="clue",
            value="The clock strikes midnight",
            is_foreshadowing=True,
            times_mentioned=1
        )
        manager = FactManager(db_session, game_session)

        result = manager.increment_mention(fact.id)

        assert result.times_mentioned == 2

    def test_get_unfulfilled_foreshadowing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_unfulfilled_foreshadowing returns ripe hints."""
        # Planted 3 times - ready for payoff
        ready = create_fact(
            db_session, game_session,
            subject_key="hint1",
            predicate="clue",
            value="Ready hint",
            is_foreshadowing=True,
            times_mentioned=3
        )
        # Only planted once - not ready
        create_fact(
            db_session, game_session,
            subject_key="hint2",
            predicate="clue",
            value="Not ready hint",
            is_foreshadowing=True,
            times_mentioned=1
        )
        # Not foreshadowing
        create_fact(
            db_session, game_session,
            subject_key="regular",
            predicate="info",
            value="Regular fact",
            is_foreshadowing=False,
            times_mentioned=5
        )
        manager = FactManager(db_session, game_session)

        result = manager.get_unfulfilled_foreshadowing(min_mentions=3)

        assert len(result) == 1
        assert result[0].id == ready.id


class TestFactManagerDelete:
    """Tests for fact deletion."""

    def test_delete_fact_removes_existing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify delete_fact removes an existing fact."""
        create_fact(
            db_session, game_session,
            subject_key="temp",
            predicate="data",
            value="to delete"
        )
        manager = FactManager(db_session, game_session)

        result = manager.delete_fact("temp", "data")

        assert result is True
        # Verify it's gone
        remaining = db_session.query(Fact).filter(
            Fact.subject_key == "temp",
            Fact.predicate == "data"
        ).first()
        assert remaining is None

    def test_delete_fact_returns_false_when_missing(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify delete_fact returns False when fact doesn't exist."""
        manager = FactManager(db_session, game_session)

        result = manager.delete_fact("nonexistent", "nonexistent")

        assert result is False
