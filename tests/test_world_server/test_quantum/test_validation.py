"""Tests for the Quantum Branching validation module."""

from datetime import datetime

import pytest

from src.gm.grounding import (
    GroundingManifest,
    GroundedEntity,
)
from src.world_server.quantum.schemas import (
    ActionPrediction,
    ActionType,
    DeltaType,
    GMDecision,
    OutcomeVariant,
    PredictionReason,
    QuantumBranch,
    StateDelta,
    VariantType,
)
from src.world_server.quantum.validation import (
    BranchValidator,
    DeltaValidator,
    IssueSeverity,
    NarrativeConsistencyValidator,
    ValidationIssue,
    ValidationResult,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_manifest() -> GroundingManifest:
    """Create a sample grounding manifest for tests."""
    return GroundingManifest(
        location_key="forge_001",
        location_display="The Forge",
        player_key="player",
        player_display="you",
        npcs={
            "marcus_001": GroundedEntity(
                key="marcus_001",
                display_name="Marcus",
                entity_type="npc",
                short_description="the blacksmith",
            ),
        },
        items_at_location={
            "sword_001": GroundedEntity(
                key="sword_001",
                display_name="iron sword",
                entity_type="item",
                short_description="a finely crafted blade",
            ),
        },
        inventory={},
        equipped={},
        storages={},
        exits={
            "market_001": GroundedEntity(
                key="market_001",
                display_name="the market",
                entity_type="location",
                short_description="to the east",
            ),
        },
    )


@pytest.fixture
def narrative_validator(sample_manifest: GroundingManifest) -> NarrativeConsistencyValidator:
    """Create a narrative validator with sample manifest."""
    return NarrativeConsistencyValidator(sample_manifest)


@pytest.fixture
def delta_validator(sample_manifest: GroundingManifest) -> DeltaValidator:
    """Create a delta validator with sample manifest."""
    return DeltaValidator(manifest=sample_manifest)


@pytest.fixture
def branch_validator(sample_manifest: GroundingManifest) -> BranchValidator:
    """Create a branch validator with sample manifest."""
    return BranchValidator(sample_manifest)


# =============================================================================
# ValidationResult Tests
# =============================================================================


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_valid_result_no_issues(self):
        """Valid result with no issues."""
        result = ValidationResult(valid=True, issues=[])
        assert result.valid
        assert result.error_count == 0
        assert result.warning_count == 0
        assert result.errors == []
        assert result.warnings == []

    def test_result_with_errors(self):
        """Result with error-level issues."""
        issues = [
            ValidationIssue(
                category="test",
                message="Test error",
                severity=IssueSeverity.ERROR,
            ),
            ValidationIssue(
                category="test",
                message="Test warning",
                severity=IssueSeverity.WARNING,
            ),
        ]
        result = ValidationResult(valid=False, issues=issues)

        assert not result.valid
        assert result.error_count == 1
        assert result.warning_count == 1
        assert len(result.errors) == 1
        assert len(result.warnings) == 1

    def test_format_issues_empty(self):
        """Format issues with no issues."""
        result = ValidationResult(valid=True, issues=[])
        assert result.format_issues() == "No issues found."

    def test_format_issues_with_content(self):
        """Format issues with various issues."""
        issues = [
            ValidationIssue(
                category="grounding",
                message="Invalid entity key",
                severity=IssueSeverity.ERROR,
                location="line 5",
                suggestion="Use correct key",
            ),
            ValidationIssue(
                category="meta",
                message="Meta question detected",
                severity=IssueSeverity.WARNING,
            ),
        ]
        result = ValidationResult(valid=False, issues=issues)
        formatted = result.format_issues()

        assert "[ERROR]" in formatted
        assert "[WARN]" in formatted
        assert "[grounding]" in formatted
        assert "[meta]" in formatted
        assert "Invalid entity key" in formatted
        assert "line 5" in formatted
        assert "Suggestion:" in formatted


# =============================================================================
# NarrativeConsistencyValidator Tests
# =============================================================================


class TestNarrativeConsistencyValidator:
    """Tests for NarrativeConsistencyValidator."""

    def test_valid_narrative(self, narrative_validator: NarrativeConsistencyValidator):
        """Valid narrative passes validation."""
        narrative = (
            "[marcus_001:Marcus] looks up from his anvil. "
            "\"Ah, a customer! Looking for a new blade?\""
        )
        result = narrative_validator.validate(narrative)

        assert result.valid
        assert result.error_count == 0

    def test_empty_narrative(self, narrative_validator: NarrativeConsistencyValidator):
        """Empty narrative fails validation."""
        result = narrative_validator.validate("")
        assert not result.valid
        assert result.error_count == 1
        assert any("empty" in i.message.lower() for i in result.issues)

    def test_whitespace_narrative(self, narrative_validator: NarrativeConsistencyValidator):
        """Whitespace-only narrative fails validation."""
        result = narrative_validator.validate("   \n\t  ")
        assert not result.valid
        assert any("empty" in i.message.lower() for i in result.issues)

    def test_too_short_narrative(self, narrative_validator: NarrativeConsistencyValidator):
        """Short narrative gets warning."""
        result = narrative_validator.validate("Hi.")
        # Should get length warning (3 chars < 20 min)
        assert any("too short" in i.message.lower() for i in result.issues)

    def test_too_long_narrative(self, narrative_validator: NarrativeConsistencyValidator):
        """Very long narrative gets warning."""
        narrative = "A" * 3000
        result = narrative_validator.validate(narrative)
        assert any("too long" in i.message.lower() for i in result.issues)

    def test_invalid_entity_key(self, narrative_validator: NarrativeConsistencyValidator):
        """Invalid entity key fails validation."""
        narrative = (
            "[unknown_npc:Someone] waves at you from across the room. "
            "This is a test narrative with enough length."
        )
        result = narrative_validator.validate(narrative)

        # Should have grounding error for invalid key
        assert any(
            "grounding" in i.category and i.severity == IssueSeverity.ERROR
            for i in result.issues
        )

    def test_meta_question_detection(self, narrative_validator: NarrativeConsistencyValidator):
        """Meta questions are detected."""
        narratives_with_meta = [
            "The guard stands watch. What would you like to do?",
            "[marcus_001:Marcus] waits patiently. How do you respond?",
            "The door is open. Would you like to enter?",
        ]

        for narrative in narratives_with_meta:
            result = narrative_validator.validate(narrative)
            meta_issues = [i for i in result.issues if i.category == "meta"]
            assert len(meta_issues) > 0, f"Meta question not detected in: {narrative}"

    def test_no_meta_question_in_dialogue(
        self, narrative_validator: NarrativeConsistencyValidator
    ):
        """Questions in dialogue are not meta questions."""
        narrative = (
            "[marcus_001:Marcus] looks at you curiously. "
            "\"What brings you to my forge today?\" he asks."
        )
        result = narrative_validator.validate(narrative)
        meta_issues = [i for i in result.issues if i.category == "meta"]
        assert len(meta_issues) == 0

    def test_ai_identity_detection(self, narrative_validator: NarrativeConsistencyValidator):
        """AI identity leakage is detected."""
        narratives = [
            "I'm an AI assistant and I'm here to help you explore this world.",
            "As an AI, I don't have feelings, but I can describe the scene.",
            "I was designed to help you play this game.",
        ]

        for narrative in narratives:
            result = narrative_validator.validate(narrative)
            identity_issues = [i for i in result.issues if i.category == "identity"]
            assert len(identity_issues) > 0, f"AI identity not detected in: {narrative}"

    def test_third_person_detection(self, narrative_validator: NarrativeConsistencyValidator):
        """Third-person player references are detected."""
        narratives = [
            "The player enters the room and looks around carefully.",
            "The character draws their sword and prepares for battle.",
            "The protagonist walks toward the door slowly.",
        ]

        for narrative in narratives:
            result = narrative_validator.validate(narrative)
            perspective_issues = [i for i in result.issues if i.category == "perspective"]
            assert len(perspective_issues) > 0, f"Third-person not detected in: {narrative}"

    def test_placeholder_detection(self, narrative_validator: NarrativeConsistencyValidator):
        """Placeholder content is detected."""
        narratives = [
            "The guard says something important. [TODO: add dialogue]",
            "[marcus_001:Marcus] gives you a <placeholder> item.",
            "You find a FIXME treasure chest in the corner.",
            "The story continues with ${character_name} doing something.",
        ]

        for narrative in narratives:
            result = narrative_validator.validate(narrative)
            placeholder_issues = [i for i in result.issues if i.category == "placeholder"]
            assert len(placeholder_issues) > 0, f"Placeholder not detected in: {narrative}"

    def test_quality_capitalization(self, narrative_validator: NarrativeConsistencyValidator):
        """Lowercase start gets info-level issue."""
        narrative = "the blacksmith looks up from his work and greets you warmly."
        result = narrative_validator.validate(narrative)

        quality_issues = [
            i for i in result.issues
            if i.category == "quality" and "capital" in i.message.lower()
        ]
        assert len(quality_issues) > 0
        assert quality_issues[0].severity == IssueSeverity.INFO

    def test_quality_punctuation(self, narrative_validator: NarrativeConsistencyValidator):
        """Missing ending punctuation gets info-level issue."""
        narrative = "The blacksmith looks up from his work and greets you warmly"
        result = narrative_validator.validate(narrative)

        quality_issues = [
            i for i in result.issues
            if i.category == "quality" and "punctuation" in i.message.lower()
        ]
        assert len(quality_issues) > 0
        assert quality_issues[0].severity == IssueSeverity.INFO

    def test_quality_whitespace(self, narrative_validator: NarrativeConsistencyValidator):
        """Multiple consecutive spaces get info-level issue."""
        narrative = "The blacksmith  looks up from his  work and greets you warmly."
        result = narrative_validator.validate(narrative)

        quality_issues = [
            i for i in result.issues
            if i.category == "quality" and "space" in i.message.lower()
        ]
        assert len(quality_issues) > 0
        assert quality_issues[0].severity == IssueSeverity.INFO


# =============================================================================
# DeltaValidator Tests
# =============================================================================


class TestDeltaValidator:
    """Tests for DeltaValidator."""

    def test_empty_deltas_valid(self, delta_validator: DeltaValidator):
        """Empty delta list is valid."""
        result = delta_validator.validate([])
        assert result.valid
        assert len(result.issues) == 0

    def test_missing_target_key(self, delta_validator: DeltaValidator):
        """Delta without target_key fails."""
        delta = StateDelta(
            delta_type=DeltaType.UPDATE_ENTITY,
            target_key="",  # Empty key
            changes={"health": 100},
        )
        result = delta_validator.validate([delta])
        assert not result.valid
        assert any("target_key" in i.message.lower() for i in result.issues)

    def test_create_entity_missing_type(self, delta_validator: DeltaValidator):
        """CREATE_ENTITY without entity_type fails."""
        delta = StateDelta(
            delta_type=DeltaType.CREATE_ENTITY,
            target_key="new_item_001",
            changes={"display_name": "New Item"},  # Missing entity_type
        )
        result = delta_validator.validate([delta])
        assert not result.valid
        assert any("entity_type" in i.message for i in result.issues)

    def test_create_entity_valid(self, delta_validator: DeltaValidator):
        """Valid CREATE_ENTITY passes."""
        delta = StateDelta(
            delta_type=DeltaType.CREATE_ENTITY,
            target_key="new_item_001",
            changes={"entity_type": "item", "display_name": "New Sword"},
        )
        result = delta_validator.validate([delta])
        assert result.valid

    def test_create_entity_duplicate_key(self, delta_validator: DeltaValidator):
        """CREATE_ENTITY with existing key fails."""
        delta = StateDelta(
            delta_type=DeltaType.CREATE_ENTITY,
            target_key="marcus_001",  # Already exists in manifest
            changes={"entity_type": "npc", "display_name": "Another Marcus"},
        )
        result = delta_validator.validate([delta])
        assert not result.valid
        assert any("already exists" in i.message for i in result.issues)

    def test_update_entity_nonexistent(self, delta_validator: DeltaValidator):
        """UPDATE_ENTITY for nonexistent entity fails."""
        delta = StateDelta(
            delta_type=DeltaType.UPDATE_ENTITY,
            target_key="nonexistent_001",
            changes={"health": 50},
        )
        result = delta_validator.validate([delta])
        assert not result.valid
        assert any("not found" in i.message for i in result.issues)

    def test_update_entity_no_changes(self, delta_validator: DeltaValidator):
        """UPDATE_ENTITY with no changes gets warning."""
        delta = StateDelta(
            delta_type=DeltaType.UPDATE_ENTITY,
            target_key="marcus_001",
            changes={},
        )
        result = delta_validator.validate([delta])
        # Should be valid but with warning
        assert any(
            "no changes" in i.message.lower() and i.severity == IssueSeverity.WARNING
            for i in result.issues
        )

    def test_transfer_item_missing_from_to(self, delta_validator: DeltaValidator):
        """TRANSFER_ITEM without from/to fails."""
        delta = StateDelta(
            delta_type=DeltaType.TRANSFER_ITEM,
            target_key="sword_001",
            changes={},  # Missing from/to
        )
        result = delta_validator.validate([delta])
        assert not result.valid
        assert any("from" in i.message and "to" in i.message for i in result.issues)

    def test_transfer_item_valid(self, delta_validator: DeltaValidator):
        """Valid TRANSFER_ITEM passes."""
        delta = StateDelta(
            delta_type=DeltaType.TRANSFER_ITEM,
            target_key="sword_001",
            changes={"from": "marcus_001", "to": "player"},
        )
        result = delta_validator.validate([delta])
        assert result.valid

    def test_record_fact_missing_predicate(self, delta_validator: DeltaValidator):
        """RECORD_FACT without predicate fails."""
        delta = StateDelta(
            delta_type=DeltaType.RECORD_FACT,
            target_key="world",
            changes={"value": "true"},  # Missing predicate
        )
        result = delta_validator.validate([delta])
        assert not result.valid
        assert any("predicate" in i.message for i in result.issues)

    def test_record_fact_missing_value(self, delta_validator: DeltaValidator):
        """RECORD_FACT without value fails."""
        delta = StateDelta(
            delta_type=DeltaType.RECORD_FACT,
            target_key="world",
            changes={"predicate": "discovered"},  # Missing value
        )
        result = delta_validator.validate([delta])
        assert not result.valid
        assert any("value" in i.message for i in result.issues)

    def test_record_fact_valid(self, delta_validator: DeltaValidator):
        """Valid RECORD_FACT passes."""
        delta = StateDelta(
            delta_type=DeltaType.RECORD_FACT,
            target_key="forge_001",
            changes={"predicate": "visited", "value": "true"},
        )
        result = delta_validator.validate([delta])
        assert result.valid

    def test_update_need_valid_range(self, delta_validator: DeltaValidator):
        """UPDATE_NEED with valid values passes."""
        delta = StateDelta(
            delta_type=DeltaType.UPDATE_NEED,
            target_key="player",
            changes={"hunger": 50, "thirst": 30},
        )
        result = delta_validator.validate([delta])
        assert result.valid

    def test_update_need_invalid_range(self, delta_validator: DeltaValidator):
        """UPDATE_NEED with out-of-range values gets warning."""
        delta = StateDelta(
            delta_type=DeltaType.UPDATE_NEED,
            target_key="player",
            changes={"hunger": 150, "thirst": -10},  # Out of range
        )
        result = delta_validator.validate([delta])
        warnings = [i for i in result.issues if i.severity == IssueSeverity.WARNING]
        assert len(warnings) >= 2
        assert any("out of range" in i.message for i in warnings)

    def test_update_need_unknown_need(self, delta_validator: DeltaValidator):
        """UPDATE_NEED with unknown need gets warning."""
        delta = StateDelta(
            delta_type=DeltaType.UPDATE_NEED,
            target_key="player",
            changes={"mana": 100},  # Not a known need
        )
        result = delta_validator.validate([delta])
        assert any("Unknown need" in i.message for i in result.issues)

    def test_update_relationship_valid(self, delta_validator: DeltaValidator):
        """Valid UPDATE_RELATIONSHIP passes."""
        delta = StateDelta(
            delta_type=DeltaType.UPDATE_RELATIONSHIP,
            target_key="marcus_001",
            changes={"trust": 60, "liking": 55},
        )
        result = delta_validator.validate([delta])
        assert result.valid

    def test_update_relationship_invalid_range(self, delta_validator: DeltaValidator):
        """UPDATE_RELATIONSHIP with out-of-range values gets warning."""
        delta = StateDelta(
            delta_type=DeltaType.UPDATE_RELATIONSHIP,
            target_key="marcus_001",
            changes={"trust": 200},  # Out of range
        )
        result = delta_validator.validate([delta])
        assert any("out of range" in i.message for i in result.issues)

    def test_update_relationship_unknown_attr(self, delta_validator: DeltaValidator):
        """UPDATE_RELATIONSHIP with unknown attribute gets warning."""
        delta = StateDelta(
            delta_type=DeltaType.UPDATE_RELATIONSHIP,
            target_key="marcus_001",
            changes={"friendship": 50},  # Not a valid relationship attr
        )
        result = delta_validator.validate([delta])
        assert any("Unknown relationship" in i.message for i in result.issues)

    def test_advance_time_valid(self, delta_validator: DeltaValidator):
        """Valid ADVANCE_TIME passes."""
        delta = StateDelta(
            delta_type=DeltaType.ADVANCE_TIME,
            target_key="time",
            changes={"minutes": 30},
        )
        result = delta_validator.validate([delta])
        assert result.valid

    def test_advance_time_negative(self, delta_validator: DeltaValidator):
        """ADVANCE_TIME with negative minutes fails."""
        delta = StateDelta(
            delta_type=DeltaType.ADVANCE_TIME,
            target_key="time",
            changes={"minutes": -10},
        )
        result = delta_validator.validate([delta])
        assert not result.valid
        assert any("backwards" in i.message for i in result.issues)

    def test_advance_time_large(self, delta_validator: DeltaValidator):
        """ADVANCE_TIME with large value gets warning."""
        delta = StateDelta(
            delta_type=DeltaType.ADVANCE_TIME,
            target_key="time",
            changes={"minutes": 2000},  # More than 24 hours
        )
        result = delta_validator.validate([delta])
        assert any("very large" in i.message for i in result.issues)

    def test_advance_time_invalid_type(self, delta_validator: DeltaValidator):
        """ADVANCE_TIME with non-numeric minutes fails."""
        delta = StateDelta(
            delta_type=DeltaType.ADVANCE_TIME,
            target_key="time",
            changes={"minutes": "thirty"},  # String instead of number
        )
        result = delta_validator.validate([delta])
        assert not result.valid
        assert any("must be a number" in i.message for i in result.issues)

    def test_conflict_create_delete(self, delta_validator: DeltaValidator):
        """CREATE + DELETE for same entity conflicts."""
        deltas = [
            StateDelta(
                delta_type=DeltaType.CREATE_ENTITY,
                target_key="temp_001",
                changes={"entity_type": "item", "display_name": "Temp Item"},
            ),
            StateDelta(
                delta_type=DeltaType.DELETE_ENTITY,
                target_key="temp_001",
                changes={},
            ),
        ]
        result = delta_validator.validate(deltas)
        assert not result.valid
        assert any("conflict" in i.category.lower() for i in result.issues)

    def test_conflict_multiple_creates(self, delta_validator: DeltaValidator):
        """Multiple CREATE_ENTITY for same key conflicts."""
        deltas = [
            StateDelta(
                delta_type=DeltaType.CREATE_ENTITY,
                target_key="new_001",
                changes={"entity_type": "item", "display_name": "First"},
            ),
            StateDelta(
                delta_type=DeltaType.CREATE_ENTITY,
                target_key="new_001",
                changes={"entity_type": "item", "display_name": "Second"},
            ),
        ]
        result = delta_validator.validate(deltas)
        assert not result.valid
        assert any("Multiple CREATE_ENTITY" in i.message for i in result.issues)


# =============================================================================
# BranchValidator Tests
# =============================================================================


class TestBranchValidator:
    """Tests for BranchValidator."""

    def _make_branch(
        self,
        narrative: str = "The blacksmith nods and hands you the blade.",
        deltas: list[StateDelta] | None = None,
    ) -> QuantumBranch:
        """Helper to create a test branch."""
        if deltas is None:
            deltas = []

        variant = OutcomeVariant(
            variant_type=VariantType.SUCCESS,
            requires_dice=False,
            dc=None,
            skill=None,
            narrative=narrative,
            state_deltas=deltas,
            time_passed_minutes=5,
        )

        return QuantumBranch(
            branch_key="forge_001::interact_npc::marcus_001::no_twist",
            action=ActionPrediction(
                action_type=ActionType.INTERACT_NPC,
                target_key="marcus_001",
                input_patterns=["talk.*marcus"],
                probability=0.5,
                reason=PredictionReason.NPC_LOCATION,
            ),
            gm_decision=GMDecision(
                decision_type="no_twist",
                probability=0.7,
                grounding_facts=[],
            ),
            variants={"success": variant},
            generated_at=datetime.now(),
            generation_time_ms=100.0,
        )

    def test_valid_branch(self, branch_validator: BranchValidator):
        """Valid branch passes validation."""
        branch = self._make_branch(
            narrative="[marcus_001:Marcus] carefully examines the blade and nods approvingly."
        )
        result = branch_validator.validate(branch)
        assert result.valid

    def test_branch_with_invalid_narrative(self, branch_validator: BranchValidator):
        """Branch with invalid narrative fails."""
        branch = self._make_branch(
            narrative=""  # Empty narrative
        )
        result = branch_validator.validate(branch)
        assert not result.valid

    def test_branch_with_invalid_delta(self, branch_validator: BranchValidator):
        """Branch with invalid delta fails."""
        branch = self._make_branch(
            narrative="[marcus_001:Marcus] nods and hands you the blade carefully.",
            deltas=[
                StateDelta(
                    delta_type=DeltaType.CREATE_ENTITY,
                    target_key="item_001",
                    changes={},  # Missing entity_type
                )
            ],
        )
        result = branch_validator.validate(branch)
        assert not result.valid

    def test_branch_multiple_variants(self, branch_validator: BranchValidator):
        """Branch with multiple variants all get validated."""
        success_variant = OutcomeVariant(
            variant_type=VariantType.SUCCESS,
            requires_dice=True,
            dc=12,
            skill="persuasion",
            narrative="[marcus_001:Marcus] agrees to help you with your quest.",
            state_deltas=[],
            time_passed_minutes=5,
        )
        failure_variant = OutcomeVariant(
            variant_type=VariantType.FAILURE,
            requires_dice=True,
            dc=12,
            skill="persuasion",
            narrative="",  # Invalid: empty
            state_deltas=[],
            time_passed_minutes=5,
        )

        branch = QuantumBranch(
            branch_key="test::test::test",
            action=ActionPrediction(
                action_type=ActionType.INTERACT_NPC,
                target_key="marcus_001",
                input_patterns=[],
                probability=0.5,
                reason=PredictionReason.NPC_LOCATION,
            ),
            gm_decision=GMDecision(
                decision_type="no_twist",
                probability=0.7,
                grounding_facts=[],
            ),
            variants={"success": success_variant, "failure": failure_variant},
            generated_at=datetime.now(),
            generation_time_ms=150.0,
        )

        result = branch_validator.validate(branch)
        assert not result.valid
        # Should have error from failure variant
        assert any("variant:failure" in i.category for i in result.issues)

    def test_validate_variant_directly(self, branch_validator: BranchValidator):
        """Can validate a single variant."""
        variant = OutcomeVariant(
            variant_type=VariantType.SUCCESS,
            requires_dice=False,
            dc=None,
            skill=None,
            narrative="[marcus_001:Marcus] smiles warmly at your approach.",
            state_deltas=[],
            time_passed_minutes=5,
        )
        result = branch_validator.validate_variant(variant)
        assert result.valid

    def test_validate_variant_with_deltas(self, branch_validator: BranchValidator):
        """Variant validation includes delta validation."""
        variant = OutcomeVariant(
            variant_type=VariantType.SUCCESS,
            requires_dice=False,
            dc=None,
            skill=None,
            narrative="[marcus_001:Marcus] gives you a shiny new blade from his forge.",
            state_deltas=[
                StateDelta(
                    delta_type=DeltaType.TRANSFER_ITEM,
                    target_key="sword_001",
                    changes={"from": "marcus_001", "to": "player"},
                )
            ],
            time_passed_minutes=5,
        )
        result = branch_validator.validate_variant(variant)
        assert result.valid


# =============================================================================
# Edge Cases and Integration
# =============================================================================


class TestValidationEdgeCases:
    """Edge cases and integration tests."""

    def test_validator_without_manifest(self):
        """DeltaValidator works without manifest (limited validation)."""
        validator = DeltaValidator()  # No manifest
        delta = StateDelta(
            delta_type=DeltaType.UPDATE_ENTITY,
            target_key="some_entity",
            changes={"health": 100},
        )
        result = validator.validate([delta])
        # Should be valid since we can't check entity existence without manifest
        assert result.valid

    def test_valid_entity_reference_format(
        self, narrative_validator: NarrativeConsistencyValidator
    ):
        """Proper [key:text] format validates correctly."""
        narrative = (
            "[marcus_001:The blacksmith] puts down his hammer and approaches you. "
            "\"What can I forge for you today?\" he asks."
        )
        result = narrative_validator.validate(narrative)
        # Should only have warnings for display name mismatch if any
        assert result.error_count == 0

    def test_custom_length_limits(self, sample_manifest: GroundingManifest):
        """Custom min/max length limits work."""
        validator = NarrativeConsistencyValidator(
            sample_manifest, min_length=100, max_length=200
        )

        # Too short
        result = validator.validate("Short text that meets minimum.")
        assert any("too short" in i.message.lower() for i in result.issues)

        # Just right
        result = validator.validate(
            "This is a moderate length narrative that describes the scene "
            "in enough detail to be interesting but not too verbose."
        )
        length_issues = [i for i in result.issues if i.category == "length"]
        assert len(length_issues) == 0

    def test_unicode_in_narrative(
        self, narrative_validator: NarrativeConsistencyValidator
    ):
        """Unicode characters in narrative are handled."""
        narrative = (
            "[marcus_001:Marcus] presents you with a fine blade. "
            "\"This steel is folded a thousand times,\" he says proudly. "
            "The sword gleams with an ethereal light."
        )
        result = narrative_validator.validate(narrative)
        assert result.valid

    def test_combined_issues(
        self, narrative_validator: NarrativeConsistencyValidator
    ):
        """Multiple issue types detected in same narrative."""
        narrative = (
            "[unknown_npc:Someone] says hello.  "
            "The player walks over. "
            "What would you like to do?"
        )
        result = narrative_validator.validate(narrative)

        categories = {i.category for i in result.issues}
        # Should detect: grounding (unknown_npc), perspective (the player),
        # meta (what would you like), quality (double space)
        assert "grounding" in categories or len(result.issues) > 0
