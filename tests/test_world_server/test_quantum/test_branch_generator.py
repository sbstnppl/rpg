"""Tests for BranchGenerator."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.gm.grounding import GroundingManifest, GroundedEntity
from src.llm.response_types import LLMResponse
from src.world_server.schemas import PredictionReason
from src.world_server.quantum.schemas import (
    ActionType,
    ActionPrediction,
    GMDecision,
    VariantType,
)
from src.world_server.quantum.branch_generator import (
    BranchGenerator,
    BranchContext,
    BranchGenerationResponse,
    GeneratedVariant,
    GeneratedStateDelta,
)


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture
def mock_game_session():
    """Create a mock game session."""
    session = MagicMock()
    session.id = 1
    return session


@pytest.fixture
def mock_llm():
    """Create a mock LLM provider."""
    llm = AsyncMock()
    return llm


@pytest.fixture
def sample_manifest():
    """Create a sample grounding manifest."""
    return GroundingManifest(
        location_key="tavern_main",
        location_display="The Rusty Anchor Tavern",
        player_key="player_001",
        player_display="you",
        npcs={
            "innkeeper_tom": GroundedEntity(
                key="innkeeper_tom",
                display_name="Old Tom",
                entity_type="npc",
                short_description="the friendly innkeeper",
            ),
        },
        items_at_location={
            "ale_mug_001": GroundedEntity(
                key="ale_mug_001",
                display_name="mug of ale",
                entity_type="item",
                short_description="a frothy ale",
            ),
        },
        inventory={},
        exits={
            "village_square": GroundedEntity(
                key="village_square",
                display_name="Village Square",
                entity_type="location",
            ),
        },
    )


@pytest.fixture
def sample_context():
    """Create sample branch context."""
    return BranchContext(
        location_key="tavern_main",
        location_display="The Rusty Anchor Tavern",
        player_key="player_001",
        game_time="14:30",
        game_day=1,
        recent_events=["Arrived at the tavern", "Met the innkeeper"],
    )


@pytest.fixture
def sample_action():
    """Create a sample action prediction."""
    return ActionPrediction(
        action_type=ActionType.INTERACT_NPC,
        target_key="innkeeper_tom",
        input_patterns=["talk to tom"],
        probability=0.25,
        reason=PredictionReason.ADJACENT,
        display_name="Talk to Old Tom",
    )


@pytest.fixture
def sample_gm_decision():
    """Create a sample GM decision."""
    return GMDecision(
        decision_type="no_twist",
        probability=0.7,
        grounding_facts=[],
    )


@pytest.fixture
def sample_llm_response():
    """Create a sample structured LLM response."""
    return BranchGenerationResponse(
        variants=[
            GeneratedVariant(
                variant_type="success",
                narrative="You approach [innkeeper_tom:Old Tom] and strike up a conversation. He smiles warmly.",
                state_deltas=[],
                time_passed_minutes=2,
                requires_skill_check=False,
            ),
            GeneratedVariant(
                variant_type="failure",
                narrative="[innkeeper_tom:Old Tom] seems distracted and waves you off.",
                state_deltas=[],
                time_passed_minutes=1,
                requires_skill_check=True,
                skill="persuasion",
                dc=12,
            ),
        ],
        action_summary="Player talks to innkeeper",
    )


class TestBranchGenerator:
    """Tests for BranchGenerator class."""

    def test_initialization(self, mock_db, mock_game_session, mock_llm):
        """Test generator initialization."""
        generator = BranchGenerator(mock_db, mock_game_session, mock_llm)
        assert generator.db == mock_db
        assert generator.game_session == mock_game_session
        assert generator.llm == mock_llm


class TestGenerateBranch:
    """Tests for generate_branch method."""

    @pytest.mark.asyncio
    async def test_generate_branch_success(
        self,
        mock_db,
        mock_game_session,
        mock_llm,
        sample_manifest,
        sample_context,
        sample_action,
        sample_gm_decision,
        sample_llm_response,
    ):
        """Test successful branch generation."""
        # Set up mock LLM response
        mock_llm.complete_structured.return_value = LLMResponse(
            content="",
            parsed_content=sample_llm_response,
        )

        generator = BranchGenerator(mock_db, mock_game_session, mock_llm)

        branch = await generator.generate_branch(
            sample_action, sample_gm_decision, sample_manifest, sample_context
        )

        # Verify branch structure
        assert branch is not None
        assert branch.action == sample_action
        assert branch.gm_decision == sample_gm_decision
        assert len(branch.variants) >= 1
        assert branch.generation_time_ms > 0

    @pytest.mark.asyncio
    async def test_generate_branch_creates_correct_key(
        self,
        mock_db,
        mock_game_session,
        mock_llm,
        sample_manifest,
        sample_context,
        sample_action,
        sample_gm_decision,
        sample_llm_response,
    ):
        """Test that branch key is created correctly."""
        mock_llm.complete_structured.return_value = LLMResponse(
            content="",
            parsed_content=sample_llm_response,
        )

        generator = BranchGenerator(mock_db, mock_game_session, mock_llm)

        branch = await generator.generate_branch(
            sample_action, sample_gm_decision, sample_manifest, sample_context
        )

        expected_key = "tavern_main::interact_npc::innkeeper_tom::no_twist"
        assert branch.branch_key == expected_key

    @pytest.mark.asyncio
    async def test_generate_branch_fallback_on_llm_error(
        self,
        mock_db,
        mock_game_session,
        mock_llm,
        sample_manifest,
        sample_context,
        sample_action,
        sample_gm_decision,
    ):
        """Test fallback variants when LLM fails."""
        # Make LLM fail
        mock_llm.complete_structured.side_effect = Exception("LLM error")

        generator = BranchGenerator(mock_db, mock_game_session, mock_llm)

        branch = await generator.generate_branch(
            sample_action, sample_gm_decision, sample_manifest, sample_context
        )

        # Should still return a branch with fallback variants
        assert branch is not None
        assert "success" in branch.variants

    @pytest.mark.asyncio
    async def test_generate_branch_fallback_on_empty_response(
        self,
        mock_db,
        mock_game_session,
        mock_llm,
        sample_manifest,
        sample_context,
        sample_action,
        sample_gm_decision,
    ):
        """Test fallback when LLM returns no parsed content."""
        mock_llm.complete_structured.return_value = LLMResponse(
            content="some text",
            parsed_content=None,
        )

        generator = BranchGenerator(mock_db, mock_game_session, mock_llm)

        branch = await generator.generate_branch(
            sample_action, sample_gm_decision, sample_manifest, sample_context
        )

        # Should use fallback variants
        assert branch is not None
        assert "success" in branch.variants


class TestGenerateBranches:
    """Tests for generate_branches method."""

    @pytest.mark.asyncio
    async def test_generate_branches_multiple_decisions(
        self,
        mock_db,
        mock_game_session,
        mock_llm,
        sample_manifest,
        sample_context,
        sample_action,
        sample_llm_response,
    ):
        """Test generating branches for multiple GM decisions."""
        mock_llm.complete_structured.return_value = LLMResponse(
            content="",
            parsed_content=sample_llm_response,
        )

        gm_decisions = [
            GMDecision(decision_type="no_twist", probability=0.7),
            GMDecision(decision_type="npc_busy", probability=0.3),
        ]

        generator = BranchGenerator(mock_db, mock_game_session, mock_llm)

        branches = await generator.generate_branches(
            sample_action, gm_decisions, sample_manifest, sample_context
        )

        assert len(branches) == 2
        assert branches[0].gm_decision.decision_type == "no_twist"
        assert branches[1].gm_decision.decision_type == "npc_busy"

    @pytest.mark.asyncio
    async def test_generate_branches_handles_individual_failures(
        self,
        mock_db,
        mock_game_session,
        mock_llm,
        sample_manifest,
        sample_context,
        sample_action,
        sample_llm_response,
    ):
        """Test that individual failures don't stop all generation."""
        call_count = [0]

        async def conditional_response(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("First call fails")
            return LLMResponse(content="", parsed_content=sample_llm_response)

        mock_llm.complete_structured.side_effect = conditional_response

        gm_decisions = [
            GMDecision(decision_type="failing", probability=0.5),
            GMDecision(decision_type="succeeding", probability=0.5),
        ]

        generator = BranchGenerator(mock_db, mock_game_session, mock_llm)

        branches = await generator.generate_branches(
            sample_action, gm_decisions, sample_manifest, sample_context
        )

        # Should have at least one branch (the successful one)
        assert len(branches) >= 1


class TestPromptBuilding:
    """Tests for prompt building methods."""

    def test_format_entities_includes_npcs(
        self, mock_db, mock_game_session, mock_llm, sample_manifest
    ):
        """Test that entity formatting includes NPCs."""
        generator = BranchGenerator(mock_db, mock_game_session, mock_llm)

        formatted = generator._format_entities(sample_manifest)

        assert "NPCs PRESENT AT THIS LOCATION" in formatted
        assert "innkeeper_tom" in formatted
        assert "Old Tom" in formatted

    def test_format_entities_includes_items(
        self, mock_db, mock_game_session, mock_llm, sample_manifest
    ):
        """Test that entity formatting includes items."""
        generator = BranchGenerator(mock_db, mock_game_session, mock_llm)

        formatted = generator._format_entities(sample_manifest)

        assert "Items at location:" in formatted
        assert "ale_mug_001" in formatted

    def test_format_entities_includes_exits(
        self, mock_db, mock_game_session, mock_llm, sample_manifest
    ):
        """Test that entity formatting includes exits."""
        generator = BranchGenerator(mock_db, mock_game_session, mock_llm)

        formatted = generator._format_entities(sample_manifest)

        assert "Exits:" in formatted
        assert "village_square" in formatted

    def test_format_entities_empty_npcs_shows_none(
        self, mock_db, mock_game_session, mock_llm
    ):
        """Test that entity formatting shows NONE when no NPCs present."""
        from src.gm.grounding import GroundingManifest

        generator = BranchGenerator(mock_db, mock_game_session, mock_llm)

        # Create manifest with no NPCs
        empty_manifest = GroundingManifest(
            location_key="empty_room",
            location_display="Empty Room",
            player_key="test_hero",
            npcs={},  # No NPCs
            items_at_location={},
            inventory={},
            storages={},
            exits={},
        )

        formatted = generator._format_entities(empty_manifest)

        assert "NPCs PRESENT AT THIS LOCATION: NONE" in formatted

    def test_describe_action_npc_interaction(
        self, mock_db, mock_game_session, mock_llm, sample_manifest
    ):
        """Test action description for NPC interaction."""
        generator = BranchGenerator(mock_db, mock_game_session, mock_llm)

        action = ActionPrediction(
            action_type=ActionType.INTERACT_NPC,
            target_key="innkeeper_tom",
            input_patterns=[],
            probability=0.25,
            reason=PredictionReason.ADJACENT,
        )

        desc = generator._describe_action(action, sample_manifest)

        assert "innkeeper_tom" in desc
        assert "Old Tom" in desc

    def test_describe_action_movement(
        self, mock_db, mock_game_session, mock_llm, sample_manifest
    ):
        """Test action description for movement."""
        generator = BranchGenerator(mock_db, mock_game_session, mock_llm)

        action = ActionPrediction(
            action_type=ActionType.MOVE,
            target_key="village_square",
            input_patterns=[],
            probability=0.25,
            reason=PredictionReason.ADJACENT,
        )

        desc = generator._describe_action(action, sample_manifest)

        assert "village_square" in desc
        assert "Village Square" in desc

    def test_describe_action_observe(
        self, mock_db, mock_game_session, mock_llm, sample_manifest
    ):
        """Test action description for observation."""
        generator = BranchGenerator(mock_db, mock_game_session, mock_llm)

        action = ActionPrediction(
            action_type=ActionType.OBSERVE,
            target_key=None,
            input_patterns=[],
            probability=0.2,
            reason=PredictionReason.ADJACENT,
        )

        desc = generator._describe_action(action, sample_manifest)

        assert "observe" in desc.lower() or "look" in desc.lower()


class TestVariantParsing:
    """Tests for variant parsing."""

    async def test_parse_variants_success(
        self, mock_db, mock_game_session, mock_llm, sample_manifest
    ):
        """Test parsing successful variants."""
        generator = BranchGenerator(mock_db, mock_game_session, mock_llm)

        response = BranchGenerationResponse(
            variants=[
                GeneratedVariant(
                    variant_type="success",
                    narrative="You succeed!",
                    state_deltas=[],
                    time_passed_minutes=1,
                ),
            ],
            action_summary="Test",
        )

        variants = await generator._parse_variants(response, sample_manifest)

        assert "success" in variants
        assert variants["success"].variant_type == VariantType.SUCCESS
        assert variants["success"].narrative == "You succeed!"

    async def test_parse_variants_with_state_deltas(
        self, mock_db, mock_game_session, mock_llm, sample_manifest
    ):
        """Test parsing variants with state deltas."""
        generator = BranchGenerator(mock_db, mock_game_session, mock_llm)

        response = BranchGenerationResponse(
            variants=[
                GeneratedVariant(
                    variant_type="success",
                    narrative="You pick up the item.",
                    state_deltas=[
                        GeneratedStateDelta(
                            delta_type="transfer_item",
                            target_key="sword_001",
                            changes={"holder_id": "player"},
                        ),
                    ],
                    time_passed_minutes=1,
                ),
            ],
            action_summary="Pick up item",
        )

        variants = await generator._parse_variants(response, sample_manifest)

        # State deltas may include auto-created items if needed
        assert len(variants["success"].state_deltas) >= 1
        # Find the original TRANSFER_ITEM delta
        transfer_delta = next(
            d for d in variants["success"].state_deltas if d.target_key == "sword_001"
        )
        assert transfer_delta.target_key == "sword_001"

    async def test_parse_variants_with_skill_check(
        self, mock_db, mock_game_session, mock_llm, sample_manifest
    ):
        """Test parsing variants with skill checks."""
        generator = BranchGenerator(mock_db, mock_game_session, mock_llm)

        response = BranchGenerationResponse(
            variants=[
                GeneratedVariant(
                    variant_type="success",
                    narrative="You pick the lock!",
                    state_deltas=[],
                    time_passed_minutes=5,
                    requires_skill_check=True,
                    skill="lockpicking",
                    dc=15,
                ),
            ],
            action_summary="Pick lock",
        )

        variants = await generator._parse_variants(response, sample_manifest)

        assert variants["success"].requires_dice is True
        assert variants["success"].skill == "lockpicking"
        assert variants["success"].dc == 15

    async def test_parse_variants_unknown_type_skipped(
        self, mock_db, mock_game_session, mock_llm, sample_manifest
    ):
        """Test that unknown variant types are skipped."""
        generator = BranchGenerator(mock_db, mock_game_session, mock_llm)

        response = BranchGenerationResponse(
            variants=[
                GeneratedVariant(
                    variant_type="unknown_type",
                    narrative="Mystery!",
                    state_deltas=[],
                    time_passed_minutes=1,
                ),
                GeneratedVariant(
                    variant_type="success",
                    narrative="Valid!",
                    state_deltas=[],
                    time_passed_minutes=1,
                ),
            ],
            action_summary="Test",
        )

        variants = await generator._parse_variants(response, sample_manifest)

        # Unknown type skipped, success included
        assert "unknown_type" not in variants
        assert "success" in variants


class TestFallbackVariants:
    """Tests for fallback variant generation."""

    def test_fallback_includes_success(self, mock_db, mock_game_session, mock_llm):
        """Test that fallback always includes success."""
        generator = BranchGenerator(mock_db, mock_game_session, mock_llm)

        action = ActionPrediction(
            action_type=ActionType.OBSERVE,
            target_key=None,
            input_patterns=[],
            probability=0.2,
            reason=PredictionReason.ADJACENT,
        )
        decision = GMDecision(decision_type="no_twist", probability=0.7)

        variants = generator._generate_fallback_variants(action, decision)

        assert "success" in variants

    def test_fallback_includes_failure_for_skill_actions(
        self, mock_db, mock_game_session, mock_llm
    ):
        """Test that fallback includes failure for skill-based actions."""
        generator = BranchGenerator(mock_db, mock_game_session, mock_llm)

        action = ActionPrediction(
            action_type=ActionType.SKILL_USE,
            target_key="lock_001",
            input_patterns=[],
            probability=0.2,
            reason=PredictionReason.MENTIONED,
        )
        decision = GMDecision(decision_type="no_twist", probability=0.7)

        variants = generator._generate_fallback_variants(action, decision)

        assert "success" in variants
        assert "failure" in variants
        assert variants["failure"].requires_dice is True


class TestBranchContext:
    """Tests for BranchContext dataclass."""

    def test_create_context(self):
        """Test creating branch context."""
        context = BranchContext(
            location_key="tavern",
            location_display="The Tavern",
            player_key="player_001",
            game_time="10:00",
            game_day=1,
            recent_events=["Event 1", "Event 2"],
        )

        assert context.location_key == "tavern"
        assert context.game_day == 1
        assert len(context.recent_events) == 2


class TestSystemPromptContent:
    """Tests for system prompt content - verifying critical guidance is present."""

    def test_system_prompt_includes_position_vs_location_guidance(
        self, mock_db, mock_game_session, mock_llm
    ):
        """The system prompt should include guidance on position vs location changes.

        This is critical to prevent the LLM from generating UPDATE_LOCATION deltas
        for position changes within a room (e.g., "sneak behind the bar" should not
        create an UPDATE_LOCATION to "tavern_cellar").
        """
        generator = BranchGenerator(mock_db, mock_game_session, mock_llm)
        prompt = generator._get_system_prompt()

        # Should have the position vs location distinction
        assert "UPDATE_LOCATION vs POSITION CHANGE" in prompt
        assert "Position changes within a room do NOT require update_location" in prompt

        # Should give clear examples
        assert "sneak behind the bar" in prompt.lower()
        assert "same room" in prompt.lower()

    def test_system_prompt_warns_against_hallucinating_locations(
        self, mock_db, mock_game_session, mock_llm
    ):
        """The prompt should warn against inventing location keys."""
        generator = BranchGenerator(mock_db, mock_game_session, mock_llm)
        prompt = generator._get_system_prompt()

        # Should warn about using exact keys from exits
        assert "EXACT location_key from the Exits" in prompt
        assert "NEVER derive or invent keys" in prompt

    def test_system_prompt_includes_skill_check_rules(
        self, mock_db, mock_game_session, mock_llm
    ):
        """The prompt should include skill check rules for SKILL_USE actions."""
        generator = BranchGenerator(mock_db, mock_game_session, mock_llm)
        prompt = generator._get_system_prompt()

        # Should have skill check rules
        assert "SKILL CHECK RULES" in prompt
        assert "stealth" in prompt.lower()
        assert "requires_skill_check" in prompt

    def test_system_prompt_includes_entity_grounding_rules(
        self, mock_db, mock_game_session, mock_llm
    ):
        """The prompt should enforce entity grounding rules."""
        generator = BranchGenerator(mock_db, mock_game_session, mock_llm)
        prompt = generator._get_system_prompt()

        # Should enforce [key:display] format
        assert "[entity_key:display_name]" in prompt or "[key:display]" in prompt.lower()
        # Should warn against hallucinating entities
        assert "ONLY reference entities that appear" in prompt or "Do NOT invent" in prompt
