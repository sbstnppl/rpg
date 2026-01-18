"""Tests for the Delta Translator (Phase 3 of split architecture)."""

import pytest

from src.world_server.quantum.delta_translator import (
    DeltaTranslator,
    TranslationResult,
    ManifestContext,
    EntityKeyGenerator,
    create_manifest_context,
)
from src.world_server.quantum.reasoning import SemanticOutcome, SemanticChange
from src.world_server.quantum.schemas import DeltaType


class TestEntityKeyGenerator:
    """Tests for EntityKeyGenerator."""

    def test_generate_item_key(self):
        gen = EntityKeyGenerator()
        key = gen.generate_item_key("a mug of honeyed ale")
        assert key.startswith("item_")
        assert "honeyed_ale" in key or "mug" in key

    def test_generate_item_key_removes_articles(self):
        gen = EntityKeyGenerator()
        key1 = gen.generate_item_key("a sword")
        key2 = gen.generate_item_key("the shield")
        key3 = gen.generate_item_key("an apple")

        assert "sword" in key1
        assert "shield" in key2
        assert "apple" in key3

    def test_generate_npc_key(self):
        gen = EntityKeyGenerator()
        key = gen.generate_npc_key("Old Tom")
        assert key.startswith("npc_")
        assert "old_tom" in key

    def test_keys_are_unique(self):
        gen = EntityKeyGenerator()
        keys = [gen.generate_item_key("sword") for _ in range(10)]
        assert len(keys) == len(set(keys))  # All unique

    def test_normalizes_special_characters(self):
        gen = EntityKeyGenerator()
        key = gen.generate_item_key("Tom's Magic Sword!")
        assert "toms_magic_sword" in key
        assert "'" not in key
        assert "!" not in key


class TestManifestContext:
    """Tests for ManifestContext."""

    @pytest.fixture
    def manifest(self):
        return ManifestContext(
            npcs={"old tom": "npc_tom_001", "patron": "npc_patron_001"},
            items={"ale mug": "item_ale_001", "rusty sword": "item_sword_001"},
            locations={"village square": "loc_square", "tavern": "loc_tavern"},
            current_location_key="loc_tavern",
            player_key="test_hero",
        )

    def test_get_npc_key(self, manifest):
        assert manifest.get_npc_key("Old Tom") == "npc_tom_001"
        assert manifest.get_npc_key("old tom") == "npc_tom_001"
        assert manifest.get_npc_key("Unknown") is None

    def test_get_item_key(self, manifest):
        assert manifest.get_item_key("Ale Mug") == "item_ale_001"
        assert manifest.get_item_key("ale mug") == "item_ale_001"
        assert manifest.get_item_key("Unknown") is None

    def test_get_location_key(self, manifest):
        assert manifest.get_location_key("Village Square") == "loc_square"
        assert manifest.get_location_key("village square") == "loc_square"

    def test_resolve_target_player(self, manifest):
        assert manifest.resolve_target("player") == "test_hero"
        assert manifest.resolve_target("the player") == "test_hero"
        assert manifest.resolve_target("you") == "test_hero"

    def test_resolve_target_npc(self, manifest):
        assert manifest.resolve_target("Old Tom") == "npc_tom_001"

    def test_resolve_target_item(self, manifest):
        assert manifest.resolve_target("Ale Mug") == "item_ale_001"

    def test_resolve_target_location(self, manifest):
        assert manifest.resolve_target("Village Square") == "loc_square"


class TestCreateManifestContext:
    """Tests for create_manifest_context helper."""

    def test_creates_lowercase_mappings(self):
        manifest = create_manifest_context(
            npcs={"Old Tom": "npc_tom"},
            items={"Rusty Sword": "item_sword"},
            locations={"Village Square": "loc_square"},
            current_location_key="loc_tavern",
        )
        # Should lowercase the keys
        assert manifest.get_npc_key("old tom") == "npc_tom"
        assert manifest.get_item_key("rusty sword") == "item_sword"


class TestTranslationResult:
    """Tests for TranslationResult."""

    def test_has_errors(self):
        result_ok = TranslationResult(
            deltas=[],
            key_mapping={},
            time_minutes=5,
            errors=[],
        )
        result_err = TranslationResult(
            deltas=[],
            key_mapping={},
            time_minutes=5,
            errors=["Something went wrong"],
        )
        assert result_ok.has_errors is False
        assert result_err.has_errors is True


