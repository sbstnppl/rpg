"""Tests for combat resolver node."""

import pytest
from unittest.mock import patch, MagicMock

from sqlalchemy.orm import Session

from src.database.models.session import GameSession
from src.database.models.entities import Entity
from src.database.models.enums import EntityType
from tests.factories import create_entity, create_monster_extension, create_entity_attribute


class TestCombatState:
    """Test CombatState dataclass."""

    def test_combatant_creation(self):
        """Test creating a Combatant."""
        from src.agents.schemas.combat import Combatant

        combatant = Combatant(
            entity_id=1,
            entity_key="hero",
            display_name="Hero",
            initiative=15,
            hit_points=30,
            max_hit_points=30,
            armor_class=15,
        )

        assert combatant.entity_id == 1
        assert combatant.hit_points == 30
        assert combatant.is_dead is False

    def test_combat_state_creation(self):
        """Test creating a CombatState."""
        from src.agents.schemas.combat import CombatState, Combatant

        player = Combatant(
            entity_id=1, entity_key="hero", display_name="Hero",
            initiative=18, hit_points=30, max_hit_points=30,
            is_player=True,
        )
        goblin = Combatant(
            entity_id=2, entity_key="goblin", display_name="Goblin",
            initiative=12, hit_points=7, max_hit_points=7,
        )

        state = CombatState(
            combatants=[player, goblin],
            initiative_order=[1, 2],
        )

        assert len(state.combatants) == 2
        assert state.round_number == 1
        assert state.current_turn_index == 0

    def test_combat_state_current_combatant(self):
        """Test getting current combatant."""
        from src.agents.schemas.combat import CombatState, Combatant

        player = Combatant(
            entity_id=1, entity_key="hero", display_name="Hero",
            initiative=18, hit_points=30, max_hit_points=30,
            is_player=True,
        )
        goblin = Combatant(
            entity_id=2, entity_key="goblin", display_name="Goblin",
            initiative=12, hit_points=7, max_hit_points=7,
        )

        state = CombatState(
            combatants=[player, goblin],
            initiative_order=[1, 2],  # Player first
        )

        current = state.current_combatant
        assert current.entity_id == 1
        assert current.is_player is True

    def test_combat_over_all_enemies_dead(self):
        """Combat ends when all enemies are dead."""
        from src.agents.schemas.combat import CombatState, Combatant

        player = Combatant(
            entity_id=1, entity_key="hero", display_name="Hero",
            hit_points=30, max_hit_points=30, is_player=True,
        )
        goblin = Combatant(
            entity_id=2, entity_key="goblin", display_name="Goblin",
            hit_points=0, max_hit_points=7, is_dead=True,
        )

        state = CombatState(combatants=[player, goblin], initiative_order=[1, 2])

        assert state.is_combat_over is True
        assert state.player_victory is True

    def test_combat_over_player_dead(self):
        """Combat ends when player is dead."""
        from src.agents.schemas.combat import CombatState, Combatant

        player = Combatant(
            entity_id=1, entity_key="hero", display_name="Hero",
            hit_points=0, max_hit_points=30, is_player=True, is_dead=True,
        )
        goblin = Combatant(
            entity_id=2, entity_key="goblin", display_name="Goblin",
            hit_points=7, max_hit_points=7,
        )

        state = CombatState(combatants=[player, goblin], initiative_order=[1, 2])

        assert state.is_combat_over is True
        assert state.player_victory is False


