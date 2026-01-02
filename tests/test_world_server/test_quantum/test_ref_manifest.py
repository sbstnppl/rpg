"""Tests for RefManifest - reference-based entity resolution."""

import pytest

from src.gm.grounding import GroundedEntity, GroundingManifest
from src.world_server.quantum.ref_manifest import RefEntry, RefManifest, _RefGenerator


class TestRefGenerator:
    """Tests for the ref generator."""

    def test_generates_a_to_z(self) -> None:
        """First 26 refs are A-Z."""
        gen = _RefGenerator()
        refs = [gen.next_ref() for _ in range(26)]

        assert refs[0] == "A"
        assert refs[25] == "Z"
        assert refs == list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

    def test_overflow_adds_number(self) -> None:
        """After Z, continues with A1, B1, etc."""
        gen = _RefGenerator()
        # Skip first 26
        for _ in range(26):
            gen.next_ref()

        assert gen.next_ref() == "A1"
        assert gen.next_ref() == "B1"

    def test_multiple_overflow_rounds(self) -> None:
        """Continues A2, B2 after Z1."""
        gen = _RefGenerator()
        # Skip first 52 (A-Z, A1-Z1)
        for _ in range(52):
            gen.next_ref()

        assert gen.next_ref() == "A2"
        assert gen.next_ref() == "B2"


class TestRefEntry:
    """Tests for RefEntry."""

    def test_format_basic(self) -> None:
        """Basic entry formats correctly."""
        entry = RefEntry(
            ref="A",
            entity_key="rusty_sword_01",
            display_name="rusty sword",
            entity_type="item",
        )

        assert entry.format_for_prompt() == "[A] rusty sword"

    def test_format_with_location_hint(self) -> None:
        """Entry with location hint includes it."""
        entry = RefEntry(
            ref="A",
            entity_key="rusty_sword_01",
            display_name="rusty sword",
            entity_type="item",
            location_hint="on the wooden table",
        )

        assert entry.format_for_prompt() == "[A] rusty sword - on the wooden table"

    def test_format_with_short_description(self) -> None:
        """Entry with short description includes it."""
        entry = RefEntry(
            ref="C",
            entity_key="greta_bartender",
            display_name="Greta",
            entity_type="npc",
            short_description="the bartender",
        )

        assert entry.format_for_prompt() == "[C] Greta (the bartender)"

    def test_format_with_all_fields(self) -> None:
        """Entry with all fields formats correctly."""
        entry = RefEntry(
            ref="D",
            entity_key="old_tom",
            display_name="Old Tom",
            entity_type="npc",
            short_description="a grizzled farmer",
            location_hint="sitting by the fire",
        )

        result = entry.format_for_prompt()
        assert "[D] Old Tom" in result
        assert "(a grizzled farmer)" in result
        assert "- sitting by the fire" in result


