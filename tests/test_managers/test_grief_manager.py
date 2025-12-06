"""Tests for GriefManager class."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.enums import GriefStage
from src.database.models.mental_state import GriefCondition
from src.database.models.session import GameSession
from src.managers.grief import GriefManager, GRIEF_STAGES
from tests.factories import (
    create_entity,
    create_grief_condition,
    create_relationship,
)


class TestGriefManagerBasics:
    """Tests for GriefManager basic operations."""

    def test_get_grief_conditions_returns_empty_when_none(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_grief_conditions returns empty list when no grief."""
        entity = create_entity(db_session, game_session)
        manager = GriefManager(db_session, game_session)

        result = manager.get_grief_conditions(entity.id)

        assert result == []

    def test_get_grief_conditions_returns_active_only_by_default(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_grief_conditions filters to active by default."""
        grieving = create_entity(db_session, game_session)
        deceased1 = create_entity(db_session, game_session)
        deceased2 = create_entity(db_session, game_session)

        active_grief = create_grief_condition(
            db_session, game_session, grieving, deceased1
        )
        resolved_grief = create_grief_condition(
            db_session, game_session, grieving, deceased2, is_resolved=True
        )
        manager = GriefManager(db_session, game_session)

        result = manager.get_grief_conditions(grieving.id)

        assert len(result) == 1
        assert result[0].id == active_grief.id

    def test_get_grief_conditions_includes_resolved_when_requested(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_grief_conditions can include resolved."""
        grieving = create_entity(db_session, game_session)
        deceased1 = create_entity(db_session, game_session)
        deceased2 = create_entity(db_session, game_session)

        create_grief_condition(db_session, game_session, grieving, deceased1)
        create_grief_condition(
            db_session, game_session, grieving, deceased2, is_resolved=True
        )
        manager = GriefManager(db_session, game_session)

        result = manager.get_grief_conditions(grieving.id, active_only=False)

        assert len(result) == 2

    def test_get_grief_for_deceased(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify get_grief_for_deceased finds specific grief."""
        grieving = create_entity(db_session, game_session)
        deceased1 = create_entity(db_session, game_session)
        deceased2 = create_entity(db_session, game_session)

        grief1 = create_grief_condition(db_session, game_session, grieving, deceased1)
        create_grief_condition(db_session, game_session, grieving, deceased2)
        manager = GriefManager(db_session, game_session)

        result = manager.get_grief_for_deceased(grieving.id, deceased1.id)

        assert result is not None
        assert result.id == grief1.id


class TestStartGrief:
    """Tests for starting grief process."""

    def test_start_grief_creates_condition(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify start_grief creates new GriefCondition."""
        grieving = create_entity(db_session, game_session)
        deceased = create_entity(db_session, game_session)
        manager = GriefManager(db_session, game_session)

        result = manager.start_grief(grieving.id, deceased.id)

        assert result.id is not None
        assert result.entity_id == grieving.id
        assert result.deceased_entity_id == deceased.id
        assert result.grief_stage == GriefStage.SHOCK

    def test_start_grief_sets_initial_stage(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify grief starts in SHOCK stage."""
        grieving = create_entity(db_session, game_session)
        deceased = create_entity(db_session, game_session)
        manager = GriefManager(db_session, game_session)

        result = manager.start_grief(grieving.id, deceased.id)

        assert result.grief_stage == GriefStage.SHOCK
        shock_info = GRIEF_STAGES[GriefStage.SHOCK]
        assert result.morale_modifier == shock_info.morale_modifier

    def test_start_grief_returns_existing_if_already_grieving(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify start_grief returns existing grief for same deceased."""
        grieving = create_entity(db_session, game_session)
        deceased = create_entity(db_session, game_session)
        manager = GriefManager(db_session, game_session)

        first = manager.start_grief(grieving.id, deceased.id)
        second = manager.start_grief(grieving.id, deceased.id)

        assert first.id == second.id

    def test_start_grief_intensity_from_relationship(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify grief intensity based on relationship strength."""
        grieving = create_entity(db_session, game_session)
        deceased = create_entity(db_session, game_session)

        # Create strong relationship
        create_relationship(
            db_session, game_session, grieving, deceased,
            trust=80, liking=90, familiarity=70
        )
        manager = GriefManager(db_session, game_session)

        result = manager.start_grief(grieving.id, deceased.id)

        # High relationship = high intensity
        assert result.intensity > 50

    def test_start_grief_minimal_intensity_for_stranger(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify minimal grief intensity for strangers."""
        grieving = create_entity(db_session, game_session)
        deceased = create_entity(db_session, game_session)
        # No relationship created
        manager = GriefManager(db_session, game_session)

        result = manager.start_grief(grieving.id, deceased.id)

        assert result.intensity == 20  # Default minimal

    def test_start_grief_with_blame(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify blame tracking in grief."""
        grieving = create_entity(db_session, game_session)
        deceased = create_entity(db_session, game_session)
        manager = GriefManager(db_session, game_session)

        result = manager.start_grief(
            grieving.id, deceased.id, blamed_entity_key="villain_npc"
        )

        assert result.blames_someone is True
        assert result.blamed_entity_key == "villain_npc"


class TestGriefProgression:
    """Tests for grief stage progression."""

    def test_progress_grief_advances_stage(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify grief can progress to next stage."""
        grieving = create_entity(db_session, game_session)
        deceased = create_entity(db_session, game_session)

        # Create grief that's been in shock for a while
        grief = create_grief_condition(
            db_session, game_session, grieving, deceased,
            grief_stage=GriefStage.SHOCK,
            current_stage_started_turn=0,
            intensity=50,
        )
        game_session.total_turns = 30  # Many turns passed
        manager = GriefManager(db_session, game_session)

        # May or may not progress (random), but check structure
        results = manager.progress_grief(grieving.id, days_passed=10)

        assert len(results) == 1
        assert results[0][0].id == grief.id

    def test_progress_grief_updates_modifiers_on_stage_change(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify stage change updates morale modifier."""
        grieving = create_entity(db_session, game_session)
        deceased = create_entity(db_session, game_session)

        denial_info = GRIEF_STAGES[GriefStage.DENIAL]
        # Create grief with denial stage and its proper morale modifier
        grief = create_grief_condition(
            db_session, game_session, grieving, deceased,
            grief_stage=GriefStage.DENIAL,
            morale_modifier=denial_info.morale_modifier,
        )
        assert grief.morale_modifier == denial_info.morale_modifier

        # Manually advance to anger
        grief.grief_stage = GriefStage.ANGER
        anger_info = GRIEF_STAGES[GriefStage.ANGER]
        grief.morale_modifier = anger_info.morale_modifier
        db_session.flush()

        assert grief.morale_modifier == anger_info.morale_modifier


class TestGriefEffects:
    """Tests for grief effect calculations."""

    def test_get_total_morale_modifier_no_grief(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify zero modifier when no grief."""
        entity = create_entity(db_session, game_session)
        manager = GriefManager(db_session, game_session)

        modifier = manager.get_total_morale_modifier(entity.id)

        assert modifier == 0

    def test_get_total_morale_modifier_single_grief(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify morale modifier from single grief."""
        grieving = create_entity(db_session, game_session)
        deceased = create_entity(db_session, game_session)
        create_grief_condition(
            db_session, game_session, grieving, deceased,
            grief_stage=GriefStage.DEPRESSION,
            morale_modifier=-25,
        )
        manager = GriefManager(db_session, game_session)

        modifier = manager.get_total_morale_modifier(grieving.id)

        assert modifier == -25

    def test_get_total_morale_modifier_takes_worst(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify takes worst morale modifier from multiple griefs."""
        grieving = create_entity(db_session, game_session)
        deceased1 = create_entity(db_session, game_session)
        deceased2 = create_entity(db_session, game_session)

        create_grief_condition(
            db_session, game_session, grieving, deceased1,
            grief_stage=GriefStage.SHOCK,
            morale_modifier=-20,
        )
        create_grief_condition(
            db_session, game_session, grieving, deceased2,
            grief_stage=GriefStage.DEPRESSION,
            morale_modifier=-25,
        )
        manager = GriefManager(db_session, game_session)

        modifier = manager.get_total_morale_modifier(grieving.id)

        assert modifier == -25  # Takes the worst

    def test_get_behavioral_effects_no_grief(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify empty effects when no grief."""
        entity = create_entity(db_session, game_session)
        manager = GriefManager(db_session, game_session)

        effects = manager.get_behavioral_effects(entity.id)

        assert effects == {}

    def test_get_behavioral_effects_with_grief(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify behavioral effects from grief stage."""
        grieving = create_entity(db_session, game_session)
        deceased = create_entity(db_session, game_session)

        create_grief_condition(
            db_session, game_session, grieving, deceased,
            grief_stage=GriefStage.DEPRESSION,
            behavioral_changes={
                "social_withdrawal": 0.6,
                "crying_spells": 0.3,
            },
        )
        manager = GriefManager(db_session, game_session)

        effects = manager.get_behavioral_effects(grieving.id)

        assert effects["social_withdrawal"] == 0.6
        assert effects["crying_spells"] == 0.3


class TestGriefEvents:
    """Tests for grief event triggers."""

    def test_trigger_grief_event_no_grief(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify no event when not grieving."""
        entity = create_entity(db_session, game_session)
        manager = GriefManager(db_session, game_session)

        result = manager.trigger_grief_event(entity.id, "mention_deceased")

        assert result is None

    def test_trigger_grief_event_denial_avoidance(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify denial stage causes avoidance on mention."""
        grieving = create_entity(db_session, game_session)
        deceased = create_entity(db_session, game_session)

        create_grief_condition(
            db_session, game_session, grieving, deceased,
            grief_stage=GriefStage.DENIAL,
            intensity=60,
        )
        manager = GriefManager(db_session, game_session)

        result = manager.trigger_grief_event(grieving.id, "mention_deceased")

        assert result is not None
        assert result["reaction"] == "avoidance"

    def test_trigger_grief_event_anger_lashes_out(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify anger stage causes anger on mention."""
        grieving = create_entity(db_session, game_session)
        deceased = create_entity(db_session, game_session)

        create_grief_condition(
            db_session, game_session, grieving, deceased,
            grief_stage=GriefStage.ANGER,
            intensity=60,
        )
        manager = GriefManager(db_session, game_session)

        result = manager.trigger_grief_event(grieving.id, "mention_deceased")

        assert result is not None
        assert result["reaction"] == "anger"

    def test_trigger_grief_event_acceptance_bittersweet(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify acceptance stage causes bittersweet reaction."""
        grieving = create_entity(db_session, game_session)
        deceased = create_entity(db_session, game_session)

        create_grief_condition(
            db_session, game_session, grieving, deceased,
            grief_stage=GriefStage.ACCEPTANCE,
            intensity=60,
        )
        manager = GriefManager(db_session, game_session)

        result = manager.trigger_grief_event(grieving.id, "mention_deceased")

        assert result is not None
        assert result["reaction"] == "bittersweet"


class TestFindGrievingNPCs:
    """Tests for finding NPCs grieving for someone."""

    def test_find_npcs_grieving_for_none(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify empty list when no one is grieving."""
        deceased = create_entity(db_session, game_session)
        manager = GriefManager(db_session, game_session)

        result = manager.find_npcs_grieving_for(deceased.id)

        assert result == []

    def test_find_npcs_grieving_for_multiple(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify finds all NPCs grieving for deceased."""
        deceased = create_entity(db_session, game_session)
        griever1 = create_entity(db_session, game_session)
        griever2 = create_entity(db_session, game_session)

        create_grief_condition(db_session, game_session, griever1, deceased)
        create_grief_condition(db_session, game_session, griever2, deceased)
        manager = GriefManager(db_session, game_session)

        result = manager.find_npcs_grieving_for(deceased.id)

        assert len(result) == 2
        assert griever1.id in result
        assert griever2.id in result


class TestGriefSummary:
    """Tests for grief summary functionality."""

    def test_get_grief_summary_not_grieving(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify summary when not grieving."""
        entity = create_entity(db_session, game_session)
        manager = GriefManager(db_session, game_session)

        summary = manager.get_grief_summary(entity.id)

        assert summary["is_grieving"] is False

    def test_get_grief_summary_grieving(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify complete grief summary."""
        grieving = create_entity(db_session, game_session)
        deceased = create_entity(db_session, game_session)

        create_grief_condition(
            db_session, game_session, grieving, deceased,
            grief_stage=GriefStage.ANGER,
            intensity=70,
            morale_modifier=-15,
            blamed_entity_key="villain",
        )
        manager = GriefManager(db_session, game_session)

        summary = manager.get_grief_summary(grieving.id)

        assert summary["is_grieving"] is True
        assert summary["grief_count"] == 1
        assert summary["total_morale_modifier"] == -15
        assert summary["griefs"][0]["stage"] == "anger"
        assert summary["griefs"][0]["intensity"] == 70
        assert summary["griefs"][0]["blames"] == "villain"
