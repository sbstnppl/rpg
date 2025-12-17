"""Tests for complication types and dataclasses."""

import pytest

from src.oracle.complication_types import (
    Complication,
    ComplicationType,
    Effect,
    EffectType,
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