class TestDeltaTranslator:
    """Tests for DeltaTranslator."""

    @pytest.fixture
    def translator(self):
        return DeltaTranslator()

    @pytest.fixture
    def manifest(self):
        return ManifestContext(
            npcs={"old tom": "npc_tom_001"},
            items={"ale mug": "item_ale_001"},
            locations={"village square": "loc_square"},
            current_location_key="loc_tavern",
            player_key="test_hero",
        )

    def test_translate_new_items(self, translator, manifest):
        """Test that new_things get CREATE_ENTITY deltas."""
        outcome = SemanticOutcome(
            what_happens="Tom gives the player a mug of honeyed ale",
            outcome_type="success",
            new_things=["a mug of honeyed ale"],
            changes=[],
            time_description="a moment",
        )

        result = translator.translate(outcome, manifest)

        # Should have CREATE_ENTITY for the new item
        create_deltas = [d for d in result.deltas if d.delta_type == DeltaType.CREATE_ENTITY]
        assert len(create_deltas) == 1
        assert create_deltas[0].changes["entity_type"] == "item"
        assert "honeyed ale" in create_deltas[0].changes["display_name"]

        # Should be in key mapping
        assert "a mug of honeyed ale" in result.key_mapping

    def test_translate_give_item_new(self, translator, manifest):
        """Test give_item with newly created item."""
        outcome = SemanticOutcome(
            what_happens="Tom gives ale",
            outcome_type="success",
            new_things=["a mug of honeyed ale"],
            changes=[
                SemanticChange(
                    change_type="give_item",
                    description="Tom gives ale to player",
                    actor="Old Tom",
                    target="the player",
                    object_involved="a mug of honeyed ale",
                )
            ],
            time_description="a moment",
        )

        result = translator.translate(outcome, manifest)

        # Should have CREATE + TRANSFER
        create_deltas = [d for d in result.deltas if d.delta_type == DeltaType.CREATE_ENTITY]
        transfer_deltas = [d for d in result.deltas if d.delta_type == DeltaType.TRANSFER_ITEM]

        assert len(create_deltas) == 1
        assert len(transfer_deltas) == 1
        assert transfer_deltas[0].changes["to_entity"] == "test_hero"

    def test_translate_give_item_existing(self, translator, manifest):
        """Test give_item with existing item from manifest."""
        outcome = SemanticOutcome(
            what_happens="Tom gives his ale mug",
            outcome_type="success",
            new_things=[],
            changes=[
                SemanticChange(
                    change_type="give_item",
                    description="Tom gives ale to player",
                    actor="Old Tom",
                    target="the player",
                    object_involved="Ale Mug",
                )
            ],
            time_description="a moment",
        )

        result = translator.translate(outcome, manifest)

        # Should have TRANSFER for existing item (no CREATE)
        create_deltas = [d for d in result.deltas if d.delta_type == DeltaType.CREATE_ENTITY]
        transfer_deltas = [d for d in result.deltas if d.delta_type == DeltaType.TRANSFER_ITEM]

        assert len(create_deltas) == 0
        assert len(transfer_deltas) == 1
        assert transfer_deltas[0].target_key == "item_ale_001"

    def test_translate_take_item(self, translator, manifest):
        """Test take_item translation."""
        outcome = SemanticOutcome(
            what_happens="Player picks up ale mug",
            outcome_type="success",
            new_things=[],
            changes=[
                SemanticChange(
                    change_type="take_item",
                    description="Player takes the ale mug",
                    actor="the player",
                    object_involved="Ale Mug",
                )
            ],
            time_description="a moment",
        )

        result = translator.translate(outcome, manifest)

        transfer_deltas = [d for d in result.deltas if d.delta_type == DeltaType.TRANSFER_ITEM]
        assert len(transfer_deltas) == 1
        assert transfer_deltas[0].target_key == "item_ale_001"
        assert transfer_deltas[0].changes["to_entity"] == "test_hero"

    def test_translate_learn_info(self, translator, manifest):
        """Test learn_info translation."""
        outcome = SemanticOutcome(
            what_happens="Tom tells the player about the robbery",
            outcome_type="success",
            new_things=[],
            changes=[
                SemanticChange(
                    change_type="learn_info",
                    description="The player learns about the recent robbery",
                    actor="Old Tom",
                )
            ],
            time_description="a few minutes",
        )

        result = translator.translate(outcome, manifest)

        fact_deltas = [d for d in result.deltas if d.delta_type == DeltaType.RECORD_FACT]
        assert len(fact_deltas) == 1
        assert fact_deltas[0].changes["predicate"] == "knows"
        assert "robbery" in fact_deltas[0].changes["value"]

    def test_translate_move_entity(self, translator, manifest):
        """Test move_entity translation."""
        outcome = SemanticOutcome(
            what_happens="The player walks to the village square",
            outcome_type="success",
            new_things=[],
            changes=[
                SemanticChange(
                    change_type="move_entity",
                    description="Player moves to village square",
                    actor="the player",
                    target="Village Square",
                )
            ],
            time_description="a few minutes",
        )

        result = translator.translate(outcome, manifest)

        move_deltas = [d for d in result.deltas if d.delta_type == DeltaType.UPDATE_LOCATION]
        assert len(move_deltas) == 1
        assert move_deltas[0].target_key == "test_hero"
        assert move_deltas[0].changes["location_key"] == "loc_square"

    def test_translate_time_delta(self, translator, manifest):
        """Test that time deltas are added."""
        outcome = SemanticOutcome(
            what_happens="Player waits",
            outcome_type="success",
            new_things=[],
            changes=[],
            time_description="about an hour",
        )

        result = translator.translate(outcome, manifest)

        time_deltas = [d for d in result.deltas if d.delta_type == DeltaType.ADVANCE_TIME]
        assert len(time_deltas) == 1
        assert time_deltas[0].changes["minutes"] == 60
        assert result.time_minutes == 60

    def test_create_before_transfer_ordering(self, translator, manifest):
        """Test that CREATE deltas come before TRANSFER deltas."""
        outcome = SemanticOutcome(
            what_happens="Tom creates and gives a magic potion",
            outcome_type="success",
            new_things=["a magic potion"],
            changes=[
                SemanticChange(
                    change_type="give_item",
                    description="Tom gives potion",
                    actor="Old Tom",
                    target="the player",
                    object_involved="a magic potion",
                )
            ],
            time_description="a moment",
        )

        result = translator.translate(outcome, manifest)

        # Find indices of CREATE and TRANSFER
        create_idx = None
        transfer_idx = None
        for i, delta in enumerate(result.deltas):
            if delta.delta_type == DeltaType.CREATE_ENTITY:
                create_idx = i
            if delta.delta_type == DeltaType.TRANSFER_ITEM:
                transfer_idx = i

        assert create_idx is not None
        assert transfer_idx is not None
        assert create_idx < transfer_idx, "CREATE must come before TRANSFER"

    def test_error_on_unresolved_item(self, translator, manifest):
        """Test that unresolved items generate errors."""
        outcome = SemanticOutcome(
            what_happens="Player picks up something",
            outcome_type="success",
            new_things=[],
            changes=[
                SemanticChange(
                    change_type="take_item",
                    description="Player takes nonexistent item",
                    actor="the player",
                    object_involved="Nonexistent Item",
                )
            ],
            time_description="a moment",
        )

        result = translator.translate(outcome, manifest)

        assert result.has_errors
        assert any("Nonexistent Item" in e for e in result.errors)

    def test_destroy_item(self, translator, manifest):
        """Test destroy_item translation."""
        outcome = SemanticOutcome(
            what_happens="The ale mug shatters",
            outcome_type="failure",
            new_things=[],
            changes=[
                SemanticChange(
                    change_type="destroy_item",
                    description="The mug falls and breaks",
                    object_involved="Ale Mug",
                )
            ],
            time_description="a moment",
        )

        result = translator.translate(outcome, manifest)

        delete_deltas = [d for d in result.deltas if d.delta_type == DeltaType.DELETE_ENTITY]
        assert len(delete_deltas) == 1
        assert delete_deltas[0].target_key == "item_ale_001"

    def test_change_relationship(self, translator, manifest):
        """Test change_relationship translation."""
        outcome = SemanticOutcome(
            what_happens="Tom becomes friendlier",
            outcome_type="success",
            new_things=[],
            changes=[
                SemanticChange(
                    change_type="change_relationship",
                    description="Tom becomes more friendly toward the player",
                    actor="the player",
                    target="Old Tom",
                )
            ],
            time_description="a moment",
        )

        result = translator.translate(outcome, manifest)

        rel_deltas = [d for d in result.deltas if d.delta_type == DeltaType.UPDATE_RELATIONSHIP]
        assert len(rel_deltas) == 1
        assert rel_deltas[0].target_key == "npc_tom_001"
        assert rel_deltas[0].changes["delta_trust"] > 0


