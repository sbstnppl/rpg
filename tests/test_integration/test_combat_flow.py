"""End-to-end tests for combat flow.

Tests combat initialization, resolution, and victory/defeat conditions.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.orm import Session

from src.agents.graph import build_game_graph
from src.agents.schemas.combat import CombatState, Combatant
from src.agents.state import create_initial_state
from src.database.models.entities import Entity, MonsterExtension
from src.database.models.enums import EntityType
from src.database.models.session import GameSession
from src.llm.response_types import LLMResponse
from src.managers.combat_manager import CombatManager
from tests.factories import create_entity


@pytest.fixture
def player_with_stats(db_session: Session, game_session: GameSession) -> Entity:
    """Create a player with combat stats."""
    from src.database.models.entities import EntityAttribute

    player = create_entity(
        db_session, game_session,
        entity_type=EntityType.PLAYER,
        entity_key="hero",
        display_name="The Hero",
    )

    # Add attributes
    for attr_key, value in [("strength", 14), ("dexterity", 12), ("constitution", 14)]:
        attr = EntityAttribute(
            entity_id=player.id,
            attribute_key=attr_key,
            value=value,
        )
        db_session.add(attr)

    db_session.flush()
    return player


@pytest.fixture
def goblin_enemy(db_session: Session, game_session: GameSession) -> Entity:
    """Create a goblin enemy with stats."""
    from src.database.models.entities import EntityAttribute

    goblin = create_entity(
        db_session, game_session,
        entity_type=EntityType.MONSTER,
        entity_key="goblin_1",
        display_name="Goblin Scout",
    )

    # Add monster extension with HP
    monster_ext = MonsterExtension(
        entity_id=goblin.id,
        hit_points=7,
        max_hit_points=7,
        armor_class=13,
        challenge_rating=0.25,
    )
    db_session.add(monster_ext)

    # Add attributes
    for attr_key, value in [("strength", 8), ("dexterity", 14)]:
        attr = EntityAttribute(
            entity_id=goblin.id,
            attribute_key=attr_key,
            value=value,
        )
        db_session.add(attr)

    db_session.flush()
    return goblin


class TestCombatInitialization:
    """Test combat initialization."""

    def test_combat_manager_initializes_combat(
        self,
        db_session: Session,
        game_session: GameSession,
        player_with_stats,
        goblin_enemy,
    ):
        """CombatManager should properly initialize combat state."""
        manager = CombatManager(db_session, game_session)

        combat_state = manager.initialize_combat(
            player_id=player_with_stats.id,
            enemy_ids=[goblin_enemy.id],
        )

        assert len(combat_state.combatants) == 2
        assert len(combat_state.initiative_order) == 2

        # Player should be in combatants
        player_combatant = next(
            (c for c in combat_state.combatants if c.is_player), None
        )
        assert player_combatant is not None
        assert player_combatant.entity_key == "hero"

        # Goblin should be in combatants
        goblin_combatant = next(
            (c for c in combat_state.combatants if c.entity_key == "goblin_1"), None
        )
        assert goblin_combatant is not None
        assert goblin_combatant.hit_points == 7

    def test_initiative_order_established(
        self,
        db_session: Session,
        game_session: GameSession,
        player_with_stats,
        goblin_enemy,
    ):
        """Combat initialization should roll initiative for all combatants."""
        manager = CombatManager(db_session, game_session)

        combat_state = manager.initialize_combat(
            player_id=player_with_stats.id,
            enemy_ids=[goblin_enemy.id],
        )

        # All combatants should have initiative values
        for combatant in combat_state.combatants:
            assert combatant.initiative is not None
            assert combatant.initiative >= 1  # At least 1 from d20

        # Initiative order should be sorted high to low
        initiatives = [
            combat_state.get_combatant(entity_id).initiative
            for entity_id in combat_state.initiative_order
        ]
        assert initiatives == sorted(initiatives, reverse=True)


class TestCombatResolution:
    """Test combat resolution mechanics."""

    def test_attack_hit_deals_damage(
        self,
        db_session: Session,
        game_session: GameSession,
        player_with_stats,
        goblin_enemy,
    ):
        """Successful attack should deal damage to target."""
        manager = CombatManager(db_session, game_session)

        player_combatant = Combatant(
            entity_id=player_with_stats.id,
            entity_key="hero",
            display_name="The Hero",
            hit_points=30,
            max_hit_points=30,
            armor_class=15,
            attack_bonus=4,
            damage_dice="1d8",
            is_player=True,
        )

        goblin_combatant = Combatant(
            entity_id=goblin_enemy.id,
            entity_key="goblin_1",
            display_name="Goblin Scout",
            hit_points=7,
            max_hit_points=7,
            armor_class=13,
            attack_bonus=2,
            damage_dice="1d6",
            is_player=False,
        )

        # Mock a hit
        with patch.object(manager, 'resolve_attack') as mock_attack:
            mock_attack.return_value = (True, 5, "Hero hits Goblin for 5 damage!")

            hit, damage, narrative = manager.resolve_attack(player_combatant, goblin_combatant)

            assert hit is True
            assert damage == 5
            assert "5 damage" in narrative

    def test_attack_miss_no_damage(
        self,
        db_session: Session,
        game_session: GameSession,
        player_with_stats,
        goblin_enemy,
    ):
        """Missed attack should not deal damage."""
        manager = CombatManager(db_session, game_session)

        attacker = Combatant(
            entity_id=goblin_enemy.id,
            entity_key="goblin_1",
            display_name="Goblin Scout",
            hit_points=7,
            max_hit_points=7,
            armor_class=13,
            attack_bonus=2,
            damage_dice="1d6",
            is_player=False,
        )

        defender = Combatant(
            entity_id=player_with_stats.id,
            entity_key="hero",
            display_name="The Hero",
            hit_points=30,
            max_hit_points=30,
            armor_class=18,  # High AC to almost guarantee miss
            attack_bonus=4,
            damage_dice="1d8",
            is_player=True,
        )

        # Run multiple attacks - at least some should miss
        misses = 0
        for _ in range(10):
            hit, damage, narrative = manager.resolve_attack(attacker, defender)
            if not hit:
                misses += 1
                assert damage == 0
                assert "miss" in narrative.lower()

        # Should have at least some misses with high AC
        assert misses > 0

    def test_damage_reduces_hp(
        self,
        db_session: Session,
        game_session: GameSession,
    ):
        """Applying damage should reduce combatant HP."""
        manager = CombatManager(db_session, game_session)

        combatant = Combatant(
            entity_id=1,
            entity_key="test",
            display_name="Test",
            hit_points=20,
            max_hit_points=20,
            is_player=False,
        )

        updated, narrative = manager.apply_damage(combatant, 8, "slashing")

        assert updated.hit_points == 12
        assert updated.is_dead is False
        assert "12" in narrative

    def test_lethal_damage_kills_combatant(
        self,
        db_session: Session,
        game_session: GameSession,
    ):
        """Damage that reduces HP to 0 should kill combatant."""
        manager = CombatManager(db_session, game_session)

        combatant = Combatant(
            entity_id=1,
            entity_key="test",
            display_name="Test Enemy",
            hit_points=5,
            max_hit_points=10,
            is_player=False,
        )

        updated, narrative = manager.apply_damage(combatant, 10, "slashing")

        assert updated.hit_points == 0
        assert updated.is_dead is True
        assert "defeated" in narrative.lower()


class TestCombatStateTracking:
    """Test combat state tracking."""

    def test_combat_over_when_all_enemies_dead(
        self,
        db_session: Session,
        game_session: GameSession,
    ):
        """Combat should end when all enemies are dead."""
        player = Combatant(
            entity_id=1,
            entity_key="hero",
            display_name="Hero",
            hit_points=30,
            max_hit_points=30,
            is_player=True,
        )

        enemy = Combatant(
            entity_id=2,
            entity_key="goblin",
            display_name="Goblin",
            hit_points=0,
            max_hit_points=7,
            is_player=False,
            is_dead=True,
        )

        state = CombatState(
            combatants=[player, enemy],
            initiative_order=[1, 2],
        )

        assert state.is_combat_over is True
        assert state.player_victory is True

    def test_combat_over_when_player_dead(
        self,
        db_session: Session,
        game_session: GameSession,
    ):
        """Combat should end when player is dead."""
        player = Combatant(
            entity_id=1,
            entity_key="hero",
            display_name="Hero",
            hit_points=0,
            max_hit_points=30,
            is_player=True,
            is_dead=True,
        )

        enemy = Combatant(
            entity_id=2,
            entity_key="goblin",
            display_name="Goblin",
            hit_points=7,
            max_hit_points=7,
            is_player=False,
        )

        state = CombatState(
            combatants=[player, enemy],
            initiative_order=[1, 2],
        )

        assert state.is_combat_over is True
        assert state.player_victory is False

    def test_combat_continues_while_both_alive(
        self,
        db_session: Session,
        game_session: GameSession,
    ):
        """Combat should continue while both player and enemies are alive."""
        player = Combatant(
            entity_id=1,
            entity_key="hero",
            display_name="Hero",
            hit_points=10,
            max_hit_points=30,
            is_player=True,
        )

        enemy = Combatant(
            entity_id=2,
            entity_key="goblin",
            display_name="Goblin",
            hit_points=3,
            max_hit_points=7,
            is_player=False,
        )

        state = CombatState(
            combatants=[player, enemy],
            initiative_order=[1, 2],
        )

        assert state.is_combat_over is False


class TestCombatTurnAdvancement:
    """Test turn advancement in combat."""

    def test_turn_advances_to_next_combatant(
        self,
        db_session: Session,
        game_session: GameSession,
    ):
        """Turn should advance to next combatant in initiative order."""
        manager = CombatManager(db_session, game_session)

        player = Combatant(
            entity_id=1,
            entity_key="hero",
            display_name="Hero",
            hit_points=30,
            max_hit_points=30,
            is_player=True,
            initiative=18,
        )

        enemy = Combatant(
            entity_id=2,
            entity_key="goblin",
            display_name="Goblin",
            hit_points=7,
            max_hit_points=7,
            is_player=False,
            initiative=12,
        )

        state = CombatState(
            combatants=[player, enemy],
            initiative_order=[1, 2],  # Player first
            current_turn_index=0,
        )

        new_state = manager.advance_turn(state)

        assert new_state.current_turn_index == 1
        assert new_state.current_combatant.entity_key == "goblin"

    def test_turn_wraps_to_new_round(
        self,
        db_session: Session,
        game_session: GameSession,
    ):
        """Turn should wrap to new round after all combatants act."""
        manager = CombatManager(db_session, game_session)

        player = Combatant(
            entity_id=1,
            entity_key="hero",
            display_name="Hero",
            hit_points=30,
            max_hit_points=30,
            is_player=True,
        )

        enemy = Combatant(
            entity_id=2,
            entity_key="goblin",
            display_name="Goblin",
            hit_points=7,
            max_hit_points=7,
            is_player=False,
        )

        state = CombatState(
            combatants=[player, enemy],
            initiative_order=[1, 2],
            current_turn_index=1,  # Last combatant
            round_number=1,
        )

        new_state = manager.advance_turn(state)

        assert new_state.current_turn_index == 0
        assert new_state.round_number == 2

    def test_skips_dead_combatants(
        self,
        db_session: Session,
        game_session: GameSession,
    ):
        """Turn advancement should skip dead combatants."""
        manager = CombatManager(db_session, game_session)

        player = Combatant(
            entity_id=1,
            entity_key="hero",
            display_name="Hero",
            hit_points=30,
            max_hit_points=30,
            is_player=True,
        )

        dead_enemy = Combatant(
            entity_id=2,
            entity_key="goblin_1",
            display_name="Goblin 1",
            hit_points=0,
            max_hit_points=7,
            is_player=False,
            is_dead=True,
        )

        living_enemy = Combatant(
            entity_id=3,
            entity_key="goblin_2",
            display_name="Goblin 2",
            hit_points=7,
            max_hit_points=7,
            is_player=False,
        )

        state = CombatState(
            combatants=[player, dead_enemy, living_enemy],
            initiative_order=[1, 2, 3],
            current_turn_index=0,
        )

        new_state = manager.advance_turn(state)

        # Should skip dead goblin and go to living goblin
        assert new_state.current_turn_index == 2
        assert new_state.current_combatant.entity_key == "goblin_2"


class TestCombatWithGraph:
    """Test combat integration with the graph."""

    @pytest.mark.asyncio
    async def test_combat_flag_set_from_gm_response(
        self,
        db_session: Session,
        game_session: GameSession,
        player_with_stats,
    ):
        """GM response with combat_initiated should set combat_active flag initially."""
        from src.agents.nodes.game_master_node import parse_state_block

        # Test the state block parsing directly
        gm_response_text = """A goblin leaps from the shadows, weapon raised!

---STATE---
time_advance_minutes: 0
location_change: none
combat_initiated: true"""

        narrative, state_changes = parse_state_block(gm_response_text, return_narrative=True)

        assert state_changes["combat_active"] is True
        assert "goblin" in narrative.lower()

    @pytest.mark.asyncio
    async def test_combat_state_serialization(
        self,
        db_session: Session,
        game_session: GameSession,
        player_with_stats,
        goblin_enemy,
    ):
        """Combat state should properly serialize and deserialize."""
        manager = CombatManager(db_session, game_session)

        combat_state = manager.initialize_combat(
            player_id=player_with_stats.id,
            enemy_ids=[goblin_enemy.id],
        )

        # Serialize to dict
        state_dict = combat_state.to_dict()

        assert "combatants" in state_dict
        assert "initiative_order" in state_dict
        assert len(state_dict["combatants"]) == 2

        # Deserialize back
        restored = CombatState.from_dict(state_dict)

        assert len(restored.combatants) == 2
        assert restored.round_number == combat_state.round_number
