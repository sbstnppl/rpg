"""Parse intent node for the System-Authority architecture.

This node parses player input into structured actions using pattern matching
and LLM classification as fallback.
"""

from typing import Any, Callable, Coroutine

from sqlalchemy.orm import Session

from src.agents.state import GameState
from src.database.models.session import GameSession
from src.parser.intent_parser import IntentParser


async def parse_intent_node(state: GameState) -> dict[str, Any]:
    """Parse player input into structured actions.

    Uses the IntentParser to convert natural language into Action objects.

    Args:
        state: Current game state with player_input and context.

    Returns:
        Partial state update with parsed_actions and ambient_flavor.
    """
    db: Session = state.get("_db")  # type: ignore
    game_session: GameSession = state.get("_game_session")  # type: ignore

    if db is None or game_session is None:
        return {
            "parsed_actions": None,
            "errors": ["Missing database session or game session in state"],
        }

    player_input = state.get("player_input", "")
    if not player_input:
        return {
            "parsed_actions": [],
            "ambient_flavor": None,
        }

    parser = IntentParser(db, game_session)

    try:
        parsed_intent = await parser.parse(
            input_text=player_input,
            player_location=state.get("player_location", ""),
        )

        # Convert actions to dicts for state serialization
        action_dicts = [
            {
                "type": action.type.value,
                "target": action.target,
                "indirect_target": action.indirect_target,
                "manner": action.manner,
            }
            for action in parsed_intent.actions
        ]

        return {
            "parsed_actions": action_dicts,
            "ambient_flavor": parsed_intent.ambient_flavor,
        }

    except Exception as e:
        return {
            "parsed_actions": [],
            "ambient_flavor": None,
            "errors": [f"Failed to parse intent: {str(e)}"],
        }


def create_parse_intent_node(
    db: Session,
    game_session: GameSession,
) -> Callable[[GameState], Coroutine[Any, Any, dict[str, Any]]]:
    """Create a parse intent node with bound dependencies.

    Args:
        db: Database session.
        game_session: Current game session.

    Returns:
        Async node function that parses player input.
    """

    async def node(state: GameState) -> dict[str, Any]:
        """Parse player input into structured actions.

        Args:
            state: Current game state.

        Returns:
            Partial state update with parsed_actions and ambient_flavor.
        """
        player_input = state.get("player_input", "")
        if not player_input:
            return {
                "parsed_actions": [],
                "ambient_flavor": None,
            }

        parser = IntentParser(db, game_session)

        try:
            parsed_intent = await parser.parse(
                input_text=player_input,
                player_location=state.get("player_location", ""),
            )

            action_dicts = [
                {
                    "type": action.type.value,
                    "target": action.target,
                    "indirect_target": action.indirect_target,
                    "manner": action.manner,
                }
                for action in parsed_intent.actions
            ]

            return {
                "parsed_actions": action_dicts,
                "ambient_flavor": parsed_intent.ambient_flavor,
            }

        except Exception as e:
            return {
                "parsed_actions": [],
                "ambient_flavor": None,
                "errors": [f"Failed to parse intent: {str(e)}"],
            }

    return node