# =============================================================================
# Ref-Based Delta Translator Tests
# =============================================================================


class TestRefDeltaTranslator:
    """Tests for RefDeltaTranslator - uses refs instead of display names."""

    @pytest.fixture
    def translator(self):
        from src.world_server.quantum.delta_translator import RefDeltaTranslator
        return RefDeltaTranslator()

    @pytest.fixture
    def ref_manifest(self):
        """Create a RefManifest for testing."""
        from src.gm.grounding import GroundedEntity, GroundingManifest
        from src.world_server.quantum.ref_manifest import RefManifest

        grounding = GroundingManifest(
            location_key="loc_tavern",
            location_display="The Rusty Tankard",
            player_key="test_hero",
            npcs={
                "npc_tom_001": GroundedEntity(
                    key="npc_tom_001",
                    display_name="Old Tom",
                    entity_type="npc",
                    short_description="a farmer",
                ),
            },
            items_at_location={
                "item_sword_01": GroundedEntity(
                    key="item_sword_01",
                    display_name="rusty sword",
                    entity_type="item",
                ),
                "item_sword_02": GroundedEntity(
                    key="item_sword_02",
                    display_name="rusty sword",
                    entity_type="item",
                ),
                "item_ale_001": GroundedEntity(
                    key="item_ale_001",
                    display_name="mug of ale",
                    entity_type="item",
                ),
            },
            exits={
                "loc_square": GroundedEntity(
                    key="loc_square",
                    display_name="Village Square",
                    entity_type="location",
                ),
            },
        )
        return RefManifest.from_grounding_manifest(grounding)

    def test_translate_take_item_valid_ref(self, translator, ref_manifest):
        """Valid ref resolves to entity key."""
        from src.world_server.quantum.reasoning import RefBasedOutcome, RefBasedChange

        # Find the ref for the first rusty sword
        sword_ref = ref_manifest.get_ref_for_key("item_sword_01")
        assert sword_ref is not None

        outcome = RefBasedOutcome(
            what_happens="Player takes the sword",
            changes=[
                RefBasedChange(
                    change_type="take_item",
                    entity=sword_ref,
                )
            ],
        )

        result = translator.translate(outcome, ref_manifest)

        assert not result.has_errors
        transfer_deltas = [d for d in result.deltas if d.delta_type == DeltaType.TRANSFER_ITEM]
        assert len(transfer_deltas) == 1
        assert transfer_deltas[0].target_key == "item_sword_01"
        assert transfer_deltas[0].changes["to_entity_key"] == "test_hero"

    def test_translate_take_item_invalid_ref_error(self, translator, ref_manifest):
        """Invalid ref generates error, no fuzzy fallback."""
        from src.world_server.quantum.reasoning import RefBasedOutcome, RefBasedChange

        outcome = RefBasedOutcome(
            what_happens="Player tries to take something",
            changes=[
                RefBasedChange(
                    change_type="take_item",
                    entity="Z",  # Invalid ref
                )
            ],
        )

        result = translator.translate(outcome, ref_manifest)

        assert result.has_errors
        assert any("Invalid ref 'Z'" in e for e in result.errors)
        # Should NOT have any transfer deltas
        transfer_deltas = [d for d in result.deltas if d.delta_type == DeltaType.TRANSFER_ITEM]
        assert len(transfer_deltas) == 0

    def test_translate_give_item(self, translator, ref_manifest):
        """Test give_item with refs."""
        from src.world_server.quantum.reasoning import RefBasedOutcome, RefBasedChange

        ale_ref = ref_manifest.get_ref_for_key("item_ale_001")
        tom_ref = ref_manifest.get_ref_for_key("npc_tom_001")

        outcome = RefBasedOutcome(
            what_happens="Tom gives ale to player",
            changes=[
                RefBasedChange(
                    change_type="give_item",
                    entity=ale_ref,
                    from_entity=tom_ref,
                    to_entity="player",
                )
            ],
        )

        result = translator.translate(outcome, ref_manifest)

        assert not result.has_errors
        transfer_deltas = [d for d in result.deltas if d.delta_type == DeltaType.TRANSFER_ITEM]
        assert len(transfer_deltas) == 1
        assert transfer_deltas[0].target_key == "item_ale_001"
        assert transfer_deltas[0].changes["from_entity_key"] == "npc_tom_001"
        assert transfer_deltas[0].changes["to_entity_key"] == "test_hero"

    def test_translate_move_to_uses_location_key(self, translator, ref_manifest):
        """move_to uses location key, not ref."""
        from src.world_server.quantum.reasoning import RefBasedOutcome, RefBasedChange

        outcome = RefBasedOutcome(
            what_happens="Player walks to the square",
            changes=[
                RefBasedChange(
                    change_type="move_to",
                    destination="loc_square",
                )
            ],
        )

        result = translator.translate(outcome, ref_manifest)

        assert not result.has_errors
        move_deltas = [d for d in result.deltas if d.delta_type == DeltaType.UPDATE_LOCATION]
        assert len(move_deltas) == 1
        assert move_deltas[0].changes["location_key"] == "loc_square"

    def test_translate_create_entity_generates_key(self, translator, ref_manifest):
        """New entities get generated keys."""
        from src.world_server.quantum.reasoning import RefBasedOutcome, RefBasedChange

        outcome = RefBasedOutcome(
            what_happens="Player kindles a fire",
            changes=[
                RefBasedChange(
                    change_type="create_entity",
                    description="small campfire",
                    entity_type="object",
                )
            ],
        )

        result = translator.translate(outcome, ref_manifest)

        assert not result.has_errors
        create_deltas = [d for d in result.deltas if d.delta_type == DeltaType.CREATE_ENTITY]
        assert len(create_deltas) == 1
        assert "campfire" in create_deltas[0].target_key
        assert create_deltas[0].changes["display_name"] == "small campfire"

        # Should be in key_mapping
        assert "small campfire" in result.key_mapping

    def test_translate_change_relationship(self, translator, ref_manifest):
        """Test change_relationship with NPC ref."""
        from src.world_server.quantum.reasoning import RefBasedOutcome, RefBasedChange

        tom_ref = ref_manifest.get_ref_for_key("npc_tom_001")

        outcome = RefBasedOutcome(
            what_happens="Tom warms up to the player",
            changes=[
                RefBasedChange(
                    change_type="change_relationship",
                    npc=tom_ref,
                    delta="+trust",
                )
            ],
        )

        result = translator.translate(outcome, ref_manifest)

        assert not result.has_errors
        rel_deltas = [d for d in result.deltas if d.delta_type == DeltaType.UPDATE_RELATIONSHIP]
        assert len(rel_deltas) == 1
        assert rel_deltas[0].target_key == "npc_tom_001"
        assert rel_deltas[0].changes["delta_trust"] > 0

    def test_translate_learn_info(self, translator, ref_manifest):
        """Test learn_info doesn't need refs."""
        from src.world_server.quantum.reasoning import RefBasedOutcome, RefBasedChange

        outcome = RefBasedOutcome(
            what_happens="Player learns about the passage",
            changes=[
                RefBasedChange(
                    change_type="learn_info",
                    fact="The secret passage is behind the fireplace",
                )
            ],
        )

        result = translator.translate(outcome, ref_manifest)

        assert not result.has_errors
        fact_deltas = [d for d in result.deltas if d.delta_type == DeltaType.RECORD_FACT]
        assert len(fact_deltas) == 1
        assert "fireplace" in fact_deltas[0].changes["value"]

    def test_translate_advance_time(self, translator, ref_manifest):
        """Test advance_time doesn't need refs."""
        from src.world_server.quantum.reasoning import RefBasedOutcome, RefBasedChange

        outcome = RefBasedOutcome(
            what_happens="Player rests",
            changes=[
                RefBasedChange(
                    change_type="advance_time",
                    duration="6 hours",
                )
            ],
        )

        result = translator.translate(outcome, ref_manifest)

        assert not result.has_errors
        # Should have 2 time deltas - one from explicit change, one from outcome
        time_deltas = [d for d in result.deltas if d.delta_type == DeltaType.ADVANCE_TIME]
        assert len(time_deltas) >= 1

    def test_translate_update_need(self, translator, ref_manifest):
        """Test update_need for sleep/fatigue."""
        from src.world_server.quantum.reasoning import RefBasedOutcome, RefBasedChange

        outcome = RefBasedOutcome(
            what_happens="Player sleeps and recovers",
            changes=[
                RefBasedChange(
                    change_type="update_need",
                    need="fatigue",
                    need_change="rested",
                )
            ],
        )

        result = translator.translate(outcome, ref_manifest)

        assert not result.has_errors
        need_deltas = [d for d in result.deltas if d.delta_type == DeltaType.UPDATE_NEED]
        assert len(need_deltas) == 1
        assert need_deltas[0].changes["need_name"] == "fatigue"
        assert need_deltas[0].changes["delta_value"] < 0  # Decrease (rested)

    def test_empty_changes_valid(self, translator, ref_manifest):
        """Empty changes is valid (pure roleplay)."""
        from src.world_server.quantum.reasoning import RefBasedOutcome

        outcome = RefBasedOutcome(
            what_happens="Player whistles a tune",
            changes=[],
        )

        result = translator.translate(outcome, ref_manifest)

        assert not result.has_errors
        # Should only have ADVANCE_TIME for the "a moment" default
        assert len(result.deltas) == 1
        assert result.deltas[0].delta_type == DeltaType.ADVANCE_TIME

    def test_duplicate_items_different_refs(self, translator, ref_manifest):
        """Two items with same display name have different refs."""
        from src.world_server.quantum.reasoning import RefBasedOutcome, RefBasedChange

        sword1_ref = ref_manifest.get_ref_for_key("item_sword_01")
        sword2_ref = ref_manifest.get_ref_for_key("item_sword_02")

        assert sword1_ref != sword2_ref

        # Take the first sword
        outcome = RefBasedOutcome(
            what_happens="Player takes the first sword",
            changes=[
                RefBasedChange(
                    change_type="take_item",
                    entity=sword1_ref,
                )
            ],
        )

        result = translator.translate(outcome, ref_manifest)

        assert not result.has_errors
        transfer_deltas = [d for d in result.deltas if d.delta_type == DeltaType.TRANSFER_ITEM]
        assert len(transfer_deltas) == 1
        assert transfer_deltas[0].target_key == "item_sword_01"  # Not sword_02

    def test_ref_stored_in_key_mapping(self, translator, ref_manifest):
        """Resolved refs are stored in key_mapping."""
        from src.world_server.quantum.reasoning import RefBasedOutcome, RefBasedChange

        sword_ref = ref_manifest.get_ref_for_key("item_sword_01")

        outcome = RefBasedOutcome(
            what_happens="Player takes sword",
            changes=[
                RefBasedChange(
                    change_type="take_item",
                    entity=sword_ref,
                )
            ],
        )

        result = translator.translate(outcome, ref_manifest)

        assert sword_ref in result.key_mapping
        assert result.key_mapping[sword_ref] == "item_sword_01"

    def test_create_entity_validates_type_location(self, translator, ref_manifest):
        """Create entity with 'location' type produces location entity_type."""
        from src.world_server.quantum.reasoning import RefBasedOutcome, RefBasedChange

        outcome = RefBasedOutcome(
            what_happens="A hidden storage room is discovered",
            changes=[
                RefBasedChange(
                    change_type="create_entity",
                    description="hidden storage room",
                    entity_type="location",
                )
            ],
        )

        result = translator.translate(outcome, ref_manifest)

        assert not result.has_errors
        create_deltas = [d for d in result.deltas if d.delta_type == DeltaType.CREATE_ENTITY]
        assert len(create_deltas) == 1
        assert create_deltas[0].changes["entity_type"] == "location"
        # Key should start with loc_
        assert create_deltas[0].target_key.startswith("loc_")

    def test_create_entity_validates_type_object_becomes_item(self, translator, ref_manifest):
        """Create entity with 'object' type becomes 'item'."""
        from src.world_server.quantum.reasoning import RefBasedOutcome, RefBasedChange

        outcome = RefBasedOutcome(
            what_happens="A campfire is lit",
            changes=[
                RefBasedChange(
                    change_type="create_entity",
                    description="small campfire",
                    entity_type="object",
                )
            ],
        )

        result = translator.translate(outcome, ref_manifest)

        assert not result.has_errors
        create_deltas = [d for d in result.deltas if d.delta_type == DeltaType.CREATE_ENTITY]
        assert len(create_deltas) == 1
        # "object" maps to "item"
        assert create_deltas[0].changes["entity_type"] == "item"
        assert create_deltas[0].target_key.startswith("item_")

    def test_create_entity_unknown_type_defaults_to_item(self, translator, ref_manifest):
        """Create entity with unknown type defaults to 'item' with warning."""
        from src.world_server.quantum.reasoning import RefBasedOutcome, RefBasedChange

        outcome = RefBasedOutcome(
            what_happens="A magical portal appears",
            changes=[
                RefBasedChange(
                    change_type="create_entity",
                    description="magical portal",
                    entity_type="portal",  # Invalid type
                )
            ],
        )

        result = translator.translate(outcome, ref_manifest)

        # Should not error, just default to item
        assert not result.has_errors
        create_deltas = [d for d in result.deltas if d.delta_type == DeltaType.CREATE_ENTITY]
        assert len(create_deltas) == 1
        assert create_deltas[0].changes["entity_type"] == "item"

    def test_give_item_with_descriptive_key_new_item(self, translator, ref_manifest):
        """give_item with a descriptive key (not a ref) produces TRANSFER_ITEM.

        When an NPC gives a new item that doesn't exist in the manifest,
        the LLM uses a descriptive snake_case key like "ale_mug" instead of a ref.
        The translator should accept this and pass it through for postprocessor
        to auto-create the item.
        """
        from src.world_server.quantum.reasoning import RefBasedOutcome, RefBasedChange

        tom_ref = ref_manifest.get_ref_for_key("npc_tom_001")

        outcome = RefBasedOutcome(
            what_happens="Tom gives the player a fresh mug of ale",
            changes=[
                RefBasedChange(
                    change_type="give_item",
                    entity="ale_mug",  # Descriptive key, not a ref
                    from_entity=tom_ref,
                    to_entity="player",
                )
            ],
        )

        result = translator.translate(outcome, ref_manifest)

        # Should NOT error - descriptive keys are allowed for new items
        assert not result.has_errors
        transfer_deltas = [d for d in result.deltas if d.delta_type == DeltaType.TRANSFER_ITEM]
        assert len(transfer_deltas) == 1
        assert transfer_deltas[0].target_key == "ale_mug"
        assert transfer_deltas[0].changes["from_entity_key"] == "npc_tom_001"
        assert transfer_deltas[0].changes["to_entity_key"] == "test_hero"

        # Key should be in key_mapping
        assert "ale_mug" in result.key_mapping
        assert result.key_mapping["ale_mug"] == "ale_mug"

    def test_give_item_with_descriptive_key_lowercase(self, translator, ref_manifest):
        """give_item with lowercase word (no underscore) is also accepted."""
        from src.world_server.quantum.reasoning import RefBasedOutcome, RefBasedChange

        tom_ref = ref_manifest.get_ref_for_key("npc_tom_001")

        outcome = RefBasedOutcome(
            what_happens="Tom gives the player bread",
            changes=[
                RefBasedChange(
                    change_type="give_item",
                    entity="bread",  # Lowercase, no underscore
                    from_entity=tom_ref,
                    to_entity="player",
                )
            ],
        )

        result = translator.translate(outcome, ref_manifest)

        assert not result.has_errors
        transfer_deltas = [d for d in result.deltas if d.delta_type == DeltaType.TRANSFER_ITEM]
        assert len(transfer_deltas) == 1
        assert transfer_deltas[0].target_key == "bread"

    def test_give_item_uppercase_non_ref_still_errors(self, translator, ref_manifest):
        """give_item with uppercase non-ref value should error.

        If the entity value is uppercase (like a ref) but not in manifest,
        this is likely a mistake and should error rather than silently create.
        """
        from src.world_server.quantum.reasoning import RefBasedOutcome, RefBasedChange

        tom_ref = ref_manifest.get_ref_for_key("npc_tom_001")

        outcome = RefBasedOutcome(
            what_happens="Tom gives the player something",
            changes=[
                RefBasedChange(
                    change_type="give_item",
                    entity="Z",  # Looks like a ref but doesn't exist
                    from_entity=tom_ref,
                    to_entity="player",
                )
            ],
        )

        result = translator.translate(outcome, ref_manifest)

        # Should error because "Z" looks like a ref but isn't valid
        assert result.has_errors
        assert any("Invalid ref 'Z'" in e for e in result.errors)