class TestRefManifest:
    """Tests for RefManifest."""

    @pytest.fixture
    def sample_grounding_manifest(self) -> GroundingManifest:
        """Create a sample GroundingManifest for testing."""
        return GroundingManifest(
            location_key="tavern_main",
            location_display="The Rusty Tankard",
            player_key="player_hero",
            player_display="you",
            npcs={
                "greta_bartender": GroundedEntity(
                    key="greta_bartender",
                    display_name="Greta",
                    entity_type="npc",
                    short_description="the bartender",
                ),
                "old_tom": GroundedEntity(
                    key="old_tom",
                    display_name="Old Tom",
                    entity_type="npc",
                    short_description="a farmer",
                ),
            },
            items_at_location={
                "rusty_sword_01": GroundedEntity(
                    key="rusty_sword_01",
                    display_name="rusty sword",
                    entity_type="item",
                ),
                "rusty_sword_02": GroundedEntity(
                    key="rusty_sword_02",
                    display_name="rusty sword",
                    entity_type="item",
                ),
                "ale_mug_01": GroundedEntity(
                    key="ale_mug_01",
                    display_name="mug of ale",
                    entity_type="item",
                ),
            },
            inventory={
                "gold_pouch": GroundedEntity(
                    key="gold_pouch",
                    display_name="leather pouch",
                    entity_type="item",
                ),
            },
            exits={
                "village_square": GroundedEntity(
                    key="village_square",
                    display_name="Village Square",
                    entity_type="location",
                ),
            },
        )

    def test_from_grounding_manifest_assigns_refs(
        self, sample_grounding_manifest: GroundingManifest
    ) -> None:
        """Entities get sequential refs."""
        ref_manifest = RefManifest.from_grounding_manifest(sample_grounding_manifest)

        # Should have 6 entities (2 NPCs + 3 items at loc + 1 inventory)
        assert ref_manifest.entity_count() == 6

        # All refs should be A-F
        refs = ref_manifest.all_refs()
        assert set(refs) == {"A", "B", "C", "D", "E", "F"}

    def test_duplicate_display_names_get_unique_refs(
        self, sample_grounding_manifest: GroundingManifest
    ) -> None:
        """Two 'rusty sword' items get different refs."""
        ref_manifest = RefManifest.from_grounding_manifest(sample_grounding_manifest)

        # Find refs for both rusty swords
        sword1_ref = ref_manifest.get_ref_for_key("rusty_sword_01")
        sword2_ref = ref_manifest.get_ref_for_key("rusty_sword_02")

        assert sword1_ref is not None
        assert sword2_ref is not None
        assert sword1_ref != sword2_ref

    def test_resolve_ref_valid(
        self, sample_grounding_manifest: GroundingManifest
    ) -> None:
        """Valid ref resolves to entry."""
        ref_manifest = RefManifest.from_grounding_manifest(sample_grounding_manifest)

        entry = ref_manifest.resolve_ref("A")

        assert entry is not None
        assert entry.ref == "A"
        assert entry.entity_key in sample_grounding_manifest.all_keys()

    def test_resolve_ref_invalid(
        self, sample_grounding_manifest: GroundingManifest
    ) -> None:
        """Invalid ref returns None."""
        ref_manifest = RefManifest.from_grounding_manifest(sample_grounding_manifest)

        entry = ref_manifest.resolve_ref("Z")

        assert entry is None

    def test_resolve_ref_normalizes_brackets(
        self, sample_grounding_manifest: GroundingManifest
    ) -> None:
        """Ref lookup handles [A] and A."""
        ref_manifest = RefManifest.from_grounding_manifest(sample_grounding_manifest)

        entry1 = ref_manifest.resolve_ref("A")
        entry2 = ref_manifest.resolve_ref("[A]")
        entry3 = ref_manifest.resolve_ref("a")  # lowercase

        assert entry1 == entry2 == entry3

    def test_resolve_ref_to_key(
        self, sample_grounding_manifest: GroundingManifest
    ) -> None:
        """Can get entity key directly from ref."""
        ref_manifest = RefManifest.from_grounding_manifest(sample_grounding_manifest)

        key = ref_manifest.resolve_ref_to_key("A")

        assert key is not None
        assert key in sample_grounding_manifest.all_keys()

    def test_get_ref_for_key(
        self, sample_grounding_manifest: GroundingManifest
    ) -> None:
        """Can look up ref from entity key."""
        ref_manifest = RefManifest.from_grounding_manifest(sample_grounding_manifest)

        ref = ref_manifest.get_ref_for_key("greta_bartender")

        assert ref is not None
        assert ref_manifest.resolve_ref_to_key(ref) == "greta_bartender"

    def test_exits_without_refs(
        self, sample_grounding_manifest: GroundingManifest
    ) -> None:
        """By default, exits don't get refs."""
        ref_manifest = RefManifest.from_grounding_manifest(sample_grounding_manifest)

        # Exits should be stored but not as refs
        assert "village_square" in ref_manifest.exit_refs
        assert ref_manifest.exit_displays["village_square"] == "Village Square"

        # Exit key should not resolve as a ref
        entry = ref_manifest.resolve_ref("village_square")
        assert entry is None

    def test_exits_with_refs(
        self, sample_grounding_manifest: GroundingManifest
    ) -> None:
        """Optionally, exits can get refs."""
        ref_manifest = RefManifest.from_grounding_manifest(
            sample_grounding_manifest,
            include_exits_as_refs=True,
        )

        # Should have 7 entries now (6 + 1 exit)
        assert ref_manifest.entity_count() == 7

        # Exit should be resolvable
        ref = ref_manifest.get_ref_for_key("village_square")
        assert ref is not None

    def test_format_for_reasoning_prompt(
        self, sample_grounding_manifest: GroundingManifest
    ) -> None:
        """Prompt format includes all sections."""
        ref_manifest = RefManifest.from_grounding_manifest(sample_grounding_manifest)

        prompt = ref_manifest.format_for_reasoning_prompt()

        # Should have sections
        assert "CHARACTERS:" in prompt
        assert "ITEMS:" in prompt
        assert "EXITS:" in prompt

        # Should have refs
        assert "[A]" in prompt
        assert "[B]" in prompt

        # Should have display names
        assert "Greta" in prompt
        assert "rusty sword" in prompt

    def test_location_info_preserved(
        self, sample_grounding_manifest: GroundingManifest
    ) -> None:
        """Location info is preserved from grounding manifest."""
        ref_manifest = RefManifest.from_grounding_manifest(sample_grounding_manifest)

        assert ref_manifest.location_key == "tavern_main"
        assert ref_manifest.location_display == "The Rusty Tankard"
        assert ref_manifest.player_key == "player_hero"