class TestCombatManager:
    """Test CombatManager business logic."""

    def test_initialize_combat(self, db_session: Session, game_session: GameSession):
        """Test initializing combat between player and monster."""
        from src.managers.combat_manager import CombatManager

        player = create_entity(db_session, game_session, entity_type=EntityType.PLAYER)
        create_entity_attribute(db_session, player, attribute_key="dexterity", value=14)

        monster = create_entity(db_session, game_session, entity_type=EntityType.MONSTER)
        create_monster_extension(db_session, monster, hit_points=10, armor_class=12)

        manager = CombatManager(db_session, game_session)
        state = manager.initialize_combat(player.id, [monster.id])

        assert len(state.combatants) == 2
        assert len(state.initiative_order) == 2

    def test_roll_initiatives_sorted(self, db_session: Session, game_session: GameSession):
        """Test that initiatives are sorted high to low."""
        from src.managers.combat_manager import CombatManager
        from src.agents.schemas.combat import CombatState, Combatant

        player = Combatant(
            entity_id=1, entity_key="hero", display_name="Hero",
            hit_points=30, max_hit_points=30, is_player=True,
        )
        goblin = Combatant(
            entity_id=2, entity_key="goblin", display_name="Goblin",
            hit_points=7, max_hit_points=7,
        )

        state = CombatState(combatants=[player, goblin], initiative_order=[])

        manager = CombatManager(db_session, game_session)

        # Roll initiatives with mocked dice
        with patch('src.managers.combat_manager.roll_initiative') as mock_roll:
            # Player rolls 18, goblin rolls 12
            mock_roll.side_effect = [
                MagicMock(total=18),
                MagicMock(total=12),
            ]
            state = manager.roll_all_initiatives(state)

        # Player (18) should be first
        assert state.initiative_order[0] == 1

    def test_resolve_attack_hit(self, db_session: Session, game_session: GameSession):
        """Test resolving an attack that hits."""
        from src.managers.combat_manager import CombatManager
        from src.agents.schemas.combat import Combatant

        attacker = Combatant(
            entity_id=1, entity_key="hero", display_name="Hero",
            hit_points=30, max_hit_points=30,
            attack_bonus=5, damage_dice="1d8",
        )
        defender = Combatant(
            entity_id=2, entity_key="goblin", display_name="Goblin",
            hit_points=7, max_hit_points=7, armor_class=12,
        )

        manager = CombatManager(db_session, game_session)

        # Mock attack roll to always hit
        with patch('src.managers.combat_manager.make_attack_roll') as mock_attack:
            mock_attack.return_value = MagicMock(hit=True, is_critical_hit=False)
            with patch('src.managers.combat_manager.roll_damage') as mock_damage:
                mock_damage.return_value = MagicMock(roll_result=MagicMock(total=5))

                hit, damage, narrative = manager.resolve_attack(attacker, defender)

        assert hit is True
        assert damage == 5

    def test_resolve_attack_miss(self, db_session: Session, game_session: GameSession):
        """Test resolving an attack that misses."""
        from src.managers.combat_manager import CombatManager
        from src.agents.schemas.combat import Combatant

        attacker = Combatant(
            entity_id=1, entity_key="hero", display_name="Hero",
            hit_points=30, max_hit_points=30, attack_bonus=5,
        )
        defender = Combatant(
            entity_id=2, entity_key="goblin", display_name="Goblin",
            hit_points=7, max_hit_points=7, armor_class=20,  # High AC
        )

        manager = CombatManager(db_session, game_session)

        with patch('src.managers.combat_manager.make_attack_roll') as mock_attack:
            mock_attack.return_value = MagicMock(hit=False, is_critical_hit=False)

            hit, damage, narrative = manager.resolve_attack(attacker, defender)

        assert hit is False
        assert damage == 0

    def test_apply_damage_reduces_hp(self, db_session: Session, game_session: GameSession):
        """Test applying damage reduces hit points."""
        from src.managers.combat_manager import CombatManager
        from src.agents.schemas.combat import Combatant

        combatant = Combatant(
            entity_id=1, entity_key="goblin", display_name="Goblin",
            hit_points=10, max_hit_points=10,
        )

        manager = CombatManager(db_session, game_session)
        updated, narrative = manager.apply_damage(combatant, 5, "slashing")

        assert updated.hit_points == 5
        assert updated.is_dead is False

    def test_apply_damage_kills_at_zero(self, db_session: Session, game_session: GameSession):
        """Test that 0 HP marks combatant as dead."""
        from src.managers.combat_manager import CombatManager
        from src.agents.schemas.combat import Combatant

        combatant = Combatant(
            entity_id=1, entity_key="goblin", display_name="Goblin",
            hit_points=5, max_hit_points=10,
        )

        manager = CombatManager(db_session, game_session)
        updated, narrative = manager.apply_damage(combatant, 10, "slashing")

        assert updated.hit_points == 0
        assert updated.is_dead is True

    def test_advance_turn(self, db_session: Session, game_session: GameSession):
        """Test advancing to next turn."""
        from src.managers.combat_manager import CombatManager
        from src.agents.schemas.combat import CombatState, Combatant

        player = Combatant(entity_id=1, entity_key="hero", display_name="Hero",
                           hit_points=30, max_hit_points=30, is_player=True)
        goblin = Combatant(entity_id=2, entity_key="goblin", display_name="Goblin",
                           hit_points=7, max_hit_points=7)

        state = CombatState(
            combatants=[player, goblin],
            initiative_order=[1, 2],
            current_turn_index=0,
        )

        manager = CombatManager(db_session, game_session)
        state = manager.advance_turn(state)

        assert state.current_turn_index == 1

    def test_advance_turn_wraps_to_new_round(self, db_session: Session, game_session: GameSession):
        """Test that turn wraps to new round."""
        from src.managers.combat_manager import CombatManager
        from src.agents.schemas.combat import CombatState, Combatant

        player = Combatant(entity_id=1, entity_key="hero", display_name="Hero",
                           hit_points=30, max_hit_points=30, is_player=True)
        goblin = Combatant(entity_id=2, entity_key="goblin", display_name="Goblin",
                           hit_points=7, max_hit_points=7)

        state = CombatState(
            combatants=[player, goblin],
            initiative_order=[1, 2],
            current_turn_index=1,  # Last combatant's turn
            round_number=1,
        )

        manager = CombatManager(db_session, game_session)
        state = manager.advance_turn(state)

        assert state.current_turn_index == 0
        assert state.round_number == 2


