"""Validate actions node for the System-Authority architecture.

This node validates parsed actions mechanically before execution.
"""

from typing import Any, Callable, Coroutine

from sqlalchemy.orm import Session

from src.agents.state import GameState
from src.database.models.entities import Entity
from src.database.models.session import GameSession
from src.parser.action_types import Action, ActionType
from src.validators.action_validator import ActionValidator


async def validate_actions_node(state: GameState) -> dict[str, Any]:
    """Validate all parsed actions mechanically.

    Uses the ActionValidator to check if each action is possible.

    Args:
        state: Current game state with parsed_actions.

    Returns:
        Partial state update with validation_results.
    """
    db: Session = state.get("_db")  # type: ignore
    game_session: GameSession = state.get("_game_session")  # type: ignore

    if db is None or game_session is None:
        return {
            "validation_results": None,
            "errors": ["Missing database session or game session in state"],
        }

    parsed_actions = state.get("parsed_actions", [])
    if not parsed_actions:
        return {
            "validation_results": [],
        }

    # Get actor (player entity)
    player_id = state.get("player_id")
    if not player_id:
        return {
            "validation_results": [],
            "errors": ["Missing player_id in state"],
        }

    actor = db.query(Entity).filter(Entity.id == player_id).first()
    if not actor:
        return {
            "validation_results": [],
            "errors": [f"Player entity not found: {player_id}"],
        }

    # Create validator with combat state
    combat_active = state.get("combat_active", False)
    validator = ActionValidator(db, game_session, combat_active=combat_active)

    # Get player location for validation
    player_location = state.get("player_location", "")

    validation_results = []

    for action_dict in parsed_actions:
        # Convert dict back to Action
        action = Action(
            type=ActionType(action_dict["type"]),
            target=action_dict.get("target"),
            indirect_target=action_dict.get("indirect_target"),
            manner=action_dict.get("manner"),
            parameters=action_dict.get("parameters", {}),
        )

        # Validate (pass player_location for players without NPCExtension)
        result = validator.validate(action, actor, actor_location=player_location)

        # Convert to dict for state serialization
        result_dict = {
            "action": action_dict,
            "valid": result.valid,
            "reason": result.reason,
            "warnings": result.warnings,
            "risk_tags": result.risk_tags,
            "resolved_target": result.resolved_target,
            "resolved_indirect": result.resolved_indirect,
            "metadata": result.metadata,
        }
        validation_results.append(result_dict)

    return {
        "validation_results": validation_results,
    }


def create_validate_actions_node(
    db: Session,
    game_session: GameSession,
) -> Callable[[GameState], Coroutine[Any, Any, dict[str, Any]]]:
    """Create a validate actions node with bound dependencies.

    Args:
        db: Database session.
        game_session: Current game session.

    Returns:
        Async node function that validates actions.
    """

    async def node(state: GameState) -> dict[str, Any]:
        """Validate all parsed actions.

        Args:
            state: Current game state.

        Returns:
            Partial state update with validation_results.
        """
        parsed_actions = state.get("parsed_actions", [])
        if not parsed_actions:
            return {"validation_results": []}

        player_id = state.get("player_id")
        if not player_id:
            return {
                "validation_results": [],
                "errors": ["Missing player_id in state"],
            }

        actor = db.query(Entity).filter(Entity.id == player_id).first()
        if not actor:
            return {
                "validation_results": [],
                "errors": [f"Player entity not found: {player_id}"],
            }

        combat_active = state.get("combat_active", False)
        validator = ActionValidator(db, game_session, combat_active=combat_active)

        validation_results = []

        for action_dict in parsed_actions:
            action = Action(
                type=ActionType(action_dict["type"]),
                target=action_dict.get("target"),
                indirect_target=action_dict.get("indirect_target"),
                manner=action_dict.get("manner"),
                parameters=action_dict.get("parameters", {}),
            )

            result = validator.validate(action, actor)

            result_dict = {
                "action": action_dict,
                "valid": result.valid,
                "reason": result.reason,
                "warnings": result.warnings,
                "risk_tags": result.risk_tags,
                "resolved_target": result.resolved_target,
                "resolved_indirect": result.resolved_indirect,
                "metadata": result.metadata,
            }
            validation_results.append(result_dict)

        return {"validation_results": validation_results}

    return node
