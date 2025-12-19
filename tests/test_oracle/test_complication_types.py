"""Tests for complication types and dataclasses."""

import pytest

from src.oracle.complication_types import (
    Complication,
    ComplicationType,
    Effect,
    EffectType,
    ItemSpawnDecision,
    ItemSpawnResult,
)


class TestEffectType:
    """Tests for EffectType enum."""

    def test_all_effect_types_exist(self):
        """Test that all expected effect types exist."""
        expected = {
            "hp_loss", "hp_gain", "resource_loss", "resource_gain",
            "status_add", "status_remove", "relationship_change",
            "time_advance", "spawn_entity", "reveal_fact", "tension_change",
        }

        actual = {e.value for e in EffectType}
        assert expected == actual


class TestEffect:
    """Tests for Effect dataclass."""

    def test_create_basic_effect(self):
        """Test creating a basic effect."""
        effect = Effect(type=EffectType.HP_LOSS, target="player", value=3)

        assert effect.type == EffectType.HP_LOSS
        assert effect.target == "player"
        assert effect.value == 3

    def test_effect_to_dict(self):
        """Test serialization to dictionary."""
        effect = Effect(
            type=EffectType.STATUS_ADD,
            target="player",
            value="poisoned",
            metadata={"duration": 3},
        )

        result = effect.to_dict()

        assert result["type"] == "status_add"
        assert result["target"] == "player"
        assert result["value"] == "poisoned"
        assert result["metadata"] == {"duration": 3}

    def test_effect_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "type": "hp_loss",
            "target": "goblin_1",
            "value": 5,
            "metadata": {"source": "fire"},
        }

        effect = Effect.from_dict(data)

        assert effect.type == EffectType.HP_LOSS
        assert effect.target == "goblin_1"
        assert effect.value == 5
        assert effect.metadata == {"source": "fire"}

    def test_effect_roundtrip(self):
        """Test that to_dict and from_dict are inverse operations."""
        original = Effect(
            type=EffectType.SPAWN_ENTITY,
            target="tavern",
            value="mysterious_stranger",
            metadata={"hostile": False},
        )

        roundtrip = Effect.from_dict(original.to_dict())

        assert roundtrip.type == original.type
        assert roundtrip.target == original.target
        assert roundtrip.value == original.value
        assert roundtrip.metadata == original.metadata


class TestComplicationType:
    """Tests for ComplicationType enum."""

    def test_all_complication_types_exist(self):
        """Test that all expected complication types exist."""
        expected = {"discovery", "interruption", "cost", "twist"}
        actual = {c.value for c in ComplicationType}
        assert expected == actual


class TestComplication:
    """Tests for Complication dataclass."""

    def test_create_simple_complication(self):
        """Test creating a simple complication."""
        comp = Complication(
            type=ComplicationType.DISCOVERY,
            description="You notice a hidden compartment.",
        )

        assert comp.type == ComplicationType.DISCOVERY
        assert "hidden compartment" in comp.description
        assert comp.mechanical_effects == []
        assert comp.new_facts == []
        assert comp.interrupts_action is False

    def test_create_complex_complication(self):
        """Test creating a complication with all fields."""
        effects = [
            Effect(type=EffectType.HP_LOSS, target="player", value=2),
            Effect(type=EffectType.REVEAL_FACT, value="The merchant is a spy"),
        ]

        comp = Complication(
            type=ComplicationType.COST,
            description="Success, but at a price.",
            mechanical_effects=effects,
            new_facts=["The fight drew attention", "Guards are alerted"],
            interrupts_action=False,
            source_arc_key="main_quest",
            foreshadowing="This will have consequences...",
        )

        assert comp.type == ComplicationType.COST
        assert len(comp.mechanical_effects) == 2
        assert len(comp.new_facts) == 2
        assert comp.source_arc_key == "main_quest"
        assert comp.foreshadowing is not None

    def test_complication_to_dict(self):
        """Test serialization to dictionary."""
        comp = Complication(
            type=ComplicationType.INTERRUPTION,
            description="The door bursts open.",
            mechanical_effects=[
                Effect(type=EffectType.SPAWN_ENTITY, value="guard"),
            ],
            new_facts=["Guards have arrived"],
            interrupts_action=True,
        )

        result = comp.to_dict()

        assert result["type"] == "interruption"
        assert "door bursts" in result["description"]
        assert len(result["mechanical_effects"]) == 1
        assert result["new_facts"] == ["Guards have arrived"]
        assert result["interrupts_action"] is True

    def test_complication_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "type": "twist",
            "description": "The merchant reveals her true identity.",
            "mechanical_effects": [],
            "new_facts": ["Merchant is the missing princess"],
            "interrupts_action": False,
            "source_arc_key": "mystery_arc",
            "foreshadowing": "Her disguise was perfect... until now.",
        }

        comp = Complication.from_dict(data)

        assert comp.type == ComplicationType.TWIST
        assert "true identity" in comp.description
        assert comp.new_facts == ["Merchant is the missing princess"]
        assert comp.source_arc_key == "mystery_arc"

    def test_complication_roundtrip(self):
        """Test that to_dict and from_dict are inverse operations."""
        original = Complication(
            type=ComplicationType.DISCOVERY,
            description="A secret passage is revealed.",
            mechanical_effects=[
                Effect(type=EffectType.REVEAL_FACT, value="Secret passage exists"),
            ],
            new_facts=["Passage leads to the dungeon"],
            interrupts_action=False,
            source_arc_key="exploration",
            foreshadowing="What lies beyond?",
        )

        roundtrip = Complication.from_dict(original.to_dict())

        assert roundtrip.type == original.type
        assert roundtrip.description == original.description
        assert len(roundtrip.mechanical_effects) == len(original.mechanical_effects)
        assert roundtrip.new_facts == original.new_facts
        assert roundtrip.interrupts_action == original.interrupts_action
        assert roundtrip.source_arc_key == original.source_arc_key
        assert roundtrip.foreshadowing == original.foreshadowing


