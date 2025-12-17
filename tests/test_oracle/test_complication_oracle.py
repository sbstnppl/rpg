"""Tests for the ComplicationOracle class."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.narrative import ArcPhase, ArcStatus, ArcType, StoryArc
from src.database.models.session import GameSession
from src.oracle.complication_oracle import ComplicationOracle, OracleResult
from src.oracle.complication_types import ComplicationType
from src.oracle.probability import ProbabilityCalculator


class TestComplicationOracle:
    """Tests for ComplicationOracle."""

    def test_oracle_creation(self, db_session: Session, game_session: GameSession):
        """Test creating an oracle instance."""
        oracle = ComplicationOracle(db=db_session, game_session=game_session)

        assert oracle.db == db_session
        assert oracle.game_session == game_session
        assert oracle.llm_provider is None

    def test_oracle_with_custom_calculator(
        self, db_session: Session, game_session: GameSession
    ):
        """Test creating oracle with custom probability calculator."""
        custom_calc = ProbabilityCalculator(base_chance=0.50, max_chance=0.90)

        oracle = ComplicationOracle(
            db=db_session,
            game_session=game_session,
            probability_calculator=custom_calc,
        )

        assert oracle.probability.base_chance == 0.50
        assert oracle.probability.max_chance == 0.90

    def test_get_turns_since_complication_no_history(
        self, db_session: Session, game_session: GameSession
    ):
        """Test getting turns since complication when no history exists."""
        oracle = ComplicationOracle(db=db_session, game_session=game_session)

        result = oracle.get_turns_since_complication()

        assert result is None

    @pytest.mark.asyncio
    async def test_check_returns_oracle_result(
        self, db_session: Session, game_session: GameSession
    ):
        """Test that check() returns an OracleResult."""
        oracle = ComplicationOracle(db=db_session, game_session=game_session)

        result = await oracle.check(
            actions_summary="TAKE sword",
            scene_context="A dusty tavern.",
            risk_tags=[],
        )

        assert isinstance(result, OracleResult)
        assert hasattr(result, "complication")
        assert hasattr(result, "probability")
        assert hasattr(result, "triggered")
        assert hasattr(result, "reason")

    @pytest.mark.asyncio
    async def test_check_with_high_probability(
        self, db_session: Session, game_session: GameSession
    ):
        """Test that high probability increases trigger chance."""
        # Use 100% probability to ensure trigger
        high_prob_calc = ProbabilityCalculator(base_chance=1.0, max_chance=1.0)

        oracle = ComplicationOracle(
            db=db_session,
            game_session=game_session,
            probability_calculator=high_prob_calc,
        )

        result = await oracle.check(
            actions_summary="ATTACK guard",
            scene_context="Castle courtyard.",
            risk_tags=["dangerous"],
        )

        assert result.triggered is True
        assert result.complication is not None

    @pytest.mark.asyncio
    async def test_check_with_zero_probability(
        self, db_session: Session, game_session: GameSession
    ):
        """Test that zero probability never triggers."""
        zero_prob_calc = ProbabilityCalculator(base_chance=0.0, max_chance=0.0)

        oracle = ComplicationOracle(
            db=db_session,
            game_session=game_session,
            probability_calculator=zero_prob_calc,
        )

        result = await oracle.check(
            actions_summary="TAKE gold",
            scene_context="Treasure room.",
            risk_tags=["valuable"],
        )

        assert result.triggered is False
        assert result.complication is None

    @pytest.mark.asyncio
    async def test_fallback_generation_uses_risk_tags(
        self, db_session: Session, game_session: GameSession
    ):
        """Test that fallback generation considers risk tags."""
        high_prob_calc = ProbabilityCalculator(base_chance=1.0, max_chance=1.0)

        oracle = ComplicationOracle(
            db=db_session,
            game_session=game_session,
            probability_calculator=high_prob_calc,
        )

        # Dangerous actions should trigger COST type in fallback
        result = await oracle.check(
            actions_summary="ATTACK guard",
            scene_context="Castle.",
            risk_tags=["dangerous", "aggressive"],
        )

        assert result.complication is not None
        assert result.complication.type == ComplicationType.COST

    @pytest.mark.asyncio
    async def test_fallback_generation_social_tags(
        self, db_session: Session, game_session: GameSession
    ):
        """Test fallback generation for social actions."""
        high_prob_calc = ProbabilityCalculator(base_chance=1.0, max_chance=1.0)

        oracle = ComplicationOracle(
            db=db_session,
            game_session=game_session,
            probability_calculator=high_prob_calc,
        )

        result = await oracle.check(
            actions_summary="TALK merchant",
            scene_context="Market square.",
            risk_tags=["social"],
        )

        assert result.complication is not None
        assert result.complication.type == ComplicationType.INTERRUPTION


class TestComplicationOracleWithStoryArc:
    """Tests for oracle integration with story arcs."""

    @pytest.fixture
    def story_arc(self, db_session: Session, game_session: GameSession) -> StoryArc:
        """Create a story arc for testing."""
        arc = StoryArc(
            session_id=game_session.id,
            arc_key="main_quest",
            title="The Dark Prophecy",
            arc_type=ArcType.MAIN_QUEST,
            status=ArcStatus.ACTIVE,
            current_phase=ArcPhase.CLIMAX,
            tension_level=85,
            stakes="The fate of the kingdom hangs in the balance.",
        )
        db_session.add(arc)
        db_session.flush()
        return arc

    @pytest.mark.asyncio
    async def test_oracle_uses_active_arc(
        self,
        db_session: Session,
        game_session: GameSession,
        story_arc: StoryArc,
    ):
        """Test that oracle considers active story arc."""
        high_prob_calc = ProbabilityCalculator(base_chance=1.0, max_chance=1.0)

        oracle = ComplicationOracle(
            db=db_session,
            game_session=game_session,
            probability_calculator=high_prob_calc,
        )

        result = await oracle.check(
            actions_summary="ENTER castle",
            scene_context="The final confrontation.",
            risk_tags=["dangerous"],
        )

        assert result.triggered is True
        assert result.complication is not None
        # Complication should reference the arc
        assert result.complication.source_arc_key == "main_quest"


class TestRecordComplication:
    """Tests for recording complications."""

    @pytest.mark.asyncio
    async def test_record_complication_creates_history(
        self, db_session: Session, game_session: GameSession
    ):
        """Test that recording creates history entry."""
        from src.database.models.narrative import ComplicationHistory
        from src.oracle.complication_types import Complication, ComplicationType

        oracle = ComplicationOracle(db=db_session, game_session=game_session)

        comp = Complication(
            type=ComplicationType.DISCOVERY,
            description="You find a hidden door.",
            new_facts=["Hidden door in east wall"],
        )

        await oracle.record_complication(
            complication=comp,
            turn_number=5,
            probability=0.15,
            risk_tags=["mysterious"],
        )

        # Check history was created
        history = (
            db_session.query(ComplicationHistory)
            .filter(ComplicationHistory.session_id == game_session.id)
            .first()
        )

        assert history is not None
        assert history.turn_number == 5
        assert history.description == "You find a hidden door."
        assert history.trigger_probability == 0.15

    @pytest.mark.asyncio
    async def test_record_complication_updates_turns_since(
        self, db_session: Session, game_session: GameSession
    ):
        """Test that recording updates turns_since_complication."""
        from src.oracle.complication_types import Complication, ComplicationType

        oracle = ComplicationOracle(db=db_session, game_session=game_session)
        game_session.total_turns = 10  # Set current turn

        # Initially no history
        assert oracle.get_turns_since_complication() is None

        # Record a complication
        comp = Complication(
            type=ComplicationType.COST,
            description="Minor setback.",
        )

        await oracle.record_complication(complication=comp, turn_number=7)

        # Now should have history
        turns_since = oracle.get_turns_since_complication()
        assert turns_since == 3  # 10 - 7 = 3
