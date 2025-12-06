"""Combat resolver node for LangGraph.

This node resolves one round of combat, processing attacks and damage.
"""

from typing import Any

from sqlalchemy.orm import Session

from src.agents.schemas.combat import CombatState, Combatant
from src.agents.state import GameState
from src.database.models.session import GameSession
from src.managers.combat_manager import CombatManager


async def combat_resolver_node(state: GameState) -> dict[str, Any]:
    """Resolve one round of combat.

    Processes the current combatant's turn, handles attacks and damage,
    and determines if combat should continue.

    Args:
        state: Current game state with combat_state.

    Returns:
        Partial state update with combat results.
    """
    db: Session | None = state.get("_db")
    game_session: GameSession | None = state.get("_game_session")

    if db is None or game_session is None:
        return {
            "errors": ["Missing database context in combat resolver"],
            "combat_active": False,
            "combat_state": None,
        }

    combat_manager = CombatManager(db, game_session)

    # Load or initialize combat state
    raw_state = state.get("combat_state")
    if raw_state is None:
        return {
            "errors": ["No combat state found"],
            "combat_active": False,
            "combat_state": None,
        }

    # Parse state from dict if needed
    if isinstance(raw_state, dict):
        combat_state = CombatState.from_dict(raw_state)
    else:
        combat_state = raw_state

    # Check if combat is already over
    if combat_state.is_combat_over:
        return _handle_combat_end(combat_state)

    # Get current combatant
    current = combat_state.current_combatant
    if current is None:
        return {
            "errors": ["No current combatant"],
            "combat_active": False,
            "combat_state": None,
        }

    narratives = []

    # Process turn based on whether it's player or enemy
    if current.is_player:
        # Player turn - attack first enemy
        enemies = combat_manager.get_living_enemies(combat_state)
        if enemies:
            target = enemies[0]  # Attack first living enemy

            hit, damage, narrative = combat_manager.resolve_attack(current, target)
            narratives.append(narrative)

            if hit:
                updated_target, damage_narrative = combat_manager.apply_damage(
                    target, damage, current.damage_type
                )
                narratives.append(damage_narrative)
                combat_state.update_combatant(updated_target)
    else:
        # Enemy turn - attack player
        player = combat_manager.get_player(combat_state)
        if player and not player.is_dead:
            hit, damage, narrative = combat_manager.resolve_attack(current, player)
            narratives.append(narrative)

            if hit:
                updated_player, damage_narrative = combat_manager.apply_damage(
                    player, damage, current.damage_type
                )
                narratives.append(damage_narrative)
                combat_state.update_combatant(updated_player)

    # Check if combat ended after this action
    if combat_state.is_combat_over:
        return _handle_combat_end(combat_state, narratives)

    # Advance to next turn
    combat_state = combat_manager.advance_turn(combat_state)

    # Add turn narrative to log
    combat_state.combat_log.extend(narratives)

    return {
        "combat_state": combat_state.to_dict(),
        "combat_active": True,
        "gm_response": "\n".join(narratives) if narratives else None,
    }


def _handle_combat_end(
    combat_state: CombatState,
    narratives: list[str] | None = None,
) -> dict[str, Any]:
    """Handle combat ending.

    Args:
        combat_state: Final combat state.
        narratives: Any final narratives.

    Returns:
        State update for combat end.
    """
    narratives = narratives or []

    if combat_state.player_victory:
        narratives.append("\nVictory! All enemies have been defeated!")
    else:
        narratives.append("\nDefeat... You have fallen in battle.")

    return {
        "combat_state": None,
        "combat_active": False,
        "gm_response": "\n".join(narratives) if narratives else None,
    }