class TestRefManifestLargeScene:
    """Tests for scenes with many entities."""

    def test_overflow_refs_for_large_scene(self) -> None:
        """Scenes with 26+ entities use overflow refs."""
        # Create manifest with 30 items
        items = {
            f"item_{i:02d}": GroundedEntity(
                key=f"item_{i:02d}",
                display_name=f"Item {i}",
                entity_type="item",
            )
            for i in range(30)
        }

        manifest = GroundingManifest(
            location_key="warehouse",
            location_display="Warehouse",
            player_key="player",
            items_at_location=items,
        )

        ref_manifest = RefManifest.from_grounding_manifest(manifest)

        # Should have 30 entries
        assert ref_manifest.entity_count() == 30

        # Check overflow refs exist
        refs = ref_manifest.all_refs()
        assert "A" in refs
        assert "Z" in refs
        assert "A1" in refs
        assert "B1" in refs


class TestRefManifestEdgeCases:
    """Edge case tests for RefManifest."""

    def test_empty_manifest(self) -> None:
        """Empty grounding manifest produces empty ref manifest."""
        manifest = GroundingManifest(
            location_key="void",
            location_display="The Void",
            player_key="player",
        )

        ref_manifest = RefManifest.from_grounding_manifest(manifest)

        assert ref_manifest.entity_count() == 0
        assert ref_manifest.all_refs() == []

    def test_player_is_not_assigned_ref(self) -> None:
        """Player doesn't get a ref (referenced as 'player')."""
        manifest = GroundingManifest(
            location_key="room",
            location_display="Room",
            player_key="player_hero",
        )

        ref_manifest = RefManifest.from_grounding_manifest(manifest)

        # Player key should be stored but not as a ref
        assert ref_manifest.player_key == "player_hero"
        assert ref_manifest.get_ref_for_key("player_hero") is None

    def test_resolve_exit_by_key(self) -> None:
        """Exits can be resolved by their key."""
        manifest = GroundingManifest(
            location_key="tavern",
            location_display="Tavern",
            player_key="player",
            exits={
                "village_square": GroundedEntity(
                    key="village_square",
                    display_name="Village Square",
                    entity_type="location",
                ),
            },
        )

        ref_manifest = RefManifest.from_grounding_manifest(manifest)

        # Should resolve exit by key
        result = ref_manifest.resolve_exit("village_square")
        assert result == "village_square"
