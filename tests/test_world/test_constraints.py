"""Tests for Scene-First Architecture constraint system.

These tests verify:
- Social constraints (relationship limits, introduction rates)
- Physical constraints (location access, time of day)
- Event constraints (frequency, plausibility)
- Combined constraint checking
"""

import pytest

from src.world.constraints import (
    EventLimits,
    PhysicalLimits,
    RealisticConstraintChecker,
)
from src.world.schemas import (
    ConstraintResult,
    NewElement,
    NPCPlacement,
    NPCSpec,
    PresenceReason,
    SocialLimits,
    WorldEvent,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def checker() -> RealisticConstraintChecker:
    """Create a basic constraint checker with default limits."""
    return RealisticConstraintChecker()


@pytest.fixture
def strict_social_limits() -> SocialLimits:
    """Very strict social limits for testing edge cases."""
    return SocialLimits(
        max_close_friends=2,
        max_casual_friends=5,
        max_acquaintances=10,
        max_new_relationships_per_week=1,
        min_interactions_for_friendship=3,
    )


@pytest.fixture
def strict_checker(strict_social_limits: SocialLimits) -> RealisticConstraintChecker:
    """Constraint checker with strict limits."""
    return RealisticConstraintChecker(social_limits=strict_social_limits)


@pytest.fixture
def sample_npc_spec() -> NPCSpec:
    """Sample NPC specification for testing."""
    return NPCSpec(
        display_name="Elena",
        gender="female",
        occupation="scholar",
        personality_hints=["curious", "kind"],
        relationship_to_player="childhood friend",
    )


@pytest.fixture
def sample_placement(sample_npc_spec: NPCSpec) -> NPCPlacement:
    """Sample NPC placement for testing."""
    return NPCPlacement(
        new_npc=sample_npc_spec,
        presence_reason=PresenceReason.VISITING,
        presence_justification="Came to visit the player",
        activity="sitting in chair",
        mood="happy",
        position_in_scene="by the window",
    )


@pytest.fixture
def existing_npc_placement() -> NPCPlacement:
    """Placement for an existing NPC."""
    return NPCPlacement(
        entity_key="marcus_001",
        presence_reason=PresenceReason.SCHEDULE,
        presence_justification="Works here",
        activity="hammering metal",
        position_in_scene="at the forge",
    )


# =============================================================================
# Social Constraint Tests
# =============================================================================


class TestSocialConstraints:
    """Tests for social relationship constraints."""

    def test_new_npc_allowed_by_default(
        self, checker: RealisticConstraintChecker, sample_npc_spec: NPCSpec
    ) -> None:
        """Test that new NPCs are allowed with default limits."""
        result = checker.check_social_constraints(
            new_npc=sample_npc_spec,
            relationship_type="acquaintance",
        )
        assert result.allowed is True

    def test_no_new_npc_always_allowed(
        self, checker: RealisticConstraintChecker
    ) -> None:
        """Test that existing NPCs always pass social constraints."""
        result = checker.check_social_constraints(new_npc=None)
        assert result.allowed is True

    def test_close_friend_limit_exceeded(
        self, checker: RealisticConstraintChecker, sample_npc_spec: NPCSpec
    ) -> None:
        """Test rejection when close friend limit is exceeded."""
        result = checker.check_social_constraints(
            new_npc=sample_npc_spec,
            relationship_type="close_friend",
            current_close_friends=5,  # At limit
        )
        assert result.allowed is False
        assert result.violated_constraint == "max_close_friends"
        assert "suggestion" in result.model_dump()

    def test_close_friend_under_limit(
        self, checker: RealisticConstraintChecker, sample_npc_spec: NPCSpec
    ) -> None:
        """Test acceptance when under close friend limit."""
        result = checker.check_social_constraints(
            new_npc=sample_npc_spec,
            relationship_type="close_friend",
            current_close_friends=3,  # Under limit
        )
        assert result.allowed is True

    def test_casual_friend_limit_exceeded(
        self, checker: RealisticConstraintChecker, sample_npc_spec: NPCSpec
    ) -> None:
        """Test rejection when casual friend limit is exceeded."""
        result = checker.check_social_constraints(
            new_npc=sample_npc_spec,
            relationship_type="casual_friend",
            current_casual_friends=15,  # At limit
        )
        assert result.allowed is False
        assert result.violated_constraint == "max_casual_friends"

    def test_acquaintance_limit_exceeded(
        self, checker: RealisticConstraintChecker, sample_npc_spec: NPCSpec
    ) -> None:
        """Test rejection when acquaintance limit is exceeded."""
        result = checker.check_social_constraints(
            new_npc=sample_npc_spec,
            relationship_type="acquaintance",
            current_acquaintances=50,  # At limit
        )
        assert result.allowed is False
        assert result.violated_constraint == "max_acquaintances"

    def test_rate_limit_exceeded(
        self, checker: RealisticConstraintChecker, sample_npc_spec: NPCSpec
    ) -> None:
        """Test rejection when weekly rate limit is exceeded."""
        result = checker.check_social_constraints(
            new_npc=sample_npc_spec,
            relationship_type="acquaintance",
            new_relationships_this_week=3,  # At limit
        )
        assert result.allowed is False
        assert result.violated_constraint == "max_new_relationships_per_week"

    def test_strict_limits_enforced(
        self, strict_checker: RealisticConstraintChecker, sample_npc_spec: NPCSpec
    ) -> None:
        """Test that custom strict limits are enforced."""
        result = strict_checker.check_social_constraints(
            new_npc=sample_npc_spec,
            relationship_type="close_friend",
            current_close_friends=2,  # At strict limit
        )
        assert result.allowed is False

    def test_personality_adjusted_limits(
        self, sample_npc_spec: NPCSpec
    ) -> None:
        """Test extrovert personality has higher limits."""
        extrovert_limits = SocialLimits.for_player("extrovert")
        checker = RealisticConstraintChecker(social_limits=extrovert_limits)

        result = checker.check_social_constraints(
            new_npc=sample_npc_spec,
            relationship_type="close_friend",
            current_close_friends=6,  # Above default but under extrovert
        )
        assert result.allowed is True


# =============================================================================
# Physical Constraint Tests
# =============================================================================


class TestPhysicalConstraints:
    """Tests for physical plausibility constraints."""

    def test_public_location_allowed(
        self, checker: RealisticConstraintChecker, existing_npc_placement: NPCPlacement
    ) -> None:
        """Test NPCs can be in public locations."""
        result = checker.check_physical_constraints(
            npc_placement=existing_npc_placement,
            location_type="tavern",
            current_hour=12,
        )
        assert result.allowed is True

    def test_private_location_with_lives_here(
        self, checker: RealisticConstraintChecker
    ) -> None:
        """Test LIVES_HERE reason allows private location access."""
        placement = NPCPlacement(
            entity_key="owner_001",
            presence_reason=PresenceReason.LIVES_HERE,
            presence_justification="This is their home",
            activity="sleeping",
            position_in_scene="in bed",
        )
        result = checker.check_physical_constraints(
            npc_placement=placement,
            location_type="bedroom",
            is_player_home=True,
            current_hour=12,
        )
        assert result.allowed is True

    def test_private_location_visiting_rejected(
        self, checker: RealisticConstraintChecker, sample_placement: NPCPlacement
    ) -> None:
        """Test VISITING reason rejected for player's private location."""
        # sample_placement has VISITING reason
        result = checker.check_physical_constraints(
            npc_placement=sample_placement,
            location_type="bedroom",
            is_player_home=True,
            current_hour=12,
        )
        assert result.allowed is False
        assert result.violated_constraint == "private_location"

    def test_story_reason_allows_private_access(
        self, checker: RealisticConstraintChecker, sample_npc_spec: NPCSpec
    ) -> None:
        """Test STORY reason allows player's private location access."""
        placement = NPCPlacement(
            new_npc=sample_npc_spec,
            presence_reason=PresenceReason.STORY,
            presence_justification="Important story moment",
            activity="waiting",
            position_in_scene="by door",
        )
        result = checker.check_physical_constraints(
            npc_placement=placement,
            location_type="bedroom",
            is_player_home=True,
            current_hour=12,
        )
        assert result.allowed is True

    def test_event_reason_allows_private_access(
        self, checker: RealisticConstraintChecker
    ) -> None:
        """Test EVENT reason allows private location access."""
        placement = NPCPlacement(
            entity_key="thief_001",
            presence_reason=PresenceReason.EVENT,
            presence_justification="Breaking in",
            activity="searching",
            position_in_scene="by closet",
        )
        result = checker.check_physical_constraints(
            npc_placement=placement,
            location_type="bedroom",
            is_player_home=True,
            current_hour=3,  # Even at night
        )
        assert result.allowed is True

    def test_visiting_during_sleeping_hours_rejected(
        self, checker: RealisticConstraintChecker, sample_placement: NPCPlacement
    ) -> None:
        """Test visiting during sleeping hours is rejected."""
        # Test at midnight (0)
        result = checker.check_physical_constraints(
            npc_placement=sample_placement,
            location_type="tavern",  # Even public location
            current_hour=0,
        )
        assert result.allowed is False
        assert result.violated_constraint == "sleep_hours"

        # Test at 3am
        result = checker.check_physical_constraints(
            npc_placement=sample_placement,
            location_type="tavern",
            current_hour=3,
        )
        assert result.allowed is False

    def test_schedule_during_sleeping_hours_allowed(
        self, checker: RealisticConstraintChecker
    ) -> None:
        """Test SCHEDULE reason allows presence during sleeping hours."""
        placement = NPCPlacement(
            entity_key="guard_001",
            presence_reason=PresenceReason.SCHEDULE,
            presence_justification="Night shift",
            activity="patrolling",
            position_in_scene="by gate",
        )
        result = checker.check_physical_constraints(
            npc_placement=placement,
            location_type="street",
            current_hour=2,
        )
        assert result.allowed is True

    def test_visiting_too_early(
        self, checker: RealisticConstraintChecker, sample_placement: NPCPlacement
    ) -> None:
        """Test visiting before earliest visit hour rejected."""
        result = checker.check_physical_constraints(
            npc_placement=sample_placement,
            location_type="house",
            current_hour=6,  # Before 7am
        )
        assert result.allowed is False
        assert result.violated_constraint == "visiting_hours"

    def test_visiting_too_late(
        self, checker: RealisticConstraintChecker, sample_placement: NPCPlacement
    ) -> None:
        """Test visiting after latest visit hour rejected."""
        result = checker.check_physical_constraints(
            npc_placement=sample_placement,
            location_type="house",
            current_hour=22,  # At 10pm
        )
        assert result.allowed is False
        assert result.violated_constraint == "visiting_hours"

    def test_visiting_during_valid_hours(
        self, checker: RealisticConstraintChecker, sample_placement: NPCPlacement
    ) -> None:
        """Test visiting during valid hours allowed."""
        result = checker.check_physical_constraints(
            npc_placement=sample_placement,
            location_type="house",
            current_hour=14,  # 2pm
        )
        assert result.allowed is True

    def test_custom_physical_limits(self, sample_placement: NPCPlacement) -> None:
        """Test custom physical limits are enforced."""
        custom_limits = PhysicalLimits(
            earliest_visit_hour=10,
            latest_visit_hour=18,
        )
        checker = RealisticConstraintChecker(physical_limits=custom_limits)

        # 9am should be too early with custom limits
        result = checker.check_physical_constraints(
            npc_placement=sample_placement,
            location_type="house",
            current_hour=9,
        )
        assert result.allowed is False

        # 2pm should be fine
        result = checker.check_physical_constraints(
            npc_placement=sample_placement,
            location_type="house",
            current_hour=14,
        )
        assert result.allowed is True


# =============================================================================
# Event Constraint Tests
# =============================================================================


class TestEventConstraints:
    """Tests for event frequency and plausibility constraints."""

    @pytest.fixture
    def sample_event(self) -> WorldEvent:
        """Sample world event for testing."""
        return WorldEvent(
            event_type="arrival",
            event_key="arrival_001",
            description="A merchant arrives",
            npcs_involved=["merchant_001"],
            location="market",
        )

    def test_event_allowed_by_default(
        self, checker: RealisticConstraintChecker, sample_event: WorldEvent
    ) -> None:
        """Test events allowed with default constraints."""
        result = checker.check_event_constraints(event=sample_event)
        assert result.allowed is True

    def test_daily_event_limit_exceeded(
        self, checker: RealisticConstraintChecker, sample_event: WorldEvent
    ) -> None:
        """Test rejection when daily event limit exceeded."""
        result = checker.check_event_constraints(
            event=sample_event,
            events_today=3,  # At limit
        )
        assert result.allowed is False
        assert result.violated_constraint == "max_events_per_day"

    def test_event_too_soon(
        self, checker: RealisticConstraintChecker, sample_event: WorldEvent
    ) -> None:
        """Test rejection when event is too soon after last one."""
        result = checker.check_event_constraints(
            event=sample_event,
            hours_since_last_event=1.0,  # Under 2 hour minimum
        )
        assert result.allowed is False
        assert result.violated_constraint == "min_hours_between_events"

    def test_intrusion_limit_exceeded(
        self, checker: RealisticConstraintChecker
    ) -> None:
        """Test rejection when intrusion limit exceeded."""
        intrusion = WorldEvent(
            event_type="intrusion",
            event_key="intrusion_001",
            description="Break-in",
            location="home",
        )
        result = checker.check_event_constraints(
            event=intrusion,
            intrusions_this_week=2,  # At limit
        )
        assert result.allowed is False
        assert result.violated_constraint == "max_intrusions_per_week"

    def test_too_many_npcs_in_event(
        self, checker: RealisticConstraintChecker
    ) -> None:
        """Test rejection when event has too many NPCs."""
        crowded_event = WorldEvent(
            event_type="riot",
            event_key="riot_001",
            description="Town riot",
            npcs_involved=["npc1", "npc2", "npc3", "npc4", "npc5", "npc6"],  # 6 NPCs
            location="plaza",
        )
        result = checker.check_event_constraints(event=crowded_event)
        assert result.allowed is False
        assert result.violated_constraint == "max_npcs_per_event"

    def test_custom_event_limits(self) -> None:
        """Test custom event limits are enforced."""
        custom_limits = EventLimits(
            max_events_per_day=1,
            max_intrusions_per_week=0,
            min_hours_between_events=6,
        )
        checker = RealisticConstraintChecker(event_limits=custom_limits)

        event = WorldEvent(
            event_type="arrival",
            event_key="arrival_001",
            description="Someone arrives",
            location="gate",
        )

        # Should fail with just 1 event already today
        result = checker.check_event_constraints(
            event=event,
            events_today=1,
        )
        assert result.allowed is False


# =============================================================================
# New Element Constraint Tests
# =============================================================================


class TestNewElementConstraints:
    """Tests for new element introduction constraints."""

    def test_new_npc_element(
        self, checker: RealisticConstraintChecker
    ) -> None:
        """Test new NPC element constraint checking."""
        element = NewElement(
            element_type="npc",
            specification={
                "display_name": "Elena",
                "gender": "female",
                "relationship_type": "close_friend",
            },
            justification="Player needs a friend",
            narrative_purpose="Story progression",
        )
        result = checker.check_new_element(
            element=element,
            current_close_friends=4,  # Under limit
        )
        assert result.allowed is True

    def test_new_npc_element_limit_exceeded(
        self, checker: RealisticConstraintChecker
    ) -> None:
        """Test new NPC element rejected when limit exceeded."""
        element = NewElement(
            element_type="npc",
            specification={
                "display_name": "Elena",
                "relationship_type": "close_friend",
            },
            justification="Player needs a friend",
            narrative_purpose="Story progression",
        )
        result = checker.check_new_element(
            element=element,
            current_close_friends=5,  # At limit
        )
        assert result.allowed is False

    def test_fact_element_always_allowed(
        self, checker: RealisticConstraintChecker
    ) -> None:
        """Test fact elements are always allowed."""
        element = NewElement(
            element_type="fact",
            specification={
                "subject": "world",
                "predicate": "has_problem",
                "value": "drought",
            },
            justification="World building",
            narrative_purpose="Set atmosphere",
        )
        result = checker.check_new_element(element=element)
        assert result.allowed is True

    def test_relationship_element(
        self, checker: RealisticConstraintChecker
    ) -> None:
        """Test relationship element constraint checking."""
        element = NewElement(
            element_type="relationship",
            specification={
                "type": "casual_friend",
                "between": ["npc1", "npc2"],
            },
            justification="NPCs know each other",
            narrative_purpose="World depth",
        )
        result = checker.check_new_element(element=element)
        assert result.allowed is True

    def test_unknown_element_type_rejected(
        self, checker: RealisticConstraintChecker
    ) -> None:
        """Test unknown element types are rejected."""
        element = NewElement(
            element_type="unknown_type",
            specification={},
            justification="Testing",
            narrative_purpose="Testing",
        )
        result = checker.check_new_element(element=element)
        assert result.allowed is False
        assert result.violated_constraint == "element_type"


# =============================================================================
# Combined Constraint Tests
# =============================================================================


class TestCombinedConstraints:
    """Tests for checking all constraints together."""

    def test_check_all_placements(
        self, checker: RealisticConstraintChecker
    ) -> None:
        """Test checking constraints on multiple placements."""
        placements = [
            NPCPlacement(
                entity_key="guard_001",
                presence_reason=PresenceReason.SCHEDULE,
                presence_justification="On duty",
                activity="standing",
                position_in_scene="by door",
            ),
            NPCPlacement(
                new_npc=NPCSpec(display_name="Elena"),
                presence_reason=PresenceReason.VISITING,
                presence_justification="Friend visiting",
                activity="sitting",
                position_in_scene="on chair",
            ),
        ]

        results = checker.check_all_placements(
            placements=placements,
            location_type="house",
            current_hour=14,
        )

        assert len(results) == 2
        # Both should pass with these conditions
        for placement, result in results:
            assert result.allowed is True

    def test_check_all_placements_with_failures(
        self, checker: RealisticConstraintChecker
    ) -> None:
        """Test checking placements where some fail."""
        placements = [
            # This should pass
            NPCPlacement(
                entity_key="guard_001",
                presence_reason=PresenceReason.SCHEDULE,
                presence_justification="On duty",
                activity="standing",
                position_in_scene="by door",
            ),
            # This should fail - visiting at night
            NPCPlacement(
                new_npc=NPCSpec(display_name="Elena"),
                presence_reason=PresenceReason.VISITING,
                presence_justification="Late night visit",
                activity="sitting",
                position_in_scene="on chair",
            ),
        ]

        results = checker.check_all_placements(
            placements=placements,
            location_type="house",
            current_hour=2,  # 2am - visiting not allowed
        )

        assert len(results) == 2
        assert results[0][1].allowed is True  # Guard with SCHEDULE
        assert results[1][1].allowed is False  # Visitor at night

    def test_filter_valid_placements(
        self, checker: RealisticConstraintChecker
    ) -> None:
        """Test filtering to only valid placements."""
        placements = [
            NPCPlacement(
                entity_key="guard_001",
                presence_reason=PresenceReason.SCHEDULE,
                presence_justification="On duty",
                activity="standing",
                position_in_scene="by door",
            ),
            NPCPlacement(
                new_npc=NPCSpec(display_name="Elena"),
                presence_reason=PresenceReason.VISITING,
                presence_justification="Late night visit",
                activity="sitting",
                position_in_scene="on chair",
            ),
        ]

        valid = checker.filter_valid_placements(
            placements=placements,
            location_type="house",
            current_hour=2,  # Night - visiting fails
        )

        assert len(valid) == 1
        assert valid[0].entity_key == "guard_001"

    def test_combined_social_and_physical_constraints(
        self, strict_checker: RealisticConstraintChecker
    ) -> None:
        """Test that both social and physical constraints are checked."""
        placement = NPCPlacement(
            new_npc=NPCSpec(
                display_name="Elena",
                relationship_to_player="close_friend",
            ),
            presence_reason=PresenceReason.VISITING,
            presence_justification="Friend visiting",
            activity="sitting",
            position_in_scene="on chair",
        )

        # Should fail physical constraint (visiting in private space)
        results = strict_checker.check_all_placements(
            placements=[placement],
            location_type="bedroom",
            is_player_home=True,
            current_hour=14,
        )
        assert results[0][1].allowed is False
        assert results[0][1].violated_constraint == "private_location"

        # Now try in public space at limit
        results = strict_checker.check_all_placements(
            placements=[placement],
            location_type="tavern",
            current_hour=14,
            current_close_friends=2,  # At strict limit
        )
        assert results[0][1].allowed is False
        assert results[0][1].violated_constraint == "max_close_friends"


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_boundary_hours(
        self, checker: RealisticConstraintChecker
    ) -> None:
        """Test visiting at boundary hours."""
        placement = NPCPlacement(
            entity_key="friend_001",
            presence_reason=PresenceReason.VISITING,
            presence_justification="Morning visit",
            activity="waiting",
            position_in_scene="at door",
        )

        # At exactly 7am (earliest allowed)
        result = checker.check_physical_constraints(
            npc_placement=placement,
            location_type="house",
            current_hour=7,
        )
        assert result.allowed is True

        # At exactly 21 (before 22 cutoff)
        result = checker.check_physical_constraints(
            npc_placement=placement,
            location_type="house",
            current_hour=21,
        )
        assert result.allowed is True

    def test_exact_limit_values(
        self, checker: RealisticConstraintChecker
    ) -> None:
        """Test behavior at exact limit values."""
        npc = NPCSpec(display_name="Test")

        # At exactly max (should fail)
        result = checker.check_social_constraints(
            new_npc=npc,
            relationship_type="close_friend",
            current_close_friends=5,
        )
        assert result.allowed is False

        # One under max (should pass)
        result = checker.check_social_constraints(
            new_npc=npc,
            relationship_type="close_friend",
            current_close_friends=4,
        )
        assert result.allowed is True

    def test_sleeping_hour_boundaries(
        self, checker: RealisticConstraintChecker
    ) -> None:
        """Test sleeping hour boundary conditions."""
        placement = NPCPlacement(
            entity_key="visitor_001",
            presence_reason=PresenceReason.VISITING,
            presence_justification="Visit",
            activity="waiting",
            position_in_scene="at door",
        )

        # Just before sleep starts (22:00 should be rejected already due to visit hours)
        # Sleep starts at 23:00

        # At 6am (end of sleep period) - should fail
        result = checker.check_physical_constraints(
            npc_placement=placement,
            location_type="tavern",
            current_hour=6,
        )
        # Both sleep_hours and visiting_hours should apply
        assert result.allowed is False

        # At 7am (after sleep, earliest visit) - should pass
        result = checker.check_physical_constraints(
            npc_placement=placement,
            location_type="tavern",
            current_hour=7,
        )
        assert result.allowed is True

    def test_empty_placements_list(
        self, checker: RealisticConstraintChecker
    ) -> None:
        """Test checking empty placements list."""
        results = checker.check_all_placements(
            placements=[],
            location_type="house",
            current_hour=12,
        )
        assert results == []

        valid = checker.filter_valid_placements(
            placements=[],
            location_type="house",
            current_hour=12,
        )
        assert valid == []