class TestItemSpawnDecision:
    """Tests for ItemSpawnDecision enum."""

    def test_all_spawn_decisions_exist(self):
        """Test that all expected spawn decisions exist."""
        expected = {"spawn", "plot_hook_missing", "plot_hook_relocated", "defer"}
        actual = {d.value for d in ItemSpawnDecision}
        assert expected == actual

    def test_spawn_decision_from_string(self):
        """Test enum creation from string."""
        assert ItemSpawnDecision("spawn") == ItemSpawnDecision.SPAWN
        assert ItemSpawnDecision("plot_hook_missing") == ItemSpawnDecision.PLOT_HOOK_MISSING
        assert ItemSpawnDecision("plot_hook_relocated") == ItemSpawnDecision.PLOT_HOOK_RELOCATED
        assert ItemSpawnDecision("defer") == ItemSpawnDecision.DEFER


class TestItemSpawnResult:
    """Tests for ItemSpawnResult dataclass."""

    def test_create_spawn_result(self):
        """Test creating a simple spawn result."""
        result = ItemSpawnResult(
            item_name="bucket",
            decision=ItemSpawnDecision.SPAWN,
            reasoning="Common item for location",
        )

        assert result.item_name == "bucket"
        assert result.decision == ItemSpawnDecision.SPAWN
        assert result.reasoning == "Common item for location"
        assert result.spawn_location is None
        assert result.plot_hook_description is None
        assert result.new_facts == []

    def test_create_plot_hook_missing_result(self):
        """Test creating a plot hook missing result."""
        result = ItemSpawnResult(
            item_name="bucket",
            decision=ItemSpawnDecision.PLOT_HOOK_MISSING,
            reasoning="Creates mystery - bucket should be here",
            plot_hook_description="The well bucket is mysteriously absent",
            new_facts=["bucket is_missing well_behind_farmhouse"],
        )

        assert result.decision == ItemSpawnDecision.PLOT_HOOK_MISSING
        assert result.plot_hook_description == "The well bucket is mysteriously absent"
        assert len(result.new_facts) == 1

    def test_create_plot_hook_relocated_result(self):
        """Test creating a plot hook relocated result."""
        result = ItemSpawnResult(
            item_name="medicine_chest",
            decision=ItemSpawnDecision.PLOT_HOOK_RELOCATED,
            reasoning="Valuable item was taken by bandits",
            spawn_location="bandit_camp",
            plot_hook_description="The medicine chest was taken to the bandit camp",
            new_facts=["medicine_chest is_at bandit_camp", "bandits raided farmhouse"],
        )

        assert result.decision == ItemSpawnDecision.PLOT_HOOK_RELOCATED
        assert result.spawn_location == "bandit_camp"
        assert len(result.new_facts) == 2

    def test_create_defer_result(self):
        """Test creating a defer result for decorative items."""
        result = ItemSpawnResult(
            item_name="pebbles",
            decision=ItemSpawnDecision.DEFER,
            reasoning="Decorative item - track for later on-demand spawning",
        )

        assert result.decision == ItemSpawnDecision.DEFER
        assert result.spawn_location is None

    def test_spawn_result_to_dict(self):
        """Test serialization to dictionary."""
        result = ItemSpawnResult(
            item_name="rope",
            decision=ItemSpawnDecision.SPAWN,
            reasoning="Common tool",
            new_facts=["rope found_at barn"],
        )

        data = result.to_dict()

        assert data["item_name"] == "rope"
        assert data["decision"] == "spawn"
        assert data["reasoning"] == "Common tool"
        assert data["new_facts"] == ["rope found_at barn"]

    def test_spawn_result_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "item_name": "bucket",
            "decision": "plot_hook_missing",
            "reasoning": "Creates mystery",
            "spawn_location": None,
            "plot_hook_description": "Bucket is gone",
            "new_facts": ["bucket was_stolen"],
        }

        result = ItemSpawnResult.from_dict(data)

        assert result.item_name == "bucket"
        assert result.decision == ItemSpawnDecision.PLOT_HOOK_MISSING
        assert result.plot_hook_description == "Bucket is gone"

    def test_spawn_result_roundtrip(self):
        """Test that to_dict and from_dict are inverse operations."""
        original = ItemSpawnResult(
            item_name="chest",
            decision=ItemSpawnDecision.PLOT_HOOK_RELOCATED,
            reasoning="Valuable item was moved",
            spawn_location="thief_hideout",
            plot_hook_description="The chest was taken",
            new_facts=["chest at_location thief_hideout"],
        )

        roundtrip = ItemSpawnResult.from_dict(original.to_dict())

        assert roundtrip.item_name == original.item_name
        assert roundtrip.decision == original.decision
        assert roundtrip.reasoning == original.reasoning
        assert roundtrip.spawn_location == original.spawn_location
        assert roundtrip.plot_hook_description == original.plot_hook_description
        assert roundtrip.new_facts == original.new_facts
