"""Tests for SPAWN_ITEM state change handling."""

import pytest
from src.planner.schemas import (
    StateChangeType,
    SpawnItemSpec,
    StateChange,
    DynamicActionPlan,
    DynamicActionType,
)


class TestSpawnItemSpec:
    """Tests for SpawnItemSpec validation."""

    def test_spawn_item_spec_minimal(self) -> None:
        """Test SpawnItemSpec with minimal required fields."""
        spec = SpawnItemSpec(
            item_type="misc",
            context="washbasin in bedroom corner",
        )
        assert spec.item_type == "misc"
        assert spec.context == "washbasin in bedroom corner"
        assert spec.display_name is None
        assert spec.quality is None
        assert spec.condition is None

    def test_spawn_item_spec_full(self) -> None:
        """Test SpawnItemSpec with all fields."""
        spec = SpawnItemSpec(
            item_type="tool",
            context="old rope coiled in stable corner",
            display_name="Coiled Rope",
            quality="worn",
            condition="good",
        )
        assert spec.item_type == "tool"
        assert spec.display_name == "Coiled Rope"
        assert spec.quality == "worn"
        assert spec.condition == "good"


class TestStateChangeType:
    """Tests for StateChangeType enum."""

    def test_spawn_item_type_exists(self) -> None:
        """Test that SPAWN_ITEM type exists."""
        assert StateChangeType.SPAWN_ITEM == "spawn_item"

    def test_all_types_present(self) -> None:
        """Test all expected state change types are present."""
        types = {t.value for t in StateChangeType}
        expected = {
            "item_property",
            "entity_state",
            "fact",
            "knowledge_query",
            "spawn_item",
        }
        assert types == expected


class TestStateChangeWithSpawn:
    """Tests for StateChange with spawn_spec."""

    def test_state_change_with_spawn_spec(self) -> None:
        """Test StateChange with spawn_spec."""
        change = StateChange(
            change_type=StateChangeType.SPAWN_ITEM,
            target_type="item",
            target_key="auto",
            property_name="spawn",
            new_value=None,
            spawn_spec=SpawnItemSpec(
                item_type="misc",
                context="rope coiled in stable corner",
            ),
        )
        assert change.change_type == StateChangeType.SPAWN_ITEM
        assert change.spawn_spec is not None
        assert change.spawn_spec.item_type == "misc"

    def test_state_change_without_spawn_spec(self) -> None:
        """Test normal StateChange without spawn_spec."""
        change = StateChange(
            change_type=StateChangeType.ITEM_PROPERTY,
            target_type="item",
            target_key="player_shirt",
            property_name="buttoned",
            old_value=False,
            new_value=True,
        )
        assert change.spawn_spec is None


class TestDynamicActionPlanWithSpawn:
    """Tests for DynamicActionPlan with spawn changes."""

    def test_plan_with_spawn_item(self) -> None:
        """Test DynamicActionPlan containing SPAWN_ITEM change."""
        plan = DynamicActionPlan(
            action_type=DynamicActionType.STATE_CHANGE,
            state_changes=[
                StateChange(
                    change_type=StateChangeType.SPAWN_ITEM,
                    target_type="item",
                    target_key="auto",
                    property_name="spawn",
                    new_value=None,
                    spawn_spec=SpawnItemSpec(
                        item_type="misc",
                        context="washbasin on wooden stand",
                        display_name="Washbasin",
                    ),
                ),
            ],
            narrator_facts=[
                "Player finds a simple washbasin on a wooden stand near the window"
            ],
        )
        assert plan.action_type == DynamicActionType.STATE_CHANGE
        assert len(plan.state_changes) == 1
        assert plan.state_changes[0].change_type == StateChangeType.SPAWN_ITEM
        assert plan.state_changes[0].spawn_spec.display_name == "Washbasin"
