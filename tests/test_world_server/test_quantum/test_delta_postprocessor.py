"""Tests for the Delta Post-Processor module."""

import pytest

from src.gm.grounding import GroundedEntity, GroundingManifest
from src.world_server.quantum.delta_postprocessor import (
    ITEM_TYPE_HINTS,
    DeltaPostProcessor,
    PostProcessResult,
    RegenerationNeeded,
)
from src.world_server.quantum.schemas import DeltaType, StateDelta


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_manifest() -> GroundingManifest:
    """Create a sample grounding manifest for tests."""
    return GroundingManifest(
        location_key="tavern_001",
        location_display="The Rusty Tankard",
        player_key="test_hero",
        player_display="you",
        npcs={
            "bartender_001": GroundedEntity(
                key="bartender_001",
                display_name="Old Tom",
                entity_type="npc",
                short_description="the bartender",
            ),
        },
        items_at_location={
            "ale_mug_001": GroundedEntity(
                key="ale_mug_001",
                display_name="mug of ale",
                entity_type="item",
                short_description="a frothy mug",
            ),
        },
        inventory={
            "gold_coins_001": GroundedEntity(
                key="gold_coins_001",
                display_name="gold coins",
                entity_type="item",
                short_description="10 gold pieces",
            ),
        },
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
def processor(sample_manifest: GroundingManifest) -> DeltaPostProcessor:
    """Create a post-processor with sample manifest."""
    return DeltaPostProcessor(sample_manifest)


# =============================================================================
# Test: Inject Missing CREATE_ENTITY
# =============================================================================


class TestInjectMissingCreates:
    """Tests for auto-injecting CREATE_ENTITY before TRANSFER_ITEM."""

    def test_inject_create_for_unknown_item(
        self, processor: DeltaPostProcessor
    ) -> None:
        """TRANSFER_ITEM for non-existent item should inject CREATE_ENTITY."""
        deltas = [
            StateDelta(
                delta_type=DeltaType.TRANSFER_ITEM,
                target_key="mysterious_key_001",
                changes={"to_entity_key": "test_hero"},
            ),
        ]

        result = processor.process(deltas)

        assert not result.needs_regeneration
        assert len(result.deltas) == 2  # CREATE + TRANSFER

        # First delta should be CREATE_ENTITY
        create_delta = result.deltas[0]
        assert create_delta.delta_type == DeltaType.CREATE_ENTITY
        assert create_delta.target_key == "mysterious_key_001"
        assert create_delta.changes["entity_type"] == "key"
        assert create_delta.changes["display_name"] == "Mysterious Key"

        # Second should be the original TRANSFER
        assert result.deltas[1].delta_type == DeltaType.TRANSFER_ITEM

        # Should log the repair
        assert any("Injected CREATE_ENTITY" in r for r in result.repairs_made)

    def test_no_inject_for_existing_item(
        self, processor: DeltaPostProcessor
    ) -> None:
        """TRANSFER_ITEM for existing item should not inject CREATE."""
        deltas = [
            StateDelta(
                delta_type=DeltaType.TRANSFER_ITEM,
                target_key="ale_mug_001",  # Exists in items_at_location
                changes={"to_entity_key": "test_hero"},
            ),
        ]

        result = processor.process(deltas)

        assert not result.needs_regeneration
        assert len(result.deltas) == 1  # Just the TRANSFER
        assert len(result.repairs_made) == 0

    def test_no_inject_for_inventory_item(
        self, processor: DeltaPostProcessor
    ) -> None:
        """TRANSFER_ITEM for inventory item should not inject CREATE."""
        deltas = [
            StateDelta(
                delta_type=DeltaType.TRANSFER_ITEM,
                target_key="gold_coins_001",  # Exists in inventory
                changes={"to_entity_key": "bartender_001"},
            ),
        ]

        result = processor.process(deltas)

        assert len(result.deltas) == 1
        assert len(result.repairs_made) == 0

    def test_no_inject_if_create_exists(
        self, processor: DeltaPostProcessor
    ) -> None:
        """Don't inject if CREATE_ENTITY already in delta list."""
        deltas = [
            StateDelta(
                delta_type=DeltaType.CREATE_ENTITY,
                target_key="new_sword_001",
                changes={"entity_type": "weapon", "display_name": "New Sword"},
            ),
            StateDelta(
                delta_type=DeltaType.TRANSFER_ITEM,
                target_key="new_sword_001",
                changes={"to_entity_key": "test_hero"},
            ),
        ]

        result = processor.process(deltas)

        # Should only have the original 2 deltas (reordered)
        assert len(result.deltas) == 2
        assert not any("Injected" in r for r in result.repairs_made)

    def test_inject_multiple_missing_items(
        self, processor: DeltaPostProcessor
    ) -> None:
        """Should inject CREATE for each missing item."""
        deltas = [
            StateDelta(
                delta_type=DeltaType.TRANSFER_ITEM,
                target_key="bread_loaf_001",
                changes={"to_entity_key": "test_hero"},
            ),
            StateDelta(
                delta_type=DeltaType.TRANSFER_ITEM,
                target_key="water_flask_001",
                changes={"to_entity_key": "test_hero"},
            ),
        ]

        result = processor.process(deltas)

        assert len(result.deltas) == 4  # 2 CREATEs + 2 TRANSFERs
        creates = [d for d in result.deltas if d.delta_type == DeltaType.CREATE_ENTITY]
        assert len(creates) == 2

    def test_no_duplicate_creates(
        self, processor: DeltaPostProcessor
    ) -> None:
        """Multiple TRANSFERs for same item should only get one CREATE."""
        deltas = [
            StateDelta(
                delta_type=DeltaType.TRANSFER_ITEM,
                target_key="magic_ring_001",
                changes={"to_entity_key": "test_hero"},
            ),
            StateDelta(
                delta_type=DeltaType.TRANSFER_ITEM,
                target_key="magic_ring_001",  # Same item
                changes={"to_entity_key": "bartender_001"},
            ),
        ]

        result = processor.process(deltas)

        creates = [d for d in result.deltas if d.delta_type == DeltaType.CREATE_ENTITY]
        assert len(creates) == 1


# =============================================================================
# Test: Infer Entity Type
# =============================================================================


class TestInferEntityType:
    """Tests for inferring entity type from key name."""

    @pytest.mark.parametrize(
        "key,expected_type",
        [
            ("iron_sword_001", "weapon"),
            ("rusty_dagger", "weapon"),
            ("wooden_axe_003", "weapon"),
            ("fresh_bread", "food"),
            ("red_apple_001", "food"),
            ("roasted_meat", "food"),
            ("cold_ale", "drink"),
            ("spring_water", "drink"),
            ("red_wine_001", "drink"),
            ("healing_potion", "consumable"),
            ("old_chest", "container"),
            ("wooden_box_001", "container"),
            ("leather_bag", "container"),
            ("iron_key", "key"),
            ("golden_key_001", "key"),
            ("silver_coin", "misc"),
            ("gold_coins_001", "misc"),
            ("ancient_book", "misc"),
            ("mysterious_scroll", "misc"),
            ("worn_rope", "tool"),
            ("lit_torch_001", "tool"),
            ("warm_cloak", "clothing"),
            ("leather_boots_001", "clothing"),
            ("steel_armor", "armor"),
            ("wooden_shield_001", "armor"),
            ("unknown_thing_001", "item"),  # Fallback
        ],
    )
    def test_infer_type_from_key(
        self, processor: DeltaPostProcessor, key: str, expected_type: str
    ) -> None:
        """Should infer correct entity type from key name."""
        assert processor._infer_entity_type(key) == expected_type


# =============================================================================
# Test: Key to Display Name
# =============================================================================


class TestKeyToDisplayName:
    """Tests for converting keys to display names."""

    @pytest.mark.parametrize(
        "key,expected_name",
        [
            ("iron_sword_001", "Iron Sword"),
            ("fresh_bread", "Fresh Bread"),
            ("innkeeper_box_key", "Innkeeper Box Key"),
            ("ale_mug", "Ale Mug"),
            ("mysterious_stranger_note_003", "Mysterious Stranger Note"),
        ],
    )
    def test_key_to_display_name(
        self, processor: DeltaPostProcessor, key: str, expected_name: str
    ) -> None:
        """Should convert key to proper display name."""
        assert processor._key_to_display_name(key) == expected_name


# =============================================================================
# Test: Reorder Deltas
# =============================================================================


class TestReorderDeltas:
    """Tests for delta reordering."""

    def test_create_moved_before_transfer(
        self, processor: DeltaPostProcessor
    ) -> None:
        """CREATE_ENTITY should come before TRANSFER_ITEM."""
        deltas = [
            StateDelta(
                delta_type=DeltaType.TRANSFER_ITEM,
                target_key="sword_001",
                changes={"to_entity_key": "test_hero"},
            ),
            StateDelta(
                delta_type=DeltaType.CREATE_ENTITY,
                target_key="sword_001",
                changes={"entity_type": "weapon"},
            ),
        ]

        result = processor.process(deltas)

        assert result.deltas[0].delta_type == DeltaType.CREATE_ENTITY
        assert result.deltas[1].delta_type == DeltaType.TRANSFER_ITEM
        assert any("Reordered" in r for r in result.repairs_made)

    def test_already_ordered_no_repair_log(
        self, processor: DeltaPostProcessor
    ) -> None:
        """Already correct order should not log reorder repair."""
        deltas = [
            StateDelta(
                delta_type=DeltaType.CREATE_ENTITY,
                target_key="sword_001",
                changes={"entity_type": "weapon", "display_name": "Sword"},
            ),
            StateDelta(
                delta_type=DeltaType.TRANSFER_ITEM,
                target_key="sword_001",
                changes={"to_entity_key": "test_hero"},
            ),
        ]

        result = processor.process(deltas)

        assert not any("Reordered" in r for r in result.repairs_made)


# =============================================================================
# Test: Clamp Values
# =============================================================================


class TestClampValues:
    """Tests for clamping out-of-range values."""

    def test_clamp_need_above_100(self, processor: DeltaPostProcessor) -> None:
        """Need values above 100 should be clamped."""
        deltas = [
            StateDelta(
                delta_type=DeltaType.UPDATE_NEED,
                target_key="test_hero",
                changes={"hunger": 150, "thirst": 100},
            ),
        ]

        result = processor.process(deltas)

        assert result.deltas[0].changes["hunger"] == 100
        assert result.deltas[0].changes["thirst"] == 100  # Unchanged
        assert any("Clamped need hunger=150" in r for r in result.repairs_made)

    def test_clamp_need_below_0(self, processor: DeltaPostProcessor) -> None:
        """Need values below 0 should be clamped."""
        deltas = [
            StateDelta(
                delta_type=DeltaType.UPDATE_NEED,
                target_key="test_hero",
                changes={"stamina": -10},
            ),
        ]

        result = processor.process(deltas)

        assert result.deltas[0].changes["stamina"] == 0
        assert any("Clamped need stamina=-10" in r for r in result.repairs_made)

    def test_clamp_relationship_values(
        self, processor: DeltaPostProcessor
    ) -> None:
        """Relationship values should be clamped to 0-100."""
        deltas = [
            StateDelta(
                delta_type=DeltaType.UPDATE_RELATIONSHIP,
                target_key="relationship_001",
                changes={"trust": 120, "liking": -5, "respect": 50},
            ),
        ]

        result = processor.process(deltas)

        assert result.deltas[0].changes["trust"] == 100
        assert result.deltas[0].changes["liking"] == 0
        assert result.deltas[0].changes["respect"] == 50  # Unchanged

    def test_knows_not_clamped(self, processor: DeltaPostProcessor) -> None:
        """The 'knows' field is boolean, should not be clamped."""
        deltas = [
            StateDelta(
                delta_type=DeltaType.UPDATE_RELATIONSHIP,
                target_key="relationship_001",
                changes={"knows": True},
            ),
        ]

        result = processor.process(deltas)

        assert result.deltas[0].changes["knows"] is True
        assert len(result.repairs_made) == 0


# =============================================================================
# Test: Fix Fact Categories
# =============================================================================


class TestFixFactCategories:
    """Tests for fixing invalid fact categories."""

    def test_fix_invalid_category(self, processor: DeltaPostProcessor) -> None:
        """Invalid category should default to 'personal'."""
        deltas = [
            StateDelta(
                delta_type=DeltaType.RECORD_FACT,
                target_key="test_hero",
                changes={
                    "predicate": "knows_about",
                    "value": "secret passage",
                    "category": "quest",  # Invalid
                },
            ),
        ]

        result = processor.process(deltas)

        assert result.deltas[0].changes["category"] == "personal"
        assert any("Fixed fact category 'quest'" in r for r in result.repairs_made)

    def test_valid_category_unchanged(
        self, processor: DeltaPostProcessor
    ) -> None:
        """Valid category should remain unchanged."""
        deltas = [
            StateDelta(
                delta_type=DeltaType.RECORD_FACT,
                target_key="test_hero",
                changes={
                    "predicate": "knows_about",
                    "value": "secret passage",
                    "category": "secret",  # Valid
                },
            ),
        ]

        result = processor.process(deltas)

        assert result.deltas[0].changes["category"] == "secret"
        assert len(result.repairs_made) == 0


# =============================================================================
# Test: Normalize Entity Types
# =============================================================================


class TestNormalizeEntityTypes:
    """Tests for normalizing entity_type in CREATE_ENTITY."""

    def test_normalize_unknown_type(
        self, processor: DeltaPostProcessor
    ) -> None:
        """Unknown entity_type should be inferred from key."""
        deltas = [
            StateDelta(
                delta_type=DeltaType.CREATE_ENTITY,
                target_key="iron_sword_001",
                changes={"entity_type": "unknown", "display_name": "Iron Sword"},
            ),
        ]

        result = processor.process(deltas)

        assert result.deltas[0].changes["entity_type"] == "weapon"
        assert any("Normalized entity_type" in r for r in result.repairs_made)

    def test_valid_type_unchanged(self, processor: DeltaPostProcessor) -> None:
        """Valid entity_type should remain unchanged."""
        deltas = [
            StateDelta(
                delta_type=DeltaType.CREATE_ENTITY,
                target_key="sword_001",
                changes={"entity_type": "weapon", "display_name": "Sword"},
            ),
        ]

        result = processor.process(deltas)

        assert result.deltas[0].changes["entity_type"] == "weapon"
        assert not any("Normalized" in r for r in result.repairs_made)


# =============================================================================
# Test: Conflict Detection (Needs Regeneration)
# =============================================================================


class TestConflictDetection:
    """Tests for detecting unfixable conflicts."""

    def test_create_delete_conflict(
        self, processor: DeltaPostProcessor
    ) -> None:
        """CREATE + DELETE for same entity should trigger regeneration."""
        deltas = [
            StateDelta(
                delta_type=DeltaType.CREATE_ENTITY,
                target_key="npc_001",
                changes={"entity_type": "npc"},
            ),
            StateDelta(
                delta_type=DeltaType.DELETE_ENTITY,
                target_key="npc_001",
                changes={},
            ),
        ]

        result = processor.process(deltas)

        assert result.needs_regeneration
        assert "Conflicting CREATE and DELETE" in result.regeneration_reason

    def test_duplicate_create(self, processor: DeltaPostProcessor) -> None:
        """Multiple CREATE_ENTITY for same key should trigger regeneration."""
        deltas = [
            StateDelta(
                delta_type=DeltaType.CREATE_ENTITY,
                target_key="item_001",
                changes={"entity_type": "item"},
            ),
            StateDelta(
                delta_type=DeltaType.CREATE_ENTITY,
                target_key="item_001",
                changes={"entity_type": "weapon"},
            ),
        ]

        result = processor.process(deltas)

        assert result.needs_regeneration
        assert "Duplicate CREATE_ENTITY" in result.regeneration_reason

    def test_negative_time(self, processor: DeltaPostProcessor) -> None:
        """Negative time advancement should trigger regeneration."""
        deltas = [
            StateDelta(
                delta_type=DeltaType.ADVANCE_TIME,
                target_key="time",
                changes={"minutes": -30},
            ),
        ]

        result = processor.process(deltas)

        assert result.needs_regeneration
        assert "Negative time" in result.regeneration_reason


# =============================================================================
# Test: Unknown Key Detection (Needs Regeneration)
# =============================================================================


class TestUnknownKeyDetection:
    """Tests for detecting unknown entity references."""

    def test_update_entity_unknown_key(
        self, processor: DeltaPostProcessor
    ) -> None:
        """UPDATE_ENTITY for unknown entity should trigger regeneration."""
        deltas = [
            StateDelta(
                delta_type=DeltaType.UPDATE_ENTITY,
                target_key="nonexistent_npc",
                changes={"mood": "happy"},
            ),
        ]

        result = processor.process(deltas)

        assert result.needs_regeneration
        assert "UPDATE_ENTITY references unknown entity" in result.regeneration_reason

    def test_update_entity_with_create(
        self, processor: DeltaPostProcessor
    ) -> None:
        """UPDATE_ENTITY is OK if CREATE_ENTITY precedes it."""
        deltas = [
            StateDelta(
                delta_type=DeltaType.CREATE_ENTITY,
                target_key="new_npc",
                changes={"entity_type": "npc", "display_name": "New NPC"},
            ),
            StateDelta(
                delta_type=DeltaType.UPDATE_ENTITY,
                target_key="new_npc",
                changes={"mood": "happy"},
            ),
        ]

        result = processor.process(deltas)

        assert not result.needs_regeneration

    def test_update_relationship_unknown_from(
        self, processor: DeltaPostProcessor
    ) -> None:
        """UPDATE_RELATIONSHIP with unknown from_key should trigger regeneration."""
        deltas = [
            StateDelta(
                delta_type=DeltaType.UPDATE_RELATIONSHIP,
                target_key="rel_001",
                changes={
                    "from_key": "unknown_npc",
                    "to_key": "test_hero",
                    "trust": 10,
                },
            ),
        ]

        result = processor.process(deltas)

        assert result.needs_regeneration
        assert "from_key 'unknown_npc' unknown" in result.regeneration_reason

    def test_update_relationship_known_keys(
        self, processor: DeltaPostProcessor
    ) -> None:
        """UPDATE_RELATIONSHIP with known keys should not trigger regeneration."""
        deltas = [
            StateDelta(
                delta_type=DeltaType.UPDATE_RELATIONSHIP,
                target_key="rel_001",
                changes={
                    "from_key": "bartender_001",  # Exists in manifest
                    "to_key": "test_hero",  # Player key
                    "trust": 10,
                },
            ),
        ]

        result = processor.process(deltas)

        assert not result.needs_regeneration

    def test_update_location_unknown_entity(
        self, processor: DeltaPostProcessor
    ) -> None:
        """UPDATE_LOCATION for unknown entity should trigger regeneration."""
        deltas = [
            StateDelta(
                delta_type=DeltaType.UPDATE_LOCATION,
                target_key="unknown_entity",
                changes={"location_key": "market_001"},
            ),
        ]

        result = processor.process(deltas)

        assert result.needs_regeneration
        assert "UPDATE_LOCATION for unknown entity" in result.regeneration_reason


# =============================================================================
# Test: Exception Class
# =============================================================================


class TestRegenerationNeededException:
    """Tests for RegenerationNeeded exception."""

    def test_exception_message(self) -> None:
        """Exception should include reason in message."""
        exc = RegenerationNeeded("Conflicting deltas")
        assert "Conflicting deltas" in str(exc)
        assert exc.reason == "Conflicting deltas"


# =============================================================================
# Test: Full Processing Flow
# =============================================================================


class TestFullProcessingFlow:
    """Integration tests for the full post-processing flow."""

    def test_multiple_repairs(self, processor: DeltaPostProcessor) -> None:
        """Should apply all applicable repairs."""
        deltas = [
            # Will inject CREATE and reorder
            StateDelta(
                delta_type=DeltaType.TRANSFER_ITEM,
                target_key="fresh_bread_001",
                changes={"to_entity_key": "test_hero"},
            ),
            # Will clamp value
            StateDelta(
                delta_type=DeltaType.UPDATE_NEED,
                target_key="test_hero",
                changes={"hunger": 150},
            ),
            # Will fix category
            StateDelta(
                delta_type=DeltaType.RECORD_FACT,
                target_key="world",
                changes={"predicate": "has", "value": "bread", "category": "invalid"},
            ),
        ]

        result = processor.process(deltas)

        assert not result.needs_regeneration
        assert len(result.repairs_made) >= 3

        # Check CREATE was injected
        creates = [d for d in result.deltas if d.delta_type == DeltaType.CREATE_ENTITY]
        assert len(creates) == 1
        assert creates[0].changes["entity_type"] == "food"

    def test_regeneration_stops_repairs(
        self, processor: DeltaPostProcessor
    ) -> None:
        """Regeneration-triggering issues should be detected first."""
        deltas = [
            # Would be repairable
            StateDelta(
                delta_type=DeltaType.UPDATE_NEED,
                target_key="test_hero",
                changes={"hunger": 150},
            ),
            # Triggers regeneration
            StateDelta(
                delta_type=DeltaType.ADVANCE_TIME,
                target_key="time",
                changes={"minutes": -10},
            ),
        ]

        result = processor.process(deltas)

        assert result.needs_regeneration
        # Repairs should NOT be applied when regeneration is needed
        assert len(result.repairs_made) == 0


# =============================================================================
# Test: Fuzzy Key Matching
# =============================================================================


class TestFindSimilarKeys:
    """Tests for fuzzy key matching."""

    def test_find_exact_match(self, sample_manifest: GroundingManifest) -> None:
        """Exact match should have high score."""
        processor = DeltaPostProcessor(sample_manifest)
        all_keys = list(sample_manifest.all_keys())

        # Add some test keys
        all_keys.extend(["farmer_marcus_001", "marcus_the_farmer"])

        matches = processor._find_similar_keys("farmer_marcus_001", all_keys)

        assert "farmer_marcus_001" in matches

    def test_find_similar_key(self, sample_manifest: GroundingManifest) -> None:
        """Similar keys should be found."""
        processor = DeltaPostProcessor(sample_manifest)
        all_keys = ["farmer_marcus_001", "farmer_john_001", "blacksmith_001"]

        matches = processor._find_similar_keys("farmer_marcus", all_keys)

        assert "farmer_marcus_001" in matches

    def test_no_matches_below_threshold(
        self, sample_manifest: GroundingManifest
    ) -> None:
        """Keys too different should not match."""
        processor = DeltaPostProcessor(sample_manifest)
        all_keys = ["dragon_001", "castle_002", "sword_003"]

        matches = processor._find_similar_keys("farmer_marcus", all_keys)

        assert len(matches) == 0

    def test_limit_results(self, sample_manifest: GroundingManifest) -> None:
        """Should respect the limit parameter."""
        processor = DeltaPostProcessor(sample_manifest)
        all_keys = [
            "farmer_marcus_001",
            "farmer_marcus_002",
            "farmer_marcus_003",
            "farmer_marcus_004",
        ]

        matches = processor._find_similar_keys("farmer_marcus", all_keys, limit=2)

        assert len(matches) <= 2


# =============================================================================
# Test: Collect Unknown Keys
# =============================================================================


class TestCollectUnknownKeys:
    """Tests for collecting unknown entity keys."""

    def test_collect_unknown_update_entity(
        self, sample_manifest: GroundingManifest
    ) -> None:
        """Should collect unknown keys from UPDATE_ENTITY."""
        processor = DeltaPostProcessor(sample_manifest)
        deltas = [
            StateDelta(
                delta_type=DeltaType.UPDATE_ENTITY,
                target_key="unknown_npc_001",
                changes={"mood": "happy"},
            ),
        ]

        unknown = processor._collect_unknown_keys(deltas)

        assert "unknown_npc_001" in unknown

    def test_collect_unknown_relationship_keys(
        self, sample_manifest: GroundingManifest
    ) -> None:
        """Should collect unknown from/to keys in UPDATE_RELATIONSHIP."""
        processor = DeltaPostProcessor(sample_manifest)
        deltas = [
            StateDelta(
                delta_type=DeltaType.UPDATE_RELATIONSHIP,
                target_key="relationship_001",
                changes={
                    "from_key": "unknown_from",
                    "to_key": "unknown_to",
                    "trust": 50,
                },
            ),
        ]

        unknown = processor._collect_unknown_keys(deltas)

        assert "unknown_from" in unknown
        assert "unknown_to" in unknown

    def test_known_keys_not_collected(
        self, sample_manifest: GroundingManifest
    ) -> None:
        """Known keys should not be collected."""
        processor = DeltaPostProcessor(sample_manifest)
        deltas = [
            StateDelta(
                delta_type=DeltaType.UPDATE_ENTITY,
                target_key="bartender_001",  # Known from manifest
                changes={"mood": "happy"},
            ),
        ]

        unknown = processor._collect_unknown_keys(deltas)

        assert len(unknown) == 0

    def test_created_keys_not_collected(
        self, sample_manifest: GroundingManifest
    ) -> None:
        """Keys in CREATE_ENTITY should not be collected as unknown."""
        processor = DeltaPostProcessor(sample_manifest)
        deltas = [
            StateDelta(
                delta_type=DeltaType.CREATE_ENTITY,
                target_key="new_item_001",
                changes={"entity_type": "item"},
            ),
            StateDelta(
                delta_type=DeltaType.UPDATE_ENTITY,
                target_key="new_item_001",  # Will be created
                changes={"description": "shiny"},
            ),
        ]

        unknown = processor._collect_unknown_keys(deltas)

        assert "new_item_001" not in unknown


# =============================================================================
# Test: Apply Key Replacements
# =============================================================================


class TestApplyKeyReplacements:
    """Tests for key replacement."""

    def test_replace_target_key(self, sample_manifest: GroundingManifest) -> None:
        """Should replace target_key in deltas."""
        processor = DeltaPostProcessor(sample_manifest)
        deltas = [
            StateDelta(
                delta_type=DeltaType.UPDATE_ENTITY,
                target_key="farmer_marcus",
                changes={"mood": "happy"},
            ),
        ]
        replacements = {"farmer_marcus": "farmer_marcus_001"}

        result = processor._apply_key_replacements(deltas, replacements)

        assert result[0].target_key == "farmer_marcus_001"

    def test_replace_from_to_keys(self, sample_manifest: GroundingManifest) -> None:
        """Should replace from_key and to_key in changes."""
        processor = DeltaPostProcessor(sample_manifest)
        deltas = [
            StateDelta(
                delta_type=DeltaType.UPDATE_RELATIONSHIP,
                target_key="relationship_001",
                changes={
                    "from_key": "npc_a",
                    "to_key": "npc_b",
                    "trust": 50,
                },
            ),
        ]
        replacements = {"npc_a": "npc_a_001", "npc_b": "npc_b_002"}

        result = processor._apply_key_replacements(deltas, replacements)

        assert result[0].changes["from_key"] == "npc_a_001"
        assert result[0].changes["to_key"] == "npc_b_002"

    def test_no_replacements_returns_original(
        self, sample_manifest: GroundingManifest
    ) -> None:
        """Empty replacements should return original deltas."""
        processor = DeltaPostProcessor(sample_manifest)
        deltas = [
            StateDelta(
                delta_type=DeltaType.UPDATE_ENTITY,
                target_key="some_key",
                changes={"mood": "happy"},
            ),
        ]

        result = processor._apply_key_replacements(deltas, {})

        assert result is deltas  # Same object


# =============================================================================
# Test: Inject Creates for Keys
# =============================================================================


class TestInjectCreatesForKeys:
    """Tests for injecting CREATE_ENTITY for new keys."""

    def test_inject_creates(self, sample_manifest: GroundingManifest) -> None:
        """Should inject CREATE_ENTITY for new keys."""
        processor = DeltaPostProcessor(sample_manifest)
        deltas = [
            StateDelta(
                delta_type=DeltaType.UPDATE_ENTITY,
                target_key="new_npc_001",
                changes={"mood": "happy"},
            ),
        ]
        keys_to_create = {"new_npc_001"}

        result = processor._inject_creates_for_keys(deltas, keys_to_create)

        # CREATE should be first
        assert result[0].delta_type == DeltaType.CREATE_ENTITY
        assert result[0].target_key == "new_npc_001"
        assert "entity_type" in result[0].changes
        assert "display_name" in result[0].changes

    def test_empty_keys_returns_original(
        self, sample_manifest: GroundingManifest
    ) -> None:
        """Empty keys_to_create should return original."""
        processor = DeltaPostProcessor(sample_manifest)
        deltas = [
            StateDelta(
                delta_type=DeltaType.UPDATE_ENTITY,
                target_key="some_key",
                changes={"mood": "happy"},
            ),
        ]

        result = processor._inject_creates_for_keys(deltas, set())

        assert result is deltas


# =============================================================================
# Test: Async Processing with LLM Clarification
# =============================================================================


class TestProcessAsync:
    """Tests for async processing with LLM clarification."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM that returns specific responses."""
        from unittest.mock import AsyncMock, MagicMock

        llm = MagicMock()
        llm.complete = AsyncMock()
        return llm

    async def test_process_async_no_unknown_keys(
        self, sample_manifest: GroundingManifest, mock_llm
    ) -> None:
        """Should work without LLM calls when no unknown keys."""
        processor = DeltaPostProcessor(sample_manifest)
        deltas = [
            StateDelta(
                delta_type=DeltaType.UPDATE_ENTITY,
                target_key="bartender_001",  # Known
                changes={"mood": "happy"},
            ),
        ]

        result = await processor.process_async(deltas, mock_llm)

        assert not result.needs_regeneration
        mock_llm.complete.assert_not_called()

    async def test_process_async_llm_picks_existing_key(
        self, sample_manifest: GroundingManifest, mock_llm
    ) -> None:
        """LLM picks an existing key from options."""
        from unittest.mock import MagicMock

        # LLM returns "1" to pick first option
        mock_response = MagicMock()
        mock_response.content = "1"
        mock_llm.complete.return_value = mock_response

        # Add similar key to manifest
        sample_manifest.npcs["farmer_marcus_001"] = GroundedEntity(
            key="farmer_marcus_001",
            display_name="Marcus",
            entity_type="npc",
            short_description="a farmer",
        )

        processor = DeltaPostProcessor(sample_manifest)
        deltas = [
            StateDelta(
                delta_type=DeltaType.UPDATE_ENTITY,
                target_key="farmer_marcus",  # Typo - missing _001
                changes={"mood": "happy"},
            ),
        ]

        result = await processor.process_async(deltas, mock_llm)

        assert not result.needs_regeneration
        # Key should be replaced
        assert result.deltas[0].target_key == "farmer_marcus_001"
        assert any("clarified" in r.lower() for r in result.repairs_made)

    async def test_process_async_llm_creates_new_entity(
        self, sample_manifest: GroundingManifest, mock_llm
    ) -> None:
        """LLM picks 'create new entity' option."""
        from unittest.mock import MagicMock

        # LLM returns "3" (or high number) to create new
        mock_response = MagicMock()
        mock_response.content = "3"
        mock_llm.complete.return_value = mock_response

        processor = DeltaPostProcessor(sample_manifest)
        deltas = [
            StateDelta(
                delta_type=DeltaType.UPDATE_ENTITY,
                target_key="completely_new_entity",
                changes={"mood": "happy"},
            ),
        ]

        result = await processor.process_async(deltas, mock_llm)

        assert not result.needs_regeneration
        # Should have CREATE_ENTITY delta
        creates = [d for d in result.deltas if d.delta_type == DeltaType.CREATE_ENTITY]
        assert len(creates) >= 1
        assert any("completely_new_entity" in c.target_key for c in creates)

    async def test_process_async_conflict_still_triggers_regen(
        self, sample_manifest: GroundingManifest, mock_llm
    ) -> None:
        """Hard conflicts should still trigger regeneration."""
        processor = DeltaPostProcessor(sample_manifest)
        deltas = [
            StateDelta(
                delta_type=DeltaType.CREATE_ENTITY,
                target_key="some_key",
                changes={"entity_type": "item"},
            ),
            StateDelta(
                delta_type=DeltaType.DELETE_ENTITY,
                target_key="some_key",  # Conflict!
                changes={},
            ),
        ]

        result = await processor.process_async(deltas, mock_llm)

        assert result.needs_regeneration
        assert "Conflicting" in (result.regeneration_reason or "")

    async def test_process_async_llm_error_defaults_to_create(
        self, sample_manifest: GroundingManifest, mock_llm
    ) -> None:
        """LLM errors should default to creating new entity."""
        # LLM raises exception
        mock_llm.complete.side_effect = Exception("LLM unavailable")

        processor = DeltaPostProcessor(sample_manifest)
        deltas = [
            StateDelta(
                delta_type=DeltaType.UPDATE_ENTITY,
                target_key="unknown_entity",
                changes={"mood": "happy"},
            ),
        ]

        result = await processor.process_async(deltas, mock_llm)

        assert not result.needs_regeneration
        # Should have CREATE_ENTITY as fallback
        creates = [d for d in result.deltas if d.delta_type == DeltaType.CREATE_ENTITY]
        assert len(creates) >= 1