class TestCombatResolverNode:
    """Test combat resolver graph node."""

    @pytest.mark.asyncio
    async def test_node_returns_combat_state(self, db_session: Session, game_session: GameSession):
        """Test that node returns updated combat state."""
        from src.agents.nodes.combat_resolver_node import combat_resolver_node
        from src.agents.schemas.combat import CombatState, Combatant

        player = create_entity(db_session, game_session, entity_type=EntityType.PLAYER)
        monster = create_entity(db_session, game_session, entity_type=EntityType.MONSTER)
        create_monster_extension(db_session, monster, hit_points=7, armor_class=12)

        # Set up combat state
        combat_state = CombatState(
            combatants=[
                Combatant(entity_id=player.id, entity_key=player.entity_key,
                          display_name=player.display_name, hit_points=30,
                          max_hit_points=30, is_player=True, initiative=18),
                Combatant(entity_id=monster.id, entity_key=monster.entity_key,
                          display_name=monster.display_name, hit_points=7,
                          max_hit_points=7, armor_class=12, initiative=10),
            ],
            initiative_order=[player.id, monster.id],
        )

        state = {
            "_db": db_session,
            "_game_session": game_session,
            "combat_active": True,
            "combat_state": combat_state.to_dict(),
            "player_input": "attack goblin",
            "player_id": player.id,
        }

        result = await combat_resolver_node(state)

        # Should return combat-related fields
        assert "combat_active" in result
        assert "combat_state" in result or result.get("combat_active") is False

    @pytest.mark.asyncio
    async def test_node_ends_combat_on_victory(self, db_session: Session, game_session: GameSession):
        """Test that combat ends when all enemies dead."""
        from src.agents.nodes.combat_resolver_node import combat_resolver_node
        from src.agents.schemas.combat import CombatState, Combatant

        player = create_entity(db_session, game_session, entity_type=EntityType.PLAYER)
        monster = create_entity(db_session, game_session, entity_type=EntityType.MONSTER)
        create_monster_extension(db_session, monster, hit_points=1, armor_class=5)  # Easy kill

        combat_state = CombatState(
            combatants=[
                Combatant(entity_id=player.id, entity_key=player.entity_key,
                          display_name=player.display_name, hit_points=30,
                          max_hit_points=30, is_player=True, initiative=20,
                          attack_bonus=10, damage_dice="2d6"),  # Strong attack
                Combatant(entity_id=monster.id, entity_key=monster.entity_key,
                          display_name=monster.display_name, hit_points=1,
                          max_hit_points=1, armor_class=5, initiative=1),
            ],
            initiative_order=[player.id, monster.id],
        )

        state = {
            "_db": db_session,
            "_game_session": game_session,
            "combat_active": True,
            "combat_state": combat_state.to_dict(),
            "player_input": "attack",
            "player_id": player.id,
        }

        # Mock dice to ensure hit and kill
        with patch('src.managers.combat_manager.make_attack_roll') as mock_attack:
            mock_attack.return_value = MagicMock(hit=True, is_critical_hit=False)
            with patch('src.managers.combat_manager.roll_damage') as mock_damage:
                mock_damage.return_value = MagicMock(roll_result=MagicMock(total=10))

                result = await combat_resolver_node(state)

        # Combat should end
        assert result.get("combat_active") is False


class TestCombatStateSerializer:
    """Test combat state serialization."""

    def test_to_dict(self):
        """Test CombatState to_dict."""
        from src.agents.schemas.combat import CombatState, Combatant

        state = CombatState(
            round_number=2,
            current_turn_index=1,
            combatants=[
                Combatant(entity_id=1, entity_key="hero", display_name="Hero",
                          hit_points=25, max_hit_points=30, is_player=True,
                          initiative=18),
            ],
            initiative_order=[1],
        )

        d = state.to_dict()

        assert d["round_number"] == 2
        assert d["current_turn_index"] == 1
        assert len(d["combatants"]) == 1
        assert d["combatants"][0]["entity_id"] == 1

    def test_from_dict(self):
        """Test CombatState from_dict."""
        from src.agents.schemas.combat import CombatState

        d = {
            "round_number": 2,
            "current_turn_index": 1,
            "combatants": [
                {"entity_id": 1, "entity_key": "hero", "display_name": "Hero",
                 "hit_points": 25, "max_hit_points": 30, "is_player": True,
                 "initiative": 18, "armor_class": 15, "attack_bonus": 5,
                 "damage_dice": "1d8", "damage_type": "slashing", "is_dead": False},
            ],
            "initiative_order": [1],
            "combat_log": [],
        }

        state = CombatState.from_dict(d)

        assert state.round_number == 2
        assert len(state.combatants) == 1
        assert state.combatants[0].hit_points == 25
