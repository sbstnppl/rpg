"""Execute actions node for the System-Authority architecture.

This node executes validated actions and produces mechanical results.
"""

from typing import Any, Callable, Coroutine

from sqlalchemy.orm import Session

from src.agents.state import GameState
from src.database.models.entities import Entity
from src.database.models.session import GameSession
from src.parser.action_types import Action, ActionType
from src.validators.action_validator import ValidationResult
from src.executor.action_executor import ActionExecutor


async def execute_actions_node(state: GameState) -> dict[str, Any]:
    """Execute all validated actions.

    Uses the ActionExecutor to execute each valid action and produce results.

    Args:
        state: Current game state with validation_results.

    Returns:
        Partial state update with turn_result.
    """
    db: Session = state.get("_db")  # type: ignore
    game_session: GameSession = state.get("_game_session")  # type: ignore

    if db is None or game_session is None:
        return {
            "turn_result": None,
            "errors": ["Missing database session or game session in state"],
        }

    validation_results = state.get("validation_results", [])
    if not validation_results:
        return {
            "turn_result": {
                "executions": [],
                "failed_actions": [],
            },
        }

    # Get actor (player entity)
    player_id = state.get("player_id")
    if not player_id:
        return {
            "turn_result": None,
            "errors": ["Missing player_id in state"],
        }

    actor = db.query(Entity).filter(Entity.id == player_id).first()
    if not actor:
        return {
            "turn_result": None,
            "errors": [f"Player entity not found: {player_id}"],
        }

    executor = ActionExecutor(db, game_session)

    # Get player location for execution
    player_location = state.get("player_location", "")

    # Get dynamic plans for CUSTOM actions
    dynamic_plans = state.get("dynamic_plans", {})

    # Separate valid and failed validations
    valid_results = []
    failed_results = []

    for result_dict in validation_results:
        action_dict = result_dict["action"]
        action = Action(
            type=ActionType(action_dict["type"]),
            target=action_dict.get("target"),
            indirect_target=action_dict.get("indirect_target"),
            manner=action_dict.get("manner"),
            parameters=action_dict.get("parameters", {}),
        )

        validation = ValidationResult(
            action=action,
            valid=result_dict["valid"],
            reason=result_dict.get("reason"),
            warnings=result_dict.get("warnings", []),
            risk_tags=result_dict.get("risk_tags", []),
            resolved_target=result_dict.get("resolved_target"),
            resolved_indirect=result_dict.get("resolved_indirect"),
            metadata=result_dict.get("metadata", {}),
        )

        if validation.valid:
            valid_results.append(validation)
        else:
            failed_results.append(validation)

    # Execute valid actions (pass player_location for players without NPCExtension)
    turn_result = await executor.execute_turn(
        valid_actions=valid_results,
        failed_actions=failed_results,
        actor=actor,
        actor_location=player_location,
        dynamic_plans=dynamic_plans,
    )

    # Convert TurnResult to dict for state serialization
    executions = []
    for ex in turn_result.executions:
        executions.append({
            "action": {
                "type": ex.action.type.value,
                "target": ex.action.target,
                "indirect_target": ex.action.indirect_target,
            },
            "success": ex.success,
            "outcome": ex.outcome,
            "state_changes": ex.state_changes,
            "metadata": ex.metadata,
        })

    failed_actions = []
    for fail in turn_result.failed_validations:
        failed_actions.append({
            "action": {
                "type": fail.action.type.value,
                "target": fail.action.target,
            },
            "reason": fail.reason,
        })

    new_facts = []
    for fact in turn_result.new_facts:
        new_facts.append({
            "subject_key": fact.subject_key,
            "predicate": fact.predicate,
            "value": fact.value,
        })

    turn_result_dict = {
        "executions": executions,
        "failed_actions": failed_actions,
        "new_facts": new_facts,
        "complication": None,  # Will be added when oracle is implemented
    }

    return {
        "turn_result": turn_result_dict,
    }


def create_execute_actions_node(
    db: Session,
    game_session: GameSession,
) -> Callable[[GameState], Coroutine[Any, Any, dict[str, Any]]]:
    """Create an execute actions node with bound dependencies.

    Args:
        db: Database session.
        game_session: Current game session.

    Returns:
        Async node function that executes actions.
    """

    async def node(state: GameState) -> dict[str, Any]:
        """Execute all validated actions.

        Args:
            state: Current game state.

        Returns:
            Partial state update with turn_result.
        """
        validation_results = state.get("validation_results", [])
        if not validation_results:
            return {
                "turn_result": {
                    "executions": [],
                    "failed_actions": [],
                },
            }

        player_id = state.get("player_id")
        if not player_id:
            return {
                "turn_result": None,
                "errors": ["Missing player_id in state"],
            }

        actor = db.query(Entity).filter(Entity.id == player_id).first()
        if not actor:
            return {
                "turn_result": None,
                "errors": [f"Player entity not found: {player_id}"],
            }

        executor = ActionExecutor(db, game_session)

        # Get player location for execution
        player_location = state.get("player_location", "")

        # Get dynamic plans for CUSTOM actions
        dynamic_plans = state.get("dynamic_plans", {})

        valid_results = []
        failed_results = []

        for result_dict in validation_results:
            action_dict = result_dict["action"]
            action = Action(
                type=ActionType(action_dict["type"]),
                target=action_dict.get("target"),
                indirect_target=action_dict.get("indirect_target"),
                manner=action_dict.get("manner"),
                parameters=action_dict.get("parameters", {}),
            )

            validation = ValidationResult(
                action=action,
                valid=result_dict["valid"],
                reason=result_dict.get("reason"),
                warnings=result_dict.get("warnings", []),
                risk_tags=result_dict.get("risk_tags", []),
                resolved_target=result_dict.get("resolved_target"),
                resolved_indirect=result_dict.get("resolved_indirect"),
                metadata=result_dict.get("metadata", {}),
            )

            if validation.valid:
                valid_results.append(validation)
            else:
                failed_results.append(validation)

        turn_result = await executor.execute_turn(
            valid_actions=valid_results,
            failed_actions=failed_results,
            actor=actor,
            actor_location=player_location,
            dynamic_plans=dynamic_plans,
        )

        executions = []
        for ex in turn_result.executions:
            executions.append({
                "action": {
                    "type": ex.action.type.value,
                    "target": ex.action.target,
                    "indirect_target": ex.action.indirect_target,
                },
                "success": ex.success,
                "outcome": ex.outcome,
                "state_changes": ex.state_changes,
                "metadata": ex.metadata,
            })

        failed_actions = []
        for fail in turn_result.failed_validations:
            failed_actions.append({
                "action": {
                    "type": fail.action.type.value,
                    "target": fail.action.target,
                },
                "reason": fail.reason,
            })

        new_facts = []
        for fact in turn_result.new_facts:
            new_facts.append({
                "subject_key": fact.subject_key,
                "predicate": fact.predicate,
                "value": fact.value,
            })

        return {
            "turn_result": {
                "executions": executions,
                "failed_actions": failed_actions,
                "new_facts": new_facts,
                "complication": None,
            },
        }

    return node
